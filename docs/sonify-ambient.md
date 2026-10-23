# Ambient: bản nghe có kết cấu

Kiểu nghe thứ tư, cạnh Giao hưởng và Jazz. Tối giản giữ nguyên.

Ambient là một `Score` soạn xong cả chương rồi mới xuất tiếng, cùng đường với `render_jazz_score`. Form, hợp âm Markov, câu nhạc và nốt đã lượng tử hóa có trước. Phần Ambient chỉ viết năm bè lên cái khung đó. Im lặng là mặc định, và im lặng nằm trong câu.

## Vì sao không lấy cách stream

`arrange()` trong `voices.py` chỉ thấy một bucket 250 ms và nốt vừa kêu. Giao hưởng, Jazz và Ambient trên stream đều nghe vỡ vụn vì vậy: không có câu, không có hợp âm đã chọn cho cả đoạn, mỗi bucket tự quyết định có đánh hay không.

`should_strike_ambient` là cổng của stream. Bản nghe không gọi nó. Một nốt kính được giữ hay bỏ khi đã nhìn hết đoạn.

Stream để nguyên. Tài liệu này chỉ nói bản nghe phiên và bản nghe dài.

## Hai đơn vị câu

`FormSection` là đoạn của form. Ở bản 1D (`DAILY_AMBIENT_SPEC`, 34 ô), warm-up (`intro`) dài 2 ô (`0..2`), ba đoạn `phrase` dài 10, 8 và 12 ô (`2..12`, `12..20`, `20..32`), và cool-down (`outro`) dài 2 ô (`32..34`). Từ 1W trở đi độ dài lấy từ `spec.sections`. Chương II của 1M không có `outro` giá (chỉ có `cooldown` 3 ô nhịp 6/4 khi gắn `attach_frame`).

`Phrase` của `plan_phrases()` là câu giai điệu bên trong đoạn đó. Trần là `MAX_EIGHTHS = 32`, tức 4 ô. Một đoạn `phrase` 8–12 ô luôn bị cắt thành hai hoặc ba `Phrase`. Phiên phẳng bị cắt giữa nốt, `held_over=True` ở câu đầu. `_settle_edge` còn cho một câu tràn tối đa `PERIOD` (4 móc đơn, nửa ô) sang section sau.

Mọi quy tắc tỉa giai điệu kính trong tài liệu này nói về `FormSection` có `kind == "phrase"`. `plan_phrases()` vẫn cung cấp các `Phrase` để `_shimmer` tìm ứng viên đỉnh và breakout sau khi cắt vào biên section.

## Chỗ nó ngồi

`render()` / `_compose()` làm xong phần chung, rồi rẽ biến thể. Ambient rẽ cùng chỗ Jazz và Tối giản đang rẽ, sau khi đã có:

- `plan_slots`: intro, các đoạn phrase, outro, hợp âm từng ô
- thang giá và `raw_pitches`
- `quantize_strong_beats`: giai điệu trên thang, phách mạnh bám âm hợp âm
- `plan_phrases`: đường viền bên trong từng đoạn
- `liquidity_windows_for(spec)` và băng `p`–`f` trên `band_at`

`render_ambient_score` nhận các thứ của `render_jazz_score`, cộng thêm `windows` và `spec.sections`. `band_at` một mình không đủ: hai cửa sổ `f` liền nhau là bốn ô `f`, không còn thấy đâu là ô thứ hai của từng cửa sổ. Bản 1D dùng `DAILY_AMBIENT_SPEC` (34 ô) và `liquidity_windows_for(DAILY_AMBIENT_SPEC)`.

`Variant` thêm `"ambient"`. `StreamVariant` đã có chữ này cho stream. Hai kiểu không dùng chung hàm soạn. Khóa cache đã gồm variant, nên file Giao hưởng, Jazz, Tối giản không bị thay.

`audio.py` có hai danh sách variant viết cứng. Regex `_STORED_NAME` và tuple trong `_prune_spans` đều lấy từ `VARIANTS`. Thiếu `_prune_spans` thì file span Ambient vừa render bị `prune()` xóa ở lần gọi sau.

## Form giữ nguyên

1D giữ phần thân giá 30 ô (`2..32`, `2:00` ở `60 BPM`) kèm 2 ô warm-up đầu và 2 ô cool-down cuối thành 34 ô (`DAILY_AMBIENT_SPEC`). Từ 1W trở đi Ambient nhận `FormSpec` theo bảng trong `docs/sonify-long-form.md` và `docs/sonify-meter-frame.md`. Nghỉ giữa chương vẫn do player chèn.

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

