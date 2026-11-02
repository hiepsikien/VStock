# Kế hoạch sửa DFI v4 — trace theo bè và Motion theo nốt giá

> Trạng thái: **đã implement trong PR #128** (DFI v4). 5 quyết định ở §10 đã
> chốt ngày 2026-11-03. Đã đối chiếu với code, implement và đo trên `ACB / 3M`
> (local DB; dữ liệu `as_of` **2026-11-02**). Bảng số trong §1.1/§5/§7
> regenerate bằng `backend/scripts/dfi_probe.py`; cột **v3** ở §7 là baseline
> lịch sử đo trước v4, không regenerate được. Số phụ thuộc ngày dữ liệu, không
> phải hằng số.

## 0. Phạm vi

- Backend DFI: `backend/app/sonify/dfi.py`, `backend/app/sonify/render.py`,
  `backend/app/sonify/model.py`, `backend/app/schemas.py`.
- Test: `backend/tests/test_dfi.py`.
- Công cụ: `backend/scripts/dfi_probe.py` — không ghi renderer/audio cache,
  nhưng `plan_span` gọi OHLC live khi store lạnh, nên số phụ thuộc `as_of`
  (probe in ra đầu mỗi lần chạy). Đường dẫn dùng `Path(__file__).parents[1]`.
- Tài liệu: `docs/sonify-data-fidelity-index.md` và file này.
- **Không** đổi audio, endpoint, hay UI (trừ copy ambient nếu chốt §10.1).
- Không đổi trọng số `S/M/T/R/V`, ngưỡng band, hay công thức coverage.

## 1. Kết luận điều tra

### 1.1. Motion 0.01 ở `ACB / 3M / guitar / torroba`

Baseline qua `GET /v1/sonify/dfi/pieces` khớp plan cũ:

| | score | motion | shape | coverage |
|---|---:|---:|---:|---:|
| mv I | 30.9 | 0.0148 | 0.3198 | 0.8905 |
| mv II | 46.1 | 0.1297 | 0.8953 | 0.7555 |
| mv III | 39.7 | 0.1275 | 0.5887 | 0.8763 |

**Thuật ngữ.** Code gọi đơn vị chấm là **analysis window** (`score.analysis_windows`,
`_window_of`), không phải `Phrase`. Tài liệu cũ (§4.5) gọi là "câu"; từ đây
trong plan dùng **"cửa sổ"** cho analysis window, còn "phrase" là đơn vị nhỏ
hơn trong `score.phrases`. `_phrase_eps` là **per window**, không per phrase.

Số cặp trong movement I (`scripts/dfi_probe.py ... --classify`):

| | window I | window II | window III |
|---|---:|---:|---:|
| bước eighth trong cửa sổ | 359 | 383 | 359 |
| cặp usable (cả hai điểm có `pitch`) | 278 | 280 | 258 |
| cặp sau khi bỏ `(0,0)` | 130 | 143 | 124 |
| trong đó hold (`ΔP>0, Δpitch=0`) | 41 | 52 | 44 |
| trong đó ornament (`ΔP=0, Δpitch>0`) | 21 | 19 | 17 |
| τ-b trên mẫu đã lọc (chưa kẹp 0) | 0.045 | −0.078 | −0.061 |

- 41 hold của window I: **36 đúng 1 tick 0.05**, 3 ở 0.10, 2 ở 0.20.
- "42% bước 1 tick" ở index §9.2 là **384/919 bước nến**; trong mẫu đã lọc
  của window I là **36/86 cặp 1 tick**. Hai mẫu số khác nhau — không trộn.
- Motion của **movement** II/III là 0.130/0.127 (dương). Chỉ **window** II/III
  của movement I có τ âm; đừng gán nhầm hai cấp.

Số sau implement (frame bars đã lọc, `dfi_probe.py`):

| movement | v3 motion | anchors | anchors+eps | score v3 | score v4 |
|---|---:|---:|---:|---:|---:|
| I | 0.0148 | 0.439 | **0.455** | 30.9 | **39.2** |
| II | 0.1297 | 0.268 | **0.214** | 46.1 | **47.4** |
| III | 0.1275 | 0.475 | **0.479** | 39.7 | **46.2** |

Nguyên nhân gốc: Motion chạy trên **lưới eighth**, nơi `price_eighths` là chuỗi
nến đã resample (≈4.5 nến/bar → giá đổi ~3 lần/bar) trong khi guitar chỉ đặt
~2.7 nốt giá/bar. Các bước 1 tick nằm giữa hai nốt thành hold/ornament; τ-b xếp
hạng tất cả các bước với nhau nên tín hiệu thật bị xoá.

### 1.2. Symphony bỏ sót bè `high`

`render.py:1165` (`_attach_dfi_inputs`; pool `[*score.lead, *score.support]` ở
1187-1201) chỉ gom violin + cello khi dựng trace. Khi violin yield, violin/cello
im lặng và **flute** (`score.high`) một mình mang đường giá.

Đo trên `ACB / 3M / symphony / classic`, movement I:

