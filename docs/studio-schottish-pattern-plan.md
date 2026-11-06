# Kế hoạch Track A: production pattern + sentences cho composer

Trạng thái: revised sau review vòng 3; **design**, chưa triển khai.
Phạm vi: `release/studio-v2.1`; `main` không đổi.
Mục tiêu cuối: composer render được một bản Schottish-Choro nghe coherent, không chỉ một pattern flag-on.

Track B (Studio preview `source`/`aaba`) tách riêng tại
[`docs/studio-schottish-variant-plan.md`](studio-schottish-variant-plan.md).

---

## 0. Các điểm review đã chấp nhận

| Feedback | Xử lý trong plan |
|---|---|
| `2/4` chưa đi vào composer runtime | Không làm native 2/4 ở Phase 1; dùng 4/4 fold hiện có. Native 2/4 là Phase 3 |
| AABA 4 bar chỉ là ostinato | Phase 1 giữ **ABAB**, chỉ là foundation; phrase-level AABA là Phase 2 |
| `VILLA_CHORD_MELODY` lỗi 2/4 | Native 2/4: sửa `_chord_grid` + test no-overflow trước khi bật |
| Pattern id/title trùng | Không tạo `suite_schottish_2_4`; dùng `suite_schottish` + meter variant khi native |
| Thiếu wiring registry/doors/wave | Checklist đầy đủ §4, gồm meter-aware wave/frame |
| Studio preview/dispatch chưa nối | Phase 3 mở whitelist/family; Phase 4 authoring |
| Không có 70/30 | Không enforce trong MVP; policy 70% ±10%, semantics chốt ở Phase 5 |
| Schema `KeyFigureSpec` song song | Dùng `TextureSpec`/`PitchRef` hiện có; kind mới phải thêm validation |
| Form thật có intro/outro/pedal | Thêm **Phase 0**: audit + body/door merge design trước Phase 1 |
| `SuiteGate` dùng chung nhiều movement | Single-spec path byte-identical; multi-spec là opt-in |
| Cadence chỉ là “chọn spec” | Phase 2 thêm `VILLA_CADENCE = 5`; không dựa vào figure hiện có |
| Partial merge chưa chốt | Chốt cách A + `covered: frozenset[int]` |
| `p.apex` là `Run`, không phải int | Dùng `p.rise` |
| `plan_slots` thiếu `offset` | Thêm `offset` + test phrase > 0 |
| 4 phrase không bridge có thể mất B | B bắt buộc ở `len(body)//2`; rise chỉ nâng cấp |
| `keyFigures` scope quá rộng | Chỉ pattern mới/promote; pattern cũ grandfathered |
| Phase 3 chưa có FormSpec path | Chốt movement III (1M/3M), 1W toàn bộ; pickup không vào production |

---

## 1. Quyết định kiến trúc

### Phase 0 — framed-form audit + body/door merge design

Không đổi nhạc. Chỉ chứng minh và thiết kế:

- `SuiteGate.eligible()` hiện trả `not has_pedal_bars(ctx)`, nên **mọi** movement có frame
  (`week_spec`/`month_specs`/`attach_frame`) đều fallback;
- test hiện tại còn assert fallback:
  `test_suite_production_movements.py::test_on_falls_back_with_a_pedal_frame`;
- `bar_plan()` chỉ nhận plan cover **mọi** bar;
- sentence chỉ render body, door/pedal phải render ngoài body.

Output Phase 0: thiết kế partial `SentenceVoices`, merge body/door, và test form thật.
**Chưa tuyên bố pattern chạy composer.**

### Phase 1 — production foundation (4/4 fold)

Dùng pattern hiện có:

```text
suite_schottish
meter 4/4 (fold from 2/4)
```

- Giữ **ABAB** hiện có; không đổi sang AABA trong Phase 1.
- Nối đầy đủ wiring §4.
- Flag `VSTOCK_SUITE_SCHOTTISH` default off.
- Điều kiện xong: flag off byte-identical; flag on deterministic; composer form thật
  (có frame) chọn được pattern; body/door merge đúng; không fallback toàn movement vì pedal.
- **Không phải bản final.**

### Phase 2 — phrase-level form + cadence

- Chia movement theo phrase thật (`ctx.phrases`, fallback `ctx.sections`).
- Chọn A/B/close theo phrase; B ở bridge/trio hoặc phrase giữa; phrase cuối close/cadence.
- Không hardcode `n=0, closes=False, rise=0`.
- Cadence phải có artifact (xem §3.2), không chỉ dựa `select.closes`.
- Test 5/7/9/16/30 bar.

### Phase 3 — native 2/4

- `FormSpec`/`span` tạo được `ctx.kind == "2/4"` thật.
- Cùng pattern id `suite_schottish` + meter variant `2/4`.
- Sửa `_chord_grid` 2/4 + test no-overflow.
- Meter-aware wave/accent/frame.
- Studio whitelist/family nếu muốn authorable.

### Phase 4 — key figure tùy ý

- Dùng `TextureSpec`/`PitchRef` hiện có.
- Không tạo `KeyFigureSpec` song song.
- Kind mới (nếu thật cần) phải thêm validation/resolve/test ngay tại Phase 4.

### Phase 5 — quota mềm 70% ±10%

- Chỉ enforce sau khi chốt semantics (bar vs lead layer).
- MVP: log/plan, không enforce.

