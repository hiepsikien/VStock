# Torroba: trọng âm bậc thang 3/4 – 6/8 và độ du di nhịp Tây Ban Nha (*Aire español / Rubato*)

> **Trạng thái**: đề xuất thiết kế (đã hiệu chỉnh công thức theo review), chờ khóa.
> **Đọc cùng**: [`docs/sonify-guitar-torroba-meter-doors.md`](./sonify-guitar-torroba-meter-doors.md), [`docs/sonify-guitar-torroba-dynamics.md`](./sonify-guitar-torroba-dynamics.md), [`docs/sonify-guitar-torroba-phrase-plan.md`](./sonify-guitar-torroba-phrase-plan.md) mục 4, [`docs/sonify-humanize-timing-plan.md`](./sonify-humanize-timing-plan.md).
> **Giữ**: Lưới nhịp `3/4`, `6/8`, `4/4` đã khóa. Một tâm sóng `round(C)` và một `extra` cho cả ô (`_WHOLE_BAR_EXTRA`). Không dùng Jazz swing (`swing=True`). Không sửa `duration_beats` của `NoteEvent`.

Ba việc:

1. **Phân tầng trọng âm viết trên `6/8` và `3/4`:** Trên `6/8` của các điệu vũ (`danza`, `fandanguillo`, `_alcaniz_dance`), móc đơn `0` là trọng âm chính (`max(ordinary, 68)`, `accent=True`), móc đơn `3` là trọng âm phụ (`max(ordinary - 2, 66)`, `accent=False`). Trên `3/4` (`_render_sonatina_moving`, `_render_juglar_bar`), phách 1 (móc `0`) giữ `ordinary`, còn các phách sau hạ 1 bậc (`-2`) khi móc đó không nằm trong đỉnh câu (`phrase.apex`).
2. **Đồng bộ bậc lực `steps` trong `_type4_call`:** Đưa cụm hai móc kép + một móc đơn tại `beat = 0.5, 0.75, 1.0` của `_type4_call` từ `steps = 1, 1, 1` sang `steps = 2, 2, 1` giống `_type3_motif` (không gắn thêm `tenuto`, không đụng `_into_strong`).
3. **Mở rộng `_tempo_clock` cho `("guitar", "torroba")` bằng tổng ba độ lệch zero-sum độc lập:** Tầng câu ($\Delta_{\text{phrase}}$), tầng đầu ô ($\Delta_{\text{bar}}$), và tầng lilt ($\Delta_{\text{lilt}}$) tự triệt tiêu trung bình về `0.0` ngay trong phạm vi của chính nó, cộng tuyến tính vào `1.0`, và co tỷ lệ toàn câu nếu chạm trần `±0.10` thay vì kẹp cứng từng `unit`.

---

## 1. Trọng âm bậc thang trên `6/8` và `3/4`

### 1.1. Hiện trạng trong code

- `METER_68` đặt `strong_eighths = (0, 3)`. Trong `backend/app/sonify/guitar_torroba.py`, `_lead_velocity`, `_block`, `_answer`, `_alcaniz_dance` và `_alcaniz_opening` đang cho cả móc `0` và móc `3` sàn `68` và `accent=True`.
- Trong `guitar_wave.py`, `_is_target` của `fandanguillo`, `danza`, `alcaniz`, `olite` nhận mọi `lead` có `accent=True`.
- Trên `3/4`, `_render_sonatina_moving` viết nốt đen ở móc `0`, hai móc đơn ở móc `2, 3`, và một nốt đen ở móc `4` (phủ móc `4–5`, không có nốt riêng ở móc `5`). `_render_sonatina_bar` trên `6/8` không được bảng chọn pattern gọi.

### 1.2. Trọng âm trên `6/8` (chỉ áp cho lưới điệu: `danza`, `fandanguillo`, `_alcaniz_dance`)

Không áp cho `_alcaniz_opening`: ở `_alcaniz_opening`, móc `3` là đích của cặp slur đi vào (`slur_stop=True`), cần giữ nguyên `max(arrival, 68)` và `accent=True` để không làm yếu nốt câu đang đổ tới. Không áp cho hàng hát trên `6/8` (`castillo` và `sonatina` không đứng ở `6/8`; `_alcaniz_soft` chỉ đánh hai nốt chấm dôi ở móc `0` và móc `3`, không có móc lướt `1, 2, 4, 5`).

