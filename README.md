# Dokfin Advisor

Layanan Python yang memproses job kesehatan keuangan UMKM lewat pipeline LangGraph (Node A–D), dengan opsi worker NATS JetStream.

## Prasyarat

- Python **3.12+**
- [uv](https://docs.astral.sh/uv/) untuk dependency dan virtualenv

Opsional: Docker + Docker Compose untuk NATS, Redis, dan container advisor.

## Setup cepat

```bash
uv sync
cp .env.example .env
# Isi OPENAI_API_KEY; untuk worker NATS set NATS_URL; untuk idempotensi set REDIS_URL
```

## Menjalankan tes dan lint

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

## Mode aplikasi

- **Tanpa `NATS_URL`:** `python main.py` atau `uv run dokfin-advisor` hanya melakukan startup demo (log + timing bootstrap).
- **Dengan `NATS_URL`:** process menjalankan [`advisor/nats_worker.py`](advisor/nats_worker.py) — konsumsi subject `bhc.jobs`, publish ke `bhc.results`, DLQ ke `bhc.dlq` bila perlu. Nama **stream** JetStream tidak boleh mengandung titik (lihat `.env.example`); **subject** tetap `bhc.jobs`, dll.

## Docker Compose

```bash
docker compose up --build
```

Service `advisor` memakai `NATS_URL=nats://nats:4222` dan `REDIS_URL=redis://redis:6379/0` dari override di [`docker-compose.yml`](docker-compose.yml). Sesuaikan secret di `.env` lokal; jangan commit `.env` berisi kunci API.

## Contoh payload & kontrak hasil

- Payload contoh: [`tests/fixtures/payload_sample.json`](tests/fixtures/payload_sample.json)

## Konfigurasi penting (ringkas)

| Area | Variabel (lihat `.env.example`) |
|------|--------------------------------|
| NATS | `NATS_URL`, `NATS_STREAM_*`, `NATS_SUBJECT_*`, `ADVISOR_MAX_CONCURRENCY` |
| LLM | `OPENAI_*` atau `LLM_PROVIDER=google` + `GOOGLE_API_KEY`, `GOOGLE_MODEL_*` |
| Biaya estimasi | `OPENAI_PRICE_*_PER_M_IDR` atau `GOOGLE_PRICE_*_PER_M_IDR` (perkiraan) |
| Tavily | `TAVILY_*`, `TAVILY_TOPIC=general`, `TAVILY_COUNTRY=indonesia`, `TAVILY_INCLUDE_RAW_CONTENT`, `TAVILY_DROP_UNDATED=1`, `TAVILY_ALLOW_SUBDOMAINS=0`, `TAVILY_MAX_AGE_DAYS_*`, `TAVILY_MIN_RELEVANCE`, `TAVILY_KONTEKS_PASAR_*` |
| Idempotensi | `REDIS_URL`, `ADVISOR_IDEMPOTENCY_*` |

Waktu pemrosesan banyak bergantung pada Node C (LLM); respons bisa puluhan detik — set ekspektasi di UI (indikator tahap / loading).

Untuk meningkatkan relevansi konteks pasar, disarankan mengaktifkan `TAVILY_DROP_UNDATED=1` agar artikel tanpa tanggal terbit tidak ikut terpilih.
Jika kamu ingin whitelist lebih ketat, set `TAVILY_ALLOW_SUBDOMAINS=0` agar hanya domain persis yang lolos (subdomain ditolak kecuali di-allowlist eksplisit lewat `TAVILY_TRUSTED_DOMAINS`).
Untuk freshness sesuai tanggal run, gunakan `TAVILY_MAX_AGE_DAYS_PRIMARY=30`, `TAVILY_MAX_AGE_DAYS_FALLBACK=60`, dan fallback terakhir `TAVILY_MAX_AGE_DAYS_FALLBACK2=183` (≈ 6 bulan).
Untuk menghindari `konteks_pasar` berantakan/tidak relevan, sistem melakukan:
- Filter kualitas dokumen: hasil PDF dan konten mirip daftar isi/tabel dibuang.
- Filter relevansi deterministik berbasis profil bisnis (lihat `TAVILY_MIN_RELEVANCE=1.0`).
- Batas global: set `TAVILY_KONTEKS_PASAR_MIN_TOTAL=2` dan `TAVILY_KONTEKS_PASAR_MAX_TOTAL=3` agar hasil final 2–3 item total per run (bukan 6–9 item lintas keyword).

`TAVILY_MIN_KEEP` sekarang default 1 (per keyword) supaya fallback tidak agresif ketika relevansi rendah.
Jika metadata tanggal artikel kosong, sistem mencoba parse tanggal dari URL berita (mis. pola `/read/YYYYMMDD/`) agar artikel jadul tetap bisa difilter.

