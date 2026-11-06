# Kế hoạch đơn giản: MusicXML → Sentence / Pattern

Trạng thái: đề xuất, chưa triển khai.
Phạm vi: Studio trên `v2`; `main` không đổi.

---

## 1. Mục tiêu

1. **Ẩn Gemini** khỏi Studio, nhưng giữ code để bật lại sau.
2. Từ một passage MusicXML, tạo được:
   - sentence mới cho **pattern đã có**;
   - **pattern mới** dùng renderer/figure family đã có.
3. Người dùng không phải sửa JSON ở luồng cơ bản.
4. Preview được trước khi lưu.
5. Studio draft **không tự** vào composer runtime; cần bước promote.

---

## 2. Mô hình tối giản

```text
Composer / Suite
  └─ Pattern            ví dụ: suite_mazurka, villa_pattern
       └─ SentenceSpec  ví dụ: suite_mazurka_arpeggio_aaba
            └─ Slot → Figure/Cell
```

- `Pattern` = họ texture + selector.
- `SentenceSpec` = một câu cụ thể trong pattern.
- `Figure/Cell` = renderer thật.
- “Lobos” là composer/suite grouping, **không phải** một SentenceSpec.

### Hai loại việc

| Việc | Dùng khi | Cần pattern mới? |
|---|---|---|
| **Add to existing pattern** | rhythm khớp figure hiện có | Không |
| **Create new pattern** | muốn một texture/pattern riêng | Có |

