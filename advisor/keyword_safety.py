"""Sanitize search keywords before Tavily (PRD 5.3: no user numbers / PII in queries)."""

from __future__ import annotations

import re
import unicodedata

# Generic fallback when a keyword is rejected (still industry-topic, no user data)
_FALLBACK_KEYWORD = "tren industri UMKM Indonesia"

# Block obvious URL / email patterns
_URL_RE = re.compile(r"https?://|www\.", re.I)
_EMAIL_RE = re.compile(r"\S+@\S+\.\S+")

# Currency / number-heavy phrases common in ID locale
_RP_RE = re.compile(r"\brp\b", re.I)
_JUTA_MILYAR_RE = re.compile(r"\b(juta|milyar|miliar|ribu)\b", re.I)

# Digit detection (any digit is suspicious for "no user numbers" rule)
_DIGIT_RE = re.compile(r"\d")

# Allow safe time markers (not user-specific numbers): year and quarter.
_YEAR_RE = re.compile(r"\b(202[0-9]|2030)\b")
_QUARTER_RE = re.compile(r"\bq[1-4]\b", re.I)


def _normalize_keyword(raw: str) -> str:
    s = unicodedata.normalize("NFKC", raw).strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s


def _is_safe_keyword(normalized: str) -> bool:
    if not normalized or len(normalized) < 8:
        return False
    if _URL_RE.search(normalized) or _EMAIL_RE.search(normalized):
        return False
    if _DIGIT_RE.search(normalized):
        # Only allow digits when they look like a time marker (year / quarter),
        # otherwise assume it's leaking user-specific numbers (PRD 5.3).
        without_allowed = _YEAR_RE.sub("", normalized)
        without_allowed = _QUARTER_RE.sub("", without_allowed)
        if _DIGIT_RE.search(without_allowed):
            return False
    return not (_RP_RE.search(normalized) or _JUTA_MILYAR_RE.search(normalized))


def sanitize_search_keywords(keywords: list[str], *, max_items: int = 3) -> list[str]:
    """
    Return up to `max_items` safe keywords.

    Invalid entries are replaced with a single generic industry topic so the pipeline
    can continue (PRD: Node B still runs; empty list would also be valid—here we prefer
    at least one generic query when all are bad).
    """
    cap = min(max_items, 3)
    if cap < 1:
        return []

    out: list[str] = []
    replaced_any = False

    for raw in keywords:
        if len(out) >= cap:
            break
        normalized = _normalize_keyword(raw)
        if _is_safe_keyword(normalized):
            if normalized not in out:
                out.append(normalized)
        else:
            replaced_any = True

    if not out and keywords:
        replaced_any = True

    if not out:
        return [_FALLBACK_KEYWORD]

    if replaced_any and _FALLBACK_KEYWORD not in out and len(out) < cap:
        out.append(_FALLBACK_KEYWORD)

    return out[:cap]
