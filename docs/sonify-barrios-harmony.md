# Barrios: dialect hòa âm và tiết tấu choro

> **Trạng thái**: Plan (2026-10-23), chưa code. Tài liệu này chốt dialect và lớp tiết tấu để triển khai sau. Pha 0 đối chiếu tổng phổ trước khi khóa số móc của lớp dance; bảng hợp âm và bảng cạnh ở mục 3 là đã chốt để code ở Pha 1.
>
> **Phạm vi so với guitar v10**: [`docs/sonify-classical-guitar.md`](./sonify-classical-guitar.md) vẫn là hợp đồng của Bước 1–6. Bước 4 của file đó viết bốn lớp Barrios trên `COMMON`. File này bắt đầu sau khi Bước 4 đã có `barrios_layer` và vỏ `HarmonyDialect`. Vòng chọn hợp âm giữ nguyên, trừ một điều kiện trong `form.py`: thêm `"augmented-sixth"` cạnh `"diminished"` để ô giữ không bị đổi thành `BORROWED_HOLD_PROB` (mục 3.3). Không thêm ensemble, không đổi nhãn «Tremolo · Barrios».

---

## 1. Hai việc, một phong cách

Người nghe vẫn chọn một hàng `barrios`. Bên trong hàng đó thêm hai thứ:

1. **`BarriosDialect`**, đăng ký `DIALECTS["barrios"]`. Sor ở lại `COMMON`. Villa ở lại `VillaDialect`.
2. **Lớp dance** trong `barrios_layer`: chất choro Nam Mỹ đi theo tiết tấu của chương, không theo một ensemble mới.

Chất nghe được nằm ở cả hai. Vòng quãng 5 và chuỗi át phụ là hòa âm. Levada 2/4 và polca 6/8 là cách đánh. Tremolo vẫn là cách hát của câu giai điệu giữ nốt. Choro là cách đi của câu giai điệu đang chạy.

Hòa âm này là hợp âm chức năng. Không có sus, không có add9. Giai điệu thứ đi trên `c_natural_minor_scale`: Đô, Rê, Mi♭, Fa, Sol, La♭, Si♭. Trưởng đi trên Đô trưởng. `raw_pitches` chỉ lấy nốt của thang đó, và `bar_quantization_loss` ném lỗi nếu một nốt nằm ngoài. Fa♯, Rê♭ và Đô♯ không có trong bài thật. `color_credit` trả 0. Khoản 0.70 là của Villa.

Hợp âm thêm thắng khi các nốt thang của ô nằm trong nó, còn hợp âm catalog cùng chứa những nốt đó thì đắt hơn. Phạt 2.5 không nhìn một nốt ngoài thang. Si♭ đã nằm trong `Cm7` và `Eb`. Fa♯ đã nằm trong Fa♯°7. Rê♭ không có trong catalog và cũng không có trên thang.

Ba trường hợp đó có thật:

- `{Si♭, Rê, Fa}` sau Fa thứ ra `Bb`. Không hợp âm catalog nào chứa cả ba.
- Rê sau La♭ ra `D7`. Cửa 0.48 giá khoảng 0.57. `Dm7b5` từ La♭ giá khoảng 1.09. Sol giá khoảng 1.73. La♭ vẫn loại `D7`.
- `{La♭, Đô, Mi♭}` sau Fa thứ ra `Ab+6` khi gốc Fa đã giữ từ hai ô, ô đó nằm giữa câu, và ô sau ngồi trên {Sol, Rê} (thêm Fa nếu muốn `G7`). Fa thứ không chứa Mi♭. Cửa 0.24 giá khoảng 0.99. Hợp âm La♭ đi cửa Fa→La 0.14, giá khoảng 1.28. Fa♯°7 không chứa La♭. Ô thứ hai của gốc Fa thì `Fm7` chứa cả ba nốt với giá đổi chất 0.50 và thắng. `Ab+6` ở ô đó còn cộng phạt đổi ô, nên khoảng cách rộng hơn 0.99.

---

## 2. Vì sao catalog chung không ra chất này

Nhạc thứ của Barrios đi một vòng quãng 5 dài. Allegro Solemne của *La Catedral* (Si thứ), ô 141–150, gốc Fa♯–Si–Mi–La–Rê–Sol–Đô♯–Fa♯ (John Hall). Hạ về Đô thứ của catalog:

**Sol – Đô – Fa – Si♭ – Mi♭ – La♭ – Rê7 – Sol**

tức V–i–iv–♭VII–III–VI–V/V–V. Mắt La♭→Rê là quãng 5 giảm, mắt duy nhất không phải quãng 5 đúng, để vòng khép trên át. Rê ở mắt đó là át của át (hợp âm bảy), đúng cú «iiø bật thành V/V» mà Andante và Allegro dùng (Đô♯ nửa giảm → Đô♯7 ở Si thứ).

Preludio Saudade thêm sequence ngắn Si–Mi–La, tức i–iv–♭VII, trên bass ostinato lệch phách. *Una Limosna por el Amor de Dios* (Mi thứ) thêm cadence i → VI → Napolitaine (♭II) → ii → V.

`MINOR_CATALOG` có i, iv, iiø, V, V7, VI, III và Fa♯°7 giải vào Sol. Thiếu Si♭, Rê♭, Rê7, và La♭ có sext tăng. Hàng Fa của `_ROOT_TRANSITIONS` không có cạnh sang Si. Vì vậy vòng gãy đúng những mắt tạo chất. Pha 1 chỉ thêm hợp âm mà các nốt thang của nó không bị catalog nuốt: Si♭, Si♭7, Rê7, La♭+6. Rê♭ có trong tổng phổ và không vào `extra()`.

