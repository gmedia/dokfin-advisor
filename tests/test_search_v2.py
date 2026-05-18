"""Tests for Node B - Indonesia-first search strategy."""

from __future__ import annotations

from advisor.schemas.input import JobPayload, ProfilBisnis
from advisor.search.filtering import is_international_only, relevance_score
from advisor.search.keywords import build_search_queries, enhance_keywords
from advisor.trusted_domains import (
    indonesia_domain_score,
    is_indonesia_domain,
)


def _make_payload(
    industri: str = "F&B",
    sub_industri: str = "Restoran",
    kota: str = "Jakarta",
) -> JobPayload:
    """Create a test payload with all required fields."""
    from advisor.schemas.input import IndikatorRow, IndikatorStatus, JobDimensions

    dummy_indikator = {"DUMMY_01": IndikatorRow(status=IndikatorStatus.SEHAT)}

    return JobPayload(
        job_id="550e8400-e29b-41d4-a716-446655440000",
        created_at="2026-05-01T00:00:00Z",
        profil_bisnis=ProfilBisnis(
            industri=industri,
            sub_industri=sub_industri,
            kota=kota,
            skala="UMKM",
            jumlah_karyawan=10,
            periode_analisis="Mei 2026",
            periode_bulan=5,
            periode_tahun=2026,
            kelengkapan_data_persen=100.0,
        ),
        dimensi=JobDimensions(
            likuiditas=dummy_indikator,
            profitabilitas=dummy_indikator,
            efisiensi=dummy_indikator,
            solvabilitas=dummy_indikator,
            sdm=dummy_indikator,
            kepatuhan=dummy_indikator,
        ),
    )


class TestIndonesiaDomainDetection:
    """Test Indonesian domain detection."""

    def test_gov_id_domain(self):
        """Should detect .go.id as Indonesian government domain."""
        assert is_indonesia_domain("https://bi.go.id/suku-bunga")
        assert is_indonesia_domain("https://kemenkop.go.id/umkm")
        assert is_indonesia_domain("https://jogjakota.go.id/perizinan")

    def test_co_id_domain(self):
        """Should detect .co.id as Indonesian commercial domain."""
        assert is_indonesia_domain("https://kontan.co.id")
        assert is_indonesia_domain("https://bisnis.co.id")
        assert is_indonesia_domain("https://industrifnb.id")

    def test_or_id_domain(self):
        """Should detect .or.id as Indonesian organization domain."""
        assert is_indonesia_domain("https://umkmindonesia.id")
        assert is_indonesia_domain("https://ukmindonesia.id")

    def test_international_domain_rejected(self):
        """Should reject international domains."""
        assert not is_indonesia_domain("https://asianbusinessreview.com")
        assert not is_indonesia_domain("https://hospitalitynet.org")
        assert not is_indonesia_domain("https://retailgazette.co.uk")
        assert not is_indonesia_domain("https://cnn.com")
        assert not is_indonesia_domain("https://reuters.com")


class TestIndonesiaDomainScore:
    """Test domain scoring priority."""

    def test_gov_id_highest_score(self):
        """Government domains should have highest score."""
        assert indonesia_domain_score("https://bi.go.id") == 1.0
        assert indonesia_domain_score("https://bps.go.id") == 1.0
        assert indonesia_domain_score("https://kemenkop.go.id") == 1.0

    def test_co_id_high_score(self):
        """Commercial ID domains should have high score."""
        assert indonesia_domain_score("https://kontan.co.id") == 0.8
        assert indonesia_domain_score("https://bisnis.co.id") == 0.8

    def test_known_media_moderate_score(self):
        """Known Indonesian media should have moderate score (even with .com)."""
        # These are .com domains but known Indonesian media
        assert indonesia_domain_score("https://kompas.com") == 0.6
        assert indonesia_domain_score("https://detik.com") == 0.6
        # These are proper .id domains
        assert indonesia_domain_score("https://harianjogja.com") == 0.6
        assert indonesia_domain_score("https://umkmindonesia.id") == 0.8

    def test_international_zero_score(self):
        """International domains should have zero score."""
        assert indonesia_domain_score("https://asianbusinessreview.com") == 0.0
        assert indonesia_domain_score("https://hospitalitynet.org") == 0.0