Cách tỉa trụ cũ trong `ambient.py` giới hạn số trụ theo `cap = 2 * section_eighths // 64` (2 trụ cho đoạn 8–10 ô, 3 trụ cho đoạn 12 ô; hằng `PILLARS_PER_EIGHT = 2` không được đọc), chỉ giữ các run giữa đoạn khi nhảy từ quãng 4 đúng trở lên (`LEAP = 5` semitone), gộp mọi section có biên độ dưới `MIN_RISE` (3 semitone) thành một nốt phẳng duy nhất, loại bỏ mọi trụ sau trụ mở nếu khoảng cách tới biên cuối đoạn nhỏ hơn `_gap` (`end - run.start < _gap(run.start)`, tức xóa trắng 3 ô cuối đoạn, hoặc 4 ô cuối khi `groove_at(bar).calm`), loại bỏ cả các đỉnh nằm cách trụ mở chưa đầy 3 ô (`PILLAR_GAP = 24` móc đơn), và xóa mọi nốt trùng cao độ sau khoảng nghỉ bất chấp giá ở giữa đã dao động. Hệ quả là ở `60 BPM` (1 ô 4/4 = 4 giây), sáo giữ một nốt ngang suốt 16 giây rồi nghỉ 8–16 giây, làm mất dấu các nhịp bò dần theo bậc thang, các nhịp nhúng xuống (trough / dip) và mức giá đóng cửa ở cuối đoạn.

Để giữ đúng bản chất Ambient (ít lần lấy hơi, không chạy nốt vụn, luôn có khoảng lặng để nghe nền Drone + Halo) nhưng phản ánh sát **Price Action**, bè kính chuyển từ **«Trụ phẳng 1 nốt»** sang **«Hơi thở uốn lượn» (Inflected Breaths)**:

```text
Ô nhịp: |   Ô 1   |   Ô 2   |   Ô 3   |   Ô 4   |   Ô 5   |   Ô 6   |   Ô 7   |   Ô 8   |
Giá:    |   C5    |   C5    |   E5    |   D5    |   D5    |   D5    |   D5    |   C5    |

Trụ phẳng cũ (E5 ở Ô 3 bị loại vì cách Ô 1 < 3 ô; D5 bị loại vì < LEAP; C5 ở Ô 8 bị loại vì sát biên < 3 ô):
Sáo P1: |═══════════════ C5 (4 ô) ══════════════|         [ Nghỉ 4 ô (Ô 5–8) ]          |
        | mp ──────────────────────────────────> |                                       |

Hơi thở uốn lượn (Hơi 1: Ô 1–3; Nghỉ: Ô 4; Hơi 2: Ô 5–8 chạm ô cuối):
Sáo P1: |══════ C5 (2 ô) ══════ (slur) ══ E5 ═══| [Nghỉ]  |═════════ D5 (3 ô) ═════════ (slur) ══ C5 ═══|
        | mf ──────────────────────────────────> |        | mp ────────────────────────────────────────> |
```

### Quy tắc tỉa và đặt hơi thở trên từng `FormSection` (`kind == "phrase"`)

Tỉa từng `FormSection` có `kind == "phrase"`:

1. **Đoạn đứng yên hoàn toàn (`max(span) == min(span)`) và ngưỡng bậc thang (`STEP_INFLECT = 1`)**:
   - Đặt `STEP_INFLECT = 1` semitone (tương đương $\ge 1$ bậc trên thang đã lượng tử hóa `pitches`, bao gồm cả các bậc nửa cung `E–F`, `B–C`, `D–Eb`, `G–Ab`).
   - Khi `pitches` trong cả section hoàn toàn không đổi (`max(span) - min(span) == 0`, tức `< STEP_INFLECT`), đặt một lần tấn công ở phách 1 ô đầu của đoạn, cao độ đã gập vào `G3–C6`, dài tối đa `_hold(FLAT_HOLD)` (4 ô ở 4/4). Phần còn lại của đoạn là nghỉ trên P1, giường tiếp tục.
   - Nếu cao độ đó trùng hơi vừa tan và đường giá từ hơi trước tới đây hoàn toàn không nhúc nhích (`max(between) == min(between)`) thì không tấn công: P1 nghỉ hết đoạn để nốt vừa fade không bị thổi lại.
   - Mọi section có dịch chuyển từ `STEP_INFLECT = 1` semitone trở lên (`max(span) - min(span) >= 1`) đều đi vào bộ dựng hơi thở ở Mục 2 và Mục 3 bên dưới.

