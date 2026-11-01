# Torroba: cửa nhịp gốc, bè trung, và trần chương đầu

> **Trạng thái**: đã code trên PR 112. Bản này là khóa hiện hành. Bản mặt nốt không được dùng để viết lại nhịp hay mặt 2+2.
> **Đọc cùng**: [`docs/sonify-guitar-torroba-note-surface.md`](./sonify-guitar-torroba-note-surface.md), [`docs/sonify-guitar-torroba-castillos-frames.md`](./sonify-guitar-torroba-castillos-frames.md) mục 3, [`docs/sonify-guitar-torroba-dynamics.md`](./sonify-guitar-torroba-dynamics.md) mục 2.
> **Giữ**: `_guitar_meter` của mọi ensemble khác Torroba. Olite trên 4/4. Arada (kiểu 7 và kiểu 8) trên 4/4. Không thêm id pattern. `_shape_dynamics` vẫn chạy. Không nâng dynamics bằng bậc vi mô trong ô.

Pattern vốn là 2/4 hoặc 4/4 thì giữ đúng nhịp đó. Pattern vốn là 3/4 hoặc 6/8 thì bỏ mặt đã ép sang 4/4 và đi cửa sẵn có. Figure vốn là 2/4 hoặc 4/4 mà đang được gọi trong nhóm 3/4 hoặc 6/8 thì chuyển về pattern của nhịp gốc.

---

## 1. Nhịp gốc

Engine có `METER_34` và `METER_68`. Không có `METER_24` và không có nhịp 3/8. Một ô 3/8 viết thành một nửa ô 6/8. Hai ô 2/4 viết thành một ô 4/4, phách mạnh ở móc 0 và móc 4. Cách gộp đó chỉ dành cho nguồn vốn là 2/4.

| Pattern | Nguồn | Nhịp gốc | Cửa |
|---|---|---|---|
| `sonatina` | *Sonatina* I *Allegretto*, II *Andante* | 3/4 | 3/4 |
| `sonatina` | *Sonatina* III *Allegro* | 3/8 | 6/8, xem mục 4 |
| `castillo` | *Torija* và các *Castillos* chậm | 3/4 | 3/4. Không gọi kiểu 7, kiểu 8; gọi hai câu 3/4 (`CASTILLO_WALK = 13`, `CASTILLO_CADENCE = 14`) |
| `castillo` khi là Arada | *Suite Castellana* II, *Arada*, Lento | 4/4, hai nửa ô | 4/4. Kiểu 7 và kiểu 8 chỉ ở đây |
| `fandanguillo` | *Suite Castellana* I | 3/4 và 6/8 | Bỏ tuple `(2, 4, 6)` của `_fandanguillo_melody`. Hàm chỉ trả `(2, 3)` trên 6/8 và `(2, 4)` trên 3/4 |
| `danza` | *Suite Castellana* III | 3/4 và 6/8 | Giữ. `_danza_spans` tiếp tục trả rỗng ngoài hai nhịp này |
| `torroba_tremolo` | *Simancas*, Juglar | 3/4 | Giữ. Ngoài 3/4 vẫn là `_downbeat_only` |
| `alcaniz` | *Alcañiz*, 3/8 | 6/8 | Giữ. Ngoài 6/8 vẫn là `_downbeat_only` |
| `olite` | *Olite*, Vivace, nốt đen = 95 | 2/4 | Giữ 4/4. `_render_olite_bar` tiếp tục đòi `kind == "4/4"`. Đây không phải bản ép |

Mặt 2+2 ở `bpm > 72` và `kind == "4/4"` là cách ép. Bỏ cả ba nhánh, kể cả ô Castillo không rơi vào span kiểu 7 hoặc 8:

- `_render_castillo_bar` gọi thẳng `_render_castillo_sustain` trên 4/4 ở mọi BPM. Không còn nhánh chấm dôi và mordent khi `bpm > 72`.
- `_type7_bar1` luôn `resolution="half"` trên 4/4. Bỏ `resolution="dotted"`.
- `_type3_sustain` bỏ `fast = bpm > 72 and kind == "4/4"`.

Arada trên 4/4 dùng nửa ô đó ở mọi BPM, kể cả 96. `_type7_bar4` trên 4/4 giữ hai nửa `_type7_half`.

---

## 2. Chương nào giữ 4/4

