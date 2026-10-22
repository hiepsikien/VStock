# Nhịp và khung chương

Kế hoạch bổ sung nhịp cho bốn dạng nghe, và gắn warm-up với cool-down vào từng chương từ 1M trở lên. Form, BPM và chỗ nghỉ giữa chương nằm ở `docs/sonify-long-form.md`. Khung 2 ô của bản ngày nằm ở `daily_frame.py` và `ambient.py`. Chủ âm của sonata giao hưởng nằm ở `docs/sonify-sonata-mode.md`. 1D và 1W giữ nguyên.

Hôm nay mọi bản đều là 4/4. `BEATS_PER_BAR = 4`, mỗi ô 8 móc đơn, phách mạnh ở móc 0 và 4. Một nốt dài cả ô được viết 4 phách. Jazz bật `swing` tỉ lệ 2:1 trên từng cặp móc đơn. `_spell` cắt trong ô tại `HALF_BAR = 4`. `BASS_PATTERNS`, `left_hand` và ostinato tối giản cũng viết theo ô 8 móc.

## Hai nhịp thêm cho mỗi dạng

4/4 vẫn là nhịp nhà của chương nhanh, chương kết, finale và các tháng mở hoặc khép của giao hưởng và jazz. Nhịp mới gắn vào vai, cùng một cách cho mọi mã. Đồng hồ của thân chương giữ nguyên: BPM vẫn là phách đen trong bảng form, số móc đơn của thân chương giữ nguyên, chỉ dựng lại vạch ô.

| Dạng | Thêm | Phách mạnh | Vai |
|---|---|---|---|
| Giao hưởng | 3/4, 6/8 | 3/4: phách 1. 6/8: móc đơn 0 và 3 | 3/4 cho scherzo (1M-III). 6/8 cho chương chậm (1M-II, 3M-II, tháng 2, 5, 8, 11) |
| Jazz | 3/4, 12/8 | 3/4: phách 1, hợp âm thêm ở phách 3. 12/8: móc đơn 0, 3, 6, 9 | 3/4 cho bài ngắn (1M-III). 12/8 cho ballad (1M-II, 3M-II, tháng 2, 5, 8, 11) |
| Tối giản | 5/4, 7/8 | 5/4 nhóm 3+2, nhấn móc 0 và 6. 7/8 nhóm 2+2+3, nhấn móc 0, 2 và 4 | 5/4 cho chương mở (1M-I, 3M-I, tháng 1, 4, 7, 10). 7/8 cho scherzo và chương khép nhanh (1M-III, 3M-III, tháng 3, 6, 9) |
| Ambient | 3/4, 6/4 | 3/4: phách 1. 6/4: móc đơn 0, 4 và 8 | 3/4 cho scherzo (1M-III). 6/4 cho chương chậm (1M-II, 3M-II, tháng 2, 5, 8, 11) |

Độ dài một ô, tính bằng móc đơn và bằng phách đen:

| Nhịp | Móc đơn | Phách đen | Nốt tròn cả ô | `swing` khi dạng là jazz |
|---|---|---|---|---|
| 4/4 | 8 | 4 | nốt tròn, đã có | bật |
| 3/4 | 6 | 3 | nốt trắng chấm, đã có | bật |
| 6/8 | 6 | 3 | nốt trắng chấm. Hai phách là móc đen chấm | giao hưởng, tắt |
| 12/8 | 12 | 6 | nốt tròn chấm. Bốn phách là móc đen chấm | tắt |
| 5/4 | 10 | 5 | trắng chấm buộc với trắng | tối giản, tắt |
| 6/4 | 12 | 6 | nốt tròn chấm | ambient, tắt |
| 7/8 | 7 | 3,5 | đen buộc với đen buộc với đen chấm | tối giản, tắt |

`swing` là cờ của score, theo cặp dạng và nhịp. Giao hưởng, tối giản và ambient luôn tắt. Jazz bật ở 4/4 và 3/4. Jazz 12/8 tắt: nhịp này đã là 4/4 viết thành bốn nhóm ba móc đơn đều nhau. `<swing>` 2:1 trong `musicxml.py` bẻ từng cặp móc chẵn–lẻ, nên móc 3 (phách 2 của 12/8) bị co và cả ballad trật phách.

