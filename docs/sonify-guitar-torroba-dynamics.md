# Torroba: hai hàng sóng, cung câu hát, và La♭ áp Sol

> **Trạng thái**: đã vào code.
> **Đọc cùng**: [`docs/sonify-guitar-dynamics-wave-plan.md`](./sonify-guitar-dynamics-wave-plan.md) mục 2 và 5, [`docs/sonify-guitar-torroba-plan.md`](./sonify-guitar-torroba-plan.md) mục vận tốc trong ô và mục scale chung.
> **Giữ**: Trần ấm `63`. Một tâm `C` cho cả ô. Bass không vào lớp móng. Không thêm id pattern. Passage giữ tập nốt thứ tự nhiên. Không thêm Rê♭, không thêm Si. `_shape_dynamics` của ensemble khác không đổi.

Torroba sống bằng bậc thang: câu ngân giữ một mặt bằng, điệu bước vào sáng hơn. Sóng hiện tại để Castillo ở cửa sổ nhẹ, `W = 9`, và bass một phách `mf` nghe `38–42`. Một cửa sổ `40..63` cho cả bảy hàng làm bass lớn hơn nhưng xóa bậc đó, vì `U` min–max trong từng đoạn và `alpha_warm` không còn chỗ để mở. Plan này tách hàng hát và hàng điệu, giữ `d_hi = 8` để đỉnh câu không bị bóp, và sửa hướng scale trước khi nới sóng.

---

## 1. Hiện trạng

`_shape_dynamics` vẫn chạy trên Torroba. Hàm đó không đọc volume. Câu có `phrase.rise > 0` được cộng `extra = round(4 * swell)`, tức `0..+4`. Bảy pattern Torroba nằm trong `_WHOLE_BAR_EXTRA`, nên cả ô lấy một extra tại phách mở. Lead, bass và bè trung cùng nhận số đó. Câu phẳng, phần lớn Castillo, cộng `0`. Nốt harmonic viết `48` không cộng extra. Thủy triều không tạo hairpin khi volume của câu đứng yên.

Volume đi qua `apply_guitar_wave`. `smooth_ell` lấy trung bình `W` điểm của `ln(1 + v)` trên từng khúc cùng hàng sóng. Tâm ô là `round(C) + (vận tốc viết − 64)`, rồi kẹp `min(v_ceil, raw)` với `v_ceil ≤ 63`. Với `d_lo = -16` và `d_hi = 8`, cửa sổ rộng khoảng 28 bậc chỉ còn thủy triều `3–4` bậc.

`W` và cửa sổ đang khóa trong `PROFILES`:

| Pattern | Cửa sổ calm → wide | `W` | Tâm `C` calm / wide | Bass `mf` viết `60` |
|---|---|---|---|---|
| `castillo` | `26..54` → `30..58` | 9 | `42–46` / `46–50` | `38–42` / `42–46` |
| `sonatina`, `torroba_tremolo` | `30..58` → `34..62` | 5 | `46–50` / `50–54` | `42–46` / `46–50` |
| `fandanguillo`, `danza`, `alcaniz`, `olite` | `30..58` → `36..63` | 3 | `46–50` / `52–55` | `42–46` / `48–51` |

`castillos_wave_row` cho Juglar ở hàng tremolo. Alcaniz thưa và Olite không ở lưới đầy mượn hàng Castillo, nên các ô đó cũng `W = 9` và cửa sổ `26..54`. Contrast A–B–A không có bridge chỉ dài 8 ô. Nửa cửa sổ 9 ô dài bằng cả đoạn, nên đoạn đó gần như san phẳng. `W = 5` trên 8 ô vẫn còn hình.

Bass phách mạnh là `_under_lead`. Band `mf` viết `60`. Phách yếu thấp hơn `4`, sàn `40`. Sau sóng, bass `mf` của Castillo nằm `38–46`. Nốt chỉ dài một phách. Trên nylon, mức đó gần như mất.

Humanize chạy sau sóng. Nốt tới humanize từ `64` trở xuống ở lại từ `64` trở xuống. Nốt trên `64` của Torroba bị kẹp `69..73`. Móng viết `66` nghe thành `69`. Móng viết `74` nghe thành `73`.

`_budget` lấy `min(per_sec, max(1, floor(0.045 × số nốt lead)))`. Đoạn ngắn thường còn một móng. Nốt chỉ được xét khi `0.70 × U + 0.30 × breath ≥ 0.70`. `alpha_price < 0.25` thì ngân sách bằng 0, trừ `elogio_pizz`.

`_render_castillo_bar` gắn `accent=True` lên nốt hát đầu ô, kể cả harmonic viết `48`. `_is_target` theo accent sẽ đưa chuông vào lớp móng.

---

## 2. Hai hàng

