"""Tavily API client wrapper dengan parameter Indonesia-first yang benar."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from typing import Any

from tavily import TavilyClient
from tenacity import Retrying, retry_if_exception, stop_after_attempt, wait_fixed

from advisor.logging_setup import get_logger
from advisor.search_filters import DOMAIN_BLACKLIST

_LOG = get_logger(__name__)

_BASE_EXCLUDE: list[str] = list(DOMAIN_BLACKLIST)


def make_tavily_client(provided: TavilyClient | None, job_id: str) -> TavilyClient | None:
    """Buat atau gunakan kembali Tavily client yang sudah ada."""
    if provided is not None:
        return provided
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        _LOG.warning("tavily_api_key_missing", job_id=job_id)
        return None
    try:
        return TavilyClient(api_key=api_key)
    except Exception as e:
        _LOG.warning("tavily_init_failed", job_id=job_id, error=str(e))
        return None


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, (TimeoutError, FuturesTimeout, OSError)):
        return True
    msg = str(exc).lower()
    return any(x in msg for x in ("timeout", "timed out", "500", "502", "503", "504", "connection"))


def search_indonesia(
    client: TavilyClient,
    query: str,
    *,
    start_date: str,
    end_date: str,
    max_results: int = 3,
    search_depth: str = "advanced",
    timeout_s: float = 35.0,
    include_domains: list[str] | None = None,
    extra_exclude_domains: list[str] | None = None,
) -> dict[str, Any]:
    """
    Eksekusi Tavily search dengan parameter Indonesia-first.

    Parameter kritis:
    - topic="general"       → wajib agar country filter aktif
    - country="indonesia"   → nama lengkap (bukan "id")
    - include_answer="advanced" → AI summary yang lebih baik
    - start_date/end_date   → date range presisi (bukan 'days')
    - search_depth="advanced" → lebih banyak sumber ditemukan
    """
    all_excludes = list(set(_BASE_EXCLUDE + (extra_exclude_domains or [])))

    def _call() -> dict[str, Any]:
        with ThreadPoolExecutor(max_workers=1) as pool:
            kwargs: dict[str, Any] = {
                "query": query,
                "topic": "general",
                "country": "indonesia",
                "include_answer": "advanced",
                "search_depth": search_depth,
                "max_results": max_results,
                "start_date": start_date,
                "end_date": end_date,
                "exclude_domains": all_excludes,
            }
            if include_domains:
                kwargs["include_domains"] = include_domains

            fut = pool.submit(lambda: client.search(**kwargs))
            return fut.result(timeout=timeout_s)

    return Retrying(
        stop=stop_after_attempt(3),
        retry=retry_if_exception(_is_retryable),
        wait=wait_fixed(0.5),
        reraise=True,
    )(_call)