---

## 2. Hiện trạng đã kiểm tra

### 2.1. 2/4 runtime

- `METER_24` có trong `form.py`.
- Chỉ dùng ở Studio preview/audio/MusicXML; **không** có `FormSpec` production dùng `METER_24`.
- `span._guitar_meter()` chỉ map 3/4/6/8.
- `span.frame_bars_for()` không có key `(2, 4)`.

### 2.2. Sentence plan

- `SuiteGate._plan()` gọi `plan_slots(..., n=0, closes=False, rise=0)` một lần cho cả movement.
- `SuiteGate.specs` chỉ một spec; `ensure_registered()` raise nếu tuple khác.
- `sentence_production.bar_plan()` trả `None` nếu plan không cover đủ mọi bar.
- Vì vậy AABA 4 bar = ostinato lặp, không phải 4 câu.

### 2.3. Form thật có frame

- `sentence_production.has_pedal_bars(ctx)` đọc `ctx.kind_at` và `_PEDAL`.
- `SuiteGate.eligible()` từ chối toàn movement nếu có bất kỳ bar `_PEDAL`.
- `week_spec`/`month_specs`/`attach_frame` đều tạo pedal bar.
- Test hiện tại assert fallback cho cả 4 movement khi có pedal frame.

### 2.4. Figure B 2/4

- `guitar_villa._chord_grid()` cho meter khác 4/4/6/8 trả `[0,4]`, `[4,2]`.
- Với `ctx.epb=4`, offset 4 là downbeat bar sau → note tràn bar.
- Native 2/4 phải sửa `_chord_grid` và test no-overflow.

### 2.5. Registry/title

- `suite_schottish` đã có title `Schottish-Choro`; spec là `suite_schottish_arpeggio_abab`.
- Thêm `suite_schottish_2_4` cùng title sẽ fail title uniqueness.
- `PATTERN_META` counts/`PATTERN_NAMES`/generated TS/matrix phải cập nhật khi thêm row.

### 2.6. Studio

- `villa_preview.VILLA_PATTERNS` chỉ có `villa_pattern`, `chord_melody`, `etude1`, `etude11`.
- `dispatch.family_for("suite_schottish")` trả `None`.
- Studio preview/audio/export không nhận pattern suite nếu không mở family/whitelist.

### 2.7. Cadence

- `VILLA_FIGURES` chỉ có `VILLA_ARPEGGIO`, `VILLA_CHORD_MELODY`, `VILLA_ETUDE1`, `VILLA_ETUDE11`.
- Không có figure cadence.
- `SentenceSpec.select.closes` chỉ chọn spec, không tạo nhạc kết.

### 2.8. Wave/frame

- `guitar_wave.PROFILES` key `(ensemble, pattern)`; `profile_for()` không nhận meter.
- `test_guitar_wave._EXPECTED` cũng key theo `(ensemble, pattern)`.
- `span.frame_bars_for()` không có `(2, 4)`.

### 2.9. `PitchRef`

Kind hiện có:

```text
melody_eighth
chord_degree
chord_root
scale_step
literal_midi
```

Không có `melody_at_beat`/`bass_root`.

### 2.10. 70/30

Không tồn tại như thuật toán. `guitar_scale_passages` có 30% body budget cho scale passage,
không phải sentence.

### 2.11. Door hiện có

Pattern cũ đã có **3 role**: `intro`, `key` (body), `outro`. Trong đó intro/outro có
**2 script length**:

- `short`: 2 bar / 2 step;
- `long`: 4 bar / 4 step.

Code hiện tại:

- `guitar_frame.frame_roles(length)` chọn `steps=2` khi frame ≤2 bar, `steps=4` khi >2 bar;
- frame 1 bar dùng `_compressed` (nửa đầu intro, nửa sau cadence);
- frame 3 bar dùng long script co lại theo role `[0, 2, 3]`;
- `DOORS[(ensemble, pattern)]` nhận `(ctx, bar, role, steps, closing, index)`;
- Torroba/Bach/Sor/Barrios/Villa/Brouwer đều có cặp `_intro_short`/`_intro_long` và
  `_outro_short`/`_outro_long`.

Vì vậy yêu cầu “3 key figure” là **chuẩn hóa điều pattern cũ đã làm**, không phải schema mới
cho production. Nhưng Studio hiện chưa capture đủ 5 artifact này.

---

## 3. Phase chi tiết

### 3.0. Phase 0 — audit + body/door merge design

#### 3.0.1. Audit

- [ ] Tái hiện: `SuiteGate.eligible()` trả `False` khi `has_pedal_bars(ctx)`.
- [ ] Xác nhận `week_spec`/`month_specs`/`attach_frame` tạo pedal bars.
- [ ] Xác nhận `test_on_falls_back_with_a_pedal_frame[schottish|valsa|gavotta|choros1]`.
- [ ] Ghi lại digest/notes của form thật khi flag off.

#### 3.0.2. Partial `SentenceVoices`

**Đã chốt:** `covered: frozenset[int] | None`.

```python
@dataclass
class SentenceVoices:
    ...
    covered: frozenset[int] | None = None  # None = toàn movement
```

- `None` giữ nguyên hành vi cũ.
- Partial plan trả `covered` = bar body sentence chiếm.
- `frozenset` cho membership O(1), hỗ trợ body không liên tục, và merge/union đơn giản.
- Không dùng `range` vì chỉ biểu diễn được một đoạn liên tục; pickup/pedal chèn giữa sẽ phải đổi schema.

