# Dynamic và Cân bằng Âm lượng cho Giao hưởng & 12 Bộ Nhạc cụ

Kế hoạch này giải quyết hai bài toán đi liền nhau:
1. **Biểu cảm & phản ánh chuyển động thị trường (Market Movement)**: Đưa Flute (`P5`), Piano (`P3`) và Bass (`P4`) của Giao hưởng vào chung một hệ thống động lực học 3 tầng (Đà giá trong câu × Thanh khoản `p–f` × Tính cách phiên `BarGroove`), tương thích với cơ chế phát thực tế của MuseSounds trong MuseScore 4.
2. **Cân bằng âm lượng (Volume Balance) giữa các bè và trên toàn bộ 12 bộ nhạc cụ**: Loại bỏ tiếng Piano ẩn đánh chồng từ thẻ `<harmony>`, dọn dải tần trầm để Bass không đè Cello, và chuẩn hóa bảng gain `_VOICE_VOLUME_DB` trong `audio.py` cho tất cả 12 bộ nhạc cụ (`classic`, `wood`, `brass`, `soul`, `organ`, `mallet`, `guitar`, `breath`, `choir`).

---

## 1. Nguyên lý phát thực tế của MuseScore 4 + MuseSounds

Thực nghiệm xuất WAV qua `musescore_export` trên MuseScore 4.7.5 với thư viện MuseSounds (tính từ `0.0s` để bắt trọn transient đầu phách) cho thấy các quy luật vật lý của bộ sampler mà thiết kế phải bám sát:

1. **Cách MuseSounds phản ứng với `<direction><dynamics>`, `<wedge>` (lớp chính) và `<note dynamics="...">` (lớp phụ)**:
   - **Nhóm chỉ nghe chữ `<dynamics>` và `<wedge>`, bỏ qua 100% `<note dynamics="...">`**: Gồm cả các thư viện hơi, dây, đồng, hợp xướng (`Flute 1`, `Piccolo`, `Violins 1`, `Cellos`, `Oboe`, `Clarinet`, `Trumpet`, `Trombone`, `French Horns a6`, `Tuba`, `Contrabassoon`) **lẫn `Piano` (`Muse Keys`) và `Harp` (`Muse Harp`)**:
     - Thực nghiệm giữ nguyên `<p/>` và đổi `<note dynamics>` từ `51.11` (`vel=46`) lên `106.67` (`vel=96`):
       - `Piano`: đứng yên ở `-29.2 dB` Peak / `-46.2 dB` RMS; khi đổi chữ sang `<mp/>` tăng lên `-23.1 dB` Peak / `-40.2 dB` RMS (`+6.0 dB`), sang `<mf/>` tăng lên `-17.1 dB` Peak / `-34.6 dB` RMS (`+11.6 dB`).
       - `Harp`: đứng yên ở `-45.6 dB` Peak / `-64.1 dB` RMS; sang `<mp/>` tăng lên `-43.1 dB` Peak / `-61.6 dB` RMS, sang `<mf/>` tăng lên `-37.4 dB` Peak / `-55.4 dB` RMS.
       - `French Horns a6`: đứng yên ở `-24.3 dB` Peak / `-33.7 dB` RMS; sang `<mp/>` lên `-21.2 dB` Peak / `-30.7 dB` RMS, sang `<mf/>` lên `-18.2 dB` Peak / `-27.7 dB` RMS.
     - Do đó, `Piano`, `Harp` và `French Horns a6` **hoàn toàn đồng nhất về cơ chế phát trên MuseSounds** (chỉ nghe chữ in và `<wedge>`, không bao giờ bị cộng đúp hai lớp).
   - **Nhóm nhạc cụ gõ kim loại (`Glockenspiel`, `Crotales`, `Vibraphone`) nghe cả hai lớp**:
     - Trên `Glockenspiel` (ở `C6`): giữ `<p/>` và tăng `vel` từ `46` lên `96` làm Peak tăng từ `-45.7 dB` lên `-38.4 dB` (`+7.3 dB`); đổi chữ từ `<p/>` sang `<mp/>` ở cùng `vel=46` làm Peak tăng lên `-33.3 dB` (`+12.4 dB`).
   - **Hiệu lực của `<wedge>` trần (không có chữ đích)**:
     - Trên `Flute 1` (ở `C6`): `<mp/>` phẳng phát ở `-37.4 dB` Peak / `-47.9 dB` RMS; `<mp/>` kèm `<wedge type="crescendo">` trần (không in `<mf/>` ở cuối) vọt lên **`-25.4 dB` Peak / `-38.5 dB` RMS** (`+12.0 dB` Peak / `+9.4 dB` RMS), khớp sát với trường hợp có in `<mf/>` ở cuối (`-25.3 dB` Peak / `-38.2 dB` RMS). Một cặp `< >` không in `<mf/>` ở giữa đạt `-19.4 dB` Peak / `-33.1 dB` RMS.
   - **Vai trò của `NoteEvent.velocity` (`<note dynamics="...">`)**: Là lớp phụ bắt buộc cho bộ tổng hợp MS Basic / Fluid (trên Linux server và `minimalist classic`), cho `Glockenspiel`, và cho việc kiểm thử đường cong động lực học trên model `Score`. Còn để tai người nghe nhận ra sự thay đổi trên MuseSounds, thiết kế bắt buộc phải đi kèm **chữ `<dynamics>` hoặc `<wedge>`**.

2. **Thẻ `<harmony>` trên `P3` khiến MuseScore 4 tự tổng hợp thêm một Piano ẩn đánh chồng lên phách 1 (+6.2 dB RMS / +6.7 dB Peak)**:
   - Trong `score.mscx` sinh ra từ MusicXML, mỗi thẻ `<harmony>` biến thành phần tử `<Harmony><harmonyInfo>...</harmonyInfo></Harmony>`. Khi xuất WAV ở trạng thái mặc định, MuseScore 4 tự gõ thêm một hợp âm Piano đầy đủ chồng lên phách 1: trên một ô 4/4 `120 BPM` chỉ có `P3` đánh hợp âm `Cmaj7` ở `p`, bản có `<Harmony>` mặc định phát ở **`-35.5 dB` RMS (`-18.4 dB` Peak)**, trong khi bản thêm `<play>0</play>` vào `<Harmony>` hoặc xóa `<Harmony>` phát đúng tiếng thật của nốt viết ở **`-41.7 dB` RMS (`-25.1 dB` Peak)** (khớp tuyệt đối đến `0.0 dB`).
   - Ở bộ `symphony wood` (`Harp`) và `symphony brass` (`French Horns a6`), chính `<Harmony>` mặc định này đang phát ra tiếng Piano lạ đè lên tiếng đàn Harp và kèn Cor.

---

## 2. Ba tầng chuyển động thị trường trên các bè Giao hưởng

| Tầng chuyển động | Flute / P5 (`classic`, `wood`, `brass`) | Violin & Cello (`P1`, `P2`) | Piano / P3 (`classic`, `wood`, `brass`) | Bass / P4 (`classic`, `wood`, `brass`) |
|---|---|---|---|---|
| **1. Giá trong câu** (`phrase.rise`, đỉnh, `BREAKOUT`) | 1 nốt ngân dài $\ge 4$ móc nở `< >` ở giữa ngân; đoạn leo lên đỉnh chạy `< >` tới `span_apex`; vào ngay đỉnh lúc `peak == 80` mở `mf` rồi `>` | Giữ nguyên vòng cung `hairpins()` và `melody_parts()` hiện có; được tôn nổi nhờ Bass nhường dải tần và bảng `_VOICE_VOLUME_DB` | Hướng vuốt của câu fill (`Nở` khi câu lên, `Lắng` khi câu xuống) bằng **cả `<wedge>` ngắn (`comp_wedges`) lẫn nội suy velocity** | Gập mọi nốt Bass `>= C3 (48)` xuống một quãng 8 trên những ô Cello hát chính ($\ge \max(\text{nửa ô}, 2\text{ phách đen})$) |
| **2. Thanh khoản `p–f`** (`band_at`) | Band `mf`/`f` tại đỉnh hoặc đoạn có `BREAKOUT` nâng `peak = 80` (in chữ `mf`); band `p`/`mp` giữ `peak = 72` (giữ chữ `mp`, không nhảy lên `mf`) | Velocity và nốt nhấn phản ánh câu | Chữ in giường (`p` cho `p`/`mp`, `mp` cho `mf`/`f`), 4 bậc velocity (`46 / 54 / 62 / 68` cho MS Basic), và tay trái điểm gốc mỗi ô ở `f` | Mật độ tiết tấu từ tròn (`p`) tới 8 móc đơn (`f`), chữ in trần `mp` |
| **3. Tính cách phiên (`BarGroove`)** | `BREAKOUT` luôn nở tới chữ `mf` (`peak = 80`) | `selloff` nhường sớm vùng trung-trầm cho Cello | Đọc `chamber`, `trio_thin`, `half`, `rally`, `selloff`, `caesura`; gốc tay trái đánh mỗi ô khi `f` hoặc `rally` | Đọc `chamber`, `trio_thin`, `half`, `tresillo`, `selloff`, `rally`, `caesura` |

