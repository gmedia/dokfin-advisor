"""Sprint 2 contract tests: error paths (PRD §8–9, TASK H3)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from advisor.deps import AdvisorDeps
from advisor.graph import run_advisor
from advisor.nats_worker import handle_job_message
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
    assert validated.skor_keseluruhan.trend == "tidak_tersedia"
    assert validated.skor_keseluruhan.vs_periode_lalu is None


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


def test_openai_compatible_payload_model_with_slash_reaches_resolver(monkeypatch) -> None:
    p = _payload()
    p["llm"] = {
        "provider": "openai",
        "model_a": "cbcn/deepseek-v4-pro",
        "model_c": "cbcn/deepseek-v4-pro",
    }
    job_id = p["job_id"]
    reasoning = ContextualizeResult(
        indikator_kritis=["KES_01"],
        dimensi_terburuk="likuiditas",
        search_keywords=["tren industri kuliner indonesia"],
        ada_perishable_kritis=False,
        flag_data_tidak_lengkap=False,
    )
    resolved: dict[str, str] = {}

    def fake_build_deps_for_payload(validated, *, base_deps=None):
        assert base_deps is None
        resolved["provider"] = validated.llm.provider.value
        resolved["model_a"] = validated.llm.model_a
        resolved["model_c"] = validated.llm.model_c
        return AdvisorDeps(
            invoke_llm_a=lambda _m: reasoning.model_dump_json(),
            invoke_llm_c=lambda _m: json.dumps(
                {
                    "job_id": job_id,
                    "status": "DONE",
                    "generated_at": "2026-04-28T14:32:15Z",
                    "model_used": validated.llm.model_c,
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
                        "sdm": {
                            "skor": 5.0,
                            "status": "SEHAT",
                            "narasi": "n",
                            "saran": [],
                        },
                        "kepatuhan": {
                            "skor": 5.0,
                            "status": "SEHAT",
                            "narasi": "n",
                            "saran": [],
                        },
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
            ),
            tavily_client=None,
            cache=None,
            llm_provider=validated.llm.provider.value,
            model_name_a=validated.llm.model_a,
            model_name_c=validated.llm.model_c,
        )

    monkeypatch.setattr("advisor.graph.build_deps_for_payload", fake_build_deps_for_payload)

    out = run_advisor(p)

    assert out["status"] == "DONE"
    assert out["model_used"] == "cbcn/deepseek-v4-pro"
    assert resolved == {
        "provider": "openai",
        "model_a": "cbcn/deepseek-v4-pro",
        "model_c": "cbcn/deepseek-v4-pro",
    }


def test_deps_resolution_error_returns_failed(monkeypatch) -> None:
    p = _payload()
    p["llm"] = {
        "provider": "openai",
        "model_a": "cbcn/deepseek-v4-pro",
        "model_c": "cbcn/deepseek-v4-pro",
    }

    def fake_build_deps_for_payload(_validated, *, base_deps=None):
        raise RuntimeError("model init failed")

    monkeypatch.setattr("advisor.graph.build_deps_for_payload", fake_build_deps_for_payload)

    out = run_advisor(p)

    assert out["status"] == "FAILED"
    assert out["error_code"] == ErrorCode.UNKNOWN_ERROR.value
    assert out["retry_count"] == 0
    assert "model init failed" in out["error_message"]
    assert out["processing_time_seconds"] >= 0


def test_graph_unhandled_llm_error_returns_failed() -> None:
    p = _payload()
    deps = AdvisorDeps(
        invoke_llm_a=lambda _m: (_ for _ in ()).throw(ConnectionError("upstream boom")),
        invoke_llm_c=lambda _m: "{}",
        tavily_client=None,
        cache=None,
    )

    out = run_advisor(p, deps)

    assert out["status"] == "FAILED"
    assert out["error_code"] == ErrorCode.UNKNOWN_ERROR.value
    assert out["retry_count"] == 0
    assert "upstream boom" in out["error_message"]


@pytest.mark.anyio
async def test_worker_publishes_failed_and_acks_when_advisor_raises(monkeypatch) -> None:
    p = _payload()

    class Msg:
        def __init__(self) -> None:
            self.data = json.dumps(p).encode("utf-8")
            self.acked = False
            self.nacked = False

        async def ack(self) -> None:
            self.acked = True

        async def nak(self) -> None:
            self.nacked = True

    class Js:
        def __init__(self) -> None:
            self.published: list[tuple[str, dict]] = []

        async def publish(self, subject, payload, timeout=None) -> None:
            self.published.append((subject, json.loads(payload.decode("utf-8"))))

    def boom(_payload, _deps):
        raise RuntimeError("terminal pipeline error")

    monkeypatch.setattr("advisor.nats_worker.run_advisor", boom)
    msg = Msg()
    js = Js()

    await handle_job_message(
        msg,
        js=js,
        deps=AdvisorDeps(invoke_llm_a=lambda _m: "{}", invoke_llm_c=lambda _m: "{}"),
        subject_results="bhc.results",
        subject_dlq="bhc.dlq",
        redis_client=None,
    )

    assert msg.acked is True
    assert msg.nacked is False
    assert len(js.published) == 2
    result_body = json.loads(js.published[0][1]["body"])
    dlq_body = json.loads(js.published[1][1]["body"])
    assert js.published[0][0] == "bhc.results"
    assert js.published[1][0] == "bhc.dlq"
    assert result_body["status"] == "FAILED"
    assert result_body["error_code"] == ErrorCode.UNKNOWN_ERROR.value
    assert dlq_body["job_id"] == p["job_id"]