Trên lưới điệu `6/8` (`_render_danza_bar`, `_render_fandanguillo_bar`, `_alcaniz_dance`):

| Móc đơn trong ô `6/8` | Vai trò | Vận tốc viết (`lead`) | `accent` | Ghi chú bè đệm |
|---|---|---|---|---|
| **Móc `0`** | Trọng âm chính | `max(ordinary, 68)` | `True` (khi `mode == "full"` trên Alcaniz, và luôn `True` trên Danza / Fandanguillo) | Đủ điều kiện vào `_is_target` của lớp móng (`snap`) |
| **Móc `3`** | Trọng âm phụ | `max(ordinary - 2, 66)` (tức `max(ordinary, 68) - 2`) | `False` | Trong `_block` của Danza tại móc `3`, `_bed(velocity, band)` nhận `66` (trên câu phẳng) nên `support` và `bass` dịu theo `lead`. Trong `_alcaniz_dance`, bass đáp ở móc `1` và `4` vốn tính từ `_bed(ordinary, band)` nên giữ nguyên |
| **Móc `1, 2, 4, 5`** | Móc yếu | `64` | `False` | Giữ nguyên |

**Quan hệ với đỉnh câu và `apply_guitar_wave`:**

- Trên một câu phẳng (`ordinary = 64`), đường lực viết qua 6 móc của ô `6/8` là `68, 64, 64, 66, 64, 64`. Trên đỉnh câu (`ordinary = 72`), móc yếu vẫn ở `64` nên đường lực viết là `72, 64, 64, 70, 64, 64`.
- Sau `_shape_dynamics` (cộng một `extra` cho cả ô) và `apply_guitar_wave` (cộng `round(C) - 64` rồi kẹp `min(v_ceil, raw)` với `v_ceil = 63`):
  - Khoảng cách `2` đơn vị giữa móc `0` và móc `3` được giữ nguyên trên các ô mà cả hai nốt chưa chạm trần ấm `63` và móc `0` không bị chọn làm móng (`snap` kéo nốt trúng đích sang `69–73`).
  - Ở đỉnh thủy triều (ví dụ viết `72 + 4 = 76` và `70 + 4 = 74`), phép kẹp `v_ceil = 63` sẽ đưa cả hai về `63` (trừ khi móc `0` được snap lên `69–73`).

### 1.3. Trọng âm trên `3/4` (`_render_sonatina_moving` và `_render_juglar_bar`)

Một ô `3/4` có phách 1 ở móc `0`, phách 2 ở móc `2`, phách 3 ở móc `4`:

1. **`_render_sonatina_moving` khi `ctx.kind == "3/4"`:**
   - Móc `0` (nốt đen phủ móc `0–1`): giữ `velocity = ordinary`, `accent = True`.
   - Móc `2`, móc `3` (hai móc đơn) và móc `4` (nốt đen phủ móc `4–5`): với mỗi móc `eighth`, nếu `eighth` **không** nằm trong đỉnh câu (`not (local is not None and local.runs and local.apex.start <= eighth < local.apex.end)`), hạ vận tốc viết đi `2` đơn vị: `max(40, level - 2)`. Nếu `eighth` nằm trong `apex`, giữ nguyên `level` để đỉnh câu ở phách 2 hoặc phách 3 vẫn nhô lên đúng tự nhiên.
2. **`_render_juglar_bar` (`torroba_tremolo`, `3/4`):**
   - Phách 1 (`eighth == 0`): cú 1 của bộ ba (hoặc nốt đen khi `quarter_notes`) giữ `velocity`, `accent = (mode == "full" and not quarter_notes)`.
   - Phách 2 và phách 3 (`eighth in (2, 4)`): khi `eighth` không nằm trong `phrase.apex`, hạ cú 1 của phách đó đi `2` đơn vị (`velocity = max(40, velocity - 2)`), `accent = False`.
   - Lưu ý về `_one_under(velocity, band)`: trên câu phẳng band `mf`, `_under_lead(64, "mf")` và `_under_lead(62, "mf")` đều trả `support = 56`. Do đó cú 2 và cú 3 của bộ ba giữ ở `56` trên cả ba phách; việc hạ cú 1 của phách 2 và phách 3 từ `64` xuống `62` làm nghiêng đúng **cú đầu của mỗi phách** (`64 → 62 → 62`), tạo trọng tâm phách 1 cho ô tremolo mà không làm mỏng hai cú lặp sau. (`torroba_tremolo` không có `snap` trong `PROFILES`, nên `accent` chỉ phục vụ MusicXML).

