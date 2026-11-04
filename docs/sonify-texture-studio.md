# Texture Studio — thư viện texture guitar trong Musicalize

> **Trạng thái**: đề xuất, chưa code.
> **Phạm vi đợt đầu**: Villa-Lobos (`ensemble = "villa"`), texture lấy từ *Suite Popular Brasileira*.
> **Nơi chạy**: trong app Musicalize (room mới), backend FastAPI phía sau.
> **Mở cho tất cả bây giờ**, nhưng có seam quyền truy cập để sau này giới hạn một số người.
> **Liên quan**: [`sonify-classical-guitar.md`](./sonify-classical-guitar.md), [`sonify-pattern-names.md`](./sonify-pattern-names.md), [`sonify-guitar-torroba-plan.md`](./sonify-guitar-torroba-plan.md), [`sonify-guitar-torroba-castillos-frames.md`](./sonify-guitar-torroba-castillos-frames.md).

---

## 1. Tóm tắt

Quy trình hiện tại của bạn là một chuỗi chat: chụp ảnh bản nhạc, chỉ vùng ô, để agent đọc nốt, rồi bổ sung bằng lời các quy tắc diễn tấu, nối bè, gán bè, và ánh xạ bè vào price/volume. Cách này hiệu quả cho một lần, nhưng không để lại một artifact có thể kiểm tra, tái sử dụng, hay mở rộng cho nhạc sĩ khác.

Đề xuất: biến quy trình đó thành **Texture Studio**, một pipeline authoring nằm trong Musicalize:

```
ảnh phổ + tab
    ↓
Gemini đọc nháp (có confidence từng nốt)
    ↓
bạn sửa nốt, gán bè, nhập routing / micro-timing / sustain / meter
    ↓
TextureSpec (JSON) — nguồn chân lý
    ↓
compiler sinh preview, fixture test, docs, checklist đăng ký
    ↓
renderer hiện tại hoặc interpreter chung thực thi
```

Điểm cốt lõi: **ảnh bản nhạc chỉ là ví dụ, không phải spec**. Engine không phát lại một bản nhạc cố định; nó biến chuỗi giá/volume thành nốt. Vì vậy artifact trung tâm phải là **quy tắc ánh xạ**, không phải bản phiên âm.

---

## 2. Vấn đề của quy trình hiện tại

| Bước | Việc đang làm | Vấn đề |
|---|---|---|
| 1 | Chụp ảnh, chỉ ô | Ảnh nằm ngoài repo, không có metadata vùng crop |
| 2 | Agent đọc cao độ/trường độ | Kết quả chỉ nằm trong chat, dễ trôi, không có confidence |
| 3 | Nói chênh lệch vi mô | Kiến thức diễn tấu không được lưu thành số |
| 4 | Nói nốt ngân dài nối bè | Luật tie/ring nằm rải rác trong code |
| 5 | Nói bè bass/trung/cao, bè nào ăn price/volume | Routing không có schema, mỗi lần phải nhắc lại |
| 6 | Nói quãng bè trung so với bè cao | Ràng buộc register/interval không được validate sớm |

Hệ quả:

- Thêm một texture mới phải sửa nhiều file (`guitar_patterns.py`, `guitar_wave.py`, `program.py`, `humanize.py`, test, docs…).
- Không có round-trip test: không biết spec mới có tái tạo đúng texture cũ không.
- Không có nơi để “nghe thử” trước khi ghép vào bản đầy đủ.
- Không có phân quyền: sau này muốn giới hạn Studio cho một số người sẽ phải sửa xuyên suốt.

---

## 3. Quyết định đã chốt

| Điểm | Quyết định |
|---|---|
| Nhạc sĩ | **Villa-Lobos** (`villa`), không thêm ensemble mới |
| Nguồn | ***Suite Popular Brasileira*** |
| Đơn vị | **Figure nằm trong một pattern**. Mỗi pattern/figure có meter riêng và chỉ được gọi khi khớp meter |
| Nơi chạy | **Trong app Musicalize**, backend FastAPI + UI trong app |
| Quyền | **Mở cho tất cả bây giờ**, có seam để sau này giới hạn |
| Đầu vào | **Ảnh phổ + tab** |

### 3.1. Hệ quả của “figure nằm trong pattern”

Mô hình đúng là phân cấp:

```
Composer
└── Pattern
    ├── base grid (luôn có)
    ├── Figure A
    ├── Figure B
    └── Door (intro/outro)
```

- Scheduler **không bao giờ chọn figure trực tiếp**. Nó chọn pattern trước, rồi trong pattern mới chọn figure.
- Figure không có tên in trên chart, không có `_PATTERN_TITLE`, không vào `PATTERN_NAMES`.
- Pattern có meter riêng; figure cũng có meter riêng.
- **Điều kiện gọi**: meter của pattern phải khớp meter của movement; meter của figure phải khớp meter của bar/phrase và phải là tập con của meter mà pattern cho phép.

