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
| P2 | Halo | Bass Flute | 74 | Sol |
| P1 | Kính | Alto Flute | 74 | Sol |
| P3 | Nở | Horn in F | 61 | Sol, một khuông |
| P5 | Shimmer | Celesta | 9 | Sol |

P1 phải là tiếng ngân được và lắng chậm. Pad GM, hộp nhạc và chuông đánh một tiếng rồi tắt, nên nốt dài trên giấy vẫn nghe như nốt rời. Drone dùng Contrabasses ở dải `p`–`mp` (`+4 dB` trên fader mixer để làm nền rù rì dày ấm), Halo (`P2`) dùng Bass Flute ở dải trầm `D3–C#4` (`-5 dB`, mở đầu ở `p`) tạo lớp hơi ấm rù rì không có tiếng cọ vĩ rít của đàn dây, kính dùng Alto Flute giữ trong tầm ấm `G3–C6` kèm một đường `<diminuendo>` lắng chậm suốt cả hơi ngân, tiếng nở dùng French Horn (`Horn in F`) vuốt sóng `p < mp >` hoặc `p < mf >` qua hai nửa buộc nhau (dài 1–2 ô nhịp) trên các cửa sổ `mf`/`f`. Shimmer vẫn là Celesta (`f`, `+6 dB`, vùng chuông vang `D5–C6`), điểm ở đỉnh rồi tắt. Sự liền mạch của giai điệu là một tiếng được giữ và tan dần.

P2 xuất khóa Sol vì hai âm guide tone của Bass Flute nằm ở `D3–C#4` (`50..61`, cách nhau một quãng 4 hoặc quãng 5). P3 của Ambient đi một khuông, mở đầu ở `p`, dâng crescendo ở nửa đầu và diminuendo ở nửa sau của mỗi tiếng nở, và không xuất `<harmony>` để MuseScore không gắn kênh Grand Piano tự động đánh hợp âm ở đầu mỗi slot.

`divisions = 2`, `swing = false`. Không có móc kép, không có nhịp đi bộ, không có ostinato. Mọi nốt đi qua `written()`, để nốt cắt ở vạch nhịp được buộc đúng. Một `NoteEvent` dài 4 phách chỉ hợp lệ khi bắt đầu ở phách 1.

Màu hợp âm của giường nhạc lấy `jazz_chord()`. Giai điệu giữ nguyên nốt đã lượng tử hóa trên thang, được gập quãng 8 vào dải ấm `G3–C6` (`active_register().violin_lowest .. violin_ceiling`). Shimmer chọn một âm hợp âm ở vùng cao, gần đỉnh, một nốt.

`C` và `Cmaj7` đều thành `Cmaj9` sau `jazz_chord()`. Các ô liền nhau cùng hợp âm jazz gộp thành một lần tấn công. `Score.slots` lưu các slot đã nâng, cùng cách Jazz, để `musicxml.py` tra đúng chính tả `E9`, `Fm9` và các hợp âm mượn.

## Giường nhạc là sợi chỉ

Drone và halo không nghỉ giữa đoạn. Chúng tấn công khi hợp âm jazz đổi, và buộc tiếp những cao độ còn mặt ở ô sau.

`ChordSlot` của Markov và cửa sổ thanh khoản không trùng nhau. Slot có thể dài 1 đến 8 ô và cắt ngang nhiều cửa sổ. Băng đọc theo từng ô, `band_at[bar]`, không lấy một băng cho cả slot.

- Drone: nốt gốc trên mọi ô (`velocity` 52–68). Quãng 5 lấy từ `fifth_above_bass()` (`velocity` 48) chỉ trên ô `mf` hoặc `f`. Gốc buộc qua những ô cùng hợp âm. Quãng 5 buộc qua các ô `mf`/`f` liền nhau, rồi nhả khi ô sau dịu hơn.
- Halo: hai âm guide tone của `comp_pitches` được dịch xuống quãng trầm `D3–C#4` (`50..61`) trên `Bass Flute` (`velocity` 40–54), tạo lớp hơi rù rì ấm áp không có tiếng nhựa thông cọ dây. Cao độ còn lại thì buộc. Cao độ mới thì tấn công. Cao độ rơi mất thì nhả.
- Cường độ in trên P4: `p` giữ `p`, còn `mp`, `mf` và `f` đều viết `mp` (`_DRONE_MARKING`). `DynamicEvent` đổi ở đầu mỗi cửa sổ thanh khoản khi chữ in thay đổi.

