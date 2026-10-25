# Kế hoạch hai pattern mới của Lobos: `etude1` và `etude11`

> **Trạng thái**: đã render `etude1` và `etude11`.
>
> `villa_pattern` giữ nguyên tiếng arpeggio móc đơn đã nghe (ngón cái ở phách 1 và phách 3, giai điệu ngân riêng). Tài liệu thôi gọi nó là *Étude No. 1*. `chord_melody` và `thumb_cantabile` không đổi hành vi. `chord_melody` thôi mang tên *Étude No. 11*.

Hai pattern mới chỉ dành cho Lobos ở 4/4, tempo trên 72.

| Cửa | Pattern |
|---|---|
| `selloff`, `section.trio`, `section.bridge` | `thumb_cantabile` |
| `bpm <= 72`, `calm`, hoặc đa số ô band `p` | `chord_melody` |
| `rally` | `etude1` |
| `volatile` | `etude11` |
| 6/8, mọi mood | `villa_pattern` |
| Chương chậm 3/4 | `chord_melody` hoặc `thumb_cantabile` |

Bài có khung khóa một pattern cho cả thân bài, kể cả câu mở. Bài không khung vẫn giữ câu thân đầu ở `bpm >= 90` là `villa_pattern`. Pattern mới bắt đầu từ câu thân thứ hai. `_contrast_pattern` không đổi.

---

## 1. `etude1` — *Étude No. 1*, vòng 16 móc kép

Nguồn: ô đầu bản Eschig, *Allegro non troppo*, nhịp 4/4. Vòng tay phải lặp cả bài. Hợp âm đổi thì chỉ đổi nốt bấm. Dòng `simile la main droite` giữ đúng vòng này. Vòng đủ là `p i p i p m i a m a i m p i p i`.

Id: `etude1`. Profile: `villa_etude1`.

Một ô 4/4 là một vòng: bốn phách, mỗi phách bốn móc kép. Ở 100 BPM mật độ khoảng 7 cú mỗi giây. Lưới móc kép hiện có chứa đủ vòng này. Chương chỉ có `etude1` thì `divisions = 4`.

| Cú | Phách | Ngón trên bản | Bè | Cao độ | Độ dài |
|---|---|---|---|---|---|
| 1 | 0.00 | p | Trầm | Gốc hợp âm, ngân hết ô | 4 phách |
| 2 | 0.25 | i | Trung | Mức 1 của thang hợp âm | 1 móc kép |
| 3 | 0.50 | p | Trung | Mức 0 | 1 móc kép |
| 4 | 0.75 | i | Trung | Mức 2 | 1 móc kép |
| 5 | 1.00 | p | Trung | Mức 1 | 1 móc kép |
| 6 | 1.25 | m | Trung | Mức 3 | 1 móc kép |
| 7 | 1.50 | i | Trung | Mức 2 | 1 móc kép |
| 8 | 1.75 | a | Cao | Nốt giá đang ngân ở phách 2 | 1 móc kép |
| 9 | 2.00 | m | Trung | Mức 3, sát dưới giai điệu | 1 móc kép |
| 10 | 2.25 | a | Cao | Nốt giá đang ngân ở phách 3 | 1 móc kép |
| 11 | 2.50 | i | Trung | Mức 2 | 1 móc kép |
| 12 | 2.75 | m | Trung | Mức 3 | 1 móc kép |
| 13 | 3.00 | p | Trung | Mức 1 | 1 móc kép |
| 14 | 3.25 | i | Trung | Mức 2 | 1 móc kép |
| 15 | 3.50 | p | Trung | Mức 0 | 1 móc kép |
| 16 | 3.75 | i | Trung | Mức 1 | 1 móc kép |

Những ngón `p` sau cú 1 không phải bass mới. Chúng là bè trung. Bass chỉ gảy một lần. Bản ghi `p` ở đầu ô, không nhấn `sfz`.

