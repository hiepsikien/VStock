# Torroba: mặt nốt, chọn nhịp, tempo, và câu hát

> **Trạng thái**: đã nghe trên VRE 1M, Guitar, Torroba. Đã khóa giải pháp kỹ thuật theo sau PR 110, chờ code.
> **Thay cho**:
> - Hàng `castillo`, `ctx.bpm > 72` → «một nốt giá ngân cả ô», cổng `n % 2 == 1`, và ràng buộc «một câu chỉ có một kiểu» trong [`docs/sonify-guitar-torroba-phrase-plan.md`](./sonify-guitar-torroba-phrase-plan.md) mục 4.0;
> - Ô `4/4` mood `calm` trong [`docs/sonify-guitar-torroba-aba-tempo.md`](./sonify-guitar-torroba-aba-tempo.md) mục 3–4, và luật «một cú ở móc 0, dài một phách» của mục 5 đối với thân `castillo` / `olite` trên 4/4;
> - Cách gộp hai ô 2/4 thành một ô 4/4 trong [`docs/sonify-guitar-torroba-castillos-frames.md`](./sonify-guitar-torroba-castillos-frames.md) mục 3.3 khi phép gộp đó bỏ trống nhóm móc yếu hoặc giữ `_olite_thin` thưa ở BPM > 72, cùng `staccato=True` trên mọi hợp âm cửa `olite` ở mục 4.7;
> - Cửa sổ `floor_calm` / `floor_wide` của hai hàng sóng trong [`docs/sonify-guitar-torroba-dynamics.md`](./sonify-guitar-torroba-dynamics.md) mục 2–3 (hoặc giường `_raised_bed` trên tiếng êm; xem mục 7 bên dưới — chỉ chọn **một núm −4**, không hạ kép cả hai).
> **Giữ**: Khung nhịp `_guitar_meter` của `span.py` (không đổi nhịp riêng của Torroba). Staccato đúng chỗ trong điệu nhảy và toàn bộ cửa `fandanguillo` / `danza`. Tám kiểu đã viết. Đường giá `_melody_at`. `_MICRO_FLOOR = 40` dùng chung. Không thêm id pattern.

Bốn việc cùng một đợt nghe:

1. **Giữ khung `_guitar_meter`, sửa mặt nốt trên 4/4 (96 BPM):** Chương I của VRE 1M là `selloff` (`Castillo — Olite — Castillo`) và chương IV là `rally` (`Olite — Sonatina — Olite`). Mặt nốt của `castillo`, `sonatina` và chỗ `olite` nghỉ trắng khi giá đi ngang mới là nguyên nhân trực tiếp làm bản vừa nghe bị chậm và đứt. Riêng trên bảng 4/4, chỉ đổi ô `calm` (`Sonatina` làm A, `Castillo` làm B); các hàng `rally`, `volatile`, `selloff` trên 4/4 và toàn bộ bảng `3/4`, `6/8` giữ nguyên như đang chạy.
2. **Mặt nốt 2+2 trên 4/4 ở BPM = 96:** Một ô 4/4 vận hành như hai ô 2/4 ghép lại (hai nửa ô ở móc 0 và móc 4), chạy bằng móc đơn, móc kép và một ít nốt đen / chấm dôi. Bỏ nốt tròn 4 phách của `_render_castillo_bar` và bỏ nhịp nốt trắng (chỉ gảy ở móc 0 và 4) của `_render_sonatina_bar` cùng `_olite_thin` ở BPM > 72.
3. **Gỡ staccato sai chỗ, nối bass hai lần gảy, và thêm láy trùm ba (`E–F–E`):** Bỏ `staccato=True` trên `_type3_scale` và trên các ô cửa `olite` trước nhát kết cuối (**không** đụng cửa `fandanguillo` và `danza`). Bass trên 4/4 gảy hai lần ở móc 0 và móc 4 (không buộc thành nốt tròn gây ù dây buông) kèm cửa lùi về 1 phách khi thế tay không giữ nổi. Mở chùm ba móc kép `1/6` phách (`E–F–E` có slur) qua `_covers` và `musicxml.py`.
4. **Nhiều span kiểu trong một câu (độ phủ 60% – 70%) và một núm Velocity −4:** Cho phép một câu thân bài mang nhiều span kiểu (mỗi span đếm lại `index` từ `0`) để đạt đúng 60% – 70% số ô trên cả câu dài 5 đến 8 ô, và chọn **đúng một núm −4** tương thích với `_raised_bed` của PR 110.

---

## 1. Việc đang nghe trên VRE 1M

VRE 1M, bốn chương:
- **Chương I (`selloff`, 4/4, 96 BPM):** Đang hát `Castillo — Olite — Castillo`.
- **Chương IV (`rally`, 4/4, 96 BPM):** Đang hát `Olite — Sonatina — Olite`.

Tai nghe ba lớp lỗi khớp trực tiếp với code trên `main`:

1. **Nhát đứt (staccato và bass cụt):**
   - Trong `_render_castillo_bar`, bass chỉ viết `written(origin, 2, bass)` (dài 1 phách đen ở móc 0) rồi nghỉ suốt 3 phách còn lại trong khi lead ngân cả ô. Khi `bass` là nốt bấm cao trong vùng 40–53, tiếng tắt ở phách 2 nghe như một nhát đứt giữa câu.
   - Trong `_olite_chord`, điều kiện `if _open_bass_tone(ctx, raw)` bỏ hẳn bass khi không phải dây buông, và khi có thì chỉ dài `0.5` phách.
   - Trong `_type3_scale` (Sonatina câu đóng), cả 8 nốt móc đơn đều gắn `staccato=True`.
   - Trong `_olite_chords` (`guitar_torroba_doors.py`), mọi hợp âm intro/outro của cửa Olite đều gắn `staccato=True`.
