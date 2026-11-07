# Kế hoạch: Studio Render Piece (figure → bản nhạc → WAV)

Trạng thái: **Phase A–D + W1–W4 đã triển khai** (commit `4f90da9`). W5–W10 còn partial; Phase E hardening còn lại.
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
    "span": "1W",
    "bpm": 72
  },
  "options": {
    "includeDoors": true,
    "audio": true,
    "production": {
      "preludioBass": false,
      "campanella": false,
      "bells": false,
      "fanfares": false,
      "transitions": false,
      "caesuras": false,
      "restFill": false,
      "scales": "off"
    }
  }
}
```

`options.production` là các pass production tuỳ chọn cho `StudioPiece`.
Mặc định tất cả **false** để authored cell vẫn là note list cuối cùng. Bật một
pass có thể thêm hoặc rewrite note authored; UI phải cảnh báo rõ.

`scales` là chuỗi, không phải boolean:

```json
"scales": "off" | "safe" | "pipeline"
```

- `off`: không sinh scale.
- `safe`: chỉ điền vào gap/rest của lead.
- `pipeline`: dùng scale engine gốc với host alias; có thể overwrite lead và
  có thể không chọn được passage nào.

Warning luôn báo:

```text
safe scales selected N eighth(s)
pipeline scales selected N eighth(s)
... found no usable passage in this figure
```

`series` có thể là:

```json
{ "kind": "bars", "bars": [{ "close": 100.0, "volume": 250.0 }] }
```

`form.bpm` là optional. Bỏ trống thì dùng tempo mặc định của form
(`1W` = 96). Giá trị hợp lệ: **40..180**. BPM nằm trong `form` nên được đưa
vào `renderHash`; đổi BPM sẽ tạo bản render mới.

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
GET  /v1/studio/figure/render/{renderHash}.musicxml
GET  /v1/studio/figure/render/{audioHash}.wav
POST /v1/studio/figure/render/{renderHash}/audio   -> 202 {jobId}
```

Không tái sử dụng `/v1/studio/sentence/audio/{key}.wav`:
route đó là synth preview 45s, cache/name/metadata khác hoàn toàn.

MVP dùng async cho audio, MusicXML trả ngay.

---

## 5. Plan options

Các plan user chọn trước khi export:

| id | role pattern | Trạng thái |
|---|---|---|
| `auto_aaba` | A A B close | **implemented** |
| `trio` | A B A | **implemented** |
| `abab` | A B A B | future |
| `through` | A ... A close | future |
| `explicit` | roles từ JSON | future/advanced |

`aab_close` trùng `auto_aaba`; bỏ khỏi picker.
`abab`/`through` chưa có trong `sentence_plan.py`; Phase B chỉ làm `auto_aaba` + `trio`.

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
- Hiện `promote_figures` yêu cầu **đúng** 5 tag (`set(tags) == required`), nên Phase B phải đổi thành `required ⊆ tags` trước khi thêm `contrast`/`close`.

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

## 7. Series

Nguồn:

1. `symbol` + `date` → load bars hiện có.
2. `bars[]` do client gửi (giới hạn số lượng).
3. Demo hiện tại: synthetic, chọn được `1D` / `1W` / `1M`.

Ba demo range dùng cùng một số bar (64 cho form `1W`, 128 cho form `1M`)
nhưng waveform khác nhau:

| Range | Đặc điểm | Mục đích |
|---|---|---|
| `1D` | 3 chu kỳ chậm | baseline hiện tại |
| `1W` | 5 chu kỳ + harmonic nhỏ | nhiều đổi hướng hơn |
| `1M` | 9 chu kỳ + harmonic nhỏ | nhiều biến thiên nhất |

Range chỉ đổi dữ liệu price/volume, không đổi form. `1W`/`1M` cố ý có nhiều
dao động hơn `1D` để test ảnh hưởng của price contour lên melody; đây vẫn là
demo data, chưa phải symbol/date thật.

Yêu cầu:

- ít nhất đủ bars cho form;
- `close` hữu hạn;
- volume >= 0;
- giới hạn max bars/bytes.

UI có thể:

- dropdown symbol/date (follow-up);
- hoặc chọn “Demo 1D / 1W / 1M”;
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

