# Giọng gốc, chuyển giọng và bản sắc hợp âm theo cổ phiếu & chương

Kế hoạch bước tiếp theo sau `docs/sonify-long-form.md`: mở rộng các bản dài (`1W`, `1M`, `3M`, `1Y`) từ một giọng cố định (`C major / A minor`) sang bộ **5 vùng giọng trong biên độ dịch ±3 bán âm**, cho phép **chuyển vùng giọng giữa các chương**, và **điều phối màu sắc hòa âm theo tính chất cổ phiếu cũng như nội dung từng chương**. Bản `1D` giữ nguyên hoàn toàn ở giọng `C` (`RECAP_REVISION = "9"`).

---

## 1. Nguyên tắc cốt lõi: Hạ trần / nâng sàn trước khi soạn, chỉ dịch một lần khi xuất MusicXML

Toàn bộ engine hiện tại (`form.py`, `phrasing.py`, `jazz.py`, `minimalist.py`, `render.py`) giải bài toán hòa âm và giai điệu trên **thang 7 bậc diatonic + 12 hợp âm mượn** lấy `C` (`MIDI 60`) làm bậc `I` và `A` (`MIDI 57`) làm bậc `vi`.

1. **Mọi phép tính nội bộ và `Score` giữ nguyên trên hệ quy chiếu bậc `I = C` (`fifths = 0`)**:
   - Bậc thang âm, khoảng cách semitone, và ma trận chuyển tiếp `TRANSITIONS` + `_BORROWED_EDGES` là bất biến đối với phép dịch giọng.
   - `Score` vẫn lưu các `NoteEvent.midi` và `HarmonyEvent.chord` ở hệ C để các unit test hiện tại và việc kiểm tra contour hoạt động nguyên vẹn.
2. **Chỉ dịch một lần duy nhất trong `musicxml.py` (concert pitch)**:
   - Không dịch kép ở cả `Score` lẫn `musicxml.py`, và **không gấp quãng 8 sau khi dịch**.
   - Khi xuất MusicXML, mọi `NoteEvent.midi` và `HarmonyEvent.chord` được cộng `key.semitones`. Các kèn Sax và Bass vẫn xuất ở concert pitch như hiện tại (Bass giữ `<octave-change>-1`).
   - Thẻ `<fifths>` trong `_attributes()` ghi `score.key.fifths`.
   - **Chính tả nốt và hợp âm (`step`, `alter`) bám theo `key.fifths` của giọng đích:** Ví dụ hợp âm mượn `B♭` (trong hệ `C`) khi dịch `+3` bán âm sang giọng `E♭` (`fifths = -3`) có pitch class `1` và phải được viết là **`D♭`** (`step="D", alter=-1`), không viết là `C♯`. Các bậc thuộc thang lấy từ bảng 7 bậc của `key.fifths`; các âm mượn ngoài thang lấy chính tả theo hướng dấu hóa của `key.fifths` (giọng giáng viết giáng, secondary dominants dẫn lên viết thăng theo bậc đích).
3. **Hạ trần và nâng sàn theo `key.semitones` ngay trước khi dựng nốt**:
   - Dịch dương (`D` `+2`, `Eb` `+3`) đẩy các nốt cao lên; dịch âm (`Bb` `-2`, `A` `-3`) kéo nốt sàn `G3 (55)` của Violin và Alto Sax xuống `F3 (53)` / `E3 (52)` (thấp hơn dây buông `G3` của Violin).
   - Vì vậy, dùng một cơ chế duy nhất trước khi soạn:
     - `up_shift = max(0, key.semitones)`
     - `down_shift = max(0, -key.semitones)`
     - Trần thực tế trong hệ C giảm đi `up_shift`: `FLUTE_CEILING - up_shift`, `VIOLIN_CEILING - up_shift`, `SAX_CEILING - up_shift`.
     - Sàn bàn giao thực tế trong hệ C tăng thêm `down_shift`: `VIOLIN_LOWEST + down_shift`, `CELLO_HANDBACK + down_shift`.
     - Trong `jazz.py`, thay vì lấy cứng `scale.index(79)` và `scale.index(VIOLIN_LOWEST)`, chọn chỉ số cao nhất trong `scale` có `midi <= SAX_CEILING - up_shift` và chỉ số thấp nhất có `midi >= VIOLIN_LOWEST + down_shift`.

