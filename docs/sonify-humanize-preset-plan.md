# Humanize và lớp màu sau bản nhạc

> **Trạng thái**: đã code. Trần humanize là ±2, kể cả 0, chỉ trên plateau. `RECAP_REVISION` là 64, `SPAN_REVISION` là 50.
>
> Cửa nghe nylon ở velocity 53, 56 và 59 vẫn là chỗ quyết định có giữ trần này hay hạ xuống. ±1..±3 như bản đầu làm phẳng contour vừa viết và gần như không đổi tiếng trên phần lớn MuseSounds.
>
> Đề xuất lệch thời gian, và vì sao ±2 dưới ngưỡng nghe, nằm ở `docs/sonify-humanize-timing-plan.md`. Lớp đó chưa code.

Hai lớp xếp sau khi bản đã soạn xong. Lớp 1 sửa velocity trên nốt. Lớp 2 tô màu file tiếng. Không lớp nào viết lại nốt, hợp âm, hay đường động lực đã có.

Năm dòng nhạc là năm `variant`: `symphony`, `jazz`, `minimalist`, `ambient`, `guitar`. Bộ nhạc cụ bên trong một dòng dùng chung màu của dòng đó. `brass` vẫn là giao hưởng, `soul` và `organ` vẫn là jazz, đúng `ensemble.py`.

---

## 1. Humanize — một filter nhẹ, chỉ trên plateau

Nhiều đoạn nghe như máy vì một bè giữ nguyên một velocity suốt một chuỗi nốt. Chỗ thấy rõ trên guitar là cả ô study: bè trung đứng ở 56, bè trầm đứng ở 60.

Filter chạy một lần, sau `render()`, ngay trước `score_to_musicxml`. Hai đường xuất thật là `RecapStore._render` và `_render_movement` trong `audio.py`. Không gắn vào `_finish` của `render()`: `test_sonify_guitar.py` khóa velocity trên score trả về, ví dụ bè trung study đúng `{56}` và bè trầm đúng `{60}`.

Module mới: `backend/app/sonify/humanize.py`. Hàm `humanize(score) -> Score`.

`NoteEvent.velocity` thành `<note dynamics>` theo `velocity * 100 / 90`.

### Đi trên field của `Score`

Guitar trên giấy là một part `P1`. Ba dòng `lead`, `support`, `low` là ba field. Filter đi trên ba field đó. Đi theo part MusicXML thì ba voice bị gộp thành một chuỗi.

Bốn dòng kia đi trên `high`, `lead`, `support`, `comp`, `low`. Field nào có nốt thì xét field đó. Nốt trong một field xếp theo `(bar, beat)`.

Nốt nghỉ và nốt `velocity is None` giữ nguyên.

### Plateau được nhích khi bậc kề lớn hơn trần

Một plateau là một chuỗi cú đánh liền nhau trong cùng một field, viết cùng một velocity. `tie_stop` không phải một cú đánh trong chuỗi đó.

Plateau chỉ được nhích khi khoảng cách tới cú đánh khác velocity gần nhất, cả phía trước và phía sau trong cùng field, lớn hơn trần. Bước kề là 1 hoặc 2 thì cả đoạn đứng yên. Không có cú đánh khác velocity ở một phía thì phía đó không chặn.

Ô study toàn 56 vẫn nhích: trong field đó không có bậc kề 1 hoặc 2. Sau đó nó bị kẹp bởi bè trầm 60.

Cùng một quy tắc giữ các bậc thang vừa khóa. Không cần một danh sách ngoại lệ:

- Etude 11 (`_ETUDE11_TILT`), hairpin 60, band `mf`, ra khoảng 49, 50, 51, 51. Cặp 51, 51 là một plateau, và nó sát nốt 50 đúng một bậc, nên cả đoạn đứng yên.
- Etude 1 (`_ETUDE1_ARC` cộng vào 52) là bậc thang bước 2: `50 50 50 | 52 52 | 54 54 54 | 52 52 | 50 50 50`. Mỗi bậc là một plateau. Trần ±2 xóa được bước giữa hai bậc, nên cả ô đứng yên.
- Vòm tremolo Barrios các phách cách nhau từ 3 trở lên, và các nốt liền nhau không bằng nhau. Không có plateau nào để nhích, nên cả ô đứng yên.
- Đỉnh giai điệu 72 cạnh nền 64 là bước 8. Nốt 64 chỉ nhích nếu plateau của nó cách cú đánh khác velocity hơn 2.