Ở trưởng, choro (*Choro da Saudade*, và đệm của nhiều bản salon) là chuỗi át phụ rơi quãng 5: Mi7→La7→Rê7→Sol7→Đô, cộng một giảm bảy đi qua nằm nửa cung dưới hợp âm đích. `BORROWED` đã có các át phụ đó, nhưng La7 chỉ được giải vào Rê thứ (0.40), Rê7 ưu tiên Sol hợp âm ba (0.46) hơn Sol7 (0.34). Chuỗi át bảy không tự đi. Giảm bảy đi qua có trong bản; nốt đặc trưng của nó là Đô♯, ngoài Đô trưởng, nên Pha 1 không đăng ký. Ba cạnh chuỗi át thì có.

Planing hợp âm 6/3 của Andante và Preludio là luật viết bè của lớp Thánh ca / Preludio trong file guitar, không phải hợp âm mới. Trưởng cùng tên ở coda của *Una Limosna* là đổi mode, ngoài pipeline một-mode-mỗi-bài.

---

## 3. `BarriosDialect`

Đăng ký:

```python
DIALECTS = {"villa": VILLA, "barrios": BARRIOS}
```

`dialect_for("barrios")` trả dialect này. `dialect_for("classic")` và đường symphony vẫn là `COMMON`. `transition` đã được `plan_markov_chords` gọi cho mọi cặp; `None` để Markov cũ chạy. Dialect này dùng đúng cửa đó.

### 3.1. Hợp âm thêm

Sinh trong không gian Đô, rồi `transpose_chord` đẩy đi như mọi hợp âm khác. Thứ dùng bốn hợp âm dưới. Trưởng không thêm hợp âm. Chuỗi át phụ trưởng dùng hợp âm `BORROWED` sẵn có, chỉ thêm cạnh.

| Tên | Mode | Nguồn | `root_step`, `alter` | Nốt | Nốt trên thang thứ | Vai |
|---|---|---|---|---|---|---|
| `Bb` | thứ | `BF` sẵn có | B, −1 | Si♭–Rê–Fa | cả ba | ♭VII |
| `Bb7` | thứ | `BF7` sẵn có | B, −1 | Si♭–Rê–Fa–La♭ | cả bốn | ♭VII7, át của III |
| `D7` | thứ | `D7` sẵn có | D, 0 | Rê–Fa♯–La–Đô | Rê, Đô | V/V |
| `Ab+6` | thứ | mới | A, −1 | La♭–Đô–Mi♭–Fa♯ | La♭, Đô, Mi♭ | sext tăng Đức, vào V |

`Ab+6` không phải La♭7. Âm đặc trưng là Fa♯, sext tăng, giải ra ngoài vào gốc của át. Fa♯ không có trên thang giai điệu; ba nốt kia có. Lời gọi phải mang `degrees`:

```python
Chord(
    "Ab+6", "A", KIND_OTHER, "+6", (68, 72, 75, 78),
    alter=-1, degrees=(0, 2, 4, 5),
    tones=((8, "A", -1), (3, "E", -1), (6, "F", 1)),
)
```

`(68, 72, 75, 78)` là La♭4–Đô5–Mi♭5–Fa♯5. Fa♯ 66 nằm dưới gốc và không dùng. Pitch-class không đổi nên Viterbi không đổi; bậc 5 là chữ Fa. Thiếu `degrees`, `transpose_chord` lấy `index * 2` cho nốt thứ tư và viết Sol♭. `quality_group` trả `"augmented-sixth"` khi `kind_text == "+6"`, đặt trước nhánh mặc định `"major"`. Ở thứ, cùng `root_step` và cùng `alter` đã là cùng gốc trước khi xét nhóm. Nhóm này chỉ để luật một ô bắt được hợp âm. Rơi vào `"major"` thì luật đó bỏ qua, và La♭ → `Ab+6` thành đổi chất hợp lệ với giá 0.50 (`SECOND_BAR_STAY_COST` 0.15 cộng phạt đổi chất 0.35).

Tỉa theo mục 5.3 của file guitar: hợp âm bốn nốt bỏ `pitches[2]` (quãng 5) trước. `Ab+6` còn La♭–Đô–Fa♯. `D7` còn Rê–Fa♯–Đô. `Bb7` còn Si♭–Rê–La♭. Không gọi `jazz_chord` trên slot của dialect này.

### 3.2. Cạnh — tường minh với mọi cặp đụng `extra()`

`transition` trả một số khi một trong hai hợp âm thuộc `extra()` của mode đang chạy, hoặc khi cặp nằm trong bảng chuỗi át trưởng ở mục 3.4. Số 0 là cấm. Không có trong bảng, mà một đầu thuộc `extra()`, cũng trả 0. Mọi cặp khác trả `None`.

Cửa này bắt buộc vì hai va chạm `root_step`:

- `Bb` / `Bb7` có `root_step` B. `_ROOT_TRANSITIONS` không có hàng B. Trả `None` thì mọi cửa từ Si♭ là 0, hợp âm không bao giờ được chọn.
- `D7` dùng `root_step` D, cùng hàng với ii. Trả `None` thì nó đi cửa của `Dm7b5` (Rê→Sol = 0.34, Rê→La = 0.14). Mọi cặp có một đầu là `D7` phải có số tường minh.

`shares_root` trả `False`. Mode thứ đã coi cùng `root_step` và cùng `alter` là cùng gốc (`form.py`), nên Rê7♭5 → Rê7 là đổi chất trên ii, và La♭ → `Ab+6` cũng vậy. Không mở thêm cửa.

### 3.3. Bảng cạnh, mode thứ

Trọng số là xác suất mức gốc, đưa thẳng vào `−0.6·ln`, không nhân 2. Ô giữ một ô (`held_bars == 1`, không mở section) vẫn bỏ qua trọng số này và dùng `SECOND_BAR_STAY_COST`, đúng công thức hiện tại.

