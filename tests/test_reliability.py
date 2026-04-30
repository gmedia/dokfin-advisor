"""Sprint 2 contract tests: error paths (PRD §8–9, TASK H3)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from advisor.deps import AdvisorDeps
from advisor.graph import run_advisor
from advisor.schemas.output import AdvisorResultDone, ErrorCode
from advisor.schemas.reasoning import ContextualizeResult

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "payload_sample.json"


def _payload() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_llm_c_exhausted_returns_failed() -> None:
    p = _payload()
    job_id = p["job_id"]
    reasoning = ContextualizeResult(
        indikator_kritis=["KES_01"],
        dimensi_terburuk="likuiditas",
        search_keywords=["tren industri kuliner indonesia"],
        ada_perishable_kritis=False,
        flag_data_tidak_lengkap=False,
    )
    deps = AdvisorDeps(
        invoke_llm_a=lambda _m: reasoning.model_dump_json(),
        invoke_llm_c=lambda _m: "not valid json {{{",
        tavily_client=None,
        cache=None,
    )
    out = run_advisor(p, deps)
    assert out["status"] == "FAILED"
    assert out["job_id"] == job_id
    assert out["error_code"] == ErrorCode.LLM_INVALID_JSON.value
    assert out["retry_count"] == 3


def test_tavily_raises_still_done_with_empty_konteks() -> None:
    p = _payload()
    job_id = p["job_id"]
    reasoning = ContextualizeResult(
        indikator_kritis=["KES_01"],
        dimensi_terburuk="likuiditas",
        search_keywords=["tren industri kuliner indonesia"],
        ada_perishable_kritis=False,
        flag_data_tidak_lengkap=False,
    )

    bad = MagicMock()
    bad.search.side_effect = TimeoutError("upstream")

    done_min = {
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
            "narasi": "Ringkasan.",
            "highlight_positif": ["a"],
            "highlight_warning": ["b"],
        },
        "dimensi": {
            "likuiditas": {
                "skor": 5.0,
                "status": "PERLU_PERHATIAN",
                "narasi": "n",
                "saran": ["s"],
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

    deps = AdvisorDeps(
        invoke_llm_a=lambda _m: reasoning.model_dump_json(),
        invoke_llm_c=lambda _m: json.dumps(done_min),
        tavily_client=bad,
        cache=None,
    )
    out = run_advisor(p, deps)
    assert out["status"] == "DONE"
    validated = AdvisorResultDone.model_validate(out)
    assert validated.konteks_pasar == []


def test_payload_invalid_returns_failed() -> None:
    out = run_advisor(
        {"job_id": "not-a-uuid", "dimensi": {}},
        AdvisorDeps(
            invoke_llm_a=lambda _m: "{}",
            invoke_llm_c=lambda _m: "{}",
            tavily_client=None,
            cache=None,
        ),
    )
    assert out["status"] == "FAILED"
    assert out["error_code"] == ErrorCode.PAYLOAD_INVALID.value
