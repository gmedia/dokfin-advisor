"""Structured output from Node A (contextualize), PRD §6.2."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from advisor.keyword_safety import sanitize_search_keywords

_DIMENSI_TERBURUK: frozenset[str] = frozenset(
    ("likuiditas", "profitabilitas", "efisiensi", "solvabilitas", "sdm", "kepatuhan")
)


class ContextualizeResult(BaseModel):
    """JSON shape from Node A after validation + keyword sanitization."""

    model_config = ConfigDict(extra="forbid")

    indikator_kritis: list[str] = Field(..., max_length=3)
    dimensi_terburuk: Literal[
        "likuiditas",
        "profitabilitas",
        "efisiensi",
        "solvabilitas",
        "sdm",
        "kepatuhan",
    ]
    search_keywords: list[str] = Field(..., min_length=1, max_length=3)
    ada_perishable_kritis: bool = False
    flag_data_tidak_lengkap: bool = False

    @field_validator("dimensi_terburuk", mode="before")
    @classmethod
    def normalize_dimensi_terburuk(cls, v: object) -> str:
        """Gemini/LLM kadang mengembalikan kapitalisasi judul; wajib slug lowercase PRD."""
        if not isinstance(v, str):
            msg = "dimensi_terburuk must be a string"
            raise TypeError(msg)
        key = v.strip().lower()
        if key not in _DIMENSI_TERBURUK:
            msg = f"dimensi_terburuk must be one of {sorted(_DIMENSI_TERBURUK)}, got {v!r}"
            raise ValueError(msg)
        return key

    @field_validator("indikator_kritis", mode="before")
    @classmethod
    def cap_indikator(cls, v: object) -> list[str]:
        if not isinstance(v, list):
            msg = "indikator_kritis must be a list"
            raise TypeError(msg)
        return [str(x) for x in v][:3]

    @field_validator("search_keywords", mode="before")
    @classmethod
    def sanitize_keywords(cls, v: object) -> list[str]:
        if not isinstance(v, list):
            msg = "search_keywords must be a list"
            raise TypeError(msg)
        raw = [str(x) for x in v]
        out = sanitize_search_keywords(raw, max_items=3)
        if len(out) == 1:
            out = out + ["benchmark umkm industri indonesia"]
        return out[:3]
