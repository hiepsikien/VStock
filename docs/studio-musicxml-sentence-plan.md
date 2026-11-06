# Kế hoạch đơn giản: MusicXML → Sentence / Pattern

Trạng thái: đề xuất, chưa triển khai.
Phạm vi: Studio trên `v2`; `main` không đổi.

---

## 1. Mục tiêu

1. **Ẩn Gemini** khỏi Studio, nhưng giữ code để bật lại sau.
2. Từ passage MusicXML, tạo được:
   - sentence mới cho **pattern đã có**;
   - **pattern mới** dùng renderer/figure family đã có;
   - **nhiều sentence** trong cùng một pattern.
3. Giữ nguyên luồng MusicXML hiện có: upload, summary, matrix, zoom, playhead, play.
4. Người dùng không phải sửa JSON ở luồng cơ bản.
5. Preview trước khi lưu; Studio draft không tự vào composer runtime.

---

## 2. Mô hình tối giản

```text
Composer / Suite
  └─ Pattern                 ví dụ: suite_mazurka, villa_choro_mazurka
       ├─ SentenceSpec A     ví dụ: câu mở đầu
       ├─ SentenceSpec B     ví dụ: câu đáp
       └─ SentenceSpec C
            └─ Slot → Figure/Cell
```

- `Pattern` = họ texture + selector.
- `Pattern` có thể chứa **nhiều `SentenceSpec`**.
- `SentenceSpec` = một câu cụ thể.
- `Figure/Cell` = renderer thật.

“Lobos” là composer/suite grouping, không phải một SentenceSpec.

### Hai loại việc

| Việc | Dùng khi | Pattern mới? |
|---|---|---|
| **Add sentence to existing pattern** | pattern generic còn nhận thêm spec | Không |
| **Create new pattern** | muốn pattern riêng, dùng renderer/figure family có sẵn | Có |

MVP hỗ trợ **cả hai mode**, nhưng:

- `existing` **chỉ** dành cho pattern generic có registry tuple nhiều spec;
- **không** cho add sentence vào `suite_*`, vì `SuiteGate.specs` chỉ một spec và `ensure_registered` sẽ raise;
- `new` dùng renderer/figure family có sẵn, có thể chứa nhiều sentence.

Chưa hỗ trợ viết figure/algorithm mới từ Studio.

---

## 3. Luồng UI: 4 bước

```text
┌──────────────────────────────────────────────┐
│ 1. MusicXML                                  │
│    [Choose file]  [Upload]                   │
├──────────────────────────────────────────────┤
│ 2. Passage                                   │
│    Lead / Mid / Bass matrix                  │
│    kéo chọn beat · Play · zoom               │
│    bar 2 · beat 1 → bar 5 · beat 2           │
├──────────────────────────────────────────────┤
│ 3. Create / add sentence                     │
│    (•) Existing pattern                      │
│        Pattern [suite_mazurka ▼]             │
│        Template [auto ▼]                     │
│                                              │
│    ( ) New pattern                           │
│        Name [villa_choro_mazurka]            │
│        Composer [Villa-Lobos ▼]              │
│        Family [Villa ▼]                      │
│        Meter 3/4 (auto)                      │
│        Figure [arpeggio ▼]                   │
│                                              │
│    [Preview]                                 │
├──────────────────────────────────────────────┤
│ 4. Pattern draft                             │
│    villa_choro_mazurka · 3/4                 │
│    Sentences:                                │
│      A  bars 2–5   [Preview] [Remove]        │
│      B  bars 6–9   [Preview] [Remove]        │
│    [+ Add sentence from current passage]     │
│    [Export bundle]                           │
│    Advanced ▸ JSON                           │
└──────────────────────────────────────────────┘
```

### Nguyên tắc UI

- `Create sentence` là nút chính sau khi chọn passage.
- Nếu tạo pattern mới, sentence đầu tiên lấy từ passage hiện tại.
- Muốn thêm sentence: chọn passage khác → `Add sentence`.
- Không hiện JSON mặc định; chỉ trong `Advanced`.
- Warnings gom lại, không đổ hàng loạt.
- Preview từng sentence ngay tại chỗ.
- Không auto-overwrite spec đang edit.
- Không auto-publish.

