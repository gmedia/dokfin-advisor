"""Node B: Market context search - Indonesia-first strategy (PRD §5).

Perbaikan vs versi lama:
- topic="general" + country="indonesia" (versi lama pakai topic="news" yang menonaktifkan country)
- include_answer="advanced" untuk AI summary yang lebih baik
- start_date/end_date berdasarkan periode analisis payload (bukan parameter 'days' generik)
- Kode modular via advisor/search/ package
- Domain detection dan scoring dipusatkan di advisor/trusted_domains.py
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from advisor.cache import MemoryTTLCache, cache_key_for_keyword
from advisor.logging_setup import get_logger, log_node_timing
from advisor.schemas.input import JobPayload
from advisor.search.client import make_tavily_client, search_indonesia
from advisor.search.config import POLICY_SALT, date_range_for_search, get_search_config
from advisor.search.filtering import filter_and_rank, pick_indonesia_first
from advisor.search.formatter import build_market_context, build_seeds
from advisor.search.keywords import enhance_keywords
from advisor.search_filters import is_valid_result
from advisor.trusted_domains import is_indonesia_domain

_LOG = get_logger(__name__)
_default_cache = MemoryTTLCache()


def run_search(
    state: dict[str, Any],
    *,
    cache: MemoryTTLCache | None = None,
    tavily_client: Any | None = None,
) -> dict[str, Any]:
    """
    Node B: fetch market context dari Tavily untuk keywords dari Node A.

    Perbaikan vs versi lama:
    - topic="general" + country="indonesia" (topic="news" menonaktifkan country filter)
    - include_answer="advanced" untuk AI summary yang lebih baik dari Tavily
    - start_date/end_date berdasarkan periode analisis (bukan 'days' generik)
    - Tidak ada whitelist restrictif; country filter yang mengurus sumber Indonesia
    """
    job_id = str(state.get("job_id", ""))
    payload = JobPayload.model_validate(state.get("payload") or {})
    original_keywords: list[str] = (state.get("reasoning") or {}).get("search_keywords") or []
    cache = cache or _default_cache
    cfg = get_search_config()

    ref_dt = datetime.now(UTC)
    t0 = time.perf_counter()

    # Date range selalu dari hari ini ke belakang — konteks pasar harus actionable sekarang
    start_date, end_date = date_range_for_search(cfg["primary_days"])

    # Expand keywords dengan variasi konteks Indonesia
    enhanced_kws: list[tuple[str, str]] = []
    for kw in original_keywords:
        for variant in enhance_keywords(kw, payload):
            enhanced_kws.append((kw, variant))

    _LOG.info(
        "search_start",
        job_id=job_id,
        original_keywords=len(original_keywords),
        enhanced_keywords=len(enhanced_kws),
        start_date=start_date,
        end_date=end_date,
    )

    client = make_tavily_client(tavily_client, job_id)
    answers_by_kw: dict[str, str] = {}
    all_candidates: list[dict[str, Any]] = []

    for orig_kw, kw in enhanced_kws:
        ck = cache_key_for_keyword(kw, policy_salt=POLICY_SALT)
        cached = cache.get(ck)

        if cached and isinstance(cached, dict) and "picked_results" in cached:
            answers_by_kw.setdefault(orig_kw, str(cached.get("answer") or ""))
            for r in cached.get("picked_results", []):
                if isinstance(r, dict):
                    r2 = dict(r)
                    r2["_original_kw"] = orig_kw
                    r2["_enhanced_kw"] = kw
                    all_candidates.append(r2)
            continue

        if client is None:
            continue

        try:
            resp = search_indonesia(
                client,
                kw,
                start_date=start_date,
                end_date=end_date,
                max_results=cfg["max_results"],
                search_depth=cfg["search_depth"],
                timeout_s=cfg["timeout_s"],
            )

            answer = str(resp.get("answer") or "")
            raw = [r for r in (resp.get("results") or []) if is_valid_result(r)]

            _LOG.info(
                "tavily_search_ok",
                job_id=job_id,
                keyword=kw,
                raw_count=len(raw),
            )

            ranked = filter_and_rank(
                raw,
                payload=payload,
                keyword=kw,
                min_words=cfg["min_words"],
                min_relevance=cfg["min_relevance"],
            )

            picked_for_kw: list[dict[str, Any]] = []
            for r in ranked[:3]:
                r2 = dict(r)
                r2["_original_kw"] = orig_kw
                r2["_enhanced_kw"] = kw
                picked_for_kw.append(r2)
                all_candidates.append(r2)

            answers_by_kw.setdefault(orig_kw, answer)
            cache.set(ck, {"answer": answer, "picked_results": picked_for_kw})

        except Exception as e:
            _LOG.warning("tavily_search_failed", job_id=job_id, keyword=kw, error=str(e))

    # Pilih hasil akhir: Indonesia-first, diverse domain
    picked = pick_indonesia_first(
        all_candidates,
        max_total=cfg["konteks_pasar_max"],
        prefer_indonesia=cfg["force_indonesia_only"],
    )

    id_count = sum(1 for r in picked if is_indonesia_domain(str(r.get("url") or "")))
    _LOG.info(
        "search_complete",
        job_id=job_id,
        total_candidates=len(all_candidates),
        picked_count=len(picked),
        indonesia_sources=id_count,
        international_sources=len(picked) - id_count,
    )

    market_context = build_market_context(picked, answers_by_kw)
    seeds = build_seeds(picked, ref_dt.date().isoformat())

    elapsed_ms = (time.perf_counter() - t0) * 1000
    log_node_timing(
        _LOG,
        job_id=job_id,
        node="B",
        duration_ms=elapsed_ms,
        keywords=len(enhanced_kws),
    )

    return {
        "market_context": market_context,
        "konteks_pasar_seed": seeds,
        "_search_meta": {
            "indonesia_sources": id_count,
            "international_sources": len(picked) - id_count,
            "total_candidates": len(all_candidates),
        },
    }
