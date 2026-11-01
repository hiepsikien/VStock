# Torroba: cửa nhịp gốc, bè trung, và trần chương đầu

> **Trạng thái**: đã nghe SSI 1M trên PR 111, đã đối chiếu nguồn và code. Đã khóa. Chờ code.
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
| `castillo` | *Torija* và các *Castillos* chậm | 3/4 | 3/4. Không gọi kiểu 7, kiểu 8 |
| `castillo` khi là Arada | *Suite Castellana* II, *Arada*, Lento | 4/4, hai nửa ô | 4/4. Kiểu 7 và kiểu 8 chỉ ở đây |
| `fandanguillo` | *Suite Castellana* I | 3/4 và 6/8 | Bỏ tuple `(2, 4, 6)` của `_fandanguillo_melody`. Hàm chỉ trả `(2, 3)` trên 6/8 và `(2, 4)` trên 3/4 |
| `danza` | *Suite Castellana* III | 3/4 và 6/8 | Giữ. `_danza_spans` tiếp tục trả rỗng ngoài hai nhịp này |
| `torroba_tremolo` | *Simancas*, Juglar | 3/4 | Giữ. Ngoài 3/4 vẫn là `_downbeat_only` |
| `alcaniz` | *Alcañiz*, 3/8 | 6/8 | Giữ. Ngoài 6/8 vẫn là `_downbeat_only` |
| `olite` | *Olite*, Vivace, nốt đen = 95 | 2/4 | Giữ 4/4. `_render_olite_bar` tiếp tục đòi `kind == "4/4"`. Đây không phải bản ép |

Mặt 2+2 ở `bpm > 72` trên `castillo`, `_type7_bar1` (`resolution="dotted"`), và `_type3_sustain` là cách ép một điệu 3/4 hoặc một Lento 4/4 vào hai ô 2/4. Bỏ nhánh `dotted`. Arada trên 4/4 dùng `resolution="half"` ở mọi BPM, kể cả 96. `_type7_bar4` trên 4/4 giữ hai nửa `_type7_half`.

---

## 2. Chương nào giữ 4/4

`_guitar_meter` không đổi. Nhịp Torroba được quyết định khi dựng `PreparedMovement`, trước `render()`, vì `scale_fingerprint` băm `meter.beats` và `meter.beat_type`. Đổi meter bên trong `render()` sau khi fingerprint đã tính sẽ làm cache và `piece_seconds` lệch khỏi ô nhạc.

`prepare_month`, `prepare_quarter`, và `prepare_year` hiện chỉ nhận `variant`. `prepare_week` không nhận `variant` lẫn `ensemble`. `plan_span` trong `backend/app/services/spans.py` phải truyền `ensemble` vào bốn hàm đó. Chỉ khi `variant == "guitar"` và `ensemble == "torroba"` thì áp bảng dưới. Ensemble khác nhận đúng spec guitar hiện tại.

1D không đi qua `prepare_*`. `render.py` gán `DAILY_ENSEMBLE_SPEC`, đang là 4/4. Bản copy cho Torroba đổi meter của spec đó trước khi soạn, cùng bảng character.

Chương guitar đã là 3/4 hoặc 6/8 thì giữ. Chương guitar đang 4/4 thì:

| Character | Nhịp Torroba | A | B |
|---|---|---|---|
| `rally` | 4/4 | `olite` | `castillo`, chỉ Arada |
| `volatile` | 4/4 | `olite` | `castillo`, chỉ Arada |
| `calm` | 3/4 | `sonatina` | `castillo` lưới 3/4, không kiểu 7 và 8 |
| `selloff` | 3/4 | `castillo` lưới 3/4 | `danza` |

`_torroba_contrast` trên 4/4 khi primary là `olite` trả `castillo`, không trả `sonatina`. Hàng 4/4 của `_torroba_primary` chỉ còn `olite` cho `rally` và `volatile`. Ô `calm` và `selloff` của hàng 4/4 không còn được chọn, vì hai character đó đã sang 3/4 trước lúc chọn pattern.

SSI 1M sau bảng này:

| Chương | Character | Nhịp | Điệu |
|---|---|---|---|
| I | calm | 3/4 | Sonatina — Castillo — Sonatina |
| II | selloff | 3/4 | Castillo — Danza — Castillo, giữ |
| III | selloff | 6/8 | Fandanguillo — Danza — Fandanguillo, giữ |
| IV | volatile | 4/4 | Olite — Castillo — Olite. Castillo ở đây là Arada |

---

## 3. Arada rời nhóm 3/4 và 6/8

Kiểu 7 và kiểu 8 là *Arada*, nhịp gốc 4/4. `_castillo_spans` hiện không đọc `kind`, nên hai kiểu này đang hát trên Castillo 3/4. Sửa: `kind` không phải `4/4` thì `_castillo_spans` trả `[]`. Castillo 3/4 hát lưới nền của 3/4, không hát Arada.

Trên 4/4, Arada không dùng mặt nhanh `bpm > 72`. `_type7_bar1` luôn `resolution="half"`.

---

## 4. Sonatina trên 6/8

