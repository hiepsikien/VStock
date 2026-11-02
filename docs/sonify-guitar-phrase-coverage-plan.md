# Kế hoạch: lớp phrase phủ câu + micro cho texture mỏng

> **Trạng thái**: đã đo xong baseline, chưa sửa code.
> **Phạm vi**: toàn bộ guitar ensemble (`bach`, `classic`, `barrios`, `villa`, `brouwer`, `torroba`), thân bài. Không đụng intro/outro, `select_scale_plan`, profile sóng, hay cổng snap trừ khi ghi rõ.
> **Mục tiêu**: mỗi pattern đạt **≥ 80% câu có arch ≥ 2**, và mỗi texture mỏng (`alcaniz_soft`, `olite_thin`, `JUGLAR_THIN`) có **≥ 80% ô có micro range ≥ 2** — đồng thời giữ đúng chất của từng pattern.

---

## 0. Cách đo (chuẩn của đợt này)

### 0.1. Arch của câu

Với một câu body có `rise > 0`:

- `q = max(1, (phrase.end - phrase.start) // 4)` (một phần tư câu).
- `apex` = trung bình velocity của các **singing attack** rơi trong `[phrase.apex.start, phrase.apex.end)`.
- `edge`:
  - nếu `phrase.apex.end >= phrase.end - q` (apex chạm cuối câu): lấy phần tư **đầu**, trừ các nốt đã nằm trong apex;
  - nếu `phrase.apex.start <= phrase.start + q` (apex chạm đầu câu): lấy phần tư **cuối**, trừ apex;
  - còn lại: lấy **min** của hai phần tư đầu/cuối, trừ apex.
- `arch = apex - edge`. Câu đạt khi `arch >= 2`.

Sửa so với bản đo cũ: bản cũ lấy `max(open, close)` làm mốc, nên câu có apex ở đầu/cuối bị chấm oan. Bảng dưới là số **đã sửa**:

| Pattern | n | median arch | arch ≥ 2 |
|---|---:|---:|---:|
| andante | 41 | 9.0 | 100% |
| bach_bourree | 7 | 8.0 | 100% |
| olite | 51 | 9.0 | 96% |
| cantabile | 43 | 10.5 | 93% |
| chord_melody | 68 | 9.0 | 91% |
| castillo | 142 | 8.5 | 90% |
| noviembre | 43 | 9.0 | 86% |
| alcaniz | 18 | 9.8 | 83% |
| fandanguillo | 34 | 7.1 | 82% |
| bach_allemande | 36 | 8.0 | 81% |
| **preludio** | 17 | 9.0 | **76%** |
| **torroba_tremolo** | 25 | 5.3 | **76%** |
| **danza** | 62 | 3.8 | **69%** |
| **bach_prelude** | 12 | 5.9 | **67%** |

> Ghi chú mẫu: con số **59%** ở §1.3 là 68 câu `danza`/`fandanguillo` của VIC 1M + MSN 1M (trước điểm 1); **69%** ở bảng trên là toàn bộ span. Hai mẫu khác nhau, không so trực tiếp. Sau khi sửa metric 0.4, dùng đúng một script và một tập span cho mọi con số.

Tức là trong danh sách 7 pattern bạn nêu, **3 pattern đã ≥ 80%** sau khi sửa metric: `bach_allemande` (81%), `fandanguillo` (82%), `alcaniz` (83%). Chỉ còn **4 pattern** thật sự dưới 80%: `preludio` (76%), `torroba_tremolo` (76%), `danza` (69%), `bach_prelude` (67%).

### 0.2. "Singing attack"

Không phải mọi nốt lead đều là bè hát. Với từng pattern, arch chỉ nên đo trên nốt hát:

| Pattern | Singing attack |
|---|---|
| phần lớn pattern | nốt lead dài nhất/đầu phách, không phải nốt láy/pickup |
| `torroba_tremolo` | cú đầu mỗi phách (ngón đầu chùm Juglar; ngón cái đi sau +2) |
| `bach_prelude` | nốt **price** của mỗi cặp 16th, không phải nốt neighbor (−2) |
| `bach_allemande`, `cantabile`, `chord_melody`, `andante`, `preludio` | nốt `_sustain` (nốt giai điệu đang ngân) |
| `danza`, `fandanguillo` | nốt melody ở phách mạnh; hợp âm chỉ là accompaniment |

