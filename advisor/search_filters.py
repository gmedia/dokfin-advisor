"""Utilitas host dan filter dasar untuk hasil Tavily (Node B)."""

from __future__ import annotations

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
