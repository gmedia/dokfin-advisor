"""Filter hasil Tavily: panjang/kualitas teks, whitelist host, ranking (Node B).

Filter tanggal publikasi sisi klien bersifat opsional: gunakan argumen ``max_age``
jika masih ingin membatasi usia artikel; secara default tidak memfilter tanggal
(karena freshness sudah diatur lewat parameter Tavily, mis. ``days``).
"""

from __future__ import annotations

import os
import re
from datetime import date, datetime, timedelta
from typing import Any
from urllib.parse import urlparse

DOMAIN_BLACKLIST: frozenset[str] = frozenset(
    {
        "linkedin.com",
        "facebook.com",
        "twitter.com",
        "x.com",
        "instagram.com",
        "tiktok.com",
        "youtube.com",
        "reddit.com",
        "quora.com",
    }
)

_LOGIN_WALL_SIGNALS: tuple[str, ...] = (
    "sign in",
    "log in",
    "session_redirect",
    "/uas/login",
)


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


_ID_MONTHS: dict[str, int] = {
    "januari": 1,
    "februari": 2,
    "maret": 3,
    "april": 4,
    "mei": 5,
    "juni": 6,
    "juli": 7,
    "agustus": 8,
    "september": 9,
    "oktober": 10,
    "november": 11,
    "desember": 12,
}


def _parse_date_from_text(text: str) -> date | None:
    """Parse publish date from common Indonesian date strings in snippets."""
    if not text:
        return None
    t = text.lower()

    # Example: "Kamis, 05 Januari 2023 / 05:15 WIB"
    # Example: "8 April 2021 | 16.02 WIB"
    weekday = r"(?:senin|selasa|rabu|kamis|jumat|sabtu|minggu)"
    month = (
        r"(?:januari|februari|maret|april|mei|juni|juli|agustus|september|"
        r"oktober|november|desember)"
    )
    m = re.search(
        rf"\b(?:{weekday}\s*,\s*)?(?P<day>\d{{1,2}})\s+(?P<month>{month})\s+(?P<year>\d{{4}})\b",
        t,
    )
    if m:
        try:
            d = int(m.group("day"))
            mo = _ID_MONTHS[m.group("month")]
            y = int(m.group("year"))
            return date(y, mo, d)
        except (KeyError, ValueError):
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
    """Best-effort publish date: metadata first, then parse from URL/snippet."""
    pub = _parse_published_date(_published_raw(result))
    if pub is not None:
        return pub
    url = str(result.get("url") or "")
    pub = _parse_date_from_url(url)
    if pub is not None:
        return pub
    title = str(result.get("title") or "")
    content = str(result.get("content") or "")
    return _parse_date_from_text(f"{title}\n{content}")


def _word_count(text: str) -> int:
    return len(text.split())


def _is_pdf_result(*, title: str, url: str) -> bool:
    t = (title or "").strip().lower()
    u = (url or "").strip().lower()
    return "[pdf]" in t or u.endswith(".pdf")


def _looks_like_toc_or_table(*, title: str, content: str) -> bool:
    t = (title or "").lower()
    c = (content or "").lower()
    keywords = (
        "daftar isi",
        "table of contents",
        "glossary",
        "glosarium",
        "daftar tabel",
        "daftar gambar",
        "tabel ",
        "table ",
    )
    if any(k in t for k in keywords) or any(k in c for k in keywords):
        return True

    # Heuristik: konten tabel/daftar biasanya punya banyak baris pendek.
    lines = [ln.strip() for ln in (content or "").splitlines() if ln.strip()]
    if len(lines) >= 30:
        short = sum(1 for ln in lines if len(ln) <= 30)
        if short / len(lines) >= 0.65:
            return True
    return False


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


