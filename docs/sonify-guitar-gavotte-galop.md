# Gavotte và Galop: đường giá, và câu thứ hai của Sor Op. 32 No. 6

> **Phạm vi**: thân bài `bach_gavotte` trong `backend/app/sonify/guitar_bach.py`, thân bài `galop` trong `backend/app/sonify/guitar_sor.py`, cửa `galop` trong `backend/app/sonify/guitar_frame_bach_sor.py`.
> **Bản đối chiếu**: Fernando Sor, *Galop*, Op. 32 No. 6, trong *Six petites pièces* (Paris, 1828). Bản Tecla, *New Complete Works for Guitar*, tập 4, trang 78. Ảnh đính kèm là câu sau chữ *Fine* của chính bài này, Tecla đánh số 17–24.
> **Mục tiêu**: ghi vì sao Gavotte không phản ánh price action, vì sao Galop nghe chưa ra bài của Sor, và cách dùng câu đối đáp trong ảnh (Galop 2) xen với câu phi. Chưa đổi code phát nhạc.

Mốc móc đơn là chỉ số eighth `0 .. epb - 1`. Ô 4/4 dùng `epb = 8`. Một ô 4/4 của sonify bằng hai ô 2/4 của Sor, tức 8 ô 2/4 bằng **bốn** ô 4/4. Velocity thân bài: lead `_MELODY = 64`, bass `_BASS = 56`, bè trong `_INNER = 46`.

Cột “Giá” trong bảng dưới là cao độ đầu vào, trước `quantize_strong_beats`. Đường render của bảng không có `raw_pitches`. `_place_melody` vẫn lượng tử phách mạnh trước khi pattern đọc `ctx.melody`.

---

## 1. Gavotte

Bourrée hát dòng đã lượng tử. Gavotte thì nửa sau mỗi ô hát một thang dẫn vào nốt đầu ô sau.

`_render_bach_gavotte_bar` đọc `ctx.melody` ở móc đơn 0 và móc đơn 2. Mỗi cú kéo thành một nốt đen, nên bước giá nằm giữa nốt đen bị nuốt. Từ móc 4, `_approach_eighths` đi bốn bước thang lên nốt đầu ô sau. Nốt đó đã qua `quantize_strong_beats`. Bè trong là quãng 3 hoặc quãng 6 song song dưới thang đó.

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

Giữ nhịp: nốt đen, nốt đen staccato, bốn móc đơn. Cao độ của sáu cú đánh lấy từ `ctx.melody` tại móc 0, 2, 4, 5, 6, 7. Quãng 3/6 ở lại bè trong, dưới những móc đơn đó.

Bass nửa đầu giữ đúng code hiện tại: gốc ở móc 0, quãng 5 ở móc 2, nốt ở móc 2 staccato. Nửa sau vẫn một nốt hợp âm ngân.

Thang dẫn vào ô sau rút còn hai nốt, và chỉ khi `ctx.melody` đang đi về nốt đầu ô sau. Ô đứng yên thì bốn móc đơn nhắc lại nốt giá, hoặc một nốt lân bậc. Chúng không bịa một quãng 6.

Kế hoạch Bach ghi anacrusis Gavotte là nửa ô. Nửa ô đó đang là chỗ máy viết giai điệu. Khi bốn móc đơn mang giá, nửa ô hát của điệu trùng với đường giá.

---

## 2. Galop đang phát

`_classic_macro` chọn `galop` khi rally, trưởng, và `rel_span >= 0.012`, sau một cửa nữa: `character is None` và vùng không được đánh dấu rally thì vẫn `study`, kể cả biên rộng và trưởng. `render()` có character, nên cửa này ít khi kêu. Trên 1D, pattern này chiếm cả thân bài.

`_render_galop_bar` vẽ mỗi ô giống nhau:

- Bass staccato, nốt đen ở móc 0 (gốc, có accent) và móc 4 (quãng 5). `_galop_bass_points` của 4/4 là `(0, 4)`.
- Bè trong staccato có accent ở móc 1, 3, 5, 7. Hai nốt hợp âm thay nhau.
- Lead là `_sustain` của `ctx.melody`, nốt móc đơn legato.
- Không có móc kép. `test_sor_galop_and_mozart_variations_and_the_op9_overture` khóa `assert _sixteenths(galop.lead, 2) == []` trên ô thân đầu của `_frame_score("classic", 2)`.

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

