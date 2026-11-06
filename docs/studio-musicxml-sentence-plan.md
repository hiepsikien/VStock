# Kế hoạch: MusicXML → Sentence, ẩn Gemini

Trạng thái: đề xuất, chưa triển khai.
Phạm vi: Studio trên `v2`; `main` không đổi.
Cập nhật gần nhất: sau `ccaa7bd` + hardening follow-up.

---

## 1. Mục tiêu

1. **Ẩn luồng Gemini/image scan** khỏi Studio, nhưng **không xoá code**.
   - Giữ `studio_vision`, `app/studio/vision.py`, Gemini client cho tương lai.
   - UI và router mặc định off; không có network call khi ẩn.
2. **Tạo Sentence mới từ MusicXML** theo cách đơn giản:
   - chọn passage;
   - nhận 1–3 draft `SentenceSpec`;
   - review diff;
   - load vào editor;
   - Validate → Preview → Publish.
3. **Hỗ trợ texture mới**:
   - texture mới dùng figure/pitch policy hiện có;
   - texture mới cần rhythm-template/algorithm mới;
   - không để Studio tự đưa texture chưa review vào composer.

## 2. Nguyên tắc

- MusicXML chỉ cung cấp **rhythm + voice role**, không cấp absolute pitch cho production.
- Pitch production lấy từ price action / chord progression.
- Không tự động ghi đè SentenceSpec đang edit.
- Không auto-publish draft.
- Flag mới mặc định off; flag off phải byte-identical.
- Không commit file nhạc có bản quyền; chỉ lưu derived rhythm + metadata.
- API MusicXML cần được scope theo `X-Studio-Session` trước khi coi là ổn định.

## 3. Hiện trạng

### Đã có

```text
MusicXML upload
  → summary + notes + per-measure meter
  → passage (bar/beat, Lead/Mid/Bass)
  → preview-only TextureSpec (literal MIDI)
  → WAV
```

- Parser deterministic, hỗ trợ chord/tie/slur/tuplet/grace warning.
- Per-measure meter; `1/4`, `2/4`, `3/4`, `4/4`, `6/8`.
- Passage beat range, clipping, rebase, BPM cho playhead.
- UI role-lane matrix, zoom, playhead, drag chọn beat.
- Full backend/frontend tests xanh.

### Chưa có

- Nút “tạo Sentence” từ passage.
- Matcher rhythm → figure/cell.
- TextureSpec rhythm-template cho production.
- Registry/promotion cho texture mới.
- Owner scoping cho MusicXML imports/passages.

---

## 4. Kiến trúc đích

```text
MusicXML upload
  → passage
  → rhythm signature
  → sentence draft
      ├─ texture có sẵn  → SentenceSpec (figure/cell hiện có)
      └─ texture mới     → rhythm-template TextureSpec
  → Validate → Preview → Publish
  → composer runtime
```

### Phân biệt “sentence mới” và “texture mới”

| Trường hợp | Dữ liệu cần | Code? |
|---|---|---|
| Pattern cũ + figure cũ | SentenceSpec mới | Không |
| Pattern mới + figure cũ | SentenceSpec + pattern registration/selection | Ít |
| Rhythm mới + pitch policy cũ | TextureSpec rhythm-template + interpreter | Backend vừa |
| Algorithm/instrument mới | Figure/materializer mới | Backend PR |

Một `SentenceSpec` đơn lẻ **không tạo ra texture mới**. Texture mới cần:
- pattern id;
- materializer/figure;
- selection policy;
- registry/flag.

---

## 5. Phase 1 — Ẩn Gemini

### UI

- Thêm flag `EXPO_PUBLIC_STUDIO_VISION` mặc định off.
- Khi off:
  - ẩn card `IMG · Score photo`;
  - ẩn card `IMG · Gemini draft`;
  - ẩn crop/upload/analyze state;
  - không gọi `/access`, `/uploads`, `/analyze`.
- Giữ code trong repo để bật lại sau.

### Backend

- `studio_vision` router mount sau `VSTOCK_STUDIO_VISION` default off.
- Khi off: route trả `404` hoặc không mount.
- Giữ `vision.py`, `gemini_companion`, tests backend.
- Không xoá Gemini client toàn cục vì `companion` còn dùng.

### Acceptance

- Studio không gửi request vision/Gemini khi flag off.
- UI chỉ còn MusicXML + Sentence editor + publish.
- Bật flag lại vẫn hoạt động như cũ.
- Test: flag off không có route; flag on route cũ pass.

---

## 6. Phase 2 — Passage → Sentence draft (MVP)

### 6.1 Rhythm signature

Module mới:

```text
backend/app/studio/musicxml_sentence.py
```

Input: passage đã chọn.

Output:

```json
{
  "meter": "3/4",
  "bars": 4,
  "lanes": {
    "lead": [
      {"bar": 0, "beat": 0, "duration": 2, "rest": false, "tie": "none"}
    ],
    "mid": [],
    "bass": []
  },
  "density": {"lead": 6, "mid": 2, "bass": 4},
  "onsets": [0, 1, 2, 3]
}
```

Không giữ absolute pitch; pitch chỉ dùng để phân role.

### 6.2 Matcher

So signature với 46 example hiện có:

- ưu tiên cùng meter;
- cùng số bar hoặc tile gần nhất;
- so density/onset/rest pattern;
- trả top 3 candidate.

Mỗi candidate là `SentenceSpec` hợp lệ, chỉ dùng figure/cell có trong registry.

Nếu không khớp:
- trả `noMatch` + lý do;
- không tạo spec rác;
- gợi ý “Create rhythm texture”.

Với `2/4` (Scotish):
- chỉ thử pattern `ANY_METER` (`sonatina`, `fandanguillo`, `galop`);
- nếu figure không hợp, báo cần figure/texture `2/4`.

### 6.3 API

```text
POST /v1/studio/import/musicxml/{importId}/sentence-draft
{
  "barStart": 2, "beatStart": 0,
  "barEnd": 5, "beatEnd": 2,
  "pattern": "castillo",             // optional
  "templateId": "castillo_34_walk"   // optional
}
```

Response:

```json
{
  "ok": true,
  "passageId": "mxp_...",
  "candidates": [
    {
      "spec": {"...SentenceSpec...": true},
      "fixture": {"length": 4, "n": 2, "closes": false, "rise": 1},
      "pattern": "castillo",
      "meter": "3/4",
      "templateId": "castillo_34_walk",
      "confidence": 0.82,
      "warnings": ["bar 3 density differs"],
      "unmatchedBars": [3]
    }
  ],
  "noMatchReason": null
}
```

Không thêm endpoint publish riêng. UI load candidate rồi dùng:
- `POST /sentence/validate`
- `POST /sentence/preview`
- `POST /sentence/publish`

### 6.4 UI

Thay `Use passage` bằng **`Draft sentence`**:

1. Chọn passage.
2. `Draft sentence`.
3. Hiện 1–3 candidate:
   - pattern/meter;
   - template nguồn;
   - confidence;
   - rhythm diff;
   - warnings.
4. Chọn candidate.
5. `Open in editor`:
   - nếu editor dirty → confirm overwrite;
   - nếu không → load JSON.
6. `Validate → Preview → Publish`.

Không auto-overwrite, không auto-publish.

### Acceptance

- Valsa `3/4`: passage 4 bar → ít nhất 1 candidate preview được.
- Scotish `2/4`: có candidate hoặc thông báo rõ “chưa có figure 2/4”.
- Không có `literal_midi` trong production spec.
- Publish/rollback hiện có không đổi.

---

## 7. Phase 3 — Texture mới

### 7.1 Rhythm-template TextureSpec

Dùng `TextureSpec` + `PitchRef` hiện có, không tạo model mới.

Ví dụ event:

```json
{
  "bar": 0,
  "beat": 0,
  "duration_beats": 2,
  "voice": 1,
  "pitch": {"kind": "melody_eighth", "eighth": 0},
  "tie": "none",
  "review": "edited"
}
```

Mapping role:

| Role | Pitch policy |
|---|---|
| Lead | `melody_eighth` / `melody_at_beat` |
| Mid | `chord_degree` 2/3/4 |
| Bass | `chord_root` / `bass_root` |

Cần bổ sung:
- `melody_at_beat`: melody note theo onset, không chỉ eighth index;
- `bass_root`: root ở register bass.

### 7.2 Interpreter

Hiện `texture_interpreter` chỉ dispatch `chord_melody`. Cần:

- generic `render_rhythm_template_bar`;
- dispatch key `(pattern, meter signature, excerpt digest)`;
- `runtime: "interpreter"`;
- `materializer: "rhythm_template"`;
- `provenance.schema_version: "texture-spec-1"`.

Flag `VSTOCK_TEXTURE_INTERPRETER` default off. Off phải byte-identical.

### 7.3 Pattern mới

#### A. Manual/palette texture (MVP)

- Pattern mới chỉ xuất hiện khi user chọn.
- Không cần rule tự động.
- Vẫn cần pattern id, label/composer/meter, registry spec, flag.

#### B. Auto-selection trong composer

- Thêm rule vào `_select_body`/`_patterns`.
- Thêm flag.
- Matrix row + digest pin + full tests.
- Đây là “promote production”, không phải Studio tự làm.

### 7.4 API

```text
POST /v1/studio/import/musicxml/{importId}/texture-draft
{
  "barStart": 2, "beatStart": 0,
  "barEnd": 5, "beatEnd": 2,
  "pattern": "new_texture",
  "pitchPolicy": {
    "lead": "melody",
    "mid": "chord_degree",
    "bass": "bass_root"
  }
}
```

