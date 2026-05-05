# Contributing

Terima kasih telah tertarik berkontribusi ke Dokfin Advisor!

## Cara berkontribusi

1. Fork repo ini
2. Buat branch baru dari `main`: `git checkout -b feat/nama-fitur`
3. Buat perubahan dan pastikan test + lint lolos:
   ```bash
   uv run ruff check .
   uv run ruff format .
   uv run pytest
   ```
4. Commit dengan pesan yang jelas
5. Buat Pull Request ke branch `main`

## Panduan kode

- Ikuti konvensi yang sudah ada (type hints, docstring, Pydantic schema)
- Semua perubahan pada schema atau alur A→B→C→D harus tercermin di `PRD.md`
- Scoring harus deterministik — tidak boleh bergantung pada LLM
- Jaga agar keyword Tavily tidak memuat data spesifik user (angka, nama)

## Melaporkan bug

Gunakan [GitHub Issues](https://github.com/GMEDIA/dokfin-advisor/issues) dengan template **Bug report**.

## Lisensi

Dengan berkontribusi, kamu setuju bahwa kontribusimu dilisensikan di bawah [MIT License](../LICENSE).
