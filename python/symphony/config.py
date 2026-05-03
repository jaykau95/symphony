"""Typed configuration layer resolved from WorkflowDefinition + environment."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .models import WorkflowDefinition


class ConfigError(Exception):
    pass


@dataclass
class TrackerConfig:
    kind: str = "linear"
    endpoint: str = "https://api.linear.app/graphql"
    api_key: Optional[str] = None
    project_slug: Optional[str] = None
    active_states: list[str] = field(default_factory=lambda: ["Todo", "In Progress"])
    terminal_states: list[str] = field(
        default_factory=lambda: ["Closed", "Cancelled", "Canceled", "Duplicate", "Done"]
    )


@dataclass
class PollingConfig:
    interval_ms: int = 30_000


@dataclass
class WorkspaceConfig:
    root: Path = field(default_factory=lambda: Path(tempfile.gettempdir()) / "symphony_workspaces")


@dataclass
class HooksConfig:
    after_create: Optional[str] = None
    before_run: Optional[str] = None
    after_run: Optional[str] = None
    before_remove: Optional[str] = None
    timeout_ms: int = 60_000


@dataclass
class AgentConfig:
    max_concurrent_agents: int = 10
    max_turns: int = 20
    max_retry_backoff_ms: int = 300_000
    max_concurrent_agents_by_state: dict[str, int] = field(default_factory=dict)


@dataclass
class CodexConfig:
    command: str = "codex app-server"
    approval_policy: object = field(
        default_factory=lambda: {
            "reject": {"sandbox_approval": True, "rules": True, "mcp_elicitations": True}
        }
    )
    thread_sandbox: str = "workspace-write"
    turn_sandbox_policy: Optional[dict] = None
    turn_timeout_ms: int = 3_600_000
    read_timeout_ms: int = 5_000
    stall_timeout_ms: int = 300_000


@dataclass
class SymphonyConfig:
    tracker: TrackerConfig = field(default_factory=TrackerConfig)
    polling: PollingConfig = field(default_factory=PollingConfig)
    workspace: WorkspaceConfig = field(default_factory=WorkspaceConfig)
    hooks: HooksConfig = field(default_factory=HooksConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)
    codex: CodexConfig = field(default_factory=CodexConfig)


# ---------------------------------------------------------------------------
# Resolution helpers
# ---------------------------------------------------------------------------

def _resolve_env(value: str) -> Optional[str]:
    """If value starts with $, resolve it as an env var (return None if empty)."""
    if isinstance(value, str) and value.startswith("$"):
        resolved = os.environ.get(value[1:], "")
        return resolved or None
    return value


def _expand_path(value: str, workflow_dir: Path) -> Path:
    """Expand ~ and leading $VAR, then resolve relative to workflow_dir."""
    if isinstance(value, str) and value.startswith("$"):
        var_name = value[1:]
        value = os.environ.get(var_name, value)
    expanded = os.path.expanduser(str(value))
    p = Path(expanded)
    if not p.is_absolute():
        p = workflow_dir / p
    return p.resolve()


def _safe_int(raw, default: int) -> int:
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def from_workflow(workflow_def: WorkflowDefinition, workflow_path: Path) -> SymphonyConfig:
    """Build a SymphonyConfig from a parsed WorkflowDefinition."""
    raw = workflow_def.config
    workflow_dir = workflow_path.parent
    cfg = SymphonyConfig()

    # tracker
    tr = raw.get("tracker") or {}
    cfg.tracker.kind = tr.get("kind", "linear")
    cfg.tracker.endpoint = tr.get("endpoint", "https://api.linear.app/graphql")

    raw_key = tr.get("api_key", "$LINEAR_API_KEY")
    cfg.tracker.api_key = _resolve_env(str(raw_key)) if isinstance(raw_key, str) else None
    if not cfg.tracker.api_key and cfg.tracker.kind == "linear":
        cfg.tracker.api_key = os.environ.get("LINEAR_API_KEY") or None

    cfg.tracker.project_slug = tr.get("project_slug")
    if isinstance(tr.get("active_states"), list):
        cfg.tracker.active_states = list(tr["active_states"])
    if isinstance(tr.get("terminal_states"), list):
        cfg.tracker.terminal_states = list(tr["terminal_states"])

    # polling
    pol = raw.get("polling") or {}
    cfg.polling.interval_ms = _safe_int(pol.get("interval_ms", 30_000), 30_000)

    # workspace
    ws = raw.get("workspace") or {}
    if "root" in ws:
        cfg.workspace.root = _expand_path(str(ws["root"]), workflow_dir)

    # hooks
    hk = raw.get("hooks") or {}
    cfg.hooks.after_create = hk.get("after_create")
    cfg.hooks.before_run = hk.get("before_run")
    cfg.hooks.after_run = hk.get("after_run")
    cfg.hooks.before_remove = hk.get("before_remove")
    cfg.hooks.timeout_ms = _safe_int(hk.get("timeout_ms", 60_000), 60_000)

    # agent
    ag = raw.get("agent") or {}
    cfg.agent.max_concurrent_agents = _safe_int(ag.get("max_concurrent_agents", 10), 10)
    max_turns = _safe_int(ag.get("max_turns", 20), 20)
    cfg.agent.max_turns = max_turns if max_turns > 0 else 20
    cfg.agent.max_retry_backoff_ms = _safe_int(ag.get("max_retry_backoff_ms", 300_000), 300_000)
    by_state_raw = ag.get("max_concurrent_agents_by_state") or {}
    by_state: dict[str, int] = {}
    if isinstance(by_state_raw, dict):
        for state, limit in by_state_raw.items():
            try:
                v = int(limit)
                if v > 0:
                    by_state[str(state).lower()] = v
            except (TypeError, ValueError):
                pass
    cfg.agent.max_concurrent_agents_by_state = by_state

    # codex
    cx = raw.get("codex") or {}
    if "command" in cx:
        cfg.codex.command = str(cx["command"])
    if "approval_policy" in cx:
        cfg.codex.approval_policy = cx["approval_policy"]
    if "thread_sandbox" in cx:
        cfg.codex.thread_sandbox = str(cx["thread_sandbox"])
    if "turn_sandbox_policy" in cx:
        cfg.codex.turn_sandbox_policy = cx["turn_sandbox_policy"]
    cfg.codex.turn_timeout_ms = _safe_int(cx.get("turn_timeout_ms", 3_600_000), 3_600_000)
    cfg.codex.read_timeout_ms = _safe_int(cx.get("read_timeout_ms", 5_000), 5_000)
    cfg.codex.stall_timeout_ms = _safe_int(cx.get("stall_timeout_ms", 300_000), 300_000)

    return cfg


def validate(cfg: SymphonyConfig) -> list[str]:
    """Return a list of validation error strings; empty means valid."""
    errors: list[str] = []
    if not cfg.tracker.kind:
        errors.append("tracker.kind is required")
    elif cfg.tracker.kind != "linear":
        errors.append(f"tracker.kind={cfg.tracker.kind!r} is not supported (only 'linear')")
    if not cfg.tracker.api_key:
        errors.append(
            "tracker.api_key is missing — set LINEAR_API_KEY env var or tracker.api_key in WORKFLOW.md"
        )
    if cfg.tracker.kind == "linear" and not cfg.tracker.project_slug:
        errors.append("tracker.project_slug is required when tracker.kind=linear")
    if not cfg.codex.command:
        errors.append("codex.command must be non-empty")
    return errors