**Vòng, đi xuống quãng 5**

| Cặp | Trọng số |
|---|---|
| `Fm`/`Fm7` → `Bb` | 0.42 |
| `Fm`/`Fm7` → `Bb7` | 0.34 |
| `Cm`/`Cm7` → `Bb` | 0.12 |
| `Bb` → `Eb` | 0.42 |
| `Bb` → `Ebmaj7` | 0.26 |
| `Bb7` → `Eb` | 0.50 |
| `Bb7` → `Ebmaj7` | 0.34 |
| `Bb` → `G` | 0.22 |
| `Bb` → `G7` | 0.26 |
| `Bb` → `Bb` | 0.18 |
| `Bb` → `Bb7`, `Bb7` → `Bb` | 0.24 |
| `Bb7` → `Bb7` | 0.14 |

`Cm` → `Fm` giữ cửa Markov 0.26 (cặp không đụng `extra()`). `Eb` → `Ab` giữ cửa E→A = 0.34. Hai mắt thuận thang đó không cần dialect. `Bb7` đắt hơn `Bb` đúng bằng phạt bốn nốt 0.05 cộng chênh cửa: từ Fa thứ, giai điệu nằm trong {Si♭, Rê, Fa} ra `Bb`; có thêm La♭ thì ra `Bb7`, vì hợp âm ba không chứa La♭.

Ô chỉ Si♭ không giữ `Bb` mãi. `sing_leading` nâng Si♭ thành Si khi ứng viên là Sol hoặc Sol7, nên hai hợp âm đó hát Si♭ với phát xạ 0. Cửa `Bb` → `G` là 0.22, giá khoảng 0.95. Ô thứ hai của gốc Si♭ (`prev_held == 1`) ở lại giá 0.15 cộng sàn 0.08. Sol còn bị phạt đổi ô, nên ở lại thắng. Từ ô thứ ba, ở lại đi cửa tự thân 0.18: `−0.6·ln(0.18) + 0.25` cộng sàn 0.08, khoảng 1.36. Sol rẻ hơn khoảng 0.41. Ô chỉ Si♭ sau khi `Bb` đã giữ hai ô ra `G` hoặc `G7`.

**Khép vòng và bật iiø thành V/V**

| Cặp | Trọng số |
|---|---|
| `Ab`/`Abmaj7` → `D7` | 0.48 / 0.40 |
| `Dm7b5` → `D7` | 0.40 |
| `D7` → `G` | 0.46 |
| `D7` → `G7` | 0.55 |
| `D7` → `D7` | 0.12 |

Không có hợp âm ba Rê trưởng. Mọi nốt thang của hợp âm ba đó đã nằm trong `D7` hoặc trong `Dm7b5`. Nốt thang của `D7` chỉ là Rê và Đô. Fa♯ và La không có trên thang thứ.

`Dm7b5` → `D7` cùng gốc. Ô thứ hai của gốc (`prev_held == 1`) lấy 0.15 cộng phạt đổi chất 0.35, thành 0.50, rồi cộng sàn `D7` 0.13. Ở lại trên `Dm7b5` chỉ tốn 0.15 cộng `minor_bias` 0.06. Khi ô thuộc {Rê, Đô}, ô thứ hai ở lại nửa giảm. Cạnh 0.40 chỉ vào từ ô thứ ba: `−0.6·ln(0.40) ≈ 0.55` cộng `EXTENDED_STAY_PENALTY` 0.25 cộng phạt đổi chất, rồi cộng sàn 0.13, thành khoảng 1.28. Ở lại từ ô thứ ba khoảng 1.41. `D7` thắng mà không cần Fa♯.

Phách mạnh Rê sau La♭ thì `D7` thắng. Cửa 0.48 giá ≈ 0.44 cộng sàn 0.13 thành ≈ 0.57. `Dm7b5` từ La♭ đi cửa A→D = 0.18, giá ≈ 1.03 cộng bias 0.06 thành ≈ 1.09. Sol đi cửa A→G = 0.06, giá ≈ 1.69 cộng bias 0.04 thành ≈ 1.73. Fa♯°7 không chứa Rê. Phách mạnh La♭ thì `D7` mất 2.5, vì `D7` không chứa La♭.

**Không đăng ký `Db` và `C#dim7`**

Napolitaine và giảm bảy đi qua có trong tổng phổ Barrios. Pipeline không hát được nốt đặc trưng của chúng.

`Db` có nốt thang Fa và La♭. Fa thứ chứa cả hai. Từ Đô thứ, cửa sang Fa thứ là 0.26, giá khoảng 0.81, cửa sang `Db` là 0.14, giá khoảng 1.18 cộng sàn 0.08. Bias `selloff` −0.08 không bù khoản này. Rê♭ tự nó không có trên thang, nên không có ô nào để phạt 2.5 kéo `Db` vào.

`C#dim7` ở thứ có nốt thang Sol và Si♭. Ô chỉ Sol sau Đô thứ ở lại `Cm`: Sol nằm trong chủ, giá giữ 0.15. Thêm Si♭ thì `Cm7` chứa cả hai với giá đổi chất 0.50. Cửa vào giảm bảy khoảng 1.51. Ở trưởng, nốt thang của nó là Mi và Sol, và Đô trưởng chứa cả hai. Ở lại Đô giá 0.15. Cửa 0.20 giá khoảng 1.10. Ô thuận thang không bước lên hợp âm đó.

**Sext tăng**

| Cặp | Trọng số |
|---|---|
| `Fm`/`Fm7` → `Ab+6` | 0.24 / 0.20 |
| `Cm`/`Cm7` → `Ab+6` | 0.06 |
| `Ab+6` → `G` | 0.62 |
| `Ab+6` → `G7` | 0.55 |

