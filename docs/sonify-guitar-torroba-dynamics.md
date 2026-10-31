# Torroba: thủy triều volume, bass, và La♭ áp Sol

> **Trạng thái**: chưa vào code.
> **Đọc cùng**: [`docs/sonify-guitar-dynamics-wave-plan.md`](./sonify-guitar-dynamics-wave-plan.md) mục 2 và 5, [`docs/sonify-guitar-torroba-plan.md`](./sonify-guitar-torroba-plan.md) mục vận tốc trong ô và mục scale chung.
> **Giữ**: `_shape_dynamics` vẫn chỉ cộng extra của câu. Trần ấm `63`. Một tâm `C` cho cả ô. Bass không vào lớp móng. Không thêm id pattern. Passage giữ tập nốt thứ tự nhiên. Không thêm Rê♭, không thêm Si.

Torroba là hàng điệu, độ động cao. Sóng volume hiện xếp Castillo vào câu ngân và Sonatina vào câu chạy, rồi để tâm ô chỉ đi được 3–4 bậc. Bass một phách viết quanh `60` nên nghe trong khoảng `38–51`. Plan này đưa cả bảy hàng về chu kỳ `W = 3`, nới thủy triều bằng dự trữ riêng của Torroba, và chốt range vận tốc nghe được. Phần scale giữ thang hiện có. Việc còn lại là La♭ chỉ áp khi đích là Sol, và nét chạy ngắn của Castillo, Sonatina đi cùng bước đó.

---

## 1. Hiện trạng

`_shape_dynamics` vẫn chạy trên Torroba. Hàm đó không đọc volume. Câu có `phrase.rise > 0` được cộng `extra = round(4 * swell)`, tức `0..+4`. Bảy pattern Torroba nằm trong `_WHOLE_BAR_EXTRA`, nên cả ô lấy một extra tại phách mở. Lead, bass và bè trung cùng nhận số đó. Câu phẳng, phần lớn Castillo, cộng `0`. Nốt harmonic viết `48` không cộng extra. Khoảng trong ô sống sót. Extra không tạo độ động cho bass.

Volume đi qua `apply_guitar_wave`. `smooth_ell` lấy trung bình `W` điểm của `ln(1 + v)` trên từng khúc cùng hàng sóng. Tâm ô là `round(C) + (vận tốc viết − 64)`, rồi kẹp `min(v_ceil, raw)` với `v_ceil ≤ 63`. Với `d_lo = -16` và `d_hi = 8`, cửa sổ rộng khoảng 28 bậc chỉ còn thủy triều `3–4` bậc, vì `24` bậc bị giữ để lệch đã viết không bị nuốt.

`W` và cửa sổ đang khóa trong `PROFILES`:

| Pattern | Cửa sổ calm → wide | `W` | Tâm `C` calm / wide | Bass `mf` viết `60` |
|---|---|---|---|---|
| `castillo` | `26..54` → `30..58` | 9 | `42–46` / `46–50` | `38–42` / `42–46` |
| `sonatina`, `torroba_tremolo` | `30..58` → `34..62` | 5 | `46–50` / `50–54` | `42–46` / `46–50` |
| `fandanguillo`, `danza`, `alcaniz`, `olite` | `30..58` → `36..63` | 3 | `46–50` / `52–55` | `42–46` / `48–51` |

`castillos_wave_row` cho Juglar ở hàng tremolo. Alcaniz thưa và Olite không ở lưới đầy mượn hàng Castillo, nên các ô đó cũng `W = 9` và cửa sổ `26..54`. Contrast A–B–A không có bridge chỉ dài 8 ô. Cửa sổ 9 ô phản chiếu hai đầu và gần như san phẳng đoạn đó.

Castillo không có móng: `snap_wide` là `None`, và `_is_target` không có nhánh `castillo`. Các hàng kia chỉ móng lead có `accent`, một nốt mỗi câu. `alpha_price < 0.25` thì ngân sách móng bằng 0. Bass không bao giờ vào lớp đó.

Bass phách mạnh là `_under_lead`. Band `mf` viết `60`, `f` viết `64`, `mp` viết `58`, `p` viết `54`. Phách yếu thấp hơn phách mạnh `4`, sàn `40`. Sau sóng, bass `mf` của Castillo nằm `38–46`. Nốt chỉ dài một phách. Trên nylon, mức đó gần như mất.

Bước `|round(C) − round(C ô trước)| ≤ 4` vẫn đúng. Thủy triều 4 bậc thì một ô đã đi hết quãng, nhưng quãng đó quá hẹp để nghe là độ động.

---

## 2. Chu kỳ

