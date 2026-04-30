"""Node B: Tavily search + cache (PRD §5)."""

from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from typing import Any

from tavily import TavilyClient
from tenacity import Retrying, retry_if_exception, stop_after_attempt, wait_fixed

from advisor.cache import MemoryTTLCache, cache_key_for_keyword
from advisor.logging_setup import get_logger, log_node_timing

_LOG = get_logger(__name__)
_default_cache = MemoryTTLCache()


def _tavily_retryable(exc: BaseException) -> bool:
    if isinstance(exc, (TimeoutError, FuturesTimeout, OSError)):
        return True
    msg = str(exc).lower()
    return any(x in msg for x in ("timeout", "timed out", "500", "502", "503", "504", "connection"))


def _format_market_block(keyword: str, answer: str, results: list[dict[str, Any]]) -> str:
    lines = [f"=== [{keyword}] ===", answer or "(tanpa ringkasan otomatis)"]
    for r in results[:3]:
        title = r.get("title") or ""
        url = r.get("url") or ""
        content = r.get("content") or ""
        if title or content:
            lines.append(f"- {title}: {content[:500]}")
        if url:
            lines.append(f"  sumber: {url}")
    return "\n".join(lines)


def _search_with_retries(client: TavilyClient, kw: str, timeout_s: float) -> dict[str, Any]:
    def _call() -> dict[str, Any]:
        with ThreadPoolExecutor(max_workers=1) as pool:
            fut = pool.submit(
                lambda: client.search(
                    query=kw,
                    max_results=3,
                    search_depth="basic",
                    include_answer=True,
                ),
            )
            return fut.result(timeout=timeout_s)

    return Retrying(
        stop=stop_after_attempt(3),
        retry=retry_if_exception(_tavily_retryable),
        wait=wait_fixed(0.4),
        reraise=True,
    )(_call)


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

    t0 = time.perf_counter()
    blocks: list[str] = []
    client = tavily_client
    if client is None and os.environ.get("TAVILY_API_KEY"):
        try:
            client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
        except Exception as e:  # noqa: BLE001
            _LOG.warning("tavily_init_failed", job_id=job_id, error=str(e))
            client = None

    for kw in keywords:
        ck = cache_key_for_keyword(kw)
        cached = cache.get(ck)
        if cached is not None:
            blocks.append(str(cached))
            continue
        if client is None:
            continue
        try:
            resp = _search_with_retries(client, kw, timeout_s)
            answer = str(resp.get("answer") or "")
            results = list(resp.get("results") or [])
            block = _format_market_block(kw, answer, results)
            cache.set(ck, block)
            blocks.append(block)
        except Exception as e:  # noqa: BLE001
            _LOG.warning("tavily_search_failed", job_id=job_id, keyword=kw, error=str(e))

    market_context = "\n\n".join(blocks) if blocks else ""
    elapsed_ms = (time.perf_counter() - t0) * 1000
    log_node_timing(_LOG, job_id=job_id, node="B", duration_ms=elapsed_ms, keywords=len(keywords))

    return {"market_context": market_context}
