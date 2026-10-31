# Kế hoạch: câu Torroba, vòng quay đầu, extra cả ô

> **Trạng thái**: mục 1–3 đã hát trên `main`. Mục 4 đã chốt, chờ code.
> **Khung đang chạy**: [`docs/sonify-guitar-torroba-plan.md`](./sonify-guitar-torroba-plan.md), mục 4, 5 và 6. Vi mô trong ô: [`docs/sonify-guitar-micro-contour-plan.md`](./sonify-guitar-micro-contour-plan.md).

Ba việc đã hát. Câu thở theo `Phrase` trên mọi span. Vòng thứ được phép quay về chủ. `castillo` và `sonatina` nhận một extra cho cả ô, cùng cửa PR97 đã mở cho hai điệu vũ.

Mục 4 là tám kiểu từ *Sonatina* chương I và *Suite Castellana* chương I, II, III, cùng luật phối chúng với bốn pattern nền.

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

## 4. Tám kiểu kết cấu từ *Sonatina* và *Suite Castellana*

> **Trạng thái**: đã chốt, chờ code trong `guitar_torroba.py`.
> Tám kiểu là cách đánh bên trong pattern đã khóa. Chúng không thêm id vào `_FAMILY`, và `_bar_pattern` không đổi.

### 4.0. Phối với bốn pattern nền

Mood vẫn khóa pattern theo mục 7 của [`docs/sonify-guitar-torroba-plan.md`](./sonify-guitar-torroba-plan.md). Một câu có một pattern. Kiểu chỉ được gọi từ pattern của câu đó.

| Pattern | Kiểu được gọi | Lưới khi câu không nhận kiểu |
|---|---|---|
| `castillo`, `ctx.bpm <= 72` | 7 hoặc 8, xoay theo `k % 2` | Một nốt giá ngân cả ô |
| `castillo`, `ctx.bpm > 72` | không gọi kiểu nào | Một nốt giá ngân cả ô |
| `sonatina` | 4, 2, 1 trên câu chưa đóng. 3 trên câu `closes` | Rải móc đơn, giai điệu ở phách mạnh |
| `fandanguillo` | 5 hoặc 2, mỗi câu chỉ một trong hai | Hợp âm ở móc đơn 0, giai điệu ở các phách mạnh còn lại |
| `danza` trên 3/4 và 6/8 | 6 | Hợp âm staccato đầu mỗi nhóm ba móc, rồi nốt đáp |
| `danza` trên 4/4 | không có lưới | Pattern này không được chọn ở chương 4/4 |

`castillo` trên 72 BPM giữ một nốt ngân mỗi ô. Đó là `calm` của chương 4/4. Kiểu 7 và kiểu 8 chỉ vào `castillo` khi `ctx.bpm <= 72`, tức chương chậm và `selloff` chậm. Kiểu 1 không vào `castillo`.

Cửa chọn chạy một lần cho mỗi câu thân, sau khi pattern của câu đã khóa. `intro`, `outro`, `warmup`, `cooldown` không nhận kiểu. `n` đếm câu thân của cùng pattern trong section, bắt đầu từ 0. Câu `sonatina` có `closes` không lấy số `n`: câu đó đi kiểu 3, và các câu sau không bị dịch thứ tự. `k` đếm riêng các câu `n` chẵn, cũng từ 0. Câu `fandanguillo`, `danza` và `castillo` có `closes` vẫn lấy số `n`. Với `fandanguillo` và `danza`, ô cuối của câu `closes` không nằm trong span của kiểu. Với `castillo`, nốt ngân của ô cuối kiểu 7, hoặc nửa sau ô 2 của kiểu 8 khi câu dài đúng 2 ô, là chỗ đóng.

1. Câu `sonatina` có `closes`: cả câu dành cho kiểu 3. Không cộng thêm kiểu 4, 2 hay 1.
2. Câu có `n` lẻ, kể cả câu `fandanguillo`, `danza` hoặc `castillo` đang `closes`: cả câu là lưới nền.
3. Câu `sonatina` chưa đóng, `n` chẵn:
   - `k % 3 == 0` và câu dài ít nhất 4 ô: kiểu 4 trên hai ô đầu. Các ô sau là lưới nền.
   - `k % 3 == 1`, `phrase.rise >= MIN_RISE` (`3`), câu dài ít nhất 2 ô: kiểu 2 trên hai ô bắt đầu tại chỉ số `length // 2 - 1` (không âm).
   - `k % 3 == 2` và câu dài ít nhất 3 ô: kiểu 1 trên đúng một ô, chỉ số 1. Ô đầu và ô cuối giữ lưới nền.
   - Không cửa nào khớp thì câu về lưới nền. `k % 3 == 0` mà câu ngắn hơn 4 ô, `k % 3 == 1` mà `rise` dưới 3 hoặc câu ngắn hơn 2 ô, và `k % 3 == 2` mà câu ngắn hơn 3 ô, đều là lưới nền. Không đổi sang kiểu khác.
4. Câu `fandanguillo` có `n` chẵn:
   - `k % 2 == 0`, `rise >= 3`, và còn ít nhất 4 ô đứng trước ô đóng: kiểu 5 trên bốn ô đầu của các ô đó. Ô đóng không nằm trong bốn ô này. Câu chưa đóng thì ô đóng không có, nên bốn ô đó là bốn ô đầu câu.
   - `k % 2 == 1`, `rise >= 3`, còn ít nhất 2 ô không phải ô đóng: kiểu 2 trên hai ô đó, cùng chỗ đặt của bước 3.
   - Không đủ chỗ thì câu về lưới nền. Không đổi kiểu 5 thành kiểu 2, cũng không đổi ngược lại.
5. Câu `danza` trên 3/4 hoặc 6/8, `n` chẵn, dài đúng 4 ô, và câu không `closes`: cả câu là kiểu 6. Câu `closes`, câu khác độ dài, và mọi chương 4/4: lưới nền. Kiểu 6 không có lưới 4/4.
6. Câu `castillo`, `n` chẵn:
   - `ctx.bpm > 72`: lưới nền.
   - `ctx.bpm <= 72` và `k % 2 == 0`: câu dài ít nhất 5 ô thì kiểu 7 trên năm ô đầu, các ô sau ngân một nốt. Câu dài 2, 3 hoặc 4 ô thì kiểu 8 trên hai ô đầu, để không cắt đứt 5 ô của câu đầu *Arada*. Câu dài 1 ô: lưới nền.
   - `ctx.bpm <= 72` và `k % 2 == 1`: câu dài ít nhất 2 ô thì kiểu 8 trên hai ô đầu, các ô sau ngân một nốt. Câu dài 1 ô: lưới nền.
7. Câu liền trước trong section đã dùng đúng kiểu vừa chọn: câu này về lưới nền.

Một câu chỉ có một kiểu. Ô không thuộc span của kiểu hát renderer nền của pattern. Trong một pattern, câu `n` lẻ là lưới nền. Câu đóng `sonatina` có thể đứng cạnh một câu đang hát kiểu khác, vì kiểu 3 không lấy số `n`. Bước 7 chặn hai câu sát nhau khi chúng chọn cùng một số kiểu, kể cả khi hai câu thuộc hai pattern. `castillo` trên 72 BPM, và mọi câu `castillo` có `n` lẻ, vẫn ngân một nốt, nên đoạn chậm vẫn có các câu ngân của *Castillos* xen giữa kiểu 7 và kiểu 8. Hai đỉnh `volatile` không ở chung một câu: kiểu 2 là cụm ngắn, kiểu 5 là vòm bốn ô, và cửa trên không gọi cả hai.

Ví dụ một đoạn `sonatina`. Câu 6 là câu đóng.

| Câu | Dài | `rise` | Kết quả |
|---|---|---|---|
| 1 | 6 | 1 | `k = 0`. Kiểu 4 trên hai ô đầu. Bốn ô sau là `sonatina` |
| 2 | 4 | 5 | `n` lẻ. Cả câu lưới nền |
| 3 | 4 | 5 | `k = 1`. Kiểu 2 trên hai ô giữa. Hai ô rìa là lưới nền |
| 4 | 5 | 0 | `n` lẻ. Lưới nền |
| 5 | 4 | 4 | `k = 2`. Kiểu 1 ở ô thứ hai. Ba ô kia là lưới nền |
| 6, `closes` | 4 | 2 | Kiểu 3 trên ba ô cuối. Ô đầu là lưới nền |

Đoạn `fandanguillo` dài 6, 4, 5 ô, `rise` đều trên 3, chưa đóng: câu 1 kiểu 5 trên bốn ô đầu, câu 2 lưới nền, câu 3 kiểu 2. Cùng câu đầu nếu `closes` thì kiểu 5 ở chỉ số 0–3, chỉ số 4 ở lại lưới nền, chỉ số 5 là ô thở. Đoạn `danza` 6/8 toàn câu dài 4 và chưa đóng: câu `n` chẵn là kiểu 6, câu `n` lẻ là lưới `danza`. Đoạn `castillo` ở 66 BPM, các câu dài 6, 4 và 4: câu 1 (`k = 0`) là 5 ô kiểu 7 rồi 1 ô ngân, câu 2 (`n = 1`) ngân một nốt, câu 3 (`k = 1`) là 2 ô kiểu 8 rồi 2 ô ngân. Câu đầu mà chỉ dài 3 ô thì nhận 2 ô kiểu 8 thay vì cắt kiểu 7. Cùng đoạn đó ở 96 BPM thì cả ba câu ngân một nốt.

#### Việc mọi kiểu cùng tuân

Phách mạnh của meter: 4/4 là móc đơn 0 và 4. 6/8 là móc đơn 0 và 3. 3/4 là móc đơn 0. Móc đơn 4 của 3/4 là phách yếu. Engine không có nhịp 3/8. Một ô 3/4 hoặc 6/8 là 6 móc đơn. Một ô 4/4 là 8 móc đơn. Một chu kỳ 6 móc kép bằng 3 móc đơn.