Đây là điểm cần làm rõ vì hiện tại meter đang là **thuộc tính ngầm của movement**, không phải trường khai báo trên pattern/figure.

### 3.2. *Suite Popular Brasileira* — danh sách movement

Năm movement, cùng tên tạm trong code. Cột nhịp là nhịp **cần đối chiếu lại với bản nhạc** trước khi khoá spec; không lấy ký ức làm nguồn.

| Movement | Nhịp thường gặp | Id đề xuất | Tên in đề xuất |
|---|---|---|---|
| Mazurka-Choro | 3/4 | `suite_mazurka` | Mazurka |
| Schottish-Choro | 2/4 (cần xác nhận) | `suite_schottish` | Schottish |
| Valsa-Choro | 3/4 | `suite_valsa` | Valsa |
| Gavotta-Choro | 4/4 (cần xác nhận chỗ bắt đầu) | `suite_gavotta` | Gavotta |
| Choros No. 1 | 2/4 hoặc 4/4 (cần xác nhận) | `suite_choros1` | Choros No. 1 |

Ràng buộc engine:

- Engine hiện chỉ có `3/4`, `4/4`, `6/8`.
- Movement nào ở **2/4** phải gộp hai ô 2/4 thành một ô 4/4, đúng cách `olite` đang làm. Đây là quyết định của spec, không phải lỗi của tool.
- Không dùng lại id đã có: `choro` (Barrios), `vals` (Barrios), `gavotte` (Bach), `waltz` (Barrios). Nếu tên in trùng, `PATTERN_NAMES` sẽ nhận nhầm pattern của nhà khác.
- Mỗi movement là một **pattern** riêng, không phải figure nằm trong `villa_pattern`. Figure chỉ là biến thể bên trong movement đó.

---

## 4. Cách tổ chức hiện tại và chỗ cần sửa

### 4.1. Meter đang nằm ở đâu

Trong code hiện tại:

- `span.py` tạo `FormSpec` cho movement, gồm meter (`kind`) và tempo.
- `guitar_patterns.py` dựng `_Ctx`; `ctx.kind` là meter của movement/bar.
- Pattern được chọn bởi `_select_body`, `_dominant_pattern`, `_contrast_pattern`, dùng `ctx.kind` để lọc.
- Figure được chọn bởi `select_torroba_spans` / `select_torroba_figure`, cũng dùng `ctx.kind`.

Ví dụ Torroba:

| Đối tượng | Meter được gọi | Chỗ code |
|---|---|---|
| `castillo` | 3/4 và 4/4 | `_torroba_primary`, `_torroba_contrast` |
| Arada (kiểu 7), Float (kiểu 8) | chỉ 4/4 | `_castillo_spans`: `if kind != "4/4": return []` |
| Walk (13), Cadence (14) | chỉ 3/4 | `_castillo_34_spans` |
| `danza` | 3/4 và 6/8; không 4/4 | `_danza_spans`: `if ctx.kind not in {"3/4", "6/8"}` |
| `alcaniz` | chỉ 6/8 | `_torroba_primary` + scheduler |
| `olite` | scheduler chỉ 4/4 | `_torroba_primary`; renderer có thể bị gọi ép ở meter khác |
| `torroba_tremolo` (Juglar) | chỉ 3/4 | `_torroba_primary`, `_torroba_contrast` |

Kết luận: **meter là cổng gọi**, nhưng hiện đang được viết bằng `if ctx.kind == ...` rải rác. Texture Studio cần kéo các cổng này ra thành dữ liệu có schema, rồi sinh test cho chúng.

### 4.2. Đề xuất mô hình meter

Mỗi spec có:

```json
"when": {
  "meter": ["3/4"],
  "tempo": [0, 132],
  "mood": ["calm", "selloff"],
  "phrase": { "position": "body", "closes": false }
}
```

Quy tắc validate:

1. `pattern.when.meter` phải là tập con của `composer.meters`; không được rỗng.
2. `figure.when.meter` phải là tập con của `parent_pattern.when.meter`; không được rỗng.
3. Figure không có `parent` hợp lệ thì bị từ chối. Figure không bao giờ là ứng viên cấp cao nhất.
4. Nếu pattern nhận một meter nhưng không có figure/base grid cho meter đó, compiler cảnh báo.
5. Nếu một figure bị gọi ép ngoài meter (trong test), phải khai báo `allow_forced: true`; nếu không, validation fail.
6. Scheduler chỉ gọi figure khi:
   - pattern đang active,
   - `ctx.kind` nằm trong `figure.when.meter`,
   - các điều kiện phrase (`position`, `closes`, `n`, `rise`, `previous`) khớp.