---

## 2. Bậc lực `♬ ♪` trong `_type4_call` và lý do không chạm `_into_strong`

1. **Không sửa `_render_sonatina_moving` quanh `_into_strong`:**
   - Trong `guitar_torroba.py`, `_sixteenth` đặt các nốt lấy đà lùi về phía trước phách mạnh đích (`arrival_eighth`): một nốt grace rơi vào `beat = 1.75` (nửa sau móc `3`), còn run 3 nốt (`run=True`) rơi vào `beat = 1.25, 1.50, 1.75` (chiếm cả nửa sau móc `2` lẫn toàn bộ móc `3`).
   - Do đó, khi `kind in {"leap", "run"}`, việc bỏ qua cặp móc đơn `base + 2, base + 3` hiện tại là bắt buộc để không chồng tiếng lên run 3 nốt ở `1.25..1.75`. Giữ nguyên cấu trúc nốt của `_render_sonatina_moving`.
2. **Đồng bộ `steps` của `_type4_call` với `_type3_motif`:**
   - Trong `_type3_motif` (dòng 2167), cụm hai móc kép (`beat = 0.5, 0.75`) + một móc đơn (`beat = 1.0`) đã viết `steps = 2, 2` (chung `group = bundle`) rồi `steps = 1`, không gắn `tenuto`.
   - Trong `_type4_call` (dòng 2259), cùng cụm tiết tấu `0.5, 0.75, 1.0` hiện đang viết `steps = 1, 1, 1`.
   - **Sửa `_type4_call`:** Đổi hai móc kép tại `0.5` và `0.75` sang `steps = 2` (cùng `group = pen.group()`), giữ móc đơn tại `1.0` ở `steps = 1`. Không thêm cờ `tenuto` vào `_type3_motif` hay `_type4_call`.

---

## 3. Ba độ lệch Zero-Sum độc lập trên `_tempo_clock` (`humanize.py`)

### 3.1. Vì sao phải tách thành các độ lệch cộng tính có trung bình bằng `0.0`?

Trong `humanize.py`, đồng hồ câu hiện tính `factor` trên từng `unit` thuộc `range(start_units, end_units)` (với `divisions` là số đơn vị trong một phách đen). Nếu vừa nhân hệ số giữa các tầng, vừa dịch trung bình cả câu về `1.0` ở cuối, hoặc vừa kẹp `[0.90, 1.10]` từng `unit` rồi mới trừ trung bình:
- Bước trừ trung bình toàn câu sẽ xóa mất phần *animando* của nửa câu khi lilt chỉ nằm ở một nửa câu.
- Khi cuối câu đóng, đầu ô và lilt cùng âm và chạm sàn `0.90`, phép kẹp cắt mất phần âm mà không cắt phần dương, làm trung bình BPM của cả câu lệch khỏi `score.bpm`.

**Cách thiết kế đúng toán học:**
Mỗi tầng $k \in \{\text{phrase}, \text{bar}, \text{lilt}\}$ sinh ra một mảng độ lệch riêng $\Delta_k[u]$ trên các `unit` $u \in [u_{\text{start}}, u_{\text{end}})$ sao cho **tổng của chính tầng đó bằng `0.0`**:

$$\sum_{u = u_{\text{start}}}^{u_{\text{end}} - 1} \Delta_k[u] = 0.0$$

Khi đó, tổng độ lệch $\Delta[u] = \Delta_{\text{phrase}}[u] + \Delta_{\text{bar}}[u] + \Delta_{\text{lilt}}[u]$ tự động có trung bình bằng `0.0` mà không tầng nào xóa tầng nào. Nếu $\max_u |\Delta[u]| > \Delta_{\max}$ (với $\Delta_{\max} = 0.10$), ta **nhân toàn bộ mảng $\Delta[u]$ của câu đó với hệ số co $s = \Delta_{\max} / \max_u |\Delta[u]|$**:

$$f[u] = 1.0 + s \cdot \Delta[u]$$

