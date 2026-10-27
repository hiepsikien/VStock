# Humanize: xung lực, sai số, và cửa MuseScore

> **Trạng thái**: đề xuất, chưa code. Lớp đang chạy vẫn là ±2 trên plateau, ghi ở `docs/sonify-humanize-preset-plan.md`. `RECAP_REVISION` là 64, `SPAN_REVISION` là 50.
>
> ±2 là nhiễu lực dưới ngưỡng nghe. Đồng hồ chung khoảng ±1% BPM thì MuseScore 4 phát được bằng `<sound tempo>`. Lệch từng voice khoảng 7 ms thì không có `<type>`. Hạt nghe được của melody lead là nốt 128, 1/32 phách: 21 ms ở 88 BPM, 16 ms ở 120 BPM. Writer chưa phát hình nốt còn lại sau khi trừ hạt đó.

Mục đích của lớp này là nhạc nghe người hơn. Người chơi khác máy ở hai chỗ. Xung lực là việc cố ý: phách mạnh nặng hơn, một bè vào sau bè kia một hạt nhỏ, cuối câu nới ra. Sai số là phần còn lại, nhỏ, và có sửa: đánh trễ thì khoảng sau rút lại. Một tay dùng một đồng hồ. Máy theo công thức thì mọi tiếng cùng một phách rơi đúng cùng một mẫu, cùng một lực.

Trong repo, một phách đen là hai móc đơn hoặc bốn móc kép. Móc đơn là 0,5 phách, nốt `eighth`. Móc kép là 0,25 phách, nốt `16th`. Ở 88 BPM móc kép dài 170 ms. `etude1` đã viết vòng 16 móc kép với `divisions = 4`, và `_NOTE_TYPES` đã có `0.25: ("16th", 0)`. Nốt 128 là 1/32 phách. Tài liệu này giữ hai tên đó tách nhau.

---

## 1. Lớp đang chạy

`humanize()` trong `backend/app/sonify/humanize.py` chạy sau khi bản đã soạn, trong `RecapStore._render` và `_render_movement`, rồi mới ghi MusicXML. Không gắn vào `_finish` của `render()`. Cao độ, độ dài, chữ động lực và hairpin giữ nguyên.

Số cộng vào không phải `random`. FNV-1a của `variant`, `ensemble`, field, ô và phách chọn một giá trị trong `{-2, -1, 0, +1, +2}`. Trần là `CAP = 2`. Cùng một bản ra cùng một file. Không dùng `hash()` của Python.

Chỉ một plateau được nhích: từ hai cú đánh liền nhau trong cùng field, cùng velocity, và cú đánh khác lực gần nhất mỗi phía phải cách hơn 2. Không có cú khác lực ở một phía thì phía đó không chặn. Bậc thang 1 hoặc 2 đứng yên, nên Etude 1 và Etude 11 không bị làm phẳng. Nốt cùng phách, cùng field, cùng lực viết dùng chung một số. Hợp âm không bị xé. Nếu độ lệch làm đảo thứ tự lực giữa hai bè đang chồng, hoặc xóa một bước 3–4 giữa hai plateau liền nhau, offset bị kéo về 0 từng bậc, giữ nguyên dấu. `tie_stop` không nằm trong plateau. Nốt nối viết cùng lực với cú đánh thì nhận lực đã nhích. Đỉnh cung viết lực khác, như 64 hoặc 80 sau nốt mở 49, giữ số đã viết.

Ô study guitar `classic`, bar 0, bốn cú, ra số thật. Bè trung 56 nhận `+1, +1, +2, +1`, thành 57, 57, 58, 57. Phách 3 là `+2`, 56 thành 58. Bè trầm 60 nhận `−2, −1, +1, +2`, thành 58, 59, 61, 62. Thứ tự 60 trên 56 vẫn còn.

Với `variant == "guitar"`, `humanize()` gọi `_clamp_guitar` sau khi cộng offset, trước khi chép `tie_stop`. Nốt viết ≤ 64 bị kéo về ≤ 64. Snap bị kéo về 66..70 với `classic` / `bach`, hoặc 66..76 với ensemble khác.