Như vậy yêu cầu “pattern hay figure sẽ có meter riêng, phải khớp meter thì mới được gọi” trở thành một luật máy kiểm tra được, không còn là lời nhắc trong chat.

### 4.3. Điểm đăng ký khi thêm pattern mới

Khi thêm một pattern mới cho Villa-Lobos, checklist hiện tại gồm:

- `backend/app/sonify/guitar_villa.py`: renderer, helper.
- `backend/app/sonify/guitar_patterns.py`:
  - `_FAMILY`, `_PROFILE`
  - dispatch trong `render_patterned_voices`
  - `_select_body`, `_dominant_pattern`, `_contrast_pattern`
  - các dict fallback của Villa trong `_select_body`, `_owning_pattern`, `_fallback_body_pattern`, và `headline_id`
- `backend/app/sonify/program.py`: `_PATTERN_TITLE`.
- `src/sonify/program.ts`: `PATTERN_NAMES`.
- `backend/app/sonify/guitar_wave.py`: `PROFILES[("villa", id)]`.
- `backend/tests/test_guitar_wave.py`: `_EXPECTED`.
- `backend/app/sonify/humanize.py`: `_clamp_guitar` nếu trần velocity khác.
- `backend/app/sonify/guitar_scale_passages.py`: `_KINETIC_PATTERNS`, `_NARROW_ROWS`, `_HOST` nếu pattern tham gia scale.
- `backend/app/sonify/guitar_frame.py` hoặc `guitar_frame_rest.py`: nếu có cửa intro/outro riêng.
- `backend/tests/`: test pattern, test meter gate, test figure parent.
- `docs/`: cập nhật trạng thái.

Texture Studio sẽ sinh checklist này tự động từ `kind` và các cờ trong spec, để không bỏ sót.

---

## 5. Mô hình khái niệm

| Khái niệm | Vai trò | Có lên chart? | Ví dụ |
|---|---|---|---|
| `Composer` | Nhà soạn nhạc + dialect + palette | Có, ở hàng chọn nghệ sĩ | `villa` |
| `Pattern` | Đơn vị scheduler khoá cho một vùng | Có | `villa_pattern`, `suite_mazurka` |
| `Figure` | Cách đánh bên trong pattern | Không | Arada, Float, Rasgueado |
| `Door` | Kịch bản intro/outro | Không | cửa `olite`, cửa `danza` |
| `ComposerProfile` | Mặc định dùng chung: voice, routing, velocity, register | Không | profile của `villa` |
| `TextureSpec` | Một pattern/figure/door cụ thể | Tuỳ `kind` | `suite_mazurka` |

### 5.1. Routing tín hiệu

Đây là chỗ trả lời trực tiếp câu “bè nào ăn vào cái gì”:

```json
"routing": {
  "price":   { "voice": "lead", "source": "_melody_at" },
  "volume":  { "voice": "mid",  "mode": "velocity_band", "source": "liquidity" },
  "regime":  { "voice": "bass", "mode": "root_or_fifth" },
  "density": { "voice": "mid",  "mode": "eighth_grid" }
}
```

- `price` quyết định cao độ của bè nào.
- `volume` quyết định velocity/liquidity của bè nào.
- `regime` quyết định bass chọn gốc hay quãng năm.
- `density` quyết định bè nào dày/thưa theo band.

Khi một texture đảo vai (ví dụ `thumb_cantabile` cho price nằm ở bass), chỉ đổi `routing.price.voice = "bass"`, không viết lại toàn bộ renderer.

---

## 6. Kiến trúc trong Musicalize

### 6.1. Phía app

App hiện có:

- `src/musicalize/MusicalizeApp.tsx` với `Mode = 'replay' | 'live'`.
- `TopBar` nhận `mode: 'replay' | 'live'`.
- `ReplayRoom`, `LiveRoom`.

Đề xuất:

- Thêm `Mode = 'replay' | 'live' | 'studio'`.
- Thêm `src/musicalize/StudioRoom.tsx`.
- `TopBar` thêm pill **Studio** (chỉ hiện khi capability bật).
- `StudioRoom` dùng layout riêng, không dùng `RoomFrame` của phòng nghe để tránh ràng buộc.
- Không đưa Studio vào `RootNavigator` của VStock; đây là room của Musicalize.

### 6.2. Capability / phân quyền

Hiện tại app chưa có auth. Để “mở bây giờ, giới hạn sau”, cần seam ngay từ đầu:

```ts
type StudioAccess = {
  enabled: boolean;
  reason: 'open_beta' | 'entitled' | 'disabled';
  seats?: number;
};
```

