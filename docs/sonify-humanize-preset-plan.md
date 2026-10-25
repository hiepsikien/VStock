# Humanize và lớp màu sau bản nhạc

> **Trạng thái**: kế hoạch đã sửa sau review. Chưa code.
>
> Biên độ humanize chưa khóa. Trần đang xét là ±2, và chỉ trên plateau. Trước khi chọn số, nghe nylon ở velocity 53, 56 và 59. ±1..±3 như bản trước làm phẳng contour vừa viết và gần như không đổi tiếng trên phần lớn MuseSounds.

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

### Chỉ plateau mới nhích

Một plateau là một chuỗi cú đánh liền nhau trong cùng một field, viết cùng một velocity. Đó là việc của filter. Cả ô study ở 56 là một plateau.

Nốt đã có bước viết thì giữ nguyên. Ba chỗ vừa khóa nằm trong nhóm này:

- Etude 11 nghiêng từng bước 1 (`_ETUDE11_TILT`). Với hairpin 60, band `mf`, bốn nốt trong ra khoảng 49, 50, 51, 51.
- Vòm tremolo Barrios lấy biên trong ô là 8. Các phách cách nhau từ 6. Bước 2 đã bị bỏ vì không nghe được trên chương dài.
- Đỉnh giai điệu 72 cạnh nền 64 là bước 8.

Một độ lệch nghe được mà vẫn nhỏ hơn các bước đã soạn thì không đứng cùng một lúc với bước 1 của Etude 11. Vì vậy nốt đã có bước thì đứng yên. Filter không cố làm chúng "đỡ máy" thêm.

### Độ lệch trên plateau

Mỗi cú đánh trên plateau được cộng một số trong `{-2, -1, +1, +2}`. Trần là 2. Số 0 được phép khi một số khác 0 sẽ phá một ràng buộc bên dưới. Chưa khóa bước 1 hay bước 2 cho đến khi nghe nylon.

Số đó cố định theo `(variant, ensemble, field, bar, beat, midi)`, không dùng `random` và không dùng `hash()` của Python. Cùng một bản ra cùng một file, vì cache tiếng khóa theo revision.

Hai nốt cùng phách, cùng field, cùng lực viết là một tiếng. Dyad ngón cái tremolo đang cùng lực phải nhận cùng một độ lệch. Chúng không bị tách như hai nốt của một hợp âm khối.

Nốt ở hai field khác nhau, đang kêu cùng lúc, giữ thứ tự đã viết. Bè trầm study 60 và bè trung 56 cách nhau 4. ±2 mỗi bên có thể kéo về bằng nhau. Kết quả phải còn trầm lớn hơn trung. Trần villa cùng kiểu: trầm chỉ thấp hơn giai điệu 1, bè trung thấp hơn 2 hoặc 4. Một delta trên plateau không được đảo các khoảng đó.

`tie_stop` lấy velocity đã humanize của cú đánh, không lấy số viết ban đầu. Bỏ qua `tie_stop` thì nốt nối giữ số cũ và lệch khỏi cú đánh đúng bằng offset.

Cao độ, độ dài, cờ nhấn, và chữ động lực in trên giấy không đổi. Kẹp trong `1..127`.

### Chỗ tai nghe được

Đo trong `docs/sonify-symphony-dynamics.md`:

- Bỏ qua hoàn toàn `<note dynamics>`: hơi, dây, đồng, hợp xướng, piano và harp. Kèn cor nằm trong nhóm đó, cùng trumpet, trombone, tuba. Trên các giọng này filter không đổi tiếng. Lớp này không sửa chữ in và không sửa hairpin.
- Nghe cả chữ in lẫn velocity từng nốt, trong số đã đo: glockenspiel, crotales, vibraphone. Trên glockenspiel, velocity 46 lên 96 tăng peak 7,3 dB, nên ±3 khoảng 0,4 dB và ±2 còn nhỏ hơn.
- Marimba mới được đo peak để cân gain. Chưa đo xem nó có đọc `<note dynamics>` hay không.