---

## 2. Vì sao ±2 không làm nhạc nghe người

Đo trong `docs/sonify-symphony-dynamics.md`, glockenspiel C6, giữ chữ `p`, velocity 46 lên 96 làm đỉnh tăng 7,3 dB. Trung bình 0,146 dB mỗi bậc. ±2 là khoảng 0,3 dB. Ngưỡng cường độ cho một tiếng đơn ở mức vừa là khoảng 1 dB, tức khoảng 7 bậc trên glockenspiel. Trong bản nhiều bè ngưỡng còn cao hơn. Một bậc chữ trên piano trong cùng tài liệu là khoảng +6 dB, cỡ hai mươi lần ±2.

| Giọng | Note dynamics | ±2 làm gì |
|---|---|---|
| Hơi, dây, đồng, hợp xướng, piano, harp | Bỏ qua | WAV không đổi |
| Glockenspiel, crotales, vibraphone | Có đọc | Khoảng 0,3 dB |
| Marimba | Chưa đo | Plan cũ chỉ đo peak để cân gain |
| Tối giản `classic`, MS Basic | MIDI velocity có tiếng | Vài phần mười dB |
| Nylon, MS Basic | Chưa đo ở 53, 56, 59 | Cửa quyết định của trần velocity |
| Ambient celesta, chuông | Chưa khóa | Chỉ đáng xét nếu mẫu đổi lớp |

Nylon đi MS Basic vì MuseSounds nylon bỏ qua velocity từng nốt. Luật nghe vẫn là nốt ấm không qua 65. Cơ chế trên đường render không còn là `_shape_dynamics`. `render_patterned_voices` gọi `apply_guitar_wave` trong `guitar_wave.py`. Docstring của hàm đó ghi là thay `_shape_dynamics`. Nốt ấm của sóng bị kẹp `min(63, …)`. Snap, khi pattern có, nằm ở 66..76. Canto `preludio` trên sóng có trần 62. Snap của chính pattern đó vẫn nâng nốt canto dài lên `min(68, velocity)`, tức 66..68. Không còn cửa 54..64. Nhánh `velocity >= _MELODY_APEX` chỉ còn trong `_shape_dynamics`. Nó không giữ đỉnh 72 sau sóng, và không ràng buộc một nhấn đặt trong `humanize()`.

Trần ±2 còn bị kẹp bởi khoảng cách đã viết. Ô study 56 dưới 60 chỉ cách 4 bậc. Nhấn +4 ở bè trung chạm bè trầm và bị luật giữ thứ tự kéo về. Trần đó là hệ quả của khoảng cách, không phải liều tai nghe được.

Hình của nhiễu cũng không giống người chơi. Mỗi phách một số độc lập, hai phách liền có thể cùng `+2`. Mỗi field một chuỗi riêng, không có đồng hồ chung của một tay. Thời điểm đánh vẫn đúng lưới.

Jazz đã có xung lực thời gian riêng: swing móc đơn 2:1, ghi trong MusicXML và MuseScore áp lúc phát. Thêm một tỷ lệ swing nữa sẽ đánh đè lớp đó.

---

## 3. Hai tầng đề xuất

Giữ chỗ đứng sau `render()` và trước MusicXML. Giữ tính tất định, khóa thứ tự lực, một cú đánh một độ lệch, bậc thang 1–2 đứng yên, `tie_stop` đi theo cú đánh khi cùng lực viết, chữ in và hairpin đứng ngoài.

Tầng một là xung lực. Tầng hai là sai số. Cả hai cố định theo bản. `mapDurationSec` bám độ dài bản viết khi file WAV dài hơn vì đuôi nhả.

### Xung lực đã có cửa phát

| Cử chỉ | Điểm xuất phát | Áp vào |
|---|---|---|
| Cuối câu hơi nới, thân câu trả lại | `<sound tempo>` đối xứng trong câu | Câu đã có trong `score.phrases` |
| Phách mạnh của plateau còn chỗ trống | +4 đến +6 velocity | Chỉ khi cách bè kề ít nhất 8 bậc, sampler đọc note dynamics, và trần nylon không nuốt |

