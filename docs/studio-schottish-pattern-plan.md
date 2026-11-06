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

---

## 3. Phase chi tiết

### 3.0. Phase 0 — audit + body/door merge design

#### 3.0.1. Audit

- [ ] Tái hiện: `SuiteGate.eligible()` trả `False` khi `has_pedal_bars(ctx)`.
- [ ] Xác nhận `week_spec`/`month_specs`/`attach_frame` tạo pedal bars.
- [ ] Xác nhận `test_on_falls_back_with_a_pedal_frame[schottish|valsa|gavotta|choros1]`.
- [ ] Ghi lại digest/notes của form thật khi flag off.

#### 3.0.2. Partial `SentenceVoices`

Đề xuất tối thiểu, giữ default tương thích:

```python
@dataclass
class SentenceVoices:
    ...
    covered: frozenset[int] | None = None  # None = toàn movement
```

- `None` giữ nguyên hành vi cũ.
- Partial plan trả `covered` = bar body sentence chiếm.

#### 3.0.3. Partial `bar_plan`

```python
def bar_plan(planned, bars, *, require_full=True):
    ...
```

- `require_full=True` giữ byte-identical path.
- `require_full=False` trả plan dù thiếu bar; caller merge với base/door.

#### 3.0.4. Merge body + door

Đề xuất:

1. Render base bar-loop cho **toàn** movement (đã có door/pedal).
2. Render sentence voices cho body bars.
3. Trên `covered` bars, thay thế base events của cả 3 voice bằng sentence events.
4. Ngoài `covered`, giữ base/door/pedal.
5. `_finish_voices` chạy **một lần** trên merged voices:
   - `patterns[bar]` = sentence pattern trong `covered`, base pattern ngoài;
   - merge `figures`/`contours`/`slot_contours`;
   - `preludio_bass` chỉ do sentence own nếu toàn movement.
6. Test intro/outro + body: door notes còn nguyên; body không trùng note; không tràn bar.

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

