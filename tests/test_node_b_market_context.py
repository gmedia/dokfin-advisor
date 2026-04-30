"""Unit tests: Node B relevance scoring + global cap picking."""

from __future__ import annotations

from advisor.nodes.search import _pick_global_results, _rank_and_filter_by_relevance
from advisor.schemas.input import JobPayload


def _payload_fnb_jogja() -> JobPayload:
    return JobPayload.model_validate(
        {
            "job_id": "550e8400-e29b-41d4-a716-446655440000",
            "created_at": "2026-04-30T00:00:00Z",
            "profil_bisnis": {
                "industri": "F&B",
                "sub_industri": "Restoran",
                "kota": "Yogyakarta",
                "skala": "mikro",
                "jumlah_karyawan": 5,
                "periode_analisis": "bulanan",
                "periode_bulan": 3,
                "periode_tahun": 2026,
                "kelengkapan_data_persen": 100,
                "skor_keseluruhan_periode_sebelumnya": None,
            },
            "dimensi": {
                "likuiditas": {},
                "profitabilitas": {},
                "efisiensi": {},
                "solvabilitas": {},
                "sdm": {},
                "kepatuhan": {},
            },
        }
    )


def test_rank_and_filter_by_relevance_requires_keyword_or_profile_match() -> None:
    payload = _payload_fnb_jogja()
    results = [
        {
            "url": "https://kontan.co.id/read/20260430/aaa/mobil",
            "title": "Penjualan mobil baru membaik",
            "content": "word " * 200,
            "score": 0.9,
        },
        {
            "url": "https://kontan.co.id/read/20260430/bbb/fnb",
            "title": "Tren kuliner dan restoran di Jogja 2026",
            "content": "Pembahasan UMKM restoran dan kuliner di Yogyakarta. " * 30,
            "score": 0.1,
        },
    ]
    out = _rank_and_filter_by_relevance(
        results,
        payload=payload,
        keyword="tren penjualan f&b yogyakarta maret 2026",
        min_relevance=1.0,
    )
    assert len(out) == 1
    assert "fnb" in out[0]["url"]
    assert out[0]["score"] > 0.1


def test_pick_global_results_caps_and_prefers_diversity() -> None:
    candidates = [
        {
            "url": "https://semarang.bisnis.com/read/20260430/a",
            "score": 0.9,
            "_relevance": 3.0,
            "_kw": "k1",
        },
        {
            "url": "https://investasi.bisnis.com/read/20260430/b",
            "score": 0.8,
            "_relevance": 2.0,
            "_kw": "k2",
        },
        {
            "url": "https://tempo.co/read/20260430/c",
            "score": 0.7,
            "_relevance": 2.5,
            "_kw": "k3",
        },
        {
            "url": "https://kontan.co.id/read/20260430/d",
            "score": 0.6,
            "_relevance": 2.5,
            "_kw": "k3",
        },
    ]
    picked = _pick_global_results(candidates, min_total=2, max_total=3)
    assert 2 <= len(picked) <= 3
    urls = [r["url"] for r in picked]
    # At least one non-bisnis.com root domain should be present.
    assert any("tempo.co" in u or "kontan.co.id" in u for u in urls)