- Client gọi `GET /v1/musicalize/studio/access`.
- Bây giờ backend trả `{ enabled: true, reason: 'open_beta' }`.
- Sau này backend trả `enabled: false` hoặc `reason: 'entitled'` dựa trên user/entitlement.
- UI chỉ là lớp hiển thị; **backend vẫn phải kiểm tra quyền** ở mọi endpoint, không chỉ ẩn nút.

### 6.3. Backend

```
backend/app/routers/musicalize_studio.py
backend/app/studio/
  __init__.py
  schema.py          # Pydantic models
  store.py           # SQLite + file upload
  vision.py          # Gemini adapter
  validate.py        # schema + nhạc + meter + playability
  compiler.py        # spec -> fixture/docs/checklist/preview
  preview.py         # spec + price path -> note events / audio
  export.py          # publish spec ra repo
```

Prefix đề xuất: `/v1/musicalize/studio`.

### 6.4. Lưu trữ

Vì Studio nằm trong app và sẽ có nhiều người dùng, không nên chỉ ghi file JSON.

Đề xuất hybrid:

- **SQLite** `backend/var/musicalize_studio.db`:
  - `studio_uploads`: `id`, `sha256`, `path`, `width`, `height`, `owner_id`, `created_at`
  - `studio_specs`: `id`, `composer`, `kind`, `parent_id`, `status`, `owner_id`, `visibility`, `json`, `created_at`, `updated_at`
- **File**:
  - ảnh upload: `backend/var/musicalize_studio/uploads/<sha256>.jpg`
  - preview: `backend/var/musicalize_studio/previews/...`
- **Publish**:
  - `POST /specs/{id}/publish` ghi spec đã duyệt ra `backend/app/sonify/textures/<composer>/<id>.json`
  - Chỉ file publish mới được commit và dùng bởi compiler/test.

`owner_id` và `visibility` có ngay từ đầu dù hiện tại là `anonymous` / `public`, để sau này gắn user mà không phải migrate dữ liệu.

### 6.5. API

| Method | Path | Việc |
|---|---|---|
| `GET` | `/access` | Trả capability cho Studio |
| `POST` | `/uploads` | Upload ảnh (multipart) |
| `POST` | `/analyze` | Ảnh + crop + metadata → Gemini draft |
| `GET` | `/specs` | Danh sách spec |
| `POST` | `/specs` | Tạo spec |
| `GET` | `/specs/{id}` | Đọc spec |
| `PUT` | `/specs/{id}` | Lưu spec |
| `DELETE` | `/specs/{id}` | Xoá spec nháp |
| `POST` | `/specs/{id}/validate` | Validate |
| `POST` | `/specs/{id}/compile` | Sinh preview/fixture/docs/checklist |
| `POST` | `/specs/{id}/publish` | Xuất ra repo |
| `GET` | `/previews/{id}` | Nghe preview |

Upload cần `python-multipart` (hiện chưa có trong venv). Nếu muốn server-side crop/thumbnail, thêm `Pillow`; nếu crop ở client thì không cần.

---

## 7. Schema

### 7.1. ComposerProfile

```json
{
  "composer": "villa",
  "ensemble": "villa",
  "dialect": "VillaDialect",
  "default_bpm": 100,
  "meters": ["3/4", "4/4", "6/8"],
  "tuning": ["E2", "A2", "D3", "G3", "B3", "E4"],
  "capo": 0,
  "written_octave_shift": 12,
  "voices": {
    "lead": { "signal": "price", "register": [64, 72] },
    "mid":  { "signal": "harmony", "below_lead": [3, 6], "register": [55, 65] },
    "bass": { "signal": "pedal", "register": [40, 53], "prefer": "open_string" }
  },
  "velocity_bands": {
    "lead": [64, 72],
    "mid": [42, 52],
    "bass": [52, 64]
  },
  "constraints": {
    "strict_order": "bass < mid < lead",
    "max_simultaneous": 3,
    "max_fret_span": 5
  }
}
```

### 7.2. TextureSpec

