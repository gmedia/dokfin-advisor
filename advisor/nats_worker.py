"""NATS JetStream consumer: jobs in, results (+ optional DLQ) out."""

from __future__ import annotations

import asyncio
import json
import os
import time
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import nats
import structlog
from nats.js import api
from nats.js.errors import FetchTimeoutError, NotFoundError

from advisor.graph import AdvisorDeps, build_default_deps, run_advisor
from advisor.idempotency import (
    connect_redis,
    get_cached_result,
    release_lock,
    set_cached_result,
    try_acquire_lock,
)
from advisor.logging_setup import get_logger, log_node_timing
from advisor.schemas.dlq import DlqMessage
from advisor.schemas.input import JobPayload
from advisor.schemas.output import ErrorCode

_LOG = get_logger(__name__)


def _env(name: str, default: str) -> str:
    v = os.environ.get(name)
    return v if v is not None and v != "" else default


def _result_needs_dlq(result: dict[str, Any]) -> bool:
    if result.get("status") != "FAILED":
        return False
    code = result.get("error_code")
    return code != ErrorCode.PAYLOAD_INVALID.value


def attach_processing_time(result: dict[str, Any], seconds: float) -> dict[str, Any]:
    out = dict(result)
    out["processing_time_seconds"] = round(seconds, 3)
    if out.get("token_usage") is None:
        out["token_usage"] = None
    if out.get("status") == "DONE" and out.get("estimated_cost_idr") is None:
        out["estimated_cost_idr"] = None
    return out


async def ensure_streams(jsm: Any) -> None:
    if _env("NATS_ENSURE_STREAMS", "1") != "1":
        return
    specs = [
        (_env("NATS_STREAM_JOBS", "bhc_jobs"), [_env("NATS_SUBJECT_JOBS", "bhc.jobs")]),
        (_env("NATS_STREAM_RESULTS", "bhc_results"), [_env("NATS_SUBJECT_RESULTS", "bhc.results")]),
        (_env("NATS_STREAM_DLQ", "bhc_dlq"), [_env("NATS_SUBJECT_DLQ", "bhc.dlq")]),
    ]
    for stream_name, subjects in specs:
        try:
            await jsm.stream_info(stream_name)
        except NotFoundError:
            cfg = api.StreamConfig(name=stream_name, subjects=subjects)
            await jsm.add_stream(config=cfg)
            _LOG.info("nats_stream_created", stream=stream_name, subjects=subjects)


def _serialize_for_nats(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False).encode("utf-8")


async def _wait_for_cached_result(redis_client: Any, job_id: str) -> dict[str, Any] | None:
    for _ in range(25):
        await asyncio.sleep(0.2)
        hit = get_cached_result(redis_client, job_id)
        if hit:
            return hit
    return None


