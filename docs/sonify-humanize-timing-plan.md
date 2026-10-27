# Humanize: xung lực, sai số, và cửa MuseScore

> **Trạng thái**: đề xuất, chưa code. Lớp đang chạy vẫn là ±2 trên plateau, ghi ở `docs/sonify-humanize-preset-plan.md`.
>
> ±2 là nhiễu lực dưới ngưỡng nghe. Đồng hồ chung khoảng 1% phách thì MuseScore 4 phát được bằng `<sound tempo>`. Lệch từng tay khoảng 7 ms thì không: cú đánh bám thẻ `type`, bậc nhỏ nhất engine chịu đặt là một móc kép, 21 ms ở 88 BPM.

Mục đích của lớp này là nhạc nghe người hơn. Người chơi khác máy ở hai chỗ. Xung lực là việc cố ý: phách mạnh nặng và dài hơn, giai điệu vào trước đệm, ngón cái đúng phách còn ngón tay trễ một chút, cuối câu nới ra. Sai số là phần còn lại, nhỏ, và có sửa: đánh trễ thì khoảng sau rút lại. Một tay dùng một đồng hồ. Máy theo công thức thì mọi tiếng cùng một phách rơi đúng cùng một mẫu, cùng một lực.

---

## 1. Lớp đang chạy

`humanize()` trong `backend/app/sonify/humanize.py` chạy sau khi bản đã soạn, trong `RecapStore._render` và `_render_movement`, rồi mới ghi MusicXML. Không gắn vào `_finish` của `render()`. Cao độ, độ dài, chữ động lực và hairpin giữ nguyên.

Số cộng vào không phải `random`. FNV-1a của `variant`, `ensemble`, field, ô và phách chọn một giá trị trong `{-2, -1, 0, +1, +2}`. Trần là `CAP = 2`. Cùng một bản ra cùng một file. Không dùng `hash()` của Python.

Chỉ một plateau được nhích: từ hai cú đánh liền nhau trong cùng field, cùng velocity, và cú đánh khác lực gần nhất mỗi phía phải cách hơn 2. Không có cú khác lực ở một phía thì phía đó không chặn. Bậc thang 1 hoặc 2 đứng yên, nên Etude 1 và Etude 11 không bị làm phẳng. Nốt cùng phách, cùng field, cùng lực viết dùng chung một số. Hợp âm không bị xé. Nếu độ lệch làm đảo thứ tự lực giữa hai bè đang chồng, hoặc xóa một bước 3–4 giữa hai plateau liền nhau, offset bị kéo về 0 từng bậc, giữ nguyên dấu. `tie_stop` không nằm trong plateau. Nốt nối viết cùng lực với cú đánh thì nhận lực đã nhích. Đỉnh cung viết lực khác, như 64 hoặc 80 sau nốt mở 49, giữ số đã viết.

Ô study guitar `classic`, bar 0, ra số thật. Bè trung 56 nhận `+1, +1, +2, +1`, thành 57, 57, 58, 57. Bè trầm 60 nhận `−2, −1, +1, +2`, thành 58, 59, 61, 62. Thứ tự 60 trên 56 vẫn còn. Phần thay đổi trên bè trung là 1 bậc velocity.

---

## 2. Vì sao ±2 không làm nhạc nghe người

Đo trong `docs/sonify-symphony-dynamics.md`, glockenspiel C6, giữ chữ `p`, velocity 46 lên 96 làm đỉnh tăng 7,3 dB. Trung bình 0,146 dB mỗi bậc. ±2 là khoảng 0,3 dB. Ngưỡng cường độ cho một tiếng đơn ở mức vừa là khoảng 1 dB, tức khoảng 7 bậc trên glockenspiel. Trong bản nhiều bè ngưỡng còn cao hơn. Một bậc chữ trên piano trong cùng tài liệu là khoảng +6 dB, cỡ hai mươi lần ±2.

| Giọng | Note dynamics | ±2 làm gì |
|---|---|---|
| Hơi, dây, đồng, hợp xướng, piano, harp | Bỏ qua | WAV không đổi |
| Glockenspiel, crotales, vibraphone | Có đọc | Khoảng 0,3 dB |
| Tối giản `classic`, MS Basic | MIDI velocity có tiếng | Vài phần mười dB |
| Nylon | Chưa đo ở 53, 56, 59 | Cửa quyết định của trần velocity |
| Ambient celesta, chuông | Chưa khóa | Chỉ đáng xét nếu mẫu đổi lớp |

Trần ±2 còn bị kẹp bởi khoảng cách đã viết. Ô study 56 dưới 60 chỉ cách 4 bậc. Nhấn +4 ở bè trung chạm bè trầm và bị luật giữ thứ tự kéo về. Trần đó là hệ quả của khoảng cách, không phải liều tai nghe được.