Ở các cột gảy thường (hợp âm khối và rải), mỗi voice tối đa một nốt và tối đa ba tiếng cùng vang. Riêng hợp âm dải (`rasgueado`) mở ở móc đơn 0 của `torroba` được phép quạt 3–6 dây theo hai loại dưới đây (`bass` voice 3 có thể gảy 1–2 dây trầm `<= 53`, `support` voice 2 có thể gảy 1–3 dây trung `>= 50` và `< lead`, `lead` voice 1 giữ 1 nốt đỉnh). Lực là `lead > bass > support`, mỗi cặp cách ít nhất 2. Cao độ khi `lead` đang hát: `lead` cao nhất, mọi nốt `support` nằm giữa (`max(bass) < min(support) <= max(support) < lead`), `bass` thấp nhất. Khi `lead` nghỉ, `support` vẫn ở trên `bass`.

**Hợp âm dải (rasgueado) — phân loại theo mật độ dây và lực quạt, đối chiếu với hợp âm khối:**

- **Hai loại rasgueado của Torroba (không dùng loại 3 kết bài > 5 nốt chậm ở `outro`):**
  1. **Loại 1 — Rasgueado mạnh, tạo không khí / báo hiệu mở câu (5–6 dây, khi thế bấm hẹp tối thiểu 4 dây):**
     - **Vị trí:** **Kiểu 5, ô 1, móc đơn 0** (mở vòm `ff` *Fandanguillo*), **lưới `fandanguillo`, móc đơn 0** (phách dập đầu ô điệu vũ), và **Kiểu 2, ô 1, móc đơn 0 khi `pattern == "fandanguillo"`**.
     - **Mật độ dây và xếp bè (`_rasgueado_voicing(..., max_notes=6)`):** Quạt tối đa **5–6 dây** hợp lệ trong cùng một thế tay (`_playable` đúng, độ giãn các ngăn bấm `> 0` không quá 5 ngăn, cao độ tăng nghiêm ngặt theo thứ tự dây `6 -> 1`, nốt dây cao nhất là `lead`). Phân bổ vào 3 bè tại các mốc `0.0`, `1/12`, `2/12`:
       - `voice 3` (`bass`, tại `beat = 0.0`, dài `0.5`): 1–2 nốt trầm của thế bấm có cao độ vang `<= 53` (ưu tiên có mặt bậc gốc hợp âm ở dây thấp nhất).
       - `voice 2` (`support`, tại `beat = 1/12`, dài `5/12`): 2–3 nốt trung của thế bấm có cao độ vang `>= 50` và nằm hẳn giữa `max(bass)` với `lead`.
       - `voice 1` (`lead`, tại `beat = 2/12`, dài `4/12`): 1 nốt giai điệu `_melody_at` trên đỉnh.
     - **Cường độ:** Đánh dứt khoát báo hiệu — `lead` viết `max(_note_velocity, 68)`, `accent=True`, bậc 0; `bass` bậc 0 trên mức bass (`60`); `support` bậc 0 trên mức support (`56`).
  2. **Loại 2 — Rasgueado nhẹ, vuốt mềm mở mô-típ hoặc đỉnh trữ tình (3–4 dây):**
     - **Vị trí:** **Kiểu 2, ô 1, móc đơn 0 khi `pattern == "sonatina"`**, **Kiểu 3, ô mô-típ, móc đơn 0** (*Sonatina* câu đóng), và **Kiểu 7, ô 5, móc đơn 0** (đỉnh trữ tình *Arada* ngân trên dòng chạy trầm).
     - **Mật độ dây và xếp bè (`_rasgueado_voicing(..., max_notes=4)`):** Quạt **3–4 dây** hợp lệ trong một thế tay (`_playable` đúng):
       - `voice 3` (`bass`, tại `beat = 0.0`, dài `0.5`): 1 nốt trầm (`<= 53`).
       - `voice 2` (`support`, tại `beat = 1/12`, dài `5/12`): 1–2 nốt trung (`>= 50`, nằm giữa `bass` và `lead`).
       - `voice 1` (`lead`, tại `beat = 2/12`): 1 nốt `_melody_at` trên đỉnh (cắt tại `0.5` tức dài `4/12` ở Kiểu 2 và Kiểu 3; ngân hết ô `epb * 0.5 - 2/12` ở Kiểu 7 ô 5).
     - **Cường độ làm mềm:** Ở **Kiểu 2 (`sonatina`)** và **Kiểu 3 (mô-típ)**: `lead` giữ mức viết `sonatina` (`64` trên câu phẳng), bậc 0, **không gắn `accent`** (`accent=False` để tiếng vuốt mềm, không bật gắt như Loại 1), đồng thời `bass` và `support` **hạ 1 bậc vi mô (`steps = 1`)** từ giường `60 / 56` xuống **`58 / 54`**. Ở **Kiểu 7 ô 5**: `lead` ngân dài làm trụ đỉnh câu nên giữ `accent=True`, bậc 0 (`64`), còn `bass` và `support` vuốt nhẹ bên dưới ở **bậc −1 (`58 / 54`)** rồi nhường cho 7 móc đơn chạy trầm.
  3. **Trường hợp suy biến (ít dây):** Nếu thế bấm với `lead` chỉ cho phép 2 bè có tiếng (khi thiếu `support` hoặc thiếu `bass`) thì hai bè đó đứng ở `0.0` và `1/12` (`duration_beats` lần lượt `0.5` và `T_1 - 1/12`); nếu chỉ còn `lead` một mình thì đứng tại `0.0`. Các hợp âm ở cột khối giữ nguyên đánh chập tại cùng một `beat`.
- **Cổng `assert_playable` cho hợp âm dải nhiều dây:** Với `profile == "torroba"` trong cửa sổ quạt đầu ô (`beat < 0.25`), `assert_playable` cho phép tối đa **6 nốt đồng thời** (Loại 1 tối đa 2 nốt `voice 3`, 3 nốt `voice 2`, 1 nốt `voice 1`; Loại 2 tối đa 1 nốt `voice 3`, 2 nốt `voice 2`, 1 nốt `voice 1`), miễn là mọi nốt cùng thoả `_playable` (mỗi nốt một dây riêng trong 6 dây, độ giãn ngăn bấm `<= 5`) và giữ đúng thứ tự vùng `max(lows) < min(mids) <= max(mids) < min(highs)`. Từ `beat >= 0.25` trở đi và trên mọi hợp âm khối, trần 3 tiếng (mỗi voice 1 nốt) giữ nguyên.
- **Lưới khắc `divisions = 12`, tuplet khép kín trong MusicXML và đồng bộ thời gian trên Musicalize:**
  - Chương nào có ít nhất một hợp âm dải (`_needs_twelfths`) thì `render_patterned_voices` bật `divisions = 12` cho cả chương, cùng cửa với `etude11`.
  - **Không dùng `<forward>` hay tuplet hở làm MuseScore báo lỗi `Voice too long` (exit 40) trên `.mscz`:** Khi một tuplet không khép trọn phách đơn (6 đơn vị ở `divisions = 12`) hoặc dùng tỉ lệ lẻ kiểu `24:23` / `18:17`, MuseScore làm tròn lệch tick nội bộ (`3197/3072`), từ chối xuất `.mscz -> .wav` và làm lệch đồng hồ:
    - Ở `voice 3` (`bass` tại `0.0`, dài `0.5` = 6 đơn vị): xuất nốt `<type>eighth</type>` thường (`duration = 6`, không `<time-modification>`); nếu Loại 1 có 2 nốt bass thì nốt thứ hai gắn `<chord/>`.
    - Ở `voice 2` (`support` tại `1/12`, dài `5/12` = 5 đơn vị): viết trọn một chùm ba móc đôi (`3:2` trên `normal-type = 32nd`) gồm **dấu lặng móc đôi** (`<rest/>`, `duration = 1`, `type = 32nd`, `3:2`) + **nốt/hợp âm móc đôi** (`duration = 1`, `type = 32nd`, `3:2`, `tie="start"`) buộc (`tie`) sang **nốt/hợp âm móc đơn** (`duration = 4`, `type = eighth`, `3:2`, `tie="stop"`). Khi `support` có 2–3 nốt (chập cùng `beat = 1/12`), cả phần đầu (`duration = 1`) lẫn phần đuôi (`duration = 4`) đều xuất đủ các nốt phụ có `<chord/>` và `<tie>` tương ứng để nghe đúng một lần quạt.
    - Ở `voice 1` (`lead` tại `2/12`, dài `4/12` = 4 đơn vị, hoặc `5/12` khi thiếu 1 bè): khi dài 4 đơn vị, viết trọn một chùm ba móc kép (`3:2` trên `normal-type = 16th`) gồm **dấu lặng móc kép** (`duration = 2`, `type = 16th`, `3:2`) + **nốt móc đơn** (`duration = 4`, `type = eighth`, `3:2`). Khi dài 5 đơn vị (quạt 2 bè tại `1/12`), dùng cùng cách viết chùm ba móc đôi buộc (`1 + 1 + 4`) như `voice 2`.
    - Ở `voice 1` ngân cả ô của **Kiểu 7 ô 5** (`duration = epb * 6 - 2`, hoặc `epb * 6 - 1` khi 2 bè): tách phần đầu trong móc đơn 0 thành tuplet `3:2` khép kín (với `beat = 2/12`: dấu lặng `16th` `2` đơn vị + nốt `eighth` `4` đơn vị có `tie="start"`; với `beat = 1/12`: dấu lặng `32nd` `1` đơn vị + nốt `32nd` `1` đơn vị buộc sang `eighth` `4` đơn vị có `tie="start"`), rồi **buộc (`tie`) sang các nốt chuẩn không tuplet** phủ phần còn lại của ô (`epb * 6 - 6` đơn vị: trên 4/4 là `half` chấm dôi `36` đơn vị buộc sang `eighth` `6` đơn vị; trên 3/4 và 6/8 là `half` `24` đơn vị buộc sang `eighth` `6` đơn vị). Cách viết này giữ nguyên đúng 1 lần gảy tại `2/12` (hoặc `1/12`), ngân liền tới đúng vạch ô (`tick = bar_beats * 480`), và MuseScore xuất `.mscz -> .wav/.mid` với mã `0` mà không cần fallback.
  - **Đồng bộ đồng hồ `<sound tempo>` giữa nhạc và chart trên Musicalize:** MuseScore bỏ qua `<offset sound="yes">` âm khi `<direction>` đặt sau một nốt dài (như nốt tròn của `castillo` hoặc nốt ngân cả ô của Kiểu 7 ô 5), làm mất nửa sau đường cong `humanize` và khiến thời lượng file lệch khỏi `piece_seconds` (`mapDurationSec`). Trong `musicxml.py`, mọi `TempoEvent` rơi vào giữa một nốt dài không được phát sau nốt đó với `<offset>` âm: phát `<direction><sound tempo="..."/></direction>` (không `<offset>`) trên một luồng con trỏ `<backup>` / `<forward>` đặt đúng tại đơn vị `int(round(event.beat * score.divisions))` của ô nhịp, rồi trả con trỏ về cuối ô trước khi sang bè tiếp theo. Ngoài ra, trên Musicalize (`ReplayRoom.tsx`, `seek.ts`), các chương dài (`1W`, `1M`, `3M`, `1Y`) cũng phải tách đồng hồ bản đồ nến (`mapDurationSec`, tức độ dài viết của chương) khỏi độ dài file thực tế có đuôi ngân ~3 giây của MuseScore, giống hệt `1D`, để playhead trên chart và thanh kéo không trượt khỏi tiếng đàn.
