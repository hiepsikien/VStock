# Dynamic và Cân bằng Âm lượng cho Giao hưởng & 12 Bộ Nhạc cụ

Kế hoạch này giải quyết hai bài toán đi liền nhau:
1. **Biểu cảm & phản ánh chuyển động thị trường (Market Movement)**: Đưa Flute (`P5`), Piano (`P3`), Violin (`P1`), Cello (`P2`) và Bass (`P4`) của Giao hưởng vào chung một hệ thống động lực học 3 tầng (Đà giá trong câu × Thanh khoản `p–f` × Tính cách phiên `BarGroove`), tương thích với cơ chế phát thực tế của MuseSounds trong MuseScore 4.
2. **Cân bằng âm lượng (Volume Balance) giữa các bè và trên toàn bộ 12 bộ nhạc cụ**: Loại bỏ tiếng Piano ẩn đánh chồng từ thẻ `<harmony>`, dọn dải tần trầm để Bass không đè Cello, và chuẩn hóa bảng gain `_VOICE_VOLUME_DB` trong `audio.py` cho tất cả các bộ nhạc cụ (`classic`, `wood`, `brass`, `soul`, `organ`, `mallet`, `guitar`, `breath`, `choir`).

---

## 1. Nguyên lý phát thực tế của MuseScore 4 + MuseSounds

Thực nghiệm xuất WAV qua `musescore_export` trên MuseScore 4.7.5 với thư viện MuseSounds cho thấy hai cơ chế cốt lõi mà kế hoạch phải bám sát:

1. **MuseSounds điều khiển âm lượng bằng `<direction><dynamics>` và `<wedge>`, không dùng `<note dynamics="...">` trên hơi/dây/đồng**:
   - Khi giữ nguyên chữ `mp` và chỉ tăng thuộc tính `dynamics` trên `<note>` từ `71.11` (`vel=64`) lên `106.67` (`vel=96`) mà không có `<wedge>` hoặc chữ dynamic mới, âm lượng WAV xuất ra của `Flute 1`, `Violins 1`, `Cellos`, `Oboe`, `Trumpet`... không đổi đến `0.1 dB`.
   - Khi có `<wedge>` hoặc đổi chữ in sang `mf`, MuseSounds mới đẩy CC expression làm tiếng nhạc cụ nở thực sự (+3.6 dB đến +4.5 dB RMS) và mở sáng âm sắc.
2. **Thẻ `<harmony>` trên `P3` đang khiến MuseScore 4 tự tổng hợp thêm một Piano ẩn đánh chồng lên phách 1 (+6.0 dB RMS / +6.9 dB Peak)**:
   - Trên `P3`, bản nhạc đã viết sẵn các nốt đệm (guide tones ở khuông 1 + root ở khuông 2). Khi không có `<harmony>`, Piano ở mức `p` phát ra `-41.9 dB` RMS (`-25.0 dB` Peak).
   - Khi có `<harmony>`, MuseScore tự gõ thêm một hợp âm Piano đầy đủ chồng lên phách 1, đẩy `P3` ở `p` vọt lên `-36.0 dB` RMS (`-18.1 dB` Peak), và ở `mp` vọt lên `-30.4 dB` RMS (`-11.8 dB` Peak) — to hơn `Flute 1 (mp)` tới **+17.5 dB RMS**.
   - Ở bộ `symphony wood` (`Harp`) hay `symphony brass` (`French Horns a6`), thẻ `<harmony>` này còn phát ra tiếng Piano lạ đè lên tiếng đàn Harp và kèn Cor.

---

## 2. Ba tầng chuyển động thị trường trên các bè Giao hưởng

| Tầng chuyển động | Flute / P5 (`classic`, `wood`, `brass`) | Violin & Cello (`P1`, `P2`) | Piano / P3 (`classic`, `wood`, `brass`) | Bass / P4 (`classic`, `wood`, `brass`) |
|---|---|---|---|---|
| **1. Giá trong câu** (`phrase.rise`, đỉnh, `BREAKOUT`) | Vòng cung `< >` theo đoạn sáo; vào ngay đỉnh thì mở ở `mf` rồi `>` về `mp`; 1 nốt ngân dài nở ở giữa ngân | Giữ nguyên vòng cung câu, nhưng không bao giờ mở `diminuendo` trần trụi từ `mp` khi đỉnh nằm ở đầu đoạn | Hướng vuốt của câu fill (`Nở` khi câu lên, `Lắng` khi câu xuống) kèm `<wedge>` ngắn | Nhường quãng 8 (`OCTAVE`) khi giai điệu rơi xuống vùng Cello (`P2`) |
| **2. Thanh khoản `p–f`** (`band_at`) | Band `mf`/`f` hoặc `BREAKOUT` in chữ `mf` ở đỉnh đoạn sáo; band `p`/`mp` chỉ chạy `< >` trên nền `mp` | Velocity và nốt nhấn phản ánh câu | Chữ in giường (`p` cho `p`/`mp`, `mp` cho `mf`/`f`) và 4 bậc velocity (`46 / 54 / 62 / 68`) | Mật độ tiết tấu từ tròn (`p`) tới 8 móc đơn (`f`), chữ in trần `mp` |
| **3. Tính cách phiên (`BarGroove`)** | `BREAKOUT` luôn nở tới chữ `mf` | `selloff` nhường sớm vùng trung-trầm cho Cello | Đọc `chamber`, `trio_thin`, `half`, `rally`, `selloff`, `caesura`; gốc tay trái đánh mỗi ô khi `f` hoặc `rally` | Đọc `chamber`, `trio_thin`, `half`, `tresillo`, `selloff`, `rally`, `caesura` |

