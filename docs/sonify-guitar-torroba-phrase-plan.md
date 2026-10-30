# Kế hoạch: câu Torroba, vòng quay đầu, extra cả ô

> **Trạng thái**: chưa triển khai. Dialect, bốn pattern, và extra cả ô của `danza` / `fandanguillo` đã hát trên `main`.
> **Khung đang chạy**: [`docs/sonify-guitar-torroba-plan.md`](./sonify-guitar-torroba-plan.md), mục 4, 5 và 6. Vi mô trong ô: [`docs/sonify-guitar-micro-contour-plan.md`](./sonify-guitar-micro-contour-plan.md).

Ba việc. Câu thở theo `Phrase` trên mọi span. Vòng thứ được phép quay về chủ. `castillo` và `sonatina` nhận một extra cho cả ô, cùng cửa PR97 đã mở cho hai điệu vũ.

---

## 1. Chia câu trên mọi span

`_breath` trong `guitar_torroba.py` trả về `bar % 4 == 3`. Ô đó làm mỏng bè trong. Bè cao vẫn ngân. Lưới này không đọc câu.

`plan_phrases` cắt câu từ đường giá trên mọi span. `Phrase.closes` đúng khi nốt cuối dài ít nhất `PERIOD` (4 móc đơn) và câu không `held_over`. Ô cuối câu là `(phrase.end - 1) // epb`. Hàm thở mới nhận `ctx` và `bar`, tìm câu chứa móc đầu ô, và chỉ thở khi ô đó là ô cuối của một câu `closes`.

Không có nhánh `span == "1D"`. `_Ctx` không có trường span. Một vị từ trên `ctx.phrases` phủ `1D`, `1W`, `1M`, `3M` và `1Y`. Khóa theo `PHRASE_STARTS = (2, 10, 18)` chỉ đúng lưới bài ngày, và vẫn sai bên trong câu ngày vì `plan_phrases` cắt tiếp theo nốt.

Ô pedal không thở: `intro`, `outro`, `warmup`, `cooldown`. Khung intro/outro đã có texture riêng. Câu `held_over` không thở, vì nốt cuối còn ngân sang câu sau cùng section.

Câu có thể kết giữa ô. Chỉ bỏ bè trong có eighth nằm trong câu đóng và trong ô cuối của câu đó. Móc thuộc câu sau, cùng ô, giữ nguyên. Bè cao của câu đóng vẫn là close. `_thin` vẫn bỏ khoảng nửa số nốt trong của phần đó.

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

### Nốt lấy đà dừng ở biên câu

`apply_sonatina_downbeats` slur vào phách mạnh của mọi ô `sonatina` từ ô 1 trở đi. Biên câu cũng bị dính.

Cửa mới dùng câu của phách mạnh đích và câu của phách mạnh ngay trước. Hai câu khác nhau thì không trồng nốt lấy đà, không slur. `_same_phrase` đã có trong `guitar_patterns.py`. Điệu Barrios từ chối nốt lấy đà khi sang câu khác qua `_allow_approach`. Sonatina đi cùng cửa đó. Castillo, fandanguillo và danza vốn không trồng pickup.

Cửa này không đọc span. Fixture một câu và fixture nhiều câu trên lưới 4/4, 3/4, 6/8 đều đi qua cùng hàm.

### Test

`test_breath_harmonics_and_fandanguillo_grids` đang khóa ô 3 mỏng hơn ô 0 vì `3 % 4 == 3`. Viết lại. Ô cuối một câu `closes` mà chỉ số ô không chia hết kiểu `n % 4 == 3` vẫn mỏng. Ô giữa câu có `bar % 4 == 3` vẫn đầy. Câu `held_over` không mỏng. Ô `intro` / `warmup` không mỏng. Nốt lấy đà sonatina không vượt biên câu. Không thêm đối số span vào renderer.

---

## 2. Vòng thứ được quay đầu

Vòng nhận diện giữ nguyên: `Cm → Bb → Ab → G → Cm`. `G → Cm` vẫn là cadenza mạnh nhất (`0.74`). La♭ trên `G` / `G7` giữ như mục 2 của kế hoạch Torroba. Picardy vẫn chỉ đổi ô cuối câu đóng từ `Cm` sang `C`.

Ba cạnh dưới đây đang trả `0.0`, vì cặp không có trong `_TORROBA_MINOR` mà một đầu là `Bb`. `Bb` nằm trong `_TORROBA_MINOR_TOUCH`.

| Cạnh | Vai trò | Trọng số |
|---|---|---|
| `Bb → Cm` | i–♭VII rồi về chủ, không buộc tuột hết xuống Sol | `0.40` |
| `Ab → Bb` | ♭VI–♭VII–i | `0.36` |
| `Fm → Bb` | iv–♭VII | `0.34` |

`Bb → Ab` đang là `0.62`. Cạnh quay đầu thấp hơn, nên khi cả hai hợp lệ thì đường đi xuống của vòng vẫn được chọn. `G7` vẫn chỉ về `Cm`. Các lối ra khác của `G7` vẫn `0.0`.

Giọng trưởng không thêm `Ab` hay `Eb`. Khung `C → Bb → F → C` và màu `Fm` giữ nguyên. Không thêm maj7, sus, add9, hay hợp âm Rê♭. Nốt Phrygian vẫn là La♭ ngân trên Sol.

Dialect không biết span. Ba cạnh có mặt trên `1D`, `1W`, `1M`, `3M` và `1Y`.

Test: `Bb → Cm`, `Ab → Bb`, `Fm → Bb` trả đúng số. `Bb → Ab` vẫn cao hơn `Bb → Cm`. `G7 → Fm` vẫn `0.0`. Một đường năm ô `Cm → Bb → Cm` đi được khi phách mạnh hợp với chủ. Đường `Cm → Bb → Ab → G → Cm` cũ vẫn đi được.

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

1. **Câu.** Đổi `_breath` sang câu `closes`, mọi span, bỏ móc trong đúng phạm vi câu. Chặn nốt lấy đà sonatina ở biên câu. Viết lại test ô 3.
2. **Ba cạnh thứ.** `0.40`, `0.36`, `0.34`. Vòng bốn bước và La♭ trên Sol không đổi.
3. **Extra cả ô.** `castillo` và `sonatina` vào `_WHOLE_BAR_EXTRA`.

Bước 1 là chỗ nghe hết vỡ câu. Bước 2 và 3 không phụ thuộc lưới ô của `1D`.