2. **Phẳng và thiếu luyến láy trùm ba:**
   - `_span_castillo` trả về `(None, ())` ngay khi `ctx.bpm > 72`, nên toàn bộ chương I (`Castillo` ở 96 BPM) có **0%** ô nhận Kiểu 7 (*Arada*) hay Kiểu 8.
   - `select_torroba_figure` trả về `(None, ())` cho mọi câu lẻ (`n % 2 == 1`).
   - Láy trùm ba (`E–F–E` có slur trong 1 móc đơn) chưa có mặt: mordent của Kiểu 7 đang rút thành 2 móc kép (`0.25 + 0.25`) và cũng bị khóa ngoài chương 96 BPM.
3. **Chậm dề dà ở 96 BPM:**
   - `_render_castillo_bar` viết một nốt tròn `written(origin, epb, midi)` dài 4 phách (2,5 giây ở 96 BPM).
   - `_render_sonatina_bar` chỉ đặt lead ở `ctx.strong` (móc 0 và móc 4), làm nhịp giai điệu giãn thành nốt trắng.
   - `_olite_group` trả về `[]` khi `start == target` (giá đi ngang giữa móc 0 và móc 4), làm 3 móc yếu `(1, 2, 3)` hoặc `(5, 6, 7)` nghỉ trắng. Và khi câu rơi vào `_olite_thin` (câu đóng hoặc `rise < 3`), cả ô cũng chỉ có đúng 2 móc đơn lead ở móc 0 và móc 4, bass `0.5` phách ở móc 0, còn lại nghỉ trắng.

---

## 2. Khung nhịp `_guitar_meter` và bảng chọn Pattern

Giữ nguyên `_guitar_meter` trong `span.py` (chương I và IV của 1M ở `4/4`, chương II ở `3/4`, chương III ở `6/8`). Không đổi nhịp riêng cho Torroba; trên `4/4`, mặt nốt 2+2 vận hành như **hai ô 2/4 ghép lại** (phách mạnh ở móc 0 và móc 4), không phải chu kỳ 3 móc của 3/4.

Trong bảng chọn pattern (`_torroba_primary` và `_torroba_contrast` trong `guitar_torroba.py`):
- Giữ nguyên toàn bộ bảng `3/4`, bảng `6/8`, và các hàng `rally`, `volatile`, `selloff` trên `4/4` như `docs/sonify-guitar-torroba-aba-tempo.md`:
  - `4/4 selloff` (như VRE 1M chương I): **Castillo — Olite — Castillo** (nhưng Castillo ở 96 BPM chạy mặt 2+2 và mở Kiểu 7/8, không ngân nốt tròn).
  - `4/4 rally` và `volatile` (như VRE 1M chương IV): **Olite — Sonatina — Olite**.
- Chỉ đổi duy nhất ô **`4/4 calm`**:
  - Primary (A): **`sonatina`** (thay vì `castillo`).
  - Contrast (B): **`castillo`** (8 ô ở giữa vùng B).
  - Khi `_torroba_contrast` nhận `primary == "sonatina"` trên `4/4`, trả về `"castillo"`.

---

## 3. Mặt nốt ở 96 BPM (4/4 như hai ô 2/4)

Ở nốt đen = 96, mặt của `castillo`, `sonatina` và `olite` là móc đơn (`0.5`), móc kép (`0.25`) / chùm ba móc kép (`1/6`), và một ít nốt đen (`1.0`) hoặc chấm dôi (`1.5`). Nốt tròn (`4.0`) không được làm lưới nền ở BPM > 72.

### 3.1. Lưới nền `_render_castillo_bar` và các ô ngân ở BPM > 72

- **Khi `ctx.bpm <= 72` (chương chậm 3/4 ở 60–72 BPM, đúng chỗ của *Torija* / *Castillos* chậm):** Giữ nguyên `_render_castillo_bar` hiện tại (lead ngân cả ô, bass 1 phách ở móc 0, support ở móc 2 và 4).
- **Khi `ctx.bpm > 72` (chương 4/4 ở 90–108 BPM):**
  - `_render_castillo_bar` chia ô 4/4 thành **hai nửa ô (`base = 0` và `base = 4`)**:
    - Tại `base = 0`: `lead` hát `_melody_at(origin)` chấm dôi (`duration_beats = 1.5`, phủ móc 0–2), `accent=True`. Tại móc 3 (`beat = 1.5`), `lead` đánh móc đơn `_melody_at(origin + 3)` (hoặc chùm ba láy `E–F–E` có slur đổ vào móc 4 khi bước liền bậc).
    - Tại `base = 4`: nếu cả nửa sau nằm trong `_closing_offsets(ctx, bar)` (cuối câu đóng), `lead` hát một nốt trắng `_melody_at(origin + 4)` (`duration_beats = 2.0`) để câu khép; ngược lại `lead` hát chấm dôi `_melody_at(origin + 4)` (`1.5`) + móc 7 (`0.5`) nối sang ô sau.
    - `support` đi móc đơn ở móc 2 và móc 6 (mỏng dần trên `_closing_offsets` như hiện tại).
