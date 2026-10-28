# Điều Chỉnh Biên Độ Scale Theo Thể Loại

> **Trạng thái**: đề xuất, chưa viết vào engine.
> **Tài liệu liên kết**: [`docs/sonify-guitar-scales-plan.md`](./sonify-guitar-scales-plan.md) Mục 2.6, [`docs/sonify-guitar-bach-suite-plan.md`](./sonify-guitar-bach-suite-plan.md).
> **Mục tiêu**: câu scale vẫn là một hairpin một chiều, nhưng bước vào, biên độ và trần theo thể loại. Điểm đo là velocity bè cao sau sóng volume, để câu chạy không cắt khỏi chỗ nhỏ của câu nhạc.

---

## 1. Chỗ đang gắt

Ô 27 của Prelude trong MSN 1W Bach (Guitar, 22–28/10/2026) là mẫu. Vùng quanh đó đang ở velocity khoảng 45–56. Chín móc kép đầu ô bị in lại thành 84, 80, 75, 71, 67, 63, 58, 54, rồi nốt trụ đứng ở 62.

Đó là một scale đi xuống trên `bach_prelude`. Cửa sổ Baroque là `54…84`. Công thức mở sóng xuống của nhóm Hát và Baroque là

```text
open = min(loud, max(prev + 8, 72))
```

`prev` lấy nốt lead viết trước sóng volume. Nốt đó đã là 76, nên `76 + 8` chạm trần 84. Sóng volume đã kéo ô xuống khoảng 56. Hairpin được in lại sau sóng, nên tai nghe một cú nhảy khoảng +28, tức ba bậc nhấn, trên một câu dài hai phách.

Trong thang của engine, giai điệu thường là 64 và đỉnh câu `_MELODY_APEX` là 72. Một bậc nhấn là khoảng 8. Câu scale của Bach trong bản gốc là chính chất nhạc. Bản guitar của Prelude BWV 1007 giữ dòng chạy đều. Chỗ to hơn là cột mốc hòa âm và câu kết, không phải từng cụm móc kép.

Cùng công thức này, Villa và Sor ở nhóm Động năng còn mở sóng xuống ngay tại 90 khi câu rơi vào phách mạnh.

## 2. Giữ cách xếp theo thể loại

Họ pattern vẫn đúng hơn một cửa sổ cho mỗi composer. Brouwer là mốc đang nghe ổn, nên cửa sổ Hát `52…82` và étude Động năng `46…90` giữ nguyên, kể cả bước vào `+8` và cách étude mở tại trần trên phách mạnh.

Các thể loại còn lại thu hẹp. Villa bỏ kiểu mở sóng xuống tại 90. Sor cũng vậy: câu chạy lớn dần về đích. Barrios vẫn rộng hơn Sor một chút, vì preludio có chỗ ngân và thở. Bach hẹp nhất. Chaconne rộng hơn các vũ điệu vì đó là đoạn hùng biện.

## 3. Mức đề xuất

Ba số đo từ velocity bè cao **sau** sóng volume của nốt lead liền trước. `prev` không còn là nốt viết trước sóng.

| Thể loại | Bước vào khi đi xuống | Biên độ cả câu | Trần |
|---|---:|---:|---:|
| Brouwer, Hát và étude | +8. Étude vẫn mở tại trần khi vào phách mạnh | 30 và 44 như hiện tại | 82 và 90 |
| Villa, dòng hát và choro, vals, polca, hemiola, `villa_pattern` | +6 | 24 | 80 |
| Barrios | +4 | 18 | 76 |
| Sor, cantabile, étude và galop | +4 | 16 | 76 |
| Bach sarabande, fugue, allemande, courante, bourrée, gavotte, gigue | +4 | 12 | 74 |
| Bach chaconne | +6 | 18 | 80 |
| Bach prelude | +2 | 6 | 72 |

Sóng lên dùng cùng biên độ và bắt đầu đúng mức đang nghe. Prelude không bị kéo xuống sàn 54 rồi trèo lên 84. Nốt trụ của prelude nằm trên cùng ramp đó, không bị kéo riêng lên sàn `_BASS + 2` (62).

Elogio của Brouwer giữ cửa sổ `44…92`. Nó thuộc mốc Brouwer đang nghe ổn.

Dịch band `p / mp / mf / f` giữ như Mục 2.6.B, nhưng không được kéo prelude vượt trần 72 hay kéo biên độ prelude quá 6.

## 4. Ô 27 sau khi chỉnh

Nốt lead ô 26 đang nghe ở khoảng 56. Prelude mở tại 58 và hạ khoảng 6 bậc, về quanh 52, cùng vùng với ô đứng trước. Không còn đỉnh 84 và không còn nốt trụ 62.

## 5. Phần không đổi

Đường cao độ, ngân sách 30%, cửa sổ tirata, và chỗ bass nghỉ của Courante và Allemande giữ nguyên. Hairpin vẫn chỉ ở bè cao. Bass và bè giữa giữ mức của pattern.

Chưa sửa `guitar_scale_passages.py`. Khi viết code, `restamp_passage_hairpins` phải đọc velocity sau `apply_guitar_wave`, và test hairpin Mục 2.6 cần khóa các số mới này thay cho cửa sổ tuyệt đối `52…84` trên prelude.
