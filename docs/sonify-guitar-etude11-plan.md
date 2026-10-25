# Kế hoạch pattern `etude11` — Villa-Lobos, *Étude No. 11*, đoạn Animé

> **Trạng thái**: đã chốt ô nhạc, chưa render. *Étude No. 1* (`villa_pattern`, rally, band `mf`) nghe tạm ổn và giữ nguyên.
>
> **Nguồn**: trang giữa bản Eschig, khoảng ô 52–60, nhịp 2/4, mỗi nốt đen một chùm 6. Đối chiếu với tab cùng đoạn (*Poco meno*, *bien rythmé*).

Đoạn này là vòm sextuplet, không phải khối ba nốt của `chord_melody`. `chord_melody` giữ vai thánh ca cho chương chậm, `calm`, và band `p`. Pattern mới chỉ thay `villa_pattern` khi Lobos đang `volatile` ở 4/4.

## 1. Vòm trên tổng phổ

Một nốt đen, sáu cú, đọc từ trái sang phải:

| Cú | Trên bản | Vai |
|---|---|---|
| 1 | Ngón cái đánh kép, nhấn `>` hoặc `sfz` | Gốc dây trầm, cộng một nốt cùng họ cao hơn một quãng 8 |
| 2, 3 | Cùng một cao độ, hai dây | Nốt trang trí, đi lên |
| 4 | Dây mi buông | Đỉnh vòm, lặp mọi chùm |
| 5, 6 | Đúng cú 3 rồi cú 2 | Đi xuống |

Nốt trang trí đổi theo hợp âm (La, Fa♯, Sol, Mi trong đoạn mẫu). So với mi buông ở cú 4, La là quãng 5 dưới. Họa âm ở cuối trang là màu của một ô kết, không đưa vào pattern. Không chép dây mi buông: nó chỉ sống ở Mi thứ.

## 2. Ô nhạc đã chốt

Id pattern: `etude11`. Profile playability: `villa_etude11`.

Một ô 4/4 có bốn chùm, mỗi chùm một nốt đen. Nhịp 2/4 của bản gốc chỉ là hai chùm một ô, nên không thêm meter. Giai điệu là đường giá, lấy ở móc đơn đầu của nốt đen. Móc đơn sau trong cùng nốt đen chờ chùm kế.

| Cú | Beat trong nốt đen | Bè | Cao độ | Độ dài | Lực |
|---|---|---|---|---|---|
| 1 | 0 | Cao | Nốt giá của phách | 1/2 phách (ba cú), nhấn | Hairpin câu: mở 60, đỉnh 72 |
| 1 | 0 | Trầm | Gốc hợp âm | Cả nốt đen, nhấn | Dưới nốt hát |
| 2 | 1/6 | Trung | Nốt trang trí | 1/6 phách | 50–54 |
| 3 | 2/6 | Trung | Cùng nốt trang trí | 1/6 phách | 50–54 |
| 4 | 1/2 | Cao | Nhắc lại đúng nốt giá | 1/2 phách | Thấp hơn cú 1 khoảng 8 |
| 5 | 4/6 | Trung | Cùng nốt trang trí | 1/6 phách | 50–54 |
| 6 | 5/6 | Trung | Cùng nốt trang trí | 1/6 phách | 50–54 |

Cú 1 của bè cao không ngân hết nốt đen: cú 4 gảy lại cùng cao độ, nên nốt đầu nhường chỗ ở giữa phách. Bass không gảy lại. Bè trung nghỉ ở cú 1 và cú 4. Bốn cú trung cùng một cao độ trong chùm.

Nốt trang trí, theo thứ tự:

1. Quãng 5 đúng dưới giai điệu (`melody - 7`), nếu thuộc hợp âm, `bass < nốt < giai điệu`, và bộ ba bass–trang trí–giai điệu chơi được.
2. Không có quãng 5 thì quãng 3 dưới (`melody - 3` hoặc `melody - 4`), cùng các điều kiện đó.
3. Giai điệu giữ nguyên thì giữ nốt trang trí nếu nó còn hợp lệ. Giai điệu lên thì chọn ứng viên hợp lệ cao hơn nốt trước. Giai điệu xuống thì chọn ứng viên thấp hơn.

