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
