# Dynamic và Cân bằng Âm lượng cho Giao hưởng & 12 Bộ Nhạc cụ

Kế hoạch này giải quyết hai bài toán đi liền nhau:
1. **Biểu cảm & phản ánh chuyển động thị trường (Market Movement)**: Đưa Flute (`P5`), Piano (`P3`) và Bass (`P4`) của Giao hưởng vào chung một hệ thống động lực học 3 tầng (Đà giá trong câu × Thanh khoản `p–f` × Tính cách phiên `BarGroove`), tương thích với cơ chế phát thực tế của MuseSounds trong MuseScore 4.
2. **Cân bằng âm lượng (Volume Balance) giữa các bè và trên toàn bộ 12 bộ nhạc cụ**: Loại bỏ tiếng Piano ẩn đánh chồng từ thẻ `<harmony>`, dọn dải tần trầm để Bass không đè Cello, và chuẩn hóa bảng gain `_VOICE_VOLUME_DB` trong `audio.py` cho tất cả 12 bộ nhạc cụ (`classic`, `wood`, `brass`, `soul`, `organ`, `mallet`, `guitar`, `breath`, `choir`).

---

## 1. Nguyên lý phát thực tế của MuseScore 4 + MuseSounds

Thực nghiệm xuất WAV qua `musescore_export` trên MuseScore 4.7.5 với thư viện MuseSounds cho thấy hai cơ chế cốt lõi mà thiết kế phải bám sát:

1. **Vai trò của `<direction><dynamics>` / `<wedge>` (lớp chính) và `<note dynamics="...">` (lớp phụ)**:
   - Trên các thư viện hơi, dây, đồng, hợp xướng của MuseSounds (`Flute 1`, `Piccolo`, `Violins 1`, `Cellos`, `Oboe`, `Clarinet`, `Trumpet`, `Trombone`, `French Horns a6`, `Tuba`, `Contrabassoon`), âm lượng và âm sắc được điều khiển bởi **biểu thức `<direction><dynamics>` và `<wedge>`** (+3.6 dB đến +4.5 dB RMS khi nở từ `mp` lên `mf`). Khi giữ nguyên chữ `mp` mà chỉ đổi thuộc tính `dynamics` trên `<note>`, âm lượng WAV của các giọng này không đổi.
   - Ngược lại, thuộc tính `dynamics` trên `<note>` (suy từ `NoteEvent.velocity`) đóng vai trò là **lớp phụ bắt buộc** cho bộ tổng hợp MS Basic / Fluid (trên Linux server hoặc các track synth), cho nhạc cụ gõ tắt dần (`Glockenspiel`), và cho việc kiểm thử đường cong động lực học trên model `Score`. Do đó, bản kế hoạch thiết kế **cả hai lớp đồng bộ**: đường nghe chính bằng `<wedge>` + chữ dynamic, và đường số học bằng `NoteEvent.velocity`.
2. **Thẻ `<harmony>` trên `P3` khiến MuseScore 4 tự tổng hợp thêm một Piano ẩn đánh chồng lên phách 1 (+6.2 dB RMS / +6.7 dB Peak)**:
   - Trong `score.mscx` sinh ra từ MusicXML, mỗi thẻ `<harmony>` biến thành phần tử `<Harmony><harmonyInfo>...</harmonyInfo></Harmony>`. Khi xuất WAV ở trạng thái mặc định, MuseScore 4 tự gõ thêm một hợp âm Piano đầy đủ chồng lên phách 1: trên một ô 4/4 `120 BPM` chỉ có `P3` đánh hợp âm `Cmaj7` ở `p` (`velocity=49`), bản có `<Harmony>` mặc định phát ở **`-35.5 dB` RMS (`-18.4 dB` Peak)**, trong khi bản thêm `<play>0</play>` vào `<Harmony>` hoặc xóa `<Harmony>` phát đúng tiếng thật của nốt viết ở **`-41.7 dB` RMS (`-25.1 dB` Peak)** (khớp tuyệt đối đến `0.0 dB`).
   - Ở bộ `symphony wood` (`Harp`) và `symphony brass` (`French Horns a6`), chính `<Harmony>` mặc định này đang phát ra tiếng Piano lạ đè lên tiếng đàn Harp và kèn Cor.

---

## 2. Ba tầng chuyển động thị trường trên các bè Giao hưởng

| Tầng chuyển động | Flute / P5 (`classic`, `wood`, `brass`) | Violin & Cello (`P1`, `P2`) | Piano / P3 (`classic`, `wood`, `brass`) | Bass / P4 (`classic`, `wood`, `brass`) |
|---|---|---|---|---|
| **1. Giá trong câu** (`phrase.rise`, đỉnh, `BREAKOUT`) | Vòng cung `< >` theo đoạn sáo; vào ngay đỉnh thì mở ở `mf` rồi `>` về `mp`; 1 nốt ngân dài nở ở giữa ngân | Giữ nguyên vòng cung `hairpins()` và `melody_parts()` hiện có; được tôn nổi nhờ Bass nhường dải tần và bảng `_VOICE_VOLUME_DB` | Hướng vuốt velocity của câu fill (`Nở` khi câu lên, `Lắng` khi câu xuống, `Ngang` khi bằng) | Hạ bước nhảy `OCTAVE` về `ROOT` trên những ô Cello hát chính ($\ge$ nửa ô) |
| **2. Thanh khoản `p–f`** (`band_at`) | Band `mf`/`f` tại đỉnh hoặc đoạn có `BREAKOUT` nâng `peak = 80` (`mf`); band `p`/`mp` giữ `peak = 72` | Velocity và nốt nhấn phản ánh câu | Chữ in giường (`p` cho `p`/`mp`, `mp` cho `mf`/`f`) và 4 bậc velocity (`46 / 54 / 62 / 68`) | Mật độ tiết tấu từ tròn (`p`) tới 8 móc đơn (`f`), chữ in trần `mp` |
| **3. Tính cách phiên (`BarGroove`)** | `BREAKOUT` luôn nở tới chữ `mf` | `selloff` nhường sớm vùng trung-trầm cho Cello | Đọc `chamber`, `trio_thin`, `half`, `rally`, `selloff`, `caesura`; gốc tay trái đánh mỗi ô khi `f` hoặc `rally` | Đọc `chamber`, `trio_thin`, `half`, `tresillo`, `selloff`, `rally`, `caesura` |

---

## 3. Flute (`P5`): State Machine cho chữ Dynamic, Hairpin và Velocity

Flute vào khi câu lên cao (`>= FLUTE_TRIGGER`), khi có `BREAKOUT`, hoặc khi nốt vượt trần violin (`violin_ceiling`). `_flute_and_violin_dovetail` ghi `yield_spans` và dựng vòng cung cho đúng đoạn `[span_start, sounding_end)` mà Flute hát.

### A. Định nghĩa chính xác các biến của một đoạn Flute `[span_start, sounding_end)`

