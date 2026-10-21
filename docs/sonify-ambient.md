# Ambient: bản nghe có kết cấu

Kiểu nghe thứ tư, cạnh Giao hưởng và Jazz. Tối giản giữ nguyên.

Ambient ở đây là một `Score` được soạn xong cả chương rồi mới xuất tiếng, cùng đường với `render_jazz_score`. Form, hợp âm Markov, câu nhạc và nốt đã lượng tử hóa có trước. Phần Ambient chỉ viết năm bè lên cái khung đó. Im lặng là mặc định, nhưng im lặng nằm trong câu, không phải từng nhịp bị cắt rời.

## Vì sao không lấy cách stream

`arrange()` trong `voices.py` chỉ thấy một bucket 250 ms và nốt vừa kêu. Giao hưởng, Jazz và Ambient trên stream đều nghe vỡ vụn vì vậy: không có câu, không có hợp âm đã chọn cho cả đoạn, mỗi bucket tự quyết định có đánh hay không.

`should_strike_ambient` là cổng của stream. Bản nghe không gọi nó. Một nốt kính được giữ hay bỏ khi đã nhìn hết câu.

Stream để nguyên. Tài liệu này chỉ nói bản nghe phiên và bản nghe dài.

## Chỗ nó ngồi

`render()` / `_compose()` làm xong phần chung, rồi rẽ biến thể. Ambient rẽ cùng chỗ Jazz và Tối giản đang rẽ, sau khi đã có:

- `plan_slots`: intro, các phrase, outro, hợp âm từng ô
- thang giá và `raw_pitches`
- `quantize_strong_beats`: giai điệu trên thang, phách mạnh bám âm hợp âm
- `plan_phrases`: câu, đỉnh (`apex`), nốt kết (`cadence`), `rise`, `held_over`
- cửa sổ thanh khoản và băng `p`–`f`

`ambient.py` nhận đúng các thứ `render_jazz_score` đang nhận, rồi trả một `Score` với `variant="ambient"`.

`Variant` thêm `"ambient"`. `StreamVariant` đã có chữ này cho stream; hai kiểu không dùng chung hàm soạn. Khóa cache đã gồm variant, nên file Giao hưởng, Jazz, Tối giản không bị thay. Regex tên file trong `audio.py` thêm `ambient`.

## Form giữ nguyên

1D vẫn là tiểu phẩm 30 ô: 2 ô intro, ba phrase 8 ô, 4 ô outro. Từ 1W trở đi Ambient nhận cùng `FormSpec` với hai kiểu kia: cùng số ô, cùng chỗ intro và coda, cùng BPM của bảng trong `docs/sonify-long-form.md`. Nghỉ giữa chương vẫn do player chèn.

Intro và outro đã đạp chủ âm của phrase bên cạnh. Ambient không viết tiến trình riêng.

Mỗi chương là một file. Đuôi reverb chỉ ở cuối chương, cùng quy ước `map_duration`.

## Năm bè

| Phần | Vai | Nhạc cụ MuseScore | Program |
|---|---|---|---|
| P4 | Drone | Pad 1 (new age) | 89 |
| P2 | Halo | Pad 2 (warm) | 90 |
| P1 | Kính | Pad 3 (polysynth) | 91 |
| P3 | Nở | Pad 8 (sweep) | 96 |
| P5 | Shimmer | Celesta | 9 |

P1 phải là tiếng ngân được. Hộp nhạc và chuông tắt ngay, nốt dài trên giấy sẽ vẫn nghe như nốt rời. Sự liền mạch của giai điệu là một tiếng được giữ, không phải một tiếng được gõ lại.

`divisions = 2`, `swing = false`. Không có móc kép, không có nhịp đi bộ, không có ostinato.

Màu hợp âm của giường nhạc lấy `jazz_chord()`: maj9, m9, dominant 9. Giai điệu giữ nguyên nốt đã lượng tử hóa trên thang. Shimmer chọn một âm hợp âm ở vùng cao, gần đỉnh câu, một nốt.

## Giường nhạc là sợi chỉ

Drone và halo không nghỉ giữa câu. Chúng tấn công khi hợp âm đổi, buộc (`tie`) suốt `ChordSlot`, và tấn công lại khi slot sau khác hợp âm. Hai ô cùng hợp âm là một nốt dài, không đánh lại ở phách 1.

- Drone: nốt gốc. Thêm quãng 5 lấy từ `chord.pitches[2]` chỉ khi băng của slot là `mf` hoặc `f`. Cả hai nốt kéo hết slot.
- Halo: hai âm hợp âm khi băng là `p` hoặc `mp`, ba âm khi `mf` hoặc `f`. Nốt tròn, nhỏ hơn drone một bậc.
- Cường độ giường: `p` và `mp` giữ nguyên, `mf` và `f` đều viết `mf`. Chữ `f` dành cho tiếng nở. Đổi marking ở đầu cửa sổ thanh khoản, cùng chỗ dynamic hiện tại.

Intro: giường vào phách 1 của ô 0. Outro: giường là pedal chủ âm sẵn có, ngân hết 4 ô rồi nhả.

Ngày đi ngang thì hợp âm ít đổi, giường gần như một tiếng. Đó là Ambient của một phiên phẳng, và vẫn là một bài vì intro, câu và outro còn đó.

## Giai điệu kính: ít nốt, nhưng là một câu

Tỉa từng phrase sau khi `plan_phrases` đã chạy. Một phrase 8 ô có tối đa bốn lần tấn công.

Giữ lại, theo thứ tự thời gian:

1. Run mở của câu.
2. `apex`, khi `rise >= MIN_RISE` (3 semitone) và đỉnh không trùng run mở hay run kết.
3. Một run lệch ít nhất một quãng 4 đúng (5 semitone) so với trụ đang giữ gần nhất. Bước đi bậc thang không thêm trụ. Trần bốn trụ tính cả run mở và run kết.
4. Run kết, nếu khác cao độ với trụ cuối. Cùng cao độ thì buộc dài, không đánh lại.

Phrase phẳng (`rise < MIN_RISE`): một nốt, cao độ run mở, dài khoảng nửa câu, phần còn lại là nghỉ trên P1. Giường tiếp tục.

Cách đặt nốt:

- Bắt đầu tại ô chứa run đó.
- Dài tối đa 2 ô. Khoảng tới trụ sau dài hơn 2 ô thì phần dư là nghỉ trên P1.
- Trụ sau cách không quá 2 ô và khác cao độ: nối bằng liaison trong cùng một câu, không chọc một lỗ ngắn giữa hai trụ gần nhau.
- Cùng cao độ: `tie`, một lần tấn công.
- `held_over` và nốt kết trùng cao độ nốt mở của phrase sau trong cùng section: buộc qua ranh giới câu, cùng quy ước giai điệu giao hưởng.

Hairpin dùng `hairpins()` của câu: crescendo tới đỉnh, diminuendo về nốt kết, vẽ trên P1. Phrase phẳng không có hairpin.

Intro không phải phrase 8 ô. Một nốt kính suốt 2 ô, cùng cao độ với nốt mở của phrase 1, buộc sang phrase đó.

Outro: một nốt, cao độ close cuối đã lượng tử hóa, giữ hết 4 ô, nhả ở ô cuối. Hai ô cuối không có shimmer.

Register lấy đúng nốt giai điệu đã có. Không dò octave từng nốt. Đường viền giá vì thế không bị gãy khi một nốt bị bỏ.

## Nở và shimmer là sự kiện của cả bài

P3 để trống, trừ một lần nở trong một cửa sổ thanh khoản băng `f`. Đặt ở phách 1 của ô thứ hai trong cửa sổ, dài 2 phách, voicing jazz ở giữa register, rồi nghỉ đến cửa sổ sau. Cửa sổ `p`, `mp`, `mf` không nở. Outro không nở.

Shimmer nhìn cả chương rồi mới chọn, cùng kiểu ngân sách chuông:

- Ứng viên là đỉnh câu có MIDI từ G5 (79) trở lên, và các sự kiện breakout sẵn có.
- Ngân sách mỗi section là `round(0.05 * số móc đơn của section)`. 1W tính theo từng phiên 32 ô, không phải 5% của cả tuần.
- Các nốt cách nhau ít nhất 4 ô. Hết ngân sách thì bỏ ứng viên yếu hơn (`rise` nhỏ hơn).
- Mỗi shimmer là một nốt tròn, `mp`, một âm. Section không có đỉnh cao thì không có shimmer.

## Tempo

| Range | BPM |
|---|---|
| 1D | 60. Ba mươi ô thành 2:00. Hằng `AMBIENT_BPM`. |
| 1W trở đi | BPM của `FormSpec`, chung với Giao hưởng và Jazz. |

Từ 1W, khoảng trống nằm ở nốt nghỉ và nốt giữ. Không chạy chậm hơn bảng form.

## Việc không làm

- Không sửa `minimalist.py`, nhãn «Tối giản», hay các test của biến thể đó.
- Không đưa `should_strike_ambient` vào bản nghe.
- Không đổi `voices.py`. Stream vẫn một bucket một lần.
- Không thêm hợp âm mới. Giường dùng `jazz_chord()` trên slot sẵn có.
- Không fill arpeggio ở cadence. Sự kết là giường về chủ âm và nốt kính cuối ngân hết outro.

## Khi đưa vào code

1. `backend/app/sonify/ambient.py`: `render_ambient_score`, `AMBIENT_BPM = 60`. Tỉa trụ, giường theo slot, nở theo cửa sổ `f`, shimmer theo ngân sách 5%.
2. Nhánh `variant == "ambient"` trong `_compose`, sau khi slot, phrase và pitch đã có. 1D truyền `AMBIENT_BPM`. Có `FormSpec` thì dùng `spec.bpm`.
3. `Variant` trong `model.py` và schema recap / span thêm `"ambient"`. `Score.variant` nhận giá trị đó.
4. `_PARTS_BY_VARIANT` trong `musicxml.py` thêm năm program ở bảng trên.
5. Regex file trong `audio.py` nhận `ambient`.
6. Chip «Ambient» trong `SessionRecap` và `SpanRecap`. `RecapVariant` ở client thêm `'ambient'`.

## Kiểm tra

- Phiên phẳng: mỗi phrase 8 ô có một lần tấn công kính; drone có mặt suốt bài và không đánh lại khi hợp âm không đổi.
- Phrase đi lên đủ `MIN_RISE`: có nốt mở, nốt đỉnh, nốt kết, đúng thứ tự thời gian, không quá bốn lần tấn công.
- Hai trụ cùng cao độ là một tie, không phải hai nốt.
- `held_over` buộc nốt cuối sang phrase sau khi cao độ không đổi.
- Cửa sổ `f` có đúng một tiếng nở. Cửa sổ nhỏ hơn và outro không có.
- Tổng độ dài shimmer trong một section không quá 5% số móc đơn, và hai shimmer cách nhau ít nhất 4 ô.
- Intro dài 2 ô, outro dài 4 ô, giường outro là hợp âm chủ của phrase cuối.
- Một tuần đủ 5 phiên vẫn 160 ô và dùng BPM của form, không dùng 60.
- Score Tối giản của cùng một chuỗi nến không đổi.
