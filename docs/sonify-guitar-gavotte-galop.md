# Gavotte và Galop: đường giá, và câu thứ hai của Sor Op. 32 No. 6

> **Phạm vi**: thân bài `bach_gavotte` trong `backend/app/sonify/guitar_bach.py`, thân bài `galop` trong `backend/app/sonify/guitar_sor.py`, cửa `galop` trong `backend/app/sonify/guitar_frame_bach_sor.py`.
> **Bản đối chiếu**: Fernando Sor, *Galop*, Op. 32 No. 6, trong *Six petites pièces* (Paris, 1828). Bản Tecla, *New Complete Works for Guitar*, tập 4, trang 78. Ảnh đính kèm là câu sau chữ *Fine* của chính bài này, Tecla đánh số 17–24.
> **Mục tiêu**: Gavotte 4/4 hát giá, Galop xen tế bào phi với câu đối đáp. Code phát nhạc đã theo mục 1.1 và mục 4. Mục 1 và mục 2 là đo engine trước đợt này, không phải code đang hát.
> **Mốc code**: đối chiếu với `main` `7d856b3`. Merge scale không sửa `guitar_bach.py`, `guitar_sor.py`, hay `guitar_frame_bach_sor.py`. Sóng vẫn là `affine_raw`: `round(C) + (V - 64)`.

Mốc móc đơn là chỉ số eighth `0 .. epb - 1`. Ô 4/4 dùng `epb = 8`. Một ô 4/4 của sonify bằng hai ô 2/4 của Sor, tức 8 ô 2/4 bằng **bốn** ô 4/4. Velocity thân bài: lead `_MELODY = 64`, bass `_BASS = 56`, bè trong `_INNER = 46`.

Cột “Giá” trong bảng dưới là cao độ đầu vào, trước `quantize_strong_beats`. Đường render của bảng không có `raw_pitches`. `_place_melody` vẫn lượng tử phách mạnh trước khi pattern đọc `ctx.melody`.

---

## 1. Gavotte, đo trước khi sửa

Đoạn này là engine trước đợt hát giá. Code 4/4 hiện tại nằm ở mục 1.1.

Bourrée hát dòng đã lượng tử. Engine cũ: nửa sau mỗi ô Gavotte hát một thang dẫn vào nốt đầu ô sau.

`_render_bach_gavotte_bar` đọc `ctx.melody` ở móc đơn 0 và móc đơn 2. Mỗi cú kéo thành một nốt đen, nên bước giá nằm giữa nốt đen bị nuốt. Từ móc 4, engine cũ gọi `_approach_eighths` bốn bước thang lên nốt đầu ô sau. Nốt đó đã qua `quantize_strong_beats`. Bè trong là quãng 3 hoặc quãng 6 song song dưới thang đó.

Nửa đầu bass không phải một nốt gốc ngân suốt. `degree` là 0 rồi 2: gốc ở móc 0, quãng 5 ở móc 2, và nốt ở móc 2 là staccato, cùng lead. Kế hoạch Bach cũng ghi gốc và quãng 5. Nửa sau là một nốt hợp âm ngân, `_gavotte_tail_bass`.

Đo trên đường giá đang đi, ensemble Bach, `character = "calm"`, hợp âm ô 0–3 là C, G, F, C. “Khớp” đếm từng móc đơn đang ngân so với cột Giá.

| Ô | Giá | Nốt lead nghe được | Khớp với cột Giá |
|---|---|---|---|
| 0 | 67 69 71 72 74 72 71 69 | 67 67 71 71 60 62 64 65 | 2/8 |
| 1 | 69 71 72 74 76 74 72 71 | 67 67 72 72 65 67 69 71 | 2/8 |
| 2 | 72 71 69 67 65 67 69 71 | 72 72 69 69 59 59 60 62 | 2/8 |
| 3 | 64 65 67 69 71 72 74 76 | 64 64 67 67 59 59 60 62 | 2/8 |

Ô 1, giá 69 ở phách mạnh thuộc hợp âm G. Cùng một run với nốt 69 cuối ô 0, nên cả run thành 67 trước khi Gavotte đọc. Thang đuôi ô 0 nhắm vào 67 đó. Bốn bước thang dưới 67 là 60, 62, 64, 65. Ô 0, nốt 74 ở móc 4 (phách mạnh, hợp âm C) thành 76. Đó là lý do Bourrée lệch cột Giá dù lead không tự viết giai điệu.