Việc đo trên toàn bộ lead (cách cũ) làm loãng arch của các pattern có micro trong cùng bè (Juglar 3 ngón, prelude 2 nốt/1 eighth). Trước khi sửa nhạc, phải đo lại bằng "singing attack" để không chữa bệnh không có.

### 0.3. Micro

`residual = velocity thực − _note_velocity − extra _shape_dynamics`. Sóng cộng một hằng số cho cả ô nên bị triệt tiêu. Micro range của ô = `max(residual) − min(residual)`.

Baseline (lead, đã đo):

| Pattern / texture | % ô phẳng (range ≤ 1) | median range |
|---|---:|---:|
| `alcaniz_soft` | 74% | 0.0 |
| `olite_thin` | 71% | 0.0 |
| `JUGLAR_THIN` | 60% | 1.0 |
| `alcaniz` full | 18% | 6.0 |
| `olite` full | 18% | 10.0 |
| `castillo_walk` | 2% | 7.0 |
| `danza` / `fandanguillo` | 2–4% | 6–8 |
| `torroba_tremolo` | 4% | 10.0 |

### 0.4. Câu đã chia, nhưng renderer đọc câu theo đầu ô

Đây là lỗi gốc của `bach_prelude` (và `preludio` Barrios, cùng mọi pattern đi qua `_sustain`). Không phải "chưa chia câu".

Bằng chứng trên `VNM 1W` m0:

- `plan_phrases` cắt câu **147–173**, mở **giữa ô** (e147 = eighth offset 3, beat 1.5 của ô 18), apex **147–149**.
- `render_patterned_voices` tính `phrase_here = phrases[owner]` với `owner = _owner(ctx, bar)`, tức câu chứa **đầu ô 18** (câu 128–147), rồi truyền nguyên `phrase_here` cho `_render_bach_prelude_bar`.
- Renderer gọi `_note_velocity(eighth, 1, apex, phrase)` cho **mọi eighth trong ô** bằng câu cũ. Vì vậy e147–151 (đúng phần chứa apex) ra `63` (mức cuối câu cũ) thay vì `72` (apex câu mới). Sang ô sau (e152) mới đọc câu 147 → vọt lên `70`.
- Kết quả: **arch bị đảo** — đỉnh câu mới nhỏ hơn phần sau. Đo được `apex 51` vs `open/close 57`.

Cùng lỗi ở:

| File / hàm | Cách đang đọc câu |
|---|---|
| `guitar_patterns._sustain()` | nhận `phrase` của đầu ô, dùng cho mọi run trong ô |
| `guitar_bach._render_bach_prelude_bar()` | `_note_velocity(..., phrase)` cho mọi eighth |
| `guitar_barrios._render_catedral_preludio_bar()` → `_catedral_cell()` | `raw_a`/`raw_b` dùng cùng `phrase` của ô |
| `guitar_bach._render_bach_allemande_bar()` | `_sustain(..., phrase=phrase)` |
| hầu hết `_render_*_bar(..., phrase_here)` | chỉ đúng khi câu mở đúng đầu ô |

Torroba đã làm đúng: `_lead_vel()` dùng `_phrase_covering(ctx, eighth, phrase)`, nên câu mở giữa ô vẫn đọc đúng.

**Sửa**: thêm helper `_covering_phrase(ctx, eighth, fallback)` (hoặc dùng `_phrase_at(ctx, eighth)`) và đọc câu **theo từng eighth** tại mọi chỗ gọi `_note_velocity`/`_sustain`. Đây là bước 0 của đợt này, làm trước mọi thay đổi cảm giác.

---

## 1. Điểm 1 — `danza` / `fandanguillo`: phách yếu đi theo câu

### 1.1. Hiện trạng

`_block()` và `_answer()` trong `guitar_torroba.py` ghim phách yếu ở `64` (và 6/8 phách mạnh phụ ở `66`), trong khi phách mạnh là `max(ordinary, 68)`. Vì vậy contour câu chỉ còn trên phách mạnh + extra 0–4 của `_shape_dynamics`; phách yếu mất contour. Đây là lý do `danza` chỉ đạt 69%.

### 1.2. Luật

- Phách mạnh: giữ `max(ordinary, 68)`.
- Phách yếu: `min(ordinary, 67)` — đi theo câu nhưng luôn dưới sàn 68.
- 6/8 phách mạnh phụ (offset 3): giữ `max(ordinary - 2, 66)` như hiện tại.
- `_lead_velocity(..., dance=True)` là dead code hiện tại (mọi call là `dance=False`), nhưng sửa cùng luật để khỏi tái sinh lỗi.
- Giữ `accent`: mạnh `True`, yếu `False`.

