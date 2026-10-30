# Kế hoạch: câu Torroba, vòng quay đầu, extra cả ô

> **Trạng thái**: đã hát. Dialect, bốn pattern, và extra cả ô của `danza` / `fandanguillo` đã hát trên `main`.
> **Khung đang chạy**: [`docs/sonify-guitar-torroba-plan.md`](./sonify-guitar-torroba-plan.md), mục 4, 5 và 6. Vi mô trong ô: [`docs/sonify-guitar-micro-contour-plan.md`](./sonify-guitar-micro-contour-plan.md).

Ba việc. Câu thở theo `Phrase` trên mọi span. Vòng thứ được phép quay về chủ. `castillo` và `sonatina` nhận một extra cho cả ô, cùng cửa PR97 đã mở cho hai điệu vũ.

---

## 1. Chia câu trên mọi span

`_breath` trong `guitar_torroba.py` trả về `bar % 4 == 3`. Ô đó làm mỏng bè trong. Bè cao vẫn ngân. Lưới này không đọc câu.

`plan_phrases` cắt câu từ đường giá trên mọi span. `Phrase.closes` đúng khi nốt cuối dài ít nhất `PERIOD` (4 móc đơn) và câu không `held_over`. Ô cuối câu là `(phrase.end - 1) // epb`.

Hơi thở không phải một cờ cho cả ô. `_owner` và `_bar_pattern` chỉ nhìn câu chứa `bar * epb`. Câu mở sau móc đầu ô thì cờ đó không thấy. Hàm mới nhận `ctx` và `bar`, trả về tập offset trong ô mà eighth nằm trong một câu `closes` và nằm trong ô cuối của câu đó. Chỗ cắt là `phrase.end`, không phải giữa ô.

Không có nhánh `span == "1D"`. `_Ctx` không có trường span. Tập offset này phủ `1D`, `1W`, `1M`, `3M` và `1Y`. Khóa theo `PHRASE_STARTS = (2, 10, 18)` chỉ đúng lưới bài ngày, và vẫn sai bên trong câu ngày vì `plan_phrases` cắt tiếp theo nốt.

Ô pedal cho tập rỗng: `intro`, `outro`, `warmup`, `cooldown`. Khung intro/outro đã có texture riêng. Câu `held_over` không vào tập, vì nốt cuối còn ngân sang câu sau cùng section.

Chỉ bỏ bè trong có offset nằm trong tập đó. Móc của câu sau, cùng ô, giữ nguyên. Bè cao của câu đóng vẫn là close. Đuôi câu có từ hai móc trong thì giữ `_thin` kiểu `[::2]`. Đuôi chỉ có một móc thì bỏ móc đó. Castillo 4/4 chỉ đặt bè trong ở móc 2 và 6. Câu đóng kết ở eighth 4 thì phần đóng chỉ còn móc 2. Cửa `len < 2` hiện tại trong `_thin` sẽ giữ móc đó. Đuôi một móc không đi qua cửa đó.

`band = "p"` đang gắn cả ô ở năm chỗ: `_render_castillo_bar`, `_render_sonatina_bar`, `_block`, `_render_fandanguillo_bar`, `_render_danza_bar`. Bed `p` chỉ áp cho móc có eighth nằm trong tập đóng. Câu đóng không phủ tới hết ô thì bed của ô giữ `ctx.band(bar)`. Castillo ngân một nốt giá cả ô từ móc đầu. Nốt đó giữ bed của ô. Các móc trong thuộc tập đóng vẫn bị bỏ.

### Vì sao lưới `bar % 4` vỡ trên từng span

`DAILY_ENSEMBLE_SPEC` là bài ngày guitar: 34 ô, warmup 2. Section câu nằm ở 2–4, 4–12, 12–20, 20–28, 28–32. Vì warmup chẵn và các đoạn dài 2, 4 hoặc 8, ô cuối section tình cờ thỏa `bar % 4 == 3`. Ô 7, 15 và 23 vẫn bị khoét dù nằm giữa section 8 ô. `1W` cũng mở ở ô 0 với đoạn 4 và 8, nên ô cuối section trùng lưới, còn giữa đoạn 8 ô thì không.

`plan_phrases` cắt tiếp theo chỗ giá dừng. Câu nghe ngắn hơn section. Ô kết của câu nốt đó không còn là bội của 4, trong khi ô `n % 4 == 3` ở giữa câu vẫn mỏng.

| Span | Thân bài guitar | Chỗ lưới modulo lệch câu |
|---|---|---|
| `1D` | 34 ô, 4/4, warmup 2 | Ô 7, 15, 23 thủng giữa section. Câu nốt kết ở ô khác thì không thở |
| `1W` | 32 ô mỗi phiên, 4/4, tempo 90. Đoạn câu 4 hoặc 8 ô | Giữa đoạn 8 ô thủng. Câu nốt bên trong đoạn không ăn ô cuối section |
| `1M`, `3M` | Thân symphony, rồi `_guitar_meter`. 4/4 giữ meter. Chương chậm thành 3/4, scherzo thành 6/8. Khung 4 ô ở 4/4, 6 ô ở 3/4 và 6/8 | Section câu dài 16–32 ô. Khung 6 ô đẩy ô cuối section ra khỏi `n % 4 == 3`. Câu nghe là `Phrase` bên trong section |
| `1Y` | Cùng họ chương. Khung 2 ô ở 4/4, 3 ô ở 3/4 và 6/8 | Thân bài mở ở ô 2 hoặc ô 3. Ô cuối section 4/4 rơi vào `n % 4 == 1` |

`1M` chương I là 4/4, khoảng 96 ô thân, câu form 32 rồi 24 rồi 24. Một vòng hòa âm không phải một câu của cả section đó. Câu nghe vẫn là `Phrase`.

### Nốt lấy đà của sonatina