`score.dynamics` mà `_compose` dựng sẵn đã đi qua `bass_marking()`, trần `BASS_CEILING = "mp"`. Ambient tự dựng chữ từ `windows` và `bands` theo `_DRONE_MARKING`, trần `mp`. `_bass_part` in các chữ này.

`_bass_part` gắn `<chord/>` khi hai nốt cùng phách, để gốc và quãng 5 không thành tám phách trong ô 4/4. Bass một nốt của ba biến thể kia vẫn tuần tự.

Intro: giường vào phách 1 của ô 0 và ngân hết section intro. Outro: giường là pedal chủ âm sẵn có, ngân hết section outro. Đoạn không có outro thì không có pedal outro.

Ngày đi ngang thì hợp âm ít đổi, giường gần như một tiếng. Đó là Ambient của một phiên phẳng, và vẫn là một bài vì intro, các đoạn phrase và outro còn đó.

## Giai điệu kính: Hơi thở uốn lượn (Inflected Breaths)

### Vấn đề của trụ phẳng (Flat Pillars) và hướng giải quyết

Cách tỉa trụ cũ giữ tối đa 2 nốt đơn cho mỗi 8 ô (`PILLARS_PER_EIGHT = 2`, `PILLAR_GAP = 24` móc đơn), chỉ bắt bước nhảy từ quãng 4 đúng trở lên (`LEAP = 5` semitone), gộp mọi section có biên độ dưới `MIN_RISE` (3 semitone) thành một nốt phẳng duy nhất, xóa toàn bộ trụ rơi vào 3 ô cuối section (`end - run.start >= _gap`), và xóa mọi nốt trùng cao độ sau khoảng nghỉ bất chấp giá ở giữa đã dao động. Hệ quả là ở `60 BPM` (1 ô 4/4 = 4 giây), sáo giữ một nốt ngang suốt 16 giây rồi nghỉ 8–16 giây, làm mất dấu các nhịp bò dần theo bậc thang (1–2 bậc âm giai), các nhịp nhúng xuống (trough / dip) và giá đóng cửa ở cuối đoạn.

Để giữ đúng bản chất Ambient (ít lần lấy hơi, không chạy nốt vụn, luôn có khoảng lặng để nghe nền Drone + Halo) nhưng phản ánh sát **Price Action**, bè kính chuyển từ **«Trụ phẳng 1 nốt»** sang **«Hơi thở uốn lượn» (Inflected Breaths)**:

```text
Trụ phẳng cũ (Flat Pillar + Long Silence):
Ô nhịp: | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
Giá:      C5 ──> D5 ──> E5 ──> D5 ──> C5
Sáo P1: [====== C5 (4 ô) ======] [ Nghỉ 4 ô ... ]  (Bỏ sót nhịp tăng lên E5 rồi lùi về C5)

Hơi thở uốn lượn (Inflected Breath + Short Breath Gap):
Ô nhịp: | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
Giá:      C5 ──> D5 ──> E5 ──> D5 ──> C5
Sáo P1: [=== C5 === (slur) == E5 ==] [Nghỉ] [== D5 == (slur) == C5 ==]
         mp ───────────────────────>         mp ────────────────────>
```

### Quy tắc tỉa và đặt hơi thở trên từng `FormSection` (`kind == "phrase"`)

Tỉa từng `FormSection` có `kind == "phrase"`, sau khi các `Phrase` bên trong đã bị cắt vào biên section:

1. **Đoạn đứng yên hoàn toàn (`max(span) == min(span)`)**:
   - Khi `pitches` trong cả section hoàn toàn không đổi (`max(span) - min(span) == 0`), đặt một lần tấn công ở phách 1 ô đầu của đoạn, cao độ đã gập vào `G3–C6`, dài tối đa 4 ô (`_hold(FLAT_HOLD)`). Phần còn lại của đoạn là nghỉ trên P1, giường tiếp tục.
   - Nếu cao độ đó trùng hơi vừa tan và đường giá từ hơi trước tới đây không hề nhúc nhích thì không tấn công: P1 nghỉ hết đoạn để nốt vừa fade không bị thổi lại.
   - Những đoạn có dịch chuyển bậc thang nhẹ (`1..2` semitone, tức `0 < max(span) - min(span) < MIN_RISE`) **không** bị ép thành một nốt phẳng như cũ mà đi vào bộ dựng hơi thở bên dưới để bắt được bước chuyển nấc thang.