- **Hai chỗ ngân cả ô / nửa ô trong Kiểu 3 và Kiểu 7 khi `ctx.bpm > 72`:**
  - **Kiểu 7 ô 1 (`_type7_bar1`) trên 4/4:** Nửa sau ô (`beat = 2.0..4.0`) hiện viết `resolution="half"` (1 nốt trắng `2.0`). Khi `ctx.bpm > 72`, đổi nửa sau sang chấm dôi `1.5` tại `beat = 2.0` (`pen.mel(4)`) + 1 móc đơn dẫn tại `beat = 3.5` (`pen.mel(7)`), giống nhịp nửa sau của `_type7_bar2`.
  - **Kiểu 3 ô ngân (`_type3_sustain`):** Hiện viết `pen.add(0.0, midi, pen.beats, 1, ...)` (nốt tròn `4.0` trên 4/4) và bass `0.5` phách. Khi `pen.ctx.bpm > 72` và `pen.ctx.kind == "4/4"` (trừ khi `midi` khớp cửa harmonic `velocity == 48`), chia thành hai nửa ô: nửa đầu (`beat = 0.0`) chấm dôi `1.5` + móc 3 (`0.5`, có slur vào móc 4), nửa sau (`beat = 2.0`) ngân nốt trắng `2.0` khép câu, kèm bass ở cả móc 0 và móc 4.

### 3.2. Lưới nền `_render_sonatina_bar`

- Không chỉ đặt `lead` ở `ctx.strong` (móc 0 và móc 4):
  - Trong mỗi nửa ô 4/4 (`0..3` và `4..7`) hoặc trên 3/4 (`0..5`), `lead` hát ở phách mạnh (`0`, `4`), giữ `1.0` phách (nốt đen) ở móc `0` (phủ móc 0–1) rồi đi **hai móc đơn ở móc 2 và móc 3** (`_melody_at(origin + 2)`, `_melody_at(origin + 3)`) có slur nối vào móc 4 (hoặc giữ nốt lấy đà móc kép `_into_strong` khi nhảy quãng / lên đỉnh `at_apex`). Nửa sau (`4..7`) đi tương tự: nốt đen ở móc 4 (hoặc móc đơn + láy) rồi móc đơn ở móc 6, 7 dẫn sang ô kế.
  - `support` đệm ở các móc không có móc kép lấy đà (móc 1 và móc 5), giữ `lead > bass > support`.

### 3.3. Thân `olite` (`_olite_vivace` và `_olite_thin`) khi gộp hai ô 2/4 vào một ô 4/4

- **Trong `_olite_group` (các nhóm móc `(1, 2, 3)` và `(5, 6, 7)` của `_olite_vivace`):**
  - Khi `start != target`, `_scale_steps` đã có đường đi. Thêm slur trên cặp móc đầu của nhóm (`eighths[0]` sang `eighths[1]`).
  - Khi `start == target` (giá đi ngang giữa móc 0 và móc 4, hoặc giữa móc 4 và đầu ô sau): **không trả về `[]`**. Thay bằng mô-típ 3 móc đơn / láy quanh `start` theo thang âm của ô:
    - Móc đầu nhóm (`eighths[0]`, tức móc 1 hoặc móc 5): đánh chùm ba láy `start -> upper -> start` (hoặc 2 móc kép slur `upper -> start` khi không đủ khe `1/6`) nếu thế tay với bass đang vang hợp lệ; nếu không thì đánh nốt bậc kề `neighbor = torroba_scale_step(ctx, start, -1, ...)`.
    - Móc giữa (`eighths[1]`): đánh nốt bậc dưới `lower = torroba_scale_step(ctx, start, -1, ...)`.
    - Móc cuối nhóm (`eighths[2]`): quay về `start` (hoặc bậc áp vào `target`).
- **Trong `_olite_thin` (ô thưa của Olite khi câu đóng hoặc `rise < 3`):**
  - Hiện tại `_olite_thin` chỉ viết 2 nốt móc đơn ở móc 0 và móc 4, bass `0.5` phách ở móc 0, còn 6 móc kia nghỉ trắng — ở 96 BPM nghe đứt và trống.
  - **Sửa `_olite_thin`:**
    - Giữ tính chất nhẹ hơn `_olite_vivace` (không hợp âm khối 3 tiếng, không `accent`, không sàn `68`, vẫn dùng hàng sóng `castillo`), nhưng **nối liền câu hát**:
    - Tại móc 0 và móc 4: `lead` hát nốt đen chấm dôi (`duration_beats = 1.5`, phủ móc 0–2 và 4–6), tại móc 3 và móc 7 (`beat = 1.5` và `3.5`) `lead` đi một móc đơn dẫn (có slur từ móc 3 vào móc 4) đọc `_melody_at`. Nếu là ô đóng cuối câu (`closing`), nửa sau (móc 4..7) ngân một nốt trắng (`duration_beats = 2.0`).

---

## 4. Luật Bass hai lần gảy (cửa lùi thế tay) và phạm vi gỡ Staccato

### 4.1. Bass nửa ô là hai lần gảy, có cửa lùi khi thế tay không giữ nổi

`docs/sonify-guitar-torroba-aba-tempo.md` mục 5 và `docs/sonify-guitar-torroba-dynamics.md` mục 7 đặt bass 1 phách để dây buông không ngân cả ô gây ù. Khi sửa tiếng bass cụt trên 4/4, phải tuân thủ hai quy tắc:

1. **Hai lần gảy độc lập ở móc 0 và móc 4 (không buộc thành nốt tròn 4 phách):**
   - Trong `_render_castillo_bar` (ở 4/4), `_render_sonatina_bar` (ở 4/4), `_olite_vivace`, và `_olite_thin`: đặt một sự kiện bass ở **móc 0** (`beat = 0.0`) và một sự kiện bass thứ hai ở **móc 4** (`beat = 2.0`). Kể cả khi dây buông cùng cao độ, móc 4 vẫn là một lần gảy mới (`tie_start=False, tie_stop=False`).
   - Trong `_olite_chord` và `_olite_thin`: bỏ điều kiện chỉ nhận `_open_bass_tone(ctx, raw)` — lấy trực tiếp `raw = _torroba_bass(ctx, ctx.chord(bar), bar, midi)` để các hợp âm có bass bấm (40–53) không bị mất bè trầm.
