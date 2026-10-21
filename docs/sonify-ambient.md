# Ambient: bản nghe có kết cấu

Kiểu nghe thứ tư, cạnh Giao hưởng và Jazz. Tối giản giữ nguyên.

Ambient là một `Score` soạn xong cả chương rồi mới xuất tiếng, cùng đường với `render_jazz_score`. Form, hợp âm Markov, câu nhạc và nốt đã lượng tử hóa có trước. Phần Ambient chỉ viết năm bè lên cái khung đó. Im lặng là mặc định, và im lặng nằm trong câu.

## Vì sao không lấy cách stream

`arrange()` trong `voices.py` chỉ thấy một bucket 250 ms và nốt vừa kêu. Giao hưởng, Jazz và Ambient trên stream đều nghe vỡ vụn vì vậy: không có câu, không có hợp âm đã chọn cho cả đoạn, mỗi bucket tự quyết định có đánh hay không.

`should_strike_ambient` là cổng của stream. Bản nghe không gọi nó. Một nốt kính được giữ hay bỏ khi đã nhìn hết đoạn.

Stream để nguyên. Tài liệu này chỉ nói bản nghe phiên và bản nghe dài.

## Hai đơn vị câu

`FormSection` là đoạn của form. Ở 1D, ba đoạn `phrase` dài 8 ô, intro dài 2 ô, outro dài 4 ô. Từ 1W trở đi độ dài lấy từ `spec.sections`. Intro của bản dài là 8 ô. Outro có thể là 8, 12, 16 hoặc 40 ô. Chương II của 1M không có outro.

`Phrase` của `plan_phrases()` là câu giai điệu bên trong đoạn đó. Trần là `MAX_EIGHTHS = 32`, tức 4 ô. Một đoạn `phrase` 8 ô luôn bị cắt thành ít nhất hai `Phrase`. Phiên phẳng bị cắt giữa nốt, `held_over=True` ở câu đầu. `_settle_edge` còn cho một câu tràn tối đa `PERIOD` (4 móc đơn, nửa ô) sang section sau.

Mọi quy tắc «một câu 8 ô» trong tài liệu này nói về `FormSection` có `kind == "phrase"`. `plan_phrases()` chỉ cung cấp đường viền: run mở, `apex`, `cadence`, `rise`, bước nhảy. Trước khi tỉa, cắt mỗi `Phrase` vào đúng biên section, bỏ phần tràn.

## Chỗ nó ngồi

`render()` / `_compose()` làm xong phần chung, rồi rẽ biến thể. Ambient rẽ cùng chỗ Jazz và Tối giản đang rẽ, sau khi đã có:

- `plan_slots`: intro, các đoạn phrase, outro, hợp âm từng ô
- thang giá và `raw_pitches`
- `quantize_strong_beats`: giai điệu trên thang, phách mạnh bám âm hợp âm
- `plan_phrases`: đường viền bên trong từng đoạn
- `liquidity_windows_for(spec)` và băng `p`–`f` trên `band_at`

`render_ambient_score` nhận các thứ của `render_jazz_score`, cộng thêm `windows` và `spec.sections`. `band_at` một mình không đủ: hai cửa sổ `f` liền nhau là bốn ô `f`, không còn thấy đâu là ô thứ hai của từng cửa sổ. Bản 1D truyền `DAILY_SPEC` và `LIQUIDITY_WINDOWS`.

`Variant` thêm `"ambient"`. `StreamVariant` đã có chữ này cho stream. Hai kiểu không dùng chung hàm soạn. Khóa cache đã gồm variant, nên file Giao hưởng, Jazz, Tối giản không bị thay.

`audio.py` có hai danh sách variant viết cứng. Regex `_STORED_NAME` và tuple trong `_prune_spans` đều lấy từ `VARIANTS`. Thiếu `_prune_spans` thì file span Ambient vừa render bị `prune()` xóa ở lần gọi sau.

## Form giữ nguyên

1D vẫn là tiểu phẩm 30 ô. Từ 1W trở đi Ambient nhận cùng `FormSpec` với hai kiểu kia: cùng số ô, cùng chỗ intro và coda, cùng BPM của bảng trong `docs/sonify-long-form.md`. Nghỉ giữa chương vẫn do player chèn.

Intro và outro đã đạp chủ âm của đoạn bên cạnh. Ambient không viết tiến trình riêng.

Mỗi chương là một file. Đuôi reverb chỉ ở cuối chương, cùng quy ước `map_duration`.

## Năm bè

