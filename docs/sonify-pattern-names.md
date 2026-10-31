# Tên pattern: Cathedral và Torroba

Chuỗi ghi vào file audio ra từ `_PATTERN_TITLE` trong `backend/app/sonify/program.py`, qua `pattern_title`. Ngoại lệ duy nhất: `thumb_cantabile` khi ensemble là `villa` thành Prelude, không lấy mục Cantabile trong bảng. `PATTERN_NAMES` trong `src/sonify/program.ts` là tập để client nhận ra chuỗi đó. Id trong code giữ nguyên. Tên lấy từ tác phẩm, viết hoa chữ đầu, không dấu. Một tên đã thuộc nhà khác thì pattern mới không dùng lại tên đó.

Không thêm vùng riêng cho tên chương. Chuỗi đó là tên của cả chương, tức `pattern_form` đã ghi cùng file audio. Nó không đổi theo từng `Phrase`. `formatMovement` trong `src/sonify/program.ts` giữ hậu tố nhịp và BPM, ví dụ `Cathedral — Andante — Tremolo (4/4, 96 BPM)`, hoặc `Finale: …` khi có tiền tố Finale.

Guitar một chương: `pieceCopy` đặt tên pattern vào title (`Cathedral HVN 23/10 in D`) và để `movement` là `null`. Không có dòng thứ hai.

Guitar nhiều chương, dòng đó là `movement` của `pieceCopy`:

- Lúc intro, `PieceTitle` đặt dòng dưới title, cỡ body, dòng nhạc cụ ở giữa.
- Lúc đang phát, `playingLines` xếp title và dòng đó cùng một style, ở góc dưới chart.

Đợt đổi Cathedral không sửa `pieceCopy`, `playingLines`, hay `PieceTitle`. Chỉ đổi chuỗi của `preludio`.

---

## 1. Barrios: Prelude thành Cathedral

Pattern `preludio` của Barrios viết theo *La Catedral — Preludio Saudade*. Tên in ra đổi từ **Prelude** thành **Cathedral**.

Id vẫn là `preludio`. Hàm render, profile `barrios_preludio`, và cửa `_catedral_preludio` giữ nguyên.

Hai Prelude khác giữ nguyên:

| Nguồn | Id | Tên in |
|---|---|---|
| Barrios, *La Catedral* | `preludio` | **Cathedral** |
| Bach | `bach_prelude` | Prelude |
| Villa, *Prélude* No. 1 | `thumb_cantabile` khi ensemble là `villa` | Prelude |

Chuỗi `preludio` của Barrios đổi theo. Tám assert trong `backend/tests/test_program.py` sẽ gãy. Ba assert còn lại trong `test_long_barrios_movements_walk_a_pattern_row` không chứa Prelude của Barrios, giữ nguyên: `Andante — Cantabile — Andante`, `Polka — Waltz — Polka`, `Tremolo — Andante — Tremolo`.

| Trước | Sau | Chỗ |
|---|---|---|
| Prelude — Andante — Tremolo | Cathedral — Andante — Tremolo | `pattern_form` |
| Prelude — Andante | Cathedral — Andante | `pattern_form` (hai assert) và `guitar_movement_name` với `week_spec(2)`, chương tuần gồm 2 phiên |
| Prelude — Tremolo — Prelude | Cathedral — Tremolo — Cathedral | `pattern_form` |
| Prelude — Andante — Prelude | Cathedral — Andante — Cathedral | `guitar_movement_name` với `opening`, `week_spec(4)` và `week_spec(5)`: chương mở, chương tuần 4 phiên và 5 phiên |

Bốn assert `pattern_form` nằm trong `test_pattern_form_keeps_three_names_and_centers_a_longer_row`. Bốn assert ghi vào file audio rồi in lên chart nằm trong `test_long_barrios_movements_walk_a_pattern_row`, các lời gọi `guitar_movement_name` với `opening`, `week_spec(2)`, `week_spec(4)` và `week_spec(5)`.

`PATTERN_NAMES` thêm `Cathedral`. `Prelude` ở lại, vì `isPatternForm` tách bằng ` — `. Thiếu `Cathedral` thì suite Barrios mất tên điệu và chỉ còn nhịp hoặc `Finale`.

Bach (`bach_prelude`) và Villa (`thumb_cantabile` khi ensemble là `villa`) giữ `Prelude`. Hai assert Villa (`Chord Melody — Prelude — Chord Melody`, `Arpeggio — Prelude — Arpeggio`) và mọi assert Bach không nằm trong đợt này.

Chỗ sửa khi thực hiện:

- `backend/app/sonify/program.py`: `"preludio": "Cathedral"`. Docstring của `pattern_form` có ba chỗ ví dụ Barrios: `Prelude — Andante — Tremolo`, câu “plays Prelude, Andante, Andante, Prelude”, và `Prelude — Andante — Prelude`. Cả ba thành Cathedral.
- `backend/tests/test_program.py`: bốn assert `pattern_form` và bốn assert `guitar_movement_name` ở trên.
- `src/sonify/program.ts`: thêm `Cathedral` vào `PATTERN_NAMES`. Giữ `Prelude`.