#### 3.0.3. Partial `bar_plan`

```python
def bar_plan(planned, bars, *, require_full=True):
    ...
```

- `require_full=True` giữ byte-identical path.
- `require_full=False` trả plan dù thiếu bar; caller merge với base/door.

#### 3.0.4. Merge body + door

**Đã chốt cách A** — render base toàn movement rồi thay bar body:

1. Render base bar-loop cho **toàn** movement (đã có door/pedal).
2. Render sentence voices cho body bars.
3. Trên `covered` bars, thay thế base events của cả 3 voice bằng sentence events.
4. Ngoài `covered`, giữ base/door/pedal.
5. `_finish_voices` chạy **một lần** trên merged voices:
   - `patterns[bar]` = sentence pattern trong `covered`, base pattern ngoài;
   - merge `figures`/`contours`/`slot_contours`;
   - `preludio_bass` chỉ do sentence own nếu toàn movement.
6. Test intro/outro + body: door notes còn nguyên; body không trùng note; không tràn bar.

Lý do chọn A:

- door/pedal do đúng path cũ tạo, không phải viết lại;
- `_finish_voices` thấy voices đầy đủ, ít rủi ro nhất;
- `covered=None` giữ byte-identical path;
- chấp nhận render thừa body bar để đổi lấy tính đúng đắn.

Cách B (chỉ render base ngoài body rồi ghép) để sau, chỉ khi perf thành vấn đề:
`_finish_voices`/`apply_scale_passages`/`_apply_campanella` đang giả định mạch liên tục,
nên B cần thêm test biên body/door.

#### 3.0.4b. Implementation shape

“Base” là **raw voices** của historical bar loop, **chưa** qua `_finish_voices`.
Cần tách `render_patterned_voices` thành:

```python
def _render_base_raw(ctx, patterns) -> tuple[list, list, list]:
    """Historical per-bar loop, stops before _finish_voices."""

base = _render_base_raw(ctx, patterns)
sentence = _gated_sentence(ctx)

if sentence is not None:
    sentence_voices = apply_default_contours(ctx, sentence, enabled=...)
    merged = merge_covered(base, sentence_voices, sentence.covered)
    merged_patterns = [
        sentence_pattern if bar in covered else patterns[bar]
        for bar in range(ctx.bars)
    ]
    return _finish_voices(ctx, merged_patterns, *merged, ...)

return _finish_voices(ctx, patterns, *base, ...)
```

Quy tắc:

- `_render_base_raw` không gọi `_finish_voices`; chỉ path cuối gọi một lần.
- Base raw đã có door/pedal và figure defaults của base.
- `apply_default_contours` chỉ chạy cho sentence body trước merge.
- `patterns[bar]` cho body = sentence pattern; door/pedal = base pattern.
- `preludio_bass`/campanella/scale passages chạy trên merged voices, một lần, sau merge.
- `covered=None` phải đi đúng path cũ: `base` rồi `_finish_voices`, byte-identical.
- Test extraction trước: flag off digest không đổi; sau đó mới bật partial.

Đây là refactor có rủi ro; Phase 0 phải làm extraction + byte-identical test trước khi thêm merge.

#### 3.0.5. `eligible` opt-in

- `SuiteGate` thêm `partial: bool = False`.
- `partial=False`: giữ `not has_pedal_bars(ctx)` byte-identical.
- `partial=True`: chỉ yêu cầu body bars đủ `min_bars`; door/pedal được phép.
- Không đổi hành vi 3 movement còn lại khi flag off.

#### 3.0.6. Phase 0 acceptance

- [ ] Form thật có frame chọn được `suite_schottish` khi flag on.
- [ ] Flag off digest byte-identical.
- [ ] Không fallback toàn movement chỉ vì pedal.
- [ ] Test cả 4 movement flag off/on.
- [ ] Chưa đổi nhạc Phase 1 (vẫn ABAB).

### 3.1. Phase 1 — production foundation (4/4 fold)

Phase 1 là **audit + bổ sung phần thiếu**, không phải build lại pattern.

Đã có sẵn:

- `_FAMILY`, `_PROFILE`, `PROFILES`, `_RETAINED_DOORS`;
- `_KINETIC_PATTERNS`, `_NARROW_ROWS`, `_PATTERN_TITLE`, `PATTERN_META`;
- flag `VSTOCK_SUITE_SCHOTTISH`, selection/render tests.

Việc còn lại:

1. Giữ `suite_schottish` hiện có; không tạo pattern id mới.
2. Giữ **ABAB** (`suite_schottish_arpeggio_abab`).
3. Chỉ thêm:
   - Phase 0 body/door partial merge;
   - test composer form thật có frame;
   - test flag off digest byte-identical;
   - bất kỳ wiring nào audit thấy còn thiếu (ghi rõ file/dòng).
4. Không duplicate `DOORS`/`PROFILES` row đã có.
5. Test:
   - flag off digest byte-identical;
   - flag on selection/render;
   - plan/slots;
   - no note overflow;
   - composer form thật chọn được pattern;
   - intro/outro + body merge.

Không tuyên bố Phase 1 là bản nhạc final.

### 3.2. Phase 2 — phrase-level form + cadence