Hát và điệu không dùng chung cửa sổ. `U` vẫn min–max trong từng đoạn. Cửa sổ của một hàng có hai đầu bằng nhau, nên `alpha_warm` và hệ số `0.5` của bridge không đổi độ lớn bên trong hàng đó. Đoạn B sáng hơn đoạn A vì nó đổi hàng, và vì rasgueado, không vì một thủy triều bị kéo giãn.

| Hàng | Pattern | `W` | Cửa sổ | `d_lo`, `d_hi` |
|---|---|---|---|---|
| Hát | `castillo`, `sonatina`, `torroba_tremolo` | 5 | `34..58` | `-8`, `8` |
| Điệu | `fandanguillo`, `danza`, `alcaniz`, `olite` | 3 | `40..63` | `-8`, `8` |

Ô thưa đang mượn Castillo đi theo hàng hát mới: `W = 5`, cửa sổ `34..58`. Hết cảnh 8 ô bị `W = 9` san phẳng.

`d_hi` giữ `8` ở cả hai hàng. Bản cửa sổ `40..63` với `d_hi = 4` đưa đỉnh viết `72` tới `67` rồi kẹp `63`, khoảng với lead thường từ `8` xuống `4`. `d_hi = 8` để khoảng đó còn `8`.

Giường bass `mf` của riêng Torroba nhấc `4`, từ `60` lên `64`. Phách yếu cũng nhấc `4`, vẫn thấp hơn phách mạnh `4`. `_under_lead` vẫn giữ lead cao hơn bass ít nhất `2`, và bass cao hơn bè trung ít nhất `2`. Khi nốt hát viết `64`, bass dừng ở `62`. Ensemble khác không nhấc giường này.

---

## 3. Số nghe được

Hát, `span = 24`, `M = 1`. Tâm đúng `42` và `50`.

| Bè | Viết | Đáy, `C = 42` | Đỉnh, `C = 50` |
|---|---|---|---|
| Lead thường | `64` | 42 | 50 |
| Lead đỉnh câu | `72` | 50 | 58 |
| Bass `mf` khi lead còn chỗ | `64` | 42 | 50 |
| Bass khi lead viết `64` | `62` | 40 | 48 |

`50 + 8 = 58`, sát trần. Đỉnh câu không bị kẹp bớt. Bass mạnh nghe `42–50` khi nốt hát đã nhô lên. Câu phẳng siết bass xuống `40–48`.

Điệu, `span = 23`, `M = 23/24`. Tâm `47.67 → 55.33`. `round` hai đầu là `48` và `55`.

| Bè | Viết | Đáy, `C = 48` | Đỉnh, `C = 55` |
|---|---|---|---|
| Lead thường | `64` | 48 | 55 |
| Lead đỉnh câu | `72` | 56 | 63 |
| Bass `mf` khi lead còn chỗ | `64` | 48 | 55 |
| Bass khi lead viết `64` | `62` | 46 | 53 |

`55 + 8 = 63`. Khoảng giữa lead thường và đỉnh câu là `8` ở cả hai đầu. Đỉnh bass là `55`, cùng mức bass viết `60` đạt được khi `d_hi = 4` và tâm đỉnh là `59`. Đáy bass là `48`, không phải `44`: nhấc số viết bù đúng phần `d_hi` lấy ở đỉnh, còn `C_lo` không hạ. Bước `|round(C) − round(C ô trước)| ≤ 4` vẫn đúng. Hàng điệu hết quãng khoảng hai ô. Hàng hát, thủy triều `8` bậc, hết quãng khoảng hai ô.

Nốt viết thấp hơn `56` ở đáy có thể ngồi dưới sàn. Harmonic `48` ở đáy hàng hát ra `26`, ở đáy hàng điệu ra `32`. Plan sóng vốn cho nốt `48` chạm sàn nhờ `C_lo = sàn + 16`. Hai hàng này không giữ bất biến đó. Harmonic vẫn viết `48`, không cộng extra, và không vào lớp móng.

---

## 4. Móng và tenuto

Móng chỉ thuộc hàng điệu. Hàng hát không có `snap_wide`. Castillo giữ nốt ngân.

| Hàng | `snap_calm` / `snap_wide` | Mỗi câu / trần đoạn |
|---|---|---|
| Hát | không | `0` / `0` |
| Điệu | `70` / `73` | `1` / `3` |

Công thức móng vẫn mở từ `66`. Humanize kéo `66–68` lên `69` và cắt trên `73`. Tiếng còn lại là `69–73`. Không ghi `66` hoặc `74`. `_is_target` của điệu vẫn là lead có `accent`, và loại nốt viết `48`. Bass và bè trung không vào. Trần đoạn `3` chỉ là mũ của `_budget`. Đoạn contrast ngắn thường còn một móng.

Nhấn của câu hát là tenuto trong cửa sổ, viết trước sóng, khoảng `+4..+6` trên nốt hát so với các nốt hát quanh nó. Bass không được cộng cùng số đó. Sau sóng nốt này vẫn từ `63` trở xuống, nên humanize không kéo nó vào `69`.

---