Bourrée trên cùng đường giá, `character = "rally"`, lead là `_sustain` của dòng đã lượng tử:

| Ô | So với cột Giá | So với `ctx.melody` | Nốt lead nghe được |
|---|---|---|---|
| 0 | 6/8 | 8/8 | 67 69 71 72 76 72 71 67 |
| 1 | 6/8 | 8/8 | 67 71 72 74 74 74 72 71 |

Ô 1, nốt 74 ở phách 1.5 có `tie_start`, và nốt `tie_stop` ở phách 2 dài một phách, phủ móc 4 và 5. Bỏ `tie_stop` thì hai móc đó thành lỗ và ô 1 chỉ còn 5/8 so với cột Giá. Dòng đã lượng tử của ô 1 là `67 71 72 74 74 74 72 71`, lead khớp hết.

Ngày đi ngang: giá đứng ở 72 thì hai nốt đen vẫn là 72, rồi thang `65 67 69 71`. Đường giá không có đường nét. Đường nét tai nghe được là thang dẫn vào ô sau.

Gavotte đứng ở thân bài 4/4 khi `calm` và BPM trên 72. Đó là `1D` và các chương 4/4. `_bach_primary` trả `bach_gavotte` chỉ sau khi đã loại `3/4`, `bpm <= 72`, `volatile`, `selloff`, và `6/8`.

Scherzo 6/8 không hát Gavotte. `_bach_contrast` gặp `ctx.kind == "6/8"` thì trả `bach_bourree` khi calm, còn lại `bach_fuga`, rồi return. Nhánh `bach_gavotte` nằm sau và không chạy trên meter này. Chương chậm 3/4 cũng return sớm, contrast là `bach_chaconne`. Form guitar chỉ gắn `trio` cho scherzo, và `_guitar_meter` đổi scherzo thành 6/8. Nhánh contrast trả Gavotte vì vậy không kêu trên form guitar. Bảng trong `docs/sonify-classical-guitar.md` vẫn ghi fuga/chaconne đối với gavotte ở scherzo. Code hiện tại không làm vậy.

### 1.1. Cách hát để còn là Gavotte và còn là giá

Giữ nhịp: nốt đen, nốt đen staccato, bốn móc đơn. Quãng 3/6 ở lại bè trong, dưới những móc đơn đó.

Bass nửa đầu giữ đúng code hiện tại: gốc ở móc 0, quãng 5 ở móc 2, nốt ở móc 2 staccato. Nửa sau vẫn một nốt hợp âm ngân.

Sáu cú lấy giá, trừ hai móc cuối khi ô đang đi tới một nốt khác. Móc 0, 2, 4 và 5 là `ctx.melody` tại đúng móc đó. Móc 6 và 7 cũng là `ctx.melody` khi nốt đầu ô sau bằng `ctx.melody` tại móc 4. Khi hai nốt đó khác nhau, móc 6 và 7 là `_approach_eighths(ctx, target, 2)` vào nốt đầu ô sau. Thang bốn nốt cũ bỏ. Không chèn lân bậc. Không bịa một quãng 6.

Kế hoạch Bach ghi anacrusis Gavotte là nửa ô. Nửa ô đó đang là chỗ máy viết giai điệu. Khi bốn móc đơn mang giá, nửa ô hát của điệu trùng với đường giá.

Không đổi `_bach_contrast`. Bảng scherzo trong `docs/sonify-classical-guitar.md` vẫn ghi contrast Gavotte. Code return sớm ở `6/8`. Đợt này không sửa hàm cho khớp bảng đó.

---

## 2. Galop, đo trước khi sửa

Đoạn này là engine trước tế bào phi. Code hiện tại nằm ở mục 4.

`_classic_macro` chọn `galop` khi rally, trưởng, và `rel_span >= 0.012`, sau một cửa nữa: `character is None` và vùng không được đánh dấu rally thì vẫn `study`, kể cả biên rộng và trưởng. `render()` có character, nên cửa này ít khi kêu. Trên 1D, pattern này chiếm cả thân bài.

