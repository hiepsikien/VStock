# Chẩn đoán thời gian render bản dài (span audio)

> **Trạng thái**: đã đo trên máy dev ngày 2026-11-03. **P0-1 (vector hóa color bằng numpy) đã vào code trong PR này** và đã đo lại; các đề xuất còn lại (P0-2, P1, P2) **chưa** làm.
> **Phạm vi**: pipeline `plan_span` → `ensure_movement` → `_render_movement` cho `1W`, `1M`, `3M`, `1Y` ở phòng Replay.
> **Liên quan**: [`sonify-span-render-ahead-plan.md`](./sonify-span-render-ahead-plan.md) (hàng đợi prefetch), [`sonify-long-form.md`](./sonify-long-form.md) (form và độ dài chương).
> **Công cụ tái lập**: [`backend/scripts/bench_render.py`](../backend/scripts/bench_render.py).

Mục tiêu: biết thời gian thật của từng phase, xác định phase nào đáng tối ưu, và chọn thứ tự làm có bằng chứng thay vì đoán.

---

## 1. Kết luận ngắn

1. **MuseScore và tô màu (color) chiếm ~90%** thời gian render trước khi tối ưu. Phần soạn nhạc thật (compose, humanize, DFI, MusicXML) chỉ ~1–2%.
2. Một movement `1M` (221 nến, 263 s nhạc) mất **22,2 s**; trong đó MuseScore **10,5 s**, color **9,7 s**, encode AAC **1,8 s**.
3. Cả tác phẩm `1M` (4 movement, 16:04 nhạc) mất **86,7 s** khi cache lạnh. `1W` 31,4 s; `3M` 108,9 s; `1Y` 62,3 s (3 movement theo dữ liệu hiện tại).
4. **Color là vòng lặp Python trên từng sample**, tốn ~3,8–4,0% độ dài nhạc. Với `3M` (25:23 nhạc), color **60,9 s**, nhiều hơn cả MuseScore (35,6 s).
5. **Vector hóa color bằng numpy** đã vào code (P0-1): phase `color` trong bench 10,4 s → **0,51 s** cho cùng file 263 s, và file WAV **giống hệt từng byte** với bản cũ (cả float32 của MuseScore 4 lẫn int16 của MuseScore 3). Đây là win lớn nhất, ít rủi ro nhất.
6. **Batch MuseScore** (đã prototype, chưa vào code): 4 movement xuất trong **26,7 s** thay vì 41,0 s; movement 0 vẫn xong ~10,6 s, các movement sau ~5–6 s mỗi cái thay vì ~10–11 s.
7. **Đo lại sau P0-1**: `1W` **15,9 s**, `1M` **50,5 s**, `3M` **50,6 s**, `1Y` **36,1 s**; chương 0 của `1M` còn **13,1 s**. Sau P0-1 + batch (ước tính): `1M` còn **~30 s**, `3M` **~28 s**.
8. **Chương 0 là chờ bắt buộc**, không có file thì không có tiếng. Vì vậy ưu tiên UX là giảm chương 0 (P0-1); batch chủ yếu giảm tổng thời gian và chuẩn bị chương sau, không làm chương 0 nhanh hơn. Với chương 4–8 phút, chương 1+ có rất nhiều thời gian để render trong lúc nghe.
9. Sau P0-1, **MuseScore là phase lớn nhất** (70–82% thời gian render còn lại), encode AAC 12–20%, còn color chỉ 3–5%. Vì vậy P1-1 (batch) là bước tiếp theo đáng làm.


> Các số trên đo trên Apple M5 với MuseScore 4.7.6. Production là Ubuntu 24.04, MuseScore 3, VM 2 vCPU — phải đo lại trong container trước khi chốt ngưỡng. Xem mục 7.

---

## 2. Phương pháp đo

- Chạy đúng đường code production: `plan_span` → `RecapStore.ensure_movement` → `_render_movement` → `musescore_export` → `_color_for_export` → `waveform_peaks_with_level` → `_transcode_m4a`.
- Đo ở tầng service, không gồm HTTP/FileResponse (overhead vài ms) và không gồm thời gian chờ slot.
- Cache lạnh: mỗi lần đo dùng audio root mới (`--fresh`), không đọc file đã render.
- Một render tại một thời điểm, không có request tranh slot. Số đo **không** gồm thời gian chờ slot.
- Dữ liệu thật: ACB, SSI; `as_of` 2026-11-03; variant `guitar` (mặc định) và một mẫu `symphony`.
- Môi trường: macOS 26.6.2, Apple M5, MuseScore 4.7.6, ffmpeg, Python 3.11.15.
- Script in JSON từng movement; phase được wrap bằng `time.monotonic()`.

