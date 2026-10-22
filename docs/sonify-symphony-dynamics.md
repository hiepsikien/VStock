# Dynamic cho Flute và Piano của Giao hưởng

Kế hoạch cho hai bè đang đứng một mức suốt bài. Flute in một chữ `mp` ở ô 1, velocity cố định `FLUTE_VELOCITY = 64`, không hairpin. Piano in một chữ `p` ở ô 1; hợp âm đệm không gắn velocity, fill cuối câu đứng ở `FILL_VELOCITY = 64`. Violin, Cello và Bass đã có đường dynamic. Tài liệu này đưa Flute và Piano vào cùng khuôn đó, và để mỗi bè đọc một tầng chuyển động của phiên.

Chỉ Giao hưởng. Jazz, Tối giản và Ambient giữ cách viết hiện tại. Piccolo, Harp và sáu kèn cor đi cùng đường dynamic của vai P5 và P3. Glockenspiel (`ensemble == "brass"`) giữ velocity và chữ, nhưng chỉ có hairpin khi đoạn có từ hai tiếng gõ.

Ba tầng chuyển động, mỗi tầng một chỗ:

| Tầng | Flute | Piano |
|---|---|---|
| Giá trong câu (`phrase.rise`, đỉnh, `BREAKOUT`) | Vòng cung của đoạn sáo | Hướng vuốt của fill |
| Thanh khoản `p`–`f` | Trần velocity của đỉnh | Chữ in và velocity giường |
| `BarGroove` (`rally`, `selloff`, `calm`, `volatile`) | Breakout vẫn chạm trần `mf` | `chamber`, `trio_thin`, `half`, `rally`, `caesura` |

## Flute thở theo đoạn nó hát

Flute vào khi câu lên cao, khi có breakout, hoặc khi nốt vượt trần violin. `_flute_and_violin_dovetail` ghi `yield_spans`. `melody_parts` chỉ dựng hairpin trên đoạn violin còn giữ, nên cao trào bị mất đúng lúc sáo hát. Flute nhận vòng cung của đoạn `[span_start, sounding_end)`.

### Đỉnh là đỉnh giá, trước khi gập

`flute_harmony_pitch` cộng thêm quãng 3, 4 hoặc 7, rồi gập xuống khi vượt `flute_ceiling` (Mi6 = 88). Giá `Rê6 → Mi6 → Fa6` có thể thành sáo `Sol6` rồi `La5` ở đúng nốt đỉnh. Đỉnh crescendo vì vậy không lấy cao độ đã gập.

`span_apex` là móc đơn sớm nhất trong `[span_start, sounding_end)` mà `pitches[eighth]` (đường giá gốc, cùng nguồn với `soar_runs`) đạt cực đại. `hairpins(span_start, sounding_end, span_apex)` trỏ vào móc đó. Mỗi cạnh vẫn cần ít nhất `WEDGE_MIN` (2 móc đơn).

### Vòng cung của đoạn, không của cả câu

`swell(phrase, onset)` trả 0 ở `phrase.start`, 1 ở `phrase.apex.start`, 0 ở `phrase.end`. Đoạn sáo thường chỉ là một phần câu, và `span_apex` có thể khác `phrase.apex.start`. Gọi `swell(phrase, …)` làm velocity đi ngược hairpin đang in.

Velocity dùng vòng cung nội bộ. `span_swell(onset)` bằng 0 ở hai đầu đoạn và 1 ở `span_apex`, tuyến tính từng phía, cùng hình với `swell()` nhưng trên `(span_start, sounding_end, span_apex)`. `lift(phrase)` vẫn là hệ số của cả câu: `phrase.rise < MIN_RISE` thì `lift` bằng 0 và cả đoạn đứng ở 64, không hairpin.

```
velocity = round(64 + (peak - 64) * lift(phrase) * span_swell(onset))
```

Nốt nhấn trong đoạn được đẩy lên, rồi kẹp lại không vượt `peak`.

`peak` đọc thanh khoản tại ô của `span_apex` (`band_at`) và màu của đoạn:

| Đoạn | `peak` |
|---|---|
| Band `p` hoặc `mp`, không có `BREAKOUT` | 72 |
| Band `mf` hoặc `f`, hoặc đoạn có `BREAKOUT` | 80 |

