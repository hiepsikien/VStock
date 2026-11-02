# Kế hoạch sửa DFI v4 — trace theo bè và Motion theo nốt giá

> Trạng thái: **kế hoạch, chưa implement**. Tài liệu này chốt phạm vi, thiết kế
> và thứ tự triển khai cho hai lỗi đã điều tra. Code hiện tại vẫn ở bản `"3"`.

## 0. Phạm vi

- Backend DFI: `backend/app/sonify/dfi.py`, `backend/app/sonify/render.py`.
- Test: `backend/tests/test_dfi.py`.
- Tài liệu: `docs/sonify-data-fidelity-index.md` và file này.
- **Không** đổi audio, endpoint, hay UI (trừ copy ambient nếu cần, xem §10).
- Không đổi trọng số `S/M/T/R/V`, không đổi ngưỡng band, không đổi coverage.

## 1. Kết luận điều tra

### 1.1. Motion 0.01 ở `ACB / 3M / guitar / torroba`

Tái hiện bằng `GET /v1/stocks/ACB/span?range=3M&variant=guitar&ensemble=torroba&humanize=1&color=1`:

```
movement I  shape 0.3198  motion 0.0148  structure 0.5791
            resolution 0.5031  volume 0.4311  coverage 0.8905  score 30.9
```

Trong 130 cặp eighth liên tiếp của cửa sổ câu I:

| Kiểu cặp | Số lượng | Ghi chú |
|---|---:|---|
| cả giá và nốt cùng đổi | 68 | tín hiệu thật |
| hold (giá đổi, nốt đứng) | 41 | 36/41 là đúng 1 tick 0.05 |
| ornament (giá đứng, nốt đổi) | 21 | nốt hoa mỹ, không mang giá |

- Trên **nốt giá** (attack mang giá), τ = 0.51 / 0.26 / 0.44 cho ba câu; Spearman 0.66 / 0.34 / 0.62.
- Median bước nốt: 2 semitone cho bước giá nhỏ, 4–7 cho bước giá lớn.

Nguyên nhân: Motion đang chạy trên **lưới eighth**, nơi `price_eighths` là chuỗi
nến đã resample (≈4.5 nến/bar → giá đổi ~3 lần/bar) trong khi guitar chỉ đặt
~2.7 nốt giá/bar. Các bước giá 1 tick nằm giữa hai nốt trở thành "hold" hoặc
"ornament"; τ-b xếp hạng tất cả các bước với nhau nên tín hiệu thật bị xoá.
Hai câu còn lại còn cho τ âm, bị `max(0, tau)` kẹp về 0.

Kết luận: **0.01 không đo biên độ; nó đo nhiễu lượng tử hoá của thang nhạc.**

### 1.2. Symphony bỏ sót bè flute

`render.py:1187-1201` chỉ gom `[*score.lead, *score.support]` (violin + cello)
khi dựng trace. Nhưng khi violin "yield", violin/cello im lặng và **flute**
(`score.high`) một mình mang đường giá (`_flute_and_violin_dovetail`).

Đo trên `ACB / 3M / symphony / classic`, movement I:

```
grid                     1472 eighth
pitch = None              906  (62%)
  trong đó flute đang kêu 810  (55% toàn bộ timeline)
trace points              196
coverage                 0.48
score                    33.7
```

Ví dụ bar 10–13: giá chạy 22.30 → 22.40, violin/cello nghỉ, flute kêu, mà
`pitch_at()` trả `None`. Tức là 89% phần timeline bị mù là span flute.

Ước lượng thô khi thêm flute (dùng cao độ flute đang kêu): coverage 0.48 → 1.00,
score 33.7 → 54.8. Đây chỉ là **upper bound** vì flute chơi hòa âm +3/+4/+7
semitone, không phải cao độ đường giá; lấy midi flute làm trace sẽ làm méo
Shape/Motion. Vì vậy phải ghi **cao độ ý định**, không phải midi đang kêu.

## 2. Nguyên tắc sửa

1. **Theo vai trò bè, không theo tên nhạc cụ.** Các ensemble chỉ đổi MuseSounds
   voice và vài biên cao độ; thứ tự part vẫn là `P5/P1/P2/P3/P4` →
   `high/lead/support/comp/low` (`backend/app/sonify/ensemble.py:3-6`). Mọi
   logic phải viết trên `score.lead`, `score.support`, `score.high`,
   `score.low`, không nhắc "violin", "flute", "alto".
