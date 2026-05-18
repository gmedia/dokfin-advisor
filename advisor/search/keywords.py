"""Keyword enhancement untuk Indonesia-first search strategy."""

from __future__ import annotations

from advisor.schemas.input import JobPayload

CITY_ALIASES: dict[str, list[str]] = {
    "yogyakarta": ["yogyakarta", "jogja"],
    "kota yogyakarta": ["yogyakarta", "jogja"],
    "d.i. yogyakarta": ["yogyakarta", "jogja", "diy"],
    "diy": ["yogyakarta", "jogja", "diy"],
    "jogja": ["jogja", "yogyakarta"],
    "jakarta": ["jakarta"],
    "jakarta pusat": ["jakarta"],
    "jakarta selatan": ["jakarta"],
    "jakarta barat": ["jakarta"],
    "jakarta utara": ["jakarta"],
    "jakarta timur": ["jakarta"],
    "surabaya": ["surabaya"],
    "bandung": ["bandung"],
    "medan": ["medan"],
    "semarang": ["semarang"],
    "makassar": ["makassar"],
    "solo": ["solo", "surakarta"],
    "surakarta": ["surakarta", "solo"],
    "malang": ["malang"],
    "denpasar": ["denpasar", "bali"],
    "bali": ["bali", "denpasar"],
}

INDUSTRY_KEYWORD_MAP: dict[str, tuple[str, ...]] = {
    "f&b": ("kuliner indonesia", "restoran indonesia", "fnb indonesia"),
    "fnb": ("kuliner indonesia", "restoran indonesia", "fnb indonesia"),
    "food": ("kuliner indonesia", "makanan minuman indonesia"),
    "retail": ("ritel indonesia", "penjualan eceran indonesia"),
    "ritel": ("ritel indonesia", "penjualan eceran indonesia"),
    "manufaktur": ("manufaktur indonesia", "industri pengolahan indonesia"),
    "manufacture": ("manufaktur indonesia", "industri pengolahan indonesia"),
    "jasa": ("jasa indonesia", "layanan bisnis indonesia"),
    "service": ("jasa indonesia", "layanan bisnis indonesia"),
    "fashion": ("fashion indonesia", "industri tekstil indonesia"),
    "properti": ("properti indonesia", "real estate indonesia"),
    "teknologi": ("startup teknologi indonesia", "industri digital indonesia"),
    "pertanian": ("agribisnis indonesia", "pertanian indonesia"),
    "pendidikan": ("pendidikan indonesia", "edukasi indonesia"),
    "kesehatan": ("kesehatan indonesia", "industri medis indonesia"),
}


def enhance_keywords(keyword: str, payload: JobPayload) -> list[str]:
    """
    Buat variasi keyword dengan konteks Indonesia yang kuat.
    Mengembalikan list terurut (max 4), mulai dari paling spesifik.
    """
    industri = (payload.profil_bisnis.industri or "").lower().strip()
    kota = (payload.profil_bisnis.kota or "").lower().strip()

    variants: list[str] = [keyword]

    # Tambahkan "indonesia" jika belum ada
    if "indonesia" not in keyword.lower():
        variants.append(f"{keyword} indonesia")

    # Tambahkan "umkm indonesia" jika umkm belum ada
    if "umkm" not in keyword.lower():
        variants.append(f"{keyword} umkm indonesia")

    # Tambahkan variant kota
    city_list = CITY_ALIASES.get(kota, [kota] if kota else [])
    if city_list:
        primary_city = city_list[0]
        if primary_city and primary_city not in keyword.lower():
            base = keyword if "indonesia" in keyword.lower() else f"{keyword} indonesia"
            variants.append(f"{base} {primary_city}")

    # Tambahkan variant industri
    for biz_type, id_keywords in INDUSTRY_KEYWORD_MAP.items():
        if biz_type in industri:
            for id_kw in id_keywords[:1]:
                if id_kw not in keyword.lower():
                    variants.append(f"{keyword} {id_kw}")
            break

    # Deduplicate sambil pertahankan urutan
    seen: set[str] = set()
    result: list[str] = []
    for kw in variants:
        kw_norm = kw.strip().lower()
        if kw_norm not in seen:
            seen.add(kw_norm)
            result.append(kw.strip())

    return result[:4]


def build_search_queries(
    keywords: list[str],
    payload: JobPayload,
    *,
    max_keywords: int = 3,
    enable_enhancement: bool = False,
    max_enhanced_total: int = 0,
) -> list[tuple[str, str]]:
    """
    Build final Tavily queries as (original_keyword, query).

    Default produksi sengaja hemat: pakai keyword Node A apa adanya. Enhancement hanya
    ditambahkan saat diaktifkan via env, dan dibatasi global agar 3 keyword tidak melebar
    menjadi banyak request Tavily.
    """
    seen_originals: set[str] = set()
    originals: list[str] = []
    for raw in keywords:
        kw = str(raw).strip()
        norm = kw.lower()
        if not kw or norm in seen_originals:
            continue
        seen_originals.add(norm)
        originals.append(kw)
        if len(originals) >= max(1, max_keywords):
            break

    final: list[tuple[str, str]] = [(kw, kw) for kw in originals]
    if not enable_enhancement or max_enhanced_total <= 0:
        return final

    seen_queries = {kw.lower() for kw in originals}
    enhanced_count = 0
    for original in originals:
        for variant in enhance_keywords(original, payload)[1:]:
            variant = variant.strip()
            norm = variant.lower()
            if not variant or norm in seen_queries:
                continue
            final.append((original, variant))
            seen_queries.add(norm)
            enhanced_count += 1
            if enhanced_count >= max_enhanced_total:
                return final

    return final
