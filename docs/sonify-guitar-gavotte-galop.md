# Gavotte và Galop: đường giá, và câu thứ hai của Sor Op. 32 No. 6

> **Phạm vi**: thân bài `bach_gavotte` trong `backend/app/sonify/guitar_bach.py`, thân bài `galop` trong `backend/app/sonify/guitar_sor.py`, cửa `galop` trong `backend/app/sonify/guitar_frame_bach_sor.py`.
> **Bản đối chiếu**: Fernando Sor, *Galop*, Op. 32 No. 6, trong *Six petites pièces* (Paris, 1828). Bản Tecla, *New Complete Works for Guitar*, tập 4, trang 78. Ảnh đính kèm là câu sau chữ *Fine* của chính bài này.
> **Mục tiêu**: ghi vì sao Gavotte không phản ánh price action, vì sao Galop nghe chưa ra bài của Sor, và cách dùng câu đối đáp trong ảnh (Galop 2) xen với câu phi. Chưa đổi code phát nhạc.

Mốc móc đơn là chỉ số eighth `0 .. epb - 1`. Ô 4/4 dùng `epb = 8`. Một ô 4/4 của sonify bằng hai ô 2/4 của Sor. Velocity thân bài: lead `_MELODY = 64`, bass `_BASS = 56`, bè trong `_INNER = 46`.

---

## 1. Gavotte

Bourrée hát đường giá. Gavotte thì nửa sau mỗi ô hát một thang âm do máy viết.

`_render_bach_gavotte_bar` đọc giá ở móc đơn 0 và móc đơn 2. Mỗi cú kéo thành một nốt đen, nên bước giá nằm giữa nốt đen bị nuốt. Bốn móc đơn từ offset 4 đi qua `_approach_eighths`: một thang trèo vào nốt đầu ô sau, thường thấp hơn đường giá khoảng một quãng tám. Bè trong là quãng 3 hoặc quãng 6 song song dưới thang đó. Bass là nốt hợp âm, ngân suốt nửa sau.

Đo trên một đường giá đang đi, ensemble Bach, `character = "calm"`, 4/4. “Khớp” đếm từng móc đơn đang ngân có đúng cao độ giá tại móc đó hay không.

| Ô | Giá | Nốt lead nghe được | Khớp |
|---|---|---|---|
| 0 | 67 69 71 72 74 72 71 69 | 67 67 71 71 60 62 64 65 | 2/8 |
| 1 | 69 71 72 74 76 74 72 71 | 67 67 72 72 65 67 69 71 | 2/8 |
| 2 | 72 71 69 67 65 67 69 71 | 72 72 69 69 59 59 60 62 | 2/8 |
| 3 | 64 65 67 69 71 72 74 76 | 64 64 67 67 59 59 60 62 | 2/8 |

Nửa đầu còn giữ hướng. Nửa sau đổi cả chiều lẫn âm vực. Ô 0 giá rơi từ 74 về 69. Tai nghe một thang đi lên 60–65. Bourrée trên cùng đường giá, `character = "rally"`, khớp 6/8 ở ô 0 và 5/8 ở ô 1, vì lead là `_sustain(ctx.melody)`.

Ngày đi ngang lộ rõ hơn. Giá đứng yên ở 72 thì Gavotte vẫn hát 72, 72, rồi 65 67 69 71. Đường giá không có đường nét, nên đường nét tai nghe được là thang do máy viết.

Gavotte đứng ở hai chỗ:

- `1D` và mọi chương 4/4 khi `calm`: cả thân bài.
- Scherzo 6/8: đoạn B của `bach_fuga` (`volatile`) và của `bach_chaconne` (`selloff`). `_bach_contrast` trả `bach_gavotte`. Ở đây giá đang chạy, nửa ô vẫn bị thay bằng thang dẫn.

### 1.1. Cách hát để còn là Gavotte và còn là giá

Giữ nhịp: nốt đen, nốt đen staccato, bốn móc đơn. Cao độ của sáu cú đánh lấy từ giá tại móc 0, 2, 4, 5, 6, 7, gập vào thang và âm vực guitar. Quãng 3/6 ở lại bè trong, dưới những móc đơn đó. Bass vẫn là bass Gavotte: gốc ở nửa đầu, một nốt hợp âm ngân dưới bốn móc đơn.