#### 3.2.1. Chọn phrase

```text
body_phrases = [p for p in ctx.phrases if bar không thuộc _PEDAL]
n = index trong body_phrases
closes = p.closes (nếu có; fallback False)
rise = p.rise (property có sẵn; fallback 0)
```

- 0 phrase: fallback toàn movement.
- 1 phrase: A, thêm close ở nửa sau nếu đủ bar.
- 2 phrase: A + close.
- 3 phrase: A + B + close.
- 4 phrase: A + A + B + close (B = n2).
- 5 phrase: A + A + B + A + close (B = n2).
- ≥6 phrase: A + A + B + A ... + close; B = `len(body)//2`.

#### 3.2.2. Chọn spec

```text
if phrase cuối: close
elif phrase là bridge/trio: B
elif phrase đầu: A
elif body >= 3 và n == len(body)//2: B
elif rise >= MIN_RISE: B (biến thể mạnh hơn)
else: A
```

- `B` **luôn có** khi body ≥3; không phụ thuộc rise.
- `rise >= MIN_RISE` (3 semitone) chỉ nâng cấp A→B hoặc đổi contour, không dùng để bỏ B.
- `close` không bị thay bằng A/B dù quota thiếu.
- Phrase quá ngắn cho spec: dùng spec ngắn hơn hoặc fallback A; không cắt B/close.

#### 3.2.3. Cadence artifact

**Đã chốt:** thêm `VILLA_CADENCE = 5` trong `guitar_villa_figures.py` ở Phase 2.
Không dựa vào figure hiện có để “hy vọng” ra cadence.

Lý do: `SentenceSpec` chỉ chọn figure id, không viết note.
`VILLA_ARPEGGIO`/`VILLA_CHORD_MELODY` là writer tổng quát, không biết bar nào là bar kết,
nên không đảm bảo tonic/bass root.

Thiết kế `VILLA_CADENCE`:

```python
VILLA_CADENCE = 5

def _cadence_bar(ctx, bar, phrase):
    start = bar * ctx.epb
    chord = ctx.chord(bar)
    bass = _choose_bass(
        chord, 0, None, ctx.bass_low, ctx.bass_high, ctx.semitones
    )
    # Lead = chord root pitch class, nearest the previous melody note.
    lead = _nearest_chord_root(ctx, chord, start, ctx.treble_floor, ctx.treble_top)
    support = _choose_inner(
        chord, lead, bass, ctx.mid_low, ctx.mid_high, ctx.semitones,
        color=False, index=0,
    )
    # One attack at beat 0, sustained through the bar.
    low = [_eighth_event(0, ctx.epb, bass, ctx.epb, 3, _P)]
    mid = [] if support is None else [
        _eighth_event(0, ctx.epb, support, ctx.epb, 2, _P)
    ]
    high = [_eighth_event(0, ctx.epb, lead, ctx.epb, 1, _P)]
    return high, mid, low
```

- “Tonic” = **root pitch class của chord cuối** (`ctx.chord(bar).pitches[0]`), không phải
  key tonic toàn cục. Nếu chord cuối không phải I, đó là half cadence; test riêng và log warning.
- Lead chọn root pc gần `ctx.melody[start - 1]` nhất, trong treble range.
- Support dùng `_choose_inner`; bass dùng `_choose_bass`.
- 4/4: một attack beat 0, sustain `epb` (8 eighth = 4 beat).
- 2/4: một attack beat 0, sustain `epb` (4 eighth = 2 beat); **không** dùng `_chord_grid`.
- Không arpeggio, không re-attack giữa bar.
- Là adapter mới, không viết renderer mới; tái dùng `_choose_bass`/`_choose_inner`/`_eighth_event`.
- Thêm vào `VILLA_FIGURES` + `VILLA_FIGURE_NAMES`; `FIGURE_CONTOURS` để trống.
- `valid_figures` vẫn là `VILLA_FIGURES`.
- `SentenceSpec` close dùng figure 5 ở bar cuối.
- `select.closes=True` chỉ là điều kiện chọn spec, không phải nhạc kết.

Test:

- final bar có bass root beat 0, sustain hết bar;
- lead là chord root pc, không phải note lạc;
- không có arpeggio/re-attack giữa bar;
- bar trước/sau không bị đổi;
- 4/4 và 2/4 không tràn bar;
- chord cuối I → close; chord cuối V → half cadence + warning;
- `assert_playable`/voice order;
- Studio preview và production dùng cùng figure.

A2 variation (MVP):

- cùng figure, đổi contour/rhythm ở 1–2 slot;
- hoặc dùng `VILLA_CHORD_MELODY` cho A2 nếu A là arpeggio;
- phải có test A ≠ A2 nhưng cùng tonal center.

#### 3.2.4. Multi-spec gate

- Không đổi `SuiteGate` single-spec path.
- Thêm seam opt-in, ví dụ `PhraseGate`/`MultiSpecGate`, chỉ `suite_schottish` dùng.
- `plan_slots` nhận offset phrase và danh sách spec.
- Giữ `ensure_registered`/`unregister` đúng cho tuple.
- Test Valsa/Gavotta/Choros1 flag off/on byte-identical.

### 3.3. Phase 3 — native 2/4

#### 3.3.1. FormSpec path (chốt)

