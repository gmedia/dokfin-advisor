"""Filter hasil Tavily: usia artikel, panjang teks, ranking (Node B)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
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


def _word_count(text: str) -> int:
    return len(text.split())


def _hostname_in_trust_list(host: str, trusted: set[str]) -> bool:
    if not trusted:
        return True
    host = host.lower()
    if host in trusted:
        return True
    return any(host == d or host.endswith("." + d) for d in trusted)


def filter_tavily_results(
    results: list[dict[str, Any]],
    *,
    trusted_domains: set[str],
    reference_date: date,
    max_keep: int = 3,
    min_words: int = 100,
    max_age: timedelta = timedelta(days=183),
) -> list[dict[str, Any]]:
    """Buang hasil terlalu tua, terlalu pendek, di luar whitelist; urutkan by score; ambil max_keep."""
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
        pub = _parse_published_date(_published_raw(r))
        if pub is not None and pub < cutoff:
            continue
        score = float(r.get("score") or 0.0)
        scored.append((score, r))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [r for _, r in scored[:max_keep]]