BPM:
[ 56 ] [ 64 ] [ 72 ] [ 84 ] [ 96 ]  [ 72 ]

Production extras:
[ Preludio bass ] [ Campanella ] [ Bells ] [ Fanfares ]
[ Transitions ] [ Caesuras ] [ Rest fill ]

Scales:
[ Off ] [ Safe ] [ Pipeline (original) ]

[ Render piece ]  [ Play ]  [ Export WAV ]  [ Export MusicXML ]
```

Production extras:

- `preludioBass`: root pedal ở intro/outro.
- `campanella`: cho support note ngân dưới lead.
- `bells`: chèn high chord tone ở intro/outro.
- `fanfares`: downbeat chord ở section có band `f`.
- `transitions`: pickup/relax ở boundary section.
- `caesuras`: khoảng lặng trước peak.
- `restFill`: điền rest cho đủ voice.
- `scales: "safe"`: điền scalar run vào các gap lead (một gap/bar), không ghi
  đè authored note. Đây là Studio-specific fallback vì pattern id của Studio
  không phải scale host của production.
- `scales: "pipeline"`: thử scale engine gốc với host alias `etude1` →
  `etude11` → `thumb_cantabile`; dùng lại contour/realization/velocity của
  production. Có thể overwrite lead. Nếu host line bị giữ nguyên một pitch
  (price đi ngang), fallback ghi một diatonic run thật: mỗi run tối đa 2
  bars, tổng ngân sách 30% body eighths (tối thiểu một bar), cách nhau ít
  nhất một bar. Fallback dùng cùng `_regions`/`_use_sixteenths`, nên cũng
  theo ngưỡng 88 BPM và leap-promotion. Đây là mode thử nghiệm.

Các pass này **có thể ghi đè authored note**. Mặc định off. Bật/tắt phải
invalidate render và nằm trong `renderHash`.

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
6. **Cache**: `renderHash` cho score/MusicXML; `audioHash` riêng cho WAV (audioRevision/paramsHash/MuseScore/soundfont). TTL 24h, LRU.

---

## 13. Production audio + hardening (W1–W10)

Phần này là **blocker trước Phase C**. Không được nói “production audio có sẵn”.

### W1 — `StudioPieceAudioStore`

Không gọi trực tiếp `RecapStore._render_movement`. Tách store riêng:

```text
app/studio/render_audio.py

render_studio_wav(
    score,
    *,
    render_hash: str,
    params,
    title: str,
) -> StudioAudioAsset
```

Tái sử dụng:

- `score_to_musicxml`;
- `musescore_export`;
- voice balance/waveform helpers;
- `piece_seconds`.

Không tái sử dụng:

- `RecapStore` cache theo symbol/span;
- `EXPORT_SLOTS` toàn cục;
- title/dance logic của `_compose`.

### W2 — Async/job cho audio dài

MuseScore/export có thể chậm; `EXPORT_SLOTS=1`.

```text
POST /v1/studio/figure/render
→ 200: renderHash, musicxmlUrl, audio:{status:"queued"|"ready"|"unavailable", jobId?}

POST /v1/studio/figure/render/{renderHash}/audio
→ 202 {jobId}

GET  /v1/studio/figure/render/{renderHash}/audio/{jobId}
→ {status, audioUrl?, error?}
```

- Queue riêng cho audio dài; không dùng chung worker validate/preview.
- Timeout: `max(180, piece_seconds*2 + 60)`.
- Semaphore: `VSTOCK_STUDIO_RENDER_SLOTS` (default 1).
- HTTP đồng bộ không được chờ vô hạn.

### W3 — Route/store riêng

Không dùng `/v1/studio/sentence/audio`:

- route đó là synth preview 45s;
- cache root/name/metadata khác;
- `MAX_AUDIO_SEC=45`.

Route mới:

```text
GET /v1/studio/figure/render/{renderHash}.musicxml
GET /v1/studio/figure/render/{audioHash}.wav
```

### W4 — Hash/cache

Hai hash khác nhau:

```text
renderHash = sha256(canonical({
  figures specs, plan id/roles, resolved series bars, form, meter,
  paramsHash, STUDIO_RENDER_REVISION
}))

