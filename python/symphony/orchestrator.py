"""Orchestrator: poll loop, dispatch, concurrency control, retries, reconciliation.

State invariants (all mutations happen on the single asyncio thread):
- running[issue_id]  -> task is alive for that issue
- claimed            -> issue_id is in running OR retry_attempts
- retry_attempts     -> a call_later handle is pending for that issue_id
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from . import workspace as ws_mgr
from .agent_runner import run as run_agent, AgentRunError
from .config import SymphonyConfig, from_workflow, validate
from .linear.client import LinearClient, LinearClientError
from .models import (
    CodexTotals,
    Issue,
    LiveSession,
    OrchestratorState,
    RetryEntry,
    RunningEntry,
)
from .workflow import WorkflowDefinition, WorkflowError, load as load_workflow

logger = logging.getLogger(__name__)

_CONTINUATION_RETRY_MS = 1_000  # short delay after a clean worker exit


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

class Orchestrator:
    def __init__(self, workflow_path: Path):
        self._workflow_path = workflow_path
        self._workflow_mtime: Optional[float] = None
        self._workflow: Optional[WorkflowDefinition] = None
        self._config: Optional[SymphonyConfig] = None
        self._linear: Optional[LinearClient] = None
        self._state = OrchestratorState()
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def run(self) -> None:
        self._loop = asyncio.get_event_loop()

        # Initial load — fail fast if invalid
        self._reload_workflow(initial=True)

        errors = validate(self._config)  # type: ignore[arg-type]
        if errors:
            for err in errors:
                logger.error(f"startup_config_error: {err}")
            raise RuntimeError(f"Config validation failed at startup: {errors}")

        await self._startup_cleanup()
        logger.info("orchestrator_started")

        await self._tick()  # immediate first tick

        while True:
            poll_ms = self._config.polling.interval_ms if self._config else 30_000
            await asyncio.sleep(poll_ms / 1000)
            self._maybe_reload_workflow()
            await self._tick()

    # ------------------------------------------------------------------
    # Workflow loading
    # ------------------------------------------------------------------

    def _reload_workflow(self, initial: bool = False) -> None:
        try:
            mtime = self._workflow_path.stat().st_mtime
        except OSError:
            mtime = None

        try:
            wf = load_workflow(self._workflow_path)
        except WorkflowError as exc:
            if not initial and self._workflow is not None:
                logger.error(f"workflow_reload_failed keeping_last_good: {exc}")
                return
            raise

        self._workflow = wf
        self._workflow_mtime = mtime
        self._config = from_workflow(wf, self._workflow_path)

        if self._config.tracker.api_key:
            self._linear = LinearClient(
                api_key=self._config.tracker.api_key,
                endpoint=self._config.tracker.endpoint,
            )
        else:
            self._linear = None

        logger.info(f"workflow_loaded path={self._workflow_path}")

    def _maybe_reload_workflow(self) -> None:
        try:
            mtime = self._workflow_path.stat().st_mtime
        except OSError:
            return
        if mtime != self._workflow_mtime:
            logger.info(f"workflow_file_changed reloading path={self._workflow_path}")
            self._reload_workflow()

    # ------------------------------------------------------------------
    # Startup cleanup
    # ------------------------------------------------------------------

    async def _startup_cleanup(self) -> None:
        if not self._config or not self._linear:
            return
        logger.info("startup_cleanup_started")
        try:
            terminal_issues = await self._linear.fetch_issues_by_states(
                self._config.tracker.project_slug,  # type: ignore[arg-type]
                self._config.tracker.terminal_states,
            )
            for issue in terminal_issues:
                try:
                    await ws_mgr.remove_for_issue(issue, self._config)
                except Exception as exc:
                    logger.warning(
                        f"startup_cleanup_remove_failed issue_id={issue.id} "
                        f"issue_identifier={issue.identifier}: {exc}"
                    )
        except Exception as exc:
            logger.warning(f"startup_cleanup_fetch_failed (continuing): {exc}")
        logger.info("startup_cleanup_done")

    # ------------------------------------------------------------------
    # Poll tick
    # ------------------------------------------------------------------

    async def _tick(self) -> None:
        await self._reconcile()

        if not self._config:
            logger.error("dispatch_skipped: config not loaded")
            return

        errors = validate(self._config)
        if errors:
            for err in errors:
                logger.error(f"dispatch_skipped config_error={err!r}")
            return

        if not self._linear:
            logger.error("dispatch_skipped: no Linear client")
            return

        try:
            candidates = await self._linear.fetch_candidate_issues(
                self._config.tracker.project_slug,  # type: ignore[arg-type]
                self._config.tracker.active_states,
            )
        except LinearClientError as exc:
            logger.error(f"candidate_fetch_failed: {exc}")
            return

        for issue in _sort_candidates(candidates):
            if not self._can_dispatch(issue):
                continue
            self._dispatch(issue, attempt=None)

    # ------------------------------------------------------------------
    # Reconciliation
    # ------------------------------------------------------------------

    async def _reconcile(self) -> None:
        if not self._config:
            return

        now = datetime.now(timezone.utc)
        stall_ms = self._config.codex.stall_timeout_ms

        # Stall detection
        stalled = []
        for issue_id, entry in list(self._state.running.items()):
            if stall_ms > 0:
                ls = entry.live_session
                ref = (ls.last_event_time if ls and ls.last_event_time else None) or entry.started_at
                elapsed_ms = (now - ref).total_seconds() * 1000
                if elapsed_ms > stall_ms:
                    logger.warning(
                        f"stall_detected issue_id={issue_id} "
                        f"issue_identifier={entry.issue.identifier} elapsed_ms={elapsed_ms:.0f}"
                    )
                    stalled.append((issue_id, entry.issue.identifier))

        for issue_id, identifier in stalled:
            self._cancel_task(issue_id)
            # Done callback will NOT schedule retry for cancelled tasks,
            # so we schedule one explicitly here before the callback fires.
            self._schedule_retry(issue_id, identifier, attempt=1,
                                  delay_ms=_CONTINUATION_RETRY_MS, error="stall_timeout")

        # State refresh
        running_ids = list(self._state.running.keys())
        if not running_ids or not self._linear:
            return

        try:
            refreshed = await self._linear.fetch_issue_states_by_ids(running_ids)
        except Exception as exc:
            logger.error(f"reconcile_state_refresh_failed (keeping workers running): {exc}")
            return

        refreshed_by_id = {i.id: i for i in refreshed}
        terminal = {s.lower() for s in self._config.tracker.terminal_states}
        active = {s.lower() for s in self._config.tracker.active_states}

        for issue_id in list(self._state.running.keys()):
            fresh = refreshed_by_id.get(issue_id)
            if not fresh:
                continue
            state_lower = fresh.state.lower()
            if state_lower in terminal:
                logger.info(
                    f"reconcile_terminal issue_id={issue_id} "
                    f"issue_identifier={fresh.identifier} state={fresh.state}"
                )
                self._cancel_task(issue_id)
                try:
                    await ws_mgr.remove_for_issue(fresh, self._config)
                except Exception as exc:
                    logger.warning(f"workspace_remove_failed issue_id={issue_id}: {exc}")
            elif state_lower in active:
                if issue_id in self._state.running:
                    self._state.running[issue_id].issue = fresh
            else:
                logger.info(
                    f"reconcile_non_active issue_id={issue_id} "
                    f"issue_identifier={fresh.identifier} state={fresh.state}"
                )
                self._cancel_task(issue_id)

    # ------------------------------------------------------------------
    # Eligibility check
    # ------------------------------------------------------------------

    def _can_dispatch(self, issue: Issue) -> bool:
        if not (issue.id and issue.identifier and issue.title and issue.state):
            return False

        cfg = self._config
        active_lower = {s.lower() for s in cfg.tracker.active_states}  # type: ignore[union-attr]
        terminal_lower = {s.lower() for s in cfg.tracker.terminal_states}  # type: ignore[union-attr]
        state_lower = issue.state.lower()

        if state_lower not in active_lower or state_lower in terminal_lower:
            return False
        if issue.id in self._state.running or issue.id in self._state.claimed:
            return False

        # Global concurrency
        if len(self._state.running) >= cfg.agent.max_concurrent_agents:  # type: ignore[union-attr]
            return False

        # Per-state concurrency
        by_state = cfg.agent.max_concurrent_agents_by_state  # type: ignore[union-attr]
        if state_lower in by_state:
            count = sum(
                1 for e in self._state.running.values()
                if e.issue.state.lower() == state_lower
            )
            if count >= by_state[state_lower]:
                return False

        # Blocker rule for "todo" state
        if state_lower == "todo":
            for blocker in issue.blocked_by:
                blocker_state = (blocker.state or "").lower()
                if blocker_state not in terminal_lower:
                    return False

        return True

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    def _dispatch(self, issue: Issue, attempt: Optional[int]) -> None:
        self._state.claimed.add(issue.id)

        task = asyncio.create_task(
            self._agent_task(issue, attempt),
            name=f"agent-{issue.identifier}",
        )
        task.add_done_callback(lambda t: self._on_task_done(issue.id, issue.identifier, t))

        self._state.running[issue.id] = RunningEntry(
            issue=issue,
            task=task,
            started_at=datetime.now(timezone.utc),
            attempt=attempt,
            workspace_path=str(ws_mgr.issue_path(issue.identifier, self._config.workspace.root)),  # type: ignore[union-attr]
        )
        logger.info(
            f"dispatched issue_id={issue.id} issue_identifier={issue.identifier} "
            f"state={issue.state} attempt={attempt}"
        )

    # ------------------------------------------------------------------
    # Agent task wrapper
    # ------------------------------------------------------------------

    async def _agent_task(self, issue: Issue, attempt: Optional[int]) -> None:
        await run_agent(
            issue=issue,
            config=self._config,  # type: ignore[arg-type]
            prompt_template=self._workflow.prompt_template if self._workflow else "",
            on_update=self._make_update_cb(issue.id),
            attempt=attempt,
            issue_state_fetcher=self._fetch_states_for_runner,
            linear_client=self._linear,
        )

    async def _fetch_states_for_runner(self, issue_ids: list) -> list:
        if not self._linear:
            return []
        return await self._linear.fetch_issue_states_by_ids(issue_ids)

    # ------------------------------------------------------------------
    # Task done callback
    # ------------------------------------------------------------------

    def _on_task_done(self, issue_id: str, identifier: str, task: asyncio.Task) -> None:
        entry = self._state.running.pop(issue_id, None)

        # Accumulate runtime seconds
        if entry:
            duration = (datetime.now(timezone.utc) - entry.started_at).total_seconds()
            self._state.codex_totals.ended_session_seconds += duration

        if task.cancelled():
            # Task was cancelled by reconciliation which may have already
            # scheduled a retry. Only clear claim if no retry is pending.
            if issue_id not in self._state.retry_attempts:
                self._state.claimed.discard(issue_id)
            return

        exc = None
        try:
            exc = task.exception()
        except (asyncio.CancelledError, Exception):
            pass

        if exc is not None:
            next_attempt = (entry.attempt or 0) + 1 if entry else 1
            delay_ms = min(
                10_000 * (2 ** (next_attempt - 1)),
                (self._config.agent.max_retry_backoff_ms if self._config else 300_000),
            )
            logger.info(
                f"scheduling_failure_retry issue_id={issue_id} "
                f"issue_identifier={identifier} attempt={next_attempt} delay_ms={delay_ms} "
                f"error={exc!r}"
            )
            self._schedule_retry(issue_id, identifier, next_attempt, delay_ms, str(exc))
        else:
            logger.info(
                f"scheduling_continuation issue_id={issue_id} issue_identifier={identifier}"
            )
            self._schedule_retry(issue_id, identifier, attempt=1,
                                  delay_ms=_CONTINUATION_RETRY_MS)

    # ------------------------------------------------------------------
    # Retry scheduling
    # ------------------------------------------------------------------

    def _schedule_retry(
        self,
        issue_id: str,
        identifier: str,
        attempt: int,
        delay_ms: int,
        error: Optional[str] = None,
    ) -> None:
        # Cancel existing retry timer
        existing = self._state.retry_attempts.get(issue_id)
        if existing and existing.handle:
            existing.handle.cancel()

        due_at = time.monotonic() + delay_ms / 1000
        handle = self._loop.call_later(  # type: ignore[union-attr]
            delay_ms / 1000,
            lambda: self._loop.create_task(self._handle_retry(issue_id)),  # type: ignore[union-attr]
        )
        self._state.retry_attempts[issue_id] = RetryEntry(
            issue_id=issue_id,
            identifier=identifier,
            attempt=attempt,
            due_at=due_at,
            error=error,
            handle=handle,
        )
        self._state.claimed.add(issue_id)

    async def _handle_retry(self, issue_id: str) -> None:
        retry = self._state.retry_attempts.pop(issue_id, None)
        if not retry:
            return

        if not self._config or not self._linear:
            self._state.claimed.discard(issue_id)
            return

        try:
            candidates = await self._linear.fetch_candidate_issues(
                self._config.tracker.project_slug,  # type: ignore[arg-type]
                self._config.tracker.active_states,
            )
        except Exception as exc:
            logger.error(f"retry_fetch_failed issue_id={issue_id}: {exc}")
            next_attempt = retry.attempt + 1
            self._schedule_retry(issue_id, retry.identifier, next_attempt, 10_000, str(exc))
            return

        issue = next((i for i in candidates if i.id == issue_id), None)
        if issue is None:
            logger.info(f"retry_issue_not_found releasing_claim issue_id={issue_id}")
            self._state.claimed.discard(issue_id)
            return

        if len(self._state.running) >= self._config.agent.max_concurrent_agents:
            logger.info(f"retry_no_slots requeuing issue_id={issue_id}")
            self._schedule_retry(
                issue_id, retry.identifier, retry.attempt, 30_000,
                "no available orchestrator slots"
            )
            return

        self._dispatch(issue, attempt=retry.attempt)

    # ------------------------------------------------------------------
    # Task cancellation
    # ------------------------------------------------------------------

    def _cancel_task(self, issue_id: str) -> None:
        """Cancel the running task. The done callback handles claim/state cleanup."""
        entry = self._state.running.get(issue_id)
        if entry and not entry.task.done():
            entry.task.cancel()

    # ------------------------------------------------------------------
    # Update callback (called from agent runner)
    # ------------------------------------------------------------------

    def _make_update_cb(self, issue_id: str) -> Callable:
        def callback(msg: dict) -> None:
            entry = self._state.running.get(issue_id)
            if not entry:
                return

            event = msg.get("event")
            now = datetime.now(timezone.utc)

            if event == "session_started":
                entry.live_session = LiveSession(
                    session_id=msg.get("session_id", ""),
                    thread_id=msg.get("thread_id", ""),
                    turn_id=msg.get("turn_id", ""),
                    codex_app_server_pid=msg.get("codex_app_server_pid"),
                    last_event=str(event),
                    last_event_time=now,
                    turn_count=1,
                )
            elif entry.live_session:
                ls = entry.live_session
                ls.last_event = str(event) if event else None
                ls.last_event_time = now
                _update_tokens(ls, msg.get("usage") or {})

            if isinstance(msg.get("rate_limits"), dict):
                self._state.rate_limits = msg["rate_limits"]

        return callback

    # ------------------------------------------------------------------
    # Runtime snapshot (for dashboard / status surface)
    # ------------------------------------------------------------------

    def snapshot(self) -> dict:
        now = datetime.now(timezone.utc)
        running_rows = []
        active_seconds = 0.0
        for issue_id, entry in self._state.running.items():
            elapsed = (now - entry.started_at).total_seconds()
            active_seconds += elapsed
            ls = entry.live_session
            row: dict = {
                "issue_id": issue_id,
                "issue_identifier": entry.issue.identifier,
                "issue_title": entry.issue.title,
                "state": entry.issue.state,
                "started_at": entry.started_at.isoformat(),
                "attempt": entry.attempt,
                "workspace_path": entry.workspace_path,
                "turn_count": ls.turn_count if ls else 0,
                "last_event": ls.last_event if ls else None,
            }
            running_rows.append(row)

        retrying_rows = [
            {
                "issue_id": r.issue_id,
                "issue_identifier": r.identifier,
                "attempt": r.attempt,
                "error": r.error,
                "due_in_seconds": max(0.0, r.due_at - time.monotonic()),
            }
            for r in self._state.retry_attempts.values()
        ]

        totals = self._state.codex_totals
        return {
            "running": running_rows,
            "retrying": retrying_rows,
            "codex_totals": {
                "input_tokens": totals.input_tokens,
                "output_tokens": totals.output_tokens,
                "total_tokens": totals.total_tokens,
                "seconds_running": totals.ended_session_seconds + active_seconds,
            },
            "rate_limits": self._state.rate_limits,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sort_candidates(issues: list[Issue]) -> list[Issue]:
    _MAX = 99_999

    def key(issue: Issue):
        priority = issue.priority if isinstance(issue.priority, int) else _MAX
        created = issue.created_at.timestamp() if issue.created_at else float("inf")
        return (priority, created, issue.identifier)

    return sorted(issues, key=key)


def _update_tokens(ls: LiveSession, usage: dict) -> None:
    input_tok = _coerce_int(usage.get("inputTokens") or usage.get("input_tokens"))
    output_tok = _coerce_int(usage.get("outputTokens") or usage.get("output_tokens"))
    total_tok = _coerce_int(usage.get("totalTokens") or usage.get("total_tokens"))
    if input_tok is not None:
        ls.input_tokens = input_tok
    if output_tok is not None:
        ls.output_tokens = output_tok
    if total_tok is not None:
        ls.total_tokens = total_tok


def _coerce_int(val) -> Optional[int]:
    if isinstance(val, int):
        return val
    try:
        return int(val)
    except (TypeError, ValueError):
        return None