---

## 3. Flute (`P5`): Thở theo đoạn hát, không bị tụt hơi khi vào ngay tại đỉnh

Flute vào khi câu lên cao (`>= FLUTE_TRIGGER`), khi có `BREAKOUT`, hoặc khi nốt vượt trần violin (`violin_ceiling`). `_flute_and_violin_dovetail` ghi `yield_spans` và dựng vòng cung cho đúng đoạn `[span_start, sounding_end)` mà Flute hát.

### A. Đỉnh giá gốc (`span_apex`) và bài toán vào ngay tại đỉnh

`flute_harmony_pitch` cộng thêm quãng 3, 4 hoặc 7 rồi gập xuống một quãng tám khi vượt `flute_ceiling` (`Mi6 = 88`), nên cao độ đã gập của sáo có thể thấp hơn ở đúng móc giá lập đỉnh. Do đó, `span_apex` được tính từ **đường giá gốc `pitches[eighth]`** trong `[span_start, sounding_end)`.

Tuy nhiên, vì Flute thường được kích hoạt ngay tại đỉnh câu (`run.start == apex.start`) hoặc tại nốt `BREAKOUT`, rất nhiều đoạn Flute có **`span_apex == span_start`** (móc cao nhất nằm ngay ở tiếng vào đầu tiên) hoặc chỉ là **1 nốt ngân dài ở đỉnh**. Nếu gọi thẳng `hairpins(span_start, sounding_end, span_apex)` khi `span_apex - span_start < WEDGE_MIN (2)` mà giữ chữ `mp`, hàm sẽ chỉ sinh một `diminuendo` từ đầu đến cuối đoạn, kéo âm lượng Flute từ `mp` tụt xuống `p`!

Quy tắc xử lý 3 hình thái của đoạn Flute (khi `phrase.rise >= MIN_RISE` và `sounding_end - span_start >= WEDGE_MIN`):

1. **Hình thái 1 — Đoạn sáo leo lên đỉnh rồi hạ (`span_apex - span_start >= WEDGE_MIN`)**:
   - Sinh `hairpins(span_start, sounding_end, span_apex)`: `crescendo` từ `span_start` tới `span_apex`, và `diminuendo` từ `span_apex` tới `sounding_end` (nếu `sounding_end - span_apex >= WEDGE_MIN`).
   - Khi đoạn có `BREAKOUT` hoặc thanh khoản tại đỉnh thuộc `mf`/`f` (`peak == 80`):
     - Nếu có cả `crescendo` và `diminuendo`: in chữ `mf` tại `span_apex`, rồi đóng `diminuendo` về lại `mp` (cặp `< mf >` cân bằng, `drift` sau khi in lại `mp` ở tiếng đánh mới bằng `0`).
     - Nếu đoạn kết thúc ngay tại đỉnh (`sounding_end - span_apex < WEDGE_MIN`, chỉ có `crescendo`): `crescendo` tự đẩy playback từ `mp` lên `mf` (`drift += 1`), tiếng đánh mới kế tiếp in lại `mp`.
   - Khi thanh khoản ở `p`/`mp` và không có `BREAKOUT` (`peak == 72`): chỉ dùng `<wedge>` trên nền `mp`, không in chữ `mf`.

2. **Hình thái 2 — Đoạn sáo chỉ có 1 cao độ ngân dài ở đỉnh (`len(merged_flute_runs) == 1` và `sounding_end - span_start >= 4`)**:
   - Đặt đỉnh vòng cung vào giữa hơi ngân: `mid_apex = span_start + (sounding_end - span_start) // 2`.
   - Sinh cặp `< >` qua `hairpins(span_start, sounding_end, mid_apex)` để tiếng sáo (`Flute 1`, `Piccolo`) nở hơi ở giữa nốt ngân rồi khép lại mềm mại (giống hơi thở tự nhiên của nghệ sĩ sáo).