`Ab+6` là một ô nhờ nhóm `"augmented-sixth"`, không nhờ cạnh tự thân bằng 0. Khi `transition` trả ≤ 0 mà chất không phải `"diminished"`, vòng lặp đổi tự thân thành `BORROWED_HOLD_PROB` 0.16. Luật một ô phải thấy `"augmented-sixth"` trước nhánh đó thì ô giữ mới bị chặn. Thêm nhóm này vào điều kiện đang dành cho `"diminished"` trong `form.py` (`target_held != 1`). Hai việc đi cùng nhau: nhóm chất, và điều kiện một ô. Cùng gốc với La♭ nên nhánh `same_root` đòi `held == 2`; luật một ô cấm `held == 2`; vậy `Ab+6` không đi được từ La♭ / La♭maj7. Trên thang thật nó vào từ hạ át, giữa câu, khi gốc Fa đã giữ từ hai ô, rồi ra Sol. Cửa từ chủ 0.06 không thắng một ô thuận thang. Ô mở section cũng không: mục 3.5.

Trên thang thật, ô thuộc {La♭, Đô, Mi♭} sau Fa thứ. Fa thứ không chứa Mi♭. `Ab+6` cửa 0.24 giá ≈ 0.86 + sàn 0.13 ≈ 0.99. Hợp âm La♭ cửa Fa→La = 0.14 giá ≈ 1.18 cộng bias gốc La ≈ 0.10, thành khoảng 1.28. Fa♯°7 không chứa La♭. `Fm7` chứa cả ba nốt. Ô thứ hai của gốc Fa đổi chất giá 0.50 và thắng `Ab+6`. Ở ô đó `Ab+6` còn cộng phạt đổi ô vì `prev_held == 1` và khác gốc: 0.45 với `volatile`, 0.35 khi `volatile` rơi vào slot 1, 0.60 với `rally` và `selloff`, 0.80 với `calm`, 0.65 khi character là `None`. Giá không dừng ở 0.99. `Fm7` vẫn thắng, khoảng cách rộng hơn. Gốc Fa đã giữ từ hai ô, và ô đó không phải phách đầu câu, thì `Fm7` khoảng 1.70, `Ab+6` khoảng 0.99, và `Ab+6` thắng.

Ô sau cũng phải thuộc Sol. `Ab+6` chỉ có cửa ra `G` và `G7`, và không hợp âm nào trong hai cửa đó chứa La♭, Đô hay Mi♭. Ba ô liên tiếp toàn {La♭, Đô, Mi♭} thì Sol mất 2.5 ở ô kế, và Viterbi không mở sext tăng. Đường sống là đường kết tại ô sext, hoặc ô sau ngồi trên {Sol, Rê}. Thêm Fa thì `G7` chứa nốt đó, Sol hợp âm ba thì không. Ô pedal kế tiếp cũng chết: pedal chỉ cho chủ, còn cửa `Ab+6` → chủ là 0.

Cửa `Cm` → `Ab+6` giữ 0.06 vì khoản 0.05 với Fa♯°7. Đó là sổ sách của một ô có Fa♯, không phải test pipeline: Fa♯°7 vào bằng 0.06, giá ≈ 1.68 cộng bias 0.08 thành ≈ 1.76. `Ab+6` trên giao {Fa♯, Đô, Mi♭} giá ≈ 1.68 + 0.13 ≈ 1.81, đắt hơn đúng 0.05. Cửa 0.12 đảo người thắng. Móc yếu lệch một bậc nặng 0.02 và thuộc run riêng. Hai móc như vậy còn trong khoản 0.05. Móc thứ ba vượt. Móc yếu ngân tiếp đúng cao độ của phách mạnh không tính 0.02: nó thuộc run của phách mạnh và nặng 1.0 (`HELD_STRONG_WEIGHT`). Ô pipeline không có Fa♯, nên vế «sau Đô thứ ra Fa♯°7» không có test trên thang. Ô {Đô, Mi♭} sau Đô thứ ở lại `Cm`, giá giữ 0.15.

### 3.4. Bảng cạnh, mode trưởng — chuỗi choro

Ba cặp trong bảng được trả số. Các cửa còn lại của La7, Rê7, Mi7 giữ `borrowed_transition`. Không có `C#dim7` ở trưởng.

| Cặp | Trọng số |
|---|---|
| `E7` → `A7` | 0.55 |
| `A7` → `D7` | 0.55 |
| `D7` → `G7` | 0.55 |

`A7` → `Dm` vẫn 0.40. `D7` → `G` vẫn 0.46. Giá chuyển tiếp khi cả hai hợp âm đều chứa phách mạnh:

- `A7` → `D7` giá `−0.6·ln(0.55) ≈ 0.36`. `A7` → `Dm` giá ≈ 0.55. Rê thứ còn lợi khoảng 0.02 vì `D7` mang sàn hợp âm mượn 0.08 còn Rê thứ nằm trong `CHORDS`. Chuỗi vẫn rẻ hơn khoảng 0.17 khi nốt là Đô, La hoặc Rê. Đô là âm 7 của Rê7 và có trên Đô trưởng. La và Rê nằm trong cả Rê7 lẫn Rê thứ. Phách mạnh Fa thì Rê7 mất 2.5 và Rê thứ thắng. Fa♯ là âm dẫn của chuỗi này và không có trên thang, nên không phải điều kiện của test.
- `D7` → `G7` giá ≈ 0.36. `D7` → `G` giá ≈ 0.47. Sol7 thắng khi cả hai đều chứa phách mạnh. Phách mạnh Fa (âm 7 của Sol7, có trên thang) giữ Sol7.

### 3.5. `allowed`, `bias`, `color_credit`

