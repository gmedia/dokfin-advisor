"""Node A: contextualize — LLM JSON reasoning + keyword sanitization via schema."""

from __future__ import annotations

import time
from typing import Any

from advisor.deps import AdvisorDeps
from advisor.json_utils import parse_llm_json
from advisor.logging_setup import get_logger, log_node_timing
from advisor.prompts import build_node_a_messages
from advisor.retry_llm import call_with_json_retries
from advisor.schemas.input import JobPayload
from advisor.schemas.reasoning import ContextualizeResult

_LOG = get_logger(__name__)


def make_contextualize_node(deps: AdvisorDeps):
    def contextualize(state: dict[str, Any]) -> dict[str, Any]:
        job_id = str(state.get("job_id", ""))
        payload = JobPayload.model_validate(state["payload"])
        messages = build_node_a_messages(payload)

        t0 = time.perf_counter()

        def _once() -> dict[str, Any]:
            text = deps.invoke_llm_a(messages)
            data = parse_llm_json(text)
            validated = ContextualizeResult.model_validate(data)
            return validated.model_dump(mode="json")

        reasoning = call_with_json_retries(_once)
        log_node_timing(
            _LOG,
            job_id=job_id,
            node="A",
            duration_ms=(time.perf_counter() - t0) * 1000,
        )
        return {"reasoning": reasoning}

    return contextualize