### 1.3. Vì sao `min(ordinary, 67)`

Mô phỏng trên `VIC 1M` + `MSN 1M` (68 câu dance/fandanguillo):

| Cách | median arch | arch ≥ 2 |
|---|---:|---:|
| hiện tại (64) | 2.6 | 59% |
| `min(ordinary, 67)` | **4.8** | **75%** |
| `min(ordinary, 66)` | 4.0 | 69% |
| `min(ordinary, 64)` | 2.8 | 60% |

`67` là mức tốt nhất; cần đo lại bằng metric 0.1 (có thể vượt 80%). Nếu vẫn dưới 80%, xem mục 5 (post-wave arch).

### 1.4. Test

- Câu lên: phách mạnh ≥ 68, phách yếu = `ordinary` (≤ 67), lead > bass.
- Câu xuống: phách yếu giảm theo `ordinary`; phách mạnh giữ sàn 68.
- 6/8: phách mạnh phụ vẫn `max(ordinary-2, 66)`.
- `danza` và `fandanguillo` đều áp; `castillo`/`sonatina` không đổi.

---

## 2. Điểm 2 — câu `rise 1–2` dùng swell mượt

### 2.1. Hiện trạng

`_note_velocity()` trong `guitar_patterns.py` chỉ dùng `_melody_swell()` khi `_rises(phrase)` (tức `phrase.rise >= MIN_RISE = 3`). Câu `rise 1–2` rơi vào `_span_velocity()`: `72` ở apex, `64` ở mọi chỗ khác — một bậc nhảy, không phải arch.

### 2.2. Luật

Trong `_note_velocity()`:

```python
if phrase is None or length <= 0:
    return _span_velocity(start, length, apex)
if phrase.rise == 0:
    return _flat_swell(phrase, start)      # điểm 3
if any(phrase.apex.start <= e < phrase.apex.end for e in range(start, start + length)):
    base = _MELODY_APEX
else:
    base = _melody_swell(phrase, start)
if phrase.rise >= MIN_RISE:
    return base
# Một câu lên 1–2 semitone không nhận nguyên arch 12 bậc; biên độ co theo rise.
return int(round(64 + (base - 64) * (phrase.rise / MIN_RISE)))
```

Không đổi `_rises()`: nó còn được `guitar_bach.py`, `guitar_sor.py`, `guitar_villa.py` dùng cho các quyết định khác (breakout, scale run, drawn). Chỉ `_note_velocity()` đổi cửa.

### 2.3. Test

- Câu `rise = 1`: arch khoảng `63 → 67 → 63`; `rise = 2`: `61 → 69 → 61`; không còn bậc `72/64`.
- Câu `rise >= 3`: giữ nguyên `60 → 68 → 72 → 62` (nhánh scale = 1).
- Câu `rise = 0`: đi qua `_flat_swell` (mục 3).

---

## 3. Điểm 3 — câu phẳng có arch theo vị trí

### 3.1. Hiện trạng

`_note_velocity()` trả `_span_velocity()` cho câu phẳng, và `_apex_eighths()` cố ý bỏ câu `rise = 0`. Vì vậy câu phẳng hoàn toàn không có contour; chỉ còn tide theo ô.

### 3.2. Luật

Thêm helper trong `guitar_patterns.py`:

```python
def _flat_swell(phrase: Phrase, eighth: int) -> int:
    """Câu phẳng vẫn thở: mở 60, giữa 64, nhả 62."""
```

Công thức:

```text
progress = (clamp(eighth, start, end - 1) - start) / max(1, end - start)
if progress <= 0.5:
    value = 60 + (64 - 60) * (progress / 0.5)
else:
    value = 64 + (62 - 64) * ((progress - 0.5) / 0.5)
```

