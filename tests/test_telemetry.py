"""Token usage accumulation and cost merge (Sprint 3 G5)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

from advisor.cost_estimate import estimate_cost_idr
from advisor.deps import AdvisorDeps
from advisor.graph import merge_telemetry_into_result, run_advisor
from advisor.llm_usage import TokenUsageAccumulator
from advisor.schemas.output import AdvisorResultDone
from advisor.schemas.reasoning import ContextualizeResult
from langchain_core.messages import AIMessage

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "payload_sample.json"


def test_extract_usage_from_aimessage() -> None:
    acc = TokenUsageAccumulator()
    msg = AIMessage(
        content="{}",
        usage_metadata={
            "input_tokens": 100,
            "output_tokens": 40,
            "total_tokens": 140,
        },
    )
    acc.add_node_a(msg)
    assert acc.node_a_input == 100
    assert acc.node_a_output == 40
    tu = acc.to_token_usage()
    assert tu is not None
    assert tu.total == 140


def test_merge_telemetry_into_done() -> None:
    acc = TokenUsageAccumulator()
    acc.node_a_input = 10
    acc.node_a_output = 5
    acc.node_c_input = 20
    acc.node_c_output = 8
    deps = AdvisorDeps(
        invoke_llm_a=lambda _m: "",
        invoke_llm_c=lambda _m: "",
        token_usage=acc,
        model_name_a="gpt-4o-mini",
        model_name_c="gpt-4o",
    )
    base = {"status": "DONE", "job_id": "550e8400-e29b-41d4-a716-446655440000"}
    merged = merge_telemetry_into_result(deps, base)
    assert merged["token_usage"]["node_a_input"] == 10
    assert merged["token_usage"]["total"] == 43


def test_estimate_cost_idr_when_env_set() -> None:
    acc = TokenUsageAccumulator()
    acc.node_a_input = 1_000_000
    acc.node_a_output = 0
    acc.node_c_input = 0
    acc.node_c_output = 0
    with patch.dict(
        os.environ,
        {
            "OPENAI_PRICE_INPUT_PER_M_IDR": "3000",
            "OPENAI_PRICE_OUTPUT_PER_M_IDR": "9000",
        },
        clear=False,
    ):
        c = estimate_cost_idr(acc, model_a="gpt-4o-mini", model_c="gpt-4o")
    assert c == 3000.0


def test_run_advisor_merges_usage_from_mock_llm() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    job_id = payload["job_id"]
    reasoning = ContextualizeResult(
        indikator_kritis=["KES_01"],
        dimensi_terburuk="likuiditas",
        search_keywords=["tren industri kuliner indonesia", "benchmark umkm"],
        ada_perishable_kritis=False,
        flag_data_tidak_lengkap=False,
    )

    def invoke_a(_m) -> str:
        acc_holder["v"].add_node_a(
            AIMessage(
                content=reasoning.model_dump_json(),
                usage_metadata={
                    "input_tokens": 12,
                    "output_tokens": 8,
                    "total_tokens": 20,
                },
            )
        )
        return reasoning.model_dump_json()

    done_body = {
        "job_id": job_id,
        "status": "DONE",
        "generated_at": "2026-04-28T14:32:15Z",
        "model_used": "mock",
        "skor_keseluruhan": {
            "nilai": 5.0,
            "label": "Netral",
            "trend": "datar",
            "vs_periode_lalu": 0.0,
        },
        "ringkasan_eksekutif": {
            "narasi": "x",
            "highlight_positif": ["a"],
            "highlight_warning": ["b"],
        },
        "dimensi": {
            "likuiditas": {
                "skor": 5.0,
                "status": "PERLU_PERHATIAN",
                "narasi": "n",
                "saran": [],
            },
            "profitabilitas": {
                "skor": 5.0,
                "status": "SEHAT",
                "narasi": "n",
                "saran": [],
            },
            "efisiensi": {
                "skor": 5.0,
                "status": "SEHAT",
                "narasi": "n",
                "saran": [],
            },
            "solvabilitas": {
                "skor": 5.0,
                "status": "SEHAT",
                "narasi": "n",
                "saran": [],
            },
            "sdm": {"skor": 5.0, "status": "SEHAT", "narasi": "n", "saran": []},
            "kepatuhan": {"skor": 5.0, "status": "SEHAT", "narasi": "n", "saran": []},
        },
        "konteks_pasar": [],
        "rekomendasi_prioritas": [
            {
                "prioritas": 1,
                "label": "SEGERA",
                "aksi": "a",
                "detail": "d",
                "estimasi_dampak": "e",
            },
            {
                "prioritas": 2,
                "label": "BULAN_INI",
                "aksi": "a",
                "detail": "d",
                "estimasi_dampak": "e",
            },
            {
                "prioritas": 3,
                "label": "PELUANG",
                "aksi": "a",
                "detail": "d",
                "estimasi_dampak": "e",
            },
        ],
    }

    acc = TokenUsageAccumulator()
    acc_holder: dict[str, TokenUsageAccumulator] = {"v": acc}

    def invoke_c(_m) -> str:
        acc.add_node_c(
            AIMessage(
                content=json.dumps(done_body),
                usage_metadata={
                    "input_tokens": 50,
                    "output_tokens": 100,
                    "total_tokens": 150,
                },
            )
        )
        return json.dumps(done_body)

    deps = AdvisorDeps(
        invoke_llm_a=invoke_a,
        invoke_llm_c=invoke_c,
        tavily_client=None,
        cache=None,
        token_usage=acc,
    )
    out = run_advisor(payload, deps)
    assert out["status"] == "DONE"
    assert out["token_usage"]["node_a_input"] == 12
    assert out["token_usage"]["node_c_output"] == 100
    AdvisorResultDone.model_validate(out)