72 nằm trong khoảng hơi nhẹ 70–74: câu lên hết một quãng tám (`lift == 1`) chạm 72, câu lên ít hơn thì thấp hơn. 80 là `mf`. Không có bậc `f` (96). Sàn mọi đoạn là `mp` (64).

### Chữ in theo `drift`, không có `mf` trên khuông

Violin và Cello không in `mf` ở đỉnh hairpin. Chúng in `mp`, vẽ `<wedge>`, ghi velocity trên từng nốt, và đếm `drift` (`crescendo` +1, `diminuendo` −1). Cặp hairpin đủ hai chiều đưa `drift` về 0. Hairpin chỉ một chiều để `drift != 0`, và `melody_parts` in lại `mp` ở tiếng đánh mới đầu tiên, không trên nốt nối dây.

Flute dùng đúng luật đó.

- Không in `mf` ở `span_apex`. Đỉnh nghe bằng hairpin và thuộc tính `dynamics` trên nốt.
- `_melody_part` đã in `mp` ở ô 1, kể cả khi sáo nghỉ ô đó. Tiếng vào đầu tiên của sáo không thêm một chữ `mp` nữa. `test_repeated_dynamics_are_printed_once` cấm hai chữ giống nhau khi không có gì đổi ở giữa.
- `mp` chỉ in lại khi `drift != 0`, tại tiếng đánh mới. Cặp crescendo rồi diminuendo không in lại, vì playback đã về chỗ cũ.

### Glockenspiel

Hơi và piccolo crescendo được trên một nốt ngân. Glockenspiel tắt sau cú gõ. Khi `score.ensemble == "brass"`, đoạn có `len(merged_flute_runs) < 2` không sinh `<wedge>`. Velocity của tiếng gõ đó lấy `peak` của đoạn, vì không có hairpin để tiếng lớn dần. Đoạn từ hai tiếng gõ trở lên vẫn có hairpin, chữ `drift` và `span_swell` như sáo. `classic` và `wood` vẫn hairpin trên một nốt dài khi đoạn đủ `WEDGE_MIN`.

Warm-up và cool-down vẫn để sáo nghỉ. `apply_span_frame` cắt `score.high` về thân. Hairpin và chữ của sáo chỉ nằm trong thân. Không thêm `p` đầu khung hay `ppp` cuối khung.

## Piano đọc thanh khoản, rồi groove

Hợp âm đệm không đi theo hairpin giai điệu. P3 mang `<harmony>`. MuseScore phát ký hiệu hợp âm theo `<sound dynamics>` của chữ in trên P3. Chữ in vì vậy chỉ là `p` và `mp`. Bốn bậc thanh khoản nằm ở velocity của nốt, tách khỏi `<sound>` của hợp âm.

### Chữ in và velocity giường

Band thô lấy từ `band_at[bar]`, cùng cửa sổ với bass. Trước khi ra chữ, hạ band theo đúng ba nhánh của `_bass_pattern`:

- `groove.chamber`: band thành `p`. Giữa phiên tuần `calm`, tay phải đã nghỉ (`_right_hand` bỏ ô này).
- `groove.trio_thin`: hạ một bậc, `f→mf`, `mf→mp`, `mp→p`, `p` giữ `p`.
- `groove.half` khi band còn `mp`: hạ thành `p`. `mf` và `f` giữ nguyên.

`piano_marking()` chạy trên band đã hạ, và không gọi `bass_marking()` (`bass_marking("mp")` vẫn là `mp`):

| Band sau groove | Chữ in | `<sound>` | Velocity nốt |
|---|---|---|---|
| `p` | `p` | 54 | 46 |
| `mp` | `p` | 54 | 54 |
| `mf` | `mp` | 71 | 62 |
| `f` | `mp` | 71 | 68 |

Guide tone và tay trái nhận velocity của hàng đó. `<sound dynamics>` đi theo chữ in, nên hợp âm MuseScore không vượt `mp`. Hai band cùng một chữ in vẫn khác nhau khi nghe nốt piano.

Chữ giường đổi theo từng ô, không theo cả cửa sổ: `chamber` và `half` có thể cắt ngang một cửa sổ. Chỉ in khi chữ khác chữ đang hiệu lực trên P3. Chỉ gắn vào một phách có nốt kêu. Ô nghỉ cả hai tay không có chữ.

