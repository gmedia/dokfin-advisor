"""ContextualizeResult normalizes LLM quirks (dimensi_terburuk casing)."""

from __future__ import annotations

import pytest
from advisor.schemas.reasoning import ContextualizeResult
from pydantic import ValidationError


def _minimal(**overrides: object) -> dict:
    base = {
        "indikator_kritis": ["KES_01"],
        "dimensi_terburuk": "likuiditas",
        "search_keywords": ["tren umkm indonesia", "benchmark kuliner"],
    }
    base.update(overrides)
    return base


def test_dimensi_terburuk_title_case_accepted() -> None:
    r = ContextualizeResult.model_validate(_minimal(dimensi_terburuk="Profitabilitas"))
    assert r.dimensi_terburuk == "profitabilitas"


def test_dimensi_terburuk_whitespace_stripped() -> None:
    r = ContextualizeResult.model_validate(_minimal(dimensi_terburuk="  SDM  "))
    assert r.dimensi_terburuk == "sdm"


def test_dimensi_terburuk_invalid_rejected() -> None:
    with pytest.raises(ValidationError, match="dimensi_terburuk"):
        ContextualizeResult.model_validate(_minimal(dimensi_terburuk="cashflow"))