`_NOTE_TYPES` thêm `6.0: ("whole", 1)` cho nốt tròn chấm. Ô 5 phách và 3,5 phách không có một loại nốt. Chúng đi qua `_spell` thành nốt buộc. Ô 7/8 vì vậy là đen + đen + đen chấm, theo nhóm 2+2+3 móc đơn.

## Dựng lại ô

Một câu vẫn dài xấp xỉ 64 móc đơn, bằng câu 8 ô 4/4. Mỗi section kết thúc đúng vạch ô mới. 6/8, 3/4, 12/8 và 6/4 chia hết số móc của các chương chậm và scherzo hiện có, nên đồng hồ thân chương không đổi. 5/4 và 7/8 lệch tối đa 8 móc đơn; phần lệch chỉ rút ở coda.

Cụm xuất vẫn là ranh giới câu trong một score, cùng quy ước `docs/sonify-long-form.md`. Số ô dưới đây là thân chương, trước khi cộng khung.

### 1M

Chương I giao hưởng, jazz và ambient ở lại 96 ô 4/4, 96 BPM, 4:00. Chương IV cả bốn dạng ở lại 96 ô 4/4, 96 BPM, 4:00. Chương II của tối giản ở lại 72 ô 4/4, 72 BPM, 4:00.

| Chương | Dạng | Nhịp | Ô | BPM | Đồng hồ | Đoạn | Cụm |
|---|---|---|---|---|---|---|---|
| I | Tối giản | 5/4 | 76 | 96 | 3:58 | 8, 24, 20, 16, 8 | 32, 52, 76 |
| II | Giao hưởng | 6/8 | 96 | 72 | 4:00 | 8, 32, 24, 32 | 40, 96 |
| II | Jazz | 12/8 | 48 | 72 | 4:00 | 4, 16, 12, 16 | 20, 48 |
| II | Ambient | 6/4 | 48 | 72 | 4:00 | 4, 16, 12, 16 | 20, 48 |
| III | Giao hưởng, Ambient | 3/4 | 96 | 120 | 2:24 | 8, 24, 24, 24, 8, 8 | 56, 96 |
| III | Jazz | 3/4 | 96 | 120 | 2:24 | 8, 24, 24, 24, 8, 8 | 56, 96 |
| III | Tối giản | 7/8 | 82 | 120 | 2:23 | 8, 16, 16, 16, 14, 12 | 40, 82 |

Chương II vẫn không có outro giá. 5/4 của chương I rút 8 móc ở coda (768 xuống 760). 7/8 của chương III rút 2 móc ở coda (576 xuống 574).

### 3M

Chương I giao hưởng, jazz và ambient ở lại 192 ô 4/4, 96 BPM, 8:00. Chương II của tối giản ở lại 120 ô 4/4, 60 BPM, 8:00. Chương III giao hưởng, jazz và ambient ở lại 216 ô 4/4, 108 BPM, 8:00.

| Chương | Dạng | Nhịp | Ô | BPM | Đồng hồ | Đoạn | Cụm |
|---|---|---|---|---|---|---|---|
| I | Tối giản | 5/4 | 153 | 96 | 7:58 | 6, 45, 51, 38, 13 | 51, 102, 153 |
| II | Giao hưởng | 6/8 | 160 | 60 | 8:00 | 8, 44, 56, 44, 8 | 52, 108, 160 |
| II | Jazz | 12/8 | 80 | 60 | 8:00 | 4, 24, 24, 24, 4 | 28, 52, 80 |
| II | Ambient | 6/4 | 80 | 60 | 8:00 | 4, 24, 24, 24, 4 | 28, 52, 80 |
| III | Tối giản | 7/8 | 246 | 108 | 7:58 | 9, 64, 73, 55, 45 | 73, 146, 246 |

5/4 rút 6 móc (1536 xuống 1530). 7/8 rút 6 móc (1728 xuống 1722).

