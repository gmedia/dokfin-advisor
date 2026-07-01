"""CLI smoke tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from advisor.cli import main


@pytest.fixture(autouse=True)
def _skip_dotenv(monkeypatch) -> None:
    monkeypatch.setattr("advisor.cli.load_dotenv", lambda: None)


def test_analyze_command_prints_json(monkeypatch, tmp_path, capsys) -> None:
    payload_path = tmp_path / "payload.json"
    payload_path.write_text(
        json.dumps({"job_id": "550e8400-e29b-41d4-a716-446655440000"}),
        encoding="utf-8",
    )

    def fake_run_advisor(payload):
        assert payload["job_id"] == "550e8400-e29b-41d4-a716-446655440000"
        return {"status": "DONE", "job_id": payload["job_id"]}

    monkeypatch.setattr("advisor.graph.run_advisor", fake_run_advisor)

    main(["analyze", str(payload_path), "--compact"])

    out = json.loads(capsys.readouterr().out)
    assert out == {
        "status": "DONE",
        "job_id": "550e8400-e29b-41d4-a716-446655440000",
    }


def test_analyze_command_writes_output_file(monkeypatch, tmp_path) -> None:
    payload_path = tmp_path / "payload.json"
    output_path = tmp_path / "result.json"
    payload_path.write_text(json.dumps({"job_id": "job-1"}), encoding="utf-8")

    monkeypatch.setattr(
        "advisor.graph.run_advisor",
        lambda payload: {"status": "DONE", "job_id": payload["job_id"]},
    )

    main(["analyze", str(payload_path), "-o", str(output_path)])

    out = json.loads(Path(output_path).read_text(encoding="utf-8"))
    assert out == {"status": "DONE", "job_id": "job-1"}