Meter được chọn ở `plan_week`/`plan_month`/`plan_quarter`, **không** đổi `_guitar_meter` toàn cục.

- Thêm helper:

```python
def _suite_meter_override(
    spec: FormSpec,
    *,
    ensemble: str,
    span: str,
    index: int,
) -> FormSpec:
    if ensemble != "villa" or not suite_schottish_enabled():
        return spec
    if span == "1W" and index == 0:
        return replace(spec, meter=METER_24)
    if span in ("1M", "3M") and index == 2:   # III = Schottish
        return replace(spec, meter=METER_24)
    return spec
```

- Gọi trong `plan_week` (1W) và `plan_month`/`plan_quarter` (1M/3M) **trước** `attach_frame`.
- `attach_frame` sau đó dùng `frame_bars_for(METER_24, span)`.
- Các movement khác giữ nguyên 4/4/3/4/6/8.
- `active_meter`/`compose_meter` đã generic; không cần path mới.
- `ctx.kind` sẽ là `"2/4"`; `SuiteGate`/registry dùng key `("suite_schottish","2/4")`.
- Pattern id giữ `suite_schottish`; thêm meter variant `2/4`, không tạo title thứ hai.
- 1W: cả movement 2/4; 1M/3M: chỉ movement III 2/4.

#### 3.3.2. Figure/wave/frame

1. Sửa `_chord_grid` 2/4:
   - ví dụ `[0,2] / [2,2]` hoặc `[0] / [epb]`;
   - test mọi figure 2/4 không có `beat/duration` vượt bar.
2. Meter-aware wave/accent:
   - `PROFILES` key thêm meter hoặc `profile_for(ensemble, pattern, meter)`;
   - `_EXPECTED` cập nhật;
   - accent strong beat 0/subbar 2, không copy `tresillo` 4/4.
3. Frame:
   - `frame_bars_for((2,4), span)` có giá trị;
   - test `1Y`/`1M`/`3M`.
4. Studio preview:
   - mở `VILLA_PATTERNS`/dispatch/export cho `suite_schottish` 2/4;
   - hoặc ghi rõ production-only, không authorable.

#### 3.3.3. Pickup 1/4

- Parser normalize 1/4 pickup thành 2/4, note shift beat 2; đây là metadata của **Studio import**.
- `FormSpec` production chỉ có một meter/movement, không có per-bar meter.
- Vì vậy native 2/4 production:
  - bắt đầu ở bar 1, **không** giữ pickup như bar riêng;
  - Studio promote phải drop pickup hoặc align passage bắt đầu sau pickup;
  - key figure "bar 2/3" = full bar thứ 2/3 sau pickup.
- Nếu cần pickup thật trong production, phải thiết kế `FormSpec` per-bar meter ở phase sau; không đưa vào Phase 3.

### 3.4. Phase 4 — key figure tùy ý

1. Chọn 1 bar passage **sau pickup**.
2. Trích rhythm/role.
3. Tạo `TextureSpec` chỉ với kind hiện có:
   - Lead: `melody_eighth` (offset nếu cần);
   - Mid: `chord_degree`;
   - Bass: `chord_root`;
   - fallback: `scale_step`/`literal_midi` chỉ khi có lý do và test.
4. Nếu cần `melody_at_beat`/`bass_root`: thêm kind + validation/resolve/test ngay tại Phase 4.
5. Renderer generic loop key figure; sentence slots override.
6. Promote qua registry/flag; preview/export trước.

### 3.5. Pattern door contract (Studio)

**Đã chốt:** mỗi pattern Studio phải có **3 role** và **5 artifact**:

| Role | Artifact | Bars | Dùng khi |
|---|---|---|---|
| Intro | `short` | 2 | frame ≤2 bar, `steps=2` |
| Intro | `long` | 4 | frame >2 bar, `steps=4` |
| Key | `key` | body | sentence/key figure |
| Outro | `short` | 2 | frame ≤2 bar, `steps=2` |
| Outro | `long` | 4 | frame >2 bar, `steps=4` |

- 3 role: `intro`, `key`, `outro`.
- `key` là **key figure đại diện cho body**, không thay danh sách sentence; pattern vẫn có thể chứa nhiều `SentenceSpec`.
- `short`/`long` là hai script của cùng role, không phải hai pattern.
- Frame 1 bar: `_compressed` dùng short script cho cả vào và kết.
- Frame 3 bar: long script co theo `frame_roles` → role 0, 2, 3.
- Frame 4 bar: đủ long script 0, 1, 2, 3.

#### Draft shape

```json
{
  "keyFigures": {
    "intro": {
      "short": { "bars": 2, "spec": { "...TextureSpec..." } },
      "long":  { "bars": 4, "spec": { "...TextureSpec..." } }
    },
    "key": { "bars": 4, "spec": { "...TextureSpec..." } },
    "outro": {
      "short": { "bars": 2, "spec": { "...TextureSpec..." } },
      "long":  { "bars": 4, "spec": { "...TextureSpec..." } }
    }
  }
}
```

#### Completeness gate

- `draft` được lưu/export để review dù thiếu; export ghi `complete:false` + `missing[]`.
- `promote`/registry chỉ chấp nhận khi:
  - đủ 5 artifact;
  - cùng `meter`/`ensemble`/pattern;
  - đúng bar count (2/4/2/4);
  - key ≥1 bar;
  - không tràn bar;
  - không có tie/slur bắc qua biên door → body hoặc body → door.
