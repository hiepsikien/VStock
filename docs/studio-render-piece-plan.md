# Kế hoạch: Studio Render Piece (figure → bản nhạc → WAV)

Trạng thái: **draft, chưa triển khai**.
Phạm vi: `release/studio-v2.1`.
Mục tiêu: sau khi user chọn/tag figure, có thể chọn plan, render full piece, nghe thử bằng **Play**, và export WAV/MusicXML — không auto-publish.

Liên quan:

- `docs/studio-schottish-pattern-plan.md` (production pattern)
- `docs/studio-schottish-variant-plan.md` (preview `source`/`aaba`)
- code hiện có: `sentence_plan.py`, `pattern_figures.py`, `pattern_doors.py`, `pattern_promote.py`, `texture_figure.py`

---

## 1. Vấn đề hiện tại

Đã có:

```text
MusicXML → figure → tags (key/intro/outro)
→ validate/promote
→ TEXTURE_CELLS + STUDIO_DOORS + body SentenceSpec
```

Nhưng **chưa có**:

```text
figure pool + plan + 1D series
→ render full piece
→ Play / Export WAV / Export MusicXML
```

`render()` hiện chọn pattern qua `_patterns()` / `selectable_pattern()`, nên pattern/figure mới không được chọn.

---

## 2. Nguyên tắc

1. **Tái sử dụng renderer hiện có**, không viết engine mới:
   - `render()` → `_compose()` → `guitar` → `render_patterned_voices()` → `_finish_voices()`.
2. **Tái sử dụng MusicXML/audio**:
   - `score_to_musicxml(score)`;
   - production audio pipeline (MuseScore/`sonify/audio.py`), không dùng synth preview 45s cho Render Piece.
3. **Không auto-publish**:
   - render/export/play là preview;
   - promote là hành động riêng.
4. **Plan là data**, không hardcode ABA/AABA trong UI.
5. **1D series là input**, không cố định symbol.
6. **Hard validator vẫn thắng**:
   - bar/voice/playability/cadence;
   - critic AI sau này chỉ xếp hạng, không thay validator.

---

## 3. Kiến trúc

```text
Studio draft
  figures[] + tags
  + planId (auto_aaba/trio/abab/...)
  + series (symbol/date hoặc bars[])
  + form (1W / 1M movement III)
        │
        ▼
RenderPieceRequest
        │
        ├─ validate figure pool (5 tag + optional B/close)
        ├─ build Plan (sentence_plan)
        ├─ load 1D series → bars
        ├─ build FormSpec (plan_week/month; 2/4 override)
        ├─ build StudioPiece arrangement
        │    intro.* + body roles + outro.*
        ▼
render(..., studio_piece=...)
        │
        ├─ Score
        ├─ MusicXML
        └─ WAV (production audio; không cap 45s)
```

---

## 4. API đề xuất

### 4.1. `POST /v1/studio/figure/render`

Request:

```json
{
  "pattern": "studio_schottish",
  "meter": "2/4",
  "figures": [
    {
      "id": "fig_key",
      "cellId": "texture_...",
      "bars": 4,
      "tags": ["key"],
      "spec": { "...TextureSpec..." }
    }
  ],
  "plan": {
    "id": "auto_aaba",
    "sentenceByRole": {
      "A": "fig_key",
      "B": "fig_b",
      "close": "fig_close"
    }
  },
  "series": {
    "kind": "symbol",
    "symbol": "VIC",
    "date": "2026-10-14"
  },
  "form": {
    "span": "1W"
  },
  "options": {
    "includeDoors": true,
    "audio": true
  }
}
```

`series` có thể là:

```json
{ "kind": "bars", "bars": [{ "close": 100.0, "volume": 250.0 }] }
```

Response:

```json
{
  "ok": true,
  "renderHash": "sha256:...",
  "audioUrl": "/v1/studio/sentence/audio/<key>.wav",
  "durationSec": 32.4,
  "musicxmlUrl": "/v1/studio/figure/render/<hash>.musicxml",
  "notes": 204,
  "meter": "2/4",
  "bars": 32,
  "plan": "auto_aaba",
  "warnings": []
}
```

Quy tắc:

- `audio:true` luôn dùng production audio pipeline, không phân biệt ngắn/dài, không cap 45s.
- Nếu production audio lỗi: trả MusicXML + lỗi audio rõ; không fallback sang synth preview.
- `includeDoors:false` → chỉ body.
- Không ghi `SENTENCE_SPECS`/registry.
- Cache theo `renderHash`.

### 4.2. Export

```text
GET /v1/studio/figure/render/{hash}.musicxml
GET /v1/studio/sentence/audio/{key}.wav   (tái sử dụng route hiện có)
```

Có thể thêm:

```text
POST /v1/studio/figure/render/export
→ { musicxml, wav }
```

nhưng MVP chỉ cần URL.

---

## 5. Plan options

Các plan user chọn trước khi export:

| id | role pattern | Ghi chú |
|---|---|---|
| `auto_aaba` | A A B close | mặc định |
| `trio` | A B A | B ở trio/bridge |
| `abab` | A B A B | close ở cuối nếu cần |
| `aab_close` | A A B close | |
| `through` | A ... A close | |
| `explicit` | roles từ JSON | future/advanced |

### 5.1. Vật liệu B và close

Hiện tại **chưa có tag `close`**. Cần phân biệt rõ:

| Tên | Là gì | Bars |
|---|---|---|
| `key` | figure body A | 1–4 |
| `contrast` | figure body B (optional) | 1–4 |
| `close` | figure body kết (optional) | 1–4 |
| `intro.short` | door intro 2 bar | 2 |
| `intro.long` | door intro 4 bar | 4 |
| `outro.short` | door outro 2 bar | 2 |
| `outro.long` | door outro 4 bar | 4 |

- `intro/outro` là **cửa** (frame door), có short/long.
- `close` là **câu kết trong body**, không phải door, nên **không có short/long**.
- `VILLA_CADENCE` là figure built-in dùng cho bar kết, không phải tag.

Quyết định MVP:

```text
tags bắt buộc: key, intro.short, intro.long, outro.short, outro.long
tags optional: contrast, close
```

- Plan có B (`aaba`, `trio`, `abab`, `aab_close`):
  - dùng `contrast` nếu có;
  - nếu không, fallback variation của `key` + warning, chỉ cho preview/export, không promote.
- Plan có close:
  - dùng `close` nếu có;
  - nếu không, bar cuối dùng `VILLA_CADENCE` (nếu pattern hỗ trợ), else key + warning.
- `complete` cơ bản vẫn dựa trên 5 tag; plan-specific completeness kiểm thêm `contrast`/`close`.

---

## 6. Renderer seam

### 6.1. `StudioPiece`

```python
@dataclass(frozen=True)
class StudioPiece:
    pattern: str
    meter: str
    cells: Mapping[str, TextureSpec]
    arrangement: tuple[tuple[str, int], ...]  # (cell_id, cell_bar) per bar
```

### 6.2. Injection

Thêm optional param:

```python
render(..., studio_piece: StudioPiece | None = None)
```

Prop:

```text
render → _compose → guitar → render_patterned_voices
```

Trong `render_patterned_voices`:

```python
if studio_piece is not None:
    lead, support, low = render_studio_arrangement(ctx, studio_piece)
    patterns = [studio_piece.pattern] * ctx.bars
    return _finish_voices(
        ctx, patterns, lead, support, low,
        levels=levels,
        micro_velocity_writers=micro_velocity_writers,
        micro_velocity_token=micro_velocity_token,
    )
```

`render_studio_arrangement`:

- loop `arrangement` theo bar;
- gọi `render_texture_bar(texture, ctx, bar, cell_bar=...)`;
- ghép voice 1/2/3;
- clip/tie tại biên.

Mặc định `studio_piece=None` → byte-identical.

### 6.3. Arrangement builder

Từ `FormSpec` + tags:

```text
intro bars   → intro.short / intro.long
body bars    → A/B/close theo Plan
outro bars   → outro.short / outro.long
```

- `frame_roles` quyết định role 0/1/2/3.
- body tiling theo cell.bars.
- close bar cuối có thể dùng `VILLA_CADENCE` nếu không có `close` tag.

---

## 7. 1D series

Nguồn:

1. `symbol` + `date` → load bars hiện có.
2. `bars[]` do client gửi (giới hạn số lượng).
3. Demo mặc định: `VIC 2026-10-14` hoặc synthetic.

Yêu cầu:

- ít nhất đủ bars cho form;
- `close` hữu hạn;
- volume >= 0;
- giới hạn max bars/bytes.

UI có thể:

- dropdown symbol/date;
- hoặc “Use demo 1D series”;
- hoặc paste JSON bars.

---

## 8. Studio UI

Khi figure pool đủ 5 tag:

```text
Plan:
(•) AABA
( ) Trio (ABA)
( ) ABAB
( ) AAB close
( ) Through

1D series:
[ VIC · 2026-10-14 ▼ ]  or  [ Use demo ]

[ Render piece ]  [ Play ]  [ Export WAV ]  [ Export MusicXML ]
```

Hành vi:

- Đổi plan/series → invalidate render/audio.
- `Render piece` gọi API.
- `Play` phát `audioUrl`.
- `Export WAV` tải WAV.
- `Export MusicXML` tải MusicXML.
- `Promote` là nút riêng, không auto.
- Hiện:
  - meter/bars/notes/duration;
  - plan roles;
  - warnings (B fallback, audio cap, missing close).

---

## 9. Phases

### Phase A — renderer seam
- `StudioPiece` + injection vào `render`.
- `render_studio_arrangement`.
- Test: figure pool + form → score; flag off byte-identical.

### Phase B — plan + B/close
- optional tags `contrast`, `close`.
- plan picker data.
- arrangement builder A/B/close.
- test AABA/trio/ABAB.

### Phase C — API render/export
- `POST /figure/render`.
- cache hash.
- WAV luôn qua production audio pipeline; MusicXML luôn có.
- tests.

### Phase D — Studio UI
- plan picker.
- series picker.
- Render/Play/Export.
- tests.

### Phase E — hardening
- quota/TTL.
- long piece path.
- warnings/errors.
- audition.

---

## 10. Acceptance

- User chọn 1D series.
- Chọn plan AABA/trio/ABAB.
- Render full piece.
- Nghe bằng Play.
- Export WAV + MusicXML.
- 2/4 và 4/4 đều chạy.
- Không tràn bar/voice.
- Không auto-publish.
- Flag off byte-identical.
- Không cần viết lại renderer/audio.

---

## 11. Reuse

| Thành phần | Reuse |
|---|---|
| `render` / `_finish_voices` | Có |
| `score_to_musicxml` | Có |
| production audio / MuseScore | Có, dùng cho mọi độ dài |
| `plan_week`/`plan_month` | Có |
| `sentence_plan` | Có |
| `pattern_promote`/`pattern_doors` | Có |
| `texture_figure` | Có |
| Pattern selection | Cần `studio_piece` seam |
| UI Render/Play/Export | Cần mới |

---

## 12. Quyết định đã chốt

0. **Promote hiện tại là registry preview, không phải composer selection.** `/promote` đăng ký cells/door/body nhưng chưa làm pattern mới selectable trong `_patterns()`/`selectable_pattern()`. Render Piece dùng seam `studio_piece` để render trực tiếp; muốn composer tự chọn pattern phải làm bước registry/flag riêng.
1. **B material**: optional `contrast` tag. Nếu thiếu, fallback variation của `key` + warning; chỉ preview/export, không promote.
2. **Close**: optional `close` tag cho body kết. Không có short/long; `outro.short/long` là door riêng. Fallback `VILLA_CADENCE` ở bar cuối nếu pattern hỗ trợ.
3. **1D series mặc định**: `VIC 2026-10-14`.
4. **Audio**: Render Piece **luôn dùng production audio pipeline** (MuseScore/`sonify/audio.py`), cho cả bản ngắn và dài.
   - Không dùng `studio_audio.ensure_audio` 45s cho Render Piece.
   - Nếu production audio lỗi: trả MusicXML + lỗi audio rõ, không fallback synth và không cắt im lặng.
5. **Quota**: render preview **không tiêu publish quota**. Có rate limit riêng cho render/audio; quota publish giữ nguyên.
6. **Cache**: content hash `renderHash`, TTL 24h, LRU; MusicXML/WAV cùng key.
