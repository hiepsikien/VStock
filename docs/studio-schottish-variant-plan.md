# Kế hoạch Track B: Studio preview variants (`source` / `aaba`)

Trạng thái: design, gần ready; chưa triển khai.
Phạm vi: `release/studio-v2.1`; preview/export-only.
Liên quan: `docs/studio-schottish-pattern-plan.md` (Track A — production).

---

## 1. Mục tiêu

Cho user chọn và đổi giữa hai preview arrangement của cùng passage:

```text
previewMode = "source" | "aaba"
```

- `source`: đúng passage rhythm/reference pitch hiện tại.
- `aaba`: bar-loop preview `[A,A,B,A]`, dùng bar nguồn; **không phải AABA âm nhạc**.
- Không đăng ký `SENTENCE_SPECS`, không đổi composer runtime.
- Có spec id/audio riêng; export giữ `previewMode`.

---

## 2. Naming

Không dùng `variant` trần. Dùng:

```text
previewMode: "source" | "aaba"
```

Các tầng khác vẫn tên riêng:

- `sentenceId` — SentenceSpec;
- `planId` — PlanVariant (future);
- `keyFigureId` — key figure (future).

---

## 3. `source`

- Là behavior hiện tại của `mode:"new"`.
- Nếu request cũ không gửi `previewMode`, server trả `source`.
- `mode:"existing"` **reject** `previewMode` (không silent ignore):
  - explicit check trong route;
  - trả `200 {ok:false, errors:[{path:"previewMode"}]}` như các validation Studio khác;
  - lý do: `existing` dùng template/SentenceSpec, không có passage loop.
- Spec/audio giữ nguyên passage; `rhythmTemplate:true`, `productionReady:false`.

---

## 4. `aaba` — bar loop preview

### 4.1. Usable bars và mapping

Selection là `barStart..barEnd` (1-based, whole bars).

```text
selection = [barStart, barEnd]
pickup = bar in summary.pickupBars      # metadata từ parser/import
usable = selection bỏ pickup
A = usable[0]           nếu usable không rỗng
B = usable[2]           nếu len(usable) >= 3
    else usable[1]      nếu len(usable) >= 2
    else A
tile = [A, A, B, A]
mapping = tile lặp, truncate đúng outputBars
```

**Không** detect pickup bằng “note đầu tiên ở beat > 0”. Một bar đầy đủ có thể mở bằng rest
rồi note ở beat 0.5 và sẽ bị nhận nhầm.

Nguồn pickup:

- thêm `pickup_bars: tuple[int, ...]` (0-based) vào `ImportedScore`;
- `_normalise_incomplete_edges` đánh dấu bar đầu khi shift 1/4 → 2/4;
- `ImportSummary.pickupBars` (1-based) cho client;
- fallback chỉ khi thiếu metadata: so độ dài thực của bar với meter length;
  **không** dùng onset heuristic.

Test bắt buộc: full bar có rest ở beat 0 rồi note ở beat 0.5 → **không** phải pickup.

Output length:

- **`outputBars = selectionBars`** (không tự kéo dài lên 4).
- Selection 4 bar → `[A,A,B,A]`.
- Selection 3 bar → `[A,A,B]`.
- Selection 2 bar → `[A,A]`.
- Selection 1 bar → `[A]`.
- Selection >4 bar → lặp tile, truncate đúng `selectionBars`.

Ví dụ có pickup:

```text
selection = [pickup, full1, full2]   # 3 bar
usable = [full1, full2]
A = full1
B = full2
mapping = [full1, full1, full2]
```

- Pickup **vẫn tính** vào `selectionBars`, nhưng không dùng làm A/B.
- Nếu user chỉ chọn pickup bar:
  - cho phép chạy;
  - `A = pickup`, `B = A`;
  - trả warning:
    ```text
    AABA preview uses a pickup bar; the loop may repeat the leading rest.
    ```

### 4.2. Warning khi < 4 bar

Với `outputBars = selectionBars`:

```text
AABA bar loop needs at least 4 bars for [A,A,B,A]; this preview is truncated.
```

- Không chặn request.
- Response có `warnings[]`; UI hiển thị cạnh label.

### 4.3. `loop_texture_bars(spec, mapping)`