### 1Y

Tháng finale, tháng 12, cả bốn dạng ở lại 108 ô 4/4, 96 BPM, 4:30. Tháng giữa của tối giản ở lại 72 ô 4/4, 66 BPM, 4:22. Tháng khép của giao hưởng, jazz và ambient ở lại 84 ô 4/4, 108 BPM, 3:07. Tháng mở của giao hưởng, jazz và ambient ở lại 80 ô 4/4, 100 BPM, 3:12.

| Vị trí | Dạng | Nhịp | Ô | BPM | Đồng hồ | Đoạn | Cụm |
|---|---|---|---|---|---|---|---|
| Mở (1, 4, 7, 10) | Tối giản | 5/4 | 64 | 100 | 3:12 | 8, 24, 24, 8 | 32, 64 |
| Giữa (2, 5, 8, 11) | Giao hưởng | 6/8 | 96 | 66 | 4:22 | 8, 32, 24, 24, 8 | 40, 96 |
| Giữa | Jazz | 12/8 | 48 | 66 | 4:22 | 4, 16, 12, 12, 4 | 20, 48 |
| Giữa | Ambient | 6/4 | 48 | 66 | 4:22 | 4, 16, 12, 12, 4 | 20, 48 |
| Khép (3, 6, 9) | Tối giản | 7/8 | 96 | 108 | 3:07 | 8, 36, 36, 16 | 44, 96 |

Tháng mở 5/4 và tháng khép 7/8 chia hết, không rút coda.

## Meter trên FormSpec

`FormSpec` nhận một `Meter`: tử số, mẫu số, móc mạnh, và điểm cắt trong ô. 4/4 mặc định là `(4, 4)`, móc mạnh `(0, 4)`, cắt tại `(4,)`. `bars` của spec là số ô của nhịp đó. `eighths` bằng `bars * meter.eighths_per_bar`. Đồng hồ lấy từ tổng móc đơn, vì BPM là phách đen.

Điểm cắt trong ô, `subbar_breaks`, là các móc đơn mà `_spell` phải dừng. Nốt phủ cả ô vẫn là một nốt khi độ dài phách đen có trong `_NOTE_TYPES` (3, 4 hoặc 6). Ô 5/4 và 7/8 luôn cắt, rồi buộc:

| Nhịp | `subbar_breaks` | Mảnh trong ô |
|---|---|---|
| 4/4 | `(4,)` | 4+4, như `HALF_BAR` hôm nay |
| 3/4 | `(4,)` | không mảnh nào dài quá 4 móc, để khỏi nốt 2,5 phách |
| 6/8 | `(3,)` | 3+3, hai phách đen chấm |
| 12/8 | `(3, 6, 9)` | bốn nhóm ba móc |
| 6/4 | `(6,)` | hai nốt trắng chấm |
| 5/4 | `(6,)` | 6+4 móc, trắng chấm buộc với trắng, đúng nhóm 3+2 |
| 7/8 | `(2, 4)` | 2+2+3 móc, đen buộc với đen buộc với đen chấm |

`_spell` hôm nay cắt mọi nốt giữa ô tại móc 4. Trong 6/8, nốt ở phách 2 (móc 3–6) bị xẻ thành một móc và một đen. Hàm đọc `meter.subbar_breaks` và `meter.eighths_per_bar`.

Những chỗ đang đọc hằng `BEATS_PER_BAR`, `EIGHTHS_PER_BAR` hoặc `HALF_BAR` chuyển sang meter của spec đang soạn:

- `quantize_strong_beats` và `STRONG_EIGHTHS` trong `phrasing.py`
- `STRONG_BEAT_EIGHTHS` trong `quantize.py`, dùng bởi `bar_quantization_loss`
- `_prev_last_touched_strong` trong `form.py`. Hôm nay hàm coi móc mạnh cuối ô là dải `range(4, 8)`. Dải đó trở thành các móc từ móc mạnh cuối cùng đến hết ô
- `BASS_PATTERNS` trong `render.py`. Pattern 8 móc tràn sang ô sau khi ô chỉ có 6 móc
- `left_hand` trong `phrasing.py`. `duration_beats` bằng số phách đen của ô. 4.0 tràn ô 3/4 và 6/8, và thiếu phách ở 12/8 với 6/4. Jazz gọi cùng hàm này
- walking bass và comp của jazz
- ostinato, sub-bass và pulse của tối giản. `ostinato_offsets` dài 8. Móc thứ 8 của ô 5/4 đọc quá tuple. `_sub_bass_part` lặp `range(BEATS_PER_BAR)` với nốt đen. Ô 7/8 dài 3,5 phách đen, không có bốn nốt đen
- quy tắc ambient ở mục Phối khí
- thẻ `<time>` lấy tử số và mẫu số từ meter, viết một lần ở ô đầu

Ô nghỉ trọn, `midi is None` và dài đúng một ô, xuất một `<rest measure="yes"/>`. `<duration>` bằng cả ô. Thẻ `<type>` bỏ qua. `_add_note` hôm nay gọi `_note_type` cho cả nốt nghỉ, và chỉ gắn `measure="yes"` khi `duration_beats == 4`. Nghỉ 5/4 hoặc 7/8 mà bị `_spell` xẻ đôi sẽ hỏi `_note_type(5.0)` hoặc `_note_type(3.5)` và văng `KeyError`. `written()` giữ nguyên một sự kiện nghỉ khi nghỉ phủ cả ô, kể cả nhịp không có nốt tròn một mảnh.

Khóa cache của chương thêm tử số, mẫu số và cờ swing. File 4/4 đã render không dùng cho chương đã đổi nhịp.

## Đồng hồ và playhead

`piece_seconds` nhận tổng móc đơn:

```text
seconds = total_eighths * 30 / bpm
```

Một móc đơn là nửa phách đen, nên mỗi móc kéo dài `30 / bpm` giây. 576 móc ở 72 BPM là 240 giây, đúng 4:00 của chương chậm 1M. `movement_duration` và hai lời gọi trong `audio.py` truyền số móc của score. Tử số 6, 12 hoặc 7 không đưa vào `beats_per_bar`: tham số đó đang đếm phách đen, còn tử số của nhịp /8 không phải số phách đen. 96 ô với `beats_per_bar=6` ở 72 BPM ra 8:00, gấp đôi chương.

`plan_span(symbol, span, variant)` nhận dạng nghe. `get_span` đã có `variant` nhưng đang gọi `plan_span(sym, range)`. Số ô và nhịp từ 1M trở đi phụ thuộc dạng, nên spec, `durationSec` và đường audio phải chọn theo dạng. 1W vẫn một lưới 4/4 cho cả bốn dạng.

`SpanMovementResponse` thêm `warmupSec` và `cooldownSec`, cắt từ chính `durationSec` theo số ô khung. `SpanRecap` hôm nay gọi `candleIndexAt`, hàm chia đều từ giây 0 đến hết file. Playhead chương dài dùng cùng luật giữ hai đầu với `ambientDailyCandleIndexAt`: trước `warmupSec` đứng ở nến đầu, từ `durationSec - cooldownSec` đứng ở nến cuối, thân trải giữa hai mốc. 1W gửi hai đầu bằng 0 và playhead chạy suốt file.

## Phối khí

Nhịp mới nghe ra chất khi bè đệm bám nhóm phách của ô. Pattern 4/4 hiện có giữ nguyên trên các chương còn ở 4/4.

### Giao hưởng

6/8 là pastorale, đung đưa trên hai phách đen chấm. Bass và piano nhấn móc 0 và móc 3. Ba phách đen 0, 2, 4 là chất 3/4, dành cho scherzo.

Bass 6/8, cùng các mức thanh khoản với `BASS_PATTERNS`:

| Mức | Mẫu, (móc bắt đầu, dài, bậc) |
|---|---|
| `p` | `(0, 6, gốc)` một trắng chấm |
| `mp` | `(0, 3, gốc), (3, 3, quãng 5)` hai đen chấm |
| `mf` | `(0, 2, gốc), (2, 1, quãng 5), (3, 2, quãng 8), (5, 1, quãng 5)` |
| `f` | sáu móc đơn, nhấn móc 0 và móc 3 |