def is_valid_result(result: dict[str, Any]) -> bool:
    """Return False for blacklisted domains, login walls, short content, or PDF titles."""
    url = str(result.get("url") or "")
    title = str(result.get("title") or "")
    content = str(result.get("content") or "").strip()

    host = hostname_from_url(url)
    root = root_domain_from_host(host)
    if root in DOMAIN_BLACKLIST or host in DOMAIN_BLACKLIST:
        return False

    content_lower = content.lower()
    if any(signal in content_lower for signal in _LOGIN_WALL_SIGNALS):
        return False

    if len(content) < 200:
        return False

    return not title.strip().upper().startswith("[PDF]")


def truncate_content(content: str, max_chars: int = 500) -> str:
    """Truncate at last sentence boundary within max_chars; hard truncate as fallback."""
    if len(content) <= max_chars:
        return content
    chunk = content[:max_chars]
    for sep in (".", "!", "?"):
        idx = chunk.rfind(sep)
        if idx > max_chars // 2:
            return chunk[: idx + 1]
    return chunk + "..."


def get_root_domain(url: str) -> str:
    """Extract root domain from a URL (e.g. 'semarang.bisnis.com' → 'bisnis.com')."""
    return root_domain_from_host(hostname_from_url(url))


def diversify_results(
    results: list[dict[str, Any]],
    max_per_domain: int = 1,
) -> list[dict[str, Any]]:
    """Keep at most max_per_domain articles per root domain, preserving relevance order."""
    seen: dict[str, int] = {}
    out: list[dict[str, Any]] = []
    for r in results:
        url = str(r.get("url") or "")
        root = get_root_domain(url) or url
        count = seen.get(root, 0)
        if count < max_per_domain:
            seen[root] = count + 1
            out.append(r)
    return out


def score_relevance(result: dict[str, Any], industry: str, city: str) -> int:
    """Integer relevance score; returns -1 (hard reject) for irrelevant articles."""
    title = str(result.get("title") or "")
    content = str(result.get("content") or "")
    url = str(result.get("url") or "")
    text = f"{title} {content} {url}".lower()

    reject_keywords = (
        "penjualan mobil",
        "industri otomotif",
        "gaikindo",
        "industri rokok",
        "industri tembakau",
        "pandemi covid",
        "logistik ekspor",
    )
    if any(kw in text for kw in reject_keywords):
        return -1

    positive_keywords = (
        "umkm",
        "restoran",
        "f&b",
        "fnb",
        "makanan",
        "minuman",
        "industri",
        "konsumen",
    )
    score = sum(1 for kw in positive_keywords if kw in text)
    if city and city.lower() in text:
        score += 1
    if industry and industry.lower() in text:
        score += 1
    return score


def filter_tavily_results(
    results: list[dict[str, Any]],
    *,
    trusted_domains: set[str],
    reference_date: date,
    max_keep: int = 3,
    min_words: int = 100,
    max_age: timedelta | None = None,
    drop_undated: bool | None = None,
) -> list[dict[str, Any]]:
    """Buang hasil pendek/berkualitas rendah atau di luar whitelist; urut score; ambil max_keep.

    Jika ``max_age`` tidak None, hasil dengan tanggal terbit lebih lama dari cutoff dibuang.
    Jika ``max_age`` None (default), tidak ada filter tanggal di sisi klien.
    """
    if drop_undated is None:
        drop_undated = _env_drop_undated()
    cutoff = (reference_date - max_age) if max_age is not None else None
    scored: list[tuple[float, dict[str, Any]]] = []

    for r in results:
        url = str(r.get("url") or "")
        title = str(r.get("title") or "")
        if _is_pdf_result(title=title, url=url):
            continue
        host = hostname_from_url(url)
        if trusted_domains and not _hostname_in_trust_list(host, trusted_domains):
            continue
        content = str(r.get("content") or "")
        if _looks_like_toc_or_table(title=title, content=content):
            continue
        if len(content.strip()) < 220:
            continue
        if _word_count(content) < min_words:
            continue
        pub = published_date_for_result(r)
        if drop_undated and pub is None:
            continue
        if cutoff is not None and pub is not None and pub < cutoff:
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