1. **`span_apex` (tie-break khi có cao nguyên giá)**:
   - Lấy từ đường giá gốc `pitches[eighth]` (trước khi `flute_harmony_pitch` cộng quãng và gập trần `Mi6`), và **lấy móc đơn đầu tiên đạt giá trị cực đại** trong đoạn (đồng nhất với `Phrase.apex`):
     ```python
     span_apex = max(range(span_start, sounding_end), key=lambda e: (pitches[e], -e))
     ```
2. **Cờ `has_breakout` của đoạn**:
   - Bằng `True` nếu bất kỳ `run` nào của `phrase.runs` giao với `[span_start, sounding_end)` được đánh dấu `colours.get(run.start) == BREAKOUT`:
     ```python
     has_breakout = any(
         colours.get(r.start) == BREAKOUT
         for r in phrase.runs
         if r.end > span_start and r.start < sounding_end
     )
     ```
3. **Mức `peak` của đoạn**:
   - Luôn tra `band_at` tại ô của `span_apex` gốc (`apex_bar = span_apex // epb`), bất kể đoạn thuộc hình thái nào:
     ```python
     peak = 80 if (has_breakout or band_at[span_apex // epb] in ("mf", "f")) else 72
     ```
4. **Ranh giới câu nối dây (`tie_first_in` / `held_over`)**:
   - `_flute_and_violin_dovetail` duyệt từng `phrase`. Mỗi đoạn `[span_start, sounding_end)` nằm gọn trong một `phrase`. Nếu `tie_first_in == True` (nốt đầu đoạn buộc nối từ cuối phrase trước), run đầu tiên (`r_i == 0`) là nốt nối dây (`tie_stop=True`), không phải tiếng đánh mới; mọi chữ dynamic in lại hoặc mở mới chỉ được đặt trên **run đầu tiên có tiếng đánh mới** (`first_attack`, tức run đầu tiên có `not (r_i == 0 and tie_first_in)`). Nếu cả đoạn chỉ có 1 run duy nhất và `tie_first_in == True` thì `first_attack = None`: đoạn này chỉ ngân nốt nối dây, không sinh chữ mới và không mở `<wedge>`.

### B. Thứ tự ưu tiên giữa 3 Hình thái và `Glockenspiel` (`ensemble == "brass"`)

Với mỗi đoạn Flute có `sounding_end > span_start` và `first_attack is not None`, đặt `arc_start = first_attack.start`:

- **Nhánh A — Đoạn phẳng hoặc quá ngắn (`phrase.rise < MIN_RISE` hoặc `sounding_end - arc_start < WEDGE_MIN`)**:
  - Không sinh `<wedge>`.
  - Riêng `ensemble == "brass"` (`Glockenspiel`) khi `phrase.rise >= MIN_RISE` và `len(merged_flute_runs) == 1`: gán `velocity = peak`; chữ mở đoạn `start_marking = "mf"` nếu `peak == 80`, ngược lại `"mp"`.
  - Mọi trường hợp phẳng/ngắn khác: `start_marking = "mp"`, gán `velocity = 64`.

- **Nhánh B — Đoạn có độ dốc và đủ độ dài (`phrase.rise >= MIN_RISE` và `sounding_end - arc_start >= WEDGE_MIN`)**:
  Kiểm tra theo đúng thứ tự ưu tiên từ 1 đến 4:
  1. **Ưu tiên 1 — `Glockenspiel` 1 tiếng gõ (`ensemble == "brass"` và `len(merged_flute_runs) < 2`)**:
     - Không sinh `<wedge>` (nhạc cụ gõ kim loại tắt dần sau cú gõ).
     - Gán `velocity = peak`; `start_marking = "mf"` nếu `peak == 80`, ngược lại `"mp"`.
  2. **Ưu tiên 2 (Hình thái 1) — Đoạn leo lên đỉnh (`span_apex - arc_start >= WEDGE_MIN`)**:
     - `eff_apex = span_apex`, `start_marking = "mp"`.
     - Sinh `wedges = hairpins(arc_start, sounding_end, eff_apex)` (gồm `crescendo` từ `arc_start` tới `eff_apex`, và `diminuendo` từ `eff_apex` tới `sounding_end` nếu `sounding_end - eff_apex >= WEDGE_MIN`).
     - Chỉ in thêm chữ `"mf"` tại `eff_apex` khi `peak == 80` **và** có cả 2 cạnh (`sounding_end - eff_apex >= WEDGE_MIN`).
  3. **Ưu tiên 3 (Hình thái 2) — Một cao độ ngân dài ở đỉnh (`len(merged_flute_runs) == 1` và `sounding_end - arc_start >= 4`)**:
     - Đặt đỉnh vào giữa hơi ngân: `eff_apex = arc_start + (sounding_end - arc_start) // 2`, `start_marking = "mp"`.
     - Sinh `wedges = hairpins(arc_start, sounding_end, eff_apex)` (luôn đủ $\ge 2$ móc mỗi bên nên luôn có đủ cặp `< >`).
     - Nếu `peak == 80`, in thêm chữ `"mf"` tại `eff_apex`.
  4. **Ưu tiên 4 (Hình thái 3) — Vào ngay tại đỉnh rồi đi xuống (`span_apex - arc_start < WEDGE_MIN`)**:
     - `eff_apex = arc_start`, `start_marking = "mf"` (đón tiếp đỉnh cao trào từ Violin).
     - Sinh `wedges = [_wedge_at(arc_start, "diminuendo"), _wedge_at(sounding_end, "stop")]`.

### C. State Machine duy nhất quản lý chữ in (`high_dynamics`), Bảng chuyển trạng thái và chống trùng ở `bar == 0`

`_flute_and_violin_dovetail` duy trì một biến trạng thái `effective_level: str = "mp"` (nhận một trong hai giá trị: `"mp"` khi kênh P5 đang đứng yên ở mức `mp` chuẩn, hoặc `"drifted"` khi kênh P5 vừa rời khỏi `mp` do chữ `"mf"` hoặc do một `<wedge>` mà mức kết thúc chưa được khóa bằng chữ `"mp"`):

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
| **1. Không có `<wedge>` và đứng ở `"mp"`**<br>*(Đoạn phẳng `rise < MIN_RISE`, đoạn `< WEDGE_MIN`, hoặc `Glockenspiel` 1 run với `peak == 72`)* | `emit_flute_dynamic(arc_start, "mp")` | **`"mp"`** | Đoạn sau mở `"mp"` sẽ không in lặp `"mp"`; đoạn sau mở `"mf"` sẽ in `"mf"`. |
| **2. Không có `<wedge>` nhưng mở `"mf"`**<br>*(`Glockenspiel` 1 run với `rise >= MIN_RISE` và `peak == 80`)* | `emit_flute_dynamic(arc_start, "mf")` | **`"drifted"`** | Đoạn sau bắt buộc in lại `"mp"` (nếu `start_marking == "mp"`) hoặc in `"mf"` (nếu `start_marking == "mf"`). |
| **3. Có cặp `< >` cân bằng trên nền `"mp"`, không in `"mf"` ở đỉnh**<br>*(Hình thái 1 hoặc 2 với `peak == 72` và có đủ cả `crescendo` lẫn `diminuendo`)* | `emit_flute_dynamic(arc_start, "mp")` | **`"mp"`** | `crescendo` (+1) và `diminuendo` (-1) tự triệt tiêu về `"mp"` (giống `drift == 0` của Violin/Cello), đoạn sau mở `"mp"` không in thừa chữ. |
| **4. Mọi đoạn có `<wedge>` còn lại**<br>*(Gồm: **(4a)** Hình thái 1 kết thúc ngay tại đỉnh chỉ có `crescendo` trần; **(4b)** Hình thái 1 hoặc 2 có `peak == 80` in `"mf"` tại `eff_apex` rồi `diminuendo`; **(4c)** Hình thái 3 mở `"mf"` tại `arc_start` rồi `diminuendo`)* | • **(4a)**: `emit(arc_start, "mp")`<br>• **(4b)**: `emit(arc_start, "mp")` rồi `emit(eff_apex, "mf")`<br>• **(4c)**: `emit(arc_start, "mf")` | **`"drifted"`** | Vì `"drifted"` khác cả `"mp"` lẫn `"mf"`, đoạn kế tiếp **luôn in tường minh** `start_marking` của nó (`"mp"` để reset về nền, hoặc `"mf"` nếu đoạn kế tiếp lại là Hình thái 3!). |

