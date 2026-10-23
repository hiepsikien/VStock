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

Hòa âm này là hợp âm chức năng. Không có sus, không có add9. Những hợp âm thêm sở hữu một pitch-class mà catalog thứ không có (Si♭, Rê♭, Fa♯ của sext tăng), nên phạt phách mạnh 2.5 đã kéo chúng vào đúng ô. `color_credit` của dialect này trả 0. Khoản 0.70 là của Villa.

---

## 2. Vì sao catalog chung không ra chất này

Nhạc thứ của Barrios đi một vòng quãng 5 dài. Allegro Solemne của *La Catedral* (Si thứ), ô 141–150, gốc Fa♯–Si–Mi–La–Rê–Sol–Đô♯–Fa♯ (John Hall). Hạ về Đô thứ của catalog:

**Sol – Đô – Fa – Si♭ – Mi♭ – La♭ – Rê7 – Sol**

tức V–i–iv–♭VII–III–VI–V/V–V. Mắt La♭→Rê là quãng 5 giảm, mắt duy nhất không phải quãng 5 đúng, để vòng khép trên át. Rê ở mắt đó là át của át (hợp âm bảy), đúng cú «iiø bật thành V/V» mà Andante và Allegro dùng (Đô♯ nửa giảm → Đô♯7 ở Si thứ).

Preludio Saudade thêm sequence ngắn Si–Mi–La, tức i–iv–♭VII, trên bass ostinato lệch phách. *Una Limosna por el Amor de Dios* (Mi thứ) thêm cadence i → VI → Napolitaine (♭II) → ii → V.

`MINOR_CATALOG` có i, iv, iiø, V, V7, VI, III và Fa♯°7 giải vào Sol. Thiếu Si♭, Rê♭, Rê7, và La♭ có sext tăng. Hàng Fa của `_ROOT_TRANSITIONS` không có cạnh sang Si. Vì vậy vòng gãy đúng những mắt tạo chất.

Ở trưởng, choro (*Choro da Saudade*, và đệm của nhiều bản salon) là chuỗi át phụ rơi quãng 5: Mi7→La7→Rê7→Sol7→Đô, cộng một giảm bảy đi qua nằm nửa cung dưới hợp âm đích. `BORROWED` đã có các át phụ đó, nhưng La7 chỉ được giải vào Rê thứ (0.40), Rê7 ưu tiên Sol hợp âm ba (0.46) hơn Sol7 (0.34). Chuỗi át bảy không tự đi. Giảm bảy đi qua vào ii thì chưa có: catalog chỉ có Fa♯°7 vào Sol.

Planing hợp âm 6/3 của Andante và Preludio là luật viết bè của lớp Thánh ca / Preludio trong file guitar, không phải hợp âm mới. Trưởng cùng tên ở coda của *Una Limosna* là đổi mode, ngoài pipeline một-mode-mỗi-bài.

---

## 3. `BarriosDialect`

Đăng ký:

```python
DIALECTS = {"villa": VILLA, "barrios": BARRIOS}
```

`dialect_for("barrios")` trả dialect này. `dialect_for("classic")` và đường symphony vẫn là `COMMON`. `transition` đã được `plan_markov_chords` gọi cho mọi cặp; `None` để Markov cũ chạy. Dialect này dùng đúng cửa đó.

### 3.1. Hợp âm thêm

Sinh trong không gian Đô, rồi `transpose_chord` đẩy đi như mọi hợp âm khác. Thứ dùng bảy hợp âm dưới. Trưởng chỉ thêm Đô♯°7; chuỗi át phụ trưởng dùng hợp âm `BORROWED` sẵn có, chỉ thêm cạnh.

| Tên | Mode | Nguồn | `root_step`, `alter` | Nốt | Vai |
|---|---|---|---|---|---|
| `Bb` | thứ | `BF` sẵn có | B, −1 | Si♭–Rê–Fa | ♭VII |
| `Bb7` | thứ | `BF7` sẵn có | B, −1 | Si♭–Rê–Fa–La♭ | ♭VII7, át của III |
| `Db` | thứ | mới | D, −1 | Rê♭–Fa–La♭ | Napolitaine, ♭II |
| `D7` | thứ | `D7` sẵn có | D, 0 | Rê–Fa♯–La–Đô | V/V |
| `Ab+6` | thứ | mới | A, −1 | La♭–Đô–Mi♭–Fa♯ | sext tăng Đức, vào V |
| `C#dim7` | thứ và trưởng | mới | C, +1 | Đô♯–Mi–Sol–Si♭ | giảm bảy đi qua, vào ii hoặc vào V/V |