- **Đặc tính độc chiếm tay phải khi đang quạt dây:** Trong khoảng thời gian bàn tay đang quạt qua dây (`0.0 .. 0.25` của phách quạt), mọi bè khác phải im lặng — không có câu rải phụ, không có nốt điểm nền hay nốt giữ từ ô trước chọc vào cửa sổ quạt. Khi ngón tay đã dừng ở nốt đỉnh `lead` và trả tay tại mốc `0.5`, các móc tiếp theo của ô mới bắt đầu hát.
- **Phân định chỗ dải (Loại 1 / Loại 2) và chỗ khối:**

| Loại hợp âm | Vị trí áp dụng | Số dây & cách đánh |
|---|---|---|
| **Hợp âm dải Loại 1 (rasgueado mạnh, báo hiệu)** | • **Kiểu 5, ô 1, móc đơn 0** (mở vòm `ff` trước 4 móc đơn bass `staccato`)<br>• **Lưới `fandanguillo`, móc đơn 0** (phách đầu dập quạt của điệu Fandanguillo)<br>• **Kiểu 2, ô 1, móc đơn 0** khi câu là `fandanguillo` | **5–6 dây** (tối thiểu 4 dây khi thế bấm hẹp): `bass` (1–2 dây) tại `0.0` $\rightarrow$ `support` (2–3 dây) tại `1/12` $\rightarrow$ `lead` (1 dây) tại `2/12`; `lead` viết `max(ordinary, 68)`, `accent=True`; giường `60 / 56` bậc 0 |
| **Hợp âm dải Loại 2 (rasgueado nhẹ, làm mềm)** | • **Kiểu 2, ô 1, móc đơn 0** khi câu là `sonatina` (mở cụm lặp trong *Sonatina*)<br>• **Kiểu 3, ô mô-típ, móc đơn 0** (mở mô-típ trước nhịp gõ móc kép)<br>• **Kiểu 7, ô 5, móc đơn 0** (đỉnh trữ tình *Arada* mở đầu ô kết trước dòng chạy trầm) | **3–4 dây**: `bass` (1 dây) tại `0.0` $\rightarrow$ `support` (1–2 dây) tại `1/12` $\rightarrow$ `lead` (1 dây) tại `2/12`. Ở Kiểu 2 (`sonatina`) và Kiểu 3: `lead` viết `64`, **không `accent`**, `bass`/`support` hạ 1 bậc (`58 / 54`). Ở Kiểu 7 ô 5: `lead` giữ cả ô (`accent=True`, `64`), `bass`/`support` hạ 1 bậc (`58 / 54`) |
| **Hợp âm khối (gảy chập)** | • **Kiểu 2, ô 2** (chuỗi hợp âm móc đơn đi theo giai điệu)<br>• **Kiểu 4, ô gọi** (móc 0 nền và các hợp âm cuối ô)<br>• **Kiểu 5, ô 4** (các phách nốt đen / chấm dôi kết vòm)<br>• **Kiểu 6** (hợp âm ngân đầu nửa A và hợp âm staccato đầu nửa B)<br>• **Kiểu 7, ô 1, 2, 3, 4** (trụ chấm dôi có rải móc đơn bên dưới, quãng đôi song song, hai trụ đối xứng)<br>• **Kiểu 8, ô 1, 2** (hợp âm chấm dôi 2 tiếng nhường `Arm. 8` và trụ nửa ô)<br>• **Lưới `danza`** và **khung `intro`/`outro`** (hợp âm `staccato` nảy gọn đầu nhóm nhịp và hợp âm mở/đóng khung) | Ba tiếng (hoặc hai tiếng) vào cùng một thời điểm `beat` |

Bậc vi mô là số lần `_MICRO = 2`, hạ sau vận tốc viết và sau extra cả ô, cùng chỗ contour của Galop. Bậc của `lead` đi qua `_micro_fits`. Hết chỗ thì bậc rút lại, không chọc qua bass. Chùm nào mục của kiểu đã giao một bậc thì các nốt lặp trong chùm đó lấy bậc ngắn nhất còn sống. Ba chỗ cố ý lệch bậc trên cùng cao độ thì giữ đúng bậc đã viết: kiểu 3, móc 1–2 là −2, −2, −1; kiểu 5 ô 3 là −2, −2, −1, rồi 0 ở nốt thứ tư; chùm đầu kiểu 6 là 0, −2, −2. `_micro_fits` rút từng nốt lead khi nốt đó chạm bass, và không kéo nốt bên cạnh xuống theo. Trên câu phẳng band `mf`, `_under_lead(64)` ra bass 60, support 56. `sonatina` viết lead 64, nên lead chỉ hạ được 1 bậc khi bass 60 còn vang (`62 >= 60 + 2`). `fandanguillo` và `danza` viết phách mạnh `max(_note_velocity, 68)`, nên lead hạ được 3 bậc (`62 >= 60 + 2`) khi bass đó còn vang. Lead hát một mình thì hạ đúng bậc trong bảng, sàn 40. Extra cả ô cộng cùng một số cho cả ô, nên khoảng giữa lead và bass không mở lại.

Bass của hợp âm mở là một móc đơn (`duration_beats = 0.5`), trừ pedal được nêu tên ở kiểu 1, kiểu 5, kiểu 6 và ô 3 của kiểu 7. Pedal thả ở vạch ô khi ô sau đánh voice 3 ngay móc đơn 0, và thả ở vạch ô khi `ctx.chord` đổi. Không khóa Viterbi để giữ một hợp âm nhiều ô. Ô sau là kiểu 1 thì bass kiểu 1 được ngân tiếp tới `s3` của chu kỳ sau, vì chu kỳ đó không đánh bass ở móc đơn 0. Ô sau là lưới nền, kiểu 2, kiểu 3 (ô mô-típ), kiểu 4, kiểu 5 ô 1, kiểu 6, hoặc kiểu 7 thì cắt ở vạch ô: các lưới đó đều đánh bass ở móc đầu.

Extra cả ô của pattern vẫn một mức cho cả ô, kể cả ô thuộc kiểu. Nốt nào `_harmonic_velocity` trả 48 thì nốt đó không cộng extra. Ô thuộc kiểu nằm trong `skip_bars` của `_slur()`, và `apply_sonatina_downbeats` không trồng nốt lấy đà lên các ô đó. Kiểu tự viết slur của nó. Ô lưới nền `sonatina` giữ cửa slur của mục 1.

Mục 1 vẫn làm mỏng `support` trên offset đóng của ô lưới nền, và bed `p` chỉ trên tiếng đệm của các offset đó. Mục 1 không xóa `lead` của một kiểu, và không viết lại vận tốc `lead` mà kiểu đã đặt. Kiểu 3 vốn đã nghỉ `support`.

Cao độ:

- `lead` di chuyển đọc `_melody_at` của móc đó, sau khi đã về hòa âm.
- `support` và `bass` là nốt của `ctx.chord(bar)`, trừ các ô 1–3 của kiểu 5 và ô 5 của kiểu 7, nơi voice 3 hát câu trầm trong vùng MIDI 40–52.
- Lặp cao độ do kiểu bịa ra chỉ ở các chỗ trong bảng dưới. `_melody_at` trả cùng một cao độ hai lần thì cứ đánh, vì đó là giá.
- Nốt thêu là `_walk` một bậc thang, slur về đúng `_melody_at` nó thêu. Cả nhóm phải qua `_assert_scale_positions`. Không vừa thế tay thì cặp slur thành hai tiếng của chính `_melody_at` đó.

