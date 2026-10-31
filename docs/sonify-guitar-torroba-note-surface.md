# Torroba: mặt nốt, chọn nhịp, tempo, và câu hát

> **Trạng thái**: đã nghe trên VRE 1M, Guitar, Torroba. Đã chốt giải pháp kỹ thuật và cách chọn nhịp, chờ code.
> **Thay cho**: hàng `castillo`, `ctx.bpm > 72` → «một nốt giá ngân cả ô» và cổng `n % 2 == 1` trong [`docs/sonify-guitar-torroba-phrase-plan.md`](./sonify-guitar-torroba-phrase-plan.md) mục 4.0; bảng chọn pattern trên 4/4 / 3/4 / 6/8 trong [`docs/sonify-guitar-torroba-aba-tempo.md`](./sonify-guitar-torroba-aba-tempo.md) mục 3–4; và cách gộp hai ô 2/4 thành một ô 4/4 trong [`docs/sonify-guitar-torroba-castillos-frames.md`](./sonify-guitar-torroba-castillos-frames.md) mục 3.3 khi phép gộp đó kéo dài hình nốt hoặc bỏ trống nhóm móc yếu.
> **Giữ**: staccato đúng chỗ trong một điệu nhảy. Tám kiểu đã viết. Đường giá `_melody_at`. Không thêm id pattern.

Bốn việc cùng một đợt nghe:

1. **Chọn nhịp và ghép bản vào chương**: Hầu hết các tác phẩm tiêu biểu của Torroba (*Sonatina* I Allegretto, *Fandanguillo*, *Arada*, *Danza*, *Simancas*, *Redaba*, *Alcañiz*, *Torija*) đều viết ở nhịp ba (**3/4, 3/8, 6/8**), chỉ một số bản hành khúc / lễ hội như *Olite* là **2/4** (tương đương hai nửa ô 4/4). Đẩy *Sonatina* (vốn là 3/4 Allegretto) và *Castillo* (nốt tròn 4 phách) vào chương I và IV ở 4/4 đang làm biến dạng chu kỳ 3 móc đơn của Torroba.
2. **Mặt nốt ở BPM = 96**: Mặt nốt đang quá dài (nốt tròn 2,5 giây ở Castillo, nhịp nốt trắng mỗi nửa ô ở Sonatina và Olite khi giá ngang), nên tempo 96 nghe chậm dề dà.
3. **Câu hát, láy trùm ba, và tiếng bass đứt**: Nốt đen ở bè trầm (nhất là bass bấm cao 40–53) tắt cụt giữa lúc câu còn hát, cộng thêm `staccato=True` bị gắn tràn sang cả scale của Sonatina và toàn bộ cửa Olite. Láy trùm ba (`E–F–E` có slur) bị rút thành 2 móc kép hoặc bị khóa ngoài BPM > 72.
4. **Cận dưới Velocity −4 và độ phủ texture**: Cổng `bpm > 72` và `n % 2 == 1` bỏ phí gần hết 8 kiểu kết cấu đã viết; còn `_micro_fits` cùng sàn `guitar_wave.py` đang chặn câu êm xuống −4.

---

## 1. Việc đang nghe

VRE 1M, bốn chương. Chương I và chương IV hiện là 4/4, nốt đen = 96. Chương I có Castillo. Chương IV có Olite — Sonatina — Olite.

Tai nghe ba lớp lỗi:

1. **Nhát đứt (staccato và bass cụt):** Nốt đen ở bè trầm, nhất là nốt bấm cao hơn dây buông, tắt ngay sau 1 phách (hoặc 0,5 phách ở Olite) giữa lúc câu còn hát. Cửa intro/outro của Olite đánh toàn hợp âm `staccato=True` suốt nhiều ô, và ô chạy thang âm của Sonatina (`_type3_scale`) cũng gắn `staccato=True` lên cả 8 móc đơn. Staccato thỉnh thoảng, đúng vị trí, trong một điệu nhảy (như nhát đầu của *Danza* hay *Fandanguillo*), thì là nhạc. Staccato và bass ngắn thành cách dựng cả câu thì làm đứt bản.
2. **Phẳng và thiếu chất luyến láy:** Castillo và Sonatina của chương I không có câu dài, không có contrast, không có chấm phá. Một nốt ngân suốt ô, hoặc hai tiếng rời cách nhau nửa ô, không phải mặt của Torroba. Chữ ký luyến láy trùm ba (`E–F–E` có slur) vắng mặt.
3. **Chậm dề dà vì sai mặt nốt và sai nhịp:** Cùng nốt đen = 96, mặt đang hát là nốt trắng và nốt tròn. Bản gốc của ông chạy bằng móc đơn và móc kép.

---

## 2. Xem lại cách chọn nhịp cho các chương Torroba

Nhìn lại toàn bộ các bản gốc của Torroba đang làm nguồn cho 7 pattern và 8 kiểu trong engine:

| Bản gốc của Torroba | Nhịp gốc | Tempo & Tính chất gốc | Khi ép vào 4/4 hiện tại |
|---|---|---|---|
| *Sonatina* I | **3/4** | Allegretto, tươi sáng, đối đáp móc đơn / móc kép (chu kỳ 3 móc hoặc 6 móc) | Bị dư 2 móc đơn cuối ô (`eighth 6, 7`): Kiểu 1 phải chêm 2 nốt đệm, Kiểu 2 phải đặt 2 dấu lặng ở móc 3 và 7, lưới nền chỉ gảy ở móc 0 và 4 (biến thành nhịp nốt trắng) |
| *Suite Castellana* I — *Fandanguillo* | **3/4** | Allegro / nhịp vũ khúc 3 phách | Quạt đầu ô rồi rải 3 phách; sang 4/4 bị kéo dài đuôi |
| *Suite Castellana* II — *Arada* | **3/4** | Lento trữ tình, chấm dôi + mordent trùm ba + rải móc đơn | Sang 4/4 nửa sau ô 1 bị kéo thành nốt trắng (`duration_beats = 2.0`) |
| *Suite Castellana* III — *Danza* | **3/8** (6/8) | Allegro vivace, nhóm 3 móc đơn | Đã cấm ở 4/4 vì không chia hết cho 8 móc |
| *Simancas* (Juglar) | **3/4** | Allegretto, chùm ba móc đơn (triplets) | Chỉ sống trên 3/4 |
| *Alcañiz* | **3/8** (6/8) | Allegro, nhóm 3 móc đơn | Chỉ sống trên 6/8 |
| *Torija* (Elegía) | **3/4** | Andantino / Lento ngân nga | Là ngoại lệ chậm trong *Castillos de España*, cũng ở nhịp 3/4 |
| *Olite* (*Fiesta del Rey Noble*) | **2/4** | Vivace (nốt đen = 95), rộn ràng, câu chạy 7 nốt móc kép + móc đơn qua 2 ô 2/4 | Ghép 2 ô 2/4 thành 1 ô 4/4 (4 phách đen) thì vừa khít, miễn là giữ nguyên móc kép và móc đơn |

### Hệ quả về chọn nhịp và phân vai chương

1. **Nhịp tự nhiên của Torroba là nhịp 3 (`3/4` và `6/8`) và nhịp `2/4` (tức `4/4` chia đôi mỗi 2 phách = 4 móc đơn):**
   - Trong `span.py`, `_guitar_meter` hiện chỉ đổi chương chậm (II) sang `3/4` và scherzo (III) sang `6/8`, còn chương mở đầu (1M-I, 3M-I, 1Y opener) và finale (1M-IV, 3M-III, 1Y closer) giữ `4/4`.
   - Với riêng Torroba (hoặc khi chọn nhịp chương cho Guitar):
     - **Nếu chương mở đầu / chương nhanh dùng *Sonatina* I (Allegretto), *Fandanguillo*, hoặc *Arada* / *Castillo*:** Nhịp đúng phong cách nhất của chúng là **3/4** (ở Allegretto 96–108 BPM) hoặc nếu giữ khung **4/4** của toàn hệ thống thì **mỗi ô 4/4 phải vận hành như hai ô 2/4 ghép lại (chu kỳ 4 móc đơn = 2 phách đen, phách mạnh tại móc 0 và móc 4)**, tuyệt đối không viết nốt tròn 4 phách hay bỏ trống 3 móc yếu.
     - **Nếu giữ `_guitar_meter` chung nhưng cho phép chương nhanh Guitar hoặc bảng pattern theo nhịp đúng chất Torroba:**
       - Trên **4/4 (90–108 BPM)** — thực chất là **hai ô 2/4 ghép lại**:
         - `rally` và `volatile`: **Olite** (A) — **Sonatina** (B) — **Olite** (A).
         - `calm`: **Sonatina** (A) — **Castillo** (B) — **Sonatina** (A) *(thay vì để Castillo ngân nốt tròn cả vùng A suốt chương 1 làm bản nhạc chậm dề dà; Sonatina Allegretto đứng làm A cho chương mở đầu tươi sáng, còn Castillo với Kiểu 7/8 Arada làm vùng B trữ tình 8 ô ở giữa)*.
         - `selloff`: **Castillo** (A, nhưng bắt buộc chạy mặt móc đơn + Kiểu 7/8 *Arada*, không ngân nốt tròn) — **Olite** (B) — **Castillo** (A).
       - Trên **3/4 (60–72 BPM, chương II)**:
         - Đây mới là chỗ của *Torija* / *Arada* chậm (**Castillo** với Kiểu 7 và Kiểu 8), đối đáp với **Juglar** (*Simancas* chùm ba) hoặc **Danza**.
       - Trên **6/8 (108–120 BPM, chương III Scherzo)**:
         - Giữ đúng nhịp vũ khúc 3/8–6/8 của **Fandanguillo**, **Alcaniz**, và **Danza**.