audioHash = sha256(
  AUDIO_REVISION | renderHash | paramsHash |
  musescore_version | soundfont_version
)
```

Sidecar:

```json
{
  "renderHash": "...",
  "audioHash": "...",
  "scoreHash": "...",
  "audioRevision": 1,
  "durationSec": 32.4,
  "createdAt": "..."
}
```

- Atomic write + lock theo hash.
- TTL/LRU 24h.
- Không cache theo `symbol/date`; series phải resolve thành bars rồi hash.

### W4b — Pitch provenance

Render Piece **không giữ literal MIDI của MusicXML**. Trước render, `render_piece`
rebind từng event:

- voice 1 / lead → `melody_eighth` (pitch từ price melody);
- voice 2 / inner → `chord_degree(2)`;
- voice 3/4 / bass → `chord_root`.

Source passage preview vẫn giữ literal MIDI. Production promote vẫn reject
absolute literal. Warning:

```text
MusicXML literal pitches were rebound to the price/chord context
for production preview
```

### W5 — Title/pattern mới

Pattern Studio (`studio_*`) không có `PATTERN_META`/`movement_title`.
Không gọi title logic của `_compose`; dùng:

- `title` từ request; hoặc
- `patternLabel` từ draft.

MusicXML title lấy từ đó.

### W6 — `_finish_voices` trong Studio mode

`_finish_voices` thêm preludio bass, campanella, scale passages, bells, transitions, fill.
Với authored cell, các pass này có thể thêm/ghi đè nốt.

Chốt:

```text
studio_piece mode:
- chạy shape/overlap/repair;
- chạy wave/dynamics/humanize;
- KHÔNG chạy preludio_bass/campanella/scale/bells/transitions/fill (kể cả final rest fill)
  trừ khi có flag riêng.
```

Test: note authored vẫn đúng số/độ dài/voice sau tail.

### W7 — `VILLA_CADENCE` là figure, không phải cell

`StudioPiece.cells` chỉ chứa `TextureSpec`; `VILLA_CADENCE=5` là figure id.
Fallback close bằng `VILLA_CADENCE` sẽ fail nếu arrangement chỉ hỗ trợ cell.

Chốt:

```python
arrangement entry = ("cell", cell_id, cell_bar)
                  | ("cadence", "villa_cadence", 0)