| Phần | Vai | Nhạc cụ MuseScore | Program | Khuông |
|---|---|---|---|---|
| P4 | Drone | Contrabass | 43 | Fa, như bass hiện tại |
| P2 | Halo | Viola | 42 | Sol |
| P1 | Kính | Alto Flute | 74 | Sol |
| P3 | Nở | Harp | 47 | Sol, một khuông |
| P5 | Shimmer | Celesta | 9 | Sol |

P1 phải là tiếng ngân được và có nhịp thở. Pad GM, hộp nhạc và chuông đánh một tiếng rồi tắt, nên nốt dài trên giấy vẫn nghe như nốt rời. Drone dùng Contrabasses ở dải `p`–`mp`, halo dùng Violas mở đầu ở `p` với quãng mở (không xếp quãng 2 sát nhau), kính dùng Alto Flute giữ trong tầm ấm `G3–C6` kèm cung thở `p < mp/mf > p` trên mỗi hơi ngân, tiếng nở dùng Harp rải nhẹ 3 nốt hợp âm mở ở các cửa sổ `f`. Shimmer vẫn là Celesta, chỉ điểm ở đỉnh rồi tắt. Sự liền mạch của giai điệu là một tiếng được giữ và có độ phập phồng tự nhiên.

P2 xuất khóa Sol vì guide tone nằm ở A3–E5. P3 của Ambient đi một khuông, mở đầu ở `p`, in `mp` trên ô nở, và không xuất `<harmony>` để MuseScore không gắn kênh Grand Piano tự động đánh hợp âm ở đầu mỗi slot.

`divisions = 2`, `swing = false`. Không có móc kép, không có nhịp đi bộ, không có ostinato. Mọi nốt đi qua `written()`, để nốt cắt ở vạch nhịp được buộc đúng. Một `NoteEvent` dài 4 phách chỉ hợp lệ khi bắt đầu ở phách 1.

Màu hợp âm của giường nhạc lấy `jazz_chord()`. Giai điệu giữ nguyên nốt đã lượng tử hóa trên thang, được gập quãng 8 vào dải ấm `G3–C6` (`active_register().violin_lowest .. violin_ceiling`). Shimmer chọn một âm hợp âm ở vùng cao, gần đỉnh, một nốt.

`C` và `Cmaj7` đều thành `Cmaj9` sau `jazz_chord()`. Các ô liền nhau cùng hợp âm jazz gộp thành một lần tấn công. `Score.slots` lưu các slot đã nâng, cùng cách Jazz, để `musicxml.py` tra đúng chính tả `E9`, `Fm9` và các hợp âm mượn.

## Giường nhạc là sợi chỉ

Drone và halo không nghỉ giữa đoạn. Chúng tấn công khi hợp âm jazz đổi, và buộc tiếp những cao độ còn mặt ở ô sau.

`ChordSlot` của Markov và cửa sổ thanh khoản không trùng nhau. Slot có thể dài 1 đến 8 ô và cắt ngang nhiều cửa sổ. Băng đọc theo từng ô, `band_at[bar]`, không lấy một băng cho cả slot.

- Drone: nốt gốc trên mọi ô (`velocity` 38–54). Quãng 5 lấy từ `fifth_above_bass()` (`velocity` 40) chỉ trên ô `mf` hoặc `f`. Gốc buộc qua những ô cùng hợp âm. Quãng 5 buộc qua các ô `mf`/`f` liền nhau, rồi nhả khi ô sau dịu hơn.
- Halo: hai âm khi ô là `p` hoặc `mp`, ba âm khi ô là `mf` hoặc `f`. Hai âm là guide tone của `comp_pitches` (quãng 3 và quãng 7, hoặc quãng 3 và quãng 5 với hợp âm ba). Ba âm thêm bậc 9 đặt cách guide tone cao nhất ít nhất một quãng 3 thứ (`>= 3` semitone, `<= E5`), để không tạo cụm quãng 2 gây nhiễu trên dàn dây. Cao độ còn lại thì buộc. Cao độ mới thì tấn công. Cao độ rơi mất thì nhả.
- Cường độ in trên P4: `p` và `mp` đều viết `p`, `mf` và `f` đều viết `mp` (`_DRONE_MARKING`). `DynamicEvent` đổi ở đầu mỗi cửa sổ thanh khoản khi chữ in thay đổi.