Lệnh tái lập:

```bash
cd backend
.venv/bin/python scripts/bench_render.py ACB 1W 0 --fresh
.venv/bin/python scripts/bench_render.py ACB 1M 0 1 2 3 --fresh
.venv/bin/python scripts/bench_render.py ACB 3M 0 1 2 --fresh
.venv/bin/python scripts/bench_render.py ACB 1Y 0 1 2 --fresh
.venv/bin/python scripts/bench_render.py ACB 1M 0 --variant symphony --fresh
```

---

## 3. Kết quả đo

### 3.1. Một movement `1M` (ACB, 221 nến, 263,0 s nhạc)

| Phase | Thời gian | Tỷ lệ |
|---|---:|---:|
| Lập kế hoạch / tải OHLC (`plan_span`) | 0,21 s | *ngoài render* |
| Soạn score (`_compose` → `render`) | 0,22 s | 1,0% |
| Humanize | 0,005 s | ~0% |
| DFI (`compute_dfi`) | 0,003 s | ~0% |
| Ghi MusicXML | 0,011 s | 0,05% |
| **MuseScore xuất WAV** | **10,48 s** | **47,3%** |
| **Tô màu preset (`apply_preset`)** | **9,65 s** | **43,5%** |
| Đo peaks | 0,014 s | 0,06% |
| **Nén AAC (`_transcode_m4a`)** | **1,78 s** | **8,0%** |
| Publish + đọc metadata | 0,003 s | ~0% |
| **Tổng render** | **22,17 s** | **100%** |

`renderRatio = 22,17 / 263,02 = 0,084`.

Mẫu `symphony` cùng movement: MuseScore **14,48 s**, color **10,37 s**, encode **1,78 s**, tổng **26,86 s**. Nhiều nhạc cụ hơn nên export chậm hơn ~4 s.

### 3.2. Toàn bộ tác phẩm (cold cache)

| Span | Movements | Độ dài nhạc | Plan | Render | End-to-end | Ratio |
|---|---:|---:|---:|---:|---:|---:|
| `1W` | 1 | 429,7 s (7:10) | 0,10 s | 31,30 s | **31,40 s** | 0,073 |
| `1M` | 4 | 964,1 s (16:04) | 0,22 s | 86,44 s | **86,66 s** | 0,090 |
| `3M` | 3 | 1522,9 s (25:23) | 0,10 s | 108,80 s | **108,90 s** | 0,072 |
| `1Y` | 3 | 683,8 s (11:24) | 0,07 s | 62,20 s | **62,27 s** | 0,091 |

`1Y` trong dữ liệu hiện tại chỉ có 3 movement; form 12 movement sẽ dài hơn tuyến tính theo số movement.

### 3.3. Tổng theo phase

| Phase | `1W` (1 mv) | `1M` (4 mv) | `3M` (3 mv) | `1Y` (3 mv) |
|---|---:|---:|---:|---:|
| Plan | 0,10 | 0,22 | 0,10 | 0,07 |
| Compose | 0,62 | 1,00 | 2,15 | 0,57 |
| Humanize | 0,02 | 0,03 | 0,06 | 0,02 |
| DFI | 0,01 | 0,02 | 0,04 | 0,01 |
| MusicXML | 0,03 | 0,07 | 0,13 | 0,05 |
| **MuseScore** | **11,52** | **40,96** | **35,58** | **29,47** |
| **Color** | **16,26** | **38,02** | **60,91** | **27,45** |
| Peaks | 0,02 | 0,05 | 0,08 | 0,04 |
| **Encode AAC** | **2,82** | **6,26** | **9,84** | **4,59** |
| **Tổng** | **31,40** | **86,66** | **108,90** | **62,27** |

`Tổng` ở bảng này là end-to-end, **gồm cả Plan**; cột `Render` ở mục 3.2 thì không gồm Plan.

Đọc bảng này theo hai câu:

- Với tác phẩm ngắn/nhiều movement (`1M`, `1Y`), **MuseScore chiếm gần một nửa** vì mỗi movement phải khởi động một process.
- Với tác phẩm dài (`3M`), **color chiếm hơn một nửa** vì nó tỷ lệ thuận với số giây nhạc.

### 3.4. Đo lại sau P0-1 (numpy color, đã vào code)

Cùng lệnh, cùng máy, cache lạnh, sau khi `apply_preset` chuyển sang numpy:

| Span | Movements | Render (trước) | Render (sau) | Tiết kiệm | Ratio sau |
|---|---:|---:|---:|---:|---:|
| `1W` | 1 | 31,30 s | **15,77 s** | −15,53 s | 0,037 |
| `1M` | 4 | 86,44 s | **50,29 s** | −36,15 s | 0,052 |
| `3M` | 3 | 108,80 s | **50,51 s** | −58,29 s | 0,033 |
| `1Y` | 3 | 62,20 s | **36,06 s** | −26,14 s | 0,053 |

Cộng `plan` (0,06–0,22 s) thì end-to-end là `1W` 15,9 s, `1M` 50,5 s, `3M` 50,6 s, `1Y` 36,1 s.

Tổng theo phase sau P0-1:

| Phase | `1W` (1 mv) | `1M` (4 mv) | `3M` (3 mv) | `1Y` (3 mv) |
|---|---:|---:|---:|---:|
| Compose | 0,63 | 1,01 | 2,12 | 0,54 |
| Humanize + DFI + MusicXML | 0,06 | 0,14 | 0,22 | 0,07 |
| **MuseScore** | **11,55** | **41,02** | **35,56** | **29,51** |
| **Color** | **0,69** | **1,75** | **2,56** | **1,28** |
| Peaks | 0,02 | 0,07 | 0,08 | 0,04 |
| **Encode AAC** | **2,81** | **6,28** | **9,95** | **4,62** |

Ba điều đổi sau P0-1:

- Color từ **38,02 s** xuống **1,75 s** ở `1M`, và từ **60,91 s** xuống **2,56 s** ở `3M`.
- Color không còn tỷ lệ theo "số giây nhạc" nữa: 0,5 s cho 263 s nhạc, 0,84 s cho 503 s nhạc. Phần còn lại là thời gian đọc/ghi file.
- **MuseScore giờ là phase lớn nhất** (70–82% tổng), rồi encode AAC (12–20%). Đây là lý do P1-1 (batch) là bước tiếp theo.

Kiểm chứng âm thanh: chạy `apply_preset` cũ và mới trên cùng file dry 263 s (float32, guitar), so sánh SHA-256 — **hai file giống hệt từng byte**, 9,708 s → 0,399 s. Số này thấp hơn phase `color` trong bench (10,4 → 0,51 s) vì `apply_preset` thuần không gồm phần đo peaks, publish và overhead của `ensure_movement`. Với int16 (MuseScore 3) cũng khớp từng sample, vì phép cộng giữ ở float64 rồi mới cắt về int16 giống `int()` trong vòng lặp cũ.


---

## 4. Phân tích từng phase

### 4.1. MuseScore (~9,5–12,5 s/movement, `symphony` ~14,5 s)

- Mỗi movement gọi `musescore_export` một lần; mỗi lần là một process mới (`subprocess` trong `_run_musescore`).
- Phần lớn là chi phí cố định: khởi động MuseScore, nạp score, khởi tạo synth, ghi WAV. Số đo gần như không đổi từ movement 0 đến movement 3 (10,48 / 10,50 / 9,50 / 10,48 s).
- Vì chi phí cố định theo movement, tác phẩm càng nhiều movement càng tốn: `1M` 4 movement → **41,0 s** chỉ cho MuseScore.
- `symphony` chậm hơn `guitar` ~4 s/movement vì nhiều nhạc cụ hơn.
- Thử nghiệm `-F` (factory settings) giảm 10,5 s → 8,3 s, nhưng **không dùng được** ngay: nó bỏ qua cấu hình soundfont và có thể bật lại metronome. Chỉ ghi nhận như một hướng khảo sát.

**Batch experiment** (MuseScore 4.7.6, `mscore -j job.json`):