2. **Tách biệt trần ngân (`GLASS_HOLD`) và cửa sổ thở (`WINDOW_BARS`, phần kêu, phần nghỉ) theo từng nhịp**:
   - Không dùng `_hold(GLASS_HOLD)` làm độ dài cửa sổ thở. Hai đại lượng được định nghĩa tách biệt cho từng nhịp:

     | Nhịp | `epb` | Trần ngân 1 cao độ trong thân `_hold(GLASS_HOLD)` (`max_hold_bars`) | Bước cửa sổ chuẩn (`WINDOW_BARS`) | Phần kêu tiêu chuẩn (`sound_bars`) | Nghỉ giữa hai hơi (`rest_bars` thường / `calm`) |
     |---|---|---|---|---|---|
     | **4/4** | 8 | 32 móc (**4 ô**) | **4 ô** (32 móc) | **3 ô** (24 móc); khi `calm`: **2 ô** (16 móc) | **1 ô** (8 móc); khi `calm`: **2 ô** (16 móc) |
     | **3/4** | 6 | 30 móc (**5 ô**) | **4 ô** (24 móc) | **3 ô** (18 móc); khi `calm`: **2 ô** (12 móc) | **1 ô** (6 móc); khi `calm`: **2 ô** (12 móc) |
     | **6/4** | 12 | 36 móc (**3 ô**) | **4 ô** (48 móc) | **3 ô** (36 móc, kể cả khi `calm`) | **1 ô** (12 móc, kể cả khi `calm`) |

   - **Cách chia một section `phrase` dài `L = section.end - section.start` ô thành các miền hơi kêu `[b_start, b_end)`**:
     - Nếu `L <= WINDOW_BARS` (ví dụ đoạn `phrase` 4 ô ở hai đầu bản `1W`): có **1 hơi thở duy nhất** phủ trọn `[section.start, section.end)`, không có nghỉ giữa hơi.
     - Nếu `L > WINDOW_BARS`: số hơi thở trong section là `N = L // WINDOW_BARS`. Chia `L` ô thành `N` cửa sổ liền kề bằng `split_into(L, N)` (các cửa sổ chênh nhau tối đa 1 ô, phần dư nằm ở các cửa sổ cuối: đoạn 8 ô $\rightarrow$ `[4, 4]`; đoạn 10 ô $\rightarrow$ `[5, 5]`; đoạn 12 ô $\rightarrow$ `[4, 4, 4]`; đoạn 13 ô $\rightarrow$ `[4, 4, 5]`; đoạn 14 ô $\rightarrow$ `[4, 5, 5]`).
     - **Nghỉ chỉ nằm giữa hai hơi; hơi cuối section luôn chạm ô cuối (`b_end = section.end`)**:
       - Với các cửa sổ trước cửa sổ cuối (`0 <= i < N - 1`, cửa sổ `[w_start, w_end)` dài `w = w_end - w_start` ô):
         - Hơi thở mở tại đầu cửa sổ: `b_start = w_start`.
         - Số ô nghỉ ở đuôi cửa sổ (ngăn cách với hơi `i + 1`) là `rest = max(rest_bars, w - max_hold_bars)`.
         - Miền kêu của hơi `i` là `[w_start, w_end - rest)`.
       - Với **cửa sổ cuối cùng của section (`i == N - 1`, cửa sổ `[w_start, section.end)`)**:
         - **Không dành đuôi cửa sổ để nghỉ**: `b_end = section.end`, để ô cuối cùng của section (`section.end - 1`) luôn nằm trong hơi thở cuối.
         - Điểm mở hơi cuối là `b_start = max(w_start, section.end - max_hold_bars)`. Nếu cửa sổ cuối dài hơn `max_hold_bars` (như cửa sổ 5 ô cuối của đoạn 10 ô ở 4/4, hoặc cửa sổ 4 ô cuối ở 6/4 nơi `max_hold_bars = 3`), phần ô dư ở đầu cửa sổ cuối tự động cộng vào khoảng nghỉ ngay trước hơi cuối.
     - Cụ thể trên 3 đoạn `phrase` của bản ngày `DAILY_AMBIENT_SPEC` (34 ô: warm-up `0..2`, phrase 1 `2..12` dài 10 ô, phrase 2 `12..20` dài 8 ô, phrase 3 `20..32` dài 12 ô, cool-down `32..34` dài 2 ô):
       - **Phrase 1 (`2..12`, 10 ô $\rightarrow$ `[5, 5]`)**: Hơi 1 kêu `2..6` (4 ô; hoặc `2..5` khi `calm`), nghỉ giữa hai hơi tới ô `8` (`6..8` = 2 ô; hoặc `5..8` = 3 ô khi `calm`), Hơi 2 kêu `8..12` (4 ô, chạm ô cuối `11` của Phrase 1).
       - **Phrase 2 (`12..20`, 8 ô $\rightarrow$ `[4, 4]`)**: Hơi 1 kêu `12..15` (3 ô; hoặc `12..14` khi `calm`), nghỉ `15..16` (1 ô; hoặc `14..16` = 2 ô khi `calm`), Hơi 2 kêu `16..20` (4 ô, chạm ô cuối `19` của Phrase 2).
       - **Phrase 3 (`20..32`, 12 ô $\rightarrow$ `[4, 4, 4]`)**: Hơi 1 kêu `20..23` + nghỉ `23..24`; Hơi 2 kêu `24..27` + nghỉ `27..28` (hoặc kêu 2 ô + nghỉ 2 ô khi `calm`); Hơi 3 kêu `28..32` (4 ô, chạm ô cuối `31` của thân trước khi vào cool-down ở ô `32`).

