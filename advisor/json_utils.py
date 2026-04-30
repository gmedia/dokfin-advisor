"""Parse JSON-only LLM responses (strip fences, reject non-objects)."""

from __future__ import annotations

import json
import re
from typing import Any

_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*\n?(.*?)\n?```\s*$", re.DOTALL | re.IGNORECASE)


def parse_llm_json(text: str) -> dict[str, Any]:
    """Return a JSON object dict from model output. Raises ValueError if invalid."""
    raw = (text or "").strip()
    if not raw:
        msg = "empty LLM response"
        raise ValueError(msg)

    m = _FENCE_RE.match(raw)
    if m:
        raw = m.group(1).strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        msg = f"invalid JSON: {e}"
        raise ValueError(msg) from e

    if not isinstance(data, dict):
        msg = "JSON root must be an object"
        raise ValueError(msg)

    return data