Piano 6/8: tay trái giữ gốc cả ô, `duration_beats = 3`. Tay phải đặt guide tone ở móc 0, dài một đen chấm. Fill cuối câu rải ở móc 3, 4, 5.

Bass 3/4, scherzo 1M-III ở 120 BPM:

| Mức | Mẫu |
|---|---|
| `p` | `(0, 6, gốc)` |
| `mp` | `(0, 4, gốc), (4, 2, quãng 5)` trắng rồi đen |
| `mf` | `(0, 2, gốc), (2, 2, quãng 5), (4, 2, quãng 5)` ba phách đen |
| `f` | sáu móc đơn, nhấn móc 0 |

`bar_quantization_loss` của mọi ô 3/4, kể cả jazz waltz, giữ trọng số 2,5 ở móc 0 và thêm trọng số 0,8 ở móc 4. Phách 3 được hợp âm chăm, bước nhảy qua vạch ô đỡ hẫng. Các nhịp khác chỉ trọng số mạnh trên `meter.strong_eighths`.

### Jazz

3/4 bật swing. Walking bass:

- `p` và intro: trắng rồi đen. Gốc ở phách 1 dài 2 phách, quãng 5 hoặc nốt dẫn ở phách 3 dài 1 phách.
- `mp`, `mf`, `f`: ba phách đen. Phách 1 gốc, phách 2 quãng 3 hoặc quãng 5, phách 3 là nốt dẫn về gốc ô sau.

Rhodes 3/4 thay Charleston của 4/4. Ô chẵn là waltz charleston: hợp âm ở phách 1 dài 1,5 phách, rồi một móc đơn ở phách 1,5 (phách rưỡi của phách 2). Ô lẻ đánh hợp âm ở phách 1 và phách 3.

12/8 tắt swing. Ở 60 BPM một phách đen chấm dài 1,5 giây. Ở 66 BPM còn khoảng 1,36 giây. Bốn nốt đen chấm khô và Rhodes chỉ chạm móc 3 với móc 9 sẽ nghe thưa.

- `p` và intro: hai-feel. Gốc 6 móc từ móc 0, quãng 5 sáu móc từ móc 6.
- `mp`, `mf`, `f`: bốn phách đen chấm, và thêm móc đơn dẫn ở móc 5 và móc 11. Đó là nốt cuối của nhóm ba móc thứ hai và thứ tư: hai móc liền trước là một đen, móc dẫn đẩy vào phách mạnh kế tiếp. Đây là cú pickup của ballad và slow blues.
- Rhodes đánh ở móc 3 và móc 9, mỗi tiếng dài một đen chấm (1,5 phách) để suitcase piano ngân qua phách sau.

### Tối giản

`ostinato_offsets` dài đúng số móc của ô. 4/4 giữ `(0, 1, 2, 1, 0, 2, 1, 2)`. Backbeat phách 2 và 4 chỉ còn trên 4/4.

5/4, nhóm 3+2 tức 6+4 móc:

- Arpeggio P1: `(0, 1, 2, 1, 0, 2, 0, 1, 2, 1)`. Tenuto ở móc 0 và móc 6. Accent ở móc 0, và nhẹ hơn ở móc 6 khi filter mở.
- Sub-bass P4: năm nốt đen. Tenuto ở phách 1 (`beat == 0`) và ở phách 4 (`beat == 3`, đầu nhóm 2). Mức `f` nâng quãng 8 ở phách 5 (`beat == 4`).
- Pulse P3, khuông 2: stab ở phách 2 (móc 2) và phách 5 (móc 8). Hai chỗ đó đóng nhịp 3+2. Các phách còn lại là nghỉ.

7/8, nhóm 2+2+3 móc:

- Sub-bass đạp ba xung, không đếm phách đen. Móc 0 dài 2 móc (1 phách), móc 2 dài 2 móc, móc 4 dài 3 móc (đen chấm). Mức `f` đưa xung thứ ba lên quãng 8.
- Arpeggio: `(0, 1, 0, 2, 0, 1, 2)`. Tenuto và accent tại móc 0, 2, 4.
- Pulse khuông 1: `p` là hai nốt, móc 0 dài 4 móc và móc 4 dài 3 móc. `mp` là ba nốt tại móc 0, 2, 4. `mf` là bảy móc đơn. `f` là 14 móc kép, nhấn đầu mỗi nhóm tại móc kép 0, 4 và 8.
- Pulse khuông 2 nghỉ suốt ô 7/8. Ba xung đã có ở sub-bass.

### Ambient

Drone 3/4 ngân hết 3 phách. Drone 6/4 ngân hết 6 phách. Kính vẫn đánh phách 1. Quãng 5 của drone vẫn chỉ trên ô `mf` và `f`.

`GLASS_HOLD` (32 móc), `PILLAR_GAP` (24), `SWELL_HOLD` (16) và `FLAT_HOLD` (32) giữ đơn vị móc đơn. Mỗi hằng làm tròn tới vạch ô của meter, trong khoảng một ô đến 36 móc. Đếm theo ô sẽ kéo sáo 6/4 cách nhau quá lâu, và nhồi sáo 3/4 ở 120 BPM.

| Hằng | 4/4 hôm nay | 3/4 | 6/4 |
|---|---|---|---|
| `GLASS_HOLD`, `FLAT_HOLD` | 4 ô, 32 móc | 5 ô, 30 móc | 3 ô, 36 móc |
| `PILLAR_GAP` | 3 ô, 24 móc | 4 ô, 24 móc | 2 ô, 24 móc |
| `SWELL_HOLD` | 2 ô, 16 móc | 2 ô, 12 móc, hai ô buộc nhau | 1 ô, 12 móc, hai trắng chấm buộc nhau |
| Shimmer | 8 móc | 1 ô, 6 móc | nửa ô, 6 móc |

`PILLARS_PER_EIGHT` hôm nay nhân với số ô rồi chia 8. Sang 6/4 cùng một thân 576 móc sẽ ít trụ hơn, vì ít ô hơn. Trần trụ tính trên móc: `2 * số móc của section / 64`.

## Warm-up và cool-down

Từ 1M trở lên, mỗi chương có một khung ở hai đầu file của chương đó. Warm-up đứng trước intro. Cool-down đứng sau outro. Chương II của 1M không có outro giá; cool-down đứng sau câu hát cuối và là đoạn kết của chương.

Nến không trải vào khung. Nhóm nguồn của các ô khung để trống, cùng cách `assign_daily_ambient_bars` để trống ô 0–1 và 32–33 của bản ngày. Playhead đứng ở nến đầu suốt warm-up và ở nến cuối suốt cool-down. Markov, cửa sổ thanh khoản, ngân sách chuông và shimmer chỉ chạy trên thân chương.

Khoảng im lặng do player chèn giữ nguyên và đứng sau cool-down: 6 giây với 1M, 8 giây với 3M, 4 giây trong một mùa và 8 giây khi sang mùa. Người nghe hết chương bằng cool-down, nghỉ đúng số giây đó, rồi vào chương sau bằng warm-up.

### Độ dài

Khung 1M và 3M dài khoảng 16 phách đen mỗi đầu, làm tròn lên thành ô chẵn:

| Nhịp | Ô mỗi đầu | Phách đen |
|---|---|---|
| 4/4 | 4 | 16 |
| 3/4, 6/8 | 6 | 18 |
| 12/8, 6/4 | 3 | 18 |
| 5/4 | 4 | 20 |
| 7/8 | 5 | 17,5 |

1Y dùng khoảng 8 phách đen mỗi đầu. Mười hai tháng thêm 16 phách hai đầu sẽ kéo bản năm thêm khoảng 4 phút, qua trần 45 phút. Riêng 12/8 và 6/4 của 1Y chỉ một ô mỗi đầu. Một ô đã dài 6 phách, khoảng 5,5 giây ở 66 BPM, sát mức 7 đến 9 phách của các nhịp còn lại.

