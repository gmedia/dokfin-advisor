"""Unit tests: filter hasil Tavily & merge transparansi konteks_pasar."""

from __future__ import annotations

from datetime import date, timedelta

from advisor.merge_output import merge_konteks_pasar_transparency
from advisor.search_filters import filter_tavily_results


def test_filter_drops_old_and_short() -> None:
    ref = date(2026, 4, 30)
    trusted = {"bi.go.id", "kontan.co.id"}
    old = (ref - timedelta(days=200)).isoformat()
    results = [
        {
            "url": "https://bi.go.id/a",
            "title": "A",
            "content": "word " * 30,
            "score": 0.9,
            "published_date": old,
        },
        {
            "url": "https://kontan.co.id/b",
            "title": "B",
            "content": "short",
            "score": 0.8,
        },
        {
            "url": "https://bi.go.id/c",
            "title": "C",
            "content": "word " * 30,
            "score": 0.7,
            "published_date": ref.isoformat(),
        },
    ]
    out = filter_tavily_results(
        results,
        trusted_domains=trusted,
        reference_date=ref,
        max_keep=3,
        min_words=20,
    )
    assert len(out) == 1
    assert "c" in out[0]["url"]


def test_filter_drop_undated_excludes_when_enabled() -> None:
    ref = date(2026, 4, 30)
    trusted: set[str] = set()
    results = [
        {
            "url": "https://x/oldstyle",
            "title": "u",
            "content": "word " * 30,
            "score": 0.9,
        },
        {
            "url": "https://x/dated",
            "title": "d",
            "content": "word " * 30,
            "score": 0.5,
            "published_date": ref.isoformat(),
        },
    ]
    out = filter_tavily_results(
        results,
        trusted_domains=trusted,
        reference_date=ref,
        max_keep=3,
        min_words=20,
        drop_undated=True,
    )
    assert len(out) == 1
    assert "dated" in out[0]["url"]


def test_filter_max_three_by_score() -> None:
    ref = date(2026, 4, 30)
    trusted: set[str] = set()
    results = [
        {"url": "https://x/1", "title": "a", "content": "w " * 50, "score": 0.1},
        {"url": "https://x/2", "title": "b", "content": "w " * 50, "score": 0.9},
        {"url": "https://x/3", "title": "c", "content": "w " * 50, "score": 0.5},
        {"url": "https://x/4", "title": "d", "content": "w " * 50, "score": 0.8},
    ]
    out = filter_tavily_results(
        results,
        trusted_domains=trusted,
        reference_date=ref,
        max_keep=3,
        min_words=10,
    )
    assert len(out) == 3
    scores = [r["score"] for r in out]
    assert scores == sorted(scores, reverse=True)


def test_merge_fills_diakses_pada_from_seed() -> None:
    out: dict = {
        "konteks_pasar": [
            {
                "topik": "x",
                "konten": "y",
                "dampak_ke_bisnis": "z",
                "relevansi": "TINGGI",
                "sumber": "bi.go.id",
            }
        ]
    }
    seed = [
        {
            "topik": "x",
            "konten": "y",
            "dampak_ke_bisnis": "z",
            "relevansi": "TINGGI",
            "sumber": "bi.go.id",
            "diakses_pada": "2026-04-30",
        }
    ]
    merge_konteks_pasar_transparency(out, seed)
    assert out["konteks_pasar"][0]["diakses_pada"] == "2026-04-30"


def test_merge_empty_kp_uses_seed() -> None:
    out: dict = {"konteks_pasar": []}
    seed = [
        {
            "topik": "t",
            "konten": "k",
            "dampak_ke_bisnis": "d",
            "relevansi": "TINGGI",
            "sumber": "ojk.go.id",
            "diakses_pada": "2026-04-01",
        }
    ]
    merge_konteks_pasar_transparency(out, seed)
    assert len(out["konteks_pasar"]) == 1
    assert out["konteks_pasar"][0]["sumber"] == "ojk.go.id"