---

## 3. Tempo và mặt nốt ở 96 BPM

Ngoài *Torija* và vài bài chậm ở chương II (60–72 BPM), nhạc Torroba tươi sáng và có tốc độ. *Sonatina* I là Allegretto, không phải bản chậm. *Olite* là Vivace (nốt đen = 95).

Mặt nốt Torroba viết ở chương nhanh (90–108 BPM):

| Hình | Vai |
|---|---|
| **Móc kép (`0.25`) và chùm ba móc kép (`1/6`)** | Nét chạy, láy trùm ba (`E–F–E`), chấm phá |
| **Móc đơn (`0.5`)** | Mặt chính của câu hát và bè đệm rải. Phần lớn tiếng nằm ở đây |
| **Nốt đen (`1.0`) / đen chấm dôi (`1.5`)** | Trụ đầu câu hoặc một nhát trong điệu, dưới đáy luôn có bè trầm/bè trung rải móc đơn |
| **Nốt trắng (`2.0`), nốt tròn (`4.0`)** | Chỉ đứng ở chỗ ngân có chủ đích cuối câu hoặc trong chương chậm ≤ 72 BPM. **Cấm làm lưới nền của chương 96 BPM** |

Ở nốt đen = 96, một móc đơn dài 0,31 giây, một nốt đen dài 0,63 giây, một nốt trắng dài 1,25 giây, một nốt tròn dài 2,5 giây. Cách sửa trực diện mặt nốt của ba pattern trên 4/4 (96 BPM):

1. **Thân `castillo` ở BPM > 72 (`_render_castillo_bar` và `_span_castillo`):**
   - **Bỏ cổng `if ctx.bpm > 72: return None, ()` trong `_span_castillo`**: Cho phép `castillo` ở chương 96 BPM gọi đầy đủ **Kiểu 7 (*Arada*)** và **Kiểu 8**.
   - **Sửa `_render_castillo_bar` khi BPM > 72 (hoặc cho mọi ô lưới nền `castillo` trên 4/4):** Không viết một nốt tròn `written(origin, epb, midi)` suốt 4 phách kèm 1 bass đen cụt ở móc 0. Thay bằng **mặt 2 nửa ô (như hai ô 2/4 hoặc hai trụ chấm dôi *Arada*)**:
     - Nửa đầu (móc 0..3): `lead` hát `_melody_at(origin)` chấm dôi (`duration_beats = 1.5`), dưới đáy `bass` ngân 2 phách (`duration_beats = 2.0`, không cắt cụt ở 1 phách) và `support` rải móc đơn ở móc 1, 2; tại móc 3 `lead` đi móc đơn `_melody_at(origin + 3)` (hoặc láy trùm ba có slur nối sang móc 4).
     - Nửa sau (móc 4..7): `lead` hát `_melody_at(origin + 4)` chấm dôi (`1.5`) + móc 7 nối sang ô sau (hoặc khi câu `closes` mới ngân nốt trắng ở nửa sau), `bass` đi tiếp ở móc 4 (`2.0` phách).
   - Riêng ở **Kiểu 7 ô 1 trên 4/4**: nửa sau ô (từ `beat = 2.0`) khi `ctx.bpm > 72` không đứng im một nốt trắng `2.0` mà giữ chuyển động móc đơn ở móc 6–7 giống Ô 2 để câu không bị khựng.
2. **Lưới nền `sonatina` (`_render_sonatina_bar`):**
   - Hiện tại `lead` chỉ đánh ở `ctx.strong` (móc 0 và móc 4), mỗi nốt dài `0.5` phách rồi nghỉ suốt 3 móc yếu, làm nhịp giai điệu bị giãn thành nốt trắng.
   - **Sửa `_render_sonatina_bar`**:
     - Tại móc mạnh (`0` và `4` trên 4/4; `0` trên 3/4): `lead` đánh `_melody_at` (`duration_beats = 1.0` hoặc `0.5` nối slur), `bass` ngân trọn nửa ô (`duration_beats = 2.0` trên 4/4, `1.5` hoặc `3.0` trên 3/4 — không cắt ở `0.5` phách).
     - Tại các móc giữa (`1, 2, 3` và `5, 6, 7` trên 4/4; `1, 2, 3, 4, 5` trên 3/4): `lead` và `support` đối đáp liên tục bằng **móc đơn (`0.5`) kèm nốt lấy đà móc kép (`0.25`) / láy trùm ba có slur** đọc từ `_melody_at(origin + offset)`. Không để `lead` im lặng suốt 3 móc đơn giữa ô.
