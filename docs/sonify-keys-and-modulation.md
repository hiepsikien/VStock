# Giọng gốc, chuyển giọng và bản sắc hợp âm theo cổ phiếu & chương

Kế hoạch bước tiếp theo sau `docs/sonify-long-form.md`: mở rộng hệ thống từ một giọng cố định (`C major / A minor`) sang bộ **vùng giọng trong biên độ dịch ±3 bán âm**, cho phép **chuyển vùng giọng giữa các chương**, và **điều phối màu sắc hòa âm theo tính chất cổ phiếu cũng như nội dung từng chương** mà không làm lệch register nhạc cụ hay đổi hành vi bản 1D.

---

## 1. Nguyên tắc cốt lõi: Soạn trên bậc âm (hệ C), chỉ dịch một lần khi xuất MusicXML

Toàn bộ engine hiện tại (`form.py`, `phrasing.py`, `jazz.py`, `minimalist.py`, `render.py`) đang giải bài toán hòa âm và giai điệu trên **thang 7 bậc diatonic + 12 hợp âm mượn** lấy `C` (`MIDI 60`) làm bậc `I` và `A` (`MIDI 57`) làm bậc `vi`.

1. **Mọi phép tính nội bộ và `Score` giữ nguyên trên hệ quy chiếu bậc `I = C` (`fifths = 0`)**:
   - Bậc thang âm, khoảng cách semitone, và ma trận chuyển tiếp `TRANSITIONS` + `_BORROWED_EDGES` là bất biến đối với phép dịch giọng.
   - `Score` vẫn lưu các `NoteEvent.midi` và `HarmonyEvent.chord` ở hệ C để các unit test hiện tại và việc kiểm tra contour hoạt động nguyên vẹn.
2. **Chỉ dịch một lần duy nhất trong `musicxml.py` (concert pitch)**:
   - Không dịch kép ở cả `Score` lẫn `musicxml.py`.
   - Khi xuất MusicXML, mọi `NoteEvent.midi` và `HarmonyEvent.chord` được dịch đi `key.semitones` bán âm. Các kèn Sax và Bass vẫn xuất ở concert pitch như hiện tại (Bass giữ `<octave-change>-1`).
   - Thẻ `<fifths>` trong `_attributes()` ghi `score.key.fifths`.
3. **Giữ nguyên trần register nhạc cụ sau khi dịch**:
   - Hiện tại các trần chạy trước khi xuất: Flute `FLUTE_CEILING = 88` (`E6`), Violin `VIOLIN_CEILING = 84` (`C6`), Alto Sax `SAX_CEILING = 80` (`A♭5`), Cello handback `CELLO_HANDBACK = 60` (`C4`).
   - Để phép dịch dương (`+2`, `+3` bán âm) không đẩy Flute vượt `E6`, Violin vượt `C6` hay Sax vượt `A♭5` khi phát thực tế, chỉ chọn các giọng có **`semitones` nằm trong `[-3, +3]`** và trừ `max(0, key.semitones)` vào trần của Flute/Violin/Sax lúc dựng nốt (hoặc gấp quãng 8 những nốt vượt trần sau khi cộng `key.semitones` đối với Flute/Violin).

---

## 2. Bộ 5 vùng giọng chuẩn (`KeySpec`)

Trên vòng quãng 5, mỗi nấc dấu hóa (`fifths`) cách nhau một quãng 4/5 ($\pm 7$ bán âm mod 12), không phải 1 bán âm. `F` (`+5` hoặc `-7` bán âm) và `G` (`+7` hoặc `-5` bán âm) nằm ngoài cửa sổ dịch `±3` bán âm nên nếu dịch toàn cục sẽ đẩy cữ đàn đi quá xa hoặc phải gấp quãng 8 từng nốt làm gãy contour giai điệu.

Do đó, bộ giọng chuẩn chốt ở **5 vùng giọng** vừa khít cả cửa sổ hóa biểu `fifths ∈ [-3, +3]` lẫn độ dịch chủ âm thực `semitones ∈ [-3, +3]`:

| Mã giọng (`key`) | Chủ âm bậc `I` (Trưởng) | Chủ âm bậc `vi` (Thứ song song) | `fifths` | `semitones` (dịch từ C) | Đặc tính âm sắc |
|---|---|---|---|---|---|
| `Eb` | E♭ Major | C minor | `-3` (3♭) | `+3` | Bề thế, kịch tính (bậc `I` hùng tráng ở E♭ trưởng, bậc `vi` sâu lắng ở Đô thứ) |
| `Bb` | B♭ Major | G minor | `-2` (2♭) | `-2` | Ấm, dày, giọng sở trường của Saxophone, Rhodes và dàn dây trầm |
| `C` | C Major | A minor | `0` | `0` | Trong sáng, trung tính, cân bằng |
| `D` | D Major | B minor | `+2` (2♯) | `+2` | Rực rỡ, sáng, giàu bồi âm dây (Violin/Cello) |
| `A` | A Major | F♯ minor | `+3` (3♯) | `-3` | Sắc nét nhưng đằm ở âm khu trầm (`-3` bán âm), hợp nhịp chuyển giao |

### Chuyển Trưởng ↔ Thứ trong cùng một hệ bậc
- **Không dùng "Thứ cùng chủ âm (Parallel Minor)" bằng phép dịch ở bước này**: Đô trưởng và Đô thứ khác tập hợp nốt; chỉ dịch bán âm không biến bậc `I` thành hợp âm thứ.
- Thay vào đó, mỗi `KeySpec` đã có sẵn cặp **Trưởng (`I`) – Thứ song song (`vi`)** do `regime` điều khiển (`uptrend`/`sideway` mở ở `I`, `downtrend` mở ở `vi`), cộng với các hợp âm mượn màu thứ đã có sẵn trong catalog (`Fm`, `Gm`, `A♭`, `E♭`, `Bm7♭5`, `E7`).
- Đáng chú ý: khi chuyển vùng giọng từ `C` (`C Major / A minor`) sang `Eb` (`E♭ Major / C minor`) trong một chương giảm điểm (`downtrend`), bậc `vi` của vùng `Eb` chính là **Đô thứ (`C minor`)** — đạt đúng hiệu ứng màu Đô thứ bằng chính hệ bậc hiện có mà không cần viết hệ thang thứ riêng.

---

## 3. Ánh xạ Giọng gốc (`Home Key`) cố định theo cổ phiếu

Mỗi cổ phiếu ánh xạ **1–1** vào một `Home Key` cố định (không phụ thuộc vào dữ liệu giá hay `rel_span`, và không dùng `hash()` mặc định của Python vốn đổi theo `PYTHONHASHSEED`):

| Nhóm cổ phiếu | Mã cố định trong bảng | Giọng gốc (`Home Key`) | Lý do âm nhạc |
|---|---|---|---|
| **Ngân hàng & Tài chính** | `VCB`, `BID`, `CTG`, `TCB`, `MBB`, `ACB`, `VPB`, `STB`, `HDB`, `TPB` | **`Bb`** (`B♭ Major / G minor`) | Âm khu trầm ấm (`-2` bán âm), chững chạc, hợp tiếng Sax và Piano. |
| **Công nghệ, Bán lẻ & Tăng trưởng** | `FPT`, `MWG`, `DGW`, `FRT`, `PNJ`, `CTR`, `CMG` | **`D`** (`D Major / B minor`) | Nhánh dấu thăng (`+2♯`, `+2` bán âm) làm dàn dây sáng, giàu năng lượng. |
| **Thép, BĐS, Chứng khoán (Chu kỳ cao)** | `HPG`, `HSG`, `NKG`, `VIC`, `VHM`, `VRE`, `NVL`, `KDH`, `SSI`, `VND`, `HCM`, `VCI` | **`Eb`** (`E♭ Major / C minor`) | Khi `uptrend` mở ở `E♭ Major` bề thế; khi `downtrend` rơi vào `C minor` kịch tính. |
| **Tiêu dùng, Phòng thủ, Điện – Khí** | `VNM`, `MSN`, `SAB`, `GAS`, `POW`, `REE`, `PLX`, `BVH` | **`C`** (`C Major / A minor`) | Trong trẻo, ổn định, cân bằng. |
| **Hạ tầng, Cảng biển, Hóa chất, Xuất khẩu** | `GMD`, `HAH`, `DGC`, `DPM`, `DCM`, `VHC`, `ANV`, `PTB` | **`A`** (`A Major / F♯ minor`) | Dấu hóa sáng (`+3♯`) nhưng cữ âm trầm (`-3` bán âm), vững và rõ nét. |
| **Các mã còn lại** | Ngoài danh sách trên | `KEY_ORDER[zlib.crc32(symbol.encode("utf-8")) % 5]` | Tất định (deterministic) tuyệt đối qua mọi lần khởi động server, đảm bảo một mã luôn giữ đúng một giọng. |