Hình của nhiễu cũng không giống người chơi. Mỗi phách một số độc lập, hai phách liền có thể cùng `+2`. Mỗi field một chuỗi riêng, không có đồng hồ chung của một tay. Thời điểm đánh vẫn đúng lưới.

Jazz đã có xung lực thời gian riêng: swing móc đơn 2:1, ghi trong MusicXML và MuseScore áp lúc phát. Thêm một tỷ lệ swing nữa sẽ đánh đè lớp đó.

---

## 3. Hai tầng đề xuất

Giữ chỗ đứng sau `render()` và trước MusicXML. Giữ tính tất định, khóa thứ tự lực, một cú đánh một độ lệch, bậc thang 1–2 đứng yên, `tie_stop` đi theo cú đánh khi cùng lực viết, chữ in và hairpin đứng ngoài.

Tầng một là xung lực. Tầng hai là sai số. Cả hai cố định theo bản. Tổng tick mỗi ô, và tổng thời gian bài, giữ nguyên để `mapDurationSec` không trượt khỏi nốt. `mapDurationSec` bám độ dài bản viết khi file WAV dài hơn vì đuôi nhả.

### Xung lực

| Cử chỉ | Điểm xuất phát | Áp vào |
|---|---|---|
| Ngón cái đúng phách, ngón tay trễ một móc kép | 21 ms ở 88 BPM, 16 ms ở 120 BPM | Guitar, voice ngón tay |
| Giai điệu vào trước đệm một móc kép | Cùng bậc. Đệm trễ, giai điệu giữ lưới | `lead` hoặc `high` so với `comp` và `low` |
| Phách mạnh dài hơn | Một móc kép, lấy từ nốt yếu kế tiếp | Mọi dòng trừ lưới tối giản và móc đã swing |
| Cuối câu hơi nới, thân câu trả lại | `<sound tempo>` trong câu, tổng bằng 0 | Câu đã có trong `score.phrases` |
| Phách mạnh của plateau còn chỗ trống | +4 đến +6 velocity | Chỉ khi cách bè kề ít nhất 8 bậc, và sampler đọc note dynamics |

Plateau cách bè khác từ 8 bậc trở lên, như giai điệu 72 trên nền 56, mới đủ chỗ cho một nhấn velocity mà thứ tự vẫn còn. Ô study 56/60 không thuộc chỗ đó. Trên ô đó xung lực đáng làm là thời gian.

### Sai số

Đồng hồ chung viết bằng `<sound tempo>`. Dao động khoảng ±1% BPM, trơn trên 2–4 phách, trung bình bằng 0 trong câu. Mọi bè đi cùng. Đó là nhịp thở chung.

Mỗi tay thêm tối đa một móc kép. Trên guitar, `lead` và `support` chung một chuỗi vì cùng bàn tay phải. `low` của ngón cái là chuỗi kia. Phách mạnh để 0. Phách yếu mới được một bậc. Cú trễ làm khoảng sau ngắn lại vì nốt trễ bị rút đúng số tick của dấu lặng đứng trước nó, còn cú sau giữ mốc đã viết.

Velocity dư, độ lệch chuẩn khoảng 2–3 và cùng dấu với cú đang nhấn, chỉ cộng vào giọng thực sự đọc note dynamics, và chỉ khi khoảng cách tới bè kề còn chỗ. Trên phần lớn MuseSounds, phần này vẫn dưới ngưỡng. Nó không thay được lệch thời gian.

Khung này khớp mô hình hai quá trình của Wing và Kristofferson (1973): đồng hồ trung tâm cộng nhiễu vận động, tương quan âm giữa hai khoảng kề. Dao động 1/f của nhịp người chơi được đo lại ở Rankin, Large và Fink (2009). Melody lead khoảng 20–30 ms là kết quả lặp lại của Palmer và Goebl. Cử chỉ câu, nốt dài và phách mạnh là họ luật KTH (Friberg, Bresin, Sundberg). Hệ số trên là điểm xuất phát để đo WAV, cùng cách dự án đã khóa ±2.

---

## 4. Cửa MuseScore 4

Engine phát cú đánh theo hình nốt. Từ MuseScore 4.0, importer đặt nốt kế tiếp theo thẻ `type`, không theo một `duration` lệch vài tick. Thay đổi đó vào ở PR 8429, bản sửa 4.0.0. `duration` ngắn hơn `type` được ghi vào off-time: nốt nhả sớm, cú sau đứng yên. Cơ chế lệch `ontime` của piano roll MuseScore 3 không còn đổi playback ở MuseScore 4.

Máy viết tài liệu này không có MuseScore, nên chưa đo WAV xác nhận lại trên 4.7.5. Hợp đồng import từ 4.0 là căn cứ của bảng dưới.

