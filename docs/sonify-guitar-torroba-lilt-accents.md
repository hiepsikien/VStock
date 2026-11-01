# Torroba: trọng âm bậc thang 3/4 – 6/8 và độ du di nhịp Tây Ban Nha (*Aire español / Rubato*)

> **Trạng thái**: đã vào code.
> **Đọc cùng**: [`docs/sonify-guitar-torroba-meter-doors.md`](./sonify-guitar-torroba-meter-doors.md), [`docs/sonify-guitar-torroba-dynamics.md`](./sonify-guitar-torroba-dynamics.md), [`docs/sonify-guitar-torroba-phrase-plan.md`](./sonify-guitar-torroba-phrase-plan.md) mục 4, [`docs/sonify-humanize-timing-plan.md`](./sonify-humanize-timing-plan.md).
> **Giữ**: Lưới nhịp `3/4`, `6/8`, `4/4` đã khóa. Một tâm sóng `round(C)` và một `extra` cho cả ô (`_WHOLE_BAR_EXTRA`). Không dùng Jazz swing (`swing=True`). Không sửa `duration_beats` của `NoteEvent`.

Ba việc:

1. **Phân tầng trọng âm viết trên `6/8` và `3/4`:** Trên `6/8` của các điệu vũ (`danza`, `fandanguillo`, và `_alcaniz_dance` khi `accented=True`), móc đơn `0` là trọng âm chính (`max(ordinary, 68)`, `accent=True`), móc đơn `3` là trọng âm phụ (`max(ordinary - 2, 66)`, `accent=False`). Trên `3/4` (`_render_sonatina_moving`, `_render_juglar_bar`), phách 1 (móc `0`) giữ `ordinary`, còn các phách sau hạ 1 bậc (`-2`) khi móc đó không nằm trong đỉnh (`apex`) của câu sở hữu chính móc đó (`_phrase_covering`).
2. **Đồng bộ bậc lực `steps` trong `_type4_call`:** Đưa cụm hai móc kép + một móc đơn tại `beat = 0.5, 0.75, 1.0` của `_type4_call` từ `steps = 1, 1, 1` sang `steps = 2, 2, 1` giống `_type3_motif` (không gắn thêm `tenuto`, không đụng `_into_strong`).
3. **Mở rộng `_tempo_clock` cho `("guitar", "torroba")` bằng tổng ba độ lệch zero-sum độc lập:** Tầng câu ($\Delta_{\text{phrase}}$), tầng đầu ô ($\Delta_{\text{bar}}$), và tầng lilt ($\Delta_{\text{lilt}}$) tự triệt tiêu trung bình về `0.0` ngay trong phạm vi của chính nó, cộng tuyến tính vào `1.0`, co tỷ lệ toàn câu nếu chạm trần `±0.10`, và giữ mốc trả `nominal` tại `phrase.end`.

---

## 1. Trọng âm bậc thang trên `6/8` và `3/4`

### 1.1. Hiện trạng trong code

- `METER_68` đặt `strong_eighths = (0, 3)`. Trong `backend/app/sonify/guitar_torroba.py`, `_lead_velocity`, `_block`, `_answer`, `_alcaniz_dance` (khi `accented=True`) và `_alcaniz_opening` đang cho cả móc `0` và móc `3` sàn `68` và `accent=True`.
- Trong `guitar_wave.py`, `_is_target` của `fandanguillo`, `danza`, `alcaniz`, `olite` nhận mọi `lead` có `accent=True`.
- Trên `3/4`, `_render_sonatina_moving` viết nốt đen ở móc `0`, hai móc đơn ở móc `2, 3`, và một nốt đen ở móc `4` (phủ móc `4–5`, không có nốt riêng ở móc `5`). `_render_sonatina_bar` trên `6/8` không được bảng chọn pattern gọi.

### 1.2. Trọng âm trên `6/8` (chỉ áp cho lưới điệu có nhấn: `danza`, `fandanguillo`, `_alcaniz_dance` khi `accented=True`)

