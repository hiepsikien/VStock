# Thiết Kế Pattern `preludio` (*La Catedral — Preludio Saudade*) Chuẩn Tổng Phổ Agustín Barrios

> **Tham chiếu**: Tổng phổ gốc *La Catedral — Preludio ("Saudade")* của Agustín Barrios Mangoré (nhịp `2/4`, *Lento — Ben marcato il canto*).

---

## 1. Cấu Trúc Nguyên Bản Trong Tổng Phổ Barrios

Trong bản gốc của Barrios, mỗi khung `2/4` (tương đương **2 phách đen = 4 móc đơn = 8 móc kép `0..7`**, chia làm **2 chùm 4 móc kép: `0, 1, 2, 3` và `4, 5, 6, 7`**) là sự đan xen (interlocking) tuyệt đối giữa **Bè Giai điệu trên cao (Voice 1)** và **Bè Trung rải arpeggio (Voice 2)**:

| Chùm móc kép | Vị trí móc kép (`0..7` trong khung 2 phách) | Bè đảm nhiệm | Giá trị nốt & Vị trí TAB mẫu (Ô 1: Bm/D) | Vai trò âm nhạc |
|---|---|---|---|---|
| **Chùm 1**<br>*(Phách 1: móc kép `0..3`)* | **Móc kép `0`** (`beat 0.0`) | **Bè Giai điệu Cao (`Voice 1`)** | **Nốt đen chấm dôi** (`duration = 1.5` phách = 6 móc kép, ngân qua `0..5`), dây 1 ngăn 14 (`F#5`) | **Nốt giai điệu 1** (*Ben marcato il canto* — nhấn rõ và ngân dài lơ lửng trên cao) |
| | **Móc kép `1`** (`beat 0.25`) | **Bè Trung (`Voice 2`)** | Móc kép (`0.25` phách), dây 2 buông (`B4` — `upper_mid`) | Nốt rải đi xuống bậc 1 (Sát dưới giai điệu) |
| | **Móc kép `2`** (`beat 0.50`) | **Bè Trung (`Voice 2`)** | Móc kép (`0.25` phách), dây 3 ngăn 11 (`F#4` — `mid`) | Nốt rải đi xuống bậc 2 (Giữa hợp âm) |
| | **Móc kép `3`** (`beat 0.75`) | **Bè Trung (`Voice 2`)** | Móc kép (`0.25` phách), dây 4 ngăn 12 (`D4` — `low_mid`) | Đáy của sóng arpeggio chữ V (Trầm-trung) |
| **Chùm 2**<br>*(Phách 2: móc kép `4..7`)* | **Móc kép `4`** (`beat 1.00`) | **Bè Trung (`Voice 2`)** | Móc kép (`0.25` phách), dây 3 ngăn 11 (`F#4` — `mid`) | Sóng arpeggio đảo chiều đi lên bậc 1 |
| | **Móc kép `5`** (`beat 1.25`) | **Bè Trung (`Voice 2`)** | Móc kép (`0.25` phách), dây 2 buông (`B4` — `upper_mid`) | Sóng arpeggio đi lên bậc 2 |
| | **Móc kép `6`** (`beat 1.50`) | **Bè Giai điệu Cao (`Voice 1`)** | **Nốt móc đơn** (`duration = 0.5` phách = 2 móc kép, ngân qua `6..7`), dây 1 ngăn 14 (`F#5`) | **Nốt giai điệu 2** ở cao (Lặp lại hoặc chuyển sang cao độ dữ liệu tại móc đơn thứ 3 của khung) |
| | **Móc kép `7`** (`beat 1.75`) | **Bè Trung (`Voice 2`)** | Móc kép (`0.25` phách), dây 2 buông (`B4` — `upper_mid`) | Nốt rải khép chùm móc kép thứ 2 |

---

## 2. Quy Tắc Ánh Xạ Vào Hệ Thống Sonification (`backend/app/sonify/guitar_patterns.py`)

### 2.1. Khung 2 phách đen (`4 móc đơn = 8 móc kép`)
- Trên nhịp **`4/4`** (`epb = 8` móc đơn = 16 móc kép): Mỗi ô nhịp gồm **2 khung *La Catedral* liên tiếp**:
  - **Khung 1** (Nửa đầu ô: móc đơn `0..3`, móc kép `0..7`, `beat 0.0 .. 2.0`).
  - **Khung 2** (Nửa sau ô: móc đơn `4..7`, móc kép `8..15`, `beat 2.0 .. 4.0`).