```
grid                     1472 eighth
pitch = None              906  (62%)
  trong đó flute đang kêu 810  (55% toàn bộ timeline)
trace points              196
coverage                 0.48
```

Số thực tế sau implement (đúng spec yield-span: capture `pitches` + `yield_spans`
từ writer, merge tie, lọc span, lọc overlap, `pitch=line[eighth]`, **không
clip**) trên `symphony / classic`:

| movement | coverage v3 → fill | Shape v3 → fill | Motion (anchor) v3 → fill | score v3 → v4 |
|---|---:|---:|---:|---:|
| I | 0.484 → **1.000** | 0.875 → **0.829** | 0.266 → **0.371** | 33.7 → **69.4** |
| II | 0.525 → **0.964** | 0.963 → **0.982** | 0.279 → **0.132** | 37.6 → **69.0** |
| III | 0.680 → **1.000** | 0.991 → **0.921** | 0.370 → **0.435** | 51.6 → **67.6** |

Bảng này là **fill + snap**. Nếu chỉ fill mà chưa snap, score là
54.8/46.4/69.3; phần chênh **+14.6 / +22.6 / −1.7** là do `snap_to_line`
(bảng attribution ở §7). Với ambient/jazz, snap cũng là phần lớn mức tăng.

Ba điều phải đọc đúng:

1. **Điểm nhảy gần như toàn bộ là hệ số coverage.** `33.7 / 0.484 ≈ 69.6`; S/M
   chỉ đổi vài phần trăm. Không được nói "fill làm symphony trung thực hơn 36
   điểm" — nó chỉ làm phần timeline trước đây bị bỏ nay được tính.
2. **Shape với intent không tụt còn 0.32.** Con số 0.32 của guitar đến từ
   quantization/sampling của guitar, không phải từ intent. Shape symphony sau
   fill là 0.829/0.982/0.921. Vì vậy câu cũ "score có thể thấp hơn 54.7" là
   **sai hướng**; đo thực tế là 69.4.
3. **Motion có thể giảm** (mv II 0.279 → 0.132) dù score tăng. Score và Motion
   là hai chuyện khác nhau; đừng dùng score tăng để nói Motion tốt lên.

**Band flip là thay đổi sản phẩm:** mv I 33.7 ("Rất mờ") → 69.4 ("Vừa"), chỉ
**0.6 điểm** dưới "Rõ" (70). Band thresholds không đổi (§0), nên nhãn nhảy 2
bậc; phải ghi vào PR description/re-baseline để reviewer không tưởng lỗi.

Flute chơi hòa âm **+3/+4/+7 (mod 12)** so với line; line có thể bị hạ 1–2
octave nên offset thô là −9 (= +3−12), −17 (= +7−24)… `snap_to_line` ghi
intent, `sounding_pitch` giữ **MIDI C-space** của nốt bè thực sự chơi (trước
transpose của nhạc cụ; **không phải concert pitch**) để chẩn đoán.

## 2. Nguyên tắc sửa

1. **Theo vai trò bè, không theo tên nhạc cụ.** `ensemble.py` giữ
   `P5/P1/P2/P3/P4` → `high/lead/support/comp/low`; các ensemble chỉ đổi
   MuseSounds voice và vài biên cao độ.
2. **Ghi cao độ ý định, giữ cả nốt bè thực sự chơi.** `trace.pitch = line[eighth]`
   khi `snap_to_line`; thêm `PriceTracePoint.sounding_pitch` (optional) để lưu
   **MIDI C-space** của nốt bè thực sự chơi (trước transpose của nhạc cụ; không
   phải concert pitch). Không đóng caveat "ý định vs nốt bè thực chơi" ở §9.1.
3. **Chỉ thêm bè thật sự mang giá.** Halo/shimmer/bell/vibraphone/swell không
   được thêm.
4. **Loại frame bars ở mọi nơi.** `_grid` đã bỏ (`dfi.py:435`); `motion_points`
   và `fill_trace_from_notes` cũng phải bỏ.
5. **Motion theo variant:** anchor cho guitar/symphony/jazz/minimalist; **grid**
   cho ambient (hold dài là tín hiệu fidelity thật, đúng §4.5). Xem §5/§10.1.
6. **Giữ guard `if not trace:`** trong `_attach_dfi_inputs` để writer nào sau
   này tự ghi trace không bị ghi đè.

## 3. Bản đồ bè

| Variant | `lead` (P1) | `support` (P2) | `high` (P5) | `comp` (P3) | `low` (P4) | Bè mang giá |
|---|---|---|---|---|---|---|
| Symphony | Violin / Oboe / Trumpet | Cello / Clarinet / Trombone | **Flute / Piccolo / Glockenspiel** | Harp / Horns | Contrabass / Tuba | `lead` + `support` + `high` |
| Jazz | Alto / Soprano / Trumpet | Tenor / Baritone / Trombone | Vibraphone / Electric Guitar | Rhodes / Wurly / Hammond | Bass | `lead` + `support` |
| Ambient | **Glass / English Horn / Clarinet** | Halo | Shimmer / Handchimes / Handbells | Swell | Drone | `lead` |
| Minimalist | **Arpeggio / Marimba / Guitar** | Pad / Choir / Cello | Bell / Crotales / Flute 2 | Pulse / Harpsichord / Piano | Sub bass | `lead` (register) |
| Guitar | Nylon (một part) | — | — | — | — | writer tự ghi |

