"""Per-issue workspace lifecycle: create, hooks, safety checks, removal."""

from __future__ import annotations

import asyncio
import logging
import re
import shutil
from pathlib import Path
from typing import Optional

from .config import SymphonyConfig
from .models import Issue

logger = logging.getLogger(__name__)

_SAFE_KEY_RE = re.compile(r"[^A-Za-z0-9._-]")


class WorkspaceError(Exception):
    pass


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def sanitize_key(identifier: str) -> str:
    """Replace unsafe characters with underscores for use as a directory name."""
    return _SAFE_KEY_RE.sub("_", identifier)


def issue_path(identifier: str, root: Path) -> Path:
    return root / sanitize_key(identifier)


def validate_safety(ws_path: Path, root: Path) -> None:
    """Raise WorkspaceError if ws_path is not strictly inside root."""
    try:
        ws_resolved = ws_path.resolve()
        root_resolved = root.resolve()
    except OSError as exc:
        raise WorkspaceError(f"invalid_workspace_cwd: path_unreadable: {exc}") from exc

    if ws_resolved == root_resolved:
        raise WorkspaceError(
            f"invalid_workspace_cwd: workspace_root coincides with root: {ws_resolved}"
        )

    root_prefix = str(root_resolved) + "/"
    if not (str(ws_resolved) + "/").startswith(root_prefix):
        raise WorkspaceError(
            f"invalid_workspace_cwd: outside_workspace_root: {ws_resolved} not inside {root_resolved}"
        )


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

async def create_for_issue(issue: Issue, cfg: SymphonyConfig) -> tuple[Path, bool]:
    """Ensure workspace exists. Returns (path, created_now).

    If newly created and after_create hook is configured, the hook is run.
    Hook failure removes the partially-created directory and re-raises.
    """
    root = cfg.workspace.root
    root.mkdir(parents=True, exist_ok=True)

    ws = issue_path(issue.identifier, root)
    validate_safety(ws, root)

    created_now = False
    if not ws.exists():
        ws.mkdir(parents=True, exist_ok=True)
        created_now = True
        logger.info(
            f"workspace_created path={ws} issue_id={issue.id} issue_identifier={issue.identifier}"
        )

    if created_now and cfg.hooks.after_create:
        logger.info(
            f"running_hook hook=after_create issue_id={issue.id} issue_identifier={issue.identifier}"
        )
        try:
            await run_hook(cfg.hooks.after_create, ws, cfg.hooks.timeout_ms)
        except Exception as exc:
            logger.error(
                f"hook_failed hook=after_create issue_id={issue.id} "
                f"issue_identifier={issue.identifier}: {exc}"
            )
            try:
                if ws.exists():
                    shutil.rmtree(ws)
            except OSError:
                pass
            raise WorkspaceError(f"after_create hook failed: {exc}") from exc

    return ws, created_now


async def run_hook(script: str, cwd: Path, timeout_ms: int) -> None:
    """Run a shell script in cwd with a timeout. Raises WorkspaceError on failure."""
    timeout_sec = timeout_ms / 1000
    try:
        proc = await asyncio.create_subprocess_exec(
            "bash",
            "-lc",
            script,
            cwd=str(cwd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        try:
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout_sec)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            raise WorkspaceError(f"hook timed out after {timeout_ms}ms")

        if proc.returncode != 0:
            output = (stdout or b"").decode("utf-8", errors="replace").strip()
            raise WorkspaceError(
                f"hook exited with code {proc.returncode}: {output[:500]}"
            )
    except WorkspaceError:
        raise
    except Exception as exc:
        raise WorkspaceError(f"hook error: {exc}") from exc


async def remove_for_issue(issue: Issue, cfg: SymphonyConfig) -> None:
    """Remove workspace directory for a terminal issue."""
    ws = issue_path(issue.identifier, cfg.workspace.root)
    if not ws.exists():
        return

    if cfg.hooks.before_remove:
        logger.info(
            f"running_hook hook=before_remove issue_id={issue.id} issue_identifier={issue.identifier}"
        )
        try:
            await run_hook(cfg.hooks.before_remove, ws, cfg.hooks.timeout_ms)
        except Exception as exc:
            logger.warning(
                f"hook_failed hook=before_remove issue_id={issue.id} "
                f"issue_identifier={issue.identifier}: {exc} (ignored)"
            )

    try:
        shutil.rmtree(ws)
        logger.info(
            f"workspace_removed path={ws} issue_id={issue.id} issue_identifier={issue.identifier}"
        )
    except OSError as exc:
        logger.warning(
            f"workspace_remove_failed path={ws} issue_id={issue.id} "
            f"issue_identifier={issue.identifier}: {exc}"
        )