2. **Độ dài mỗi cú bass (`1.0` đến `2.0` phách) và cửa lùi thế tay (`_playable`):**
   - Với **dây buông** (`_open_bass_tone(ctx, raw)` đúng): bass ở móc 0 và móc 4 dài `1.0` phách đen (`2` móc đơn) hoặc `2.0` phách (nửa ô) tùy miễn là mọi nốt `lead` / `support` vang trong khoảng đó thoả `_playable([raw + semi, ...])` và `raw < min(support, lead)`.
   - Với **bass bấm trên phím** (`not _open_bass_tone(ctx, raw)`, trong vùng 40–53): ưu tiên giữ `duration_beats = 2.0` (suốt nửa ô, 4 móc đơn) để tiếng trầm không tắt cụt giữa câu. **Cửa lùi bắt buộc:** trước khi ghi `duration_beats = 2.0`, kiểm tra mọi thời điểm trong nửa ô đó xem `[raw + semi]` cùng với `lead` (kể cả nét chạy móc đơn/móc kép và láy trùm ba) và `support` có thoả `_playable` (độ giãn ngăn bấm `<= 5`, khác dây) hay không. Nếu tại móc 2 hoặc móc 3 `lead` chạy sang thế tay khác làm `_playable` sai, rút độ dài cú bass đó lùi về `1.0` phách (2 móc đơn) hoặc `0.5` phách (1 móc đơn) đúng tới mốc còn giữ được thế tay, và nếu cần thì đặt một nốt bass hợp âm mới ở móc 2 (hoặc móc 6).

### 4.2. Khoanh vùng gỡ Staccato (không đụng cửa Fandanguillo và Danza)

Chỉ gỡ `staccato=True` ở đúng **2 chỗ** đang làm hỏng câu hát và chương 4/4:

1. **`_type3_scale` trong `backend/app/sonify/guitar_torroba.py` (dòng 1715):**
   - Bỏ `staccato=True` trên vòng lặp các nốt móc đơn chạy thang âm. Thêm slur trên cặp móc đơn đầu mỗi nửa ô (`eighth 0 -> 1`, và trên 4/4 thêm `eighth 4 -> 5`).
2. **`_olite_chords` trong `backend/app/sonify/guitar_torroba_doors.py` (dòng 534):**
   - Chỉ sửa cửa `("torroba", "olite")`: các ô intro và các ô outro trước ô cuối dùng `staccato=False` và `length = 2` (1 phách đen, thay vì `length = 1` staccato). Chỉ giữ `staccato=True` ở nhát kết cuối cùng của ô outro cuối (`closing and index == steps - 1`, nhát ở onset cuối).
3. **Giữ nguyên 100% staccato của `fandanguillo` và `danza` (cả thân bài lẫn cửa trong `guitar_torroba_doors.py`):**
   - Cửa `fandanguillo` (`_fandanguillo`, `_fan_strokes`) và cửa `danza` (`_danza_bar`) thuộc các điệu nhảy ở 6/8 và 3/4, **nằm ngoài đợt gỡ staccato này**. Không sửa bất kỳ cờ `staccato=True` nào của Fandanguillo và Danza.

---

## 5. Chùm ba móc kép (`1/6` phách) cho láy `E–F–E` và Slur

### 5.1. Sửa `assert_playable` (`_covers`) và `musicxml.py` (không đụng bộ rút của `_resolve`)

1. **Trong `backend/app/sonify/guitar_patterns.py`:**
   - `_resolve` (dòng 2238) **đã** đẩy mọi sự kiện `not _on_sixteenth_grid(event)` sang danh sách `odd` và giữ nguyên không cắt. **Không đưa chùm ba `1/6` qua bộ rút `_spell16` của `_resolve`.**
   - Va chạm nằm ở `assert_playable` (dòng 4057–4077): hiện tại `times` chỉ thu thập `_start16(event, epb)` (tức `floor(beat * 4)`), và `_covers(event, step16, epb)` kiểm tra trên lưới `1/4` phách. Khi có 3 nốt `duration_beats = 1/6` tại `beat = 1.5`, `1.5 + 1/6`, `1.5 + 2/6`, hai nốt đầu cùng có `floor(beat * 4) == 6` và `_dur16 == 1`, nên `_covers(event, 6, epb)` trả về `True` cho cả hai nốt cùng lúc, làm `len(highs) > 1` ném `Unplayable("two notes in the high voice")`.
   - **Cách sửa trong `guitar_patterns.py`:**
     - Kiểm tra chồng lấp trong `assert_playable` bằng đơn vị **`1/12` phách** (`twelfth = event.bar * epb * 6 + int(round(event.beat * 12))`, `dur12 = max(1, int(round(event.duration_beats * 12)))`): một nốt phủ `[twelfth, twelfth + dur12)`.
     - Tập mốc thời gian kiểm tra trong mỗi ô là tất cả các điểm bắt đầu `twelfth` của mọi sự kiện trong ô đó. Ba nốt `1/6` phách tại `beat = 1.5`, `1.5 + 1/6`, `1.5 + 2/6` có `(twelfth, dur12)` lần lượt là `(18, 2)`, `(20, 2)`, `(22, 2)` — hoàn toàn rời nhau, không chồng lấp. Cửa sổ rasgueado đầu ô (`roll_window`) tương ứng với `(twelfth % (epb * 6)) < 3`.
