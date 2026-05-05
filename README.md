# Dokfin Advisor

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/)

Layanan AI untuk analisis kesehatan keuangan UMKM. Memproses data keuangan bisnis melalui pipeline LangGraph (Node A–D) dan menghasilkan laporan berstruktur dengan skor, narasi, konteks pasar terkini, serta rekomendasi yang actionable.

**Production deployment** dikelola secara internal di GitLab. Repo ini adalah versi open source untuk komunitas.

## Arsitektur pipeline

```text
Payload keuangan → [Node A] Identifikasi masalah & keyword
                 → [Node B] Pencarian konteks pasar (Tavily, Indonesia-first)
                 → [Node C] Sintesis laporan JSON (LLM)
                 → [Node D] Validasi + merge skor deterministik
                 → Result DONE / FAILED
```

- **Node A & C**: LLM (OpenAI atau Google Gemini), output JSON ketat
- **Node B**: Tavily search dengan strategi Indonesia-first (`topic=general`, `country=indonesia`)
- **Node D**: Validasi Pydantic + scoring deterministik Python (tidak pakai LLM)
- **Worker opsional**: NATS JetStream pull consumer dengan idempotensi Redis

## Prasyarat

- Python **3.12+**
- [uv](https://docs.astral.sh/uv/) untuk dependency dan virtualenv
- API key: **LLM** (OpenAI atau Google) + **Tavily** untuk pencarian pasar

Opsional: Docker + Docker Compose untuk NATS, Redis, dan container advisor.

## Setup cepat

```bash
uv sync
cp .env.example .env
# Wajib: isi LLM_PROVIDER, OPENAI_API_KEY atau GOOGLE_API_KEY, dan TAVILY_API_KEY
```

## Menjalankan tes dan lint

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

## Mode aplikasi

- **Tanpa `NATS_URL`:** `python main.py` atau `uv run dokfin-advisor` menjalankan demo bootstrap.
- **Dengan `NATS_URL`:** process menjalankan [`advisor/nats_worker.py`](advisor/nats_worker.py) — konsumsi subject `bhc.jobs`, publish ke `bhc.results`, DLQ ke `bhc.dlq`. Nama stream JetStream tidak boleh mengandung titik (lihat `.env.example`).

## Docker Compose

```bash
docker compose up --build
```

Service `advisor` memakai `NATS_URL=nats://nats:4222` dan `REDIS_URL=redis://redis:6379/0` dari [`docker-compose.yml`](docker-compose.yml). Jangan commit `.env` berisi kunci API ke repo.

## Konfigurasi

Lihat [`.env.example`](.env.example) untuk daftar lengkap. Ringkasan:

| Area | Variabel utama |
|------|---------------|
| LLM | `LLM_PROVIDER`, `OPENAI_API_KEY` / `GOOGLE_API_KEY`, `*_MODEL_*` |
| Tavily | `TAVILY_API_KEY`, `TAVILY_FETCH_MAX_RESULTS`, `TAVILY_MIN_RELEVANCE` |
| NATS | `NATS_URL`, `NATS_STREAM_*`, `NATS_SUBJECT_*`, `ADVISOR_MAX_CONCURRENCY` |
| Idempotensi | `REDIS_URL`, `ADVISOR_IDEMPOTENCY_*` |
| Estimasi biaya | `OPENAI_PRICE_*_PER_M_IDR` / `GOOGLE_PRICE_*_PER_M_IDR` |

## Contoh payload & kontrak hasil

- Payload contoh: [`tests/fixtures/payload_sample.json`](tests/fixtures/payload_sample.json)
- Schema input/output: [`advisor/schemas/`](advisor/schemas/)
- Spesifikasi lengkap: [`PRD.md`](PRD.md)

## Kontribusi

Lihat [`.github/CONTRIBUTING.md`](.github/CONTRIBUTING.md).

## Lisensi

[MIT](LICENSE) — Copyright © 2026 PT Media Sarana Data (GMEDIA)

