# Tên pattern: Cathedral và Torroba

Tên in trên chart là chuỗi trong `backend/app/sonify/program.py` (`_PATTERN_TITLE`) và `src/sonify/program.ts` (`PATTERN_NAMES`). Id trong code giữ nguyên. Tên lấy từ tác phẩm, viết hoa chữ đầu, không dấu. Một tên đã thuộc nhà khác thì pattern mới không dùng lại tên đó.

Tên chương không cần một vùng riêng trên màn hình. Ghi cạnh title đang có, hoặc ngay dưới title đó. Title đang có là tên tác phẩm, ví dụ `Sonatina HVN 23/10 in D`. Dòng chương là pattern của câu đang hát, cùng cỡ chữ nhỏ hơn title.

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

Chuỗi dòng chương đổi theo. Ví dụ trong `backend/tests/test_program.py`:

| Trước | Sau |
|---|---|
| Prelude — Andante — Tremolo | Cathedral — Andante — Tremolo |
| Prelude — Andante | Cathedral — Andante |
| Prelude — Tremolo — Prelude | Cathedral — Tremolo — Cathedral |

`PATTERN_NAMES` thêm `Cathedral`. `Prelude` ở lại cho Bach và Villa.

Chỗ sửa khi thực hiện:

- `backend/app/sonify/program.py`: `"preludio": "Cathedral"`, và câu ví dụ Prelude — Andante — Tremolo trong `pattern_form`.
- `backend/tests/test_program.py`: bốn assert của `pattern_form` với ensemble `barrios`.
- `src/sonify/program.ts`: thêm `Cathedral` vào `PATTERN_NAMES`.

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

Tám kiểu trong mục 4 của [`docs/sonify-guitar-torroba-phrase-plan.md`](./sonify-guitar-torroba-phrase-plan.md) là cách đánh bên trong pattern đã khóa. Chúng không thêm id vào `_FAMILY`, và không vào `_PATTERN_TITLE`. Dòng cạnh hoặc dưới title chỉ ghi pattern cha (Castillo, Sonatina, Fandanguillo, Danza). Tám kiểu không ghi lên dòng đó.

Tên dưới đây thay cho “Kiểu 1” … “Kiểu 8” trong code và trong kế hoạch. Mỗi tên một hoặc hai từ, cùng kiểu với catalog.

| Số cũ | Tên | Pattern cha | Nguồn |
|---|---|---|---|
| 1 | Arpeggio | `sonatina` | *Sonatina* I, rải sáu móc kép, bass thứ tư ngân sang chu kỳ sau |
| 2 | Rasgueado | `sonatina`, `fandanguillo` | *Sonatina* I, hợp âm quạt rồi bốn móc kép lặp |
| 3 | Pizzicato | `sonatina` | *Sonatina* I, `pizz.`, mô-típ rồi nốt ngân ở câu đóng |
| 4 | Dialogue | `sonatina` | *Sonatina* I, hai ô mở đầu, câu gọi và câu đáp |
| 5 | Arch | `fandanguillo` | *Suite Castellana* I, vòm bốn ô: quạt, giá ở bè trầm, rồi giao lên bè cao |
| 6 | Bounce | `danza` | *Suite Castellana* III, chùm ba trên hợp âm ngân |
| 7 | Arada | `castillo` | *Suite Castellana* II, câu đầu *Arada*, năm ô |
| 8 | Harmonics | `castillo` | *Arada* câu 2, hợp âm chấm dôi và `Arm. 8` |

Arpeggio ở đây là nhãn kiểu của Sonatina. Villa đã in **Arpeggio** trên chart (`villa_pattern`), nên tên này không đưa vào `PATTERN_NAMES`.

Kiểu 2 và kiểu 5 đều có rasgueado. Kiểu 2 giữ tên **Rasgueado** vì đó là cả hình. Kiểu 5 là vòm bốn ô của Fandanguillo, tên **Arch**.

Kiểu 7 và kiểu 8 đều từ *Arada*. Kiểu 7 là cả câu năm ô, tên **Arada**. Kiểu 8 là câu harmonics ngay sau, tên **Harmonics**.
