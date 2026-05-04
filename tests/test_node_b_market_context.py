"""Unit tests: Node B relevance scoring + Indonesia-first picking."""

from __future__ import annotations

from advisor.search.filtering import filter_and_rank, pick_indonesia_first
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


def test_filter_and_rank_prefers_fnb_content_over_unrelated() -> None:
    payload = _payload_fnb_jogja()
    results = [
        {
            "url": "https://kontan.co.id/read/20260430/bbb/fnb",
            "title": "Tren kuliner dan restoran di Jogja 2026",
            "content": "Pembahasan UMKM restoran dan kuliner di Yogyakarta. " * 30,
            "score": 0.1,
        },
    ]
    out = filter_and_rank(
        results,
        payload=payload,
        keyword="tren penjualan f&b yogyakarta maret 2026",
        min_relevance=0.5,
    )
    assert len(out) == 1
    assert "fnb" in out[0]["url"]


def test_filter_and_rank_scores_id_domains_higher() -> None:
    """Government .go.id should score higher than .com domain."""
    payload = _payload_fnb_jogja()
    results = [
        {
            "url": "https://bps.go.id/umkm-2026",
            "title": "Data UMKM restoran Indonesia 2026",
            "content": "Statistik usaha kuliner restoran UMKM di Indonesia. " * 30,
            "score": 0.5,
        },
        {
            "url": "https://example.com/fnb-report",
            "title": "Tren kuliner dan restoran 2026",
            "content": "Bisnis kuliner restoran di Indonesia. " * 30,
            "score": 0.5,
        },
    ]
    out = filter_and_rank(
        results,
        payload=payload,
        keyword="tren penjualan f&b yogyakarta maret 2026",
        min_relevance=0.5,
    )
    assert len(out) >= 1
    # bps.go.id should be first (highest domain score 1.0 * 5.0)
    assert "bps.go.id" in out[0]["url"]


def test_pick_indonesia_first_prefers_id_sources_and_caps() -> None:
    candidates = [
        {
            "url": "https://semarang.bisnis.com/read/20260430/a",
            "_relevance": 3.0,
            "_original_kw": "k1",
        },
        {
            "url": "https://investasi.bisnis.com/read/20260430/b",
            "_relevance": 2.0,
            "_original_kw": "k2",
        },
        {
            "url": "https://tempo.co/read/20260430/c",
            "_relevance": 2.5,
            "_original_kw": "k3",
        },
        {
            "url": "https://kontan.co.id/read/20260430/d",
            "_relevance": 2.5,
            "_original_kw": "k3",
        },
    ]
    picked = pick_indonesia_first(candidates, max_total=3)
    assert len(picked) <= 3
    # All 4 are Indonesian media; should pick 3 with diversity
    urls = [r["url"] for r in picked]
    # Different root domains should be selected (bisnis, tempo, kontan)
    assert len(set(u.split("/")[2] for u in urls)) == len(urls)