class TestInternationalContentDetection:
    """Test detection of purely international content."""

    def test_apac_content_rejected(self):
        """APAC content without Indonesia context should be detected."""
        result = {
            "title": "APAC retail investment jumps $7.2b as rents slide",
            "content": "Investasi ritel di Asia Pasifik naik tajam hingga 80%",
            "url": "https://asianbusinessreview.com/news/apac-retail",
        }
        assert is_international_only(result)

    def test_asean_without_indonesia_rejected(self):
        """ASEAN content without Indonesia should be detected."""
        result = {
            "title": "ASEAN F&B market trends 2026",
            "content": "Southeast Asia food and beverage industry growing",
            "url": "https://example.com/asean-fnb",
        }
        assert is_international_only(result)

    def test_indonesia_content_accepted(self):
        """Content with Indonesia context should NOT be detected as international only."""
        result = {
            "title": "UMKM Kuliner Indonesia Menanjak 2026",
            "content": "Bisnis kuliner di Indonesia tumbuh pesat",
            "url": "https://kompas.com/read/2026/04/fnb-indonesia",
        }
        assert not is_international_only(result)

    def test_apac_with_indonesia_accepted(self):
        """APAC content with Indonesia mention should be accepted."""
        result = {
            "title": "APAC F&B Growth Led by Indonesia",
            "content": "Indonesia leads ASEAN in restaurant investments",
            "url": "https://example.com/apac-fnb",
        }
        assert not is_international_only(result)


class TestKeywordEnhancement:
    """Test keyword enhancement with Indonesia context."""

    def test_basic_keyword_enhancement(self):
        """Should add Indonesia context to basic keywords."""
        payload = _make_payload(kota="Jakarta")

        keywords = enhance_keywords("tren penjualan f&b", payload)

        # Should have multiple variations
        assert len(keywords) >= 2
        # Original keyword should be first
        assert keywords[0] == "tren penjualan f&b"
        # Should have Indonesia variation
        assert any("indonesia" in kw.lower() for kw in keywords)

    def test_jogja_keyword_enhancement(self):
        """Should handle Jogja/Yogyakarta aliases."""
        payload = _make_payload(kota="Yogyakarta")

        keywords = enhance_keywords("tren kuliner", payload)

        # Should have city variations
        assert any("yogyakarta" in kw.lower() for kw in keywords)

    def test_fnb_industry_enhancement(self):
        """Should add F&B specific Indonesia keywords."""
        payload = _make_payload(industri="F&B Retail", kota="Bandung")

        keywords = enhance_keywords("benchmark likuiditas f&b", payload)

        # Should have Indonesia context variations
        assert any("indonesia" in kw.lower() for kw in keywords)
        # Original keyword should be preserved
        assert any("f&b" in kw.lower() or "likuiditas" in kw.lower() for kw in keywords)

    def test_build_search_queries_defaults_to_original_keywords_only(self):
        payload = _make_payload(industri="F&B Retail", kota="Yogyakarta")

        queries = build_search_queries(
            [
                "tren penjualan restoran Yogyakarta 2026",
                "kondisi likuiditas UMKM restoran Indonesia 2026",
                "strategi meningkatkan penjualan restoran UMKM 2026",
            ],
            payload,
        )

        assert len(queries) == 3
        assert queries == [(kw, kw) for kw, _query in queries]

    def test_build_search_queries_caps_enhancement_globally(self):
        payload = _make_payload(industri="F&B Retail", kota="Yogyakarta")

        queries = build_search_queries(
            [
                "tren penjualan restoran Yogyakarta 2026",
                "kondisi likuiditas UMKM restoran Indonesia 2026",
                "strategi meningkatkan penjualan restoran UMKM 2026",
            ],
            payload,
            enable_enhancement=True,
            max_enhanced_total=1,
        )

        assert len(queries) == 4
        assert queries[:3] == [(kw, kw) for kw, _query in queries[:3]]
        assert queries[3][0] in {kw for kw, _query in queries[:3]}

    def test_build_search_queries_can_use_one_best_keyword(self):
        payload = _make_payload(industri="F&B Retail", kota="Yogyakarta")

        queries = build_search_queries(
            [
                "kondisi likuiditas UMKM restoran Indonesia 2026",
                "tren penjualan restoran Yogyakarta 2026",
            ],
            payload,
            max_keywords=1,
        )

        assert queries == [
            (
                "kondisi likuiditas UMKM restoran Indonesia 2026",
                "kondisi likuiditas UMKM restoran Indonesia 2026",
            )
        ]