- **Không áp cho `_alcaniz_opening`:** ở `_alcaniz_opening`, móc `3` là đích của cặp slur đi vào (`slur_stop=True`), giữ nguyên `max(arrival, 68)` và `accent=True` để không làm yếu nốt câu đang đổ tới.
- **Không áp cho `_alcaniz_dance` khi `accented=False` (`mode == "pushed"`):** ô `pushed` giữ cả móc `0` và móc `3` ở `ordinary` (`64` trên câu phẳng) và `accent=False`. Nếu áp sàn `max(ordinary - 2, 66)` khi `accented=False`, móc `3` sẽ thành `66` trong khi móc `0` vẫn ở `64`.
- **Không áp cho hàng hát trên `6/8`:** `castillo` và `sonatina` không đứng ở `6/8`; `_alcaniz_soft` (`mode == "thin"`) chỉ đánh hai nốt chấm dôi ở móc `0` và móc `3` với `ordinary`, `accent=False`.

Trên lưới điệu `6/8` có nhấn (`_render_danza_bar`, `_render_fandanguillo_bar`, và `_alcaniz_dance` khi `accented=True`):

| Móc đơn trong ô `6/8` | Vai trò | Vận tốc viết (`lead`) | `accent` | Ghi chú theo từng điệu và bè đệm |
|---|---|---|---|---|
| **Móc `0`** | Trọng âm chính | `max(ordinary, 68)` | `True` | Đủ điều kiện vào `_is_target` của lớp móng (`snap`) |
| **Móc `3`** | Trọng âm phụ | `max(ordinary - 2, 66)` (tức `max(ordinary, 68) - 2`) | `False` | Trên `_block` của Danza tại móc `3`, `_bed(velocity, band)` đi qua `_raised_bed` (`_BAND_BASS`: `p=54, mp=58, mf=60, f=64`, cộng `4` rồi kẹp `lead - 2`; `_BAND_SUPPORT`: `p=50, mp=54, mf=56, f=60`). Ở `p / mp / mf`, `lead = 68` và `lead = 66` cho cùng mức `(support, bass)` là `(50, 58)`, `(54, 62)`, `(56, 64)`; chỉ ở band `f`, `bass` tại móc `3` hạ từ `66` xuống `64` (`support` giữ `60`). Trong `_alcaniz_dance`, bass đáp ở móc `1` và `4` vốn tính từ `_bed(ordinary, band)` nên giữ nguyên |
| **Các móc `lead` yếu (nếu có)** | Móc lướt / móc đáp | `64` | `False` | • **Danza `6/8`**: `_danza_chords = (0, 3)`, `_danza_melody = (1, 2, 4, 5)` $\rightarrow$ đủ 6 móc `lead`: trên câu phẳng là `68, 64, 64, 66, 64, 64`; trên đỉnh câu (`ordinary = 72`) là `72, 64, 64, 70, 64, 64`.<br>• **Fandanguillo `6/8`**: chỉ có `lead` ở móc `0, 2, 3` (`_fandanguillo_melody("6/8") == (2, 3)`) $\rightarrow$ trên câu phẳng là `68, 64, 66`; trên đỉnh câu là `72, 64, 70`.<br>• **`_alcaniz_dance` (`accented=True`)**: chỉ có `lead` ở móc `0` và `3` $\rightarrow$ trên câu phẳng là `68, 66`; trên đỉnh câu là `72, 70` |

**Quan hệ với `apply_guitar_wave`:**

- Sau `_shape_dynamics` (cộng một `extra` cho cả ô) và `apply_guitar_wave` (cộng `round(C) - 64` rồi kẹp `min(v_ceil, raw)` với `v_ceil = 63`):
  - Khoảng cách `2` đơn vị giữa móc `0` và móc `3` được giữ nguyên trên các ô mà cả hai nốt chưa chạm trần ấm `63` và móc `0` không bị chọn làm móng (`snap` kéo nốt trúng đích sang `69–73`).
  - Ở đỉnh thủy triều (ví dụ viết `72 + 4 = 76` và `70 + 4 = 74`), phép kẹp `v_ceil = 63` đưa cả hai về `63` (trừ khi móc `0` được snap lên `69–73`).

