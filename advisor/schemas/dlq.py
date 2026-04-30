"""Dead-letter queue payload (PRD section 9.2)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DlqMessage(BaseModel):
    """Published to `bhc.dlq` when the pipeline fails after retries (PRD 9.2)."""

    model_config = ConfigDict(extra="forbid")

    job_id: UUID
    original_payload: dict[str, Any]
    error: str = Field(..., max_length=8000)
    failed_at: str = Field(..., description="ISO8601 UTC with Z suffix")
    retry_count: int = Field(..., ge=0)
