"""Node B: Tavily search + cache (PRD §5)."""

from __future__ import annotations

import hashlib
import os
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from datetime import UTC, date, datetime, timedelta
from typing import Any

from tavily import TavilyClient
from tenacity import Retrying, retry_if_exception, stop_after_attempt, wait_fixed

from advisor.cache import MemoryTTLCache, cache_key_for_keyword
from advisor.logging_setup import get_logger, log_node_timing
from advisor.schemas.input import JobPayload
from advisor.search_filters import (
    filter_tavily_results,
    hostname_from_url,
    published_date_for_result,
    root_domain_from_host,
)
from advisor.trusted_domains import trusted_domain_set, trusted_domains_for_tavily

_LOG = get_logger(__name__)
_default_cache = MemoryTTLCache()


def _policy_salt(domains: list[str] | None) -> str:
    if not domains:
        return "open:v2"
    joined = ",".join(sorted(domains))
    return hashlib.md5((joined + "|v2").encode("utf-8")).hexdigest()[:16]


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


def _seeds_from_results(
    filtered: list[dict[str, Any]],
    access_date: str,
    *,
    reference_date: datetime,
    primary_days: int,
) -> list[dict[str, Any]]:
    seeds: list[dict[str, Any]] = []
    for r in filtered:
        url = str(r.get("url") or "")
        host = hostname_from_url(url) or "unknown"
        title = str(r.get("title") or "").strip()
        content = str(r.get("content") or "")
        pub = published_date_for_result(r)
        # Label ringan jika kita terpaksa pakai fallback (lebih tua dari primary window).
        if pub is not None:
            age_days = (reference_date.date() - pub).days
            if age_days > primary_days:
                prefix = (
                    f"Catatan: sumber dipublikasikan {pub.isoformat()} "
                    f"(bukan data {primary_days} hari terakhir). "
                )
                if not content.startswith("Catatan:"):
                    content = prefix + content
        seeds.append(
            {
                "topik": (title or host)[:200],
                "konten": content[:1200],
                "dampak_ke_bisnis": (
                    "Korelasikan dampak dengan kondisi operasional UMKM (data sekunder)."
                ),
                "relevansi": "TINGGI",
                "sumber": host,
                "diakses_pada": access_date,
            },
        )
    return seeds


def _normalize_text(v: object) -> str:
    return str(v or "").strip().lower()


def _contains_any(haystack: str, needles: tuple[str, ...]) -> bool:
    return any(n in haystack for n in needles)


def _relevance_score_for_business(result: dict[str, Any], *, payload: JobPayload) -> float:
    """Deterministic relevance heuristic; higher is more relevant."""
    text = (
        f"{result.get('title') or ''} {result.get('content') or ''} {result.get('url') or ''}"
    ).lower()

    # Hard negative topics that often show up on trusted domains but irrelevant for F&B UMKM.
    hard_blacklist = (
        "gaikindo",
        "otomotif",
        "mobil",
        "kendaraan",
        "rokok",
        "tembakau",
        "sigaret",
        "logistik",
        "ekspor",
        "impor",
        "pandemi",
        "covid",
        "giiass",
    )
    if _contains_any(text, hard_blacklist):
        return -999.0

    industri = _normalize_text(payload.profil_bisnis.industri)
    sub = _normalize_text(payload.profil_bisnis.sub_industri)
    kota = _normalize_text(payload.profil_bisnis.kota)

    # Normalize common alias (Jogja / Yogyakarta).
    kota_aliases: tuple[str, ...] = (kota,) if kota else tuple()
    if kota in ("yogyakarta", "kota yogyakarta", "d.i. yogyakarta", "diy"):
        kota_aliases = ("yogyakarta", "jogja", "diy")
    if kota in ("jogja",):
        kota_aliases = ("yogyakarta", "jogja", "diy")

    score = 0.0
    # Core F&B terms
    fnb_terms = ("f&b", "kuliner", "restoran", "rumah makan", "kafe", "cafe", "makanan", "minuman")
    if _contains_any(text, fnb_terms):
        score += 2.0
    # UMKM / demand terms
    demand_terms = (
        "umkm",
        "konsumen",
        "penjualan",
        "permintaan",
        "daya beli",
        "pesan antar",
        "delivery",
    )
    if _contains_any(text, demand_terms):
        score += 1.0
    # Industry/sub-industry mentions (if present)
    if industri and industri in text:
        score += 1.0
    if sub and sub in text:
        score += 1.0
    # Location mention
    if kota_aliases and any(k and k in text for k in kota_aliases):
        score += 1.0

    return score