`Db`:

```python
Chord("Db", "D", KIND_MAJOR, "", (61, 65, 68), alter=-1,
      tones=((1, "D", -1), (8, "A", -1)))
```

`C#dim7`, cùng kiểu với `F#dim7`:

```python
Chord("C#dim7", "C", KIND_DIMINISHED_SEVENTH, "°7", (61, 64, 67, 70),
      alter=1, tones=((1, "C", 1), (10, "B", -1)))
```

`Ab+6` không phải La♭7. Âm đặc trưng là Fa♯, sext tăng, giải ra ngoài vào gốc của át. Lời gọi phải mang `degrees`, vì hai constructor `Db` và `C#dim7` không có trường này và đường mặc định không áp cho hợp âm này:

```python
Chord(
    "Ab+6", "A", KIND_OTHER, "+6", (68, 72, 75, 78),
    alter=-1, degrees=(0, 2, 4, 5),
    tones=((8, "A", -1), (3, "E", -1), (6, "F", 1)),
)
```

`(68, 72, 75, 78)` là La♭4–Đô5–Mi♭5–Fa♯5. Fa♯ 66 nằm dưới gốc và không dùng. Pitch-class không đổi nên Viterbi không đổi; bậc 5 là chữ Fa. Thiếu `degrees`, `transpose_chord` lấy `index * 2` cho nốt thứ tư và viết Sol♭. `quality_group` trả `"augmented-sixth"` khi `kind_text == "+6"`, đặt trước nhánh mặc định `"major"`. Ở thứ, cùng `root_step` và cùng `alter` đã là cùng gốc trước khi xét nhóm. Nhóm này chỉ để luật một ô bắt được hợp âm. Rơi vào `"major"` thì luật đó bỏ qua, và La♭ → `Ab+6` thành đổi chất hợp lệ với giá 0.50 (`SECOND_BAR_STAY_COST` 0.15 cộng phạt đổi chất 0.35).

Tỉa theo mục 5.3 của file guitar: hợp âm bốn nốt bỏ `pitches[2]` (quãng 5) trước. `Ab+6` còn La♭–Đô–Fa♯. `D7` còn Rê–Fa♯–Đô. `Bb7` còn Si♭–Rê–La♭. `C#dim7` còn Đô♯–Mi–Si♭. Không gọi `jazz_chord` trên slot của dialect này.

### 3.2. Cạnh — tường minh với mọi cặp đụng `extra()`

`transition` trả một số khi một trong hai hợp âm thuộc `extra()` của mode đang chạy, hoặc khi cặp nằm trong bảng chuỗi át trưởng ở mục 3.4. Số 0 là cấm. Không có trong bảng, mà một đầu thuộc `extra()`, cũng trả 0. Mọi cặp khác trả `None`.

Cửa này bắt buộc vì hai va chạm `root_step`:

- `Bb` / `Bb7` có `root_step` B. `_ROOT_TRANSITIONS` không có hàng B. Trả `None` thì mọi cửa từ Si♭ là 0, hợp âm không bao giờ được chọn.
- `Db` dùng `root_step` D, nên trả `None` sẽ đi nhầm cửa của ii (Rê→Sol = 0.34, Rê→La = 0.14). `C#dim7` dùng `root_step` C, nên trả `None` sẽ nhận xác suất ở-lại của chủ (0.18).

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

**Khép vòng và bật iiø thành V/V**

| Cặp | Trọng số |
|---|---|
| `Ab`/`Abmaj7` → `D7` | 0.48 / 0.40 |
| `Dm7b5` → `D7` | 0.40 |
| `D7` → `G` | 0.46 |
| `D7` → `G7` | 0.55 |
| `D7` → `D7` | 0.12 |

Không có hợp âm ba Rê trưởng. Mọi nốt của hợp âm ba đó đã nằm trong `D7`, và cửa vào `D7` rẻ hơn, nên hợp âm ba không bao giờ thắng. `D7` không chứa La♭: phách mạnh La♭ sau La♭ ở lại VI hoặc đi Napolitaine, không bị hút sang V/V.