Response:

```json
{
  "ok": true,
  "textureSpec": {"...TextureSpec..." : true},
  "preview": {"renderHash": "...", "audioUrl": "..."},
  "warnings": [],
  "productionReady": false
}
```

### 7.5 UI “Create rhythm texture”

Khi không có candidate:

- `Create rhythm texture`;
- form:
  - texture id / pattern id;
  - meter từ passage;
  - role mapping;
  - pitch policy;
  - preview fixture;
- kết quả:
  - TextureSpec draft;
  - preview WAV;
  - validation;
  - `Save draft`.
- Trạng thái: **preview-only / not production**.
- Promote: manual palette trước, auto-selection sau.

### 7.6 Lưu trữ / promote

`texture_registry` hiện chỉ đọc JSON trong repo và không ghi repo từ server.

Đề xuất:

- Draft lưu DB `studio_texture_specs`.
- Preview dùng draft DB.
- Promote production:
  - **Option 1 (khuyến nghị):** export JSON + commit có review.
  - **Option 2:** DB-backed registry + flag + version gate + rollback.

MVP chọn Option 1.

### Acceptance

- Texture `2/4` mới preview được, không literal MIDI.
- Flag off byte-identical.
- Không tự vào composer nếu chưa promote.
- Có digest/preview cho texture mới.
- Spec production không chứa absolute MusicXML pitch.

---

## 8. Phase 4 — Hardening

1. **Owner scoping**
   - `X-Studio-Session` → owner.
   - Import/passage record lưu owner.
   - GET/passage kiểm tra owner.
   - Import id có thể hash thêm owner.
2. **Pickup/implicit measure**
   - Hiện dùng full meter length.
   - Tương lai: lưu `measure_lengths` thật.
3. **Tie/visual**
   - Spec/audio đã xử lý split note.
   - UI mới vẽ connector; hiện chỉ accessibility label.
4. **Warning hygiene**
   - Truncate extreme values trong warning.
   - Entity declaration bị từ chối.
5. **Docs**
   - Cập nhật contract, giới hạn pickup, quy tắc tie, owner.

---

## 9. Test plan

### Backend

- Rhythm signature: bar/beat/role/rest/tie.
- Matcher: cùng meter, khác bar, no-match, 2/4.
- Draft spec validate 100%.
- Không có `literal_midi` trong production draft.
- Publish/rollback không đổi.
- Interpreter rhythm-template:
  - flag off identical;
  - flag on deterministic digest.
- Mixed meter bị chặn.
- Entity/extreme values không 500.
- Owner isolation.

### Frontend

- Draft candidate cards.
- Dirty editor confirm.
- Không overwrite khi cancel.
- 2/4 no-match warning.
- New texture wizard preview + save draft.
- Không request vision khi flag off.

### Manual

- Valsa `3/4`: passage → draft → preview → publish.
- Scotish `2/4`: draft hoặc “cần texture 2/4”.
- New texture: rhythm-template → preview → save draft → promote flag.

---

## 10. Thứ tự thực hiện

| Sprint | Việc | Kết quả |
|---|---|---|
| A | Ẩn Gemini sau flag | Studio chỉ còn MusicXML |
| B | Rhythm signature + matcher + `sentence-draft` | Passage → Sentence draft |
| C | UI Draft sentence + load editor + preview/publish | Luồng tạo sentence hoàn chỉnh |
| D | Rhythm-template TextureSpec + generic interpreter | Texture mới preview được |
| E | Pattern registration/promote + docs | Texture mới dùng được ở palette |

MVP nên dừng ở **A + B + C**. Phase D/E sau khi có ít nhất một texture `2/4` thực tế.

---

## 11. Rủi ro / cần chốt

1. Matcher chỉ là gợi ý; luôn cần user xác nhận.
2. `2/4` hiện thiếu figure; có thể cần figure `2/4` trước Scotish.
3. Texture mới auto-selection cần code, không chỉ JSON.
4. Không lưu absolute pitch từ MusicXML vào production spec.
5. Bản quyền: không commit score; chỉ lưu derived rhythm + metadata, hoặc xoá upload sau TTL.
6. Gemini: ẩn bằng flag, không xoá code.
7. Owner scoping cần làm trước khi coi MusicXML API là ổn định.

---

## 12. Đề xuất bắt đầu

Làm ngay **Sprint A + B + C**:

1. Ẩn Gemini sau flag.
2. `sentence-draft` từ passage cho pattern/figure hiện có.
3. UI `Draft sentence` → chọn candidate → load editor → Validate/Preview/Publish.

Sau khi có kết quả thực tế với Valsa/Scotish, mới làm texture mới (Phase D/E).
