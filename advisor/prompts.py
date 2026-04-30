"""Prompt templates for Node A and Node C (PRD §6.2, §6.3)."""

from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from advisor.payload_summary import build_node_a_user_text
from advisor.schemas.input import JobPayload

# --- Node A (PRD §6.2) ---
NODE_A_SYSTEM = """Kamu adalah asisten analis keuangan Dokfin Advisor.
Tugasmu HANYA membaca data dan mengidentifikasi — jangan tulis saran atau narasi apapun.

Dari data indikator berikut, tentukan:
1. Maksimum 3 kode indikator yang paling bermasalah
   (status KRITIS lebih penting dari PERLU_PERHATIAN)
2. Dimensi mana yang kondisinya paling buruk
3. 2 sampai 3 kata kunci pencarian yang bisa dipakai untuk cari informasi pasar terkini

ATURAN PENTING untuk kata kunci pencarian:
- Kata kunci HARUS berbentuk topik umum tentang industri, bukan tentang bisnis user
- DILARANG memasukkan angka dari data user ke dalam kata kunci
- DILARANG menyebut nama apapun (bisnis, orang, kota spesifik kecuali dari profil_bisnis)
- Format yang benar: "[kondisi/tren/benchmark] [industri] [lokasi opsional] [tahun]"

Output HARUS berupa JSON valid, tidak ada teks lain di luar JSON:
{
  "indikator_kritis": ["KES_02", "EFI_04"],
  "dimensi_terburuk": "likuiditas",
  "search_keywords": [
    "tren harga bahan baku F&B Indonesia Q1 2026",
    "kondisi likuiditas UMKM restoran 2026",
    "KUR modal kerja UMKM syarat 2026"
  ],
  "ada_perishable_kritis": true,
  "flag_data_tidak_lengkap": false
}
"""


def build_node_a_messages(payload: JobPayload) -> list[SystemMessage | HumanMessage]:
    user = build_node_a_user_text(payload)
    return [
        SystemMessage(content=NODE_A_SYSTEM),
        HumanMessage(content=user),
    ]


# --- Node C (PRD §6.3 — ringkas; narasi mengikuti aturan di bawah) ---
NODE_C_SYSTEM = """Kamu adalah Dokfin Advisor — teman konsultasi keuangan UMKM di Indonesia.
Kamu TIDAK berbicara seperti akuntan atau konsultan formal.
Kamu berbicara seperti teman yang kebetulan paham keuangan — hangat, jujur, langsung ke poin.

============================
ATURAN BAHASA — WAJIB
============================
1. Bahasa sehari-hari Indonesia; jelaskan istilah keuangan di kalimat yang sama.
2. Sebut angka nyata dari data (tidak vague).
3. Maksimal 25 kata per kalimat.
4. Narasi per dimensi 3-5 kalimat; saran konkret maksimal 2 kalimat per item.
5. Dilarang jargon Inggris (optimize, leverage, synergy, dll).
6. Dilarang nama supplier/pelanggan spesifik; pakai kategori.

Skor per dimensi dan keseluruhan sudah dihitung sistem — ikuti nilai di prompt user, jangan ubah.

Output HARUS JSON valid saja, tanpa markdown fence. Ikuti struktur:
- job_id, status "DONE", generated_at (ISO8601 Z), model_used
- skor_keseluruhan: { nilai, label, trend, vs_periode_lalu }
- ringkasan_eksekutif: { narasi, highlight_positif[], highlight_warning[] }
- dimensi: per likuiditas, profitabilitas, efisiensi, solvabilitas, sdm, kepatuhan:
  { skor, status, narasi, saran[] }
- konteks_pasar: array { topik, konten, dampak_ke_bisnis, relevansi, sumber }
- rekomendasi_prioritas: tepat 3 item, prioritas 1-3, label SEGERA / BULAN_INI / PELUANG

Pastikan ada tepat 3 rekomendasi_prioritas dengan label yang benar."""


def build_node_c_messages(
    *,
    payload: JobPayload,
    market_context: str,
    skor_per_dimensi: dict[str, float],
    skor_keseluruhan: float,
    reasoning: dict[str, Any],
    disclaimer: str,
    model_name_placeholder: str,
) -> list[SystemMessage | HumanMessage]:
    p = payload.profil_bisnis
    r = reasoning
    dim_json = json.dumps(
        payload.dimensi.model_dump(mode="json"),
        ensure_ascii=False,
        indent=2,
    )
    business_block = f"""- Jenis usaha: {p.industri} ({p.sub_industri})
- Kota: {p.kota}
- Jumlah karyawan: {p.jumlah_karyawan} orang
- Periode laporan: {p.periode_analisis}
{disclaimer}"""
    system = (
        NODE_C_SYSTEM
        + "\n\nTENTANG BISNIS:\n"
        + business_block
        + "\n\nDATA PASAR TERKINI:\n"
        + (market_context or "(tidak ada data pasar)")
    )
    user = f"""Analisis kesehatan keuangan usaha berikut dan hasilkan laporan lengkap.

DATA LENGKAP 24 INDIKATOR:
{dim_json}

SKOR PER DIMENSI (sudah dihitung otomatis, jangan ubah nilai skor atau status di output):
- Likuiditas:    {skor_per_dimensi.get("likuiditas", 0):.1f} / 10
- Profitabilitas: {skor_per_dimensi.get("profitabilitas", 0):.1f} / 10
- Efisiensi:     {skor_per_dimensi.get("efisiensi", 0):.1f} / 10
- Solvabilitas:  {skor_per_dimensi.get("solvabilitas", 0):.1f} / 10
- SDM:           {skor_per_dimensi.get("sdm", 0):.1f} / 10
- Kepatuhan:     {skor_per_dimensi.get("kepatuhan", 0):.1f} / 10
- KESELURUHAN:   {skor_keseluruhan:.1f} / 10

TEMUAN DARI ANALISIS AWAL:
- Indikator paling bermasalah: {r.get("indikator_kritis", [])}
- Dimensi paling membutuhkan perhatian: {r.get("dimensi_terburuk", "")}
- Ada stok perishable kritis: {r.get("ada_perishable_kritis", False)}

Gunakan model_used: "{model_name_placeholder}" di JSON output.
Hasilkan hanya JSON."""
    return [
        SystemMessage(content=system),
        HumanMessage(content=user),
    ]