---

## 3. Flute (`P5`): State Machine cho chữ Dynamic, Hairpin và Velocity

Flute vào khi câu lên cao (`>= FLUTE_TRIGGER`), khi có `BREAKOUT`, hoặc khi nốt vượt trần violin (`violin_ceiling`). `_flute_and_violin_dovetail` ghi `yield_spans` và dựng vòng cung cho đúng đoạn `[span_start, sounding_end)` mà Flute hát.

### A. Định nghĩa chính xác các biến của một đoạn Flute `[span_start, sounding_end)`

1. **`span_apex` (tie-break khi có cao nguyên giá)**:
   - Lấy từ đường giá gốc `pitches[eighth]` (trước khi `flute_harmony_pitch` cộng quãng và gập trần `Mi6`), và **lấy móc đơn đầu tiên đạt giá trị cực đại** trong đoạn (đồng nhất với `Phrase.apex`):
     ```python
     span_apex = max(range(span_start, sounding_end), key=lambda e: (pitches[e], -e))
     ```
2. **Cờ `has_breakout` của đoạn và `run_has_breakout(f_run)`**:
   - Vì `colours = techniques(phrase, pitches, band_at)` đánh dấu `BREAKOUT` theo `r.start` của `phrase.runs` (đường giá giai điệu), trong khi `merged_flute_runs` được gộp theo cao độ hòa âm của sáo (biên `f_run.start` có thể không trùng `r.start`), cả đoạn và từng `f_run` kiểm tra `BREAKOUT` bằng **phép giao khoảng thời gian `[start, end)`**:
     ```python
     def overlaps_breakout(start: int, end: int) -> bool:
         return any(
             colours.get(r.start) == BREAKOUT
             for r in phrase.runs
             if r.end > start and r.start < end
         )

     has_breakout = overlaps_breakout(span_start, sounding_end)
     ```
3. **Mức `peak` của đoạn**:
   - Luôn tra `band_at` tại ô của `span_apex` gốc (`apex_bar = span_apex // epb`), bất kể đoạn thuộc hình thái nào:
     ```python
     peak = 80 if (has_breakout or band_at[span_apex // epb] in ("mf", "f")) else 72
     ```
4. **Ranh giới câu nối dây (`tie_first_in` / `held_over`)**:
   - Nếu `tie_first_in == True` (nốt đầu đoạn buộc nối từ cuối phrase trước), run đầu tiên (`r_i == 0`) là nốt nối dây (`tie_stop=True`), không phải tiếng đánh mới; mọi chữ dynamic in lại hoặc mở mới chỉ được đặt trên **run đầu tiên có tiếng đánh mới** (`first_attack`, tức run đầu tiên có `not (r_i == 0 and tie_first_in)`). Nếu cả đoạn chỉ có 1 run duy nhất và `tie_first_in == True` thì `first_attack = None`: đoạn này chỉ ngân nốt nối dây, không sinh chữ mới và không mở `<wedge>`.

### B. Thứ tự ưu tiên giữa `Glockenspiel` và 3 Hình thái của Flute

Với mỗi đoạn Flute có `sounding_end > span_start` và `first_attack is not None`, đặt `arc_start = first_attack.start`:

- **Nhánh A — Đoạn phẳng hoặc quá ngắn (`phrase.rise < MIN_RISE` hoặc `sounding_end - arc_start < WEDGE_MIN`)**:
  - Không sinh `<wedge>`.
  - Riêng `ensemble == "brass"` (`Glockenspiel`) khi `phrase.rise >= MIN_RISE` và `len(merged_flute_runs) == 1`: gán `velocity = peak`; chữ mở đoạn `start_marking = "mf"` nếu `peak == 80`, ngược lại `"mp"`.
  - Mọi trường hợp phẳng/ngắn khác: `start_marking = "mp"`, gán `velocity = 64`.

- **Nhánh B — Đoạn có độ dốc và đủ độ dài (`phrase.rise >= MIN_RISE` và `sounding_end - arc_start >= WEDGE_MIN`)**:
  Kiểm tra theo đúng thứ tự ưu tiên từ 1 đến 4 (trong đó **Hình thái 2 đứng trước Hình thái 1** để một nốt sáo ngân dài duy nhất luôn nở cân đối ở giữa hơi ngân, và **Hình thái 3 chỉ mở `"mf"` khi `peak == 80`** để câu yên `p`/`mp` không bị nhảy vọt lên `"mf"`):
  1. **Ưu tiên 1 — `Glockenspiel` 1 tiếng gõ (`ensemble == "brass"` và `len(merged_flute_runs) < 2`)**:
     - Không sinh `<wedge>` (nhạc cụ gõ kim loại tắt dần sau cú gõ).
     - Gán `velocity = peak`; `start_marking = "mf"` nếu `peak == 80`, ngược lại `"mp"`.
  2. **Ưu tiên 2 (Hình thái 2) — Một cao độ sáo ngân dài duy nhất (`len(merged_flute_runs) == 1` và `sounding_end - arc_start >= 4`)**:
     - Đặt đỉnh vào giữa hơi ngân: `eff_apex = arc_start + (sounding_end - arc_start) // 2`, `start_marking = "mp"`.
     - Sinh `wedges = hairpins(arc_start, sounding_end, eff_apex)` (luôn đủ $\ge 2$ móc mỗi bên nên luôn có đủ cặp `< >`).
     - Nếu `peak == 80`, in thêm chữ `"mf"` tại `eff_apex`.
  3. **Ưu tiên 3 (Hình thái 1) — Đoạn leo lên đỉnh (`span_apex - arc_start >= WEDGE_MIN`)**:
     - `eff_apex = span_apex`, `start_marking = "mp"`.
     - Sinh `wedges = hairpins(arc_start, sounding_end, eff_apex)` (gồm `crescendo` từ `arc_start` tới `eff_apex`, và `diminuendo` từ `eff_apex` tới `sounding_end` nếu `sounding_end - eff_apex >= WEDGE_MIN`).
     - Chỉ in thêm chữ `"mf"` tại `eff_apex` khi `peak == 80` **và** có cả 2 cạnh (`sounding_end - eff_apex >= WEDGE_MIN`). (Khi đoạn kết thúc ngay tại đỉnh chỉ có `crescendo` trần, thực nghiệm Mục 1 đã chứng minh bản thân `<wedge type="crescendo">` đã đẩy `Flute 1` lên đúng mức `-25.4 dB` Peak của `mf`).
  4. **Ưu tiên 4 (Hình thái 3) — Vào ngay tại đỉnh rồi đi xuống (`span_apex - arc_start < WEDGE_MIN`)**:
     - `eff_apex = arc_start`.
     - **Nếu `peak == 80` (thanh khoản `mf`/`f` hoặc có `BREAKOUT`)**:
       - Với `ensemble == "brass"` (`Glockenspiel`, vốn nghe cả chữ lẫn velocity): giữ `start_marking = "mp"` và mở `diminuendo` (`>`) từ `arc_start` tới `sounding_end` để chuỗi tiếng chuông giảm dần theo velocity mà không bị chữ `"mf"` kích vọt `+14 dB` ở đầu đoạn.
       - Với `classic` (`Flute 1`) và `wood` (`Piccolo`): yêu cầu `start_marking = "mf"` ngay tại `arc_start` (đón tiếp đỉnh cao trào từ Violin) rồi sinh `wedges = [_wedge_at(arc_start, "diminuendo"), _wedge_at(sounding_end, "stop")]`.
     - **Nếu `peak == 72` (thanh khoản `p`/`mp` và không có `BREAKOUT` — câu yên)**:
       - Giữ `start_marking = "mp"` và **không sinh `diminuendo` trần** (vì câu yên đang ở `mp`, mở `"mf"` sẽ làm sáo nhảy vọt bất thường, còn mở `diminuendo` trần từ `"mp"` sẽ làm sáo tụt xuống `"p"`). Velocity vẫn vuốt nhẹ từ `72` về `64` theo `span_swell`.