---

## 4. Backend: draft theo passage, pattern draft ở client

Không cần DB pattern draft trong MVP.

### Điều kiện trước khi mở endpoint

- `sentence-draft` là render thật (spec, plan, WAV, hash) → không để endpoint mở.
- Bắt buộc `X-Studio-Session` → `owner_id`.
- Import/passage lưu owner; GET/passage kiểm tra owner.
- Áp quota hiện có:
  - draft tính vào `specsPerDay` (hoặc thêm `draftsPerDay`);
  - render dùng preview concurrency/semaphore hiện có;
  - vượt quota → `429`.
- `importId`/`passage` hết TTL → `404` có cấu trúc; UI mời upload lại.

### API

```text
POST /v1/studio/import/musicxml/{importId}/sentence-draft
{
  "barStart": 2, "beatStart": 0,
  "barEnd": 5, "beatEnd": 2,

  "mode": "existing" | "new",

  "pattern": "suite_mazurka",          // existing
  "templateId": "suite_mazurka_arpeggio_aaba",

  "newPattern": {                      // new
    "id": "villa_choro_mazurka",
    "label": "Choro-Mazurka",
    "composer": "Villa-Lobos",
    "renderer": "villa",
    "meter": "3/4",
    "templateId": "suite_mazurka_arpeggio_aaba"
  }
}
```

Response:

```json
{
  "ok": true,
  "spec": { "...SentenceSpec..." : true },
  "fixture": { "length": 4, "n": 0, "closes": false, "rise": 0 },
  "preview": {
    "renderHash": "sha256:...",
    "audioUrl": "/v1/studio/sentence/audio/....wav",
    "notes": 24
  },
  "warnings": ["template tile 4 used; passage has 4 bars"],
  "productionReady": false
}
```

- Mỗi passage trả **một** draft sentence.
- UI giữ `PatternDraft` trong state:
  ```ts
  {
    id, label, composer, renderer, meter,
    sentences: SentenceSpec[]
  }
  ```
- `Add sentence` gọi lại endpoint với passage mới; UI append.
- `Export bundle` dùng `POST /v1/studio/sentence/export` hiện có, gửi từng `{spec, fixture}`; không viết compiler mới.
- Không lưu pattern draft server-side ở MVP.

### Existing mode: chỉ pattern generic

Backend phải chặn trước khi validate/render:

```text
existing pattern ∈ generic registry tuple
existing pattern ∉ suite_*
```

- `suite_*` là gate một sentence; add sentence thứ hai sẽ không promote được.
- Trả lỗi có cấu trúc:
  ```json
  {"path": "pattern", "message": "suite_mazurka is a single-sentence suite gate; create a new pattern instead"}
  ```
- UI không hiển thị `suite_*` trong dropdown `Existing pattern`.
- Nếu user chọn `New pattern` với id trùng `suite_*`/pattern đã có → chặn.

### Cách tạo draft

1. Passage → rhythm summary (bar/beat/role/rest).
2. Chọn **một** template gần nhất:
   - cùng meter;
   - cùng số bar/tile gần nhất;
   - density/onset/rest gần nhất.
3. Copy `select`/`span`/`slots` từ template, chỉnh `tile`/`bars`.
4. `mode:"new"`:
   - giữ figure/cell của renderer family;
   - đổi `pattern` sang pattern mới;
   - tạo `id` mới.
5. Preview bằng renderer family.
6. UI có dropdown `Template` để đổi nếu draft đầu chưa đúng.

### New pattern preview: reuse hạ tầng có sẵn

Không viết renderer/compiler mới.

- `app/studio/villa_preview.py` đã:
  - validate figure qua `VILLA_FIGURES`;
  - plan qua sandbox `registry={(pattern, meter): (spec,)}`;
  - render bằng đúng bar writers;
  - không mutate `SENTENCE_SPECS`.
- `app/studio/preview.py` đã dùng `use_registry` sandbox cho Torroba/Sor.
- `POST /v1/studio/sentence/audio` và `POST /v1/studio/sentence/export` đã có.

Seam nhỏ nhất:

```text
validate_villa_spec(spec, allow_draft_pattern=True)
```