3. **Điểm neo đường viền (Contour Anchors) và sự uốn lượn bên trong một hơi thở `[b_start, b_end)`**:
   - Mọi điểm đổi nốt trong hơi thở đều đặt tại phách 1 của ô nhịp (`b * epb`) để giữ nhịp điệu khoan thai của Ambient và bám âm hợp âm đã lượng tử hóa ở phách 1. Cao độ đại diện của mỗi ô `b` trong `[b_start, b_end)` là cao độ phách 1 `m(b) = _fold_glass(pitches[b * epb], prev_midi)`.
   - Trong phạm vi `b_start .. b_end - 1` (dài `2–5` ô tùy nhịp), chọn tối đa **3 điểm neo** theo thứ tự thời gian:
     1. **Neo mở (`anchor_0`)**: tại ô đầu hơi `b_start`, cao độ `m_0 = m(b_start)`.
     2. **Neo cực trị nội bộ (`anchor_mid`, xét khi hơi có ô nội bộ `b_start < b < b_end - 1`)**: chọn ô nội bộ `b_mid` có độ lệch `abs(m(b) - m_0)` lớn nhất (nếu bằng nhau, lấy ô sớm hơn), miễn là `abs(m(b_mid) - m_0) >= STEP_INFLECT` (`1` semitone). Nhờ xét `abs(m(b) - m_0)`, hơi thở bắt được cả **đỉnh (`apex`)** lẫn **đáy (`trough`)**, và bắt được cả bước chuyển 1 bậc thang nửa cung (`E–F`, `B–C`).
     3. **Neo đóng (`anchor_close`)**: tại ô cuối của hơi `b_close = b_end - 1`, cao độ `m_close = m(b_close)`. Giữ `anchor_close` nếu nó lệch ít nhất `STEP_INFLECT` (`1` semitone) so với điểm neo đang giữ liền trước (`anchor_mid` nếu có, ngược lại là `anchor_0`). Ở hơi thở cuối cùng của section, `b_close = section.end - 1` chính là phách 1 của ô cuối section, ngân trọn ô cuối tới `section.end`.
   - Từ danh sách `k` điểm neo (`1 <= k <= 3`) trong hơi thở `[(b_0, midi_0), ..., (b_{k-1}, midi_{k-1})]`:
     - Nếu `k == 1` (mọi ô trong hơi cùng cao độ `midi_0`): hơi thở là **1 nốt ngân dài** suốt `(b_end - b_start) * epb` móc đơn (`slur = False`).
     - Nếu `k >= 2`: nốt thứ `j` (`0 <= j < k - 1`) ngân từ `b_j * epb` đến `b_{j+1} * epb` với `slur = True`; nốt cuối `k - 1` ngân từ `b_{k-1} * epb` đến `b_end * epb` với `slur = False`. Chỉ nốt đầu hơi (`j == 0`, khi không phải `tie_in`) mang `<tenuto/>`; các nốt sau trượt mềm dưới một liaison `<slur>` mà không đánh lưỡi lại.

