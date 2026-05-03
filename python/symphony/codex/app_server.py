"""Codex app-server JSON-RPC 2.0 client over stdio.

Protocol flow:
  1. Launch `bash -lc <codex.command>` in workspace directory.
  2. Send `initialize` → receive response → send `initialized` notification.
  3. Send `thread/start` → receive thread_id.
  4. For each turn: send `turn/start` → receive turn_id → stream until done.
  5. Handle approvals, tool calls, and user-input requests in the stream.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from ..config import SymphonyConfig
from ..models import Issue

logger = logging.getLogger(__name__)

_MAX_LINE_BYTES = 10 * 1024 * 1024  # 10 MB subprocess line buffer
_MAX_LOG_BYTES = 1_000
_NON_INTERACTIVE_ANSWER = "This is a non-interactive session. Operator input is unavailable."

# Fixed request IDs for the sequential startup handshake
_INIT_ID = 1
_THREAD_START_ID = 2
_TURN_START_ID = 3


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class CodexError(Exception):
    pass


class TurnTimeout(CodexError):
    pass


class TurnFailed(CodexError):
    def __init__(self, kind: str, detail=None):
        self.kind = kind
        self.detail = detail
        super().__init__(f"{kind}: {detail}")


class PortExit(CodexError):
    def __init__(self, code):
        self.code = code
        super().__init__(f"port_exit: {code}")


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------

class CodexSession:
    """Wraps a single Codex app-server subprocess and implements the JSON-RPC protocol."""

    def __init__(
        self,
        proc: asyncio.subprocess.Process,
        config: SymphonyConfig,
        workspace_path: Path,
        linear_client=None,
    ):
        self._proc = proc
        self._config = config
        self._workspace = str(workspace_path)
        self._linear_client = linear_client
        self._pid: Optional[str] = str(proc.pid) if proc.pid else None
        self._thread_id: Optional[str] = None

    @property
    def pid(self) -> Optional[str]:
        return self._pid

    @property
    def thread_id(self) -> Optional[str]:
        return self._thread_id

    # ------------------------------------------------------------------
    # Startup sequence
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Send initialize handshake and wait for server acknowledgement."""
        await self._send({
            "method": "initialize",
            "id": _INIT_ID,
            "params": {
                "capabilities": {"experimentalApi": True},
                "clientInfo": {
                    "name": "symphony-orchestrator",
                    "title": "Symphony Orchestrator",
                    "version": "0.1.0",
                },
            },
        })
        await self._await_response(_INIT_ID)
        await self._send({"method": "initialized", "params": {}})

    async def start_thread(self) -> str:
        """Send thread/start and return the thread_id."""
        cfg = self._config.codex
        params: dict = {
            "approvalPolicy": cfg.approval_policy,
            "sandbox": cfg.thread_sandbox,
            "cwd": self._workspace,
            "dynamicTools": self._tool_specs(),
        }
        if cfg.turn_sandbox_policy is not None:
            params["sandboxPolicy"] = cfg.turn_sandbox_policy

        await self._send({"method": "thread/start", "id": _THREAD_START_ID, "params": params})
        result = await self._await_response(_THREAD_START_ID)
        thread = result.get("thread") or {}
        thread_id = thread.get("id")
        if not isinstance(thread_id, str) or not thread_id:
            raise CodexError(f"invalid_thread_payload: {result!r}")
        self._thread_id = thread_id
        return thread_id

    async def start_turn(self, prompt: str, issue: Issue) -> str:
        """Send turn/start and return the turn_id."""
        if not self._thread_id:
            raise CodexError("thread not started")

        cfg = self._config.codex
        params: dict = {
            "threadId": self._thread_id,
            "input": [{"type": "text", "text": prompt}],
            "cwd": self._workspace,
            "title": f"{issue.identifier}: {issue.title}",
            "approvalPolicy": cfg.approval_policy,
        }
        if cfg.turn_sandbox_policy is not None:
            params["sandboxPolicy"] = cfg.turn_sandbox_policy

        await self._send({"method": "turn/start", "id": _TURN_START_ID, "params": params})
        result = await self._await_response(_TURN_START_ID)
        turn = result.get("turn") or {}
        turn_id = turn.get("id")
        if not isinstance(turn_id, str) or not turn_id:
            raise CodexError(f"invalid_turn_payload: {result!r}")
        return turn_id

    # ------------------------------------------------------------------
    # Turn streaming
    # ------------------------------------------------------------------

    async def stream_turn(self, on_message: Callable, timeout_ms: int) -> None:
        """Read agent events until the turn completes, fails, or times out."""
        auto_approve = self._config.codex.approval_policy == "never"
        loop = asyncio.get_event_loop()
        deadline = loop.time() + timeout_ms / 1000

        while True:
            remaining = deadline - loop.time()
            if remaining <= 0:
                raise TurnTimeout()

            try:
                line_bytes = await asyncio.wait_for(
                    self._proc.stdout.readline(), timeout=remaining
                )
            except asyncio.TimeoutError:
                raise TurnTimeout()

            if not line_bytes:
                raise PortExit(self._proc.returncode)

            text = line_bytes.decode("utf-8", errors="replace").strip()
            if not text:
                continue

            try:
                msg = json.loads(text)
            except json.JSONDecodeError:
                _log_non_json(text)
                continue

            if not isinstance(msg, dict):
                continue

            done = await self._handle_stream_msg(msg, text, on_message, auto_approve)
            if done:
                return

    # ------------------------------------------------------------------
    # Stream message dispatch
    # ------------------------------------------------------------------

    async def _handle_stream_msg(
        self, msg: dict, raw: str, on_message: Callable, auto_approve: bool
    ) -> bool:
        """Return True when the turn is finished."""
        method = msg.get("method")

        if method == "turn/completed":
            _emit(on_message, "turn_completed", {"payload": msg, "raw": raw}, self._pid)
            return True

        if method == "turn/failed":
            _emit(on_message, "turn_failed", {"payload": msg, "raw": raw, "details": msg.get("params")}, self._pid)
            raise TurnFailed("turn_failed", msg.get("params"))

        if method == "turn/cancelled":
            _emit(on_message, "turn_cancelled", {"payload": msg, "raw": raw, "details": msg.get("params")}, self._pid)
            raise TurnFailed("turn_cancelled", msg.get("params"))

        if method in ("item/commandExecution/requestApproval", "item/fileChange/requestApproval"):
            await self._handle_approval(msg, raw, on_message, auto_approve, "acceptForSession")
            return False

        if method in ("execCommandApproval", "applyPatchApproval"):
            await self._handle_approval(msg, raw, on_message, auto_approve, "approved_for_session")
            return False

        if method == "item/tool/call":
            await self._handle_tool_call(msg, raw, on_message)
            return False

        if method == "item/tool/requestUserInput":
            await self._handle_user_input(msg, raw, on_message, auto_approve)
            return False

        if _is_input_required(method, msg):
            _emit(on_message, "turn_input_required", {"payload": msg, "raw": raw}, self._pid)
            raise TurnFailed("turn_input_required", msg)

        _emit(on_message, "notification", {"payload": msg, "raw": raw}, self._pid)
        logger.debug(f"codex_notification method={method!r}")
        return False

    # ------------------------------------------------------------------
    # Approval handling
    # ------------------------------------------------------------------

    async def _handle_approval(
        self,
        msg: dict,
        raw: str,
        on_message: Callable,
        auto_approve: bool,
        decision: str,
    ) -> None:
        msg_id = msg.get("id")
        if auto_approve and msg_id is not None:
            await self._send({"id": msg_id, "result": {"decision": decision}})
            _emit(on_message, "approval_auto_approved",
                  {"payload": msg, "raw": raw, "decision": decision}, self._pid)
        else:
            _emit(on_message, "approval_required", {"payload": msg, "raw": raw}, self._pid)
            raise TurnFailed("approval_required", msg)

    # ------------------------------------------------------------------
    # Tool call handling
    # ------------------------------------------------------------------

    async def _handle_tool_call(self, msg: dict, raw: str, on_message: Callable) -> None:
        msg_id = msg.get("id")
        params = msg.get("params") or {}
        tool_name = _tool_name(params)
        arguments = params.get("arguments") or {}

        result = await self._execute_tool(tool_name, arguments)
        if msg_id is not None:
            await self._send({"id": msg_id, "result": result})

        if result.get("success"):
            event = "tool_call_completed"
        elif not tool_name:
            event = "unsupported_tool_call"
        else:
            event = "tool_call_failed"
        _emit(on_message, event, {"payload": msg, "raw": raw}, self._pid)

    async def _execute_tool(self, tool_name: Optional[str], arguments: dict) -> dict:
        if tool_name == "linear_graphql":
            return await self._execute_linear_graphql(arguments)
        return _tool_error(f"Unsupported tool: {tool_name!r}")

    async def _execute_linear_graphql(self, arguments: dict) -> dict:
        if self._linear_client is None:
            return _tool_error("linear_graphql tool unavailable: no Linear client configured")

        if isinstance(arguments, str):
            query = arguments.strip()
            variables: dict = {}
        else:
            query = (arguments.get("query") or "").strip()
            variables = arguments.get("variables") or {}

        if not query:
            return _tool_error("query must be a non-empty string")
        if not isinstance(variables, dict):
            return _tool_error("variables must be a JSON object")

        try:
            body = await self._linear_client.graphql_raw(query, variables)
        except Exception as exc:
            return _tool_error(f"Linear request failed: {exc}")

        output = json.dumps(body, indent=2)
        success = "errors" not in body
        return {
            "success": success,
            "output": output,
            "contentItems": [{"type": "inputText", "text": output}],
        }

    # ------------------------------------------------------------------
    # User-input handling
    # ------------------------------------------------------------------

    async def _handle_user_input(
        self, msg: dict, raw: str, on_message: Callable, auto_approve: bool
    ) -> None:
        msg_id = msg.get("id")
        params = msg.get("params") or {}
        questions = params.get("questions") or []

        if auto_approve:
            answers = _build_approval_answers(questions)
            if answers is not None and msg_id is not None:
                await self._send({"id": msg_id, "result": {"answers": answers}})
                _emit(on_message, "approval_auto_approved",
                      {"payload": msg, "raw": raw, "decision": "Approve this Session"}, self._pid)
                return

        answers = _build_unavailable_answers(questions)
        if answers is not None and msg_id is not None:
            await self._send({"id": msg_id, "result": {"answers": answers}})
            _emit(on_message, "tool_input_auto_answered",
                  {"payload": msg, "raw": raw, "answer": _NON_INTERACTIVE_ANSWER}, self._pid)
        else:
            _emit(on_message, "turn_input_required", {"payload": msg, "raw": raw}, self._pid)
            raise TurnFailed("turn_input_required", msg)

    # ------------------------------------------------------------------
    # Tool specs advertised to Codex
    # ------------------------------------------------------------------

    def _tool_specs(self) -> list:
        if self._linear_client is None:
            return []
        return [
            {
                "name": "linear_graphql",
                "description": "Execute a raw GraphQL query or mutation against Linear.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "A single GraphQL operation document.",
                        },
                        "variables": {
                            "type": "object",
                            "description": "Optional GraphQL variables object.",
                        },
                    },
                    "required": ["query"],
                },
            }
        ]

    # ------------------------------------------------------------------
    # Transport
    # ------------------------------------------------------------------

    async def _await_response(self, request_id: int) -> dict:
        """Read lines until we get the response matching request_id."""
        timeout_ms = self._config.codex.read_timeout_ms
        loop = asyncio.get_event_loop()
        deadline = loop.time() + timeout_ms / 1000

        while True:
            remaining = deadline - loop.time()
            if remaining <= 0:
                raise CodexError("response_timeout")

            try:
                line_bytes = await asyncio.wait_for(
                    self._proc.stdout.readline(), timeout=remaining
                )
            except asyncio.TimeoutError:
                raise CodexError("response_timeout")

            if not line_bytes:
                raise PortExit(self._proc.returncode)

            text = line_bytes.decode("utf-8", errors="replace").strip()
            if not text:
                continue

            try:
                msg = json.loads(text)
            except json.JSONDecodeError:
                _log_non_json(text)
                continue

            if not isinstance(msg, dict):
                continue

            if msg.get("id") == request_id:
                if "error" in msg:
                    raise CodexError(f"response_error: {msg['error']!r}")
                return msg.get("result") or {}

            logger.debug(
                f"ignoring_message_while_awaiting_response method={msg.get('method')!r} id={msg.get('id')!r}"
            )

    async def _send(self, msg: dict) -> None:
        data = (json.dumps(msg) + "\n").encode("utf-8")
        self._proc.stdin.write(data)
        await self._proc.stdin.drain()

    # ------------------------------------------------------------------
    # Teardown
    # ------------------------------------------------------------------

    async def stop(self) -> None:
        """Terminate the subprocess gracefully."""
        try:
            if self._proc.returncode is None:
                self._proc.terminate()
                try:
                    await asyncio.wait_for(self._proc.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    self._proc.kill()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

async def start_session(
    workspace_path: Path,
    config: SymphonyConfig,
    linear_client=None,
) -> CodexSession:
    """Launch the Codex subprocess and return an initialized CodexSession."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "bash",
            "-lc",
            config.codex.command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(workspace_path),
            limit=_MAX_LINE_BYTES,
        )
    except FileNotFoundError as exc:
        raise CodexError(f"codex_not_found: {exc}") from exc
    except Exception as exc:
        raise CodexError(f"codex_launch_failed: {exc}") from exc

    asyncio.create_task(_drain_stderr(proc))

    return CodexSession(proc, config, workspace_path, linear_client=linear_client)


async def _drain_stderr(proc: asyncio.subprocess.Process) -> None:
    """Read and log stderr output from the Codex subprocess."""
    try:
        while True:
            line = await proc.stderr.readline()
            if not line:
                break
            text = line.decode("utf-8", errors="replace").strip()
            if not text:
                continue
            if re.search(r"\b(error|warn|warning|failed|fatal|panic|exception)\b", text, re.I):
                logger.warning(f"codex_stderr: {text}")
            else:
                logger.debug(f"codex_stderr: {text}")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tool_name(params: dict) -> Optional[str]:
    for key in ("tool", "name"):
        val = params.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return None


def _tool_error(msg: str) -> dict:
    return {
        "success": False,
        "output": msg,
        "contentItems": [{"type": "inputText", "text": msg}],
    }


def _emit(on_message: Callable, event: str, details: dict, pid: Optional[str]) -> None:
    payload = {"event": event, "timestamp": _utcnow(), **details}
    if pid:
        payload["codex_app_server_pid"] = pid
    try:
        on_message(payload)
    except Exception:
        pass


def _is_input_required(method: str, msg: dict) -> bool:
    _input_methods = {
        "turn/input_required", "turn/needs_input", "turn/need_input",
        "turn/request_input", "turn/request_response", "turn/provide_input",
        "turn/approval_required",
    }
    if method in _input_methods:
        return True
    params = msg.get("params") or {}
    for m in (msg, params):
        if not isinstance(m, dict):
            continue
        if any(m.get(k) for k in ("requiresInput", "needsInput", "input_required", "inputRequired")):
            return True
        if m.get("type") in ("input_required", "needs_input"):
            return True
    return False


def _log_non_json(text: str) -> None:
    truncated = text[:_MAX_LOG_BYTES]
    if re.search(r"\b(error|warn|warning|failed|fatal|panic|exception)\b", truncated, re.I):
        logger.warning(f"codex_non_json_output: {truncated}")
    else:
        logger.debug(f"codex_non_json_output: {truncated}")


def _build_approval_answers(questions: list) -> Optional[dict]:
    answers: dict = {}
    for q in questions:
        if not isinstance(q, dict):
            return None
        qid = q.get("id")
        if not isinstance(qid, str):
            return None
        label = _find_approval_label(q.get("options") or [])
        if not label:
            return None
        answers[qid] = {"answers": [label]}
    return answers or None


def _build_unavailable_answers(questions: list) -> Optional[dict]:
    answers: dict = {}
    for q in questions:
        if not isinstance(q, dict):
            return None
        qid = q.get("id")
        if not isinstance(qid, str):
            return None
        answers[qid] = {"answers": [_NON_INTERACTIVE_ANSWER]}
    return answers or None


def _find_approval_label(options: list) -> Optional[str]:
    labels = [
        o["label"]
        for o in options
        if isinstance(o, dict) and isinstance(o.get("label"), str)
    ]
    for preferred in ("Approve this Session", "Approve Once"):
        if preferred in labels:
            return preferred
    for label in labels:
        nl = label.strip().lower()
        if nl.startswith("approve") or nl.startswith("allow"):
            return label
    return None
