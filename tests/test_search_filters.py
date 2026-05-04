"""Unit tests: merge transparansi konteks_pasar & pick Indonesia-first."""

from __future__ import annotations

from advisor.merge_output import merge_konteks_pasar_transparency
from advisor.search.filtering import pick_indonesia_first


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


def test_merge_replaces_llm_non_hostname_sources_with_seed() -> None:
    out: dict = {
        "konteks_pasar": [
            {
                "topik": "t",
                "konten": "k",
                "dampak_ke_bisnis": "d",
                "relevansi": "TINGGI",
                "sumber": "Laporan Tren F&B Yogyakarta Q1 2026",
                "diakses_pada": None,
            }
        ]
    }
    seed = [
        {
            "topik": "x",
            "konten": "y",
            "dampak_ke_bisnis": "z",
            "relevansi": "TINGGI",
            "sumber": "kompas.com",
            "diakses_pada": "2026-04-30",
        }
    ]
    merge_konteks_pasar_transparency(out, seed)
    assert out["konteks_pasar"][0]["sumber"] == "kompas.com"
    assert out["konteks_pasar"][0]["diakses_pada"] == "2026-04-30"


def test_pick_indonesia_first_returns_diverse_domains() -> None:
    candidates = [
        {"url": "https://kontan.co.id/read/20260425/a/a", "title": "New A", "content": "isi a"},
        {"url": "https://kompas.com/read/20260112/b/b", "title": "Old B", "content": "isi b"},
    ]
    out = pick_indonesia_first(candidates, max_total=3)
    assert len(out) == 2
    urls = {r["url"] for r in out}
    assert any("kontan" in u for u in urls)
    assert any("kompas" in u for u in urls)


def test_pick_indonesia_first_deduplicates_same_root_domain() -> None:
    candidates = [
        {"url": "https://semarang.bisnis.com/read/20260425/a/a", "title": "A", "content": "isi"},
        {"url": "https://investasi.bisnis.com/read/20260112/b/b", "title": "B", "content": "isi"},
        {"url": "https://kontan.co.id/read/20260430/c/c", "title": "C", "content": "isi"},
    ]
    out = pick_indonesia_first(candidates, max_total=3)
    urls = [r["url"] for r in out]
    bisnis_count = sum(1 for u in urls if "bisnis.com" in u)
    assert bisnis_count <= 1
    assert any("kontan.co.id" in u for u in urls)