- **Lưu ý thực thi**: Bản thân lệnh `emit_flute_dynamic` gán `effective_level = target_marking` (`"mp"` hoặc `"mf"`), nên ở Trường hợp 2 và Trường hợp 4, **ngay sau khi xử lý xong đoạn phải có lệnh gán tường minh `effective_level = "drifted"`**.
- **Chống trùng ở `bar == 0, beat == 0.0`**: Nếu đoạn Flute đầu tiên rơi ngay vào `arc_start == 0` và `start_marking == "mf"`, `flute_dynamics[0]` là `DynamicEvent(0, "mf", SOUND["mf"], 0.0)`. Trong `musicxml.py`, hàm `_opening_dynamic(score.high_dynamics, MELODY_DYNAMIC)` lấy phần tử `(bar=0, beat=0.0)` đó làm `opening_dynamic` của `P5` và trả về phần còn lại `score.high_dynamics[1:]`, đảm bảo ô 1 chỉ có đúng một thẻ `<dynamics>`.

### D. Công thức `span_swell(onset)` cho `NoteEvent.velocity` (không dùng `stress_start`)

Bè Flute không gắn `<accent/>` như Violin/Cello, nên công thức velocity của Flute chỉ phụ thuộc vào `span_swell(onset)`, `lift(phrase)`, `peak` và cờ `BREAKOUT` (`colours.get(f_run.start) == BREAKOUT`):
- Với mỗi run `f_run` trong `merged_flute_runs` của đoạn có vòng cung (Hình thái 1, 2, 3), đặt `onset = max(arc_start, f_run.start)`:
  - Nếu `colours.get(f_run.start) == BREAKOUT`: `vel = peak` (`80`).
  - Ngược lại:
    - Nếu `onset <= eff_apex`: `s = 1.0 if eff_apex == arc_start else (onset - arc_start) / (eff_apex - arc_start)`
    - Nếu `onset > eff_apex`: `s = 1.0 - (onset - eff_apex) / max(1, sounding_end - eff_apex)`
    - `vel = round(64 + (peak - 64) * lift(phrase) * s)`
- Nếu `f_run` là run nối dây từ câu trước (`r_i == 0 and tie_first_in`) và câu hiện tại phẳng (`phrase.rise < MIN_RISE`), `vel = 64`.

---

## 4. Violin (`P1`), Cello (`P2`) và Bass (`P4`): Phạm vi giữ nguyên & Quy tắc Bass nhường Cello

### A. Giữ nguyên `melody_parts()` của Violin và Cello

- Giữ nguyên 100% logic `hairpins()`, `drift` và velocity của `melody_parts()` trong `backend/app/sonify/phrasing.py` để bảo toàn toàn bộ các bài test hiện hữu (như `test_reset_after_a_held_over_note_waits_for_the_next_attack` và `test_phrase_swells_to_its_apex_and_writes_hairpins`).
- Violin và Cello được cải thiện độ rõ nét và cân bằng âm lượng thông qua:
  1. Bảng gain `_VOICE_VOLUME_DB` (`Violins 1: +2 dB`, `Cellos: +4 dB`, `Electric Bass: -6 dB`).
  2. Quy tắc Bass nhường quãng 8 (`OCTAVE`) ở các ô Cello hát chính dưới đây.

### B. Quy tắc chính xác để Bass (`P4`) nhường dải tần `Đô3–Si3` cho Cello (`P2`)

1. **Ngưỡng xác định "ô có Cello hát chính" (`cello_lead_bars`)**:
   - Để các nốt dovetail lead-in / trail-out ngắn (1–2 móc đơn chen dưới Violin khi chuyển giao bè) không làm mất quãng 8 của Bass ở những ô Violin đang hát chính, một ô `bar` chỉ được tính vào `cello_lead_bars` khi tổng thời lượng các nốt có cao độ của Cello trong ô đó chiếm **ít nhất một nửa ô nhịp (`>= active_meter().quarter_beats / 2`)**:
     ```python
     half_beats = active_meter().quarter_beats / 2
     cello_beats_by_bar: dict[int, float] = {}
     for note in cello.notes:
         if note.midi is not None:
             cello_beats_by_bar[note.bar] = cello_beats_by_bar.get(note.bar, 0.0) + note.duration_beats
     cello_lead_bars = {bar for bar, beats in cello_beats_by_bar.items() if beats >= half_beats - 1e-6}
     ```
2. **Pitch thay thế duy nhất khi `under_cello=True`**:
   - Trong `_bass_pattern(marking: str, bar: int | None = None, *, under_cello: bool = False)`:
   - Gộp chung điều kiện `under_cello` vào nhánh `groove.selloff` đã có sẵn ở dòng 159 của `render.py` — tức **thay mọi bước `OCTAVE` bằng `ROOT` trên tất cả các nhịp `4/4`, `6/8`, `3/4`**:
     ```python
     if (groove is not None and groove.selloff) or under_cello:
         pattern = tuple(
             (start, length, ROOT if interval == OCTAVE else interval)
             for start, length, interval in pattern
         )
     ```
   - Quy tắc này hoàn toàn tường minh, không sinh nhánh mới theo từng loại nhịp, và giữ toàn bộ nốt Bass nằm gọn ở `Đô2–Si2 (36–47)` khi Cello hát chính.

---

