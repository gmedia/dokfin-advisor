"""LLM JSON retries (PRD: max 2 retries => up to 3 attempts). Node B uses tenacity in search.py."""

from __future__ import annotations

from collections.abc import Callable

from pydantic import ValidationError

# PRD §9.1: max retry 2 → total attempts = 3
MAX_LLM_ATTEMPTS = 3


def call_with_json_retries[T](fn: Callable[[], T], *, max_attempts: int = MAX_LLM_ATTEMPTS) -> T:
    """Call `fn` until it succeeds or `max_attempts` exhausted. `fn` should raise on bad output."""
    last_exc: BaseException | None = None
    for _ in range(max_attempts):
        try:
            return fn()
        except (ValueError, TypeError, KeyError, ValidationError) as e:
            last_exc = e
            continue
    msg = f"exhausted after {max_attempts} attempts"
    if last_exc:
        raise RuntimeError(msg) from last_exc
    raise RuntimeError(msg)
