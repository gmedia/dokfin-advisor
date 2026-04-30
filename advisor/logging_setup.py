"""Structured logging (structlog) and helpers for pipeline observability."""

from __future__ import annotations

import logging
import os
import sys
from typing import Any

import structlog

_CONFIGURED = False


def configure_logging() -> None:
    """Configure structlog + stdlib logging once per process (idempotent)."""
    global _CONFIGURED
    if _CONFIGURED:
        return
    _CONFIGURED = True

    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level,
    )

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)


def bind_job_context(*, job_id: str) -> None:
    """Set structlog contextvars for `job_id` (PRD: semua log bawa job_id)."""
    structlog.contextvars.clear_contextvars()
    if job_id:
        structlog.contextvars.bind_contextvars(job_id=job_id)


def log_node_timing(
    logger: structlog.BoundLogger,
    *,
    job_id: str,
    node: str,
    duration_ms: float,
    **kwargs: Any,
) -> None:
    """Emit one structured event per node with duration (Sprint 0 contract)."""
    logger.info(
        "node_timing",
        job_id=job_id,
        node=node,
        duration_ms=round(duration_ms, 3),
        **kwargs,
    )