```json
[
  { "in": "m0.musicxml", "out": "four-0.wav" },
  { "in": "m1.musicxml", "out": "four-1.wav" },
  { "in": "m2.musicxml", "out": "four-2.wav" },
  { "in": "m3.musicxml", "out": "four-3.wav" }
]
```

| Cách xuất | Tổng | Movement 0 xong | Movement 1 xong | Movement 2 xong |
|---|---:|---:|---:|---:|
| 4 process riêng | 40,96 s | ~10,5 s | ~21,0 s | ~30,5 s |
| 1 batch job | **26,7 s** | ~10,6 s | ~16,1 s | ~20,2 s |

Batch **không làm chương 0 nhanh hơn** (vẫn ~10,6 s), nhưng mỗi movement sau chỉ ~5–6 s thay vì ~10–11 s. Đây là cách giảm chi phí khởi động cho các chương sau, không phải cách giảm cold start chương 0.

### 4.2. Color (~3,8–4,0% độ dài nhạc trước P0-1; ~0,15% sau)

`apply_preset` gồm hai phần:

1. FFmpeg chạy chain preset ra PCM thô: **0,16 s** cho 263 s nhạc.
2. Đọc PCM, trộn noise từng frame (`_mix_noise`), giới hạn đỉnh (`_limit_peak`), ghi WAV.

Trước P0-1, phần 2 là vòng lặp Python từng sample: **~10,2 s**, nên color tỷ lệ thuận với độ dài nhạc:

| Span | Color (trước) | Tỷ lệ trên độ dài nhạc |
|---|---:|---:|
| `1W` | 16,26 s | 3,78% |
| `1M` | 38,02 s | 3,94% |
| `3M` | 60,91 s | 4,00% |
| `1Y` | 27,45 s | 4,01% |

Sau P0-1, phần 2 chạy theo block trong numpy: **~0,23 s** cho 263 s, và color không còn tỷ lệ theo độ dài nhạc nữa (phần lớn thời gian còn lại là đọc/ghi file). Đây là phase tối ưu được nhiều nhất mà **không đổi âm thanh**.

### 4.3. Encode AAC (~0,65% độ dài nhạc)

- `_transcode_m4a` gọi ffmpeg lần hai, decode lại file WAV đã tô màu rồi encode AAC 160 kbps.
- 1,06–3,44 s/movement; tổng 6,3 s (`1M`), 9,8 s (`3M`).
- Có thể gộp vào lần ffmpeg tô màu để bớt một lần decode, nhưng mức tiết kiệm nhỏ hơn color nhiều.

### 4.4. Phần còn lại (~1–2%)

Compose, humanize, DFI, MusicXML, peaks, publish đều rất nhỏ. Không nên tối ưu trước các phase trên.

---

## 5. Đề xuất tối ưu

Thứ tự theo **mức giảm thời gian / rủi ro**, không theo độ phức tạp.

### P0-1. Vector hóa `apply_preset` bằng numpy — ✅ đã làm trong PR này

**Thay đổi**: `_mix_noise` và `_limit_peak` chuyển sang phép toán numpy theo block; FFmpeg chain, LCG noise, gate và cách tính gain giữ nguyên. Vòng lặp từng sample vẫn còn làm fallback khi không có numpy.

**Chi tiết code** (`backend/app/sonify/preset.py`):

- Noise tính bằng `uint32`: phép nhân và dịch tự wrap mod 2³², đúng bằng `& 0xFFFFFFFF` trong `_unit_noise`.
- Cộng ở `float64` rồi mới cast về `float32`/`int16`, nên khớp đúng điểm làm tròn của vòng lặp cũ (`int()` cắt về 0, `np.trunc` cũng vậy).
- Chia block `1 << 19` sample. Một block sinh vài temporary `float64` (`seed`, `noise`, `column`, bản `gated`), đỉnh bộ nhớ tạm ~30 MB và **không phụ thuộc độ dài movement** (đo trên file 503 s stereo: +28 MB RSS).
- `import numpy` nằm trong `try/except ImportError`; thiếu numpy, hoặc gặp typecode lạ, thì chạy vòng lặp cũ. `numpy>=2.0.0` đã thêm vào `backend/requirements.txt`.

**Đã đo** trên cùng file 263 s (phase `color` trong bench, gồm cả đọc/ghi file):