```json
{
  "id": "suite_mazurka",
  "composer": "villa",
  "kind": "pattern",
  "parent": null,
  "status": "draft",

  "source": {
    "piece": "Suite Popular Brasileira — Mazurka-Choro",
    "bars": [1, 8],
    "image": "uploads/<sha256>.jpg",
    "crop": { "x": 120, "y": 340, "w": 900, "h": 420 },
    "notation": "standard+tab"
  },

  "when": {
    "meter": ["3/4"],
    "tempo": [0, 132],
    "mood": ["calm", "selloff"],
    "phrase": { "position": "body", "closes": false }
  },

  "grid": {
    "beats": 3,
    "divisions": 2,
    "positions": [0, 0.5, 1, 1.5, 2, 2.5]
  },

  "voices": {
    "lead": { "source": "price", "at": "strong_beats" },
    "mid":  { "source": "chord_tone", "below_lead": [3, 6] },
    "bass": { "source": "chord_bass", "prefer_open": true }
  },

  "routing": {
    "price":   { "voice": "lead", "source": "_melody_at" },
    "volume":  { "voice": "mid", "mode": "velocity_band", "source": "liquidity" },
    "regime":  { "voice": "bass", "mode": "root_or_fifth" },
    "density": { "voice": "mid", "mode": "eighth_grid" }
  },

  "events": [
    { "at": 0.0, "voice": "bass", "pitch": "root", "dur": 1.0, "tie": "next_bar" },
    { "at": 0.0, "voice": "lead", "pitch": "price", "dur": 1.5, "accent": true },
    { "at": 1.5, "voice": "lead", "pitch": "price+2", "dur": 0.5, "slur_to": 2.0 }
  ],

  "micro": {
    "offset": { "lead": 0.0, "mid": 0.0, "bass": 0.0 },
    "velocity_delta": { "lead": 0, "mid": -8, "bass": -4 }
  },

  "sustain": [
    { "when": "common_tone", "voice": "mid", "do": "tie_until_next_strong_beat" },
    { "when": "lead_moves_stepwise", "voice": "mid", "do": "ring_through" }
  ],

  "selection": {
    "palette_order": 1,
    "avoid_repeat": true,
    "contrast": "chord_melody"
  },

  "provenance": {
    "model": "gemini-3.5-flash",
    "confidence": 0.82,
    "reviewed_by": "human",
    "notes": "Tab dùng dây 1-3; có hai nốt tie qua vạch ô."
  }
}
```

### 7.3. FigureSpec

Figure là spec con, bắt buộc có `parent`:

```json
{
  "id": "arada",
  "composer": "torroba",
  "kind": "figure",
  "parent": "castillo",
  "when": {
    "meter": ["4/4"],
    "phrase": { "position": "body", "closes": false, "n": "even" }
  },
  "span": { "length": [5, 6, 7, 8], "slots": [0, 1, 2, 3, 4] },
  "grid": { "beats": 4, "divisions": 2 },
  "events": [],
  "status": "reviewed"
}
```

`span` mô tả figure chiếm bao nhiêu ô và bắt đầu ở đâu, tương tự `_castillo_spans` hiện tại.

### 7.4. EventSpec

Mỗi event tương ứng một `NoteEvent` hiện có:

| Trường | Ý nghĩa | Map vào code |
|---|---|---|
| `at` | vị trí trong ô, tính bằng phách | `beat` |
| `dur` | trường độ | `duration_beats` |
| `voice` | `lead` / `mid` / `bass` | `voice` 1 / 2 / 3 |
| `pitch` | `price`, `root`, `chord_tone`, `price+2`, số MIDI | `midi` |
| `tie` | `start` / `stop` / `next_bar` | `tie_start`, `tie_stop` |
| `slur_to` | nối sang vị trí sau | `slur_start`, `slur_stop` |
| `accent` | nhấn | `accent` |
| `staccato` | ngắt | `staccato` |
| `velocity` | velocity cố định hoặc band | `velocity` |

### 7.5. Vòng đời spec

```
draft → reviewed → validated → previewed → published
```

- `draft`: Gemini vừa đọc, chưa sửa.
- `reviewed`: bạn đã sửa nốt, gán bè, nhập routing/micro.
- `validated`: qua schema + luật nhạc + meter + playability.
- `previewed`: đã nghe preview.
- `published`: đã xuất ra repo và có test.

Không cho `publish` nếu chưa `validated` hoặc còn lỗi confidence thấp chưa xử lý.

---

## 8. Gemini vision

### 8.1. Đầu vào

- Ảnh toàn trang: lấy khoá nhạc, số chỉ nhịp, số ô, hệ thống khuông.
- Ảnh crop: lấy chi tiết vùng cần đọc.
- Metadata: composer, tên bản, tuning, capo, transposition, clef.
- Guitar notation viết cao hơn sounding 1 octave → phải trả cả `written_pitch` và `sounding_pitch`.

### 8.2. Đầu ra

JSON có schema cố định, mỗi nốt có confidence và bounding box:

```json
{
  "measures": [
    { "index": 1, "meter": "3/4", "key": "A minor" }
  ],
  "notes": [
    {
      "measure": 1,
      "beat": 0.0,
      "duration_beats": 1.5,
      "voice_hint": "upper",
      "written_pitch": "E4",
      "sounding_pitch": "E3",
      "string": 1,
      "fret": 0,
      "tie": "start",
      "slur": false,
      "articulation": ["accent"],
      "confidence": 0.91,
      "bbox": [120, 340, 20, 12]
    }
  ],
  "warnings": [
    "Tab và phổ lệch ở nốt measure 2 beat 1.5 — cần review."
  ]
}
```