2. **Trong `backend/app/sonify/musicxml.py`:**
   - Thêm hàm `_triplet_sixteenth_roles(events: list[NoteEvent]) -> list[str | None]` gọi bên trong `_tuplet_roles`:
     - Quét các nốt cùng một voice. Khi gặp đúng **3 sự kiện liên tiếp** thoả `_is_sixth(event.duration_beats)` (mỗi sự kiện `duration_beats = 1/6`, tức `2` đơn vị ở `divisions = 12`), có tổng `duration_beats == 0.5` (`abs(total - 0.5) < 1e-3`), bắt đầu tại biên một móc đơn (`abs(events[index].beat * 2 - round(events[index].beat * 2)) < 1e-3`), và **chưa** được `_sextuplet_roles` gắn `"start"` / `"stop"` (tức không nằm trong chùm 6 nốt 1 phách):
     - Gắn `roles[index] = "start"` và `roles[index + 2] = "stop"`.
     - Trong `_add_note`, với nốt có `_is_sixth(event.duration_beats)` thuộc chùm 3 này (hoặc dùng chung cho `_is_sixth` khi bracket là 3 nốt): ghi `<type>16th</type>`, `<duration>2</duration>`, và `<time-modification><actual-notes>3</actual-notes><normal-notes>2</normal-notes><normal-type>16th</normal-type></time-modification>`. (Hàm `_is_sixth` đã loại `4/12` của rasgueado nên không bao giờ chạm vào rasgueado).

### 5.2. Helper `pen.mordent_triplet` trong `guitar_torroba.py`

- Thêm phương thức `pen.mordent_triplet(beat: float, principal: int, others: list[int], written: int, steps: int) -> bool`:
  - Tìm nốt thêu bậc trên `upper = _walk(principal, 1, pen.ctx.mode, pen.ctx.treble_floor, pen.ctx.treble_top)`.
  - Kiểm tra `upper != principal`, `abs(upper - principal) <= 2`, và `_position_ok([principal + semi, upper + semi, *(n + semi for n in others)])`.
  - Nếu hợp lệ, ghi 3 nốt `voice = 1`, `duration_beats = 1.0 / 6.0`:
    1. `beat`: cao độ `principal`, `written`, bậc `steps`, `slur_start=True`
    2. `beat + 1.0 / 6.0`: cao độ `upper`, `written`, bậc `steps + 1`
    3. `beat + 2.0 / 6.0`: cao độ `principal`, `written`, bậc `steps`, `slur_stop=True`
  - Nếu không vừa thế tay, fallback về cặp 2 móc kép `pen.grace` hoặc 1 móc đơn `principal`.
- **Chỗ gọi `pen.mordent_triplet`:**
  - Kiểu 7 ô 1 (`_type7_opening`) và ô 2 (`_type7_bar2`) tại `beat = 1.5` (móc đơn 3, láy trên `pen.mel(3)` trước khi đổ về `pen.mel(4)` ở `beat = 2.0`).
  - Kiểu 3 ô mô-típ (`_type3_motif`) và Kiểu 4 ô gọi (`_type4_call`) tại `beat = 1.5`.

---

## 6. Nhiều Span kiểu trong một câu để đạt độ phủ 60% – 70%

### 6.1. Mở cấu trúc dữ liệu từ «một câu một kiểu» sang «danh sách span trong câu»

Trong `guitar_torroba.py` hiện tại:
- `select_torroba_figure` chỉ trả về `tuple[int | None, tuple[int, ...]]` (một `figure` duy nhất và một tuple `slots`).
- `torroba_figure_plan` ghi `plan[bars[local]] = (figure, slot_index, len(slots))`.
- Nếu truyền `slots = (0, 1, 4, 5)` cho Kiểu 8, `slot_index` sẽ là `0, 1, 2, 3`, làm hai ô sau đều chạy nhánh `pen.index != 0` (`_type8_bar2`), mất `_type8_bar1`! Và một câu Sonatina dài cũng không thể mở bằng Kiểu 4 rồi khép bằng Kiểu 3.

**Cách sửa cấu trúc lịch kiểu:**
- Thêm hàm `select_torroba_spans(ctx, phrase, pattern, *, n: int, previous: int | None) -> list[tuple[int, tuple[int, ...]]]`:
  - Trả về danh sách một hoặc hai span `[(figure_a, slots_a), (figure_b, slots_b)]` trong cùng một câu `phrase`.
  - Trong `torroba_figure_plan`, với mỗi `(figure, slots)` trong danh sách trả về:
    ```python
    for slot_index, local in enumerate(slots):
        if 0 <= local < len(bars):
            plan[bars[local]] = (figure, slot_index, len(slots))
    ```
    Nhờ đó, mỗi span tự đếm lại `slot_index` từ `0` đến `len(slots) - 1`, và một câu dài có thể chứa hai kiểu khác nhau (ví dụ Kiểu 4 ở đầu câu và Kiểu 3 ở cuối câu đóng) hoặc hai cụm của Kiểu 8 mà mỗi cụm đều có đủ `(index=0, index=1)`.
  - Giữ hàm `select_torroba_figure` làm wrapper trả về span đầu tiên `spans[0]` để tương thích ngược với các lời gọi đơn lẻ nếu có.

### 6.2. Bỏ cổng `n % 2 == 1`, bỏ cổng `bpm > 72`, và hạ cửa `rise` của Fandanguillo