---

## 2. Bộ 5 vùng giọng chuẩn (`KEY_RING`)

Trên vòng quãng 5, mỗi nấc dấu hóa (`fifths`) cách nhau một quãng 4/5 ($\pm 7$ bán âm mod 12). `F` (`+5` hoặc `-7` bán âm) và `G` (`+7` hoặc `-5` bán âm) nằm ngoài cửa sổ dịch `±3` bán âm. Bộ giọng chuẩn chốt ở tuple 5 vùng giọng `KEY_RING` xếp theo thứ tự `fifths` tăng dần:

```python
KEY_RING = (EB_KEY, BB_KEY, C_KEY, D_KEY, A_KEY)
```

| Chỉ số | Mã giọng (`name`) | Nhãn UI (`label`) | Chủ âm bậc `I` | Chủ âm bậc `vi` | `fifths` | `semitones` (dịch từ C) | Đặc tính âm sắc |
|---|---|---|---|---|---|---|---|
| `0` | `Eb` | `Mi♭` | E♭ Major | C minor | `-3` (3♭) | `+3` | Bề thế, kịch tính (bậc `I` ở Mi♭ trưởng, bậc `vi` ở Đô thứ) |
| `1` | `Bb` | `Si♭` | B♭ Major | G minor | `-2` (2♭) | `-2` | Ấm, dày, giọng sở trường của Saxophone, Rhodes và dàn dây trầm |
| `2` | `C` | `Đô` | C Major | A minor | `0` | `0` | Trong sáng, trung tính, cân bằng |
| `3` | `D` | `Rê` | D Major | B minor | `+2` (2♯) | `+2` | Rực rỡ, sáng, giàu bồi âm dây (Violin/Cello) |
| `4` | `A` | `La` | A Major | F♯ minor | `+3` (3♯) | `-3` | Sắc nét nhưng đằm ở âm khu trầm (`-3` bán âm) |

*Lưu ý về nhãn UI và màu Trưởng/Thứ:*
- Trong một chương, bậc `I` (Trưởng) và bậc `vi` (Thứ song song) thay phiên nhau theo `regime` của từng phrase (`uptrend`/`sideway` mở ở `I`, `downtrend` mở ở `vi`). Vì vậy nhãn hiển thị trên UI chỉ ghi tên vùng giọng của `KeySpec` (`Mi♭`, `Si♭`, `Đô`, `Rê`, `La`), không gắn cứng chữ "Trưởng" hay "Thứ" cho cả chương.

---

## 3. Ánh xạ Giọng gốc (`Home Key`) cố định theo cổ phiếu

Mỗi cổ phiếu ánh xạ **1–1** vào một `Home Key` cố định trong `KEY_RING`:

| Nhóm cổ phiếu | Mã cố định trong bảng | Giọng gốc (`Home Key`) | Lý do âm nhạc |
|---|---|---|---|
| **Ngân hàng & Tài chính** | `VCB`, `BID`, `CTG`, `TCB`, `MBB`, `ACB`, `VPB`, `STB`, `HDB`, `TPB` | **`Bb`** (`KEY_RING[1]`) | Âm khu trầm ấm (`-2` bán âm), chững chạc, hợp tiếng Sax và Piano. |
| **Công nghệ, Bán lẻ & Tăng trưởng** | `FPT`, `MWG`, `DGW`, `FRT`, `PNJ`, `CTR`, `CMG` | **`D`** (`KEY_RING[3]`) | Nhánh dấu thăng (`+2♯`, `+2` bán âm) làm dàn dây sáng, giàu năng lượng. |
| **Thép, BĐS, Chứng khoán (Chu kỳ cao)** | `HPG`, `HSG`, `NKG`, `VIC`, `VHM`, `VRE`, `NVL`, `KDH`, `SSI`, `VND`, `HCM`, `VCI` | **`Eb`** (`KEY_RING[0]`) | Khi `uptrend` mở ở `E♭ Major` bề thế; khi `downtrend` bậc `vi` rơi vào `C minor` kịch tính. |
| **Tiêu dùng, Phòng thủ, Điện – Khí** | `VNM`, `MSN`, `SAB`, `GAS`, `POW`, `REE`, `PLX`, `BVH` | **`C`** (`KEY_RING[2]`) | Trong trẻo, ổn định, cân bằng. |
| **Hạ tầng, Cảng biển, Hóa chất, Xuất khẩu** | `GMD`, `HAH`, `DGC`, `DPM`, `DCM`, `VHC`, `ANV`, `PTB` | **`A`** (`KEY_RING[4]`) | Dấu hóa sáng (`+3♯`) nhưng cữ âm trầm (`-3` bán âm), vững và rõ nét. |
| **Các mã còn lại** | Ngoài danh sách trên | `KEY_RING[zlib.crc32(symbol.strip().upper().encode("utf-8")) % len(KEY_RING)]` | Tất định tuyệt đối qua mọi lần khởi động server, không phụ thuộc dữ liệu giá. |

*Chế độ chọn giọng:* Chạy tự động (`Auto`) theo bảng trên để không làm nhân bộ nhớ cache (`5 giọng × 3 biến thể`).

---

## 4. Ngưỡng theo `span` và Bản sắc chương (`MovementCharacter`)

Cả việc chọn `MovementCharacter` lẫn kịch bản chuyển giọng đều đọc chung `return_pct` và `volatility` của chương với **bảng ngưỡng theo `span`**:

- `return_pct = (bars[-1].close - bars[0].close) / bars[0].close`
- `volatility = (max_close - min_close) / min_close`

| `span` | Đơn vị 1 chương | Ngưỡng xu hướng `trend_th` (`|return_pct|`) | Ngưỡng biến động `vol_th` (`volatility`) |
|---|---|---|---|
| `1W` | 1 tuần (tối đa 5 phiên) | `2.0%` (`0.020`) | `3.5%` (`0.035`) |
| `1M` | ~1 tuần (1 chương của tháng) | `2.0%` (`0.020`) | `3.5%` (`0.035`) |
| `3M` | 1 tháng (trong quý) | `4.0%` (`0.040`) | `6.5%` (`0.065`) |
| `1Y` | 1 tháng (trong năm) | `4.0%` (`0.040`) | `6.5%` (`0.065`) |

Từ `(return_pct, volatility)` so với `(trend_th, vol_th)` của `span` đó, mỗi chương nhận một `MovementCharacter` với bộ tham số cụ thể truyền vào `plan_markov_chords()`.

Vì `REGIME_BIAS` gốc khóa theo `root_step` và chỉ chứa 12 hợp âm diatonic (`CHORDS`), trong khi các hợp âm mượn (`BORROWED`: `D7`, `C7`, `A7`, `Fm`, `Gm`, `A♭`, `B♭`, `B♭7`, `E♭`, `Bm7♭5`, `E7`, `F♯°7`) nằm ngoài `REGIME_BIAS` (đang lấy fallback `0.08`), việc chỉnh bias theo chữ cái `root_step` sẽ làm `A7` đắt lên cùng với `Am` hoặc `D7` đắt lên cùng với `Dm`. Do đó, độ lệch bias của `character` được **gắn trực tiếp trên từng đối tượng `Chord`**, tách biệt nhóm `CHORDS` và nhóm `BORROWED`:

| `character` | Điều kiện | Điều chỉnh trên `CHORDS` (diatonic) | Điều chỉnh trên `BORROWED` (ngoài `REGIME_BIAS`, gốc `0.08`) | `seventh_tension_cost` | `single_bar_change_penalty` |
|---|---|---|---|---|---|
| `None` | Mặc định cho `1D` | Không chỉnh (giữ nguyên `REGIME_BIAS`) | Giữ nguyên `0.08` | `0.05` (mặc định) | `0.65` (mặc định) |
| `"rally"` | `return_pct >= +trend_th` | Giảm `0.08` cho `(C, Cmaj7, F, Fmaj7, G, G7)`; cộng `0.06` vào `(Am, Am7, Dm, Dm7, Em, Em7)` | Giảm `0.06` (còn `0.02`) cho `(D7, C7, A7)` | `0.05` | `0.60` |
| `"selloff"` | `return_pct <= -trend_th` | Giảm `0.08` cho `(Am, Am7, Dm, Dm7, Em, Em7)`; cộng `0.06` vào `(C, Cmaj7)` | Giảm `0.06` (còn `0.02`) cho `(Fm, Gm, Ab, Eb, Bm7b5, E7)` | `0.05` | `0.60` |
| `"volatile"` | `\|return_pct\| < trend_th` và `volatility >= vol_th` | Giữ nguyên theo root | Giữ nguyên `0.08` | `0.00` (ưu tiên hợp âm 7) | `0.45` (đổi hợp âm linh hoạt) |
| `"calm"` | `\|return_pct\| < trend_th` và `volatility < vol_th` | Giữ nguyên theo root | Giữ nguyên `0.08` | `0.08` (ưu tiên hợp âm 3) | `0.80` (giữ hợp âm ngân dài) |

*(Không sửa biến toàn cục `REGIME_BIAS`, `SEVENTH_TENSION_COST` hay `SINGLE_BAR_CHANGE_PENALTY`; `plan_markov_chords()` tra hàm `_chord_bias(chord, regime, character)` cho từng `Chord`).*

---

## 5. Kịch bản chuyển vùng giọng (Modulation) qua các chương

### 5.1. Nguyên tắc bước chuyển trên `KEY_RING` và phá hòa bằng âm chung (Tie-break)
Hai hợp âm ba trưởng khác nhau chỉ có tối đa 1 âm chung (ví dụ `C {0,4,7}` với `Bb {10,2,5}` hoặc `D {2,6,9}` có `0` âm chung), nên **không dùng ngưỡng lọc `>= 2` âm chung** để loại ứng viên.

Thay vào đó:
- Mỗi chương xác định một hoặc hai chỉ số ứng viên lân cận trên `KEY_RING` theo kịch bản cố định bên dưới (luôn khác rỗng).
- Khi có 2 ứng viên lân cận cần phân định (như nhánh `volatile` ở Chương II), chọn ứng viên có **số âm chung (`len(prev_pcs & next_pcs)`) lớn hơn** giữa chủ âm kết của chương trước và chủ âm mở của chương sau (ở concert pitch); nếu số âm chung bằng nhau, lấy ứng viên đứng trước trong danh sách ưu tiên.

### 5.2. Bản `1D` và `1W`
- **`1D`:** Giữ nguyên ở giọng `C` (`C_KEY`), không dùng `stock_home_key` trong đợt này.
- **`1W`:** Có 1 chương duy nhất, dùng `stock_home_key(symbol)` xuyên suốt cả tuần.

### 5.3. Bản `1M` (Sonata 4 chương: `I – II – III – IV`) và `3M` (Concerto 3 chương: `I – II – III`)
Gọi `idx_home` là chỉ số của `Home Key` trong `KEY_RING` (`0..4`):

1. **Chương I (Trình bày):** Luôn ở `Home Key` (`idx_i = idx_home`).
2. **Chương II (Chậm / Ballad):** Chọn `idx_ii` khác `idx_home`:
   - Tại hai mép vòng (chỉ có một láng giềng sát cạnh nên không phụ thuộc `character`):
     - Nếu `idx_home == 0` (`Eb`, `+3` bán âm): `idx_ii = 1` (`Bb`, `-2` bán âm — cữ âm hạ xuống một quãng 4 ấm và trầm hơn).
     - Nếu `idx_home == 4` (`A`, `-3` bán âm): `idx_ii = 3` (`D`, `+2` bán âm — cữ âm nâng lên một quãng 4 sáng và mở hơn).
   - Tại các vị trí giữa (`idx_home ∈ {1, 2, 3}`), hai láng giềng là `left = idx_home - 1` (nhiều dấu giáng hơn) và `right = idx_home + 1` (nhiều dấu thăng hơn):
     - Nếu chương II là `"selloff"` hoặc `"calm"`: chọn `idx_ii = left`.
     - Nếu chương II là `"rally"`: chọn `idx_ii = right`.
     - Nếu chương II là `"volatile"`: so sánh số âm chung giữa `(left, right)` với chủ âm kết của Chương I; nếu hòa thì chọn `left`.