`Dm7b5` → `D7` cùng gốc. Ô thứ hai của gốc (`prev_held == 1`) lấy 0.15 cộng phạt đổi chất 0.35, thành 0.50. Cạnh 0.40 không vào cú bật đó. Cạnh ấy chỉ vào khi gốc đã giữ từ hai ô: `−0.6·ln(0.40) ≈ 0.55`, cộng `EXTENDED_STAY_PENALTY` 0.25, rồi cộng phạt đổi chất. Ở lại trên `Dm7b5` ở ô thứ hai chỉ tốn 0.15 khi cả hai hợp âm đều chứa phách mạnh. Cú bật nghe được khi phách mạnh là Fa♯ hoặc La: nửa giảm không chứa hai nốt đó và mất 2.5.

Phách mạnh Fa♯ sau La♭ thì `D7` thắng Fa♯°7. Cửa vào Fa♯°7 là 0.06 với mọi hợp âm trước (`minor_root_probability`), giá `−0.6·ln(0.06) ≈ 1.68` cộng `minor_bias` 0.08 thành ≈ 1.76. `D7` cửa 0.48 giá ≈ 0.44, cộng sàn `extra()` bốn nốt 0.13, thành ≈ 0.57.

**Napolitaine**

| Cặp | Trọng số |
|---|---|
| `Cm`/`Cm7` → `Db` | 0.14 / 0.12 |
| `Ab`/`Abmaj7` → `Db` | 0.22 / 0.18 |
| `Fm`/`Fm7` → `Db` | 0.16 |
| `Db` → `G` | 0.46 |
| `Db` → `G7` | 0.52 |
| `Db` → `Dm7b5` | 0.28 |
| `Db` → `Db` | 0.14 |

`Db` chứa Rê♭–Fa–La♭. Phách mạnh chỉ là Rê♭ thì nó thắng `C#dim7`: cửa 0.14 giá chuyển tiếp ≈ 1.18 cộng sàn extra ba nốt 0.08 thành ≈ 1.26; cửa 0.10 giá ≈ 1.38 cộng sàn bốn nốt 0.13 thành ≈ 1.51. Phách mạnh có Sol (nốt của giảm bảy, không có trong Rê♭) thì giảm bảy thắng.

**Sext tăng**

| Cặp | Trọng số |
|---|---|
| `Fm`/`Fm7` → `Ab+6` | 0.24 / 0.20 |
| `Cm`/`Cm7` → `Ab+6` | 0.06 |
| `Ab+6` → `G` | 0.62 |
| `Ab+6` → `G7` | 0.55 |

`Ab+6` là một ô nhờ nhóm `"augmented-sixth"`, không nhờ cạnh tự thân bằng 0. Khi `transition` trả ≤ 0 mà chất không phải `"diminished"`, vòng lặp đổi tự thân thành `BORROWED_HOLD_PROB` 0.16. Luật một ô phải thấy `"augmented-sixth"` trước nhánh đó thì ô giữ mới bị chặn. Thêm nhóm này vào điều kiện đang dành cho `"diminished"` trong `form.py` (`target_held != 1`). Hai việc đi cùng nhau: nhóm chất, và điều kiện một ô. Cùng gốc với La♭ nên nhánh `same_root` đòi `held == 2`; luật một ô cấm `held == 2`; vậy `Ab+6` không đi được từ La♭ / La♭maj7. Nó vào từ chủ hoặc từ hạ át, rồi ra Sol.

Fa♯°7 không đi cửa gốc Fa. `minor_root_probability` trả 0.06 cho mọi hợp âm đi vào nó, rồi `minor_bias` cộng 0.08. `Ab+6` mang sàn `extra()` 0.13. Mọi móc của ô thuộc {Fa♯, Đô, Mi♭} — giao của hai hợp âm — thì phạt 2.5 không tách được chúng:

- Sau Fa thứ, cửa 0.24 giá ≈ 0.86 + 0.13 ≈ 0.99. `Ab+6` rẻ hơn Fa♯°7 (≈ 1.76) khoảng 0.78.
- Sau Đô thứ, cửa 0.06 giá ≈ 1.68 + 0.13 ≈ 1.81. Fa♯°7 rẻ hơn 0.05. Cửa 0.12 đảo người thắng: 1.27 + 0.13 ≈ 1.40, rẻ hơn khoảng 0.36. Móc yếu lệch một bậc nặng 0.02 (`WEAK_BEAT_WEIGHT`). Khoản 0.05 chịu hai móc như vậy và thua từ móc thứ ba, nên test khóa mọi móc thuộc giao, không chỉ phách mạnh.

