"""Integration tests: LangGraph A→B→C→D with mocked LLM/Tavily."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from advisor.deps import AdvisorDeps
from advisor.graph import run_advisor
from advisor.schemas.output import (
    AdvisorResultDone,
    DimensiReportOut,
    DimensiSatuOut,
    KonteksPasarItem,
    RekomendasiPrioritasItem,
    RingkasanEksekutifOut,
    SkorKeseluruhanOut,
)
from advisor.schemas.reasoning import ContextualizeResult

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "payload_sample.json"


def _load_payload() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _done_json(job_id: str) -> str:
    jid = UUID(job_id)
    dim_template = DimensiSatuOut(
        skor=5.0,
        status="PERLU_PERHATIAN",
        narasi="Narasi uji.",
        saran=["Saran uji."],
    )
    dim = DimensiReportOut(
        likuiditas=dim_template.model_copy(),
        profitabilitas=dim_template.model_copy(),
        efisiensi=dim_template.model_copy(),
        solvabilitas=dim_template.model_copy(),
        sdm=dim_template.model_copy(),
        kepatuhan=dim_template.model_copy(),
    )
    done = AdvisorResultDone(
        job_id=jid,
        generated_at=datetime(2026, 4, 28, 14, 32, 15, tzinfo=UTC),
        model_used="mock-model",
        skor_keseluruhan=SkorKeseluruhanOut(
            nilai=7.0,
            label="Cukup Sehat",
            trend="naik",
            vs_periode_lalu=0.5,
        ),
        ringkasan_eksekutif=RingkasanEksekutifOut(
            narasi="Ringkasan uji.",
            highlight_positif=["Positif uji."],
            highlight_warning=["Peringatan uji."],
        ),
        dimensi=dim,
        konteks_pasar=[
            KonteksPasarItem(
                topik="Pasar uji",
                konten="Konten singkat.",
                dampak_ke_bisnis="Netral.",
                relevansi="TINGGI",
                sumber="sumber",
            )
        ],
        rekomendasi_prioritas=[
            RekomendasiPrioritasItem(
                prioritas=1,
                label="SEGERA",
                aksi="Aksi satu",
                detail="Detail satu.",
                estimasi_dampak="Dampak satu.",
            ),
            RekomendasiPrioritasItem(
                prioritas=2,
                label="BULAN_INI",
                aksi="Aksi dua",
                detail="Detail dua.",
                estimasi_dampak="Dampak dua.",
            ),
            RekomendasiPrioritasItem(
                prioritas=3,
                label="PELUANG",
                aksi="Aksi tiga",
                detail="Detail tiga.",
                estimasi_dampak="Dampak tiga.",
            ),
        ],
    )
    return done.model_dump_json()


def test_graph_happy_path_mocked() -> None:
    payload = _load_payload()
    job_id = payload["job_id"]
    reasoning = ContextualizeResult(
        indikator_kritis=["KES_01"],
        dimensi_terburuk="likuiditas",
        search_keywords=[
            "tren industri kuliner indonesia",
            "kondisi likuiditas umkm",
        ],
        ada_perishable_kritis=False,
        flag_data_tidak_lengkap=False,
    )

    deps = AdvisorDeps(
        invoke_llm_a=lambda _m: reasoning.model_dump_json(),
        invoke_llm_c=lambda _m: _done_json(job_id),
        tavily_client=None,
        cache=None,
    )
    out = run_advisor(payload, deps)
    assert out["status"] == "DONE"
    assert out["job_id"] == job_id
    validated = AdvisorResultDone.model_validate(out)
    assert validated.skor_keseluruhan.nilai > 0
    assert validated.dimensi.likuiditas.status.value == "KRITIS"


def test_node_a_json_retry_then_ok() -> None:
    payload = _load_payload()
    job_id = payload["job_id"]
    reasoning = ContextualizeResult(
        indikator_kritis=["KES_01"],
        dimensi_terburuk="likuiditas",
        search_keywords=["tren industri kuliner indonesia", "benchmark umkm restoran"],
        ada_perishable_kritis=False,
        flag_data_tidak_lengkap=False,
    )
    calls: list[int] = []

    def invoke_a(_m) -> str:
        calls.append(1)
        if len(calls) == 1:
            return "not json {{{"
        return reasoning.model_dump_json()

    deps = AdvisorDeps(
        invoke_llm_a=invoke_a,
        invoke_llm_c=lambda _m: _done_json(job_id),
        tavily_client=None,
        cache=None,
    )
    out = run_advisor(payload, deps)
    assert out["status"] == "DONE"
    assert len(calls) >= 2


def test_validate_retry_then_ok() -> None:
    payload = _load_payload()
    job_id = payload["job_id"]
    reasoning = ContextualizeResult(
        indikator_kritis=["KES_01"],
        dimensi_terburuk="likuiditas",
        search_keywords=["tren industri kuliner indonesia", "benchmark umkm restoran"],
        ada_perishable_kritis=False,
        flag_data_tidak_lengkap=False,
    )
    c_calls: list[int] = []

    def invoke_c(_m) -> str:
        c_calls.append(1)
        if len(c_calls) == 1:
            return json.dumps(
                {
                    "job_id": job_id,
                    "status": "DONE",
                    "generated_at": "2026-04-28T14:32:15Z",
                    "model_used": "x",
                }
            )
        return _done_json(job_id)

    deps = AdvisorDeps(
        invoke_llm_a=lambda _m: reasoning.model_dump_json(),
        invoke_llm_c=invoke_c,
        tavily_client=None,
        cache=None,
    )
    out = run_advisor(payload, deps)
    assert out["status"] == "DONE"
    assert len(c_calls) >= 2