Thang bè trung là các âm hợp âm thỏa `bass < nốt < giai điệu`, xếp từ thấp lên cao, lấy tối đa bốn mức. Thiếu mức thì dùng mức cao nhất đang có. Chỉ số trong bảng là chỉ số của thang đó: `0` thấp nhất, `3` sát giai điệu. Trên ô Mi thứ của bản, bốn mức là Si2, Mi3, Sol3, Si3, và hai nốt cao đều là Mi4.

Giá đứng yên thì cú 8 và cú 10 cùng cao độ, đúng bản. Giá đổi thì cú 8 lấy nốt của phách 2, cú 10 lấy nốt của phách 3. Lực hai nốt cao theo hairpin câu (mở 60, đỉnh 72). Bass dưới giai điệu. Bè trung phẳng, khoảng 50–56.

Bè trung nghỉ ở cú 1, 8 và 10. Bè cao nghỉ mọi cú còn lại. Khi câu `etude1` sang pattern khác, bốn móc kép cuối ô chỉ còn bass. Tổng thời gian của ô không đổi.

Không tresillo. Không đoạn scale *Étude No. 7*. Không đoạn slur và không họa âm ở cuối bài.

---

## 2. `etude11` — *Étude No. 11*, đoạn Animé

Nguồn: trang giữa bản Eschig, khoảng ô 52–60, nhịp 2/4. Mỗi nốt đen là một chùm 6. Đối chiếu với tab cùng đoạn (*Poco meno*, *bien rythmé*).

Id: `etude11`. Profile: `villa_etude11`.

Đây là vòm sextuplet. Một ô 4/4 có bốn chùm. Nhịp 2/4 của bản gốc chỉ là hai chùm một ô, nên không thêm meter. Giai điệu là đường giá, lấy ở móc đơn đầu của nốt đen. Móc đơn sau trong cùng nốt đen chờ chùm kế.

Một nốt đen trên tổng phổ:

| Cú | Trên bản | Vai |
|---|---|---|
| 1 | Ngón cái đánh kép, nhấn `>` hoặc `sfz` | Gốc dây trầm, cộng một nốt thứ hai |
| 2, 3 | Cùng một cao độ, hai dây | Nốt trang trí, đi lên |
| 4 | Dây mi buông | Đỉnh vòm cố định, lặp mọi chùm |
| 5, 6 | Đúng cú 3 rồi cú 2 | Đi xuống |

Nốt thứ hai của ngón cái chỉ là quãng 8 của gốc ở những ô toàn nốt Mi. Ở ô hợp âm đổi, nốt đó là quãng 8 dưới của nốt trang trí, bass vẫn là Mi. Ô đã chốt chỉ giữ gốc. Nốt ngón cái thứ hai không vào pattern.

Nốt trang trí đổi theo hợp âm (La, Fa♯, Sol, Mi trong đoạn mẫu). So với mi buông ở cú 4, La là quãng 5 dưới. Họa âm cuối trang không đưa vào pattern. Cú 4 của ô đã chốt gảy lại nốt giá, nhẹ hơn cú 1 khoảng 8. Đó là đỉnh vòm khi bài không ở Mi, thay cho dây mi buông.

Ô đã chốt:

| Cú | Beat trong nốt đen | Bè | Cao độ | Độ dài | Lực |
|---|---|---|---|---|---|
| 1 | 0 | Cao | Nốt giá của phách | 1/2 phách (ba cú), nhấn | Hairpin câu: mở 60, đỉnh 72 |
| 1 | 0 | Trầm | Chỉ gốc hợp âm | Cả nốt đen, nhấn | Dưới nốt hát |
| 2 | 1/6 | Trung | Nốt trang trí | 1/6 phách | 50–54 |
| 3 | 2/6 | Trung | Cùng nốt trang trí | 1/6 phách | 50–54 |
| 4 | 1/2 | Cao | Nhắc lại đúng nốt giá, thay mi buông | 1/2 phách | Thấp hơn cú 1 khoảng 8 |
| 5 | 4/6 | Trung | Cùng nốt trang trí | 1/6 phách | 50–54 |
| 6 | 5/6 | Trung | Cùng nốt trang trí | 1/6 phách | 50–54 |

