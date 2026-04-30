"""text_from_message_content handles Gemini list parts."""

from __future__ import annotations

from advisor.llm_response_text import text_from_message_content


def test_plain_string() -> None:
    assert text_from_message_content('{"x": 1}') == '{"x": 1}'


def test_gemini_style_list_skips_thinking() -> None:
    parts = [
        {"type": "thinking", "thinking": "..."},
        {"type": "text", "text": '{"ok": true}'},
    ]
    assert text_from_message_content(parts) == '{"ok": true}'


def test_list_of_strings_joined() -> None:
    assert text_from_message_content(["a", "b"]) == "ab"
