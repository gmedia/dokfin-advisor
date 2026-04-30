"""Deterministic scoring (PRD section 7). LLM must not compute scores."""

from __future__ import annotations

from typing import Any

from advisor.schemas.input import IndikatorStatus

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


def status_agregat_dimensi_dari_skor(skor: float) -> IndikatorStatus:
    """Status blok dimensi di hasil publik dari skor agregat (ambang PRD 7.4, enum output)."""
    s = round(float(skor) * 10) / 10
    if s >= 8.0:
        return IndikatorStatus.SEHAT
    if s >= 4.0:
        return IndikatorStatus.PERLU_PERHATIAN
    return IndikatorStatus.KRITIS


def trend_dan_delta_skor_keseluruhan(
    skor_sekarang: float,
    skor_periode_sebelumnya: float | None,
    *,
    epsilon: float = 0.05,
) -> tuple[str, float | None]:
    """Trend dan selisih skor keseluruhan; tanpa data periode sebelumnya → tidak_tersedia / None."""
    if skor_periode_sebelumnya is None:
        return "tidak_tersedia", None
    delta = round(float(skor_sekarang) - float(skor_periode_sebelumnya), 2)
    if delta > epsilon:
        return "naik", delta
    if delta < -epsilon:
        return "turun", delta
    return "stabil", delta


def skor_from_payload_dimensi(dimensi: dict[str, dict[str, Any]]) -> dict[str, float]:
    """Compute per-dimension scores from `JobPayload.dimensi` as dicts."""
    return {name: hitung_skor_dimensi(block) for name, block in dimensi.items()}