### 1.3. Trọng âm trên `3/4` (`_render_sonatina_moving` và `_render_juglar_bar`)

Một ô `3/4` có phách 1 ở móc `0`, phách 2 ở móc `2`, phách 3 ở móc `4`. Một ô có thể chứa hai câu (`Phrase`), nên việc kiểm tra một móc `origin + offset` có phải đỉnh câu hay không **phải tra trên câu sở hữu chính móc đó** (`owner = _phrase_covering(ctx, origin + offset, phrase)`), không dùng `phrase` của phách 1:

```python
in_apex = (
    owner is not None
    and owner.runs
    and owner.apex.start <= origin + offset < owner.apex.end
)
```

1. **`_render_sonatina_moving` khi `ctx.kind == "3/4"`:**
   - Móc `0` (nốt đen phủ móc `0–1`): giữ `velocity = ordinary`, `accent = True`.
   - Móc `2`, móc `3` (hai móc đơn) và móc `4` (nốt đen phủ móc `4–5`): với mỗi móc `offset in (2, 3, 4)`, lấy `owner = _phrase_covering(ctx, origin + offset, phrase)` như hiện tại; nếu `origin + offset` **không** thỏa `in_apex` của `owner`, hạ vận tốc viết đi `2` đơn vị: `max(40, level - 2)`. Nếu thuộc `apex` của `owner`, giữ nguyên `level`.
2. **`_render_juglar_bar` (`torroba_tremolo`, `3/4`):**
   - Phách 1 (`eighth == 0`): cú 1 của bộ ba (hoặc nốt đen khi `quarter_notes`) giữ `velocity`, `accent = (mode == "full" and not quarter_notes)`.
   - Phách 2 và phách 3 (`eighth in (2, 4)`): lấy `owner = _phrase_covering(ctx, origin, phrase)` (với `origin = bar * ctx.epb + eighth`, cùng câu mà `_lead_vel` đang đọc). Nếu `origin` **không** thuộc `owner.apex`, hạ cú 1 của phách đó đi `2` đơn vị (`velocity = max(40, velocity - 2)`), `accent = False`.
   - Lưu ý về `_one_under(velocity, band)`: trên câu phẳng band `mf`, `_under_lead(64, "mf")` và `_under_lead(62, "mf")` đều trả `support = 56`. Do đó cú 2 và cú 3 của bộ ba giữ ở `56` trên cả ba phách; việc hạ cú 1 của phách 2 và phách 3 từ `64` xuống `62` làm nghiêng đúng **cú đầu của mỗi phách** (`64 → 62 → 62`). (`torroba_tremolo` không có `snap` trong `PROFILES`).

---

## 2. Bậc lực `♬ ♪` trong `_type4_call` và lý do không chạm `_into_strong`

1. **Không sửa `_render_sonatina_moving` quanh `_into_strong`:**
   - Trong `guitar_torroba.py`, `_sixteenth` đặt các nốt lấy đà lùi về phía trước phách mạnh đích (`arrival_eighth`): một nốt grace rơi vào `beat = 1.75` (nửa sau móc `3`), còn run 3 nốt (`run=True`) rơi vào `beat = 1.25, 1.50, 1.75` (chiếm cả nửa sau móc `2` lẫn toàn bộ móc `3`).
   - Do đó, khi `kind in {"leap", "run"}`, việc bỏ qua cặp móc đơn `base + 2, base + 3` hiện tại là bắt buộc để không chồng tiếng lên run 3 nốt ở `1.25..1.75`. Giữ nguyên cấu trúc nốt của `_render_sonatina_moving`.
