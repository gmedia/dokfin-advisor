"""Format picked results menjadi market context string dan seeds."""

from __future__ import annotations

from typing import Any

from advisor.search_filters import hostname_from_url
from advisor.trusted_domains import is_indonesia_domain


def format_market_block(keyword: str, answer: str, results: list[dict[str, Any]]) -> str:
    """Format satu blok konteks pasar per keyword untuk konsumsi LLM."""
    lines = [f"=== [{keyword}] ==="]
    lines.append(answer if answer else "(tidak ada ringkasan otomatis)")
    for r in results:
        title = str(r.get("title") or "")
        url = str(r.get("url") or "")
        content = str(r.get("content") or "")
        label = "[INDONESIA]" if is_indonesia_domain(url) else "[INTERNASIONAL]"
        if title or content:
            lines.append(f"{label} {title}: {content[:400]}")
        if url:
            lines.append(f"  sumber: {url}")
    return "\n".join(lines)


def build_market_context(
    picked: list[dict[str, Any]],
    answers_by_kw: dict[str, str],
) -> str:
    """Bangun string market context lengkap dikelompokkan per original keyword."""
    by_kw: dict[str, list[dict[str, Any]]] = {}
    for r in picked:
        kw = str(r.get("_original_kw") or r.get("_enhanced_kw") or "keyword")
        by_kw.setdefault(kw, []).append(r)

    blocks = []
    for kw, rs in by_kw.items():
        answer = answers_by_kw.get(kw, "")
        if not answer:
            for ek, ea in answers_by_kw.items():
                if kw in ek or ek in kw:
                    answer = ea
                    break
        blocks.append(format_market_block(kw, answer, rs))

    return "\n\n".join(blocks)


def build_seeds(
    picked: list[dict[str, Any]],
    access_date: str,
) -> list[dict[str, Any]]:
    """Bangun list konteks_pasar_seed dari hasil yang sudah dipilih."""
    seeds = []
    for r in picked:
        url = str(r.get("url") or "")
        host = hostname_from_url(url) or "unknown"
        title = str(r.get("title") or "").strip()
        content = str(r.get("content") or "")
        seeds.append(
            {
                "topik": (title or host)[:200],
                "konten": content[:1200],
                "dampak_ke_bisnis": None,
                "relevansi": "TINGGI" if is_indonesia_domain(url) else "MEDIUM",
                "sumber": host,
                "diakses_pada": access_date,
            }
        )
    return seeds
