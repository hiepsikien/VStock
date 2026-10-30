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

## 4. Thứ tự làm

1. **Câu.** Tập offset của câu `closes` trên mọi span. Bed `p` chỉ trên các móc đó. Chặn slur sonatina khi câu trước `closes` và cả hai phách là sonatina. Giữ grace castillo sang sonatina. Viết lại test ô 3.
2. **Ba cạnh thứ.** `0.40`, `0.36`, `0.34`. Vòng bốn bước và La♭ trên Sol không đổi.
3. **Extra cả ô.** `castillo` và `sonatina` vào `_WHOLE_BAR_EXTRA`.

Bước 1 là chỗ nghe hết vỡ câu. Bước 2 và 3 không phụ thuộc lưới ô của `1D`.