2. **Đồng bộ `steps` của `_type4_call` với `_type3_motif`:**
   - Trong `_type3_motif` (dòng 2292–2299 của `guitar_torroba.py`), cụm hai móc kép (`beat = 0.5, 0.75`) + một móc đơn (`beat = 1.0`) đã viết `steps = 2, 2` (chung `group = bundle`) rồi `steps = 1`, không gắn `tenuto`.
   - Trong `_type4_call` (dòng 2368–2380 của `guitar_torroba.py`), cùng cụm tiết tấu `0.5, 0.75, 1.0` hiện đang viết `steps = 1, 1, 1`.
   - **Sửa `_type4_call`:** Đổi hai móc kép tại `0.5` và `0.75` sang `steps = 2` (cùng `group = pen.group()`), giữ móc đơn tại `1.0` ở `steps = 1`. Không thêm cờ `tenuto` vào `_type3_motif` hay `_type4_call`.

---

## 3. Ba độ lệch Zero-Sum độc lập trên `_tempo_clock` (`humanize.py`)

### 3.1. Toán học cộng ba tầng và quy tắc giữ nguyên cấu trúc `_tempo_clock`

- **Giữ nguyên cổng câu ngắn và mốc trả `nominal` tại `phrase.end`:**
  - Câu ngắn hơn `_MIN_PHRASE_BEATS = 2.0` phách đen (`end - start < _MIN_PHRASE_BEATS - 1e-9`) giữ nguyên `continue` (không phát đồng hồ).
  - Cuối mỗi câu đã phát đồng hồ, khi `end < piece_end - 1e-9`, **giữ nguyên việc ghi mốc `(round(end, 4), nominal, order)`** như `_tempo_clock` đang làm (dòng 338–340 `humanize.py`), để nếu câu kế tiếp ngắn hơn `2.0` phách (không phát đồng hồ mới), đuôi tempo của câu trước không bị kéo tràn sang câu ngắn đó.
- **Tách ba độ lệch zero-sum độc lập trên từng câu:**
  - Với mỗi câu hợp lệ $u \in [u_{\text{start}}, u_{\text{end}})$ (trong đó $u_{\text{start}} = \text{round}(\text{start} \times \text{divisions})$, $u_{\text{end}} = \text{round}(\text{end} \times \text{divisions})$), mỗi tầng $k \in \{\text{phrase}, \text{bar}, \text{lilt}\}$ sinh ra một mảng độ lệch $\Delta_k[u]$ sao cho tổng của chính tầng đó bằng `0.0`:

$$\sum_{u = u_{\text{start}}}^{u_{\text{end}} - 1} \Delta_k[u] = 0.0$$

  - Cộng tuyến tính $\Delta[u] = \Delta_{\text{phrase}}[u] + \Delta_{\text{bar}}[u] + \Delta_{\text{lilt}}[u]$. Nếu $\max_u |\Delta[u]| > \Delta_{\max}$ (với $\Delta_{\max} = 0.10$), co tuyến tính toàn câu bằng hệ số $s = \Delta_{\max} / \max_u |\Delta[u]|$ (ví dụ khi câu đóng `-0.05`, ô quạt `6/8` `-0.04`, và lilt `-0.04` trùng nhau thành `-0.13`, toàn câu được nhân $s = 0.10 / 0.13 \approx 0.7692$, giữ $\sim 77\%$ liều mà không cắt bẹt đầu âm):

$$f[u] = 1.0 + s \cdot \Delta[u]$$

  - Phép co tuyến tính bảo toàn $\sum_u (f[u] - 1.0) = 0.0$ trước khi làm tròn `bpm = round(nominal * f[u], 2)`.

### 3.2. Công thức chính xác của từng tầng cho `score.ensemble == "torroba"`

Các ensemble khác giữ nguyên `_TEMPO_DELTA` hiện tại (`0.01` cho `guitar`). Khi `score.variant == "guitar"` và `score.ensemble == "torroba"`:

#### Tầng 1: $\Delta_{\text{phrase}}[u]$ — Hơi thở câu nhạc
- Dùng chính `_tempo_regions(start, end, delta)` và `_tempo_factor` đối xứng hiện có của `humanize.py`:
  - Câu mở (`not phrase.closes`): `delta = 0.035` (`±3.5%`).
  - Câu đóng (`phrase.closes`): `delta = 0.050` (`±5.0%`).
- $\Delta_{\text{phrase}}[u] = \text{factor}_{\text{phrase}}(u) - 1.0$, có tổng trên câu bằng `0.0`.

#### Tầng 2: $\Delta_{\text{bar}}[u]$ — Độ đằm đầu ô nhịp (chỉ trên các ô nằm trọn trong một `Phrase`)
Xét từng ô nhịp `bar` mà toàn bộ phạm vi ô `[bar * bar_beats, (bar + 1) * bar_beats)` nằm trọn bên trong `[start, end)` của câu đang xét (ô bị biên câu cắt ngang thì $\Delta_{\text{bar}} = 0$):

1. **Nhận diện ô có hợp âm quạt `rasgueado` đầu ô:**
   - Ô `bar` là ô quạt khi trong `score.lead` hoặc `score.support` có nốt thuộc ô đó với `0.0 < note.beat < 0.25 - 1e-6` (onset `1/12` và `2/12`; nốt đầu ô ở `beat == 0.0` không lọt vào).
2. **Cửa sổ đầu ô $W_1$ và cửa sổ bù $W_2$ theo nhịp (ô quạt thay thế luật ô thường, không cộng chồng):**
   - **Trên `6/8` (`score.beats == 6` và `score.beat_type == 8`, `bar_beats == 3.0`):**
     - $W_1 = [0.0, 1.5)$ (trọn nhóm ba móc đơn đầu) và $W_2 = [1.5, 3.0)$ (trọn nhóm ba móc đơn thứ hai):
       - **Ô quạt `rasgueado`**: $\Delta_{\text{bar}} = -0.04$ trên $W_1$, và $+0.04$ trên $W_2$.
       - **Ô `6/8` thường**: $\Delta_{\text{bar}} = -0.02$ trên $W_1$, và $+0.02$ trên $W_2$.
   - **Trên `3/4` (`score.beats == 3` và `score.beat_type == 4`, `bar_beats == 3.0`):**
     - $W_1 = [0.0, 1.0)$ (phách 1, dài `1.0` beat) và $W_2 = [1.0, 3.0)$ (phách 2–3, dài `2.0` beat):
       - **Ô quạt `rasgueado`**: $\Delta_{\text{bar}} = -0.04$ trên $W_1$, và $+0.02$ trên $W_2$.
       - **Ô `3/4` thường**: $\Delta_{\text{bar}} = -0.02$ trên $W_1$, và $+0.01$ trên $W_2$.
   - **Trên `4/4` (`score.beats == 4` và `score.beat_type == 4`, `bar_beats == 4.0`):**
     - Chỉ áp dụng cho **ô quạt `rasgueado`** (ô `4/4` thường giữ $\Delta_{\text{bar}} = 0$):
       - $W_1 = [0.0, 1.0)$ nhận $\Delta_{\text{bar}} = -0.045$; $W_2 = [1.0, 4.0)$ nhận $\Delta_{\text{bar}} = +0.015$.

#### Tầng 3: $\Delta_{\text{lilt}}[u]$ — Độ níu cụm «móc đơn + hai móc kép / ba nốt `1/6`» (quét không chồng lấp)
Trong mỗi ô nhịp `bar`, chia ô thành các khe móc đơn $s = 0, 1, \dots, \text{epb} - 1$, mỗi khe ứng với $[s \cdot 0.5, (s + 1) \cdot 0.5)$:

