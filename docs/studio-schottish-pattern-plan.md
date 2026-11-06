# Kế hoạch revised: pattern + sentences mới cho composer

Trạng thái: revised sau review kỹ thuật, chưa triển khai.
Phạm vi: `release/studio-v2.1`; `main` không đổi.
Mục tiêu cuối: composer render được một bản Schottish-Choro nghe coherent, không chỉ một pattern flag-on.

---

## 0. Các điểm review đã chấp nhận

| Feedback | Xử lý trong plan |
|---|---|
| `2/4` chưa đi vào composer runtime | **Không** làm native 2/4 ở Phase 1; dùng 4/4 fold hiện có. Native 2/4 là phase riêng sau khi có FormSpec/span path |
| AABA 4 bar chỉ là ostinato | Phase 1 chỉ là foundation; Phase 2 làm phrase-level AABA/cadence |
| `VILLA_CHORD_MELODY` lỗi 2/4 | Nếu native 2/4: sửa `_chord_grid` + test no-overflow. Phase 1 fold 4/4 không dùng lỗi này |
| Pattern id/title trùng | Không tạo `suite_schottish_2_4` ngay; dùng `suite_schottish` + meter variant khi native |
| Thiếu wiring registry/doors/wave | Thêm checklist đầy đủ §4 |
| Studio preview/dispatch chưa nối | Thêm phase Studio preview/export + whitelist/family |
| Không có 70/30 | Xác nhận **không tồn tại**; chỉ làm nếu chốt rule âm nhạc |
| Schema `KeyFigureSpec` song song | Dùng `TextureSpec`/`PitchRef` hiện có, không tạo schema mới |

---

## 1. Quyết định kiến trúc

### Phase 1 — production foundation: 4/4 fold

Dùng pattern hiện có:

```text
suite_schottish
meter 4/4 (fold from 2/4)
```

Lý do:

- `METER_24` có trong `form.py` nhưng **chưa có FormSpec/span production path**.
- `span._guitar_meter()` chỉ đổi `3/4 ↔ 6/8`; không tạo `2/4`.
- Thêm native 2/4 lúc này sẽ là dead path: `SuiteGate.eligible(ctx.kind=="2/4")` không bao giờ đúng trong composer thật.

Phase 1 **không phải bản final**. Nó để:

- nối đúng pipeline production;
- có flag/digest/tests;
- nghe thử texture;
- tạo nền cho phrase-level AABA.

### Phase 2 — musical form

- AABA phải là **câu 16 bar** hoặc **phrase-level plan**, không phải tile 4 bar lặp.
- B đặt theo phrase/trio/apex, có câu kết A/cadence.
- Sentence selection theo `n`/`closes`/`rise`, không hardcode `n=0, closes=False, rise=0`.

### Phase 3 — native 2/4

Chỉ làm khi:

- `FormSpec`/`span` tạo được `ctx.kind == "2/4"` thật;
- dùng cùng pattern id `suite_schottish` + meter variant `2/4`;
- không tạo title thứ hai trùng tên.

### Phase 4 — key figure tùy ý

- Dùng `TextureSpec`/`PitchRef` hiện có.
- Không tạo `KeyFigureSpec` song song.
- 70/30 chỉ làm nếu chốt rule; hiện không có.

---

## 2. Hiện trạng đã kiểm tra

### 2.1. 2/4 runtime

- `METER_24` có trong `form.py`.
- Chỉ dùng ở Studio preview/audio/MusicXML; **không** có `FormSpec` production dùng `METER_24`.
- `span._guitar_meter()` chỉ map 3/4/6/8.
- Docs §4.4.1 đang chốt Schottish 2/4 fold 4/4.

### 2.2. Sentence plan

- `SuiteGate._plan()` gọi `plan_slots(..., n=0, closes=False, rise=0)` một lần cho cả movement.
- `SuiteGate.specs` chỉ một spec; `ensure_registered()` raise nếu tuple khác.
- Vì vậy AABA 4 bar = ostinato lặp, không phải 4 câu.

### 2.3. Figure B 2/4

- `guitar_villa._chord_grid()` cho meter khác 4/4/6/8 trả `[0,4]`, `[4,2]`.
- Với `ctx.epb=4`, offset 4 là downbeat bar sau → note tràn bar.
- Native 2/4 phải sửa `_chord_grid` và test no-overflow.

### 2.4. Registry/title