## 5. Piano (`P3`): Plumbing hàm, Chữ giường, Nội suy Fill và `<Harmony><play>0</play>`

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
   - Viết hàm helper `_mute_mscx_harmony(mscx_bytes: bytes) -> bytes` dùng `xml.etree.ElementTree`:
     ```python
     def _mute_mscx_harmony(mscx_bytes: bytes) -> bytes:
         try:
             root = ET.fromstring(mscx_bytes.decode("utf-8"))
         except (ET.ParseError, UnicodeDecodeError):
             return mscx_bytes
         changed = False
         for harmony in root.iter("Harmony"):
             play = harmony.find("play")
             if play is None:
                 play = ET.SubElement(harmony, "play")
                 play.text = "0"
                 changed = True
             elif play.text != "0":
                 play.text = "0"
                 changed = True
         if not changed:
             return mscx_bytes
         return ('<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode")).encode("utf-8")
     ```
   - Trong `_assign_installed_sounds`, gán `payloads[mscx_name] = _mute_mscx_harmony(payloads[mscx_name])` trước khi ghi lại zip `.mscz.tmp`. Hàm hoàn toàn idempotent khi gọi nhiều lần.
2. **Hành vi ở đường fallback MS Basic (`use_config == True` hoặc `library == {}`)**:
   - Đường MS Basic chỉ chạy khi máy chủ Linux cấu hình `MUSESCORE_SOUNDFONT` (Fluid `.sf3`) hoặc máy không cài MuseSounds. Ở đường này, `musescore_export` gọi thẳng `mscore -o out.wav in.musicxml` mà không tạo `.mscz`, nên chúng ta **chấp nhận giữ nguyên hành vi MS Basic hiện tại** (không thêm bước convert `.mscz` thứ hai làm tăng gấp đôi thời gian CPU trên server 2-vCPU).

### B. Plumbing cho Piano (`_right_hand`, `left_hand`, `fills`) và cô lập hoàn toàn khỏi Jazz

Để Jazz (`render_jazz_score` trong `jazz.py`) giữ nguyên 100% hành vi hiện tại:
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
3. **Nâng cấp `_right_hand` và nội suy Velocity của Fill trong `render.py`**:
   - Giữ nguyên hàm `fills(cadences, chord_at)` và hằng `FILL_VELOCITY = 64` trong `phrasing.py` để Jazz và các test gọi trực tiếp `fills()` không bị ảnh hưởng.
   - Trong `render.py`, đổi chữ ký `_right_hand`:
     ```python
     def _right_hand(
         slots: tuple[ChordSlot, ...],
         cadence_fills: list[tuple[int, int, int]],
         piece_eighths: int = TOTAL_EIGHTHS,
         *,
         bed_velocity_at: dict[int, int] | None = None,
         bed_marking_at: dict[int, str] | None = None,
         phrases: tuple[Phrase, ...] = (),
     ) -> tuple[tuple[NoteEvent, ...], list[tuple[int, float, str]]]:
     ```
   - Khi gọi với mặc định `bed_velocity_at=None` (như trong `test_chamber_bar_drops_the_symphony_right_hand` tại `backend/tests/test_sonify_plan.py`, dòng 928 — test này sẽ được cập nhật thành `notes, _ = _right_hand(...)`): guide tones giữ `velocity=None`, fill giữ `FILL_VELOCITY = 64`, `fill_marks` trả về `[]`.
   - Khi gọi từ nhánh `symphony` của `_compose`:
     - Guide tones ở ô `bar` nhận `velocity = bed_velocity_at[bar]`.
     - Các tuple `(start, length, midi)` của `cadence_fills` sau khi lọc bỏ nửa sau ô `caesura` được gom lại theo từng `phrase` đóng (`phrase.closes` mà `start` nằm trong đuôi `phrase.cadence`).
     - Với mỗi nhóm fill của một cadence còn ít nhất 1 nốt sống:
       - Ô đặt chữ fill là `fill_bar = group[0][0] // epb`, phách đặt chữ fill là `fill_beat = (group[0][0] % epb) * 0.5`.
       - Chữ giường của ô đó là `bed_mark = bed_marking_at[fill_bar]` (`"p"` hoặc `"mp"`). Chữ fill là `fill_mark = "mp" if bed_mark == "p" else "mf"`. Ghi nhận `(fill_bar, fill_beat, fill_mark)` để đưa vào `comp_dynamics`.
       - **Hướng vuốt của nhóm fill**:
         - Nếu `groove_at(fill_bar).selloff`: `"fall"` (`Lắng`).
         - Ngược lại, nếu `groove_at(fill_bar).rally`: `"rise"` (`Nở`).
         - Ngược lại, tìm `phrase` chứa cadence đó: nếu `phrase.cadence.midi > phrase.runs[0].midi` thì `"rise"`, nếu `<` thì `"fall"`, nếu `==` thì `"flat"` (`Ngang`).
       - **Công thức nội suy tuyến tính theo chỉ số nốt `k` trong nhóm fill (`m = len(group)` runs)**:
         - Với `fill_mark == "mp"` (mốc `64`): `"rise"` đi từ `v_start = 58` đến `v_end = 66`; `"fall"` đi từ `v_start = 64` đến `v_end = 56`; `"flat"` giữ `64`.
         - Với `fill_mark == "mf"` (mốc `80`): `"rise"` đi từ `v_start = 74` đến `v_end = 80`; `"fall"` đi từ `v_start = 80` đến `v_end = 72`; `"flat"` giữ `80`.
         - Nếu nhóm chỉ có **1 nốt (`m == 1`)** hoặc hướng là `"flat"`: `vel_k = 64 if fill_mark == "mp" else 80`.
         - Nếu nhóm có **`m >= 2` nốt**: nốt thứ `k` (`0 <= k < m`) nhận:
           ```python
           vel_k = round(v_start + (v_end - v_start) * k / (m - 1))
           ```
4. **Dựng `comp_dynamics` theo từng ô và từng phách**:
   - Duyệt `bar` từ `0` đến `musical_bars - 1`, theo dõi `current_comp_mark: str | None = None`:
     - Tại `beat = 0.0`: nếu ô `bar` có ít nhất một nốt kêu (guide tone ở khuông 1 hoặc root ở khuông 2 tại `beat == 0.0`) và `bed_marking_at[bar] != current_comp_mark`:
       - Thêm `DynamicEvent(bar=bar, marking=bed_marking_at[bar], sound=SOUND[bed_marking_at[bar]], beat=0.0)`.
       - Cập nhật `current_comp_mark = bed_marking_at[bar]`.
     - Tại các sự kiện fill `(fill_bar, fill_beat, fill_mark)` rơi vào `bar`:
       - Nếu `fill_mark != current_comp_mark`:
         - Thêm `DynamicEvent(bar=bar, marking=fill_mark, sound=SOUND[fill_mark], beat=fill_beat)`.
         - Cập nhật `current_comp_mark = fill_mark`.
   - Nhờ state machine này, ngay ở ô kế tiếp sau một câu fill (nơi `current_comp_mark` đang là `"mp"` hoặc `"mf"` của fill), tại `beat = 0.0` có hợp âm đệm kêu, `bed_marking_at[next_bar]` sẽ tự động được in lại để hạ playback về mức giường!

### C. Khung Warm-up / Cool-down và thuật toán cắt biên trong `daily_frame.py` & `movement_frame.py`

