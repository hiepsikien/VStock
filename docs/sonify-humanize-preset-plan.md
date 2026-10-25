# Humanize và lớp màu sau bản nhạc

> **Trạng thái**: kế hoạch, chưa code.
>
> Hai lớp xếp sau khi bản đã soạn xong. Lớp 1 sửa velocity trên nốt. Lớp 2 tô màu file tiếng. Không lớp nào viết lại nốt, hợp âm, hay đường động lực đã có.

Năm dòng nhạc là năm `variant`: `symphony`, `jazz`, `minimalist`, `ambient`, `guitar`. Bộ nhạc cụ bên trong một dòng (`wood`, `brass`, `soul`, `organ`, …) dùng chung màu của dòng đó.

---

## 1. Humanize — một filter cho cả năm dòng

Nhiều đoạn nghe như máy vì một bè giữ nguyên một velocity suốt một chuỗi nốt liền nhau. Guitar thấy rõ điều này: cả bè trung một ô có thể đứng ở 56, cả bè trầm đứng ở 60.

Filter chạy một lần, sau `render()`, ngay trước `score_to_musicxml`, ở cả hai đường xuất trong `audio.py` (recap ngày và span). Không gắn vào `_finish` của `render()`: các test guitar đang khóa velocity từng nốt, và lớp này là màu nghe cuối, không phải một quyết định soạn nhạc.

Module mới: `backend/app/sonify/humanize.py`. Hàm `humanize(score) -> Score`.

### Đơn vị là từng bè

Mỗi part là một dòng riêng. Nốt trong part đó xếp theo `(bar, beat)`.

| Dòng | Part được xét |
|---|---|
| Guitar | `lead` (cao), `support` (trung), `low` (trầm) |
| Bốn dòng kia | `high`, `lead`, `support`, `comp`, `low` — part nào có nốt thì xét part đó |

Cùng một phách mà nhiều bè cùng kêu, mỗi bè nhận một độ lệch riêng. Trong một part, hai nốt chồng cùng phách (hợp âm khối) cũng lệch riêng, không nhích cả khối.

Nốt nghỉ và nốt `velocity is None` giữ nguyên. Nốt `tie_stop` giữ velocity của cú tấn công đã có, không bốc một độ lệch mới.

### Độ lệch

Mỗi cú tấn công cộng một số trong `{-3, -2, -1, +1, +2, +3}`. Không có 0: mục đích là chuỗi nốt cùng lực phải nhích.

Số đó cố định theo `(variant, ensemble, part, bar, beat, midi, voice)`, không dùng `random` và không dùng `hash()` của Python. Cùng một bản phải ra cùng một file, vì cache tiếng khóa theo revision.

Hai ràng buộc sau khi cộng:

- Hai nốt liền nhau trong một bè mà lực viết bằng nhau thì lực nghe phải khác nhau ít nhất 1.
- Nốt viết to hơn nốt kế phải vẫn to hơn hoặc bằng. Một bước viết từ 4 trở lên (nhấn +8, đỉnh 72 cạnh nền 64) không bị ±3 xóa. Bước viết 1–3 có thể bị kẹp lại cho khỏi đảo thứ tự.
- Kẹp trong `1..127`.

Cao độ, độ dài, cờ nhấn, và chữ động lực in trên giấy không đổi.

### Chỗ tai nghe được

`NoteEvent.velocity` thành `<note dynamics>` trong MusicXML. Guitar nylon phát lực này, nên filter nghe thấy trên guitar. Chuông và marimba cũng nghe cả chữ in lẫn velocity từng nốt.

Ghi trong `docs/sonify-symphony-dynamics.md`: hơi, dây, piano, harp và kèn cor của MuseSounds bỏ qua `<note dynamics>`, chỉ nghe chữ `<dynamics>` và `<wedge>`. Trên các giọng đó, ±1–3 vẫn được ghi vào bản nhưng tai không đổi. Lớp này không sửa chữ in và không sửa hairpin. Nếu sau khi nghe, giao hưởng vẫn phẳng, đó là một việc khác, ngoài kế hoạch này.

---

## 2. Màu bản ghi — một preset cho mỗi dòng

Lớp này chạy sau khi MuseScore đã viết WAV. Bản nhạc đã xong. Sạch tuyệt đối nghe khô; mỗi dòng được một ít không khí của một cách thu, và không dòng nào được một lớp nhiễu rõ.

`_transcode_m4a` hiện bỏ `variant` và không gắn filter (`audio.py`). `_GUITAR_HALL` (kệ cao, echo, nới stereo) đang không được gọi. Guitar không bật chuỗi đó: đó là mái vòm kính, không phải bản ghi vintage.

Thứ tự mới, cả recap ngày và span:

1. MuseScore viết WAV khô.
2. FFmpeg tô màu ra một WAV thứ hai, theo `variant`.
3. `waveform_peaks` đo trên WAV đã tô, để sóng trên chart khớp tiếng nghe.
4. Encode m4a từ WAV đã tô. Không gắn filter thêm ở bước encode.
5. `map_duration` vẫn là độ dài bản viết. Đuôi MuseScore để chart đứng ở nốt cuối, như hiện tại. Đuôi của preset phải ngắn hơn khoảng đó, không thành một đoạn nhạc mới.

