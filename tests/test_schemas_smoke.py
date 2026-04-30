"""Smoke tests for Pydantic job payload."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from advisor.schemas.input import JobPayload
from advisor.schemas.output import DimensiSatuOut
from pydantic import ValidationError

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "payload_minimal.json"


def test_job_payload_from_fixture() -> None:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    payload = JobPayload.model_validate(data)
    assert payload.job_id.version == 4
    assert payload.dimensi.likuiditas["KES_01"].status.value == "PERLU_PERHATIAN"


def test_dimensi_satu_rejects_status_mismatch_skor() -> None:
    with pytest.raises(ValidationError, match="tidak selaras"):
        DimensiSatuOut(
            skor=8.0,
            status="PERLU_PERHATIAN",
            narasi="x",
            saran=[],
        )


def test_job_payload_accepts_optional_skor_periode_sebelumnya() -> None:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    data["profil_bisnis"]["skor_keseluruhan_periode_sebelumnya"] = 6.2
    p = JobPayload.model_validate(data)
    assert p.profil_bisnis.skor_keseluruhan_periode_sebelumnya == 6.2


def test_job_id_must_be_uuid_v4() -> None:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    data["job_id"] = "6ba7b810-9dad-11d1-80b4-00c04fd430c8"
    with pytest.raises(ValidationError, match="job_id must be UUID version 4"):
        JobPayload.model_validate(data)
