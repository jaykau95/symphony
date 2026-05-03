"""CLI entrypoint for Symphony Python.

Usage:
    symphony [WORKFLOW_PATH] [--logs-root DIR] [--log-level LEVEL]

Arguments:
    WORKFLOW_PATH   Path to WORKFLOW.md (default: ./WORKFLOW.md)

Options:
    --logs-root DIR     Directory for log files (default: ./log)
    --log-level LEVEL   Logging level: DEBUG|INFO|WARNING|ERROR (default: INFO)
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import sys
from pathlib import Path

from . import log as log_setup
from .orchestrator import Orchestrator

logger = logging.getLogger(__name__)


def _parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="symphony",
        description="Symphony: autonomous agent orchestrator for Linear issues.",
    )
    parser.add_argument(
        "workflow",
        nargs="?",
        default="WORKFLOW.md",
        metavar="WORKFLOW_PATH",
        help="Path to WORKFLOW.md (default: ./WORKFLOW.md)",
    )
    parser.add_argument(
        "--logs-root",
        default="./log",
        metavar="DIR",
        help="Directory for log files (default: ./log)",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        metavar="LEVEL",
        help="Logging level (default: INFO)",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = _parse_args(argv)

    workflow_path = Path(args.workflow).expanduser().resolve()
    logs_root = Path(args.logs_root).expanduser().resolve()
    log_file = logs_root / "symphony.log"

    log_setup.configure(level=args.log_level, log_file=log_file)

    if not workflow_path.exists():
        logger.error(f"missing_workflow_file path={workflow_path}")
        print(f"Error: WORKFLOW.md not found at {workflow_path}", file=sys.stderr)
        return 1

    orchestrator = Orchestrator(workflow_path)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Graceful shutdown on SIGINT / SIGTERM
    def _shutdown(signame: str):
        logger.info(f"received_signal signal={signame} initiating_shutdown")
        for task in asyncio.all_tasks(loop):
            task.cancel()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda s=sig.name: _shutdown(s))

    logger.info(f"symphony_starting workflow={workflow_path}")
    try:
        loop.run_until_complete(orchestrator.run())
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("symphony_stopped")
    except Exception as exc:
        logger.error(f"symphony_fatal_error: {exc}")
        return 1
    finally:
        # Cancel remaining tasks
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()
        if pending:
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        loop.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