- `suite_schottish` đã có title `Schottish-Choro`.
- Thêm `suite_schottish_2_4` cùng title sẽ fail title uniqueness.
- `PATTERN_META` counts/`PATTERN_NAMES`/generated TS/matrix phải cập nhật.

### 2.5. Studio

- `villa_preview.VILLA_PATTERNS` chỉ có `villa_pattern`, `chord_melody`, `etude1`, `etude11`.
- `dispatch.family_for("suite_schottish")` trả `None`.
- Studio preview/audio/export không nhận pattern suite nếu không mở family/whitelist.

### 2.6. 70/30

Không tồn tại.

- `plan_sentence`/`plan_slots` chọn theo length/n/closes/rise và tile slots.
- `guitar_scale_passages` có 30% body budget cho scale passage, không phải sentence.
- 70/30 phải định nghĩa rõ: theo bar, beat hay voice.

---

## 3. Phase chi tiết

### Phase 1 — production foundation (4/4 fold)

1. Giữ `suite_schottish` hiện có; không tạo pattern id mới.
2. Sửa/tối thiểu sentence:
   - 4-bar tile ABAB hoặc AABA;
   - ghi rõ đây là texture foundation, không phải final AABA.
3. Nối đầy đủ wiring §4.
4. Flag:
   - `VSTOCK_SUITE_SCHOTTISH` đã có;
   - giữ default off.
5. Test:
   - flag off digest byte-identical;
   - flag on selection/render;
   - plan/slots;
   - no note overflow;
   - composer chọn được pattern trong form 4/4.

**Không tuyên bố Phase 1 là bản nhạc final.**

### Phase 2 — musical AABA

Chọn một trong hai:

#### 16-bar sentence (chỉ fallback khi movement đúng 16 bar)

```text
A1 4 bar  key figure
A2 4 bar  key figure variation
B  4 bar  contrast
A3 4 bar  close/cadence
tile = 16
```

- `SentenceSpec` tile 16.
- `select.length_min=16`.
- Movement 30 bar: 16 + 14 truncate; cần thêm spec 8/16 hoặc fallback cadence.

#### Phrase-level sentence plan (đã chọn)

- `SuiteGate` mở rộng `specs` thành tuple.
- `plan_slots` theo từng phrase:
  - chọn spec theo `n`, `closes`, `rise`;
  - B ở phrase bridge/trio;
  - phrase cuối dùng close/cadence spec.
- Không còn hardcode `n=0`.
- Cần test 5/7/9/16/30 bar.

Yêu cầu âm nhạc:

- câu kết A, không kết ở B;
- B có contrast nhưng không phá cadence;
- key figure lặp có biến đổi;
- không tràn bar/voice.

### Phase 3 — native 2/4

1. Thêm FormSpec/span path cho 2/4:
   - ít nhất một movement guitar tạo `METER_24`;
   - test composer thật, không chỉ `_render(..., METER_24, ...)`.
2. Dùng `suite_schottish` + meter variant `("suite_schottish","2/4")`.
3. Sửa `_chord_grid` 2/4:
   - ví dụ `[0,2] / [2,2]` hoặc `[0] / [epb]`;
   - test mọi figure 2/4 không có `beat/duration` vượt bar.
4. Wave/accent profile 2/4:
   - không copy `tresillo` 4/4;
   - audition strong beat 0/subbar 2.
5. Studio preview:
   - mở `VILLA_PATTERNS`/dispatch/export cho `suite_schottish` 2/4;
   - hoặc ghi rõ production-only, không authorable.
6. Cập nhật candidate 4/4 fold → 2/4 native hoặc đánh dấu legacy.

### Phase 4 — key figure tùy ý

1. Chọn 1 bar passage.
2. Trích rhythm per role.
3. Tạo `TextureSpec`:
   - `authored.events` dùng `PitchRef` hiện có;
   - Lead: `melody_eighth`/`melody_at_beat`;
   - Mid: `chord_degree`;
   - Bass: `chord_root`/`bass_root` (nếu cần thêm).
4. Renderer generic loop key figure; sentence slots override.
5. 70/30 nếu chốt:
   - định nghĩa theo bar/beat/voice;
   - test cadence và không phá phrase.
6. Promote qua registry/flag; preview/export trước.

---

## 4. Wiring checklist đầy đủ

Khi thêm pattern/meter variant:

### Production flags

- `production_flags.py`
  - env constant;
  - ContextVar override;
  - `SUITE_MOVEMENT_ENVS` nếu là suite movement;
  - `any_suite_movement_enabled()`;
  - `__all__`.