*Chế độ chọn giọng:* Bước đầu chạy hoàn toàn tự động (`Auto`) theo bảng trên để không làm phình bộ nhớ cache (`6 giọng × 3 biến thể`).

---

## 4. Ngưỡng theo `span` và Bản sắc chương (`MovementCharacter`)

Một mức biến động `2.5%` là lớn với 1 phiên (`1D`), vừa phải với 1 tuần (`1W`/`1M`), nhưng nhỏ với 1 tháng (`3M`/`1Y`). Vì vậy cả việc chọn `MovementCharacter` lẫn kịch bản chuyển giọng đều đọc chung `return_pct` và `volatility` của chương với **bảng ngưỡng theo `span`**:

- `return_pct = (bars[-1].close - bars[0].close) / bars[0].close`
- `volatility = (max_close - min_close) / min_close`

| `span` | Đơn vị 1 chương | Ngưỡng xu hướng `trend_th` (`|return_pct|`) | Ngưỡng biến động `vol_th` (`volatility`) |
|---|---|---|---|
| `1W` | 1 tuần (tối đa 5 phiên) | `2.0%` (`0.020`) | `3.5%` (`0.035`) |
| `1M` | ~1 tuần (1 chương của tháng) | `2.0%` (`0.020`) | `3.5%` (`0.035`) |
| `3M` | 1 tháng (trong quý) | `4.0%` (`0.040`) | `6.5%` (`0.065`) |
| `1Y` | 1 tháng (trong năm) | `4.0%` (`0.040`) | `6.5%` (`0.065`) |

Từ `(return_pct, volatility)` so với `(trend_th, vol_th)` của `span` đó, mỗi chương dài (`1W`–`1Y`) nhận một `MovementCharacter`:

1. **`None` (Mặc định cho `1D`):**
   - Bản 1 ngày giữ `character = None`. Không chỉnh sửa `REGIME_BIAS` hay `SINGLE_BAR_CHANGE_PENALTY`, đảm bảo âm thanh và test của `1D` không thay đổi.
2. **`"rally"` (`return_pct >= +trend_th`):**
   - Trong hàm tạo bias theo chương `_regime_bias_for(character)`, giảm nhẹ bias penalty cho hợp âm trưởng và giảm chi phí quá độ qua các secondary dominants (`D7 -> G`, `C7 -> F`, `A7 -> Dm`).
3. **`"selloff"` (`return_pct <= -trend_th`):**
   - Giảm bias cost cho chủ âm thứ (`Am`, `Am7`) và các hợp âm mượn nhóm thứ (`Fm`, `A♭`, `Bm7♭5`, `E7`).
4. **`"volatile"` (`|return_pct| < trend_th` và `volatility >= vol_th`):**
   - Bỏ `SEVENTH_TENSION_COST` (hợp âm 7 không bị phạt so với hợp âm 3) và truyền `single_bar_change_penalty = 0.45` (thấp hơn mức `0.65` mặc định) vào `plan_markov_chords` để nhịp hòa âm đổi nhanh hơn theo sóng giằng co.
5. **`"calm"` (`|return_pct| < trend_th` và `volatility < vol_th`):**
   - Tăng nhẹ `seventh_tension_cost = 0.08` khi xây bảng bias của chương để ưu tiên hợp âm ba trong trẻo (`C`, `F`, `Am`, `Dm`), và truyền `single_bar_change_penalty = 0.80` để giữ hợp âm ngân dài, tĩnh lặng.

*(Lưu ý kỹ thuật: Không gán lại hằng số toàn cục `SEVENTH_TENSION_COST` hay `SINGLE_BAR_CHANGE_PENALTY`; `plan_markov_chords()` nhận tham số hoặc đọc từ `spec.character` để tính bảng `bias` cục bộ cho lần chạy đó).*

---

## 5. Kịch bản chuyển vùng giọng (Modulation) và chọn giọng theo Pivot