hoặc tham số `allowed_patterns` chỉ cho pattern draft.
Chỉ nới whitelist validate; plan/render/audio/export giữ nguyên.

### Fixture cho draft

Không suy `n`/`closes`/`rise` từ MusicXML.

- `n`: lấy từ `Select`/template; mặc định 0.
- `closes`: `false` cho passage mở.
- `rise`: `0`.
- Villa preview dùng `_VILLA_MATRIX`: lengths 1–8, n 0/1, closes false, rise 0.
- `length` = số bar passage, capped `MAX_PLAN_BARS`.
- `bars` render capped `MAX_RENDER_BARS`.
- Passage dài hơn cap → UI warning/error, không trả “preview ok” giả.

### Namespace id

- Draft pattern id không được trùng:
  - `PATTERN_META`/pattern registry;
  - `PILOT_PATTERNS`;
  - `suite_*`;
  - `villa_pattern`, `castillo`, `galop`...
- Draft sentence id dùng namespace riêng:
  - `musicxml_<importId>_<barStart>_<barEnd>_<hash>`;
  - kiểm tra trùng id đã publish trong SQLite.
- Trùng id → lỗi trước preview, không warning UI.

---

## 5. Pattern mới + nhiều sentence

### Pattern draft

```json
{
  "id": "villa_choro_mazurka",
  "label": "Choro-Mazurka",
  "composer": "Villa-Lobos",
  "renderer": "villa",
  "meter": "3/4",
  "sentences": [
    { "...SentenceSpec A..." : true },
    { "...SentenceSpec B..." : true }
  ]
}
```

MVP:
- pattern có thể có nhiều sentence;
- tất cả dùng figure/cell của renderer family;
- preview từng sentence;
- không auto-select trong composer.

### Promote

- `Export bundle` tải JSON pattern + sentences + fixtures.
- Promote production cần sửa code/registry:
  - generic registry `SENTENCE_SPECS[(pattern, meter)]` có thể chứa nhiều spec;
  - nhưng `SuiteGate.specs` hiện chỉ trả **một** spec;
  - `SuiteGate.ensure_registered()` **raise ValueError** nếu key đã có tuple khác `gate.specs`.

Vì vậy:

```python
# Đúng cho generic registry:
SENTENCE_SPECS[key] = (sentence_a, sentence_b)

# KHÔNG đủ cho suite_*:
# suite gate chỉ chấp nhận đúng gate.specs (một spec).
# Muốn thêm sentence thứ hai dưới suite_* phải sửa:
#   - SuiteGate.specs / gate data, hoặc
#   - loader/registration path riêng.
```

Promote suite_* là **thay đổi code**, không chỉ thêm vào dict runtime.

---

## 6. Gemini

### Backend

- `VSTOCK_STUDIO_VISION` default off.
- Off: **không mount** `studio_vision` router; mọi route vision trả `404` có cấu trúc.
- Không chỉ ẩn UI: nếu route vẫn sống, client có token vẫn đốt Gemini/quota.
- On: mount router như hiện tại.
- Giữ `studio_vision`, `vision.py`, Gemini client, tests.
- Vision tests phải set env trước khi tạo app/test client; thêm test flag-off → `404`, không gọi Gemini.

### Frontend

- `EXPO_PUBLIC_STUDIO_VISION` default off; ẩn hai card ảnh.
- Expo env được inline lúc build → bật lại cần **build mới**, không chỉ toggle runtime.

---

## 7. Ví dụ 3 bản Villa-Lobos

Dùng tên canonical của registry:

| Movement | Meter | Pattern mới | Template |
|---|---|---|---|
| **Mazurka-Choro** | `3/4` | `villa_mazurka_choro` | `suite_mazurka_arpeggio_aaba` |
| **Valsa-Choro** | `3/4` | `villa_valsa_choro` | `suite_valsa_arpeggio_period` |
| **Schottish-Choro** | `4/4` | `villa_schottish_choro` | `suite_schottish_arpeggio_abab` |

Nếu file Scottish thực tế là `1/4 → 2/4`:
- không dùng template `4/4`;
- cần figure/family `2/4` mới;
- UI báo “chưa hỗ trợ meter/figure này”, không tạo draft sai.