## 5. Cung trong câu hát

Câu phẳng đang cộng extra `0`. Thêm một vòng viết riêng trên bè hát của `castillo`, `sonatina` và `torroba_tremolo`, trước sóng. Nốt đi lên về phía trước nốt đỉnh. Nốt chạm thì thả. Cả cung rộng `6–8` bậc, và không vượt `72` khi nốt thường viết `64`, để không chồng thêm một lần nữa lên tenuto. Affine giữ nguyên khoảng trong ô. Đây là độ động của câu ngân. `_shape_dynamics` không nhận vòng này. Ensemble khác không đi qua đó.

Hàng điệu giữ khoảng đã viết trong ô, kể cả phách mạnh `max(_note_velocity, 68)`. Không thêm cung của câu hát lên rasgueado.

---

## 6. La♭ áp Sol

Passage Torroba đã chạy trong pipeline chung. Bảy pattern đã có hàng hairpin. Chúng không thuộc `_HOST`. Tập nốt là thứ tự nhiên của Đô, cũng là Phrygian của Sol. Không thêm Rê♭. Không thêm Si.

`torroba_scale_step` coi đối số thứ ba là cao độ. `_trace_scale` truyền `+1` hoặc `-1`. Trên dây đàn, `+1` nhỏ hơn nốt đang đứng, nên nét đi lên bị bước xuống rồi bị bỏ. Nét đi xuống sống vì `-1` tình cờ cùng hướng. Trong Torroba, nét đi lên là nét lấy đà slur vào phách mạnh. Sửa hướng này trước khi nới sóng.

`_scale_steps` của Olite và `_scale_away` của Alcaniz truyền cao độ thật, nên hai chỗ đó đi được hai chiều và đang có La♭. Đổi chúng sang `±1` mà không gắn cửa đích thì La♭ ở hai chỗ đó mất.

La♭ chỉ đứng ngay trước một nốt Sol, pitch class 7. Hợp âm ô đích là `G` hoặc `G7` là điều kiện thêm, khi đích đã là Sol. Hợp âm một mình không được quyết định. Nét đổ vào Rê hoặc Si trên hợp âm Sol không chèn La♭. La♭–Rê không phải cú áp của vòng Andalucia. Nét đi ngang La rồi xuống tiếp cũng không chèn.

Cửa gắn ở mọi chỗ biết đích:

- `_trace_scale`, nốt ngay trước `end`
- `_approaches`, nốt ngay trước `target`
- `_scale_steps`, nốt áp cuối của danh sách
- nốt áp của `_two_into`, tức nốt thứ hai trong cặp trả về

`_approaches` bỏ `_walk`, bước bằng `torroba_scale_step`. Một nốt và ba nốt của Castillo, Sonatina khi ấy mới áp được Sol. `torroba_scale_step` đọc hướng như `classic_scale_step`: `toward >= 0` là đi lên. Cửa không nâng Si♭ thành Si ở lại trong hàm đó.

`test_scale_step_may_be_ab_and_does_not_raise_bb` đang gọi `torroba_scale_step(ctx, 69, 67)`. Đổi lời gọi sang hướng. Từ Sol, hướng `+1` trả một nốt cao hơn Sol. Nét có đích Sol vẫn áp La♭. Nét có đích khác Sol không áp. Si♭ không thành Si.

---

## 7. Khi vào code

Sửa scale trước, rồi mới đổi sóng. Nét lấy đà đang bị xóa. Nới vận tốc trên một nét không còn thì không nghe ra.

1. `torroba_scale_step` đọc hướng. Cửa La♭ ở bốn chỗ mục 6. `_approaches` dùng bước đó.
2. `PROFILES`: hai hàng mục 2. `d_lo` và `d_hi` đặt trên từng profile Torroba, không đổi mặc định toàn cục.
3. Giường bass Torroba nhấc `4` sau `_under_lead`, rồi siết lại lead > bass > bè trung. `_BAND_BASS` của ensemble khác giữ nguyên.
4. Vòng cung mục 5, chỉ ba pattern hát, chỉ bè hát, trước `apply_guitar_wave`.
5. Móng điệu `70/73`. `_is_target` loại vận tốc `48`. Không thêm nhánh `castillo`.
6. `backend/tests/test_guitar_wave.py`: tâm hát `42` và `50`, bass viết `64` ra `42` và `50`. Tâm điệu round `48` và `55`, lead viết `72` ra `56` và `63`.
7. `backend/tests/test_sonify_guitar_torroba.py`: hướng `+1` đi lên. La♭ chỉ trước Sol. Chuông `48` không là móng. Câu hát phẳng có cung `6–8` trên bè hát và bass không được cộng cùng số đó.
8. `SPAN_REVISION` tăng một bậc khi sóng đổi, để file nghe cũ không bị phát lại.

`WARM_LIMIT`, độ dài bass một phách, và `_shape_dynamics` dùng chung không sửa trong đợt này.