1. Giữ `suite_schottish` hiện có; không tạo pattern id mới.
2. Giữ **ABAB** (`suite_schottish_arpeggio_abab`).
3. Nối đầy đủ wiring §4, gồm body/door merge từ Phase 0.
4. Flag `VSTOCK_SUITE_SCHOTTISH` default off.
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
rise = p.apex - p.min (nếu có; fallback 0)
```

- 0 phrase: fallback toàn movement.
- 1 phrase: A, thêm close ở nửa sau nếu đủ bar.
- 2 phrase: A + close.
- 3 phrase: A + B + close.
- ≥4 phrase: A + (A/B xen kẽ) + B ở bridge/trio + close cuối.

#### 3.2.2. Chọn spec

```text
if phrase cuối: close
elif phrase là bridge/trio: B
elif phrase đầu: A
elif có ≥3 body phrase và phrase giữa: B hoặc A
else: A
```

- `B` fallback: phrase giữa; nếu không có, phrase thứ 2.
- `close` không bị thay bằng A/B dù quota thiếu.
- Phrase quá ngắn cho spec: dùng spec ngắn hơn hoặc fallback A; không cắt B/close.

#### 3.2.3. Cadence artifact

MVP chọn **một** hướng:

- **Close spec dùng figure hiện có**, không thêm figure mới:
  - final bar: bass `chord_root` ở beat 0;
  - lead kết ở tonic/scale step 0, duration dài;
  - support chord tone, không arpeggio chạy;
  - `select.closes=True` chỉ là điều kiện chọn, không phải nhạc kết.
- Nếu audition cho thấy không đủ kết: thêm `VILLA_CADENCE` figure ở Phase 2 follow-up,
  có test riêng. Không thêm cả hai trong một PR.

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

1. Thêm `FormSpec`/`span` path cho 2/4:
   - ít nhất một movement guitar tạo `METER_24`;
   - test composer thật, không chỉ `_render(..., METER_24, ...)`.
2. Dùng `suite_schottish` + meter variant `("suite_schottish","2/4")`.
3. Sửa `_chord_grid` 2/4:
   - ví dụ `[0,2] / [2,2]` hoặc `[0] / [epb]`;
   - test mọi figure 2/4 không có `beat/duration` vượt bar.
4. Meter-aware wave/accent:
   - `PROFILES` key thêm meter hoặc `profile_for(ensemble, pattern, meter)`;
   - `_EXPECTED` cập nhật;
   - accent strong beat 0/subbar 2, không copy `tresillo` 4/4.
5. Frame:
   - `frame_bars_for((2,4), span)` có giá trị;
   - test `1Y`/`1M`/`3M`.
6. Studio preview:
   - mở `VILLA_PATTERNS`/dispatch/export cho `suite_schottish` 2/4;
   - hoặc ghi rõ production-only, không authorable.
7. Pickup 1/4:
   - parser đã normalize thành 2/4, note shift beat 2;
   - pickup bar **không** tính là bar 1 nhạc;
   - key figure "bar 2/3" = full bar thứ 2/3 sau pickup;
   - form 2/4 có pickup bar riêng hoặc anacrusis rõ ràng.

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

---

## 6. Quota

**Chưa có thuật toán.** Policy:

```text
target = 70% body bars dùng sentence
tolerance = ±10%
key figure = phần còn lại (có thể chạy dưới sentence lead)
```

- MVP: **log/plan only, không enforce**.
- Phase 5: chốt semantics (bar độc quyền hay lead layer) rồi enforce.
- Không hy sinh close/cadence hoặc B để đủ quota.

---

## 7. Thứ tự thực hiện

| Phase | Việc | Output |
|---|---|---|
| 0 | Framed-form audit + body/door merge design | Chứng minh fallback; thiết kế partial merge |
| 1 | `suite_schottish` 4/4 ABAB wiring + merge | Pattern chạy composer form thật, flag off an toàn |
| 2 | Phrase-level A/B/close + cadence | Bản nhạc có form nghe được |
| 3 | Native 2/4 FormSpec + B figure fix + stereo/frame | 2/4 thật, không fold |
| 4 | Key figure tùy ý từ passage | Pattern + sentences từ passage |
| 5 | Quota mềm 70% ±10% | Fill policy có kiểm soát cadence/B |

Không nhảy thẳng Phase 3 khi Phase 0/1/2 chưa xong.

---

## 8. Quyết định đã chốt

1. **Phase 0 bắt buộc.** Audit form thật + body/door merge trước Phase 1.
2. **Phase 1 = 4/4 fold, giữ ABAB.** Dùng `suite_schottish`; không tạo pattern id mới; không tuyên bố final.
3. **Phase 2 = phrase-level plan + cadence artifact.** Chọn A/B/close theo phrase; close dùng figure hiện có trước, `VILLA_CADENCE` chỉ khi cần.
4. **Phase 3 = native 2/4.** `FormSpec`/`span` + meter-aware wave/frame + `_chord_grid` fix + test composer thật.
5. **Quota = policy 70% ±10%, chưa enforce MVP.** Semantics chốt Phase 5.
6. **Preset trước, user-authorable sau.** Phase 1–2 preset; Phase 3–4 mở Studio.
7. **Key figure:** bar 2/3 sau pickup; ưu tiên rhythm fidelity; chỉ dùng `PitchRef` kind hiện có.
8. **Multi-spec opt-in.** `SuiteGate` single-spec path byte-identical cho 3 movement còn lại.

---

## 9. Thuật toán phrase-level (chi tiết)

### 9.1. Input

```text
phrases = ctx.phrases (fallback ctx.sections)
body = phrases không chứa _PEDAL
bars_per_phrase = (p.end - p.start) / epb
n = index trong body
closes = p.closes nếu có, else False
rise = p.apex - p.min nếu có, else 0
```

### 9.2. Role

```text
if not body: fallback toàn movement
elif n == len(body)-1: close
elif bridge/trio tại n: B
elif n == 0: A
elif len(body) >= 3 and 0 < n < len(body)-1: B nếu rise cao, else A
else: A
```

- Bridge/trio detect từ `ctx.kind_at`/`ctx.sections`; nếu không có metadata, dùng phrase giữa.
- B không được ở phrase cuối.
- Close luôn ở phrase cuối.

### 9.3. Spec

- `plan_slots(pattern, meter, bars, offset, closes, rise)` với offset = phrase start bar.
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
6. Phase 5: quota 70% ±10%, enforce sau khi chốt semantics.
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
4. Không có cadence figure → Phase 2 close spec, `VILLA_CADENCE` fallback.
5. `PROFILES`/`profile_for`/`frame_bars_for` không meter-aware → Phase 3.
6. Quota bar vs lead layer chưa chốt → Phase 5.
7. `PitchRef` thiếu `melody_at_beat`/`bass_root` → Phase 4 chỉ dùng kind hiện có.
8. Pickup 1/4 chưa có rule production → Phase 3, thống nhất với Track B.
9. `SuiteGate` dùng chung 4 movement → multi-spec/partial opt-in, test byte-identical.

---

## 15. Câu cần chốt trước khi code Phase 0

1. Partial merge: thay thế base events trên `covered` bar (đề xuất) hay render sentence-only rồi chèn door?
2. `SentenceVoices.covered` là `frozenset[int]` (đề xuất) hay `range`?
3. Close spec dùng figure hiện có trước (đề xuất) hay thêm `VILLA_CADENCE` ngay?