| Cửa | Role | Đang là |
|---|---|---|
| Intro ngắn | 0 | `_galop_span`, lead chỉ nửa đầu |
| Intro ngắn | 1 | nửa đầu `_galop_span` trên V7, nửa sau `_lead_leaps` |
| Outro ngắn | 0 | `_galop_span` cả ô, có sparkle |
| Outro ngắn | 1 | `_staccato_hits` ở móc 0 và móc 2 hoặc 4, accent |
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
| Galop 1 | 1–8, lặp | Câu phi. Tế bào lặp là một ô 2/4: móc đơn, hai móc kép, rồi hai móc đơn. Bass một móc đơn đúng phách 1. Ô cuối câu là cadence, hợp âm rồi nghỉ. |
| Galop 2, dạng thưa | 9–16, *Fine*, lặp về đầu | Cùng câu đối đáp. Bass một móc đơn, không cú nhảy quãng 10. |
| Galop 2, dạng trong ảnh | 17–24 | Câu đối đáp đầy. Bass móc kép trầm nối móc đơn cao hơn một quãng 10. Một ô trong câu là bốn móc kép liền. Ô cuối khép bằng hợp âm khối. |
| Câu chạy | 25–28 | Giai điệu móc kép liên tục, mức *f*. Bass thưa. |
| Đối đáp nhắc lại | 29–32 | Cùng dạng đối đáp, rồi *D.C. al Fine*. |

Ảnh là ô 17–24. Op. 57 là bài khác: hợp âm có accent, nốt ba, harmonics.

Ô 9–16 và ô 17–24 là một pattern, hai mật độ bass. Một Galop 2 là đủ. Lưới ở mục 4 là dạng đầy. Dạng thưa dùng cùng chỗ giai điệu và chỗ nghỉ, bass chỉ còn một móc đơn ở phách câu.

---

## 4. Dùng hai câu cùng lúc

8 ô 2/4 bằng bốn ô 4/4. Xen **bốn** ô Galop 1 rồi **bốn** ô Galop 2, rồi lặp. “Hai ô rồi hai ô” chỉ mới là 4+4 ô 2/4, ngắn một nửa so với câu của Sor.

Hai câu là hai cách dệt trong `_render_galop_bar`. Bộ chọn vẫn trả id `"galop"`. `_settle_galop` sơn danh sách id đó trước lúc render. Xen Galop 2 bên trong một ô đã mang id `galop` không làm form sơn lại thành study. Study vẫn đứng hai đầu khi cả chương là galop. Tầng form đó giữ nguyên.

`_classic_macro` giữ cửa `character is None` như mục 2.

### 4.1. Galop 1 — một ô 2/4, tức nửa ô 4/4

Tế bào này đứng hai lần trong một ô 4/4, mở ở móc đơn 0 và móc đơn 4. Không phải một tế bào mỗi phách. Móc đơn cộng hai móc kép đã hết một phách. Phách còn lại của ô 2/4 là hai móc đơn.

Chỉ số móc kép trong nửa ô, `0 .. 7`. Tế bào mở tại móc đơn `origin`, `origin` là 0 hoặc 4:

| Móc kép | Giai điệu | Bass |
|---|---|---|
| 0–1 | móc đơn, staccato, `ctx.melody` tại `origin` | móc đơn, staccato, gốc, cùng phách |
| 2 | móc kép, không staccato. Chung một cao độ đầu vào với móc 3 | nghỉ |
| 3 | móc kép, không staccato. Chung cao độ đầu vào với móc 2 | nghỉ |
| 4–5 | móc đơn, staccato, `ctx.melody` tại `origin + 2` | nghỉ |
| 6–7 | móc đơn, staccato, `ctx.melody` tại `origin + 3` | nghỉ |

Dấu chấm ở mục 3 nằm trên các móc đơn của câu phi: giai điệu ở 0–1, 4–5, 6–7, và bass ở 0–1. Hai móc kép không mang dấu chấm. Chúng là nhịp phi nối thanh, không staccato.

Hai móc kép 2 và 3 chiếm một móc đơn của cột Giá, móc `origin + 1`. Chỉ có một cao độ đầu vào, `here = ctx.melody` tại móc đó. Cao độ móc mở là `open`.

- `here == open`: cả hai móc kép là nốt hợp âm. Không có mẫu giá thứ hai.
- `here != open`: móc kép 3 là `here`. Móc kép 2 là một bậc thang từ `open` về phía `here`. Nếu bậc đó đã là `here`, móc kép 2 giữ `open`, và cặp nốt là bước `open` rồi `here`.

Bỏ bè trong chặt phách yếu.

### 4.2. Galop 2 — lưới của ô 17–24

Cũng tính trên một ô 2/4. Ô 4/4 chứa hai lần. Đây là tế bào đối đáp, dùng cho hầu hết nửa ô trong bốn ô Galop 2.

| Móc kép | Giai điệu | Bass |
|---|---|---|
| 0 | móc đơn bắt đầu, giá. Nốt này ngân qua móc 1 | móc kép, nốt trầm, gốc |
| 1 | đuôi móc đơn trên | móc đơn bắt đầu, cao hơn nốt trầm một quãng 10. Nốt này ngân qua móc 2 |
| 2 | nghỉ | đuôi móc đơn bass |
| 3 | nghỉ | nghỉ |
| 4–5 | móc đơn, giá | nghỉ |
| 6–7 | nghỉ | nghỉ |

