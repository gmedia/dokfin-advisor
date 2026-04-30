"""Node D: validate merged JSON against AdvisorResultDone."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from advisor.logging_setup import get_logger, log_node_timing
from advisor.schemas.input import JobPayload
from advisor.schemas.output import AdvisorResultDone, AdvisorResultFailed, ErrorCode

_LOG = get_logger(__name__)


def validate_node(state: dict[str, Any]) -> dict[str, Any]:
    job_id = str(state.get("job_id", ""))
    merged = state.get("merged_output")
    vf = int(state.get("validation_failures", 0))
    t0 = time.perf_counter()

    if not isinstance(merged, dict):
        merged = {}

    try:
        done = AdvisorResultDone.model_validate(merged)
        fo = done.model_dump(mode="json")
        dur_ms = (time.perf_counter() - t0) * 1000
        log_node_timing(_LOG, job_id=job_id, node="D", duration_ms=dur_ms)
        return {
            "final_output": fo,
            "validation_error": None,
        }
    except Exception as e:  # noqa: BLE001
        err = str(e)
        vf2 = vf + 1
        payload = JobPayload.model_validate(state["payload"])
        if vf2 > 2:
            failed = AdvisorResultFailed(
                job_id=payload.job_id,
                generated_at=datetime.now(UTC),
                error_code=ErrorCode.LLM_INVALID_JSON,
                error_message=err[:2000],
                retry_count=vf2,
            )
            log_node_timing(
                _LOG,
                job_id=job_id,
                node="D",
                duration_ms=(time.perf_counter() - t0) * 1000,
                failed=True,
            )
            return {
                "validation_failures": vf2,
                "validation_error": err,
                "failed_output": failed.model_dump(mode="json"),
            }
        log_node_timing(
            _LOG,
            job_id=job_id,
            node="D",
            duration_ms=(time.perf_counter() - t0) * 1000,
            retry=True,
        )
        return {
            "validation_failures": vf2,
            "validation_error": err,
        }
