# Torroba: cửa 3/4 và 6/8, bè trung, và trần chương I

> **Trạng thái**: đã nghe SSI 1M, Guitar, Torroba, trên PR 111. Đã khóa. Chờ code.
> **Đọc cùng**: [`docs/sonify-guitar-torroba-note-surface.md`](./sonify-guitar-torroba-note-surface.md), [`docs/sonify-guitar-torroba-castillos-frames.md`](./sonify-guitar-torroba-castillos-frames.md) mục 3, [`docs/sonify-guitar-torroba-dynamics.md`](./sonify-guitar-torroba-dynamics.md) mục 2.
> **Thay cho**: câu «Giữ khung `_guitar_meter`, không đổi nhịp riêng của Torroba» và mặt 2+2 «một ô 4/4 là hai ô 2/4» trong bản mặt nốt, ở những pattern vốn là 3/4 hoặc 6/8.
> **Giữ**: `_guitar_meter` của Bach, Barrios, Villa, Brouwer, Classic. Không thêm id pattern. `_shape_dynamics` và `apply_guitar_wave` vẫn là đường dynamics. Không nâng dynamics bằng chênh velocity giữa các nốt trong một ô.

Bốn việc:

1. Pattern và figure đang khóa cửa ở 4/4 hoặc 2/4 phải được xem lại. Cái nào vốn là 3/4 hoặc 6/8 mà đang viết và ép sang nhịp khác thì sửa, để nó chạy đúng nhịp và đi được cửa 3/4 hoặc 6/8 đã có.
2. Một nửa số câu lưới thường, câu không nằm trong `torroba_figure_plan`, hát giai điệu thấp hơn khoảng một quãng 5. Bass vẫn ở bè trầm.
3. Chương mà bass và bè trung đang mờ thì dày thêm một chút. Bè cao vẫn là tuyến chính.
4. Chương I được nới biên độ nghe được từ 24–58 lên 24–63.

---

## 1. Cửa nhịp

Engine có `METER_34` và `METER_68`. Không có nhịp 2/4 và không có nhịp 3/8. Một ô 3/8 của nguồn được viết thành một nửa ô 6/8, như Alcaniz. Hai ô 2/4 ghép thành một ô 4/4 chỉ đúng với nguồn vốn là 2/4.

`_guitar_meter` để nguyên cho mọi ensemble guitar. Torroba không đi nhờ việc đổi hàm đó. Một chương Torroba đang 4/4 không tự thành 3/4. Pattern phải tự đứng ở cửa đúng của nó.

Dấu hiệu một pattern đang đứng sai nhịp là `_downbeat_only`: một nốt lead và một bass ở móc 0, các móc còn lại nghỉ. Hàm đó là lối thoát khi `kind` không phải nhịp của pattern. Nó không phải một lưới thứ ba.

### 1.1. Cửa đã đúng

Các cửa này giữ. Không viết thêm một lưới 4/4 cho chúng.

| Pattern | Nguồn đã ghi | Cửa trong code |
|---|---|---|
| `torroba_tremolo` (Juglar) | *Simancas*, 3/4 | `_render_juglar_bar` chỉ hát bộ ba khi `kind == "3/4"` |
| `alcaniz` | *Alcañiz*, 3/8, viết trên 6/8 | `_render_alcaniz_bar` chỉ hát khi `kind == "6/8"`. Ô mở đầu cũng đòi `kind == "6/8"` |
| `danza`, kiểu 6 | *Suite Castellana* III, nhóm ba của 3/4 và 6/8 | `_danza_spans` trả về rỗng khi `kind` không thuộc `{"3/4", "6/8"}` |
| `fandanguillo` trên 3/4 và 6/8, kiểu 5 và kiểu 2 | *Suite Castellana* I | Lưới 3/4 và 6/8 trong kế hoạch pattern |

### 1.2. Phải xem lại vì chỉ mở ở 4/4 hoặc 2/4