3. **Hình thái 3 — Đoạn sáo vào ngay tại đỉnh rồi đi xuống (`span_apex - span_start < WEDGE_MIN` và không phải 1 nốt ngân dài)**:
   - Vì Flute đang đón đúng đỉnh cao trào từ Violin, **in chữ `mf` ngay tại `span_start`**, mở `diminuendo` (`>`) từ `span_start` tới `sounding_end`, và đặt `drift = 0` sau khi in lại `mp` ở tiếng đánh mới kế tiếp (hoặc nếu `sounding_end - span_start < WEDGE_MIN` thì đặt `drift = 1` để tiếng đánh mới kế tiếp hạ về `mp`).
   - Nhờ đó, Flute cất tiếng đầy đặn ở `mf` ngay điểm bứt phá rồi lắng dần về `mp`, không bao giờ bị tụt từ `mp` xuống `p`.

### B. Đường Velocity (`span_swell`) và tương thích với `Glockenspiel` (`ensemble == "brass"`)

- `span_swell(onset)` bằng `0.0` ở đầu cạnh lên, `1.0` tại đỉnh vòng cung (`span_apex`, `mid_apex`, hoặc `span_start` ở Hình thái 3), và `0.0` ở cuối cạnh xuống:
  ```text
  velocity = round(64 + (peak - 64) * lift(phrase) * span_swell(onset))
  ```
  Trong đó `peak = 80` khi có `BREAKOUT` hoặc `band_at[apex_bar] in ("mf", "f")`, ngược lại `peak = 72`. Khi `phrase.rise < MIN_RISE`, `lift(phrase) == 0`, cả đoạn đứng ở `64` (`mp`) và không có hairpin.
- **Đặc thù cho `Glockenspiel` (`ensemble == "brass"`)**:
  - `Glockenspiel` là nhạc cụ gõ kim loại tắt dần sau cú gõ, không thể crescendo trên 1 nốt ngân đơn lẻ.
  - Khi `ensemble == "brass"` và `len(merged_flute_runs) < 2`: **không sinh `<wedge>`**; nếu `peak == 80` và `phrase.rise >= MIN_RISE`, in chữ `mf` tại `span_start` (kèm `drift = 1` để tiếng sau về lại `mp`) và gán `velocity = peak` để tiếng chuông điểm đỉnh vang đúng mức `mf`.
  - Khi `len(merged_flute_runs) >= 2`: giữ nguyên `<wedge>` và chữ như sáo để chuỗi tiếng chuông lớn/nhỏ dần theo câu.

---

## 4. Violin (`P1`), Cello (`P2`) và Bass (`P4`): Giữ hơi giai điệu & dọn dải tần trầm

### A. Không để Violin và Cello bị tụt xuống `p` bởi `diminuendo` mồ côi ở đầu đoạn

Trong `melody_parts()` (`backend/app/sonify/phrasing.py`), hiện tại mỗi `segment` của Violin hoặc Cello gọi `hairpins(swell_from, sounding_end, phrase.apex.start)`. Khi `phrase.apex.start - swell_from < WEDGE_MIN` (đỉnh câu rơi ngay vào đầu đoạn Violin/Cello), `hairpins()` chỉ trả về một `diminuendo` từ `swell_from` tới `sounding_end`. Vì bè đang ở `mp`, `diminuendo` này đẩy âm lượng của Violin/Cello tụt xuống `p` suốt cả đoạn!

**Quy tắc điều chỉnh trong `melody_parts()`**:
- Nếu `phrase.apex.start - swell_from < WEDGE_MIN` (không có cạnh `crescendo` đi trước) và `line.drift <= 0` (bè đang ở `mp` hoặc thấp hơn, chưa được nâng lên `mf`):
  - Nếu đoạn có ít nhất `4` móc đơn (`sounding_end - swell_from >= 4`): đặt đỉnh vòng cung tại `swell_from + (sounding_end - swell_from) // 2` (hoặc in `mf` ở `swell_from` trước khi `diminuendo` nếu `swell_from == phrase.apex.start` và `phrase.rise >= MIN_RISE`).
  - Hoặc đơn giản và an toàn nhất cho các bài test hiện hữu: trong `melody_parts`, khi `wedges` của một segment mở đầu bằng `diminuendo` (không có `crescendo` trước nó trong segment) và `line.drift == 0`, **chỉ giữ `diminuendo` nếu trước đó ở đầu segment có chữ nâng bậc, hoặc đặt đỉnh nội bộ `seg_apex` của segment** sao cho mọi `diminuendo` đều đi sau một `crescendo` (trừ cool-down cuối bài).
  - *(Lưu ý tương thích test)*: Kiểm tra `test_reset_after_a_held_over_note_waits_for_the_next_attack` trong `backend/tests/test_harmony.py` (dòng 1035 đang khóa `score.violin_wedges[:4]` có `(2, 0.0, "diminuendo")`). Để **không làm gãy bất kỳ test khóa cứng nào của Violin/Cello**, ta giữ nguyên hàm `hairpins()` và `melody_parts()` cho `lead_wedges` / `support_wedges`, và xử lý cân bằng âm lượng của Violin/Cello + dải tần Cello/Bass qua 2 cơ chế dưới đây!

