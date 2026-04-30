"""LangGraph pipeline: preprocess → A → B → C → D with Node C retry (PRD §4, §9.1)."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any, Literal, TypedDict
from uuid import UUID, uuid4

from langgraph.graph import END, START, StateGraph
from pydantic import ValidationError

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


class AdvisorState(TypedDict, total=False):
    """Graph state (PRD §4 + retry metadata)."""

    payload: dict[str, Any]
    job_id: str
    skor_per_dimensi: dict[str, float]
    skor_keseluruhan: float
    reasoning: dict[str, Any]
    market_context: str
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


def build_default_deps() -> AdvisorDeps:
    """Production-oriented deps using ChatOpenAI (requires OPENAI_API_KEY)."""

    from langchain_openai import ChatOpenAI

    model_a = os.environ.get("OPENAI_MODEL_A", "gpt-4o-mini")
    model_c = os.environ.get("OPENAI_MODEL_C", "gpt-4o")
    timeout_s = float(os.environ.get("OPENAI_TIMEOUT_S", "120"))
    llm_a = ChatOpenAI(model=model_a, temperature=0, timeout=timeout_s)
    llm_c = ChatOpenAI(model=model_c, temperature=0.2, timeout=timeout_s)

    def invoke_a(messages: list) -> str:
        return str(llm_a.invoke(messages).content or "")

    def invoke_c(messages: list) -> str:
        return str(llm_c.invoke(messages).content or "")

    from advisor.cache import MemoryTTLCache

    return AdvisorDeps(
        invoke_llm_a=invoke_a,
        invoke_llm_c=invoke_c,
        tavily_client=None,
        cache=MemoryTTLCache(),
        model_name_a=model_a,
        model_name_c=model_c,
    )


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
        return failed.model_dump(mode="json")

    if out.get("final_output"):
        return out["final_output"]
    if out.get("failed_output"):
        return out["failed_output"]
    _LOG.error("graph_no_terminal", job_id=out.get("job_id"))
    raise RuntimeError("graph finished without final_output or failed_output")