3. **Thân `olite` khi gộp hai ô 2/4 vào một ô 4/4 (`_olite_vivace` và `_olite_chord`):**
   - Giữ nguyên đồng hồ nốt đen (nốt đen = 95 của *Olite* và 96 của chương là một). Một ô 4/4 chứa đúng **hai ô 2/4**: nửa đầu là móc `0..3`, nửa sau là móc `4..7`.
   - **Cấm nghỉ trắng khi giá đi ngang (`start == target`)**: Trong `_olite_group`, hiện tại khi `start == target` thì `_scale_steps` trả về `[]` làm móc `(1, 2, 3)` hoặc `(5, 6, 7)` im lặng hoàn toàn, biến cả ô thành 2 hợp âm cách nhau một nốt trắng! Khi `start == target` (hoặc chênh 1 bậc), nhóm 3 móc `(1, 2, 3)` và `(5, 6, 7)` phải đánh **mô-típ láy của *Olite***: móc 1 là chùm láy móc kép / trùm ba quanh `start` (có slur `start -> bậc trên -> start`), móc 2 đi bậc lân cận, móc 3 dẫn về `target`.
   - Nhờ vậy, mỗi nửa ô (tức mỗi ô 2/4 gốc) luôn có đủ hợp âm mở phách + nét chạy móc kép/móc đơn đúng chất *Vivace*.

---

## 4. Giải quyết triệt để tiếng Staccato sai chỗ và Bass đứt quãng

Rà soát toàn bộ codebase Torroba, có đúng **4 nguồn** đang gây cảm giác staccato / giật cục sai phong cách. Kế hoạch khóa cách sửa từng nguồn:

1. **Nguồn 1 — Bass bấm cao (40–53) bị cắt ngắn hoặc bị bỏ rơi trong thân bài:**
   - Ở `_render_castillo_bar` (`guitar_torroba.py` dòng 364): Bass hiện viết `written(origin, 2, bass)` (chỉ dài 1 phách đen) rồi tắt. Khi `bass` là nốt bấm cao trong vùng 40–53, tiếng tắt phựt ở phách 2 nghe như một nhát staccato ở bè trầm. **Sửa:** Trên 4/4, bass ở móc 0 ngân `2.0` phách (4 móc đơn) và bass ở móc 4 ngân `2.0` phách (hoặc đi 2 nốt đen nối nhau ở móc 0 và móc 2 / móc 4 và móc 6). Trên 3/4, bass ngân ít nhất `1.5`–`3.0` phách.
   - Ở `_olite_chord` (`guitar_torroba.py` dòng 2949): Hiện có điều kiện `if _open_bass_tone(ctx, raw): low.append(...)` — nghĩa là khi hợp âm có bass bấm (không phải dây buông E2, A2, D3), **hợp âm Olite mất sạch tiếng bass**, chỉ còn 2 nốt cao chói ở trên! Và khi có bass thì chỉ dài `0.5` phách. **Sửa:** Bỏ điều kiện chỉ nhận `_open_bass_tone` ở `_olite_chord` và `_olite_thin`; luôn đánh `raw = _torroba_bass(...)` khi hợp lệ, và giữ bass ngân hết nửa ô (`duration_beats = 2.0` hoặc `1.0` phách đen), **không gắn `staccato`** lên bass của Olite thân bài.
2. **Nguồn 2 — Scale của Sonatina (`_type3_scale`, dòng 1671 `guitar_torroba.py`):**
   - Hiện tại vòng `for eighth, midi in enumerate(line):` gắn cứng `staccato=True` lên **cả 8 nốt móc đơn** của ô chạy scale. Một câu chạy 8 móc đơn mà đánh staccato toàn bộ thì nghe như máy gõ.
   - **Sửa:** Bỏ `staccato=True` trên các nốt chạy của `_type3_scale`. Thêm slur nối từng cặp móc đơn mở đầu (`slur_start` ở móc 0, `slur_stop` ở móc 1; và móc 4 sang móc 5) để câu chạy vừa rõ chữ vừa có độ luyến.
3. **Nguồn 3 — Cửa Intro / Outro của Olite (`_olite_chords` trong `guitar_torroba_doors.py`, dòng 534):**
   - Hiện tại toàn bộ 4 ô intro và 4 ô outro của Olite đều gọi `_olite_chords(..., staccato=True)` ở móc 0 và móc 4, phần còn lại của ô nghỉ trắng. Nghe suốt 4 ô đầu chương IV chỉ có tiếng hợp âm cụt giật cục.
   - **Sửa:** Trong `guitar_torroba_doors.py`:
     - Các ô intro và các ô outro trước ô cuối của `olite`: hợp âm ở móc 0 và móc 4 **không gắn `staccato=True`**, kéo dài `length = 2` (1 phách đen) hoặc kèm câu dẫn móc đơn ở móc 2–3 và 6–7.
     - Chỉ giữ `staccato=True` ở **nhát kết cuối cùng của ô outro cuối** (đúng kiểu kết điệu của Torroba).
4. **Nguồn 4 — Giữ lại Staccato đúng chỗ của điệu nhảy:**
   - Giữ `staccato=True` ở hợp âm đầu nhóm 3 của `danza` (`_render_danza_bar`), ở 3 móc đơn bass dồn sau rasgueado của `_type5_fan` (*Fandanguillo*), ở nhát móc kép mở đầu `_type6_half_b_open` (*Danza*), và ở nhát kết cuối cùng của cửa `fandanguillo` / `danza` / `olite`.