Ghi chú:

- **Symphony:** `high` chỉ mang giá khi violin yield. Khi violin còn chơi,
  `high` là doubling/hòa âm; fill chỉ vào chỗ base **không** kêu.
- **Jazz:** `high` (vibraphone) là comping; chỉ 2% grid có vibraphone kêu khi
  trace trống → không thêm.
- **Ambient:** `lead` là glass line; `high` (shimmer) là chord-tone accent;
  `support` (halo) và `low` (drone) là bed.
- **Minimalist:** giá nằm trong **register của arpeggio** (`lead`); bell là
  accent thưa.
- **Guitar:** `guitar.py:174-198` đã ghi trace từ `lead+support+low` và remap
  về `original_melody`; không đổi.

## 4. Thay đổi chi tiết

### 4.1. `backend/app/sonify/model.py`

Thêm field optional, không phá cache cũ:

```python
@dataclass(frozen=True)
class PriceTracePoint:
    ...
    pitch: float | None
    sounding_pitch: float | None = None   # MIDI C-space (trước transpose) khi pitch đã snap
```

### 4.2. `backend/app/sonify/dfi.py`

#### a) `trace_from_notes` — tie-break, snap, sounding pitch

Chữ ký:

```python
def trace_from_notes(
    notes, *, line, prices, epb, bar_beats,
    frame_bars=frozenset(), role="attack", octave_tolerant=False,
    max_octaves=3, voice="lead", snap_to_line=False,
    carrier: Callable[[NoteEvent, int], float | None] | None = None,
) -> tuple[PriceTracePoint, ...]:
```

- `carrier(note, eighth)` trả pitch đích, hoặc `None` để bỏ. Mặc định là logic
  hiện tại (`line[eighth]`, octave tolerance).
- Lưu `diff_by_key[(bar, beat)]` để tie-break thật:

```python
key = (note.bar, round(note.beat, 4))
candidate = (abs(diff), -duration)          # nhỏ hơn tốt hơn
if key in index_by_key and candidate >= best_by_key[key]:
    continue
```

  Nghĩa là: giữ note gần `line` nhất; nếu cùng `|diff|`, giữ **duration dài
  hơn** (dovetail/handoff). Đây là chỗ snippet cũ sai: `PriceTracePoint` không
  lưu `diff`, và khi `snap_to_line` thì `found[index].pitch == target` nên
  `abs(...)=0` → luôn giữ note đầu.
- Ghi `pitch=float(target)` nếu `snap_to_line`, và `sounding_pitch=float(note.midi)`.
- Tie (`tie_start`/`tie_stop`) vẫn merge vào `open_ties` như hiện tại; khi merge
  duration, cộng dồn.

#### b) `fill_trace_from_notes` — chọn theo `yield_spans`, không theo overlap

`_flute_and_violin_dovetail` đã trả `yield_spans` (`render.py:1381`) và
`melody_parts` dùng chính spans đó để chia violin/cello. `apply_span_frame`
chỉ thay bar warmup/cooldown, giữ body (`movement_frame.py:117`:
`high=with_rests(_body(score.high, body, cool), total)`), nên toạ độ eighth
của body không đổi. Vì vậy chọn high note theo span **chính xác hơn** heuristic
overlap, và loại luôn flute ornament ngoài span.

```python
def fill_trace_from_notes(base, notes, *, line, prices, epb, bar_beats,
                          frame_bars=frozenset(), yield_spans=(),
                          voice="high"):
    raw = trace_from_notes(
        notes, line=line, prices=prices, epb=epb, bar_beats=bar_beats,
        frame_bars=frame_bars, voice=voice,
        snap_to_line=True,
        carrier=lambda _note, eighth: float(line[eighth]),
    )
    spans = tuple(yield_spans)
    lookup = _PitchLookup(base, bar_beats)
    extra = []
    for point in raw:
        eighth = point.bar * epb + int(round(point.beat * 2))
        if not any(start <= eighth < end for start, end in spans):
            continue
        start, end = _trace_bounds(point, bar_beats)
        if _overlaps(lookup.items, lookup.starts, lookup.max_span, start, end):
            continue
        extra.append(point)
        lookup = _PitchLookup((*base, *extra), bar_beats)   # chặn high chồng nhau
    return tuple(sorted((*base, *extra), key=lambda item: (item.bar, item.beat)))
```

- **Không còn `_clip_after_base`.** Note high bắt đầu trong overlap (violin còn
  kêu) bị bỏ. Đo trên ACB/3M: chỉ 4/246, 5/212, 0/164 point bị loại (đều là
  hòa âm +3/+4/+7 (mod 12) ngoài span) và coverage vẫn 1.000/0.964/1.000. Xấu
  nhất lý thuyết là mất 1 beat (`FLUTE_OVERLAP`) ở đầu span; thêm test cho note
  attack ngay trước span.