Engine cũ, `_render_galop_bar` vẽ mỗi ô giống nhau:

- Bass staccato, nốt đen ở móc 0 (gốc, có accent) và móc 4 (quãng 5). `_galop_bass_points` của 4/4 là `(0, 4)`.
- Bè trong staccato có accent ở móc 1, 3, 5, 7. Hai nốt hợp âm thay nhau.
- Lead là `_sustain` của `ctx.melody`, nốt móc đơn legato.
- Không có móc kép. Test lúc đó khóa `assert _sixteenths(galop.lead, 2) == []` trên ô thân đầu của `_frame_score("classic", 2)`. Test hiện tại khóa `[0.5, 0.75, 1.5, 1.75, 2.5, 2.75]`, xem mục 4.3.

`_galop_sparkle` chỉ nhảy khi một run cùng cao độ **bắt đầu** ở phách mạnh (`local in ctx.strong`) và dài ít nhất hai móc đơn. Run bắt đầu trước phách mạnh rồi ngân xuyên qua phách đó không kêu. Cú nhảy còn cần một trong ba cửa: `ctx.mood(bar) == "rally"`, cửa sổ ô đi lên (`window[-1] > window[0]`), hoặc `phrase.rise >= MIN_RISE` và ô còn trước đỉnh câu (`bar * epb <= phrase.apex.start`). Giá chạy từng móc đơn thì không có run dài hai móc, cú nhảy không kêu.

Đo thân bài của một rally có khung. “Khớp” so với giá đầu vào của ô đó:

| Ô thân | Khớp lead / 8 móc | Móc kép |
|---|---|---|
| 0 | 6 | 0 |
| 1 | 7 | 0 |
| 2 | 7 | 0 |
| 3 | 7 | 0 |

Ô 3 mở bằng bốn nốt 64 bắt đầu đúng móc 0, nên sparkle đổi móc 1 thành 67 staccato. Phần còn lại của lead là giá, legato.

Đường giá trên lead đã bám. Tai không nhận ra bài Sor vì đệm lặp nguyên một ô: bass nốt đen gốc rồi quãng 5, bè trong chặt mỗi phách yếu. Bài Sor viết hai bè. Tiếng phi nằm ở hai móc kép của giai điệu.

Cửa `_galop_hits` không phải ô oom-pah suốt. `docs/sonify-guitar-frame-variations.md` liệt kê từng bước. Trong code, các role gọi `_galop_span` mới là tế bào bass staccato và bè trong phách yếu. Các role gọi `_staccato_hits` đã là hợp âm staccato:

| Cửa | Role | Trước đợt này |
|---|---|---|
| Intro ngắn | 0 | `_galop_span`, lead chỉ nửa đầu |
| Intro ngắn | 1 | nửa đầu `_galop_span` trên V7, nửa sau `_lead_leaps` |
| Outro ngắn | 0 | `_galop_span` cả ô, có sparkle |
| Outro ngắn | 1 | `_staccato_hits` ở móc 0 và móc 2, accent |
| Intro dài | 0 | `_galop_span`, không lead |
| Intro dài | 1 | `_galop_span` trên I rồi IV, có sparkle |
| Intro dài | 2 | `_galop_span` trên V7, có sparkle |
| Intro dài | 3 | `_galop_span` đến trước móc nghỉ, rồi ba `_staccato_hits` |
| Outro dài | 0 | `_galop_span` trên I rồi IV, có sparkle |
| Outro dài | 1 | `_galop_span` trên V7, có sparkle |
| Outro dài | 2 | `_staccato_hits` V7, I, V7 |
| Outro dài | 3 | hai `_staccato_hits` trên I, có accent |

Role `_galop_span` với `lead=True` lấy cả tế bào Galop 1 ở mục 4.1. Role `_staccato_hits` giữ hợp âm. Intro ngắn role 1, nửa sau, là `_lead_leaps`: không phải `_galop_span`, không phải `_staccato_hits`, và nửa ô đó giữ nguyên. Intro dài role 3 giữ móc nghỉ và ba hợp âm.