`_guitar_meter` không đổi. Nhịp Torroba được quyết định khi dựng `PreparedMovement`, trước `render()`, vì `scale_fingerprint` băm `meter.beats` và `meter.beat_type`. Đổi meter bên trong `render()` sau khi fingerprint đã tính sẽ làm cache và `piece_seconds` lệch khỏi ô nhạc.

`prepare_month`, `prepare_quarter`, và `prepare_year` hiện chỉ nhận `variant`. `prepare_week` không nhận `variant` lẫn `ensemble`. `plan_span` trong `backend/app/services/spans.py` phải truyền `ensemble` vào bốn hàm đó. Chỉ khi `variant == "guitar"` và `ensemble == "torroba"` thì áp bảng dưới. Ensemble khác nhận đúng spec guitar hiện tại.

1D không đi qua `prepare_*`. `render.py` gán `DAILY_ENSEMBLE_SPEC`, đang là 4/4, 34 ô. Bản copy cho Torroba đổi meter của spec đó trước khi soạn, cùng bảng character, và giữ 34 ô. Không gọi `attach_frame` cho ngày.

`_assign_torroba` và `form_pattern_ids` nhận ngày bằng `ctx.bars == 34 and ctx.kind == "4/4"`. Ngày `calm` hoặc `selloff` sang 3/4 thì cổng đó sai, và ngày bị in ba tên. Đổi hai cổng đó thành `ctx.bars == 34`. Trên engine chỉ bài ngày có 34 ô. Không đụng các cổng `bars == 34` của Bach và Barrios.

`plan_month` và `plan_quarter` gọi `attach_frame` trước khi có character. `frame_bars_for` cho 1M và 3M là 4 ô trên 4/4 và 6 ô trên 3/4 hoặc 6/8. 1Y là 2 ô trên 4/4 và 3 ô trên 3/4 hoặc 6/8. Đổi meter sau khung thì chương 3/4 vẫn mang khung 4 ô của 4/4.

Thứ tự cho Torroba: lấy spec thân từ `month_specs`, `quarter_specs`, hoặc `year_specs`, chưa khung. Biết character. Đổi meter theo bảng dưới. Rồi mới `attach_frame`. `plan_month` không còn khung hộ trước bước này.

1W không có khung. Character dùng để đổi nhịp tuần là `session_characters[0]`, cùng vùng mở mà `_torroba_opening_mood` đọc. Không dùng `movement.character` của cả tuần khi nó khác phiên đầu.

`plan_span` được gọi ở `backend/app/routers/stocks.py` (`get_span`) và ở `load_movement_audio`. Cả hai phải nhận `ensemble`. Manifest đổi nhịp mà audio vẫn dựng bằng `classic` thì fingerprint lệch và file trả 404.

Chương guitar đã là 3/4 hoặc 6/8 thì giữ nguyên hàng pattern của nhịp đó, trừ ô `3/4 calm` ở mục dưới. Chương guitar đang 4/4 thì:

| Character | Nhịp Torroba | A | B |
|---|---|---|---|
| `rally` | 4/4 | `olite` | `castillo`, chỉ Arada |
| `volatile` | 4/4 | `olite` | `castillo`, chỉ Arada |
| `calm`, `bpm > 72` | 3/4 | `sonatina` | `castillo` lưới 3/4, không kiểu 7 và 8 |
| `calm`, `bpm <= 72` | 3/4, chương vốn đã 3/4 | `castillo` | `torroba_tremolo` |
| `selloff` | 3/4 | `castillo` lưới 3/4 | `danza` |

Ô `("3/4", "calm")` không được đổi thành `sonatina` cho mọi BPM. `_torroba_primary` và `_torroba_contrast` phân nhánh: `kind == "3/4"` và `mood == "calm"` và `ctx.bpm > 72` thì A là `sonatina`, B là `castillo`. Cùng ô mà `ctx.bpm <= 72` thì A vẫn là `castillo`, B vẫn là `torroba_tremolo`. Chương II của 1M là 3/4 ở 72. Assertion `Castillo — Juglar — Castillo` trong `test_program.py` giữ nguyên. Chương I calm ở 96, sau khi sang 3/4, mới là Sonatina — Castillo — Sonatina.

`_torroba_contrast` trên 4/4 khi primary là `olite` trả `castillo`, không trả `sonatina`. Hàng 4/4 của `_torroba_primary` chỉ còn `olite` cho `rally` và `volatile`. Assertion finale `Olite — Sonatina — Olite` đổi thành `Olite — Castillo — Olite`. Ô `calm` và `selloff` của hàng 4/4 không còn được chọn, vì hai character đó đã sang 3/4 trước lúc chọn pattern.