1. **Phân loại từng khe móc đơn $s$ từ các cú đánh (`_is_attack`) của `score.lead` trong ô `bar`:**
   - Khe $s$ là **`E` (Eighth)** nếu có đúng 1 nốt `lead` bắt đầu tại `s * 0.5` với `duration_beats == 0.5` (sai số `< 1e-4`) và không có nốt `lead` nào khác trong khe đó.
   - Khe $s$ là **`S` (Subdivided)** nếu các nốt `lead` trong khe $[s \cdot 0.5, (s + 1) \cdot 0.5)$ là đúng **2 nốt móc kép** (`0.25` tại `s * 0.5` và `s * 0.5 + 0.25`) hoặc đúng **3 nốt chùm ba móc kép** (`1/6` tại `s * 0.5`, `s * 0.5 + 1/6`, `s * 0.5 + 2/6`). *(Chùm 4 móc kép của Kiểu 2 là cặp `S–S` nên bị bỏ qua; grace 1 nốt tại `1.75` hoặc run 3 móc kép `1.25..1.75` không tạo thành khe `S`).*
2. **Quét tham lam từ trái sang phải, nuốt cặp đã ghép (`s += 2`):**
   - Đặt $s = 0$:
     - Nếu cả hai khe $s$ và $s + 1$ nằm trọn trong câu `Phrase` đang xét và `(kind[s], kind[s + 1]) == ("E", "S")`: gán $\Delta_{\text{lilt}} = -0.04$ cho khe $s$, $+0.04$ cho khe $s + 1$, rồi tăng **$s \leftarrow s + 2$**.
     - Ngược lại, nếu cả hai khe $s$ và $s + 1$ nằm trọn trong câu và `(kind[s], kind[s + 1]) == ("S", "E")`: gán $\Delta_{\text{lilt}} = +0.04$ cho khe $s$, $-0.04$ cho khe $s + 1$, rồi tăng **$s \leftarrow s + 2$**.
     - Ngược lại: tăng $s \leftarrow s + 1$.

---

## 4. Chỗ sửa khi thực hiện và kiểm thử

1. **`backend/app/sonify/guitar_torroba.py`:**
   - **Trọng âm `6/8`:**
     - Trong `_block` (Danza, dòng 1102) và `_answer` (Fandanguillo / Danza, dòng 1137): khi `ctx.kind == "6/8"` và `offset == 3`, đặt `velocity = max(ordinary - 2, 66)` và `accent = False` (móc `0` giữ `max(ordinary, 68)` và `accent = True`).
     - Trong `_alcaniz_dance` (dòng 3790): khi `accented` đúng (`mode == "full"`): móc `0` viết `max(ordinary, 68)`, `accent = True`; móc `3` viết `max(ordinary - 2, 66)`, `accent = False`. Khi `not accented` (`mode == "pushed"`): giữ cả móc `0` và móc `3` ở `ordinary`, `accent = False`. Giữ nguyên `_alcaniz_opening`.
   - **Trọng âm `3/4`:** Trong `_render_sonatina_moving` (khi `ctx.kind == "3/4"`, tại `offset in (2, 3, 4)` với `origin = bar * ctx.epb`, tra `_phrase_covering(ctx, origin + offset, phrase)`) và trong `_render_juglar_bar` (tại `eighth in (2, 4)` với `origin = bar * ctx.epb + eighth` đã cộng sẵn `eighth`, tra `_phrase_covering(ctx, origin, phrase)`), kiểm tra `in_apex` trên câu sở hữu chính móc đó. Nếu không thuộc `owner.apex`, hạ vận tốc viết `max(40, velocity - 2)`.
   - **`_type4_call` (dòng 2368–2380):** Đổi hai móc kép tại `0.5, 0.75` sang `steps = 2` (chung `group = pen.group()`), giữ móc đơn tại `1.0` ở `steps = 1` (khớp `_type3_motif` ở dòng 2292–2299).