Tế bào 4.1 có giai điệu suốt nửa ô. Span gọi `_galop_span` với `lead=False` thì giai điệu của tế bào nghỉ, chỉ lấy bass: một móc đơn staccato ở đầu mỗi nửa ô mà span phủ. Span cả ô, như intro dài role 0, có hai móc đó, ở móc 0 và móc 4. Gán cả tế bào sẽ thêm lead vào chỗ cửa đang nghỉ. Các span đó là:

- Intro ngắn role 0, nửa sau.
- Intro ngắn role 1, nửa đầu.
- Intro dài role 0, cả ô.
- Intro dài role 3, đoạn span trước móc nghỉ.

Không đổi cả `_galop_hits`, và không gán “bước mở là Galop 1, bước khép là Galop 2” cho mọi role. Galop 2 ở thân bài.

---

## 3. Bài Sor có hai câu

*Galop* Op. 32 No. 6 viết ở 2/4, một dấu thăng, hai bè. Không có bè trong chặt từng phách yếu. Dấu chấm cạnh đầu nốt trong câu phi là staccato, không phải nốt chấm dôi.

| Câu | Ô Tecla | Vai |
|---|---|---|
| Galop 1 | 1–8, lặp | Câu phi. Tế bào lặp là một ô 2/4: móc đơn, hai móc kép, móc đơn, rồi hai móc kép. Biến của ô 2, không phải mọi nửa ô: nửa sau là hai móc đơn. Ô 1, phách 1 chỉ có một đầu nốt. Ô cuối câu là cadence, hợp âm rồi nghỉ. |
| Galop 2, dạng thưa | 9–16, *Fine*, lặp về đầu | Cùng câu đối đáp. Bass một móc đơn, không cú nhảy quãng 12. |
| Galop 2, dạng trong ảnh | 17–24 | Câu đối đáp đầy. Bass hai móc đơn dưới một thanh nối, nốt trầm rồi nốt cao hơn một quãng 12. Một ô trong câu là bốn móc kép liền. Ô 24 có hợp âm khối Fa–Sol–La, rồi một móc đơn Mi trầm. |
| Câu chạy | 25–28 | Giai điệu móc kép liên tục, mức *f*. Bass thưa. |
| Đối đáp nhắc lại | 29–32 | Cùng dạng đối đáp, rồi *D.C. al Fine*. |

Ảnh là ô 17–24. Op. 57 là bài khác: hợp âm có accent, nốt ba, harmonics.

Ô 9–16 và ô 17–24 là một pattern, hai mật độ bass. Một Galop 2 là đủ. Lưới ở mục 4 là dạng đầy. Dạng thưa dùng cùng chỗ giai điệu và chỗ nghỉ, bass chỉ còn một móc đơn ở phách câu.

---

## 4. Dùng hai câu cùng lúc

8 ô 2/4 bằng bốn ô 4/4. Xen **bốn** ô Galop 1 rồi **bốn** ô Galop 2, rồi lặp. “Hai ô rồi hai ô” chỉ mới là 4+4 ô 2/4, ngắn một nửa so với câu của Sor.

Chu kỳ đếm các ô thân có id `galop`, theo thứ tự trong bài, từng cụm liền nhau. Ô cửa intro và outro không vào đếm. Cụm đứt khi gặp ô không phải `galop`. Ô thứ 1–4 của cụm là Galop 1. Ô thứ 5–8 là Galop 2, rồi lặp. Cụm ngắn hơn năm ô thì toàn Galop 1.

Hai câu là hai cách dệt trong `_render_galop_bar`. Bộ chọn vẫn trả id `"galop"`. `_settle_galop` sơn danh sách id đó trước lúc render. Xen Galop 2 bên trong một ô đã mang id `galop` không làm form sơn lại thành study. Study vẫn đứng hai đầu khi cả chương là galop. Tầng form đó giữ nguyên.

`galop` vẫn nằm trong `_KINETIC_PATTERNS`. `bach_gavotte` vẫn nằm trong `_BAROQUE_PATTERNS`. Passage scale vẫn phủ hai pattern này: `_install_lead` thay lead trên eighth của passage, `_rewrite_bass` trồng bass trên `ctx.strong`. Lưới mới là phần ô không nằm trong passage. Không đổi `select_scale_plan`. Không đưa hai pattern này vào `_HOST`. Số passage của Sor, Bach và Brouwer trên cùng snapshot giữ nguyên.

`_classic_macro` giữ cửa `character is None` như mục 2.