### Pattern/runtime

- `guitar_patterns.py`
  - `_FAMILY`;
  - `_PROFILE`;
  - `_finish_voices` ringing set;
  - `_contrast_pattern` nếu pattern có thể làm contrast;
  - `_PEDAL_DOOR_PROFILE` nếu door mới.
- `guitar_wave.py`
  - `PROFILES[("villa", pattern)]`;
  - `_VILLA_SENTENCE_PATTERNS`.
- `guitar_frame.py`
  - `_RETAINED_DOORS` hoặc door riêng.
- `guitar_scale_passages.py`
  - `_KINETIC_PATTERNS`;
  - `_LOUD_DOWN_PATTERNS`;
  - `_NARROW_ROWS`;
  - `_HOST`.
- `program.py`
  - `_PATTERN_TITLE`.
- `pattern_registry.py`
  - `PATTERN_META`;
  - counts.
- `humanize.py`
  - `_clamp_guitar` nếu velocity ceiling khác.
- generated TS
  - `patternRegistry.generated.ts` / `PATTERN_NAMES`.

### Studio

- `villa_preview.VILLA_PATTERNS`;
- `dispatch.family_for` / family override;
- `/sentence/preview`, `/sentence/audio`, `/sentence/export`;
- examples/candidate JSON;
- `sentenceDraft` template picker if authorable.

### Tests

- `test_pattern_registry.py` counts + title uniqueness;
- `test_guitar_wave.py::_EXPECTED`;
- `test_suite_production_movements.py`;
- `test_studio_suite_schottish.py`;
- texture selection/render matrices;
- stabilization gate digest off/on;
- composer end-to-end 2/4/4/4;
- note bounds/accent/velocity;
- long movement 30 bar and 5/7/9 bar.

---

## 5. Tiêu chí âm nhạc

Một pattern chỉ được coi là “xong” khi:

1. AABA là câu, không phải ostinato 4 bar.
2. B đặt đúng contrast (bridge/trio/apex), không cắt giữa phrase.
3. Có câu kết A/cadence.
4. Không có note tràn bar/voice.
5. Accent/velocity 2/4 đúng, không copy 4/4 tresillo.
6. Nghe thử 8/16/30 bar:
   - có breath;
   - có cao trào;
   - kết coherent.
7. Flag off byte-identical; flag on deterministic digest.
8. Studio preview/export và composer render cùng một nội dung.

---

## 6. 70/30

**Không có sẵn.** Nếu muốn:

- định nghĩa theo **bar** hay **beat/voice**;
- key figure là accompaniment hay lead;
- sentence 70% có được phép chiếm lead 100% không.

Quyết định: dùng **70% ±10%** làm quota mềm; chưa enforce trong MVP, nhưng plan/phrase selection phải giữ cadence và B. Không dùng 70/30 cứng.

---

## 7. Thứ tự thực hiện đề xuất

| Phase | Việc | Output |
|---|---|---|
| 1 | `suite_schottish` 4/4 fold wiring đầy đủ | Pattern chạy composer, flag off an toàn |
| 2 | Phrase-level AABA + cadence | Bản nhạc có form nghe được |
| 3 | Native 2/4 FormSpec + B figure fix + Studio | 2/4 thật, không fold |
| 4 | Key figure tùy ý từ passage | Pattern + sentences từ passage |
| 5 | 70/30 (nếu chốt) | Fill policy |

MVP không nên nhảy thẳng Phase 3 khi Phase 1/2 chưa có form/cadence.

---

## 8. Quyết định đã chốt

1. **Phase 1 = 4/4 fold.** Dùng `suite_schottish` hiện có làm production foundation; không tạo pattern id mới, không tuyên bố là bản final.
2. **Phase 2 = phrase-level plan.** Không dùng 16-bar sentence làm mặc định. Chia movement theo phrase; chọn A/B/close theo `n`/`closes`/`rise`; B ở bridge/trio; phrase cuối có cadence.
3. **Phase 3 = native 2/4.** Đây là bản final. Phải có `FormSpec`/`span.py` path tạo `ctx.kind == "2/4"` và test qua composer thật. Sửa `_chord_grid` 2/4 + test no-overflow trước khi bật.
4. **Quota mềm 70% ±10%.** Không cần đúng 70/30; quota theo bar body, ưu tiên close/cadence và B; key figure lấp phần còn lại và có thể chạy dưới sentence lead.
5. **Preset trước, user-authorable sau.** Phase 1–2 là preset production; Phase 3–4 mở Studio authoring + promote. Không trộn hai mục tiêu trong một PR.
6. **Key figure:** chọn bar 2 hoặc 3 của Scottish; ưu tiên rhythm fidelity. Dùng `TextureSpec`/`PitchRef` hiện có, không tạo schema `KeyFigureSpec` song song.