class TestRelevanceScoring:
    """Test v2 relevance scoring."""

    def test_indonesia_domain_gets_high_score(self):
        """Indonesian domains should get high relevance scores."""
        payload = _make_payload(kota="Jakarta")

        result = {
            "title": "UMKM Kuliner Indonesia",
            "content": "Bisnis kuliner di Indonesia",
            "url": "https://kompas.com/read/2026/umkm-kuliner",
        }

        score = relevance_score(result, payload=payload, keyword="tren kuliner indonesia")
        # Should have high score due to .com domain (known media)
        assert score > 0.5

    def test_gov_id_gets_highest_score(self):
        """Government ID domains should get highest scores."""
        payload = _make_payload(kota="Jakarta")

        result = {
            "title": "Data UMKM 2026",
            "content": "Statistik usaha kecil menengah",
            "url": "https://bps.go.id/umkm-2026",
        }

        score = relevance_score(result, payload=payload, keyword="data umkm")
        # Should have very high score (1.0 domain score * 5.0 weight)
        assert score >= 5.0

    def test_international_only_gets_negative_score(self):
        """Purely international content should be rejected."""
        payload = _make_payload(kota="Jakarta")

        result = {
            "title": "APAC Retail Investment",
            "content": "Asia Pacific retail growing",
            "url": "https://asianbusinessreview.com/apac-retail",
        }

        score = relevance_score(result, payload=payload, keyword="tren retail")
        # Should be rejected
        assert score == -1.0

    def test_location_match_boosts_score(self):
        """Matching location should boost score."""
        payload = _make_payload(kota="Yogyakarta")

        result = {
            "title": "Kuliner Yogyakarta 2026",
            "content": "Tren kuliner di Yogyakarta",
            "url": "https://harianjogja.com/kuliner",
        }

        score = relevance_score(result, payload=payload, keyword="tren kuliner")
        # Should have bonus for location match
        assert score > 0.5

    def test_jogja_alias_matches_yogyakarta(self):
        """Jogja alias should match Yogyakarta."""
        payload = _make_payload(kota="Yogyakarta")

        result = {
            "title": "Kuliner Jogja",
            "content": "Makanan khas Jogja",
            "url": "https://krjogja.com/kuliner",
        }

        score = relevance_score(result, payload=payload, keyword="tren kuliner")
        # Should match jogja even though kota is Yogyakarta
        assert score > 0.5


class TestEdgeCases:
    """Test edge cases."""

    def test_empty_url(self):
        """Empty URL should return zero score."""
        assert indonesia_domain_score("") == 0.0
        assert not is_indonesia_domain("")

    def test_subdomain_handling(self):
        """Should handle subdomains correctly."""
        assert is_indonesia_domain("https://news.kompas.com")
        assert is_indonesia_domain("https://finance.detik.com")
        assert is_indonesia_domain("https://www.bi.go.id")

    def test_case_insensitive(self):
        """Should be case insensitive."""
        assert is_indonesia_domain("https://BI.GO.ID")
        assert is_indonesia_domain("https://KOMPAS.COM")

    def test_keyword_with_existing_indonesia(self):
        """Should not duplicate Indonesia if already present."""
        payload = _make_payload(kota="Jakarta")

        keywords = enhance_keywords("tren kuliner indonesia", payload)

        # Should not create "indonesia indonesia"
        assert all(keywords.count(kw) == 1 for kw in keywords)