2. **`backend/app/sonify/humanize.py`:**
   - Trong `_tempo_clock` / `_phrase_tempos`: khi `score.variant == "guitar"` và `score.ensemble == "torroba"` (với `divisions >= 2` chẵn), tính $\Delta[u] = \Delta_{\text{phrase}}[u] + \Delta_{\text{bar}}[u] + \Delta_{\text{lilt}}[u]$ theo Mục 3.2, co tỷ lệ toàn câu bằng $s = 0.10 / \max_u |\Delta[u]|$ nếu $\max_u |\Delta[u]| > 0.10$, phát `round(nominal * (1.0 + s * delta_u), 2)`, và giữ nguyên mốc trả `(round(end, 4), nominal, order)` tại `phrase.end` cùng cổng `_MIN_PHRASE_BEATS = 2.0`.
3. **Tests (tách bạch mặt viết trước sóng và đồng hồ sau `humanize`):**
   - Trong `backend/tests/test_sonify_guitar_torroba.py`:
     - **Test vận tốc viết trên `6/8` (gọi thẳng `_render_torroba_bar` trên một `Phrase` phẳng):**
       - Danza `6/8`: sắp xếp `lead` theo `note.beat` (vì `_render_danza_bar` append hợp âm móc `0, 3` trước rồi mới append melody `1, 2, 4, 5`), xác nhận theo thứ tự móc ra `[68, 64, 64, 66, 64, 64]` và chỉ móc `0` có `accent=True`.
       - Fandanguillo `6/8` ra 3 nốt `lead` tại móc `0, 2, 3` với vận tốc `[68, 64, 66]`, chỉ móc `0` có `accent=True`.
       - `_alcaniz_dance` ở `mode == "full"` ra 2 nốt `lead` tại móc `0, 3` với vận tốc `[68, 66]`, chỉ móc `0` có `accent=True`; ở `mode == "pushed"` cả hai móc giữ `[64, 64]` và `accent=False`; `_alcaniz_opening` giữ móc `3` ở `68` (`accent=True`).
     - **Test vận tốc viết trên `3/4`:** Câu phẳng (`rise == 0`) của Sonatina (với cao độ giữa móc `0` và móc `4` cách nhau $\le 2$ bán cung để `_sonatina_approach` không rẽ nhánh `leap`/`run` bỏ qua móc `2, 3`) và của Juglar có phách 1 viết `64` và phách 2, 3 viết `62`; khi một câu thứ hai mở ở giữa ô và có `apex` tại móc `4` (`_phrase_covering`), móc `4` không bị hạ.
     - **Test `_type4_call` trên câu phẳng (`rise == 0`):** Vì hai móc kép đọc `lead_level(1)` và móc đơn đọc `lead_level(2)`, test trên câu phẳng để cả hai cùng mức nền `64`, xác nhận vận tốc sau `_realize` của hai móc kép (`0.5, 0.75`) thấp hơn móc đơn (`1.0`) đúng một bậc `_MICRO = 2` (`60` so với `62`).
   - Trong `backend/tests/test_humanize.py`:
     - **Test đồng hồ tính sẵn trên Torroba:** Kiểm tra dãy hệ số từng `division` trên câu `3/4` và `6/8` có cụm `♪ ♬` (và chuỗi `♪ ♬ ♪` liên tiếp để xác nhận nuốt cặp `s += 2`), xác nhận mốc `phrase.end` trả về `nominal` BPM khi tiếp theo là một câu ngắn `< 2.0` phách, xác nhận khi cả ba tầng cùng dấu tới `0.13` thì toàn câu được co về trần `0.10` (`~77%` liều), và trung bình cộng các BPM theo division sau `round(..., 2)` khớp `score.bpm` trong sai số làm tròn `pytest.approx(score.bpm, abs=0.01)`.
4. **`SPAN_REVISION` và `RECAP_REVISION`:** Chỉ tăng một lần khi đưa code vào `guitar_torroba.py` và `humanize.py`.
