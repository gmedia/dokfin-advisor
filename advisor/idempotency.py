"""Result cache per job_id (Redis) for idempotent NATS processing."""

from __future__ import annotations

import contextlib
import json
import os
from typing import Any

RESULT_PREFIX = "advisor:result:v1:"
LOCK_PREFIX = "advisor:lock:v1:"


def _enabled() -> bool:
    if os.environ.get("ADVISOR_IDEMPOTENCY_ENABLED", "1") != "1":
        return False
    url = os.environ.get("REDIS_URL", "")
    return bool(url.strip())


def result_key(job_id: str) -> str:
    return f"{RESULT_PREFIX}{job_id}"


def lock_key(job_id: str) -> str:
    return f"{LOCK_PREFIX}{job_id}"


def connect_redis() -> Any | None:
    if not _enabled():
        return None
    try:
        import redis

        return redis.Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)
    except Exception:  # noqa: BLE001
        return None


def cache_ttl_seconds() -> int:
    return int(os.environ.get("ADVISOR_IDEMPOTENCY_TTL_S", str(7 * 24 * 3600)))


def lock_ttl_seconds() -> int:
    return int(os.environ.get("ADVISOR_IDEMPOTENCY_LOCK_TTL_S", "900"))


def get_cached_result(client: Any, job_id: str) -> dict[str, Any] | None:
    if client is None:
        return None
    raw = client.get(result_key(job_id))
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def set_cached_result(client: Any, job_id: str, result: dict[str, Any]) -> None:
    if client is None:
        return
    ttl = cache_ttl_seconds()
    payload = json.dumps(result, ensure_ascii=False)
    client.setex(result_key(job_id), ttl, payload)


def try_acquire_lock(client: Any, job_id: str) -> bool:
    """Return True if this worker owns the lock or idempotency disabled."""
    if client is None:
        return True
    return bool(client.set(lock_key(job_id), "1", nx=True, ex=lock_ttl_seconds()))


def release_lock(client: Any, job_id: str) -> None:
    if client is None:
        return
    with contextlib.suppress(Exception):
        client.delete(lock_key(job_id))