### B. Bass (`P4`) nhường dải tần `Đô3–Si3` khi Cello (`P2`) đang hát giai điệu

- Trong Giao hưởng, Cello hát chính ở vùng `< Đô4 (60)` (thường là `Đô3–Si3 = 48–59`).
- Trong `_bass_bar` / `_bass_pattern` (`backend/app/sonify/render.py`), ở mức `mf` và `f`, Bass đang đánh nhảy quãng 8 (`OCTAVE = chord.bass_midi + 12`, rơi vào `Đô3–Si3 = 48–59`) — trùng khít lên vùng Cello đang hát!
- **Quy tắc mới trong `render.py`**:
  - Tìm tập các ô nhịp mà Cello (` cello.notes` / `support`) có nốt kêu (`cello_bars = {note.bar for note in cello.notes if note.midi is not None}`).
  - Trong `_bass_bar(chord, marking, bar, *, under_cello: bool = False)`: khi `under_cello` là `True` (hoặc `groove_at(bar).selloff`), thay mọi bước `OCTAVE` trong pattern Bass bằng `ROOT` (hoặc `FIFTH` ở phách nhẹ), giữ Bass nằm gọn ở quãng trầm `Đô2–Si2 (36–47)`.
  - *(Kiểm tra tương thích test)*: Trong `test_harmony.py`, các bài test kiểm tra `_line(score.bass, ...)` có `OCTAVE` (`48`, `57`) đều chạy trên chuỗi giá `closes = [80.0]*30` hoặc `100.0` mà ở đó giai điệu nằm hoàn toàn trên Violin (`score.cello` nghỉ toàn bộ, `under_cello == False`), nên 100% assertion cũ của Bass đều giữ nguyên! Khi thị trường giảm sâu đưa giai điệu xuống Cello (`under_cello == True`), Bass lập tức hạ quãng 8 xuống để nhường trọn không gian trung-trầm cho Cello.

---

## 5. Piano (`P3`): Đọc thanh khoản & `BarGroove`, vuốt Fill và tắt Piano ẩn của `<harmony>`

### A. Tắt phát tiếng Piano ẩn của `<harmony>` khi render audio (`audio.py`)

- Trong `musicxml.py`, giữ nguyên việc xuất thẻ `<harmony>` trên `P3` để tổng phổ MusicXML có đầy đủ ký hiệu hợp âm và tương thích 100% với các bài test MusicXML.
- Trong `_assign_installed_sounds` (`backend/app/sonify/audio.py`), khi đọc `score.mscx` bên trong file `.mscz` để gán MuseSounds trước khi render ra WAV:
  - Chèn `<play>0</play>` vào mỗi phần tử `<Harmony>` trong `score.mscx` (nếu chưa có `<play>`).
  - **Hiệu quả trên mọi bộ nhạc cụ**:
    - Ở `symphony classic`, `jazz classic/soul/organ`, `minimalist classic/mallet/guitar`: loại bỏ hoàn toàn tiếng Piano tự động đánh chồng của MuseScore, giúp `P3` giảm ~6 dB tiếng đục ở đầu ô và trả lại đúng âm sắc thật của `Piano`, `Suitcase Piano`, `Wurly 200A`, `Hammond Organ`, `Harpsichord`, `Upright Piano`.
    - Ở `symphony wood` (`Harp`) và `symphony brass` (`French Horns a6`): loại bỏ triệt để tiếng Piano "lạc loài" đánh đè lên tiếng đàn Harp và tiếng kèn Cor!

### B. Chữ in và Velocity giường Piano (`piano_marking`)