### 4.1. Galop 1 — một ô 2/4, tức nửa ô 4/4

Tế bào lặp đứng hai lần trong một ô 4/4, mở ở móc đơn 0 và móc đơn 4. Không phải một tế bào mỗi phách. Móc đơn cộng hai móc kép đã hết một phách. Phách còn lại của ô 2/4, trên lưới lặp, là một móc đơn rồi hai móc kép.

Chỉ số móc kép trong nửa ô, `0 .. 7`. Tế bào mở tại móc đơn `origin`, `origin` là 0 hoặc 4. Bảng là lưới lặp. Biến Tecla ô 2 chỉ là nửa sau của ô Galop 1 đầu tiên trong cụm: `variant = index == 0 and origin == 4`, hai móc đơn lấy `ctx.melody` tại `origin+2` và `origin+3`. Ô thứ 9 của cụm (`index == 8`) trở lại Galop 1 và hát lưới lặp suốt, không có hai móc đơn đó. Điều kiện không phải `index % 8 == 0`. Các nửa ô Galop 1 còn lại hát lưới lặp.

| Móc kép | Giai điệu | Bass |
|---|---|---|
| 0–1 | móc đơn, staccato, `ctx.melody` tại `origin` | móc đơn, staccato, gốc, cùng phách |
| 2 | móc kép, không staccato. Quãng tám trên nốt ở móc 0–1 | nghỉ |
| 3 | móc kép, không staccato. Nốt hợp âm dưới móc 2, trong một quãng 5 | nghỉ |
| 4–5 | móc đơn, staccato, `ctx.melody` tại `origin + 2`. Trên biến ô 2, đây là móc đơn đầu của nửa sau | nghỉ |
| 6 | lưới lặp: móc kép, không staccato, quãng tám trên nốt ở móc 4–5. Biến ô 2 không có móc kép này | nghỉ |
| 7 | lưới lặp: móc kép, không staccato, nốt hợp âm dưới móc 6, trong một quãng 5. Biến ô 2: móc 6–7 là một móc đơn, `ctx.melody` tại `origin + 3` | nghỉ |

Dấu chấm ở mục 3 nằm trên hai móc đơn của câu phi: giai điệu ở 0–1 và 4–5, và bass ở 0–1. Bốn móc kép của lưới lặp không mang dấu chấm. Chúng là nhịp phi nối thanh, không staccato.

Ô 1 Tecla hát đúng lưới nhịp đó. Phách đầu: Re dưới khuông, móc đơn có chấm, rồi Re trên dòng thứ tư và Si trên dòng giữa, hai móc kép. Phách sau: Sol trên dòng thứ hai, móc đơn có chấm, rồi Sol trên khuông và Re trên dòng thứ tư, hai móc kép. Móc kép đầu của mỗi cặp là quãng tám trên móc đơn vừa đánh, không giữ nguyên nốt đó. Móc kép sau đi xuống: Si dưới Re một quãng 3, Re dưới Sol một quãng 4, cả hai là nốt hợp âm. Phách 1 của ô này chỉ có một đầu nốt Re, không có đầu nốt bass thứ hai cùng phách. Ô 2 phách đầu cùng lưới: Si móc đơn, rồi Si quãng tám và Sol hai móc kép. Phách sau của ô 2 là biến của ô đó, không phải mọi nửa ô: hai móc đơn, Re rồi Si, `ctx.melody` tại `origin+2` và `origin+3`.

`here == open` không mô tả ô 1, và cũng không mô tả nửa sau của chính ô đó. Móc kép 2 không giữ nốt mở. Móc kép 3 không phải nốt hợp âm kế trên trong vòng một quãng 5. Cặp nốt là quãng tám lên, rồi nốt hợp âm gần nhất nằm dưới nốt cao đó và cách không quá 7 nửa cung. Không có nốt hợp âm nào trong cửa đó, hoặc quãng tám hay nốt hợp âm nằm ngoài register của lead, hoặc một trong hai nốt không `_playable` một mình, thì hai móc kép nghỉ và móc đơn giá vẫn giữ. `_octave_pair_ok` bỏ bass của tế bào: móc đơn staccato gốc đã hết trước hai móc kép, nên bass đó không nằm trong sonority. Bass còn đang ngân trên chính móc kép, kể cả pickup cuối ô biên, là cửa khác. Pickup đó hỏi `_safe_pickup` với gốc Galop đã có trong dòng bass, cùng nốt `_plant_pickup` sẽ thấy. Cặp chỉ nghỉ khi nốt pickup đó không `_playable` cùng quãng tám hoặc cùng nốt hợp âm.