| Chỗ được lặp cao độ | Tiếng |
|---|---|
| Kiểu 2, mỗi chùm 4 móc kép | Một nốt hợp âm, chọn một lần cho ô |
| Kiểu 3, nhịp gõ ở móc đơn 1–2 | Ba tiếng, cao độ `_melody_at` của móc đơn 1 |
| Kiểu 4, hai móc kép của móc đơn 1 | `_melody_at` của móc đơn 1, hai lần |
| Kiểu 5 ô 1, ba móc đơn trầm đầu của chùm bốn | Cùng cao độ đã hạ quãng 8. Móc thứ tư bước |
| Kiểu 5 ô 3, ba móc đơn `lead` đầu của chùm bốn | `_melody_at` của móc đầu chùm. Móc thứ tư bước |
| Kiểu 6, chùm 3 móc đơn đầu tiên | `_melody_at` của móc đầu, ba lần |
| Kiểu 7 ô 3, các cặp móc đơn đánh đôi | Hai tiếng trong một cặp lấy `_melody_at` của móc chẵn. Đuôi móc kép lướt là một bậc trên |
| Kiểu 8 ô 2, hai móc đơn đầu của chùm ba (`base + 1` và `base + 2`) | `_melody_at` của `base + 1`, đánh hai lần trước khi slur sang `base + 3` |

`s4 = s2` của kiểu 1 là nốt hợp âm của `support` nhắc lại, không phải một đường giá thứ hai.

### 4.1. Kiểu 1 — Rải 6 móc kép, bass thứ tư ngân tới chu kỳ sau

Nguồn: *Sonatina* I, đoạn chặn `VIII` sang `VI`. Mỗi chùm 6 móc kép đi hình chữ V. `s0` là đỉnh, có nhấn. `s1` rồi `s2` là hai nốt hợp âm đi xuống. `s3` là bass, có nhấn, nối sang đầu chu kỳ sau. `s4 = s2`, `s5 = s1`.

Một chu kỳ là 6 móc kép, tức 3 móc đơn. 3/4 và 6/8 chạy hai chu kỳ: móc đơn 0–2, rồi móc đơn 3–5. 4/4 chạy hai chu kỳ đó trên móc đơn 0–2 và 3–5. Móc đơn 6 và 7 là hai nốt `support`, mỗi móc một tiếng, nốt hợp âm dưới vùng `lead`. Không có `lead` và không có bass mới ở hai móc đó.

- `s0`, voice 1: `_melody_at` của móc đơn chứa nó, `accent=True`, bậc 0. Mỗi `s0` đều nhấn, kể cả `s0` thứ hai trong ô. Trên 3/4, `s0` đó không rơi vào phách mạnh của meter.
- `s1`, `s2`, voice 2: hai nốt hợp âm nằm dưới `lead` và trên bass, `s1` cao hơn `s2`. Thiếu nốt thì móc đó nghỉ.
- `s3`, voice 3: `_torroba_bass`, bậc 0 trên mức bass. Ngân tới `s3` sau, hoặc tới vạch ô khi ô sau đánh bass ở móc đơn 0.
- `s4`, `s5`: nhắc `s2`, `s1`.

| Tiếng | Bậc |
|---|---|
| `s0` lead | 0, có `accent` |
| `s1` support, rồi `s2` | −1, rồi −2 |
| `s3` bass | 0 trên mức bass |
| `s4` support, rồi `s5` | −2, rồi −1 |
| 4/4, support ở móc đơn 6 và 7 | −1, −1 |

Support bậc −2 từ 56 còn 52, dưới bass 60 và trên sàn 40.

### 4.2. Kiểu 2 — Rasgueado, bốn móc kép lặp, bass đáp, rồi hợp âm móc đơn

Nguồn: *Sonatina* I, đoạn `ff` chặn `V` và `II`, rồi hạ về `p`. Ba ô gốc, mỗi ô 3 móc đơn: ô A là hợp âm quạt rồi bốn móc kép cùng cao độ, ô B là một nốt trầm rồi bốn móc kép đó, ô C là hợp âm móc đơn theo giai điệu.

Engine gom thành hai ô trên mọi meter.

Ô 1 trên 3/4 và 6/8:

- Móc đơn 0: hợp âm dải rasgueado (`bass → support → lead` lệch `1/12` phách tại `0.0`, `1/12`, `2/12`, cùng cắt tại `0.5`), `lead` là `_melody_at`, bậc 0. Khi `pattern == "fandanguillo"` đây là **Loại 1 (5–6 dây)**: `lead` viết `max(_note_velocity, 68)`, `accent=True`, `bass`/`support` bậc 0 (`60 / 56`). Khi `pattern == "sonatina"` đây là **Loại 2 (3–4 dây)**: `lead` viết `64`, **không `accent`** (`accent=False`), `bass`/`support` hạ 1 bậc (`58 / 54`). Trong lúc quạt không có tiếng nào khác.
- Móc đơn 1–2: bốn móc kép, chỉ voice 1, một cao độ, mỗi nốt bậc −1.
- Móc đơn 3: chỉ voice 3, `_torroba_bass`, bậc 0 trên mức bass. Không có `lead`.
- Móc đơn 4–5: bốn móc kép, cùng cao độ với chùm trước, bậc −1.

Ô 1 trên 4/4 dùng cùng hai cụm, và có hai móc nghỉ vì 8 không chia hết cho hai nhóm 3. Móc đơn 0 là hợp âm dải rasgueado (Loại 1 trên `fandanguillo`, Loại 2 trên `sonatina`). Móc đơn 1–2 là bốn móc kép. Móc đơn 3 nghỉ. Móc đơn 4 là bass. Móc đơn 5–6 là bốn móc kép. Móc đơn 7 nghỉ.

Ô 2, mọi meter: mỗi móc đơn một hợp âm khối ba tiếng, `duration_beats = 0.5`, `lead` là `_melody_at` của móc đó. Móc đơn trúng phách mạnh của meter giữ bậc 0. Móc đơn khác bậc −1.

Cao độ của chùm lặp chọn một lần cho ô 1: nốt hợp âm cao nhất còn thấp hơn `lead` của rasgueado. Không còn nốt nào thì dùng chính cao độ `lead` đó. Mi4 buông (dây 1, MIDI 64) chỉ được chọn khi nó là nốt hợp âm đó. MIDI 64 ở đây là cao độ, không phải vận tốc 64.

Vận tốc rasgueado là mức phách mạnh của pattern đang hát. `sonatina` câu phẳng viết `lead` 64 (Loại 2: không `accent`, giường `58 / 54`). `fandanguillo` viết ít nhất 68 (Loại 1: có `accent`, giường `60 / 56`). Không có sàn cứng 68 cho riêng kiểu này. Bốn móc kép hát sau khi bass của hợp âm đã hết, nên lead đứng một mình: bậc −1 từ 64 ra 62, từ 68 ra 66, và bốn nốt bằng nhau.

### 4.3. Kiểu 3 — Mô-típ, scale `pizz.`, rồi nốt ngân ở câu đóng

Nguồn: *Sonatina* I, đoạn `pizz.`, chặn `V`, `Arm.`, `con gracia`. Trên bản gốc, scale `pizz.` đứng trước mô-típ. Engine đảo lại để câu đi tới chỗ đóng: mô-típ, rồi scale, rồi nốt ngân.

Kiểu này là hậu tố của câu `sonatina` có `closes`.

- Câu dài ít nhất 3 ô: ba ô cuối là mô-típ, scale, ngân. Các ô trước là lưới nền.
- Câu dài 2 ô: scale, rồi ngân.
- Câu dài 1 ô: một ô ngân.

Ô mô-típ, móc đơn 0–5, thêm móc đơn 6–7 khi ô là 4/4:

- Móc đơn 0: hợp âm dải rasgueado **Loại 2 (3–4 dây)** (`bass → support → lead` lệch `1/12` phách, cùng cắt tại `0.5`), `lead` là `_melody_at`, bậc 0, **không `accent`** (`accent=False`), `bass` (1 dây) và `support` (1–2 dây) hạ 1 bậc (`58 / 54`).
- Móc đơn 1–2: hai móc kép rồi một móc đơn, cả ba cùng `_melody_at` của móc đơn 1. Hai móc kép bậc −2, móc đơn sau chúng bậc −1. Bass đã hết, lead đứng một mình, nên bậc −2 từ 64 còn 60.
- Móc đơn 3: hai móc kép slur, nốt thêu trên rồi `_melody_at`. Bậc −2, rồi −1.
- Móc đơn 4–5, và trên 4/4 là móc đơn 6–7: mỗi móc một tiếng `lead` đọc `_melody_at`. Móc trúng phách mạnh bậc 0. Móc khác bậc −1. Trên 4/4, móc đơn 4 là phách mạnh.

Ô scale: chỉ voice 1, `staccato=True`, một móc đơn mỗi móc. Cao độ đi từ một nốt hợp âm hoặc nốt thang ở dưới nốt đích, lên đúng `_melody_at` của móc cuối. Móc cuối là nốt giá. `support` và `bass` nghỉ. Mọi móc trừ móc cuối bậc −1. Móc cuối bậc 0. Một bậc, không dâng thêm 2 cho từng nốt: run dài làm vậy sẽ thành một chữ mới và nuốt nốt tới, cùng lý do tirata của Courante.

Ô ngân: voice 1 giữ `_melody_at` của móc đơn 0 suốt ô, `duration_beats = epb * 0.5`, không đánh lại. Vận tốc là `_harmonic_velocity`. Hàm đó trả 48 chỉ khi cao độ vang nằm trong `{52, 57, 62, 67, 71, 76, 79}` và nốt dài ít nhất hai phách đen. Cả ô luôn đủ dài. Không trùng nút thì giữ vận tốc `sonatina` thường và vẫn nhận extra cả ô. Nốt 48 không cộng extra, bậc 0, không hạ thêm. `support` nghỉ. `bass` là `_torroba_bass` một móc đơn ở móc 0, bậc −1 trên mức bass. Không thêm một dây buông ngoài nốt bass đó.