Phép co tuyến tính giữ nguyên $\sum_u (f[u] - 1.0) = 0.0$ tuyệt đối trong mọi trường hợp.

*(Lưu ý về thời gian thực tế WAV và `mapDurationSec`)*: Trung bình cộng của BPM bằng `nominal` kéo theo thời gian phát thực tế $\propto \sum (1 / f[u])$ dài hơn thời lượng danh định khoảng $O(\Delta^2)$ (vài phần nghìn giây, nằm gọn trong đuôi ngân ~3 giây của MuseScore). `piece_seconds` và `mapDurationSec` tính từ `score.bpm` danh định nên không đổi.

### 3.2. Công thức chính xác của từng tầng cho `score.ensemble == "torroba"`

Các ensemble khác giữ nguyên `_TEMPO_DELTA` hiện tại (`0.01` cho `guitar`). Khi `score.variant == "guitar"` và `score.ensemble == "torroba"`:

#### Tầng 1: $\Delta_{\text{phrase}}[u]$ — Hơi thở câu nhạc
- Giữ đúng hàm `_tempo_regions(start, end, delta)` và `_tempo_factor` đối xứng hiện có của `humanize.py` (chia đôi đối xứng quanh `mid = (start + end) / 2.0`, trượt qua `_RAMP_BEATS = 3.0` phách ở giữa, nên trung bình trên lưới `divisions` đã bằng `1.0`), chỉ nâng `delta`:
  - Câu mở (`not phrase.closes`): `delta = 0.035` (`±3.5%`).
  - Câu đóng (`phrase.closes`): `delta = 0.050` (`±5.0%`, nửa đầu `+5.0%`, nửa cuối lơi `-5.0%`).
- Độ lệch tầng 1 là $\Delta_{\text{phrase}}[u] = \text{factor}_{\text{phrase}}(u) - 1.0$. Vì `_tempo_regions` đối xứng hoàn toàn quanh `mid`, $\sum_u \Delta_{\text{phrase}}[u] = 0.0$.

#### Tầng 2: $\Delta_{\text{bar}}[u]$ — Độ đằm đầu ô nhịp (chỉ trên các ô nằm trọn trong một `Phrase`)
Xét từng ô nhịp `bar` mà toàn bộ phạm vi ô `[bar * bar_beats, (bar + 1) * bar_beats)` nằm trọn bên trong `[start, end)` của câu đang xét (ô bị biên câu cắt ngang thì $\Delta_{\text{bar}} = 0$ để không làm lệch tổng câu):

1. **Nhận diện ô có hợp âm quạt `rasgueado` đầu ô:**
   - Một ô `bar` là ô quạt khi trong `score.lead` hoặc `score.support` có nốt thuộc ô đó với onset nằm strictly giữa `0` và `0.25` phách: `0.0 < note.beat < 0.25 - 1e-6` (đúng chữ ký `1/12` và `2/12` của `_open_rasgueado` / `_stamp_rasgueado`; nốt đầu ô thường có `beat == 0.0` nên không bao giờ khớp nhầm).