1. **Mọi câu thân bài đều tăng `n = 0, 1, 2, ...`** (kể cả câu `sonatina` có `closes`) và đều đi vào bộ chọn span. Không bỏ trống câu `n % 2 == 1`.
2. **Khi `figure` đầu của câu trùng với `previous` (kiểu cuối của câu liền trước):** xoay `n` cộng thêm `1` để chọn kiểu kế tiếp trong họ pattern đó, thay vì trả về rỗng.
3. **Trong `_span_fandanguillo`:** hạ cổng đầu hàm từ `if phrase.rise < MIN_RISE:` (`3`) xuống `if phrase.rise < 1:` để các câu có biến động vừa (`rise >= 1`) vẫn nhận được Kiểu 5 hoặc Kiểu 2.
4. **Trong `_span_danza`:** cho phép câu dài `length >= 4` trên `3/4` và `6/8` nhận Kiểu 6 trên 4 ô `(0, 1, 2, 3)` (thay vì bắt buộc `length == 4` và `not closes`; nếu `closes` và `length == 4` thì lấy câu không đóng hoặc khi `length >= 5` lấy 4 ô đầu trước ô đóng).

### 6.3. Bảng phân bổ Span theo độ dài câu `L` (khóa độ phủ 60% – 75% trên cả `L = 5` và `L = 8`)

Với câu có độ dài `L = len(_bars_of(ctx, phrase))` ô:

| Pattern | Độ dài câu `L` | Span được gắn `(figure, slots)` | Số ô có Kiểu / `L` | Độ phủ |
|---|---|---|---|---|
| **`castillo`** (mọi BPM) | `L == 1` | Lưới nền 2+2 (`[]`) | `0 / 1` | 0% |
| | `L == 2` | `[(8, (0, 1))]` | `2 / 2` | 100% |
| | `L == 3` | `[(8, (0, 1))]` (ô 2 là lưới nền dẫn) | `2 / 3` | **67%** |
| | `L == 4` | `[(8, (0, 1))]` khi `n % 2 == 0`; `[(8, (1, 2))]` khi `n % 2 == 1` | `2 / 4` | **50%** |
| | `L == 5` | `n % 2 == 0`: `[(7, (0, 1, 2, 3, 4))]` (5 ô *Arada*);<br>`n % 2 == 1`: `[(8, (0, 1)), (8, (3, 4))]` (hai cụm Kiểu 8, ô 2 ở giữa là lưới nền) | `5 / 5` và `4 / 5` | Trung bình hai câu = **90% / 80%** (riêng `n` lẻ đạt **80%**, hoặc 1 cụm `[(8, (1, 2))]` = **40%**, trung bình cặp câu chẵn–lẻ `L=5` là `(5 + 2)/10 =` **70%**) |
| | `L == 6` | `n % 2 == 0`: `[(7, (0, 1, 2, 3, 4))]` (ô 5 dẫn mượt);<br>`n % 2 == 1`: `[(8, (0, 1)), (8, (3, 4))]` (ô 2 và ô 5 dẫn mượt) | `5 / 6` (83%) và `4 / 6` (67%) | Trung bình **75%** |
| | `L == 7` | `[(7, (0, 1, 2, 3, 4))]` (5 ô đầu, 2 ô cuối dẫn mượt) | `5 / 7` | **71%** |
| | `L >= 8` (ví dụ `L == 8`) | `[(7, (0, 1, 2, 3, 4))]` (5 ô đầu là Kiểu 7, 3 ô cuối là lưới nền cantabile; hoặc khi `n % 2 == 1`: `[(8, (0, 1)), (7, (3, 4, 5, 6, 7))]` = 5–7 ô) -> chọn cố định 5 ô trên 8 ô: `[(7, (0, 1, 2, 3, 4))]` hoặc `[(8, (0, 1)), (8, (3, 4)), (8, (6))]` -> chốt: với `L == 8`, đặt `[(7, (0, 1, 2, 3, 4))]` (`5 / 8` = **62,5%**) khi lượt Kiểu 7, và `[(8, (0, 1)), (3, (5, 6, 7))]` / `[(8, (0, 1)), (8, (4, 5))]` kèm 1 ô Kiểu 1 `(1, (2,))` (`5 / 8` = **62,5%**) | `5 / 8` | **62,5%** |
| **`sonatina`** (chưa `closes`) | `L == 2` | Xoay `n % 3`: `[(4, (0, 1))]`, `[(2, (0, 1))]`, `[(1, (0,))]` | `1..2 / 2` | 50%–100% |
| | `L == 3` | Xoay `n % 3`: `[(4, (0, 1))]`, `[(2, (1, 2))]`, `[(1, (0, 1))]` | `2 / 3` | **67%** |
| | `L == 4` | Xoay `n % 3`: `[(4, (0, 1)), (1, (3,))]`, `[(2, (1, 2)), (1, (3,))]`, `[(1, (0,)), (4, (2, 3))]` | `3 / 4` | **75%** |
| | `L == 5` | `[(4, (0, 1)), (1, (3,))]` hoặc `[(4, (0, 1)), (2, (3, 4))]` (ô 2 ở giữa là lưới nền cantabile) | `3 / 5` hoặc `4 / 5` | **60% – 80%** |
| | `L == 6` | `[(4, (0, 1)), (2, (3, 4))]` (hoặc `[(2, (0, 1)), (4, (3, 4))]`, để ô 2 và ô 5 là lưới nền) | `4 / 6` | **67%** |
| | `L == 7` | `[(4, (0, 1)), (1, (3,)), (2, (5, 6))]` | `5 / 7` | **71%** |
| | `L >= 8` (`L == 8`) | `[(4, (0, 1)), (1, (3,)), (2, (5, 6))]` (các ô 2, 4, 7 là lưới nền cantabile) | `5 / 8` | **62,5%** |
| **`sonatina`** (`closes`) | `L <= 3` | `[(3, tuple(range(L)))]` (ô cuối dùng `_type3_sustain` mới ở 3.1) | `L / L` | 100% |
| | `L == 4` | `[(3, (1, 2, 3))]` (ô 0 là lưới nền, 3 ô cuối là đủ bộ mô-típ + scale + ngân của Kiểu 3) | `3 / 4` | **75%** |
| | `L == 5` | `[(3, (2, 3, 4))]` (2 ô đầu lưới nền, 3 ô cuối Kiểu 3) | `3 / 5` | **60%** |
| | `L == 6` | `[(4, (0, 1)), (3, (4, 5))]` hoặc `[(1, (0,)), (3, (3, 4, 5))]` (giữ đủ 3 ô cho Kiểu 3 để không mất ô mô-típ!) | `4 / 6` | **67%** |
| | `L == 7` | `[(4, (0, 1)), (3, (4, 5, 6))]` (ô 2, 3 là lưới nền, 3 ô cuối đủ bộ Kiểu 3) | `5 / 7` | **71%** |
| | `L >= 8` (`L == 8`) | `[(4, (0, 1)), (3, (5, 6, 7))]` (ô 2, 3, 4 là lưới nền, 3 ô cuối đủ bộ Kiểu 3) | `5 / 8` | **62,5%** |

