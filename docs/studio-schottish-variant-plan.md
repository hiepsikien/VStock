# Kế hoạch Track B: Studio preview variants (`source` / `aaba`)

Trạng thái: design, chưa triển khai.
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
- `mode:"existing"` không nhận `previewMode`; nếu gửi, reject hoặc ignore + warning, không silent apply.
- Spec/audio giữ nguyên passage; `rhythmTemplate:true`, `productionReady:false`.

---

## 4. `aaba` — bar loop preview

### 4.1. Mapping

Với selection `N` bar:

```text
A = bar đầu tiên (source index 0)
B = bar thứ ba (index 2), fallback index 1, rồi 0
tile = [A, A, B, A]
```

Output length:

- **`outputBars = selectionBars`** (không tự kéo dài lên 4).
- Selection 4 bar → `[A,A,B,A]`.
- Selection 3 bar → `[A,A,B]`.
- Selection 2 bar → `[A,A]` (B fallback nhưng truncate).
- Selection 1 bar → `[A]`.
- Selection >4 bar → lặp tile, truncate đúng `selectionBars`.

Lý do: UI/export/audio luôn khớp range user đã chọn.

### 4.2. Pickup 1/4

Parser đã normalize pickup 1/4 thành 2/4, note shift sang beat 2.

Rule:

- Nếu bar nguồn là pickup bar (note đầu tiên ở beat > 0 và bar có gap đầu), **không dùng làm A/B mặc định**; chọn bar kế tiếp.
- Nếu user cố chọn chỉ pickup bar, cho phép nhưng warning:
  ```text
  AABA preview uses a pickup bar; the loop may repeat the leading rest.
  ```
- `beatStart`/`beatEnd` trong API là **quarter-note offset 0-based**; bar là 1-based. Ghi rõ trong request docs/UI.

### 4.3. `loop_texture_bars(spec, mapping)`

Cần helper mới:

```python
loop_texture_bars(
    spec: TextureSpec,
    mapping: Sequence[int],
    *,
    output_bars: int,
    preview_mode: str,
) -> TextureSpec
```

Yêu cầu:

- remap `authored.events[].bar` theo mapping;
- giữ `beat`, `duration_beats`, `voice`, `pitch`, `tie`, `slur`, `accent`, `staff`, `string`, `fret`;
- cập nhật `id`, `source.bars`, `source.patternId`, `provenance` (`previewMode`);
- xử lý `micro_velocity` bar-relative nếu có;
- **clip note ở biên bar**:
  - nếu `beat + duration > bar_length`, cắt duration;
  - clear tie/slur không còn pair ở biên loop;
  - test no note/tie vượt bar.
- Validate lại bằng `check_texture_spec`.
- Không mutate spec gốc.

### 4.4. Audio

- Build synth notes từ events đã remap.
- Hash canonical `sha256:<hex>` gồm previewMode + notes; không dùng hash/audio của `source`.
- `ensure_audio` với `beats_per_bar` từ meter.
- `preview.notes` = số synth notes.
- `preview.renderHash` nếu có; UI optional.

### 4.5. Quota/cache

- Mỗi draft request tiêu 1 quota unit, kể cả switch variant.
- Có thể cache preview theo `(selection, previewMode)` để tránh đốt quota khi switch; quyết định:
  - MVP: chấp nhận mỗi lần Preview = 1 request/quota; UI ghi rõ.
  - Phase sau: cache cả hai variant trong một response hoặc cache theo key.

MVP: **mỗi Preview = 1 draft**, ghi rõ UI; không trả cả hai variant trong một request.

---

## 5. API

`POST /v1/studio/import/musicxml/{importId}/sentence-draft`

```json
{
  "mode": "new",
  "previewMode": "source" | "aaba",
  "barStart": 1, "beatStart": 1,
  "barEnd": 5, "beatEnd": 1,
  "newPattern": { "...": "..." }
}
```

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
  "preview": { "audioUrl": "...", "notes": 47 }
}
```

- `mode:"existing"` giữ contract cũ, không `previewMode`.
- Missing `previewMode` → `source`.
- Invalid `previewMode` → 200 `{ok:false, errors:[{path:"previewMode"}]}`.

---

## 6. UI

New pattern mode:

```text
Preview mode:
(•) Source rhythm
( ) AABA bar loop
```

- Label **AABA bar loop (preview)**, không gọi “AABA sentence”.
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

---

## 8. Tests

- `source` events khớp passage.
- `aaba` mapping đúng cho 1/2/3/4/5/6/7/8 bar; outputBars = selectionBars.
- Tie/slur/note không vượt bar; clip đúng.
- Pickup bar fallback/warning.
- Spec id/hash/audio khác `source`.
- `source` default khi thiếu field; existing mode reject/ignore previewMode.
- Switching invalidates preview but keeps draft.
- Export round-trip `previewMode`.
- Quota one unit per request.

---

## 9. Giới hạn

- `aaba` là **bar loop preview**, không phải form/cadence.
- Không sản xuất `SENTENCE_SPECS`.
- Không đổi composer.
- Chưa có PlanVariant.

---

## 10. Future — Section 13 PlanVariant

Chỉ làm sau Track A Phase 2:

- `PlanVariant` schema/version/round-trip;
- validate `sentenceByRole` IDs tồn tại;
- rule phrase count vs `phrases` entries;
- precedence `PlanVariant` vs `SentenceSpec.select`;
- một nguồn quota duy nhất;
- access/owner cho `/sentence/variants`;
- UI đánh dấu future, không MVP.

---

## 11. Quyết định đã chốt

1. **Output length = `selectionBars`.** Không tự kéo lên 4 bar; selection 3 bar → 3 bar.
2. **Pickup:** skip pickup bar khi chọn A/B mặc định; nếu user chỉ chọn pickup bar thì cho phép + warning.
3. **MVP quota:** mỗi lần `Preview sentence` = 1 draft request/quota; không cache cả hai variant trong một response.
4. **UI label:** **“AABA bar loop”**, không dùng “AABA key loop” hay “AABA sentence”.