4. **Quy tắc buộc `<tie>` qua biên và lọc tấn công trùng cao độ (`_omit_same_pitch_reattacks`)**:
   - Trần `_hold(GLASS_HOLD)` (32 móc = 4 ô ở 4/4, 30 móc = 5 ô ở 3/4, 36 móc = 3 ô ở 6/4) là **trần của một cao độ đứng yên liên tục bên trong thân `phrase`** (tính trước khi gắn `warm-up` và `cool-down`).
   - Khi hai miền cùng cao độ trong thân `phrase` chạm nhau tại vạch nhịp (ví dụ cuối hơi trước chạm đầu hơi của section kế tiếp), phần chạm được buộc `<tie>` tối đa cho đủ phần còn thiếu của `_hold(GLASS_HOLD)`, rồi nhả để P1 nghỉ.
   - Khi sau một khoảng nghỉ giữa hai hơi trong thân `phrase`, hơi mới mở ra ở cùng cao độ `prev_midi` với nốt cuối của hơi trước:
     - **Chỉ bỏ hơi mới** nếu hơi mới là một nốt đơn đứng yên (`not slur`) **và** trong suốt khoảng thời gian từ cuối hơi trước đến hết hơi mới, đường giá `pitches` hoàn toàn không nhúc nhích (`max(span) - min(span) == 0`, tức `< STEP_INFLECT`).
     - Nếu giữa hai hơi đường giá `pitches` đã dịch chuyển ($\ge 1$ semitone) rồi mới quay lại test đúng cao độ `prev_midi`, hoặc nếu hơi mới tự nó uốn lượn sang cao độ khác (`slur = True`), thì hơi mới **vẫn được phát âm**.

5. **Động lực học của hơi ngân trong `phrase` so với khung `warm-up` / `cool-down`**:
   - **Bên trong thân `phrase` (`_arc_breaths`)**: Mỗi chuỗi nốt nối liền nhau bằng `<tie>` hoặc `<slur>` tạo thành **một hơi ngân lắng chậm duy nhất**. Mở đầu ngay ở phách 1 của nốt đầu hơi bằng chữ `mf` (khi biên độ `max(arc_midis) - min(arc_midis) >= MIN_RISE` hoặc bước chuyển từ cuối hơi trước `abs(arc_midis[0] - prev_arc_midi) >= MIN_RISE`, với `MIN_RISE = 3` semitone) hoặc `mp` (khi cả biên độ trong hơi và bước chuyển từ hơi trước đều `< MIN_RISE`), kèm **một `<diminuendo>` duy nhất** từ đầu hơi đến hết nốt cuối của hơi đó.
   - **Khung `warm-up` và `cool-down` (`_attach_daily_frames`, `_daily_frame_breaths`, và `movement_frame.py:_ambient`) giữ nguyên**:
     - **Warm-up** (ô `0..2` của bản 1D có frame, hoặc `warmup` của bản dài 1M–1Y): đạp chủ âm `_tonic_glass`, mở bằng chữ `p` tại phách 1 ô đầu và chạy `<crescendo>` tới hết warm-up. Khi nốt mở đầu thân `phrase` trùng cao độ chủ âm và chạm biên warm-up, hai bên buộc `<tie>` qua biên; độ dài warm-up **nằm ngoài trần `_hold(GLASS_HOLD)` của thân** (nên phiên 1D phẳng ngân liền 2 ô warm-up + 4 ô đầu thân = **6 ô = 24 phách đen**).
     - **Cool-down** (ô `32..34` dài **2 ô** của bản 1D có frame, hoặc `cooldown` của bản dài 1M–1Y): đạp chủ âm `_tonic_glass`, **không** đọc giá đóng cửa và **không** áp luật re-attack theo biến động giá. Nếu nốt cuối thân cùng cao độ với chủ âm và chạm biên cool-down (`touches`), hơi đang kêu được buộc kéo dài tối đa đủ `COOLDOWN_HOLD = 40` móc (5 ô tính từ đầu hơi đó) rồi nghỉ; nếu cùng cao độ nhưng đã có khoảng nghỉ trước biên cool-down (`not touches`), cool-down **luôn nghỉ** (không bao giờ thổi lại chủ âm dù giá trong thân có nhích). Nếu khác cao độ với chủ âm, cool-down mở chủ âm mới ở `mp`. Trong mọi trường hợp có tiếng trên cool-down, hơi lắng dần bằng `<diminuendo>` về `ppp` (`COOLDOWN_MARKING`) ở ô cuối.
     - **Bản không gắn frame riêng** (như `1W`, hoặc khi gọi `render(..., framed=False)` với `DAILY_SPEC`): `intro` giữ cao độ mở của `phrase` đầu (buộc `<tie>` nếu chạm); `outro` giữ cao độ close cuối đã lượng tử hóa (khác cao độ hơi trước thì ngân hết `outro`, cùng cao độ và chạm biên thì buộc cho đủ `_hold(GLASS_HOLD)`, cùng cao độ mà sau khoảng nghỉ thì nghỉ). Chương II của 1M không có `outro` giá (chỉ có `cooldown` khi gắn `attach_frame`). Hai ô cuối của `outro` không có shimmer.

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