Tên file người dùng có thể là `choro-mazuka`, `valse-mazuka`, `scottish-mazuka`;
trong docs/registry luôn dùng tên movement canonical:
`Mazurka-Choro`, `Valsa-Choro`, `Schottish-Choro`.

> Footnote: “Schottish-Choro” là tên movement dùng trong registry/audit hiện tại.
> Cách viết nhạc học phổ biến là “Schottisch”; không tự đổi registry nếu chưa có
> migration tên.

---

## 8. JSON draft mẫu đầy đủ

```json
{
  "id": "suite_mazurka_musicxml_abc123",
  "pattern": "suite_mazurka",
  "meter": "3/4",
  "select": {
    "length_min": 4,
    "length_max": null,
    "n_parity": "any",
    "n_mod": null,
    "closes": null,
    "rise_min": 0
  },
  "span": {
    "tile": 4,
    "remainder": "same_figure",
    "truncate_to_length": true,
    "cycle": false,
    "exact": false
  },
  "slots": [
    { "start": 0, "bars": 1, "figure": 1, "cell": null, "anchor": "start" },
    { "start": 1, "bars": 1, "figure": 1, "cell": null, "anchor": "start" },
    { "start": 2, "bars": 1, "figure": 2, "cell": null, "anchor": "start" },
    { "start": 3, "bars": 1, "figure": 1, "cell": null, "anchor": "start" }
  ]
}
```

---

## 9. Không làm trong MVP

- Top 3 candidate / matcher phức tạp.
- Rhythm-template `TextureSpec` + interpreter generic.
- Tạo figure/algorithm mới từ UI.
- DB-backed texture/pattern registry.
- Auto-selection pattern trong composer.
- Pickup/implicit measure length thật.
- DB-backed runtime registry.

---

## 10. Thứ tự làm

| Sprint | Việc | Kết quả |
|---|---|---|
| A | Ẩn Gemini sau flag; gate router thật | Studio sạch, vision 404 |
| B | Draft endpoint + access/quota + reuse preview sandbox + whitelist seam | 1 draft + preview |
| C | UI 4 bước + multi-sentence pattern draft + export | Người dùng tạo pattern nhiều câu |
| D | Promote docs/code path | Đưa vào composer có kiểm soát |

MVP dừng ở **A + B + C**.

---

## 11. Test

- Passage 3/4, 4/4 → draft preview được.
- New pattern preview bằng renderer family, không cần đăng ký.
- Thêm nhiều sentence vào cùng pattern draft.
- Không match template → lỗi rõ, không tạo spec rác.
- 2/4 không có figure → báo “chưa hỗ trợ”.
- Gemini flag off → không request vision.
- Draft không overwrite editor.
- Export bundle đúng pattern + nhiều sentence + fixtures; parse lại và preview round-trip.
- Composer vẫn byte-identical khi flag mới off.
- `importId`/`passage` hết TTL → lỗi rõ.
- Hai request cùng import_id không hỏng store.
- Draft pattern id trùng pattern đã có → chặn trước validate.
- Existing mode với `suite_*` → lỗi UI/backend, không draft chết.
- Vision flag off → `POST /analyze` trả 404, không đốt Gemini.
- Vượt quota draft/preview → `429`.
- Passage dài hơn `MAX_RENDER_BARS`/`MAX_PLAN_BARS` → warning/error rõ.

---

## 12. Quyết định cần giữ

1. Một draft gợi ý, không top 3.
2. Pattern mới dùng renderer/figure family có sẵn.
3. Pattern có thể có nhiều sentence.
4. `existing` chỉ pattern generic; `suite_*` phải tạo pattern mới.
5. JSON chỉ trong `Advanced`.
6. Studio draft không tự vào composer.
7. Gemini ẩn nhưng backend phải gate thật, không chỉ ẩn UI.
8. Draft/preview phải qua access/quota/owner.

---

## 13. Kết luận

Luồng đơn giản:

```text
Upload XML
  → chọn passage
  → Create sentence
  → Existing pattern  hoặc  New pattern
  → Preview
  → Add sentence (nếu cần)
  → Export bundle
```

MusicXML upload/matrix/play giữ nguyên.