Đặc biệt lưu ý với **Kiểu 3**: Khi `L >= 4`, luôn giao cho Kiểu 3 đúng **3 ô cuối `(L - 3, L - 2, L - 1)`** (`pen.count == 3`) để Kiểu 3 luôn hát đủ cả 3 vai `("motif", "scale", "sustain")`, không bao giờ bị rút thành 2 ô làm mất ô mô-típ.

---

## 7. Cận dưới Velocity −4: chọn một núm tương thích với PR 110

Trong [`docs/sonify-guitar-torroba-dynamics.md`](./sonify-guitar-torroba-dynamics.md) (PR 110 đã vào `main`):
- Hai hàng sóng trong `guitar_wave.py` đang khóa:
  - Hàng Hát (`castillo`, `sonatina`, `torroba_tremolo`): cửa sổ `34..58`, `d_lo = -8, d_hi = 8` $\rightarrow$ tâm `C` đi từ **`42` đến `50`**.
  - Hàng Điệu (`fandanguillo`, `danza`, `alcaniz`, `olite`): cửa sổ `40..63`, `d_lo = -8, d_hi = 8` $\rightarrow$ tâm `C` làm tròn đi từ **`48` đến `55`**.
- Trong `guitar_torroba.py`, `_raised_bed` đã nhấc bass thêm `+4` so với `_under_lead`: khi `lead` viết `64` (band `mf`), `bass` dừng ở **`62`** (không phải `60`), `support` ở **`56`**, `weak` bass ở **`58`**.
- Với `lead = 64` và `bass = 62`, hàm `_micro_fits` (yêu cầu `heard >= bass + 2`) **không cho phép `lead` hạ dù chỉ 1 bậc** khi `bass = 62` đang vang (`64 - 2 = 62 < 62 + 2`)!
- Nếu vừa hạ sàn sóng trong `guitar_wave.py` đi 4, vừa hạ giường viết đi 4, thì bass ở đáy sẽ tụt tổng cộng **8 đơn vị** (xuống `32`), làm mất tiếng bass trên đàn nylon và làm gãy toàn bộ các test tâm sóng `42/50` và `48/55` trong `test_guitar_wave.py`.

### Quyết định: Chọn Núm 1 — Giữ nguyên cửa sổ sóng trong `guitar_wave.py`, chỉ mở giường êm trong `guitar_torroba.py`

1. **Không sửa `PROFILES` trong `backend/app/sonify/guitar_wave.py` và không sửa `_MICRO_FLOOR = 40` trong `guitar_patterns.py`:**
   - Cửa sổ Hàng Hát giữ nguyên `34..58` (tâm `42..50`), Hàng Điệu giữ nguyên `40..63` (tâm `48..55`), `d_lo = -8, d_hi = 8`. Mọi invariant của `test_guitar_wave.py` giữ nguyên.
2. **Mở chỗ `−4` (2 bậc `_MICRO`) ngay trong `guitar_torroba.py` bằng giường êm (`_soft_bed`):**
   - Khi một ô hoặc một phách thuộc **câu êm / tiếng láy** (cụ thể: trong `_realize` của `_Pen` khi nốt `lead` có `steps >= 2`, hoặc trên các ô thưa `mode == "thin"` / câu phẳng `phrase.rise == 0` ở nửa yếu của ô):
     - Giường `bass` tại thời điểm có nốt `lead` xin hạ `steps >= 2` (như nốt láy, nốt nhại `p`, chùm lặp móc kép của Kiểu 2/3/4/7/8) dùng mức `weak` của `_raised_bed` (tức hạ `4` từ `62` xuống **`58`**, và `support` ở **`54`**).
     - Với `bass = 58` và `support = 54`, `_micro_fits(lead=64, bass=58, support=54, steps=2)` cho phép `lead` hạ trọn **2 bậc (`steps = 2`, tức `−4`)** từ `64` xuống **`60`** (`60 >= 58 + 2`, và `58 >= 54 + 2`)!
     - Khi `lead` đứng một mình (sau khi bass nửa ô đã tắt hoặc ở các móc yếu chỉ có `lead`), `_drop_level(64, 2)` cũng xuống thẳng **`60`** (`−4`).
   - **Số nghe được sau sóng (với tâm Hàng Hát `C = 42..50`):**
     - `lead` thường viết `64` $\rightarrow$ nghe `42..50`.
     - `lead` êm / láy hạ `−4` (viết `60`) $\rightarrow$ nghe **`38..46`** (êm hơn đúng `4` đơn vị so với tiếng chính trong cùng ô).
     - `bass` trụ đầu phách (khi `lead` ở bậc `0`, viết `64`) vẫn giữ `_raised_bed` viết `62` $\rightarrow$ nghe **`40..48`** ở Hàng Hát và **`46..53`** ở Hàng Điệu (đúng số PR 110 đã khóa, không bị tụt xuống `32`).
     - Chỉ tại những móc có `lead` hạ 2 bậc (`viết 60`), `bass` dưới nó mới lùi về `58` (bằng đúng mức `weak` bass sẵn có của `_raised_bed`).