### 8.3. Hai pass

1. **Pass layout**: đọc số ô, hệ thống khuông, khoá, nhịp, vị trí phổ và tab.
2. **Pass transcription**: từng cụm 2–4 ô, gửi cả phổ + tab, yêu cầu đối chiếu từng nốt.

### 8.4. Đối chiếu phổ + tab

- Mỗi nốt có `note_id` chung cho cả phổ và tab.
- Nếu tab cho string/fret khác với cao độ suy ra từ phổ: trả `conflict: true`.
- Không tự chọn bên đúng. UI đánh dấu vàng, người dùng quyết định.
- Tab hữu ích để xác định octave, dây, phím; phổ hữu ích để xác định trường độ, tie, slur, bè.

### 8.5. Những gì Gemini không được quyết định

- Bè nào là bass/trung/cao khi bè bị ẩn.
- Bè nào ăn price, bè nào ăn volume.
- Micro-timing, velocity contour, humanize.
- “Nốt này phải ngân dài để nối bè”.
- Quãng bè trung so với bè cao.
- Meter của pattern/figure.
- Điều kiện chọn pattern/figure.

Những thứ này là **field của bạn** trong UI, không phải output của model.

### 8.6. Validate sau Gemini

Trước khi cho lưu `draft`:

- Tổng trường độ mỗi ô khớp meter.
- Pitch nằm trong range guitar.
- String/fret khả thi.
- Không có hai nốt cùng voice chồng nhau.
- Tie/slur có đầu có cuối.
- `written_pitch` và `sounding_pitch` lệch đúng 12 nửa cung (trừ khi capo/scordatura).

### 8.7. Cache, chi phí, bản quyền

- Cache theo `sha256(image) + crop + prompt_version`.
- Chỉ gọi Gemini ở backend; không bao giờ đưa key vào app.
- Rate limit theo client.
- Ảnh bản nhạc có thể có bản quyền: lưu trong `backend/var/` (đã gitignore), không commit ảnh; chỉ commit spec + trích đoạn ngắn nếu được phép.

---

## 9. UI trong Musicalize

### 9.1. Bố cục

```
┌──────────────────────────────────────────────────────────────┐
│  Musicalize · Studio                         [Nghe lại] [Live]│
├──────────────────┬───────────────────┬───────────────────────┤
│ Ảnh phổ + tab    │  Draft Gemini     │  Voice / Routing      │
│ [crop rectangle] │  ┌─────────────┐  │  lead  ← price        │
│                  │  │ ô 1: E4 1.0 │  │  mid   ← harmony      │
│  Zoom / pan      │  │ ô 1: C3 0.5 │  │  bass  ← volume/pedal │
│                  │  └─────────────┘  │  quãng: 3/6           │
│                  │  confidence màu   │  micro offset         │
├──────────────────┴───────────────────┴───────────────────────┤
│  Validate: 3 lỗi — bar 2 thiếu 0.5 phách; mid > lead; ...     │
├──────────────────────────────────────────────────────────────┤
│  Preview  ▶   |  Trạng thái: reviewed → validated            │
└──────────────────────────────────────────────────────────────┘
```

- Wide: 3 cột.
- Narrow: ảnh trên, draft giữa, routing dưới; preview sticky.
- Ảnh: pinch zoom, kéo crop, hiển thị số ô.
- Draft: bảng nốt, ô confidence tô màu; click một nốt thì highlight trên ảnh.
- Routing: chọn voice cho price/volume/regime/density; nhập quãng, velocity band, micro offset.
- Validate: danh sách lỗi, click để nhảy tới nốt.
- Preview: phát MIDI/audio ngắn, có thể đổi price path mẫu (flat/up/down/leap).

### 9.2. Nhập ảnh trên app

App chưa có image picker. Cần thêm dependency Expo SDK 58 (đọc docs versioned trước khi code):

- `expo-image-picker` để chọn/chụp ảnh.
- `expo-image-manipulator` để crop/resize, hoặc crop bằng overlay + canvas trên web.

Đề xuất:

- **Web**: `<input type="file">` + crop canvas.
- **Native**: `expo-image-picker`, crop thô, rồi fine crop trên web nếu cần.
- Không chặn MVP vì thiếu crop native; cho phép upload ảnh đã crop sẵn.

### 9.3. Feature flag

- `GET /access` trả `enabled`.
- Ẩn pill Studio nếu `enabled == false`.
- Backend vẫn kiểm tra quyền; UI không phải lớp bảo mật.

---

## 10. Compiler

### 10.1. Preview

`compile_preview(spec, price_path, volume_path)`:

- Sinh note events từ spec.
- Không cần dựng cả `Score`; chỉ cần một đoạn 2–4 ô.
- Xuất MIDI hoặc audio ngắn.
- Dùng để nghe trước khi tích hợp.