### C. State Machine duy nhất quản lý chữ in (`high_dynamics`), Bảng chuyển trạng thái và chống trùng ở `bar == 0`

`_flute_and_violin_dovetail` duy trì một biến trạng thái `effective_level: str = "mp"` (nhận `"mp"` khi kênh P5 đang đứng yên ở mức `mp` chuẩn, hoặc `"drifted"` khi kênh P5 vừa rời khỏi `mp` do chữ `"mf"` hoặc do một `<wedge>` mà mức kết thúc chưa được khóa bằng chữ `"mp"`):

```python
# Khởi tạo đầu bài (ứng với opening_dynamic = "mp" ở bar 0, beat 0.0):
effective_level = "mp"

def emit_flute_dynamic(eighth_pos: int, target_marking: str) -> None:
    nonlocal effective_level
    if effective_level == target_marking:
        return
    bar = eighth_pos // epb
    beat = (eighth_pos % epb) * 0.5
    flute_dynamics.append(
        DynamicEvent(bar=bar, marking=target_marking, sound=SOUND[target_marking], beat=beat)
    )
    effective_level = target_marking
```

**Bảng chuyển trạng thái `effective_level` cho cả 4 cách kết thúc một đoạn Flute**:

| Cách thực thi của đoạn Flute | Lệnh gọi `emit_flute_dynamic` trong đoạn | Giá trị `effective_level` sau khi kết thúc đoạn | Hệ quả ở đoạn Flute kế tiếp (có `first_attack`) |
|---|---|---|---|
| **1. Không có `<wedge>` và đứng ở `"mp"`**<br>*(Đoạn phẳng `rise < MIN_RISE`, đoạn `< WEDGE_MIN`, Hình thái 3 ở `peak == 72`, hoặc `Glockenspiel` 1 run ở `peak == 72`)* | `emit_flute_dynamic(arc_start, "mp")` | **`"mp"`** | Đoạn sau mở `"mp"` sẽ không in lặp `"mp"`; đoạn sau mở `"mf"` sẽ in `"mf"`. |
| **2. Không có `<wedge>` nhưng mở `"mf"`**<br>*(`Glockenspiel` 1 run với `rise >= MIN_RISE` và `peak == 80`)* | `emit_flute_dynamic(arc_start, "mf")` | **`"drifted"`** | Đoạn sau bắt buộc in lại `"mp"` (nếu `start_marking == "mp"`) hoặc in `"mf"` (nếu `start_marking == "mf"`). |
| **3. Có cặp `< >` cân bằng trên nền `"mp"`, không in `"mf"` ở đỉnh**<br>*(Hình thái 1 hoặc 2 với `peak == 72` và có đủ cả `crescendo` lẫn `diminuendo`)* | `emit_flute_dynamic(arc_start, "mp")` | **`"mp"`** | `crescendo` (+1) và `diminuendo` (-1) tự triệt tiêu về `"mp"` (giống `drift == 0` của Violin/Cello), đoạn sau mở `"mp"` không in thừa chữ. |
| **4. Mọi đoạn có `<wedge>` còn lại**<br>*(Gồm: **(4a)** Hình thái 1 kết thúc ngay tại đỉnh chỉ có `crescendo` trần; **(4b)** Hình thái 1 hoặc 2 có `peak == 80` in `"mf"` tại `eff_apex` rồi `diminuendo`; **(4c)** Hình thái 3 ở `peak == 80` mở `"mf"`/`"mp"` rồi `diminuendo`)* | • **(4a)**: `emit(arc_start, "mp")`<br>• **(4b)**: `emit(arc_start, "mp")` rồi `emit(eff_apex, "mf")`<br>• **(4c)**: `emit(arc_start, start_marking)` | **`"drifted"`** | Vì `"drifted"` khác cả `"mp"` lẫn `"mf"`, đoạn kế tiếp **luôn in tường minh** `start_marking` của nó (`"mp"` để reset về nền, hoặc `"mf"` nếu đoạn kế tiếp lại là Hình thái 3 ở `peak == 80`!). |

- **Lưu ý thực thi**: Bản thân lệnh `emit_flute_dynamic` gán `effective_level = target_marking` (`"mp"` hoặc `"mf"`), nên ở Trường hợp 2 và Trường hợp 4, **ngay sau khi xử lý xong đoạn phải có lệnh gán tường minh `effective_level = "drifted"`**.
- **Chống trùng ở `bar == 0, beat == 0.0` (chỉ áp dụng cho `P5` và `P3`)**: Trong `musicxml.py`, giữ nguyên `_opening_p` cho `P1` (Violin) và `P2` (Cello). Viết hàm `_opening_dynamic(dynamics, default)` chỉ dùng cho `P5` và `P3` của Giao hưởng: nếu phần tử đầu tiên của `dynamics` nằm tại `(bar=0, beat=0.0)`, dùng phần tử đó làm `opening_dynamic` của part và trả về `dynamics[1:]`, đảm bảo ô 1 không bao giờ có 2 thẻ `<dynamics>`.

### D. Công thức `span_swell(onset)` cho `NoteEvent.velocity`

- Với mỗi run `f_run` trong `merged_flute_runs` của đoạn có `phrase.rise >= MIN_RISE` và `first_attack is not None`, đặt `onset = max(arc_start, f_run.start)`:
  - Nếu `overlaps_breakout(f_run.start, f_run.end)`: `vel = peak` (`80`).
  - Ngược lại:
    - Nếu `onset <= eff_apex`: `s = 1.0 if eff_apex == arc_start else (onset - arc_start) / (eff_apex - arc_start)`
    - Nếu `onset > eff_apex`: `s = 1.0 - (onset - eff_apex) / max(1, sounding_end - eff_apex)`
    - `vel = round(64 + (peak - 64) * lift(phrase) * s)`
- Nếu `f_run` là run nối dây từ câu trước (`r_i == 0 and tie_first_in`) và câu hiện tại phẳng (`phrase.rise < MIN_RISE`), `vel = 64`.

---

## 4. Violin (`P1`), Cello (`P2`) và Bass (`P4`): Phạm vi giữ nguyên & Quy tắc Bass nhường Cello

### A. Giữ nguyên `melody_parts()` của Violin và Cello

- Giữ nguyên 100% logic `hairpins()`, `drift` và velocity của `melody_parts()` trong `backend/app/sonify/phrasing.py` để bảo toàn toàn bộ các bài test hiện hữu.
- Violin và Cello được cải thiện độ rõ nét và cân bằng âm lượng thông qua:
  1. Bảng gain `_VOICE_VOLUME_DB` (`Violins 1: +2 dB`, `Cellos: +4 dB`, `Electric Bass: -6 dB`).
  2. Quy tắc Bass gập toàn bộ nốt `>= Đô3 (48)` xuống dưới `Đô3` ở các ô Cello hát chính dưới đây.

### B. Quy tắc chính xác để Bass (`P4`) nhường trọn dải tần `>= Đô3 (48)` cho Cello (`P2`)

1. **Ngưỡng xác định "ô có Cello hát chính" (`cello_lead_bars`)**:
   - Để các nốt dovetail lead-in / trail-out ngắn (1–2 móc đơn ở `4/4`, hoặc đoạn 3 móc đơn `MIN_VIOLIN_SPAN` ở `6/8`) không làm mất quãng 8 của Bass ở những ô Violin đang hát chính, một ô `bar` chỉ được tính vào `cello_lead_bars` khi tổng thời lượng các nốt có cao độ của Cello trong ô đó đạt **ít nhất `max(active_meter().quarter_beats / 2, 2.0)` phách đen** (tức tối thiểu `2.0` phách đen = `4` móc đơn trên mọi nhịp `4/4`, `3/4`, `6/8`):
     ```python
     min_cello_beats = max(active_meter().quarter_beats / 2, 2.0)
     cello_beats_by_bar: dict[int, float] = {}
     for note in cello.notes:
         if note.midi is not None:
             cello_beats_by_bar[note.bar] = cello_beats_by_bar.get(note.bar, 0.0) + note.duration_beats
     cello_lead_bars = {bar for bar, beats in cello_beats_by_bar.items() if beats >= min_cello_beats - 1e-6}
     ```
