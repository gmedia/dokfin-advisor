"""Unit tests for deterministic scoring (PRD section 7)."""

from __future__ import annotations

from advisor.schemas.input import IndikatorStatus
from advisor.scoring import (
    BOBOT_DIMENSI,
    get_label_skor,
    hitung_skor_dimensi,
    hitung_skor_keseluruhan,
    skor_from_payload_dimensi,
    status_agregat_dimensi_dari_skor,
    trend_dan_delta_skor_keseluruhan,
)


def test_hitung_skor_dimensi_skips_data_tidak_tersedia() -> None:
    d = {
        "A": {"status": "SEHAT"},
        "B": {"status": "DATA_TIDAK_TERSEDIA"},
        "C": {"status": "KRITIS"},
    }
    # (10 + 2) / 2 = 6.0
    assert hitung_skor_dimensi(d) == 6.0


def test_hitung_skor_dimensi_all_unavailable_defaults_neutral() -> None:
    d = {
        "A": {"status": "DATA_TIDAK_TERSEDIA"},
        "B": {"status": "DATA_TIDAK_TERSEDIA"},
    }
    assert hitung_skor_dimensi(d) == 5.0


def test_hitung_skor_keseluruhan_rounding() -> None:
    skor_per_dimensi = {k: 8.0 for k in BOBOT_DIMENSI}
    assert hitung_skor_keseluruhan(skor_per_dimensi) == 8.0

    skor_per_dimensi = {k: 7.33 for k in BOBOT_DIMENSI}
    out = hitung_skor_keseluruhan(skor_per_dimensi)
    assert out == round(sum(7.33 * BOBOT_DIMENSI[k] for k in BOBOT_DIMENSI), 1)


def test_get_label_skor_buckets() -> None:
    assert get_label_skor(8.0) == "Sangat Sehat"
    assert get_label_skor(7.9) == "Cukup Sehat"
    assert get_label_skor(6.0) == "Cukup Sehat"
    assert get_label_skor(4.0) == "Perlu Perhatian"
    assert get_label_skor(3.9) == "Kritis"


def test_status_agregat_dimensi_dari_skor_buckets() -> None:
    assert status_agregat_dimensi_dari_skor(8.0) == IndikatorStatus.SEHAT
    assert status_agregat_dimensi_dari_skor(7.9) == IndikatorStatus.PERLU_PERHATIAN
    assert status_agregat_dimensi_dari_skor(4.0) == IndikatorStatus.PERLU_PERHATIAN
    assert status_agregat_dimensi_dari_skor(3.9) == IndikatorStatus.KRITIS


def test_trend_dan_delta_skor_keseluruhan() -> None:
    assert trend_dan_delta_skor_keseluruhan(7.0, None) == ("tidak_tersedia", None)
    assert trend_dan_delta_skor_keseluruhan(7.0, 6.0)[0] == "naik"
    assert trend_dan_delta_skor_keseluruhan(6.0, 7.0)[0] == "turun"
    t, d = trend_dan_delta_skor_keseluruhan(6.0, 6.02, epsilon=0.05)
    assert t == "stabil" and d == -0.02


def test_skor_from_payload_dimensi() -> None:
    dimensi = {
        "likuiditas": {"KES_01": {"status": "SEHAT"}},
        "profitabilitas": {"PRO_01": {"status": "TURUN"}},
        "efisiensi": {"EFI_01": {"status": "KRITIS"}},
        "solvabilitas": {"SOL_01": {"status": "PERLU_PERHATIAN"}},
        "sdm": {"SDM_01": {"status": "ON_TRACK"}},
        "kepatuhan": {"PAT_01": {"status": "DATA_TIDAK_TERSEDIA"}},
    }
    out = skor_from_payload_dimensi(dimensi)
    assert out["likuiditas"] == 10.0
    assert out["profitabilitas"] == 4.0
    assert out["efisiensi"] == 2.0
    assert out["solvabilitas"] == 6.0
    assert out["sdm"] == 8.0
    assert out["kepatuhan"] == 5.0