Cú 1 của bè cao nhường chỗ cho cú 4. Bass chỉ là gốc, ngân hết nốt đen, không thêm quãng 8. Cú 4 trùng cao độ với cú 1 khi giá đứng yên. Lực thấp hơn khoảng 8 để hai cú không dính thành một nốt bị cắt. Bè trung nghỉ ở cú 1 và cú 4. Bốn cú trung cùng một cao độ trong chùm.

Nốt trang trí, theo thứ tự:

1. Quãng 5 đúng dưới giai điệu (`melody - 7`), nếu thuộc hợp âm, `bass < nốt < giai điệu`, và bộ ba bass–trang trí–giai điệu chơi được.
2. Không có quãng 5 thì quãng 3 dưới (`melody - 3` hoặc `melody - 4`), cùng các điều kiện đó.
3. Giai điệu giữ nguyên thì giữ nốt trang trí nếu nó còn hợp lệ. Giai điệu lên thì chọn ứng viên hợp lệ cao hơn nốt trước. Giai điệu xuống thì chọn ứng viên thấp hơn.

Ở 100 BPM mật độ khoảng 10 cú mỗi giây.

Playhead guitar hiện đếm móc kép (`beat * 4`). Một cú dài 1/6 phách không phải số nguyên trên lưới đó, và `_note_type` chưa có giá trị này. Chương nào có ít nhất một câu `etude11` thì `Score.divisions = 12`:

| Giá trị | Đơn vị |
|---|---|
| Nốt đen | 12 |
| Móc đơn | 6 |
| Móc kép | 3 |
| Một cú trong chùm 6 | 2 |

MusicXML viết cú đó là móc kép trong bộ 6 ăn 4 (`type` = `16th`, `time-modification` actual 6 / normal 4). Playback đọc `duration`. Rest 1/6 của bè trung đi cùng đường này. `_fill` không được cắt một cú 1/6 thành móc kép. Ô `etude11` phải được phát đủ trước khi playhead chung chạy. Móc kép của `etude1` vẫn đúng khi `divisions = 12`, vì một móc kép bằng 3 đơn vị.

Không đoạn scale *Étude No. 7*. Không tresillo `3+3+2`. Không campanella kéo dài: bốn cú trung là bốn lần gảy cùng cao độ. Câu `etude11` sang pattern khác thì chùm cuối chỉ còn giai điệu và bass.

---

## 3. Chỗ sửa khi làm

- `backend/app/sonify/guitar_villa.py`: render `etude1` và `etude11`.
- `backend/app/sonify/guitar_patterns.py`: đăng ký cả hai trong `_FAMILY` và `_PROFILE`. Cửa `rally` và `volatile` trong `_select_body` và `_dominant_pattern`. Nhánh render. `divisions` theo mục 2. Tắt scale và tresillo trên hai pattern này. Thở ở cuối câu khi sang pattern khác.
- `backend/app/sonify/musicxml.py`: type và tuplet cho duration 1/6.
- `docs/sonify-classical-guitar.md`: `villa_pattern` là arpeggio móc đơn. `etude1` là vòng 16 móc kép. `etude11` là sextuplet Animé. `chord_melody` giữ hành vi, bỏ tên *Étude No. 11*.
- `backend/tests/test_sonify_guitar.py`: cửa gọi, một ô của mỗi pattern, quãng 5 của `etude11` khi hợp âm có, bốn mức của `etude1`, `divisions`, playability, không tresillo, không scale, export MusicXML.

## 4. Ngoài phạm vi

Không đổi tiếng của `villa_pattern`, `chord_melody`, `thumb_cantabile`. Không thêm nhịp 2/4. Không họa âm. Không chép nốt ngón cái thứ hai và không chép pedal mi buông của *Étude No. 11*. Không chép dây bấm cố định của ô Mi thứ trong *Étude No. 1*.
