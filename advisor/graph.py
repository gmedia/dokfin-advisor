"""LangGraph pipeline: preprocess → A → B → C → D with Node C retry (PRD §4, §9.1)."""

from __future__ import annotations

import os
import time
from datetime import UTC, datetime
from typing import Any, Literal, TypedDict
from uuid import UUID, uuid4

from langgraph.graph import END, START, StateGraph
from pydantic import ValidationError

from advisor.cost_estimate import estimate_cost_idr
from advisor.deps import AdvisorDeps
from advisor.logging_setup import get_logger
from advisor.nodes.contextualize import make_contextualize_node
from advisor.nodes.search import run_search
from advisor.nodes.synthesize import make_synthesize_node
from advisor.nodes.validate import validate_node
from advisor.retry_llm import MAX_LLM_ATTEMPTS
from advisor.schemas.input import JobPayload
from advisor.schemas.output import AdvisorResultFailed, ErrorCode
from advisor.scoring import hitung_skor_keseluruhan, skor_from_payload_dimensi

_LOG = get_logger(__name__)


def merge_telemetry_into_result(deps: AdvisorDeps, result: dict[str, Any]) -> dict[str, Any]:
    """Attach token_usage and estimated_cost_idr when accumulator has data."""
    acc = deps.token_usage
    if acc is None or acc.is_empty():
        return result
    out = dict(result)
    tu = acc.to_token_usage()
    if tu:
        out["token_usage"] = tu.model_dump(mode="json")
    cost = estimate_cost_idr(acc, model_a=deps.model_name_a, model_c=deps.model_name_c)
    if cost is not None:
        out["estimated_cost_idr"] = cost
    return out


class AdvisorState(TypedDict, total=False):
    """Graph state (PRD §4 + retry metadata)."""

    payload: dict[str, Any]
    job_id: str
    skor_per_dimensi: dict[str, float]
    skor_keseluruhan: float
    reasoning: dict[str, Any]
    market_context: str
    konteks_pasar_seed: list
    raw_output: dict[str, Any]
    merged_output: dict[str, Any]
    final_output: dict[str, Any]
    failed_output: dict[str, Any]
    validation_failures: int
    validation_error: str | None


def preprocess_node(state: AdvisorState) -> dict[str, Any]:
    payload = JobPayload.model_validate(state["payload"])
    dim = payload.dimensi.model_dump(mode="json")
    skor_pd = skor_from_payload_dimensi(dim)
    skor_k = hitung_skor_keseluruhan(skor_pd)
    return {
        "job_id": str(payload.job_id),
        "skor_per_dimensi": skor_pd,
        "skor_keseluruhan": skor_k,
        "validation_failures": 0,
        "validation_error": None,
    }


def _route_after_validate(state: AdvisorState) -> Literal["ok", "fail", "retry"]:
    if state.get("final_output"):
        return "ok"
    if state.get("failed_output"):
        return "fail"
    return "retry"


def build_graph(deps: AdvisorDeps):
    g = StateGraph(AdvisorState)
    g.add_node("preprocess", preprocess_node)
    g.add_node("contextualize", make_contextualize_node(deps))
    g.add_node(
        "search",
        lambda s: run_search(s, cache=deps.cache, tavily_client=deps.tavily_client),
    )
    g.add_node("synthesize", make_synthesize_node(deps))
    g.add_node("validate", validate_node)

    g.add_edge(START, "preprocess")
    g.add_edge("preprocess", "contextualize")
    g.add_edge("contextualize", "search")
    g.add_edge("search", "synthesize")
    g.add_edge("synthesize", "validate")
    g.add_conditional_edges(
        "validate",
        _route_after_validate,
        {"ok": END, "fail": END, "retry": "synthesize"},
    )
    return g


def _job_id_for_failed_response(payload: dict[str, Any]) -> UUID:
    raw = payload.get("job_id")
    if raw is not None:
        try:
            return UUID(str(raw))
        except ValueError:
            pass
    return uuid4()


def _llm_timeout_s(*, google: bool) -> float:
    if google:
        raw = os.environ.get("GOOGLE_TIMEOUT_S")
        if raw:
            return float(raw)
    return float(os.environ.get("OPENAI_TIMEOUT_S", "120"))


