"""parse_llm_json tolerates preamble and markdown fences."""

from __future__ import annotations

import pytest
from advisor.json_utils import parse_llm_json


def test_strip_markdown_fence() -> None:
    raw = """```json
{"a": 1}
```"""
    assert parse_llm_json(raw) == {"a": 1}


def test_extract_object_with_preamble() -> None:
    raw = 'Sure! Here is the result:\n{"x": "y", "n": 2}\nHope this helps.'
    assert parse_llm_json(raw) == {"x": "y", "n": 2}


def test_nested_braces_in_string() -> None:
    raw = r'{"k": "literal { not end", "b": 1}'
    assert parse_llm_json(raw)["b"] == 1


def test_reject_non_object_root() -> None:
    with pytest.raises(ValueError, match="object"):
        parse_llm_json("[1,2]")


def test_python_single_quote_dict_literal() -> None:
    raw = "{'a': 1, 'b': 'hello'}"
    assert parse_llm_json(raw) == {"a": 1, "b": "hello"}