1. **`_curtain_comp` trong `movement_frame.py` (Khung động của Giao hưởng)**:
   - Khi `dynamic == True`, `_curtain_comp` sinh các nốt đệm ở `warm_start..body` và (nếu `tag > 0`, tức `cool_len >= 3`) ở `cool..cool + tag`. Khi `tag == 0` (`cool_len < 3`, như khung ngắn 1–2 ô của `1Y`), `_curtain_comp` chỉ đánh ở `warm_start..body` và nghỉ toàn bộ `cool..end`.
   - **Điểm chạm gán `velocity = 49`**: Chỉ gán `velocity = 49` trên danh sách `notes` của warm-up / `tag_bars` **trước khi gọi `with_rests(notes, ...)`** bên trong `_curtain_comp` (tuyệt đối không chạm vào `*_kept_comp(score.comp, body, cool)` để bảo toàn nguyên vẹn velocity giường `46/54/62/68` và velocity fill của thân bài).
2. **Cắt `high_wedges` và `high_dynamics` theo đúng chữ ký từng file**:
   - Trong `daily_frame.py` (dùng hằng `BODY_START = 2`, `COOL_START = 32`):
     - `high_wedges = _body_wedges(score.high_wedges)` (hàm 1 tham số sẵn có của `daily_frame.py`).
     - `high_dynamics = _flute_body_dynamics(score.high_dynamics, BODY_START, COOL_START)`.
   - Trong `movement_frame.py` (dùng tham số `body`, `cool`):
     - `high_wedges = _body_wedges(score.high_wedges, body, cool)` (hàm 3 tham số sẵn có của `movement_frame.py`).
     - `high_dynamics = _flute_body_dynamics(score.high_dynamics, body, cool)`.
   - Hàm lọc `_flute_body_dynamics(events, body, cool)`:
     - Giữ các sự kiện `kept = [e for e in events if body <= e.bar < cool]`.
     - Vì Flute nghỉ hoàn toàn ở `0..body` và `P5` luôn mở đầu bằng `MELODY_DYNAMIC` (`"mp"`) tại `bar == 0`, nếu `kept` không rỗng và `kept[0].marking == "mp"`, bỏ `kept[0]` (`kept = kept[1:]`) để không bao giờ in trùng 2 chữ `"mp"` liên tiếp khi vào thân bài; ngược lại nếu `kept[0].marking == "mf"` thì giữ nguyên.
3. **Thuật toán cắt và nối `comp_dynamics` qua biên khung (`_piano_frame_dynamics`)**:
   - Khi ở trong `daily_frame.py` (`body = BODY_START`, `cool = COOL_START`) hoặc `movement_frame.py` (`body`, `cool`), hàm khung chỉ nhận `score: Score`.
   - Trong `score.comp_dynamics`, mọi chữ giường đều có `event.beat == 0.0`, còn chữ fill luôn có `event.beat > 0.0`. Do đó, **chữ giường đang có hiệu lực tại ô mở đầu thân bài (`bar == body`)** được suy ra chính xác từ sự kiện giường gần nhất tại hoặc trước `body`:
     ```python
     bed_before = [e.marking for e in score.comp_dynamics if e.bar <= body and e.beat == 0.0]
     body_mark = bed_before[-1] if bed_before else "p"
     kept = [e for e in score.comp_dynamics if body <= e.bar < cool]
     ```
   - **Với Khung tĩnh** (`daily_frame._symphony`, hoặc `movement_frame._symphony` khi `not dynamic`):
     - Piano nghỉ ở `0..body` và `cool..end`; đầu bài (`bar == 0`) `_piano_part` đã in `PIANO_DYNAMIC` (`"p"`).
     - Nếu `kept` mở đầu tại `(bar == body, beat == 0.0)`:
       - Nếu `kept[0].marking == "p"`: bỏ `kept[0]` (vì đầu bài đã là `"p"` và `0..body` không có nốt hay chữ nào khác).
     - Ngược lại (nếu `kept` không có sự kiện tại `(bar == body, beat == 0.0)`) và `body_mark != "p"`:
       - Chèn `DynamicEvent(bar=body, marking=body_mark, sound=SOUND[body_mark], beat=0.0)` vào đầu `kept` (để khôi phục chữ `"mp"` vốn được đặt ở `bar < body` trước khi khung cắt bỏ `0..body`).
   - **Với Khung động** (`movement_frame._symphony` khi `dynamic == True`):
     - Mở đầu bằng `out = [DynamicEvent(bar=warm_start, marking="p", sound=SOUND["p"], beat=0.0)]`.
     - Tại biên vào thân bài `(bar == body, beat == 0.0)`: áp dụng cùng quy tắc như khung tĩnh (nếu `kept` bắt đầu bằng `"p"` ở `(body, 0.0)` thì bỏ đi vì warm-up đã là `"p"`; nếu `body_mark != "p"` và `kept` chưa có sự kiện ở `(body, 0.0)` thì chèn `DynamicEvent(bar=body, marking=body_mark, sound=SOUND[body_mark], beat=0.0)`).
     - Nối `out.extend(kept)`.
     - Tại biên ra cool-down: nếu `tag > 0` (có nốt `_curtain_comp` ở `cool..cool + tag`) và `out[-1].marking != "p"`, nối thêm `DynamicEvent(bar=cool, marking="p", sound=SOUND["p"], beat=0.0)` để `tag_bars` đầu của cool-down về lại `"p"`.

---

## 6. Ma trận Cân bằng Âm lượng đầy đủ cho 12 Bộ Nhạc cụ (`_VOICE_VOLUME_DB`)

### A. Quy trình đo tái lập (Reproducible Measurement Protocol)

Mọi con số RMS và Peak dBFS dưới đây được đo bằng script chuẩn hóa trên MuseScore 4.7.5 (`macOS`, thư viện MuseSounds cài đặt ở `state = 1`):
- **Fixture đo**: Bản nhạc 6 ô nhịp `4/4` ở `120 BPM` (`2.0 giây/ô`), hòa âm `Cmaj7`:
  - Ô 0 (`0.1s–1.8s`): chỉ `P5` phát nốt tròn ở `C6 (84)`, chữ `mp` (`velocity=64`).
  - Ô 1 (`2.1s–3.8s`): chỉ `P1` phát nốt tròn ở `G4 (67)`, chữ `mp` (`velocity=64`).
  - Ô 2 (`4.1s–5.8s`): chỉ `P2` phát nốt tròn ở `G3 (55)`, chữ `mp` (`velocity=64`).
  - Ô 3 (`6.1s–7.8s`): chỉ `P3` phát hợp âm đệm `E4+G4` (khuông 1) + `C3` (khuông 2) ở chữ `p` (`velocity=49`), **không có `<harmony>`** (tương đương sau khi gắn `<play>0</play>`).
  - Ô 4 (`8.1s–9.8s`): chỉ `P3` phát cùng hợp âm đệm kèm `<harmony>` mặc định (để đối chứng mức lệch của Piano ẩn).
  - Ô 5 (`10.1s–11.8s`): chỉ `P4` phát 4 nốt đen `C2–G2–C3–G2` ở chữ `mp`.