---

## 9. Làm rõ: 16-bar sentence vs phrase-level plan

### 16-bar sentence

```text
A1 4 bar  key figure
A2 4 bar  key figure variation
B  4 bar  contrast
A3 4 bar  close
tile = 16
```

Ưu điểm:

- dễ code, dễ test;
- đúng AABA nếu movement đúng 16 bar;
- dùng `SentenceSpec` hiện có.

Nhược:

- movement 8/30 bar không khớp: 30 bar = 16 + 14, dễ cắt giữa B/A3;
- không theo phrase thật;
- B không đặt theo bridge/trio;
- cadence cuối không đảm bảo.

### Phrase-level plan (khuyến nghị)

- Chia movement theo `ctx.phrases`/`ctx.sections`.
- Mỗi phrase chọn một `SentenceSpec`:
  - phrase mở: A;
  - phrase giữa: A/B;
  - phrase có bridge/trio: B;
  - phrase cuối: close/cadence.
- Trong phrase dài, lặp A unit; B chỉ ở vị trí contrast.
- `n`, `closes`, `rise` được dùng thật, không hardcode.

Ưu điểm:

- 8/16/30 bar đều có form;
- không cắt giữa B;
- cadence cuối;
- nghe coherent hơn.

Nhược:

- cần mở rộng `SuiteGate`/sentence planner để chọn nhiều spec theo phrase;
- test nhiều hơn.

**Đề xuất: chọn phrase-level plan.** Nếu cần ship nhanh, làm 16-bar nhưng chỉ dùng cho movement đúng 16 bar; không dùng cho 30 bar.

---

## 10. Sentence quota (thay cho 70/30 cứng)

Không cần đúng 70/30. Đề xuất quota mềm:

```text
target = 70% body bars dùng sentence
tolerance = ±10%
key figure = phần bar còn lại
```

Quy tắc:

1. Ưu tiên câu kết/close; không hy sinh cadence để đủ quota.
2. B được đặt ở phrase contrast; không cắt B.
3. Nếu quota vượt tolerance:
   - giảm A lặp ở phrase giữa;
   - giữ key figure ở phrase mở/đoạn chuyển.
4. Key figure vẫn có thể chạy **dưới** sentence lead (accompaniment), không nhất thiết chiếm bar riêng.
5. Quota cấu hình:

```text
VSTOCK_SENTENCE_QUOTA=0.7
VSTOCK_SENTENCE_QUOTA_TOLERANCE=0.1
```

MVP: có thể chỉ log/plan quota, chưa cần ép; Phase sau mới enforce.

---

## 11. Preset production vs user-authorable

### Preset production

- Pattern + sentence nằm trong code.
- User không tạo/sửa trong Studio.
- Chỉ chọn được trong composer khi flag bật.
- Không cần mở `VILLA_PATTERNS`/dispatch.
- Nhanh, an toàn, nhưng không phải luồng MusicXML authoring.

### User-authorable trong Studio

- User upload MusicXML → passage → draft.
- Pattern/sentence preview/audio/export trong Studio.
- Promote lên production qua code/flag.
- Cần:
  - `VILLA_PATTERNS`/dispatch family;
  - 2/4 template/key figure;
  - registry/promotion.
- Đúng vision Studio, nhưng nhiều việc hơn.

**Đề xuất:**

- Phase 1–2: preset production để có bản nhạc chạy.
- Phase 3–4: mở user-authorable cho pattern/key figure mới.
- Không trộn hai mục tiêu trong cùng PR.

---

## 12. Chốt tạm

1. Phase 1: **4/4 fold** — đã đồng ý.
2. Phase 2: **phrase-level plan** — khuyến nghị.
3. Native 2/4: làm ở Phase 3, sau khi form/span path có test composer thật.
4. Quota: **70% ±10%**, mềm, không cắt cadence/B.
5. Preset trước; user-authorable sau.
6. Key figure Bước 4: chọn bar 2 hoặc 3 của Scottish; ưu tiên rhythm fidelity, dùng `TextureSpec` hiện có.