*Sonatina* III là 3/8. Bảng mood 6/8 hiện không có ô nào trả `sonatina`: calm là `danza`, rally là `alcaniz`, volatile và selloff là `fandanguillo`. Ba ô đó là đúng nguồn, không nhường cho Sonatina.

Đợt này không thêm ô mood 6/8 cho `sonatina`, và không viết lưới mới. `_render_sonatina_bar` khi `kind == "6/8"` đang rơi nhánh phách mạnh cũ. Nhánh đó không phải chương III. Vì bảng không chọn `sonatina` trên 6/8, nhánh đó không được gọi. Đừng coi nó là cửa 6/8 của Sonatina.

Sonatina I và II đi cửa 3/4 qua `_render_sonatina_moving`.

---

## 5. Một nửa đoạn lưới nền hát thấp một quãng 5

Giai điệu hạ vẫn là `voice 1`. Không chuyển sang `voice 2`. `apply_torroba_sung_arch` chỉ nhận nốt lead. Voice 1 trống thì câu đó mất vòng cung.

PR 111 cho hầu hết câu `castillo` và `sonatina` có `L >= 2` ít nhất một span trong `torroba_figure_plan`. Điều kiện «cả câu không có ô figure» gần như không bao giờ đúng trên hai pattern đó. Không viết `if any(bar in plan)`.

Đơn vị là một đoạn lưới nền: dãy ô thân bài liên tiếp, cùng một câu, vắng mặt trong `torroba_figure_plan`. Đoạn thứ 1, 3, 5… của chương hạ giai điệu. Đoạn chẵn giữ bè cao. Ô figure giữ bè cao.

Cao độ không phải `midi - 7`. Hạ bốn bậc thang bằng `_scale_degree_below(midi, 4, ctx.mode)`. Trong docstring của hàm đó, hai bậc là một quãng 3, nên bốn bậc là một quãng 5 đúng điệu thức. Trên phách mạnh, nếu nốt đó không thuộc hợp âm, lấy nốt hợp âm gần nó nhất mà vẫn không cao hơn nốt thang vừa hạ.

Sàn là `max(bass + 3, 55 - ctx.semitones)` khi có bass, nếu không thì `55 - ctx.semitones`. Nốt thang nằm dưới sàn thì lấy nốt thang tại hoặc ngay trên sàn. Nốt đó vẫn chạm bass thì nốt này không hạ.

Khi lead đã hạ có cao độ vang `<= 62`, support dưới nốt đó nghỉ. `_torroba_inner` không bị ép vào một quãng hẹp giữa bass và lead. Bass giữ bè trầm.

---

## 6. Dày thêm một bước

Chương IV của SSI dày vì Olite ngân bass khoảng 1,7 phách. Không kéo các chương kia lên mức đó, và không kéo dài bass của Olite.

Một bước, trên lưới nền của 3/4 và 6/8:

| Nhịp | Bass hiện tại | Bass sau sửa |
|---|---|---|
| 3/4 | 2 móc đơn, 1.0 phách, ở móc 0 | 3 móc đơn, 1.5 phách, vẫn một nhát ở móc 0 |
| 6/8 | 1 móc đơn, 0.5 phách, ở móc 0 | 2 móc đơn, 1.0 phách, ở móc 0 |

`_playable` thất bại thì giữ độ dài cũ. Không thêm nhát bass ở móc 4 của 3/4. Bass 6/8 không được phủ móc 3.

Áp cho bass móc 0 của `castillo` lưới 3/4, Juglar, Fandanguillo, Danza, và Alcaniz. Không áp cho Olite.

Ô lưới nền đang có `support` rỗng thì thêm một nốt bè trung, nếu `_torroba_inner` trả được một nốt:

| Ô | Móc của nốt mới |
|---|---|
| Juglar, 3/4 | 2 |
| Alcaniz điệu và Alcaniz mềm, 6/8 | 2 |

Ô đã có support thì không thêm. Không thêm support cho Olite.

---

## 7. Trần chương đầu là 63

`PROFILES` trong `guitar_wave.py` không sửa cho chương khác. Hàng hát (`castillo`, `sonatina`, `torroba_tremolo`) giữ `floor_calm = floor_wide = 34` và `d_lo = -8`, `d_hi = 8`.

Số 24 đo trên SSI 1M chương I là velocity cửa intro và outro (`OUTRO_END` 23, `SPEECH` 22), không phải `v_floor`. Không gán `floor_calm = 24`. Làm vậy kéo `c_lo` của thân bài xuống khoảng 10 bậc.

Chỉ chương đầu của một span, tức movement index 0 trong tuple `prepare_*` trả về, nâng `ceil_calm` và `ceil_wide` của hàng hát từ 58 lên 63. `d_hi` giữ 8, nên đỉnh viết 72 chạm 63. 1D và 1W là một chương, index 0, cùng trần này. Trên 1Y, index 0 là tháng đầu tiên còn đủ nến, không phải tháng một của lịch.

`_Ctx` chưa có movement index. `render()` nhận thêm chỉ số này từ chỗ đã biết nó (`audio.py` và đường 1D), ghi vào ctx, và `apply_guitar_wave` đọc lúc chọn trần. Chương index 1 trở đi giữ trần 58 của hàng hát và trần 63 cùng snap của hàng điệu.