Cần helper mới:

```python
loop_texture_bars(
    spec: TextureSpec,
    mapping: Sequence[int],
    *,
    output_bars: int,
    meter: MeterSpec,
    preview_mode: str,
) -> TextureSpec
```

- `meter` là `MeterSpec` (không phải `form.Meter`), lấy từ `spec.meter_variants[0].meter`.
- Nếu `len(spec.meter_variants) != 1`, reject/warning thay vì chọn mù; hoặc caller truyền
  `bar_quarters: float` tương đương `eighths_per_bar / 2`.
- Không dùng `ctx.epb`/`active_meter()` vì helper là pure transform trên `TextureSpec`.

Yêu cầu:

- remap `authored.events[].bar` theo mapping;
- giữ `beat`, `duration_beats`, `voice`, `pitch`, `tie`, `slur`, `accent`, `staff`, `string`, `fret`;
- cập nhật `id`, `source.bars`, `source.patternId`, `provenance` (`previewMode`);
- xử lý `micro_velocity` bar-relative nếu có;
- **bar length lấy từ `meter`**:
  - không suy đoán từ note;
  - nếu `spec.meter_variants` có nhiều hơn một variant, reject/warning thay vì chọn mù;
  - `beat`/`duration_beats` là đơn vị beat của meter đó.
- **clip note ở biên bar**:
  - nếu `beat + duration > meter bar length`, cắt duration;
  - note bị clip thì clear tie hai phía.
- **tie/slur pair-aware**:
  - build pair theo `(voice, staff, string, pitch)`;
  - chỉ giữ tie nếu note `stop` nằm ngay sau note `start` trong output và cùng bar boundary;
  - nếu pair không còn adjacent: clear **cả hai** phía; không để tie treo một đầu;
  - test cả trường hợp pair còn adjacent và pair bị tách.
- Validate lại bằng `check_texture_spec`.
- Không mutate spec gốc.

### 4.4. Audio

- Build synth notes từ events đã remap.
- Hash canonical `sha256:<hex>` gồm `previewMode` + notes; không dùng hash/audio của `source`.
- `ensure_audio` với `beats_per_bar` từ meter.
- `preview.notes` = số synth notes.
- `preview.renderHash` nếu có; UI optional.

### 4.5. Quota/cache

- Mỗi draft request tiêu 1 quota unit, kể cả switch `previewMode`.
- MVP: **mỗi Preview = 1 draft**, ghi rõ UI; không trả cả hai mode trong một request.
- Phase sau: cache theo `(selection, previewMode)` hoặc trả cả hai.

---

## 5. API

`POST /v1/studio/import/musicxml/{importId}/sentence-draft`

```json
{
  "mode": "new",
  "previewMode": "source" | "aaba",
  "barStart": 1, "beatStart": 0,
  "barEnd": 5, "beatEnd": 0,
  "newPattern": { "...": "..." }
}
```

- `barStart`/`barEnd`: 1-based.
- `beatStart`/`beatEnd`: **quarter-note offset 0-based** trong bar.
- Draft dùng whole bars; offset chỉ để UI đối chiếu.

Response:

```json
{
  "ok": true,
  "mode": "new",
  "previewMode": "aaba",
  "rhythmTemplate": true,
  "productionReady": false,
  "spec": { "...TextureSpec..." },
  "fixture": { "meter": "2/4", "bars": 5 },
  "preview": { "audioUrl": "...", "notes": 47 },
  "warnings": ["AABA bar loop needs at least 4 bars..."]
}
```

- `mode:"existing"` giữ contract cũ, **không** `previewMode`.
- Missing `previewMode` → `source`.
- Invalid `previewMode` → `200 {ok:false, errors:[{path:"previewMode"}]}`.
- `mode:"existing"` + `previewMode` → **cùng shape** `200 {ok:false, errors:[...]}`, không ignore.
  Chỉ lỗi transport/upload mới dùng 400/413/415.

---

## 6. UI

New pattern mode:

```text
Preview mode:
(•) Source rhythm
( ) AABA bar loop
```

- Label **AABA bar loop (preview)**, không gọi “AABA sentence”.
- Warning <4 bar hiển thị cạnh label.
- Đổi `previewMode`:
  - invalidate preview hiện tại;
  - không tự xoá `PatternDraft`;
  - `Add sentence` lưu `previewMode` vào sentence.
