"""Merge deterministic scores/status into LLM JSON before Node D (PRD: skor dari Python)."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from advisor.schemas.input import JobPayload
from advisor.scoring import (
    get_label_skor,
    status_agregat_dimensi_dari_skor,
    trend_dan_delta_skor_keseluruhan,
)
from advisor.search_filters import hostname_from_url


def _normalize_sumber(s: str | None) -> str:
    if not s:
        return ""
    s2 = str(s).strip()
    if not s2:
        return ""
    if s2.startswith("http://") or s2.startswith("https://"):
        return hostname_from_url(s2)
    h = s2.lower()
    if h.startswith("www."):
        h = h[4:]
    return h


def _pick_forward_looking_saran(saran: list[str]) -> str:
    """Pick one suggestion deterministically; prefer forward-looking wording."""
    if not saran:
        return ""
    weights: list[tuple[int, str]] = [
        (3, "sop"),
        (3, "panduan"),
        (3, "prosedur"),
        (2, "audit"),
        (2, "pemeriksaan"),
        (2, "kredit"),
        (2, "bank"),
        (2, "pinjaman"),
        (2, "buka cabang"),
        (2, "ekspansi"),
    ]

    best_idx = 0
    best_score = -1
    for i, text in enumerate(saran):
        t = str(text).lower()
        score = 0
        for w, kw in weights:
            if kw in t:
                score += w
        if score > best_score:
            best_score = score
            best_idx = i
    if best_score <= 0:
        return str(saran[0])
    return str(saran[best_idx])


def merge_konteks_pasar_transparency(
    out: dict[str, Any],
    seed: list[dict[str, Any]] | None,
) -> None:
    """Isi / perkaya konteks_pasar dengan sumber, tanggal akses, dan tanggal terbit."""
    if not seed:
        return
    kp = out.get("konteks_pasar")
    if not isinstance(kp, list):
        kp = []

    by_domain: dict[str, dict[str, Any]] = {}
    for s in seed:
        if not isinstance(s, dict):
            continue
        dom = _normalize_sumber(str(s.get("sumber") or ""))
        if dom:
            by_domain[dom] = s

    if not kp:
        out["konteks_pasar"] = [dict(x) for x in seed if isinstance(x, dict)]
        return

    def _looks_like_hostname(value: str) -> bool:
        v = (value or "").strip().lower()
        # Heuristik: hostname biasanya mengandung titik dan tidak mengandung spasi.
        return bool(v) and "." in v and " " not in v

    for item in kp:
        if not isinstance(item, dict):
            continue
        raw_src = str(item.get("sumber") or "")
        dom = _normalize_sumber(raw_src)
        src = by_domain.get(dom) if dom else None
        if src:
            if not item.get("diakses_pada") and src.get("diakses_pada"):
                item["diakses_pada"] = src["diakses_pada"]
            if not item.get("sumber") and src.get("sumber"):
                item["sumber"] = src["sumber"]
        else:
            # Jika LLM mengisi `sumber` bukan hostname (mis. judul laporan),
            # lebih aman untuk transparansi: pakai seed Node B apa adanya.
            if raw_src and not _looks_like_hostname(raw_src):
                out["konteks_pasar"] = [dict(x) for x in seed if isinstance(x, dict)]
                return


def merge_deterministic_into_raw(
    *,
    payload: JobPayload,
    skor_per_dimensi: dict[str, float],
    skor_keseluruhan: float,
    raw: dict[str, Any],
    konteks_pasar_seed: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return a new dict: LLM narrative preserved where possible; skor/status overwritten."""
    out = deepcopy(raw)
    job_id_str = str(payload.job_id)

    out["job_id"] = job_id_str
    out["status"] = "DONE"

    skor_k = out.get("skor_keseluruhan")
    if not isinstance(skor_k, dict):
        skor_k = {}
    label = get_label_skor(skor_keseluruhan)
    skor_k["nilai"] = float(skor_keseluruhan)
    skor_k["label"] = label
    prev_skor = payload.profil_bisnis.skor_keseluruhan_periode_sebelumnya
    trend, delta = trend_dan_delta_skor_keseluruhan(skor_keseluruhan, prev_skor)
    skor_k["trend"] = trend
    skor_k["vs_periode_lalu"] = delta
    out["skor_keseluruhan"] = skor_k

    dim_out = out.get("dimensi")
    if not isinstance(dim_out, dict):
        dim_out = {}

    for key in ("likuiditas", "profitabilitas", "efisiensi", "solvabilitas", "sdm", "kepatuhan"):
        sk = float(skor_per_dimensi.get(key, 5.0))
        sk_rounded = round(sk * 10) / 10
        st = status_agregat_dimensi_dari_skor(sk_rounded)
        row = dim_out.get(key)
        if not isinstance(row, dict):
            row = {"narasi": "", "saran": []}
        row["skor"] = sk_rounded
        row["status"] = st.value
        if "narasi" not in row:
            row["narasi"] = ""
        if "saran" not in row or not isinstance(row["saran"], list):
            row["saran"] = []
        # Kepatuhan skor sempurna: cukup 1 saran proaktif (bukan checklist basic).
        if key == "kepatuhan" and row["status"] == "SEHAT" and float(row["skor"]) >= 10.0:
            saran = [str(x) for x in row["saran"] if str(x).strip()]
            if len(saran) > 1:
                row["saran"] = [_pick_forward_looking_saran(saran)]
            else:
                row["saran"] = saran
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
    # Jika Node B tidak menghasilkan seed (mis. filter terlalu ketat / Tavily gagal),
    # jangan biarkan LLM mengarang konteks pasar (PRD: fallback boleh kosong).
    if not konteks_pasar_seed:
        out["konteks_pasar"] = []

    merge_konteks_pasar_transparency(out, konteks_pasar_seed)

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
