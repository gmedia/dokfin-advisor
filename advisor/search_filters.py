"""Filter hasil Tavily: usia artikel, panjang teks, ranking (Node B)."""

from __future__ import annotations

import os
import re
from datetime import date, datetime, timedelta
from typing import Any
from urllib.parse import urlparse


def hostname_from_url(url: str) -> str:
    if not url:
        return ""
    try:
        netloc = urlparse(url).netloc.lower()
    except ValueError:
        return ""
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc


def root_domain_from_host(host: str) -> str:
    """Best-effort root domain for diversity (works for common ID suffixes)."""
    h = (host or "").lower().strip(".")
    if not h:
        return ""
    labels = h.split(".")
    if len(labels) <= 2:
        return h
    public_suffixes = ("co.id", "go.id", "ac.id", "or.id", "web.id")
    for suf in public_suffixes:
        if h.endswith("." + suf) or h == suf:
            return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def _parse_date_from_url(url: str) -> date | None:
    """Parse publish date from common news URL patterns (fallback when metadata missing)."""
    if not url:
        return None
    try:
        path = urlparse(url).path
    except ValueError:
        return None

    # /read/YYYYMMDD/
    m = re.search(r"/read/(\d{8})/", path)
    if m:
        try:
            return datetime.strptime(m.group(1), "%Y%m%d").date()
        except ValueError:
            return None

    # /YYYY/MM/DD/ or /YYYY-MM-DD/
    m = re.search(r"/(\d{4})[/-](\d{2})[/-](\d{2})/", path)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None

    return None


def _parse_published_date(raw: Any) -> date | None:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s).date()
    except ValueError:
        pass
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _published_raw(result: dict[str, Any]) -> Any:
    for key in ("published_date", "published_time", "pub_date", "date"):
        v = result.get(key)
        if v:
            return v
    return None


def published_date_for_result(result: dict[str, Any]) -> date | None:
    """Best-effort publish date: metadata first, then parse from URL."""
    pub = _parse_published_date(_published_raw(result))
    if pub is not None:
        return pub
    url = str(result.get("url") or "")
    return _parse_date_from_url(url)


def _word_count(text: str) -> int:
    return len(text.split())


def _freshness_bonus(content: str, pub: date | None, *, reference_date: date) -> float:
    """Heuristik kecil untuk prefer hasil yang lebih fresh dan informatif (tanpa hard filter)."""
    bonus = 0.0
    c = content.lower()
    if pub is not None:
        age_days = (reference_date - pub).days
        if age_days <= 31:
            bonus += 0.12
        elif age_days <= 93:
            bonus += 0.07
        elif age_days <= 183:
            bonus += 0.03
    # Prefer statistik/angka umum dan periode (biasanya artikel lebih konkret).
    if any(x in c for x in ("2025", "2026", "q1", "q2", "q3", "q4", "%")):
        bonus += 0.05
    return bonus


def _hostname_in_trust_list(host: str, trusted: set[str]) -> bool:
    if not trusted:
        return True
    host = host.lower()
    if host in trusted:
        return True
    allow_subdomains = os.environ.get("TAVILY_ALLOW_SUBDOMAINS", "1").strip().lower() in (
        "1",
        "true",
        "yes",
    )
    if not allow_subdomains:
        return False
    return any(host == d or host.endswith("." + d) for d in trusted)


def _env_drop_undated() -> bool:
    return os.environ.get("TAVILY_DROP_UNDATED", "0").strip().lower() in ("1", "true", "yes")


def filter_tavily_results(
    results: list[dict[str, Any]],
    *,
    trusted_domains: set[str],
    reference_date: date,
    max_keep: int = 3,
    min_words: int = 100,
    max_age: timedelta = timedelta(days=183),
    drop_undated: bool | None = None,
) -> list[dict[str, Any]]:
    """Buang hasil terlalu tua, pendek, atau di luar whitelist; urut score; ambil max_keep."""
    if drop_undated is None:
        drop_undated = _env_drop_undated()
    cutoff = reference_date - max_age
    scored: list[tuple[float, dict[str, Any]]] = []

    for r in results:
        url = str(r.get("url") or "")
        host = hostname_from_url(url)
        if trusted_domains and not _hostname_in_trust_list(host, trusted_domains):
            continue
        content = str(r.get("content") or "")
        if _word_count(content) < min_words:
            continue
        pub = published_date_for_result(r)
        if drop_undated and pub is None:
            continue
        if pub is not None and pub < cutoff:
            continue
        score = float(r.get("score") or 0.0)
        score += _freshness_bonus(content, pub, reference_date=reference_date)
        scored.append((score, r))

    scored.sort(key=lambda x: x[0], reverse=True)

    # Diversity pass: prefer distinct root-domains (anti “semua dari satu publisher”).
    picked: list[dict[str, Any]] = []
    seen_roots: set[str] = set()
    rest: list[dict[str, Any]] = []
    for _score, r in scored:
        host = hostname_from_url(str(r.get("url") or ""))
        root = root_domain_from_host(host) or host
        if root and root not in seen_roots and len(picked) < max_keep:
            seen_roots.add(root)
            picked.append(r)
        else:
            rest.append(r)
    # Fill remaining slots if diversity leaves less than max_keep.
    for r in rest:
        if len(picked) >= max_keep:
            break
        picked.append(r)
    return picked[:max_keep]