- `yield_spans` loại flute ornament ngoài span (kể cả khi violin nghỉ vì
  breath), nên không cần heuristic overlap.
- Nếu `yield_spans` rỗng, `fill` trả `base`; test
  `test_fill_without_yield_spans_adds_nothing` pin hành vi.
- `trace_from_notes` giữ check biên `eighth < len(line)` **trước khi** gọi
  `carrier`; `carrier` trả `None` thì bỏ note, và `target` của carrier được
  dùng để tính `diff` cho tie-break.

#### c) `_motion` — dùng `eps` đúng tài liệu

`dfi.py:546` đang lọc bằng `_EPS = 1e-9`; sửa:

```python
if abs(right.price - left.price) > eps
   or abs((right.pitch or 0.0) - (left.pitch or 0.0)) > _EPS
```

Đúng §4.5: bỏ cặp khi `|ΔP| ≤ εp` **và** `Δpitch = 0`. Đồng thời sửa doc
§4.5 cho nhất quán `<4 cặp` (code hiện dùng `<4`, không phải `<3`).

#### d) `motion_points` — nốt giá, có lọc frame

```python
def motion_points(score, windows, epb) -> dict[int, list[_Point]]:
    frame = frozenset(score.frame_bars)          # ← thiếu trong snippet cũ
    points, seen = [], set()
    for point in score.price_trace:
        if point.pitch is None or point.bar in frame:
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
    points.sort(key=lambda item: item.eighth)
    by_window = {}
    for point in _deregister(points):
        by_window.setdefault(point.window, []).append(point)
    return by_window
```

Lý do frame: `guitar.py:174-198` gọi `trace_from_notes` **không** truyền
`frame_bars`, nên trace guitar có point trong intro/outro (ACB/3M mv I: 5 point
trong 20 frame bars). Nếu `motion_points` không lọc, Motion đọc frame trong khi
Shape/Resolution/Structure/`n_moves` vẫn bỏ → lệch component.

#### e) `compute` — Motion theo variant

```python
MOTION_ON_ANCHORS = {
    "guitar": True, "symphony": True, "jazz": True,
    "minimalist": True, "ambient": False,
}
...
use_anchors = MOTION_ON_ANCHORS.get(variant, True)   # variant lạ → mặc định anchor
notes_by_window = motion_points(score, windows, epb) if use_anchors else None
...
if notes_by_window is not None:
    chunk_for_motion = notes_by_window.get(chunk[0].window, [])
else:
    chunk_for_motion = chunk          # ambient: giữ grid
value, weight, _low = _motion(chunk_for_motion, eps)
```

#### f) Version

- `dfi.py:26`: `DFI_VERSION = "4"`.
- `schemas.py:122`: `version: str = "3"` → import `DFI_VERSION` từ
  `app.sonify.dfi` và dùng default; tránh hard-code lần hai. Thêm test.

#### g) `n_moves` / `opportunity` và renormalize — ghi rõ

`n_moves` và `opportunity` vẫn đếm trên lưới eighth; Motion đo trên anchor.
Hai đại lượng không còn mô tả cùng tập bằng chứng. v4 **giữ nguyên** `n_moves`
(để không đổi confidence/opportunity lần nữa) và ghi rõ trong doc.

Khi một window trả `M = None`, `compute` vẫn chia lại trọng số cho các component
còn lại (`dfi.py:900-915`). v4 **chấp nhận renormalize** — không thêm luật
"score không vượt trần bằng chứng" vì chưa có cơ chế đó. Test chỉ pin hành vi
`test_motion_null_renormalizes_the_rest`, không hứa điều không làm được.

Đã thêm `motion_pairs: int` (additive, default 0) vào `DfiBreakdown` và
`schemas.py`. Đây là **diagnostic API-only**: `DfiSheet` chưa hiển thị; UI có
thể đọc sau nếu muốn cảnh báo "ít mẫu". Test recap đã cập nhật.

### 4.3. `backend/app/sonify/render.py`

Giữ guard `if not trace:` hiện có. Trong `_attach_dfi_inputs`:

```python
if not trace:
    if variant == "minimalist":
        trace = trace_register_per_bar(score.lead, ...)      # giữ nguyên
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
            trace = fill_trace_from_notes(
                trace, score.high, line=pitches, prices=price_eighths,
                epb=dfi_epb, bar_beats=dfi_bar_beats, frame_bars=frame_set,
                yield_spans=yield_spans, voice="high",
            )
```

`yield_spans` được tính ở nhánh symphony/jazz (`render.py:1381`). Khởi tạo
`yield_spans: list[tuple[int, int]] = []` **trước** khi định nghĩa
`_attach_dfi_inputs` để closure không `UnboundLocalError` ở nhánh không phải
symphony. Chỉ symphony truyền spans vào fill.

`_attach_dfi_inputs` chạy sau `fit_ensemble`/frame nên thấy `lead/support/high`
cuối cùng. `fill_trace_from_notes` chỉ dùng cho symphony.