### 4.4. Kiểu 4 — Đối đáp hai ô mở đầu *Sonatina* I

Nguồn: *Sonatina* I, ô 1–4, *Allegretto*, 3/4, `mf`. Ô lẻ là câu gọi: nửa phách đầu bè cao nghỉ, rồi mô-típ móc kép, rồi hai hợp âm cuối ô. Ô chẵn là câu đáp: bè cao ngân một nốt, bè trung nhại tiết tấu, bass ở móc đầu và móc cuối.

Hai ô này là hai ô đầu của câu `sonatina` chưa đóng dài ít nhất 4 ô. Các ô sau là lưới nền. `apply_sonatina_downbeats` không chạy trên hai ô này. `lead` không hát móc đơn 0. Đó là ngoại lệ của luật “mỗi phách mạnh là `_melody_at`”, và chỉ hai ô này.

Ô gọi trên 3/4 và 6/8:

- Móc đơn 0: `bass` và `support`, `lead` nghỉ. Cả hai bậc 0. Bass dài một móc đơn.
- Móc đơn 1: hai móc kép cùng `_melody_at` của móc đó, bậc −1 và −1.
- Móc đơn 2: một móc đơn, `_melody_at`, bậc −1.
- Móc đơn 3: hai móc kép slur, nốt thêu trên rồi về `_melody_at` của móc đơn 2. Trên 3/4 cả hai bậc −1. Trên 6/8 móc đơn 3 là phách mạnh: nốt thêu bậc −1, nốt giải bậc 0.
- Móc đơn 4 và 5: hợp âm, `lead` là `_melody_at` của móc, bậc 0 trên mức phách yếu. Bass chỉ đánh ở móc đơn 5. Bass đó lấy mức bass phách yếu, thấp hơn bass phách mạnh đúng 4, câu phẳng ra 56, không hạ thêm. Support móc 4 giữ mức support 56. Support móc 5 hạ một bậc, ra 54, để còn `bass (56) > support (54)`.

Ô gọi trên 4/4: móc đơn 0–3 giống trên, cặp slur ở móc đơn 3 bậc −1 và −1 vì móc đó yếu. Móc đơn 4–7 mỗi móc một hợp âm. Bass ở móc đơn 4, bậc 0, mức 60. Bass ở móc đơn 7, mức yếu 56. Support ở móc 7 hạ một bậc, ra 54. Support ở móc 4, 5 và 6 giữ mức 56: móc 4 có bass 60, móc 5 và 6 không có bass. `lead` móc đơn 4 bậc 0. `lead` móc đơn 5, 6, 7 bậc −1.

Ô đáp, mọi meter:

- `lead`: một nốt, `_melody_at` của móc đơn 0, dài cả ô, bậc 0, không đánh lại.
- `support` nhại trên móc đơn 1, 2, 3, rồi một nốt đen ở móc đơn 4 (`duration_beats = 1.0`, phủ móc đơn 4–5). Nhịp là hai móc kép slur, một móc đơn, hai móc kép slur, một nốt đen. Cao độ là hai nốt thang liền bậc, dưới `lead`, không quá 65, trên bass. Bậc −1 trên mức support. Trên 4/4, móc đơn 6 và 7 `support` nghỉ.
- `bass`: móc đơn 0, bậc 0, dài một móc đơn. Móc đơn cuối ô, mức bass yếu, không hạ thêm.

### 4.5. Kiểu 5 — Rasgueado, giá ở bè trầm, rồi giao lên bè cao

Nguồn: *Suite Castellana* I, *Fandanguillo*, đoạn `ff` / `fff` chặn `V`, `II`, `VII`, nhịp 3/4. Ba pha của bản gốc là hợp âm quạt với bốn móc đơn staccato ở trầm, rồi giá chạy trên dây trầm, rồi bốn móc đơn giao lên cao và sáu nốt đen hợp âm.

Chỉ `fandanguillo`. Bốn ô, trên cả 4/4, 3/4 và 6/8. Bản gốc có hai hình cho pha trầm: nốt đen đi bậc, và mô-típ lướt. Engine giữ mô-típ lướt cho một ô, vì nốt cuối của nó là pedal sang ô giao. Sáu nốt đen của bản gốc là hai ô 3/4. Engine để một ô hợp âm, để cụm còn bốn ô.

Giá khi hát ở voice 3: lấy `_melody_at`, trừ 12 cho tới khi cao độ không quá 52. Tụt dưới 40 thì dùng `_torroba_bass`. Sau đó kéo về nốt hợp âm gần nhất trong 40–52. Hai nốt cách đều thì lấy nốt thấp hơn. Hợp âm không có nốt trong vùng thì `_torroba_bass`.

Ô 1:

- Móc đơn 0: hợp âm dải rasgueado **Loại 1 (5–6 dây)** (`bass → support → lead` lệch `1/12` phách, cùng cắt tại `0.5`), `lead` là `_melody_at`, viết `max(_note_velocity, 68)`, `accent=True`, bậc 0; `bass` (1–2 dây `<= 53`) bậc 0 (`60`), `support` (2–3 dây `>= 50`) bậc 0 (`56`).
- Móc 1, 2, 3: chỉ voice 3, mỗi tiếng một móc đơn, `staccato=True`, cùng cao độ đã hạ vùng. Bậc −2, −2, −2, ra 56.
- Móc 4: voice 3 bước sang giá của móc đó, bậc −1, ra 58. Nốt này không staccato. Nó ngân hết phần còn lại của ô và thả ở vạch ô, vì ô 2 đánh bass ở móc 0. Trên 3/4 và 6/8 đó là móc 4–5, `duration_beats = 1.0`. Trên 4/4 đó là móc 4–7, `duration_beats = 2.0`.

Ô 2, chỉ voice 3. `lead` và `support` nghỉ.

- 3/4 và 6/8: móc đơn 0 là một móc đơn bass, bậc 0. Móc đơn 1 là hai móc kép slur, bậc −2 rồi −1. Móc đơn 2 và 3 là hai móc đơn, mỗi nốt bậc −1. Pedal bắt đầu ở móc 4, bậc −1, ra 58. Hợp âm ô 3 không đổi thì nốt này không đánh lại và ngân tới hết ô 3, `duration_beats = 4.0`. Hợp âm đổi thì thả ở vạch ô, `duration_beats = 1.0`.
- 4/4: cùng hình trên móc đơn 0–3. Pedal bắt đầu ở móc 4, bậc −1, ra 58. Hợp âm ô 3 không đổi thì cùng nốt đó phủ móc 4–7 của ô 2 và hết ô 3, `duration_beats = 6.0`. Hợp âm đổi thì thả ở vạch ô, phủ móc 4–7, `duration_beats = 2.0`.

Pedal viết 58 để ô 3 còn chỗ. Lead 64 vẫn cao hơn 58 đúng 6. Ô 3 không đánh bass mới.

Ô 3: pedal tiếp tục, không đánh bass mới, `support` nghỉ. Bốn móc đơn `lead` viết 68 kể cả khi không rơi phách mạnh, bậc −2, −2, −1, 0, ra 64, 64, 66, 68. Ba nốt đầu cùng `_melody_at` của móc đầu chùm. Nốt thứ tư đọc `_melody_at` của móc nó. Trên 3/4 và 6/8, bốn nốt nằm ở móc đơn 2–5. Móc đơn 0–1 chỉ có pedal. Trên 4/4 cũng vậy, và móc đơn 6–7 chỉ có pedal.

Ô 4: hợp âm khối ba tiếng trên từng phách của meter, nốt trên là `_melody_at`, viết `max(_note_velocity, 68)`, mọi phách bậc 0. Không khía trong phách. `cresc.` là extra cả ô. Câu phẳng có extra 0, nên các phách bằng nhau.

- 4/4: bốn nốt đen, `duration_beats = 1.0`, tại móc đơn 0, 2, 4, 6.
- 3/4: ba nốt đen tại móc đơn 0, 2, 4.
- 6/8: hai nốt chấm dôi, `duration_beats = 1.5`, tại móc đơn 0 và 3.

### 4.6. Kiểu 6 — Chùm ba trên hợp âm ngân, rồi bè trung đệm

Nguồn: *Suite Castellana* III, *Danza*, từ thế `VII` đầu đến trước thế `VII` sau. Bản gốc là 3/8, tám ô. Nửa A là bốn phách chấm, hợp âm ngân, bè cao chạy chùm ba. Nửa B là hợp âm đầu phách, ba móc kép đổ vào một nốt ngân, rồi bè trung và bè trầm đi.

Chỉ `danza`, chỉ 3/4 và 6/8, và chỉ khi mục 4.0 chọn câu đó: `n` chẵn, dài đúng 4 ô, chưa `closes`. Không viết lưới 4/4: `danza` không được chọn ở chương 4/4, và bốn chùm ba móc đơn không vừa một ô 8 móc. Trên 3/4 và 6/8, một chùm ba móc đơn là nửa ô. Nửa A là hai ô đầu, bốn chùm. Nửa B là hai ô sau.

Nửa A. Móc đơn 0 của ô đầu: `bass` bậc 0 và `support` bậc 0, `accent=True`, ngân suốt nửa A (`duration_beats = 6`). `lead` của móc đó là tiếng trên, viết 68, bậc 0, ra 68. Hai móc đơn sau của chùm đầu nhắc cùng cao độ, bậc −2, ra 64. Cả hai vẫn trên bass 60. Ba nốt này là chỗ lặp của kiểu. `ctx.chord` đổi ở ô thứ hai của nửa A thì cắt pedal ở vạch ô và đánh lại bass với support của hợp âm mới, cùng bậc.

