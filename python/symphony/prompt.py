"""Render per-issue prompts from Jinja2/Liquid-compatible WORKFLOW.md templates."""

from __future__ import annotations

from typing import Optional

from jinja2 import Environment, StrictUndefined, TemplateSyntaxError, UndefinedError

from .models import Issue

_DEFAULT_PROMPT = "You are working on an issue from Linear."


class PromptError(Exception):
    pass


def build(template_str: str, issue: Issue, attempt: Optional[int] = None) -> str:
    """Render template_str with issue context. Raises PromptError on failure."""
    if not template_str:
        return _DEFAULT_PROMPT

    try:
        env = Environment(undefined=StrictUndefined, keep_trailing_newline=True)
        template = env.from_string(template_str)
    except TemplateSyntaxError as exc:
        raise PromptError(f"template_parse_error: {exc}") from exc

    try:
        return template.render(issue=issue.to_template_dict(), attempt=attempt)
    except UndefinedError as exc:
        raise PromptError(f"template_render_error: {exc}") from exc
    except Exception as exc:
        raise PromptError(f"template_render_error: {exc}") from exc