`left_hand` đánh lại gốc mỗi hai ô. Hai ngoại lệ, gốc đánh mỗi ô: band sau groove là `f`, hoặc `groove.rally`. Outro vẫn một lần ở ô đầu pedal. Velocity của những nốt gốc là velocity giường của ô đó.

### Fill: chữ giữa ô, velocity theo hướng câu

Fill nói hơn chữ giường một bậc, trần `mf`:

| Chữ giường | Chữ fill | Mốc velocity |
|---|---|---|
| `p` | `mp` | 64 |
| `mp` | `mf` | 80 |

Fill bắt đầu sau phách 1 (`FILL_DELAY`, thường `beat > 0`). Chữ fill là một `DynamicEvent` có `beat` bằng phách nốt fill đầu tiên còn sống, không phải phách 1 của ô.

`_right_hand` đã bỏ fill ở nửa sau ô `caesura`. Chữ và velocity chỉ gắn vào nốt fill còn lại sau bước đó. Fill bị cắt sạch thì không có chữ.

Các nốt trong một fill không cùng một velocity. Vuốt tuyến tính từ nốt đầu đến nốt cuối. Một nốt đứng ở mốc.

| Hướng | `mp` | `mf` |
|---|---|---|
| Nở | 58 → 66 | 74 → 80 |
| Lắng | 64 → 56 | 80 → 72 |
| Ngang | 64 | 80 |

Hướng của fill, theo thứ tự: `groove.selloff` thì lắng; không thì `groove.rally` thì nở; không thì nốt cuối câu cao hơn nốt mở thì nở, thấp hơn thì lắng, bằng thì ngang. Không thêm `<wedge>` trên fill.

Chữ giường được in lại ở phách 1 của hợp âm đệm kế tiếp, khi phách đó có nốt và chữ giường khác chữ fill vừa in. Playback vì vậy không kẹt ở `mf`.

### Khung

Khung tĩnh: `_rest_comp` để piano nghỉ ở warm-up và cool-down. Những ô đó không có chữ mới.

Khung động: `_curtain_comp` đánh ở warm-up và `tag_bars` đầu cool-down. Những nốt này, hiện `velocity=None` trong `_rhodes_warmup_bar`, nhận velocity 49 (mức `p` của `DYNAMICS`). Chữ in ở các ô đó là `p`. Phần cool-down còn lại piano nghỉ. `ppp` cuối khung vẫn thuộc bass và dây.

## Chỗ để trên Score

`Score` thêm ba tuple, mặc định rỗng để Jazz, Tối giản, Ambient và mọi `Score(...)` cũ không đổi:

- `high_wedges`
- `high_dynamics` (chỉ chữ `mp` do `drift` in lại)
- `comp_dynamics` (chữ giường và chữ fill, có `beat`)

Không thêm `comp_wedges`. Piano không có hairpin.

`slice_score` dịch ô của ba tuple này cùng `lead_wedges`, `support_dynamics` và `dynamics`.

## Xuất MusicXML

`score_to_musicxml` đưa `high_wedges` và `high_dynamics` vào P5 khi variant là `symphony`. Chữ mở đầu của `_melody_part` vẫn là `mp` ở ô 1. `high_dynamics` không chứa thêm một `mp` ở tiếng vào đầu nếu `drift` vẫn bằng 0.

`_piano_part` khi variant là `symphony` xả chữ theo phách trên khuông 1, cùng kiểu `flush(event.beat)` của `_melody_part`:

- `beat == 0`: in chữ giường trước `<harmony>` và guide tone, khi chữ đó khác chữ đang hiệu lực. Đây cũng là chỗ hạ từ `mf` hoặc `mp` của fill ô trước về chữ giường.
- `beat == fill_start`: in chữ fill ngay trước nốt fill đầu tiên trên khuông 1.
- Khuông 2 không in lại chữ.

Nhánh `variant == "jazz"` và `low_wedges` giữ nguyên. Tối giản vẫn một chữ `p`. Ambient vẫn `_ambient_swell_part`.

## Khung ngày và khung chương

`apply_daily_frame` và `apply_span_frame` cắt `high_wedges` cùng `high_dynamics` bằng `_body_wedges` và lọc chữ vào `[body, cool)`. Không gọi `_letters` cho sáo, vì hàm đó thêm `p` lúc vào và `ppp` lúc nghỉ.