- Đỉnh **64**, không phải 68: `_clamp_guitar` đẩy 65+ vào lớp móng (69…73) và như vậy câu phẳng sẽ nhảy band giữa câu. 64 vẫn là band ấm; nếu `v_ceil` của ô thấp hơn thì arch vẫn sống dưới trần.
- `_note_velocity()` dùng `_flat_swell()` khi `phrase.rise == 0` và câu có ≥ 2 móc.
- Câu phẳng chỉ có **một** attack (nốt ngân cả câu) thì không tạo re-attack; velocity của attack đó là `60` (mở), phần còn lại do tide lo. Không bịa nốt mới.
- `_shape_dynamics()`: **chưa** mở cho câu phẳng trong đợt này, để tránh cộng hai lần arch. Nếu sau khi đo vẫn thiếu, mở `phrase_at()` cho `rise == 0` và dùng `_flat_swell()` cho `extra` (0–4), nhưng phải đo lại toàn bộ pattern.

### 3.3. Test

- Câu phẳng 8 mốc, 8 attack: arch `60 → 64 → 62`, spread = 4; không nốt nào vượt 64.
- Câu phẳng một nốt ngân: không sinh attack mới; velocity = 60.
- Câu `rise = 0` không còn `64` phẳng tuyệt đối ở mọi nốt.
- Sóng giữ nguyên hiệu trong ô (arch sống qua `apply_guitar_wave`).

---

## 4. Điểm 4 — micro tối thiểu cho texture mỏng

### 4.1. Phạm vi

Chỉ 3 texture đang phẳng:

| Texture | Hàm | Hiện trạng |
|---|---|---|
| `alcaniz_soft` (`ALCANIZ_SOFT = 11`) | `_alcaniz_soft()` | 2 attack/ô (offset 0, 3), cùng `_lead_vel` |
| `olite_thin` (`OLITE_THIN = 12`) | `_olite_thin()` | 4 attack/ô (offset 0, 3, 4, 7), cùng `_lead_vel` |
| `JUGLAR_THIN` (`9`) | `_render_juglar_bar(..., "thin")` | 1 nốt/phách; đã có `_three_four_offbeat` |

### 4.2. Luật

Dùng đúng cơ chế micro hiện có: `_MICRO = 2`, `_micro_drop()`, `_micro_fits()`, sàn `_MICRO_FLOOR = 40`, lead > bass + 2, bass > support + 2.

- **`alcaniz_soft`**: offset 3 (phách mạnh phụ) hạ 1 bậc (`−2`) nếu `_micro_fits` cho phép. Offset 0 giữ `_lead_vel`.
- **`olite_thin`**: hai nốt **leading eighth** (offset 3 và 7, đang là `slur_start` vào phách sau) hạ 1 bậc; offset 0 và 4 (dotted quarter) giữ `_lead_vel`. Đúng vai trò "nốt lấy đà".
- **`JUGLAR_THIN`**: giữ `_three_four_offbeat` (đã hạ phách 2/4). Chỉ thêm fallback: nếu phách 2/4 đang bằng phách trước (vì `_on_moving_apex` trả `True`) thì hạ 1 bậc, nhưng **không** hạ nếu đã hạ bởi `_three_four_offbeat`. Tốt nhất là sửa `_three_four_offbeat` trả `level - 2` cho mọi phách 2/4 ở `mode=thin`, bỏ nhánh apex, vì thin là texture đệm.
- Không đụng `alcaniz_opening`, `alcaniz` full, `olite` full: các texture đó đã có micro (0–18% phẳng).

### 4.3. Test

- Mỗi texture: residual range ≥ 2 ở ≥ 80% số ô; lead > bass; không note nào dưới 40.
- `alcaniz_soft`: offset 0 và 3 lệch đúng 2 (hoặc 0 nếu `_micro_fits` chặn).
- `olite_thin`: offset 3 và 7 thấp hơn dotted quarter liền trước đúng 2.
- `JUGLAR_THIN`: phách 2/4 thấp hơn phách 1 đúng 2 (trừ khi bass chặn).
- Full/opening không đổi.

---

## 5. Bốn pattern còn dưới 80% — nguyên nhân và cách xử lý

### 5.1. Bảng nguyên nhân

| Pattern | Arch hiện tại | Nguyên nhân chính | Cách xử lý |
|---|---:|---|---|
| `danza` | 69% | phách yếu ghim 64; sàn 68 nén đỉnh | Điểm 1; nếu vẫn < 80% thì mục 5.2 |
| `torroba_tremolo` | 76% | arch chỉ đặt lên ngón đầu chùm, nhưng metric cũ lấy trung bình cả chùm; trần 72 | Đo lại trên "singing attack" (0.2); nếu vẫn thấp, mục 5.2 |
| `preludio` | 76% | câu 147 mở giữa ô 18; `_catedral_cell` đọc câu của đầu ô (câu 128–147) cho cả cell, nên apex 147–149 nhận mức cuối câu cũ; sau đó tide đi ngược chiều | **Sửa 0.4 trước**; nếu vẫn < 80% mới mục 5.2 |
| `bach_prelude` | 67% | câu 147 mở giữa ô 18; renderer dùng `phrase_here` của câu 128–147 cho mọi eighth, apex 147–149 nhận `63` thay vì `72` | **Sửa 0.4 trước**; đo lại trên nốt price |