| Nhịp | Ô mỗi đầu | Phách đen |
|---|---|---|
| 4/4 | 2 | 8 |
| 3/4, 6/8 | 3 | 9 |
| 12/8, 6/4 | 1 | 6 |
| 5/4 | 2 | 10 |
| 7/8 | 2 | 7 |

Đồng hồ cả tác phẩm sau khi cộng khung, phần thân đã tính cả chỗ coda bị rút. Mốc gốc 14:42, 24:16 và 45:00 đã gồm khoảng nghỉ:

| Range | Giao hưởng | Jazz | Tối giản | Ambient |
|---|---|---|---|---|
| 1M | 16:10 | 16:10 | 16:08 | 16:10 |
| 3M | 25:30 | 25:30 | 25:29 | 25:30 |
| 1Y | 47:21 | 46:59 | 47:20 | 46:59 |

Bản năm của jazz và ambient trước đó là 47:42 khi tháng giữa có hai ô khung. Một ô mỗi đầu rút 12 phách trên mỗi tháng giữa, bốn tháng ở 66 BPM là khoảng 44 giây, còn 46:59. Bốn dạng khi đó nằm trong khoảng một phút của nhau.

### Chỗ khung trong spec

`Section` thêm `warmup` và `cooldown`. Hai kind này không nhận regime, không có slot Markov, và không nằm trong `liquidity_windows_for`. Các section thân dịch sang phải đúng số ô warm-up, cùng cách thân 30 ô của bản ngày dịch sau `DAILY_WARMUP_BARS`.

Chương I giao hưởng của 1M, thân 96 ô 4/4 cộng khung 4 ô, thành 104 ô:

- warmup 0–4
- intro 4–12, phrase 12–44, phrase 44–68, phrase 68–92, outro 92–100
- cooldown 100–104

### Tiếng khung

Chủ âm warm-up là hợp âm mở của chương. Chủ âm cool-down là hợp âm kết của chương. Chương finale theo override trưởng hoặc thứ của `finale_outro` khi cả tác phẩm đổi chiều. Ô khung đạp hợp âm đó, không chạy tiến trình.

Khung 1M và 3M dài 10 đến 18 giây. Giao hưởng vào bè theo tầng, từ ô `warmup_bars // 2`:

- Nửa đầu: bass và cello từ `p`.
- Nửa sau: violin nhập, crescendo `p < mp` dẫn tới phách 1 của intro.

Bản ngày vẫn để violin từ ô 1 của khung 2 ô. 1Y khung ngắn, violin cũng vào ô `warmup_bars // 2`. Với hai ô, đó vẫn là ô thứ hai.

- Giao hưởng: cello và bass ngân từ phách 1 của warm-up. Violin giữ suốt cool-down. Hairpin từ `p` lên `mp` khi vào thân, rồi từ `mp` xuống `ppp` ở cool-down. Sáo nghỉ.
- Jazz: Rhodes warm-up theo nhịp chương. 4/4 giữ nốt trắng rồi nghỉ, như `_jazz_rhodes` của bản ngày. 3/4 dùng waltz charleston trên chủ âm. 12/8 ngân đen chấm ở các phách của ballad. Cool-down buộc tiếp cao độ đang hát khi nốt đó chạm vạch khung. Bass buộc gốc chủ âm.
- Tối giản: khung chỉ còn mạch phách đều trên chủ âm, tenuto ở phách 1 của mỗi ô. 7/8 dùng ba xung 2+2+3 thay vì nốt đen đều. Pad ngân và diminuendo tới `ppp`.
- Ambient: kính ngân chủ âm suốt warm-up và buộc sang câu đầu khi cùng cao độ và chạm biên. Cool-down kéo hơi đang chạm, tối đa hết khung, rồi nghỉ. Drone là pedal chủ âm.

`apply_daily_frame` vẫn chỉ nhận bản ngày 34 ô. Bản dài đi qua một lần gắn khung riêng, đọc `warmup` và `cooldown` trên spec, và dùng cùng luật buộc nốt với khung ngày: hơi cuối phrase còn cách vạch một móc đơn vẫn được nối, vì khoảng đó là hơi thở.

