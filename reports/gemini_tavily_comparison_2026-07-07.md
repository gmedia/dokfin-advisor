# Komparasi Gemini + Tavily

Tanggal run: 2026-07-07  
Fixture: `tests/fixtures/payload_reality.json`  
Mode search: `SEARCH_MAX_QUERIES=1`, `SEARCH_QUERY_SELECTION_MODE=best`, enhancement off  
Kurs: USD 1 = Rp 17.982,00

## Asumsi Harga

| Item | Input / 1M token | Output / 1M token | Catatan |
| --- | ---: | ---: | --- |
| Gemini 3.1 Pro Preview | USD 2,00 | USD 12,00 | Tarif prompt <= 200k token |
| Gemini 3.5 Flash | USD 1,50 | USD 9,00 | Tarif paid tier standard |
| Tavily basic search | - | - | Diasumsikan 1 request = 1 credit = USD 0,008 |

Biaya LLM dihitung dari total input token Node A + Node C dan total output token Node A + Node C.
Biaya Tavily ditambahkan manual karena `estimated_cost_idr` dari aplikasi hanya menghitung token LLM.

## Ringkasan Utama

| Variant | Tavily | Status | Total Token | Input Token | Output Token | Waktu App | Biaya LLM | Biaya Tavily | Total Biaya |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Gemini 3.1 Pro Preview | Ya | DONE | 14.543 | 6.563 | 7.980 | 68,794s | USD 0,108886 / Rp 1.957,99 | USD 0,008000 / Rp 143,86 | USD 0,116886 / Rp 2.101,84 |
| Gemini 3.1 Pro Preview | Tidak | DONE | 15.510 | 6.563 | 8.947 | 63,378s | USD 0,120490 / Rp 2.166,65 | USD 0 / Rp 0 | USD 0,120490 / Rp 2.166,65 |
| Gemini 3.5 Flash | Ya | DONE | 14.009 | 6.561 | 7.448 | 37,835s | USD 0,076873 / Rp 1.382,34 | USD 0,008000 / Rp 143,86 | USD 0,084873 / Rp 1.526,20 |
| Gemini 3.5 Flash | Tidak | DONE | 14.803 | 6.561 | 8.242 | 40,463s | USD 0,084019 / Rp 1.510,84 | USD 0 / Rp 0 | USD 0,084019 / Rp 1.510,84 |

## Detail Token

| Variant | Node A Input | Node A Output | Node C Input | Node C Output | Total |
| --- | ---: | ---: | ---: | ---: | ---: |
| Gemini 3.1 Pro + Tavily | 1.202 | 1.746 | 5.361 | 6.234 | 14.543 |
| Gemini 3.1 Pro tanpa Tavily | 1.202 | 1.684 | 5.361 | 7.263 | 15.510 |
| Gemini 3.5 Flash + Tavily | 1.202 | 2.294 | 5.359 | 5.154 | 14.009 |
| Gemini 3.5 Flash tanpa Tavily | 1.202 | 2.294 | 5.359 | 5.948 | 14.803 |

## Detail Waktu

| Variant | Node A | Node B | Node C | Node D | Processing Time | Wall Time |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Gemini 3.1 Pro + Tavily | 16,751s | 2,693s | 49,334s | 0,000s | 68,794s | 69,535s |
| Gemini 3.1 Pro tanpa Tavily | 13,710s | 0,000s | 49,657s | 0,000s | 63,378s | 63,445s |
| Gemini 3.5 Flash + Tavily | 11,022s | 1,897s | 24,904s | 0,000s | 37,835s | 37,906s |
| Gemini 3.5 Flash tanpa Tavily | 11,216s | 0,000s | 29,236s | 0,000s | 40,463s | 40,531s |

## Detail Tavily

| Variant | Search Query | Raw Count | Picked Context | Market Sources | Credit |
| --- | --- | ---: | ---: | --- | ---: |
| Gemini 3.1 Pro + Tavily | `tren penjualan f&b retail yogyakarta q1 2026` | 1 | 0 | Tidak ada | 1 |
| Gemini 3.1 Pro tanpa Tavily | - | 0 | 0 | Tidak ada | 0 |
| Gemini 3.5 Flash + Tavily | `tren penjualan f&b retail yogyakarta maret 2026` | 1 | 0 | Tidak ada | 1 |
| Gemini 3.5 Flash tanpa Tavily | - | 0 | 0 | Tidak ada | 0 |