---

## 5. Luyến láy trùm ba (`E–F–E`) và Slur chữ ký của Torroba

Trong nhạc Torroba (*Arada*, *Sonatina*, *Torija*, *Olite*), chữ ký trang trí là **chùm ba móc kép luyến nhanh (mordent 3 nốt, ví dụ `E–F–E`) có slur** nằm gọn trong 1 móc đơn (`0.5` phách đen), đổ vào nốt chính ở móc đơn kế tiếp; cùng với các **slur nối câu dài** trên mặt móc đơn.

### 5.1. Gỡ rào kỹ thuật cho chùm ba móc kép (`duration_beats = 1/6`) trong Engine

Hiện tại mục 4.7 của `docs/sonify-guitar-torroba-phrase-plan.md` từng phải rút mordent 3 nốt của *Arada* thành 2 móc kép (`0.25 + 0.25`) vì ba rào kỹ thuật trong `guitar_patterns.py` và `musicxml.py`. Bản kế hoạch này gỡ cả ba rào để viết đúng chùm ba `1/6` phách:

1. **Bật `divisions = 12` khi có chùm ba móc kép:**
   - Ở `divisions = 12`, 1 phách đen = 12 đơn vị, 1 móc đơn (`0.5` phách) = 6 đơn vị, và mỗi nốt trong chùm ba móc kép (`duration_beats = 1/6`) dài đúng **2 đơn vị** (chẵn, không lẻ tick).
   - Hàm `_needs_twelfths` trong `guitar_patterns.py` (dòng 2423) kiểm tra `abs(value * 4 - round(value * 4)) > 1e-6`. Với `duration_beats = 1/6`, `value * 4 = 2/3` nên `_needs_twelfths` **đã tự động trả về `True`** và bật `divisions = 12`, đồng thời `_fill` đã tự chuyển sang `_fill_twelfths`.
2. **Sửa `_resolve` và `assert_playable` trong `guitar_patterns.py` để không đè nốt `1/6`:**
   - Hiện tại `_resolve` (dòng 2230) chỉ miễn cho ô có `_is_sixth` khi cả nhóm dài 6 nốt, còn `_start16(event, epb)` lấy `floor(event.beat * 4)` nên hai nốt tại `beat = 1.5` và `beat = 1.5 + 1/6` (`1.6667`) cùng ra `_start16 = 6` và bị `assert_playable` (dòng 4057) báo `Unplayable("two notes in the high voice")`.
   - **Cách sửa trong `guitar_patterns.py`:**
     - Trong `_resolve`: khi một voice trong ô có bất kỳ sự kiện nào nằm trên lưới `1/12` (không nằm trên lưới `1/4` phách), `_resolve` tính điểm bắt đầu và độ dài trên **lưới `1/12` phách** (`int(round(event.beat * 12))` và `max(1, int(round(event.duration_beats * 12)))`) thay vì `_start16` / `_dur16`.
     - Trong `assert_playable` và `_covers`: thêm helper `_ covers_at_12` (hoặc kiểm tra chồng lấp theo khoảng thực `[event.beat, event.beat + event.duration_beats)` với dung sai `1e-4`) để 3 nốt liên tiếp tại `1.5`, `1.5 + 1/6`, `1.5 + 2/6` (mỗi nốt dài `1/6`) là 3 thời điểm nối đuôi nhau, không bao giờ bị coi là đánh chồng 2 nốt cùng lúc.
3. **Xuất `<time-modification>` (3:2 trên `16th`) và `<tuplet>` trong `musicxml.py`:**
   - Hiện tại `_sextuplet_roles` (dòng 272 `musicxml.py`) chỉ đóng khung `<tuplet type="start/stop">` khi có đủ **6 nốt `_is_sixth` liên tiếp (tổng = 1.0 phách)**.
   - **Cách sửa trong `musicxml.py`:**
     - Mở rộng `_sextuplet_roles` (hoặc thêm `_triplet_sixteenth_roles`): khi gặp chuỗi **3 nốt `_is_sixth` liên tiếp có tổng `duration_beats == 0.5`** (1 móc đơn) mà không nằm trong chùm 6 nốt, gắn `tuplet = "start"` ở nốt đầu, `tuplet = "stop"` ở nốt thứ ba, và ghi `<time-modification><actual-notes>3</actual-notes><normal-notes>2</normal-notes><normal-type>16th</normal-type></time-modification>` với `<type>16th</type>` (`duration = 2` ở `divisions = 12`).
     - Tổng thời lượng của 3 nốt là `2 + 2 + 2 = 6` đơn vị = đúng 1 móc đơn ở `divisions = 12`. MuseScore xuất `.mscz -> .wav/.mid` khớp tuyệt đối `0` tick lệch.