`apply_sonatina_downbeats` slur vào phách mạnh của mọi ô `sonatina` từ ô 1 trở đi. `_render_sonatina_bar` cũng nối các phách mạnh trong cùng một ô. Hàm đó nhận `phrase_here` của câu sở hữu móc đầu ô, rồi vòng `for offset in strong` slur từ offset 0 sang offset 4 mà không gọi `_phrase_at`.

Cửa mới so câu của hai phách mạnh, cả qua vạch ô lẫn trong ô. Chặn slur và nốt lấy đà khi cả hai phách đều là `sonatina` và câu của phách trước `closes`. `_phrase_at` đã có trong `guitar_torroba.py`.

Nhánh castillo ngân sang phách mạnh sonatina giữ nguyên. `apply_sonatina_downbeats` đọc nốt đang ngân của ô trước, không đọc close ở eighth 4. Ba fixture `held`, `held_step`, `held_leap` trong `test_sonatina_downbeat_leap_step_run_and_castillo_hold` mỗi bên một `Phrase`, `held=False`, nốt dài 8 móc nên `closes` đúng, mood `calm` rồi `rally` ra `castillo` rồi `sonatina`. Chúng khóa grace ở phách 3.75. Cấm mọi biên câu sẽ làm ba assert đó fail, và nhánh đọc nốt ngân castillo không còn chỗ chạy. `held_over` không phải cửa giữ chúng, vì ba fixture không `held_over`.

`leap`, `step` và `running` trong cùng test là một `Phrase` phủ hai ô. Chúng vẫn lấy đà. Castillo, fandanguillo và danza vốn không trồng pickup.

Cửa này không đọc span. Fixture một câu và fixture nhiều câu trên lưới 4/4, 3/4, 6/8 đều đi qua cùng hàm.

### Test

`test_breath_harmonics_and_fandanguillo_grids` đang khóa ô 3 mỏng hơn ô 0 vì `3 % 4 == 3`. Viết lại. Offset cuối một câu `closes` mà chỉ số ô không chia hết kiểu `n % 4 == 3` vẫn mỏng. Offset giữa câu có `bar % 4 == 3` vẫn đầy. Câu kết giữa ô chỉ mỏng đúng phần của câu đó. Đuôi một móc trong thì móc đó mất. Câu `held_over` không mỏng. Ô `intro` / `warmup` không mỏng. Sonatina không slur qua hai phách mạnh của hai câu khi câu trước `closes`. Ba fixture castillo sang sonatina vẫn có grace ở phách 3.75. Không thêm đối số span vào renderer.

---

## 2. Vòng thứ được quay đầu

Vòng nhận diện giữ nguyên: `Cm → Bb → Ab → G → Cm`. `G → Cm` vẫn là cadenza mạnh nhất (`0.74`). La♭ trên `G` / `G7` giữ như mục 2 của kế hoạch Torroba. Picardy vẫn chỉ đổi ô cuối câu đóng từ `Cm` sang `C`.

Ba cạnh dưới đây đang trả `0.0`, vì cặp không có trong `_TORROBA_MINOR` mà một đầu là `Bb`. `Bb` nằm trong `_TORROBA_MINOR_TOUCH`.

| Cạnh | Vai trò | Trọng số |
|---|---|---|
| `Bb → Cm` | i–♭VII rồi về chủ, không buộc tuột hết xuống Sol | `0.40` |
| `Ab → Bb` | ♭VI–♭VII–i | `0.36` |
| `Fm → Bb` | iv–♭VII | `0.34` |

`Bb → Ab` đang là `0.62`, `Ab → G` là `0.66`. `Bb → Cm` (`0.40`) và `Ab → Bb` (`0.36`) thấp hơn hai cạnh đi xuống đó. Khi cả hai hợp lệ, đường Andalucia vẫn được chọn.

`Fm → Bb` ở `0.34` cao hơn mọi lối ra hiện có của Fa thứ: `Fm → G` là `0.30`, `Fm → Ab` và `Fm → G7` là `0.28`, `Fm → Cm` và `Fm → Eb` là `0.20`. Loss bằng nhau thì Viterbi rời `Fm` sang `Bb`. Đó là lối `iv → ♭VII`, không phải cạnh của vòng bốn bước. Vòng `Cm → Bb → Ab → G → Cm` giữ nguyên trọng số.

`G7` vẫn chỉ về `Cm`. Các lối ra khác của `G7` vẫn `0.0`.

Giọng trưởng không thêm `Ab` hay `Eb`. Khung `C → Bb → F → C` và màu `Fm` giữ nguyên. Không thêm maj7, sus, add9, hay hợp âm Rê♭. Nốt Phrygian vẫn là La♭ ngân trên Sol.

Dialect không biết span. Ba cạnh có mặt trên `1D`, `1W`, `1M`, `3M` và `1Y`.

Test: `Bb → Cm`, `Ab → Bb`, `Fm → Bb` trả đúng số. `Bb → Ab` vẫn cao hơn `Bb → Cm`. `Fm → Bb` cao hơn `Fm → G`. `G7 → Fm` vẫn `0.0`. Đường ba ô `Cm → Bb → Cm` đi được khi phách mạnh hợp với chủ. Đường năm ô `Cm → Bb → Ab → G → Cm` cũ vẫn đi được.

---

## 3. Extra cả ô cho Castillo và Sonatina

PR97 thêm `danza` và `fandanguillo` vào `_WHOLE_BAR_EXTRA` trước khi pattern Torroba có thân. Hai điệu viết khoảng phách mạnh là 4 (`68` so với `64`). Một extra theo từng móc xóa khoảng đó. Cửa này giữ.

`castillo` và `sonatina` chưa nằm trong tập.

- Castillo ngân một nốt giá cả ô. Nốt đó nhận extra của phách đầu. Bè trong ở các móc sau nhận extra của móc đó. Câu đang lên làm bè trong leo về phía giai điệu.
- Nét chạy sonatina viết `56`, `60`, `64` trên các móc kép trước phách mạnh. Ba nốt có thể nằm trên hai móc đơn của cùng một ô. Extra khác nhau làm gãy bậc chạy.