Không có FFmpeg thì phát WAV khô, như hôm nay. Đỉnh không được nhô hơn bản khô: nếu saturation làm lớn, hạ lại trước khi đo peak. Hệ số dưới đây là điểm xuất phát, chỉnh sau khi nghe.

| Dòng | Preset | Vì sao | Không làm |
|---|---|---|---|
| `symphony` | `vintage` | Bản thu dàn nhạc analog, hơi ấm, hơi mờ ở trên cao | Xì đĩa, nứt, phòng hòa nhạc lớn |
| `guitar` | `vintage` | Đĩa guitar cổ điển thu gần, ấm, ít phòng | `_GUITAR_HALL`, mái vòm, nhiễu rõ |
| `jazz` | `club` | Combo thu gần trong phòng nhỏ: sax, Rhodes, vibraphone cần thân tiếng nhưng nhịp phải còn sắc | Băng vintage của dàn nhạc, nền xì, đuôi dài |
| `minimalist` | `wood` | Phòng gỗ ngắn, đều, để ostinato hết khô mà lưới phách không nhòe | Saturation bơm theo vòng lặp, wow, nhiễu |
| `ambient` | `air` | Một ít không khí xa, nhẹ, để kính và horn bớt sắc số | Nền xì trên drone, reverb dài phủ cả chương |

### `vintage` — giao hưởng

Bản thu dàn, khoảng cách vừa, băng nhẹ.

- Kệ cao khoảng 8 kHz, hạ khoảng 2 dB.
- Ấm nhẹ ở khoảng 200–400 Hz.
- Saturation rất nhẹ.
- Nền nhiễu trộn vào khoảng −60 dB hoặc thấp hơn. Nghe là "không phải file trắng", không phải tiếng xì.
- Phòng ngắn, sớm, mức ướt thấp.

### `vintage` — guitar

Cùng ý bản ghi cũ, thu gần hơn giao hưởng. Móng tay và tiếng dây phải còn.

- Ấm nhẹ, kệ cao nông hơn giao hưởng (khoảng 1 dB).
- Phòng nhỏ, chỉ phản xạ sớm, ngắn hơn chuỗi giao hưởng.
- Nền nhiễu thấp hơn giao hưởng.
- Không echo dài, không `extrastereo`.

Hai chuỗi `vintage` là hai filter FFmpeg. Chúng chung tên preset, khác hệ số.

### `club` — jazz

Sax, kèn, Rhodes, Hammond, vibraphone và bass điện nghe khô khi không có phòng. Phòng thu nhỏ cho thân tiếng. Đuôi dài làm nhòe swing.

- Phản xạ sớm, cỡ vài chục ms, mức thấp.
- Saturation nhẹ trên cả bus, như qua bàn analog.
- Không nguồn nhiễu. Hơi kèn đã là nhiễu của dòng này.
- Không cắt cao sâu: vibraphone và kèn cần khoảng trên.

### `wood` — tối giản

Mallet, guitar thép, piano đứng, hợp xướng và pulse cần lưới rõ. Khô quá thì nghe như file MIDI. Nhiễu hoặc wow làm mờ vòng lặp.

- Chỉ phản xạ sớm của phòng gỗ, decay dưới khoảng 0,4 giây, mức ướt thấp.
- Không saturation, không nguồn nhiễu, không nới stereo.

### `air` — ambient

Drone, halo, kính và horn đã ngân dài và đã có diminuendo (`docs/sonify-ambient.md`). Xì trên nốt dài sẽ thành nội dung của bài. Reverb phủ cả chương sẽ xóa ranh câu và kéo file dài hơn `map_duration`.

- Làm mềm phía trên, nhẹ, để celesta và flute bớt tiếng số.
- Không khí mức thấp, đuôi vừa phải và tắt trong khoảng release sẵn có của MuseScore.
- Không nguồn nhiễu.
- Không một bed reverb riêng ở cuối chương. Đuôi cuối bài vẫn là đuôi MuseScore hiện tại.

---

## 3. Việc không làm trong đợt này

- Không sửa pattern, dialect, chữ `p–f`, hay hairpin.
- Không humanize bằng lệch thời gian.
- Không một preset dùng chung cho năm dòng.
- Không bật `_GUITAR_HALL`.
- Không đổi màu theo từng ensemble. `brass` vẫn `vintage` của giao hưởng; `soul` và `organ` vẫn `club`.

---

## 4. Cache và test

Đổi tiếng nghe thì tăng `RECAP_REVISION` và `SPAN_REVISION` trong `audio.py`. File cũ không được phát lại.

`backend/tests/test_humanize.py`:

- Một bè nhiều nốt cùng velocity ra các lực khác nhau, mỗi nốt lệch đúng ±1..±3 so với lực viết.
- Hai bè cùng phách không nhận cùng một độ lệch.
- Nốt viết to hơn vẫn không bị nốt sau vượt.
- `tie_stop` giữ lực của cú tấn công.
- Nốt nghỉ và `velocity is None` đứng yên.
- Cùng đầu vào thì cùng đầu ra.

Test velocity hiện có của guitar, jazz, tối giản và ambient giữ nguyên, vì `render()` không gọi humanize.

Preset: một test nhỏ khóa `variant` → chuỗi FFmpeg (`vintage` giao hưởng, `vintage` guitar, `club`, `wood`, `air`). Không khóa file WAV mẫu. Nghe tay năm dòng, mỗi dòng một đoạn có nhiều nốt liền nhau trong một bè, trước khi tăng revision.
