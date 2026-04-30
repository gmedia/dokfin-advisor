"""Domain Indonesia terpercaya untuk pembatasan hasil Tavily (Node B)."""

from __future__ import annotations

import os

DEFAULT_TRUSTED_DOMAINS: tuple[str, ...] = (
    "bi.go.id",
    "bps.go.id",
    "kemenkeu.go.id",
    "ojk.go.id",
    "kemendag.go.id",
    "kemenperin.go.id",
    "kontan.co.id",
    "bisnis.com",
    "cnbcindonesia.com",
    "katadata.co.id",
    "ddtc.co.id",
    "kompas.com",
    "tempo.co",
    "detik.com",
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