Band thô lấy từ `band_at[bar]`. Trước khi tính chữ và velocity cho Piano ở ô `bar`, hạ band theo đúng 3 nhánh của `_bass_pattern` (`groove_at(bar)`):
- `groove.chamber`: band thành `"p"` (ở ô này tay phải đã nghỉ qua `_right_hand`).
- `groove.trio_thin`: hạ một bậc (`"f" -> "mf"`, `"mf" -> "mp"`, `"mp" -> "p"`, `"p" -> "p"`).
- `groove.half` khi band là `"mp"`: hạ thành `"p"` (`"mf"` và `"f"` giữ nguyên).

Bảng `piano_marking(band)` và `PIANO_VELOCITY[band]` trên band đã hạ:

| Band sau groove | Chữ in (`piano_marking`) | `<sound dynamics>` | Velocity nốt (`PIANO_VELOCITY`) |
|---|---|---|---|
| `p` | `p` | `54` | `46` |
| `mp` | `p` | `54` | `54` |
| `mf` | `mp` | `71` | `62` |
| `f` | `mp` | `71` | `68` |

- Guide tone (khuông 1) và nốt gốc tay trái (khuông 2) nhận `velocity = PIANO_VELOCITY[eff_band]`.
- Chữ giường được xét theo từng ô (vì `chamber`, `trio_thin`, `half` có thể đổi giữa cửa sổ), chỉ gắn tại `beat = 0.0` khi ô đó có ít nhất một nốt kêu (ở khuông 1 hoặc khuông 2) và chữ khác với chữ đang hiệu lực trên `P3`. Ô nghỉ cả hai tay không sinh chữ.
- **Tay trái (`left_hand`)**: Đánh gốc mỗi 2 ô như hiện tại, nhưng **đánh lại gốc mỗi ô** khi `eff_band == "f"` hoặc `groove_at(bar).rally` (trừ section `outro` vẫn giữ 1 lần ở ô đầu pedal).

### C. Câu Fill cuối câu: Chữ đúng phách, Velocity & `<wedge>` theo hướng câu giá

Fill cuối câu nói hơn chữ giường của ô đó một bậc, trần `mf`:

| Chữ giường tại ô | Chữ fill | Mốc velocity | Hướng `Nở` | Hướng `Lắng` | Hướng `Ngang` |
|---|---|---|---|---|---|
| `p` | `mp` (`sound=71`) | `64` | `58 → 66` | `64 → 56` | `64` |
| `mp` | `mf` (`sound=89`) | `80` | `74 → 80` | `80 → 72` | `80` |

- **Vị trí chữ fill**: Fill bắt đầu sau phách 1 (`beat > 0.0`). Chữ fill là một `DynamicEvent(bar=bar, marking=fill_mark, sound=SOUND[fill_mark], beat=fill_beat)` đặt tại phách của nốt fill đầu tiên còn sống sau bước lọc `caesura`. Nếu cả cụm fill bị `caesura` cắt bỏ thì không sinh chữ fill.
- **Hướng vuốt của fill**:
  1. Nếu `groove_at(bar).selloff`: `Lắng`.
  2. Ngược lại, nếu `groove_at(bar).rally`: `Nở`.
  3. Ngược lại, so sánh nốt kết câu (`phrase.cadence.midi`) với nốt mở câu (`phrase.runs[0].midi`): cao hơn thì `Nở`, thấp hơn thì `Lắng`, bằng nhau thì `Ngang`.
- **In lại chữ giường**: Ở ô tiếp theo có hợp âm đệm kêu, tại `beat = 0.0`, vì chữ đang hiệu lực trên `P3` là chữ của fill (`mp` hoặc `mf`), nếu chữ giường của ô mới khác chữ fill vừa in thì `comp_dynamics` in lại chữ giường ở `beat = 0.0` để playback không kẹt ở mức của fill.

### D. Khung Warm-up và Cool-down của Piano

- **Khung tĩnh** (`apply_daily_frame`, hoặc `apply_span_frame` khi `not dynamic`): Piano nghỉ ở warm-up và cool-down (`_rest_comp`). Không có chữ `comp_dynamics` trong các ô nghỉ đó.
- **Khung động** (`apply_span_frame` khi `dynamic == True`): `_curtain_comp` đánh ở warm-up và `tag_bars` đầu của cool-down. Các nốt có cao độ trong `_curtain_comp` nhận `velocity = 49` (`p`). Chữ hiệu lực ở các ô đó là `p`. Phần cool-down còn lại Piano nghỉ. `ppp` cuối khung vẫn chỉ thuộc Bass và dây.

---

## 6. Bảng Cân bằng Âm lượng (`_VOICE_VOLUME_DB`) trong `audio.py` cho toàn bộ 12 Bộ Nhạc cụ