`comp_dynamics` bị cắt khỏi ô piano nghỉ. Khung động giữ chữ `p` trên warm-up và trên `tag_bars`, và gán velocity 49 cho nốt `_curtain_comp`. Thân giữ chữ thanh khoản đã qua groove. Không gắn `ppp` vào piano.

## Việc không làm

- Không đổi hairpin hay chữ của Violin, Cello, Bass.
- Không đổi Vibraphone, Rhodes, Synth Pulse, French Horn.
- Không in `mf` trên Flute. Không đưa Flute lên `f`.
- Không cho piano hairpin theo câu giai điệu, và không đưa chữ in của piano qua `mp` trừ chữ fill.
- Không thêm `pp` vào `MARKINGS`.

## Khi đưa vào code

1. `model.py`: ba field mới trên `Score`.
2. `dynamics.py`: `piano_marking()` trên band đã hạ. Hạ band bằng cùng ba nhánh với `_bass_pattern`. Bảng velocity 46 / 54 / 62 / 68 đứng cạnh hàm đó.
3. `_flute_and_violin_dovetail` trả thêm wedges và chữ `drift`. `span_apex` lấy từ `pitches`. Velocity đi theo `span_swell` và `lift`, với `peak` 72 hoặc 80. `ensemble == "brass"` bỏ wedge khi đoạn chỉ có một run, và tiếng gõ đó dùng `peak`.
4. Nhánh symphony trong `render`: `comp_dynamics` theo từng ô và theo `beat` của fill; guide tone và tay trái nhận velocity giường; `left_hand` đánh mỗi ô khi band sau groove là `f` hoặc `groove.rally`; fill còn sống sau `caesura` nhận chữ và đường vuốt.
5. `musicxml.py`: P5 nhận hai tuple của flute. P3 symphony xả `comp_dynamics` theo phách trên khuông 1.
6. `span.slice_score`, `movement_frame.apply_span_frame`, `daily_frame.apply_daily_frame`: cắt và dịch ba tuple. `_curtain_comp` của symphony gán velocity 49.

## Kiểm tra

- Đỉnh hairpin flute trùng móc giá cao nhất trong đoạn, kể cả khi `flute_harmony_pitch` đã gập nốt đó xuống một quãng tám. Velocity cùng chiều với hairpin, không đi theo `swell(phrase, …)`.
- `phrase.rise < MIN_RISE`: flute đứng ở 64, không hairpin. Band `p`/`mp` và không breakout: velocity đỉnh không quá 72. Band `mf`/`f` hoặc có `BREAKOUT`: velocity đỉnh chạm 80 và không vượt 80.
- P5 chỉ in `mp`. Ô 1 có một chữ `mp`. Tiếng sáo đầu tiên sau đó không thêm `mp` khi `drift` bằng 0. `mp` in lại chỉ khi hairpin còn dang dở.
- `ensemble == "brass"` và đoạn một run: không có `<wedge>`, velocity nốt bằng `peak`. Đoạn hai run vẫn có hairpin. `classic` và `wood` vẫn hairpin trên một nốt dài.
- Chữ piano trên giường chỉ `p` và `mp`. Cùng chữ `p`, band `p` có velocity 46 và band `mp` có velocity 54. Cùng chữ `mp`, band `mf` là 62 và band `f` là 68.
- Ô `chamber` không in `mp`. Ô `trio_thin` và ô `half` dùng band đã hạ. Ô `f` hoặc `rally` có gốc tay trái mỗi ô.
- Chữ fill đứng ở `beat` của nốt fill, không ở phách 1. Phách 1 của hợp âm đệm sau đó in lại chữ giường khi chữ đổi. Fill bị `caesura` bỏ thì không còn chữ. Fill nở và fill lắng khớp hai hàng velocity ở bảng fill.
- Nốt `_curtain_comp` của symphony có velocity 49. Warm-up và cool-down tĩnh không có chữ piano. Sáo không có `p` đầu khung và không có `ppp`.
- Jazz, Tối giản, Ambient giữ nguyên số chữ và số hairpin trên cả năm bè.
- Assertion đang khóa piano Giao hưởng đúng một thẻ `<dynamics>p</dynamics>` được viết lại theo bảng band và groove ở trên.