MVP chỉ hỗ trợ **pattern mới dùng renderer/figure family có sẵn**.
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
│    Selection: bar 2 · beat 1 → bar 5 · beat 2│
├──────────────────────────────────────────────┤
│ 3. Create sentence                           │
│    (•) Existing pattern                      │
│        Pattern [suite_mazurka ▼]             │
│        Template [auto / đổi ▼]               │
│    ( ) New pattern                           │
│        Name [villa_choro_mazurka]            │
│        Composer [Villa-Lobos ▼]              │
│        Family [Villa ▼]                      │
│        Meter 3/4 (auto)                      │
│        Figure [arpeggio ▼]                   │
│    [Preview]                                 │
├──────────────────────────────────────────────┤
│ 4. Result                                    │
│    Mini matrix + audio                       │
│    [Save draft]  [Export bundle]             │
│    Advanced ▸ JSON / full matrix             │
└──────────────────────────────────────────────┘
```

### Nguyên tắc UI

- Mặc định **không hiện JSON**; chỉ hiện trong `Advanced`.
- `Create sentence` là hành động chính sau khi chọn passage.
- Preview ngay trong panel, không chuyển trang.
- Sai/không khớp: hiện **một lý do rõ ràng**, không dump hàng loạt lỗi.
- Không auto-overwrite spec đang edit.
- Không auto-publish.

---

## 4. Backend: 1 endpoint draft + preview

```text
POST /v1/studio/import/musicxml/{importId}/sentence-draft
{
  "barStart": 2, "beatStart": 0,
  "barEnd": 5, "beatEnd": 2,

  "mode": "existing" | "new",

  "pattern": "suite_mazurka",        // existing
  "templateId": "suite_mazurka_arpeggio_aaba",

  "newPattern": {                    // new
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
  "mode": "new",
  "spec": { "...SentenceSpec..." : true },
  "fixture": { "length": 4, "n": 2, "closes": false, "rise": 1 },
  "preview": {
    "renderHash": "sha256:...",
    "audioUrl": "/v1/studio/sentence/audio/....wav",
    "notes": 24
  },
  "warnings": ["template tile 4 used; passage has 4 bars"],
  "productionReady": false
}
```

### Cách tạo draft

1. Passage → rhythm summary (bar/beat/role/rest).
2. Chọn **một** template gần nhất:
   - cùng meter;
   - cùng số bar/tile gần nhất;
   - density/onset/rest gần nhất.
3. Copy `select`/`span`/`slots` từ template, chỉnh `tile`/`bars`.
4. Với `mode:"new"`:
   - giữ nguyên figure/cell của renderer family;
   - đổi `pattern` sang pattern mới;
   - tạo `id` mới.
5. Preview bằng renderer family, không cần pattern đã đăng ký production.
6. Trả **một** draft, không trả top 3.

UI có dropdown `Template` để user đổi nếu draft đầu chưa đúng.

### New pattern preview

Cần thêm một seam nhỏ:

```text
preview_draft_sentence(spec, renderer="villa")
```

Nó dùng đúng figure/validator của family, nhưng cho phép `spec.pattern` là pattern draft chưa có trong `VILLA_PATTERNS`.
Không đăng ký pattern, không ghi global.

---

## 5. Pattern mới

### Pattern draft

```json
{
  "id": "villa_choro_mazurka",
  "label": "Choro-Mazurka",
  "composer": "Villa-Lobos",
  "renderer": "villa",
  "meter": "3/4",
  "sentence": { "...SentenceSpec..." : true }
}
```

MVP:
- một pattern = một sentence;
- dùng figure/cell của renderer family;
- không tạo figure mới;
- không auto-select trong composer.

### Promote

- `Export bundle` tải JSON pattern + sentence + fixture.
- Promote production bằng code/registry:
  - thêm `SentenceSpec` vào owner;
  - thêm pattern metadata + flag;
  - nếu muốn composer tự chọn: thêm selection rule.
- Chưa làm DB-backed texture registry trong MVP.

---

## 6. Gemini

- Flag `EXPO_PUBLIC_STUDIO_VISION` + `VSTOCK_STUDIO_VISION`, default off.
- Ẩn hai card ảnh và không gọi API vision.
- Giữ `studio_vision`, `vision.py`, Gemini client, tests backend.
- Bật lại bằng flag khi cần.

---

## 7. Ví dụ 3 bản Villa-Lobos

| Bản nhạc | Meter | Pattern mới | Template |
|---|---|---|---|
| Choro-Mazurka | `3/4` | `villa_choro_mazurka` | `suite_mazurka_arpeggio_aaba` |
| Valse-Mazurka | `3/4` | `villa_valse_mazurka` | `suite_valsa_arpeggio_period` |
| Scottish-Mazurka | `4/4` | `villa_scottish_mazurka` | `suite_schottish_arpeggio_abab` |

Nếu Scottish thực tế là `1/4 → 2/4`:
- không dùng template `4/4` đó;
- cần figure/family `2/4` mới;
- UI báo “chưa hỗ trợ meter/figure này”, không tạo draft sai.

---

## 8. Không làm trong MVP

- Top 3 candidate / matcher phức tạp.
- Rhythm-template `TextureSpec` + interpreter generic.
- Tạo figure/algorithm mới từ UI.
- DB-backed texture registry.
- Auto-selection pattern trong composer.
- Owner scoping MusicXML (hardening sau).
- Pickup/implicit measure length thật.

---

## 9. Thứ tự làm

| Sprint | Việc | Kết quả |
|---|---|---|
| A | Ẩn Gemini sau flag | Studio sạch |
| B | Draft endpoint + new-pattern preview seam | 1 draft + preview |
| C | UI 4 bước | Người dùng tạo sentence/pattern không cần JSON |
| D | Export bundle + promote docs | Đưa vào composer có kiểm soát |

MVP dừng ở **A + B + C**.

---

## 10. Test

- Passage 3/4, 4/4 → draft preview được.
- New pattern preview bằng renderer family, không cần đăng ký.
- Không match template → lỗi rõ, không tạo spec rác.
- 2/4 không có figure → báo “chưa hỗ trợ”.
- Gemini flag off → không request vision.
- Draft không overwrite editor.
- Export bundle đúng spec/fixture.
- Composer vẫn byte-identical khi flag mới off.

---

## 11. Quyết định cần giữ

1. Một draft gợi ý, không top 3.
2. Pattern mới dùng renderer/figure family có sẵn.
3. JSON chỉ trong `Advanced`.
4. Studio draft không tự vào composer.
5. Gemini ẩn, không xoá.

---

## 12. Kết luận

Luồng đơn giản là:

```text
Upload XML
  → chọn passage
  → Create sentence
  → Existing pattern  hoặc  New pattern
  → Preview
  → Save draft / Export
```

Không cần matcher phức tạp, không cần interpreter mới, không cần JSON editor cho người dùng thường.