`score.dynamics` mà `_compose` dựng sẵn đã đi qua `bass_marking()`, trần `BASS_CEILING = "mp"`. Ambient tự dựng chữ từ `windows` và `bands` theo `_DRONE_MARKING`, trần `mp`. `_bass_part` in các chữ này.

Halo mở đầu ở chữ `p` (`PIANO_DYNAMIC`) trên ô 0 và giữ `velocity` 36–52 (`_HALO_VELOCITY`).

`_bass_part` gắn `<chord/>` khi hai nốt cùng phách, để gốc và quãng 5 không thành tám phách trong ô 4/4. Bass một nốt của ba biến thể kia vẫn tuần tự.

Intro: giường vào phách 1 của ô 0 và ngân hết section intro. Outro: giường là pedal chủ âm sẵn có, ngân hết section outro. Đoạn không có outro thì không có pedal outro.

Ngày đi ngang thì hợp âm ít đổi, giường gần như một tiếng. Đó là Ambient của một phiên phẳng, và vẫn là một bài vì intro, các đoạn phrase và outro còn đó.

## Giai điệu kính

Tỉa từng `FormSection` có `kind == "phrase"`, sau khi các `Phrase` bên trong đã bị cắt vào biên section.

Đoạn phẳng: biên độ của `pitches` trong cả section nhỏ hơn `MIN_RISE` (3 semitone). Một lần tấn công ở phách 1 ô đầu của đoạn, cao độ đó (đã gập vào `G3–C6`), dài tối đa 4 ô (`FLAT_HOLD`). Phần còn lại của đoạn là nghỉ trên P1. Giường tiếp tục.

Đoạn có hướng đi lên hoặc đi xuống thì giữ trụ theo thứ tự thời gian:

1. Run mở của đoạn.
2. `apex` của một `Phrase` bên trong, khi `rise >= MIN_RISE` và đỉnh không trùng run mở hay run kết của đoạn.
3. Một run lệch ít nhất một quãng 4 đúng (5 semitone) so với trụ đang giữ gần nhất. Bước đi bậc thang không thêm trụ.
4. Run kết của đoạn. Khác cao độ với trụ cuối thì giữ. Cùng cao độ thì xử lý theo quy tắc buộc ở dưới.

Trần là bốn lần tấn công cho mỗi 8 ô của section. Đoạn 8 ô được bốn trụ. Đoạn 24 ô được mười hai. Trần tính cả run mở và run kết.

Cách đặt nốt:

- Mỗi ô tối đa một trụ, đặt ở phách 1 của ô đó (`_one_per_bar`), qua `written()`. Hai trụ rơi vào cùng một ô thì giữ trụ sớm hơn, để P1 không thành hợp âm.
- Cao độ mỗi trụ được gập quãng 8 (`_fold_glass`) vào vùng `G3–C6` và tránh nhảy quá một quãng 8 so với trụ ngay trước.
- Dài tối đa 3 ô (`GLASS_HOLD`, 24 móc đơn). Khoảng tới trụ sau dài hơn 3 ô thì phần dư là nghỉ trên P1.
- Trụ sau cách không quá 3 ô và khác cao độ: nối bằng liaison (`<slur>`) trong cùng đoạn. Nốt mở đầu một hơi có `<tenuto/>`.
- Cùng cao độ chỉ buộc khi hai miền ngân chạm nhau. `<tie>` không đi qua nốt nghỉ. Trụ ngân tối đa 3 ô, nên chỉ gộp một lần tấn công qua `written()` khi trụ trước, trong trần đó, chạm đúng đầu trụ sau.
- Trụ trùng cao độ nằm giữa đoạn mà không chạm được thì bỏ. Run kết cùng cao độ nhưng không chạm được thì đánh lại, để cuối đoạn vẫn có nốt.

Mỗi chuỗi nốt nối liền nhau (bằng `<tie>` hoặc `<slur>`, kể cả trên đoạn phẳng, intro và outro) tạo thành một cung hơi (`_breath`):

- Mở đầu ở `p`, `<crescendo>` tới giữa hơi, đạt `mp` (khi cung hơi phẳng) hoặc `mf` (khi các nốt trong cung hơi chênh nhau ít nhất `MIN_RISE`), rồi `<diminuendo>` về cuối hơi.
- Khi đỉnh hơi rơi vào giữa một nốt đang giữ (ví dụ phách 3 của một nốt tròn), nốt đó được cắt thành hai nốt buộc nhau (`_split_at`) tại đúng điểm đỉnh, để `_melody_part` đặt chữ `mp`/`mf` và `<wedge>` ngay trên điểm tách thay vì đẩy ra sau nốt tròn.