Đặt thứ tự 5 vùng giọng theo chiều dấu hóa tăng dần (`fifths` từ `-3` đến `+3`):

```
KEY_RING = (Eb [-3], Bb [-2], C [0], D [+2], A [+3])
```

Mọi phép dịch chuyển vùng giọng giữa các chương đều đi trên chỉ số `idx ∈ {0, 1, 2, 3, 4}` của `KEY_RING` (dùng hàm kẹp hoặc bước lân cận hợp lệ trong `KEY_RING`), tuyệt đối không sinh ra `fifths` nằm ngoài 5 giọng này.

### 5.1. Luật chọn ứng viên giọng theo âm chung (`Pivot Key Selection`)
Khi chương $k$ kết thúc và chương $k+1$ có tập ứng viên giọng $C_{\text{keys}} \subseteq \text{KEY\_RING}$:
- Xác định hợp âm kết thực tế của chương $k$: vì outro khóa trên chủ âm của phrase cuối chương $k$, pitch classes ở concert pitch của hợp âm kết chương $k$ là `(tonic_pcs(last_regime_k) + key_k.semitones) mod 12`.
- Xác định chủ âm mở đầu (intro) của chương $k+1$ dưới mỗi giọng ứng viên $K' \in C_{\text{keys}}$: `(tonic_pcs(first_regime_{k+1}) + K'.semitones) mod 12`.
- Ưu tiên giọng $K'$ nào mà hai tập pitch classes trên có **từ 2 âm chung trở lên** (`len(prev_pcs & next_pcs) >= 2`). Nếu có nhiều ứng viên cùng đạt, chọn theo hướng kịch bản của chương dưới đây.

### 5.2. Bản `1D` và `1W`
- Chỉ có 1 chương: dùng trực tiếp `Home Key` (`K_home`) của cổ phiếu.

### 5.3. Bản `1M` (Sonata 4 chương: `I – II – III – IV`) và `3M` (Concerto 3 chương: `I – II – III`)
Gọi `idx_home` là vị trí của `Home Key` trong `KEY_RING`:

- **Chương I (Trình bày):** Luôn ở `Home Key` (`KEY_RING[idx_home]`).
- **Chương II (Chậm / Ballad):**
  - Nếu chương II có `character == "selloff"` (`return_pct <= -trend_th`): bước về phía nhiều dấu giáng hơn trên `KEY_RING` (`max(0, idx_home - 1)`, hoặc `idx_home + 1` nếu `idx_home == 0`, tức từ `Eb` sang `Bb`).
  - Nếu chương II là `"rally"`, `"calm"` hoặc `"volatile"`: chọn trong hai giọng lân cận `{idx_home - 1, idx_home + 1}` (nằm trong `[0..4]`) giọng nào thỏa điều kiện **Pivot $\ge 2$ âm chung** với hợp âm kết của Chương I.
- **Chương III của `1M` (Scherzo):**
  - Bước sang hướng đối diện trên `KEY_RING` (`min(4, idx_home + 1)`, hoặc `idx_home - 1` nếu `idx_home == 4`) để tạo độ sáng/độ căng trước khi về chương kết.
- **Chương cuối (Finale — Chương IV của `1M`, Chương III của `3M`):**
  - Luôn quay về **`Home Key`** (`KEY_RING[idx_home]`) để đóng khung tác phẩm.
  - **Hiệu ứng Coda kết (Triumph / Tragedy trên section `outro`):**
    - Không can thiệp vào regime của cả chương (để không xung đột với `plan_markov_chords`).
    - Chỉ riêng section `outro` (coda cuối chương Finale): nếu cả kỳ (`1M` hoặc `3M`) mở đầu giảm nhưng chương Finale có `character == "rally"`, section `outro` được phép kết trên chủ âm Trưởng (`I` — `C`/`Cmaj7` trong hệ quy chiếu) ngay cả khi phrase sát trước đó là `sideway`/`downtrend`. Ngược lại, nếu chương Finale là `"selloff"`, section `outro` kết trên chủ âm Thứ (`vi` — `Am`/`Am7`).

### 5.4. Bản `1Y` (Tổ khúc 12 tháng theo thứ tự thời gian thực)
Vì `prepare_year()` xếp tối đa 12 tháng gần nhất theo **thứ tự thời gian thực** (tháng 12 có thể nằm ở giữa chuỗi chứ không nhất thiết là chương cuối):
- **Chương đầu tiên (`position == 0`)** và **Chương cuối cùng (`position == len(movements) - 1`)** luôn đặt ở **`Home Key`** (`idx_home`), đảm bảo cả tổ khúc mở và khép đúng giọng gốc của cổ phiếu.
- **Các chương ở giữa (`0 < position < len - 1`):**
  - Mỗi quý lịch (`season = (day.month - 1) // 3`) có một độ lệch bước nhỏ `season_offset` quanh `idx_home`, được kẹp chặt trong `[0, 4]`:
    - Quý 1 (`season == 0`): `idx_home`
    - Quý 2 (`season == 1`): `min(4, idx_home + 1)` (nếu `idx_home == 4` thì `3`)
    - Quý 3 (`season == 2`): `max(0, idx_home - 1)` (nếu `idx_home == 0` thì `1`)
    - Quý 4 (`season == 3`): chọn giữa `idx_home` và giọng lân cận theo điều kiện Pivot với chương trước.
  - Bên trong một mùa, tháng nào có `character == "selloff"` lùi 1 bước về phía giáng `max(0, season_idx - 1)` để tạo độ tối tương phản.