2. **Ghi cao độ ý định.** Nơi nào bè chơi hòa âm/octave fold, trace ghi
   `line[eighth]` (đường giá ý định), không ghi `note.midi`.
3. **Chỉ thêm bè thật sự mang giá.** Bè đệm/hoa mỹ (halo, shimmer, bell,
   vibraphone, swell) không được thêm vào trace.
4. **Motion so tại cùng sự kiện:** nốt-giá → nốt-giá, không phải từng eighth.
5. **Không đổi Shape/Structure/Resolution/Coverage** trừ khi trace thay đổi
   (hệ quả tất yếu, phải re-baseline).

## 3. Bản đồ bè

`ensemble.py` giữ nguyên vai trò; cột "ensemble khác" chỉ là tên nhạc cụ thay.

| Variant | `lead` (P1) | `support` (P2) | `high` (P5) | `comp` (P3) | `low` (P4) | Bè mang giá |
|---|---|---|---|---|---|---|
| Symphony | Violin / Oboe / Trumpet | Cello / Clarinet / Trombone | **Flute / Piccolo / Glockenspiel** | Harp / Horns | Contrabass / Tuba | `lead` + `support` + `high` |
| Jazz | Alto / Soprano / Trumpet | Tenor / Baritone / Trombone | Vibraphone / Electric Guitar | Rhodes / Wurly / Hammond | Bass | `lead` + `support` |
| Ambient | **Glass / English Horn / Clarinet** | Halo | Shimmer / Handchimes / Handbells | Swell | Drone | `lead` |
| Minimalist | **Arpeggio / Marimba / Guitar** | Pad / Choir / Cello | Bell / Crotales / Flute 2 | Pulse / Harpsichord / Piano | Sub bass | `lead` (register) |
| Guitar | Nylon (một part) | — | — | — | — | writer tự ghi |

Ghi chú:

- **Symphony:** `high` chỉ mang giá khi violin yield. Khi violin còn chơi,
  `high` là doubling/hòa âm; `fill_trace_from_notes` chỉ điền vào chỗ base
  **không** kêu nên không tạo lần đọc giá thứ hai.
- **Jazz:** `high` (vibraphone) là comping; chỉ 2% grid có vibraphone kêu khi
  trace trống → không thêm.
- **Ambient:** `lead` là glass line. `high` (shimmer) là chord-tone accent,
  `support` (halo) và `low` (drone) là bed. 49% grid `None` là breath có chủ ý,
  không phải bè bị bỏ sót (xem §5).
- **Minimalist:** giá nằm trong **register của arpeggio** (`lead`), không nằm ở
  bell. Bell là accent thưa trên breakout/apex (xem §5).
- **Guitar:** đã đúng; `guitar.py:174-198` ghi trace từ `lead+support+low` và
  remap về `original_melody`.

## 4. Thay đổi chi tiết

### 4.1. `backend/app/sonify/dfi.py`

#### a) `trace_from_notes` — thêm `snap_to_line`

```python
def trace_from_notes(
    notes, *, line, prices, epb, bar_beats,
    frame_bars=frozenset(), role="attack", octave_tolerant=False,
    max_octaves=3, voice="lead", snap_to_line: bool = False,
):
    ...
    pitch=float(target) if snap_to_line else float(note.midi),
```

Đồng thời sửa tie-break khi trùng `(bar, beat)` để so `abs(diff)` đã lưu,
không so `found[index].pitch - target` (sai khi `snap_to_line=True`).

#### b) `fill_trace_from_notes` — bè `high` mang giá bằng hòa âm

