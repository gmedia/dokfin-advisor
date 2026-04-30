"""Pydantic contracts for NATS payloads."""

from advisor.schemas.input import (
    IndikatorRow,
    IndikatorStatus,
    JobDimensions,
    JobPayload,
    ProfilBisnis,
)
from advisor.schemas.output import (
    AdvisorResult,
    AdvisorResultDone,
    AdvisorResultFailed,
    ErrorCode,
)

__all__ = [
    "AdvisorResult",
    "AdvisorResultDone",
    "AdvisorResultFailed",
    "ErrorCode",
    "IndikatorRow",
    "IndikatorStatus",
    "JobDimensions",
    "JobPayload",
    "ProfilBisnis",
]