### 5.2. Post-wave phrase arch (chỉ bật nếu sau 0.2 + điểm 1–4 vẫn < 80%)

Đây là "Cách A" ở mục 8 của doc Torroba, tổng quát cho mọi guitar ensemble.

**Vị trí**: trong `apply_guitar_wave()`, sau `_apply_affine()` và **trước** `_apply_snaps()` / `_apply_stabs()`. Snap và stab sau đó được phép ghi đè đúng nốt accent. Nếu buộc phải đặt sau, lưu tập index snap/stab và loại trừ chúng — snap không mang cờ `pinned`, nên không có bảo vệ tự động.

**Hàm mới** trong `guitar_wave.py`:

```python
def _apply_phrase_arch(ctx, voices, placed, patterns, scale_eighths):
    """Câu giữ arch sau khi tide đã dời ô. Zero-sum trong câu."""
```

**Luật**:

1. Chỉ body phrase, bỏ pedal và scale passage (`scale_eighths`).
2. Chỉ "singing attack" theo bảng 0.2.
3. `curve`:
   - `rise > 0`: `swell(phrase, onset)` (0…1, đỉnh ở apex);
   - `rise == 0`: `_flat_swell()` chuẩn hoá 0…1 (đỉnh ở giữa).
4. `offset = round(AMP * (curve - mean_curve))`, `AMP = 6` (range ±3). Zero-sum để không đổi mức trung bình của tide.
5. Cộng `offset` vào velocity **sau** wave, clamp:
   - nốt ấm (≤ 64) vẫn ≤ 64;
   - nốt móng (> 64) vẫn trong 69…`v_ceil`;
   - tôn trọng `v_ceil` của ô.
6. Bỏ `pinned` (fan), `hairpin` (scale/swarm), `tie_stop`; `_sync_ties` chạy sau nên tie tự theo.
7. Với Torroba: **không** chạy thêm nếu `apply_torroba_sung_arch` đã chạy, hoặc gộp hai hàm (truyền `only_pattern`/`sung`). Tránh cộng hai arch.
8. Nếu chỉ bật cho 4 pattern yếu: truyền `only_patterns={...}` để không đổi các pattern đã ≥ 80%.

**Vì sao zero-sum**: tide đã lo mức trung bình của câu; arch chỉ cần chênh lệch trong câu. Zero-sum bảo đảm không làm câu to/nhỏ đi, chỉ làm rõ mở → đỉnh → nhả.

**Test**:

- `preludio`: câu có tide dốc ngược vẫn có arch ≥ 2 sau wave.
- `bach_prelude`: đo trên nốt price; neighbor vẫn −2.
- `torroba_tremolo`: đo trên cú đầu phách; ngón cái vẫn +2 so với ngón đầu.
- `danza`: nếu bật, phách mạnh vẫn ≥ 68 và phách yếu vẫn dưới.
- Mọi pattern không nằm trong `only_patterns` giữ nguyên từng velocity.

---

## 6. Đo lại sau mỗi bước

Script đo (phải commit để review tái lập):

- `backend/scripts/diag_phrase_coverage.py` — arch theo câu + micro theo pattern, đo cả **written** (`render()`) và **heard** (`humanize(score)`), dùng metric 0.1 và singing attack 0.2.
- `backend/scripts/diag_humanize_repeats.py` — audit pass nốt lặp (đã có trong PR fix): eq pair, cross-voice, floor, max move.

Các script scratch cũ trong `backend/tmp/` (`diag_phrase_micro.py`, `diag_micro_residual.py`, `diag_weak_phrases.py`) không được commit; không dùng số của chúng làm chuẩn.

Thứ tự đo:

1. Sau 0.4 + điểm 1: `danza`/`fandanguillo`.
2. Sau điểm 2–3: các pattern dùng `_note_velocity`/`_sustain`.
3. Sau điểm 4: 3 texture mỏng.
4. Sau mục 5.2 (nếu bật): 4 pattern còn lại.