| Chỗ | Cửa hiện tại | Việc |
|---|---|---|
| `olite` | `_render_olite_bar` trả `_downbeat_only` khi `kind != "4/4"`. Bảng A chỉ chọn Olite ở hàng 4/4 `rally` và `volatile` | Nguồn là *Olite*, Vivace, **2/4**. Đây là pattern 2/4 duy nhất đã ghi. Xem lại vì cửa chỉ mở trên 4/4. Không bịa một lưới 3/4 hoặc 6/8 cho Olite trong đợt này. Chương nào rời 4/4 thì không còn chọn Olite |
| Mặt 2+2 của `castillo`, `_type7_bar1`, `_type3_sustain`, `sonatina`, `_olite_thin` khi `bpm > 72` và `kind == "4/4"` | Một ô 4/4 bị viết thành hai ô 2/4, phách mạnh ở móc 0 và móc 4 | Đây là cách ép. Kiểu 7 đã có nhánh 3/4 và 6/8 (`resolution="quarter"` trong `_type7_bar1`, và nửa sau `_type7_bar4`). Nhánh `resolution="dotted"` và `resolution="half"` chỉ phục vụ 4/4 |

### 1.3. Vốn là 3/4 hoặc 6/8 nhưng đang bị ép

Sửa những chỗ này. Sau khi sửa, pattern đó phải được `_torroba_primary` hoặc `_torroba_contrast` chọn trên đúng hàng 3/4 hoặc 6/8, và renderer không rơi `_downbeat_only`.

- **`castillo` và kiểu 7, kiểu 8.** *Castillos* chậm và *Arada* hát trên 3/4. `_castillo_spans` hiện không đọc `kind`, nên kiểu 7 và 8 cũng rơi vào chương 4/4. `_type7_bar4` khi `kind == "4/4"` chạy hai nửa `_type7_half`. Trên 3/4 và 6/8 nó giữ một chu kỳ rồi một nốt đen. Chương 4/4 đang hát Castillo phải về cửa 3/4 và dùng nhánh đã viết cho 3/4, không dùng mặt hai nửa 2/4.
- **`sonatina` và kiểu 1, 2, 3, 4.** Bảng hiện tại chỉ chọn Sonatina ở ô 4/4 `calm`, và làm B của Olite trên 4/4 (`_torroba_contrast`). Nguồn đã ghi là *Sonatina* chương I, chương III, còn Andante nằm ở `castillo`. Pattern này không có cửa 3/4 và không có cửa 6/8. Chương của Sonatina vốn 3/4 đi cửa 3/4. Chương vốn 3/8 đi cửa 6/8, cùng cách Alcaniz đã viết một nhóm ba móc. Không giữ Sonatina như một pattern chỉ sống trên 4/4.
- **Lưới `fandanguillo` 4/4** trong kế hoạch pattern: hợp âm dải ở móc 0, giai điệu ở móc 2, 4 và 6. Nguồn là điệu 3/4 và 6/8. Lưới 4/4 đó là bản ép. Fandanguillo chạy lưới 3/4 hoặc 6/8 đã có, và bảng mood của hai nhịp đó phải gọi được nó. Hàng 4/4 không còn là chỗ đứng của Fandanguillo.

`_torroba_primary` khi `kind` lạ đang lấy hàng 4/4. Sau đợt này một chương Torroba chỉ còn `3/4` hoặc `6/8`, nên lối rơi về hàng 4/4 không còn được dùng cho Torroba.

### 1.4. Chương suite

Các chương guitar sau đây đang 4/4 vì `_fast` và `_finale` giữ `METER_44`, và vì ngày cùng tuần không đi qua `_guitar_meter`:

| Span | Chương đang 4/4 |
|---|---|
| 1D | cả bài, 96 |
| 1W | cả tuần, 90 |
| 1M | I ở 96, IV ở 96 |
| 3M | I ở 96, III ở 108 |
| 1Y | chương 1, 4, 7, 10 ở 100, chương 12 ở 96 |

Chỉ bản Torroba của các chương đó đổi nhịp. Nhịp mới là nhịp của pattern mà chương đó hát: cửa 3/4 hoặc cửa 6/8 ở mục 1.1 và 1.3. Tempo của chương giữ nguyên. Ensemble khác vẫn nhận đúng form guitar hiện tại.