def _rank_and_filter_by_relevance(
    results: list[dict[str, Any]],
    *,
    payload: JobPayload,
    min_relevance: float,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for r in results:
        rel = _relevance_score_for_business(r, payload=payload)
        if rel < 0:
            continue
        if rel < min_relevance:
            continue
        r2 = dict(r)
        r2["_relevance"] = rel
        # Boost Tavily ranking lightly (keep stable; avoid overpowering original score).
        base = float(r2.get("score") or 0.0)
        r2["score"] = base + (0.15 * rel)
        out.append(r2)
    return out


def _pick_global_results(
    candidates: list[dict[str, Any]],
    *,
    min_total: int,
    max_total: int,
) -> list[dict[str, Any]]:
    min_total = max(0, min_total)
    max_total = max(0, max_total)
    if max_total <= 0:
        return []
    if not candidates:
        return []

    def _sort_key(r: dict[str, Any]) -> tuple[float, float]:
        return (float(r.get("score") or 0.0), float(r.get("_relevance") or 0.0))

    ranked = sorted(candidates, key=_sort_key, reverse=True)

    picked: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    seen_roots: set[str] = set()

    def _try_pick(r: dict[str, Any], *, enforce_diversity: bool) -> bool:
        url = str(r.get("url") or "")
        if url and url in seen_urls:
            return False
        host = hostname_from_url(url)
        root = root_domain_from_host(host) or host
        if enforce_diversity and root and root in seen_roots:
            return False
        if url:
            seen_urls.add(url)
        if root:
            seen_roots.add(root)
        picked.append(r)
        return True

    # Pass 1: diversity-first
    for r in ranked:
        if len(picked) >= max_total:
            break
        _try_pick(r, enforce_diversity=True)

    # Pass 2: fill remainder regardless diversity
    if len(picked) < max_total:
        for r in ranked:
            if len(picked) >= max_total:
                break
            _try_pick(r, enforce_diversity=False)

    # If we still cannot reach min_total, return what we have (no error).
    return picked[:max_total]


def _pick_results_with_ladders(
    results: list[dict[str, Any]],
    *,
    trusted_domains: set[str],
    reference_date: date,
    min_words: int,
    max_keep: int,
    min_keep: int,
    ladder_days: list[int],
) -> list[dict[str, Any]]:
    """Pick results with age ladder; aim for >=min_keep and up to max_keep."""
    min_keep = max(0, min(min_keep, max_keep))
    picked: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    seen_roots: set[str] = set()

    def _add_candidates(cands: list[dict[str, Any]], *, target: int) -> None:
        nonlocal picked
        if len(picked) >= target:
            return
        # 1) Prefer diverse roots
        for r in cands:
            if len(picked) >= target:
                break
            url = str(r.get("url") or "")
            if url and url in seen_urls:
                continue
            host = hostname_from_url(url)
            root = root_domain_from_host(host) or host
            if root and root in seen_roots:
                continue
            if url:
                seen_urls.add(url)
            if root:
                seen_roots.add(root)
            picked.append(r)
        # 2) Fill remaining regardless root (last resort)
        for r in cands:
            if len(picked) >= target:
                break
            url = str(r.get("url") or "")
            if url and url in seen_urls:
                continue
            host = hostname_from_url(url)
            root = root_domain_from_host(host) or host
            if url:
                seen_urls.add(url)
            if root:
                seen_roots.add(root)
            picked.append(r)

    for days in ladder_days:
        cands = filter_tavily_results(
            results,
            trusted_domains=trusted_domains,
            reference_date=reference_date,
            max_keep=max_keep,
            min_words=min_words,
            max_age=timedelta(days=days),
        )
        # Ensure we get at least min_keep, then fill up to max_keep
        target = min_keep if len(picked) < min_keep else max_keep
        _add_candidates(cands, target=target)
        if len(picked) >= max_keep:
            break

    return picked[:max_keep]


def run_search(
    state: dict[str, Any],
    *,
    cache: MemoryTTLCache | None = None,
    tavily_client: TavilyClient | None = None,
) -> dict[str, Any]:
    """Fetch market context from Tavily for sanitized keywords in `reasoning`."""
    job_id = str(state.get("job_id", ""))
    payload = JobPayload.model_validate(state.get("payload") or {})
    reasoning = state.get("reasoning") or {}
    keywords = reasoning.get("search_keywords") or []
    cache = cache or _default_cache
    timeout_s = float(os.environ.get("TAVILY_TIMEOUT_S", "30"))
    include_domains = trusted_domains_for_tavily()
    salt = _policy_salt(include_domains)
    trusted = trusted_domain_set()
    ref_dt = datetime.now(UTC)
    ref_date = ref_dt.date()

    t0 = time.perf_counter()
    per_kw_answer: dict[str, str] = {}
    all_candidates: list[dict[str, Any]] = []
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
        if isinstance(cached, dict) and "picked_results" in cached:
            answer = str(cached.get("answer") or "")
            picked_results = cached.get("picked_results") or []
            if isinstance(picked_results, list):
                per_kw_answer[kw] = answer
                for r in [dict(x) for x in picked_results if isinstance(x, dict)]:
                    r["_kw"] = kw
                    all_candidates.append(r)
            continue
        if isinstance(cached, str):
            per_kw_answer[kw] = ""
            continue
        if client is None:
            continue
        try:
            resp = _search_with_retries(client, kw, timeout_s, include_domains=include_domains)
            answer = str(resp.get("answer") or "")
            results = list(resp.get("results") or [])
            min_words = int(os.environ.get("TAVILY_MIN_WORDS", "100"))
            primary_days = int(os.environ.get("TAVILY_MAX_AGE_DAYS_PRIMARY", "30"))
            fallback_days = int(os.environ.get("TAVILY_MAX_AGE_DAYS_FALLBACK", "60"))
            fallback2_days = int(os.environ.get("TAVILY_MAX_AGE_DAYS_FALLBACK2", "183"))
            min_relevance = float(os.environ.get("TAVILY_MIN_RELEVANCE", "1.0"))
            rel_filtered = _rank_and_filter_by_relevance(
                results,
                payload=payload,
                min_relevance=min_relevance,
            )

            max_keep = 3
            # Per-keyword minimum keep: default 1 (global min/max will handle overall coverage).
            min_keep = int(os.environ.get("TAVILY_MIN_KEEP", "1"))
            filtered = _pick_results_with_ladders(
                rel_filtered,
                trusted_domains=trusted,
                reference_date=ref_date,
                min_words=min_words,
                max_keep=max_keep,
                min_keep=min_keep,
                ladder_days=[primary_days, fallback_days, fallback2_days],
            )
            per_kw_answer[kw] = answer
            # Attach context for global picking + later seed rendering.
            picked_results: list[dict[str, Any]] = []
            for r in filtered:
                r2 = dict(r)
                r2["_kw"] = kw
                picked_results.append(r2)
                all_candidates.append(r2)
            cache.set(ck, {"answer": answer, "picked_results": picked_results})
        except Exception as e:  # noqa: BLE001
            _LOG.warning("tavily_search_failed", job_id=job_id, keyword=kw, error=str(e))

    min_total = int(os.environ.get("TAVILY_KONTEKS_PASAR_MIN_TOTAL", "2"))
    max_total = int(os.environ.get("TAVILY_KONTEKS_PASAR_MAX_TOTAL", "3"))
    picked_global = _pick_global_results(
        all_candidates,
        min_total=min_total,
        max_total=max_total,
    )

    by_kw: dict[str, list[dict[str, Any]]] = {}
    for r in picked_global:
        kw = str(r.get("_kw") or "")
        by_kw.setdefault(kw, []).append(r)

    blocks: list[str] = []
    for kw, rs in by_kw.items():
        blocks.append(_format_market_block(kw, per_kw_answer.get(kw, ""), rs))
    market_context = "\n\n".join(blocks) if blocks else ""

    access_date = ref_date.isoformat()
    all_seeds = _seeds_from_results(
        picked_global,
        access_date,
        reference_date=ref_dt,
        primary_days=int(os.environ.get("TAVILY_MAX_AGE_DAYS_PRIMARY", "30")),
    )
    elapsed_ms = (time.perf_counter() - t0) * 1000
    log_node_timing(_LOG, job_id=job_id, node="B", duration_ms=elapsed_ms, keywords=len(keywords))

    return {"market_context": market_context, "konteks_pasar_seed": all_seeds}