2. **Giữ toàn bộ nốt Bass nghiêm ngặt trong vùng `Đô2–Si2 (36–47)` khi `under_cello=True`**:
   - `chord.bass_midi` nằm trong `36..47` (`Đô2..Si2`), nhưng khi gốc hợp âm từ `Fa2 (41)` đến `Si2 (47)`, cả bậc `OCTAVE` (`chord.bass_midi + 12 = 48..59`) lẫn bậc `FIFTH` (`fifth_above_bass(chord) = 48..54`, tức `Đô3..Fa♯3`) đều vươn lên vùng `Đô3–Si3` của Cello!
   - Do đó, khi `under_cello == True`:
     - Trong `_bass_pattern`: thay bước `OCTAVE` bằng `ROOT` (cùng nhánh với `groove.selloff`).
     - Trong `_bass_bar(chord, marking, bar, *, under_cello: bool = False)`: nếu `under_cello` là `True` và cao độ `midi` của bất kỳ nốt Bass nào vẫn `>= 48` (`Đô3`, xảy ra ở bậc `FIFTH` của các hợp âm `F, G, Ab, A, Bb, B`), hạ nốt đó về `chord.bass_midi` (hoặc `midi - 12` khi `midi - 12 >= 36`):
       ```python
       def _under_cello_ceiling(midi: int, root: int) -> int:
           if midi < 48:
               return midi
           return midi - 12 if midi - 12 >= 36 else root
       ```
   - Nhờ vậy, trên mọi ô Cello hát chính (kể cả khi thanh khoản ở `mf` hay `f`), 100% các nốt của Bass đều nằm gọn trong `36..47` (`Đô2–Si2`), nhường sạch quãng `>= Đô3 (48)` cho Cello.

---

## 5. Piano (`P3`): Plumbing hàm, Chữ giường, `<wedge>` + Nội suy cho Fill và `<Harmony><play>0</play>`

### A. Tắt phát tiếng Piano ẩn của `<harmony>` trong `.mscz` và hành vi ở đường MS Basic

1. **Thao tác XML trên `score.mscx` trong `_assign_installed_sounds` (`backend/app/sonify/audio.py`)**:
   - Trong file `.mscz` của MuseScore 4, cấu trúc XML của `score.mscx` đặt `<Harmony>` bên trong `<Score>/<Staff>/<Measure>/<voice>/<Harmony>`:
     ```xml
     <Harmony>
       <harmonyInfo>
         <name>maj7</name>
         <root>14</root>
       </harmonyInfo>
       <eid>...</eid>
     </Harmony>
     ```
   - Để **không làm thay đổi định dạng XML gốc của `score.mscx`** (tránh mọi rủi ro do `ElementTree.tostring` đổi khoảng trắng, thứ tự thuộc tính hay header của MuseScore 4), hàm `_mute_mscx_harmony(mscx_bytes: bytes) -> bytes` dùng phép thay thế chuỗi/regex chính xác trên từng khối `<Harmony>...</Harmony>` chưa có `<play>` (sau khi đã xác thực XML hợp lệ):
     ```python
     _HARMONY_BLOCK = re.compile(r"<Harmony\b[^>]*>.*?</Harmony>", re.DOTALL)

     def _mute_mscx_harmony(mscx_bytes: bytes) -> bytes:
         try:
             text = mscx_bytes.decode("utf-8")
         except UnicodeDecodeError:
             return mscx_bytes
         def _inject(match: re.Match[str]) -> str:
             block = match.group(0)
             if "<play>" in block:
                 return re.sub(r"<play>\s*[^<]*\s*</play>", "<play>0</play>", block)
             return block.replace("</Harmony>", "<play>0</play></Harmony>", 1)
         updated = _HARMONY_BLOCK.sub(_inject, text)
         return updated.encode("utf-8") if updated != text else mscx_bytes
     ```
   - Thực nghiệm ở Mục 1 đã chứng minh đúng chuỗi thay thế này hạ mức phát của `P3` từ `-35.5 dB` RMS xuống `-41.7 dB` RMS (bằng hệt khi xóa `<Harmony>`). Đồng thời trên Jazz (`Suitcase Piano`, `Wurly 200A`, `Hammond Organ`) và Tối giản (`Harpsichord`, `Upright Piano`), việc tắt Piano ẩn giúp lộ rõ âm sắc thật của Rhodes/Wurly/Organ/Harpsichord mà trước đây bị tiếng Grand Piano của `<Harmony>` đánh đè lên.
2. **Hành vi ở đường fallback MS Basic (`use_config == True` hoặc `library == {}`)**:
   - Đường MS Basic chỉ chạy khi máy chủ Linux cấu hình `MUSESCORE_SOUNDFONT` (Fluid `.sf3`) hoặc máy không cài MuseSounds. Ở đường này, `musescore_export` gọi thẳng `mscore -o out.wav in.musicxml` mà không tạo `.mscz`, nên chúng ta **chấp nhận giữ nguyên hành vi MS Basic hiện tại** (không thêm bước convert `.mscz` thứ hai làm tăng gấp đôi thời gian CPU trên server 2-vCPU).

### B. Plumbing cho Piano (`_right_hand`, `left_hand`, `fills`), `<wedge>` trên Fill và xử lý Fill vượt vạch ô

Vì thực nghiệm Mục 1 chứng minh cả `Piano`, `Harp` và `French Horns a6` trong MuseSounds đều chỉ nghe chữ `<dynamics>` và `<wedge>`, kế hoạch kết hợp **chữ in + `<wedge>` ngắn trên câu Fill (`comp_wedges`)** cho MuseSounds, song song với **4 bậc `PIANO_VELOCITY` + nội suy velocity** cho MS Basic và model `Score`:

1. **`left_hand` trong `backend/app/sonify/phrasing.py`**:
   - Giữ nguyên chữ ký mặc định cho Jazz, thêm 2 tham số keyword-only tùy chọn:
     ```python
     def left_hand(
         slot: ChordSlot,
         *,
         velocity_at: dict[int, int] | None = None,
         every_bar_at: frozenset[int] = frozenset(),
     ) -> list[NoteEvent]:
     ```
   - Khi `velocity_at is None` và `every_bar_at` rỗng (khi `jazz.py` gọi `left_hand(slot)`): hành vi giữ nguyên 100% (`velocity=None`, đánh mỗi 2 ô).
   - Khi `render.py` (nhánh `symphony`) gọi: truyền `velocity_at=bed_velocity_by_bar` và `every_bar_at=dense_left_bars` (gồm các ô có `eff_band == "f"` hoặc `groove_at(bar).rally`, trừ `slot.section == "outro"` vẫn chỉ đánh ở `offset == 0`).
2. **Hạ band theo Groove (`effective_comp_band`) và bảng `PIANO_VELOCITY` trong `dynamics.py`**:
   - Hàm `effective_comp_band(band: str, bar: int | None = None) -> str` áp dụng đúng 3 nhánh của `_bass_pattern`:
     - `groove.chamber` $\rightarrow$ `"p"`
     - `groove.trio_thin` $\rightarrow$ `{"f": "mf", "mf": "mp", "mp": "p", "p": "p"}[band]`
     - `groove.half` và `band == "mp"` $\rightarrow$ `"p"`
   - `piano_marking(eff_band)` trả về `"p"` cho `"p"/"mp"`, và `"mp"` cho `"mf"/"f"`.
   - `PIANO_VELOCITY = {"p": 46, "mp": 54, "mf": 62, "f": 68}`.