- `Preview sentence` dùng mode đang chọn.
- `Play sentence` phát audio mode đó.
- `Add sentence` lưu `previewMode` + spec/fixture/audio.
- Template picker vẫn ẩn.
- Existing mode không hiện control này.

---

## 7. PatternDraft/export

```json
{
  "previewMode": "aaba",
  "spec": { "...TextureSpec..." },
  "fixture": { "meter": "2/4", "bars": 5 }
}
```

- Export bundle giữ `previewMode`.
- Không trộn hai mode trong một sentence.
- Có thể có nhiều sentence source/aaba trong pattern draft để so sánh; duplicate id vẫn chặn.

### 7.1. Pattern draft completeness: figure pool + tags

**Đã chốt.** Track B tạo figure/key sentence như bình thường; pattern chỉ `complete` khi
figure pool có đủ **5 tag** (xem Track A §3.5):

```json
{
  "figures": [
    { "id": "fig_key", "bars": 4, "tags": ["key"], "previewMode": "aaba" },
    { "id": "fig_intro_2", "bars": 2, "tags": ["intro.short"] },
    { "id": "fig_intro_4", "bars": 4, "tags": ["intro.long"] },
    { "id": "fig_outro_2", "bars": 2, "tags": ["outro.short"] },
    { "id": "fig_outro_4", "bars": 4, "tags": ["outro.long"] }
  ]
}
```

- User gắn tag cho figure đã có; không tạo riêng intro/outro/key artifact.
- `PatternDraft.figures[]` là nguồn cell/tag; `sentences[]` giữ SentenceSpec, không auto-add figure.
- `figures[].cellId` map 1:1 `TEXTURE_CELLS`; Studio-generated mặc định `cellId = id`.
- Một figure có thể mang nhiều tag nếu bar count khớp.
- `previewMode` chỉ thuộc figure tag `key`; không áp dụng cho intro/outro.
- `aaba` không bao giờ trộn intro/outro vào loop.
- Track B **không tự sinh door** từ `_villa_pattern_door`; mặc định `complete:false`.
- UI ghi rõ: “Key-only preview; tag intro/outro before promote.”
- Export draft được phép khi thiếu; ghi `complete:false` + `missing[]`.
- Promote/publish bị chặn nếu thiếu bất kỳ tag nào hoặc key body không derivable.
- `key` tag đủ để auto-create body SentenceSpec khi promote; không bắt user tạo sentence thủ công.
- Draft cũ chỉ có `sentences` → `figures:[]`, `complete:false`.
- UI hiển thị `3/3 role`, `5/5 tag`; figure intro/outro preview `2 bars` / `4 bars`.

---

## 8. Files cần sửa

### Backend

- `backend/app/routers/studio_musicxml.py`
  - `SentenceDraftRequest`: `previewMode`.
  - route validate `existing` + `previewMode`.
  - `_rhythm_preview_payload` nhận `previewMode`.
  - `_rhythm_spec_id` seed thêm `previewMode`.
  - response `previewMode`, `warnings`.
  - import/score summary response thêm `pickupBars`; Pydantic response model cập nhật.
- `backend/app/studio/musicxml_sentence.py`
  - `prepare_draft`/`render_draft` cho `previewMode`.
- `backend/app/studio/musicxml_import.py`
  - `ImportedScore.pickup_bars` (0-based);
  - `ImportSummary.pickupBars` (1-based);
  - `_normalise_incomplete_edges` mark bar đầu.
- `backend/app/studio/texture_spec.py` (hoặc module mới)
  - `loop_texture_bars`, tie-pair helper; `meter: MeterSpec`.
- `backend/app/studio/villa_preview.py` nếu spec validation cần.
- Tests:
  - `tests/test_studio_musicxml_sentence.py`
  - `tests/test_studio_musicxml_api.py`
  - `tests/test_studio_villa_sentence.py`
  - `tests/test_studio_audio.py`

### Frontend