### 5.2. Chỗ đặt láy trùm ba (`E–F–E`) và Slur trong câu

Thêm helper `pen.mordent_triplet(beat, principal, others, written, steps)` trong `guitar_torroba.py`:
- Nhận nốt chính `principal` (ví dụ `E`) và tìm nốt bậc thang liền trên `upper = _walk(principal, +1, ...)` (ví dụ `F`).
- Kiểm tra thế tay `_position_ok` cho `[principal, upper] + others`.
- Nếu hợp lệ, viết **3 nốt `duration_beats = 1/6`** tại `beat`, `beat + 1/6`, `beat + 2/6`:
  1. `principal` (`E`), `slur_start=True`, bậc `steps`
  2. `upper` (`F`), bậc `steps + 1` (nhẹ hơn 1 bậc vi mô để tiếng láy mềm)
  3. `principal` (`E`), `slur_stop=True`, bậc `steps`
- Áp dụng tại:
  - **Kiểu 7 (*Arada*) ô 1 và ô 2** (móc đơn 3, `beat = 1.5`): thay cặp 2 móc kép hiện tại bằng đúng chùm 3 móc kép mordent `principal -> upper -> principal` đổ vào phách 3 (`pen.mel(4)`).
  - **Kiểu 7 ô 3** (móc 1 và móc 5) và **ô 4** (`base + 3`): dùng chùm ba láy hoặc láy slur mềm.
  - **Kiểu 3 (`_type3_motif`)** và **Kiểu 4 (`_type4_call`)** ở `beat = 1.5`: dùng chùm ba móc kép `E–F–E` có slur.
  - **Thân `olite` (`_olite_group`), thân `sonatina` (`_render_sonatina_bar`), và thân `castillo` nhanh (`_render_castillo_bar`)**: đặt láy trùm ba ở móc dẫn trước phách mạnh (móc 3 dẫn vào móc 4) và nối slur giữa các cặp móc đơn đi liền bậc.

---

## 6. Phân bổ 8 Kiểu kết cấu: 100% số câu có Kiểu, độ phủ 60% – 70% số ô thân bài

Hiện tại `select_torroba_figure` và `torroba_figure_plan` làm rơi phần lớn chương (chỉ đạt 0% ở `castillo` BPM > 72 và ~15%–20% ở `sonatina`) về lưới nền vì 3 cổng hạn chế:
1. `if ctx.bpm > 72` trong `_span_castillo` -> khóa sạch Kiểu 7, 8 ở chương 96 BPM.
2. `elif n is None or n % 2 == 1: return None, ()` -> cứ 2 câu thì 1 câu bị bỏ trống toàn bộ.
3. Trong câu chẵn `n % 2 == 0`, `_span_sonatina` chỉ trả về `slots = (0, 1)` (2 ô) hoặc `(1,)` (1 ô). Một câu dài 6–8 ô thì 4–6 ô sau vẫn rơi về lưới nền.

Ngược lại, nếu phủ kín 100% số ô bằng các Kiểu có cá tính mạnh (rasgueado, đối đáp giật nhịp, chạy bass 7 móc đơn, *Arm. 8*) thì bản nhạc sẽ thành chắp vá (patchwork), mất khoảng thở và không còn phân biệt được đâu là câu hát dẫn dắt, đâu là nét chấm phá / contrast.

### Luật phân bổ 60% – 70% trong `guitar_torroba.py`

Khi lưới nền của `castillo` và `sonatina` đã được đổi thành mặt móc đơn / chấm dôi cantabile có slur (Mục 3), các ô lưới nền đóng vai trò **đường dẫn câu mượt mà (30% – 40% số ô)**, còn 8 Kiểu kết cấu đóng vai trò **hình thái chủ đạo và chấm phá (60% – 70% số ô)**:

1. **100% số câu thân bài đều có Kiểu (bỏ cổng `n % 2 == 1` và bỏ cổng `ctx.bpm > 72`):**
   - Mọi chương `castillo` (kể cả 4/4 ở 96 BPM và 1D) đều được gọi Kiểu 7 và Kiểu 8.
   - Mọi câu thân bài (`_body_phrase`) đều được xếp kiểu xoay vòng theo chỉ số câu `n = 0, 1, 2, ...` (không bỏ trống câu lẻ).
   - Khi `previous == figure`, thay vì trả về `None` (rơi cả câu về lưới nền), hàm **xoay sang kiểu kế tiếp trong họ pattern đó** để hai câu sát nhau vừa có contrast vừa luôn có Kiểu.
