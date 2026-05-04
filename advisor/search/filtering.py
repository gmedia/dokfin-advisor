"""Result filtering, scoring, dan selection dengan Indonesia-first strategy."""

from __future__ import annotations

from typing import Any

from advisor.schemas.input import JobPayload
from advisor.search_filters import hostname_from_url, is_valid_result, root_domain_from_host
from advisor.trusted_domains import indonesia_domain_score, is_indonesia_domain

_INTERNATIONAL_MARKERS: tuple[str, ...] = (
    "apac", "asia pacific", "asean", "southeast asia",
    "global market", "worldwide", "international market",
)

_CITY_ALIASES: dict[str, list[str]] = {
    "yogyakarta": ["yogyakarta", "jogja", "diy"],
    "kota yogyakarta": ["yogyakarta", "jogja", "diy"],
    "d.i. yogyakarta": ["yogyakarta", "jogja", "diy"],
    "diy": ["yogyakarta", "jogja", "diy"],
    "jogja": ["jogja", "yogyakarta", "diy"],
    "solo": ["solo", "surakarta"],
    "surakarta": ["surakarta", "solo"],
    "denpasar": ["denpasar", "bali"],
    "bali": ["bali", "denpasar"],
}


def is_international_only(result: dict[str, Any]) -> bool:
    """Return True jika konten murni internasional tanpa konteks Indonesia."""
    combined = " ".join([
        str(result.get("title") or ""),
        str(result.get("content") or ""),
    ]).lower()
    url = str(result.get("url") or "")

    has_international = any(m in combined for m in _INTERNATIONAL_MARKERS)
    has_indonesia = "indonesia" in combined or is_indonesia_domain(url)
    return has_international and not has_indonesia


def relevance_score(
    result: dict[str, Any],
    *,
    payload: JobPayload,
    keyword: str,
) -> float:
    """
    Score relevansi hasil untuk konteks UMKM Indonesia.

    Returns:
        -1.0 = tolak (murni internasional)
        0.0+ = terima (makin tinggi makin relevan)
    """
    if is_international_only(result):
        return -1.0

    url = str(result.get("url") or "")
    title = str(result.get("title") or "")
    content = str(result.get("content") or "")
    text = f"{title} {content} {url}".lower()

    industri = (payload.profil_bisnis.industri or "").lower()
    kota = (payload.profil_bisnis.kota or "").lower()

    score = 0.0

    # 1. Domain Indonesia — bobot paling besar
    score += indonesia_domain_score(url) * 5.0

    # 2. Keyword term overlap
    kw_terms = set(keyword.lower().split())
    text_terms = set(text.split())
    score += min(3.0, len(kw_terms & text_terms)) * 1.0

    # 3. Industry match
    if industri:
        ind_terms = set(industri.split())
        score += min(2.0, len(ind_terms & text_terms)) * 0.8

    # 4. Location match dengan alias kota
    if kota:
        candidates = _CITY_ALIASES.get(kota, [kota])
        if any(c in text for c in candidates):
            score += 1.5

    # 5. UMKM/bisnis context
    if any(t in text for t in ("umkm", "bisnis", "usaha", "ekonomi", "kewirausahaan")):
        score += 0.5

    return score


def filter_and_rank(
    results: list[dict[str, Any]],
    *,
    payload: JobPayload,
    keyword: str,
    min_words: int = 80,
    min_relevance: float = 0.5,
) -> list[dict[str, Any]]:
    """Filter hasil invalid/tidak relevan lalu urutkan berdasarkan skor relevansi."""
    scored: list[tuple[float, dict[str, Any]]] = []
    for r in results:
        if not is_valid_result(r):
            continue
        rel = relevance_score(r, payload=payload, keyword=keyword)
        if rel < 0 or rel < min_relevance:
            continue
        r2 = dict(r)
        r2["_relevance"] = rel
        scored.append((rel, r2))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [r for _, r in scored]


def pick_indonesia_first(
    candidates: list[dict[str, Any]],
    *,
    max_total: int = 5,
    prefer_indonesia: bool = True,
) -> list[dict[str, Any]]:
    """
    Pilih hasil akhir dengan prioritas sumber Indonesia dan diversitas domain.

    Fase 1: Isi dari sumber Indonesia (diverse domain).
    Fase 2: Jika kurang, tambahkan sumber internasional (jika prefer_indonesia=False).
    """
    if not candidates:
        return []

    id_candidates = [r for r in candidates if is_indonesia_domain(str(r.get("url") or ""))]
    intl_candidates = [r for r in candidates if not is_indonesia_domain(str(r.get("url") or ""))]

    picked: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    seen_roots: set[str] = set()

    def _try_add(r: dict[str, Any]) -> bool:
        url = str(r.get("url") or "")
        if url and url in seen_urls:
            return False
        host = hostname_from_url(url)
        root = root_domain_from_host(host) or host
        if root and root in seen_roots:
            return False
        if url:
            seen_urls.add(url)
        if root:
            seen_roots.add(root)
        picked.append(r)
        return True

    for r in id_candidates:
        if len(picked) >= max_total:
            break
        _try_add(r)

    if not prefer_indonesia or len(picked) < 1:
        for r in intl_candidates:
            if len(picked) >= max_total:
                break
            _try_add(r)

    return picked