| Bước | Trước | Sau |
|---|---:|---:|
| FFmpeg preset → PCM | 0,16 s | 0,16 s |
| DSP (noise + gate + limit) | ~10,2 s | ~0,23 s |
| **Tổng color** | **10,4 s** | **0,51 s** |

**Độ chính xác**: so sánh SHA-256 của file WAV tạo bởi `apply_preset` cũ và mới trên cùng file dry 263 s (float32, guitar): **giống hệt từng byte**. Với int16 của MuseScore 3, kết quả khớp từng sample. Vì vậy **không bump `SPAN_REVISION`/`RECAP_REVISION`**; file đã cache vẫn dùng được.

**Test**: `tests/test_humanize.py` có sáu test mới — noise khớp công thức `_unit_noise`, đường int16 cắt giống vòng lặp, `_limit_peak` dùng một gain chung rồi cắt về 0, fallback không numpy khớp đường block, một ma trận block × channels × gate trên cả hai typecode, và một golden SHA-256 để phát hiện lệch âm thầm.

**Ảnh hưởng đo được**: `1M` 86,4 → **50,3 s**, `3M` 108,8 → **50,5 s**, `1Y` 62,2 → **36,1 s**, `1W` 31,3 → **15,8 s**. Đây là win lớn nhất và ít rủi ro nhất; sau bước này MuseScore là phase lớn nhất.

### P0-2. Ghi thêm phase vào log `span_render`

Hiện log chỉ có `export`, `color`, `peaks`, `encode`, `total`, `ratio`. Thêm `compose`, `humanize`, `dfi`, `musicxml`, và `slotWait` để theo dõi trên production. Không đổi hành vi.

### P1-1. Batch MuseScore cho các chương sau

**Thay đổi**: một `mscore -j job.json` xuất nhiều MusicXML trong một process. Giữ **chương 0 xuất riêng** để cold start không bị chậm; batch các chương 1..N (hoặc cửa sổ 2–4 chương) sau khi chương 0 bắt đầu export.

**Đã đo**: 4 movement 26,7 s thay vì 41,0 s. Chương 0 vẫn ~10,6 s; chương 1–3 xong ở ~16,1 / 20,2 / 26,7 s.

**Thiết kế gợi ý**:

1. Khi có request chương 0, soạn score chương 0, xuất riêng như hiện tại.
2. Trong lúc chương 0 export, soạn score các chương kế (compose rất rẻ: ~1–2 s cho cả tác phẩm) và ghi MusicXML.
3. Chạy một batch job cho các chương kế, thứ tự tăng dần.
4. Phát hiện từng WAV xong để đưa vào color/encode ngay:
   - Linux: `inotify` `IN_CLOSE_WRITE` là chính xác nhất.
   - Cross-platform: poll kích thước file, coi là xong khi không đổi trong ~1 s (đã thử với MuseScore 4).
5. Color/encode chạy ngoài slot MuseScore (xem P1-2) để overlap với batch.
6. Huỷ batch khi không còn ai chờ; batch là một process nên không thể huỷ riêng một file.

**Rủi ro**:

- Cần xác nhận `mscore3` trên Ubuntu 24.04 hỗ trợ `-j` với MusicXML và hành vi ghi file giống MuseScore 4.
- Batch giữ CPU lâu hơn; trên VM 2 vCPU phải đo lại.
- Nếu người dùng dừng sau chương 0, batch có thể đã render thêm vài chương — chấp nhận được với `1M`/`3M` (3–4 chương), không nên batch cả 12 chương của `1Y`.
- Cần dọn WAV tạm sau mỗi chương; batch 4 chương có thể tạo ~350 MB WAV cùng lúc.

### P1-2. Chỉ giữ slot MuseScore quanh `self._exporter`

**Hiện tại**: `ensure_movement` giữ `with self._slots` bao trọn `_render_movement`, gồm cả color, peaks, encode, publish (`audio.py:1320`). Vì vậy slot bị chiếm ~22 s thay vì ~10,5 s.

**Thay đổi**: chỉ acquire slot quanh `self._exporter(xml_path, wav_path)`. Compose, color, peaks, encode, publish chạy ngoài slot.

**Lợi ích**:

