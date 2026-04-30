"""Build human-readable summaries for prompts (Node A: PRD §6.2 user block)."""

from __future__ import annotations

import math
from typing import Any

from advisor.schemas.input import JobPayload

_NODE_A_LABELS: dict[str, dict[str, str]] = {
    "likuiditas": {
        "KES_01": "Kemampuan bayar harian",
        "KES_02": "Perbandingan aset vs tagihan jangka pendek",
        "KES_03": "Kecepatan piutang lunas",
        "KES_04": "Arus kas periode ini",
    },
    "profitabilitas": {
        "PRO_01": "Margin keuntungan kotor",
        "PRO_02": "Margin keuntungan bersih",
        "PRO_03": "Seberapa produktif aset menghasilkan uang",
        "PRO_04": "Tren keuntungan vs bulan lalu",
        "PRO_05": "Pencapaian vs titik balik modal",
    },
    "efisiensi": {
        "EFI_01": "Kecepatan stok terjual",
        "EFI_02": "Proporsi biaya produksi dari penjualan",
        "EFI_03": "Efisiensi belanja bahan vs kebutuhan",
        "EFI_04": "Nilai stok yang tidak bergerak",
        "EFI_05": "Ketelitian pencatatan jurnal",
    },
    "solvabilitas": {
        "SOL_01": "Rasio hutang vs modal sendiri",
        "SOL_02": "Komposisi hutang pendek vs panjang",
        "SOL_03": "Kondisi aset tetap (peralatan dll)",
        "SOL_04": "Kemampuan laba bayar cicilan hutang",
    },
    "sdm": {
        "SDM_01": "Porsi gaji dari omzet",
        "SDM_02": "Pendapatan per karyawan",
        "SDM_03": "Pencapaian target penjualan",
    },
    "kepatuhan": {
        "PAT_01": "Status pajak",
        "PAT_02": "Kelengkapan laporan keuangan",
        "PAT_03": "Kecocokan catatan kas vs rekening bank",
    },
}


def _row_dict(row: object) -> dict[str, Any]:
    if row is None:
        return {}
    if isinstance(row, dict):
        return row
    if hasattr(row, "model_dump"):
        return row.model_dump(mode="json")
    return {}


def _status_str(row: dict[str, Any]) -> str:
    st = row.get("status")
    if st is None:
        return "—"
    return str(getattr(st, "value", st))


def _num_str(v: Any) -> str:
    if v is None:
        return "—"
    if isinstance(v, bool):
        return str(v)
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    if math.isnan(f):
        return "—"
    if abs(f - round(f)) < 1e-9:
        return str(int(round(f)))
    s = f"{f:.2f}"
    return s.rstrip("0").rstrip(".")


def _idr_pretty(v: Any) -> str:
    if v is None:
        return "—"
    if isinstance(v, str) and v.strip():
        return v.strip()
    try:
        n = int(round(float(v)))
    except (TypeError, ValueError):
        return str(v)
    neg = n < 0
    n = abs(n)
    raw = f"{n:,}"
    s = ".".join(raw.split(","))
    prefix = "-Rp " if neg else "Rp "
    return prefix + s


def _mid_fragment(code: str, row: dict[str, Any]) -> str:
    if code == "KES_01" or code == "KES_02":
        return f"{_num_str(row.get('nilai'))} x"
    if code == "KES_03":
        return f"{_num_str(row.get('nilai_hari'))} hari"
    if code == "KES_04":
        fmt = row.get("nilai_formatted")
        if isinstance(fmt, str) and fmt.strip():
            return fmt.strip()
        n = row.get("nilai")
        if n is not None:
            return _num_str(n)
        return "—"
    if code in ("PRO_01", "PRO_02", "PRO_03", "PRO_04"):
        return f"{_num_str(row.get('nilai'))}%"
    if code == "PRO_05":
        v = row.get("rasio_aktual", row.get("nilai"))
        return f"{_num_str(v)}x"
    if code == "EFI_01":
        return f"{_num_str(row.get('nilai_hari'))} hari"
    if code == "EFI_02":
        return f"{_num_str(row.get('nilai'))}%"
    if code == "EFI_03":
        return f"{_num_str(row.get('nilai'))}x"
    if code == "EFI_04":
        fmt = row.get("nilai_total_idr_formatted")
        if isinstance(fmt, str) and fmt.strip():
            return fmt.strip()
        return _idr_pretty(row.get("nilai_total_idr"))
    if code == "EFI_05":
        return f"{_num_str(row.get('persen_error'))}% error"
    if code == "SOL_01" or code == "SOL_04":
        return f"{_num_str(row.get('nilai'))}x"
    if code == "SOL_02":
        return f"{_num_str(row.get('persen_jangka_pendek'))}% pendek"
    if code == "SOL_03":
        return f"{_num_str(row.get('rasio_depresiasi_persen'))}% terdepresiasi"
    if code == "SDM_01":
        return f"{_num_str(row.get('nilai'))}%"
    if code == "SDM_02":
        fmt = row.get("nilai_idr_formatted")
        if isinstance(fmt, str) and fmt.strip():
            return fmt.strip()
        return _idr_pretty(row.get("nilai_idr"))
    if code == "SDM_03":
        return f"{_num_str(row.get('pencapaian_persen'))}%"
    if code == "PAT_02":
        return f"{_num_str(row.get('kelengkapan_persen'))}%"
    return "—"


def _format_indicator_line(code: str, label: str, row: dict[str, Any]) -> str:
    st = _status_str(row)
    if code == "PAT_03":
        return f"- {code} {label}: {st}"
    if code == "PAT_01":
        sb = row.get("status_bayar", "—")
        if sb is None or sb == "":
            sb = "—"
        return f"- {code} {label}: {sb} → {st}"

    mid = _mid_fragment(code, row)
    return f"- {code} {label}: {mid} → {st}"


def _lines_for_block(block: dict[str, object], dim_key: str) -> list[str]:
    labels = _NODE_A_LABELS[dim_key]
    lines: list[str] = []
    for code in sorted(labels.keys()):
        label = labels[code]
        raw = block.get(code)
        rd = _row_dict(raw)
        lines.append(_format_indicator_line(code, label, rd))
    return lines


def build_node_a_user_text(payload: JobPayload) -> str:
    """User prompt Node A — sama struktur PRD §6.2 (nilai + status per indikator)."""
    p = payload.profil_bisnis
    dim = payload.dimensi.model_dump(mode="json")
    sections: list[str] = [
        "DATA INDIKATOR (ringkasan status saja):",
        "",
        (
            f"Profil bisnis: {p.industri} di {p.kota}, "
            f"{p.jumlah_karyawan} karyawan, periode {p.periode_analisis}"
        ),
        "",
        "Likuiditas:",
        *_lines_for_block(dim["likuiditas"], "likuiditas"),
        "",
        "Profitabilitas:",
        *_lines_for_block(dim["profitabilitas"], "profitabilitas"),
        "",
        "Efisiensi:",
        *_lines_for_block(dim["efisiensi"], "efisiensi"),
        "",
        "Solvabilitas:",
        *_lines_for_block(dim["solvabilitas"], "solvabilitas"),
        "",
        "SDM:",
        *_lines_for_block(dim["sdm"], "sdm"),
        "",
        "Kepatuhan:",
        *_lines_for_block(dim["kepatuhan"], "kepatuhan"),
    ]
    return "\n".join(sections)