- Trên nhịp **`3/4`** hoặc **`6/8`** (`epb = 6` móc đơn = 12 móc kép):
  - Khung đầu 2 phách đen (`móc kép 0..7`, `beat 0.0 .. 2.0`) chạy trọn vẹn mẫu 8 móc kép *La Catedral* (`0` và `6` ở Voice 1; `1, 2, 3, 4, 5, 7` ở Voice 2).
  - Phách thứ 3 (`móc kép 8..11`, `beat 2.0 .. 3.0`) chạy 1 chùm 4 móc kép: Giai điệu ở móc kép `8` (`duration = 1.0` phách = 4 móc kép) và Bè Trung rải đi xuống ở móc kép `9, 10, 11` (`upper_mid -> mid -> low_mid`).

### 2.2. Bè Giai Điệu Cao (`Voice 1` — `lead`)
Trong mỗi khung 8 móc kép (`origin16 = cell_start_eighth * 2`):
1. **Nốt Giai điệu 1 tại `origin16 + 0` (`beat = 0.0` của khung)**:
   - Cao độ: `pitch_1 = _melody_at(ctx, cell_start_eighth)`.
   - Độ dài: **6 móc kép** (`duration_beats = 1.5`, nốt đen chấm dôi) — nếu có chuông (`_insert_bells`) hoặc khe thở cuối câu thì tự động cắt gọn ở bước sau.
   - Lực gảy: Nổi rõ theo chỉ dẫn *Ben marcato il canto* (`_note_velocity` với `tenuto=True`).
2. **Nốt Giai điệu 2 tại `origin16 + 6` (`beat = 1.5` của khung, tức móc đơn thứ 3 `cell_start_eighth + 3`)**:
   - Cao độ: `pitch_2 = _melody_at(ctx, cell_start_eighth + 3)` (giữ nguyên nốt đang ngân như ô 1–2 của Barrios hoặc bước sang nốt giai điệu mới như ô 3–4 của Barrios).
   - Độ dài: **2 móc kép** (`duration_beats = 0.5`, nốt móc đơn).
   - Lực gảy: Hơi nhẹ hơn Nốt 1 một bậc (`max(56, vel_1 - 2)`) để tạo nhịp thở tự nhiên.

### 2.3. Bè Trung (`Voice 2` — `support`)
Trong mỗi khung 8 móc kép (`origin16 = cell_start_eighth * 2`), Bè Trung chọn **3 âm hợp âm khác nhau** nằm dưới giai điệu (`low_mid < mid < upper_mid < min(pitch_1, pitch_2)`):
- Nếu trong vùng `[ctx.mid_low, ctx.mid_high]` (kết hợp dây buông nếu hợp thế tay) có đủ 3 âm hợp âm: lấy 3 nốt cao nhất dưới giai điệu làm `(low_mid, mid, upper_mid)`. Nếu chỉ có 2 âm `(a, b)`: dùng `(a, a, b)` hoặc `(a, b, b)` sao cho các móc kép liền kề đổi nốt mượt mà.
- **Lịch gảy móc kép (`duration_beats = 0.25`)**:
  - `origin16 + 1`: `upper_mid`
  - `origin16 + 2`: `mid`
  - `origin16 + 3`: `low_mid` *(Đáy chữ V)*
  - `origin16 + 4`: `mid`
  - `origin16 + 5`: `upper_mid`
  - *(Móc kép `origin16 + 6` nghỉ ở Voice 2 hoặc nhường onset cho Nốt Giai điệu 2 của Voice 1)*
  - `origin16 + 7`: `upper_mid` (hoặc `mid` nếu `upper_mid >= pitch_2`)
- **Lực gảy**: Mềm mại hơn giai điệu (`support_vel` thấp hơn `lead_vel` ít nhất 8–10 đơn vị) để giai điệu trên cao luôn nổi bật (*Ben marcato il canto*).

### 2.4. Bè Trầm (`Voice 3` — `low`)
- Giữ nền Bass trầm ấm (ngân 2 ô nhịp ở `_preludio_bass` như phần mở bài trầm mặc của Barrios, đảm bảo `bass < low_mid < mid < upper_mid < lead` và vượt qua `assert_playable` với profile `"barrios_preludio"`).
