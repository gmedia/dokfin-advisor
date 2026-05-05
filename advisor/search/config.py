"""Tavily search configuration: env vars dan date range calculation."""

from __future__ import annotations

import os
from datetime import date, timedelta
from typing import Any

POLICY_SALT = "v3-indonesia|topic=general|country=indonesia"


def get_search_config() -> dict[str, Any]:
    """Load search configuration from environment variables."""
    return {
        "timeout_s": float(os.environ.get("TAVILY_TIMEOUT_S", "35")),
        "max_results": int(os.environ.get("TAVILY_FETCH_MAX_RESULTS", "3")),
        "search_depth": os.environ.get("TAVILY_SEARCH_DEPTH", "advanced"),
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