2. **Chia cửa sổ thở (Breath Windows) trong mỗi section có chuyển động**:
   - Mỗi section được chia thành các cửa sổ thở liên tiếp có độ dài chuẩn bằng `_hold(GLASS_HOLD)` (`32` móc đơn = 4 ô ở 4/4; `30` móc = 5 ô ở 3/4; `36` móc = 3 ô ở 6/4). Một section 8 ô 4/4 có 2 cửa sổ thở (4 ô đầu và 4 ô sau).
   - Giữa hai hơi thở liên tiếp phải có tối thiểu **1 ô nhịp nghỉ lấy hơi** (`BREATH_REST = epb` móc đơn, hoặc `2 * epb` khi `groove_at(bar).calm`). Nhờ vậy mỗi cửa sổ 4 ô tạo ra một hơi ngân dài `2–3` ô nhịp (`16–24` móc đơn) kèm `1–2` ô nhịp nghỉ thoáng đãng trước khi sang hơi thở kế tiếp.
   - Hơi thở ở cửa sổ cuối của section được phép bắt đầu và ngân trong nửa sau của section (không bị cắt bỏ bởi điều kiện `end - run.start >= PILLAR_GAP`), giúp giữ được hành động giá và mức đóng cửa ở cuối đoạn.

3. **Điểm neo đường viền (Contour Anchors) và sự uốn lượn bên trong một hơi thở**:
   - Mọi điểm đổi nốt trong hơi thở đều đặt tại phách 1 của ô nhịp (`bar_start`, qua `_one_per_bar`) để giữ nhịp điệu khoan thai của Ambient, không sinh nốt móc lẻ hay nhịp vụn.
   - Trong phạm vi các ô đang kêu của một hơi thở (dài `2–3` ô nhịp), chọn tối đa **2 đến 3 điểm neo** theo đường viền giá thực tế:
     1. **Nốt mở hơi (`anchor_0`)**: cao độ tại đầu cửa sổ thở.
     2. **Cực trị cục bộ (`apex` hoặc `trough`)**: ô nhịp bên trong hơi thở có độ lệch lớn nhất so với `anchor_0` theo **cả chiều tăng lẫn chiều giảm** (bắt cả đỉnh kéo lên lẫn đáy nhúng xuống), miễn là chênh lệch ít nhất một bậc âm giai (`abs(midi - anchor_0.midi) >= STEP_INFLECT`, với `STEP_INFLECT = 2` semitone).
     3. **Nốt kết hơi (`closing anchor`)**: cao độ ở ô cuối của hơi thở nếu nó tiếp tục đi xa hơn hoặc đổi chiều $\ge 2$ semitone so với điểm neo liền trước.
   - Nếu trong suốt cửa sổ thở giá không lệch đủ `2` semitone, hơi thở giữ nguyên **1 nốt ngân dài**. Nếu giá dịch chuyển một chiều, hơi thở gồm **2 nốt nối `<slur>`**. Nếu giá nhún xuống rồi rút lên (hoặc kéo lên đỉnh rồi lùi lại) trong cửa sổ, hơi thở gồm **2–3 nốt nối `<slur>`** bám đúng đường cong đó.