3. **Nâng cấp `_right_hand` trong `render.py` (kèm xử lý Fill vượt qua vạch ô nhịp)**:
   - Giữ nguyên hàm `fills(cadences, chord_at)` và hằng `FILL_VELOCITY = 64` trong `phrasing.py` để Jazz và các test gọi trực tiếp `fills()` không bị ảnh hưởng.
   - Đổi chữ ký `_right_hand`:
     ```python
     def _right_hand(
         slots: tuple[ChordSlot, ...],
         cadence_fills: list[tuple[int, int, int]],
         piece_eighths: int = TOTAL_EIGHTHS,
         *,
         bed_velocity_at: dict[int, int] | None = None,
         bed_marking_at: dict[int, str] | None = None,
         phrases: tuple[Phrase, ...] = (),
     ) -> tuple[tuple[NoteEvent, ...], list[tuple[int, float, str]], list[WedgeEvent]]:
     ```
   - Khi gọi với mặc định `bed_velocity_at=None` (như trong `test_chamber_bar_drops_the_symphony_right_hand` tại `backend/tests/test_sonify_plan.py`, dòng 928 — test này sẽ được cập nhật thành `notes, *_ = _right_hand(...)`): guide tones giữ `velocity=None`, fill giữ `FILL_VELOCITY = 64`, trả về `(notes, [], [])`.
   - Khi gọi từ nhánh `symphony` của `_compose`:
     - Guide tones ở ô `bar` nhận `velocity = bed_velocity_at[bar]`.
     - Các tuple `(start, length, midi)` của `cadence_fills` sau khi lọc bỏ nửa sau ô `caesura` được gom lại theo từng `phrase` đóng (`phrase.closes` mà `start` nằm trong đuôi `phrase.cadence`).
     - Với mỗi nhóm fill của một cadence còn ít nhất 1 nốt sống:
       - **Hướng vuốt của nhóm fill**:
         - Lấy `first_bar = group[0][0] // epb`.
         - Nếu `groove_at(first_bar).selloff`: `"fall"` (`Lắng`).
         - Ngược lại, nếu `groove_at(first_bar).rally`: `"rise"` (`Nở`).
         - Ngược lại, so sánh `phrase.cadence.midi` với `phrase.runs[0].midi`: `>` thì `"rise"`, `<` thì `"fall"`, `==` thì `"flat"` (`Ngang`).
       - **Chữ fill và xử lý khi nhóm fill vượt qua vạch ô nhịp (`bar` $\rightarrow$ `bar + 1`)**:
         - Vì `fills()` luôn bỏ qua phách 1 (`eighth % epb != 0`), nếu một nhóm fill có các nốt ở cuối `bar` và tiếp tục ở `bar + 1` (từ `beat >= 0.5`), thì tại `(bar + 1, beat = 0.0)` guide tone của ô `bar + 1` vẫn đánh ở mức giường!
         - Do đó, ta tách nhóm fill theo từng ô `b` mà nó đi qua: tại nốt fill đầu tiên của mỗi ô `b` trong nhóm fill (`sub_start`), đặt một yêu cầu chữ fill `(b, (sub_start % epb) * 0.5, fill_mark_b)` với `fill_mark_b = "mp" if bed_marking_at[b] == "p" else "mf"`. Nhờ vậy, sau khi `(bar + 1, beat = 0.0)` hạ về chữ giường để đánh guide tone, ngay tại `(bar + 1, beat = 0.5)` chữ `fill_mark` được in lại để các nốt fill sau vạch ô vẫn vang đúng mức fill!
       - **Sinh `<wedge>` ngắn (`comp_wedges`) cho câu fill**:
         - Trên từng đoạn con trong cùng một ô `b` của nhóm fill (`sub_group` từ `sub_start` đến `sub_end = sub_group[-1][0] + sub_group[-1][1]`), nếu `len(sub_group) >= 2` và `sub_end - sub_start >= WEDGE_MIN (2)` và hướng là `"rise"` hoặc `"fall"`:
           - Thêm `_wedge_at(sub_start, "crescendo" if direction == "rise" else "diminuendo")` và `_wedge_at(sub_end, "stop")` vào `comp_wedges`.
       - **Công thức nội suy tuyến tính cho `NoteEvent.velocity` (`m = len(group)` runs)**:
         - Với `fill_mark == "mp"` (mốc `64`): `"rise"` đi từ `v_start = 58` đến `v_end = 66`; `"fall"` đi từ `v_start = 64` đến `v_end = 56`; `"flat"` giữ `64`.
         - Với `fill_mark == "mf"` (mốc `80`): `"rise"` đi từ `v_start = 74` đến `v_end = 80`; `"fall"` đi từ `v_start = 80` đến `v_end = 72`; `"flat"` giữ `80`.
         - Nếu `m == 1` hoặc hướng là `"flat"`: `vel_k = 64 if fill_mark == "mp" else 80`.
         - Nếu `m >= 2`: nốt thứ `k` (`0 <= k < m`) nhận `vel_k = round(v_start + (v_end - v_start) * k / (m - 1))`.
4. **Dựng `comp_dynamics` theo từng ô và từng phách**:
   - Duyệt `bar` từ `0` đến `musical_bars - 1`, theo dõi `current_comp_mark: str | None = None`:
     - Tại `beat = 0.0`: nếu ô `bar` có ít nhất một nốt kêu tại `beat == 0.0` (guide tone ở khuông 1 hoặc root ở khuông 2) và `bed_marking_at[bar] != current_comp_mark`:
       - Thêm `DynamicEvent(bar=bar, marking=bed_marking_at[bar], sound=SOUND[bed_marking_at[bar]], beat=0.0)`.
       - Cập nhật `current_comp_mark = bed_marking_at[bar]`.
     - Tại các sự kiện fill `(fill_bar, fill_beat, fill_mark)` rơi vào `bar` (đã sắp xếp theo `fill_beat`):
       - Nếu `fill_mark != current_comp_mark` (hoặc trước đó có `<wedge>` trên fill làm lệch mức):
         - Thêm `DynamicEvent(bar=bar, marking=fill_mark, sound=SOUND[fill_mark], beat=fill_beat)`.
       - Nếu ô `bar` có `<wedge>` của fill tại `fill_beat`, đặt `current_comp_mark = "drifted"` sau fill để tại `beat = 0.0` của ô kế tiếp có hợp âm đệm kêu, chữ giường luôn được in lại tường minh; nếu không có `<wedge>`, đặt `current_comp_mark = fill_mark`.

### C. Thứ tự ghi XML trong `_piano_part` và thuật toán cắt biên trong `daily_frame.py` & `movement_frame.py`

1. **Thứ tự ghi XML trong `_piano_part` (`backend/app/sonify/musicxml.py`)**:
   - Khi `score.variant == "symphony"`:
     - Lấy `comp_open, comp_rest = _opening_dynamic(score.comp_dynamics, PIANO_DYNAMIC)`.
     - Tại `bar == 0`, in `_dynamic(measure, comp_open)` ngay sau `_attributes(...)` (trước vòng lặp `for event in symbols[bar]: _harmony(...)`).
     - Với `bar > 0`, các sự kiện trong `comp_rest` của ô `bar` có `beat == 0.0` được in **trước vòng lặp `symbols[bar]`** (để chữ giường đầu ô đứng trước cả `<harmony>` lẫn guide tone trên mọi bộ tổng hợp, kể cả MS Basic).
     - Các sự kiện `comp_rest` có `beat > 0.0` và `score.comp_wedges` của ô `bar` được trộn theo `_direction_order` và xả bằng `flush(event.beat)` bên trong vòng lặp `staff == 1` (và `flush(score.bar_beats)` ở cuối `staff == 1`).
2. **`_curtain_comp` trong `movement_frame.py` (Khung động của Giao hưởng)**:
   - Chỉ gán `velocity = 49` trên danh sách `notes` của warm-up / `tag_bars` **trước khi gọi `with_rests(notes, ...)`** bên trong `_curtain_comp` (tuyệt đối không chạm vào `*_kept_comp(score.comp, body, cool)`).