```python
def fill_trace_from_notes(
    base, notes, *, line, prices, epb, bar_beats,
    frame_bars=frozenset(), voice="high",
) -> tuple[PriceTracePoint, ...]:
    """Thêm bè high ở nơi base im lặng, ghi cao độ ý định line[eighth]."""
    lookup = _PitchLookup(base, bar_beats)
    extra = []
    seen = set()
    for note in notes:
        if note.midi is None or note.bar in frame_bars:
            continue
        eighth = _event_eighth(note, epb)
        if eighth is None or not (0 <= eighth < len(line)):
            continue
        key = (note.bar, round(note.beat, 4))
        if key in seen:
            continue
        point = PriceTracePoint(
            bar=note.bar, beat=note.beat,
            duration_beats=max(note.duration_beats, 0.01),
            price=prices[eighth] if eighth < len(prices) else 0.0,
            pitch=float(line[eighth]), role="anchor", voice=voice,
        )
        start, end = _trace_bounds(point, bar_beats)
        if _overlaps(lookup.items, lookup.starts, lookup.max_span, start, end):
            continue
        seen.add(key)
        extra.append(point)
    if not extra:
        return tuple(base)
    return tuple(sorted((*base, *extra), key=lambda p: (p.bar, p.beat)))
```

#### c) `_motion` — dùng `eps` đúng tài liệu

Hiện tại `dfi.py:546` lọc bằng `_EPS = 1e-9`; tham số `eps` không được dùng.
Sửa thành:

```python
if abs(right.price - left.price) > eps
   or abs((right.pitch or 0.0) - (left.pitch or 0.0)) > _EPS
```

Đúng §4.5 của `sonify-data-fidelity-index.md`: bỏ cặp khi `|ΔP| ≤ εp` **và**
`Δpitch = 0`.

#### d) `motion_points` — lấy nốt giá thay vì lưới eighth

```python
def motion_points(score, windows, epb) -> dict[int, list[_Point]]:
    """Một điểm mỗi attack mang giá, gom theo analysis window."""
    points, seen = [], set()
    for point in score.price_trace:
        if point.pitch is None:
            continue
        window = _window_of(windows, point.bar)
        if window is None:
            continue
        eighth = point.bar * epb + int(round(point.beat * 2))
        if eighth in seen:
            continue
        seen.add(eighth)
        points.append(_Point(eighth, point.price, point.pitch, window,
                             _phrase_of(score.phrases, eighth)))
    points.sort(key=lambda p: p.eighth)
    by_window = {}
    for point in _deregister(points):
        by_window.setdefault(point.window, []).append(point)
    return by_window
```

- Dedup theo `eighth` (base và fill có thể trùng ở cùng một eighth).
- `_deregister` toàn bộ chuỗi trước khi chia window để bỏ nhảy octave ở biên câu.

#### e) `compute` — Motion dùng `motion_points`

```python
notes_by_window = motion_points(score, windows, epb)
...
value, weight, _low = _motion(notes_by_window.get(chunk[0].window, []), eps)
```

- Shape / Resolution / Structure / Coverage vẫn dùng lưới eighth.
- `n_moves` vẫn đếm trên lưới (giữ confidence/opportunity hiện tại).

#### f) `DFI_VERSION = "4"`

Đổi ở `dfi.py:26`. Cache sidecar có `dfi_checked` sẽ tự bỏ.

### 4.2. `backend/app/sonify/render.py`

Import thêm:

```python
from app.sonify.dfi import fill_trace_from_notes, trace_from_notes, trace_register_per_bar
```

Trong `_attach_dfi_inputs` (khoảng dòng 1165):

```python
if variant == "minimalist":
    trace = trace_register_per_bar(score.lead, ...)          # giữ nguyên

elif variant == "ambient":
    trace = trace_from_notes(
        score.lead, line=pitches, prices=price_eighths,
        epb=dfi_epb, bar_beats=dfi_bar_beats, frame_bars=frame_set,
        role="anchor", octave_tolerant=True, snap_to_line=True,
    )

elif variant in ("symphony", "jazz"):
    trace = trace_from_notes(
        [*score.lead, *score.support], line=pitches, prices=price_eighths,
        epb=dfi_epb, bar_beats=dfi_bar_beats, frame_bars=frame_set,
        octave_tolerant=True, voice="line", snap_to_line=True,
    )
    if variant == "symphony":
        # Flute (high) nhận line khi violin yield; chơi hòa âm nên phải ghi
        # cao độ ý định, và chỉ điền nơi violin/cello im lặng.
        trace = fill_trace_from_notes(
            trace, score.high, line=pitches, prices=price_eighths,
            epb=dfi_epb, bar_beats=dfi_bar_beats, frame_bars=frame_set,
            voice="high",
        )
```