Cặp tempo ±1% rồi ∓1% dài hơn khoảng 0,01%, vì thời gian đi theo nghịch đảo tempo. Tổng độ lệch BPM bằng 0 không phải tổng thời gian bằng 0. Phần dư đó nhỏ hơn đuôi nhả của MuseScore, nên `mapDurationSec` vẫn bám độ dài bản viết.

Nhấn +4 đến +6 nằm trong `humanize()`, trước `_clamp_guitar`. Nốt ấm viết ≤ 64 bị kéo về ≤ 64, nên +4 trên nền 64 dừng ở 64. Snap viết 68 trên `classic` bị trần 70 nuốt một phần. 56 cách 60 bốn bậc thì không thuộc chỗ +4. Đỉnh 72 sau sóng không đi qua nhánh `_MELODY_APEX`. `_clamp_guitar` xét nốt viết trên 64 như snap. Luật nghe vẫn là nốt ấm không qua 65. Cơ chế giữ luật đó là `_clamp_guitar` và cửa snap của `apply_guitar_wave`.

### Xung lực thời gian từng voice, chưa viết được

Hạt nghe được của melody lead 20–30 ms là một nốt 128: 21 ms ở 88 BPM (`60/88/32` giây), 16 ms ở 120 BPM. Đó là lượng hóa, chưa phải một `<type>` writer phát được. Mục 4 ghi vì sao dấu lặng ẩn cộng rút `<duration>` không giữ được cú sau.

Trên guitar, luật tay là một luật, không cộng thêm luật “giai điệu trước, đệm sau”. Pattern nào ngón cái là nền thì ngón tay (`lead` và `support`, cùng bàn tay phải) trễ một hạt so với ngón cái, và hai voice ngón tay chung một chuỗi. `thumb_cantabile` đặt giai điệu lên ngón cái (`low`), bè trên chỉ chập hợp âm ở phách yếu. Ở pattern đó hạt trễ thuộc hợp âm, ngón cái giữ phách. Áp cả hai luật lên cùng một nốt thì nốt đó vừa phải vào trước vừa phải vào sau.

Ở giao hưởng, giai điệu (`lead` hoặc `high`) giữ lưới và đệm (`comp`, `low`) trễ một hạt. Luật đó không áp cho guitar.

“Phách mạnh dài hơn, lấy một hạt từ nốt yếu sau” đụng cùng cửa `<type>` ở mục 4. Chưa xếp vào thứ tự viết.

### Sai số

Đồng hồ chung viết bằng `<sound tempo>`. Dao động khoảng ±1% BPM, trơn trên 2–4 phách, trung bình độ lệch BPM bằng 0 trong câu. Mọi bè đi cùng. Đó là nhịp thở chung. Phần dài thêm 0,01% nằm trong đuôi nhả.

Sai số từng tay, phách mạnh ít lệch hơn phách yếu, và cú trễ làm khoảng sau ngắn lại, cần cùng một hạt nốt 128. Cửa đó chưa mở. Mục 4.

Velocity dư, độ lệch chuẩn khoảng 2–3 và cùng dấu với cú đang nhấn, chỉ cộng vào giọng thực sự đọc note dynamics, sau khi khoảng cách tới bè kề và trần nylon còn chỗ. Trên phần lớn MuseSounds, phần này vẫn dưới ngưỡng. Nó không thay được lệch thời gian.

Khung này khớp mô hình hai quá trình của Wing và Kristofferson (1973): đồng hồ trung tâm cộng nhiễu vận động, tương quan âm giữa hai khoảng kề. Dao động 1/f của nhịp người chơi được đo lại ở Rankin, Large và Fink (2009). Melody lead khoảng 20–30 ms là kết quả lặp lại của Palmer và Goebl. Cử chỉ câu, nốt dài và phách mạnh là họ luật KTH (Friberg, Bresin, Sundberg). Hệ số trên là điểm xuất phát để đo WAV, cùng cách dự án đã khóa ±2.

---

## 4. Cửa MuseScore 4

