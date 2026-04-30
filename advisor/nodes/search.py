"""Node B: Tavily search + cache (PRD §5)."""

from __future__ import annotations

import hashlib
import os
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from datetime import UTC, datetime
from typing import Any

from tavily import TavilyClient
from tenacity import Retrying, retry_if_exception, stop_after_attempt, wait_fixed

from advisor.cache import MemoryTTLCache, cache_key_for_keyword
from advisor.logging_setup import get_logger, log_node_timing
from advisor.search_filters import filter_tavily_results, hostname_from_url
from advisor.trusted_domains import trusted_domains_for_tavily, trusted_domain_set

_LOG = get_logger(__name__)
_default_cache = MemoryTTLCache()


def _policy_salt(domains: list[str] | None) -> str:
    if not domains:
        return "open"
    joined = ",".join(sorted(domains))
    return hashlib.md5(joined.encode("utf-8")).hexdigest()[:16]


def _tavily_retryable(exc: BaseException) -> bool:
    if isinstance(exc, (TimeoutError, FuturesTimeout, OSError)):
        return True
    msg = str(exc).lower()
    return any(x in msg for x in ("timeout", "timed out", "500", "502", "503", "504", "connection"))


def _format_market_block(keyword: str, answer: str, results: list[dict[str, Any]]) -> str:
    lines = [f"=== [{keyword}] ===", answer or "(tanpa ringkasan otomatis)"]
    for r in results:
        title = r.get("title") or ""
        url = r.get("url") or ""
        content = r.get("content") or ""
        if title or content:
            lines.append(f"- {title}: {content[:500]}")
        if url:
            lines.append(f"  sumber: {url}")
    return "\n".join(lines)


def _fetch_max_results() -> int:
    return max(3, int(os.environ.get("TAVILY_FETCH_MAX_RESULTS", "15")))


def _search_with_retries(
    client: TavilyClient,
    kw: str,
    timeout_s: float,
    *,
    include_domains: list[str] | None,
) -> dict[str, Any]:
    def _call() -> dict[str, Any]:
        with ThreadPoolExecutor(max_workers=1) as pool:
            kwargs: dict[str, Any] = {
                "query": kw,
                "max_results": _fetch_max_results(),
                "search_depth": "basic",
                "include_answer": True,
            }
            if include_domains:
                kwargs["include_domains"] = include_domains
            fut = pool.submit(lambda: client.search(**kwargs))
            return fut.result(timeout=timeout_s)

    return Retrying(
        stop=stop_after_attempt(3),
        retry=retry_if_exception(_tavily_retryable),
        wait=wait_fixed(0.4),
        reraise=True,
    )(_call)


def _seeds_from_results(filtered: list[dict[str, Any]], access_date: str) -> list[dict[str, Any]]:
    seeds: list[dict[str, Any]] = []
    for r in filtered:
        url = str(r.get("url") or "")
        host = hostname_from_url(url) or "unknown"
        title = str(r.get("title") or "").strip()
        content = str(r.get("content") or "")
        seeds.append(
            {
                "topik": (title or host)[:200],
                "konten": content[:1200],
                "dampak_ke_bisnis": "Korelasikan dampak dengan kondisi operasional UMKM (data sekunder).",
                "relevansi": "TINGGI",
                "sumber": host,
                "diakses_pada": access_date,
            },
        )
    return seeds


def run_search(
    state: dict[str, Any],
    *,
    cache: MemoryTTLCache | None = None,
    tavily_client: TavilyClient | None = None,
) -> dict[str, Any]:
    """Fetch market context from Tavily for sanitized keywords in `reasoning`."""
    job_id = str(state.get("job_id", ""))
    reasoning = state.get("reasoning") or {}
    keywords = reasoning.get("search_keywords") or []
    cache = cache or _default_cache
    timeout_s = float(os.environ.get("TAVILY_TIMEOUT_S", "30"))
    include_domains = trusted_domains_for_tavily()
    salt = _policy_salt(include_domains)
    trusted = trusted_domain_set()
    ref_date = datetime.now(UTC).date()

    t0 = time.perf_counter()
    blocks: list[str] = []
    all_seeds: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str]] = set()
    client = tavily_client
    if client is None and os.environ.get("TAVILY_API_KEY"):
        try:
            client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
        except Exception as e:  # noqa: BLE001
            _LOG.warning("tavily_init_failed", job_id=job_id, error=str(e))
            client = None

    for kw in keywords:
        ck = cache_key_for_keyword(kw, policy_salt=salt)
        cached = cache.get(ck)
        if isinstance(cached, dict) and "market_block" in cached:
            blocks.append(str(cached["market_block"]))
            for s in cached.get("seed") or []:
                if isinstance(s, dict):
                    dom = str(s.get("sumber") or "")
                    key = (dom, str(s.get("topik") or "")[:80])
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)
                    all_seeds.append(dict(s))
            continue
        if isinstance(cached, str):
            blocks.append(cached)
            continue
        if client is None:
            continue
        try:
            resp = _search_with_retries(client, kw, timeout_s, include_domains=include_domains)
            answer = str(resp.get("answer") or "")
            results = list(resp.get("results") or [])
            filtered = filter_tavily_results(
                results,
                trusted_domains=trusted,
                reference_date=ref_date,
                max_keep=3,
                min_words=int(os.environ.get("TAVILY_MIN_WORDS", "100")),
            )
            access_date = ref_date.isoformat()
            block = _format_market_block(kw, answer, filtered)
            seeds = _seeds_from_results(filtered, access_date)
            cache.set(ck, {"market_block": block, "seed": seeds})
            blocks.append(block)
            for s in seeds:
                dom = str(s.get("sumber") or "")
                key = (dom, str(s.get("topik") or "")[:80])
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                all_seeds.append(s)
        except Exception as e:  # noqa: BLE001
            _LOG.warning("tavily_search_failed", job_id=job_id, keyword=kw, error=str(e))

    market_context = "\n\n".join(blocks) if blocks else ""
    elapsed_ms = (time.perf_counter() - t0) * 1000
    log_node_timing(_LOG, job_id=job_id, node="B", duration_ms=elapsed_ms, keywords=len(keywords))

    return {"market_context": market_context, "konteks_pasar_seed": all_seeds}
