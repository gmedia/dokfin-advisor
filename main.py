"""Entry point: NATS worker when NATS_URL is set, else short demo bootstrap."""

from __future__ import annotations

import os
import uuid

import structlog
from advisor.logging_setup import configure_logging, get_logger, log_node_timing
from dotenv import load_dotenv


def main() -> None:
    load_dotenv()
    configure_logging()
    log = get_logger("dokfin_advisor")

    if os.environ.get("NATS_URL"):
        from advisor.nats_worker import run_nats_worker_sync

        log.info("nats_worker_mode")
        run_nats_worker_sync()
        return

    job_id = os.environ.get("DEMO_JOB_ID", str(uuid.uuid4()))
    structlog.contextvars.bind_contextvars(job_id=job_id)

    log.info("service_startup", service="dokfin-advisor", mode="demo_no_nats")
    log_node_timing(log, job_id=job_id, node="bootstrap", duration_ms=0.0)


if __name__ == "__main__":
    main()