---

## 8. Danh mục chỗ sửa khi thực hiện

1. **`backend/app/sonify/guitar_patterns.py`:**
   - Trong `assert_playable`: đổi kiểm tra chồng lấp từ lưới `_start16` (`1/4` phách) sang lưới `1/12` phách (`twelfth = bar * epb * 6 + round(beat * 12)`) để 3 nốt `1/6` phách liên tiếp trong một móc đơn không bị báo `Unplayable("two notes in the high voice")`. Không đưa nốt `1/6` qua `_spell16` của `_resolve`.
   - Không sửa `_MICRO_FLOOR = 40`.
2. **`backend/app/sonify/musicxml.py`:**
   - Thêm `_triplet_sixteenth_roles` vào `_tuplet_roles`: chỉ đóng ngoặc `tuplet="start"/"stop"` và ghi `<time-modification>` (`3:2` trên `16th`, `<duration>2</duration>` ở `divisions = 12`) khi gặp đúng **3 nốt `_is_sixth` liên tiếp cùng voice, tổng `0.5` phách**, bắt đầu trên biên móc đơn, và không nằm trong chùm 6 nốt của `_sextuplet_roles`.
3. **`backend/app/sonify/guitar_torroba.py`:**
   - **Bảng pattern (`_torroba_primary`, `_torroba_contrast`)**: Chỉ đổi ô `4/4 calm` sang `sonatina` (A) và `castillo` (B). Giữ nguyên `4/4 selloff` (`castillo`), `4/4 rally/volatile` (`olite`), và toàn bộ `3/4`, `6/8`.
   - **Lịch nhiều span trong một câu (`select_torroba_spans`, `torroba_figure_plan`)**:
     - Cho phép một câu trả về nhiều `(figure, slots)`, mỗi span tự đếm lại `slot_index` từ `0`.
     - Bỏ cổng `ctx.bpm > 72` trong `_span_castillo`; bỏ cổng `n % 2 == 1`; xoay sang kiểu kế tiếp khi trùng `previous`; hạ cổng `rise` đầu `_span_fandanguillo` xuống `1`; giữ đủ 3 ô cuối cho Kiểu 3 khi `L >= 4` để không mất ô mô-típ; áp dụng bảng phân bổ mục 6.3 để đạt độ phủ 60% – 75% trên mọi độ dài câu (kể cả `L = 5` và `L = 8`).
   - **Mặt nốt ở BPM > 72 (`_render_castillo_bar`, `_type7_bar1`, `_type3_sustain`, `_render_sonatina_bar`, `_olite_group`, `_olite_thin`)**:
     - `_render_castillo_bar` ở `ctx.bpm > 72`, `_type7_bar1` (nửa sau ô 4/4 ở `bpm > 72`), và `_type3_sustain` (ở 4/4 `bpm > 72`) bỏ nốt tròn / nốt trắng đứng suốt ô, chuyển sang mặt 2+2 (chấm dôi + móc đơn / láy).
     - `_render_sonatina_bar`: thêm chuyển động móc đơn có slur cho `lead` ở các móc giữa ô.
     - `_olite_group`: khi `start == target` không trả về `[]` mà đánh mô-típ láy + bước bậc quanh `start`.
     - `_olite_thin`: nối câu bằng chấm dôi + móc đơn dẫn có slur thay vì để nghỉ trắng 6 móc đơn.
   - **Bass hai lần gảy và cửa lùi thế tay**:
     - Trên 4/4, bass của `castillo`, `sonatina`, `olite` gảy ở móc 0 và móc 4 (hai sự kiện rời), lấy cả bass bấm từ `_torroba_bass` cho `_olite_chord` / `_olite_thin`, và rút độ dài từ `2.0` xuống `1.0` hoặc `0.5` phách khi `_playable` báo xung đột thế tay với `lead`.
   - **Láy trùm ba (`pen.mordent_triplet`) và gỡ staccato `_type3_scale`**:
     - Thêm `pen.mordent_triplet` (3 nốt `1/6` phách `E–F–E` có slur) cho Kiểu 7 (ô 1, ô 2), Kiểu 3, Kiểu 4.
     - Bỏ `staccato=True` trên `_type3_scale`, thay bằng slur.
   - **Núm Velocity −4 trong `_realize`**:
     - Khi `lead` có `steps >= 2` (tiếng êm / láy), hạ `bass` đang phủ thời điểm đó từ `62` xuống mức `weak = 58` (và `support` xuống `54`) để `_micro_fits` cho phép `lead` hạ đủ 2 bậc (`64 -> 60`, tức `−4`), trong khi trụ bass đầu phách vẫn giữ `62` và cửa sổ `guitar_wave.py` không đổi.
4. **`backend/app/sonify/guitar_torroba_doors.py`:**
   - Chỉ sửa `_olite_chords`: bỏ `staccato=True` trên các ô cửa `olite` trước nhát kết cuối cùng và kéo dài hợp âm thành `length = 2`. **Giữ nguyên toàn bộ cửa `fandanguillo` và `danza`.**
5. **`backend/app/sonify/audio.py` và Tests:**
   - Tăng `SPAN_REVISION`.
   - Giữ nguyên `test_guitar_wave.py` (tâm `42/50` và `48/55`). Cập nhật `test_sonify_guitar_torroba.py`, `test_sonify_guitar_torroba_doors.py`, và `test_program.py` theo đúng các mục trên.