## Thứ tự làm

1. `Meter` trên `FormSpec`, gồm móc mạnh, `subbar_breaks` và cách tính giây từ móc đơn. Mặc định 4/4. MusicXML viết đúng thẻ `<time>`. Bản ngày và mọi chương 4/4 nghe như hiện tại.
2. `_spell` cắt theo `subbar_breaks`. Nghỉ trọn ô là một `<rest measure="yes"/>` và không có `<type>`. `bar_quantization_loss` cùng `_prev_last_touched_strong` đọc móc mạnh của meter. Ô 3/4 thêm trọng số 0,8 ở móc 4.
3. `plan_span(symbol, span, variant)`. `SpanMovementResponse` có `warmupSec` và `cooldownSec`. `SpanRecap` giữ playhead ở hai đầu khung.
4. Giao hưởng 3/4 và 6/8, kèm bảng bass và piano. `left_hand` dài đúng ô.
5. Jazz 3/4 với swing, và jazz 12/8 với swing tắt, walking bass có móc dẫn, Rhodes đen chấm.
6. Tối giản 5/4 và 7/8. Ostinato dài bằng ô. Sub-bass và pulse theo nhóm phách. Rút coda đúng số móc ở bảng.
7. Ambient 3/4 và 6/4. Hơi thở làm tròn từ hằng số móc đơn. Trần trụ đếm theo móc.
8. Khung `warmup` và `cooldown` cho 1M và 3M, violin vào nửa sau. 1Y dùng nửa khung, và một ô mỗi đầu với 12/8 cùng 6/4. Nến để trống trên ô khung.

## Kiểm tra

- Score 1D đủ bốn dạng giữ 4/4 và khung 2+2 hiện có. Jazz 1D vẫn có thẻ swing 2:1.
- Một tuần đủ 5 phiên vẫn 160 ô 4/4. `plan_span` của 1W nhận variant mà spec không đổi.
- Chương III giao hưởng của 1M là 96 ô, `<beats>3</beats>`. Bass mức `mp` là trắng rồi đen. Phách mạnh của loss nằm ở móc 0 với trọng số 2,5 và móc 4 với trọng số 0,8.
- Chương II giao hưởng của 1M là 96 ô 6/8, 576 móc, 4:00 ở 72 BPM. Một nốt phủ phách 2 cắt tại móc 3. Bass mức `mp` là hai đen chấm.
- Jazz 12/8 của chương đó có `swing` tắt. Walking mức `mf` có nốt ở móc 5 và móc 11. Rhodes ở móc 3 và 9 dài 1,5 phách.
- Jazz 3/4 có `swing` bật. Ô chẵn của Rhodes là hợp âm 1,5 phách ở phách 1 rồi một móc ở phách 1,5.
- Chương I tối giản của 1M là 76 ô 5/4. 8 móc bị rút nằm ở coda. `ostinato_offsets` dài 10. Sub-bass là năm nốt đen, tenuto ở phách 1 và phách 4.
- Chương III tối giản là 82 ô 7/8. Sub-bass là ba xung dài 2, 2 và 3 móc. Pulse mức `f` là 14 móc kép.
- Nghỉ trọn một ô 5/4 là một `<rest measure="yes"/>`, duration bằng cả ô, không có `<type>`.
- Ô `warmup` và `cooldown` không có slot Markov, không có cửa sổ thanh khoản, và nhóm nến rỗng.
- Chương II của 1M có cool-down dù spec thân không có outro.
- Cool-down cùng cao độ, chạm vạch, được buộc với nốt cuối của thân. Hairpin kết ở `ppp`.
- Warm-up giao hưởng 4 ô: violin bắt đầu ở ô 2. Hai ô đầu chỉ có bass và cello.
- `SpanRecap` đứng ở nến đầu suốt `warmupSec` và ở nến cuối suốt `cooldownSec`.
- Khóa cache đổi khi tử số, mẫu số hoặc swing đổi. File 4/4 của cùng chương không bị trả lại.