Ở 100 BPM mật độ khoảng 10 cú mỗi giây. Dày hơn tremolo Barrios ở 120, đúng cửa `volatile`.

## 3. Cửa gọi

Chỉ Lobos, chỉ 4/4, chỉ khi tempo trên 72 và mood là `volatile`.

| Cửa | Kết quả |
|---|---|
| `selloff`, `section.trio`, `section.bridge` | `thumb_cantabile`, như hiện tại |
| `bpm <= 72`, `calm`, hoặc đa số ô band `p` | `chord_melody` |
| `rally` | `villa_pattern` (*Étude No. 1*) |
| `volatile`, 4/4, `bpm > 72` | `etude11` |
| 6/8, kể cả `volatile` | `villa_pattern` |
| Chương chậm 3/4 | `chord_melody` hoặc `thumb_cantabile`, không sextuplet |

Bài có khung khóa một pattern cho cả thân bài. Phiên `volatile` 4/4 vì thế hát `etude11` từ câu mở. Bài không khung vẫn giữ câu thân đầu ở `bpm >= 90` là `villa_pattern`; `etude11` bắt đầu từ câu thân thứ hai.

`_contrast_pattern` không đổi. Trio và bridge của Lobos không nằm trên 4/4 `volatile`.

## 4. Những lớp không phủ lên `etude11`

- Không đoạn scale *Étude No. 7*. Cửa scale của Villa (`volatile`, band `f`, câu lên đủ `MIN_RISE`) bỏ qua câu đã chọn `etude11`.
- Không tresillo `3+3+2`. Tresillo chỉ còn trên câu `villa_pattern` của bài không khung. Phiên có khung mà mood là `volatile` không còn ô `villa_pattern` để nhấn.
- Không campanella kéo dài nốt. Bốn cú trung là bốn lần gảy cùng cao độ. Kéo dài sẽ chồng lên cú sau và vỡ lưới.
- Câu `etude11` đi sang pattern khác: chùm cuối chỉ còn giai điệu và bass, bè trung nghỉ. Tổng số thời gian của ô không đổi.

## 5. Lưới thời gian

Playhead guitar hiện đếm móc kép (`beat * 4`, `_start16`, `_dur16`, `_fill`, `_spell16`). Một cú dài 1/6 phách không phải số nguyên trên lưới đó, và `_note_type` chưa có giá trị này.

Chương nào có ít nhất một câu `etude11` thì `Score.divisions = 12`:

| Giá trị | Đơn vị |
|---|---|
| Nốt đen | 12 |
| Móc đơn | 6 |
| Móc kép | 3 |
| Một cú trong chùm 6 | 2 |

MusicXML viết cú đó là móc kép trong bộ 6 ăn 4 (`type` = `16th`, `time-modification` actual 6 / normal 4). Playback đọc `duration`, không đọc tên nốt. Rest 1/6 của bè trung đi cùng đường này.

`_fill` không được cắt một cú 1/6 thành móc kép. Ô `etude11` phải được phát đủ, kể cả rest ở cú 1 và cú 4 của bè trung, trước khi playhead chung chạy.

## 6. Chỗ sửa khi làm

- `backend/app/sonify/guitar_villa.py`: render một chùm và một ô.
- `backend/app/sonify/guitar_patterns.py`: đăng ký `etude11` trong `_FAMILY` và `_PROFILE`; cửa trong `_select_body` và `_dominant_pattern`; nhánh render; `divisions = 12`; tắt scale trên câu này; thở ở chùm cuối khi sang pattern khác.
- `backend/app/sonify/musicxml.py`: type và tuplet cho duration 1/6.
- `docs/sonify-classical-guitar.md`: `etude11` là sextuplet Animé. `chord_melody` thôi mang tên *Étude No. 11*. Hành vi `chord_melody` không đổi.
- `backend/tests/test_sonify_guitar.py`: các cửa ở mục 3, lưới một ô ở mục 2, quãng 5 khi hợp âm có, `divisions == 12`, playability, không tresillo, không scale, export MusicXML.

## 7. Ngoài phạm vi

Không đổi `villa_pattern`, `chord_melody`, `thumb_cantabile`. Không thêm nhịp 2/4. Không họa âm. Không chép pedal mi buông.