3. **Cắt `high_wedges`, `high_dynamics`, `comp_wedges`, `comp_dynamics` trong `daily_frame.py` & `movement_frame.py`**:
   - **Hàm `_flute_body_wedges` (và áp dụng tương tự cho `comp_wedges`)**:
     - Khác với Violin/Cello (có nốt pedal ở warm-up), Flute và Piano tĩnh nghỉ hoàn toàn ở `0..body`. Do đó, nếu một `<wedge>` mở ở `bar < body` thì cả cạnh mở lẫn cạnh `stop` của nó đều phải bị loại bỏ (không để sót một `stop` mồ côi ở `bar >= body`). Chỉ giữ các cặp wedge mở tại `body <= wedge.bar < cool` (và nếu cạnh `stop` của nó vượt sang `>= cool` thì đóng tại `(cool - 1, beats)`).
   - **Hàm `_flute_body_dynamics(events, body, cool)`**:
     - Lấy `kept = [e for e in events if body <= e.bar < cool]`.
     - Vì mọi nốt và wedge của Flute trước `body` đã bị xóa và `P5` mở đầu bằng `"mp"` tại `bar == 0`, kênh `P5` khi bước vào `bar == body` đang ở mức `"mp"`.
     - Nếu `kept` không rỗng và `kept[0].marking == "mp"`, bỏ `kept[0]` (`kept = kept[1:]`) để không in trùng 2 chữ `"mp"`.
     - Ngược lại, nếu đoạn Flute đầu tiên trong `[body, cool)` bắt đầu tại `first_pos = (first_note.bar, first_note.beat)` mà trước khi cắt khung nó vốn đứng sau một đoạn ở `< body` từng để lại `"mf"` (khiến ở `[body, cool)` không có chữ `"mp"` tại `first_pos`), thì việc bỏ các đoạn `< body` vẫn hoàn toàn an toàn vì `P5` ở `bar == 0` đã là `"mp"` sẵn!
   - **Hàm `_piano_frame_dynamics` cho `comp_dynamics`**:
     - Suy chữ giường tại ô `body` từ sự kiện giường (`beat == 0.0`) gần nhất tại hoặc trước `body`:
       ```python
       bed_before = [e.marking for e in score.comp_dynamics if e.bar <= body and e.beat == 0.0]
       body_mark = bed_before[-1] if bed_before else "p"
       kept = [e for e in score.comp_dynamics if body <= e.bar < cool]
       ```
     - **Khung tĩnh**: Đầu bài (`bar == 0`) đã là `"p"`. Nếu `kept` có phần tử đầu tại `(bar == body, beat == 0.0)` với `marking == "p"` thì bỏ phần tử đó; nếu `kept` chưa có phần tử tại `(bar == body, beat == 0.0)` và `body_mark != "p"` thì chèn `DynamicEvent(bar=body, marking=body_mark, sound=SOUND[body_mark], beat=0.0)` vào đầu `kept`.
     - **Khung động**: Mở đầu bằng `DynamicEvent(bar=warm_start, marking="p", sound=SOUND["p"], beat=0.0)`, xử lý biên `(bar == body, beat == 0.0)` giống khung tĩnh, nối `kept`, và nếu `tag > 0` mà sự kiện cuối trước `cool` khác `"p"` thì nối thêm `DynamicEvent(bar=cool, marking="p", sound=SOUND["p"], beat=0.0)`.

---

## 6. Ma trận Cân bằng Âm lượng đầy đủ cho 12 Bộ Nhạc cụ (`_VOICE_VOLUME_DB`)

### A. Quy trình đo tái lập và Kiểm tra Peak từ `0.0s` (gồm cả Transient nhóm gõ)

Mọi con số RMS và Peak dBFS dưới đây được đo trên MuseScore 4.7.5 (`macOS`, thư viện MuseSounds `state = 1`) với fixture 6 ô nhịp `4/4` ở `120 BPM` (`2.0 giây/ô`), hòa âm `Cmaj7`:
- **Cửa sổ đo**: Lấy từ **`0.0s` đến `1.8s`** của từng ô `[b * 2.0, b * 2.0 + 1.8]` để bắt trọn cú gõ đầu tiên (attack transient) của các nhạc cụ gõ và dây gảy (`Glockenspiel`, `Crotales`, `Marimba`, `Harp`, `Acoustic Steel Plucked`).
- **Kiểm tra Headroom / Chống Clipping từ `0.0s`**:
  - `Glockenspiel` (`symphony brass` P5): Peak gốc từ `0.0s` là **`-40.0 dBFS`** $\rightarrow$ cộng `+10 dB` thành **`-30.0 dBFS`**.
  - `Crotales` (`minimalist mallet` P5): Peak gốc từ `0.0s` là **`-36.5 dBFS`** $\rightarrow$ cộng `+12 dB` thành **`-24.5 dBFS`**.
  - `Marimba` (`minimalist mallet` P1): Peak gốc từ `0.0s` là **`-38.6 dBFS`** $\rightarrow$ cộng `+10 dB` thành **`-28.6 dBFS`**.
  - `Harp` (`symphony wood` P3): Peak gốc từ `0.0s` là **`-34.5 dBFS`** $\rightarrow$ cộng `+8 dB` thành **`-26.5 dBFS`**.
  - Lưu ý về đặc tính âm học của `Glockenspiel` và `Crotales`: đây là các nhạc cụ chuông kim loại có sóng âm tắt nhanh sau cú gõ nên trị số RMS trung bình trên cả ô 2 giây thấp hơn kèn/marimba, nhưng **Peak transient ở đầu phách sau khi cộng `+10 / +12 dB` đạt `-30.0 dBFS` đến `-24.5 dBFS`**, ngang bằng với Peak của `Trumpet` (`-29.2 dBFS`) và `Marimba` (`-28.6 dBFS`), giúp tiếng chuông xuyên qua bản phối rất rõ mà vẫn còn hơn `24 dB` headroom chống clip.

### B. Cơ chế phân biệt `French Horns a6` (`symphony brass`) và `French Horn` (`ambient classic`)

Trong `backend/app/sonify/audio.py` (dòng 581–598 và 674–679), `_assign_installed_sounds` tra giọng MuseSounds ưu tiên theo `_xml_part_sounds(xml_path)` (đọc `<part-name>` trước, rồi mới tới `<instrument-name>` và `instrumentId`):
- Ở `("symphony", "brass")`: `ensemble.py` xuất `<part-name>French Horns a6</part-name>`, khớp trực tiếp với `_VOICE_BY_SOUND["French Horns a6"]` $\rightarrow$ gắn **`museName = "French Horns a6"` (`id = 96`)**.
- Ở `("ambient", "classic")`: `musicxml.py` xuất `<part-name>Swell</part-name>` và `<instrument-name>Horn in F</instrument-name>` $\rightarrow$ gắn **`museName = "French Horn"` (`id = 108`)**.
Hai giọng này hoàn toàn tách biệt nhau trong `audiosettings.json`, nên khóa `"French Horns a6": -5` chỉ hạ dàn 6 kèn cor của Giao hưởng Đồng mà giữ nguyên `French Horn` đơn của Ambient ở `0 dB`.

### C. Bảng Ma trận toàn bộ 12 Bộ Nhạc cụ (60 vị trí = 4 Variants × 3 Ensembles × 5 Parts)

Đối với `Clarinet in Bb`: đặt **`Clarinet in Bb: +3 dB`**, kết hợp với **`Oboe: +6 dB`** (ở `symphony wood`) và **`Tenors: +2 dB`, `Violas: +3 dB`** (ở `ambient choir`). Khi đó:
- Ở `symphony wood`: `Oboe` (P1, `-43.2 + 6 = -37.2 dB`) đứng trên `Clarinet in Bb` (P2, `-41.2 + 3 = -38.2 dB`) đúng `1.0 dB`.
- Ở `ambient choir`: `Clarinet in Bb` (P1, `-46.4 + 3 = -43.4 dB`) đứng trên cả `Tenors` (P2, `-46.4 + 2 = -44.4 dB`) lẫn `Violas` (P3, `-47.7 + 3 = -44.7 dB`).

