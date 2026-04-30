"""Merge deterministic scores/status into LLM JSON before Node D (PRD: skor dari Python)."""

from __future__ import annotations

import math
from copy import deepcopy
from typing import Any

from advisor.schemas.input import JobPayload
from advisor.scoring import get_label_skor

# Urutan "terburuk" untuk memilih status agregat per dimensi (PRD-style).
_STATUS_RANK: dict[str, int] = {
    "KRITIS": 5,
    "PERLU_PERHATIAN": 4,
    "TURUN": 3,
    "ON_TRACK": 2,
    "SEHAT": 1,
    "DATA_TIDAK_TERSEDIA": 0,
}


def worst_status_in_dimensi(block: dict[str, Any]) -> str:
    present: set[str] = set()
    for row in block.values():
        if not isinstance(row, dict):
            continue
        st = row.get("status")
        if st is None:
            continue
        present.add(str(getattr(st, "value", st)))
    for status in sorted(_STATUS_RANK.keys(), key=lambda s: _STATUS_RANK[s], reverse=True):
        if status in present:
            return status
    return "SEHAT"


def merge_deterministic_into_raw(
    *,
    payload: JobPayload,
    skor_per_dimensi: dict[str, float],
    skor_keseluruhan: float,
    raw: dict[str, Any],
) -> dict[str, Any]:
    """Return a new dict: LLM narrative preserved where possible; skor/status overwritten."""
    out = deepcopy(raw)
    dim_payload = payload.dimensi.model_dump(mode="json")
    job_id_str = str(payload.job_id)

    out["job_id"] = job_id_str
    out["status"] = "DONE"

    skor_k = out.get("skor_keseluruhan")
    if not isinstance(skor_k, dict):
        skor_k = {}
    label = get_label_skor(skor_keseluruhan)
    skor_k["nilai"] = float(skor_keseluruhan)
    skor_k["label"] = label
    if "trend" not in skor_k or not skor_k.get("trend"):
        skor_k["trend"] = "datar"
    vpl = skor_k.get("vs_periode_lalu")
    if vpl is None or (isinstance(vpl, float) and math.isnan(vpl)):
        skor_k["vs_periode_lalu"] = 0.0
    out["skor_keseluruhan"] = skor_k

    dim_out = out.get("dimensi")
    if not isinstance(dim_out, dict):
        dim_out = {}

    for key in ("likuiditas", "profitabilitas", "efisiensi", "solvabilitas", "sdm", "kepatuhan"):
        block = dim_payload.get(key) or {}
        st = worst_status_in_dimensi(block if isinstance(block, dict) else {})
        sk = float(skor_per_dimensi.get(key, 5.0))
        sk_rounded = round(sk * 10) / 10
        row = dim_out.get(key)
        if not isinstance(row, dict):
            row = {"narasi": "", "saran": []}
        row["skor"] = sk_rounded
        row["status"] = st
        if "narasi" not in row:
            row["narasi"] = ""
        if "saran" not in row or not isinstance(row["saran"], list):
            row["saran"] = []
        dim_out[key] = row

    out["dimensi"] = dim_out

    recs = out.get("rekomendasi_prioritas")
    if not isinstance(recs, list):
        recs = []
    recs = _normalize_rekomendasi(recs)
    out["rekomendasi_prioritas"] = recs

    kp = out.get("konteks_pasar")
    if not isinstance(kp, list):
        out["konteks_pasar"] = []

    return out


def _normalize_rekomendasi(recs: list[Any]) -> list[dict[str, Any]]:
    labels = ["SEGERA", "BULAN_INI", "PELUANG"]
    out: list[dict[str, Any]] = []
    for i, label in enumerate(labels):
        if i < len(recs) and isinstance(recs[i], dict):
            r = dict(recs[i])
            r.setdefault("prioritas", i + 1)
            r["label"] = label
            r.setdefault("aksi", "Tinjau prioritas keuangan")
            r.setdefault("detail", "Sesuaikan dengan kondisi usaha saat ini.")
            r.setdefault("estimasi_dampak", "Mengurangi risiko operasional.")
            out.append(r)
        else:
            out.append(
                {
                    "prioritas": i + 1,
                    "label": label,
                    "aksi": "Tinjau prioritas keuangan",
                    "detail": "Diskusikan langkah konkret dengan tim atau mentor bisnis.",
                    "estimasi_dampak": "Memperjelas fokus perbaikan dalam 2–4 minggu.",
                }
            )
    return out[:3]
