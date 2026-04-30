"""Parse JSON-only LLM responses (strip fences, reject non-objects)."""

from __future__ import annotations

import ast
import json
import re
from typing import Any

_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*\n?(.*?)\n?```\s*$", re.DOTALL | re.IGNORECASE)


def _extract_first_json_object(text: str) -> str:
    """Ambil substring dari `{` pertama sampai `}` penutup yang seimbang (abaikan dalam string)."""
    start = text.find("{")
    if start < 0:
        msg = "no JSON object found in LLM response"
        raise ValueError(msg)

    depth = 0
    in_string = False
    escape = False
    string_quote: str | None = None

    for i in range(start, len(text)):
        c = text[i]
        if escape:
            escape = False
            continue
        if in_string and string_quote == '"':
            if c == "\\":
                escape = True
            elif c == '"':
                in_string = False
                string_quote = None
            continue
        if in_string and string_quote == "'":
            if c == "\\":
                escape = True
            elif c == "'":
                in_string = False
                string_quote = None
            continue
        if not in_string:
            if c in ('"', "'"):
                in_string = True
                string_quote = c
                continue
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]

    msg = "unbalanced braces in JSON candidate"
    raise ValueError(msg)


def _loads_object(blob: str) -> dict[str, Any]:
    blob = blob.strip()
    try:
        data = json.loads(blob)
    except json.JSONDecodeError:
        try:
            obj = ast.literal_eval(blob)
        except (ValueError, SyntaxError) as e:
            msg = f"invalid JSON: {e}"
            raise ValueError(msg) from e
        if not isinstance(obj, dict):
            msg = "JSON root must be an object"
            raise ValueError(msg) from None
        data = obj
    if not isinstance(data, dict):
        msg = "JSON root must be an object"
        raise ValueError(msg)
    return data


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
        return _loads_object(raw)
    except ValueError:
        pass

    try:
        candidate = _extract_first_json_object(raw)
        return _loads_object(candidate)
    except ValueError as e:
        msg = f"invalid JSON: {e}"
        raise ValueError(msg) from e