Bỏ bè trong chặt phách yếu.

### 4.2. Galop 2 — lưới của ô 17–24

Cũng tính trên một ô 2/4. Ô 4/4 chứa hai lần. Đây là tế bào đối đáp, dùng cho hầu hết nửa ô trong bốn ô Galop 2.

| Móc kép | Giai điệu | Bass |
|---|---|---|
| 0 | móc đơn bắt đầu, giá. Nốt này ngân qua móc 1 | móc đơn, nốt trầm, gốc. Nốt này ngân qua móc 1 |
| 1 | đuôi móc đơn trên | đuôi móc đơn trầm |
| 2 | nghỉ | móc đơn, cao hơn nốt trầm một quãng 12. Nốt này ngân qua móc 3 |
| 3 | nghỉ | đuôi móc đơn cao |
| 4–5 | móc đơn, giá | nghỉ |
| 6–7 | nghỉ | nghỉ |

Ô 17 của Tecla là mẫu: giai điệu móc đơn, nghỉ, móc đơn, nghỉ. Hai móc đơn đó là Mi rồi Sol, có đuôi cờ. Bass là Mi ở khoảng trống dưới dòng phụ thứ ba, móc đơn, nối Si trên dòng giữa khuông, móc đơn, một thanh nối, rồi nghỉ. Không phải Sol trên hai dòng phụ, và không phải móc kép nối móc đơn. Mi dưới Si đó 19 nửa cung, một quãng 12 đúng.

Quãng 12 là 19 nửa cung. Nốt bass viết nằm trong `guitar_floor .. guitar_bass_top`, mặc định `40 .. 53` (`Register` trong `keys.py`; `register_for` trừ `key.semitones`). Từ một nốt trong `40 .. 53`, quãng 12 rơi vào `59 .. 72`, trên `guitar_bass_top`. `_choose_bass` gọi `_stored_bass`, và `_stored_bass` gọi `_clamp` vào `[low, high]` với `high` là `bass_high`. Thân bài đặt `bass_high = guitar_bass_top`. `_bass_note` và `_bass_match` cũng chặn tại `_bass_hi`. `_clamp` trừ 12 cho đến khi nốt vào cửa sổ, và quãng 12 mất. Nốt trên của cú nhảy vẫn là bè bass, voice 3, và được đứng trên `53`. Không đưa nốt đó qua `_choose_bass`, `_stored_bass`, `_bass_note`, hay `_bass_match`.

Nốt trên kêu ở móc kép 2, trong chỗ nghỉ của giai điệu, nên không kêu cùng móc đơn trước. Ở ô 17 nốt trên là Si, dưới Mi vừa nghỉ và dưới Sol sắp vào. Gốc đã hết ở cuối móc 1. Gốc bắt đầu trong cửa sổ bass. Nếu `gốc + 19` không còn dưới giai điệu quanh đó, hoặc `_playable` không nhận các nốt đang kêu sau khi cộng `ctx.semitones`, hạ gốc một quãng tám rồi tính lại nốt trên. Không hạ nốt trên. Gốc không xuống dưới `guitar_floor`. Hết quãng tám mà quãng 12 vẫn không nằm dưới giai điệu hoặc không qua `_playable` thì nửa ô đó hát bass dạng thưa: một móc đơn gốc, không cú nhảy.

Đợt này không hát các ô đặc biệt của Tecla. Cả bốn ô Galop 2 hát lưới đối đáp ở trên. Dạng thưa chỉ khi quãng 12 không đặt được. Ô 19, 20, 22, 23, 24 và câu 25–28 để đợt sau. Ghi từ bản Tecla, chưa có trong `_render_galop_dance`:

- **Ô 19.** Bốn móc kép La, Sol, Fa thăng bởi khóa, Mi, đi xuống từng quãng 2. Hai slur chụm La–Sol và Fa–Mi. Không phải bậc trên, nốt giá, bậc dưới, rồi lại nốt giá.
- **Ô 20 và ô 23.** Re thăng thay nốt bass trầm của nửa ô đó.
- **Ô 22.** Dấu thăng ngang tầm La trên khuông, slur dưới, và một móc đơn Si. Đầu nốt móc kép dính vào dấu thăng, không tách được. Không ghi cao độ lân giai điệu cho ô đó.
- **Ô 24.** Hợp âm khối Fa, Sol, La, rồi một móc đơn Mi trầm.
- **Ô 25–28.** Câu chạy móc kép, bass thưa. Đầu nốt không có trong tài liệu này. Không bịa chuỗi đó.

### 4.3. Test đang khóa

`_settle_galop` không đọc bass. `test_an_even_week_puts_galop_across_the_two_middle_sessions` và `test_a_galop_scherzo_moves_the_dance_into_the_trio` gọi thẳng hàm đó trên danh sách id. Hai test đó giữ nguyên.

`test_a_long_sor_rally_keeps_galop_in_the_middle_of_aba` và `test_two_galop_phrases_keep_the_dance_on_the_second` chỉ có một cụm galop ngắn ở giữa, nên các ô đó là Galop 1. Bass Galop 1 vẫn là hai nốt staccato tại `0.0` và `2.0`. Hai hàm `galop_bar` giữ dấu nhận đó.

`test_sor_galop_and_mozart_variations_and_the_op9_overture`, ô thân đầu của `_frame_score("classic", 2)`:

- Móc kép lead là `[0.5, 0.75, 1.5, 1.75, 2.5, 2.75]`.
- Phách 0.5 cao hơn phách 0 đúng một quãng tám, không staccato. Nốt hợp âm kế dưới nằm trong 7 nửa cung.
- Phách 3.0 và 3.5 là hai móc đơn của biến ô 2: 3.0 staccato, 3.5 không staccato, cả hai trùng nốt đầu vì giai điệu giữ nguyên. Không có móc kép tại 3.5 và 3.75. `test_galop_bar_two_variant_reads_the_melody_at_those_eighths` khóa cao độ khi hai móc đó khác nốt đầu: chúng là `ctx.melody` tại `origin+2` và `origin+3`.
- Bass là hai móc đơn staccato tại `0.0` và `2.0`. Bè trong rỗng.

`_frame_score("classic", 4)` trong test đó: lead ô 0 rỗng, bass ô 0 toàn staccato, lead ô 3 chỉ ở `2.5, 3.0, 3.5`, bass ô cuối staccato có accent. Ô 0 là intro dài role 0, `lead=False`. Ô 3 giữ móc nghỉ rồi ba hợp âm. Bass ô cuối là outro dài role 3, `_staccato_hits`.

`test_composer_intro_and_outro_frames_for_two_and_four_bars` trên `_frame_score("classic", 2)`: `divisions == 4`, bè trong ô 0 rỗng, onset bass `[0.0, 2.0]`, `velocity <= 52`. Lead ô 0 là nửa đầu `lead=True`: móc kép tại `0.5, 0.75, 1.5, 1.75`, quãng tám trên nốt phách 0, nốt hợp âm trong 7 nửa cung, không có lead từ phách 2. Nửa sau `lead=False` chỉ còn bass móc đơn. Lead ô 1 từ phách 2 là `_lead_leaps`.

Bass ô 0 của cửa ngắn giữ mức cửa: nửa đầu `_P = 50`, nửa sau `_MP = 56`. Sau `affine_raw`, mức nghe là 36 rồi 42.

`test_the_last_gavotte_bar_keeps_the_price_on_eighths_six_and_seven` khóa móc 6–7 của ô cuối. `test_gavotte_tail_follows_the_price_until_the_next_downbeat_changes` khóa hai nhánh còn lại của ô 4/4: móc 4–5 là giá, móc 6–7 là `_approach_eighths` khi nốt đầu ô sau khác móc 4, và móc 6–7 vẫn là giá khi hai nốt đó bằng nhau.

`test_boundary_galop_keeps_the_sixteenth_pair_the_real_pickup_can_play` khóa cặp móc kép cuối ô biên khi pickup tính với gốc Galop còn trong dòng bass chơi được với cặp đó.
