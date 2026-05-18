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

_STATUS_PRESSURE: dict[str, int] = {
    "KRITIS": 5,
    "PERLU_PERHATIAN": 2,
    "TURUN": 3,
}

_DIMENSION_TERMS: dict[str, tuple[str, ...]] = {
    "likuiditas": (
        "likuiditas",
        "kas",
        "cash",
        "hutang",
        "utang",
        "tagihan",
        "piutang",
        "modal kerja",
    ),
    "profitabilitas": (
        "profit",
        "profitabilitas",
        "laba",
        "margin",
        "keuntungan",
        "penjualan",
        "omzet",
        "pendapatan",
        "daya beli",
        "konsumen",
        "bep",
    ),
    "efisiensi": ("stok", "persediaan", "bahan baku", "hpp", "biaya produksi"),
    "solvabilitas": ("solvabilitas", "cicilan", "pinjaman", "kredit", "hutang", "utang"),
    "sdm": ("sdm", "karyawan", "pegawai", "target", "produktivitas", "sales"),
    "kepatuhan": ("pajak", "laporan", "pencatatan", "kepatuhan"),
}

_ACTIONABLE_TERMS: dict[str, int] = {
    "penjualan": 7,
    "omzet": 7,
    "pendapatan": 4,
    "daya beli": 4,
    "konsumen": 3,
    "pelanggan": 3,
    "kas": 3,
    "modal kerja": 3,
    "tren": 2,
    "strategi": 2,
}

_LESS_ACTIONABLE_TERMS: dict[str, int] = {
    "benchmark": -4,
    "rasio": -2,
    "margin": -1,
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


def _dimension_pressure(payload: JobPayload) -> dict[str, int]:
    out: dict[str, int] = {}
    dimensi = payload.dimensi.model_dump(mode="json")
    for dim_name, indicators in dimensi.items():
        pressure = 0
        if not isinstance(indicators, dict):
            continue
        for row in indicators.values():
            if not isinstance(row, dict):
                continue
            pressure += _STATUS_PRESSURE.get(str(row.get("status") or ""), 0)
        out[dim_name] = pressure
    return out


def _profile_terms(payload: JobPayload) -> set[str]:
    raw_parts = [
        payload.profil_bisnis.industri,
        payload.profil_bisnis.sub_industri,
        payload.profil_bisnis.skala,
    ]
    terms: set[str] = set()
    for part in raw_parts:
        text = str(part or "").lower().replace("&", " ")
        for token in text.split():
            token = token.strip(" ,./()[]{}")
            if len(token) >= 3:
                terms.add(token)
    return terms


def score_search_keyword(keyword: str, payload: JobPayload) -> float:
    """Score keyword usefulness for 1-query mode; deterministic and payload-local only."""
    kw = keyword.lower()
    pressure = _dimension_pressure(payload)
    score = 0.0

    for dim_name, terms in _DIMENSION_TERMS.items():
        if any(term in kw for term in terms):
            score += pressure.get(dim_name, 0) * 1.2

    for term, weight in _ACTIONABLE_TERMS.items():
        if term in kw:
            score += weight

    for term, weight in _LESS_ACTIONABLE_TERMS.items():
        if term in kw:
            score += weight

    profile_hits = sum(1 for term in _profile_terms(payload) if term in kw)
    score += min(profile_hits, 3) * 2

    city = payload.profil_bisnis.kota.lower().strip()
    if city and city in kw:
        score += 2
    if str(payload.profil_bisnis.periode_tahun) in kw:
        score += 1

    return score


def build_search_queries(
    keywords: list[str],
    payload: JobPayload,
    *,
    max_keywords: int = 3,
    selection_mode: str = "ordered",
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
        if len(originals) >= max(1, max_keywords) and selection_mode != "best":
            break

    if selection_mode == "best":
        originals.sort(key=lambda kw: score_search_keyword(kw, payload), reverse=True)
        originals = originals[: max(1, max_keywords)]

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