4. **Cách đặt nốt, nối `<slur>` / `<tie>` và lọc tấn công trùng cao độ**:
   - Cao độ mỗi điểm neo được gập quãng 8 (`_fold_glass`) vào vùng `G3–C6` và tránh nhảy quá một quãng 8 so với nốt ngay trước.
   - Các nốt khác cao độ nằm trong cùng một hơi thở chạm nhau tại vạch nhịp và được nối liền thành một làn hơi bằng liaison (`<slur>` từ nốt đầu hơi đến nốt cuối hơi). Chỉ nốt mở đầu hơi mới mang `<tenuto/>`; các nốt uốn lượn bên trong hơi trượt mềm dưới `<slur>` mà không đánh lưỡi lại.
   - Cùng cao độ chỉ buộc `<tie>` khi hai miền ngân chạm nhau, tổng độ dài một cao độ đứng yên liên tục không vượt quá `_hold(GLASS_HOLD)` (4 ô). Hơi đã đủ trần 4 ô ở cùng một cao độ thì nhả tại biên để P1 nghỉ.
   - **Quy tắc không thổi lại sau khoảng nghỉ (`_omit_same_pitch_reattacks`)**:
     - Khi sau một khoảng nghỉ mà hơi mới mở ra ở cùng cao độ `prev_midi` với cuối hơi trước: **chỉ bỏ hơi mới** nếu hơi mới là một nốt đơn đứng yên **và** trong suốt khoảng thời gian từ hơi trước đến hơi mới, đường giá `pitches` cũng đứng yên (`max(span) - min(span) < STEP_INFLECT`).
     - Nếu giữa hai hơi giá đã dao động đi nơi khác rồi mới quay lại test đúng cao độ `prev_midi`, hoặc nếu hơi mới tự nó uốn lượn sang cao độ khác (`slur`), thì hơi mới **vẫn được phát âm** để người nghe nhận biết sự vận động của giá.

5. **Động lực học của một hơi ngân (`_breath` & `_arc_breaths`)**:
   - Mỗi chuỗi nốt nối liền nhau (bằng `<tie>` hoặc `<slur>`, kể cả hơi có 2–3 nốt uốn lượn, đoạn phẳng, intro và outro) tạo thành **một hơi ngân lắng chậm duy nhất**:
   - Mở đầu ngay ở phách 1 của nốt đầu hơi bằng chữ `mp` (khi biên độ trong hơi và bước chuyển từ hơi trước nhỏ hơn `MIN_RISE`) hoặc `mf` (khi các nốt trong hơi hoặc bước chuyển từ hơi trước chênh nhau ít nhất `MIN_RISE` = 3 semitone), rồi mở **một `<diminuendo>` duy nhất** kéo dài từ đầu hơi tới hết nốt cuối của hơi đó để tiếng sáo tan dần tự nhiên.

6. **Intro và Outro**:
   - Intro: một nốt kính suốt section intro (chủ âm ở bản có frame, hoặc cùng cao độ với nốt mở của đoạn `phrase` đầu ở bản không frame). Trùng cao độ và chạm nhau thì buộc `<tie>` sang đoạn `phrase` đầu.
   - Outro: một nốt (chủ âm ở bản có frame, hoặc cao độ close cuối đã lượng tử hóa và gập vào `G3–C6`). Cao độ khác hơi vừa ngân thì giữ hết section outro. Cùng cao độ và chạm biên thì chỉ buộc phần hơi còn thiếu cho đủ trần (`COOLDOWN_HOLD = 40` móc ở bản ngày có frame, hoặc `_hold(GLASS_HOLD)` ở bản thường), rồi nghỉ. Cùng cao độ mà hơi đã đủ, hoặc đã có nghỉ mà giá đứng yên, thì outro không có sáo. Hai ô cuối của outro không có shimmer. Không có section outro thì không viết nốt outro.

## Nở và shimmer

P3 để trống, trừ các cửa sổ thanh khoản có băng `mf` hoặc `f` mà ô thứ hai của cửa sổ thuộc section `phrase`. Hai lần nở cách nhau ít nhất 4 ô (`SWELL_GAP_BARS = 4`). Đặt tại phách 1 của ô thứ hai đó một hợp âm 3 âm mở trên kèn French Horn (`Horn in F`, `Muse Brass`) ở vùng ấm `C3–A4` (`48..69`), viết qua `written()` thành hai nửa buộc nhau với tổng độ dài tối đa 2 ô nhịp (`SWELL_HOLD = 16` móc đơn, hoặc 1 ô = 8 móc đơn khi chạm biên cuối section `phrase`):

