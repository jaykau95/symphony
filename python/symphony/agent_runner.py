"""AgentRunner: workspace preparation → Codex session → multi-turn loop."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Callable, Optional

from . import workspace as ws_mgr
from .codex.app_server import CodexError, TurnFailed, TurnTimeout, PortExit, start_session
from .config import SymphonyConfig
from .linear.client import LinearClient
from .models import Issue
from .prompt import build as build_prompt, PromptError

logger = logging.getLogger(__name__)

_CONTINUATION_PROMPT = """\
Continuation guidance:

- The previous Codex turn completed normally, but the Linear issue is still in an active state.
- Resume from the current workspace and workpad state instead of restarting from scratch.
- The original task instructions and prior turn context are already present in this thread; \
do not restate them before acting.
- Focus on the remaining ticket work and do not end the turn while the issue stays active \
unless you are truly blocked.
"""


class AgentRunError(Exception):
    pass


async def run(
    issue: Issue,
    config: SymphonyConfig,
    prompt_template: str,
    on_update: Callable,
    attempt: Optional[int] = None,
    issue_state_fetcher: Optional[Callable] = None,
    linear_client: Optional[LinearClient] = None,
) -> None:
    """Run the full agent lifecycle for one issue: workspace → hooks → Codex turns.

    Raises AgentRunError on unrecoverable failure. CancelledError propagates as-is
    so the orchestrator can detect task cancellation.
    """
    logger.info(
        f"starting_agent_run issue_id={issue.id} issue_identifier={issue.identifier}"
    )

    # --- workspace ---
    try:
        ws_path, _ = await ws_mgr.create_for_issue(issue, config)
    except Exception as exc:
        raise AgentRunError(f"workspace_failed: {exc}") from exc

    on_update({"event": "worker_runtime_info", "workspace_path": str(ws_path)})

    # --- before_run hook ---
    if config.hooks.before_run:
        logger.info(
            f"running_hook hook=before_run issue_id={issue.id} issue_identifier={issue.identifier}"
        )
        try:
            await ws_mgr.run_hook(config.hooks.before_run, ws_path, config.hooks.timeout_ms)
        except Exception as exc:
            raise AgentRunError(f"before_run hook failed: {exc}") from exc

    # --- Codex turns ---
    try:
        await _run_turns(issue, config, prompt_template, ws_path, on_update,
                         attempt, issue_state_fetcher, linear_client)
    finally:
        # after_run hook — failure is logged and ignored
        if config.hooks.after_run and ws_path.exists():
            logger.info(
                f"running_hook hook=after_run issue_id={issue.id} issue_identifier={issue.identifier}"
            )
            try:
                await ws_mgr.run_hook(config.hooks.after_run, ws_path, config.hooks.timeout_ms)
            except Exception as exc:
                logger.warning(
                    f"hook_failed hook=after_run issue_id={issue.id} "
                    f"issue_identifier={issue.identifier}: {exc}"
                )


async def _run_turns(
    issue: Issue,
    config: SymphonyConfig,
    prompt_template: str,
    ws_path: Path,
    on_update: Callable,
    attempt: Optional[int],
    issue_state_fetcher: Optional[Callable],
    linear_client: Optional[LinearClient],
) -> None:
    active_states = {s.lower() for s in config.tracker.active_states}
    max_turns = config.agent.max_turns

    session = await start_session(ws_path, config, linear_client=linear_client)
    try:
        await session.initialize()
        thread_id = await session.start_thread()

        for turn_number in range(1, max_turns + 1):
            # Build prompt: full template on first turn, continuation guidance after
            if turn_number == 1:
                try:
                    prompt = build_prompt(prompt_template, issue, attempt)
                except PromptError as exc:
                    raise AgentRunError(f"prompt_error: {exc}") from exc
            else:
                prompt = _continuation_prompt(turn_number, max_turns)

            turn_id = await session.start_turn(prompt, issue)
            session_id = f"{thread_id}-{turn_id}"

            on_update({
                "event": "session_started",
                "session_id": session_id,
                "thread_id": thread_id,
                "turn_id": turn_id,
                "codex_app_server_pid": session.pid,
            })
            logger.info(
                f"codex_turn_started issue_id={issue.id} issue_identifier={issue.identifier} "
                f"session_id={session_id} turn={turn_number}/{max_turns}"
            )

            await session.stream_turn(on_update, config.codex.turn_timeout_ms)

            logger.info(
                f"codex_turn_completed issue_id={issue.id} issue_identifier={issue.identifier} "
                f"session_id={session_id} turn={turn_number}/{max_turns}"
            )

            # Check whether we should continue on the same thread
            if issue_state_fetcher is None:
                break

            refreshed = await _refresh_issue(issue, issue_state_fetcher)
            if refreshed is None or refreshed.state.lower() not in active_states:
                logger.info(
                    f"issue_no_longer_active issue_id={issue.id} issue_identifier={issue.identifier}"
                )
                break

            issue = refreshed

            if turn_number >= max_turns:
                logger.info(
                    f"max_turns_reached issue_id={issue.id} "
                    f"issue_identifier={issue.identifier} max_turns={max_turns}"
                )
                break

            logger.info(
                f"continuing_to_next_turn issue_id={issue.id} "
                f"issue_identifier={issue.identifier} turn={turn_number}/{max_turns}"
            )
    finally:
        await session.stop()


def _continuation_prompt(turn_number: int, max_turns: int) -> str:
    return (
        f"Continuation guidance:\n\n"
        f"- The previous Codex turn completed normally, but the Linear issue is still active.\n"
        f"- This is continuation turn #{turn_number} of {max_turns}.\n"
        f"- Resume from the current workspace and workpad state instead of restarting.\n"
        f"- Do not restate previous context; focus on remaining work.\n"
    )


async def _refresh_issue(issue: Issue, fetcher: Callable) -> Optional[Issue]:
    try:
        issues = await fetcher([issue.id])
        return issues[0] if issues else None
    except Exception as exc:
        logger.error(
            f"issue_state_fetch_failed issue_id={issue.id} "
            f"issue_identifier={issue.identifier}: {exc}"
        )
        return None
