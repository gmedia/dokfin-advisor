"""Normalize LangChain message content to plain text (Gemini multi-part / thinking blocks)."""

from __future__ import annotations

from typing import Any


def text_from_message_content(content: Any) -> str:
    """Ambil teks yang dipakai untuk parse JSON; abaikan blok non-teks (thinking, dll.)."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks: list[str] = []
        for item in content:
            if isinstance(item, str):
                chunks.append(item)
            elif isinstance(item, dict) and item.get("type") == "text":
                chunks.append(str(item.get("text", "")))
        return "".join(chunks)
    return str(content)