Mọi bảng số phải ghi rõ: span, movement, metric, written hay heard, và `n` câu/ô.

---

## 7. Thứ tự thực hiện

1. **Sửa 0.4 — đọc câu theo từng eighth** (bug gốc, không đổi cảm giác):
   - `_sustain()` nhận `ctx` (hoặc callback `phrase_at`) và dùng `_phrase_at(ctx, attack)` cho từng run;
   - `_render_bach_prelude_bar()`: `_covering_phrase(ctx, eighth, phrase)` cho từng eighth;
   - `_catedral_cell()` / `_render_catedral_preludio_bar()`: tra câu cho `eighth` và `eighth+3`;
   - rà các `_render_*_bar(..., phrase_here)` còn lại, ưu tiên các pattern có câu mở giữa ô.
2. **Đo lại bằng metric 0.1 + singing attack 0.2**; chốt danh sách thật sự < 80%. (Sau bước 1, dự kiến `bach_prelude` và `preludio` tăng mạnh.)
3. **Điểm 1** (`danza`/`fandanguillo`): sửa `_block()`, `_answer()`; test; đo.
4. **Điểm 2** (small-rise): sửa `_note_velocity()`; test; đo.
5. **Điểm 3** (flat): thêm `_flat_swell()`; test; đo.
6. **Điểm 4** (thin micro): sửa `_alcaniz_soft()`, `_olite_thin()`, `_three_four_offbeat()`; test; đo.
7. **Mục 5.2** chỉ bật cho pattern còn < 80%; test; đo.
8. Chạy toàn bộ `backend/tests`, bump `RECAP_REVISION` + `SPAN_REVISION` khi audio đổi.

---

## 8. Tiêu chí nghiệm thu

- [ ] Câu mở giữa ô: mọi eighth dùng swell của **câu chứa nó**, không dùng câu của đầu ô. Test câu 147–173 (apex 147–149) phải ra `72` ở apex, không phải `63`.
- [ ] Metric 0.1 + singing attack 0.2: **mọi pattern ≥ 80% câu có arch ≥ 2**, median arch ≥ 4.
- [ ] `danza`/`fandanguillo`: phách mạnh ≥ 68; phách yếu = `min(ordinary, 67)`; lead > bass.
- [ ] Câu `rise 1–2`: arch co theo rise (`63 → 67 → 63` cho rise 1; `61 → 69 → 61` cho rise 2), không còn `72/64`.
- [ ] Câu `rise 0`: 8 mốc ra arch `60 → 64 → 62` (spread 4), không nốt nào vượt 64; nốt ngân không sinh attack mới.
- [ ] `alcaniz_soft`, `olite_thin`, `JUGLAR_THIN`: ≥ 80% ô có residual range ≥ 2; không note nào dưới 40; lead > bass.
- [ ] Full/opening textures và các pattern đã ≥ 80% không đổi từng velocity (trừ khi cố ý).
- [ ] `pytest` toàn bộ xanh; test mới cho từng mục.
- [ ] Audio đổi → bump revision.

---

## 9. Rủi ro / quyết định cần chốt

1. **Cộng hai arch**: `_melody_swell` (written) + post-wave arch (mục 5.2) có thể thành 2 lần. Nếu bật 5.2 toàn cục, phải giảm biên độ written hoặc chỉ bật cho pattern yếu. Đề xuất: chỉ bật `only_patterns` cho 4 pattern yếu trước.
2. **Dance gap**: `min(ordinary, 67)` làm khoảng mạnh–yếu co lại còn 1 ở đỉnh câu. Nếu nghe mất chất vũ khúc, hạ trần xuống 66 hoặc giữ 67 nhưng kiểm tra bằng tai.
3. **Câu phẳng**: arch 4 bậc (`60 → 64 → 62`) là nhỏ có chủ đích để không nhảy sang lớp móng. Nếu nghe quá ít, có thể dùng 63 làm đỉnh; không dùng 68.
4. **Thin/soft micro**: hạ nốt lấy đà 2 bậc là thay đổi cảm giác; phải nghe `alcaniz_soft` và `olite_thin` trước khi chốt.
5. **Metric**: các con số cũ (78/77/72/69/68/58/54) là metric cũ. Sau khi sửa metric, 3 pattern đã ≥ 80%; đừng sửa nhạc để chạy theo metric cũ.