Catatan: Tavily berhasil dipanggil pada dua variant, tetapi hasil mentah tidak lolos filter/ranking akhir sehingga `konteks_pasar` tetap kosong. Jadi pada run ini Tavily menambah latency dan biaya credit, tetapi tidak menambah konteks pasar ke output final.

## Ringkasan Response

| Variant | Skor | Label | Ringkasan Eksekutif | Rekomendasi Prioritas |
| --- | ---: | --- | --- | --- |
| Gemini 3.1 Pro + Tavily | 7,0 | Cukup Sehat | Usaha restoran masih cukup baik, tapi penjualan turun 12,6% membuat kas mepet untuk bayar hutang jangka pendek. | Negosiasi ulang jadwal bayar tagihan; kejar kekurangan target penjualan; pertahankan sistem pencatatan stok dan kas. |
| Gemini 3.1 Pro tanpa Tavily | 7,0 | Cukup Sehat | Kondisi cukup stabil, keuntungan kotor bagus, tetapi kas tergerus karena target penjualan tidak tercapai dan tagihan menumpuk. | Kejar tagihan pelanggan horeka; bagi target penjualan menjadi target harian; buat jadwal cek stok bumbu dan kemasan. |
| Gemini 3.5 Flash + Tavily | 7,0 | Cukup Sehat | Stok efisien dan pencatatan rapi, tetapi kas jangka pendek mepet karena target penjualan kurang Rp 25,32 juta dan hutang jatuh tempo Rp 28 juta. | Amankan dana Rp 28 juta; kejar kekurangan target penjualan Rp 25,32 juta; manfaatkan efisiensi stok untuk kurangi biaya pembelian. |
| Gemini 3.5 Flash tanpa Tavily | 7,0 | Cukup Sehat | Bisnis cukup sehat, tetapi aset lancar tidak cukup untuk hutang jangka pendek dan kegagalan target penjualan memicu tekanan kas. | Negosiasi jatuh tempo hutang Rp 28 juta; kejar piutang horeka Rp 12 juta; buat program loyalitas pelanggan. |

## File Output

| Variant | Raw output |
| --- | --- |
| Gemini 3.1 Pro + Tavily | `reports/raw/gemini_3_1_pro_preview__with_tavily.json` |
| Gemini 3.1 Pro tanpa Tavily | `reports/raw/gemini_3_1_pro_preview__no_tavily.json` |
| Gemini 3.5 Flash + Tavily | `reports/raw/gemini_3_5_flash__with_tavily.json` |
| Gemini 3.5 Flash tanpa Tavily | `reports/raw/gemini_3_5_flash__no_tavily.json` |
| Summary JSON | `reports/gemini_tavily_comparison_2026-07-07.json` |

## Kesimpulan

1. Gemini 3.5 Flash jauh lebih cepat dari Gemini 3.1 Pro pada fixture ini.
   - Dengan Tavily: 37,835s vs 68,794s.
   - Tanpa Tavily: 40,463s vs 63,378s.

2. Gemini 3.5 Flash juga lebih murah pada semua variant.
   - Flash + Tavily: Rp 1.526,20 total.
   - Pro + Tavily: Rp 2.101,84 total.
   - Flash tanpa Tavily: Rp 1.510,84 total.
   - Pro tanpa Tavily: Rp 2.166,65 total.

3. Tavily pada run ini tidak memberi konteks pasar final karena hasil search tidak lolos filter.
   - Biaya tambahannya kecil: sekitar Rp 143,86 per 1 query.
   - Latency tambahannya sekitar 1,9-2,7 detik.
   - Karena `konteks_pasar` kosong di semua variant, kualitas response lebih banyak ditentukan oleh payload internal.

4. Untuk baseline production murah dan cepat, Gemini 3.5 Flash tanpa Tavily terlihat paling efisien pada run ini.
   Namun kalau ingin tetap memberi peluang konteks pasar saat query bagus, Gemini 3.5 Flash + Tavily masih masuk akal karena totalnya hanya naik sekitar Rp 15,36 dibanding Flash tanpa Tavily pada run ini. Selisih kecil ini terjadi karena output token Flash + Tavily lebih rendah, bukan karena Tavily mengurangi harga LLM secara langsung.

5. Untuk eksperimen berikutnya, perlu test dengan payload dari industri non-F&B dan query yang lebih umum agar Tavily punya peluang menghasilkan `konteks_pasar` yang lolos filter.
