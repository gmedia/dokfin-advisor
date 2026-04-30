"""Node C: synthesize — LLM laporan JSON (skor ditimpa di merge)."""

from __future__ import annotations

import os
import time
from datetime import UTC, datetime
from typing import Any

from advisor.deps import AdvisorDeps
from advisor.json_utils import parse_llm_json
from advisor.logging_setup import get_logger, log_node_timing
from advisor.merge_output import merge_deterministic_into_raw
from advisor.prompts import build_node_c_messages
from advisor.retry_llm import call_with_json_retries
from advisor.schemas.input import JobPayload

_LOG = get_logger(__name__)


def _disclaimer_kelengkapan(persen: float) -> str:
    if persen < 85:
        return (
            f"- Disclaimer: kelengkapan data {persen:.0f}% (di bawah 85%). "
            "Sebutkan di ringkasan bahwa hasil bisa kurang lengkap."
        )
    return ""


def make_synthesize_node(deps: AdvisorDeps):
    def synthesize(state: dict[str, Any]) -> dict[str, Any]:
        job_id = str(state.get("job_id", ""))
        payload = JobPayload.model_validate(state["payload"])
        reasoning = state.get("reasoning") or {}
        market_context = str(state.get("market_context") or "")
        skor_per_dimensi = state["skor_per_dimensi"]
        skor_keseluruhan = float(state["skor_keseluruhan"])
        disclaimer = _disclaimer_kelengkapan(payload.profil_bisnis.kelengkapan_data_persen)
        model_ph = os.environ.get("ADVISOR_MODEL_C", deps.model_name_c)

        messages = build_node_c_messages(
            payload=payload,
            market_context=market_context,
            skor_per_dimensi=skor_per_dimensi,
            skor_keseluruhan=skor_keseluruhan,
            reasoning=reasoning,
            disclaimer=disclaimer,
            model_name_placeholder=model_ph,
        )

        t0 = time.perf_counter()

        def _once() -> dict[str, Any]:
            text = deps.invoke_llm_c(messages)
            return parse_llm_json(text)

        raw = call_with_json_retries(_once)
        merged = merge_deterministic_into_raw(
            payload=payload,
            skor_per_dimensi=skor_per_dimensi,
            skor_keseluruhan=skor_keseluruhan,
            raw=raw,
        )

        merged["generated_at"] = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        merged["model_used"] = model_ph

        log_node_timing(
            _LOG,
            job_id=job_id,
            node="C",
            duration_ms=(time.perf_counter() - t0) * 1000,
        )
        return {"raw_output": raw, "merged_output": merged}

    return synthesize