Cả bảy hàng Torroba dùng `W = 3`, cùng loại điệu trong plan sóng (gigue, galop, choro, polca, vals, tresillo, etude Brouwer). Ô đang mượn Castillo đi theo hàng Castillo mới, không cần một hàng nhẹ riêng.

`W = 3` để đỉnh volume đứng gần ô có volume thô, và đoạn contrast 8 ô còn một hình. Nó không nới quãng tâm. Quãng nằm ở mục 3.

---

## 3. Cửa sổ và range

Giữ `WARM_LIMIT = 63` và công thức tâm. Chỉ bảy profile Torroba đổi dự trữ và cửa sổ:

| Trường | Hiện tại | Plan |
|---|---|---|
| `floor_calm`, `floor_wide` | theo bảng mục 1 | `40`, `40` |
| `ceil_calm`, `ceil_wide` | theo bảng mục 1 | `63`, `63` |
| `d_lo`, `d_hi` | `-16`, `8` | `-8`, `4` |
| `smooth` | `9` / `5` / `3` | `3` |

Sàn và trần không đổi theo `alpha_warm`. Bridge và trio vẫn nhân `0.5` vào alpha, nhưng cửa sổ hai đầu bằng nhau nên đoạn B không bị kéo về cửa sổ nhẹ. Độ động của đoạn B nằm ở `U` và ở pattern, không ở việc hạ trần.

`span = 23`, nên `M = 23/24`. Tâm chạy `47.67 → 59.17`. `round` hai đầu là `48` và `59`. Thủy triều khoảng `11.5` bậc. Bước giữa hai ô vẫn không quá `4`, nên hết quãng mất khoảng ba ô.

Vận tốc viết không đổi. Bảng dưới là nốt `mf` sau sóng, chưa móng, tại hai đầu thủy triều:

| Bè | Viết | Đáy, `C = 48` | Đỉnh, `C = 59` |
|---|---|---|---|
| Lead thường | `64` | 48 | 59 |
| Lead đỉnh câu | `72` | 56 | 63 |
| Bass phách mạnh | `60` | 44 | 55 |
| Bass phách yếu | `56` | 40 | 51 |
| Bè trung | `56` | 40 | 51 |

Lead đỉnh viết `72` ở đỉnh sóng ra `67` rồi kẹp `63`. Extra `+4` của câu đang lên dịch cả ô lên trước khi vào sóng. Bass `60` có extra thành viết `64`, nghe `48–59`. Câu phẳng không có extra.

Band khác, bass phách mạnh, cùng hai đầu:

| Band | Viết | Đáy | Đỉnh |
|---|---|---|---|
| `p` | `54` | 38 | 49 |
| `mp` | `58` | 42 | 53 |
| `mf` | `60` | 44 | 55 |
| `f` | `64` | 48 | 59 |

Range cần nghe trên thân bài: lead `48–63`, bass mạnh `44–55`, bass yếu và bè trung `40–51`. Móng nằm ngoài cửa sổ này.

`d_lo = -8` giữ được bass viết `56` và lead viết `64`. Nốt viết thấp hơn `56` ở đáy có thể ngồi dưới sàn `40`. Harmonic `48` ở đáy ra `32`. Plan sóng vốn cho nốt viết `48` chạm sàn nhờ `C_lo = sàn + 16`. Hàng Torroba không giữ bất biến đó. Harmonic vẫn viết `48` và không cộng extra. Nó được phép nhỏ hơn sàn.

---

## 4. Móng

Móng vẫn chỉ là lead có `accent`, sau bước kẹp trần ấm, một nốt mỗi câu. Bass và bè trung không vào.

| Pattern | `snap_calm` / `snap_wide` | Mỗi câu / mỗi đoạn |
|---|---|---|
| `castillo` | `66` / `70` | `1` / `2` |
| `sonatina`, `torroba_tremolo` | `66` / `68` | `1` / `2` |
| `fandanguillo`, `danza`, `alcaniz`, `olite` | `70` / `74` | `1` / `3` |

`_is_target` thêm `castillo` vào cùng cửa lead có `accent` với Sonatina. Không có dòng đó thì `snap_wide` của Castillo không bao giờ được chọn. `alpha_price < 0.25` vẫn tắt ngân sách, trừ đường riêng của `elogio_pizz`. Phiên phẳng không có móng. Độ nảy của phiên đó là thủy triều và khoảng đã viết trong ô.

---

## 5. Khi vào code