- `src/studio/sentenceDraft.ts`
  - `previewMode` type/normalizer;
  - `MusicXmlSentenceDraftRequest`;
  - `SentenceDraftResponse`;
  - `PatternDraftSentence`;
  - `PatternDraft.figures[].tags` (`key`, `intro.short/long`, `outro.short/long`);
  - `keyFigures` projection optional;
  - `sentenceDraftKey`;
  - `buildPatternDraftExport` (gồm `complete`/`missing`);
  - `sentenceDraftSourceLabel`.
- `src/studio/SentenceDraftPanel.tsx`
  - variant chips/switch;
  - invalidate preview;
  - warning label.
- `src/studio/musicxml.ts`
  - `MusicXmlImportSummary.pickupBars`;
  - normalize `pickupBars`/`pickup_bars` (snake_case/camelCase).
- `src/studio/api.ts` nếu request type dùng chung.
- `src/studio/studio.test.ts`
  - normalizer/request/label/export.

---

## 9. Tests

- `source` events khớp passage.
- `aaba` mapping đúng cho 1/2/3/4/5/6/7/8 bar; outputBars = selectionBars.
- Có pickup: 1/2/3/4 bar selection mapping đúng; pickup không thành A/B.
- `summary.pickupBars` từ parser; full bar có rest đầu bar **không** phải pickup.
- Client normalize `pickupBars`/`pickup_bars`.
- `spec.meter_variants > 1` → reject/warning rõ.
- Warning khi <4 bar; warning khi chỉ chọn pickup.
- Tie/slur/note không vượt bar; clip đúng.
- Tie pair còn adjacent được giữ; pair bị tách bị clear cả hai phía.
- Spec id/hash/audio khác `source`.
- `source` default khi thiếu field; `existing` + `previewMode` reject.
- Switching invalidates preview but keeps draft.
- Export round-trip `previewMode`.
- Quota one unit per request.
- Pattern draft `complete:false` khi thiếu tag; `missing[]` đúng.
- Old draft `{sentences}` → `figures:[]`, `complete:false`.
- `previewMode` chỉ thuộc key, không áp dụng intro/outro.

---

## 10. Giới hạn

- `aaba` là **bar loop preview**, không phải form/cadence.
- Không sản xuất `SENTENCE_SPECS`.
- Không đổi composer.
- Chưa có PlanVariant.

---

## 11. Future — PlanVariant / external plan

Chỉ làm sau Track A Phase 2, dùng chung schema với `sentence_plan.py`:

- `PlanVariant` = JSON `explicit` của Track A: `version`, `pattern`, `meter`, `phrases`, `sentenceByRole`;
- validate như Track A §3.2.4: startBar tăng, bars ≥1, role cuối close, B không cuối,
  sentence IDs tồn tại;
- `PlanPolicy`/`CompositePolicy` nhận plan ngoài, không mutate registry;
- precedence: explicit plan thắng auto policy; `SentenceSpec.select` chỉ dùng khi auto;
- một nguồn quota duy nhất;
- access/owner cho `/sentence/variants`;
- UI đánh dấu future, không MVP;
- preview/export trước, promote sau.

---

## 12. Quyết định đã chốt

1. **Output length = `selectionBars`.** Không tự kéo lên 4 bar.
2. **Pickup:** bỏ pickup khỏi `usable`; nếu chỉ có pickup thì cho phép + warning.
3. **MVP quota:** mỗi lần `Preview sentence` = 1 draft request/quota.
4. **UI label:** **“AABA bar loop”**.
5. **`existing` + `previewMode`:** reject, không ignore.
6. **`loop_texture_bars`:** nhận `meter: MeterSpec`, clip theo bar length, tie pair-aware.
7. **<4 bar:** warning, không chặn.
8. **Thiếu tag:** chỉ warning + `complete:false`; **không** tự lấy default `_villa_pattern_door`.
9. **Pickup:** lấy từ `ImportSummary.pickupBars`; không dùng onset heuristic.
10. **Error shape:** `existing + previewMode` và invalid `previewMode` đều `200 {ok:false}`.
11. **`pickupBars` propagation:** backend summary + `MusicXmlImportSummary` + client normalizer; test snake_case/camelCase.
12. **`PatternDraft.figures[]`:** nguồn cell/tag; `sentences[]` giữ SentenceSpec; `cellId` map 1:1 `TEXTURE_CELLS`.