- **Cách tính**: Trên WAV 32-bit float xuất ra từ `musescore_export`, cắt cửa sổ `[b * 2.0 + 0.1, b * 2.0 + 1.8]` giây của từng ô `b` (bỏ `0.1s` đầu và `0.2s` cuối để không dính attack/release sang ô cạnh), tính `rms_db = 20 * log10(sqrt(mean(x^2)))` và `peak_db = 20 * log10(max(|x|))`.
- **Kiểm tra Headroom / Chống Clipping**: Ngay cả ở mức cộng lớn nhất (`+10 dB` cho `Glockenspiel`/`Marimba`/`Contrabassoon`, `+12 dB` cho `Crotales`), Peak gốc của các sample này đều nằm ở `-40 dB` đến `-52 dB`, nên sau khi cộng gain, Peak vẫn nằm dưới **`-28 dBFS`** (cách trần `0 dBFS` hơn `28 dB`, tuyệt đối không bao giờ clip).

### B. Bảng Ma trận toàn bộ 12 Bộ Nhạc cụ (60 vị trí = 4 Variants × 3 Ensembles × 5 Parts)

Đối với `Clarinet in Bb` (xuất hiện ở cả `symphony wood` P2 với RMS `-41.2 dB` và `ambient choir` P1 với RMS `-46.4 dB`), mức tăng chung **`+4 dB`** đưa P2 của `symphony wood` lên `-37.2 dB` (nằm ngay dưới `Oboe` P1 `-38.2 dB`) và đưa P1 của `ambient choir` lên `-42.4 dB` (rõ trên nền `Tenors` P2 và `Violas` P3), nên **khóa đơn theo `voice.sound` trong `_VOICE_VOLUME_DB` hoàn toàn đáp ứng cả hai vai** mà không cần phức tạp hóa chữ ký của `_assign_installed_sounds`.

