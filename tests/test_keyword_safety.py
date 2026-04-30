"""Tests for Tavily keyword sanitization (PRD 5.3)."""

from __future__ import annotations

from advisor.keyword_safety import sanitize_search_keywords


def test_accepts_clean_keywords() -> None:
    kws = [
        "tren harga bahan baku restoran indonesia",
        "kondisi likuiditas umkm kuliner",
    ]
    out = sanitize_search_keywords(kws)
    assert len(out) == 2
    assert "restoran" in out[0]


def test_rejects_numbers_and_rp() -> None:
    kws = [
        "current ratio 0.8 restoran",
        "tren harga bahan baku umkm",
    ]
    out = sanitize_search_keywords(kws)
    assert len(out) <= 3
    assert all("0.8" not in x for x in out)
    assert "tren harga bahan baku umkm" in out


def test_allows_year_and_quarter_time_markers() -> None:
    kws = [
        "tren harga bahan baku restoran yogyakarta 2026",
        "benchmark margin restoran kecil indonesia q1 2026",
    ]
    out = sanitize_search_keywords(kws)
    assert "2026" in out[0]
    assert "q1" in out[1]


def test_max_three_items() -> None:
    kws = [
        "satu keyword panjang untuk uji",
        "dua keyword panjang untuk uji",
        "tiga keyword panjang",
        "empat keyword panjang",
    ]
    out = sanitize_search_keywords(kws, max_items=3)
    assert len(out) == 3


def test_fallback_when_all_bad() -> None:
    out = sanitize_search_keywords(["Rp 45 juta", "stok 18 juta"])
    assert len(out) >= 1
    assert "umkm" in out[0].lower()