### Độ lệch trên plateau

Mỗi cú đánh trên một plateau được phép nhích cộng một số trong `{-2, -1, 0, +1, +2}`. Trần là 2. 0 nằm trong tập chọn, và cũng là bậc cuối khi offset làm đảo thứ tự.

Số đó cố định theo `(variant, ensemble, field, bar, beat)`, không có `midi`, không dùng `random`, và không dùng `hash()` của Python. Cùng một bản ra cùng một file, vì cache tiếng khóa theo revision.

Mọi nốt cùng phách, cùng field, cùng lực viết dùng chung một số. Gốc và quãng 5 của ngón cái khác `midi` nhưng cùng một cú, nên cùng một độ lệch. Hợp âm ba nốt cùng lực trên cùng phách, cùng field, cũng dùng chung số đó.

Nốt ở hai field khác nhau, đang kêu cùng lúc, giữ thứ tự đã viết. Khi offset đã chọn làm đảo thứ tự, hạ đúng offset đó về phía 0 theo tập `{-2, -1, 0, +1, +2}`. 0 là bậc cuối. Đổi dấu sẽ làm hai lần chạy cùng đầu vào ra hai kết quả. Bè trầm study 60 và bè trung 56 cách nhau 4. Trần villa cùng kiểu: trầm chỉ thấp hơn giai điệu 1, bè trung thấp hơn 2 hoặc 4.

`tie_stop` không tham gia plateau. Nốt nối viết cùng lực với cú đánh nhận lực đã humanize của cú đó. Nốt nối viết lực khác, như đỉnh cung nở 64 hoặc 80 sau nốt mở 49, giữ lực viết của nó.

Cao độ, độ dài, cờ nhấn, và chữ động lực in trên giấy không đổi. Kẹp trong `1..127`.

### Chỗ tai nghe được

Đo trong `docs/sonify-symphony-dynamics.md`:

- Bỏ qua hoàn toàn `<note dynamics>`: hơi, dây, đồng, hợp xướng, piano và harp. Kèn cor nằm trong nhóm đó, cùng trumpet, trombone, tuba. Trên các giọng này filter không đổi tiếng. Lớp này không sửa chữ in và không sửa hairpin.
- Nghe cả chữ in lẫn velocity từng nốt, trong số đã đo: glockenspiel, crotales, vibraphone. Trên glockenspiel, velocity 46 lên 96 tăng peak 7,3 dB, nên ±3 khoảng 0,4 dB và ±2 còn nhỏ hơn.
- Marimba mới được đo peak để cân gain. Chưa đo xem nó có đọc `<note dynamics>` hay không.

Nylon nghe được nếu thư viện đổi lớp mẫu trong khoảng đang xét. Sax, Rhodes, flute, piano, dây và kèn không đổi. Tối giản `classic` đi MS Basic, nên velocity MIDI có tiếng, nhưng bước 2 trên thang mượt chỉ khoảng vài phần mười dB. Ambient gần như im, trừ celesta và chuông nếu chúng đọc velocity. Cửa quyết định có khóa ±2 hay không là nylon ở 53, 56 và 59, ghi ở mục 4.

---

## 2. Màu bản ghi — một preset cho mỗi dòng

Lớp này chạy sau khi MuseScore đã viết WAV. Bản nhạc đã xong. Sạch tuyệt đối nghe khô. Mỗi dòng được một ít không khí của một cách thu, và không dòng nào được một lớp nhiễu rõ.

`_transcode_m4a` hiện bỏ `variant` và encode không filter. `_GUITAR_HALL` (kệ cao, echo, nới stereo) không được gọi. Guitar không bật chuỗi đó.

