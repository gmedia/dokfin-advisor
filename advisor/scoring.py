"""Deterministic scoring (PRD section 7). LLM must not compute scores."""

from __future__ import annotations

from typing import Any

STATUS_POIN: dict[str, int | None] = {
    "SEHAT": 10,
    "ON_TRACK": 8,
    "PERLU_PERHATIAN": 6,
    "TURUN": 4,
    "KRITIS": 2,
    "DATA_TIDAK_TERSEDIA": None,
}

BOBOT_DIMENSI: dict[str, float] = {
    "likuiditas": 0.25,
    "profitabilitas": 0.25,
    "efisiensi": 0.20,
    "solvabilitas": 0.15,
    "sdm": 0.10,
    "kepatuhan": 0.05,
}


def hitung_skor_dimensi(indikator_dict: dict[str, Any]) -> float:
    poin_list: list[int] = []
    for _kode, data in indikator_dict.items():
        if not isinstance(data, dict):
            continue
        status = data.get("status")
        if status is None:
            continue
        key = getattr(status, "value", status)
        poin = STATUS_POIN.get(str(key))
        if poin is not None:
            poin_list.append(poin)
    if not poin_list:
        return 5.0
    return sum(poin_list) / len(poin_list)


def hitung_skor_keseluruhan(skor_per_dimensi: dict[str, float]) -> float:
    total = 0.0
    for dimensi, bobot in BOBOT_DIMENSI.items():
        skor = skor_per_dimensi.get(dimensi, 5.0)
        total += skor * bobot
    return round(total, 1)


def get_label_skor(skor: float) -> str:
    if skor >= 8.0:
        return "Sangat Sehat"
    if skor >= 6.0:
        return "Cukup Sehat"
    if skor >= 4.0:
        return "Perlu Perhatian"
    return "Kritis"


def skor_from_payload_dimensi(dimensi: dict[str, dict[str, Any]]) -> dict[str, float]:
    """Compute per-dimension scores from `JobPayload.dimensi` as dicts."""
    return {name: hitung_skor_dimensi(block) for name, block in dimensi.items()}
