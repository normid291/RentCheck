"""Token-usage accumulation for one analysis request.

The model endpoint is called by the document classifier, the jurisdiction check
and the per-clause verifier. They all share `ai_inference._post_with_retries`,
which records any `usage` object it receives here. `_run_pipeline` starts and
ends one accumulator, so the admin event can report the whole run's token totals
without threading a return value through every model call.
"""
from __future__ import annotations

from contextvars import ContextVar, Token
from typing import Literal, TypedDict


class Usage(TypedDict):
    model_name: str | None
    input_tokens: int | None
    output_tokens: int | None


_current: ContextVar[Usage | None] = ContextVar("tenura_ai_usage", default=None)


def start() -> Token[Usage | None]:
    """Start a fresh accumulator for this request's AI calls."""
    return _current.set(
        {"model_name": None, "input_tokens": None, "output_tokens": None}
    )


def finish(token: Token[Usage | None]) -> Usage | None:
    """Return the accumulated usage and restore the previous context."""
    usage = _current.get()
    _current.reset(token)
    return usage


def _add(usage: Usage, key: Literal["input_tokens", "output_tokens"], value) -> None:
    if value is None:
        return
    try:
        n = int(value)
    except (TypeError, ValueError):
        return
    if n < 0:
        return
    usage[key] = (usage[key] or 0) + n


def record(model_name: str | None, input_tokens, output_tokens) -> None:
    """Add one model response's usage. Never raises."""
    usage = _current.get()
    if usage is None:
        return
    if model_name and not usage["model_name"]:
        usage["model_name"] = str(model_name)[:120]
    _add(usage, "input_tokens", input_tokens)
    _add(usage, "output_tokens", output_tokens)