**Guitar.** Trong `guitar.py:180-190`, khi remap `pitch=intended[eighth]`, set
luôn `sounding_pitch` bằng pitch cũ (MIDI C-space của nốt đang chơi):

```python
remapped.append(replace(point, pitch=float(intended[eighth]),
                        sounding_pitch=point.pitch))
```

Đây là chỗ caveat "ý định vs nốt bè thực chơi" khởi nguồn; nếu không set, field
mới bỏ trống đúng chỗ cần nhất. `sounding_pitch` là **diagnostic-only**:
`compute` vẫn đọc `pitch`; thêm test offset cho guitar (0/12) và symphony
(`(sounding_pitch - pitch) % 12 ∈ {3,4,7}`).

### 4.4. Test và tài liệu

Xem §6 và §9. Cập nhật `docs/sonify-data-fidelity-index.md` §4.2, §4.5, §9.1,
§9.2, §10; không đóng caveat "ý định vs nốt bè thực chơi (C-space)".

## 5. Ambient và Minimalist

### Ambient — giữ grid Motion

`render_ambient_score` (`ambient.py:1086-1097`): `lead=glass` (line),
`high=shimmer` (chord-tone accent), `support=halo`, `comp=swell`, `low=drone`.

Đo `ACB / 3M / ambient / classic`: `none=720/1472 (49%)`, support/low kêu 720,
high chỉ 24. 49% là **breath có chủ ý**; halo/drone là nền, không mang giá.
Vì vậy **chỉ dùng `lead`**, và **giữ grid Motion** để hold dài vẫn bị phạt.

| movement | v3 score | v3 motion | anchors (v4 trace) | grid+eps | score v4 (grid) |
|---|---:|---:|---:|---:|---:|
| I | 22.6 | 0.000 | 0.325 | 0.005 | **29.8** |
| II | 19.8 | 0.037 | 0.333 | 0.049 | **29.9** |
| III | 18.7 | 0.000 | 0.496 | 0.010 | **27.2** |

Số `score v4` cao hơn bảng Motion-only cũ (22.6/20.0/18.8) vì `snap_to_line`
bỏ octave fold của glass, sửa **cả Shape/Resolution**, không chỉ Motion.
Motion vẫn ~0 vì grid giữ hold. Đây là số **đã implement**, không phải ước lượng.

Nếu làm anchor toàn cục, ambient còn cao hơn nữa (anchors 0.325/0.333/0.496) và
thưởng hold, trái §4.5/§10 #6. Đề xuất: **per-variant** như §4.2(e).

### Minimalist — anchor, giữ `eps` chung, chấp nhận 0

`render_minimalist_score`: `lead=arpeggio` encode giá bằng register/brightness;
`high=bell` là accent thưa. `trace_register_per_bar(lead)` phủ 100% bar.

| movement | v3 score | anchors | anchors+eps | score v4 (anchors+eps) |
|---|---:|---:|---:|---:|
| I | 51.7 | 0.307 | 0.255 | 57.0 |
| II | 39.6 | 0.105 | **0.000** | 39.6 |
| III | 28.4 | 0.151 | **0.000** | 28.4 |

**Chẩn đoán đúng** (probe `--classify`, anchor pairs): sau eps filter **vẫn còn
19–63 cặp**, không rơi xuống `<4`; τ từng window **âm** rồi bị `max(0, …)`:

| movement | window | pairs sau eps | τ sau eps (chưa kẹp) |
|---|---|---:|---:|
| II | 0 / 1 / 2 | 24 / 25 / 19 | −0.148 / −0.353 / −0.300 |
| III | 0 / 1 / 2 | 40 / 50 / 63 | −0.115 / −0.098 / −0.124 |

Đây là **tín hiệu thật**: giá đi xa hơn không cho bước register lớn hơn. Câu cũ
"`_phrase_eps` (5% range) lớn hơn bước register" **sai thứ nguyên**: eps là
ngưỡng **giá** (0.02–0.0575), còn bước register là semitone (0.38–3.62).

Nếu hạ eps, Motion chỉ tăng vì các cặp `(ΔP nhỏ, Δpitch=0)` quay lại làm loãng
τ, không phải vì tín hiệu tốt lên:

| movement | eps 1× | 0.25× | 0× |
|---|---:|---:|---:|
| II | 0.000 | 0.070 | 0.133 |
| III | 0.000 | 0.092 | 0.156 |

Đề xuất: **giữ một eps chung, chấp nhận M = 0 cho minimalist II/III**, ghi vào
re-baseline. Nếu muốn M > 0 thì sửa **encoding register của writer** (để bước
register phản ánh biên độ giá), không hạ eps để được số đẹp. Đây là quyết định
§10.2.

## 6. Kế hoạch test

Thêm vào `backend/tests/test_dfi.py`:

| Test | Assert |
|---|---|
| `test_trace_snaps_to_the_intended_line` | note lệch octave + snap → `pitch == line[eighth]`, `sounding_pitch == midi` |
| `test_trace_keeps_the_longer_note_on_a_tie` | 2 note cùng `(bar,beat)`, cùng `|diff|` → giữ duration dài hơn |
| `test_fill_trace_merges_high_ties` | một nốt high tied dài → **1** trace point |
| `test_fill_trace_does_not_stack_overlapping_high_notes` | 2 high overlap → chỉ 1 point |
| `test_fill_uses_yield_spans` | high note ngoài `yield_spans` không vào trace |
| `test_fill_skips_high_ornament_outside_yield_spans` | flute ornament khi violin nghỉ nhưng ngoài span → không vào trace |
| `test_fill_without_yield_spans_adds_nothing` | `yield_spans=()` → trả đúng `base` |
| `test_fill_keeps_a_note_attacking_just_before_the_span` | note attack sát trước span: hành vi bỏ được pin; coverage mất ≤ 1 beat |
| `test_guitar_sets_sounding_pitch_on_remap` | guitar remap `pitch=intended` vẫn giữ `sounding_pitch` cũ |
| `test_sounding_pitch_keeps_the_flute_offset` | symphony `(sounding_pitch - pitch) % 12 ∈ {3,4,7}` (diagnostic-only, C-space; offset thô có thể −9/−17) |
| `test_motion_points_drops_frame_bars` | point trong `frame_bars` không vào Motion |
| `test_motion_deduplicates_base_and_fill` | base + fill cùng eighth → 1 point, giữ base |
| `test_motion_uses_anchors_for_guitar` | Motion guitar ≠ grid Motion trên cùng score |
| `test_motion_uses_grid_for_ambient` | ambient vẫn đọc grid |
| `test_motion_filters_below_the_window_eps` | cặp `|ΔP| < eps`, `Δpitch=0` bị bỏ |
| `test_motion_returns_zero_when_every_step_holds` | đủ cặp, mọi `y=0` → `0`, không `None` |
| `test_motion_null_renormalizes_the_rest` | window thiếu cặp → Motion `None`, `compute` chia lại trọng số (hành vi chấp nhận) |
| `test_symphony_trace_covers_a_flute_only_bar` | bar chỉ `high` kêu → có trace point |
| `test_same_trace_across_symphony_ensembles` | `classic/wood/brass` cho cùng tập bar/pitch (sai khác octave đã snap) |
| `test_schemas_version_matches_dfi_version` | `DfiBreakdown.version == DFI_VERSION` |

Cập nhật `test_non_guitar_ensembles_keep_the_same_chart_clarity`: siết dung sai
`<= 4` sau khi trace thống nhất theo vai trò (xem §10.4).

Chạy:

```bash
pytest backend/tests/test_dfi.py -q
pytest backend/tests -q
.venv/bin/python scripts/dfi_probe.py ACB 3M guitar torroba
```

## 7. Re-baseline (số đo sau implement)

`backend/scripts/dfi_probe.py`, `ACB / 3M`, humanize. "score v4" là số thực tế
sau implement (fill + snap); bảng "chưa fill" bên dưới là ước lượng lịch sử.

### Guitar torroba

| movement | v3 motion | anchors | anchors+eps | score v3 | score v4 |
|---|---:|---:|---:|---:|---:|
| I | 0.0148 | 0.439 | 0.455 | 30.9 | 39.2 |
| II | 0.1297 | 0.268 | 0.214 | 46.1 | 47.4 |
| III | 0.1275 | 0.475 | 0.479 | 39.7 | 46.2 |

### Symphony — chưa fill (ước lượng lịch sử)

Các số này chỉ để thấy Motion đổi thế nào khi chưa có fill; **không phải số v4**.
Số v4 thực tế ở bảng dưới.

| mv | v3 motion | anchors+eps | score v3 | score ước tính (chưa fill) |
|---|---|---:|---:|---:|
| I | 0.266 | 0.274 | 33.7 | 33.8 |
| II | 0.279 | 0.107 | 37.6 | 35.7 |
| III | 0.370 | 0.359 | 51.6 | 51.5 |

### Jazz — v4 actual

`snap_to_line` bỏ octave fold của alto/tenor, nên score cao hơn ước lượng
Motion-only; Motion giữ anchor+eps.

| mv | v3 motion | anchors+eps | score v3 | score v4 |
|---|---|---:|---:|---:|
| I | 0.343 | 0.351 | 66.8 | 68.2 |
| II | 0.205 | 0.138 | 57.4 | 57.4 |
| III | 0.438 | 0.437 | 61.7 | 63.9 |

### Symphony — fill + snap actual

Số thực tế sau implement (`dfi_probe.py`, `as_of` 2026-11-02); khớp target.

| movement | coverage v3 → v4 | Shape v3 → v4 | Motion v3 → v4 | score v3 → v4 |
|---|---:|---:|---:|---:|
| I | 0.484 → 1.000 | 0.875 → 0.829 | 0.266 → 0.371 | 33.7 → **69.4** |
| II | 0.525 → 0.964 | 0.963 → 0.982 | 0.279 → 0.132 | 37.6 → **69.0** |
| III | 0.680 → 1.000 | 0.991 → 0.921 | 0.370 → 0.435 | 51.6 → **67.6** |