Ba chùm sau: mỗi móc đơn là `_melody_at` của móc đó. Không bịa thêm nốt lặp. Móc đơn đầu của chùm bậc −1, ra 66. Hai móc sau bậc −2, ra 64. Chùm thứ ba của bốn chùm: móc giữa tách thành hai móc kép slur, nốt thêu trên rồi `_melody_at`, cả hai bậc −2. Chùm vẫn dài ba móc đơn.

Nửa B, tính móc đơn trong hai ô:

- Móc kép đầu của ô: `bass` và `support`, staccato, dài một móc kép, bậc 0. `lead` chưa vào.
- Ba móc kép `lead` chiếm nốt phần còn lại của móc đơn 0 và cả móc đơn 1. Chúng hát sau hợp âm, không đè lên bass. Viết 68, bậc −2, −2, −1, ra 64, 64, 66. Ba móc kép đi bậc xuống vào nốt đích. Không vừa thế tay thì cả ba đọc `_melody_at`.
- Nốt đích bắt đầu ở móc đơn 2, là `_melody_at` của móc đó, viết 68, bậc 0, ngân đến hết nửa B, không đánh lại. Móc kép cuối của chùm lướt vẫn dưới mức viết. Nốt đích mới là nốt ở mức viết. Allemande để mức viết trên móc kép thứ tư vì móc đó là nốt tới. Ở đây nốt tới là nốt ngân.
- Trong lúc `lead` ngân, đệm là nốt hợp âm, support không quá 65 và ở dưới `lead`:
  - Ô đầu của nửa B, móc đơn 2, 3, 4: support bậc −1, bass bậc −2, support bậc −1.
  - Móc đơn 5 của ô đó: nghỉ.
  - Ô sau, móc đơn 0: bass bậc −2. Móc đơn 1: nghỉ. Móc đơn 2: support bậc −1. Móc đơn 3–4: nghỉ.
  - Móc đơn 5 của ô sau: bass staccato, bậc −2, `support` nghỉ.

Bass bậc −2 từ 60 còn 56. Support bậc −1 từ 56 còn 54. Lead đang ngân ở 68. Thứ tự 68, rồi 56, rồi 54.

### 4.7. Kiểu 7 — Câu đầu *Arada* (*Suite Castellana* II, *Lento*, đủ 5 ô)

Nguồn: câu mở đầu chương II, 4/4, *Lento*, `p` rồi `mf` rồi `f`. Năm ô của bản gốc đi liền một vòm, kết ở dấu nhắc lại:

1. **Ô 1 (`p`, chặn `II`):** Nốt hát đen chấm dôi (`$A_4$` kèm bè trong `$A_3$`), bè dưới rải hai móc đơn (`$A_2 \rightarrow E_3 \rightarrow C\#_4$`). Nửa sau phách 2 là **chùm ba móc kép mordent có slur** (`$G\#_4\text{-}A_4\text{-}G\#_4$`) đổ vào phách 3 (`$[G\#_3, E_4]$`), rồi lại rải bass (`$A_2 \rightarrow E_3 \rightarrow B_3$`).
2. **Ô 2 (chặn `V`, `cresc.`):** Mở bằng hợp âm chặn `V` chấm dôi, bass dây 6 ngân, bè trung rải lên rồi lại **chùm ba móc kép mordent** (`$A_4\text{-}B_4\text{-}A_4$`) đổ về phách 3 (`$F\#_4$`). Cuối ô rải từ dây 5 buông (`$A_2 \rightarrow F\natural_3 \rightarrow A_3$`) đẩy lên nốt cao (`$A_4$`) ở móc đơn 7.
3. **Ô 3 (`mf`, quãng đôi trên bass ngân):** Bè trầm giữ dây 5 buông ngân cả ô. Bè trên đánh 4 cặp móc đơn song song với bè trong (quãng 6 / quãng 3), trong đó **móc chẵn của cặp 1 và cặp 3 có nốt láy trên (acciaccatura) kéo xuống** (`$D_5 \rightarrow E_5\text{p}D_5 \rightarrow C_5$`, rồi `$B_4 \rightarrow B_4 \rightarrow C_5\text{p}B_4 \rightarrow A_4$`).
4. **Ô 4 (hai hợp âm chấm dôi + bass đáp + láy rơi):** Hai nửa ô đối xứng. Mỗi nửa mở bằng một hợp âm đen chấm dôi (3 móc đơn), bè trầm nghỉ móc đầu rồi đáp hai móc đơn đi xuống (`$B_2 \rightarrow E_2$`), và ở móc đơn thứ tư bè cao đánh một móc đơn có **nốt láy từ bậc trên slur xuống** (`$B_4\text{p}A_4$`).
5. **Ô 5 (`f`, hợp âm dải phách 1 + 7 móc đơn chạy trầm kết câu):** Móc đơn 0 quạt hợp âm ba tiếng từ trầm lên cao, bè cao ngân giữ trên đầu, `bass` và `support` cắt tại `0.5` rồi từ móc đơn 1 bè trầm chạy liền **7 nốt móc đơn đi bậc ở dây 5** (`$F\natural_3 \rightarrow E_3 \rightarrow E\flat_3 \rightarrow D_3 \rightarrow C_3 \rightarrow B_2 \rightarrow E_3$`) về nốt kết ở móc đơn cuối.

#### Quy tắc ánh xạ vào Engine (đủ 5 ô)
Chỉ `castillo`, chỉ khi `ctx.bpm <= 72`, và câu dài ít nhất 5 ô. Bè cao cấu trúc đọc `_melody_at`. Bóng bè trung ở ô 3 dùng `_torroba_inner(..., allow_high=True)` để đi song song dưới `lead`. Mordent trên bản là bộ ba trong một móc đơn. Engine không viết bộ ba: `_note_type` không có `duration_beats = 1/6`, `_is_sixth` chỉ là sextuplet 6:4, và `_start16` lấy `floor(beat * 4)` nên hai nốt đầu của bộ ba rơi vào cùng một móc kép. `assert_playable` khi đó báo hai nốt ở bè cao. Chỗ mordent đánh hai móc kép thường, `duration_beats = 0.25`, nốt thêu rồi nốt chính, slur, nằm trọn trong móc đó. Nốt thứ ba trên bản là nốt giải ở móc sau.

- **Ô 1 (Canto + mordent hai móc kép + giải về phách sau):**
  - **4/4 (8 móc đơn):**
    - Móc 0: `lead` là `_melody_at`, nốt đen chấm dôi (`duration_beats = 1.5`, phủ móc 0–2), `accent=True`, bậc 0. `support` một móc đơn ở móc 0, bậc 0.
    - Móc 0–2 ở dưới: mỗi tiếng dài một móc đơn. `bass` ở móc 0 (bậc 0), `bass` ở móc 1 (bậc −1), `support` ở móc 2 (bậc −1). `support` ở móc 0 cũng chỉ dài một móc đơn, nên không đè `support` ở móc 2.
    - Móc 3: hai móc kép, chỉ `lead`, slur. Nốt đầu là `_walk` một bậc trên `_melody_at` của móc 4, bậc −2. Nốt sau là chính cao độ đó, bậc −1. Không vừa thế tay thì một móc đơn `_melody_at` của móc 4, bậc −1.
    - Móc 4 (phách 3): `lead` là `_melody_at`, nốt trắng (`duration_beats = 2.0`, phủ móc 4–7), bậc 0, kèm `support` móc 4 (bậc 0). Dưới đó `bass` đánh móc 4 (bậc −1), bước ở móc 5 (bậc −2), và `support` ở móc 6 (bậc −1). Nốt trắng giữ bậc 0. Cửa “lead hạ được 1 bậc khi bass 60 còn vang” không áp vào nó: bass móc 5 đã ở 56, extra cả ô tối đa +4 đưa bass đó lên 60 và lead lên 68, vẫn cách 8. Bass móc 4 sau extra là 62, vẫn dưới lead.
  - **3/4 và 6/8 (6 móc đơn):** Móc 0–2 là nốt đen chấm dôi của `lead` và rải một móc đơn mỗi tiếng, cùng bậc 4/4. Móc 3 là hai móc kép mordent. Móc 4–5 là nốt đen kết của `lead` (`_melody_at`) kèm `bass` móc 4 và `support` móc 5.
- **Ô 2 (Chặn hợp âm + mordent hai móc kép + rải đón sang Ô 3):**
  - **4/4:** Móc 0–3 cùng khung Ô 1. Mordent ở móc 3 vẫn là hai móc kép. Móc 4: `lead` là `_melody_at` dài 1.5 phách (móc 4–6), bậc −1. Dưới đó `bass` đánh móc 4 (bậc −1), bước ở móc 5 và 6 (bậc −1), mỗi tiếng một móc đơn. Móc 7: `lead` đọc `_melody_at` một móc đơn, bậc 0, đón vào Ô 3.
  - **3/4 và 6/8:** Móc 0–2 hợp âm chấm dôi và rải. Móc 3 là hai móc kép mordent. Móc 4 là `lead` một móc đơn (bậc −1) kèm `bass`. Móc 5 là `lead` một móc đơn (`_melody_at`, bậc 0) đón vào Ô 3.
- **Ô 3 (Cặp móc đơn song song + đuôi láy + bass pedal):**
  - `bass`: một nốt `_torroba_bass` ở móc 0, ngân trọn ô (`duration_beats = epb * 0.5`), bậc 0.
  - **4/4:** Bốn cặp móc đơn `(0,1), (2,3), (4,5), (6,7)`. Trong mỗi cặp `(2m, 2m+1)`:
    - Móc `2m`: `lead` lấy `p = _melody_at(origin + 2m)`, kèm `support` là quãng 3/6 ngay dưới `p`. Móc 0 và 4 bậc 0 (`accent=True`), móc 2 và 6 bậc −1.
    - Móc `2m+1` của cặp 0 và cặp 2 (tức móc 1 và móc 5): tách thành **2 móc kép slur** (`duration_beats = 0.25`) trên `lead`: nốt láy bậc trên `_walk(p, +1)` rồi kéo về `p`, bậc `−1, −1`, trong khi `support` giữ 1 móc đơn dưới `p`. Không vừa thế tay thì `lead` giữ 1 móc đơn `p`.
    - Móc `2m+1` của cặp 1 và cặp 3 (móc 3 và móc 7): 1 móc đơn `_melody_at`, bậc −1, kèm `support`.
  - **3/4 và 6/8:** Ba cặp `(0,1), (2,3), (4,5)`. Cặp 0 và cặp 2 có 2 móc kép láy slur ở móc 1 và móc 5; cặp 1 giữ móc đơn.