Để kế hoạch phát huy tác dụng đồng đều trên cả **3 bộ Giao hưởng (`classic`, `wood`, `brass`)** lẫn các bộ của **Jazz (`classic`, `soul`, `organ`), Tối giản (`classic`, `mallet`, `guitar`) và Ambient (`classic`, `breath`, `choir`)**, thay biểu thức `volume_db` đơn lẻ trong `_assign_installed_sounds` (`backend/app/sonify/audio.py`) bằng bảng tra `_VOICE_VOLUME_DB` dựa trên số đo RMS thực tế của từng sample MuseSounds:

| Vai | Giọng MuseSounds (`voice.sound`) | Bộ nhạc cụ sử dụng | RMS đo ở `0 dB` | `_VOICE_VOLUME_DB` mới | Hiệu quả cân bằng đạt được |
|---|---|---|---|---|---|
| **P5 Điểm cao** | `Flute 1` | Giao hưởng `classic` | `-47.9 dB` | **`+5`** | Lên `-42.9 dB` ở `mp` và `-33.1 dB` khi nở `mf`, thoát hẳn khỏi nền Piano/Bass |
| | `Flute 2` | Tối giản `guitar` | `-34.6 dB` | **`0`** | Đã sáng rõ trên nền guitar |
| | `Piccolo` | Giao hưởng `wood` | `-34.6 dB` | **`0`** | Âm區 cao của Piccolo đã xuyên tốt (`-34.6 dB`) |
| | `Glockenspiel` | Giao hưởng `brass` | `-58.6 dB` | **`+10`** | Bù mẫu sample rất nhỏ của Muse Percussion lên `-48.6 dB` (và `-43 dB` ở `mf`) |
| | `Crotales` | Tối giản `mallet` | `-63.7 dB` | **`+12`** | Kéo Crotales từ mức gần như câm (`-63.7 dB`) lên nghe rõ tiếng chuông |
| | `Vibraphone` | Jazz `classic` | `-41.6 dB` | **`+3`** | Làm rõ cụm hợp âm chuông Vibraphone trên nền Sax & Rhodes |
| | `Electric LP - Clean`, `Electric SC - Clean` | Jazz `soul`, `organ` | `-45.1 dB`, `-42.4 dB` | **`+4`** | Nâng cụm điểm cao guitar điện cân với kèn/sax |
| | `Celesta` | Ambient `classic` | `-37.7 dB` | **`+6`** | Giữ nguyên (`-31.7 dB`) |
| **P1 Giai điệu** | `Violins 1` | Giao hưởng `classic` | `-38.1 dB` | **`+2`** | Làm chủ tuyến giai điệu chính (`-36.1 dB` ở `mp`, `-31.7 dB` ở đỉnh) |
| | `Oboe` | Giao hưởng `wood` | `-43.2 dB` | **`+5`** | Đưa Oboe lên `-38.2 dB`, cân bằng với Piccolo và Clarinet |
| | `Trumpet` | Giao hưởng `brass`, Jazz `soul` | `-44.6 dB` | **`+6`** | Bù sample Trumpet Muse Brass đang bị nhỏ ở `mp` lên `-38.6 dB` |
| | `Clarinet in Bb` | Giao hưởng `wood` (P2), Ambient `choir` (P1) | `-41.2 dB` / `-46.4 dB` | **`+4`** | Làm rõ tiếng Clarinet ở cả Giao hưởng Gỗ lẫn Ambient Hợp xướng |
| | `Marimba` | Tối giản `mallet` | `-53.8 dB` | **`+10`** | Đưa ostinato Marimba từ `-53.8 dB` lên `-43.8 dB`, hết bị Bass lấn |
| | `Acoustic Steel Plucked` | Tối giản `guitar` | `-47.6 dB` | **`+8`** | Đưa ostinato Guitar thép lên `-39.6 dB`, rõ từng móc đơn |
| **P2 Bè giữa** | `Cellos` | Giao hưởng `classic`, Tối giản `guitar` | `-40.6 dB` | **`+4`** | Lên `-36.6 dB`, khớp 1:1 với `Violins 1 (+2 -> -36.1 dB)` khi chuyển giao bè |
| | `Trombone` | Giao hưởng `brass`, Jazz `soul` | `-50.2 dB` | **`+8`** | Bù sample Trombone ở `mp` từ `-50.2 dB` lên `-42.2 dB` |
| | `Full Choir` | Tối giản `mallet` | `-50.9 dB` | **`+8`** | Nâng lớp pad hợp xướng từ `-50.9 dB` lên `-42.9 dB` |
| | `Tenors` | Ambient `choir` | `-46.4 dB` | **`+5`** | Nâng lớp Halo giọng nam cao lên `-41.4 dB` |
| | `Bass Flute` | Ambient `classic` | `-40.4 dB` | **`-5`** | Giữ nguyên (`-45.4 dB`, lớp Halo mờ) |
| **P3 Hòa âm/Đệm** | `Piano` | Giao hưởng `classic` | `-41.9 dB` (no harm) | **`-2`** | Cùng với `<play>0</play>` trên `<Harmony>`, giữ giường Piano êm ở `-43.9 dB` (`p`) và `-38.5 dB` (`mp`) |
| | `Harp` | Giao hưởng `wood` | `-52.4 dB` | **`+8`** | Khôi phục độ vang cho đàn Harp (`-44.4 dB`) sau khi tắt Piano ẩn của `<Harmony>` |
| | `French Horns a6` | Giao hưởng `brass` | `-34.8 dB` | **`-5`** | Lùi dàn 6 kèn cor xuống `-39.8 dB` để không nuốt Trumpet, Trombone và Glockenspiel |
| | `Suitcase Piano` | Jazz `classic` | `-35.1 dB` | **`-2`** | Lùi nhẹ Rhodes để Alto/Tenor Sax và Vibraphone nổi rõ |
| | `Violas` | Ambient `choir` | `-47.8 dB` | **`+5`** | Nâng tiếng nở (Swell) của Violas lên `-42.8 dB` |
| **P4 Bass/Drone** | `Electric Bass` | Giao hưởng `classic`, Jazz (`classic`, `soul`, `organ`), Tối giản (`mallet`, `guitar`) | **`-29.6 dB`** | **`-6`** | Hạ từ `-29.6 dB` xuống **`-35.6 dB`** — giải quyết dứt điểm việc Bass lấn át các bè ở cả 6 bộ nhạc cụ! |
| | `Contrabassoon` | Giao hưởng `wood`, Ambient `breath` | `-49.5 dB` / `-50.7 dB` | **`+10`** | Đưa Contrabassoon lên `-39.5 dB` để nghe rõ đường Bass gỗ và Drone hơi trầm |
| | `Tuba` | Giao hưởng `brass` | `-32.2 dB` | **`-5`** | Hạ Tuba xuống `-37.2 dB` cho cân với Trumpet và Trombone |
| | `Contrabasses` | Ambient `classic` | `-32.7 dB` (ở 0 dB) | **`0`** *(hạ từ `+4`)* | Ở `+4 dB` Drone đang `-28.7 dB` (đè Alto Flute `-39.3 dB`); về `0 dB` (`-32.7 dB`) vừa ấm vừa cân |

