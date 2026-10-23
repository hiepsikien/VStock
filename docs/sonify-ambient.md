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
Giá:    |   C5    |   E5    |   E5    |   D5    |   D5    |   D5    |   D5    |   C5    |

Trụ phẳng cũ (E5 ở Ô 2 bị loại vì cách Ô 1 < 3 ô; D5 bị loại vì < LEAP; C5 ở Ô 8 bị loại vì sát biên < 3 ô):
Sáo P1: |═══════════════ C5 (4 ô) ══════════════|         [ Nghỉ 4 ô (Ô 5–8) ]          |
        | mp ──────────────────────────────────> |                                       |

Hơi thở uốn lượn (Hơi 1: Ô 1–2; Nghỉ: Ô 3–4; Hơi 2: Ô 5–8 chạm ô cuối):
Sáo P1: |════ C5 ════ (slur) ══ E5 ══| [ Nghỉ 2 ô ] |═════════ D5 (3 ô) ═════════ (slur) ══ C5 ═══|
        | mf ────────────────────────> |              | mp ────────────────────────────────────────> |
```

### Phân vai giữa Bè kính (`P1`) và các lớp còn lại

Để giữ không gian tĩnh lặng của Ambient, biến động thị trường được dịch thành **đường cong cao độ (pitch contour)** thay vì tăng mật độ nốt, và tách bạch vai trò giữa các bè:

- **Bè kính (`P1` — Alto Flute / English Horn / Clarinet)**: chỉ kể **đường viền hướng đi của giá (price contour)** theo từng ô nhịp — giá đang bò lên, trượt xuống, tạo đỉnh/đáy cục bộ hay quay lại kiểm định (retest) mốc cũ. Nhịp điệu luôn neo ở phách 1 của ô nhịp, tối đa 3 điểm neo nối `<slur>` trong một hơi thở ngân dài.
- **Biến động biên độ thực tế (realized volatility / range) và thanh khoản**: không nhồi vào bè kính mà do các lớp kia đảm nhiệm — độ lớn của sóng trong hơi quyết định chữ động lực học (`mp` hay `mf`), thanh khoản `mf`/`f` mở quãng 5 của Drone (`P4`) và tiếng nở French Horn (`P3`), còn biên độ dao động của cả phiên/chunk (`_section_rel_span`) quyết định ngân sách chuông Celesta (`P5` Shimmer qua `bell_budget`). Vì vậy, một phiên có râu nến (high–low range) rộng nhưng giá đóng các ô đi ngang sẽ kích hoạt Shimmer/Swell thay vì biến bè kính thành chuỗi nốt giật cục.

### Quy tắc tỉa và đặt hơi thở trên từng `FormSection` (`kind == "phrase"`)

Tỉa từng `FormSection` có `kind == "phrase"`:

1. **Ba ngưỡng tách biệt: Đoạn phẳng (`0` semitone), Uốn trong hơi (`STEP_INFLECT = 1`), và Tấn công lại sau nghỉ (`RETEST_RISE = MIN_RISE = 3`)**:
   - Không dùng chung một con số cho cả ba quyết định:
     - **Đoạn đứng yên hoàn toàn (`max(span) == min(span)`)**: Khi `pitches` trong cả section hoàn toàn không đổi (`0` semitone), đặt một lần tấn công ở phách 1 ô đầu của đoạn, cao độ đã gập vào `G3–C6`, dài tối đa `_hold(FLAT_HOLD)` (4 ô ở 4/4). Phần còn lại của đoạn là nghỉ trên P1, giường tiếp tục. Nếu cao độ đó trùng hơi vừa tan và đường giá từ hơi trước tới đây không đổi thì P1 nghỉ hết đoạn.
     - **Ngưỡng uốn lượn bên trong một hơi thở (`STEP_INFLECT = 1` semitone)**: Khi một hơi thở đã mở, mọi bước dịch chuyển từ `1` semitone trở lên (tương đương $\ge 1$ bậc trên thang đã lượng tử hóa `pitches`, bao gồm cả các bậc nửa cung `E–F`, `B–C`, `D–Eb`, `G–Ab`) đều được bắt làm điểm neo `<slur>` bên trong hơi đó, vì nối `<slur>` không tốn thêm lần lấy hơi mới.
     - **Ngưỡng tấn công lại cùng cao độ sau khoảng nghỉ (`RETEST_RISE = MIN_RISE = 3` semitone)**: Ngăn hiện tượng giá chỉ dao động ngang 1 bậc (`E–F–E`) nhưng sáo lại thổi lặp đi lặp lại cùng một cao độ sau mỗi khoảng nghỉ (xem chi tiết tại Mục 4).

2. **Tách biệt trần ngân (`GLASS_HOLD`), cửa sổ thở (`WINDOW_BARS`), và nghỉ đuôi 2 ô ở 4/4, 3/4**:
   - Không dùng `_hold(GLASS_HOLD)` làm độ dài cửa sổ thở. `rest_bars = 2` ở 4/4 và 3/4, và `rest_bars = 1` ở 6/4, cho mọi character. `groove_at(w_start).calm` không đọc cho sáo: renderer Ambient không dùng `calm`, `half`, hay `chamber` để tỉa P1, nở, shimmer, hoặc drone. Hợp âm của một ngày `calm` vẫn thưa hơn nhờ `bar_change_penalty = 0.80` ở tầng form. Một ô nghỉ 4/4 ở 60 BPM chỉ dài 4 giây. Giữa các hơi của đoạn 8 và 12 ô là nghỉ 2 ô (8 giây); đoạn 10 ô nghỉ `5..8` (3 ô, 12 giây). Cả hai để giường và halo thành khoảng không. Hơi cuối vẫn ngân tới `max_hold_bars` và chạm `section.end`. Cửa sổ từ 3 ô trở lên vẫn kêu ít nhất 2 ô, nên đoạn lỡ cỡ `L = 6` và `L = 7` không thành một nốt 4 giây rồi nghỉ dài hơn nốt đó.

     | Nhịp | `epb` | Trần ngân `_hold(GLASS_HOLD)` (`max_hold_bars`) | Bước cửa sổ chuẩn (`WINDOW_BARS`) | Nghỉ đuôi tối thiểu ở cửa sổ trước cuối `rest_bars` | Số ô kêu ở cửa sổ trước cuối (`w - rest_tail`) | Nghỉ dẫn đầu cửa sổ cuối (khi `N >= 2`: `lead_rest = max(0, w_last - max_hold_bars)`) |
     |---|---|---|---|---|---|---|
     | **4/4** | 8 | 32 móc (**4 ô**) | **4 ô** (32 móc) | **2 ô** | Khi `w = 4`: **2 ô** (nghỉ đuôi 2 ô). Khi `w = 5`: **3 ô** (nghỉ đuôi 2 ô). Khi `w = 3`: **2 ô** (nghỉ đuôi 1 ô, vì `rest_tail` không vượt `w - 2`). Khi `w = 2`: **1 ô** (nghỉ đuôi 1 ô, vì không còn sàn 2 ô) | Khi `w_last <= 4`: **0 ô**. Khi `w_last = 5`: **1 ô** (tổng nghỉ trước hơi cuối = **3 ô**: 2 đuôi + 1 đầu). Khi `w_last = 6` (`L = 11 -> [5, 6]`): **2 ô** (tổng nghỉ = **4 ô**: 2 đuôi cửa sổ 5 ô + 2 đầu) |
     | **3/4** | 6 | 30 móc (**5 ô**) | **4 ô** (24 móc) | **2 ô** | Khi `w = 4`: **2 ô** (nghỉ đuôi 2 ô). Khi `w = 5`: **3 ô** (nghỉ đuôi 2 ô). Khi `w = 3`: **2 ô** (nghỉ đuôi 1 ô, cùng sàn `w - 2`) | Khi `w_last <= 5`: **0 ô**. Khi `w_last = 6` (`L = 11 -> [5, 6]`): **1 ô** (tổng nghỉ = **3 ô**: 2 đuôi cửa sổ 5 ô + 1 đầu) |
     | **6/4** | 12 | 36 móc (**3 ô**) | **4 ô** (48 móc) | **1 ô** | Khi `w = 4`: **3 ô** (nghỉ đuôi `1 ô`). Khi `w = 5`: **3 ô** (nghỉ đuôi `2 ô`). Khi `w = 3`: **2 ô** (nghỉ đuôi `1 ô`). Khi `w = 2`: **1 ô** (nghỉ đuôi `1 ô`) | Khi `w_last = 4`: **1 ô** (cộng nghỉ đuôi `1 ô` thành **2 ô**). Khi `w_last = 5`: **2 ô** (cộng nghỉ đuôi `1 ô` của cửa sổ 4 ô ở `L = 13 -> [4, 4, 5]` thành **3 ô**, hoặc cộng nghỉ đuôi `2 ô` của cửa sổ 5 ô ở `L = 14 -> [4, 5, 5]` thành **4 ô**). Khi `w_last = 6` (`L = 11 -> [5, 6]`): **3 ô** |

   - **Công thức số cửa sổ `N` và cách chia section dài `L = section.end - section.start` ô (phủ mọi `L >= 1`, kể cả `L = 1..7`)**:
     - Dùng hàm chia đều cục bộ `_split_bars(L, N)` ngay trong `ambient.py` (`base, extra = divmod(L, N); return [base] * (N - extra) + [base + 1] * extra`) để tránh import vòng qua `span.py`.
     - **Trường hợp `L <= max_hold_bars`** (`L = 1..4` ở 4/4; `L = 1..5` ở 3/4; `L = 1..3` ở 6/4 — bao gồm các đoạn `phrase` 4 ô ở hai đầu bản `1W`):
       - Có **đúng `N = 1` hơi thở** mở ngay tại đầu section: `b_start = section.start`, `b_end = min(section.end, section.start + max_hold_bars) = section.end`, **không có nghỉ ở đầu hay ở đuôi section** (quy tắc lùi `b_start = max(w_start, section.end - max_hold_bars)` chỉ áp dụng cho cửa sổ cuối khi `N >= 2`, không bao giờ áp dụng khi `N == 1`).
     - **Trường hợp `L > max_hold_bars`** (`L >= 5` ở 4/4; `L >= 6` ở 3/4; `L >= 4` ở 6/4):
       - Số hơi thở là `N = max(2, L // WINDOW_BARS)`. Nhờ `max(2, ...)`, các section lỡ cỡ dài `5..7` ô ở 4/4 (hoặc `6..7` ô ở 3/4, `4..7` ô ở 6/4) luôn được chia thành **2 cửa sổ** (`L = 5 -> [2, 3]`, `L = 6 -> [3, 3]`, `L = 7 -> [3, 4]`, `L = 4` ở 6/4 `-> [2, 2]`), đảm bảo hơi đầu luôn mở ngay tại `section.start` và hơi cuối luôn chạm `section.end`.
       - **Với các cửa sổ trước cửa sổ cuối (`0 <= i < N - 1`, cửa sổ `[w_start, w_end)` dài `w = w_end - w_start` ô)**:
         - Mở hơi tại đầu cửa sổ: `b_start = w_start`.
         - Số ô nghỉ ở đuôi cửa sổ là `rest_tail = min(w - 2 if w >= 3 else w - 1, max(rest_bars, w - max_hold_bars))`, với `rest_bars = 2` ở 4/4 và 3/4, và `rest_bars = 1` ở 6/4. Sàn `w - 2` giữ mọi cửa sổ từ 3 ô trở lên kêu ít nhất 2 ô. Cửa sổ 2 ô vẫn kêu 1 ô. Không đọc `groove_at(w_start).calm` cho sáo.
         - Miền kêu của hơi `i` là `[w_start, w_end - rest_tail)`. Khi `w >= 3` miền này dài ít nhất 2 ô; khi `w = 2` còn 1 ô. Cả hai không vượt `max_hold_bars`.
       - **Với cửa sổ cuối cùng của section khi `N >= 2` (`i == N - 1`, cửa sổ `[w_start, section.end)` dài `w_last = section.end - w_start` ô)**:
         - **Không dành đuôi cửa sổ để nghỉ**: `b_end = section.end`, để ô cuối cùng của section (`section.end - 1`) luôn nằm trong hơi thở cuối.
         - Điểm mở hơi cuối là `b_start = max(w_start, section.end - max_hold_bars)`. Khi `w_last > max_hold_bars` (như cửa sổ 5 ô cuối của đoạn 10 ô ở 4/4, hoặc cửa sổ 4–5 ô cuối ở 6/4 nơi `max_hold_bars = 3`), phần dư đầu cửa sổ `lead_rest = b_start - w_start` cộng vào khoảng nghỉ ngay trước hơi cuối (tổng khoảng nghỉ trước hơi cuối là `rest_tail + lead_rest`). Ở 4/4 tổng đó là **2 ô** trên các đoạn 8 và 12 ô chia `[4, ..., 4]`, và **3 ô** (2 đuôi + 1 đầu) trên đoạn 10 ô chia `[5, 5]`. Ở 6/4 là `1 + 1 = 2` ô trên các đoạn 8, 12, 16 ô chia `[4, ..., 4]`, và `2 + 2 = 4` ô trước hơi cuối trên đoạn 14 ô chia `[4, 5, 5]`; mỗi hơi thở 6/4 trong cửa sổ 4–5 ô vẫn kêu đủ `3` ô = `36` móc cho tối đa 3 điểm neo.
     - **Bảng hành vi đầy đủ theo độ dài section `L` (ở nhịp 4/4, `max_hold_bars = 4`, `WINDOW_BARS = 4`)**:

       | Độ dài section `L` (4/4) | Số hơi `N` | Chia cửa sổ `_split_bars(L, N)` | Miền kêu và nghỉ (`rest_bars = 2`; `calm` cùng bảng này) |
       |---|---|---|---|---|
       | `L = 1..4` (vd: đầu/cuối `1W`) | `1` | `[L]` | Kêu trọn `0..L` (`L` ô), không nghỉ |
       | `L = 5` | `2` | `[2, 3]` | Hơi 1 `0..1` (1 ô), nghỉ `1..2` (1 ô), Hơi 2 `2..5` (3 ô) |
       | `L = 6` | `2` | `[3, 3]` | Hơi 1 `0..2` (2 ô), nghỉ `2..3` (1 ô), Hơi 2 `3..6` (3 ô) |
       | `L = 7` | `2` | `[3, 4]` | Hơi 1 `0..2` (2 ô), nghỉ `2..3` (1 ô), Hơi 2 `3..7` (4 ô) |
       | `L = 8` (Phrase 2 `12..20` của 1D) | `2` | `[4, 4]` | Hơi 1 `12..14` (2 ô), nghỉ `14..16` (2 ô), Hơi 2 `16..20` (4 ô) |
       | `L = 10` (Phrase 1 `2..12` của 1D) | `2` | `[5, 5]` | Hơi 1 `2..5` (3 ô), nghỉ `5..8` (3 ô: 2 đuôi + 1 đầu), Hơi 2 `8..12` (4 ô) |
       | `L = 12` (Phrase 3 `20..32` của 1D) | `3` | `[4, 4, 4]` | Hơi 1 `20..22` (2 ô), nghỉ `22..24` (2 ô), Hơi 2 `24..26` (2 ô), nghỉ `26..28` (2 ô), Hơi 3 `28..32` (4 ô) |

3. **Điểm neo đường viền (Contour Anchors) và sự uốn lượn bên trong một hơi thở `[b_start, b_end)`**:
   - Mọi điểm đổi nốt trong hơi thở đều đặt tại phách 1 của ô nhịp (`b * epb`) để giữ nhịp điệu khoan thai của Ambient.
   - Trong phạm vi `b_start .. b_end - 1` (dài `1–5` ô tùy nhịp và `L`), chọn tối đa **3 điểm neo** theo thứ tự thời gian. Hơi dài đúng 2 ô không có ô nội bộ (`b_start < b < b_end - 1` là rỗng), nên không có `anchor_mid`: cửa sổ 4 ô ở 4/4 nghỉ đuôi 2 ô thì hơi trước cuối chỉ còn nốt mở slur sang nốt đóng. Đáy giữa ô và Fixture 2 cần hơi dài ít nhất 3 ô, tức hơi đầu của đoạn 10 ô và hơi cuối 4 ô của mỗi đoạn.
     1. **Neo mở (`anchor_0`)**: tại ô đầu hơi `b_start`, lấy cao độ phách 1 đã lượng tử hóa `m_0 = _fold_glass(pitches[b_start * epb], prev_midi)`.
     2. **Neo cực trị nội bộ (`anchor_mid`, xét khi hơi có ô nội bộ `b_start < b < b_end - 1`)**:
        - Để không bỏ sót các đỉnh (`Phrase.apex`) hoặc đáy (`trough`) rơi vào giữa ô nội bộ `b`, cao độ ứng viên `cand(b)` của mỗi ô nội bộ `b` (`b_start < b < b_end - 1`) được chọn bằng **cực trị trên các móc đơn hợp lệ trong ô `b` đó** (`span_b = pitches[b * epb : (b + 1) * epb]`):
          - Khi hợp âm tại ô `b` thuộc nhóm trưởng (`chord_at[b].quality_group == "major"`, như `C`, `Cmaj7`, `Cmaj9`, `Fmaj9`), lọc bỏ **bậc 4 đúng trên gốc** (`avoid_pc = (chord_at[b].pitches[0] + 5) % 12`, ví dụ nốt `F` trên nền `Cmaj9`) khỏi các móc ứng viên của `span_b`, vì `Cmaj9` chỉ chứa `1–3–5–7–9` (`C–E–G–B–D`) nên bậc 4 ngân dài 1–3 ô ở phách 1 sẽ tạo quãng 9 thứ (bán âm) chỏi với bậc 3 trưởng `E` trong Halo mà không có giải quyết. (Phách 1 `pitches[b * epb]` đã qua `quantize_strong_beats` nên luôn là âm hợp âm và không bao giờ bị lọc mất).
          - Khi hợp âm tại ô `b` thuộc nhóm thứ hoặc dominant (`chord_at[b].quality_group in ("minor", "dominant")`, như `Am9`, `Dm9`, `G9`), mọi pitch class trong `span_b` đều được giữ nguyên (trên `Am9` và `Dm9`, `root + 5` là bậc 11 hòa quyện với quãng 3 thứ; trên `G9`, `root + 5` là `C` = bậc 11 còn `F` là bậc 7 của hợp âm):
          ```python
          avoid_pc = (
              (chord_at[b].pitches[0] + 5) % 12
              if chord_at is not None and b in chord_at and chord_at[b].quality_group == "major"
              else None
          )
          pool = [
              p for p in pitches[b * epb : (b + 1) * epb]
              if avoid_pc is None or p % 12 != avoid_pc
          ] or [pitches[b * epb]]
          cand(b) = max(
              (_fold_glass(p, m_0) for p in pool),
              key=lambda midi: abs(midi - m_0),
          )
          ```
        - Chọn ô nội bộ `b_mid` có `abs(cand(b) - m_0)` lớn nhất (nếu bằng nhau, ưu tiên ô sớm hơn), miễn là `abs(cand(b_mid) - m_0) >= STEP_INFLECT` (`1` semitone), và đặt `anchor_mid = (b_mid, cand(b_mid))` tại phách 1 của ô `b_mid`.
     3. **Neo đóng (`anchor_close`)**: khi `b_end - 1 > b_start`, xét ô cuối của hơi `b_close = b_end - 1` với cao độ phách 1 `m_close = _fold_glass(pitches[b_close * epb], prev_anchor_midi)`. Giữ `anchor_close` nếu nó lệch ít nhất `STEP_INFLECT` (`1` semitone) so với điểm neo đang giữ liền trước (`anchor_mid` nếu có, ngược lại là `anchor_0`). `anchor_0` và `anchor_close` luôn chỉ đọc phách 1 (`pitches[b * epb]`, vốn đã bám âm hợp âm qua `quantize_strong_beats`) để hai đầu hơi thở neo vững vào hợp âm phách 1 và khớp với điều kiện buộc `<tie>` qua biên `intro`/`outro` (biến động rơi vào phách yếu của ô mở hoặc ô đóng được để lại cho bước chuyển sang hơi kế tiếp hoặc thể hiện qua `bell_budget` / dynamics). Ở hơi thở cuối cùng của section, `b_close = section.end - 1` chính là phách 1 của ô cuối section, ngân trọn ô cuối tới `section.end`.
   - Từ danh sách `k` điểm neo (`1 <= k <= 3`) trong hơi thở `[(b_0, midi_0), ..., (b_{k-1}, midi_{k-1})]`:
     - Nếu `k == 1` (mọi điểm trong hơi cùng cao độ `midi_0`): hơi thở là **1 nốt ngân dài** suốt `(b_end - b_start) * epb` móc đơn (`slur = False`).
     - Nếu `k >= 2`: nốt thứ `j` (`0 <= j < k - 1`) ngân từ `b_j * epb` đến `b_{j+1} * epb` với `slur = True`; nốt cuối `k - 1` ngân từ `b_{k-1} * epb` đến `b_end * epb` với `slur = False`. Trong `_emit(segments)`, một chuỗi hơi nối `<slur>` mở `<slur type="start">` ở segment đầu (`slur_start = slur and not previous_slur`), giữ nguyên dưới vòm slur ở segment giữa (`slur_start = False, slur_stop = False`), và đóng `<slur type="stop">` ở segment cuối (`slur_stop = previous_slur and not slur`); chỉ nốt đầu hơi (`tenuto = not tie_in and not previous_slur`) mang `<tenuto/>`.

4. **Quy tắc buộc `<tie>` qua biên và lọc tấn công lại theo chuỗi hơi (`_omit_same_pitch_reattacks(segments, pitches=None)`)**:
   - **Nhóm segments thành chuỗi hơi (`chain`) trước khi lọc**:
     - Vì một hơi thở uốn lượn gồm `1..3` segment nối tiếp nhau bằng `slur` (hoặc `tie`), `_omit_same_pitch_reattacks(segments, pitches: list[int] | None = None)` **không xét rời rạc từng segment** (nếu chỉ bỏ segment đầu của một hơi uốn lượn thì segment thứ hai sẽ biến thành một lần tấn công mồ côi mang `<tenuto/>`).
     - Hàm gom các segment chạm nhau và nối bằng `slur`/`tie` (`seg_end == next_start and (seg_slur or seg_tie_out or next_tie_in)`) thành từng **chuỗi hơi `chain: list[Segment]`**. Mỗi `chain` có chỉ số móc đơn đầu `chain_start = chain[0][0]`, chỉ số móc đơn cuối `chain_end = chain[-1][0] + chain[-1][1]`, cao độ mở đầu `anchor_0 = chain[0][2]`, và **cao độ cuối thực tế của chuỗi hơi `anchor_last = chain[-1][2]`** (phân biệt với `anchor_close` ở Mục 3: khi `k == 1` thì `anchor_last == anchor_0`; khi `k == 2` mà chỉ có `anchor_0 -> anchor_mid` do ô cuối trùng cao độ với `anchor_mid` thì `anchor_last == anchor_mid != anchor_0`; khi có `anchor_close` thì `anchor_last == anchor_close`).
   - **Khi `chain` chạm chuỗi trước (`chain_start == prev_end`, với `prev_end = kept[-1][0] + kept[-1][1]` và `prev_midi = kept[-1][2]`)**:
     - Trần `_hold(GLASS_HOLD)` (32 móc = 4 ô ở 4/4, 30 móc = 5 ô ở 3/4, 36 móc = 3 ô ở 6/4) là **trần của một cao độ đứng yên liên tục giữa các đoạn `phrase` chưa liên kết (`not linked`)**.
     - Các đoạn đã được liên kết chủ động bằng cờ `tie_out / tie_in` hoặc `slur` (`linked = touches and (kept[-1][3] or kept[-1][5] or chain[0][4])`) **được giữ nguyên như đã viết và nằm ngoài trần `_hold(GLASS_HOLD)`**:
       - Ở bản 1D (`DAILY_AMBIENT_SPEC`): `warm-up` 2 ô buộc `tie_out=True` sang nốt mở đầu của `phrase` 1; khi nốt mở đầu đó giữ nguyên cao độ chủ âm suốt 4 ô (điển hình là phiên phẳng), chuỗi buộc liên tục dài `2 + 4 = 6` ô (24 phách đen; nếu hơi đầu thân uốn `<slur>` sang cao độ mới sau `1..3` ô thì phần buộc chủ âm dài `2 + (1..3)` ô rồi trượt `<slur>` sang điểm neo kế tiếp).
       - Ở bản 1W (`week_spec`) hoặc các bản không gắn `warmup` riêng: section `intro` (4 ô ở 1W) gắn `tie_out=True` vào nốt mở đầu của đoạn `phrase` 4 ô kế tiếp (`tie_in=True`); khi nốt mở đầu đó giữ nguyên cao độ suốt 4 ô (như phiên đầu phẳng), cả 8 ô đầu (`0..8`) là **một lần tấn công duy nhất** kéo dài 8 ô.
     - Khi hai miền cùng cao độ (`anchor_0 == prev_midi`) giữa hai hơi `phrase` chạm nhau tại vạch nhịp mà chưa có `tie_out / tie_in` (`not linked`): segment đầu `chain[0]` được gộp vào `kept[-1]` tối đa phần còn thiếu `take = min(chain[0][1], max(0, _hold(GLASS_HOLD) - _breath_eighths(kept, prev_midi, chain_start)))`. Nếu `len(chain) > 1` (hơi mới mở ở `prev_midi` rồi `<slur>` sang `chain[1:]`): khi `take == chain[0][1]` thì bật `slur=True` trên `kept[-1]` và nối tiếp `chain[1:]` — lúc này **hai hơi chạm nhau hợp nhất thành một chuỗi hơi (`chain`) duy nhất**; khi `take < chain[0][1]` (đã chạm trần 4 ô trước `chain[1]`) thì nhả `kept[-1]` (`slur=False`) sau `take` móc rồi mở hơi mới từ `chain[1:]` tại `chain[1][0]`.
   - **Khi `chain` mở ra sau một khoảng nghỉ (`chain_start > prev_end`) ở cùng cao độ `anchor_0 == prev_midi` với nốt cuối của hơi trước**:
     - Xóa cờ `slur` và `tie_out` trên `kept[-1]`, xóa `tie_in` trên `chain[0]`.
     - Tính `excursion` là độ lệch lớn nhất của đường giá `pitches` (đã gập gần `prev_midi`) so với `prev_midi` trên đoạn chỉ số móc đơn `prev_end .. chain_end` (khi gọi trực tiếp `_omit_same_pitch_reattacks(segments)` với `pitches=None` trong unit test độc lập thì tính `excursion = max(abs(seg[2] - prev_midi) for seg in chain)`):
       ```python
       excursion = max(
           (abs(_fold_glass(p, prev_midi) - prev_midi) for p in pitches[prev_end : min(chain_end, len(pitches))]),
           default=0,
       )
       ```
     - Chuỗi hơi `chain` bắt đầu tại `prev_midi` sau khoảng nghỉ **chỉ được giữ lại (giữ nguyên toàn bộ `chain`) khi thỏa ít nhất một trong hai điều kiện**:
       1. **Có chuyển dịch ròng ở cuối hơi sang mức giá mới (`anchor_last != prev_midi`)**: hơi thở mới rời bỏ `prev_midi` để kết thúc ở một cao độ khác (kể cả khi chỉ có 2 neo `anchor_0 -> anchor_mid` với `anchor_last == anchor_mid != prev_midi`).
       2. **Có chuyến đi giá thực sự (`excursion >= MIN_RISE`, tức $\ge 3$ semitone đo trên khoảng cách sau khi gập `_fold_glass(p, prev_midi)`)**: giữa hai hơi thở (hoặc ngay trong hơi mới, ví dụ `E -> G -> E`), cao độ đã gập đi xa khỏi `prev_midi` ít nhất `MIN_RISE = 3` semitone rồi mới quay về kiểm định (retest) đúng mốc `prev_midi`. Lưu ý khoảng cách sau khi gập `_fold_glass` mới là thước đo: `_fold_glass` giữ khoảng cách $\le 12$ semitone nên bước thô `3..12` semitone giữ nguyên `3..12` ($\ge 3$), bước thô `13` hoặc `14` semitone bị gập quãng 8 thành `1` hoặc `2` semitone ($< 3$, không đủ ngưỡng retest), còn bước thô `15` semitone gập thành `3` semitone ($\ge 3$, đủ ngưỡng).
     - Ngược lại — khi `anchor_last == prev_midi` **và** `excursion < MIN_RISE` (bao gồm cả trường hợp `k == 1` đứng im `0` semitone lẫn trường hợp hơi uốn nhẹ 1–2 semitone sau khi gập kiểu `E -> F -> E` mở ở `E` và đóng ở `E`) — **toàn bộ chuỗi hơi `chain` đó bị lược bỏ cùng nhau**, để P1 giữ im lặng và không bao giờ sinh nốt giữa hơi mồ côi.

5. **Động lực học của hơi ngân trong `phrase` và hai cơ chế khung (`_attach_daily_frames` vs. `movement_frame._ambient`)**:
   - **Bên trong thân `phrase` (`_arc_breaths`, chạy sau `_omit_same_pitch_reattacks`)**: Mỗi chuỗi nốt nối liền nhau bằng `<tie>` hoặc `<slur>` (sau khi đã gộp các hơi chạm nhau cùng cao độ ở Mục 4) tạo thành **một hơi ngân lắng chậm duy nhất** — cả số lượng hơi thở lẫn chữ động lực học đều tính **sau khi gộp**. Mở đầu ngay ở phách 1 của nốt đầu hơi bằng chữ `mf` (khi biên độ `max(arc_midis) - min(arc_midis) >= MIN_RISE` hoặc bước chuyển từ cuối hơi trước `abs(arc_midis[0] - prev_arc_midi) >= MIN_RISE`, với `MIN_RISE = 3` semitone) hoặc `mp` (khi cả biên độ trong hơi và bước chuyển từ hơi trước đều `< MIN_RISE`), kèm **một `<diminuendo>` duy nhất** từ đầu hơi đến hết nốt cuối của hơi đó.
   - **Khung ngày 1D (`_attach_daily_frames` & `_daily_frame_breaths` trên `DAILY_AMBIENT_SPEC`, khi `frame=True`)**:
     - **Warm-up 1D** (ô `0..2`, `kind == "intro"`): đạp chủ âm `_tonic_glass`, mở bằng chữ `p` tại phách 1 ô 0 và chạy `<crescendo>` tới ô 2. Khi nốt mở đầu thân `phrase` trùng cao độ chủ âm và chạm ô 2, hai bên buộc `<tie>` qua biên (ngoài trần 4 ô của thân; khi nốt mở đầu thân ngân đủ 4 ô như ở phiên phẳng thì tổng chuỗi buộc là 6 ô = 24 phách đen).
     - **Cool-down 1D** (ô `32..34`, `kind == "outro"`, dài 2 ô): đạp chủ âm `_tonic_glass`, **không** đọc giá đóng cửa và **không** áp luật re-attack theo biến động giá. Nếu nốt cuối thân cùng cao độ với chủ âm và chạm ô 32 (`touches`), hơi đang kêu được buộc kéo dài tối đa đủ `COOLDOWN_HOLD = 40` móc (5 ô tính từ đầu hơi đó) rồi nghỉ; nếu cùng cao độ nhưng đã có khoảng nghỉ trước ô 32 (`not touches`), cool-down **luôn nghỉ**. Nếu nốt cuối thân **khác cao độ** với chủ âm, cool-down mở chủ âm mới ở `mp` tại ô 32. Khi có tiếng trên cool-down, hơi lắng dần bằng `<diminuendo>` về `ppp` (`COOLDOWN_MARKING`) ở ô 33.
   - **Khung chương dài 1M–1Y (`movement_frame.py:_ambient`, trên `spec` có `warmup` và `cooldown`)**:
     - **Warm-up chương dài** (`warm_start .. body`): đạp chủ âm mở chương `_fold(opening.pitches[0] % 12, ...)`, mở bằng chữ `p` + `<crescendo>` tới `body`, và buộc `<tie>` vào đầu `body` nếu cùng cao độ và chạm biên (`_joins(lead_body, body, glass)`).
     - **Cool-down chương dài** (`cool .. end`): kiểm tra nốt cuối cùng của thân `sung = _latest(lead_body)`. Nếu nốt đó chạm đúng vạch `cool` (`_touching(lead_body, cool - 1, sung, beats)`), kéo dài (`_pedal(cool, end, sung, tie_in=True)`) chính cao độ `sung` đó suốt toàn bộ `cool .. end` (không áp trần `COOLDOWN_HOLD = 40` móc) kèm `<diminuendo>` về `ppp` ở `end - 1`. Nếu không có nốt nào chạm vạch `cool` (`touch is None`), bè kính **nghỉ hoàn toàn** suốt `cool .. end` (không có nhánh mở chủ âm mới khi khác cao độ như bản ngày).
   - **Bản không gắn frame riêng** (như `1W`, hoặc khi truyền tường minh `form=DAILY_SPEC` 30 ô; lưu ý `render(..., variant="ambient")` khi `form=None` luôn chọn `DAILY_AMBIENT_SPEC` bất kể tham số `framed`): `intro` giữ cao độ mở của `phrase` đầu và gắn `tie_out=True` khi chạm biên; `outro` giữ cao độ close cuối đã lượng tử hóa (khác cao độ hơi trước thì ngân hết `outro`, cùng cao độ và chạm biên thì buộc cho đủ `_hold(GLASS_HOLD)`, cùng cao độ mà sau khoảng nghỉ thì nghỉ). Chương II của 1M không có `outro` giá (chỉ có `cooldown` 3 ô nhịp 6/4 khi gắn `attach_frame`). Hai ô cuối của `outro` không có shimmer.

## Nở và shimmer

P3 để trống, trừ các cửa sổ thanh khoản có băng `mf` hoặc `f` mà ô thứ hai của cửa sổ thuộc section `phrase`. Hai lần nở cách nhau ít nhất 4 ô (`SWELL_GAP_BARS = 4`). Đặt tại phách 1 của ô thứ hai đó một hợp âm 3 âm mở trên kèn French Horn (`Horn in F`, `Muse Brass`) ở vùng ấm `C3–A4` (`48..69`), viết qua `written()` thành hai nửa buộc nhau với tổng độ dài tối đa 2 ô nhịp (`SWELL_HOLD = 16` móc đơn, hoặc 1 ô = 8 móc đơn khi chạm biên cuối section `phrase`):

- Nốt đỉnh (`top`) là âm hợp âm cao nhất trong vùng `C4–A4` (`60..69`).
- Nốt đáy (`bottom`) là âm hợp âm trong vùng khoảng một quãng 8 dưới `top` (`max(45, top - 16) .. top - 8`) không tạo quãng 2 với `top`.
- Nốt giữa (`middle`) là âm hợp âm (`chord.pitch_classes`) nằm giữa `bottom` và `top` với khoảng cách ít nhất một quãng 3 thứ so với cả hai đầu.
- Nửa đầu của tiếng nở mang `velocity = 49` (`p`), nửa sau mang `velocity = 64` (`mp`, khi băng là `mf`) hoặc `80` (`mf`, khi băng là `f`), khớp với bảng `DYNAMICS`. `_ambient_swell_part` in cung sóng `p < mp >` hoặc `p < mf >` trên hai nửa đó (kể cả khi tiếng nở ở cuối phrase chỉ dài 1 ô và tách làm hai nốt trắng buộc nhau), để cả direction lẫn note velocity đều xuất phát từ `p` rồi dâng lên đỉnh trước khi tan dần. Các cửa sổ `p`, `mp`, intro và outro không nở.

Shimmer chọn sau khi nhìn hết cửa sổ ngân sách. Cửa sổ là `spec.chunk_bounds()` (sau khi `_body_window` cắt bỏ các section có `kind == "warmup"` và `"cooldown"`):

- 1D (`DAILY_AMBIENT_SPEC`, `chunks` rỗng, khung ngày mang `kind == "intro"` / `"outro"`): cả 34 ô (`272` móc đơn). (Nếu truyền `form=DAILY_SPEC` 30 ô thì là `240` móc đơn).
- 1W: từng phiên 32 ô (`256` móc đơn).
- 1M trở đi: từng chunk của thân chương (đã cắt `warmup` và `cooldown`).

Không tính theo `spec.sections`. Section 8 ô có 64 móc đơn, `round(0.05 × 64) = 3`, nhỏ hơn một nốt tròn (8 móc đơn). `week_spec` còn chia mỗi phiên thành bốn section 8 ô, nên vòng `bell_caps` hiện tại cũng ra 3 móc đơn.

Ngân sách thô của một cửa sổ là `round(0.05 × số móc đơn)`. Nhân với `bell_budget(span_cửa_sổ) / BELL_MAX_EIGHTHS`, bằng 0 khi span đó không quá 0,5%. Làm tròn. Một shimmer tốn 8 móc đơn (ở 4/4; hoặc 6 móc ở 3/4 và 6/4). Cửa sổ còn dưới độ dài một shimmer thì không có shimmer. 1D (`DAILY_AMBIENT_SPEC`, 272 móc) đủ biến động được `round(0.05 × 272) = 14` móc đơn (hoặc `12` móc trên `DAILY_SPEC` 240 móc), tức một nốt tròn (8 móc). Một phiên 1W đủ biến động được 13 móc đơn, cũng một nốt tròn.

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

1. `backend/app/sonify/ambient.py`: `render_ambient_score(..., windows, sections, bars, groups)`, `AMBIENT_BPM = 60`, `STEP_INFLECT = 1`, `WINDOW_BARS = 4`. Đặt helper cục bộ `_split_bars(L, N)` ngay trong `ambient.py` (không import từ `span.py`). Với mỗi `FormSection` (`kind == "phrase"`, dài `L` ô): khi `L <= max_hold_bars` (tức `N = 1`) thì hơi duy nhất luôn mở tại `b_start = section.start` và phủ tới `min(section.end, section.start + max_hold_bars)`; khi `L > max_hold_bars` thì `N = max(2, L // WINDOW_BARS)` cửa sổ qua `_split_bars(L, N)`, các cửa sổ trước cửa sổ cuối nghỉ đuôi `rest_tail = min(w - 2 if w >= 3 else w - 1, max(rest_bars, w - max_hold_bars))` (với `rest_bars = 2` ở 4/4 và 3/4, `rest_bars = 1` ở 6/4; `groove_at(w_start).calm` không đổi nghỉ của sáo), cửa sổ cuối (`i == N - 1` khi `N >= 2`) không nghỉ đuôi để hơi cuối chạm đúng `section.end` (`b_start = max(w_start, section.end - max_hold_bars)`, `b_end = section.end`). Trong mỗi hơi `[b_start, b_end)`, chọn tối đa 3 điểm neo đặt tại phách 1 (`anchor_0` tại `b_start`, `anchor_mid` tại ô nội bộ có cực trị móc đơn `abs(cand(b) - m_0) >= STEP_INFLECT` lớn nhất sau khi đã lọc bỏ bậc 4 đúng `avoid_pc = (chord.pitches[0] + 5) % 12` trên hợp âm `chord.quality_group == "major"`, và `anchor_close` tại `b_end - 1` nếu lệch $\ge 1$ semitone so với neo liền trước) nối `<slur>` dưới một `<diminuendo>` duy nhất (`mp` hoặc `mf` trong thân `phrase`). `_omit_same_pitch_reattacks(segments, pitches=None)` gom các segment nối bằng `slur`/`tie` thành chuỗi hơi `chain` rồi mới lọc theo chuỗi: sau khoảng nghỉ, chỉ giữ lại `chain` mở ở `prev_midi` khi `anchor_last != prev_midi` (cao độ cuối thực tế của `chain`) hoặc `excursion >= MIN_RISE` (`3` semitone trên `pitches[prev_end:chain_end]`), ngược lại bỏ nguyên cả `chain`. Trong `_emit(segments)`, đặt `slur_start = slur and not previous_slur`, `slur_stop = previous_slur and not slur`, `tenuto = not tie_in and not previous_slur`. Giường theo từng ô sau `jazz_chord()`, nở French Horn theo cửa sổ `mf`/`f`, shimmer theo `chunk_bounds` và `bell_budget` của từng chunk.
2. Nhánh `variant == "ambient"` trong `_compose`, sau khi slot, phrase và pitch đã có. Truyền `windows`, `spec.sections`, `bars` và `groups`. 1D dùng `DAILY_AMBIENT_SPEC` (34 ô: warm-up 2 ô, ba đoạn `phrase` 10, 8, 12 ô, cool-down 2 ô) và `AMBIENT_BPM`. Có `FormSpec` thì BPM là `spec.bpm`. `Score.slots` là slot đã nâng. `Score.dynamics` là chữ giường trần `mp`.
3. `Variant` trong `model.py` và schema recap / span thêm `"ambient"`. `Score.variant` nhận giá trị đó.
4. `_PARTS_BY_VARIANT` thêm năm program ở bảng trên. `_bass_part` gắn `chord` khi hai nốt cùng phách. P2 Ambient dùng khóa Sol và mở đầu ở `p`. P3 Ambient là một khuông (`Horn in F`), mở đầu ở `p`, vuốt sóng `p < mp >` hoặc `p < mf >` qua hai nửa buộc nhau (1–2 ô), và không in `<harmony>`.
5. `_STORED_NAME` và `_prune_spans` dùng `VARIANTS`.
6. Chip «Ambient» trong `SessionRecap` và `SpanRecap`. `RecapVariant` ở client thêm `'ambient'`.

## Kiểm tra

- **Định nghĩa thuật toán `_breaths(notes)` và `_onsets(notes)` trên `P1`**:
  - `_onsets(notes)` (`note.midi is not None and not note.tie_stop`): mọi nốt phát âm mới hoặc đổi cao độ dưới `<slur>` (dùng để kiểm tra các điểm neo `anchor_0`, `anchor_mid`, `anchor_close` bên trong hơi).
  - `_breaths(notes) -> list[list[NoteEvent]]` (**chuỗi hơi sau khi đã gộp**): duyệt các `note` đang kêu (`note.midi is not None`) theo thứ tự `(note.bar, note.beat)` cùng một cờ trạng thái `in_slur = False`:
    - Nếu `current` đang mở và (`note.tie_stop` hoặc `in_slur` là `True`) thì nối `note` vào `current`; ngược lại đóng `current` và mở `current = [note]` mới.
    - Cập nhật trạng thái vòm slur trên `note` vừa nhận: nếu `note.slur_start` thì `in_slur = True`; nếu `note.slur_stop` thì `in_slur = False`.
  - **Gán hơi thở cho một section `[start_bar, end_bar)`**: một chuỗi `breath` trong `_breaths(score.lead)` thuộc về section `[start_bar, end_bar)` khi phần kêu của nó giao với section (`any(start_bar <= n.bar < end_bar for n in breath)`) và chuỗi đó không phải là đuôi của một hơi mở từ section `phrase` trước tràn sang (nhờ đó chuỗi `warm-up` ở ô `0..2` buộc `<tie>` sang đầu `phrase` 1 ở ô `2` vẫn được tính là hơi thở đầu tiên của `phrase` 1; còn nếu hai hơi ở biên hai section `phrase` cùng cao độ và bị `_omit_same_pitch_reattacks` gộp thành một chuỗi duy nhất thì tính là một hơi hợp nhất).
- **Phiên 1D đứng yên hoàn toàn (`max(span) == min(span)`, `test_flat_day_states_the_flute_pitch_once`)**: chỉ mở một hơi phẳng ở đầu thân (`2..6`, 4 ô) rồi nghỉ hết các đoạn phẳng tiếp theo; warm-up (`0..2`, 2 ô, mở `p` + `<crescendo>`) buộc `<tie>` sang 4 ô đầu thân thành một chuỗi 6 ô (24 phách đen), cool-down (`32..34`, 2 ô) nghỉ trên P1 và giường lắng về `ppp`.
- **Fixture 1 — Bậc thang 1 semitone (`STEP_INFLECT = 1`) và cửa sổ không đổi cao độ (`k == 1`)**: trong một section có chuyển động, cửa sổ thở nào mà các ô bên trong và ô cuối cùng cao độ với `anchor_0` (`k == 1`) vẫn giữ **1 nốt ngân dài**; cửa sổ thở nào có bước chuyển $\ge 1$ semitone (kể cả 1 bậc nửa cung `E4 -> F4` hoặc `B4 -> C5`, tức `k in (2, 3)`) tạo ra một hơi thở 2–3 nốt nối `<slur>` tại phách 1 (chỉ nốt đầu hơi có `<tenuto/>`), kèm một `<diminuendo>` duy nhất (`mf` khi biên độ hơi hoặc bước chuyển từ hơi trước $\ge 3$ semitone, ngược lại `mp`).
- **Fixture 2 — Đáy cục bộ (`trough` / dip), phép dời cực trị phách yếu về phách 1, và lọc avoid note bậc 4 trên hợp âm trưởng**:
  - Khi trong cửa sổ 4 ô, cực trị (trough hoặc âm màu hợp lệ) chỉ xuất hiện ở phách yếu (phách 2–4) của ô nội bộ `b_mid` trong khi phách 1 của `b_mid` vẫn bằng `m_0`, `cand(b_mid)` quét `pitches[b_mid * epb : (b_mid + 1) * epb]` để bắt cực trị đó và dời về phách 1 của `b_mid`, rồi hồi lên ở phách 1 ô cuối $\rightarrow$ tạo 1 hơi thở (`1` breath chain) gồm 3 `_onsets` (`anchor_0 -> trough -> anchor_close`) đặt ở phách 1 của từng ô dưới một vòm `<slur>` duy nhất (`slur_start=True` ở nốt đầu, `slur_start=False, slur_stop=False, tenuto=False` ở nốt giữa, `slur_stop=True` ở nốt cuối).
  - Trên ô nội bộ có hợp âm trưởng (`chord.quality_group == "major"`, như `Cmaj9`), móc yếu mang bậc 4 đúng (`F` trên `Cmaj9`) bị loại khỏi `pool` của `cand(b_mid)` để không ngân dài avoid note chỏi với bậc 3 trưởng `E` của Halo; trong khi trên hợp âm thứ (`Am9`, `Dm9`) hoặc dominant (`G9`) thì bậc đó vẫn được giữ.
- **Fixture 3 — Số hơi thở `2 / 2 / 3` (khi phách 1 qua vạch section đổi cao độ) và hơi cuối luôn phủ qua ô cuối `11`, `19`, `31` trên `DAILY_AMBIENT_SPEC` (cập nhật `test_a_rising_phrase_section_keeps_at_most_four_glass_attacks`)**: trên phiên có xu hướng tăng liên tục suốt 30 ô thân (`2..12`, `12..20`, `20..32`, ví dụ `closes = [100.0 + index * 4.0 for index in range(30)]` nơi cao độ phách 1 tại ô `12` khác ô `11` và tại ô `20` khác ô `19` nên không bị gộp qua biên section), đếm theo đơn vị hơi thở (`_breaths`) thì ba đoạn `phrase` có lần lượt `2`, `2` và `3` hơi thở (nếu một phiên khác có phách 1 hai bên biên `11..12` hoặc `19..20` trùng cao độ thì `_omit_same_pitch_reattacks` hợp nhất hai hơi chạm nhau đó theo Mục 4); các hơi thở cuối của từng đoạn luôn kêu chạm `section.end` (phủ trọn qua các ô `11`, `19` và `31`, và mở `anchor_close` riêng tại phách 1 của ô `section.end - 1` khi cao độ phách 1 đó lệch $\ge 1$ semitone so với neo liền trước; nếu trùng cao độ với neo liền trước thì neo liền trước ngân xuyên qua ô `section.end - 1` tới `section.end`), và khoảng nghỉ chỉ nằm giữa các hơi thở.
- **Fixture 4 — Lọc theo chuỗi hơi (`chain`), phân biệt dao động ngang 1 bậc (`sideways E–F–E`) với chuyển dịch ròng (`anchor_last != prev_midi`) và retest thật (`excursion >= MIN_RISE` sau `_fold_glass`, cập nhật `test_a_faded_pitch_is_not_rebreathed_until_the_line_moves`)**:
  - Dao động ngang 1–2 semitone lặp lại sau khoảng nghỉ (ví dụ chuỗi hơi `E -> F -> E` nơi `anchor_0 == E == prev_midi`, `anchor_last == E == prev_midi` và `excursion < MIN_RISE`, bao gồm cả bước thô `13..14` semitone sau khi gập còn `1..2` semitone): `_omit_same_pitch_reattacks` **bỏ nguyên cả chuỗi hơi `E -> F -> E`** (không bao giờ chỉ bỏ `E` đầu rồi để lại `F` thành attack mồ côi có `<tenuto/>`).
  - Khi chuỗi hơi sau khoảng nghỉ mở ở `E` nhưng có `anchor_last != E` (kể cả hơi 2 neo `E -> F` nơi neo cuối chính là `anchor_mid = F`, hoặc hơi 3 neo `E -> G -> F`), hoặc khi `anchor_last == E` nhưng khoảng cách đã gập qua `_fold_glass(p, prev_midi)` đạt `excursion >= MIN_RISE = 3` semitone (chênh `3..12` semitone sau khi gập, ví dụ bước thô `3..12` hoặc `15` semitone), toàn bộ chuỗi hơi mới được giữ lại.
- **Fixture 5 — Nghỉ đuôi 2 ô là mức thường của 4/4 (`rest_bars = 2` trên `DAILY_AMBIENT_SPEC`)**: Phrase 1 (`2..12`, chia `[5, 5]`) có Hơi 1 kêu 3 ô (`2..5`), nghỉ 3 ô (`5..8`, gồm 2 ô đuôi cửa sổ đầu + 1 ô đầu cửa sổ cuối), Hơi 2 kêu 4 ô (`8..12`); Phrase 2 (`12..20`, chia `[4, 4]`) có Hơi 1 kêu 2 ô (`12..14`, không có `anchor_mid`), nghỉ 2 ô (`14..16`), Hơi 2 kêu 4 ô (`16..20`); Phrase 3 (`20..32`, chia `[4, 4, 4]`) có hai hơi đầu mỗi hơi 2 ô (`20..22`, `24..26`) và hơi cuối 4 ô (`28..32`). Đường sáo của `character="calm"` trùng đường sáo của một ngày thường, kể cả các ô nghỉ `{5, 6, 7}`, `{14, 15}`, `{22, 23}` và `{26, 27}` (`test_a_calm_day_keeps_the_same_flute_rests`).
- **Fixture 6 — Nhịp `6/4` (`METER_64`) và các section ngắn theo từng nhịp**:
  - Trên `FormSpec` nhịp `6/4` (`max_hold_bars = 3`) với các section dài từ 8 ô trở lên (các cửa sổ dài `w in (4, 5)` ô, như các đoạn 8, 12, 14, 16, 24, 26 ô): mỗi hơi thở trong cửa sổ `4–5` ô kêu `3` ô (`36` móc, đủ 3 phách 1 cho tối đa 3 điểm neo). Giữa hai cửa sổ 4 ô trước cửa sổ cuối là `1` ô nghỉ đuôi (`12` móc); trước hơi thở cuối cùng của section, khoảng nghỉ cộng thêm `lead_rest = w_last - 3`, nên tổng nghỉ trước hơi cuối là **2 ô** (`24` móc) trên các đoạn 8, 12, 16 ô (chia `[4, ..., 4]`) và **4 ô** (`48` móc: 2 ô đuôi cửa sổ 5 ô trước + 2 ô đầu cửa sổ 5 ô cuối) trên đoạn 14 ô (chia `[4, 5, 5]`). (Với cửa sổ `w = 3` thì hơi trước cuối kêu `2` ô + nghỉ `1` ô; với `L = 4` ở 6/4 chia `[2, 2]` thì Hơi 1 kêu `1` ô + nghỉ `1` ô và Hơi 2 kêu `2` ô; với `L <= 3` ở 6/4 thì `N == 1` hơi kêu trọn `L` ô).
  - Trên section ngắn có `L <= max_hold_bars` (`L = 1..4` ở 4/4 như đoạn `phrase` 4 ô ở đầu/cuối `1W`, giữ nguyên `test_week_uses_form_tempo_and_chunk_spans_for_shimmer`; `L = 1..5` ở 3/4; `L = 1..3` ở 6/4) thì `N == 1` hơi phủ trọn `section.start .. section.end`; còn khi `max_hold_bars < L < 2 * WINDOW_BARS` (`L = 5..7` ở 4/4; `L = 6..7` ở 3/4; `L = 4..7` ở 6/4) thì chia `N = 2` cửa sổ qua `_split_bars(L, 2)`: hơi đầu luôn mở ngay tại `section.start` (không bao giờ có nghỉ đầu section) và hơi cuối luôn chạm `section.end`.
- **Khung `warm-up` / `cool-down` (1D vs. 1M–1Y) và các quy tắc hiện hữu**:
  - Hai miền cùng cao độ giữa hai hơi `phrase` chạm nhau mà chưa có `tie_out / tie_in` (`not linked`) buộc `<tie>` tối đa đủ trần `_hold(GLASS_HOLD)` (4 ô ở 4/4), rồi nhả. Các đoạn đã liên kết `linked` giữ nguyên ngoài trần 4 ô: khi nốt mở đầu thân giữ nguyên cao độ suốt 4 ô (như ở phiên phẳng), `warm-up` 2 ô của 1D buộc vào 4 ô đầu thân thành 6 ô = 24 phách, và `intro` 4 ô của 1W buộc `tie_out=True` vào `phrase` 4 ô kế tiếp thành 8 ô (1 lần tấn công duy nhất trong 8 ô đầu).
  - Cool-down 1D (`_attach_daily_frames`, ô `32..34`) đạp chủ âm: chạm cùng cao độ thì kéo dài tối đa đủ `COOLDOWN_HOLD = 40` móc (5 ô) rồi nghỉ; sau khoảng nghỉ mà trùng chủ âm thì luôn nghỉ; khác cao độ chủ âm thì mở chủ âm mới ở `mp` (`test_cool_down_extends_a_touching_breath_to_five_bars_then_rests`). Cool-down chương dài (`movement_frame._ambient`, 1M–1Y) chỉ nối nốt cuối thân đang chạm biên `cool` xuyên hết `cool .. end` (không trần 40 móc) và nghỉ hoàn toàn nếu không chạm.
  - Mọi chữ dynamic và `<wedge>` của hơi thở trên P1 đều đứng ngay phách 1 của nốt đầu hơi (`test_breathing_directions_land_before_a_sounding_note_and_harp_swell_is_open`).
  - Chương II của 1M không có nốt kính `outro` giá (`test_month_movement_without_an_outro_does_not_invent_one`).
  - `C` rồi `Cmaj7` sau `jazz_chord()` là một lần tấn công `Cmaj9`. Drone không đánh lại khi hợp âm jazz không đổi. Quãng 5 chỉ có trên ô `mf` và `f`, và trong MusicXML là `<chord>`, không làm ô 4/4 thành 8 phách.
  - Cửa sổ `mf`/`f` mà ô thứ hai thuộc `phrase` (cách lần nở trước ít nhất 4 ô) có một hợp âm French Horn 3 âm mở chia hai nửa buộc nhau (dài 1–2 ô) với cung sóng `p < mp >` hoặc `p < mf >`. P3 một khuông, không có `<harmony>`.
  - Shimmer của 1D đủ biến động dài 8 móc đơn và không vượt `round(0.05 × 272) = 14` móc đơn trên `DAILY_AMBIENT_SPEC` (hoặc `round(0.05 × 240) = 12` trên `DAILY_SPEC`). Span của cửa sổ không quá 0,5% thì cửa sổ đó không có shimmer. Hai shimmer cách nhau ít nhất 4 ô.
  - Một tuần đủ 5 phiên vẫn 160 ô, BPM của form, ngân sách shimmer tính theo từng chunk 32 ô. Phiên phẳng trong tuần có sóng không có shimmer. Phiên đủ biến động vẫn có.
  - Score Tối giản của cùng một chuỗi nến không đổi. File span Ambient còn sau `prune()`.