Thêm `"castillo"` và `"sonatina"` vào `_WHOLE_BAR_EXTRA`. Một extra, lấy ở móc đầu ô, cùng luật Galop và hai điệu vũ. Không viết `_contour_*` mới. Không hạ thêm bằng `_MICRO`: khoảng 68/64 của điệu vũ đã là vi mô của chúng. Không sửa `PROFILES` trong `guitar_wave.py`.

`_shape_dynamics` không đọc span. Cả năm span đi qua cùng một cửa.

Test hiệu trong ô, câu có `rise` trên `MIN_RISE`, band `mf`. Trên một ô `castillo`, bè trong và nốt giá ngân cùng một extra. Trên một ô `sonatina`, ba nốt chạy cách nhau đúng `4` sau extra. Hai điệu vũ giữ test khoảng phách mạnh đã có.

---

## 4. Bổ sung 6 kiểu kết cấu và tổ hợp câu từ *Sonatina* và *Suite Castellana*

> **Trạng thái**: thiết kế đã xác nhận, chờ triển khai code.
> **Nguyên tắc chung**:
> - **Giữ và kết hợp (Compound Phrase 2–4 ô nhịp)**: Giữ 4 pattern nền hiện có (`castillo`, `sonatina`, `fandanguillo`, `danza`) và ghép 4 kiểu mới thành các tổ hợp câu theo mood / `Phrase`.
> - **Co giãn trên cả 3 nhịp (`4/4`, `3/4`, `6/8`)**: Giữ nguyên lưới 6 móc đơn ở `3/4` và `6/8`; mở rộng tự nhiên lên 8 móc đơn ở `4/4` (`1D`, `1W`, chương 4/4 của `1M`/`3M`/`1Y`).
> - **Phân bổ đúng 3 bè của engine**: `Voice 1` (`lead`: Price Action + móc kép giai điệu/ornament), `Voice 2` (`support`: bè trung rải / khối hợp âm / nhại tiết tấu), `Voice 3` (`low`: Bass hợp âm / bass nối qua vạch ô). Tại mọi thời điểm mỗi voice phát tối đa 1 nốt, tổng số tiếng đồng thời $\le 3$ (`lead > support > low`), và mọi nhóm móc kép ở `Voice 1` thỏa `_assert_scale_positions` trong `assert_playable`.
> - **Quy tắc cao độ**: Trừ chùm 4 nốt móc kép lặp cùng cao độ ở Kiểu 2, tất cả các nốt giai điệu và nốt di chuyển khác đều lấy từ **Price Action (`_melody_at`) sau khi đã chuyển đổi về nốt trong hòa âm / thang âm**.

---

### 4.1. Kiểu 1 — Arpeggio 6 nốt móc kép, nốt thứ 4 là bè trầm nối qua vạch ô (Syncopated Tied-Bass 6-Note Arpeggio)

#### Phân tích bản gốc (*Sonatina* I, đoạn chặn `VIII` $\rightarrow$ `VI`, nhịp 3 móc đơn/ô)
Mỗi chùm 6 nốt móc kép ($s_0, s_1, s_2, s_3, s_4, s_5$) tạo thành một đường rải hình chữ **V đối xứng**:
$$\text{Cao } (s_0) \searrow \text{Trung cao } (s_1) \searrow \text{Trung thấp } (s_2) \searrow \mathbf{\text{BASS } (s_3)} \nearrow \text{Trung thấp } (s_4) \nearrow \text{Trung cao } (s_5)$$

- **$s_0$ (Móc kép 1, có dấu nhấn `>`):** Nốt giai điệu cao nhất ở bè trên (ví dụ trên bản gốc: $C_6 \rightarrow B\flat_5 \rightarrow C_6 \rightarrow B\flat_5 \rightarrow A_5 \rightarrow G\flat_5 \rightarrow A_5 \rightarrow B\flat_5 \rightarrow A_5$).
- **$s_1, s_2$ (Móc kép 2 & 3):** 2 nốt hợp âm ở bè trung rải đi xuống ($s_1 > s_2$, ví dụ $F_5 \rightarrow D_5$ hoặc $E\flat_5 \rightarrow C_5$).
- **$s_3$ (Móc kép 4 — phách đảo giữa ô):** Nốt **Trầm (Bass)** có dấu nhấn `>` và **dấu nối (Tie `⏝`) ngân qua vạch ô sang phách 1 của ô nhịp kế tiếp**. Nhờ vậy, ở đầu ô sau, bè trầm không đánh lại mà vẫn ngân từ giữa ô trước.
- **$s_4, s_5$ (Móc kép 5 & 6):** 2 nốt bè trung rải ngược trở lên ($s_4 = s_2, s_5 = s_1$).

#### Quy tắc ánh xạ vào Engine
- **Phân bổ 3 bè & Cao độ:**
  - `Voice 1 (lead)` tại $s_0$: Nốt **Price Action** (`_melody_at`) đã quy về hòa âm, `accent=True`.
  - `Voice 2 (support)` tại $s_1, s_2$ và $s_4, s_5$: Chọn 2 nốt thuộc `ctx.chord(bar)` nằm dưới `lead` và trên `bass` ($s_1 > s_2$). Lượt lên lấy $s_4 = s_2, s_5 = s_1$ (hoặc bám theo price action nửa sau ô nếu dịch chuyển).
  - `Voice 3 (low)` tại $s_3$: Nốt `_torroba_bass(ctx, chord, bar, lead)`, đặt ở vị trí thứ 4 của chùm 6 và kéo độ dài ngân qua phách đầu của ô tiếp theo (hoặc nửa sau ô trong 4/4).