Thứ tự quan trọng: `_attach_dfi_inputs` chạy **sau** `fit_ensemble` và frame,
nên trace thấy đúng `lead/support/high` cuối cùng.

### 4.3. `backend/tests/test_dfi.py`

Thêm:

| Test | Assert |
|---|---|
| `test_trace_snaps_to_the_intended_line` | note lệch octave + `snap_to_line=True` → `pitch == line[eighth]` |
| `test_fill_trace_adds_high_only_where_base_is_silent` | base bar 0, high bar 0+1 → chỉ bar 1 được thêm, pitch = line |
| `test_symphony_trace_covers_a_flute_only_bar` | render uptrend; có bar chỉ `high` kêu và bar đó nằm trong trace |
| `test_motion_reads_price_notes_not_the_eighth_grid` | `_motion` trên hold 1 tick + anchor path; anchor motion cao hơn grid motion |
| `test_motion_filters_below_the_phrase_eps` | cặp `|ΔP| < eps` và `Δpitch=0` bị bỏ |

Giữ nguyên `test_symphony_and_jazz_trace_the_lower_line_voice` (đã có) và thêm
biến thể `high`-only cho symphony.

### 4.4. Tài liệu

- `docs/sonify-data-fidelity-index.md`
  - §4.2 Trace: nói rõ pool theo vai trò; symphony dùng `lead+support+high`.
  - §4.5 Motion: nói rõ chạy trên **nốt giá**, không trên lưới eighth; `eps`
    là `εp` của câu.
  - §9.1: đóng mục "flute/piano bị bỏ sót" sau khi sửa.
  - §10: thêm quyết định "Motion anchor-to-anchor" và version `"4"`.
- File này: cập nhật trạng thái + số re-baseline sau khi implement.

## 5. Ambient và Minimalist — kết luận kiểm tra

### Ambient

`render_ambient_score` (`ambient.py:1086-1097`):

- `lead = glass` — **đường giá**, dựng từ `pitches` qua `_glass()`.
- `high = shimmer` — accent hợp âm thưa (`_shimmer`, `_shimmer_midi`), không
  phải line.
- `support = halo`, `comp = swell`, `low = drone` — bed.

Đo `ACB / 3M / ambient / classic`:

```
none=720/1472 (49%)   support kêu 720   low kêu 720   high kêu 24
```

49% đó là **breath có chủ ý** của glass; halo/drone vẫn kêu nhưng là hợp âm/nền,
không mang giá. Vì vậy **chỉ dùng `lead`**, không fill từ `high/support`.
Coverage thấp ở ambient là đúng thiết kế ("thưa là bản sắc").

### Minimalist

`render_minimalist_score` (`minimalist.py:661-672`):

- `lead = arpeggio`. `_synth_arpeggio_part` map `raw_pitches` → `norm` →
  `base_idx` trên chord ladder. Giá nằm ở **register/brightness của arpeggio**.
- `high = bell` — accent thưa trên breakout/apex, không phải line liên tục.
- `support = pad`, `comp = pulse`, `low = sub bass` — nền.

Đo `ACB / 3M / minimalist / classic`: `none = 0` trên cả ba movement; trace
register phủ 100% bar. Vì vậy **giữ `trace_register_per_bar(score.lead)`**,
không thêm bell.

### Khi nào phải xem lại

Nếu sau này writer cho bè khác nhận line (ví dụ ambient để shimmer dẫn trong
breath, hoặc minimalist để bell dẫn), phải thêm một `fill_trace_from_notes`
tương ứng và một test "voice-only bar". Không suy đoán theo tên nhạc cụ.

## 6. Kế hoạch test

1. `pytest backend/tests/test_dfi.py -q`.
2. `pytest backend/tests -q` (không chỉ DFI).
3. Test thủ công:
   - `ACB / 3M / guitar / torroba` → Motion phải > 0.2; điểm ~38 (xem §7).
   - `ACB / 3M / symphony / classic` → coverage phải > 0.9; không còn bar
     flute-only nào `None`.
   - `ACB / 3M / symphony / wood|brass` → cùng hành vi (chỉ đổi tên nhạc cụ).
   - `ACB / 3M / ambient|minimalist` → Motion thay đổi nhưng coverage không
     giảm thêm.
