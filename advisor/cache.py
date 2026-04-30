"""Tavily result cache: key = MD5(keyword.lower().strip()), TTL 24h (PRD §5.1)."""

from __future__ import annotations

import hashlib
import time
from typing import Any


def cache_key_for_keyword(keyword: str) -> str:
    normalized = keyword.lower().strip()
    return hashlib.md5(normalized.encode("utf-8")).hexdigest()


class MemoryTTLCache:
    """In-memory TTL cache (Sprint 1). Redis dapat mengganti backend di Sprint 2."""

    def __init__(self, ttl_seconds: int = 24 * 3600) -> None:
        self._ttl = ttl_seconds
        self._data: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        now = time.monotonic()
        item = self._data.get(key)
        if item is None:
            return None
        expires_at, value = item
        if now > expires_at:
            del self._data[key]
            return None
        return value

    def set(self, key: str, value: Any) -> None:
        self._data[key] = (time.monotonic() + self._ttl, value)