2. **Cửa sổ đầu ô $W_1$ và cửa sổ bù $W_2$ theo nhịp (không cắt đôi nhóm ba của `6/8`):**
   - **Khi `score.beats == 6` và `score.beat_type == 8` (`6/8`, `bar_beats == 3.0`):**
     - Nhóm ba móc đơn đầu tiên là một phách chấm dôi `[0.0, 1.5)`. Nhóm ba móc đơn thứ hai là `[1.5, 3.0)`.
     - Đặt $W_1 = [0.0, 1.5)$ và $W_2 = [1.5, 3.0)$. Hai nửa bằng nhau (`1.5` beat mỗi nửa), nên:
       - Nếu là **ô quạt `rasgueado`**: $\Delta_{\text{bar}} = -0.04$ trên $W_1$, và $+0.04$ trên $W_2$.
       - Nếu là **ô `6/8` thường**: $\Delta_{\text{bar}} = -0.02$ trên $W_1$, và $+0.02$ trên $W_2$.
   - **Khi `score.beats == 3` và `score.beat_type == 4` (`3/4`, `bar_beats == 3.0`):**
     - Phách 1 là $W_1 = [0.0, 1.0)$ (dài `1.0` beat). Phách 2 và 3 là $W_2 = [1.0, 3.0)$ (dài `2.0` beat, gấp đôi $W_1$).
     - Để tổng trên `3.0` beat bằng `0.0`, độ lệch trên $W_2$ bằng $-\frac{1}{2}$ độ lệch trên $W_1$:
       - Nếu là **ô quạt `rasgueado`**: $\Delta_{\text{bar}} = -0.04$ trên $W_1 = [0.0, 1.0)$, và $+0.02$ trên $W_2 = [1.0, 3.0)$.
       - Nếu là **ô `3/4` thường**: $\Delta_{\text{bar}} = -0.02$ trên $W_1 = [0.0, 1.0)$, và $+0.01$ trên $W_2 = [1.0, 3.0)$.
   - **Khi `score.beats == 4` và `score.beat_type == 4` (`4/4`, `bar_beats == 4.0`):**
     - Chỉ áp dụng khi là **ô quạt `rasgueado`** (ô `4/4` thường giữ $\Delta_{\text{bar}} = 0$):
       - Phách 1 là $W_1 = [0.0, 1.0)$ (dài `1.0` beat) nhận $\Delta_{\text{bar}} = -0.045$.
       - Ba phách còn lại $W_2 = [1.0, 4.0)$ (dài `3.0` beat) nhận $\Delta_{\text{bar}} = +0.015$. Tổng: $-0.045 \times 1 + 0.015 \times 3 = 0.0$.
   - *(Ghi chú)*: Ô quạt dùng trực tiếp hệ số của nhánh quạt ở trên, **thay cho** hệ số ô thường, không cộng chồng cả hai.

#### Tầng 3: $\Delta_{\text{lilt}}[u]$ — Độ níu cụm «móc đơn + hai móc kép / ba nốt `1/6`» (quét không chồng lấp)
Trong mỗi ô nhịp `bar`, chia ô thành các khe nửa phách (móc đơn) $s = 0, 1, \dots, \text{epb} - 1$, mỗi khe ứng với đoạn $[s \cdot 0.5, (s + 1) \cdot 0.5)$.

1. **Phân loại từng khe móc đơn $s$ từ các cú đánh của `score.lead` trong ô `bar`:**
   - Khe $s$ là **`E` (Eighth)** nếu có đúng 1 nốt `lead` bắt đầu tại `s * 0.5` với `duration_beats == 0.5` (sai số `< 1e-4`) và không có nốt `lead` nào khác nằm trong khe đó.
   - Khe $s$ là **`S` (Subdivided — hai móc kép hoặc chùm ba `1/6`)** nếu các nốt `lead` nằm trong khe $[s \cdot 0.5, (s + 1) \cdot 0.5)$ phủ kín cả khe đó và rơi vào đúng một trong hai mẫu:
     - Đúng **2 nốt móc kép** (`duration_beats == 0.25`) tại `s * 0.5` và `s * 0.5 + 0.25`; hoặc
     - Đúng **3 nốt chùm ba móc kép** (`duration_beats == 1/6`) tại `s * 0.5`, `s * 0.5 + 1/6`, `s * 0.5 + 2/6`.
     - *(Một nốt grace đơn lẻ ở `beat = 1.75` hoặc một run 3 móc kép trải qua hai khe không tạo thành khe `S`, nên không bị bắt nhầm).*
2. **Quét tham lam từ trái sang phải, nuốt cặp đã ghép (non-overlapping scan):**
   - Đặt con trỏ $s = 0$:
     - Nếu cả hai khe $s$ và $s + 1$ cùng nằm trọn trong câu `Phrase` đang xét, và `(kind[s], kind[s + 1]) == ("E", "S")` (hình `♪ ♬`):
       - Mọi `unit` thuộc khe $s$ nhận $\Delta_{\text{lilt}} = -0.04$; mọi `unit` thuộc khe $s + 1$ nhận $\Delta_{\text{lilt}} = +0.04$.
       - Tăng con trỏ **$s \leftarrow s + 2$** (nuốt trọn cả hai khe, nên chuỗi `E – S – E` chỉ ghép cặp đầu `(0, 1)` và không bao giờ cộng hai lần lên khe `1`).
     - Ngược lại, nếu cả hai khe $s$ và $s + 1$ cùng nằm trọn trong câu, và `(kind[s], kind[s + 1]) == ("S", "E")` (hình `♬ ♪` như `_type3_motif` / `_type4_call` tại `s = 1, 2`, tức `beat = 0.5..1.5`):
       - Mọi `unit` thuộc khe $s$ nhận $\Delta_{\text{lilt}} = +0.04$; mọi `unit` thuộc khe $s + 1$ nhận $\Delta_{\text{lilt}} = -0.04$.
       - Tăng con trỏ **$s \leftarrow s + 2$**.
     - Ngược lại: tăng $s \leftarrow s + 1$.
   - Vì mỗi cặp `(s, s + 1)` được chấp nhận đều có đúng hai khe dài bằng nhau (`0.5` phách = `divisions // 2` đơn vị) mang dấu đối nhau `(-0.04, +0.04)` và nằm trọn trong câu, tổng $\sum_u \Delta_{\text{lilt}}[u] = 0.0$ tuyệt đối.