2. **Tỷ lệ 60% – 70% số ô bên trong mỗi câu:**
   - **Câu ngắn (2–4 ô):**
     - Câu 2 ô: Kiểu chiếm 1–2 ô (Kiểu 1 trên 1 ô, hoặc Kiểu 2 / Kiểu 4 / Kiểu 8 trên 2 ô).
     - Câu 3–4 ô: Kiểu chiếm **2–3 ô** (ví dụ 2 ô Kiểu 4 hoặc Kiểu 2 hoặc Kiểu 8, hoặc 3 ô Kiểu 3 ở câu đóng), dành **1–2 ô** cho mặt móc đơn cantabile nối mượt vào/ra ($\approx 60\% - 75\%$).
   - **Câu dài (5–8 ô):**
     - Với `castillo`: **Kiểu 7 (*Arada*, 5 ô)** chiếm 5 ô đầu, **1–3 ô cuối** là mặt chấm dôi / móc đơn dẫn mượt để câu thở trước khi sang câu mới ($\approx 65\% - 80\%$). Khi đến lượt `k` của Kiểu 8 trên câu dài 5–8 ô: đặt **Kiểu 8 (2 ô)** ở đầu câu và **Kiểu 8 (2 ô)** ở nửa sau (cách nhau 1–2 ô dẫn mượt), đạt 4/6 hoặc 4/7 ô ($\approx 60\% - 67\%$).
     - Với `sonatina`: Câu 5–8 ô không chỉ gắn 2 ô đầu rồi bỏ trống 3–6 ô cuối. Mở câu bằng **2 ô Kiểu 4 (đối đáp)** (hoặc **Kiểu 1**), đi **1–2 ô mặt móc đơn cantabile có láy trùm ba** ở giữa câu để nối hơi, rồi nửa sau vào **2 ô Kiểu 2** (nếu câu chưa đóng) hoặc **2–3 ô Kiểu 3** (nếu câu `closes`), đạt 4/6 hoặc 5/7 ô ($\approx 65\% - 70\%$).
     - Với `fandanguillo` và `danza`: **Kiểu 5 (4 ô)** hoặc **Kiểu 6 (4 ô)** chiếm 4 ô trong câu 5–6 ô (hoặc 2 ô Kiểu 2 trong câu 3–4 ô), dành **1–2 ô** chạy nhịp điệu cơ bản của điệu nhảy cho người nghe bắt nhịp ($\approx 65\% - 75\%$). Hạ ngưỡng `rise` của Kiểu 2 từ `3` xuống `1` để các câu ít biến động giá vẫn đạt tỷ lệ này.

---

## 7. Cho phép câu êm xuống Velocity −4 (cận dưới −4)

Để những đoạn êm của Torroba thực sự xuống nhẹ hơn −4 như cảm quan nghe yêu cầu, phải mở đồng thời ở **hai tầng** đang khóa cận dưới:

1. **Tầng vi mô trong ô (`guitar_torroba.py` và `_micro_fits`):**
   - Hiện tại `_MICRO = 2`. Trên câu phẳng band `mf`, `lead` viết `64`, `bass` viết `60`, `support` viết `56`. Khi `lead` xin hạ 2 bậc (`steps = 2`, tức `−4` xuống `60`), hàm `_micro_fits` thấy `bass = 60` đang vang nên chặn lại, chỉ cho `lead` hạ 1 bậc (`−2`, còn `62`) để giữ `lead >= bass + 2`.
   - **Cách sửa trong `_realize` / `_Pen.beds` của `guitar_torroba.py`:**
     - Trên các câu êm (`phrase.rise < MIN_RISE` hoặc ô thuộc `castillo`, `sonatina`, `olite_thin`, `alcaniz_soft`, và các tiếng láy / nhại `p`), cho phép bậc vi mô của các nốt êm/láy nhận `steps = 2` (tức **−4** so với mức viết), và **hạ đồng thời giường `bass` / `support` đi 2 bậc (`−4`, từ `60 / 56` xuống `56 / 52`, sàn `_MICRO_FLOOR = 36` thay vì `40`)**.
     - Khi `bass` ở `56` và `support` ở `52`, `lead` từ `64` hạ `−4` xuống `60` vẫn cao hơn `bass` đúng `4` đơn vị (`60 > 56 > 52`), vượt qua `_micro_fits` một cách tự nhiên mà không bao giờ chọc thủng bè trầm.
2. **Tầng sóng động lực toàn cục (`PROFILES` trong `backend/app/sonify/guitar_wave.py`):**
   - Hiện tại trong `guitar_wave.py` (dòng 116–124), các profile của Torroba đang đặt cận dưới (`floor_calm`, `floor_wide`) cao hơn hẳn Bach/Sor/Barrios:
     - `castillo`, `sonatina`, `torroba_tremolo`: `floor_calm = 34, floor_wide = 34`
     - `fandanguillo`, `danza`, `alcaniz`, `olite`: `floor_calm = 40, floor_wide = 40`
   - **Cách sửa trong `guitar_wave.py`:** Hạ `floor_calm` và `floor_wide` của toàn bộ 7 hàng `("torroba", ...)` xuống **−4 đơn vị**:
     - `castillo`, `sonatina`, `torroba_tremolo`: **`30, 30`** (từ `34, 34`)
     - `fandanguillo`, `danza`, `alcaniz`, `olite`: **`36, 36`** (từ `40, 40`)
   - Nhờ vậy, cả độ chênh vi mô trong câu lẫn đáy sóng `p / pp` của toàn chương đều xuống êm hơn đúng **−4**.