Thứ tự, cả recap ngày và span, khớp cách `SessionRecap` chia thời gian: sóng và playhead theo độ dài file, nến theo `mapDurationSec`.

1. MuseScore viết WAV khô.
2. FFmpeg tô màu ra một WAV thứ hai, theo `variant`. Nền nhiễu trộn sau chuỗi đó, từ một bộ đếm cố định: `anoisesrc` không ra cùng một file giữa hai lần chạy. Biên độ `0.001` là thang `[-1, 1]`. WAV 16-bit của MuseScore 3 nhân biên độ và ngưỡng cổng guitar với `32767`.
3. Cắt WAV đã tô về đúng độ dài WAV khô. `aecho` và reverb của FFmpeg nối thêm đuôi ở cuối file. `mapDurationSec` lấy từ độ dài bản viết khi file dài hơn bản viết. Cắt giữ độ dài đoạn chart đứng ở nốt cuối.
4. `waveform_peaks` đo trên WAV đã tô và đã cắt.
5. Encode m4a từ WAV đó. Không gắn filter thêm ở bước encode.

Chuỗi filter không có lookahead, để attack không trượt khỏi nốt.

Không có FFmpeg thì phát WAV khô. Đỉnh không được nhô hơn bản khô: nếu saturation làm lớn, hạ lại trước khi đo peak. Hệ số dưới đây là điểm xuất phát, chỉnh sau khi nghe.

| Dòng | Preset | Vì sao | Không làm |
|---|---|---|---|
| `symphony` | `vintage` | Bản thu dàn nhạc analog, hơi ấm, hơi mờ ở trên cao | Xì đĩa, nứt, phòng hòa nhạc lớn |
| `guitar` | `vintage` | Đĩa guitar cổ điển thu gần, ấm, ít phòng | `_GUITAR_HALL`, mái vòm, nhiễu trong khoảng nghỉ |
| `jazz` | `club` | Combo thu gần trong phòng nhỏ. Sax, Rhodes, vibraphone cần thân tiếng, nhịp vẫn sắc | Băng vintage của dàn nhạc, nền xì, đuôi dài |
| `minimalist` | `wood` | Phản xạ sớm vài chục ms, để ostinato hết khô mà lưới phách không nhòe | Decay 0,4 giây, saturation, wow, nhiễu |
| `ambient` | `air` | Một ít không khí xa, nhẹ, để kính và horn bớt sắc số | Nền xì trên drone, reverb dài phủ cả chương |

### `vintage` — giao hưởng

Bản thu dàn, khoảng cách vừa, băng nhẹ.

- Kệ cao khoảng 8 kHz, hạ khoảng 2 dB.
- Ấm nhẹ ở khoảng 200–400 Hz.
- Saturation rất nhẹ.
- Nền nhiễu rất thấp, quanh −60 dB. Dàn nuốt được mức đó. Nghe là "không phải file trắng", không phải tiếng xì.
- Phòng ngắn. Đuôi bị cắt về độ dài WAV khô.

### `vintage` — guitar

Cùng tên preset, khác hệ số. Thu gần hơn giao hưởng. Móng tay và tiếng dây phải còn.

- Ấm nhẹ, kệ cao nông hơn giao hưởng (khoảng 1 dB).
- Phòng nhỏ, chỉ phản xạ sớm, ngắn hơn chuỗi giao hưởng.
- Nền nhiễu thấp hơn giao hưởng, và im trong khoảng nghỉ. Một tiếng trải suốt file ở −60 dB thành tiếng xì ở chỗ nylon nghỉ.
- Không echo dài, không `extrastereo`.

### `club` — jazz

Sax, kèn, Rhodes, Hammond, vibraphone và bass điện nghe khô khi không có phòng. Phòng thu nhỏ cho thân tiếng. Đuôi dài làm nhòe swing.

- Phản xạ sớm, cỡ vài chục ms, mức thấp.
- Saturation nhẹ trên cả bus.
- Không nguồn nhiễu. Hơi kèn đã là nhiễu của dòng này.
- Không cắt cao sâu: vibraphone và kèn cần khoảng trên.
- Cắt về độ dài WAV khô.