3. **Chương III của `1M` (Scherzo):** Chọn `idx_iii` **khác cả `idx_home` lẫn `idx_ii`** để Chương II và Chương III không bao giờ trùng giọng:
   - Nếu `idx_home ∈ {1, 2, 3}`: lấy láng giềng đối diện với `idx_ii` (`idx_iii = right if idx_ii == left else left`).
   - Nếu `idx_home == 0` (`Eb`, lúc này `idx_ii == 1` là `Bb`): bước tiếp vào `idx_iii = 2` (`C`).
   - Nếu `idx_home == 4` (`A`, lúc này `idx_ii == 3` là `D`): bước tiếp vào `idx_iii = 2` (`C`).
   *(Kết quả: với mọi `Home Key` trong 5 giọng, ba chương `I – II – III` của `1M` luôn đi qua 3 vùng giọng hoàn toàn phân biệt).*
4. **Chương cuối (Finale — Chương IV của `1M`, Chương III của `3M`):**
   - Luôn quay về **`Home Key`** (`idx_home`).
   - **Cờ `outro_override` (`Literal["major", "minor"] | None`) trên Coda của Finale:**
     - Mặc định section `outro` dùng chủ âm của phrase cuối (`uptrend` và `sideway` vốn đã kết ở bậc `I` trưởng; chỉ `downtrend` kết ở bậc `vi` thứ).
     - **Triumph (`outro_override = "major"`):** Khi **Chương I có `character == "selloff"`** và **Chương Finale có `character == "rally"`**, ép `allowed_tonics` của section `outro` về chủ âm Trưởng (`C`, `Cmaj7` trong hệ quy chiếu) ngay cả khi phrase cuối của Finale đang ở `downtrend`.
     - **Tragedy (`outro_override = "minor"`):** Khi **Chương I có `character == "rally"`** và **Chương Finale có `character == "selloff"`**, ép `allowed_tonics` của section `outro` về chủ âm Thứ (`Am`, `Am7` trong hệ quy chiếu) ngay cả khi phrase cuối của Finale đang ở `uptrend` hoặc `sideway`.
     - Các trường hợp còn lại: `outro_override = None`.

### 5.4. Bản `1Y` (Tổ khúc 12 tháng theo thứ tự thời gian thực)
- **Chương đầu tiên (`position == 0`)** và **Chương cuối cùng (`position == len(movements) - 1`)** luôn đặt ở **`Home Key`** (`idx_home`).
- **Các chương ở giữa (`0 < position < len - 1`):**
  - Ba quý đầu đi qua **3 vùng giọng hoàn toàn phân biệt** (cùng cấu trúc với Chương I – II – III của `1M`), và Quý 4 quay về **`idx_home`** để mùa cuối chuẩn bị cho Finale:
    - Quý 1 (`season == 0`): `base = idx_home`
    - Quý 2 (`season == 1`): `base = 1 if idx_home == 0 else (3 if idx_home == 4 else idx_home + 1)`
    - Quý 3 (`season == 2`): `base = 2 if idx_home in (0, 4) else idx_home - 1`
    - Quý 4 (`season == 3`): `base = idx_home`

  | `Home Key` (`idx_home`) | Quý 1 (`season 0`) | Quý 2 (`season 1`) | Quý 3 (`season 2`) | Quý 4 (`season 3`) |
  |---|---|---|---|---|
  | `Eb` (`0`) | `0` (`Eb`) | `1` (`Bb`) | `2` (`C`) | `0` (`Eb`) |
  | `Bb` (`1`) | `1` (`Bb`) | `2` (`C`) | `0` (`Eb`) | `1` (`Bb`) |
  | `C` (`2`) | `2` (`C`) | `3` (`D`) | `1` (`Bb`) | `2` (`C`) |
  | `D` (`3`) | `3` (`D`) | `4` (`A`) | `2` (`C`) | `3` (`D`) |
  | `A` (`4`) | `4` (`A`) | `3` (`D`) | `2` (`C`) | `4` (`A`) |

  - Bên trong mỗi quý, nếu một tháng ở giữa chuỗi có `character == "selloff"` và `base > 0`, lùi 1 nấc `base - 1`; nếu có `character == "rally"` và `base < 4`, tiến 1 nấc `base + 1`.