---

## 6. Cache & Fingerprint (`audio.py`, `span.py`)

Vì âm thanh của một chương giờ phụ thuộc vào:
1. Chuỗi nến (`candle_count`, `min_close`, `max_close`)
2. Giọng của chương (`key.name`)
3. Bản sắc hòa âm (`character`)
4. Hợp âm kết của chương (`outro_override` nếu là Finale)

`scale_fingerprint` trên `PreparedMovement` sẽ bao gồm đầy đủ các thành phần này:

```python
f"{self.key.name}-{self.character or 'std'}-{low:.2f}-{high:.2f}"
```

Đồng thời tăng `SPAN_REVISION = "2"` trong `backend/app/sonify/audio.py` để tự động dọn các file span cũ chưa có giọng mới. Bản `1D` (`RECAP_REVISION = "9"`) giữ nguyên hoặc chỉ tăng khi bật `stock_home_key` cho 1D.

---

## 7. Thứ tự triển khai (Từng bước kiểm thử độc lập)

1. **Bước 1 — `keys.py` & `musicxml.py` (Chính tả & Dịch giọng khi xuất):**
   - Tạo `backend/app/sonify/keys.py` với 5 `KeySpec` (`Eb`, `Bb`, `C`, `D`, `A`), hàm `transpose_chord(chord, key)` và `midi_to_spelled_pitch(midi, key, harmony)`.
   - Cập nhật `musicxml.py` để ghi `<fifths>{score.key.fifths}</fifths>` và dịch cao độ + hợp âm một lần duy nhất lúc xuất XML; giữ trần nhạc cụ an toàn khi `key.semitones > 0`.
   - Viết unit test kiểm tra cả 5 giọng với toàn bộ 12 hợp âm thuận + 12 hợp âm mượn: không nốt nào sai chính tả hoặc lệch quãng 8, MuseScore đọc đúng hóa biểu.
2. **Bước 2 — `MovementCharacter` trong `form.py`:**
   - Thêm hàm tạo bảng bias theo `character` (`None`, `"rally"`, `"selloff"`, `"volatile"`, `"calm"`) và tham số `single_bar_change_penalty` trong `plan_markov_chords()`.
   - Kiểm thử: khi `character=None`, đầu ra của `plan_slots()` trùng khít 100% với bản 1D hiện tại.
3. **Bước 3 — Gắn `Home Key` cố định & Chuyển giọng các chương trong `span.py`:**
   - Áp dụng `stock_home_key(symbol)` dùng `zlib.crc32` cho các mã ngoài bảng.
   - Áp dụng quy tắc chọn giọng theo `KEY_RING` + Pivot $\ge 2$ âm chung cho `1M`, `3M`, `1Y`, và cập nhật `scale_fingerprint` + `SPAN_REVISION`.
4. **Bước 4 — Nhãn giọng trên UI (`SpanRecap.tsx`):**
   - Thêm `keyLabel` vào `SpanMovementResponse` (ví dụ `"Si♭ Trưởng"`, `"Đô Thứ"`) để hiển thị cạnh tên chương khi phát.