Intro: một nốt kính suốt section intro, cùng cao độ với nốt mở của đoạn `phrase` đầu. Trùng cao độ và chạm nhau thì buộc sang đoạn đó.

Outro: một nốt, cao độ close cuối đã lượng tử hóa và gập vào `G3–C6`, giữ hết section outro, nhả ở ô cuối. Hai ô cuối của outro không có shimmer. Không có section outro thì không viết nốt outro.

## Nở và shimmer

P3 để trống, trừ các cửa sổ thanh khoản có băng `f` mà ô thứ hai của cửa sổ thuộc section `phrase`. Hai lần nở cách nhau ít nhất 6 ô (`SWELL_GAP_BARS = 6`). Đặt tại ô thứ hai đó một arpeggio 3 nốt hợp âm mở hướng lên trên đàn Harp:

- Nốt đỉnh (`top`) là âm cao nhất của `_halo_midis` tại ô đó (tối thiểu `C4 = 60`), rơi vào phách 3, ngân 2 phách (`duration_beats = 2.0`, `velocity` 60, `tenuto=True`, đóng `<slur>`).
- Nốt đáy (`bottom`) là âm hợp âm trong vùng khoảng một quãng 8 dưới `top` (`max(48, top - 16) .. top - 8`) không tạo quãng 2 với `top`, đặt ở phách 1 (`duration_beats = 1.0`, `velocity` 48, mở `<slur>`).
- Nốt giữa (`middle`) là âm hợp âm (`chord.pitch_classes`) nằm giữa `bottom` và `top` với khoảng cách ít nhất một quãng 3 thứ so với cả hai đầu, đặt ở phách 2 (`duration_beats = 1.0`, `velocity` 54).
- Chữ in trên ô nở là `mp`. Các cửa sổ `p`, `mp`, `mf`, intro và outro không nở.

Shimmer chọn sau khi nhìn hết cửa sổ ngân sách. Cửa sổ là `spec.chunk_bounds()`:

- 1D, `chunks` rỗng: cả 30 ô.
- 1W: từng phiên 32 ô.
- 1M trở đi: từng chunk của chương.

Không tính theo `spec.sections`. Section 8 ô có 64 móc đơn, `round(0.05 × 64) = 3`, nhỏ hơn một nốt tròn (8 móc đơn). `week_spec` còn chia mỗi phiên thành bốn section 8 ô, nên vòng `bell_caps` hiện tại cũng ra 3 móc đơn.

Ngân sách thô của một cửa sổ là `round(0.05 × số móc đơn)`. Nhân với `bell_budget(span_cửa_sổ) / BELL_MAX_EIGHTHS`, bằng 0 khi span đó không quá 0,5%. Làm tròn. Một shimmer tốn 8 móc đơn. Cửa sổ còn dưới 8 thì không có shimmer. 1D đủ biến động được 12 móc đơn, tức một nốt tròn. Một phiên 1W đủ biến động được 13 móc đơn, cũng một nốt tròn.

`span_cửa_sổ` là `_section_rel_span(bars, groups, chunk_start, chunk_end)` của chính chunk đó. `rel_span` mà `render.py` tính cho cả chương không dùng ở đây. Với 1W, đó là biên độ của một phiên, nên ngày phẳng trong tuần có sóng không có shimmer. `render_ambient_score` nhận `bars` và `groups` để tính span này.

Ứng viên là đỉnh có MIDI từ G5 (79) trở lên, và các sự kiện breakout sẵn có, nằm trong đoạn `phrase`. Hết ngân sách thì bỏ ứng viên có `rise` nhỏ hơn. Hai shimmer cách nhau ít nhất 4 ô. Mỗi shimmer là một nốt tròn, `mp`, một âm, bắt đầu bằng `written()` tại phách 1 của ô chứa đỉnh.

## Tempo

| Range | BPM |
|---|---|
| 1D | 60. Ba mươi ô thành 2:00. Hằng `AMBIENT_BPM`. |
| 1W trở đi | BPM của `FormSpec`, chung với Giao hưởng và Jazz. |

Từ 1W, khoảng trống nằm ở nốt nghỉ và nốt giữ.

## Việc không làm