`allowed` trả `True` với hợp âm không thuộc `extra()`, để `_borrowed_allowed` chạy tiếp. Mọi hợp âm `extra()` trả `False` ở ô pedal và ở phách đầu câu.

`phrase_starts` là mọi section có `kind == "phrase"`. `Section` chỉ có `intro`, `phrase`, `outro`, `warmup`, `cooldown`. Bốn kind còn lại nằm trong `_PEDAL`. Trên form thật, mọi ô `new_section` rơi vào một trong hai cửa: phách đầu câu, hoặc pedal. Cả hai đều chặn `extra()` trước khi tính giá. Pedal còn lọc thêm `allowed_tonics`, nên chủ vẫn là hợp âm duy nhất ở đó kể cả khi `allowed()` lỏng. Không có ô mở section nào cho `Ab+6`.

`Bb` đứng được từ ô thứ hai của câu. `Ab+6` chỉ đứng giữa câu, khi gốc Fa đã giữ từ hai ô và ô sau thuộc Sol, như mục 3.3.

`bias`, cộng thêm lên bias sẵn có, trị tuyệt đối dưới 0.1:

| Điều kiện | Mức |
|---|---|
| `volatile`, hợp âm là `Bb`, `Bb7` hoặc `D7` | −0.06 |
| `rally`, `D7` hoặc `Bb7` | −0.04 |

Không mức nào trong bảng bù được phạt phách mạnh 2.5, và cũng không bù cửa 0.26 của Fa thứ khi nốt thang đã nằm trong Fa thứ.

`color_credit` trả 0 với mọi hợp âm, kể cả khi `prev` là `None`.

### 3.6. Sàn của hợp âm `extra()`

Trong vòng lặp, hợp âm thuộc `extra()` nhận sàn 0.08 ngay, rồi hợp âm bốn nốt cộng `SEVENTH_TENSION_COST` 0.05. `minor_bias` chỉ chạy cho hợp âm còn lại. `Bb` chỉ sống trong `extra()`, nên `root_step` B không chạm `_MINOR_ROOT_BIAS` và không ném `KeyError` trên đường planner. Pha 1 không sửa `minor_bias`. Gọi thẳng `minor_bias(Bb)` vẫn lỗi; đó không phải đường chọn hợp âm.

`D7`, `Bb7` và `Ab+6` sàn 0.13. `Bb` ba nốt dừng ở 0.08. Fa♯°7 không thuộc `extra()`, nên vẫn đi `minor_bias` và giữ 0.08.

---

## 4. Lớp dance — choro theo tiết tấu

Lớp này là chất Nam Mỹ ở tầng nhịp, trong cùng `barrios_layer`. Choro gốc là nhịp 2/4. Pipeline giữ một meter mỗi chương (mục 4.0 của file guitar), nên lớp đọc meter đang chạy và đổi mẫu, không đổi ký hiệu nhịp.

| Meter | Mẫu | Nhà của nó |
|---|---|---|
| 4/4 | Hai ô choro 2/4 trong một ô. Levada lệch, kiểu *Choro da Saudade* và maxixe | `1D`, chương nhanh 4/4, finale |
| 6/8 | Polca Paraguay: bass ở hai phách chấm, hợp âm ở phần yếu; band `f` đổi nhấn sang hemiola | Scherzo `1M` (120), tháng khép `1Y` (108), mọi chương 6/8 |
| 3/4 | Không dance. Chương chậm vẫn tremolo và thánh ca | Chương II, tháng giữa mùa |

Maxixe dùng cùng mẫu 4/4. Không tách lớp.

### 4.1. Khi nào lớp này thắng

Chữ ký thêm meter, vì luật phụ thuộc meter mà bpm không suy ra được:

```python
barrios_layer(..., meter) -> Literal["preludio", "run", "tremolo", "chorale", "dance"]
```

Thứ tự ưu tiên khi cùng khớp — các bậc 1 và 2 giữ nguyên file guitar:

1. Ô khung mở, hoặc câu đầu chương → Preludio.
2. Điều kiện chạy dây, còn ngân sách → Chạy dây. Ngoại lệ chương chậm giữ nguyên: chỉ khi band `f`, có breakout, và `bpm <= 84`.
3. Meter 3/4 → không xét dance. Rơi xuống tremolo / thánh ca như hiện tại.
4. Meter 6/8, `bpm > 100`, band `f` → dance, kể cả khi giai điệu giữ nốt. Lưới tremolo giảm ở tempo này không chơi ở band `f`.
5. Giai điệu giữ ≥ 2 phách, band `mp–f` → Tremolo, trên lưới của mục 4.3.4 file guitar. Tempo ≤ 100 là lưới đầy `p–a–m–i`. Tempo > 100 là lưới giảm, kể cả 4/4. Ở 6/8 nhanh hơn 100, bậc này chỉ còn band `mp` và `mf`.
6. Meter 4/4 hoặc 6/8, character khác `calm`, band `mp–f` → dance.
7. `calm` ở ô chuyển section → Thánh ca.
8. Còn lại → arpeggio thưa kiểu Preludio rút gọn.

Hệ quả nghe: câu hát ngân vẫn là tremolo; câu nốt chạy ở 4/4 và 6/8 là choro hoặc polca; chương chậm 3/4 không có dance; mở bài vẫn là Preludio. Choro xuất hiện thường, vì phần lớn câu của một phiên `volatile` / `rally` không giữ nốt hai phách. `calm` không dance.

Bậc 4 chỉ lấy band `f` của 6/8 trên 100 BPM. Mọi câu tremolo còn lại ở tempo > 100 dùng lưới giảm của mục 4.3.4 file guitar, không riêng 6/8. Chương III của `3M` là 4/4 ở 108: ngón cái và giai điệu ở móc kép 0 và 2 của từng phách đen. Viết tremolo đầy ở đó là sai. Scherzo `1M` (120, 6/8) và tháng khép `1Y` (108, 6/8) ở band dưới `f` vẫn là lưới giảm: ngón cái ở móc kép 0 và 6, giai điệu ở móc kép 2 và 8.