- UI hiển thị `3/3 role`, `5/5 artifact`; thiếu role nào đánh dấu role đó.

#### Studio UX

- Pattern draft có 3 section: **Intro**, **Key**, **Outro**.
- Intro/Outro có tab **2 bars** / **4 bars**; preview riêng từng tab.
- `Add sentence` chỉ điền **Key**; door có `Add intro` / `Add outro`.
- `source`/`aaba` preview chỉ áp dụng cho **Key**, không áp dụng cho door.
- Door preview không tự ghép vào body; muốn nghe seam thì có `Preview with doors`.

#### Production mapping

- Compile 4 door artifact thành một callable cho `DOORS[(ensemble, pattern)]`:

```python
def door(ctx, bar, role, *, steps, closing, index):
    if closing:
        specs = outro_short if steps == 2 else outro_long
    else:
        specs = intro_short if steps == 2 else intro_long
    return specs[role](ctx, bar)
```

- `frame_roles`/`_dispatch` giữ nguyên; không thêm selection path mới.
- `_RETAINED_DOORS` **đã có** `("villa", "suite_schottish") -> _villa_pattern_door`.
  Không thêm row trùng; chỉ override nếu muốn door riêng khác `_villa_pattern_door`.
- Nếu pattern chưa có door riêng: `_dispatch` tiếp tục fallback composer door.

#### Scope + storage

- `keyFigures` là metadata **Studio authoring + export**, không phải registry production mới.
- `key` là `TextureSpec` preview; production body vẫn là `SentenceSpec`/`source` key figure.
- Intro/outro `TextureSpec` compile thành callable trong `DOORS` khi promote.
- Lưu ở:
  - client `PatternDraft` (localStorage/state);
  - export JSON `keyFigures` + `complete`/`missing`;
  - payload promote (optional) — **không** thêm SQLite/schema production.
- Gate `complete` chỉ áp dụng cho:
  - pattern mới tạo trong Studio; hoặc
  - draft có `keyFigures` và user bấm promote.
- Candidate/pattern cũ **grandfathered**, không bị đánh `incomplete` chỉ vì chưa có `keyFigures`.
- Track B key-only draft: `complete:false`, UI ghi rõ “preview only; doors required before promote”.

#### Tests

- `frame_roles(1/2/3/4)` trả role đúng;
- short/long đúng bar count và không tràn;
- intro kết dẫn vào body; outro kết tonic;
- seam body/door không tie treo;
- `complete` gate chặn promote khi thiếu 1/5 artifact;
- export round-trip 5 artifact;
- 2/4 door không copy 4/4 accent.

---

## 4. Wiring checklist đầy đủ

Khi thêm pattern/meter variant:

### Production flags

- `production_flags.py`
  - env constant;
  - ContextVar override;
  - `SUITE_MOVEMENT_ENVS`;
  - `any_suite_movement_enabled()`;
  - `__all__`.

### Pattern/runtime

- `guitar_patterns.py`
  - `_FAMILY`;
  - `_PROFILE`;
  - `_finish_voices` ringing set;
  - `_contrast_pattern`;
  - `_PEDAL_DOOR_PROFILE`.
- `guitar_wave.py`
  - meter-aware `PROFILES`/`profile_for` (hoặc branch `ctx.kind`);
  - `_VILLA_SENTENCE_PATTERNS`;
  - `test_guitar_wave._EXPECTED`.
- `guitar_frame.py` / `span.py`
  - `frame_bars_for((2,4), span)`;
  - `_RETAINED_DOORS` hoặc door riêng theo meter.
- `guitar_scale_passages.py`
  - `_KINETIC_PATTERNS`;
  - `_LOUD_DOWN_PATTERNS`;
  - `_NARROW_ROWS`;
  - `_HOST`.
- `guitar_villa_figures.py`
  - `VILLA_CADENCE`/`VILLA_FIGURES`/`VILLA_FIGURE_NAMES` nếu Phase 2 thêm cadence.
- `program.py`
  - `_PATTERN_TITLE`.
- `pattern_registry.py`
  - `PATTERN_META`;
  - counts;
  - meter nếu row cần phân biệt.
- `humanize.py`
  - `_clamp_guitar` nếu velocity ceiling khác.
- generated TS
  - `patternRegistry.generated.ts` / `PATTERN_NAMES`.

### Studio

- `villa_preview.VILLA_PATTERNS`;
- `dispatch.family_for` / family override;
- `/sentence/preview`, `/sentence/audio`, `/sentence/export`;
- `PatternDraft.keyFigures` (`intro.short/long`, `key`, `outro.short/long`);
- completeness gate `3 role / 5 artifact` trước promote;
- door preview `2 bars` / `4 bars` + `Preview with doors`;
- examples/candidate JSON;
- `sentenceDraft` template picker nếu authorable.

### Tests

- `test_pattern_registry.py` counts + title uniqueness;
- `test_guitar_wave.py::_EXPECTED`;
- `test_suite_production_movements.py` (gồm pedal frame);
- `test_studio_suite_schottish.py`;
- texture selection/render matrices;
- stabilization gate digest off/on;
- composer end-to-end 4/4 (form thật có frame) và 2/4;
- note bounds/accent/velocity;
- long movement 5/7/9/16/30 bar;
- intro/outro + body merge.

