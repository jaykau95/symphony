"""Minimal async HTTP status server — no extra dependencies required.

Serves:
  GET /          → HTML status dashboard
  GET /api/status → JSON snapshot of orchestrator state
  GET /healthz   → 200 OK (for Railway health checks)
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from .orchestrator import Orchestrator

logger = logging.getLogger(__name__)

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Symphony Status</title>
  <meta http-equiv="refresh" content="15">
  <style>
    body {{ font-family: monospace; background: #0f0f0f; color: #e0e0e0; padding: 2rem; }}
    h1 {{ color: #7c6af7; margin-bottom: 0.25rem; }}
    .sub {{ color: #666; font-size: 0.85rem; margin-bottom: 2rem; }}
    .section {{ margin-bottom: 2rem; }}
    h2 {{ color: #aaa; font-size: 0.9rem; text-transform: uppercase; letter-spacing: 0.1em; border-bottom: 1px solid #333; padding-bottom: 0.25rem; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; }}
    th {{ text-align: left; color: #888; padding: 0.35rem 0.5rem; }}
    td {{ padding: 0.35rem 0.5rem; border-top: 1px solid #222; }}
    .badge {{ display: inline-block; padding: 0.1rem 0.5rem; border-radius: 3px; font-size: 0.75rem; }}
    .running {{ background: #1a3a1a; color: #4caf50; }}
    .retrying {{ background: #3a2a0a; color: #ff9800; }}
    .idle {{ color: #555; }}
    .stat {{ display: inline-block; margin-right: 2rem; }}
    .stat-val {{ font-size: 1.4rem; color: #7c6af7; }}
    .stat-lbl {{ font-size: 0.75rem; color: #666; }}
  </style>
</head>
<body>
  <h1>⚡ Symphony</h1>
  <div class="sub">Auto-refreshes every 15s &nbsp;·&nbsp; {timestamp}</div>

  <div class="section">
    <div class="stat"><div class="stat-val">{running_count}</div><div class="stat-lbl">Running</div></div>
    <div class="stat"><div class="stat-val">{retrying_count}</div><div class="stat-lbl">Retrying</div></div>
    <div class="stat"><div class="stat-val">{total_tokens}</div><div class="stat-lbl">Total tokens</div></div>
    <div class="stat"><div class="stat-val">{runtime_hours}</div><div class="stat-lbl">Agent hours</div></div>
  </div>

  {running_section}
  {retrying_section}
</body>
</html>
"""

_RUNNING_ROW = """\
<tr>
  <td><span class="badge running">running</span></td>
  <td>{identifier}</td>
  <td>{state}</td>
  <td>{turn_count}</td>
  <td>{last_event}</td>
  <td>{elapsed}</td>
</tr>"""

_RETRY_ROW = """\
<tr>
  <td><span class="badge retrying">retrying</span></td>
  <td>{identifier}</td>
  <td>attempt {attempt}</td>
  <td colspan="2">{error}</td>
  <td>in {due_in:.0f}s</td>
</tr>"""


def _render_html(snapshot: dict) -> str:
    running = snapshot.get("running") or []
    retrying = snapshot.get("retrying") or []
    totals = snapshot.get("codex_totals") or {}

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    total_tokens = f"{totals.get('total_tokens', 0):,}"
    secs = totals.get("seconds_running", 0)
    runtime_hours = f"{secs / 3600:.1f}h"

    if running:
        rows = ""
        for r in running:
            rows += _RUNNING_ROW.format(
                identifier=r.get("issue_identifier", ""),
                state=r.get("state", ""),
                turn_count=r.get("turn_count", 0),
                last_event=r.get("last_event") or "—",
                elapsed=_elapsed(r.get("started_at")),
            )
        running_section = (
            '<div class="section"><h2>Active agents</h2>'
            '<table><tr><th></th><th>Issue</th><th>State</th>'
            '<th>Turns</th><th>Last event</th><th>Elapsed</th></tr>'
            + rows + "</table></div>"
        )
    else:
        running_section = '<div class="section"><h2>Active agents</h2><p class="idle">No agents running.</p></div>'

    if retrying:
        rows = ""
        for r in retrying:
            rows += _RETRY_ROW.format(
                identifier=r.get("issue_identifier", ""),
                attempt=r.get("attempt", ""),
                error=(r.get("error") or "")[:80],
                due_in=r.get("due_in_seconds", 0),
            )
        retrying_section = (
            '<div class="section"><h2>Retry queue</h2>'
            '<table><tr><th></th><th>Issue</th><th>Attempt</th>'
            '<th colspan="2">Error</th><th>Due</th></tr>'
            + rows + "</table></div>"
        )
    else:
        retrying_section = ""

    return _HTML_TEMPLATE.format(
        timestamp=now,
        running_count=len(running),
        retrying_count=len(retrying),
        total_tokens=total_tokens,
        runtime_hours=runtime_hours,
        running_section=running_section,
        retrying_section=retrying_section,
    )


def _elapsed(started_at: str | None) -> str:
    if not started_at:
        return "—"
    try:
        dt = datetime.fromisoformat(started_at)
        secs = int((datetime.now(timezone.utc) - dt).total_seconds())
        if secs < 60:
            return f"{secs}s"
        if secs < 3600:
            return f"{secs // 60}m {secs % 60}s"
        return f"{secs // 3600}h {(secs % 3600) // 60}m"
    except Exception:
        return "—"


async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter, get_snapshot: Callable) -> None:
    try:
        data = await asyncio.wait_for(reader.read(1024), timeout=5.0)
        request = data.decode("utf-8", errors="replace")
        path = _parse_path(request)

        if path == "/healthz":
            body = b"OK"
            writer.write(
                b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n"
                b"Content-Length: 2\r\nConnection: close\r\n\r\nOK"
            )
        elif path == "/api/status":
            snapshot = get_snapshot()
            body = json.dumps(snapshot, default=str, indent=2).encode("utf-8")
            writer.write(
                f"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
                f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode()
                + body
            )
        else:
            snapshot = get_snapshot()
            html = _render_html(snapshot).encode("utf-8")
            writer.write(
                f"HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\n"
                f"Content-Length: {len(html)}\r\nConnection: close\r\n\r\n".encode()
                + html
            )

        await writer.drain()
    except Exception as exc:
        logger.debug(f"status_server_request_error: {exc}")
    finally:
        writer.close()


def _parse_path(request: str) -> str:
    try:
        first_line = request.split("\r\n")[0]
        return first_line.split(" ")[1]
    except Exception:
        return "/"


async def serve(port: int, get_snapshot: Callable) -> None:
    """Start the status HTTP server on the given port."""
    server = await asyncio.start_server(
        lambda r, w: handle(r, w, get_snapshot),
        host="0.0.0.0",
        port=port,
    )
    logger.info(f"status_server_started port={port}")
    async with server:
        await server.serve_forever()