**Giảm bảy đi qua, trong thứ**

| Cặp | Trọng số |
|---|---|
| `Cm`/`Cm7` → `C#dim7` | 0.10 |
| `C#dim7` → `D7` | 0.55 |

`C#dim7` một ô bởi luật giảm bảy sẵn có: chất `"diminished"` không bị đổi tự thân thành 0.16. Bảng này chỉ thuộc mode thứ. `C#dim7` → `D7` không có ở trưởng. Mọi cửa khác có một đầu là hợp âm `extra()` của thứ, không nằm ở các bảng trên, trả 0.

### 3.4. Bảng cạnh, mode trưởng — chuỗi choro

Sáu cặp trong bảng được trả số: ba mắt chuỗi át, cửa `C`/`Cmaj7` → `C#dim7`, và hai cửa từ `C#dim7` ra Rê thứ. Các cửa còn lại của La7, Rê7, Mi7 giữ `borrowed_transition`. Bảng trưởng và bảng thứ không gộp một dict: `C#dim7` → `D7` ở đây trả 0.

| Cặp | Trọng số |
|---|---|
| `E7` → `A7` | 0.55 |
| `A7` → `D7` | 0.55 |
| `D7` → `G7` | 0.55 |
| `C`/`Cmaj7` → `C#dim7` | 0.20 / 0.18 |
| `C#dim7` → `Dm` | 0.62 |
| `C#dim7` → `Dm7` | 0.55 |

`A7` → `Dm` vẫn 0.40. `D7` → `G` vẫn 0.46. Giá chuyển tiếp khi cả hai hợp âm đều chứa phách mạnh:

- `A7` → `D7` giá `−0.6·ln(0.55) ≈ 0.36`. `A7` → `Dm` giá ≈ 0.55. Rê thứ còn lợi khoảng 0.02 vì `D7` mang sàn hợp âm mượn 0.08 còn Rê thứ nằm trong `CHORDS`. Chuỗi vẫn rẻ hơn khoảng 0.17. Phách mạnh là Fa (âm ba thứ, không có trong Rê7) thì Rê7 mất 2.5 và Rê thứ thắng. Phách mạnh Fa♯ thì chuỗi đi tiếp.
- `D7` → `G7` giá ≈ 0.36. `D7` → `G` giá ≈ 0.47. Sol7 thắng khi cả hai đều chứa phách mạnh. Phách mạnh Fa (âm 7 của Sol7, không có trong Sol) giữ Sol7; không cần phạt thêm.

`C#dim7` ở trưởng chỉ giải vào Rê thứ / Rê thứ bảy. Mọi cửa khác có `C#dim7` trả 0.

### 3.5. `allowed`, `bias`, `color_credit`

`allowed` trả `True` với hợp âm không thuộc `extra()`, để `_borrowed_allowed` chạy tiếp. Mọi hợp âm `extra()` trả `False` ở ô pedal và ở phách đầu câu. Ô pedal vẫn là hợp âm chủ. Câu vẫn mở bằng chủ; vòng và Napolitaine đứng từ ô thứ hai của câu.

`bias`, cộng thêm lên bias sẵn có, trị tuyệt đối dưới 0.1:

| Điều kiện | Mức |
|---|---|
| `selloff`, thứ, `Db` | −0.08 |
| `volatile`, hợp âm là `Bb`, `Bb7`, `D7` hoặc `C#dim7` | −0.06 |
| `rally`, `D7` hoặc `Bb7` | −0.04 |

Không có mức +0.08 cho `C#dim7`. Hợp âm đó đã nhận sàn `extra()` 0.13 trước bias dialect (mục 3.6). Cộng thêm 0.08 thành 0.21, đắt hơn mọi hợp âm lạ bốn nốt. Không mức nào trong bảng bù được phạt phách mạnh 2.5.

`color_credit` trả 0 với mọi hợp âm, kể cả khi `prev` là `None`.

### 3.6. Sàn của hợp âm `extra()`

