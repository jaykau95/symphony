"""Structured logging setup for Symphony."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional


def configure(
    level: str = "INFO",
    log_file: Optional[Path] = None,
) -> None:
    """Configure root logger with a structured format.

    Emits key=value style lines so operators can grep for specific fields.
    """
    fmt = "%(asctime)s level=%(levelname)s module=%(name)s %(message)s"
    datefmt = "%Y-%m-%dT%H:%M:%S"

    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]

    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format=fmt,
        datefmt=datefmt,
        handlers=handlers,
        force=True,
    )
    # Quiet noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