---

## 8. Danh mục chỗ sửa khi thực hiện

1. **`backend/app/sonify/guitar_patterns.py`:**
   - Mở `_resolve` và `assert_playable` (`_covers`) cho chùm ba móc kép (`duration_beats = 1/6` ở `divisions = 12`) để 3 nốt láy liên tiếp trong 1 móc đơn không bị coi là trùng `_start16`.
   - Hạ `_MICRO_FLOOR` từ `40` xuống `36` (hoặc cho phép giường êm hạ −4).
2. **`backend/app/sonify/musicxml.py`:**
   - Mở `_sextuplet_roles` / thêm `_triplet_sixteenth_roles` để xuất `<time-modification>` (`3:2` trên `16th`) và `<tuplet type="start/stop">` cho chùm 3 nốt `1/6` phách đứng trong 1 móc đơn (`0.5` phách).
3. **`backend/app/sonify/guitar_torroba.py`:**
   - **Chọn pattern theo nhịp (`_torroba_primary`, `_torroba_contrast`)**: Trên 4/4 `calm`, đưa `sonatina` (Allegretto) lên làm vùng A và `castillo` (*Arada*) làm vùng B 8 ô ở giữa để chương mở đầu tươi sáng, không trải `castillo` cả vùng A.
   - **Lịch kiểu 60% – 70% (`_span_castillo`, `_span_sonatina`, `_span_fandanguillo`, `_span_danza`, `select_torroba_figure`, `torroba_figure_plan`)**: Bỏ cổng `ctx.bpm > 72` của `_span_castillo`; bỏ cổng `n % 2 == 1` trả về lưới nền (100% số câu đều có Kiểu); khi `previous == figure` thì xoay sang kiểu kế tiếp; trên các câu dài 5–8 ô đặt 2 cụm Kiểu ở đầu và nửa sau câu, cách nhau 1–2 ô mặt móc đơn cantabile để đạt độ phủ **60% – 70% số ô thân bài** (không để trống < 25% và không nhồi kín 100%).
   - **Mặt nốt lưới nền (`_render_castillo_bar`, `_render_sonatina_bar`, `_olite_vivace`, `_olite_chord`, `_olite_group`)**:
     - `_render_castillo_bar`: đổi từ 1 nốt tròn 4 phách + 1 bass đen cụt sang hai nửa ô chấm dôi + móc đơn rải + bass ngân 2 phách mỗi nửa ô.
     - `_render_sonatina_bar`: `lead` hát móc đơn/móc kép xuyên qua các móc yếu kèm slur, `bass` ngân nửa ô (`2.0` phách).
     - `_olite_group` & `_olite_chord`: không nghỉ trắng khi `start == target` (thay bằng chùm láy móc kép/trùm ba + móc đơn); luôn đánh bass (kể cả bass bấm 40–53) và giữ ngân, không cắt cụt.
   - **Gỡ staccato sai chỗ**: Bỏ `staccato=True` trên 8 móc đơn của `_type3_scale`, thay bằng slur đầu nhóm.
   - **Láy trùm ba (`pen.mordent_triplet`)**: Viết 3 nốt `1/6` phách (`E–F–E`) có slur cho mordent của Kiểu 7 (ô 1, ô 2), Kiểu 3, Kiểu 4, và móc dẫn của Olite / Sonatina / Castillo.
   - **Cận dưới Velocity −4**: Hạ giường `bass / support` đi 4 đơn vị ở câu êm và cho phép các tiếng êm/láy hạ 2 bậc (`-4`).
4. **`backend/app/sonify/guitar_torroba_doors.py`:**
   - Trong `_olite_chords`: bỏ `staccato=True` trên các ô intro và các ô outro trước ô cuối; kéo dài hợp âm thành nốt đen (`length = 2`) hoặc nối móc đơn dẫn; chỉ giữ `staccato=True` ở nhát kết cuối cùng của outro.
5. **`backend/app/sonify/guitar_wave.py`:**
   - Hạ `floor_calm` và `floor_wide` của 7 profile `("torroba", ...)` đi 4 đơn vị (`34 -> 30`, `40 -> 36`).
6. **`backend/app/sonify/audio.py` và Tests (`test_sonify_guitar_torroba.py`, `test_sonify_guitar_torroba_doors.py`, `test_program.py`):**
   - Tăng `SPAN_REVISION` để làm mới các file audio cached.
   - Cập nhật và thêm test khóa: mặt nốt chương 4/4 ở 96 BPM không còn nốt tròn làm lưới, Olite không nghỉ trắng khi giá đi ngang, chùm ba móc kép `1/6` xuất MusicXML hợp lệ và qua `assert_playable`, `_type3_scale` và cửa intro Olite không còn staccato tràn lan, và cận dưới velocity xuống thêm −4.