### 10.2. Fixture test

`compile_fixture(spec)` sinh pytest:

- Một `Phrase` cố định.
- Gọi renderer hiện tại hoặc interpreter.
- So note table với expected từ spec.
- Assert meter gate: gọi sai meter phải không trả figure.

### 10.3. Registration checklist

Từ `kind` và các cờ, sinh `registration.md`:

- Pattern mới: liệt kê đủ file/hàm như mục 4.3.
- Figure mới: chỉ cần parent pattern, `_FIGURES`, test, không cần `_PATTERN_TITLE`.
- Door mới: `DOORS`, frame test.

### 10.4. Docs

Sinh một mục trong `docs/` hoặc cập nhật file trạng thái:

- Nguồn bản nhạc.
- Meter/tempo.
- Voice/routing.
- Micro/sustain.
- Test đã có.

### 10.5. Round-trip

Đây là tiêu chí sống còn:

- Chọn một texture đang có của Villa-Lobos.
- Viết spec bằng tay.
- Compiler sinh note events.
- So với output hiện tại của `guitar_villa.py` / `guitar_patterns.py` trên cùng một `Phrase`.
- Sai số: cùng pitch/voice/beat; velocity lệch ±2.

Nếu không round-trip được, sửa schema trước khi làm UI.

Đề xuất thứ tự:

1. `chord_melody` — dễ nhất, kiểm tra schema cơ bản.
2. `villa_pattern` — khó hơn, kiểm tra campanella, tresillo, bass.
3. `thumb_cantabile` — kiểm tra routing price → bass.

---

## 11. Lộ trình

### Phase 0 — Chứng minh schema (chưa cần Gemini)

- `schema.py`, `store.py`, `validate.py`.
- Spec tay cho `chord_melody`.
- Round-trip test với renderer hiện tại.
- Preview MIDI.
- Chưa có UI; có thể dùng CLI/JSON.

**Điều kiện qua Phase 0**: round-trip đúng, validate bắt được meter/voice/duration sai.

### Phase 1 — Studio room + Gemini draft

- `StudioRoom` trong app, capability `open_beta`.
- Upload ảnh, crop.
- `vision.py` gọi Gemini, mock trong test.
- Bảng draft + confidence.
- Sửa nốt, gán voice/routing/micro.
- Validate + preview.

**Điều kiện qua Phase 1**: một người dùng thật có thể upload ảnh, sửa draft, lưu spec, nghe preview mà không cần sửa code.

### Phase 2 — Suite Popular Brasileira

- Chọn movement(s) đầu tiên.
- Tạo pattern spec + figure spec.
- Compiler sinh checklist đăng ký.
- Tích hợp renderer + test.
- Đo DFI/nghe thử.

**Điều kiện qua Phase 2**: thêm ít nhất một movement mà không phải sửa tay ngoài checklist compiler sinh.

### Phase 3 — Thư viện + phân quyền

- Danh sách spec theo composer, trạng thái, độ phủ meter.
- Publish flow: draft → reviewed → validated → published.
- Entitlement thật: user, seat, visibility.
- Có thể giới hạn Studio cho một số người mà không đổi UI.

---

## 12. Tiêu chí nghiệm thu toàn tool

1. **Round-trip**: spec của một texture cũ tái tạo đúng output hiện tại.
2. **Meter gate**: pattern/figure chỉ được gọi khi meter khớp; test âm tính cho sai meter.
3. **Figure parent**: figure không có parent hợp lệ bị từ chối.
4. **Generality**: cùng spec chạy đúng trên ít nhất 5 price path (flat, up, down, leap, reversal).
5. **Determinism**: cùng spec + cùng input → cùng note events.
6. **Safety**: `assert_playable` bắt lỗi register/voice/string trước khi publish.
7. **Review**: nốt confidence thấp phải được đánh dấu, không tự động nhận.
8. **Diff**: thêm spec mới không làm đổi output của spec cũ (golden tests).
9. **Publish**: chỉ spec đã validate mới xuất ra repo.
10. **Access**: ẩn UI không đủ; backend kiểm tra quyền.

---

## 13. Rủi ro và cách giảm

| Rủi ro | Cách giảm |
|---|---|
| Gemini đọc sai tie/slur, đặc biệt phổ + tab lệch | confidence + conflict + review bắt buộc |
| Tab và phổ khác octave | lưu cả `written_pitch` và `sounding_pitch`, validate 12 nửa cung |
| Meter 2/4 của Schottish-Choro không có trong engine | gộp hai ô 2/4 thành 4/4 như `olite`; ghi rõ trong spec |
| Figure bị gọi sai meter | schema `when.meter` + test âm tính |
| Spec mô tả đúng một bản nhạc nhưng không tổng quát | replay nhiều price path + round-trip |
| UI mobile khó crop | web-first, cho upload ảnh đã crop; native sau |
| Bản quyền ảnh bản nhạc | ảnh trong `var/`, không commit; chỉ commit spec |
| Studio thành DAW/thư viện quá lớn | giữ phạm vi: authoring + preview + publish |
| Phân quyền sau này phải sửa xuyên suốt | `owner_id`, `visibility`, `/access` ngay từ Phase 1 |
| Code hiện tại có nhiều luật ngầm | Phase 0 round-trip là bắt buộc, không bỏ qua |