### `wood` — tối giản

Mallet, guitar thép, piano đứng, hợp xướng và pulse cần lưới rõ. Khô quá thì nghe như file MIDI.

Phản xạ sớm vài chục ms, mức ướt thấp. Đó là lựa chọn cho `wood`. Decay 0,4 giây phủ khoảng ba móc đơn ở 120 BPM, đủ để nhòe ostinato, nên không dùng.

Không saturation, không nguồn nhiễu, không nới stereo. Cắt về độ dài WAV khô.

### `air` — ambient

Drone, halo, kính và horn đã ngân dài và đã có diminuendo (`docs/sonify-ambient.md`). Xì trên nốt dài sẽ thành nội dung của bài.

- Làm mềm phía trên, nhẹ, để celesta và flute bớt tiếng số.
- Không khí mức thấp. Đuôi của filter bị cắt về độ dài WAV khô, nên không kéo `mapDurationSec`.
- Không nguồn nhiễu.
- Đuôi cuối bài vẫn là đuôi MuseScore đã có trong WAV khô.

---

## 3. Việc không làm trong đợt này

- Không sửa pattern, dialect, chữ `p–f`, hay hairpin.
- Không humanize plateau khi bậc kề trong cùng field là 1 hoặc 2.
- Không humanize bằng lệch thời gian.
- Không một preset dùng chung cho năm dòng.
- Không bật `_GUITAR_HALL`.
- Không đổi màu theo từng ensemble.

---

## 4. Cache và test

`RECAP_REVISION` là 64, `SPAN_REVISION` là 50. Cả humanize và preset đổi tiếng nghe, nên hai số tăng cùng một lần. File cũ không được phát lại. Revision 64 thay file 63 vì đỉnh cung nở ambient và nền nhiễu 16-bit chưa đúng ở 63.

Cửa nghe nylon ở 53, 56 và 59 vẫn quyết định có giữ trần ±2 hay không. Nếu ba mức đó không khác nhau trên nylon, ±2 cũng không khác, và trần có thể hạ ở một revision sau. Tối giản `classic` đi MS Basic, nhưng bước 2 trên thang velocity mượt chỉ khoảng vài phần mười dB. Cửa nylon đủ cho quyết định đó.

`backend/tests/test_humanize.py`:

- Ô study toàn 56 được nhích, mỗi cú đánh trong `{-2, -1, 0, +1, +2}`, rồi vẫn thấp hơn bè trầm 60.
- Etude 11 (49, 50, 51, 51) đứng yên vì bậc kề là 1. Etude 1 (`50 50 50 | 52 52 | 54 54 54 | 52 52 | 50 50 50`) đứng yên vì bậc kề là 2. Vòm tremolo đứng yên vì các nốt liền nhau không bằng nhau.
- Gốc và quãng 5 cùng phách, cùng field, khác `midi`, nhận một độ lệch. Hợp âm ba nốt cùng lực cũng vậy. Khóa là `(variant, ensemble, field, bar, beat)`.
- Offset làm đảo thứ tự liên bè thì hạ về phía 0. Cùng đầu vào thì cùng đầu ra.
- `tie_stop` không nằm trong plateau. Cùng lực viết với cú đánh thì bằng lực đã humanize. Đỉnh cung viết lực khác thì giữ số đó.
- Nốt nghỉ và `velocity is None` đứng yên.

Test velocity hiện có của guitar, jazz, tối giản và ambient giữ nguyên, vì `render()` không gọi humanize.

Preset: một test nhỏ khóa `variant` → chuỗi FFmpeg (`vintage` giao hưởng, `vintage` guitar, `club`, `wood`, `air`), và khóa rằng WAV đã tô bị cắt về số sample của WAV khô. Không khóa file WAV mẫu. Nghe tay năm dòng vẫn là chỗ chỉnh hệ số; lần nghe đó có thể tăng revision thêm một bậc.