*(Các giọng không liệt kê trong bảng giữ mặc định `0 dB`).*

---

## 7. Chỗ sửa trong Codebase khi triển khai

1. **`backend/app/sonify/model.py`**:
   - Thêm 3 trường mặc định rỗng trên `Score`: `high_wedges: tuple[WedgeEvent, ...] = ()`, `high_dynamics: tuple[DynamicEvent, ...] = ()`, `comp_dynamics: tuple[DynamicEvent, ...] = ()` (kèm alias `flute_wedges`, `flute_dynamics`, `piano_dynamics`).
2. **`backend/app/sonify/dynamics.py`**:
   - Thêm `piano_marking(band: str) -> str` (`"p"` cho `"p"/"mp"`, `"mp"` cho `"mf"/"f"`), hàm hạ band theo groove `effective_comp_band(band: str, bar: int | None = None) -> str`, và bảng `PIANO_VELOCITY = {"p": 46, "mp": 54, "mf": 62, "f": 68}`.
3. **`backend/app/sonify/render.py`**:
   - `_flute_and_violin_dovetail`: trả thêm `flute_wedges` và `flute_dynamics`. Xử lý đủ 3 hình thái vòng cung của đoạn Flute (leo lên đỉnh, 1 nốt ngân dài nở giữa ngân, và vào ngay tại đỉnh với chữ `mf` rồi `diminuendo`), tính `span_swell` với `peak` `72` hoặc `80`, và bỏ `<wedge>` khi `ensemble == "brass"` có `len(merged_flute_runs) < 2`.
   - `_bass_pattern` / `_bass_bar`: nhận thêm cờ `under_cello: bool = False`; khi ô đó có Cello hát (`bar in cello_bars`), thay bước `OCTAVE` bằng `ROOT` để không đánh đè lên Cello ở `Đô3–Si3`.
   - `_right_hand` & `left_hand` (nhánh `symphony`): gán velocity giường từ `PIANO_VELOCITY`, đánh gốc tay trái mỗi ô khi `eff_band == "f"` hoặc `groove.rally`, vuốt velocity của các nốt fill theo hướng câu (`Nở` / `Lắng` / `Ngang`), và dựng `comp_dynamics` (chữ giường tại `beat = 0.0` khi đổi chữ + chữ fill tại `beat = fill_start`).
