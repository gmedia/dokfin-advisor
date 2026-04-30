"""Node A user text matches PRD §6.2 layout (nilai → status)."""

from __future__ import annotations

import json
from pathlib import Path

from advisor.payload_summary import build_node_a_user_text
from advisor.schemas.input import JobPayload

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "payload_sample.json"


def test_node_a_user_text_matches_prd_shape() -> None:
    payload = JobPayload.model_validate(json.loads(FIXTURE.read_text(encoding="utf-8")))
    text = build_node_a_user_text(payload)

    assert text.startswith("DATA INDIKATOR (ringkasan status saja):")
    assert "Profil bisnis: F&B Retail di Jakarta, 12 karyawan, periode Maret 2026" in text
    assert "- KES_01 Kemampuan bayar harian: 1.3 x → PERLU_PERHATIAN" in text
    assert "- KES_02 Perbandingan aset vs tagihan jangka pendek: 0.35 x → KRITIS" in text
    assert "- KES_03 Kecepatan piutang lunas: — hari → —" in text
    assert "- PRO_01 Margin keuntungan kotor: 38.2% → SEHAT" in text
    assert "- EFI_01 Kecepatan stok terjual: 28 hari → PERLU_PERHATIAN" in text
    assert "- PAT_01 Status pajak: LUNAS → SEHAT" in text
    assert "- PAT_03 Kecocokan catatan kas vs rekening bank: —" in text


def test_pat03_only_status_no_double_arrow() -> None:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    data["dimensi"]["kepatuhan"]["PAT_03"] = {"status": "PERLU_PERHATIAN"}
    payload = JobPayload.model_validate(data)
    text = build_node_a_user_text(payload)
    line = next(ln for ln in text.splitlines() if ln.startswith("- PAT_03"))
    assert line == "- PAT_03 Kecocokan catatan kas vs rekening bank: PERLU_PERHATIAN"
    assert " → " not in line