SSI 1M vừa nghe, trước khi đổi cửa:

| Chương | Nay | Điệu | Sau khi về đúng cửa |
|---|---|---|---|
| I, calm, 96 | 4/4 | Sonatina — Castillo — Sonatina | Hàng 3/4 hoặc 6/8 của chính hai pattern đó, không còn mặt 2+2 |
| II, selloff, 72 | 3/4 | Castillo — Danza — Castillo | Giữ. Đây đã là cửa 3/4 |
| III, selloff, 120 | 6/8 | Fandanguillo — Danza — Fandanguillo | Giữ. Đây đã là cửa 6/8 |
| IV, volatile, 96 | 4/4 | Olite — Sonatina — Olite | Olite là nguồn 2/4, không được gán sang 3/4 hoặc 6/8. Chương này hát pattern 3/4 hoặc 6/8 của mood `volatile` (`danza` trên 3/4, `fandanguillo` trên 6/8) |

---

## 2. Một nửa câu lưới thường hát thấp hơn một quãng 5

Ô figure giữ giai điệu bè cao. «Ngoài danh sách figure» là ô thân bài không có trong `torroba_figure_plan`.

Đơn vị là câu, không phải từng ô xen kẽ. Trong các câu thân mà mọi ô đều ở lưới nền, một nửa số câu hạ giai điệu khoảng 7 bán cung, vào bè trung. Câu kế giữ bè cao. Câu figure không vào lượt này.

Bass vẫn là bè trầm, dưới giai điệu đã hạ. Giai điệu hạ không được chạm bass. Trên SSI 1M, số ô thân ngoài figure là 4, 37, 60 và 20. Chương I gần kín figure, nên câu hát thấp nghe rõ ở chương II và III.

---

## 3. Dày thêm một chút

SSI 1M, tổng độ dài nốt có tiếng, tính bằng phách:

| Chương | Lead | Support | Bass |
|---|---|---|---|
| I | 376 | 72 | 172 |
| II | 280 | 113 | 164 |
| III | 201 | 116 | 126 |
| IV | 373 | 48 | 314 |

Chương IV rõ vì bass ngân khoảng 1,7 phách mỗi nhát. Support của chương đó lại thưa nhất. Tiếng đệm nghe được ở chương IV là bass bấm đang ngân, không phải một bè trung dày.

Chương I, II và III dày thêm một mức: bass ngân dài hơn một chút, và ô lưới thường đang chỉ có bè cao thì thêm một nốt bè trung. Không kéo ba chương đó lên bằng 314 phách bass của chương IV. Không nâng velocity để giả độ dày. Bè cao vẫn là giai điệu.

---

## 4. Trần chương I là 63

`_shape_dynamics` vẫn chạy. Bảy pattern Torroba vẫn nằm trong `_WHOLE_BAR_EXTRA`, nên cả ô cộng một extra `0..+4`. `apply_guitar_wave` vẫn chạy sau đó. PR 111 không sửa hai chỗ này và không sửa `PROFILES`.

Trên SSI 1M chương I, trung vị velocity giai điệu theo ô đo được **24–58**. Trần 58 là `ceil_calm = ceil_wide = 58` của hàng hát (`castillo`, `sonatina`, `torroba_tremolo`). Đỉnh câu chạm trần rồi bị kẹp.

Chương I, movement index 0 của mọi span Torroba, được nới thành **24–63**. Đáy 24 giữ. Trần hàng hát trong chương đó từ 58 lên 63, cùng trần đã khóa cho hàng điệu. Chương II trở đi giữ trần 58 của hàng hát và trần 63 cùng snap của hàng điệu. Không thêm bậc vi mô trong texture để tạo cảm giác sôi hơn. Nốt ngắn hơn nửa phách vẫn đứng ngoài `apply_torroba_sung_arch`, vì `_sung_attack` đòi `duration_beats >= 0.5`.