1. `backend/app/sonify/ambient.py`: `render_ambient_score(..., windows, sections, bars, groups)`, `AMBIENT_BPM = 60`, `STEP_INFLECT = 1`, `WINDOW_BARS = 4`. Chia từng `FormSection` (`kind == "phrase"`) thành `N = max(1, L // WINDOW_BARS)` cửa sổ thở qua `split_into(L, N)`: các cửa sổ trước cửa sổ cuối dành `rest_bars` ở đuôi (4/4 và 3/4: 1 ô thường / 2 ô `calm`; 6/4: 1 ô), cửa sổ cuối không nghỉ đuôi để hơi cuối chạm đúng `section.end` (`b_start = max(w_start, section.end - max_hold_bars)`, `b_end = section.end`). Trong mỗi hơi `[b_start, b_end)`, chọn tối đa 3 điểm neo phách 1 (`anchor_0`, `anchor_mid` có `abs(m(b) - m_0) >= STEP_INFLECT` lớn nhất, và `anchor_close` tại `b_end - 1` nếu lệch $\ge 1$ semitone so với neo liền trước) nối `<slur>` dưới một `<diminuendo>` duy nhất (`mp` hoặc `mf` trong thân `phrase`). Giường theo từng ô sau `jazz_chord()`, nở French Horn theo cửa sổ `mf`/`f`, shimmer theo `chunk_bounds` và `bell_budget` của từng chunk.
2. Nhánh `variant == "ambient"` trong `_compose`, sau khi slot, phrase và pitch đã có. Truyền `windows`, `spec.sections`, `bars` và `groups`. 1D dùng `DAILY_AMBIENT_SPEC` (34 ô: warm-up 2 ô, ba đoạn `phrase` 10, 8, 12 ô, cool-down 2 ô) và `AMBIENT_BPM`. Có `FormSpec` thì BPM là `spec.bpm`. `Score.slots` là slot đã nâng. `Score.dynamics` là chữ giường trần `mp`.
3. `Variant` trong `model.py` và schema recap / span thêm `"ambient"`. `Score.variant` nhận giá trị đó.
4. `_PARTS_BY_VARIANT` thêm năm program ở bảng trên. `_bass_part` gắn `chord` khi hai nốt cùng phách. P2 Ambient dùng khóa Sol và mở đầu ở `p`. P3 Ambient là một khuông (`Horn in F`), mở đầu ở `p`, vuốt sóng `p < mp >` hoặc `p < mf >` qua hai nửa buộc nhau (1–2 ô), và không in `<harmony>`.
5. `_STORED_NAME` và `_prune_spans` dùng `VARIANTS`.
6. Chip «Ambient» trong `SessionRecap` và `SpanRecap`. `RecapVariant` ở client thêm `'ambient'`.

## Kiểm tra