def _build_openai_deps() -> AdvisorDeps:
    """ChatOpenAI; requires OPENAI_API_KEY."""

    from langchain_openai import ChatOpenAI

    from advisor.cache import MemoryTTLCache
    from advisor.llm_usage import TokenUsageAccumulator

    model_a = os.environ.get("OPENAI_MODEL_A", "gpt-4o-mini")
    model_c = os.environ.get("OPENAI_MODEL_C", "gpt-4o")
    timeout_s = _llm_timeout_s(google=False)
    llm_a = ChatOpenAI(model=model_a, temperature=0, timeout=timeout_s)
    llm_c = ChatOpenAI(model=model_c, temperature=0.2, timeout=timeout_s)
    acc = TokenUsageAccumulator()

    def invoke_a(messages: list) -> str:
        r = llm_a.invoke(messages)
        acc.add_node_a(r)
        return str(r.content or "")

    def invoke_c(messages: list) -> str:
        r = llm_c.invoke(messages)
        acc.add_node_c(r)
        return str(r.content or "")

    return AdvisorDeps(
        invoke_llm_a=invoke_a,
        invoke_llm_c=invoke_c,
        tavily_client=None,
        cache=MemoryTTLCache(),
        model_name_a=model_a,
        model_name_c=model_c,
        token_usage=acc,
    )


def _build_google_genai_deps() -> AdvisorDeps:
    """ChatGoogleGenerativeAI; set GOOGLE_API_KEY (atau GEMINI_API_KEY)."""

    from langchain_google_genai import ChatGoogleGenerativeAI

    from advisor.cache import MemoryTTLCache
    from advisor.llm_usage import TokenUsageAccumulator

    model_a = os.environ.get("GOOGLE_MODEL_A", "gemini-2.0-flash")
    model_c = os.environ.get("GOOGLE_MODEL_C", "gemini-2.0-flash")
    timeout_s = _llm_timeout_s(google=True)
    llm_a = ChatGoogleGenerativeAI(model=model_a, temperature=0, timeout=timeout_s)
    llm_c = ChatGoogleGenerativeAI(model=model_c, temperature=0.2, timeout=timeout_s)
    acc = TokenUsageAccumulator()

    def invoke_a(messages: list) -> str:
        r = llm_a.invoke(messages)
        acc.add_node_a(r)
        return str(r.content or "")

    def invoke_c(messages: list) -> str:
        r = llm_c.invoke(messages)
        acc.add_node_c(r)
        return str(r.content or "")

    return AdvisorDeps(
        invoke_llm_a=invoke_a,
        invoke_llm_c=invoke_c,
        tavily_client=None,
        cache=MemoryTTLCache(),
        model_name_a=model_a,
        model_name_c=model_c,
        token_usage=acc,
    )


def build_default_deps() -> AdvisorDeps:
    """Deps produksi: OpenAI (default) atau Gemini (`LLM_PROVIDER=google`)."""

    provider = os.environ.get("LLM_PROVIDER", "openai").strip().lower()
    if provider in ("google", "gemini", "genai"):
        return _build_google_genai_deps()
    return _build_openai_deps()


def run_advisor(payload: dict[str, Any], deps: AdvisorDeps) -> dict[str, Any]:
    """Jalankan graph; return dict DONE atau FAILED (JSON-friendly)."""
    try:
        JobPayload.model_validate(payload)
    except ValidationError as e:
        failed = AdvisorResultFailed(
            job_id=_job_id_for_failed_response(payload),
            generated_at=datetime.now(UTC),
            error_code=ErrorCode.PAYLOAD_INVALID,
            error_message=str(e)[:2000],
            retry_count=0,
        )
        return failed.model_dump(mode="json")

    if deps.token_usage is not None:
        deps.token_usage.reset()

    t0 = time.perf_counter()

    def _with_processing_time(result: dict[str, Any]) -> dict[str, Any]:
        merged = dict(result)
        merged["processing_time_seconds"] = round(time.perf_counter() - t0, 3)
        return merged

    try:
        app = build_graph(deps).compile()
        out = app.invoke({"payload": payload})
    except RuntimeError as e:
        failed = AdvisorResultFailed(
            job_id=_job_id_for_failed_response(payload),
            generated_at=datetime.now(UTC),
            error_code=ErrorCode.LLM_INVALID_JSON,
            error_message=str(e)[:2000],
            retry_count=MAX_LLM_ATTEMPTS,
        )
        base = failed.model_dump(mode="json")
        return _with_processing_time(merge_telemetry_into_result(deps, base))

    if out.get("final_output"):
        return _with_processing_time(merge_telemetry_into_result(deps, out["final_output"]))
    if out.get("failed_output"):
        return _with_processing_time(merge_telemetry_into_result(deps, out["failed_output"]))
    _LOG.error("graph_no_terminal", job_id=out.get("job_id"))
    raise RuntimeError("graph finished without final_output or failed_output")