| Variant & Ensemble | `P5` Điểm cao | `P1` Giai điệu | `P2` Bè giữa | `P3` Hòa âm / Đệm *(sau `<play>0</play>`)* | `P4` Bass / Drone |
|---|---|---|---|---|---|
| **1. `symphony` · `classic`** | `Flute 1`<br>RMS `-47.9` $\rightarrow$ **`+5 dB`** | `Violins 1`<br>RMS `-38.1` $\rightarrow$ **`+2 dB`** | `Cellos`<br>RMS `-40.6` $\rightarrow$ **`+4 dB`** | `Piano`<br>RMS `-41.9` $\rightarrow$ **`-2 dB`** | `Electric Bass`<br>RMS `-29.6` $\rightarrow$ **`-6 dB`** |
| **2. `symphony` · `wood`** | `Piccolo`<br>RMS `-34.6` $\rightarrow$ **`0 dB`** | `Oboe`<br>RMS `-43.2` $\rightarrow$ **`+6 dB`** | `Clarinet in Bb`<br>RMS `-41.2` $\rightarrow$ **`+3 dB`** | `Harp`<br>RMS `-52.4` $\rightarrow$ **`+8 dB`** | `Contrabassoon`<br>RMS `-49.5` $\rightarrow$ **`+10 dB`** |
| **3. `symphony` · `brass`** | `Glockenspiel`<br>Pk `-40.0` $\rightarrow$ **`+10 dB`** | `Trumpet`<br>RMS `-44.6` $\rightarrow$ **`+6 dB`** | `Trombone`<br>RMS `-50.2` $\rightarrow$ **`+8 dB`** | `French Horns a6`<br>RMS `-34.8` $\rightarrow$ **`-5 dB`** | `Tuba`<br>RMS `-32.2` $\rightarrow$ **`-5 dB`** |
| **4. `jazz` · `classic`** | `Vibraphone`<br>RMS `-41.6` $\rightarrow$ **`+3 dB`** | `Alto Saxophone`<br>RMS `-33.1` $\rightarrow$ **`0 dB`** | `Tenor Saxophone`<br>RMS `-35.9` $\rightarrow$ **`0 dB`** | `Suitcase Piano`<br>RMS `-35.1` $\rightarrow$ **`-2 dB`** | `Electric Bass`<br>RMS `-29.6` $\rightarrow$ **`-6 dB`** |
| **5. `jazz` · `soul`** | `Electric LP - Clean`<br>RMS `-45.1` $\rightarrow$ **`+4 dB`** | `Trumpet`<br>RMS `-44.6` $\rightarrow$ **`+6 dB`** | `Trombone`<br>RMS `-50.2` $\rightarrow$ **`+8 dB`** | `Wurly 200A`<br>RMS `-39.7` $\rightarrow$ **`0 dB`** | `Electric Bass`<br>RMS `-29.6` $\rightarrow$ **`-6 dB`** |
| **6. `jazz` · `organ`** | `Electric SC - Clean`<br>RMS `-42.4` $\rightarrow$ **`+4 dB`** | `Soprano Saxophone`<br>RMS `-31.8` $\rightarrow$ **`0 dB`** | `Baritone Saxophone`<br>RMS `-35.4` $\rightarrow$ **`0 dB`** | `Hammond Organ`<br>RMS `-42.2` $\rightarrow$ **`0 dB`** | `Electric Bass`<br>RMS `-29.6` $\rightarrow$ **`-6 dB`** |
| **7. `minimalist` · `classic`** *(MS Basic)* | `Synth Bell`<br>RMS `-29.1` $\rightarrow$ **`0 dB`** | `Synth Arpeggio`<br>RMS `-28.0` $\rightarrow$ **`0 dB`** | `Synth Pad`<br>RMS `-32.0` $\rightarrow$ **`0 dB`** | `Synth Pulse`<br>RMS `-35.8` $\rightarrow$ **`0 dB`** | `Sub-Bass`<br>RMS `-28.0` $\rightarrow$ **`0 dB`** |
| **8. `minimalist` · `mallet`** | `Crotales`<br>Pk `-36.5` $\rightarrow$ **`+12 dB`** | `Marimba`<br>Pk `-38.6` $\rightarrow$ **`+10 dB`** | `Full Choir`<br>RMS `-50.9` $\rightarrow$ **`+8 dB`** | `Harpsichord`<br>RMS `-41.0` $\rightarrow$ **`0 dB`** | `Electric Bass`<br>RMS `-29.6` $\rightarrow$ **`-6 dB`** |
| **9. `minimalist` · `guitar`** | `Flute 2`<br>RMS `-34.6` $\rightarrow$ **`0 dB`** | `Acoustic Steel Plucked`<br>RMS `-47.6` $\rightarrow$ **`+8 dB`** | `Cellos`<br>RMS `-40.8` $\rightarrow$ **`+4 dB`** | `Upright Piano`<br>RMS `-44.6` $\rightarrow$ **`0 dB`** | `Electric Bass`<br>RMS `-29.6` $\rightarrow$ **`-6 dB`** |
| **10. `ambient` · `classic`** | `Celesta`<br>RMS `-37.7` $\rightarrow$ **`+6 dB`** | `Alto Flute`<br>RMS `-39.3` $\rightarrow$ **`0 dB`** | `Bass Flute`<br>RMS `-40.4` $\rightarrow$ **`-5 dB`** | `French Horn`<br>RMS `-40.8` $\rightarrow$ **`0 dB`** | `Contrabasses`<br>RMS `-32.7` $\rightarrow$ **`0 dB`** *(hạ từ `+4`)* |
| **11. `ambient` · `breath`** | `Handchimes`<br>RMS `-31.1` $\rightarrow$ **`0 dB`** | `English Horn`<br>RMS `-29.9` $\rightarrow$ **`0 dB`** | `Bass Clarinet`<br>RMS `-40.6` $\rightarrow$ **`0 dB`** | `Trombones a3`<br>RMS `-38.7` $\rightarrow$ **`0 dB`** | `Contrabassoon`<br>RMS `-50.7` $\rightarrow$ **`+10 dB`** |
| **12. `ambient` · `choir`** | `Handbells`<br>RMS `-29.2` $\rightarrow$ **`0 dB`** | `Clarinet in Bb`<br>RMS `-46.4` $\rightarrow$ **`+3 dB`** | `Tenors`<br>RMS `-46.4` $\rightarrow$ **`+2 dB`** | `Violas`<br>RMS `-47.7` $\rightarrow$ **`+3 dB`** | `Basses`<br>RMS `-40.0` $\rightarrow$ **`0 dB`** |

Hằng số từ điển trong `backend/app/sonify/audio.py`:
```python
_VOICE_VOLUME_DB: dict[str, float] = {
    "Flute 1": 5,
    "Glockenspiel": 10,
    "Crotales": 12,
    "Vibraphone": 3,
    "Electric LP - Clean": 4,
    "Electric SC - Clean": 4,
    "Celesta": 6,
    "Violins 1": 2,
    "Oboe": 6,
    "Trumpet": 6,
    "Clarinet in Bb": 3,
    "Marimba": 10,
    "Acoustic Steel Plucked": 8,
    "Cellos": 4,
    "Trombone": 8,
    "Full Choir": 8,
    "Tenors": 2,
    "Bass Flute": -5,
    "Piano": -2,
    "Harp": 8,
    "French Horns a6": -5,
    "Suitcase Piano": -2,
    "Violas": 3,
    "Electric Bass": -6,
    "Contrabassoon": 10,
    "Tuba": -5,
}
```

---

## 7. Danh mục thay đổi cụ thể trong Codebase

1. **`backend/app/sonify/model.py`**:
   - Thêm 4 trường có giá trị mặc định `()` trên `Score`:
     - `high_wedges: tuple[WedgeEvent, ...] = ()`
     - `high_dynamics: tuple[DynamicEvent, ...] = ()`
     - `comp_wedges: tuple[WedgeEvent, ...] = ()`
     - `comp_dynamics: tuple[DynamicEvent, ...] = ()`
   - Thêm 4 `@property` tương thích ngược: `flute_wedges`, `flute_dynamics`, `piano_wedges`, `piano_dynamics`.
2. **`backend/app/sonify/dynamics.py`**:
   - Thêm `PIANO_VELOCITY: dict[str, int] = {"p": 46, "mp": 54, "mf": 62, "f": 68}`.
   - Thêm `effective_comp_band(band: str, bar: int | None = None) -> str` (hạ band qua `groove.chamber`, `groove.trio_thin`, `groove.half`).
   - Thêm `piano_marking(band: str) -> str` (`"p"` khi `band in ("p", "mp")`, `"mp"` khi `band in ("mf", "f")`).
3. **`backend/app/sonify/phrasing.py`**:
   - Mở rộng `left_hand(slot, *, velocity_at=None, every_bar_at=frozenset())` để nhận velocity giường và tập các ô đánh gốc mỗi ô mà không làm thay đổi lời gọi `left_hand(slot)` của `jazz.py`.
4. **`backend/app/sonify/render.py`**:
   - `_flute_and_violin_dovetail`: thêm tham số `ensemble: Ensemble = "classic"`, trả về `(flute_notes, yield_spans, flute_wedges, flute_dynamics)` theo đúng state machine và bảng chuyển trạng thái ở Mục 3.
   - `_bass_pattern` / `_bass_bar`: thêm tham số `under_cello: bool = False`, chỉ bật khi ô đó nằm trong `cello_lead_bars` (Cello kêu $\ge \max(\text{quarter\_beats}/2, 2.0)$ phách đen), hạ bước `OCTAVE` về `ROOT` và gập mọi nốt Bass `>= 48` (`Đô3`) xuống dưới `48`.
   - `_right_hand`: nhận thêm `bed_velocity_at`, `bed_marking_at`, `phrases`, trả về `(comp_notes, fill_marks, comp_wedges)` với `<wedge>` ngắn và nội suy velocity fill theo Mục 5B.
   - Trong nhánh `symphony` của `_compose`: tính `eff_bands`, `bed_velocity_at`, `bed_marking_at`, `dense_left_bars`, dựng `comp_dynamics` cùng `comp_wedges` và gán vào `Score`.