- `PROFILES` trong `backend/app/sonify/guitar_wave.py`: bảy khóa `torroba` theo mục 3 và 4. `d_lo`, `d_hi` đặt trên từng profile, không đổi mặc định toàn cục.
- `_is_target`: nhận `castillo` khi `voice == "lead"` và `event.accent`.
- `backend/tests/test_guitar_wave.py`: bảng cửa sổ Torroba. Thêm một test thủy triều: sàn `40`, trần `63`, `d_lo = -8`, `d_hi = 4`, hai đầu `round(C)` là `48` và `59`, bass viết `60` ra `44` và `55`.
- `backend/tests/test_sonify_guitar_torroba.py`: Castillo có snap `66/70`. Điệu có snap `70/74`. `_is_target` của Castillo chọn lead có accent và bỏ bass.
- `SPAN_REVISION` tăng một bậc khi sóng đổi, để file nghe cũ không bị phát lại.

`_shape_dynamics`, `_under_lead`, độ dài bass một phách, và `WARM_LIMIT` không sửa trong đợt này.

---

## 6. La♭ áp Sol

Passage Torroba đã chạy trong pipeline chung. `detect_price_impulses` và `apply_scale_passages` không loại ensemble này. Bảy pattern đã có hàng hairpin: Castillo, Sonatina, Juglar ở nhóm Hát, cùng Cantabile, hàng `(4, 16, 76)`, cửa sổ `52–82`. Fandanguillo, Danza, Alcaniz, Olite ở nhóm động, cùng Polca, hàng `(4, 18, 76)`, cửa sổ `46–90`. Chúng không thuộc `_HOST`, nên không nhường cả ô. Dòng scale chỉ viết đè bè cao trên móc impulse đã chọn.

Tập nốt là thứ tự nhiên của Đô: `Đô Rê Mi♭ Fa Sol La♭ Si♭`. Đó cũng là Phrygian của Sol. La♭ là bậc 2 hạ của Sol. Không đổi sang Phrygian của Đô, vì Rê♭ lệch Rê trong hợp âm Si♭ và Sol. Không đổi sang Phrygian dominant, vì Si là cảm âm dẫn và scale step đang chặn Si♭ nâng thành Si. Si đã có trong hợp âm Sol. Vòng `Cm → Si♭ → La♭ → Sol` tiếp tục mang màu Andalucia. Passage không thêm một thang riêng.

`torroba_scale_step` đang đọc đối số thứ ba như một cao độ đích: hướng là `1` khi `toward > pitch`. `_trace_scale` truyền `+1` hoặc `-1`, cùng quy ước của `classic_scale_step`. Trên dây đàn, `+1` nhỏ hơn cao độ đang đứng, nên mọi nét passage đi lên bị bước xuống. `_trace_scale` bỏ bước đó và không dựng nét. Nét đi xuống vẫn chạy, vì `-1` tình cờ cùng hướng. `_scale_steps` của Olite và `_scale_away` của Alcaniz truyền cao độ thật, nên hai chỗ đó đi được cả hai chiều.

Cửa La♭ hiện không đọc đích của nét. Đang ở La, nửa cung kế là La♭ và nửa cung sau là Sol thì hàm trả La♭, kể cả khi nét còn đi tiếp qua Sol. Hợp âm ô đích không được hỏi.

`_approaches` vẫn gọi `_walk`. `_into_strong` dùng hàm đó cho nét 1 hoặc 3 nốt của `_render_sonatina_bar` và `apply_sonatina_downbeats`. Castillo và Sonatina vì vậy không có La♭ áp. Alcaniz và Olite đã gọi `torroba_scale_step`.

Việc cần làm:

1. `torroba_scale_step` đọc hướng như `classic_scale_step`: `toward >= 0` là đi lên, `toward < 0` là đi xuống. Giữ cửa không nâng Si♭ thành Si. `_scale_steps` và `_scale_away` truyền `1` hoặc `-1`, không truyền cao độ đích.
2. La♭ chỉ là nốt ngay trước đích. Đích của nét có pitch class 7, hoặc hợp âm ô đích là `G` hoặc `G7`, thì nốt áp được là La♭ khi nốt đó còn trong vùng chơi. Nét đi ngang La rồi xuống tiếp không chèn La♭. Chỗ biết đích là `_trace_scale` (`end`) và `_approaches` (`target`). Hợp âm là `ctx.chord` của ô đích.
3. `_approaches` bước bằng `torroba_scale_step`, rồi áp cửa La♭ ở trên. Một nốt và ba nốt của Castillo, Sonatina dùng chung cửa với passage.

`test_scale_step_may_be_ab_and_does_not_raise_bb` đang gọi `torroba_scale_step(ctx, 69, 67)`. Đổi lời gọi sang hướng. Khóa thêm: từ Sol, hướng `+1` trả một nốt cao hơn Sol. Nét có đích Sol vẫn áp La♭. Nét có đích khác Sol, đi ngang La, không áp. Si♭ không thành Si.