Vòng quãng 5 không tự bật lớp. Lớp đọc tiết tấu của câu. Hòa âm của vòng đã nằm trong `slots` từ Pha 1, và mẫu dance đánh đúng những `slots` đó.

### 4.2. Mẫu 4/4 — đề xuất, Pha 0 khóa số móc

`divisions = 4`. Một ô 4/4 là 16 móc kép, hai lần levada 8 móc. Giai điệu giá chỉ đứng trên móc kép chẵn (lưới móc đơn của dữ liệu). Móc lẻ là đệm, không có nốt giai điệu mới.

Trong mỗi nửa ô, tính móc kép từ đầu nửa đó:

| Móc | Bè | Nội dung |
|---|---|---|
| 0 | Trầm + Cao | Gốc. Cao là nốt dữ liệu |
| 3 | Trung | Âm hợp âm còn lại sau tỉa, một nốt |
| 4 | Trầm + Cao | Quãng 5 (`pitches[2]`). Cao là nốt dữ liệu |
| 6 | Trung + Cao nếu móc này trùng nốt dữ liệu | Âm bảy hoặc âm ba |
| 7 | Trung | Một nốt hợp âm, lệch về trước phách sau |

Nửa sau lặp cùng các độ dời 8, 11, 12, 14, 15. Móc 15, khi gốc ô sau thấp hơn gốc ô này đúng một quãng 5, đổi thành nốt Trầm dẫn bán cung nằm nửa cung dưới gốc ô sau. Đó là bass đi qua của choro, một nốt, không đổi `slots`. Ô không rơi quãng 5 thì móc 15 giữ nốt Trung.

Cụm cùng vang tối đa 3 nốt và vẫn qua ống sửa mục 5.5. Nốt Cao trên móc chẵn là nốt dữ liệu, không bị mẫu thay.

### 4.3. Mẫu 6/8 — đề xuất, Pha 0 khóa số móc

Một ô 6/8 là 12 móc kép, sáu móc đơn. Polca:

| Móc đơn | Móc kép | Bè |
|---|---|---|
| 0 | 0 | Trầm gốc + Cao dữ liệu |
| 1 | 2 | Trung |
| 2 | 4 | Trung + Cao nếu có nốt dữ liệu |
| 3 | 6 | Trầm quãng 5 + Cao dữ liệu |
| 4 | 8 | Trung |
| 5 | 10 | Trung + Cao nếu có nốt dữ liệu |

Band `f` là một mẫu khác, không phải polca bị khoét vài móc. Đệm chỉ đánh ở móc đơn 0, 2, 4. Móc 1, 3, 5 không có nốt Trung và không có nốt Trầm mới; Cao vẫn hát nốt dữ liệu nếu lưới dữ liệu có nốt ở đó.

| Móc đơn | Móc kép | Bè |
|---|---|---|
| 0 | 0 | Trầm gốc + Trung + Cao dữ liệu |
| 2 | 4 | Trầm + Trung + Cao nếu có nốt dữ liệu |
| 4 | 8 | Trầm + Trung + Cao nếu có nốt dữ liệu |
| 1, 3, 5 | 2, 6, 10 | Không đệm |

Đó là hemiola 3/4 chồng lên 6/8 (nhấn móc đơn 0, 2, 4, mục 4.0 file guitar). Móc đơn 5 không còn nốt Trung của polca, nên nhóm 0–2–4 khép.

Nốt dẫn bán cung, khi gốc ô sau thấp hơn đúng một quãng 5, là một nốt Trầm mới ở móc kép 11. Mẫu polca chỉ đánh Trung tới móc kép 10, và hemiola không có đệm ở móc đó, nên móc 11 không thay một nốt Trung có sẵn. Nốt này có ở cả hai mẫu. Ô không rơi quãng 5 thì móc kép 11 nghỉ.

### 4.4. Profile `barrios_dance`

Thêm một hàng vào bảng profile mục 5.4 của file guitar khi Pha 2 code:

| Profile | Bè Trầm | Bè Trung |
|---|---|---|
| `barrios_dance` | 4/4 và polca 6/8: gốc ở đầu mỗi nửa ô hoặc đầu mỗi nhóm chấm, quãng 5 ở giữa nhóm. Hemiola 6/8 band `f`: Trầm ở móc đơn 0, 2, 4. Cả hai mẫu: một nốt dẫn bán cung ở móc kép cuối ô khi gốc sau thấp hơn đúng một quãng 5. Mọi nốt Trầm khác là lỗi | Nốt hợp âm đã tỉa, chỉ ở các móc đệm của mục 4.2 và của polca 4.3. Hemiola không có nốt Trung ở móc đơn 1, 3, 5 |

`assert_playable` với profile `study` vẫn báo lỗi trên nốt dẫn đó. Test phải thấy cùng một nốt đạt ở `barrios_dance` và thất bại ở `study`.

---

## 5. Thứ tự làm

Mỗi pha nghe được một mình. Không pha nào nằm trong Bước 1–6 của file guitar.

**Pha 0 — Tổng phổ, chưa đụng code sản phẩm.** Đọc và ghi lại số, không chép giai điệu:

- *La Catedral*, Allegro, quanh ô 141–150: đúng gốc Fa♯–Si–Mi–La–Rê–Sol–Đô♯–Fa♯. Chất của mắt Đô♯ ghi lại để biết bản viết gì; mắt đó không vào `extra()`.
- Preludio: sequence Si–Mi–La và chỗ nó rơi vào át.
- *Una Limosna*: ô sext tăng hoặc giảm bảy dẫn vào át, nếu có. Napolitaine ghi lại, không đăng ký.
- *Choro da Saudade*: mẫu tay phải một ô, tính bằng móc kép, và chuỗi át thực sự đi những bậc nào.
- *Danza Paraguaya*: mẫu 6/8, và ô nào melody hát theo 3/4 trên đệm 6/8.

Đầu ra sửa mục 4.2 và 4.3 của file này nếu số móc lệch. Bảng cạnh mục 3 chỉ sửa khi tổng phổ cho một cửa khác hẳn trên nốt thuộc thang (ví dụ mắt Rê của vòng thứ là hợp âm ba, không phải bảy — trường hợp đó mới mở lại quyết định bỏ hợp âm ba Rê). Nốt đặc trưng ngoài thang, kể cả Napolitaine và Đô♯°7, không được thêm vào `extra()` dù tổng phổ có hợp âm đó.

**Pha 1 — Dialect, texture Bước 4 giữ nguyên.** `BarriosDialect` trong `harmony.py`, bốn hợp âm thứ, bảng cạnh thứ và ba cạnh chuỗi át trưởng, `allowed` / `bias` / `color_credit`, `quality_group` của `+6`, và điều kiện một ô cho `"augmented-sixth"` trong `form.py`. Không sửa `minor_bias`. Chưa có lớp dance. Nghe vòng trên tremolo và thánh ca hiện có: chuỗi hợp âm đổi, cách gảy chưa đổi.

**Pha 2 — Lớp dance.** `barrios_layer` nhận meter và thêm nhánh `"dance"` đúng thứ tự mục 4.1. Renderer viết hai mẫu. Profile `barrios_dance`. Số móc lấy từ Pha 0; nếu Pha 0 chưa sửa, dùng đề xuất mục 4.2 và 4.3.

**Pha 3 — Nghe.** Checklist mục 7. Sai chất thì sửa trọng số hoặc số móc trong file này trước, rồi mới sửa code.

Khi Pha 1 vào code, gỡ câu Barrios đi `COMMON` ở cả các chỗ sau của file guitar, cùng commit với dialect: dòng trạng thái; nguyên tắc 5; đoạn pipeline (`Sor và Barrios dùng slots của dialect COMMON`); đoạn `DIALECTS` (không có dòng `barrios`); mục 4.3; Bước 3 («không có khóa trong `DIALECTS`»); hàng `harmony.py` trong bảng file. Cuối test 11, câu `dialect_for("barrios")` là `COMMON` đổi thành `BarriosDialect`. Phần «`barrios` không sinh sus / add9» của test đó giữ nguyên: dialect này không có hai chất ấy.

---

## 6. Test khóa ở Pha 1 và Pha 2

Pha 1, trong `test_harmony.py`:

1. `dialect_for("barrios")` là `BarriosDialect`. `dialect_for("classic")` là `COMMON`. `dialect_for("villa")` vẫn sinh `Csus4` đúng các ca đã khóa. Symphony và `classic` ở thứ không sinh `Bb`, `Ab+6`, `D7`. `extra()` thứ là đúng bốn tên: `Bb`, `Bb7`, `D7`, `Ab+6`. `extra()` trưởng rỗng.
2. Hợp âm `extra()` trên đường thứ nhận sàn 0.08 trong planner, không qua `minor_bias`. `Bb` dừng ở 0.08. `Bb7`, `D7` và `Ab+6` thêm 0.05 thành 0.13. Không có test gọi thẳng `minor_bias(Bb)`.
3. Thứ, ô trước `Fm`, mọi phách mạnh thuộc {Si♭, Rê, Fa}: ra `Bb`. Thêm La♭ ở phách mạnh: ra `Bb7`.
4. Thứ, ô trước `Bb`, phách mạnh Mi♭: ra `Eb` hoặc `Ebmaj7`.
5. Thứ, ô trước `Ab`, phách mạnh Rê, các móc khác thuộc {Rê, Đô}: ra `D7`. Cùng ô mà phách mạnh là La♭: không ra `D7`.
6. Thứ, ô trước `Cm`, mọi móc là Sol: ở lại `Cm`, giá giữ 0.15. Thêm Si♭ ở phách mạnh, `prev_held == 1`: ra `Cm7`. `Cm7` giá 0.50 và chứa cả Sol lẫn Si♭. Sol hát Si♭ với phát xạ 0, nhưng cửa Đô→Sol 0.10 giá khoảng 1.42 rồi còn cộng phạt đổi ô, nên đắt hơn. `prev_held == 2`, ô thường không phải phách đầu trio: Sol khoảng 1.42, Sol7 khoảng 1.47, Mi♭ khoảng 1.58, `Cm7` khoảng 1.68, ra `G` hoặc `G7`. Không khóa `Cm7` từ ô thứ ba. Không có `Db` hay `C#dim7` trong dialect.
7. Thứ, mọi móc thuộc {La♭, Đô, Mi♭}, ô giữa câu, không phải phách đầu câu và không phải pedal. Gốc Fa đã giữ từ hai ô, ô trước là `Fm`, và đường kết tại ô này hoặc ô sau ngồi trên {Sol, Rê}: ra `Ab+6`. Thêm Fa ở ô sau thì ra được `G7`. Ô thứ hai của gốc Fa: ra `Fm7`. Ô mở section, kể cả khi ô trước là `Fm`: không ra `Ab+6`. Ô trước `Cm`, mọi móc thuộc {Đô, Mi♭}: ở lại `Cm`. Không có vế Fa♯°7 trên thang.
8. `Ab+6` không đi từ `Ab`. Ô sau `Ab+6` là `G` hoặc `G7`. `Ab+6` không đứng hai ô. Ba ô liên tiếp toàn {La♭, Đô, Mi♭} không mở sext tăng.
9. Thứ, ô trước `Bb`, phách mạnh Sol: ra `G` hoặc `G7`. Ô có Si♭ được Sol và Sol7 hát thành Si, nên hai hợp âm đó không mất 2.5 trên Si♭; nốt Si tự nhiên thì `bar_quantization_loss` ném lỗi. Ô chỉ Si♭, `prev_held == 1`: ở lại `Bb`. Cùng ô sau khi `Bb` đã giữ hai ô: ra `G` hoặc `G7`, không ở lại `Bb`.
10. Trưởng, sau `A7`. Phách mạnh Đô, La hoặc Rê: ô sau là `D7`. Phách mạnh Fa: ô sau là `Dm` hoặc `Dm7`. Không khóa bằng Fa♯.
11. Trưởng, ô thuộc {Mi, Sol} sau Đô ở lại Đô. `extra()` trưởng không có `C#dim7`.
12. Ô pedal thứ là `Cm` hoặc `Cm7` dù phách mạnh là Si♭. Phách đầu câu không phải `Bb` hay `Ab+6`.
13. `color_credit` của mọi hợp âm Barrios là 0. Ô chỉ có Đô và Sol, gốc trước Đô, không ra `Bb`.
14. `transpose_chord` của `Ab+6` giữ Fa♯ là sext tăng, không viết thành Sol♭.