Score tăng chủ yếu qua coverage (`33.7 / 0.484 ≈ 69.6`); Shape/Motion chỉ đổi
vài phần trăm và Motion mv II còn giảm. Band mv I đổi "Rất mờ" → "Vừa" (0.6
dưới "Rõ"). Ghi vào PR description để reviewer không tưởng lỗi.

### Snap attribution — fill/eps only vs v4

`snap_to_line` không chỉ đổi Motion; nó bỏ octave fold nên Shape/Resolution
cũng đổi. Số đo tách riêng (dựng lại trace bằng `sounding_pitch` cho cột
fill-only):

| variant | fill/eps only (I/II/III) | v4 actual (I/II/III) | snap |
|---|---|---|---:|
| symphony | 54.8 / 46.4 / 69.3 | 69.4 / 69.0 / 67.6 | **+14.6 / +22.6 / −1.7** |
| ambient | 22.6 / 20.0 / 18.8 | 29.8 / 29.9 / 27.2 | **+7.2 / +9.9 / +8.4** |
| jazz | 66.9 / 56.2 / 61.6 | 68.2 / 57.4 / 63.9 | +1.3 / +1.2 / +2.3 |

- Ambient mv I: S 0.581→0.896, T 0.735→0.906, M 0.000→0.005 — **toàn bộ** mức
  tăng là snap, không phải Motion.
- Symphony mv II: snap chiếm **72%** mức tăng.
- Symphony mv III **giảm −1.7** vì T 0.938→0.672 khi flute thôi bị hạ octave:
  intent không đồng nghĩa "tốt hơn". Ghi vào §8 risk.

### Band flip — 5 movement

| variant | mv | v3 | v4 | nhãn |
|---|---|---:|---:|---|
| guitar/torroba | III | 39.7 | 46.2 | Rất mờ → **Mờ** |
| symphony | I | 33.7 | 69.4 | Rất mờ → **Vừa** |
| symphony | II | 37.6 | 69.0 | Rất mờ → **Vừa** |
| symphony | III | 51.6 | 67.6 | Mờ → **Vừa** |
| minimalist | I | 51.7 | 57.0 | Mờ → **Vừa** |

**Case gốc `ACB/3M/guitar/torroba` mv I vẫn "Rất mờ"** (30.9 → 39.2, dưới 40).
Cải thiện người dùng thấy là **Motion 0.01 → 0.455** trong sheet, không phải
band. Band thresholds không đổi; QA đừng tưởng chưa fix.

### Ghi chú re-baseline

- Số đo ngày `as_of` **2026-11-02**; `plan_span` có thể fetch dữ liệu live khi
  cache lạnh, nên chạy lại có thể lệch. Probe in `as_of` ở đầu.
- `n_sounding` symphony sẽ nhảy 196/151/328 → **~438/358/492** (fill merge tie
  thêm 242/207/164 point), confidence thành `high` gần như mặc định. Ghi nhận,
  không chặn.
- `n_moves`/`opportunity` vẫn đo trên lưới; Motion đo trên anchor. Ghi rõ.
- **`snap_to_line` không chỉ đổi Motion.** Nó bỏ octave fold nên Shape/Resolution
  của ambient/jazz cũng tăng: ambient mv I 22.6 → **29.8**, jazz mv I 66.8 →
  **68.2**. Các bảng "Motion-only" trước đây đánh giá thấp hệ quả này; số v4
  thực tế ở §5/§7 là nguồn đúng.
- **M không còn so sánh chéo variant từ v4:** ambient giữ grid, 4 variant còn
  lại dùng anchor. Bảng xếp hạng genre ở index §5.3 phải đọc M là *tương đối*,
  không phải cùng một định nghĩa mẫu.
- `DFI_VERSION` bump làm sidecar cũ miss (`audio.py:422`,
  `services/dfi.py:113`, `sessions.py:238`, `spans.py:191`).
- `dfi_signatures.json` **chưa tồn tại** trong repo: endpoint trả `[]`, UI hiện
  `chuẩn —`. Phase 7 mới tạo artifact lần đầu; v4 không chặn và không tạo
  fixture tạm.

## 8. Rủi ro và cách chặn