Thang dẫn vào ô sau rút còn hai nốt, và chỉ khi giá thực sự đang đi về nốt đầu ô sau. Ô đứng yên thì bốn móc đơn nhắc lại nốt giá, hoặc một nốt lân bậc. Chúng không bịa một quãng 6.

Kế hoạch Bach ghi anacrusis Gavotte là nửa ô. Nửa ô đó đang là chỗ máy viết giai điệu. Khi bốn móc đơn mang giá, nửa ô “hát” của điệu trùng với đường giá.

---

## 2. Galop đang phát

`_classic_macro` chọn `galop` khi rally trưởng, `rel_span >= 0.012`. Trên 1D pattern này chiếm cả thân bài. `_render_galop_bar` vẽ mỗi ô giống nhau:

- Bass staccato, nốt đen ở phách 1 (gốc, có accent) và phách 3 (quãng 5). Điểm bass là `_galop_bass_points`: 4/4 là `(0, 4)`.
- Bè trong staccato từng móc đơn phách yếu, hai nốt hợp âm thay nhau. 4/4 là `(1, 3, 5, 7)`.
- Lead là `_sustain` của đường giá, nốt móc đơn legato.
- Không có móc kép. `test_sor_galop_and_mozart_variations_and_the_op9_overture` khóa `assert _sixteenths(galop.lead, 2) == []`.
- `_galop_sparkle` nhảy một quãng 3 diatonic ở móc đơn thứ hai của một nốt giá được giữ qua phách mạnh, và chỉ khi ô đang rally hoặc đường giá trong ô đi lên. Giá chạy từng móc đơn thì cú này không kêu.

Đo thân bài của một rally có khung, melody đang đi:

| Ô thân | Khớp lead / 8 móc | Móc kép |
|---|---|---|
| 0 | 6 | 0 |
| 1 | 7 | 0 |
| 2 | 7 | 0 |
| 3 (bốn móc đầu giữ một nốt, rồi đi lên) | 7 | 0 |

Ô giữ nốt là chỗ sparkle duy nhất: giá 64 ngân qua phách mạnh, móc đơn thứ hai thành 67 staccato. Phần còn lại của lead là giá, legato.

Đường giá trên lead của Galop đã bám. Cái tai không nhận ra bài Sor vì đệm. Ba bè oom-pah lặp nguyên một ô suốt thân bài: bass nốt đen gốc rồi quãng 5, bè trong chặt mỗi phách yếu. Lead legato nằm dưới nhịp chặt đó. Bài Sor viết hai bè, và tiếng phi nằm ở móc kép của giai điệu.

Cửa intro/outro trong `_galop_hits` dùng cùng tế bào staccato root/fifth và bè trong phách yếu. Sửa thân bài thì cửa phải đi theo, nếu không mở bài và thân bài là hai điệu.

---

## 3. Bài Sor thực sự có hai câu

*Galop* Op. 32 No. 6 viết ở 2/4, một dấu thăng, hai bè. Không có bè trong chặt từng phách yếu. Bố cục:

| Câu | Ô Tecla | Vai |
|---|---|---|
| Galop 1 | 1–8, lặp | Câu phi. Bass một móc đơn đúng phách. Giai điệu: móc đơn, hai móc kép, rồi hai móc đơn. Hai móc kép là tiếng ngựa. Giá đứng thì chúng nhắc nốt hợp âm. Giá đi thì chúng đi theo bước đó. |
| Galop 2, dạng thưa | 9–16, *Fine*, lặp về đầu | Câu đối đáp. Giai điệu một móc đơn rồi nghỉ một móc đơn. Bass trả lời trong chỗ nghỉ bằng một móc đơn, thường cùng một nốt. |
| Galop 2, dạng trong ảnh | 17–24, mở bằng dấu lặp, khép bằng dấu lặp | Cùng câu đối đáp, bass nhảy: móc kép trầm rồi móc đơn cao hơn một quãng 6 hoặc quãng 10. Giữa câu có một ô bốn móc kép liền (nốt vòng). Câu sau thêm nốt chromatic ở cú đáp của giai điệu. Ô cuối khép bằng hợp âm khối. |
| Câu chạy | 25–28 | Móc kép trở lại ở mức *f*. Bass gần như nghỉ. |
| Đối đáp nhắc lại | 29–32 | Cùng dạng ô 21–24, rồi *D.C. al Fine*. |