```

Cadence entry đã render `VILLA_CADENCE`; figure-entry khác vẫn future.

### W8 — Plan/tag/sentence

- Chỉ implement `auto_aaba` + `trio` ở Phase B.
- `abab`/`through` future.
- `sentenceByRole` phải map role → **tag hoặc cellId**, không phải figure id.
- `promote_figures` phải đổi từ “set(tags) == required” thành “required ⊆ tags”.
- Optional `contrast`/`close` phải có:
  - `_TAG_BARS` (1–4);
  - `FIGURE_TAGS`;
  - `complete`/`/tags`/UI.

### W9 — Series/form/validator

- `symbol/date` loader phải nêu rõ hàm/route.
- Series ngắn hơn `form.bars`: 400, không tự repeat/truncate.
- `1M`/`3M`: cần `movementIndex` + scope (`SCHOTTISH_SCOPES`).
- 2/4 override qua `compose_meter`.
- Trước render:
  - `validate_texture_spec(..., meter=...)`;
  - playability;
  - coverage/overlap/tie.

### W10 — Quota/security/UI

- Render audio production rất đắt:
  - env `VSTOCK_STUDIO_RENDER_PER_DAY` (default nhỏ);
  - per-owner + global;
  - 429 + `retryAfter`.
- `X-Studio-Session` là namespace, không phải auth:
  - audio production cần flag/session/token rõ;
  - public deployment cần auth thật.
- UI phải có trạng thái:
  - `pending` → poll;
  - `ready` → Play/Export;
  - `unavailable` → MusicXML + lỗi.
- Bỏ warning “audio cap 45s” khỏi UI plan.
- Render audio có gate `VSTOCK_STUDIO_RENDER_AUDIO` (default on như kill switch) và optional `X-Studio-Render-Token`; áp dụng cho cả `/render` và `/render/{hash}/audio`.
- Play/Export hiện web-only; native cần expo-av/FileSystem.

---

## 14. Phase C chi tiết

### C1 — Render + MusicXML + hash
- `studio_piece` injection.
- `renderHash`, cache.
- `GET .musicxml`.

### C2 — Production audio store
- `render_studio_wav`, semaphore/timeout.
- `audioHash`, sidecar, atomic write.

### C3 — Async/job + routes
- 202 + poll.
- error codes:
  - `audio_unavailable`;
  - `audio_timeout`;
  - `audio_failed`.

### C4 — Tests
- cache hit/miss;
- audio unavailable/timeout;
- 2/4 và 4/4;
- frame 1/3/4 bar;
- no authored-note drift;
- flag off no-op.

---

## 15. Thứ tự thực hiện

```text
1. C2 dispatch meter guard + unpromote flag-off (code hardening)
2. Phase A (studio_piece seam)
3. Phase B (trio/AABA, contrast/close)
4. W1–W4 audio store/async/cache
5. Phase C routes
6. Phase D UI
7. W5–W10
```

---

## 16. Consideration points

Các điểm sau **không phải bug** trong luồng hiện tại; ghi lại để quyết định sau.

### 16.1. Nốt cùng cao độ lặp liên tiếp

Hiện tượng: nhiều móc đơn/móc kép liên tiếp cùng pitch.

Nguyên nhân:

- rhythm copy từ MusicXML;
- lead dùng `melody_eighth` → pitch lấy từ price melody đã quantize;
- mid dùng `chord_degree(2)`;
- bass dùng `chord_root`.

Khi price đi ngang hoặc chord giữ nguyên, các onset liên tiếp nhận cùng scale degree/chord tone. Đây là hệ quả của nguyên tắc **không giữ pitch gốc**, không phải rebind sai.

Riêng compressed 1-bar frame **không** thuộc case này: nửa sau phải đọc melody
sau `cut`, không lặp nửa đầu. Lỗi mapping đó đã được sửa bằng
`pitch_eighth_offset` trong `bind_texture` / `render_texture_bar`.

Variation policy đã implement cho lead (`off/auto/force`); mid/bass deferred. Chi tiết ở §18. Tóm tắt:

- lead: neighbor/passing tone ở weak eighth;
- mid: cycle chord degree khi cùng chord;
- bass: root/fifth alternation;
- giữ nguyên cadence/close.

### 16.2. Source pitch vs render pitch

- `Preview sentence` / source passage: giữ literal MIDI để nghe đúng bản gốc.
- `Render Piece`: rebind **mọi** literal MIDI, kể cả door/intro/outro figures.
  Trước khi bind, Phase 0 phân vai theo **từng source voice line** dùng
  median pitch:
  - voice 1 → lead;
  - non-lead median thấp nhất → bass;
  - non-lead median còn lại → mid.

  Rewrite `voice` một lần cho cả line về role voice 1/2/3/4. Cách này giữ
  duration của bass đang ngân, tránh lỗi “role assignment” cắt nốt, và tránh
  hai source voice cùng collapse về voice 2. Bass dùng register
  `Chord.bass_midi` fold vào 40..53; mid fold chord tone vào 50..65.
- Door authored material vì vậy cũng mất pitch gốc trong Render Piece; đây là
  chủ ý để giữ nguyên tắc “production pitch đến từ price/chord”. Nếu sau này
  muốn giữ riêng door authored, phải thêm option riêng và không đổi default.
- Production `promote`: reject literal MIDI.

Nếu file Render Piece trùng pitch source note-for-note, cần kiểm tra cache/bundle cũ trước khi kết luận rebind sai.

### 16.3. Demo series 1D / 1W / 1M

Demo series chỉ để test luồng. `1D`, `1W`, `1M` là ba waveform synthetic
khác nhau, không phải dữ liệu thị trường thật. `1W`/`1M` có nhiều chu kỳ ngắn
hơn nên tạo nhiều thay đổi cao độ hơn; chúng vẫn có thể lặp pitch khi price
đi ngang và không đại diện cho một bản nhạc “hay”.

Symbol/date loader thật vẫn là follow-up; khi thêm, phải resolve thành
`bars[]` trước khi hash/render, không silent truncate hoặc repeat.

`dataRange` (`1D/1W/1M`) và form `span` (`1W/1M`) là **độc lập**. Người dùng có
thể chọn `1M` data với form `1W`; UI phải nói rõ điều này để tránh hiểu nhầm.

---

## 17. Tách bè Lead / Mid / Bass

Đây là điều chỉnh lớn cho Render Piece và các piece tạo từ `StudioPiece` +
ensemble `villa`, chia làm hai phase.

### Phase 0 — sửa register/role (đã implement)

```text
Role = median pitch của từng source line, không phải source voice number
Bass = Chord.bass_midi fold vào 40..53
Mid  = chord tone fold vào 50..65
Lead = price melody, 59..81
```

- Bass hiện tại đang cao hơn ~1 octave (E3 sounding thay vì E2).
- Voice 2 trong file thực tế là bass nhưng đang bị map thành mid.
- Sau Phase 0: render lại, nghe thử; chưa đổi sang MA5/MA20.

### Phase 1 — tách line (deferred)

```text
Lead = price
Mid  = MA5
Bass = MA20
```

- Tất cả note được quantize về harmony của bar.
- Ordering chỉ ràng buộc **trung bình** `bass < mid < lead`; không hard reject.
- MA tính trên series gốc trước khi vào form.

Chi tiết thiết kế, register band, schema `line_eighth`, cache/hash và test plan:
xem `docs/studio-line-separation-plan.md`.

Trạng thái: **Phase 0 đã implement; Phase 1 chờ nghe thử Phase 0**.

---

## 18. Pattern variation — neighbor / passing tone

Trạng thái: **đã implement cho lead** (`off/auto/force`); mid/bass variation deferred.
Phạm vi: Render Piece / pattern layer, `StudioPiece` + ensemble `villa`.
Không áp dụng cho source passage preview hay legacy render.

### 18.1. Vấn đề

Lead lấy pitch từ price melody đã quantize:

```text
rhythm = copy từ MusicXML
lead   = melody_eighth
```

Khi price đi ngang hoặc cùng scale degree, nhiều onset liên tiếp nhận cùng
pitch:

```text
76 76 76 76
```

Đây không phải bug rebind; nhưng nghe như gõ lặp một nốt. Variation policy chỉ
giải quyết **tính âm nhạc**, không thay đổi nguyên tắc pitch-from-price.

### 18.2. Ranh giới layer

Variation thuộc **pattern layer**, không phải phrasing layer.

```text
phrasing = chia câu / Phrase / Run / phrase edge / held_over
pattern  = texture, variation, neighbor, tremolo, ornament
```

Pattern layer được **đọc** `ctx.phrases` và `Run` như metadata, nhưng không
sửa phrasing, không gọi lại `plan_phrases`, và không thay đổi phrase boundary.

### 18.3. Option

```json
"options": {
  "variation": "off" | "auto" | "force"
}
```

| Mode | Hành vi |
|---|---|
| `off` | Giữ nguyên lead price melody |
| `auto` | Variation ở chỗ hợp lý; **skip tremolo** và các chỗ protected |
| `force` | Áp dụng cả tremolo; vẫn giữ protected positions; có warning khi note đổi |

Mặc định: `off`.

### 18.4. Protected positions

Không đổi pitch ở:

- strong beat;
- chord-change downbeat;
- phrase start/end;
- cadence / close / bar cuối;
- note đang là target chính của price impulse;
- scale passage vừa được chèn (để tránh hai policy tranh cùng eighth).

Chỉ xét các **weak eighth** bên trong một run lặp cùng pitch.

### 18.5. Rule cho lead

Với một run:

```text
target: p p p p p
```

1. Giữ `p` ở strong beat / protected position.
2. Với các weak onset còn lại:
   - `auto`: đổi **mỗi 2 weak onset** trong run;
   - `force`: đổi **mọi weak onset** trong run (và được phép vào tremolo).
3. Chọn neighbor/passing tone:
   - upper/lower neighbor trong scale/mode;
   - nếu target kế tiếp gần hơn theo một hướng, dùng passing tone;
   - nếu target kế tiếp bằng nhau, luân phiên upper/lower.
4. Guard:
   - run phải có >= 3 onset;
   - neighbor phải cách principal **<= 2 semitone**;
   - nếu neighbor ra ngoài treble register, thử hướng ngược;
   - không tạo same-voice overlap;
   - không đổi nếu vị trí nằm trong `scale_eighths`, impulse target,
     phrase edge, cadence/close bar, chord-change downbeat, hoặc note có tie/slur;
   - reject nếu neighbor trùng pitch kế tiếp ở biên run.

Ví dụ cho run toàn weak eighth (2/4, hoặc eighth notes không rơi vào strong beat):

```text
target:   76 76 76 76 76 76
auto:     76 77 76 74 76 77   (đổi mỗi 2 weak onset)