- Không sửa `minimalist.py`, nhãn «Tối giản», hay các test của biến thể đó.
- Không đưa `should_strike_ambient` vào bản nghe.
- Không đổi `voices.py`. Stream vẫn một bucket một lần.
- Không thêm hợp âm mới. Giường dùng `jazz_chord()` trên slot sẵn có.
- Không thêm `pp` vào `MARKINGS`.
- Không đổi `_piano_part` mà Giao hưởng và Jazz đang dùng.
- Không fill arpeggio ở cadence. Sự kết là giường về chủ âm và nốt kính cuối ngân hết outro.

## Khi đưa vào code

1. `backend/app/sonify/ambient.py`: `render_ambient_score(..., windows, sections, bars, groups)`, `AMBIENT_BPM = 60`. Tỉa theo `FormSection`, giường theo từng ô sau `jazz_chord()`, cung thở trên mỗi hơi kính (tách nốt tại đỉnh hơi), nở arpeggio Harp theo cửa sổ `f`, shimmer theo `chunk_bounds` và `bell_budget` của từng chunk.
2. Nhánh `variant == "ambient"` trong `_compose`, sau khi slot, phrase và pitch đã có. Truyền `windows`, `spec.sections`, `bars` và `groups`. 1D dùng `DAILY_SPEC` và `AMBIENT_BPM`. Có `FormSpec` thì BPM là `spec.bpm`. `Score.slots` là slot đã nâng. `Score.dynamics` là chữ giường trần `mp`.
3. `Variant` trong `model.py` và schema recap / span thêm `"ambient"`. `Score.variant` nhận giá trị đó.
4. `_PARTS_BY_VARIANT` thêm năm program ở bảng trên. `_bass_part` gắn `chord` khi hai nốt cùng phách. P2 Ambient dùng khóa Sol và mở đầu ở `p`. P3 Ambient là một khuông, mở đầu ở `p`, có chữ `mp` trên ô nở, và không in `<harmony>`.
5. `_STORED_NAME` và `_prune_spans` dùng `VARIANTS`.
6. Chip «Ambient» trong `SessionRecap` và `SpanRecap`. `RecapVariant` ở client thêm `'ambient'`.

## Kiểm tra

- Phiên 1D phẳng: mỗi `FormSection` `phrase` 8 ô có một lần tấn công kính, dài tối đa 4 ô. Hai `Phrase` 4 ô bên trong không thành hai lần tấn công.
- Đoạn 8 ô có `rise` đủ `MIN_RISE`: có nốt mở, nốt đỉnh, nốt kết, đúng thứ tự, không quá bốn lần tấn công. Hai trụ trong cùng một ô chỉ còn một nốt.
- Mọi chữ dynamic và `<wedge>` của cung thở trên P1 đều đứng trước một `<note>` đang kêu tại đúng phách đó, không bị đẩy ra cuối ô sau một nốt tròn.
- Hai trụ cùng cao độ chỉ thành một tie khi nốt trước chạm nốt sau trong trần 3 ô (`GLASS_HOLD`). Trụ trùng ở giữa đoạn, cách xa hơn, bị bỏ. Run kết cùng cao độ mà không chạm được thì có một lần tấn công mới. Intro 1D dài 2 ô và buộc sang đoạn phrase đầu khi cùng cao độ và chạm nhau. Outro 1D dài 4 ô.
- Chương II của 1M không có nốt kính outro. Intro của 1W dài 8 ô.
- `C` rồi `Cmaj7` sau `jazz_chord()` là một lần tấn công `Cmaj9`. Drone không đánh lại khi hợp âm jazz không đổi. Quãng 5 chỉ có trên ô `mf` và `f`, và trong MusicXML là `<chord>`, không làm ô 4/4 thành 8 phách.
- Cửa sổ `f` mà ô thứ hai thuộc `phrase` (cách lần nở trước ít nhất 6 ô) có một arpeggio Harp 3 âm hợp âm mở (mỗi quãng liền kề từ 3 semitone trở lên), chữ `mp`. Cửa sổ nhỏ hơn, intro và outro không có. P3 một khuông, không có `<harmony>`.
- Shimmer của 1D đủ biến động dài 8 móc đơn và không vượt `round(0.05 × 240)`. Span của cửa sổ không quá 0,5% thì cửa sổ đó không có shimmer. Hai shimmer, khi cửa sổ chứa được hai nốt, cách nhau ít nhất 4 ô.
- Một tuần đủ 5 phiên vẫn 160 ô, BPM của form, ngân sách shimmer tính theo từng chunk 32 ô. Phiên phẳng trong tuần có sóng không có shimmer. Phiên đủ biến động vẫn có.
- Score Tối giản của cùng một chuỗi nến không đổi. File span Ambient còn sau `prune()`.