Ảnh đính kèm là ô 17–24. Một số bản in đánh số lệch hai ô. Nốt và dấu lặp khớp câu sau *Fine* của Tecla, không phải Galop trong Op. 57. Op. 57 là bài khác: hợp âm có accent, nốt ba, harmonics.

Ô 9–16 và ô 17–24 là một pattern, hai mật độ bass. Một Galop 2 là đủ. Dạng trong ảnh là dạng đầy. Dạng ô 9–16 là cùng tế bào với bass một nốt.

---

## 4. Dùng hai câu cùng lúc

Tỷ lệ trong bài là 8 ô 2/4 cộng 8 ô 2/4. Trên lưới 4/4 đó là hai ô Galop 1, rồi hai ô Galop 2, rồi lặp. Rally dài hết nhàm vì thân bài hiện là một ô oom-pah nhân ra hàng chục lần. Xen hai câu theo cặp ô thì điệu đổi đúng chỗ bài Sor đổi, và đường giá vẫn có chỗ để hát.

**Galop 1.** Mỗi phách 4/4 là một tế bào phi: bass một móc đơn đúng phách, giai điệu móc đơn rồi hai móc kép rồi phần còn lại của phách. Hai móc kép lấy bước giá tại đó. Giá đứng thì hai móc kép nhắc nốt hợp âm, điệu vẫn phi. Bỏ bè trong chặt phách yếu.

**Galop 2.** Giá đặt lên những cú giai điệu thực sự kêu. Chỗ nghỉ của câu đối đáp giữ là nghỉ. Bass trả lời trong chỗ nghỉ. Dạng đầy dùng cú nhảy móc kép trầm lên móc đơn một quãng 6 hoặc quãng 10. Ô đỉnh câu được một nốt vòng bốn móc kép quanh nốt giá. Ô nào giá có nhiều cao độ khác nhau thì hát chuỗi móc kép kiểu ô 25–28, bass thưa. Ô nào chỉ vài bước thì giữ câu đối đáp.

Lead của Galop 1 và các cú giai điệu của Galop 2 vẫn là đường giá. Đổi nhịp và đổi mật độ. Không đổi họ pattern trên bộ chọn: `galop` vẫn là cửa rally trưởng `rel_span >= 0.012`. Hai câu là hai cách dệt trong cùng pattern, xoay theo cặp ô, giống cách `_settle_galop` đã xoay galop với study ở tầng form. Tầng form đó giữ nguyên. Study vẫn đứng hai đầu khi cả chương là galop.

Cửa intro và outro dùng cùng hai câu, theo bước đã có trong `_galop_hits`. Bước mở nghiêng về Galop 1. Bước dẫn vào thân bài và bước khép có thể là Galop 2, để cửa không lặp một tế bào staccato bốn lần.

Test phải đổi theo:

- `assert _sixteenths(galop.lead, 2) == []` trong `test_sor_galop_and_mozart_variations_and_the_op9_overture`. Galop 1 có móc kép trên lead.
- Các assert bass thân bài chỉ còn `(0.0, 1.0)` và `(2.0, 1.0)`, staccato, gốc rồi quãng 5. Galop 1 rút bass xuống một móc đơn đúng phách. Galop 2 đổi bass thành cú trả lời trong chỗ nghỉ.
- Assert bè trong ở `0.5, 1.5, 2.5, 3.5`, staccato có accent. Bè trong đó rời thân bài.
- `_settle_galop` và các test “galop giữa ABA”, “tuần chẵn”, “scherzo đưa galop vào trio” nhận diện galop bằng bass staccato tại `0.0` và `2.0`. Nhận diện phải đọc tế bào mới, nếu không một thân bài đã xen Galop 2 sẽ bị coi là hết galop và bị sơn lại thành study.