- Với **một người nghe hiện tại**: gần như **không đổi**, vì client chỉ request chương kế sau khi chương hiện tại đã publish xong; không có hai render chồng nhau.
- Với **batch**: color/encode chương 0 chạy được trong lúc batch xuất chương 1 → đây là điều kiện để P1-1 đạt ~30 s thay vì ~36 s.
- Với **nhiều người nghe**: color/encode của người này overlap export của người khác, tăng throughput mà không tăng số slot.

**Lưu ý**: `renderSec` hiện được đo từ đầu `_render_movement` (đã nằm trong slot) nên không gồm thời gian chờ slot. Khi chuyển slot vào trong, phải đo `slotWait` và trừ ra khỏi `renderSec`, hoặc bắt đầu đồng hồ sau khi acquire slot, để giữ đúng ý nghĩa "không gồm queue wait" trong [`sonify-span-render-ahead-plan.md`](./sonify-span-render-ahead-plan.md) mục 3.

### P2-1. Prewarm sau giờ đóng cửa

- Sau 15:00, fingerprint của phiên đã đóng ổn định; render trước các span của watchlist/top symbol sẽ cho **cold start 0 s**.
- Với phiên đang mở, fingerprint đổi theo nến mới nên prewarm chỉ có giá trị trong TTL ngắn; có thể prewarm chương 0 khi `/span` được gọi cho symbol vừa nghe.
- Không cần đổi cache key; chỉ cần gọi `ensure_movement` từ worker nền.

### P2-2. Slot và ưu tiên

- Giữ `VSTOCK_MUSESCORE_SLOTS=1` trên VM 2 vCPU. Tăng lên 2 chỉ khi ≥4 vCPU và sau khi đo; MuseScore đã dùng nhiều thread, tăng slot có thể làm chậm từng export.
- Ưu tiên playback trước prefetch (đã có trong kế hoạch §6.4). Với batch, ưu tiên càng quan trọng vì batch chiếm process lâu.

### P2-3. Synthesizer nhanh hơn (dài hạn)

- FluidSynth/MIDI có thể nhanh hơn MuseScore nhiều lần, nhưng articulation/dynamics/soundfont của MuseScore là một phần của sản phẩm. Cần A/B trước khi cân nhắc.
- Chỉ xem xét sau P0/P1; không phải việc đầu tiên.

### Không nên làm

- **Không tăng lookahead depth** để "che" thời gian render. `renderRatio` đo được 0,07–0,09, thấp hơn ngưỡng 0,7 rất xa; depth 1 là đủ khi pipeline nhanh. Tăng depth chỉ tăng tải và tranh slot.
- **Không tăng `EXPORT_SLOTS`** trên 2 vCPU để mong nhanh hơn.
- **Không giảm sample rate / mono** nếu chưa có quyết định chất lượng âm thanh.
- **Không cache riêng file color**: file cuối đã được cache theo revision/fingerprint.

---

## 6. Kết quả kỳ vọng

Số dưới đây là **ước tính** từ thời gian phase đo được, giả định code chạy đúng như thiết kế; chưa phải số đo end-to-end sau khi sửa.

### 6.1. Cold start chương 0 (người dùng bấm nghe)

| Span | Trước | Sau P0-1 (đo) |
|---|---:|---:|
| `1W` (1 movement) | 31,3 s | **15,8 s** |
| `1M` movement 0 | 22,2 s | **13,1 s** |
| `3M` movement 0 | 36,7 s | **16,8 s** |
| `1Y` movement 0 | 24,1 s | **13,1 s** |

### 6.2. Toàn bộ tác phẩm

| Span | Trước | Sau P0-1 (đo) | Sau P0-1 + P1 (ước tính) |
|---|---:|---:|---:|
| `1W` | 31,4 s | **15,9 s** | **15,9 s** |
| `1M` | 86,7 s | **50,5 s** | **~31 s** |
| `3M` | 108,9 s | **50,6 s** | **~28 s** |
| `1Y` | 62,3 s | **36,1 s** | **~22 s** |

`1Y` 12 movement: batch cả 12 không nên; dùng cửa sổ 2–4 chương, hoặc chỉ batch khi người nghe đã commit.

---

## 7. Rủi ro và cách kiểm chứng