- **Ô 4 (Hợp âm chấm dôi + 2 bass đi xuống + móc đơn có láy):**
  - **4/4:** Hai nửa ô giống nhau tại `base = 0` và `base = 4`:
    - `base`: hợp âm (`lead` = `_melody_at` chấm dôi `duration_beats = 1.5` phủ `base..base+2`, `support` chấm dôi `1.5`), bậc 0 tại `0` (`accent=True`) và bậc −1 tại `4`. `bass` nghỉ ở `base`.
    - `base + 1` và `base + 2`: `bass` đánh 2 móc đơn đi xuống (`bass_high -> bass_low` trong hợp âm, vùng 40–52), bậc `−1, −2`.
    - `base + 3` (móc 3 và móc 7): `lead` đánh **2 móc kép slur** (`0.25 + 0.25`): nốt láy trên `_walk(target, +1)` rơi xuống `target = _melody_at(origin + base + 3)`, bậc `−2, −1`. Không vừa thế tay thì đánh 1 móc đơn `target` bậc −1.
  - **3/4 và 6/8:** Móc 0–3 chạy đúng một chu kỳ `[hợp âm chấm dôi móc 0..2 + 2 bass ở móc 1..2 + 2 móc kép láy ở móc 3]`. Móc 4 là hợp âm `lead` + `support` một phách đen (`1.0`, bậc −1), `bass` đáp ở móc 5 (bậc −2).
- **Ô 5 (Hợp âm dải phách đầu + dòng móc đơn chạy ở bè trầm):**
  - Móc 0: hợp âm dải **Loại 2 (3–4 dây)** từ trầm lên cao (`bass` 1 dây tại `0.0`, `support` 1–2 dây tại `1/12`, `lead` = `_melody_at` bậc 0 `accent=True` tại `2/12`). `bass` và `support` hạ 1 bậc vi mô (`steps = 1`, câu phẳng ra `58` và `54`) rồi cắt tại `0.5` để nhường dây cho dòng chạy trầm; `lead` ngân suốt phần còn lại của ô (`duration_beats = epb * 0.5 - 2/12`). Trong nửa đầu móc 0 không có tiếng nào khác.
  - Từ móc 1 đến hết ô, chỉ `voice 3`. Mỗi tiếng một móc đơn, đi bậc trong MIDI 40–52, về nốt gốc của hợp âm ở móc cuối. `lead` ngân phía trên. Trên 4/4, bảy móc là −1, −1, −1, −1, −2, −2, −1 (móc 1 đến 7), tức 58, 58, 58, 58, 56, 56, 58. Trên 3/4 và 6/8, năm móc là −1, −1, −2, −2, −1 (móc 1 đến 5), tức 58, 58, 56, 56, 58.

| Chỗ trong Kiểu 7 | Bậc vi mô (`_MICRO = 2`) | Ghi chú |
|---|---|---|
| Nốt chấm dôi đầu Ô 1, Ô 2 (`lead`, `support`, `bass` móc 0) | 0 (`accent=True`) | Trụ mở câu *Lento* |
| Hai móc rải đệm dưới nốt chấm dôi (móc 1, 2) | −1 | Đệm rải nhẹ dưới nốt hát |
| Hai móc kép mordent (móc 3 của Ô 1, Ô 2) | −2, −1 | Nốt thêu rồi nốt chính. Nốt giải ở móc sau |
| Phách 3 của Ô 1 (nốt giải) và móc 7 của Ô 2 (nốt đón) | 0 | Giữ mức viết để nối câu |
| Phách 3 của Ô 2 (nốt dài trước khi rải lên) | −1 | Hạ nhẹ tạo đà |
| Ô 3: cặp móc đơn ở móc 0, 4 | 0 (`accent=True`) | Phách mạnh trên bass pedal |
| Ô 3: móc lẻ và hai móc kép láy | −1 | Còn 62, đứng trên bass pedal 60 |
| Ô 4: hợp âm chấm dôi đầu ô / giữa ô | 0 (móc 0), −1 (móc 4) | Hai trụ hợp âm |
| Ô 4: hai móc đơn bass đáp đi xuống | −1, rồi −2 | Chìm dần (`58 -> 56`) |
| Ô 4: hai móc kép láy ở móc 3 và móc 7 | −2, −1 | Láy nhẹ rơi vào nốt giá |
| Ô 5: hợp âm móc 0 (`lead` ngân cả ô; `bass`/`support` Loại 2) | `lead` 0 (`accent=True`); `bass`/`support` −1 (`58 / 54`) | Đỉnh câu trước dòng chạy trầm |
| Ô 5, 4/4, bass móc 1–7 | −1, −1, −1, −1, −2, −2, −1 | 58 rồi 56 rồi 58 |
| Ô 5, 3/4 và 6/8, bass móc 1–5 | −1, −1, −2, −2, −1 | Cùng hướng, năm móc |

---

### 4.8. Kiểu 8 — Hợp âm chấm dôi + `Arm. 8` + câu hát bồng bềnh sang ô kế tiếp (*Arada* câu 2)

Nguồn: *Suite Castellana* II (*Arada*), đoạn `Arm. 8` (Ảnh 1, lấy từ ô thứ 3 — đầu dòng dưới — sang ô kế tiếp):
1. **Ô 1 (Hợp âm chấm dôi + 2 tiếng `Arm. 8` ở trầm + 5 móc đơn bè cao):**
   - Móc 0: hợp âm 4 tiếng chấm dôi (`duration_beats = 1.5`), giữ ở bè trên.
   - Móc 1 và 2 (dưới hợp âm đang ngân): bản ghi 2 tiếng `Arm. 8` ở bè trầm, một móc đơn ở dây 5 ngăn 12 và một nốt đen ở dây 6 ngăn 20. Engine hát chúng ở voice 3, vùng 40–52, mức bass bậc −1. Không ra 48.
   - Móc 3 (nửa sau phách 2): bè cao vào bằng 1 móc đơn ở dải cao (`$F_5$`, ngón 4).
   - Móc 4–7 (phách 3 và 4): bè cao hát 4 móc đơn lượn bậc trên cao (`$E_5 \rightarrow F_5 \rightarrow E\flat_5 \rightarrow F_5$`), bè dưới nghỉ hoàn toàn.
2. **Ô 2 (bass ngân, bè trung chấm dôi, bè cao là câu móc đơn):**
   - Nốt dài trên bản là bè trầm, không phải bè cao. `bass` là nốt trắng (`duration_beats = 2.0`). `support` là nốt đen chấm dôi (`1.5`). `lead` không ngân cùng hai nốt đó.
   - Câu hát là các móc đơn của `lead`. Móc đầu của nửa ô là một móc đơn `_melody_at`, hết ngay trong móc đó. Ba móc sau tiếp câu, hai móc đầu của chùm cùng cao độ và slur sang móc thứ ba.

#### Quy tắc ánh xạ vào Engine (2 ô)
Chỉ `castillo`, khi `ctx.bpm <= 72`, xoay luân phiên với Kiểu 7 (hoặc dùng khi câu chậm dài 2–4 ô chưa đủ 5 ô cho Kiểu 7).

- **Ô 1 (Hợp âm chấm dôi + 2 tiếng màu `Arm. 8` + câu móc đơn `_melody_at` trên cao):**
  - **4/4 (8 móc đơn):**
    - Móc 0: `lead` là `_melody_at(origin)` chấm dôi (`duration_beats = 1.5`, phủ móc 0–2), `accent=True`, bậc 0; `support` là nốt hợp âm chấm dôi (`1.5`), bậc 0. `bass` nghỉ móc 0 để nhường tiếng chuông ở móc 1.
    - Móc 1 và 2 (`voice 3`): móc 1 dài `0.5`, móc 2 là nốt đen `1.0` và ngân qua móc 3. Cao độ nằm trong MIDI 40–52. `assert_playable` từ chối voice 3 trên 53 với profile `torroba`, nên cao độ vang 57 không vào voice này. Nút harmonic duy nhất còn sống ở voice 3 là 52. `_harmonic_velocity` chỉ trả 48 khi cao độ vang thuộc tập nút và `duration_beats >= 2`. Hai tiếng này đều ngắn hơn 2, kể cả khi cao độ là 52, nên hàm trả mức bass. Bậc −1, câu phẳng ra 58. Không có 48 ở hai móc này.
    - Móc 3..7: chỉ `voice 1` hát 5 móc đơn `_melody_at(origin + offset)`. `support` không đánh lại. Nốt đen `voice 3` còn ngân ở móc 3, khác voice với `lead`, rồi hết. Từ móc 4 cả hai bè đệm nghỉ. Móc 3 bậc −1. Móc 4 bậc 0 (`accent=True`). Móc 5, 6, 7 bậc `−1, −2, −1`.
  - **6/8:** Móc 0 là hợp âm chấm dôi (`lead` + `support`, `1.5`). Móc 1 là một móc đơn `voice 3`. Móc 2 là nốt đen `voice 3` (`1.0`), cùng mức bass bậc −1 của 4/4, ngân dưới móc 3. Móc 3 là phách mạnh, `lead` bậc 0. Móc 4 và 5 bậc −1. Từ móc 4 phần đệm nghỉ.
  - **3/4:** cùng nhịp với 6/8. Móc 3 là phách yếu, nên ba móc `lead` 3, 4, 5 bậc −1, −1, −1.