4. Kiểm tra `test_non_guitar_ensembles_keep_the_same_chart_clarity`: dung sai
   hiện tại `<= 4` có thể cần nới/thu sau khi trace đổi; ghi lý do nếu đổi.

## 7. Tác động dự kiến và re-baseline

### Guitar torroba (ACB / 3M)

```
movement I  : motion 0.015 → 0.39   score 30.9 → 38.0
movement II : motion 0.130 → 0.26   score 46.1 → 48.2
movement III: motion 0.127 → 0.45   score 39.7 → 45.7
```

### Symphony (ACB / 3M)

Sau khi trace có flute, coverage dự kiến 0.48/0.52/0.68 → ~1.0. Điểm sẽ tăng;
**số chính xác phải đo lại** bằng trace đúng (không dùng midi flute như ước
lượng thô §1.2). Shape/Motion có thể đổi vì trace phủ thêm 55% timeline.

### Ensemble

Vì trace theo vai trò, `classic/wood/brass` (symphony) và
`classic/soul/organ` (jazz) phải cho cùng một đường giá; chỉ khác octave fold.
`snap_to_line=True` loại nốt nhảy octave của wood/choir.

### Cache và signature

- `DFI_VERSION = "4"` làm sidecar cũ bị bỏ; audio không đổi.
- `backend/app/sonify/fixtures/dfi_signatures.json` là artifact của corpus;
  nếu dùng để so sánh UI thì phải regenerate sau khi chốt số.

## 8. Rủi ro và cách chặn

| Rủi ro | Hậu quả | Cách chặn |
|---|---|---|
| Fill flute cả khi violin còn chơi | Hai lần đọc cùng một giá | Chỉ fill khi `_overlaps` base = False |
| Dùng midi flute thay line | Shape/Motion méo vì hòa âm +3/+4/+7 | Luôn ghi `line[eighth]` |
| Hardcode tên nhạc cụ | Ensemble khác gãy | Chỉ dùng `lead/support/high/low` |
| Ambient/minimalist bị thêm bè đệm | Điểm bịa | Chỉ `lead`; high không mang line |
| Motion anchor quá thưa | τ bất ổn | Giữ fallback anchor-to-anchor; test cửa sổ ít cặp |
| `eps` mới làm rơi cặp thật | Motion thấp giả | Test với eps chuẩn; log `motion_weight` |
| Version bump làm cache lạnh | Chậm lần đầu | Chấp nhận; sidecar tự tính lại |
| Điểm đổi làm lệch signature/test | CI đỏ | Re-baseline có chủ đích, ghi trong PR |

## 9. Checklist triển khai

- [ ] `trace_from_notes(..., snap_to_line)` + tie-break theo `abs(diff)`.
- [ ] `fill_trace_from_notes`.
- [ ] `_motion` dùng `eps`.
- [ ] `motion_points` + `compute` dùng anchor.
- [ ] `render.py` cập nhật pool theo variant (symphony thêm `high`).
- [ ] `DFI_VERSION = "4"`.
- [ ] 5 test mới + test `high`-only cho symphony.
- [ ] Chạy `pytest backend/tests`.
- [ ] Đo lại ACB/3M cho 5 variant × 3 movement, ghi vào file này.
- [ ] Cập nhật `docs/sonify-data-fidelity-index.md` (§4.2, §4.5, §9.1, §10).
- [ ] Quyết định regenerate `dfi_signatures.json`.
- [ ] Kiểm tra thủ công URL trong báo cáo gốc.

## 10. Điểm cần chốt trước khi code

1. **Copy ambient:** nếu Motion ambient tăng sau khi chuyển anchor, câu
   "Thưa là bản sắc; điểm thấp ở Chuyển động/Hình dạng là có chủ ý" có thể
   không còn đúng. Cần quyết định giữ, sửa, hay bỏ.
2. **Signature fixture:** regenerate ngay trong PR hay để Phase 7 calibration?
3. **`snap_to_line` cho ambient:** kế hoạch đang bật. Nếu muốn giữ nguyên hành
   vi cũ của ambient, tắt riêng cho ambient (không khuyến nghị, vì register
   fold của `_fold_glass` sẽ quay lại).
4. **Ngưỡng dung sai ensemble spread** (`<= 4`): giữ hay siết sau khi trace
   thống nhất theo vai trò.