SSI 1M sau bảng này:

| Chương | Character | Nhịp | Điệu |
|---|---|---|---|
| I | calm | 3/4 | Sonatina — Castillo — Sonatina |
| II | selloff | 3/4 | Castillo — Danza — Castillo, giữ |
| III | selloff | 6/8 | Fandanguillo — Danza — Fandanguillo, giữ |
| IV | volatile | 4/4 | Olite — Castillo — Olite. Castillo ở đây là Arada |

---

## 3. Arada rời nhóm 3/4 và 6/8; hai câu Castillos 3/4 (kiểu 13 và 14)

Kiểu 7 và kiểu 8 là *Arada*, nhịp gốc 4/4. `_castillo_spans` trên `6/8` trả `[]`. Trên `4/4`, Arada không dùng mặt nhanh `bpm > 72`; `_type7_bar1` luôn `resolution="half"`.

Trên `3/4`, `_castillo_spans` không gọi Arada mà gọi hai câu *Castillos* (`CASTILLO_WALK = 13` khi `n` chẵn, `CASTILLO_CADENCE = 14` khi `n` lẻ) cho mọi câu dài từ 2 ô. Câu lặp mỗi 9 ô. Phần dư ngắn hơn 9 ô dùng bảng vai co của chính câu đó, không trở về lưới ngân cả ô. Câu đúng 1 ô vẫn ở lưới đó:

- **Câu 1 (`CASTILLO_WALK = 13`, ô #3 → #11):**
  - Ô đầu (`fan`): hợp âm dải rasgueado 5–6 dây ở móc 0 (`steps = 0`, `accent=True`), bốn móc đơn staccato lặp trên dây trầm (`steps = 2, 2, 1, 1`), móc 5 đẩy sang ô kế (`steps = 0`, `accent=True`).
  - Các ô giữa: xen kẽ ô ba nốt đen đi bước xuống (`quarters`, bậc vi mô `0, 1, 2` giảm dần trong ô) và ô bốn móc đơn có luyến đầu ô rồi một nốt đen (`turn`, bốn móc đơn lượn `0, 2, 1, 2` rồi nốt đen bậc `1`). Ô áp chót (`turn_to_bass`) đặt tiếng trầm ở phách 3 để dẫn vào ô kết.
  - Ô cuối (`hold`, bản lề ô #11): nốt trầm ngân trọn 3 phách dưới bốn móc đơn dẫn ở thế tay `II` đi từ nhẹ lên rõ (`steps = 2, 2, 1 → 0`, nốt đen cuối `accent=True`).
- **Câu 2 (`CASTILLO_CADENCE = 14`, ô #11 → #19):**
  - Ô đầu (`pickup`, cùng mặt bản lề ô #11): mở lại bằng nốt trầm ngân trọn ô và bốn móc đơn dẫn `2, 2, 1 → 0`.
  - Hai ô hợp âm đen `cresc.` (`chords_a` → `chords_b`): bậc vi mô đi từ `(2, 2, 1)` sang `(1, 1, 0)` tạo crescendo xuyên hai ô.
  - Ô bung `f` (`burst`): móc 0 bậc `0` (`accent=True`). Chùm mordent và hai phách sau ngồi bậc `2`. Trên lead viết 64 thì nghe 60. Bass cả ô là bed yếu, nên bậc 2 lọt qua; nốt giữa mordent xin thêm một bậc nhưng bed không cho, ba nốt nghe đều.
  - Ô hợp âm đáp (`echo`): ba nốt đen bậc `(0, 1, 2)`, mỗi phách một tiếng trầm cùng bậc. Trên lead viết 64 nghe `64, 62, 60`.
  - Hai ô chấm dôi thế tay `VII` (`dotted` / `tie_prep`): phách đầu chấm dôi bậc `0` (`accent=True`), móc đơn lướt nhẹ bậc `2` (trên nền `weak_bass`), phách 3 bậc `1`.
  - Ô kết `rall. / ten.` (`final`): giai điệu ngân trọn ô ở bậc `0`, đúng vận tốc viết, kể cả khi nốt trùng nút harmonic. Dưới là ba nốt trầm đen đi về đúng chủ âm, bậc `(2, 1, 0)`, nhấn vào nốt kết `ten.`.

Hai kiểu `13` và `14` nằm trong `_REAL_TORROBA_FIGURES`, nên các ô thuộc hai kiểu này giữ bè cao (không hạ quãng 5) và tách các đoạn lưới nền giống kiểu 1–8 và `ALCANIZ_OPENING`. Câu `castillo` 3/4 chỉ dài 1 ô vẫn ở lại lưới ngân cả ô.

---

## 4. Sonatina trên 6/8

*Sonatina* III là 3/8. Bảng mood 6/8 hiện không có ô nào trả `sonatina`: calm là `danza`, rally là `alcaniz`, volatile và selloff là `fandanguillo`. Ba ô đó là đúng nguồn, không nhường cho Sonatina.

Đợt này không thêm ô mood 6/8 cho `sonatina`, và không viết lưới mới. `_render_sonatina_bar` khi `kind == "6/8"` đang rơi nhánh phách mạnh cũ. Nhánh đó không phải chương III. Vì bảng không chọn `sonatina` trên 6/8, nhánh đó không được gọi. Đừng coi nó là cửa 6/8 của Sonatina.

Sonatina I và II đi cửa 3/4 qua `_render_sonatina_moving`.

---

## 5. Một nửa đoạn lưới nền hát thấp một quãng 5

Giai điệu hạ vẫn là `voice 1`. Không chuyển sang `voice 2`. `apply_torroba_sung_arch` chỉ nhận nốt lead. Voice 1 trống thì câu đó mất vòng cung.

PR 111 cho hầu hết câu `castillo` và `sonatina` có `L >= 2` ít nhất một span trong `torroba_figure_plan`. Điều kiện «cả câu không có ô figure» gần như không bao giờ đúng trên hai pattern đó. Không viết `if any(bar in plan)`.

Đơn vị là một đoạn lưới nền: dãy ô thân bài liên tiếp, cùng một câu, vắng mặt trong `torroba_figure_plan`. Đếm từ 0 theo thứ tự trong chương. Đoạn có `index % 2 == 0` hạ giai điệu, kể cả đoạn mở đầu. Đoạn có `index % 2 == 1` giữ bè cao. Ô figure giữ bè cao.

Cao độ không phải `midi - 7`. Hạ bốn bậc thang bằng `_scale_degree_below(midi, 4, ctx.mode)`. Trong docstring của hàm đó, hai bậc là một quãng 3, nên bốn bậc là một quãng 5 đúng điệu thức. Trên phách mạnh, nếu nốt đó không thuộc hợp âm, lấy nốt hợp âm gần nó nhất mà vẫn không cao hơn nốt thang vừa hạ.

Sàn là `max(bass + 3, 55 - ctx.semitones)` khi có bass, nếu không thì `55 - ctx.semitones`. Cao độ vang vì thế được xuống tới 55. Nốt thang nằm dưới sàn thì lấy nốt thang tại hoặc ngay trên sàn. Nốt đó vẫn chạm bass thì nốt này không hạ.

`assert_playable` đang đặt `floor = 59` cho mọi nốt `voice == 1` ngoài `scale_eighths`. Lead vang 55–58 ném `Unplayable`. Với `profile == "torroba"`, sàn đó hạ xuống 55. Profile khác giữ 59.

Khi lead đã hạ có cao độ vang `<= 62`, support dưới nốt đó nghỉ. `_torroba_inner` không bị ép vào một quãng hẹp giữa bass và lead. Bass giữ bè trầm.

Hạ xảy ra trên các eighth của đoạn đó, ghi vào mảng mà `_melody_at` đọc, trước vòng render từng ô. `apply_scale_passages` chạy sau vòng đó và phải vẫn thấy đường giá gốc: passage tính từ bản melody trước khi hạ, rồi ghi đè đúng các eighth của passage. Eighth không thuộc passage giữ nốt đã hạ.

`apply_sonatina_downbeats` chạy sau passage. Nó đang lấy `target = _melody_at(ctx, eighth)`. Nếu mảng đó vẫn là bè cao trong khi ô đã viết nốt hạ, nốt lấy đà móc kép bị trồng ở quãng cao rồi slur xuống bè trung. Target của một ô thuộc đoạn hạ là midi của nốt lead đã viết tại phách mạnh của ô đó, không phải `_melody_at` của đường giá gốc.

---

## 6. Dày thêm một bước

Chương IV của SSI dày vì Olite ngân bass khoảng 1,7 phách. Không kéo các chương kia lên mức đó, và không kéo dài bass của Olite.

Một bước, trên lưới nền của 3/4 và 6/8:

| Nhịp | Bass hiện tại | Bass sau sửa |
|---|---|---|
| 3/4 | 2 móc đơn, 1.0 phách, ở móc 0 | 3 móc đơn, 1.5 phách, vẫn một nhát ở móc 0 |
| 6/8 | 1 móc đơn, 0.5 phách, ở móc 0 | 2 móc đơn, 1.0 phách, ở móc 0 |

`_playable` thất bại thì giữ độ dài cũ. Không thêm nhát bass ở móc 4 của 3/4. Bass 6/8 không được phủ móc 3.

Không áp cho Olite. Sonatina cũng không. Bass của `_render_sonatina_moving` trên 3/4 và 6/8 giữ một móc đơn, 0.5 phách. Bước 1.0 lên 1.5 là giường Castillo và Juglar, không phải lưới đang hát móc đơn giữa ô. Nốt bass không bấm được cùng lead thì đổi sang nốt hợp âm khác, hoặc bỏ. Không kéo dài để giả độ dày.

Từng điệu một:

| Điệu | Bass được kéo |
|---|---|
| Castillo lưới 3/4, Juglar | Nhát ở móc 0 |
| Fandanguillo | Chỉ ô hợp âm khối, `not _fandanguillo_rolls_bar`, kéo bass móc 0. Ô đầu câu có quạt rasgueado giữ đúng 0.5 phách: `voice 3` có thể là hai nốt bass, và `assert_playable` cấm hai bass khi đã ra khỏi cửa sổ quạt. Không sửa test `beat + duration == 0.5` của cú quạt |
| Danza | Nhát bass trong `_block(..., staccato=True)` ở móc 0, và ở móc 3 trên 6/8. Bỏ `staccato` trên riêng nốt bass. Lead và support giữ staccato |
| Alcaniz mềm và Alcaniz mở | Nhát bass ở móc 0 |
| Alcaniz điệu, `_alcaniz_dance` | Không có bass ở móc 0. Lead ở móc 0 và móc 3, bass đáp ở móc 1 và móc 4, mỗi nhát 0.5 phách. Kéo hai nhát đáp đó lên 1.0 phách. Chúng dừng trước móc 3 và trước vạch ô. Không dời bass về móc 0 |

Bass mới ngân đè lên móc mà `_gap_inner` đang coi là một nốt đơn. `_gap_inner` và bước đặt bass dài hơn phải `_playable` cùng lead và support còn ngân trong cửa sổ đó. Không vừa thì giữ độ dài cũ.

Ô lưới nền đang có `support` rỗng thì thêm một nốt bè trung:

| Ô | Móc | Lead đưa vào hàm |
|---|---|---|
| Juglar, 3/4 | 2 | Lead đang vang ở móc đó, `_torroba_inner` |
| Alcaniz mềm, 6/8 | 2 | Lead móc 0 đang ngân cả 1.5 phách, `_torroba_inner` với cao độ đó |
| Alcaniz điệu, 6/8 | 2 | Lead nghỉ ở móc 2. Lấy cao độ lead của móc 0, gọi `_torroba_inner`, và `_playable` với bass móc 1 đang ngân. `_gap_inner` chỉ khi không có bass đang ngân |

Ô đã có support thì không thêm. Không thêm support cho Olite. `_torroba_inner` trả `None` thì không viết nốt đó.

---

## 7. Trần chương đầu là 63

`PROFILES` trong `guitar_wave.py` không sửa cho chương khác. Hàng hát (`castillo`, `sonatina`, `torroba_tremolo`) giữ `floor_calm = floor_wide = 34` và `d_lo = -8`, `d_hi = 8`.

Số 24 đo trên SSI 1M chương I là velocity cửa intro và outro (`OUTRO_END` 23, `SPEECH` 22), không phải `v_floor`. Không gán `floor_calm = 24`. Làm vậy kéo `c_lo` của thân bài xuống khoảng 10 bậc.

Chỉ chương đầu của một span, tức movement index 0 trong tuple `prepare_*` trả về, nâng `ceil_calm` và `ceil_wide` của hàng hát từ 58 lên 63. `d_hi` giữ 8, nên đỉnh viết 72 chạm 63. 1D và 1W là một chương, index 0, cùng trần này. Trên 1Y, index 0 là tháng đầu tiên còn đủ nến, không phải tháng một của lịch.

`_Ctx` chưa có movement index. `render()` nhận thêm chỉ số này từ chỗ đã biết nó (`audio.py` và đường 1D), ghi vào ctx, và `apply_guitar_wave` đọc lúc chọn trần. Chương index 1 trở đi giữ trần 58 của hàng hát và trần 63 cùng snap của hàng điệu.