---

## 14. Câu hỏi còn mở

1. **Movement nào của Suite Popular Brasileira làm trước?**
   Đề xuất: Mazurka-Choro (3/4, gần với `castillo`/`valsa`, dễ đối chiếu) hoặc Choros No. 1 (4/4, gần `villa_pattern`).
2. **Schottish-Choro (2/4) xử lý thế nào?**
   Gộp hai ô thành 4/4, hay thêm 2/4 vào engine? Đề xuất gộp trước, thêm 2/4 sau nếu cần.
3. **Studio ưu tiên web hay native?**
   Đề xuất web-first cho authoring; native chỉ xem/sửa nhẹ.
4. **Preview dùng MIDI hay audio?**
   MIDI nhẹ và deterministic; audio cần render server. Đề xuất MIDI trước, audio sau.
5. **Auth sau này dùng gì?**
   Cần chốt trước Phase 3, nhưng không chặn Phase 1.

---

## 15. Phụ lục A — Ánh xạ ngôn ngữ của bạn vào code

| Bạn nói | Trong code |
|---|---|
| “ô” | `bar`, `Phrase`, `Bar` |
| “vị trí trong ô” | `beat`, `eighth`, `divisions` |
| bè bass / trung / cao | voice 3 / 2 / 1 (`low`, `support`, `lead`) |
| price action | `_melody_at`, `placed` melody |
| volume | `liquidity` band, `NoteEvent.velocity`, dynamics |
| nốt dài nối bè | `duration_beats`, `tie_start`/`tie_stop`, `_type3_sustain` |
| chênh lệch vi mô | offset `1/12`, `1/6`, `1/5`, velocity delta, humanize |
| quãng bè trung | interval policy + `assert_playable` |
| texture | `_FAMILY`, `_PROFILE`, `guitar_wave` |
| pattern | `_PATTERN_TITLE`, `PATTERN_NAMES`, scheduler |
| nhạc sĩ | `Ensemble` + dialect + palette |
| meter | `ctx.kind`, `FormSpec`, các cổng `if kind == ...` |

## 16. Phụ lục B — Ví dụ prompt Gemini

```text
Bạn là một engine phiên âm bản nhạc. Chỉ trả JSON đúng schema.
Bạn nhận hai ảnh: toàn trang và vùng crop. Dùng ảnh toàn trang để đọc
khoá nhạc, số chỉ nhịp, số ô; dùng ảnh crop để đọc từng nốt.

Đây là bản nhạc guitar cổ điển. Ký âm guitar viết cao hơn âm thực 1 octave.
Hãy trả cả written_pitch và sounding_pitch.

Với mỗi nốt, trả:
measure, beat, duration_beats, voice_hint, written_pitch, sounding_pitch,
string, fret, tie, slur, articulation, confidence, bbox.

Nếu tab và phổ lệch nhau, đặt conflict=true và ghi warning.
Nếu không chắc, đặt confidence thấp; không được đoán.
Không trả lời bằng văn xuôi ngoài JSON.
```

## 17. Phụ lục C — Checklist pattern mới của Villa-Lobos

- [ ] `guitar_villa.py`: renderer + helper.
- [ ] `guitar_patterns.py`: `_FAMILY`, `_PROFILE`, dispatch, selection, fallback.
- [ ] `program.py`: `_PATTERN_TITLE`.
- [ ] `src/sonify/program.ts`: `PATTERN_NAMES`.
- [ ] `guitar_wave.py`: `PROFILES[("villa", id)]`.
- [ ] `test_guitar_wave.py`: `_EXPECTED`.
- [ ] `humanize.py`: trần velocity nếu khác.
- [ ] `guitar_scale_passages.py`: `_KINETIC_PATTERNS`, `_NARROW_ROWS`, `_HOST`.
- [ ] `guitar_frame.py` / `guitar_frame_rest.py`: cửa nếu có.
- [ ] test pattern + test meter gate + test figure parent.
- [ ] docs cập nhật.

Checklist này là thứ compiler sẽ sinh tự động. Mục tiêu của Texture Studio không phải bỏ code, mà là **không bỏ sót chỗ nào cần sửa** và **không phải nhớ lại từ đầu mỗi lần thêm nhạc sĩ**.