- **Lưới nhịp (`3/4`, `6/8`, `4/4`):**
  - Ở `6/8` và `3/4` (6 móc đơn / 12 móc kép): Mỗi nửa ô (3 móc đơn = 6 móc kép) hoặc cả ô 6 móc đơn chạy đúng 1 chu kỳ chữ V $[s_0, s_1, s_2, s_3(\text{bass}), s_4, s_5]$, trong đó bass ở vị trí thứ 4 ngân qua đầu chu kỳ kế tiếp.
  - Ở `4/4` (8 móc đơn): Chạy chu kỳ 6 móc $[0..5]$ (bass đặt ở móc thứ 4 ngân qua cuối ô sang đầu ô sau) + 2 móc cuối $[6..7]$ rải bè trung dẫn vào phách mạnh ô kế tiếp.

---

### 4.2. Kiểu 2 — Rasgueado + 4 móc kép lặp $\rightarrow$ Nốt trầm + 4 móc kép lặp $\rightarrow$ Chùm Chord móc đơn

#### Phân tích bản gốc (*Sonatina* I, đoạn cao trào `ff` chặn `V` & `II` $\rightarrow$ hạ về `p`)
Tổ hợp câu 3 ô nhịp liên tiếp (trên lưới gốc 3 móc đơn/ô):
1. **Ô A (Rasgueado + 4 móc kép lặp):**
   - Móc đơn đầu: Hợp âm quạt/rải dọc (`ff`, trên bản gốc là hợp âm $E$ mở rộng và hợp âm $A$ trưởng với đỉnh giai điệu là $A_4$).
   - 2 móc đơn sau (4 móc kép): **Chùm 4 nốt móc kép có cùng 1 cao độ lặp lại liên tiếp** ($E_4 - E_4 - E_4 - E_4$).
2. **Ô B (Nốt trầm + 4 móc kép lặp):**
   - Móc đơn đầu: **1 nốt trầm/trung trầm đơn độc** ($A_3$) đáp lại khối hợp âm của Ô A.
   - 2 móc đơn sau (4 móc kép): Lặp lại **chùm 4 nốt móc kép cùng cao độ** ($E_4 - E_4 - E_4 - E_4$ trên dây buông `⓪`).