---

## 2. Torroba: bốn pattern nền

Bốn id đã hát. Tên in khóa như bảng. Cột cuối là các cách gọi dễ lẫn, không dùng.

| Id | Tên in | Tác phẩm | Không dùng |
|---|---|---|---|
| `castillo` | Castillo | *Castillos de España*; nét ngân của *Sonatina* Andante | Castle, Castles |
| `sonatina` | Sonatina | *Sonatina* chương I và III | Sonata |
| `fandanguillo` | Fandanguillo | *Suite Castellana* I | Fandango |
| `danza` | Danza | *Suite Castellana* III | Dance |

Dance đã là `elogio_pizz` của Brouwer. Fandango là điệu khác với Fandanguillo.

Chuỗi hiện có trong `_PATTERN_TITLE` và `PATTERN_NAMES` đã đúng bốn tên này. Không thêm bản dịch.

---

## 3. Torroba: tám kiểu mới

Tám kiểu trong mục 4 của [`docs/sonify-guitar-torroba-phrase-plan.md`](./sonify-guitar-torroba-phrase-plan.md) là cách đánh bên trong pattern đã khóa. Chúng không thêm id vào `_FAMILY`, và không vào `_PATTERN_TITLE`, nên không xuất hiện trên dòng chương. Dòng chương của Torroba thường là một pattern cha cộng nhịp, ví dụ `Sonatina (4/4, 96 BPM)`, vì một chương khóa một pattern. Khi chương là một hàng pattern, dòng vẫn là cả `pattern_form`, không rút còn một tên.

Tên dưới đây là nhãn cho code. File kế hoạch vẫn đánh số Kiểu 1 … Kiểu 8 cho đến khi kế hoạch đó được sửa. Mỗi tên một hoặc hai từ.

| Số cũ | Tên | Pattern cha | Nguồn |
|---|---|---|---|
| 1 | Arpeggio | `sonatina` | *Sonatina* I, rải sáu móc kép, bass thứ tư ngân sang chu kỳ sau |
| 2 | Rasgueado | `sonatina`, `fandanguillo` | *Sonatina* I, hợp âm quạt rồi bốn móc kép lặp |
| 3 | Pizzicato | `sonatina` | *Sonatina* I, `pizz.`, mô-típ rồi nốt ngân ở câu đóng |
| 4 | Dialogue | `sonatina` | *Sonatina* I, hai ô mở đầu, câu gọi và câu đáp |
| 5 | Arch | `fandanguillo` | *Suite Castellana* I, vòm bốn ô: quạt, giá ở bè trầm, rồi giao lên bè cao |
| 6 | Bounce | `danza` | *Suite Castellana* III, chùm ba trên hợp âm ngân |
| 7 | Arada | `castillo`, BPM ≤ 72 | *Suite Castellana* II, câu đầu *Arada*, năm ô |
| 8 | Float | `castillo`, BPM ≤ 72 | *Arada* câu 2: hợp âm chấm dôi, hai tiếng `Arm. 8`, câu hát sang ô kế |

Arpeggio ở đây là nhãn kiểu của Sonatina. Villa đã in **Arpeggio** trên chart (`villa_pattern`), nên tên này không đưa vào `PATTERN_NAMES`.

Kiểu 2 và kiểu 5 đều có rasgueado. Kiểu 2 giữ tên **Rasgueado** vì đó là cả hình. Kiểu 5 là vòm bốn ô của Fandanguillo, tên **Arch**.

Kiểu 7 và kiểu 8 đều lấy nét từ *Arada*, và chỉ vào `castillo` khi `ctx.bpm <= 72`. Bốn bullet dưới chỉ nhắc cách chia độ dài. Cửa chọn đầy đủ là bước 6 và bước 7 của mục 4.0 trong [`docs/sonify-guitar-torroba-phrase-plan.md`](./sonify-guitar-torroba-phrase-plan.md): câu `n` lẻ là lưới nền, `k` chỉ đếm các câu `n` chẵn, và câu liền trước đã chọn cùng số kiểu thì câu này về lưới nền.

- `k` chẵn và câu dài ít nhất 5 ô: kiểu 7 trên năm ô đầu.
- `k` chẵn và câu dài 2, 3 hoặc 4 ô: kiểu 8 trên hai ô đầu, để khỏi cắt năm ô của câu đầu *Arada*.
- `k` lẻ và câu dài ít nhất 2 ô: kiểu 8 trên hai ô đầu, dù câu trước không phải kiểu 7.
- Câu dài 1 ô, hoặc `ctx.bpm > 72`: lưới nền.

Tên kiểu 8 là **Float**, câu hát bồng bềnh sang ô kế. Không gọi **Harmonics**. Plan đã có cửa vận tốc 48 khi nốt ngân trùng nút harmonic. Hai tiếng `Arm. 8` của kiểu 8 ngắn hơn hai phách, nên câu phẳng ra 58, không ra 48. Hàm và comment sau này không được đọc tên kiểu thành cửa vận tốc đó.