---

## 6. Cache & Fingerprint (`audio.py`, `span.py`)

Khóa `scale_fingerprint` trên `PreparedMovement` bao gồm đầy đủ **giọng (`key.name`), bản sắc (`character`), cờ coda (`outro_override`), và biên giá (`low`, `high`)**:

```python
f"{self.key.name}-{self.character or 'std'}-{self.outro_override or 'none'}-{low:.2f}-{high:.2f}"
```

Đồng thời tăng `SPAN_REVISION = "2"` trong `backend/app/sonify/audio.py` để tự động dọn các file span cũ. Bản `1D` giữ nguyên `RECAP_REVISION = "9"`.

---

## 7. Thứ tự triển khai (Từng bước kiểm thử độc lập)

1. **Bước 1 — `keys.py`, trần/sàn register & `musicxml.py`:**
   - Tạo `backend/app/sonify/keys.py` với `KEY_RING = (EB_KEY, BB_KEY, C_KEY, D_KEY, A_KEY)`, hàm `transpose_chord(chord, key)` và `midi_to_spelled_pitch(midi, key, harmony)`.
   - Hạ trần / nâng sàn theo `key.semitones` trong `render.py`, `phrasing.py`, `jazz.py`.
   - Cập nhật `musicxml.py` để ghi `<fifths>{score.key.fifths}</fifths>` và dịch cao độ + hợp âm một lần duy nhất lúc xuất XML.
   - Viết unit test kiểm tra cả 5 giọng với toàn bộ 12 hợp âm thuận + 12 hợp âm mượn: không nốt nào sai chính tả, không nốt nào vượt trần hay tụt dưới `G3` của Violin/Sax, MuseScore đọc đúng hóa biểu.
2. **Bước 2 — `MovementCharacter` và `outro_override` trong `form.py`:**
   - Thêm hàm tạo bảng bias cục bộ theo `character` (`None`, `"rally"`, `"selloff"`, `"volatile"`, `"calm"`), tham số `single_bar_change_penalty`, và `outro_override` trong `plan_markov_chords()`.
   - Kiểm thử: khi `character=None` và `outro_override=None`, đầu ra của `plan_slots()` trùng khít 100% với bản 1D hiện tại.
3. **Bước 3 — Gắn `Home Key` & Chuyển vùng giọng `1W / 1M / 3M / 1Y` trong `span.py`:**
   - Áp dụng `stock_home_key(symbol)` (chuẩn hóa `.strip().upper()` trước `zlib.crc32`).
   - Áp dụng quy tắc chọn giọng trên `KEY_RING` cho `1W`, `1M`, `3M`, `1Y`, đảm bảo `I – II – III` của `1M` luôn phân biệt ở cả 2 mép `Eb` và `A`, và cập nhật `scale_fingerprint` + `SPAN_REVISION = "2"`.
4. **Bước 4 — Nhãn giọng trên UI (`SpanRecap.tsx`):**
   - Thêm `keyLabel` (`"Mi♭"`, `"Si♭"`, `"Đô"`, `"Rê"`, `"La"`) vào `SpanMovementResponse` để hiển thị cạnh nhãn chương khi phát.