| Rủi ro | Hậu quả | Cách chặn |
|---|---|---|
| `motion_points` không lọc frame | Motion lệch Shape/Resolution | Lọc `score.frame_bars`; test |
| Tie-break không có `diff` | Luôn giữ note đầu; mất duration | `diff_by_key` + test duration |
| Fill mỗi đoạn tie thành point | Attack giả, pitch ý định đổi giữa nốt | `trace_from_notes` merge tie; test 1 point |
| Fill chồng note high | Hai lần đọc cùng giá | Cập nhật `lookup` sau mỗi extra |
| Fill note bắt đầu trong overlap | Xấu nhất mất 1 beat đầu span | Chọn theo `yield_spans`; đo ACB: 0 mất coverage |
| `yield_spans` lệch sau frame | Fill sai bar | `apply_span_frame` giữ body (`movement_frame.py:117`); test same-trace |
| Motion anchor làm rơi cặp | Renormalize đẩy điểm lên | Chấp nhận renormalize; test pin hành vi |
| Minimalist M=0 | Tưởng là lỗi eps | Giữ eps; sửa writer nếu muốn >0; ghi re-baseline |
| Band flip do coverage | Reviewer tưởng lỗi; nhãn nhảy 2 bậc | Ghi rõ score tăng qua coverage; band thresholds không đổi |
| Snap mở rộng "ý định vs nghe" | Mất khả năng phát hiện harmony trôi | Giữ `sounding_pitch`; không đóng §9.1 |
| Snap không luôn cải thiện | Symphony mv III −1.7; tưởng regression | Ghi attribution; intent ≠ "tốt hơn" |
| `compute` chỉ đọc `pitch` | Ensemble test thành tautology | Contour test trên `sounding_pitch`; docstring |
| Probe phụ thuộc dữ liệu live | Bảng §7 không tái lập | In `as_of`; ghi ngày vào doc |
| Hard-code version lần hai | Schema lệch DFI | Import `DFI_VERSION` |
| Ensemble spread | Test `<=4` đỏ | Test same-trace; siết có chủ đích |

## 9. Checklist triển khai

- [x] `PriceTracePoint.sounding_pitch` (diagnostic-only).
- [x] `trace_from_notes`: `carrier`, `snap_to_line`, `diff_by_key`, duration tie.
- [x] `guitar.py`: set `sounding_pitch` khi remap `pitch=intended`.
- [x] `fill_trace_from_notes`: `yield_spans`, merge tie, cập nhật lookup; **không clip**.
- [x] `_motion` dùng `eps`; doc §4.5 thống nhất `<4 cặp`.
- [x] `motion_points`: lọc frame; dedupe.
- [x] `compute`: `MOTION_ON_ANCHORS.get(variant, True)` (ambient grid).
- [x] `render.py`: giữ `if not trace:`; khởi tạo `yield_spans`; symphony fill `high`.
- [x] `DFI_VERSION = "4"` + `schemas.py` import.
- [x] `motion_pairs` (additive, default 0) + test recap.
- [x] Test §6, gồm `sounding_pitch` **mod 12**.
- [x] Chạy `pytest backend/tests` (805 pass).
- [x] Chạy `scripts/dfi_probe.py` cho 5 variant × 3 movement, cập nhật §1.1/§5/§7.
- [x] Đo ensemble spread = **0.00** cho cả 4 variant → siết `<= 2`.
- [x] Cập nhật `docs/sonify-data-fidelity-index.md` (§4.2, §4.5, §5.3, §9.1, §9.2, §10).
- [x] Ghi band flip ("Rất mờ" → "Vừa") vào PR description.
- [x] Xác nhận `dfi_signatures.json` chưa tồn tại; Phase 7 tạo artifact (không chặn v4).
- [x] Kiểm tra URL gốc `ACB / 3M / guitar / torroba` (motion 0.455, score 39.2).

## 10. Quyết định đã chốt (2026-11-03)

1. **Ambient Motion — giữ grid.** Anchor thưởng cho hold dài (giá chạy qua nốt
   ngân), trái §4.5. Grid+eps giữ Motion ~0 (`0.005/0.049/0.010`); score v4
   tăng do `snap_to_line` bỏ octave fold (xem §5).
   Anchor chỉ xem lại nếu ambient writer bắt đầu mã hoá biến động trong nốt ngân.
2. **Minimalist II/III — chấp nhận `M = 0`.** τ từng window âm là tín hiệu thật
   của encoding register, không phải lỗi eps. Không hạ eps. Mở task riêng để sửa
   `_synth_arpeggio_part` nếu muốn register phản ánh biên độ giá.
3. **`dfi_signatures.json` — để Phase 7 tạo lần đầu.** Artifact chưa tồn tại;
   endpoint trả `[]`, UI hiện `chuẩn —`. Không tạo fixture tạm trong v4.
4. **Bằng chứng — thêm `motion_pairs`; đã đo spread = 0.00 → siết `<= 2`.**
   `motion_pairs` (additive, default 0) vào `DfiBreakdown`/`schemas.py` + test
   recap; `test_non_guitar_ensembles...` siết từ `<= 4` xuống `<= 2`.
5. **So sánh chéo variant — chấp nhận + ghi rõ.** Ambient grid, còn lại anchor;
   `S/T/R/C` vẫn so được, `M` là chẩn đoán tương đối. Chuẩn hoá (nếu cần) để
   Phase 7 với corpus + listening panel.
6. **`snap_to_line` cho symphony/jazz/ambient — đã chốt.** Trace đo **ý định**,
   `sounding_pitch` giữ cao độ thật. Hệ quả: ambient +7–10, jazz +1–2,
   symphony +14.6/+22.6 nhưng mv III **−1.7** (T giảm). Chấp nhận vì mục tiêu
   là đo dữ liệu nguồn, không phải "điểm cao hơn"; §1.2/§7 tách fill-only vs
   v4, và §8 ghi rủi ro "intent không đồng nghĩa tốt hơn".