3. **Ô C (Chùm Chord móc đơn đi theo giai điệu):**
   - Đánh liên tiếp các **khối hợp âm móc đơn (Block Chords)**, trong đó bè dưới giữ thế tay hợp âm còn **nốt trên cùng di chuyển theo giai điệu** (trên bản gốc: $F\#_4 \rightarrow E_4 \rightarrow D\#_4$ trên nền $[A_2, F\#_3, B_3]$, hoặc $F\#_4 \rightarrow D_4 \rightarrow B_3$ trên nền $[F_2, D_3, A_3]$), rồi giải về hợp âm chủ (`p`).

#### Quy tắc ánh xạ vào Engine
- **Chùm 4 nốt móc kép lặp (`Voice 1` / `Voice 2`):**
  - Lấy **4 nốt móc kép giống hệt nhau** $(p, p, p, p)$ với `duration_beats = 0.25`, ưu tiên nốt bậc V hoặc bậc I của hợp âm trong vùng trung-cao (hoặc dây buông hợp lệ `64` / nốt neo của hợp âm).
- **Các nốt còn lại lấy theo Price Action sau khi quy về hòa âm:**
  - **Đầu Ô A (Rasgueado):** Khối 3 tiếng (`low` + `support` + `lead`), trong đó `lead` là `_melody_at` tại móc đầu, `accent=True`, vận tốc $\ge 68$.
  - **Đầu Ô B (Nốt trầm đáp):** `low` (hoặc `support` trầm) đánh nốt hợp âm tương ứng với chuyển động Price Action, không đánh `lead` ở móc đầu để tạo độ tương phản trầm – cao trước khi chùm 4 móc kép lặp vang lên.
  - **Ô C (Chùm Chord móc đơn):** Mỗi móc đơn là một khối hợp âm 3 bè (`low` + `support` + `lead`), trong đó `lead` tại từng móc đơn lấy trực tiếp từ `_melody_at(ctx, origin + offset)` đã quy về nốt trong hòa âm/thang âm.
- **Lưới nhịp (`3/4`, `6/8`, `4/4`):**
  - Ở `3/4` và `6/8`: Mỗi nửa ô (3 móc đơn) hoặc mỗi ô giữ nguyên cấu trúc `[1 móc đơn + 4 móc kép lặp]` cho A & B, và `[3 hợp âm móc đơn]` cho C.
  - Ở `4/4` (8 móc đơn): Nửa đầu ô (móc $0..2$) là **Ô A** `[Rasgueado móc 0 + 4 móc kép lặp ở móc 1..2]`, móc 3 nghỉ/ngân lấy hơi; nửa sau ô (móc $4..6$) là **Ô B** `[Nốt trầm móc 4 + 4 móc kép lặp ở móc 5..6]`, móc 7 dẫn sang ô tiếp theo là **Ô C** với chuỗi Chord móc đơn theo Price Action.

---

### 4.3. Kiểu 3 — Rasgueado móc đơn + Câu tiết tấu móc kép/móc đơn + Scale móc đơn (`pizz.`) kết bằng Harmonics (`Arm.`)

#### Phân tích bản gốc (*Sonatina* I, đoạn `pizz.` – chặn `V` – `Arm.` – `con gracia`)
Tổ hợp câu gồm 3 mảng kết cấu nối tiếp nhau:
1. **Mảng 1 — Rasgueado móc đơn mở câu + Mô-típ tiết tấu câu (Dòng 1, Ô 3 & Ô 4):**
   - **Móc đơn 0:** Hợp âm rải/rasgueado (ở ô đầu câu) hoặc 1 nốt móc đơn lấy đà (ở ô lặp lại).
   - **Móc đơn 1 & 2:** **2 nốt móc kép lặp + 1 nốt móc đơn** ($E_4 - E_4 \rightarrow E_4$, tạo thành chùm 3 tiếng gõ nhanh dồn vào phách 2).
   - **Móc đơn 3:** **2 nốt móc kép lướt có dấu nối (slur)** ($F\#_4 - E_4$).
   - **Móc đơn 4 & 5:** **2 nốt móc đơn** ($D_4 \rightarrow E_4$).
2. **Mảng 2 — Đoạn Scale / Arpeggio móc đơn `pizz.` đi lên (Dòng 1 Ô 1–2, Dòng 2 Ô 5–6):**
   - Sau phách đầu, chuỗi **5–6 nốt móc đơn đánh ngắt `pizz.` (ký hiệu `x`)** leo dần qua các nốt hòa âm và thang âm hướng lên đỉnh câu (ví dụ $F\#_3 \rightarrow A_3 \rightarrow D_4 \rightarrow F\#_4 \rightarrow A_4$ hoặc $E_5 \rightarrow B_4 \rightarrow C\#_5 \rightarrow E_5 \rightarrow G\#_5 \rightarrow A_5$).
3. **Mảng 3 — Kết câu bằng Harmonics ngân dài (`Arm.`, Dòng 2 Ô 7):**
   - Khi chuỗi móc đơn `pizz.` chạm đỉnh, ô nhịp tiếp theo dừng toàn bộ phần đệm và thả **1 nốt Harmonics (`Arm.`) ngân dài trọn ô** ở dải cao.

#### Quy tắc ánh xạ vào Engine
- **Ô Rasgueado + Nhịp câu móc kép/móc đơn:**
  - Móc 0: Khối hợp âm 3 tiếng (`low` + `support` + `lead` = `_melody_at`).
  - Các móc tiếp theo trên `Voice 1 (lead)`: Chạy mô-típ tiết tấu `[2 móc kép + 1 móc đơn] + [2 móc kép slur] + [2 móc đơn]`, với cao độ lấy từ Price Action đã quy về hòa âm/thang âm (`_walk` / `_melody_at`), đảm bảo nằm gọn trong 1 thế tay (`_assert_scale_positions`). Ở `4/4`, thêm 1 phách kết (2 móc đơn ở móc $6..7$) hoàn tất câu.
- **Ô Scale móc đơn (`staccato=True` / `pizz.`):**
  - Chạy chuỗi móc đơn (`staccato=True`) đi từ vùng trung/trầm (`support` $\rightarrow$ `lead`) bám theo các nốt hợp âm/thang âm tiến thẳng về nốt Price Action của đỉnh câu.
- **Ô kết Harmonics (`Arm.`):**
  - `Voice 1 (lead)` ngân trọn ô tại nốt Price Action với `velocity = 48` (màu chuông/harmonics, `support` nghỉ hoàn toàn, `low` điểm nhẹ bass dây buông ở đầu ô).

---

### 4.4. Kiểu 4 — Pattern mở đầu của *Sonatina* Chương I (*Allegretto*)

#### Phân tích bản gốc (*Sonatina* I, Ô 1–4 mở đầu *Allegretto*, nhịp $3/4$, `mf`)
Cặp ô nhịp **Đối đáp 2 ô (Call & Response)** kinh điển của Torroba:
1. **Ô Lẻ (Ô 1 & Ô 3 — "Call": Hợp âm mở + Giai điệu móc kép/móc đơn + 2 Chord móc đơn cuối ô):**
   - **Móc đơn 0 (Phách 1a):** Bè trầm/trung đánh hợp âm nền (hoặc nốt Bass dây buông $A_2$), trong khi bè cao nghỉ nửa phách đầu (`𝄾`).
   - **Móc đơn 1 (Phách 1b):** `Voice 1 (lead)` vào bằng **2 nốt móc kép** ở dải cao ($C\#_5 - C\#_5$).
   - **Móc đơn 2 (Phách 2a):** **1 nốt móc đơn** ($C\#_5$).
   - **Móc đơn 3 (Phách 2b):** **2 nốt móc kép lướt có slur** ($D_5 - C\#_5$, thêu bậc trên quay về).
   - **Móc đơn 4 & 5 (Phách 3):** **2 khối hợp âm móc đơn** đi theo giai điệu ($B_4 \rightarrow E_4$ hoặc $B_4 \rightarrow G\#_4$) kèm **nốt Bass dây buông móc đơn ở móc 5** làm đà sang ô sau.
2. **Ô Chẵn (Ô 2 & Ô 4 — "Response": Giai điệu ngân dài + Bè trung nhại lại tiết tấu):**
   - **Bè cao (`Voice 1`):** Giữ **1 nốt giai điệu ngân dài suốt cả ô** ($A_4$ ở ô 2, $B_4$ ở ô 4).
   - **Bè trầm (`Voice 3`):** Đánh Bass ở móc 0 và **1 nốt Bass móc đơn ở cuối ô (móc 5)**.
   - **Bè trung (`Voice 2`):** Trong lúc bè cao ngân dài, bè trung ở dải ấm ($\le 65$) **nhại lại chính xác hình tiết tấu của bè cao ở ô trước** bằng chuyển động thêu liền bậc có slur:
     - Nghỉ móc 0 $\rightarrow$ **2 móc kép** (móc 1, có slur) $\rightarrow$ **1 móc đơn** (móc 2) $\rightarrow$ **2 móc kép** (móc 3, có slur) $\rightarrow$ **1 nốt đơn/đen** (móc 4).

#### Quy tắc ánh xạ vào Engine
- **Ô Call (Ô mở câu):**
  - Móc 0: `Voice 3 (low)` (+ `Voice 2 (support)`) đánh nền hợp âm; `Voice 1` nghỉ nửa phách đầu.
  - Móc $1..3$: `Voice 1 (lead)` hát mô-típ `[2 móc kép (móc 1) + 1 móc đơn (móc 2) + 2 móc kép có slur (móc 3)]` bám theo Price Action đã quy về hòa âm (`_melody_at` và nốt bậc thang liền kề).
  - Móc cuối ô (móc $4..5$ ở `3/4` & `6/8`; móc $4..7$ ở `4/4`): Đánh các khối hợp âm móc đơn (`lead` + `support`, với `lead` là Price Action tại từng móc) và đặt **nốt Bass móc đơn (`low`) ở móc cuối cùng của ô** làm cầu nối sang ô Response.
- **Ô Response (Ô đáp câu):**
  - `Voice 1 (lead)`: Ngân dài nốt Price Action từ đầu ô (`origin`) xuyên suốt ô.
  - `Voice 2 (support)`: Nhại lại mô-típ `[2 móc kép slur (móc 1) + 1 móc đơn (móc 2) + 2 móc kép slur (móc 3) + nốt đơn/đen (móc 4)]` trên 2 nốt liền bậc trong hòa âm/thang âm ở vùng trung ($\le 65$, dưới `lead` và trên `low`).
  - `Voice 3 (low)`: Đánh Bass ở móc 0 và 1 nốt Bass móc đơn ở cuối ô.

---

### 4.5. Kiểu 5 — Rasgueado, Price Action chạy ở bè trầm rồi chuyển giao lên bè cao (1 chùm 4 nốt đơn $\rightarrow$ 6 nốt đen hợp âm)

> Nguồn: *Suite Castellana*, chương I *Fandanguillo*, đoạn `ff/fff` chặn `V`/`II`/`VII`.

#### Phân tích bản gốc (nhịp $3/4$, giọng Mi trưởng)
Ba pha nối nhau thành một vòm kịch tính:

1. **Pha 1 — Rasgueado mở câu (`ff`) + 4 nốt móc đơn staccato ở bè trầm:**
   - Phách 1: hợp âm quạt 6 dây, đỉnh là nốt giai điệu (`$G\#_5$` trên bản gốc).
   - Phách 2–3: bè cao tắt, bè trầm đánh chùm 4 nốt móc đơn ngắt lặp và tiến bậc (`$B_2 - B_2 - B_2 - C\#_3$`, dấu chấm staccato).
2. **Pha 2 — Price Action độc tấu ở bè trầm.** Câu chạy nằm hẳn ở dây 5 và dây 6, xen kẽ hai hình:
   - 3 nốt đen đi bậc (`$D\#_3 - D\#_3 - E_3$`, rồi dịch xuống từng bậc `$E_3 - D\#_3 - C\#_3$`, `$D\#_3 - C\#_3 - B_2$`).
   - Mô-típ lướt: **2 móc kép slur + 1 móc đơn + 1 móc đơn + 1 nốt đen** (`$E_3\text{-}F\#_3 \rightarrow E_3 \rightarrow D\#_3 \rightarrow C\#_3$`), kết bằng nốt trầm ngân dài nối sang ô sau.
3. **Pha 3 — Chuyển giao lên bè cao: 1 chùm 4 nốt móc đơn, rồi 6 nốt đen hợp âm (`cresc.`):**
   - Ô chuyển giao: phách 1 giữ nốt bass ngân, phách 2–3 bè cao cất tiếng bằng chùm 4 nốt móc đơn (`$B_3 - B_3 - B_3 - C\#_4$`).
   - Hai ô tiếp theo: 6 phách nốt đen hợp âm liên tiếp trên bass pedal, nốt trên cùng leo dần (`$D\#_4 \rightarrow D\#_4 \rightarrow E_4$`, rồi `$A_4 \rightarrow G\#_4 \rightarrow F\#_4$`).

#### Quy tắc ánh xạ vào Engine
- **Pha 1:** móc 0 là khối 3 tiếng (`low` + `support` + `lead` = `_melody_at`), phách sau nhường cho bè trầm chạy chùm 4 nốt móc đơn `staccato` bám price action dịch xuống quãng 8.
- **Pha 2:** `Voice 3 (low)` (hoặc `Voice 2` ở dải trầm) hát price action qua nốt đen và mô-típ lướt 2 móc kép slur. `lead` nghỉ.
- **Pha 3:** phách đầu giữ bass ngân; `Voice 1 (lead)` vào bằng chùm 4 nốt móc đơn, rồi **6 phách nốt đen hợp âm** (`duration_beats = 1.0`), mỗi phách đủ 3 bè, nốt trên cùng là `_melody_at` đã quy về hòa âm.

#### Phách mạnh, phách nhẹ và vi mô vận tốc
Đơn vị là `_MICRO = 2` của [`docs/sonify-guitar-micro-contour-plan.md`](./sonify-guitar-micro-contour-plan.md). Mức viết lấy theo bảng mục 5 của [`docs/sonify-guitar-torroba-plan.md`](./sonify-guitar-torroba-plan.md): phách mạnh `max(_note_velocity, 68)`, phách yếu 64, bè đệm theo `_under_lead`. Bậc dưới đây hạ khỏi mức đó, sau `_shape_accompaniment`, qua `_micro_fits` để giữ `lead > bass > support` ít nhất 2. Câu phẳng band `mf` thì lead 64, bass 60, bè trong 56.

| Chỗ | Phách | Bậc | Ghi chú |
|---|---|---|---|
| Rasgueado mở câu, cả 3 bè | mạnh (`accent=True`) | 0 | Đỉnh của pha. `volatile` viết 68 |
| 4 nốt móc đơn staccato ở bè trầm | yếu | −2, −2, −2, −1 | Ba nốt lặp chìm, nốt thứ 4 bước bậc nhích lên để dẫn |
| Nốt đen bè trầm rơi đầu ô | mạnh | 0 | Trụ của câu chạy trầm |
| Nốt đen bè trầm giữa và cuối ô | nhẹ | −1 | Cùng kiểu nốt dài nửa sau của *Élégiaque* |
| 2 móc kép slur trong mô-típ lướt | nhẹ | −2, −1 | Dâng vào móc đơn sau, móc kép đầu mở slur |
| Móc đơn sau slur, và nốt đen chốt mô-típ | mạnh tương đối | −1, rồi 0 | Nốt đen chốt giữ mức viết |
| Chùm 4 nốt móc đơn lúc chuyển giao | yếu $\rightarrow$ mạnh | −2, −2, −1, 0 | Dâng vào phách hợp âm đầu tiên |
| 6 nốt đen hợp âm | mạnh đều | 0 | Không khía trong phách. `cresc.` là extra cả ô của `_shape_dynamics`, không phải bậc vi mô |

---

### 4.6. Kiểu 6 — Chùm 3 hợp thành nốt đen, beat đầu là chord, bè cao ngân rồi chuyển qua bè trung đệm

> Nguồn: *Suite Castellana*, chương III *Danza*, từ thế `VII` đầu tiên đến trước thế `VII` thứ hai. Nhịp $3/8$, mỗi ô là một phách chấm dôi.

#### Phân tích bản gốc (giọng Mi trưởng)
Đoạn dài 8 ô, chia đôi đối xứng:

1. **Nửa A — 4 ô từ thế `VII` đầu (`f`): hợp âm nền ngân xuyên suốt, bè cao chạy chùm 3 nốt móc đơn.**
   - Đầu ô 1 của nửa A: khối hợp âm nền (`$B_7$`: $[B_2, A_3, D\#_4]$) nối dây ngân suốt 4 ô.
   - Bè cao, mỗi ô một chùm 3 nốt móc đơn:
     - Ô 1: **3 nốt giống nhau** (`$C\#_5 - C\#_5 - C\#_5$`, dấu tenuto).
     - Ô 2–4: bè cao đi theo giai điệu (`$B_4 - C\#_5 - D\#_5$`, `$E\natural_5 - D\#_5 - D\#_5$` có nốt lướt, `$C\#_5 - D\#_5 - B_4$`).
2. **Nửa B — 4 ô thế `IV` ngay trước thế `VII` thứ hai: chùm 3 hợp thành nốt đen, rồi bè trung đệm.**
   - Beat đầu: khối chord, bè cao lướt chùm 3 móc kép (`$A_4 - G\#_4 - F\#_4$`) đổ vào nốt đích (`$G\#_4$`).
   - Nốt đích đó nối dây ngân suốt 2 ô sau. Bè cao đứng yên.
   - Bè trung và bè trầm nhận phần vận động: `$C\#_4 \rightarrow F\#_3 \rightarrow C\#_4$`, rồi `$F\#_3 \rightarrow$ nghỉ $\rightarrow B_3$`, kết bằng một nốt điểm nhẹ giữa ô để lấy hơi.

Đoạn này lặp lại đúng hình ở thế `IX` ngay trước đó, trên hợp âm $E$ trưởng.

#### Quy tắc ánh xạ vào Engine
- **Nửa A:** `low` + `support` đánh một lần ở đầu cụm và ngân dài. `Voice 1 (lead)` hát chùm 3 nốt móc đơn mỗi ô: **chùm đầu tiên giữ 3 nốt cùng cao độ** lấy từ `_melody_at`; các chùm sau đi theo price action đã quy về hòa âm, chùm thứ ba có một móc kép lướt.
- **Nửa B:** beat đầu là khối chord, `lead` lướt chùm móc kép vào nốt đích rồi ngân dài qua 2 ô. Trong lúc `lead` ngân, `support` và `low` đệm mô-típ `trung $\rightarrow$ trầm $\rightarrow$ trung`, rồi `trầm $\rightarrow$ nghỉ $\rightarrow$ trung`.

#### Phách mạnh, phách nhẹ và vi mô vận tốc
Trong $3/8$, mỗi ô là một phách. Ô đầu của mỗi nửa là phách mạnh của cụm; ô 2 và ô 4 nhẹ, ô 3 là phách mạnh phụ. Trên lưới `3/4` và `6/8` của engine, một chùm 3 nốt móc đơn chiếm một phách chấm. Trên `4/4`, cụm co lại còn 2 ô: nửa đầu là nửa A, nửa sau là nửa B.

| Chỗ | Phách | Bậc | Ghi chú |
|---|---|---|---|
| Chord đầu nửa A, cả 3 bè | mạnh (`accent=True`) | 0 | `danza` viết 68. Hợp âm này ngân, không đánh lại |
| 3 nốt móc đơn giống nhau đầu tiên | mạnh | −1, −2, −2 | Nốt rơi phách giữ gần mức viết, hai nốt sau là tiếng vang |
| Chùm 3 móc đơn đi theo price action, nốt đầu chùm | mạnh phụ | −1 | Nốt rơi đúng phách của chùm |
| Hai nốt sau trong chùm đó | nhẹ | −2 | Nốt lệch phách, cùng luật Quantz một bậc |
| Móc kép lướt trong chùm thứ ba | nhẹ | −2 | Dưới nốt nó đổ vào |
| Chord đầu nửa B | mạnh (`accent=True`) | 0 | Beat đầu của nửa sau |
| 3 móc kép lướt vào nốt ngân | nhẹ, dâng dần | −3, −2, −1 | Cùng hướng lấy đà của allemande: móc cuối chạm mức viết |
| Nốt đích `lead` ngân dài | mạnh | 0 | Giữ mức viết suốt hai ô, không đánh lại |
| Bè trung đệm khi `lead` đang ngân | nhẹ | −1 | Dưới nốt ngân ít nhất 4, theo `_under_lead` |
| Bè trầm đệm trong mô-típ | nhẹ | −2 so với bass phách mạnh | Bass phách mạnh của nửa B là mốc |
| Nốt điểm lấy hơi cuối nửa B | nhẹ nhất | −2, và `staccato` | Câu nghỉ trước chu kỳ sau |

Ba nốt móc đơn đầu giống nhau là chỗ duy nhất trong kiểu này được phép lặp cao độ. Mọi nốt `lead` còn lại đọc `_melody_at` sau khi đã về nốt của hòa âm.

---

### 4.7. Bảng tổng hợp ghép tổ hợp câu (Compound Phrase Integration)

| Tổ hợp / Kiểu | Vai trò trong Phrase & Mood | Cấu trúc ô nhịp trong câu | Phân bổ 3 Voice (`lead` / `support` / `low`) | Phách mạnh / vi mô |
|---|---|---|---|---|
| **Kiểu 4 (*Sonatina* Opening)** | Mở câu `sonatina` (`rally`, `calm` vừa) | Cặp 2 ô: **Ô Call** (giai điệu móc kép/đơn + chord cuối ô) $\rightarrow$ **Ô Response** (lead ngân + bè trung nhại tiết tấu) | `lead`: mô-típ Call rồi ngân ở Response; `support`: chord cuối ô Call + nhại tiết tấu ở Response; `low`: bass đầu ô và móc cuối ô | Phách 1 mạnh, giữ mức viết. Móc kép slur trong mô-típ hạ 1 bậc. Bè trung nhại ở ô Response hạ 1 bậc so với `lead` đang ngân |
| **Kiểu 1 (6-Note Tied-Bass Arpeggio)** | Giữ dòng chảy giữa câu (`sonatina` / `castillo` chuyển động) | Chuỗi rải 6 nốt hình chữ V, nốt thứ 4 là Bass nối qua vạch ô | `lead`: $s_0$ (`accent`); `support`: $s_1, s_2$ đi xuống và $s_4, s_5$ đi lên; `low`: $s_3$ ngân qua phách 1 ô sau | $s_0$ giữ mức viết, có `accent`. $s_1, s_2$ hạ 1 rồi 2 bậc. Bass $s_3$ giữ mức bass phách mạnh dù rơi giữa ô. $s_4, s_5$ hạ 2 rồi 1 bậc, dâng về chu kỳ sau |
| **Kiểu 2 (Rasgueado + 4x16th + Block Chords)** | Cao trào / `volatile` / đỉnh `rally` (`fandanguillo` / `sonatina` kịch tính) | Cụm 2–3 ô: **[Rasgueado + 4 móc kép lặp]** $\rightarrow$ **[Bass + 4 móc kép lặp]** $\rightarrow$ **[Chùm Chord móc đơn theo Price]** | Chùm 4 móc kép giữ 1 cao độ $(p, p, p, p)$; Rasgueado và chùm Chord móc đơn lấy `lead` theo Price Action đã quy về hòa âm | Rasgueado và nốt trầm đáp là phách mạnh, giữ mức viết. 4 móc kép lặp hạ 1 bậc và đều nhau, vì tiếng lặp lệch sẽ vỡ. Chord móc đơn: phách đầu giữ, các phách sau hạ 1 bậc |
| **Kiểu 3 (Rasgueado + Motif + Scale `pizz.` + `Arm.`)** | Nửa cuối câu tiến về chỗ đóng câu (`phrase.closes`) | **[Rasgueado + câu 16th/8th]** $\rightarrow$ **[Scale móc đơn `pizz.` leo dốc]** $\rightarrow$ **[Ô kết Harmonics `Arm.`]** | `lead` + `support` chạy mô-típ và scale móc đơn `staccato`; ô đóng câu ngân Harmonics (`velocity = 48`, `support` nghỉ) | Rasgueado mạnh, giữ mức viết. 2 móc kép lặp hạ 2 bậc, móc đơn sau chúng hạ 1. Scale `pizz.` dâng từng bậc 2 về nốt cuối, nốt cuối giữ mức viết. Harmonics viết 48, không cộng extra |
| **Kiểu 5 (*Fandanguillo*: trầm rồi giao lên cao)** | Cao trào có hướng (`volatile`, đỉnh `rally`) | **[Rasgueado + 4 móc đơn trầm]** $\rightarrow$ **[Price Action ở bè trầm]** $\rightarrow$ **[4 móc đơn chuyển giao + 6 nốt đen hợp âm]** | Pha trầm: `low` hát price action, `lead` nghỉ. Pha giao: `lead` hát chùm 4 rồi 6 hợp âm nốt đen, `low` là pedal | Rasgueado và nốt đen đầu câu trầm giữ mức viết. 4 móc đơn trầm hạ 2 bậc, nốt cuối của chùm hạ 1. 6 hợp âm nốt đen đều mức viết. `cresc.` là extra cả ô |
| **Kiểu 6 (*Danza*: chùm 3 và bè trung đệm)** | Câu nhịp vũ (`danza`, `calm` trong scherzo) | **[4 phách chùm 3 móc đơn trên hợp âm ngân]** $\rightarrow$ **[Beat đầu là chord, lead ngân, bè trung đệm]** | Nửa A: `low` + `support` ngân, `lead` hát chùm 3. Nửa B: `lead` ngân, `support` và `low` đệm | Chord đầu mỗi nửa giữ mức viết, có `accent`. 3 nốt đầu giống nhau hạ 1, 2, 2 bậc. Chùm đi theo price action hạ 1 bậc ở nốt rơi phách và 2 bậc ở hai nốt lệch. 3 móc kép lướt dâng −3, −2, −1 vào nốt ngân |

---

## 5. Thứ tự làm

1. **Câu (đã hát).** Tập offset của câu `closes` trên mọi span. Bed `p` chỉ trên các móc đó. Chặn slur sonatina khi câu trước `closes` và cả hai phách là sonatina. Giữ grace castillo sang sonatina.
2. **Ba cạnh thứ (đã hát).** `0.40`, `0.36`, `0.34`. Vòng bốn bước và La♭ trên Sol không đổi.
3. **Extra cả ô (đã hát).** `castillo` và `sonatina` vào `_WHOLE_BAR_EXTRA`.
4. **Sáu kiểu kết hợp vào câu (tiếp theo).** Bốn kiểu *Sonatina* (mục 4.1–4.4) cộng hai kiểu *Suite Castellana* (mục 4.5 và 4.6) trong `guitar_torroba.py`. Co giãn trên `4/4`, `3/4`, `6/8`. Mỗi kiểu khóa bậc vi mô của bảng phách mạnh/nhẹ bằng hiệu trong ô, band `mf`, câu phẳng, cùng cách `test_galop_beats_keep_a_micro_velocity_contour`. Kiểm chứng `assert_playable`.