| Rủi ro | Cách kiểm |
|---|---|
| Production là MuseScore 3, không phải 4.7.6 | Chạy `scripts/bench_render.py` trong Docker image trên VM; so sánh từng phase |
| VM 2 vCPU chậm hơn M5 | Đo 1/2/4 listener đồng thời; theo dõi CPU, nhiệt, queue wait |
| Numpy đổi kết quả âm thanh | Đã kiểm: file WAV giống hệt từng byte với bản cũ (float32 và int16), và có test khoá công thức trong `tests/test_humanize.py`. Vẫn nên chạy A/B nghe trên 10 tác phẩm trước khi phát hành |
| Batch không hỗ trợ trên `mscore3` | Thử `mscore3 -j job.json` trong container trước khi viết code |
| Batch chiếm slot/CPU lâu | Đo thời gian chờ của một request playback khi batch đang chạy; thêm ưu tiên slot |
| Huỷ batch ảnh hưởng người khác | Refcount waiter hoặc chỉ batch khi một work đang được nghe |
| Đầy disk do nhiều WAV | Giữ `WORK_KEEP_SEC`, xoá WAV ngay sau color/encode, đo dung lượng batch 4 chương |
| `renderSec` sai nghĩa sau khi đổi slot | Đo riêng `slotWait`; test JSON có `renderSec` không gồm queue wait |
| Nhiều uvicorn worker tranh cache | Hiện chạy 1 process; nếu scale, cần lock liên process hoặc chấp nhận render trùng |

**A/B âm thanh**: với numpy, so sánh file WAV cũ/mới trên 10 tác phẩm (guitar + symphony), kiểm tra null test và phổ. Với phương án FFmpeg-only (mục 8), phải bump `SPAN_REVISION`/`RECAP_REVISION` vì noise/gate đổi.

---

## 8. Phương án thay thế: đưa toàn bộ color sang FFmpeg

Nếu không muốn thêm numpy, có thể đưa noise/gate vào FFmpeg:

```
[0:a]asplit=2[dry][sc];
[dry]highshelf=f=8000:g=-1,equalizer=f=280:t=h:w=180:g=1.2,aecho=1:1:12|20:0.05|0.03[col];
anoisesrc=color=white:amplitude=0.0003:seed=20261103:sample_rate=44100:duration=<s>,
  pan=stereo|c0=c0|c1=c0[nz];
[nz][sc]sidechaingate=threshold=0.01:ratio=9000:attack=2:release=5:detection=peak:range=0[gated];
[col][gated]amix=inputs=2:duration=first:weights='1 1':normalize=0[mix]
```

Đã đo trên file 263 s:

- Chain + noise + gate: **0,29 s** (so với 10,4 s).
- Gộp luôn AAC: **2,3 s** cho cả color + encode (so với 12,15 s), khi dùng `alimiter` trong cùng graph. Nếu muốn khớp đúng gain toàn cục hiện tại (`_limit_peak`), cần thêm một bước đo gain rồi `volume`; vẫn dưới ~3 s.
- Deterministic với `seed` (hash giống nhau qua hai lần chạy).
- Sau khi áp cùng gain: RMS diff **1,75e-4**, max diff **7,6e-4** so với output hiện tại. Khác noise texture nên cần A/B và bump revision.

Ưu điểm: không thêm dependency, gộp được encode. Nhược điểm: đổi âm thanh, khó tái tạo chính xác noise cũ, và filter graph phức tạp hơn. Vì numpy cho kết quả **giống hệt từng byte** và cũng rất nhanh (0,51 s so với 0,29 s), **numpy đã được chọn**; FFmpeg-only chỉ còn là phương án dự phòng nếu sau này muốn bỏ numpy.

---

## 9. Việc cần làm

- [x] P0-1: vector hóa `apply_preset` bằng numpy; thêm `numpy` vào requirements; test khoá công thức noise/gain.
- [ ] P0-2: thêm `compose`, `humanize`, `dfi`, `musicxml`, `slotWait` vào log `span_render`.
- [ ] P1-2: chuyển `with self._slots` xuống quanh `self._exporter`; giữ `renderSec` không gồm queue wait.
- [ ] P1-1: prototype batch `mscore -j` trong container MuseScore 3; đo lại 1/2/4 movement trên VM 2 vCPU.
- [ ] P1-1: thiết kế batch manager (thứ tự chương, phát hiện file xong, huỷ, dọn WAV).
- [ ] P2-1: prewarm sau đóng cửa cho watchlist/top symbol.
- [ ] P2-2: đo `EXPORT_SLOTS=2` trên ≥4 vCPU; ưu tiên playback trước prefetch.
- [ ] Chạy lại toàn bộ bảng trong tài liệu này trên production (MuseScore 3, VM 2 vCPU); cập nhật số thật.

