"""Build human-readable summaries for prompts (Node A: status-only, no numeric values)."""

from __future__ import annotations

from advisor.schemas.input import JobPayload


def _lines_for_block(block: dict[str, object], labels: dict[str, str]) -> list[str]:
    lines: list[str] = []
    for code, row in sorted(block.items()):
        if not isinstance(row, dict):
            continue
        st = row.get("status")
        if st is None:
            continue
        label = labels.get(code, code)
        key = getattr(st, "value", st)
        lines.append(f"- {code} {label}: → {key}")
    return lines


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


def build_node_a_user_text(payload: JobPayload) -> str:
    """Ringkasan status saja (tanpa angka) untuk Node A — mengurangi risiko keyword bocor."""
    p = payload.profil_bisnis
    dim = payload.dimensi.model_dump()
    sections: list[str] = [
        "DATA INDIKATOR (ringkasan status saja):",
        "",
        (
            f"Profil bisnis: {p.industri} di {p.kota}, "
            f"{p.jumlah_karyawan} karyawan, periode {p.periode_analisis}"
        ),
        "",
        "Likuiditas:",
        *_lines_for_block(dim["likuiditas"], _NODE_A_LABELS["likuiditas"]),
        "",
        "Profitabilitas:",
        *_lines_for_block(dim["profitabilitas"], _NODE_A_LABELS["profitabilitas"]),
        "",
        "Efisiensi:",
        *_lines_for_block(dim["efisiensi"], _NODE_A_LABELS["efisiensi"]),
        "",
        "Solvabilitas:",
        *_lines_for_block(dim["solvabilitas"], _NODE_A_LABELS["solvabilitas"]),
        "",
        "SDM:",
        *_lines_for_block(dim["sdm"], _NODE_A_LABELS["sdm"]),
        "",
        "Kepatuhan:",
        *_lines_for_block(dim["kepatuhan"], _NODE_A_LABELS["kepatuhan"]),
    ]
    return "\n".join(sections)