Trong vòng lặp, hợp âm thuộc `extra()` nhận sàn 0.08 ngay, rồi hợp âm bốn nốt cộng `SEVENTH_TENSION_COST` 0.05. `minor_bias` chỉ chạy cho hợp âm còn lại. `Bb` chỉ sống trong `extra()`, nên `root_step` B không chạm `_MINOR_ROOT_BIAS` và không ném `KeyError` trên đường planner. Pha 1 không sửa `minor_bias`. Gọi thẳng `minor_bias(Bb)` vẫn lỗi; đó không phải đường chọn hợp âm.

`C#dim7` cùng cửa này: sàn trước bias dialect là 0.13. `Db` ba nốt dừng ở 0.08. Fa♯°7 không thuộc `extra()`, nên vẫn đi `minor_bias` và giữ 0.08.

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

- *La Catedral*, Allegro, quanh ô 141–150: đúng gốc Fa♯–Si–Mi–La–Rê–Sol–Đô♯–Fa♯, và chất của mắt Đô♯ (bảy hay ba).
- Preludio: sequence Si–Mi–La và chỗ nó rơi vào át.
- *Una Limosna*: ô vào Napolitaine và ô sext tăng hoặc giảm bảy dẫn vào át, nếu có.
- *Choro da Saudade*: mẫu tay phải một ô, tính bằng móc kép, và chuỗi át thực sự đi những bậc nào.
- *Danza Paraguaya*: mẫu 6/8, và ô nào melody hát theo 3/4 trên đệm 6/8.

Đầu ra sửa mục 4.2 và 4.3 của file này nếu số móc lệch. Bảng cạnh mục 3 chỉ sửa khi tổng phổ cho một cửa khác hẳn (ví dụ mắt Đô♯ là hợp âm ba, không phải bảy — trường hợp đó mới mở lại quyết định bỏ hợp âm ba Rê).

**Pha 1 — Dialect, texture Bước 4 giữ nguyên.** `BarriosDialect` trong `harmony.py`, bảy hợp âm, hai bảng cạnh tách theo mode, `allowed` / `bias` / `color_credit`, `quality_group` của `+6`, và điều kiện một ô cho `"augmented-sixth"` trong `form.py`. Không sửa `minor_bias`. Chưa có lớp dance. Nghe vòng trên tremolo và thánh ca hiện có: chuỗi hợp âm đổi, cách gảy chưa đổi.

**Pha 2 — Lớp dance.** `barrios_layer` nhận meter và thêm nhánh `"dance"` đúng thứ tự mục 4.1. Renderer viết hai mẫu. Profile `barrios_dance`. Số móc lấy từ Pha 0; nếu Pha 0 chưa sửa, dùng đề xuất mục 4.2 và 4.3.

**Pha 3 — Nghe.** Checklist mục 7. Sai chất thì sửa trọng số hoặc số móc trong file này trước, rồi mới sửa code.

Khi Pha 1 vào code, gỡ câu Barrios đi `COMMON` ở cả các chỗ sau của file guitar, cùng commit với dialect: dòng trạng thái; nguyên tắc 5; đoạn pipeline (`Sor và Barrios dùng slots của dialect COMMON`); đoạn `DIALECTS` (không có dòng `barrios`); mục 4.3; Bước 3 («không có khóa trong `DIALECTS`»); hàng `harmony.py` trong bảng file. Cuối test 11, câu `dialect_for("barrios")` là `COMMON` đổi thành `BarriosDialect`. Phần «`barrios` không sinh sus / add9» của test đó giữ nguyên: dialect này không có hai chất ấy.

---

## 6. Test khóa ở Pha 1 và Pha 2

Pha 1, trong `test_harmony.py`:

1. `dialect_for("barrios")` là `BarriosDialect`. `dialect_for("classic")` là `COMMON`. `dialect_for("villa")` vẫn sinh `Csus4` đúng các ca đã khóa. Symphony và `classic` ở thứ không sinh `Bb`, `Db`, `Ab+6`, `D7`.
2. Hợp âm `extra()` trên đường thứ nhận sàn 0.08 trong planner, không qua `minor_bias`. `Bb` và `Db` dừng ở 0.08. `Bb7`, `D7`, `Ab+6` và `C#dim7` thêm 0.05 thành 0.13. Không có test gọi thẳng `minor_bias(Bb)`.
3. Thứ, ô trước `Fm`, mọi phách mạnh thuộc {Si♭, Rê, Fa}: ra `Bb`. Thêm La♭ ở phách mạnh: ra `Bb7`.
4. Thứ, ô trước `Bb`, phách mạnh Mi♭: ra `Eb` hoặc `Ebmaj7`.
5. Thứ, ô trước `Ab`, phách mạnh Fa♯ (và không có La♭): ra `D7`. Cùng ô mà phách mạnh là La♭: không ra `D7`.
6. Thứ, ô trước `Cm`, phách mạnh chỉ Rê♭: ra `Db`, không ra `C#dim7`. Thêm Sol ở phách mạnh: ra `C#dim7`.
7. Thứ, mọi móc của ô thuộc {Fa♯, Đô, Mi♭}. Ô trước `Fm`: ra `Ab+6`. Ô trước `Cm`: ra `F#dim7`. Khóa mỗi phách mạnh chưa đủ: từ móc yếu lệch bậc thứ ba (0.02 một móc), vế Đô thứ đổi người thắng.
8. `Ab+6` không đi từ `Ab`. Ô sau `Ab+6` là `G` hoặc `G7`. `C#dim7` không đứng hai ô.
9. `Db` rồi phách mạnh thuộc {Sol, Si, Rê}: ra `G` hoặc `G7`.
10. Trưởng, phách mạnh Fa♯ trên đường La7: ô sau là `D7`. Cùng chỗ mà phách mạnh là Fa: ô sau là `Dm` hoặc `Dm7`.
11. Trưởng, Đô rồi Đô♯°7 rồi Rê thứ, khi phách mạnh lần lượt là Đô, Đô♯, Rê. `C#dim7` không giữ ô, và không đi sang `D7`.
12. Ô pedal thứ là `Cm` hoặc `Cm7` dù phách mạnh là Si♭ hoặc Rê♭. Phách đầu câu không phải `Db` hay `Ab+6`.
13. `color_credit` của mọi hợp âm Barrios là 0. Ô chỉ có Đô và Sol, gốc trước Đô, không ra `Db` hay `Bb`.
14. `transpose_chord` của `Ab+6` giữ Fa♯ là sext tăng, không viết thành Sol♭. `Db` giữ quãng 5 là La♭.

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

- [ ] `1D`, câu nốt ngắn, `rally` hoặc `volatile`: đệm lệch phách kiểu choro, giai điệu vẫn là nốt giá. Chuỗi át có đi tiếp khi giá ngồi trên âm dẫn, và có chịu về hợp âm thứ khi giá ngồi trên âm ba thứ.
- [ ] `1D`, câu giữ nốt: vẫn tremolo ngân, bass đầu phách, không bị levada cắt vụn.
- [ ] Chương chậm 3/4: không có nhịp choro. Thánh ca và tremolo như Bước 4.
- [ ] Scherzo 6/8 band `f`: nghe ra polca hoặc hemiola, không nghe tremolo rè.
- [ ] Phiên `selloff` thứ, giá chạm bậc hạ hai: có một ô Napolitaine rồi át, không trải Rê♭ suốt câu.
- [ ] Mở bài: Preludio, hợp âm chủ ở pedal, chưa có Si♭ hay Rê♭.
- [ ] `calm`: không dance, không dày hơn bản Bước 4.

---

## 8. File đụng khi code

| Pha | File | Việc |
|---|---|---|
| 1 | `backend/app/sonify/chords.py` | `Db`, `C#dim7`, `Ab+6` với `degrees=(0, 2, 4, 5)` và `pitches` kết bằng 78. `quality_group` nhận `+6` |
| 1 | `backend/app/sonify/harmony.py` | `BarriosDialect`, khóa `barrios` trong `DIALECTS`. Hai bảng cạnh tách mode |
| 1 | `backend/app/sonify/form.py` | Một ô cho `"augmented-sixth"` cạnh `"diminished"`, trước nhánh `BORROWED_HOLD_PROB` |
| 1 | `backend/tests/test_harmony.py` | Mục 6, Pha 1 |
| 2 | `backend/app/sonify/guitar.py` | Nhánh `dance`, hai mẫu, profile |
| 1 | `docs/sonify-classical-guitar.md` | Gỡ câu «Barrios đi COMMON» và test 11 tương ứng, cùng commit với dialect |
| 2 | `backend/tests/test_sonify_guitar.py` | Mục 6, Pha 2 |
