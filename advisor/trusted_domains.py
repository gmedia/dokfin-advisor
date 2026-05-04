"""Domain Indonesia terpercaya untuk pembatasan hasil Tavily (Node B)."""

from __future__ import annotations

import os

from advisor.search_filters import hostname_from_url

DEFAULT_TRUSTED_DOMAINS: tuple[str, ...] = (
    # ── PEMERINTAH & REGULATOR ──────────────────────────────────────
    "bi.go.id",  # Bank Indonesia — suku bunga, inflasi, kurs
    "bps.go.id",  # Badan Pusat Statistik — data ekonomi resmi
    "kemenkeu.go.id",  # Kementerian Keuangan — kebijakan fiskal
    "ojk.go.id",  # OJK — regulasi keuangan, kredit UMKM
    "kemendag.go.id",  # Kementerian Perdagangan — tren ekspor impor
    "kemenperin.go.id",  # Kementerian Perindustrian — data industri
    "kemenkop.go.id",  # Kementerian Koperasi & UMKM — kebijakan UMKM
    "bkpm.go.id",  # BKPM/Investasi — data investasi sektoral
    "jogjaprov.go.id",  # Pemprov DIY — kebijakan lokal Yogyakarta
    "jogjakota.go.id",  # Pemkot Yogyakarta — regulasi kota
    # ── MEDIA KEUANGAN & BISNIS NASIONAL ────────────────────────────
    "kontan.co.id",  # Media keuangan terpercaya, coverage UMKM bagus
    "bisnis.com",  # Media bisnis, data industri F&B sering muncul
    "cnbcindonesia.com",  # Ekonomi makro, pasar modal
    "katadata.co.id",  # Data ekonomi, visualisasi statistik terpercaya
    "ddtc.co.id",  # Spesialis pajak — relevan untuk kepatuhan
    "wartaekonomi.co.id",  # Ekonomi & bisnis, coverage UMKM
    "investor.id",  # Pasar modal & bisnis
    "beritasatu.com",  # Ekonomi & bisnis umum
    # ── MEDIA UMUM NASIONAL TERPERCAYA ──────────────────────────────
    "kompas.com",  # Terpercaya, coverage ekonomi & UMKM luas
    "tempo.co",  # Investigatif, data ekonomi solid
    "detik.com",  # Traffic tinggi, breaking news ekonomi
    "republika.co.id",  # Coverage ekonomi syariah & UMKM
    "mediaindonesia.com",  # Ekonomi & kebijakan pemerintah
    "sindonews.com",  # Ekonomi & bisnis
    "jpnn.com",  # Coverage UMKM & daerah cukup bagus
    # ── MEDIA LOKAL YOGYAKARTA & JAWA TENGAH ────────────────────────
    "harianjogja.com",  # Koran utama Yogyakarta — sangat relevan
    "krjogja.com",  # Kedaulatan Rakyat Jogja — lokal terpercaya
    "tribunjogja.com",  # Tribun Jogja — berita ekonomi lokal
    "solopos.com",  # Solo/Jateng — coverage ekonomi regional bagus
    "radarjogja.co.id",  # Radar Jogja — bisnis & UMKM lokal
    "jatengprov.go.id",  # Pemprov Jateng — data regional
    # ── MEDIA INDUSTRI F&B & UMKM SPESIFIK ─────────────────────────
    "foodreview.co.id",  # Spesialis industri F&B Indonesia
    "industrifnb.id",  # Coverage khusus industri makanan minuman
    "umkmindonesia.id",  # Portal UMKM resmi
    "ukmindonesia.id",  # Edukasi & data UMKM
)


def trusted_domains_for_tavily() -> list[str] | None:
    """Daftar domain untuk `include_domains` Tavily. None = tidak membatasi domain."""
    if os.environ.get("TAVILY_WHITELIST_ENABLED", "1") != "1":
        return None
    custom = os.environ.get("TAVILY_TRUSTED_DOMAINS", "").strip()
    if custom:
        out = []
        for part in custom.split(","):
            d = part.strip().lower()
            if d.startswith("www."):
                d = d[4:]
            if d:
                out.append(d)
        return out or None
    return list(DEFAULT_TRUSTED_DOMAINS)


def trusted_domain_set() -> set[str]:
    """Set untuk verifikasi pasca-respons."""
    d = trusted_domains_for_tavily()
    if not d:
        return set()
    return set(d)


# ── DOMAIN DETECTION & SCORING ───────────────────────────────────────────────

_GOV_PATTERNS: tuple[str, ...] = (".go.id", ".mil.id", ".desa.id")

_ID_PATTERNS: tuple[str, ...] = (
    ".co.id", ".or.id", ".ac.id", ".sch.id",
    ".web.id", ".biz.id", ".my.id", ".id",
)

_ALL_ID_PATTERNS: tuple[str, ...] = _GOV_PATTERNS + _ID_PATTERNS

# Known Indonesian media that use international TLDs (.com, .net, etc.)
_KNOWN_ID_MEDIA: tuple[str, ...] = (
    "kompas", "detik", "tempo", "kontan", "bisnis", "cnnindonesia",
    "liputan6", "merdeka", "okezone", "tribun", "suara", "republika",
    "antara", "viva", "medcom", "inews", "beritasatu", "sindonews",
    "harianjogja", "krjogja", "radarjogja", "solopos", "jpnn",
    "cnbcindonesia", "katadata", "wartaekonomi",
)


def is_indonesia_domain(url: str) -> bool:
    """Return True jika URL dari domain Indonesia atau media Indonesia yang dikenal."""
    host = hostname_from_url(url).lower()
    if not host:
        return False
    if any(host.endswith(p) for p in _ALL_ID_PATTERNS):
        return True
    return any(media in host for media in _KNOWN_ID_MEDIA)


def indonesia_domain_score(url: str) -> float:
    """
    Score domain berdasarkan prioritas Indonesia.

    Returns:
        1.0 = pemerintah (.go.id, .mil.id, .desa.id)
        0.8 = komersial/institusi Indonesia (.co.id, .or.id, .ac.id, .id, ...)
        0.6 = media Indonesia dikenal (kompas.com, detik.com, ...)
        0.0 = internasional
    """
    host = hostname_from_url(url).lower()
    if not host:
        return 0.0
    if any(host.endswith(p) for p in _GOV_PATTERNS):
        return 1.0
    if any(host.endswith(p) for p in _ID_PATTERNS):
        return 0.8
    if any(media in host for media in _KNOWN_ID_MEDIA):
        return 0.6
    return 0.0
