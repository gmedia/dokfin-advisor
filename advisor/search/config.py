"""Tavily search configuration: env vars dan date range calculation."""

from __future__ import annotations

import os
from datetime import date, timedelta
from typing import Any

POLICY_SALT = "v3-indonesia|topic=general|country=indonesia"


def _env_first(*names: str, default: str) -> str:
    for name in names:
        value = os.environ.get(name)
        if value not in (None, ""):
            return value
    return default


def _env_bool(*names: str, default: str = "0") -> bool:
    return _env_first(*names, default=default).strip().lower() in ("1", "true", "yes")


def get_search_config() -> dict[str, Any]:
    """Load search configuration from environment variables."""
    return {
        "max_keywords": int(_env_first("SEARCH_MAX_QUERIES", "SEARCH_MAX_KEYWORDS", default="1")),
        "query_selection_mode": os.environ.get("SEARCH_QUERY_SELECTION_MODE", "best")
        .strip()
        .lower(),
        "enable_enhancement": _env_bool(
            "SEARCH_ENHANCEMENT_ENABLED",
            "SEARCH_ENABLE_ENHANCEMENT",
        ),
        "max_enhanced_total": int(os.environ.get("SEARCH_MAX_ENHANCED_TOTAL", "0")),
        "timeout_s": float(os.environ.get("TAVILY_TIMEOUT_S", "35")),
        "max_results": int(os.environ.get("TAVILY_FETCH_MAX_RESULTS", "5")),
        "search_depth": os.environ.get("TAVILY_SEARCH_DEPTH", "basic"),
        "include_answer": os.environ.get("TAVILY_INCLUDE_ANSWER", "0").strip().lower()
        in ("1", "true", "yes", "advanced", "basic"),
        "min_words": int(os.environ.get("TAVILY_MIN_WORDS", "80")),
        "primary_days": int(os.environ.get("TAVILY_MAX_AGE_DAYS_PRIMARY", "90")),
        "min_relevance": float(os.environ.get("TAVILY_MIN_RELEVANCE", "0.5")),
        "force_indonesia_only": os.environ.get("TAVILY_FORCE_INDONESIA", "1").strip()
        in (
            "1",
            "true",
            "yes",
        ),
        "konteks_pasar_min": int(os.environ.get("TAVILY_KONTEKS_PASAR_MIN_TOTAL", "2")),
        "konteks_pasar_max": int(os.environ.get("TAVILY_KONTEKS_PASAR_MAX_TOTAL", "5")),
    }


def date_range_for_search(primary_days: int = 90) -> tuple[str, str]:
    """
    Hitung start/end date untuk Tavily.

    Strategi: selalu gunakan window dari hari ini ke belakang (primary_days).
    Konteks pasar harus relevan dengan kondisi pasar saat ini, bukan periode analisis
    historis — karena rekomendasi yang dihasilkan harus actionable sekarang.
    Returns: (start_date, end_date) sebagai string ISO YYYY-MM-DD.
    """
    today = date.today()
    start = today - timedelta(days=primary_days)
    return start.isoformat(), today.isoformat()
