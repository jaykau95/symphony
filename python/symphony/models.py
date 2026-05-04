from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass
class BlockerRef:
    id: Optional[str] = None
    identifier: Optional[str] = None
    state: Optional[str] = None


@dataclass
class Issue:
    id: str
    identifier: str
    title: str
    description: Optional[str] = None
    priority: Optional[int] = None
    state: str = ""
    branch_name: Optional[str] = None
    url: Optional[str] = None
    labels: list[str] = field(default_factory=list)
    blocked_by: list[BlockerRef] = field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_template_dict(self) -> dict:
        return {
            "id": self.id,
            "identifier": self.identifier,
            "title": self.title,
            "description": self.description,
            "priority": self.priority,
            "state": self.state,
            "branch_name": self.branch_name,
            "url": self.url,
            "labels": self.labels,
            "blocked_by": [
                {"id": b.id, "identifier": b.identifier, "state": b.state}
                for b in self.blocked_by
            ],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class WorkflowDefinition:
    config: dict
    prompt_template: str


@dataclass
class LiveSession:
    session_id: str = ""
    thread_id: str = ""
    turn_id: str = ""
    codex_app_server_pid: Optional[str] = None
    last_event: Optional[str] = None
    last_event_time: Optional[datetime] = None
    last_message: Optional[str] = None
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    last_reported_input_tokens: int = 0
    last_reported_output_tokens: int = 0
    last_reported_total_tokens: int = 0
    turn_count: int = 0


@dataclass
class RunningEntry:
    issue: Issue
    task: Any  # asyncio.Task
    started_at: datetime
    attempt: Optional[int]
    workspace_path: str
    live_session: Optional[LiveSession] = None


@dataclass
class RetryEntry:
    issue_id: str
    identifier: str
    attempt: int
    due_at: float  # monotonic time
    error: Optional[str] = None
    handle: Any = None  # asyncio.TimerHandle


@dataclass
class CodexTotals:
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    ended_session_seconds: float = 0.0


@dataclass
class OrchestratorState:
    running: dict = field(default_factory=dict)        # issue_id -> RunningEntry
    claimed: set = field(default_factory=set)          # issue_ids
    retry_attempts: dict = field(default_factory=dict) # issue_id -> RetryEntry
    completed: set = field(default_factory=set)        # issue_ids (bookkeeping only)
    codex_totals: CodexTotals = field(default_factory=CodexTotals)
    rate_limits: Optional[dict] = None