- Nốt đỉnh (`top`) là âm hợp âm cao nhất trong vùng `C4–A4` (`60..69`).
- Nốt đáy (`bottom`) là âm hợp âm trong vùng khoảng một quãng 8 dưới `top` (`max(45, top - 16) .. top - 8`) không tạo quãng 2 với `top`.
- Nốt giữa (`middle`) là âm hợp âm (`chord.pitch_classes`) nằm giữa `bottom` và `top` với khoảng cách ít nhất một quãng 3 thứ so với cả hai đầu.
- Nửa đầu của tiếng nở mang `velocity = 49` (`p`), nửa sau mang `velocity = 64` (`mp`, khi băng là `mf`) hoặc `80` (`mf`, khi băng là `f`), khớp với bảng `DYNAMICS`. `_ambient_swell_part` in cung sóng `p < mp >` hoặc `p < mf >` trên hai nửa đó (kể cả khi tiếng nở ở cuối phrase chỉ dài 1 ô và tách làm hai nốt trắng buộc nhau), để cả direction lẫn note velocity đều xuất phát từ `p` rồi dâng lên đỉnh trước khi tan dần. Các cửa sổ `p`, `mp`, intro và outro không nở.

Shimmer chọn sau khi nhìn hết cửa sổ ngân sách. Cửa sổ là `spec.chunk_bounds()`:

- 1D, `chunks` rỗng: cả 30 ô.
- 1W: từng phiên 32 ô.
- 1M trở đi: từng chunk của chương.

Không tính theo `spec.sections`. Section 8 ô có 64 móc đơn, `round(0.05 × 64) = 3`, nhỏ hơn một nốt tròn (8 móc đơn). `week_spec` còn chia mỗi phiên thành bốn section 8 ô, nên vòng `bell_caps` hiện tại cũng ra 3 móc đơn.

Ngân sách thô của một cửa sổ là `round(0.05 × số móc đơn)`. Nhân với `bell_budget(span_cửa_sổ) / BELL_MAX_EIGHTHS`, bằng 0 khi span đó không quá 0,5%. Làm tròn. Một shimmer tốn 8 móc đơn. Cửa sổ còn dưới 8 thì không có shimmer. 1D đủ biến động được 12 móc đơn, tức một nốt tròn. Một phiên 1W đủ biến động được 13 móc đơn, cũng một nốt tròn.

`span_cửa_sổ` là `_section_rel_span(bars, groups, chunk_start, chunk_end)` của chính chunk đó. `rel_span` mà `render.py` tính cho cả chương không dùng ở đây. Với 1W, đó là biên độ của một phiên, nên ngày phẳng trong tuần có sóng không có shimmer. `render_ambient_score` nhận `bars` và `groups` để tính span này.

Ứng viên là đỉnh có MIDI từ E5 (76) trở lên, và các sự kiện breakout sẵn có, nằm trong đoạn `phrase`. Hết ngân sách thì bỏ ứng viên có `rise` nhỏ hơn. Hai shimmer cách nhau ít nhất 4 ô. Mỗi shimmer là một nốt tròn, `f` (`velocity` 90, cộng `+6 dB` trên fader track `Celesta`), một âm hợp âm trong vùng chuông vang `D5–C6` (`74..84`), bắt đầu bằng `written()` tại phách 1 của ô chứa đỉnh.

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

1. `backend/app/sonify/ambient.py`: `render_ambient_score(..., windows, sections, bars, groups)`, `AMBIENT_BPM = 60`. Dựng hơi thở uốn lượn (Inflected Breaths) theo cửa sổ thở trong từng `FormSection` (mỗi hơi dài 2–3 ô nhịp nối `<slur>` qua tối đa 2–3 điểm neo bắt cả đỉnh, đáy và bước chuyển bậc thang $\ge 2$ semitone, cách nhau 1–2 ô nghỉ và lắng dần qua một `<diminuendo>`), giường theo từng ô sau `jazz_chord()`, nở French Horn theo cửa sổ `mf`/`f`, shimmer theo `chunk_bounds` và `bell_budget` của từng chunk.
2. Nhánh `variant == "ambient"` trong `_compose`, sau khi slot, phrase và pitch đã có. Truyền `windows`, `spec.sections`, `bars` và `groups`. 1D dùng `DAILY_SPEC` và `AMBIENT_BPM`. Có `FormSpec` thì BPM là `spec.bpm`. `Score.slots` là slot đã nâng. `Score.dynamics` là chữ giường trần `mp`.
3. `Variant` trong `model.py` và schema recap / span thêm `"ambient"`. `Score.variant` nhận giá trị đó.
4. `_PARTS_BY_VARIANT` thêm năm program ở bảng trên. `_bass_part` gắn `chord` khi hai nốt cùng phách. P2 Ambient dùng khóa Sol và mở đầu ở `p`. P3 Ambient là một khuông (`Horn in F`), mở đầu ở `p`, vuốt sóng `p < mp >` hoặc `p < mf >` qua hai nửa buộc nhau (1–2 ô), và không in `<harmony>`.
5. `_STORED_NAME` và `_prune_spans` dùng `VARIANTS`.
6. Chip «Ambient» trong `SessionRecap` và `SpanRecap`. `RecapVariant` ở client thêm `'ambient'`.

