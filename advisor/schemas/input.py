"""Pydantic models for Laravel job payload (PRD section 3)."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class IndikatorStatus(StrEnum):
    """Status per indikator (PRD 3.2)."""

    SEHAT = "SEHAT"
    PERLU_PERHATIAN = "PERLU_PERHATIAN"
    KRITIS = "KRITIS"
    ON_TRACK = "ON_TRACK"
    TURUN = "TURUN"
    DATA_TIDAK_TERSEDIA = "DATA_TIDAK_TERSEDIA"


class IndikatorRow(BaseModel):
    """One indicator row: `status` required; other fields vary by kode (PRD sample)."""

    model_config = ConfigDict(extra="allow")

    status: IndikatorStatus


class JobDimensions(BaseModel):
    """Enam dimensi wajib (PRD 3.2)."""

    model_config = ConfigDict(extra="forbid")

    likuiditas: dict[str, IndikatorRow] = Field(
        ...,
        description="Map kode indikator -> data; setiap item wajib punya status.",
    )
    profitabilitas: dict[str, IndikatorRow] = Field(...)
    efisiensi: dict[str, IndikatorRow] = Field(...)
    solvabilitas: dict[str, IndikatorRow] = Field(...)
    sdm: dict[str, IndikatorRow] = Field(...)
    kepatuhan: dict[str, IndikatorRow] = Field(...)


class ProfilBisnis(BaseModel):
    """Profil bisnis (PRD 3.1)."""

    model_config = ConfigDict(extra="forbid")

    industri: str
    sub_industri: str
    kota: str
    skala: str
    jumlah_karyawan: int
    periode_analisis: str
    periode_bulan: int
    periode_tahun: int
    kelengkapan_data_persen: float
    skor_keseluruhan_periode_sebelumnya: float | None = None


class JobPayload(BaseModel):
    """Root payload dari Laravel via NATS `bhc.jobs`."""

    model_config = ConfigDict(extra="forbid")

    job_id: UUID
    created_at: datetime
    profil_bisnis: ProfilBisnis
    dimensi: JobDimensions

    @field_validator("job_id")
    @classmethod
    def job_id_must_be_uuid_v4(cls, v: UUID) -> UUID:
        if v.version != 4:
            msg = "job_id must be UUID version 4"
            raise ValueError(msg)
        return v
