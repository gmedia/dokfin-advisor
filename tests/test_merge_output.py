"""Merge: status dimensi dari skor, trend skor keseluruhan."""

from __future__ import annotations

import json
from pathlib import Path

from advisor.merge_output import merge_deterministic_into_raw
from advisor.schemas.input import JobPayload
from advisor.scoring import hitung_skor_keseluruhan, skor_from_payload_dimensi

FIXTURE_MIN = Path(__file__).resolve().parent / "fixtures" / "payload_minimal.json"


def test_merge_status_from_skor_not_worst_indicator() -> None:
    payload = JobPayload.model_validate(json.loads(FIXTURE_MIN.read_text(encoding="utf-8")))
    dim = payload.dimensi.model_dump(mode="json")
    skor_pd = skor_from_payload_dimensi(dim)
    skor_k = hitung_skor_keseluruhan(skor_pd)
    raw: dict = {
        "dimensi": {
            "likuiditas": {
                "skor": 0,
                "status": "KRITIS",
                "narasi": "x",
                "saran": [],
            },
        },
    }
    merged = merge_deterministic_into_raw(
        payload=payload,
        skor_per_dimensi=skor_pd,
        skor_keseluruhan=skor_k,
        raw=raw,
    )
    lik = merged["dimensi"]["likuiditas"]
    assert lik["skor"] == 6.0
    assert lik["status"] == "PERLU_PERHATIAN"


def test_merge_trend_tidak_tersedia_without_prev() -> None:
    payload = JobPayload.model_validate(json.loads(FIXTURE_MIN.read_text(encoding="utf-8")))
    dim = payload.dimensi.model_dump(mode="json")
    skor_pd = skor_from_payload_dimensi(dim)
    skor_k = hitung_skor_keseluruhan(skor_pd)
    merged = merge_deterministic_into_raw(
        payload=payload,
        skor_per_dimensi=skor_pd,
        skor_keseluruhan=skor_k,
        raw={"skor_keseluruhan": {}},
    )
    sk = merged["skor_keseluruhan"]
    assert sk["trend"] == "tidak_tersedia"
    assert sk["vs_periode_lalu"] is None


def test_merge_trend_from_prev_skor() -> None:
    data = json.loads(FIXTURE_MIN.read_text(encoding="utf-8"))
    data["profil_bisnis"]["skor_keseluruhan_periode_sebelumnya"] = 5.0
    payload = JobPayload.model_validate(data)
    dim = payload.dimensi.model_dump(mode="json")
    skor_pd = skor_from_payload_dimensi(dim)
    skor_k = hitung_skor_keseluruhan(skor_pd)
    merged = merge_deterministic_into_raw(
        payload=payload,
        skor_per_dimensi=skor_pd,
        skor_keseluruhan=skor_k,
        raw={"skor_keseluruhan": {}},
    )
    sk = merged["skor_keseluruhan"]
    assert sk["trend"] in ("naik", "turun", "stabil")
    assert sk["vs_periode_lalu"] is not None


def test_merge_clears_konteks_pasar_when_no_seed() -> None:
    payload = JobPayload.model_validate(json.loads(FIXTURE_MIN.read_text(encoding="utf-8")))
    dim = payload.dimensi.model_dump(mode="json")
    skor_pd = skor_from_payload_dimensi(dim)
    skor_k = hitung_skor_keseluruhan(skor_pd)
    raw: dict = {
        "konteks_pasar": [
            {
                "topik": "x",
                "konten": "y",
                "dampak_ke_bisnis": "z",
                "relevansi": "TINGGI",
                "sumber": "Laporan F&B 2026",
            }
        ]
    }
    merged = merge_deterministic_into_raw(
        payload=payload,
        skor_per_dimensi=skor_pd,
        skor_keseluruhan=skor_k,
        raw=raw,
        konteks_pasar_seed=None,
    )
    assert merged["konteks_pasar"] == []


def test_merge_kepatuhan_saran_picks_forward_looking_single() -> None:
    payload = JobPayload.model_validate(json.loads(FIXTURE_MIN.read_text(encoding="utf-8")))
    dim = payload.dimensi.model_dump(mode="json")
    skor_pd = skor_from_payload_dimensi(dim)
    skor_k = hitung_skor_keseluruhan(skor_pd)
    raw: dict = {
        "dimensi": {
            "kepatuhan": {
                "skor": 0,
                "status": "KRITIS",
                "narasi": "x",
                "saran": [
                    "Simpan bukti bayar di folder digital.",
                    "Dokumentasikan SOP pencatatan untuk persiapan ajukan kredit bank.",
                ],
            }
        }
    }
    merged = merge_deterministic_into_raw(
        payload=payload,
        skor_per_dimensi=skor_pd,
        skor_keseluruhan=skor_k,
        raw=raw,
    )
    saran = merged["dimensi"]["kepatuhan"]["saran"]
    assert isinstance(saran, list) and len(saran) == 1
    assert "sop" in saran[0].lower() or "bank" in saran[0].lower() or "kredit" in saran[0].lower()