Engine phát cú đánh theo hình nốt. Từ MuseScore 4.0, importer lấy độ dài và chỗ cú sau từ `<type>`, cộng chấm và `time-modification`. Thay đổi đó vào ở PR 8429, bản sửa 4.0.0. `<duration>` ngắn hơn `<type>` chỉ vào off-time: nốt nhả sớm. Cơ chế lệch `ontime` của piano roll MuseScore 3 không còn đổi playback ở MuseScore 4.

Máy viết tài liệu này không có MuseScore, nên chưa đo WAV xác nhận lại trên 4.7.5. Hợp đồng import từ 4.0 là căn cứ của bảng dưới. Bước đo WAV nằm ở mục 6, sau khi đã có một chuỗi `<type>` đúng.

| Phần sai số | Cách engine phát | Bậc ở 88 BPM |
|---|---|---|
| Đồng hồ chung, độ lệch BPM trung bình 0 trong câu | `<sound tempo>`, mọi bè cùng lệch | Khoảng 7 ms. Tempo thập phân là đủ. Bài dài thêm khoảng 0,01% |
| Từng voice, cú trễ, khoảng sau ngắn lại | Cần tổng `<type>` trước cú sau giữ nguyên | Nốt 128, 21 ms. Chưa có `<type>` cho phần còn lại |
| `<duration>` ngắn hơn `<type>` | Nốt nhả sớm. Cú sau vẫn theo `<type>` | Không dịch attack về phía trước |

`<sound tempo>` đã là đường `_metronome` đang đặt BPM.

Cú sau đứng yên khi tổng `<type>` phía trước nó không đổi. Một dấu lặng thêm một `<type>`. Muốn cú sau giữ mốc đã viết, `<type>` của nốt trễ phải ngắn đi đúng lượng của dấu lặng đó. Rút riêng `<duration>`, rồi thêm dấu lặng, làm hai việc khác: nốt nhả sớm, và mọi cú sau trễ thêm đúng hạt của dấu lặng vì tổng `<type>` tăng.

`<duration>` thì `divisions` 32 viết được một nốt 128. `<type>` thì không. `_note_type` chỉ nhận các độ dài trong `_NOTE_TYPES`, và ném lỗi khi `type` lệch `duration`. Trừ 1/32 phách khỏi các độ dài writer đang phát:

| Nốt đang viết | Còn lại | Hình nốt |
|---|---|---|
| Móc kép 0,25 | 7/32 | 32nd hai chấm |
| Móc đơn 0,5 | 15/32 | Không phải một hình nốt, kể cả hai chấm |
| Nốt đen 1 | 31/32 | Không phải một hình nốt |
| Sextuplet 1/6 | 13/96 | Không phải một hình nốt |

Writer chưa phát chấm đôi, chưa có `32nd`, `64th`, `128th`. `divisions` 96 chia hết cho 32 và cho 12, nên vừa nốt 128 vừa sextuplet guitar trên trục `<duration>`. Nó không tạo ra `<type>` còn lại. Bước lệch từng voice chỉ viết được khi nói rõ một chuỗi nốt nối mà từng khúc là một `<type>` đã có, hoặc khi chọn một hạt mà phép trừ ra đúng một `<type>` có sẵn.

Hợp âm cùng phách vẫn đi chung, vì dấu lặng đứng trước cả cú. `tie_stop` không nhận dấu lặng riêng. Dấu lặng không chen vào giữa một tie. Hai ràng buộc đó đứng sau cửa `<type>`.

Nốt 128 là lượng hóa của melody lead 20–30 ms. Đồng hồ 1% phách, khoảng 7 ms ở 88 BPM, nhỏ hơn hạt đó, nên nó đi bằng tempo.

Jazz để yên móc đơn đã swing. MuseScore kéo móc thứ hai lúc phát theo tỷ lệ 2:1. Thêm một nốt 128 lên đúng móc đó sẽ chồng hai lần trễ.

Divisions mặc định là 2: một bậc lưới là một móc đơn, 341 ms ở 88 BPM, 250 ms ở 120 BPM. Guitar có lúc lên 4, một bậc là một móc kép, 170 ms ở 88 BPM, hoặc lên 12, một bậc 57 ms ở 88 BPM.

