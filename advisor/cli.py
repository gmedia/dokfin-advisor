"""CLI entry point: direct JSON analyze, NATS worker, or short demo bootstrap."""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any

import structlog
from dotenv import load_dotenv

from advisor.logging_setup import configure_logging, get_logger, log_node_timing


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dokfin-advisor",
        description="Run Dokfin Advisor via direct JSON payload or NATS JetStream worker.",
    )
    sub = parser.add_subparsers(dest="command")

    analyze = sub.add_parser(
        "analyze",
        help="Analyze one Laravel payload JSON without NATS.",
    )
    analyze.add_argument("payload", help="Path to payload JSON from Laravel.")
    analyze.add_argument(
        "-o",
        "--output",
        default="-",
        help="Output path for result JSON. Use '-' for stdout. Default: '-'.",
    )
    analyze.add_argument(
        "--compact",
        action="store_true",
        help="Print compact JSON instead of pretty formatted JSON.",
    )

    sub.add_parser("worker", help="Run the NATS JetStream worker.")
    sub.add_parser("demo", help="Run a short startup/demo bootstrap.")

    return parser


def _read_payload(path: str) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        msg = "payload JSON root must be an object"
        raise ValueError(msg)
    return data


def _write_result(result: dict[str, Any], *, output: str, compact: bool) -> None:
    indent = None if compact else 2
    text = json.dumps(result, ensure_ascii=False, indent=indent)
    if output == "-":
        print(text)
        return
    Path(output).write_text(text + "\n", encoding="utf-8")


def _run_analyze(args: argparse.Namespace) -> None:
    # Keep stdout clean for JSON output; pipeline logs go to stderr.
    configure_logging(stream=sys.__stderr__)
    from advisor.graph import run_advisor

    payload = _read_payload(args.payload)
    result = run_advisor(payload)
    _write_result(result, output=args.output, compact=args.compact)


def _run_worker() -> None:
    configure_logging()
    log = get_logger("dokfin_advisor")
    from advisor.nats_worker import run_nats_worker_sync

    log.info("nats_worker_mode")
    run_nats_worker_sync()


def _run_demo() -> None:
    configure_logging()
    log = get_logger("dokfin_advisor")
    job_id = os.environ.get("DEMO_JOB_ID", str(uuid.uuid4()))
    structlog.contextvars.bind_contextvars(job_id=job_id)

    log.info("service_startup", service="dokfin-advisor", mode="demo_no_nats")
    log_node_timing(log, job_id=job_id, node="bootstrap", duration_ms=0.0)


def main(argv: list[str] | None = None) -> None:
    load_dotenv()
    argv = list(sys.argv[1:] if argv is None else argv)

    # Backward-compatible behavior for container deployments.
    if not argv:
        if os.environ.get("NATS_URL"):
            _run_worker()
        else:
            _run_demo()
        return

    args = _build_parser().parse_args(argv)
    if args.command == "analyze":
        _run_analyze(args)
    elif args.command == "worker":
        _run_worker()
    elif args.command == "demo":
        _run_demo()
    else:
        _build_parser().print_help()