Pha 2, trong `test_sonify_guitar.py`:

1. 3/4, câu nốt chạy, band `mf`: tremolo hoặc thánh ca, không một ô dance.
2. 4/4, tempo ≤ 100, giai điệu giữ ≥ 2 phách, band `mf`: tremolo đầy, móc kép 0 là Trầm.
3. 4/4, giai điệu đổi từng móc đơn, band `mf`, character `rally`: dance. Trong mỗi nửa ô có nốt ở móc 0, 3, 4, 6, 7 (hoặc số Pha 0 đã sửa), và mọi nốt Cao trên móc chẵn trùng nốt dữ liệu.
4. 4/4, character `calm`: không dance.
5. Ô `intro`: Preludio, không dance.
6. 6/8, 120 BPM, band `f`, giai điệu giữ nốt: dance. Đệm chỉ ở móc kép 0, 4, 8. Móc kép 2, 6, 10 không có nốt Trung mới.
7. 6/8, 120 BPM, band `mp`, giai điệu giữ ≥ 2 phách: tremolo lưới giảm (ngón cái ở móc kép 0 và 6, giai điệu ở móc kép 2 và 8).
8. 4/4, 108 BPM, giai điệu giữ ≥ 2 phách, band `mf`: tremolo lưới giảm của phách đen — ngón cái ở móc kép 0 và giai điệu ở móc kép 2 của từng phách. Không có chuỗi `p–a–m–i` bốn nốt trong một phách.
9. Ô dance 4/4 có gốc sau thấp hơn một quãng 5: móc kép 15 là nốt Trầm nửa cung dưới gốc sau. Ô 6/8 cùng điều kiện: móc kép 11 là nốt Trầm đó, và móc kép 10 của polca vẫn là nốt Trung nếu band chưa tới `f`. Ô không rơi quãng 5: hai móc đó không phải nốt chromatic. Profile `study` báo lỗi trên nốt dẫn; profile `barrios_dance` im.

---

## 7. Nghe, sau Pha 2

Năm mã × bốn character, ở `1D` (4/4, 76 BPM) và ở `1M` (chương chậm 3/4, scherzo 6/8):

- [ ] `1D`, câu nốt ngắn, `rally` hoặc `volatile`: đệm lệch phách kiểu choro, giai điệu vẫn là nốt giá. Chuỗi át có đi tiếp khi giá ngồi trên Đô, La hoặc Rê, và có chịu về hợp âm thứ khi giá ngồi trên Fa.
- [ ] `1D`, câu giữ nốt: vẫn tremolo ngân, bass đầu phách, không bị levada cắt vụn.
- [ ] Chương chậm 3/4: không có nhịp choro. Thánh ca và tremolo như Bước 4.
- [ ] Scherzo 6/8 band `f`: nghe ra polca hoặc hemiola, không nghe tremolo rè.
- [ ] Phiên thứ, ô {Si♭, Rê, Fa} sau Fa thứ: một ô Si♭, rồi đi tiếp. Không có ô Rê♭.
- [ ] Mở bài: Preludio, hợp âm chủ ở pedal, chưa có hợp âm Si♭.
- [ ] `calm`: không dance, không dày hơn bản Bước 4.

---

## 8. File đụng khi code

| Pha | File | Việc |
|---|---|---|
| 1 | `backend/app/sonify/chords.py` | `Ab+6` với `degrees=(0, 2, 4, 5)` và `pitches` kết bằng 78. `quality_group` nhận `+6`. `Bb`, `Bb7`, `D7` lấy hợp âm sẵn có |
| 1 | `backend/app/sonify/harmony.py` | `BarriosDialect`, khóa `barrios` trong `DIALECTS`. Hai bảng cạnh tách mode |
| 1 | `backend/app/sonify/form.py` | Một ô cho `"augmented-sixth"` cạnh `"diminished"`, trước nhánh `BORROWED_HOLD_PROB` |
| 1 | `backend/tests/test_harmony.py` | Mục 6, Pha 1 |
| 2 | `backend/app/sonify/guitar.py` | Nhánh `dance`, hai mẫu, profile |
| 1 | `docs/sonify-classical-guitar.md` | Gỡ câu «Barrios đi COMMON» và test 11 tương ứng, cùng commit với dialect |
| 2 | `backend/tests/test_sonify_guitar.py` | Mục 6, Pha 2 |
