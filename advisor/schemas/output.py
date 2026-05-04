"""Pydantic models for advisor result published to NATS `bhc.results` (PRD section 8)."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from advisor.schemas.input import IndikatorStatus
from advisor.scoring import status_agregat_dimensi_dari_skor


class ErrorCode(StrEnum):
    """Error codes (PRD 8.2 table)."""

    LLM_TIMEOUT = "LLM_TIMEOUT"
    LLM_INVALID_JSON = "LLM_INVALID_JSON"
    TAVILY_ERROR = "TAVILY_ERROR"
    PAYLOAD_INVALID = "PAYLOAD_INVALID"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


class TokenUsage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_a_input: int | None = None
    node_a_output: int | None = None
    node_c_input: int | None = None
    node_c_output: int | None = None
    total: int | None = None


SkorKeseluruhanTrend = Literal["naik", "turun", "stabil", "datar", "tidak_tersedia"]


class SkorKeseluruhanOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nilai: float
    label: str
    trend: SkorKeseluruhanTrend
    vs_periode_lalu: float | None


class RingkasanEksekutifOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    narasi: str
    highlight_positif: list[str]
    highlight_warning: list[str]


class DimensiSatuOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    skor: float
    status: IndikatorStatus
    narasi: str
    saran: list[str]

    @model_validator(mode="after")
    def status_selaras_skor(self) -> Self:
        expected = status_agregat_dimensi_dari_skor(self.skor)
        if self.status != expected:
            msg = (
                f"status {self.status} tidak selaras dengan skor {self.skor} "
                f"(harus {expected.value})"
            )
            raise ValueError(msg)
        return self


class DimensiReportOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    likuiditas: DimensiSatuOut
    profitabilitas: DimensiSatuOut
    efisiensi: DimensiSatuOut
    solvabilitas: DimensiSatuOut
    sdm: DimensiSatuOut
    kepatuhan: DimensiSatuOut


class KonteksPasarItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topik: str
    konten: str
    dampak_ke_bisnis: str | None = None
    relevansi: str
    sumber: str | None = None
    diakses_pada: str | None = None
    diterbitkan_pada: str | None = None


class RekomendasiPrioritasItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prioritas: int = Field(..., ge=1, le=3)
    label: Literal["SEGERA", "BULAN_INI", "PELUANG"]
    aksi: str
    detail: str
    estimasi_dampak: str


class AdvisorResultDone(BaseModel):
    """Result sukses (PRD 8.1)."""

    model_config = ConfigDict(extra="forbid")

    job_id: UUID
    status: Literal["DONE"] = "DONE"
    generated_at: datetime
    model_used: str
    token_usage: TokenUsage | None = None
    estimated_cost_idr: float | None = None
    processing_time_seconds: float | None = None
    skor_keseluruhan: SkorKeseluruhanOut
    ringkasan_eksekutif: RingkasanEksekutifOut
    dimensi: DimensiReportOut
    konteks_pasar: list[KonteksPasarItem]
    rekomendasi_prioritas: list[RekomendasiPrioritasItem]


class AdvisorResultFailed(BaseModel):
    """Result gagal (PRD 8.2)."""

    model_config = ConfigDict(extra="forbid")

    job_id: UUID
    status: Literal["FAILED"] = "FAILED"
    generated_at: datetime
    error_code: ErrorCode
    error_message: str
    retry_count: int = Field(..., ge=0)
    processing_time_seconds: float | None = None
    token_usage: TokenUsage | None = None
    estimated_cost_idr: float | None = None


AdvisorResult = Annotated[
    AdvisorResultDone | AdvisorResultFailed,
    Field(discriminator="status"),
]