- **Ô 2 (Nốt chấm dôi sang ô kế + 3 móc đơn có slur):**
  - **4/4 (hai nửa ô tại `base = 0` và `base = 4`):**
    - Tại `base`: `voice 3` là `_torroba_bass`, nốt trắng (`duration_beats = 2.0`), bậc 0 ở `0` và bậc −1 ở `4`. `voice 2` là một nốt hợp âm, nốt đen chấm dôi (`duration_beats = 1.5`), bậc 0 ở `0` và bậc −1 ở `4`. `voice 1` ở `base` chỉ là một móc đơn `_melody_at`, bậc 0 tại `0` (`accent=True`) và bậc −1 tại `4`. Móc đơn đó hết trước `base + 1`. Ba móc sau cũng là `voice 1`, nên nốt dài không nằm ở bè cao. `voice 2` còn ngân dưới các móc đó.
    - Tại `base + 1, base + 2, base + 3`: `lead` hát 3 móc đơn (`_melody_at` tại `base + 1`, lặp lại tại `base + 2` với `slur_start=True`, và bước về `_melody_at(origin + base + 3)` với `slur_stop=True`). Bậc xin là −1, −1, −2. Nửa đầu, bass bậc 0 còn 60 suốt hai phách, nên móc thứ ba rút còn −1 và nghe −1, −1, −1 (62). Nửa sau, bass bậc −1 còn 58, nên bậc −2 còn sống và nghe 62, 62, 60.
    - Nếu câu chỉ dài đúng 2 ô và `phrase.closes` đúng: nửa sau Ô 2 (`base = 4`) không đánh ba móc đơn. `voice 1` là một nốt trắng `_melody_at(origin + 4)` (`duration_beats = 2.0`, bậc −1). `voice 3` vẫn là nốt trắng. Không có hai nốt `voice 1` cùng lúc.
  - **3/4 và 6/8 (6 móc đơn):** Móc 0 là `bass` ngân cả ô (`3.0`), bậc 0, mức 60. `support` chấm dôi (`1.5`). `lead` móc 0 là một móc đơn, bậc 0. Móc 1, 2, 3 là ba móc đơn `lead`, slur ở móc 2–3. Bậc xin là −1, −1, −2. Bass 60 còn vang dưới móc 3, nên móc đó nghe −1. Cả chùm nghe −1, −1, −1 (62). Móc 4–5 là một nốt đen `lead`, `_melody_at` của móc 4, bậc −1, kèm `support` ở móc 4. Đó là phần còn lại của ô. Chỉ khi câu dài đúng 2 ô và `closes` thì nốt đen đó là nốt đóng. Câu dài hơn thì các ô sau vẫn là nốt ngân `castillo`.

| Chỗ trong Kiểu 8 | Bậc vi mô (`_MICRO = 2`) | Ghi chú |
|---|---|---|
| Hợp âm chấm dôi móc 0 của Ô 1 (`lead`, `support`) | 0 (`accent=True`) | Mở câu, ngân trên đầu hai tiếng `Arm. 8` |
| Hai tiếng trầm móc 1–2 của Ô 1 | bậc −1 trên mức bass | Ngắn hơn 2 phách và voice 3 không quá 53, nên không ra 48. Câu phẳng là 58 |
| Móc đơn 3 của Ô 1 (`lead` vào trên cao) | 0 trên 6/8, −1 trên 4/4 và 3/4 | Chỉ 6/8 có phách mạnh ở móc 3 |
| Móc đơn 4..7 của Ô 1 (`lead` một mình) | 0, −1, −2, −1 | Móc 4 giữ mức viết, các móc sau lượn nhẹ |
| Đầu mỗi nửa Ô 2 (`base = 0`, `base = 4`) | 0 ở `0`, −1 ở `4` | Hai trụ đáp xuống, giảm dần về `mf` |
| Ba móc slur, nửa đầu 4/4 và cả ô 3/4, 6/8 | xin −1, −1, −2; nghe −1, −1, −1 | Bass 60 còn vang, `_micro_fits` cắt móc thứ ba |
| Ba móc slur, nửa sau 4/4 | xin −1, −1, −2; nghe −1, −1, −2 | Bass đã ở 58, bậc −2 còn sống, nghe 60 |

---

### 4.9. Test

Fixture gọi thẳng renderer của kiểu, câu phẳng `rise` 0, band `mf`, để extra cả ô bằng 0. Mỗi tiếng bằng mức viết trừ bậc còn sống nhân `_MICRO`. Câu `sonatina` và `castillo` khóa theo 64 / 60 / 56 (riêng hợp âm dải Loại 2 của Kiểu 2 `sonatina`, Kiểu 3 ô mô-típ và Kiểu 7 ô 5 hạ `bass / support` 1 bậc xuống 58 / 54; Kiểu 2 `sonatina` và Kiểu 3 `accent=False` trên `lead`). Câu `fandanguillo` và `danza` khóa phách mạnh theo 68 / 60 / 56 (`accent=True` trên `lead`). Riêng cửa `rise` thì một test khác: kiểu 2 và kiểu 5 không xuất hiện khi `rise` dưới 3.

Khóa thêm cửa chọn. `castillo` ở 96 BPM không có ô kiểu. `castillo` ở 72 BPM: câu `n = 0` (`k = 0`) dài 5 ô hát đủ 5 ô Kiểu 7; câu `n = 1` ngân một nốt; câu `n = 2` (`k = 1`) dài 4 ô hát 2 ô Kiểu 8 rồi 2 ô ngân; câu `k = 0` chỉ dài 3 ô thì chuyển sang 2 ô Kiểu 8 thay vì cắt Kiểu 7. Câu `sonatina` đóng dài 4 ô có kiểu 3 trên ba ô cuối và không có kiểu 4. Câu `sonatina` `n` chẵn, `k % 3 == 0`, dài 2 ô là lưới nền. Câu `sonatina` `n` chẵn, `k % 3 == 1`, `rise` dưới 3 là lưới nền. Câu `fandanguillo` không có cả kiểu 2 lẫn kiểu 5. Câu liền trước đã dùng một kiểu thì câu sau về lưới nền. `danza` trên 4/4 không gọi kiểu 6. Support móc 5 của ô gọi kiểu 4 trên 3/4 là 54 khi bass yếu là 56.

Bass kiểu 1 cắt ở vạch ô khi ô sau là lưới nền, và ngân qua vạch ô khi ô sau cũng là kiểu 1. Ô ngân của kiểu 3 chỉ ra vận tốc 48 khi cao độ vang nằm trong tập nút và nốt dài ít nhất hai phách. Kiểu 7 không có `duration_beats = 1/6`. Mordent là hai móc kép `0.25`. Bass ô 5 khóa đúng dãy bậc của từng móc. Kiểu 8 móc 1–2 là mức bass bậc −1, ra 58 trên câu phẳng, không phải 48. Ba móc slur nửa đầu ô 2 nghe −1, −1, −1. Nửa sau 4/4 nghe −1, −1, −2. `lead` ở đầu mỗi nửa ô 2 là một móc đơn. Câu `sonatina` `n` chẵn không đủ cửa của bước 3 thì cả câu là lưới nền. Kiểu 3 móc 1–2, kiểu 5 ô 3, và chùm đầu kiểu 6 giữ các bậc đã viết dù cao độ lặp. Các chỗ hợp âm dải (Loại 1: Kiểu 5 ô 1, móc 0 của lưới `fandanguillo`, Kiểu 2 ô 1 trên `fandanguillo` với 5–6 dây trên hợp âm mở chuẩn; Loại 2: Kiểu 2 ô 1 trên `sonatina`, Kiểu 3 ô mô-típ, Kiểu 7 ô 5 với 3–4 dây) khóa đúng onset `0.0`, `1/12`, `2/12` theo thứ tự `bass → support → lead`, nhả tại `0.5` (riêng `lead` của Kiểu 7 ô 5 ngân hết ô `epb * 0.5 - 2/12`), không có tiếng nào khác trong nửa đầu móc 0 (`0.0 .. 0.25`), chương có hợp âm dải xuất `score.divisions == 12`, XML viết tuplet `3:2` khép kín kèm nốt buộc (`tie`) cho cả quạt móc đơn lẫn `lead` ngân cả ô của Kiểu 7 ô 5 (không dùng `<forward>` hay tỉ lệ `24:23` / `18:17`), và các `TempoEvent` rơi giữa nốt dài được đặt bằng con trỏ `<backup>` / `<forward>` thay vì `<offset>` âm. `assert_playable` đi qua từng kiểu trên 4/4, 3/4 và 6/8, trừ kiểu 6 không có mặt 4/4.

---

## 5. Thứ tự làm

1. **Câu (đã hát).** Tập offset của câu `closes` trên mọi span. Bed `p` chỉ trên các móc đó. Chặn slur sonatina khi câu trước `closes` và cả hai phách là sonatina. Giữ grace castillo sang sonatina.
2. **Ba cạnh thứ (đã hát).** `0.40`, `0.36`, `0.34`. Vòng bốn bước và La♭ trên Sol không đổi.
3. **Extra cả ô (đã hát).** `castillo` và `sonatina` vào `_WHOLE_BAR_EXTRA`.
4. **Tám kiểu (tiếp theo).** Dựng trong `guitar_torroba.py` theo mục 4.0–4.8. Pattern id không đổi. Mỗi kiểu khóa bậc vi mô bằng hiệu trong ô, cùng cách `test_galop_beats_keep_a_micro_velocity_contour`, trên fixture của mục 4.9. Kiểm chứng `assert_playable`.