---

## 4. Chỗ sửa khi thực hiện và kiểm thử

1. **`backend/app/sonify/guitar_torroba.py`:**
   - **Trọng âm `6/8`:** Trong `_block` (Danza), `_answer` (Fandanguillo), và `_alcaniz_dance`: khi `ctx.kind == "6/8"` và `offset == 3`, đặt `velocity = max(ordinary - 2, 66)` và `accent = False` (móc `0` giữ `max(ordinary, 68)` và `accent = True`). Giữ nguyên `_alcaniz_opening`.
   - **Trọng âm `3/4`:** Trong `_render_sonatina_moving` (khi `ctx.kind == "3/4"`, trên móc `2, 3, 4`) và `_render_juglar_bar` (trên `eighth in (2, 4)`), khi móc đó không thuộc `phrase.apex`, hạ vận tốc viết `max(40, velocity - 2)`.
   - **`_type4_call`:** Đổi hai móc kép tại `0.5, 0.75` sang `steps = 2` (chung `group = pen.group()`), giữ móc đơn tại `1.0` ở `steps = 1`.
2. **`backend/app/sonify/humanize.py`:**
   - Trong `_tempo_clock` / `_phrase_tempos`: khi `score.variant == "guitar"` và `score.ensemble == "torroba"`, tính $\Delta[u] = \Delta_{\text{phrase}}[u] + \Delta_{\text{bar}}[u] + \Delta_{\text{lilt}}[u]$ theo đúng Mục 3.2 (yêu cầu `divisions >= 2` chẵn để mỗi khe `0.5` phách chứa số nguyên `unit`), co tỷ lệ toàn câu nếu $\max_u |\Delta[u]| > 0.10$, rồi phát `round(nominal * (1.0 + delta_u), 2)`.
3. **Tests (tách bạch mặt viết trước sóng và đồng hồ sau `humanize`):**
   - Trong `backend/tests/test_sonify_guitar_torroba.py`:
     - **Test vận tốc viết (gọi thẳng `_render_torroba_bar` trước `apply_guitar_wave` trên một `Phrase` phẳng):** Trên `6/8`, Danza / Fandanguillo / `_alcaniz_dance` có `lead` tại móc `0` là `68` (`accent=True`) và tại móc `3` là `66` (`accent=False`); `_alcaniz_opening` giữ móc `3` ở `68` (`accent=True`). Trên `3/4`, câu phẳng của Sonatina và Juglar có phách 1 viết `64` và phách 2, 3 viết `62`; khi `apex` đặt ở móc `4` thì móc `4` không bị hạ.
     - **Test `_type4_call`:** Hai móc kép `0.5, 0.75` thấp hơn móc đơn `1.0` đúng một bậc `_MICRO = 2`.
   - Trong `backend/tests/test_humanize.py`:
     - **Test đồng hồ tính sẵn trên một câu Torroba:** Kiểm tra trực tiếp dãy hệ số từng `division` trên câu `3/4` và `6/8` có cụm `♪ ♬` (và chuỗi `♪ ♬ ♪` liên tiếp để xác nhận không cộng đè hai lần), xác nhận trung bình cộng các BPM theo division bằng đúng `score.bpm`, và khi cả ba tầng cùng âm vượt `10%` thì toàn câu được co tỷ lệ giữ nguyên trung bình `score.bpm`.
4. **`SPAN_REVISION` và `RECAP_REVISION`:** Chỉ tăng một lần khi đưa code vào `guitar_torroba.py` và `humanize.py`.