| Variant & Ensemble | `P5` Điểm cao | `P1` Giai điệu | `P2` Bè giữa | `P3` Hòa âm / Đệm *(sau `<play>0</play>`)* | `P4` Bass / Drone |
|---|---|---|---|---|---|
| **1. `symphony` · `classic`** | `Flute 1`<br>RMS `-47.9` $\rightarrow$ **`+5 dB`** | `Violins 1`<br>RMS `-38.1` $\rightarrow$ **`+2 dB`** | `Cellos`<br>RMS `-40.6` $\rightarrow$ **`+4 dB`** | `Piano`<br>RMS `-41.9` $\rightarrow$ **`-2 dB`** | `Electric Bass`<br>RMS `-29.6` $\rightarrow$ **`-6 dB`** |
| **2. `symphony` · `wood`** | `Piccolo`<br>RMS `-34.6` $\rightarrow$ **`0 dB`** | `Oboe`<br>RMS `-43.2` $\rightarrow$ **`+5 dB`** | `Clarinet in Bb`<br>RMS `-41.2` $\rightarrow$ **`+4 dB`** | `Harp`<br>RMS `-52.4` $\rightarrow$ **`+8 dB`** | `Contrabassoon`<br>RMS `-49.5` $\rightarrow$ **`+10 dB`** |
| **3. `symphony` · `brass`** | `Glockenspiel`<br>RMS `-58.6` $\rightarrow$ **`+10 dB`** | `Trumpet`<br>RMS `-44.6` $\rightarrow$ **`+6 dB`** | `Trombone`<br>RMS `-50.2` $\rightarrow$ **`+8 dB`** | `French Horns a6`<br>RMS `-34.8` $\rightarrow$ **`-5 dB`** | `Tuba`<br>RMS `-32.2` $\rightarrow$ **`-5 dB`** |
| **4. `jazz` · `classic`** | `Vibraphone`<br>RMS `-41.6` $\rightarrow$ **`+3 dB`** | `Alto Saxophone`<br>RMS `-33.1` $\rightarrow$ **`0 dB`** | `Tenor Saxophone`<br>RMS `-35.9` $\rightarrow$ **`0 dB`** | `Suitcase Piano`<br>RMS `-35.1` $\rightarrow$ **`-2 dB`** | `Electric Bass`<br>RMS `-29.6` $\rightarrow$ **`-6 dB`** |
| **5. `jazz` · `soul`** | `Electric LP - Clean`<br>RMS `-45.1` $\rightarrow$ **`+4 dB`** | `Trumpet`<br>RMS `-44.6` $\rightarrow$ **`+6 dB`** | `Trombone`<br>RMS `-50.2` $\rightarrow$ **`+8 dB`** | `Wurly 200A`<br>RMS `-39.7` $\rightarrow$ **`0 dB`** | `Electric Bass`<br>RMS `-29.6` $\rightarrow$ **`-6 dB`** |
| **6. `jazz` · `organ`** | `Electric SC - Clean`<br>RMS `-42.4` $\rightarrow$ **`+4 dB`** | `Soprano Saxophone`<br>RMS `-31.8` $\rightarrow$ **`0 dB`** | `Baritone Saxophone`<br>RMS `-35.4` $\rightarrow$ **`0 dB`** | `Hammond Organ`<br>RMS `-42.2` $\rightarrow$ **`0 dB`** | `Electric Bass`<br>RMS `-29.6` $\rightarrow$ **`-6 dB`** |
| **7. `minimalist` · `classic`** *(MS Basic)* | `Synth Bell`<br>RMS `-29.1` $\rightarrow$ **`0 dB`** | `Synth Arpeggio`<br>RMS `-28.0` $\rightarrow$ **`0 dB`** | `Synth Pad`<br>RMS `-32.0` $\rightarrow$ **`0 dB`** | `Synth Pulse`<br>RMS `-35.8` $\rightarrow$ **`0 dB`** | `Sub-Bass`<br>RMS `-28.0` $\rightarrow$ **`0 dB`** |
| **8. `minimalist` · `mallet`** | `Crotales`<br>RMS `-63.7` $\rightarrow$ **`+12 dB`** | `Marimba`<br>RMS `-53.8` $\rightarrow$ **`+10 dB`** | `Full Choir`<br>RMS `-50.9` $\rightarrow$ **`+8 dB`** | `Harpsichord`<br>RMS `-41.0` $\rightarrow$ **`0 dB`** | `Electric Bass`<br>RMS `-29.6` $\rightarrow$ **`-6 dB`** |
| **9. `minimalist` · `guitar`** | `Flute 2`<br>RMS `-34.6` $\rightarrow$ **`0 dB`** | `Acoustic Steel Plucked`<br>RMS `-47.6` $\rightarrow$ **`+8 dB`** | `Cellos`<br>RMS `-40.8` $\rightarrow$ **`+4 dB`** | `Upright Piano`<br>RMS `-44.6` $\rightarrow$ **`0 dB`** | `Electric Bass`<br>RMS `-29.6` $\rightarrow$ **`-6 dB`** |
| **10. `ambient` · `classic`** | `Celesta`<br>RMS `-37.7` $\rightarrow$ **`+6 dB`** | `Alto Flute`<br>RMS `-39.3` $\rightarrow$ **`0 dB`** | `Bass Flute`<br>RMS `-40.4` $\rightarrow$ **`-5 dB`** | `French Horn`<br>RMS `-40.8` $\rightarrow$ **`0 dB`** | `Contrabasses`<br>RMS `-32.7` $\rightarrow$ **`0 dB`** *(hạ từ `+4`)* |
| **11. `ambient` · `breath`** | `Handchimes`<br>RMS `-31.1` $\rightarrow$ **`0 dB`** | `English Horn`<br>RMS `-29.9` $\rightarrow$ **`0 dB`** | `Bass Clarinet`<br>RMS `-40.6` $\rightarrow$ **`0 dB`** | `Trombones a3`<br>RMS `-38.7` $\rightarrow$ **`0 dB`** | `Contrabassoon`<br>RMS `-50.7` $\rightarrow$ **`+10 dB`** |
| **12. `ambient` · `choir`** | `Handbells`<br>RMS `-29.2` $\rightarrow$ **`0 dB`** | `Clarinet in Bb`<br>RMS `-46.4` $\rightarrow$ **`+4 dB`** | `Tenors`<br>RMS `-46.4` $\rightarrow$ **`+5 dB`** | `Violas`<br>RMS `-47.7` $\rightarrow$ **`+5 dB`** | `Basses`<br>RMS `-40.0` $\rightarrow$ **`0 dB`** |

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
    "Oboe": 5,
    "Trumpet": 6,
    "Clarinet in Bb": 4,
    "Marimba": 10,
    "Acoustic Steel Plucked": 8,
    "Cellos": 4,
    "Trombone": 8,
    "Full Choir": 8,
    "Tenors": 5,
    "Bass Flute": -5,
    "Piano": -2,
    "Harp": 8,
    "French Horns a6": -5,
    "Suitcase Piano": -2,
    "Violas": 5,
    "Electric Bass": -6,
    "Contrabassoon": 10,
    "Tuba": -5,
}
```

---

## 7. Danh mục thay đổi cụ thể trong Codebase

1. **`backend/app/sonify/model.py`**:
   - Thêm 3 trường có giá trị mặc định `()` trên `Score`:
     - `high_wedges: tuple[WedgeEvent, ...] = ()`
     - `high_dynamics: tuple[DynamicEvent, ...] = ()`
     - `comp_dynamics: tuple[DynamicEvent, ...] = ()`
   - Thêm 3 `@property` tương thích ngược: `flute_wedges`, `flute_dynamics`, `piano_dynamics`.
2. **`backend/app/sonify/dynamics.py`**:
   - Thêm `PIANO_VELOCITY: dict[str, int] = {"p": 46, "mp": 54, "mf": 62, "f": 68}`.
   - Thêm `effective_comp_band(band: str, bar: int | None = None) -> str` (hạ band qua `groove.chamber`, `groove.trio_thin`, `groove.half`).
   - Thêm `piano_marking(band: str) -> str` (`"p"` khi `band in ("p", "mp")`, `"mp"` khi `band in ("mf", "f")`).
3. **`backend/app/sonify/phrasing.py`**:
   - Mở rộng `left_hand(slot, *, velocity_at=None, every_bar_at=frozenset())` để nhận velocity giường và tập các ô đánh gốc mỗi ô mà không làm thay đổi lời gọi `left_hand(slot)` của `jazz.py`.
4. **`backend/app/sonify/render.py`**:
   - `_flute_and_violin_dovetail`: thêm tham số `ensemble: Ensemble = "classic"`, trả về `(flute_notes, yield_spans, flute_wedges, flute_dynamics)` theo đúng state machine và bảng chuyển trạng thái ở Mục 3.
   - `_bass_pattern` / `_bass_bar`: thêm tham số `under_cello: bool = False`, chỉ bật khi ô đó nằm trong `cello_lead_bars` (Cello kêu $\ge$ nửa ô nhịp), hạ bước `OCTAVE` về `ROOT`.
   - `_right_hand`: nhận thêm `bed_velocity_at`, `bed_marking_at`, `phrases`, trả về `(comp_notes, fill_marks)` với nội suy velocity fill theo Mục 5B.
   - Trong nhánh `symphony` của `_compose`: tính `eff_bands`, `bed_velocity_at`, `bed_marking_at`, `dense_left_bars`, dựng `comp_dynamics` và gán vào `Score`.
5. **`backend/app/sonify/musicxml.py`**:
   - Nâng cấp `_opening_p` thành `_opening_dynamic(dynamics, default)`: nếu `dynamics` có phần tử đầu tại `bar == 0` và `beat == 0.0` (bất kể `marking` là `"p"`, `"mp"` hay `"mf"`), dùng phần tử đó làm `opening_dynamic` của part và trả về `dynamics[1:]` để không bao giờ in trùng 2 chữ ở đầu ô 1.
   - `score_to_musicxml`: khi `score.variant == "symphony"`, lấy `high_open, high_rest = _opening_dynamic(score.high_dynamics, MELODY_DYNAMIC)` và truyền `score.high_wedges`, `high_rest`, `opening_dynamic=high_open` vào `_melody_part` của `P5`.
   - `_piano_part`: khi `score.variant == "symphony"`, lấy `comp_open, comp_rest = _opening_dynamic(score.comp_dynamics, PIANO_DYNAMIC)`, in `comp_open` ở `bar == 0`, và trong vòng lặp `staff == 1` dùng `flush(event.beat)` để xả `comp_rest` tại đúng phách (`beat == 0.0` trước `<harmony>` / guide tone, và `beat == fill_beat` trước nốt fill đầu tiên).
6. **`backend/app/sonify/span.py`, `movement_frame.py`, `daily_frame.py`**:
   - `slice_score`: dịch `high_wedges`, `high_dynamics`, `comp_dynamics`.
   - `apply_span_frame` & `apply_daily_frame`: cắt `high_wedges`, `high_dynamics`, `comp_dynamics` theo đúng chữ ký riêng của từng file và thuật toán suy `body_mark` ở Mục 5C; gán `velocity = 49` chỉ cho các nốt có cao độ do `_curtain_comp` sinh ra ở warm-up / `tag_bars` (trước `with_rests`, không chạm vào `_kept_comp`).
7. **`backend/app/sonify/audio.py`**:
   - Thêm `_VOICE_VOLUME_DB` và `_mute_mscx_harmony(mscx_bytes)` vào `_assign_installed_sounds`.
   - Tăng `RECAP_REVISION` từ `"28"` lên **`"29"`**, và `SPAN_REVISION` từ `"14"` lên **`"15"`**.
8. **`backend/tests/test_harmony.py`, `test_sonify_plan.py`, `test_daily_frame.py`, `test_recap.py`**:
   - Cập nhật `test_chamber_bar_drops_the_symphony_right_hand` trong `test_sonify_plan.py` (dòng 928) mở tuple `notes, _ = _right_hand(...)`.
   - Trong `test_harmony.py`, cập nhật đầy đủ các assertion Piano/velocity hiện hữu bị ảnh hưởng bởi thiết kế mới:
     1. `test_phrase_regime_uses_the_downbeat_window` (dòng 187–197): kiểm tra ô không có fill theo `len(right) == 3` (thay vì `not any(note.velocity for note in right)` vì guide tones đã mang velocity giường), và cập nhật `expected_left` khi ô có `eff_band == "f"` hoặc `groove.rally`.
     2. `test_musicxml_writes_harmony_and_letter_dynamics` & `_assert_measure_timing` (dòng 529–530, 587–600): cập nhật assertion các thẻ `<dynamics>` của `piano` (`P3`) theo `score.comp_dynamics`, kiểm tra `dynamics` attribute của guide tones (`right[:2]`) và fill (`right[2:]`) theo `PIANO_VELOCITY` / nội suy fill, và cập nhật `expected_left` cho các ô đánh gốc mỗi ô (`eff_band == "f"` ở đầu/cuối phiên của bài test).
     3. `test_piano_answers_a_held_cadence_under_the_violin` (dòng 897–905): cập nhật tuple `(beat, midi, duration_beats, velocity)` của `right` tại `bar == 4` (guide tones ở `beat == 0.0` nhận velocity giường `62` của band `mf`, 3 nốt fill nhận velocity nội suy của mức `mf`).
     4. `test_fills_stay_in_the_cadence_tail_on_chord_tones` (dòng 930–936): nhận diện nốt fill bằng `note.staff == 1 and note.midi is not None and note.beat > 0.0` (thay vì `note.velocity is not None`).
   - Chạy toàn bộ test suite (`pytest`) và bổ sung đầy đủ các bài test mới ở Mục 8.

---

## 8. Tiêu chí Kiểm tra (Test Plan)

- **Flute (`P5`)**:
  - Đỉnh hairpin trùng móc giá gốc cao nhất đầu tiên (`span_apex` từ `pitches`), kể cả khi `flute_harmony_pitch` đã gập nốt đó xuống một quãng tám.
  - Khi Flute vào ngay tại đỉnh (`span_apex - arc_start < WEDGE_MIN`, Hình thái 3), `P5` mở chữ `mf` tại `arc_start` kèm `diminuendo`, rồi in lại `mp` ở tiếng đánh mới kế tiếp; nếu đoạn đó rơi vào `(bar=0, beat=0.0)`, ô 1 chỉ in đúng một thẻ `<dynamics><mf/></dynamics>` (không bị trùng với `mp` mặc định).
  - Đoạn 1 nốt ngân dài ở đỉnh ($\ge 4$ móc, Hình thái 2) sinh cặp `< >` với đỉnh ở giữa ngân (`mid_apex`).
  - **Chuyển trạng thái sau `crescendo` trần (Trường hợp 4a)**: Đoạn Flute kết thúc ngay tại đỉnh (`sounding_end - span_apex < WEDGE_MIN`, chỉ có `crescendo`) đặt `effective_level = "drifted"`; đoạn Flute kế tiếp nếu thuộc Hình thái 1/2 sẽ in lại `"mp"` tại `arc_start`, còn nếu thuộc Hình thái 3 sẽ in `"mf"` tại `arc_start`.
  - **Đoạn có nốt đầu buộc nối qua ranh giới phrase (`tie_first_in == True`)**: Không đặt chữ dynamic hay mở `<wedge>` trên nốt nối dây (`r_i == 0`), mà đặt tại `first_attack` (`merged_flute_runs[1]`), hoặc bỏ qua nếu cả đoạn chỉ có 1 run nối dây (`first_attack is None`).
  - `phrase.rise < MIN_RISE`: Flute đứng ở velocity `64`, không hairpin, không in `mf`. Band `p`/`mp` (không breakout): velocity không vượt `72` và cặp `< >` cân bằng không in thừa `"mp"` ở đoạn sau (Trường hợp 3). Band `mf`/`f` hoặc `BREAKOUT`: đỉnh chạm `80`.
  - `ensemble == "brass"` (`Glockenspiel`): khi `phrase.rise >= MIN_RISE` và đoạn chỉ có 1 run, không sinh `<wedge>` và velocity bằng `peak`; khi `phrase.rise < MIN_RISE`, velocity giữ `64`; đoạn $\ge 2$ runs có `<wedge>` như sáo.
- **Violin (`P1`), Cello (`P2`) & Bass (`P4`)**:
  - `lead_wedges` và `support_wedges` giữ nguyên hành vi hiện tại (pass toàn bộ test trong `test_harmony.py`).
  - Khi Cello hát chính ở ô `bar` (tổng thời lượng nốt Cello trong ô $\ge$ nửa ô nhịp), Bass ở ô đó thay bước `OCTAVE` bằng `ROOT`. Các ô chỉ có nốt dovetail ngắn của Cello (`<` nửa ô) hoặc các ô Violin hát giữ nguyên pattern Bass hiện tại.
- **Piano (`P3`) & Frame (`daily_frame`, `movement_frame`)**:
  - Giường chỉ in `p` và `mp` theo `effective_comp_band` (`chamber`, `trio_thin`, `half`). Velocity giường nhận đúng `46 / 54 / 62 / 68`.
  - Ô `f` (sau groove) hoặc `groove.rally` đánh gốc tay trái mỗi ô trên Giao hưởng; `left_hand` của Jazz giữ nguyên đánh mỗi 2 ô.
  - Chữ fill (`mp` hoặc `mf`) đứng đúng tại `beat` bắt đầu fill trên khuông 1; hợp âm đệm kế tiếp in lại chữ giường ở `beat = 0.0`. Velocity các nốt trong fill khớp công thức nội suy tuyến tính (`58 → 66`, `64 → 56`, `74 → 80`, `80 → 72`, hoặc `64`/`80` khi 1 nốt / ngang). Fill bị `caesura` cắt sạch không sinh chữ fill.
  - **Cắt/nối qua Frame**: Nốt do `_curtain_comp` sinh ở warm-up / `tag_bars` có `velocity = 49`, trong khi nốt thân bài (`_kept_comp`) giữ nguyên velocity `46/54/62/68` và velocity fill. Khi chữ giường tại ô `body` là `"mp"` (suy từ sự kiện giường `beat == 0.0` gần nhất $\le body$), cả khung tĩnh lẫn khung động đều in `"mp"` tại `(bar=body, beat=0.0)` và không in chữ trên các ô khung nghỉ.
- **Audio & `<Harmony>` (`audio.py`)**:
  - Unit test với fixture `.mscz` chứa `<Harmony><harmonyInfo>...</harmonyInfo></Harmony>` trong `score.mscx` xác nhận `_assign_installed_sounds` chèn `<play>0</play>` (idempotent) và gắn đúng `volumeDb` từ `_VOICE_VOLUME_DB`, kèm smoke test tích hợp qua `musescore_export` (tự động `pytest.skip` khi môi trường CI/máy chạy test không cài đặt binary MuseScore) xác nhận file `.mscz` đã gắn `<play>0</play>` xuất WAV thành công.
  - Jazz, Tối giản và Ambient giữ nguyên số chữ và số hairpin trên cả 5 bè trong MusicXML.