target:   62 62 62 62
auto:     62 64 62 60

target:   62 62 62 62
force:    62 64 60 64          (đổi mọi weak onset)
```

### 18.6. Tremolo

Tremolo là lặp cùng pitch có chủ ý. `auto` phải **skip**.

Detection hiện tại:

1. pattern id/name chứa `tremolo`;
2. rhythm density: run same-pitch ở 16th/32nd (dùng sixteenth grid).

`auto` skip khi một trong hai điều kiện trên đúng. `force` bỏ qua skip tremolo
nhưng vẫn giữ strong beat, cadence/close, scale passage, impulse target và
tie/slur. Warning chung chỉ xuất hiện khi thực sự có note bị đổi:

```text
pattern variation is force; changed N repeated lead note(s)
```

### 18.7. Mid / bass (deferred)

Variation cho lead là MVP. Sau đó có thể thêm:

- **mid**: cycle chord degree khi cùng chord giữ nguyên;
- **bass**: root → fifth → root khi chord giữ;
- giữ nguyên cadence/close;
- mỗi voice có option riêng, không gộp vào lead.

### 18.8. Quan hệ với scales

Thứ tự pattern-layer:

```text
resolve pattern lead
  -> scales (safe / pipeline)
  -> variation (auto / force)
  -> repair / voice order
  -> dynamics