---

## 5. Tiêu chí âm nhạc

Một pattern chỉ được coi là “xong” khi:

1. AABA là câu, không phải ostinato 4 bar.
2. B đặt đúng contrast (bridge/trio/apex), không cắt giữa phrase.
3. Có câu kết A/cadence thật.
4. Không có note tràn bar/voice.
5. Accent/velocity 2/4 đúng, không copy 4/4 tresillo.
6. Nghe thử 8/16/30 bar:
   - có breath;
   - có cao trào;
   - kết coherent.
7. Flag off byte-identical; flag on deterministic digest.
8. Studio preview/export và composer render cùng một nội dung.
9. Form thật có intro/outro/frame vẫn chọn được pattern.
10. Pattern Studio có đủ 3 role / 5 artifact: intro short+long, key, outro short+long.
11. Seam intro→key và key→outro không tie treo, không tràn bar.

---

## 6. Quota

**Chưa có thuật toán.** Policy:

```text
target = 70% body bars dùng sentence
tolerance = ±10%
key figure = phần còn lại (có thể chạy dưới sentence lead)
```

- MVP: **log/plan only, không enforce**.
- Target policy only; semantics (bar vs lead layer) TBD; chỉ enforce ở Phase 5.
- Không hy sinh close/cadence hoặc B để đủ quota.

---

## 7. Thứ tự thực hiện

| Phase | Việc | Output |
|---|---|---|
| 0 | Framed-form audit + body/door merge design | Chứng minh fallback; thiết kế partial merge |
| 1 | `suite_schottish` 4/4 ABAB wiring + merge | Pattern chạy composer form thật, flag off an toàn |
| 2 | Phrase-level A/B/close + cadence | Bản nhạc có form nghe được |
| 3 | Native 2/4 FormSpec + B figure fix + profile/frame | 2/4 thật, không fold |
| 4 | Key figure tùy ý từ passage | Pattern + sentences từ passage |
| 5 | Quota mềm 70% ±10% | Fill policy có kiểm soát cadence/B |

Không nhảy thẳng Phase 3 khi Phase 0/1/2 chưa xong.

---

## 8. Quyết định đã chốt

1. **Phase 0 bắt buộc.** Audit form thật + body/door merge trước Phase 1.
2. **Phase 1 = 4/4 fold, giữ ABAB.** Dùng `suite_schottish`; không tạo pattern id mới; không tuyên bố final.
3. **Phase 2 = phrase-level plan + cadence artifact.** Chọn A/B/close theo phrase; thêm `VILLA_CADENCE` ở Phase 2, không dựa vào figure hiện có.
4. **Phase 3 = native 2/4.** `FormSpec`/`span` + meter-aware wave/frame + `_chord_grid` fix + test composer thật.
5. **Quota = policy 70% ±10%, chưa enforce MVP.** Semantics chốt Phase 5.
6. **Preset trước, user-authorable sau.** Phase 1–2 preset; Phase 3–4 mở Studio.
7. **Key figure:** bar 2/3 sau pickup; ưu tiên rhythm fidelity; chỉ dùng `PitchRef` kind hiện có.
8. **Multi-spec opt-in.** `SuiteGate` single-spec path byte-identical cho 3 movement còn lại.
9. **Pattern Studio phải có 3 role / 5 artifact.** Intro short(2)+long(4), Key, Outro short(2)+long(4); thiếu thì không promote.
10. **Door dùng `frame_roles`/`DOORS` hiện có.** `suite_schottish` đã có row `_villa_pattern_door`; `short` = steps 2, `long` = steps 4.
11. **`keyFigures` là metadata Studio/export**, không phải registry production mới; gate chỉ áp cho pattern mới/promote.

---

## 9. Thuật toán phrase-level (chi tiết)

### 9.1. Input

```text
phrases = ctx.phrases (fallback ctx.sections)
body = phrases không chứa _PEDAL
bars_per_phrase = (p.end - p.start) / epb
n = index trong body
closes = p.closes nếu có, else False
rise = p.rise          # property có sẵn; p.apex là Run, không phải int
```

### 9.2. Role

```text
if not body: fallback toàn movement
elif n == len(body)-1: close
elif bridge/trio tại n: B
elif n == 0: A
else: A hoặc B theo bảng dưới
```

B **luôn tồn tại** khi body ≥3 phrase; `rise` chỉ chọn B mạnh/yếu, không phải điều kiện duy nhất:

| body phrases | role |
|---|---|
| 1 | close (hoặc A + close nếu đủ bar) |
| 2 | A, close |
| 3 | A, B, close |
| 4 | A, A, B, close |
| 5 | A, A, B, A, close |
| ≥6 | A, A, B, A, ..., close; B ở `len(body)//2` |

- Bridge/trio có metadata: B đặt đúng phrase đó.
- Không có bridge/trio: B mặc định ở `len(body)//2` (4 phrase → n2, 5 phrase → n2).
- `rise >= MIN_RISE` (3 semitone) chỉ **nâng cấp** một A thành B mạnh hơn hoặc đổi contour;
  không dùng để bỏ B bắt buộc.
- B không được ở phrase cuối.
- Close luôn ở phrase cuối.

### 9.3. Spec + offset

- `plan_sentence`/`plan_slots` cần thêm `offset: int = 0` (keyword) hoặc shift `PlannedSlot.bars`
  và `slot_start` sau khi plan.