5. **`backend/app/sonify/musicxml.py`**:
   - Giữ nguyên `_opening_p` cho `P1` và `P2`. Thêm `_opening_dynamic(dynamics, default)` chỉ dùng cho `P5` và `P3` của Giao hưởng.
   - `score_to_musicxml`: khi `score.variant == "symphony"`, lấy `high_open, high_rest = _opening_dynamic(score.high_dynamics, MELODY_DYNAMIC)` và truyền `score.high_wedges`, `high_rest`, `opening_dynamic=high_open` vào `_melody_part` của `P5`.
   - `_piano_part`: khi `score.variant == "symphony"`, lấy `comp_open, comp_rest = _opening_dynamic(score.comp_dynamics, PIANO_DYNAMIC)`, in `comp_open` ở `bar == 0` và các sự kiện `comp_rest` tại `beat == 0.0` trước vòng lặp `symbols[bar]`, rồi xả các sự kiện `comp_rest` tại `beat > 0.0` cùng `score.comp_wedges` theo `flush(event.beat)` trong vòng lặp `staff == 1`.
6. **`backend/app/sonify/span.py`, `movement_frame.py`, `daily_frame.py`**:
   - `slice_score`: dịch `high_wedges`, `high_dynamics`, `comp_wedges`, `comp_dynamics`.
   - `apply_span_frame` & `apply_daily_frame`: cắt `high_wedges`, `high_dynamics`, `comp_wedges`, `comp_dynamics` theo đúng chữ ký riêng của từng file và thuật toán ở Mục 5C; gán `velocity = 49` chỉ cho các nốt có cao độ do `_curtain_comp` sinh ra ở warm-up / `tag_bars` (trước `with_rests`, không chạm vào `_kept_comp`).
7. **`backend/app/sonify/audio.py`**:
   - Thêm `_VOICE_VOLUME_DB` và `_mute_mscx_harmony(mscx_bytes)` (thay thế regex không phá định dạng XML gốc của `score.mscx`) vào `_assign_installed_sounds`.
   - Tăng `RECAP_REVISION` từ `"28"` lên **`"29"`**, và `SPAN_REVISION` từ `"14"` lên **`"15"`**.
8. **`backend/tests/test_harmony.py`, `test_sonify_plan.py`, `test_daily_frame.py`, `test_recap.py`**:
   - Cập nhật `test_chamber_bar_drops_the_symphony_right_hand` trong `test_sonify_plan.py` (dòng 928) mở tuple `notes, *_ = _right_hand(...)`.
   - Trong `test_harmony.py`, cập nhật đầy đủ 4 nhóm assertion Piano/velocity hiện hữu bị ảnh hưởng (`test_phrase_regime_uses_the_downbeat_window`, `test_musicxml_writes_harmony_and_letter_dynamics` & `_assert_measure_timing`, `test_piano_answers_a_held_cadence_under_the_violin`, `test_fills_stay_in_the_cadence_tail_on_chord_tones`).
   - Chạy toàn bộ test suite (`pytest`) và bổ sung đầy đủ các bài test mới ở Mục 8.

---

## 8. Tiêu chí Kiểm tra (Test Plan)

- **Flute (`P5`)**:
  - Đỉnh hairpin trùng móc giá gốc cao nhất đầu tiên (`span_apex` từ `pitches`), kể cả khi `flute_harmony_pitch` đã gập nốt đó xuống một quãng tám.
  - Đoạn 1 nốt sáo ngân dài duy nhất ($\ge 4$ móc, Hình thái 2 — ưu tiên trước Hình thái 1) luôn sinh cặp `< >` với đỉnh ở giữa ngân (`mid_apex`).
  - Khi Flute vào ngay tại đỉnh (`span_apex - arc_start < WEDGE_MIN`, Hình thái 3): nếu `peak == 80` (và `ensemble != "brass"`), `P5` mở chữ `mf` tại `arc_start` kèm `diminuendo`, rồi in lại `mp` ở tiếng đánh mới kế tiếp (nếu rơi vào `(bar=0, beat=0.0)`, ô 1 chỉ in đúng một thẻ `<dynamics><mf/></dynamics>`); nếu `peak == 72` (câu yên `p`/`mp`), giữ `"mp"` và không mở `"mf"` hay `diminuendo` trần.
  - **Chuyển trạng thái sau `crescendo` trần (Trường hợp 4a)**: Đoạn Flute kết thúc ngay tại đỉnh (`sounding_end - span_apex < WEDGE_MIN`, chỉ có `crescendo`) đặt `effective_level = "drifted"`; đoạn Flute kế tiếp luôn in tường minh `start_marking` của nó (`"mp"` hoặc `"mf"`).
  - **Đoạn có nốt đầu buộc nối qua ranh giới phrase (`tie_first_in == True`)** và **giao khoảng `BREAKOUT`**: Không đặt chữ/wedge trên nốt nối dây (`r_i == 0`), và `f_run` giao với run `BREAKOUT` của `phrase.runs` nhận đúng `vel = 80`.
  - `ensemble == "brass"` (`Glockenspiel`): đoạn 1 run không sinh `<wedge>`; đoạn $\ge 2$ runs có `<wedge>` và không bị kích chữ `"mf"` ở đầu Hình thái 3.
- **Violin (`P1`), Cello (`P2`) & Bass (`P4`)**:
  - `lead_wedges` và `support_wedges` giữ nguyên hành vi hiện tại (pass toàn bộ test trong `test_harmony.py`).
  - Khi Cello hát chính ở ô `bar` (tổng thời lượng nốt Cello $\ge \max(\text{quarter\_beats}/2, 2.0)$ phách đen), toàn bộ nốt Bass trong ô đó (kể cả bậc 5 của các hợp âm `F..B`) đều có `midi < 48` (`Đô3`). Các ô chỉ có nốt dovetail ngắn (`< 2.0` phách đen, bao gồm đoạn 3 móc ở `6/8`) giữ nguyên pattern Bass hiện tại.
- **Piano (`P3`) & Frame (`daily_frame`, `movement_frame`)**:
  - Giường chỉ in `p` và `mp` theo `effective_comp_band`, đứng trước `<harmony>` tại `beat == 0.0`. Velocity giường nhận đúng `46 / 54 / 62 / 68`.
  - Ô `f` (sau groove) hoặc `groove.rally` đánh gốc tay trái mỗi ô trên Giao hưởng; `left_hand` của Jazz giữ nguyên đánh mỗi 2 ô.
  - Chữ fill (`mp` hoặc `mf`) đứng đúng tại `beat` bắt đầu fill trên khuông 1 (và in lại ở `beat >= 0.5` của ô sau nếu câu fill vượt qua vạch ô nhịp); hợp âm đệm kế tiếp in lại chữ giường ở `beat = 0.0`. Nhóm fill $\ge 2$ nốt có hướng `Nở`/`Lắng` sinh `<wedge>` ngắn trong `comp_wedges` và khớp velocity nội suy tuyến tính. Fill bị `caesura` cắt sạch không sinh chữ hay wedge.
  - **Cắt/nối qua Frame**: Nốt do `_curtain_comp` sinh ở warm-up / `tag_bars` có `velocity = 49` (không chạm `_kept_comp`). Cắt `high_wedges` và `comp_wedges` không để sót `stop` mồ côi từ `< body`. Khi chữ giường tại ô `body` là `"mp"`, cả khung tĩnh lẫn khung động đều in `"mp"` tại `(bar=body, beat=0.0)`.
- **Audio & `<Harmony>` (`audio.py`)**:
  - Unit test với fixture `.mscz` xác nhận `_mute_mscx_harmony` chèn `<play>0</play>` (idempotent, giữ nguyên phần còn lại của `score.mscx`) và gắn đúng `volumeDb` từ `_VOICE_VOLUME_DB`, kèm smoke test tích hợp qua `musescore_export` (tự động `pytest.skip` khi không có binary MuseScore) kiểm tra cả xuất WAV thành công lẫn độ giảm RMS (~6 dB) khi tắt Piano ẩn của `<Harmony>`.