async def handle_job_message(
    msg: Any,
    *,
    js: Any,
    deps: AdvisorDeps,
    subject_results: str,
    subject_dlq: str,
    redis_client: Any | None,
) -> None:
    t0 = time.perf_counter()
    try:
        payload = json.loads(msg.data.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        _LOG.error("job_body_invalid", error=str(e))
        await msg.nak()
        return

    job_id_str = str(payload.get("job_id", ""))
    try:
        UUID(job_id_str)
    except ValueError:
        job_id_str = ""

    structlog.contextvars.bind_contextvars(job_id=job_id_str or None)

    from_cache = False
    locked = False

    if redis_client and job_id_str:
        hit = get_cached_result(redis_client, job_id_str)
        if hit:
            result = hit
            from_cache = True

    if not from_cache and redis_client and job_id_str:
        if not try_acquire_lock(redis_client, job_id_str):
            hit2 = await _wait_for_cached_result(redis_client, job_id_str)
            if hit2:
                result = hit2
                from_cache = True
            else:
                _LOG.warning("idempotency_lock_busy", job_id=job_id_str)
                await msg.nak()
                return
        else:
            locked = True

    try:
        if not from_cache:
            try:
                result = await asyncio.to_thread(run_advisor, payload, deps)
            except Exception:
                _LOG.exception("advisor_unhandled_error", job_id=job_id_str)
                await msg.nak()
                return

        elapsed = time.perf_counter() - t0
        if not from_cache:
            result = attach_processing_time(result, elapsed)

        pub_timeout = float(_env("NATS_REQUEST_TIMEOUT_S", "30"))
        try:
            await js.publish(subject_results, _serialize_for_nats({"body": json.dumps(result, ensure_ascii=False)}), timeout=pub_timeout)
        except Exception as e:  # noqa: BLE001
            _LOG.error("publish_results_failed", error=str(e), job_id=job_id_str)
            await msg.nak()
            return

        if redis_client and job_id_str and not from_cache:
            set_cached_result(redis_client, job_id_str, result)

        if _result_needs_dlq(result) and not from_cache:
            jp = JobPayload.model_validate(payload)

            dlq = DlqMessage(
                job_id=jp.job_id,
                original_payload=payload,
                error=str(result.get("error_message", ""))[:8000],
                failed_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                retry_count=int(result.get("retry_count", 0)),
            )
            try:
                await js.publish(
                    subject_dlq,
                    _serialize_for_nats({"body": json.dumps(dlq.model_dump(mode="json"), ensure_ascii=False)}),
                    timeout=pub_timeout,
                )
            except Exception as e:  # noqa: BLE001
                _LOG.error("publish_dlq_failed", error=str(e), job_id=job_id_str)

        await msg.ack()
        log_node_timing(
            _LOG,
            job_id=job_id_str or "unknown",
            node="worker_total",
            duration_ms=elapsed * 1000,
            idempotency_hit=from_cache,
        )
    finally:
        if locked and redis_client and job_id_str:
            release_lock(redis_client, job_id_str)


async def run_nats_worker(*, deps: AdvisorDeps | None = None) -> None:
    url = _env("NATS_URL", "nats://localhost:4222")
    stream_jobs = _env("NATS_STREAM_JOBS", "bhc_jobs")
    subject_jobs = _env("NATS_SUBJECT_JOBS", "bhc.jobs")
    subject_results = _env("NATS_SUBJECT_RESULTS", "bhc.results")
    subject_dlq = _env("NATS_SUBJECT_DLQ", "bhc.dlq")
    durable = _env("NATS_CONSUMER_DURABLE", "dokfin-advisor")
    fetch_batch = int(_env("NATS_FETCH_BATCH", "1"))
    fetch_timeout = float(_env("NATS_FETCH_TIMEOUT_S", "30"))
    max_conc = max(1, int(_env("ADVISOR_MAX_CONCURRENCY", "1")))

    redis_client = connect_redis()
    if redis_client is None and _env("ADVISOR_IDEMPOTENCY_ENABLED", "1") == "1":
        _LOG.info("idempotency_redis_disabled", reason="no_redis_client")

    nc = await nats.connect(
        servers=[url],
        connect_timeout=int(float(_env("NATS_CONNECT_TIMEOUT_S", "10"))),
    )
    js = nc.jetstream(timeout=float(_env("NATS_REQUEST_TIMEOUT_S", "30")))
    await ensure_streams(js)

    sub = await js.pull_subscribe(
        subject_jobs,
        durable=durable,
        stream=stream_jobs,
    )
    _LOG.info(
        "nats_worker_started",
        stream=stream_jobs,
        subject=subject_jobs,
        durable=durable,
        max_concurrency=max_conc,
    )

    d = deps if deps is not None else build_default_deps()
    sem = asyncio.Semaphore(max_conc)

    async def process_one(m: Any) -> None:
        async with sem:
            await handle_job_message(
                m,
                js=js,
                deps=d,
                subject_results=subject_results,
                subject_dlq=subject_dlq,
                redis_client=redis_client,
            )

    try:
        while True:
            try:
                msgs = await sub.fetch(fetch_batch, timeout=fetch_timeout)
            except (FetchTimeoutError, nats.errors.TimeoutError):
                continue
            await asyncio.gather(*(process_one(m) for m in msgs))
    finally:
        await nc.close()


def run_nats_worker_sync(*, deps: AdvisorDeps | None = None) -> None:
    asyncio.run(run_nats_worker(deps=deps))