Nylon nghe được nếu thư viện đổi lớp mẫu trong khoảng đang xét. Sax, Rhodes, flute, piano, dây và kèn không đổi. Tối giản `classic` đi MS Basic, nên velocity MIDI có tiếng. Ambient gần như im, trừ celesta và chuông nếu chúng đọc velocity.

Cache khóa theo revision. Cả năm dòng bị render lại khi tăng revision. Đo nylon ở 53, 56 và 59 trước khi khóa biên độ. Nếu ba mức đó không đổi tiếng nylon, filter plateau không đủ lý do để tăng revision một mình.

---

## 2. Màu bản ghi — một preset cho mỗi dòng

Lớp này chạy sau khi MuseScore đã viết WAV. Bản nhạc đã xong. Sạch tuyệt đối nghe khô. Mỗi dòng được một ít không khí của một cách thu, và không dòng nào được một lớp nhiễu rõ.

`_transcode_m4a` hiện bỏ `variant` và encode không filter. `_GUITAR_HALL` (kệ cao, echo, nới stereo) không được gọi. Guitar không bật chuỗi đó.

Thứ tự, cả recap ngày và span, khớp cách `SessionRecap` chia thời gian: sóng và playhead theo độ dài file, nến theo `mapDurationSec`.

1. MuseScore viết WAV khô.
2. FFmpeg tô màu ra một WAV thứ hai, theo `variant`.
3. Cắt WAV đã tô về đúng độ dài WAV khô. `aecho` và reverb của FFmpeg nối thêm đuôi. Không cắt thì đuôi đó kéo dài đoạn chart đang đứng ở nốt cuối.
4. `waveform_peaks` đo trên WAV đã tô và đã cắt.
5. Encode m4a từ WAV đó. Không gắn filter thêm ở bước encode.

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

Chọn phản xạ sớm vài chục ms, mức ướt thấp. Decay 0,4 giây phủ khoảng ba móc đơn ở 120 BPM, đủ để nhòe ostinato, nên không dùng. Nếu phản xạ sớm vẫn quá khô, nghe một phòng ngắn trên vòng nhanh nhất rồi chọn một trong hai, không cộng cả hai.

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
- Không humanize nốt đã có bước viết.
- Không humanize bằng lệch thời gian.
- Không một preset dùng chung cho năm dòng.
- Không bật `_GUITAR_HALL`.
- Không đổi màu theo từng ensemble.
- Không code biên độ trước khi nghe nylon ở 53, 56 và 59.

---

## 4. Cache và test

Đổi tiếng nghe thì tăng `RECAP_REVISION` và `SPAN_REVISION`. Hai số hiện tại là 62 và 48. File cũ không được phát lại. Chưa tăng trong lúc kế hoạch còn chờ lần nghe nylon.

`backend/tests/test_humanize.py`, khi đã code:

- Một plateau cùng velocity được nhích, mỗi cú đánh lệch trong trần đã chọn, tối đa ±2.
- Etude 11 (49, 50, 51, 51) và một vòm tremolo đã có bước thì đứng yên.
- Dyad cùng phách, cùng field, cùng lực viết nhận một độ lệch.
- Bè trầm 60 và bè trung 56 đang kêu cùng lúc vẫn còn trầm lớn hơn trung.
- `tie_stop` bằng lực đã humanize của cú đánh.
- Nốt nghỉ và `velocity is None` đứng yên.
- Cùng đầu vào thì cùng đầu ra.

Test velocity hiện có của guitar, jazz, tối giản và ambient giữ nguyên, vì `render()` không gọi humanize.

Preset: một test nhỏ khóa `variant` → chuỗi FFmpeg (`vintage` giao hưởng, `vintage` guitar, `club`, `wood`, `air`), và khóa rằng WAV đã tô bị cắt về số sample của WAV khô. Không khóa file WAV mẫu. Nghe tay năm dòng trước khi tăng revision.