---

## 5. Liều theo dòng

| Dòng | Nên thêm, khi cửa đã mở | Giữ nhỏ |
|---|---|---|
| `symphony` | Đồng hồ tempo. Đệm trễ một nốt 128 so với giai điệu | Velocity, trừ glockenspiel và vibraphone. Marimba vẫn chưa đo |
| `guitar` | Ngón tay trễ một nốt 128 so với ngón cái, trừ `thumb_cantabile` | Velocity cho đến khi đo nylon 53, 56, 59. Nốt ấm ≤ 64 do `_clamp_guitar` giữ ≤ 64 |
| `jazz` | Đồng hồ tempo rất nhỏ quanh swing 2:1 đã có | Nốt 128 chồng lên móc đơn swing |
| `minimalist` | Đồng hồ tempo dưới 1% | Nốt 128, vì lưới là chất của dòng |
| `ambient` | Tempo thở theo câu, trên nốt dài | Nốt 128 trên từng cú vào |

`thumb_cantabile` hát giai điệu bằng ngón cái. Hạt trễ ở pattern đó là hợp âm phách yếu, không phải ngón cái.

Ô study guitar ở 88 BPM, nếu một ngày viết được hạt nốt 128 mà cú sau vẫn giữ mốc. Đây là liều nghe, chưa phải chuỗi `<type>`:

| Phách | Bè trung viết | Bè trầm viết | Ngón cái | Ngón tay |
|---|---|---|---|---|
| 1 | 56 | 60 | 0 | +21 ms |
| 2 | 56 | 60 | +21 ms | +21 ms |
| 3 | 56 | 60 | 0 | +21 ms |
| 4 | 56 | 60 | +21 ms | +21 ms |

Velocity trên ô này giữ số đã viết. 56 dưới 60 bốn bậc, không đủ chỗ cho nhấn +4.

---

## 6. Thứ tự khi viết

1. Đồng hồ tempo trước. `<sound tempo>` đã là đường MuseScore đang phát. Cặp tempo đối xứng dài hơn khoảng 0,01%. Phần dư nằm trong đuôi nhả, `mapDurationSec` vẫn bám độ dài bản viết.
2. Chưa viết dấu lặng từng voice. Cửa MuseScore đòi phần nốt còn lại là một `<type>`, hoặc một chuỗi nốt nối từng khúc đã có trong `_NOTE_TYPES`. `divisions` 96 không thay việc đó. Đo WAV trên 4.7.5 làm sau khi chuỗi đó có thật: đỉnh nốt trước và sau hạt phải dịch đúng milli-giây, và cú kế tiếp phải giữ mốc.
3. Bỏ velocity ±2 trên plateau cách bè kề dưới 8 bậc. Nhấn +4 đến +6 chỉ nơi còn khoảng trống, nơi sampler đọc note dynamics, và nơi trần nylon không nuốt. 56 cách 60 không thuộc chỗ đó. Nốt ấm không được qua 65. `_clamp_guitar` giữ nốt viết ≤ 64 ở mức ≤ 64. Cửa snap của `apply_guitar_wave` nằm ở 66..76, rồi `_clamp_guitar` kéo về 66..70 trên `classic` / `bach`, hoặc 66..76 trên ensemble khác. Cửa nylon 53, 56, 59 vẫn quyết định phần velocity của guitar. Marimba đo note dynamics trước khi tính nó vào nhóm có đọc.
4. Sai số velocity tương quan thêm sau lần nghe, không làm trước lệch thời gian.
5. Đổi tiếng thật thì tăng `RECAP_REVISION` và `SPAN_REVISION` một lần.

“Phách mạnh dài hơn một hạt” xếp cùng bước 2. Nó rút `<type>` của nốt yếu sau, cùng cửa chưa mở.

Phần giữ nguyên từ lớp đang chạy: vị trí sau `render()`, tính tất định, khóa thứ tự lực, một cú một độ lệch, bậc thang 1 và 2 đứng yên, `tie_stop` cùng lực viết thì đi theo cú đánh, chữ in và hairpin đứng ngoài.