## Kiểm tra

- Phiên 1D đứng yên hoàn toàn (`max(span) == min(span)`): chỉ mở một hơi phẳng ở đầu thân rồi nghỉ hết các đoạn phẳng tiếp theo; warm-up buộc sang đoạn đầu khi trùng cao độ, cool-down nghỉ khi hơi đã tan.
- Đoạn có chuyển động bậc thang ($\ge 2$ semitone) hoặc có đỉnh/đáy cục bộ (`apex` / `trough`): mỗi cửa sổ thở 4 ô tạo một hơi thở uốn lượn gồm 2–3 nốt nối `<slur>` ở đầu các ô nhịp kèm một `<diminuendo>` duy nhất, cách hơi thở kế tiếp 1–2 ô nghỉ.
- Giá ở cuối section (`closing anchor`) vẫn được giữ trong hơi thở nửa sau của section thay vì bị xóa trắng 3 ô cuối đoạn.
- Khi giá dao động đi chỗ khác rồi quay lại test cao độ cũ sau một khoảng nghỉ, hơi thở mới vẫn cất tiếng; chỉ khi đường giá thực tế đứng yên suốt khoảng nghỉ thì nốt đơn trùng cao độ mới bị lược bỏ.
- Mọi chữ dynamic và `<wedge>` của hơi thở trên P1 đều đứng ngay phách 1 của nốt đầu hơi, không bị đẩy ra cuối ô sau một nốt tròn.
- Hai miền cùng cao độ chạm nhau buộc `<tie>` tối đa đủ trần 4 ô (`GLASS_HOLD`), rồi nhả. Intro 1D dài 2 ô và buộc sang đoạn phrase đầu khi cùng cao độ và chạm nhau. Outro 1D dài 2 ô (bản có frame) hoặc 4 ô (`DAILY_SPEC`).
- Chương II của 1M không có nốt kính outro. Intro của 1W dài 8 ô.
- `C` rồi `Cmaj7` sau `jazz_chord()` là một lần tấn công `Cmaj9`. Drone không đánh lại khi hợp âm jazz không đổi. Quãng 5 chỉ có trên ô `mf` và `f`, và trong MusicXML là `<chord>`, không làm ô 4/4 thành 8 phách.
- Cửa sổ `mf`/`f` mà ô thứ hai thuộc `phrase` (cách lần nở trước ít nhất 4 ô) có một hợp âm French Horn 3 âm mở (mỗi quãng liền kề từ 3 semitone trở lên) chia hai nửa buộc nhau (dài 1–2 ô) với cung sóng `p < mp >` hoặc `p < mf >`. Cửa sổ nhỏ hơn, intro và outro không có. P3 một khuông, không có `<harmony>`.
- Shimmer của 1D đủ biến động dài 8 móc đơn và không vượt `round(0.05 × 240)`. Span của cửa sổ không quá 0,5% thì cửa sổ đó không có shimmer. Hai shimmer, khi cửa sổ chứa được hai nốt, cách nhau ít nhất 4 ô.
- Một tuần đủ 5 phiên vẫn 160 ô, BPM của form, ngân sách shimmer tính theo từng chunk 32 ô. Phiên phẳng trong tuần có sóng không có shimmer. Phiên đủ biến động vẫn có.
- Score Tối giản của cùng một chuỗi nến không đổi. File span Ambient còn sau `prune()`.