- `offset` = phrase start bar; nếu không, phrase 2+ sẽ plan về bar 0 và đè phrase trước.
- `micro_velocity` giữ relative; chỉ `bars`/`slot_start` shift.
- Test phrase bắt đầu ở bar > 0, `bar_plan`/`slot_contours` đúng offset.
- Nếu không spec nào khớp: fallback A của phrase, không bỏ phrase.
- Nếu phrase cuối không đủ bar cho close: dùng close ngắn hơn; nếu vẫn không, cadence bar cuối
  dùng figure hiện có.

### 9.4. Multi-spec registry

- `SENTENCE_SPECS[(pattern, meter)]` giữ tuple đã đăng ký.
- `SuiteGate.specs` vẫn một spec cho movement cũ.
- `PhraseGate.specs` trả tuple + plan; chỉ pattern mới dùng.
- `ensure_registered`/`unregister` so sánh đúng tuple.

---

## 10. Quota semantics

Hai lựa chọn, chưa chốt:

1. **Bar độc quyền**: sentence chiếm bar; key figure không chạy cùng bar.
2. **Lead layer**: sentence chiếm lead; key figure accompaniment dưới.

Plan hiện nghiêng (2), nhưng quota theo bar sẽ vô nghĩa nếu key figure chạy dưới.
Phase 5 phải chọn một và test:

- đếm bar body;
- loại bar cadence/B;
- log target/actual;
- không enforce nếu vượt tolerance.

---

## 11. Preset production vs user-authorable

### Preset production

- Pattern + sentence trong code.
- User không tạo/sửa trong Studio.
- Chỉ chọn trong composer khi flag bật.
- Không cần mở `VILLA_PATTERNS`/dispatch.

### User-authorable

- Upload MusicXML → passage → draft.
- Preview/audio/export trong Studio.
- Promote lên production qua code/flag.
- Cần `VILLA_PATTERNS`/dispatch, 2/4 template/key figure, registry/promotion.

**Thứ tự:** Phase 1–2 preset; Phase 3–4 mở authorable.

---

## 12. Chốt cuối

1. Phase 0: **bắt buộc** — audit + body/door merge.
2. Phase 1: **4/4 fold ABAB** — foundation, không final.
3. Phase 2: **phrase-level + cadence artifact**.
4. Phase 3: **native 2/4**, meter-aware wave/frame.
5. Phase 4: key figure dùng `TextureSpec`/`PitchRef` hiện có.
6. Phase 5: quota 70% ±10% là **target policy only**; chưa enforce đến Phase 5, semantics TBD.
7. Pickup 1/4: không tính là bar 1; A/B/key figure lấy full bar sau pickup.
8. Multi-spec/partial path opt-in; 3 movement còn lại byte-identical.

---

## 13. Track B

Preview variants `source`/`aaba` nằm ở file riêng:

```text
docs/studio-schottish-variant-plan.md
```

Không trộn `previewMode` với production `SentenceSpec`/plan.

---

## 14. Production blockers (đã xác nhận)

1. `SuiteGate.eligible` reject toàn movement khi có pedal bar → Phase 0.
2. `bar_plan` đòi cover mọi bar → partial plan Phase 0.
3. `_gated_sentence`/`_render_sentence_tail` chỉ render toàn movement → body/door merge Phase 0.
4. Không có cadence figure → Phase 2 thêm `VILLA_CADENCE = 5`.
5. `PROFILES`/`profile_for`/`frame_bars_for` không meter-aware → Phase 3.
6. Quota bar vs lead layer chưa chốt → Phase 5.
7. `PitchRef` thiếu `melody_at_beat`/`bass_root` → Phase 4 chỉ dùng kind hiện có.
8. Pickup 1/4 chưa có rule production → Phase 3, thống nhất với Track B.
9. `SuiteGate` dùng chung 4 movement → multi-spec/partial opt-in, test byte-identical.
10. Studio chưa capture đủ door: mỗi pattern cần 3 role / 5 artifact (intro short+long, key, outro short+long) → Phase 3/4.
11. `_RETAINED_DOORS` đã có row `suite_schottish`; gap thật là Studio chưa capture door artifacts, không phải thiếu DOORS row.
12. `Phrase.apex` là `Run`; `rise` phải đọc `p.rise`.
13. `plan_slots`/`plan_sentence` chưa có `offset`; phrase 2+ sẽ plan về bar 0 nếu không sửa.
14. 4 phrase không bridge phải vẫn có B ở `len(body)//2`; rise không được làm mất B.
15. Phase 3 cần `_suite_meter_override` ở `plan_*`, không đổi `_guitar_meter` toàn cục.

---

## 15. Quyết định đã chốt trước Phase 0

1. **Partial merge = cách A**: render base toàn movement, thay base events trên `covered` bar.
2. **`SentenceVoices.covered = frozenset[int] | None`**, `None` = toàn movement.
3. **Close dùng `VILLA_CADENCE = 5`** ở Phase 2; không dựa vào figure hiện có.
4. **Pattern Studio = 3 role / 5 artifact**: intro short(2)+long(4), key, outro short(2)+long(4).
5. **Door map vào `DOORS` + `frame_roles` hiện có**; `short` = steps 2, `long` = steps 4, 1-bar compressed, 3-bar long co còn role 0/2/3.