```

Variation bỏ qua các eighth đã thuộc scale passage để tránh chồng policy.

### 18.9. Cache / hash

Đưa vào `renderHash`:

- `variation` mode;
- bump `STUDIO_RENDER_REVISION` khi note thực tế đổi (hiện là **9**).

Output plan hiện không được hash riêng; mode đã đủ để tách cache `off/auto/force`.

### 18.10. Test plan

- Run lặp `p p p p`:
  - strong beat giữ `p`;
  - weak eighth có neighbor/passing;
  - không đổi cadence/close.
- Run dài 8 nốt: auto đổi >= 2 nốt, không chỉ 1/run.
- Neighbor cách principal > 2 semitone bị reject.
- Impulse target + scale eighth được giữ nguyên.
- Tremolo:
  - `auto` không đổi tremolo;
  - `force` đổi, giữ protected positions và warning khi note đổi.
- `off`: output giống baseline.
- Không same-voice overlap.
- Scale + variation: variation không ghi vào eighth của scale passage.
- E2E: MusicXML lead khác baseline khi có repeated run.
- Legacy render không đổi.

### 18.11. Rollout

Đã implement:

1. `variation: off | auto | force` cho lead.
2. Auto đổi mỗi 2 weak onset; force đổi mọi weak onset + tremolo.
3. UI hint:
   ```text
   Auto skips tremolo. Force may change tremolo texture.
   ```

Follow-up:

- mid/bass variation;
- tremolo-specific applied/ignored warning;
- nếu cần, thêm density knob thay vì cố định auto/force.


### 18.12. Studio lead register

Studio lead được hạ window xuống **2 semitone** so với guitar mặc định:

```text
standard: 59..81
Studio:   57..79   (lead_shift = -2)
```

- Chỉ áp dụng cho `StudioPiece`; legacy/production guitar giữ 59..81.
- `_place_melody` nhận floor/top đã hạ.
- `ctx.treble_floor/top` trong pattern layer cũng hạ theo để `scale_step`/line
  resolution nhất quán.
- Mid/bass register không đổi.
- `StudioPiece.lead_shift` có thể override; default `-2`.