---

## Phụ lục: số đo chi tiết

### A.0. Sau P0-1, từng movement (guitar, cache lạnh)

| Span | Index | Nến | Nhạc | MuseScore | Color | Encode | Tổng |
|---|---:|---:|---:|---:|---:|---:|---:|
| `1W` | 0 | 1112 | 429,70 s | 11,548 | 0,691 | 2,814 | 15,77 |
| `1M` | 0 | 221 | 263,02 s | 10,512 | 0,511 | 1,783 | 13,07 |
| `1M` | 1 | 1115 | 273,02 s | 10,514 | 0,500 | 1,795 | 13,08 |
| `1M` | 2 | 1129 | 165,01 s | 9,500 | 0,298 | 1,067 | 11,11 |
| `1M` | 3 | 3792 | 263,02 s | 10,491 | 0,438 | 1,640 | 13,03 |
| `3M` | 0 | 874 | 503,04 s | 11,512 | 0,838 | 3,461 | 16,82 |
| `3M` | 1 | 920 | 519,04 s | 11,480 | 0,837 | 3,419 | 16,21 |
| `3M` | 2 | 1104 | 500,81 s | 12,568 | 0,888 | 3,070 | 17,48 |
| `1Y` | 0 | 171 | 281,20 s | 10,508 | 0,497 | 1,886 | 13,12 |
| `1Y` | 1 | 180 | 198,01 s | 9,509 | 0,438 | 1,335 | 11,51 |
| `1Y` | 2 | 198 | 204,61 s | 9,490 | 0,343 | 1,397 | 11,43 |

So với bảng A.1–A.3 bên dưới, **chỉ cột Color đổi rõ rệt**. MuseScore và encode dao động ~±1 s giữa hai lần đo (ví dụ `3M` index 0: 12,457 → 11,512 s; index 2: 11,603 → 12,568 s), nên đừng đọc chênh lệch dưới ~1 s ở hai cột đó là do P0-1.

### A.1. `1M` từng movement (guitar, trước P0-1)

| Index | Nến | Nhạc | Compose | MuseScore | Color | Encode | Tổng |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 221 | 263,02 s | 0,217 | 10,483 | 9,650 | 1,781 | 22,17 |
| 1 | 1115 | 273,02 s | 0,213 | 10,498 | 10,582 | 1,778 | 23,12 |
| 2 | 1129 | 165,01 s | 0,190 | 9,500 | 6,891 | 1,060 | 17,69 |
| 3 | 3792 | 263,02 s | 0,383 | 10,476 | 10,898 | 1,636 | 23,46 |

### A.2. `3M` từng movement (guitar, trước P0-1)

| Index | Nến | Nhạc | Compose | MuseScore | Color | Encode | Tổng |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 874 | 503,04 s | 0,934 | 12,457 | 19,852 | 3,382 | 36,74 |
| 1 | 920 | 519,04 s | 0,388 | 11,518 | 20,581 | 3,435 | 36,00 |
| 2 | 1104 | 500,81 s | 0,832 | 11,603 | 20,481 | 3,020 | 36,06 |

### A.3. `1W` và `1Y` (guitar, trước P0-1)

| Span | Index | Nến | Nhạc | Compose | MuseScore | Color | Encode | Tổng |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `1W` | 0 | 1112 | 429,70 s | 0,623 | 11,523 | 16,257 | 2,817 | 31,30 |
| `1Y` | 0 | 171 | 281,20 s | 0,188 | 10,491 | 11,460 | 1,880 | 24,06 |
| `1Y` | 1 | 180 | 198,01 s | 0,205 | 9,498 | 8,147 | 1,311 | 19,20 |
| `1Y` | 2 | 198 | 204,61 s | 0,177 | 9,480 | 7,844 | 1,400 | 18,94 |

### A.4. Mẫu `symphony` (trước P0-1)

| Index | Nến | Nhạc | Compose | MuseScore | Color | Encode | Tổng |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 221 | 262,55 s | 0,190 | 14,480 | 10,371 | 1,775 | 26,86 |
