"""Unit tests: filter hasil Tavily & merge transparansi konteks_pasar."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from unittest.mock import patch

from advisor.merge_output import merge_konteks_pasar_transparency
from advisor.search.formatter import build_seeds
from advisor.search.filtering import filter_and_rank, pick_indonesia_first
from advisor.search_filters import filter_tavily_results


def test_filter_drops_old_and_short() -> None:
    ref = date(2026, 4, 30)
    trusted = {"bi.go.id", "kontan.co.id"}
    old = (ref - timedelta(days=200)).isoformat()
    results = [
        {
            "url": "https://bi.go.id/a",
            "title": "A",
            "content": "word " * 80,
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
            "content": "word " * 80,
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
    # Tanpa max_age: artikel lama tidak dibuang di sisi klien (freshness lewat Tavily ``days``).
    assert len(out) == 2
    urls = "".join(r["url"] for r in out)
    assert "c" in urls and "a" in urls


def test_filter_drop_undated_excludes_when_enabled() -> None:
    ref = date(2026, 4, 30)
    trusted: set[str] = set()
    results = [
        {
            "url": "https://x/oldstyle",
            "title": "u",
            "content": "word " * 80,
            "score": 0.9,
        },
        {
            "url": "https://x/dated",
            "title": "d",
            "content": "word " * 80,
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


def test_filter_drops_pdf_results() -> None:
    ref = date(2026, 4, 30)
    trusted: set[str] = set()
    results = [
        {
            "url": "https://ojk.go.id/report.pdf",
            "title": "Laporan X",
            "content": "word " * 200,
            "score": 0.9,
            "published_date": ref.isoformat(),
        },
        {
            "url": "https://kemenkeu.go.id/ok",
            "title": "[PDF] KEM PPKF 2026",
            "content": "word " * 200,
            "score": 0.8,
            "published_date": ref.isoformat(),
        },
        {
            "url": "https://kontan.co.id/read/20260430/ok",
            "title": "Berita UMKM F&B",
            "content": "word " * 200,
            "score": 0.1,
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
    assert "kontan.co.id" in out[0]["url"]


def test_filter_drops_toc_like_content() -> None:
    ref = date(2026, 4, 30)
    trusted: set[str] = set()
    toc = "\n".join([f"Tabel {i} ..." for i in range(1, 80)])
    results = [
        {
            "url": "https://x/1",
            "title": "Daftar isi - Laporan Bulanan",
            "content": toc,
            "score": 0.9,
            "published_date": ref.isoformat(),
        },
        {
            "url": "https://x/2",
            "title": "Narasi konsumsi F&B Yogyakarta 2026",
            "content": "Ini narasi panjang. " * 50,
            "score": 0.1,
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
    assert out[0]["url"].endswith("/2")


def test_filter_rejects_subdomain_when_allow_subdomains_disabled() -> None:
    ref = date(2026, 4, 30)
    trusted = {"kompas.com"}
    results = [
        {
            "url": "https://cahaya.kompas.com/x",
            "title": "X",
            "content": "word " * 80,
            "score": 0.9,
            "published_date": ref.isoformat(),
        },
        {
            "url": "https://kompas.com/y",
            "title": "Y",
            "content": "word " * 80,
            "score": 0.1,
            "published_date": ref.isoformat(),
        },
    ]
    with patch.dict("os.environ", {"TAVILY_ALLOW_SUBDOMAINS": "0"}, clear=False):
        out = filter_tavily_results(
            results,
            trusted_domains=trusted,
            reference_date=ref,
            max_keep=3,
            min_words=20,
        )
    assert len(out) == 1
    assert out[0]["url"].startswith("https://kompas.com/")


def test_filter_two_pass_example_primary_empty_then_fallback_hits() -> None:
    ref = date(2026, 4, 30)
    trusted: set[str] = set()
    older = (ref - timedelta(days=40)).isoformat()
    results = [
        {
            "url": "https://x/older",
            "title": "Old",
            "content": "word " * 80,
            "score": 0.5,
            "published_date": older,
        }
    ]
    # Primary 30d should drop it
    primary = filter_tavily_results(
        results,
        trusted_domains=trusted,
        reference_date=ref,
        max_keep=3,
        min_words=20,
        max_age=timedelta(days=30),
    )
    assert primary == []
    # Fallback 60d should accept it
    fallback = filter_tavily_results(
        results,
        trusted_domains=trusted,
        reference_date=ref,
        max_keep=3,
        min_words=20,
        max_age=timedelta(days=60),
    )
    assert len(fallback) == 1


def test_filter_parses_url_date_and_drops_old_when_metadata_missing() -> None:
    ref = date(2026, 4, 30)
    trusted: set[str] = set()
    # URL contains YYYYMMDD=20250929 (older than 6 months from ref)
    results = [
        {
            "url": "https://semarang.bisnis.com/read/20250929/536/1915476/foo",
            "title": "Old",
            "content": "word " * 80,
            "score": 0.9,
        },
        {
            "url": "https://kontan.co.id/read/20260410/123/ok",
            "title": "New",
            "content": "word " * 80,
            "score": 0.1,
        },
    ]
    out = filter_tavily_results(
        results,
        trusted_domains=trusted,
        reference_date=ref,
        max_keep=3,
        min_words=20,
        max_age=timedelta(days=183),
        drop_undated=False,
    )
    assert len(out) == 1
    assert "20260410" in out[0]["url"]


def test_filter_parses_id_date_from_snippet_when_url_has_no_date() -> None:
    ref = date(2026, 4, 30)
    trusted: set[str] = set()
    results = [
        {
            "url": "https://tempo.co/x",
            "title": "Yogyakarta Bangkitkan Pariwisata Lewat UMKM Kuliner",
            "content": "8 April 2021 | 16.02 WIB. " + ("word " * 200),
            "score": 0.9,
        },
        {
            "url": "https://tempo.co/y",
            "title": "Yogyakarta Bangkitkan Pariwisata Lewat UMKM Kuliner",
            "content": "10 April 2026 | 21.18 WIB. " + ("word " * 200),
            "score": 0.1,
        },
    ]
    out = filter_tavily_results(
        results,
        trusted_domains=trusted,
        reference_date=ref,
        max_keep=3,
        min_words=20,
        max_age=timedelta(days=183),
        drop_undated=False,
    )
    assert len(out) == 1
    assert out[0]["url"].endswith("/y")


def test_filter_parses_kontan_style_date_from_snippet() -> None:
    ref = date(2026, 4, 30)
    trusted: set[str] = set()
    results = [
        {
            "url": "https://investasi.kontan.co.id/news/a",
            "title": "Emiten Restoran dan Gerai F&B Diproyeksi Raup Cuan Gede Tahun Ini",
            "content": "Kamis, 05 Januari 2023 / 05:15 WIB. " + ("word " * 200),
            "score": 0.9,
        },
        {
            "url": "https://industri.kontan.co.id/news/b",
            "title": "Erajaya (ERAA) Optimalkan Potensi Ritel, Lifestyle, dan F&B 2026",
            "content": "Senin, 05 Januari 2026 / 19:36 WIB. " + ("word " * 200),
            "score": 0.1,
        },
    ]
    out = filter_tavily_results(
        results,
        trusted_domains=trusted,
        reference_date=ref,
        max_keep=3,
        min_words=20,
        max_age=timedelta(days=183),
        drop_undated=False,
    )
    assert len(out) == 1
    assert out[0]["url"].endswith("/b")


def test_filter_prefers_diverse_root_domains() -> None:
    ref = date(2026, 4, 30)
    trusted: set[str] = set()
    # Two results from *.bisnis.com (root: bisnis.com), one from kontan.co.id
    results = [
        {
            "url": "https://semarang.bisnis.com/read/20260410/aaa/a",
            "title": "A",
            "content": "word " * 80,
            "score": 0.95,
            "published_date": ref.isoformat(),
        },
        {
            "url": "https://investasi.bisnis.com/read/20260411/bbb/b",
            "title": "B",
            "content": "word " * 80,
            "score": 0.9,
            "published_date": ref.isoformat(),
        },
        {
            "url": "https://kontan.co.id/read/20260409/ccc/c",
            "title": "C",
            "content": "word " * 80,
            "score": 0.2,
            "published_date": ref.isoformat(),
        },
    ]
    out = filter_tavily_results(
        results,
        trusted_domains=trusted,
        reference_date=ref,
        max_keep=2,
        min_words=20,
    )
    urls = [r["url"] for r in out]
    assert any("bisnis.com" in u for u in urls)
    assert any("kontan.co.id" in u for u in urls)


def test_filter_max_three_by_score() -> None:
    ref = date(2026, 4, 30)
    trusted: set[str] = set()
    results = [
        {"url": "https://x/1", "title": "a", "content": "w " * 200, "score": 0.1},
        {"url": "https://x/2", "title": "b", "content": "w " * 200, "score": 0.9},
        {"url": "https://x/3", "title": "c", "content": "w " * 200, "score": 0.5},
        {"url": "https://x/4", "title": "d", "content": "w " * 200, "score": 0.8},
    ]
    out = filter_tavily_results(
        results,
        trusted_domains=trusted,
        reference_date=ref,
        max_keep=3,
        min_words=10,
    )
    assert len(out) == 3
    # Order should still be descending by (adjusted) score; compare positions by url.
    urls = [r["url"] for r in out]
    assert urls[0].endswith("/2")


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
            "diterbitkan_pada": "2026-04-10",
        }
    ]
    merge_konteks_pasar_transparency(out, seed)
    assert out["konteks_pasar"][0]["diakses_pada"] == "2026-04-30"
    assert out["konteks_pasar"][0]["diterbitkan_pada"] == "2026-04-10"


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


def test_build_seeds_labels_stale_content() -> None:
    ref_dt = datetime(2026, 4, 30, tzinfo=UTC)
    picked = [
        {
            "url": "https://kontan.co.id/read/20260112/x/y",
            "title": "T",
            "content": "isi konten",
        }
    ]
    seeds = build_seeds(
        picked,
        "2026-04-30",
        reference_dt=ref_dt,
        primary_days=30,
    )
    assert seeds[0]["konten"].startswith("Catatan: artikel dari 2026-01-12")


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
    # bisnis.com subdomains share root domain so only one gets picked; kontan gets the other slot
    urls = [r["url"] for r in out]
    bisnis_count = sum(1 for u in urls if "bisnis.com" in u)
    assert bisnis_count <= 1
    assert any("kontan.co.id" in u for u in urls)
