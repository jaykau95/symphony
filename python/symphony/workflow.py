"""Load and parse WORKFLOW.md files (YAML front matter + Markdown body)."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from .models import WorkflowDefinition

_FRONT_MATTER_RE = re.compile(r"^---\r?\n(.*?)^---\r?\n", re.MULTILINE | re.DOTALL)


class WorkflowError(Exception):
    pass


def load(path: Path) -> WorkflowDefinition:
    """Load and parse a WORKFLOW.md file. Raises WorkflowError on any failure."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise WorkflowError(f"missing_workflow_file: {exc}") from exc

    match = _FRONT_MATTER_RE.match(text)
    if match:
        front_matter_str = match.group(1)
        body = text[match.end():]
        try:
            config = yaml.safe_load(front_matter_str)
        except yaml.YAMLError as exc:
            raise WorkflowError(f"workflow_parse_error: {exc}") from exc
        if not isinstance(config, dict):
            raise WorkflowError("workflow_front_matter_not_a_map")
    else:
        config = {}
        body = text

    return WorkflowDefinition(config=config, prompt_template=body.strip())