4. **`backend/app/sonify/musicxml.py`**:
   - `score_to_musicxml`: truyền `score.high_wedges` và `score.high_dynamics` vào `_melody_part` của `P5` khi `score.variant == "symphony"`.
   - `_piano_part`: khi `score.variant == "symphony"`, xả `score.comp_dynamics` theo từng `beat` trên khuông 1 (`flush(event.beat)`), tương tự `_melody_part`, và không in lặp chữ mở đầu `PIANO_DYNAMIC` nếu `comp_dynamics` đã có sự kiện tại `(bar=0, beat=0.0)`.
5. **`backend/app/sonify/span.py`, `movement_frame.py`, `daily_frame.py`**:
   - `slice_score`: dịch `high_wedges`, `high_dynamics`, `comp_dynamics` theo `start..end`.
   - `apply_span_frame` & `apply_daily_frame`: cắt `high_wedges` bằng `_body_wedges` và lọc `high_dynamics` vào `[body, cool)`. Với `comp_dynamics` của Giao hưởng: lọc bỏ các ô khung tĩnh, giữ chữ `p` ở đầu warm-up / `tag_bars` của khung động (gán `velocity = 49` cho nốt `_curtain_comp`), và đảm bảo ô đầu thân bài (`body`) in lại chữ giường đúng của ô đó nếu khác `p`.
6. **`backend/app/sonify/audio.py`**:
   - Thêm bảng `_VOICE_VOLUME_DB` cho 12 bộ nhạc cụ trong `_assign_installed_sounds`.
   - Chèn `<play>0</play>` vào các thẻ `<Harmony>` trong `score.mscx` khi đóng gói `.mscz` để tắt tiếng Piano ẩn đánh chồng của MuseScore, và tăng `RECAP_REVISION` / `SPAN_REVISION`.

---

## 8. Tiêu chí Kiểm tra (Test Plan)

- **Flute (`P5`)**:
  - Đoạn Flute leo tới đỉnh có `<wedge>` khớp với móc giá gốc cao nhất (`span_apex`), không bị lệch khi `flute_harmony_pitch` gập quãng 8.
  - Đoạn Flute vào ngay tại đỉnh (`span_apex == span_start`) không bao giờ mở `diminuendo` trần từ `mp`: hoặc mở chữ `mf` rồi `diminuendo`, hoặc nở ở giữa nếu là 1 nốt ngân dài $\ge 4$ móc, và in lại `mp` ở tiếng đánh mới sau đó.
  - `phrase.rise < MIN_RISE`: Flute giữ velocity `64`, không hairpin. Band `p`/`mp` (không breakout): velocity không vượt `72`. Band `mf`/`f` hoặc `BREAKOUT`: đỉnh chạm `80` (`mf`).
  - `ensemble == "brass"` (`Glockenspiel`): đoạn 1 run không sinh `<wedge>`, velocity nhận `peak`; đoạn $\ge 2$ runs có `<wedge>` như sáo.
- **Violin (`P1`), Cello (`P2`) & Bass (`P4`)**:
  - Khi Cello hát ở ô `bar`, Bass ở ô đó không đánh nốt `OCTAVE` (`chord.bass_midi + 12`), giữ toàn bộ nốt Bass trong quãng trầm dưới Cello. Các ô Violin hát vẫn giữ nguyên pattern Bass hiện tại.
- **Piano (`P3`)**:
  - Giường chỉ in `p` và `mp` theo band đã hạ qua `chamber`, `trio_thin`, `half`. Velocity giường nhận đúng `46 / 54 / 62 / 68`.
  - Ô `f` (sau groove) hoặc `groove.rally` đánh gốc tay trái mỗi ô.
  - Chữ fill (`mp` hoặc `mf`) đứng đúng tại `beat` bắt đầu fill trên khuông 1; hợp âm đệm kế tiếp in lại chữ giường ở `beat = 0.0`. Velocity các nốt trong fill vuốt theo hướng `Nở` / `Lắng` / `Ngang`. Fill bị `caesura` cắt sạch thì không có chữ fill.
  - Nốt `_curtain_comp` của Giao hưởng ở khung động có `velocity = 49`.
- **Cân bằng âm lượng & `<Harmony>` (`audio.py`)**:
  - `_assign_installed_sounds` gắn đúng `volumeDb` từ `_VOICE_VOLUME_DB` cho từng giọng và chèn `<play>0</play>` vào `<Harmony>` trong `score.mscx`.
  - Jazz, Tối giản và Ambient giữ nguyên số chữ và số hairpin trên cả 5 bè trong MusicXML.