- Phiên 1D đứng yên hoàn toàn (`max(span) == min(span)`): chỉ mở một hơi phẳng ở đầu thân (`2..6`, 4 ô) rồi nghỉ hết các đoạn phẳng tiếp theo; warm-up (`0..2`, 2 ô, mở `p` + `<crescendo>`) buộc `<tie>` sang đoạn đầu thành một chuỗi 6 ô (24 phách đen, giữ nguyên `test_flat_day_states_the_flute_pitch_once`), cool-down (`32..34`, 2 ô) nghỉ trên P1 và giường lắng về `ppp`.
- Đoạn `phrase` có chuyển động ($\ge 1$ semitone, tức `STEP_INFLECT = 1`, kể cả bậc nửa cung `E–F`, `B–C` hoặc đỉnh/đáy cục bộ): mỗi cửa sổ thở tạo một hơi thở uốn lượn gồm 2–3 nốt nối `<slur>` tại phách 1 của các ô nhịp kèm một `<diminuendo>` duy nhất (`mf` khi biên độ hơi hoặc bước chuyển từ hơi trước $\ge 3$ semitone, ngược lại `mp`).
- Nghỉ chỉ đứng giữa hai hơi thở; hơi thở cuối của mỗi section `phrase` luôn chạm `section.end` (ô `section.end - 1` mang `anchor_close` của section). Trên `DAILY_AMBIENT_SPEC` (phrase 10, 8, 12 ô), các hơi cuối chạm đúng các ô `11`, `19` và `31`. Ở nhịp 6/4, mỗi hơi thở dài 3 ô (36 móc) và nghỉ giữa hai hơi là 1 ô (12 móc), luôn đủ chỗ cho 2–3 điểm neo.
- Khi giữa hai hơi thở đường giá `pitches` đã dịch chuyển ($\ge 1$ semitone) rồi quay lại test cao độ cũ sau khoảng nghỉ, hơi thở mới trong `phrase` vẫn cất tiếng; chỉ khi đường giá thực tế đứng yên suốt khoảng đó (`max(span) == min(span)`) thì nốt đơn trùng cao độ mới bị lược bỏ.
- Hai miền cùng cao độ trong thân `phrase` chạm nhau buộc `<tie>` tối đa đủ trần `_hold(GLASS_HOLD)` (4 ô ở 4/4), rồi nhả. Warm-up 1D dài 2 ô nằm ngoài trần 4 ô đó. Cool-down 1D dài 2 ô (`32..34`) đạp chủ âm: nếu chạm hơi cuối thân cùng cao độ thì kéo dài tối đa đủ `COOLDOWN_HOLD = 40` móc (5 ô) rồi nghỉ; nếu sau khoảng nghỉ mà trùng cao độ chủ âm thì luôn nghỉ (không thổi lại chủ âm vì biến động giá trong thân), giữ nguyên `test_cool_down_extends_a_touching_breath_to_five_bars_then_rests`.
- Mọi chữ dynamic và `<wedge>` của hơi thở trên P1 đều đứng ngay phách 1 của nốt đầu hơi, không bị đẩy ra cuối ô sau một nốt tròn.
- Các test đang khóa quy tắc trụ phẳng cũ trong `backend/tests/test_sonify_ambient.py` (`test_a_rising_phrase_section_keeps_at_most_four_glass_attacks`, `test_a_faded_pitch_is_not_rebreathed_until_the_line_moves`) sẽ được cập nhật đồng bộ khi sửa `ambient.py`.
- Chương II của 1M không có nốt kính `outro` giá. Intro của 1W dài 4 ô (buộc sang đoạn `phrase` 4 ô kế tiếp khi phiên đầu phẳng, nên 8 ô đầu chỉ có một lần tấn công).
- `C` rồi `Cmaj7` sau `jazz_chord()` là một lần tấn công `Cmaj9`. Drone không đánh lại khi hợp âm jazz không đổi. Quãng 5 chỉ có trên ô `mf` và `f`, và trong MusicXML là `<chord>`, không làm ô 4/4 thành 8 phách.
- Cửa sổ `mf`/`f` mà ô thứ hai thuộc `phrase` (cách lần nở trước ít nhất 4 ô) có một hợp âm French Horn 3 âm mở (mỗi quãng liền kề từ 3 semitone trở lên) chia hai nửa buộc nhau (dài 1–2 ô) với cung sóng `p < mp >` hoặc `p < mf >`. Cửa sổ nhỏ hơn, intro và outro không có. P3 một khuông, không có `<harmony>`.
- Shimmer của 1D đủ biến động dài 8 móc đơn và không vượt `round(0.05 × 240)`. Span của cửa sổ không quá 0,5% thì cửa sổ đó không có shimmer. Hai shimmer, khi cửa sổ chứa được hai nốt, cách nhau ít nhất 4 ô.
- Một tuần đủ 5 phiên vẫn 160 ô, BPM của form, ngân sách shimmer tính theo từng chunk 32 ô. Phiên phẳng trong tuần có sóng không có shimmer. Phiên đủ biến động vẫn có.
- Score Tối giản của cùng một chuỗi nến không đổi. File span Ambient còn sau `prune()`.