| Phần sai số | Cách engine phát | Bậc ở 88 BPM |
|---|---|---|
| Đồng hồ chung, ±1% phách, trung bình 0 trong câu | `<sound tempo>`, mọi bè cùng lệch | Khoảng 7 ms. Tempo thập phân là đủ |
| Từng tay, cú trễ làm khoảng sau ngắn lại | Dấu lặng thật trong voice đó, nốt đó ngắn lại cùng số tick | Một móc kép, 21 ms. Ở 120 BPM là 16 ms |
| `duration` lệch vài tick, `type` giữ nguyên | Cú đánh đứng yên, đuôi nốt ngắn hơn | Không dịch attack |

`<sound tempo>` đã là đường `_metronome` đang đặt BPM. Cặp tempo đối xứng, hai phách nhanh 1% rồi hai phách chậm 1%, chỉ kéo dài bài thêm khoảng 0,01%. Nến giữ nguyên.

Lệch từng voice là một dấu lặng `print-object="no"` đứng trước cú đánh, dài một móc kép, rồi rút đúng từng ấy tick khỏi nốt đó. Ô vẫn đủ tick. Hợp âm cùng phách đi chung, vì dấu lặng đứng trước cả cú. `tie_stop` không nhận dấu lặng riêng. Dấu lặng không chen vào giữa một tie.

Writer hiện chưa có bậc này. `_NOTE_TYPES` trong `musicxml.py` dừng ở móc đơn, 0,25 phách, tức 170 ms ở 88 BPM. `type` phải khớp `duration`, nếu không `_note_type` ném lỗi. Divisions mặc định là 2: một bậc lưới dài 341 ms ở 88 BPM và 250 ms ở 120 BPM. Guitar có lúc lên 4 hoặc 12, tức 170 ms hoặc 57 ms ở 88 BPM. Divisions cần ít nhất 32 để có móc kép, hoặc 96 để vừa móc kép vừa sextuplet guitar (96 chia hết cho 12 và cho 32).

Một móc kép là lượng hóa của melody lead 20–30 ms, không phải của đồng hồ 1% phách. Phần 7 ms nằm dưới bậc engine chịu đặt, nên nó đi bằng tempo, không đi bằng nốt.

Jazz để yên móc đã swing. MuseScore kéo móc thứ hai lúc phát theo tỷ lệ 2:1. Thêm một móc kép lên đúng móc đó sẽ chồng hai lần trễ.

---

## 5. Liều theo dòng

| Dòng | Nên thêm | Giữ nhỏ |
|---|---|---|
| `symphony` | Đồng hồ tempo. Đệm trễ một móc kép so với giai điệu | Velocity, trừ glockenspiel và vibraphone |
| `guitar` | Ngón tay trễ một móc kép so với ngón cái | Velocity cho đến khi đo nylon 53, 56, 59 |
| `jazz` | Đồng hồ tempo rất nhỏ quanh swing 2:1 đã có | Móc kép chồng lên móc swing |
| `minimalist` | Đồng hồ tempo dưới 1% | Móc kép, vì lưới là chất của dòng |
| `ambient` | Tempo thở theo câu, trên nốt dài | Móc kép trên từng cú vào |

Ô study guitar ở 88 BPM, nếu viết trên bậc engine phát được:

| Phách | Bè trung viết | Bè trầm viết | Ngón cái | Ngón tay |
|---|---|---|---|---|
| 1 | 56 | 60 | 0 | +21 ms |
| 2 | 56 | 60 | +21 ms | +21 ms |
| 3 | 56 | 60 | 0 | +21 ms |
| 4 | 56 | 60 | +21 ms | +21 ms |

Velocity trên ô này giữ số đã viết. Thời gian là phần nghe được.

---

## 6. Thứ tự khi viết

1. Đồng hồ tempo trước. `<sound tempo>` đã là đường MuseScore đang phát. Khóa tổng thời gian câu bằng 0 trước khi nghe.
2. Một WAV đo đỉnh nốt trước và sau một dấu lặng ẩn dài một móc kép, trên MuseScore 4.7.5. Cửa đó xác nhận attack có dịch đúng milli-giây. Writer cần `type` cho móc kép và divisions 96 ở bản có sextuplet.
3. Móc kép từng voice sau khi cửa đó mở. Tổng tick mỗi ô vẫn khớp. Phách mạnh để 0.
4. Bỏ velocity ±2 trên plateau cách bè kề dưới 8 bậc. Nhấn +4 đến +6 chỉ nơi còn khoảng trống và nơi sampler đọc note dynamics. Cửa nylon 53, 56, 59 vẫn quyết định phần velocity của guitar.
5. Sai số velocity tương quan thêm sau lần nghe, không làm trước lệch thời gian.
6. Đổi tiếng thật thì tăng `RECAP_REVISION` và `SPAN_REVISION` một lần.

Phần giữ nguyên từ lớp đang chạy: vị trí sau `render()`, tính tất định, khóa thứ tự lực, một cú một độ lệch, bậc thang 1 và 2 đứng yên, `tie_stop` cùng lực viết thì đi theo cú đánh, chữ in và hairpin đứng ngoài.