Ô 17 của Tecla là mẫu: giai điệu móc đơn, nghỉ, móc đơn, nghỉ. Bass là nốt G ở hai dòng phụ, móc kép, nối nốt Si trên dòng giữa khuông, móc đơn, rồi nghỉ. G dưới Si đó một quãng 10.

Quãng 10 là 16 nửa cung. Nốt bass viết nằm trong `guitar_floor .. guitar_bass_top`, mặc định `40 .. 53` (`Register` trong `keys.py`; `register_for` trừ `key.semitones`). Từ một nốt trong `40 .. 53`, quãng 10 rơi vào `56 .. 69`, trên `guitar_bass_top`. `_choose_bass` gọi `_stored_bass`, và `_stored_bass` gọi `_clamp` vào `[low, high]` với `high` là `bass_high`. Thân bài đặt `bass_high = guitar_bass_top`. `_bass_note` và `_bass_match` cũng chặn tại `_bass_hi`. `_clamp` trừ 12 cho đến khi nốt vào cửa sổ, và quãng 10 mất. Nốt trên của cú nhảy vẫn là bè bass, voice 3, và được đứng trên `53`. Không đưa nốt đó qua `_choose_bass`, `_stored_bass`, `_bass_note`, hay `_bass_match`. Nốt móc kép trầm vẫn là gốc trong cửa sổ bass.

Hai biến trong cùng câu, mỗi biến một ô 2/4, không thay lưới trên cho cả bốn ô:

- **Nốt vòng.** Một ô 2/4 trong câu. Móc kép 0–3 là bốn móc kép giai điệu, legato, vòng quanh nốt giá. Bass không nhảy quãng 10 ở phách đó.
- **Nốt chromatic.** Một ô 2/4 trong câu. Móc kép 3, đang nghỉ trong bảng trên, thành móc kép lân bậc, legato vào móc đơn giải ở móc kép 4–5. Móc đơn giải vẫn là giá và vẫn dài hai móc kép. Móc 6–7 vẫn nghỉ. Lân bậc không đứng ở móc kép 4: móc 4–5 đã hết chỗ của móc đơn đó. Không rút móc đơn giải thành một móc kép, vì bản viết là móc kép nối vào móc đơn. Bass vẫn là cú nhảy của bảng trên. Ô khép câu đổi cú bass cuối thành hợp âm khối.

Ô 25–28 là hai ô 4/4 giai điệu móc kép liên tục, bass thưa. Trong một nhóm Galop 2, nếu giá của nhóm có nhiều cao độ khác nhau thì hai ô cuối của nhóm hát chuỗi này. Giá chỉ vài bước thì giữ bảng đối đáp.

### 4.3. Test phải đổi khi lead có móc kép và cửa đổi tế bào

`_settle_galop` không đọc bass. `test_an_even_week_puts_galop_across_the_two_middle_sessions` và `test_a_galop_scherzo_moves_the_dance_into_the_trio` gọi thẳng hàm đó trên danh sách id. Hai test đó giữ nguyên.

Chỉ hai test render nhận galop bằng bass staccato tại `0.0` và `2.0`:

- `test_a_long_sor_rally_keeps_galop_in_the_middle_of_aba`
- `test_two_galop_phrases_keep_the_dance_on_the_second`

Dấu nhận phải đọc tế bào mới. Galop 2 trong cùng id `galop` không được làm hai test này tưởng ô đó đã thành study.

Cùng `test_sor_galop_and_mozart_variations_and_the_op9_overture`, hai assert thân bài đổi khi lead có móc kép:

- `assert _sixteenths(galop.lead, 2) == []`
- sparkle: nốt ở phách 0.5 cao hơn nốt phách 0 và staccato

Bốn khóa cửa của `_frame_score("classic", 4)` trong test đó giữ nguyên: lead ô 0 rỗng, bass ô 0 toàn staccato, lead ô 3 chỉ ở `2.5, 3.0, 3.5`, bass ô cuối staccato có accent. Ô 0 là intro dài role 0, `lead=False`. Ô 3 giữ móc nghỉ rồi ba hợp âm. Bass ô cuối là outro dài role 3, `_staccato_hits`. Bass ô 0 đổi từ nốt đen thành móc đơn, nhưng assert chỉ khóa `staccato`.

Assert bè trong thân bài ở `0.5, 1.5, 2.5, 3.5` cũng đổi, vì bè trong đó rời thân bài. Assert bass nốt đen ở `0.0` và `2.0` đổi theo mục 4.1: bass Galop 1 là một móc đơn ở móc 0 và móc 4.

`test_composer_intro_and_outro_frames_for_two_and_four_bars` khóa bè trong của cửa ngắn tại `0.5, 1.5, 2.5, 3.5`. Assert đó đổi vì cửa cũng bỏ bè trong. Onset bass `[0.0, 2.0]` giữ: mỗi nửa ô vẫn một móc đơn bass ở đầu. Lead ô 1 từ phách 2 là `_lead_leaps`, giữ.
