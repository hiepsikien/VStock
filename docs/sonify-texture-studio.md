# Texture Studio — thư viện texture guitar trong Musicalize

> **Trạng thái**: đề xuất, revision 2 sau khi đối chiếu code hiện tại. **Chưa code.**
> **Phạm vi đợt đầu**: Villa-Lobos (`ensemble = "villa"`), texture lấy từ *Suite Popular Brasileira*.
> **Nơi chạy**: trong app Musicalize (room mới), backend FastAPI phía sau.
> **Mở cho tất cả bây giờ**, nhưng có session namespace và seam quyền truy cập để sau này giới hạn.
> **Liên quan**: [`sonify-classical-guitar.md`](./sonify-classical-guitar.md), [`sonify-pattern-names.md`](./sonify-pattern-names.md), [`sonify-guitar-torroba-plan.md`](./sonify-guitar-torroba-plan.md), [`sonify-guitar-torroba-castillos-frames.md`](./sonify-guitar-torroba-castillos-frames.md).

---

## 0. Revision 2 sửa gì

Revision 1 đúng hướng nhưng có bảy lỗ hổng chặn Phase 0. Revision 2 sửa tận gốc:

| Vấn đề revision 1 | Cách sửa trong revision 2 |
|---|---|
| `when.meter` là string 3 giá trị, không phải `Meter` thật | Dùng `MeterSpec` đầy đủ; fail-closed trên meter lạ |
| Giả định meter per-bar | Meter là per-render; `kind_at` là section kind, không phải meter |
| Coi meter chỉ là “cổng gọi” | Meter là **materialization**: mỗi meter phải có grid/events riêng |
| So meter trước retarget | Spec khai meter **sau** `_guitar_meter` + `retarget_torroba_meter` |
| `EventSpec` không total so với `NoteEvent` | Tách `authored / derived / rendered`; thêm voice 4 |
| Preview “không cần Score” | Preview = `slice_score()` của một `render_guitar_score()` thật |
| Figure Villa không tồn tại | Phase 0 chỉ pattern; Torroba là mẫu figure có `figure_code` |
| Storage trong `backend/var` | Production dùng `/data`, chung `store/db.py`, có backup |
| Publish ghi thẳng repo từ server | Publish xuất artifact; PR do người/agent mở |
| Phân quyền no-op | Session namespace + owner check + quota; auth thật để sau |
| Gemini adapter mới | Reuse `services/gemini_companion.py` |
| Checklist tự sinh không đủ | Thêm `traits`; codegen registry + test drift |
| Title uniqueness không có test | Test cross-ensemble + đổi tên movement |

---

## 1. Tóm tắt

Quy trình hiện tại là một chuỗi chat: chụp ảnh bản nhạc, chỉ vùng ô, để agent đọc nốt, rồi bổ sung bằng lời các quy tắc diễn tấu, nối bè, gán bè, và ánh xạ bè vào price/volume. Cách này hiệu quả cho một lần, nhưng không để lại artifact kiểm tra được, tái sử dụng được, hay mở rộng cho nhạc sĩ khác.

Texture Studio biến quy trình đó thành pipeline:

```
ảnh phổ + tab
    ↓
Gemini đọc nháp (confidence từng nốt)
    ↓
người sửa nốt, gán bè, nhập meter/routing/micro/sustain
    ↓
TextureSpec (JSON) — nguồn chân lý cho authoring + test
    ↓
compiler: preview, fixture, registry, checklist
    ↓
renderer hiện tại (Phase 0/1) hoặc interpreter (Phase 2)
```

Điểm cốt lõi: **ảnh bản nhạc chỉ là ví dụ, không phải spec**. Engine không phát lại một bản nhạc cố định; nó biến chuỗi giá/volume thành nốt. Artifact trung tâm là **quy tắc ánh xạ**, không phải bản phiên âm.

### 1.1. Quyết định runtime

Revision 1 để mở “renderer hiện tại **hoặc** interpreter chung”. Revision 2 chốt:

- **Phase 0/1**: spec là **authoring source + test fixture**. Runtime vẫn là code hiện tại. Spec không được `guitar_patterns.py` đọc.
- **Phase 2**: chỉ pattern có `runtime: "interpreter"` mới được runtime đọc. Mọi pattern còn lại giữ `runtime: "code"`.
- **Phase 3**: mới cân nhắc chuyển thêm pattern từ `code` sang `interpreter`.

Lý do: renderer hiện tại chứa nhiều quyết định tay phải không thể biểu diễn bằng grid/events đơn giản. Nếu Phase 0 đã buộc runtime đọc spec, dự án sẽ thành một cuộc viết lại lớn trước khi có bằng chứng.

Hệ quả: **round-trip và diff là tiêu chí bắt buộc**, không phải tự nguyện. Nếu spec không tái tạo được renderer hiện tại, spec sai.

---

## 2. Vấn đề của quy trình hiện tại

| Bước | Việc đang làm | Vấn đề |
|---|---|---|
| 1 | Chụp ảnh, chỉ ô | Ảnh ngoài repo, không metadata vùng crop |
| 2 | Agent đọc cao độ/trường độ | Kết quả chỉ trong chat, không confidence |
| 3 | Nói chênh lệch vi mô | Kiến thức diễn tấu không thành số |
| 4 | Nói nốt ngân dài nối bè | Luật tie/ring rải rác trong code |
| 5 | Nói bè bass/trung/cao, bè nào ăn price/volume | Routing không schema |
| 6 | Nói quãng bè trung so với bè cao | Ràng buộc không validate sớm |

Hệ quả:

- Thêm texture phải sửa nhiều file, dễ bỏ sót.
- Không có round-trip: không biết spec mới có đúng texture cũ không.
- Không có preview trước khi ghép.
- Không có nơi lưu quyết định meter/voice/routing.

---

## 3. Quyết định đã chốt

| Điểm | Quyết định |
|---|---|
| Nhạc sĩ | **Villa-Lobos** (`villa`), không thêm ensemble |
| Nguồn | ***Suite Popular Brasileira*** |
| Đơn vị | **Figure nằm trong pattern**. Pattern/figure đều có meter riêng và chỉ được gọi khi khớp |
| Nơi chạy | **Trong app Musicalize**, backend FastAPI + UI trong app |
| Quyền | **Mở cho tất cả bây giờ**, chưa cần login; có session namespace để sau này giới hạn |
| Đầu vào | **Ảnh phổ + tab** |
| Runtime | Code-backed mặc định; interpreter chỉ ở Phase 2 cho pattern được chọn |

### 3.1. Hệ quả của “figure nằm trong pattern”

```
Composer
└── Pattern
    ├── meter variant A
    │   ├── base grid
    │   ├── Figure A1
    │   └── Figure A2
    ├── meter variant B
    │   ├── base grid
    │   └── Figure B1
    └── Door (intro/outro)
```

- Scheduler không bao giờ chọn figure trực tiếp. Nó chọn pattern trước, rồi trong pattern mới chọn figure.
- Figure không có tên in trên chart, không có `_PATTERN_TITLE`, không vào `PATTERN_NAMES`.
- Pattern có meter riêng; figure cũng có meter riêng.
- **Điều kiện gọi**: meter của pattern phải khớp meter runtime; meter của figure phải khớp meter runtime và phải là tập con của meter mà pattern cho phép.
- Mỗi cặp `(pattern, meter)` phải có **materializer** tường minh. Không có base grid ngầm.

### 3.2. *Suite Popular Brasileira* — danh sách movement

Năm movement. Cột nhịp là nhịp **cần đối chiếu lại với bản nhạc** trước khi khoá spec.

| Movement | Nhịp thường gặp | Id đề xuất | Tên in đề xuất |
|---|---|---|---|
| Mazurka-Choro | 3/4 | `suite_mazurka` | Mazurka-Choro |
| Schottish-Choro | 2/4 (cần xác nhận) | `suite_schottish` | Schottish-Choro |
| Valsa-Choro | 3/4 | `suite_valsa` | Valsa-Choro |
| Gavotta-Choro | 4/4 (cần xác nhận chỗ bắt đầu) | `suite_gavotta` | Gavotta-Choro |
| Choros No. 1 | 2/4 hoặc 4/4 (cần xác nhận) | `suite_choros1` | Choros No. 1 |

Quy tắc tên:

- Dùng **tên đầy đủ của movement**, không dùng `Mazurka`, `Valsa`, `Gavotta` trần.
- Lý do: `PATTERN_NAMES` trong `src/sonify/program.ts` là một `Set<string>` **toàn cục theo title**. `Gavotte` của Bach, `Waltz` của Barrios, `Choro` của Barrios đã tồn tại. `Gavotta`/`Valsa`/`Choro` trần là bẫy trùng nghĩa, dù không trùng ký tự.
- Python `pattern_title(pattern, ensemble)` keyed theo id + ensemble, nên trùng title không làm Python nhầm; nhưng TS `isPatternForm` sẽ nhận nhầm nếu title trùng. Vì vậy test uniqueness phải chạy trên **title toàn cục**.
- Không dùng lại id: `choro`, `vals`, `gavotte`, `waltz`.

---

## 4. Meter: mô hình đúng

### 4.1. Thực tế trong code

`form.py` có nhiều meter thật:

```python
METER_44  = Meter(4, 4, 8,  (0, 4), (4,))
METER_34  = Meter(3, 4, 6,  (0,),   (4,))
METER_68  = Meter(6, 8, 6,  (0, 3), (3,))
METER_128 = Meter(12, 8, 12, (0, 3, 6, 9), (3, 6, 9))
METER_54  = Meter(5, 4, 10, (0, 6), (6,))
METER_64  = Meter(6, 4, 12, (0, 4, 8), (6,))
METER_78  = Meter(7, 8, 7,  (0, 2, 4), (2, 4))
```

Nhưng guitar thu gọn meter thành 3 bucket bằng `_meter_kind()` trong `guitar_patterns.py`:

```python
def _meter_kind(meter) -> str:
    if meter.eighths_per_bar == 8:
        return "4/4"
    if meter.eighths_per_bar == 6 and meter.beat_type == 8:
        return "6/8"
    if meter.eighths_per_bar == 6:
        return "3/4"
    return "other"
```

Hệ quả thật:

- `ctx.kind` là **meter của toàn bộ lần render**, không phải per-bar. Nó được set một lần từ `active_meter()` / `compose_meter()`.
- `ctx.kind_at` **không phải meter**. Nó là section kind: `"phrase" / "intro" / "outro" / "warmup" / "cooldown"`.
- 12/8 trả `"other"`. `_torroba_primary` fallback `table.get(ctx.kind, table["4/4"])`, nên 12/8 chạy như 4/4 (Olite). Figure 4/4 không bắn vì `_castillo_spans` gate `kind == "4/4"`. Đây là bug runtime, không phải hành vi để spec bắt chước.
- Guitar đổi meter sau `FormSpec`: `_guitar_meter()` hoán đổi 3/4 ↔ 6/8; `retarget_torroba_meter()` đổi 4/4 calm/selloff → 3/4. Spec phải khai meter **sau** hai bước này.
- Meter không chỉ là cổng gọi. Với Villa, `ctx.kind` đổi nội dung render: `_villa_bass`, `_render_villa_bar`, `_chord_grid`, `_thumb_offsets` đều đọc `ctx.kind`.

### 4.2. `MeterSpec`

Spec lưu meter đầy đủ, không lưu string:

```json
{
  "id": "4/4",
  "beats": 4,
  "beat_type": 4,
  "eighths_per_bar": 8,
  "strong_eighths": [0, 4],
  "subbar_breaks": [4]
}
```

Quy ước:

- `id` chỉ là nhãn hiển thị. Nguồn chân lý là `beats/beat_type/eighths_per_bar/strong_eighths/subbar_breaks`.
- So sánh meter phải so **toàn bộ cấu trúc**, không so string.
- `composer.meters` là danh sách `MeterSpec` mà composer hỗ trợ.
- `pattern.meter_variants` là map `meter_id → materializer`.
- `figure.meter` phải nằm trong `parent_pattern.meter_variants`.

### 4.3. Thứ tự resolve meter

Compiler và runtime phải dùng **cùng một hàm**:

```
requested meter (form/param)
    ↓
_guitar_meter(spec)              # guitar: 3/4 ↔ 6/8
    ↓
retarget_torroba_meter(spec)     # Torroba: 4/4 calm/selloff → 3/4
    ↓
resolved MeterSpec
```

Nếu spec được viết từ `FormSpec` gốc mà bỏ qua hai bước trên, test meter gate sẽ test sai meter. Đây là lỗi revision 1.

`resolve_runtime_meter(variant, ensemble, character, requested)` là hàm dùng chung, đặt cạnh `_guitar_meter`/`retarget_torroba_meter` hoặc trong `texture_registry.py`. Không copy logic.

### 4.4. Meter variants và chuyển đổi

Không có chuyện “pattern 4/4 tự chạy 12/8”. Mỗi biến thể phải khai báo:

```json
"meter_variants": {
  "3/4": {
    "materializer": "grid_3_4",
    "transform": "none",
    "figures": ["walk", "cadence"]
  },
  "4/4": {
    "materializer": "grid_4_4",
    "transform": "none",
    "figures": ["arada", "float"]
  }
}
```

Các loại chuyển đổi được phép:

| Nguồn → đích | Điều kiện | Transform | Ghi chú |
|---|---|---|---|
| 3/4 ↔ 6/8 | Cùng 6 eighth | `accent_remap` | Phải khai lại `strong_eighths`; không dùng chung accent |
| 2/4 × 2 → 4/4 | Gộp hai ô | `fold: 2` | Tiền lệ thật là `galop` trong `guitar_sor.py:303`, không phải `olite` |
| 4/4 → 12/8 | 8 → 12 eighth | `triplet_subdivision` | Không tự động; cần nghe thử và duyệt |
| Meter khác | 5/4, 6/4, 7/8… | `none` | Fail closed nếu không có materializer |

Quy tắc:

1. Không có `transform` tường minh thì không được gọi pattern/figure ở meter đó.
2. `transform != "none"` phải có test nghe/so sánh, không chỉ test schema.
3. Nếu `requested meter` là 12/8 mà pattern chỉ có 4/4, compiler báo lỗi; runtime không fallback im lặng.
4. Nếu muốn giữ hành vi 12/8 hiện tại, phải thêm một materializer 12/8 thật hoặc một `triplet_subdivision` được duyệt. Không được để `"other"` rơi vào 4/4.

### 4.5. Validate meter

1. `pattern.meter_variants` không rỗng; mỗi key là `MeterSpec` hợp lệ.
2. `pattern.meter_variants` ⊆ `composer.meters`.
3. `figure.meter` nằm trong `parent_pattern.meter_variants`.
4. `figure.parent` tồn tại; figure không phải ứng viên cấp cao nhất.
5. Figure chỉ được gọi khi pattern active **và** `resolved_meter.id == figure.meter.id`.
6. Nếu pattern không có materializer cho `resolved_meter`, fail; không fallback.
7. Test âm tính: gọi figure ở meter sai phải trả `[]` hoặc raise, không render.

### 4.6. Không có meter per-bar

Revision 2 bỏ hoàn toàn giả định “meter của bar/phrase”. Nếu sau này cần đổi meter giữa movement, đó là refactor `render.py`/`Score` (thêm meter per-section), không phải việc của `guitar_*`.

Trong Phase 0–2:

- Meter là per-render/per-movement.
- Figure `when.meter` là gate tĩnh, resolve lúc load spec.
- Không dùng `kind_at` làm meter.

---

## 5. Pattern, figure, door

### 5.1. Torroba là mẫu tham chiếu

- Figure Torroba là **int**: `_FIGURES` trong `guitar_torroba.py:3403`.
- Có thêm gate `_REAL_TORROBA_FIGURES` (`guitar_torroba.py:32`) dùng ở `guitar_patterns.py:1862`.
- `FigureSpec` phải có `figure_code` (int) để map vào `_FIGURES`; không dùng string `"arada"` làm id runtime.
- `FigureSpec.id` chỉ là id authoring; `figure_code` là id runtime.

Ví dụ:

```json
{
  "id": "arada",
  "composer": "torroba",
  "kind": "figure",
  "parent": "castillo",
  "figure_code": 7,
  "meter": { "id": "4/4", "beats": 4, "beat_type": 4, "eighths_per_bar": 8, "strong_eighths": [0, 4] },
  "span": { "length": [5, 6, 7, 8], "slots": [0, 1, 2, 3, 4] },
  "status": "reviewed"
}
```

### 5.2. Villa chưa có figure registry

Trong code hiện tại:

- `villa_pattern` là một hàm bar-level: `_render_villa_bar`.
- `etude1`, `etude11` là bar-level: `_render_etude1_bar`, `_render_etude11_bar`.
- `chord_melody`, `thumb_cantabile` là bar/phrase-level.
- Không có `_FIGURES`, không có `span`, không có `figure_code`.

Vì vậy:

- **Phase 0/1: Villa chỉ có `kind: "pattern"`.** Không bịa `FigureSpec` cho Villa.
- Phase 2: audit từng movement của *Suite Popular Brasileira* để quyết định pattern nào thực sự có figure span. Nếu chỉ là biến thể trong một hàm bar-level, nó là `variation`, không phải figure.
- Khi Villa có figure registry, nó phải theo cùng mô hình Torroba: `figure_code` + bảng map + test.

Đây là câu trả lời cho câu hỏi “Villa tổ chức thế nào”: **chưa biết; phải audit, không suy từ Torroba.**

### 5.3. Door

Door vẫn là `kind: "door"`, có `parent` pattern và `when` riêng. Door không nhận figure. Nếu pattern mới có cửa, `traits.has_door = true`.

---

## 6. Spec model: authored / derived / rendered

### 6.1. Ba tầng

Revision 1 trộn tất cả vào `events`. Revision 2 tách:

| Tầng | Chứa gì | Có phải nguồn chân lý? | Dùng trong round-trip? |
|---|---|---|---|
| `authored` | bar, beat, duration, voice, pitch, tie, slur, accent, staccato, staff | Có | Có |
| `derived` | velocity band, hairpin rule, humanize, dynamics policy | Không | Chỉ khi cùng input |
| `rendered` | `NoteEvent` sau `_resolve`, `apply_guitar_wave`, humanize | Không | Golden artifact riêng |

`rendered` không nằm trong `TextureSpec`. Nó là file `rendered.json` hoặc hash, sinh từ một render thật.

### 6.2. `NoteEvent` tương ứng

`NoteEvent` trong `model.py:121` có:

- `bar`, `beat`, `midi`, `duration_beats`, `voice`
- `staff`, `tie_start`, `tie_stop`, `slur_start`, `slur_stop`
- `accent`, `velocity`, `tenuto`, `staccato`, `hairpin`, `pinned`

Spec `authored` phải cover: `bar`, `beat`, `midi`/pitch, `duration_beats`, `voice`, `staff`, `tie_start/stop`, `slur_start/stop`, `accent`, `tenuto`, `staccato`.
Spec `derived` cover: `velocity`, `hairpin`, `pinned`, dynamics.
Spec không cover: `Score.lead_wedges`, `support_wedges`, `dynamics`, `harmonies` — đây là artifact của render, không phải event.

### 6.3. Voice

Voice thật có **1/2/3/4**:

- 1 = lead
- 2 = support
- 3 = bass/low
- 4 = Preludio upper middle (được `assert_playable` giữ riêng, không gộp vào 2)

Spec dùng `voice: 1|2|3|4`, không dùng `"lead"|"mid"|"bass"` làm runtime value. Có thể có `role` để hiển thị, nhưng `voice` là số.

### 6.4. Routing

Revision 1 viết `routing.regime: { voice: "bass", mode: "root_or_fifth" }`. Sai ngữ nghĩa:

- `Regime` trong code là **market regime** `uptrend/downtrend/sideway` (`regime.py`), dùng để chọn chord slot.
- Guitar bass dùng regime để nghiêng bậc I (uptrend) hoặc V (downtrend), không phải “root or fifth” chung chung.

Sửa thành:

```json
"routing": {
  "price":   { "voice": 1, "source": "_melody_at" },
  "volume":  { "voice": 2, "mode": "velocity_band", "source": "liquidity" },
  "bass_tilt": { "voice": 3, "mode": "degree_i_or_v", "source": "market_regime" },
  "density": { "voice": 2, "mode": "eighth_grid" }
}
```

- `price` → voice 1 (hoặc voice 3 với `thumb_cantabile`).
- `volume` → velocity band của voice 2/3.
- `bass_tilt` → market regime nghiêng I/V; không phải “root_or_fifth”.
- `density` → grid dày/thưa.

### 6.5. Round-trip so gì

- So `authored`: cùng `bar`, `beat`, `duration_beats`, `voice`, `staff`, `midi`, tie/slur/accent/staccato.
- Không so `velocity` tuyệt đối. Velocity do `apply_guitar_wave()` + `resolve_bar_volumes()` + liquidity + humanize quyết định; nó không thuộc spec.
- Nếu muốn so `rendered`, phải dùng **cùng price path, cùng volume path, cùng chord slots, cùng liquidity bands, cùng humanize seed**. Khi đó so hash hoặc snapshot, không so ±2.
- `rendered` là golden artifact, không phải input của spec.

### 6.6. `assert_playable` không chứng minh spec playable

`assert_playable` chạy trên score **đã được repair** (`_resolve`, `_fit`, renderer sửa voicing trước khi ghi). Nó không chứng minh `authored` playable.

Cần thêm:

- `assert_authored_playable(authored, profile)`: kiểm tra string/fret/register/voice order **trước** repair.
- `assert_playable(score, profile)`: kiểm tra output sau repair, như hiện tại.
- Publish yêu cầu cả hai.

---

## 7. Runtime target và ai đọc spec

### 7.1. Phase 0/1: spec không được runtime đọc

- `TextureSpec` là authoring source + test fixture.
- `render_patterned_voices` vẫn dùng code hiện tại.
- Compiler sinh:
  - `fixture.json` (data-driven test input)
  - `registration.md` (checklist)
  - `preview.wav` (từ render thật)
  - `rendered.json` (golden)
- Không sinh Python source từ spec trong runtime.

### 7.2. Phase 2: `texture_registry.py`

Thêm loader:

```
backend/app/sonify/texture_registry.py
```

- `load_specs(root)` đọc `backend/app/sonify/textures/**/*.json`.
- Validate bằng `schema.py` + `validate.py`.
- Trả `PatternSpec` / `FigureSpec`.
- Dùng bởi compiler/test **và** runtime chỉ cho pattern có `runtime: "interpreter"`.
- Pattern `runtime: "code"` vẫn đi qua `if/elif` hiện tại.

`backend/app/sonify/textures/` hiện **không tồn tại**; đây là thư mục mới, chỉ chứa spec đã publish. Không có loader nào hôm nay, nên câu “publish xong ai đọc” phải trả lời bằng loader này.

### 7.3. Ai đọc spec publish?

| Giai đoạn | Người đọc | Mục đích |
|---|---|---|
| Phase 0 | `pytest` + compiler | Round-trip, fixture, docs |
| Phase 1 | Studio UI + compiler | Preview, validate, export |
| Phase 2 | `texture_registry.py` | Runtime cho `runtime: "interpreter"` |
| Phase 3 | Runtime + library UI | Chọn pattern/figure theo meter |

Publish không ghi thẳng vào repo từ server. Publish tạo bundle để người/agent mở PR; sau khi merge, `texture_registry.py` mới đọc được.

---

## 8. Preview

### 8.1. Preview là `slice_score` của render thật

Revision 1 nói “preview không cần dựng cả Score”. Sai. `_Ctx` cần:

- `melody`, `raw`, `chord_at`, `phrases`
- `band_at`, `regime_at`, `bar_volumes`
- `mode`, `character`, `sections`, `rel_span`
- register limits, `epb`, `bars`

Đây chính là một `Score` + `FormSpec` đã render. Vì vậy:

```
render_guitar_score(...)  →  Score đầy đủ
        ↓
slice_score(score, start, end)   # span.py:739
        ↓
preview.wav / rendered.json
```

- Preview 2–4 ô nhưng lấy từ render thật, không phải interpreter riêng.
- Preview dùng cùng price path/volume/chord slots như bản đầy đủ.
- Nếu preview khác bản đầy đủ, đó là bug.

### 8.2. Audio, không phải MIDI

- App dùng `expo-audio`, không có MIDI player.
- Guitar audio đi qua `audio.py` → MuseScore.
- `EXPORT_SLOTS` mặc định 1 (`audio.py:61`), nên preview sẽ tranh slot với nút Nghe.
- Cần:
  - cache preview theo `score hash + instrument + tempo + humanize`;
  - TTL như `AUDIO_MAX_AGE_DAYS`;
  - hàng đợi riêng hoặc `VSTOCK_MUSESCORE_SLOTS` tăng cho Studio;
  - UI hiển thị “đang chờ MuseScore” thay vì treo.
- Không hứa “MIDI nhẹ” khi app không có MIDI player.

---

## 9. Gemini vision

### 9.1. Reuse client hiện có

Không tạo key handling thứ hai. `services/gemini_companion.py` đã có:

- `_client()` (API key hoặc Vertex)
- `is_gemini_configured()`
- `_model_name()` / `DEFAULT_MODEL`
- key resolution 3 biến môi trường

Đề xuất:

- Tách phần client/config chung thành `services/gemini_client.py` nếu cần.
- `services/studio_vision.py` chỉ chứa prompt, schema, parse, cache.
- Không gọi Gemini từ app; key chỉ ở backend.

### 9.2. Input/output

Input:

- ảnh toàn trang: khoá, nhịp, số ô, hệ thống khuông
- ảnh crop: chi tiết vùng cần đọc
- metadata: composer, tên bản, tuning, capo, transposition, clef
- guitar notation viết cao hơn sounding 1 octave → trả cả `written_pitch`, `sounding_pitch`

Output JSON:

```json
{
  "measures": [{ "index": 1, "meter": "3/4", "key": "A minor" }],
  "notes": [{
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
    "bbox": [120, 340, 20, 12],
    "conflict": false
  }],
  "warnings": []
}
```

### 9.3. Cache và giới hạn

Cache key phải gồm:

```
sha256(image) + crop + model + prompt_version + schema_version
```

Thiếu `model` hoặc `schema_version` sẽ trả cache cũ sau khi đổi model/schema.

Giới hạn:

- max image bytes, max pixels, MIME whitelist;
- timeout + retry có giới hạn;
- token budget mỗi request;
- rate limit theo session;
- xử lý `SAFETY` / recitation block: trả lỗi có mã, cho nhập tay, không retry mù.

### 9.4. Gemini không quyết định

- bè bass/trung/cao khi bè ẩn
- bè nào ăn price/volume
- micro-timing, velocity, humanize
- “nốt này ngân dài để nối bè”
- quãng bè trung
- meter của pattern/figure
- điều kiện chọn pattern/figure

---

## 10. Studio trong app Musicalize

### 10.1. App

Hiện tại:

- `src/musicalize/MusicalizeApp.tsx`: `Mode = 'replay' | 'live'`.
- `TopBar` nhận `mode: 'replay' | 'live'`.
- `ReplayRoom`, `LiveRoom`.

Đề xuất:

- `Mode = 'replay' | 'live' | 'studio'`.
- `src/musicalize/StudioRoom.tsx`.
- `TopBar` thêm pill **Studio**, hiện theo capability.
- Studio dùng layout riêng, không dùng `RoomFrame` của phòng nghe.
- Mọi HTTP đi qua `src/api/client.ts` (`getApiBaseUrl`, `absoluteApiUrl`). Không tạo fetch client thứ hai.

### 10.2. Session, không phải auth

Hiện tại backend **không có auth**; CORS `allow_origins=["*"]`. Vì vậy:

- Chưa cần login.
- Nhưng phải có `X-Studio-Session` do app sinh và lưu trong AsyncStorage.
- Server dùng hash session làm `owner_id`; `visibility` mặc định `private` hoặc `public`.
- `GET/PUT/DELETE /specs/{id}` kiểm tra owner.
- `/uploads`, `/analyze`, `/preview` có quota theo session.
- Đây **không phải bảo mật** trước người cố tình; nó là namespace + chống xoá nhầm + chống đốt quota.
- Khi có auth thật, thay `owner_id` bằng user id; `visibility` enforce ở backend.

Không được viết “backend vẫn kiểm tra quyền” nếu chưa có owner check. Revision 2 nói rõ: Phase 1 có owner check theo session, chưa có auth.

### 10.3. Upload ảnh

App chưa có image picker. Cần thêm (đọc Expo SDK 58 docs trước khi code):

- `expo-image-picker` để chọn/chụp.
- `expo-image-manipulator` để crop/resize, hoặc crop canvas trên web.
- Web: `<input type="file">` + canvas.
- Native: crop thô; cho phép upload ảnh đã crop sẵn để không chặn MVP.

### 10.4. UI

```
┌──────────────────────────────────────────────────────────────┐
│ Musicalize · Studio                         [Nghe lại] [Live] │
├──────────────────┬───────────────────┬───────────────────────┤
│ Ảnh phổ + tab    │ Draft Gemini      │ Voice / Routing       │
│ [crop rectangle] │ confidence màu    │ price  → voice 1      │
│ zoom / pan       │ sửa nốt           │ volume → voice 2      │
│                  │                   │ bass_tilt → voice 3   │
├──────────────────┴───────────────────┴───────────────────────┤
│ Validate: meter, voice order, duration, playable authored     │
├──────────────────────────────────────────────────────────────┤
│ Preview ▶  (MuseScore queue)  |  draft → reviewed → validated │
└──────────────────────────────────────────────────────────────┘
```

Trạng thái:

```
draft → reviewed → validated → previewed → exported
```

- `exported`: bundle đã tải/đưa vào PR, chưa chắc đã merge.
- `published`: đã merge vào `textures/` và `texture_registry.py` đọc được.

---

## 11. Storage và publish

### 11.1. Production dùng `/data`

`backend/fly.toml` mount volume `vstock_data` tại `/data`; `VSTOCK_DB_PATH=/data/vstock.db`.

Revision 1 đặt `backend/var/musicalize_studio.db` → mất sau deploy. Sửa:

- `VSTOCK_STUDIO_DIR` mặc định `/data/studio` trên Fly.
- DB: `/data/musicalize_studio.db` hoặc `/data/vstock.db` dùng chung schema.
- Uploads: `/data/studio/uploads`.
- Previews: `/data/studio/previews`.

Khuyến nghị: dùng chung `app/store/db.py`:

- thêm bảng vào `SCHEMA`;
- thêm migration;
- `db_path()` đã đọc `VSTOCK_DB_PATH`;
- `scripts/backup-sqlite.sh` backup thêm DB Studio.

`backend/var/` chỉ dùng local dev; không dùng production.

### 11.2. Publish không ghi repo từ server

Trên Fly không có git working tree. Server không được ghi `backend/app/sonify/textures/`.

Publish = export bundle:

```
/data/studio/exports/<spec-id>/
  spec.json
  rendered.json
  fixture.json
  registration.md
  preview.wav
```

UI tải bundle; người/agent mở PR. Sau merge, `texture_registry.py` đọc.

Nếu sau này muốn tự động PR, dùng GitHub App/CI, không dùng server runtime ghi trực tiếp.

Test sinh ra phải **data-driven**:

- `backend/tests/test_texture_specs.py` quét `textures/**/*.json`;
- validate + render + so `rendered.json`;
- không sinh Python source từ spec.

---

## 12. Compiler, registry, traits

### 12.1. `traits` để checklist có nghĩa

Compiler chỉ biết `kind` + `parent` thì không thể biết pattern thuộc `_KINETIC_PATTERNS`, `_NARROW_ROWS`, `_HOST`, `_LOUD_DOWN_PATTERNS`, có `plucked`, có door hay không. Thêm:

```json
"traits": {
  "kinetic": true,
  "narrow_rows": [6, 24, 80],
  "scale_host": false,
  "plucked": false,
  "loud_down": true,
  "has_door": false,
  "pedal_door": false,
  "figure_registry": "torroba_int"
}
```

- `narrow_rows` là dữ liệu, không suy đoán.
- `figure_registry` quyết định có `figure_code` hay không.
- Compiler sinh checklist từ traits + một danh sách “review sites” cố định.
- Phần không suy được ghi là **review**, không phải **auto**.

### 12.2. Registry codegen

Repo đã có tiền lệ: `scripts/gen_params_schema.py` sinh `paramsSchema.generated.ts` và có `--check`.

Đề xuất:

- `scripts/gen_pattern_registry.py` đọc:
  - `_PATTERN_TITLE`, `_FAMILY`, `_PROFILE`
  - `PROFILES` trong `guitar_wave.py`
  - `_EXPECTED` trong `test_guitar_wave.py`
- sinh `src/sonify/patternRegistry.generated.ts` (thay hoặc bổ sung `PATTERN_NAMES`).
- `--check` phát hiện drift.
- Repo **không có CI** (`.github/` không tồn tại), nên thêm `backend/tests/test_pattern_registry.py` gọi logic `--check`; pytest là gate thật.

### 12.3. Title uniqueness

`PATTERN_NAMES` là set toàn cục theo title. Cần test:

```python
titles = [pattern_title(pattern, ensemble) for ...]
assert len(titles) == len(set(titles))
```

Nếu trùng, đổi title hoặc thêm namespace. Với *Suite Popular Brasileira*, dùng tên đầy đủ `Mazurka-Choro`, `Schottish-Choro`, `Valsa-Choro`, `Gavotta-Choro`, `Choros No. 1`.

### 12.4. Checklist đầy đủ

Ngoài checklist revision 1, thêm:

- `backend/app/sonify/guitar.py`: `_ENSEMBLE_PROFILE` (`"villa": "villa_pattern"`).
- `backend/app/sonify/guitar_patterns.py`: voice 4 path trong `assert_playable`.
- `backend/app/sonify/guitar_scale_passages.py`: `_KINETIC_PATTERNS`, `_LOUD_DOWN_PATTERNS`, `_NARROW_ROWS`, `_HOST`.
- `backend/app/sonify/guitar_patterns.py`: `_PEDAL_DOOR_PROFILE`, `_RETAINED_DOORS`.
- `backend/app/sonify/guitar_torroba.py`: `_REAL_TORROBA_FIGURES` nếu figure mới.
- Tests hardcode id: `test_humanize.py`, `test_sonify_guitar.py`, `test_sonify_guitar_scale_passages.py`.
- `backend/app/sonify/audio.py`: nếu preview/export.

---

## 13. Lộ trình

### Phase 0 — Chứng minh schema, chưa UI, chưa Gemini

- `schema.py` với `MeterSpec`, `authored/derived`.
- `resolve_runtime_meter()` dùng chung.
- `validate.py`: meter variants, figure parent, voice order, authored playable.
- Spec tay cho `chord_melody` (dễ) và `villa_pattern` (khó).
- Round-trip `authored` với renderer hiện tại.
- Preview bằng `slice_score` + `audio.py` (nếu môi trường có MuseScore), hoặc `rendered.json` nếu chưa.
- Test 12/8 fail-closed.

**Gate**: round-trip đúng; meter gate âm tính; 12/8 không fallback im lặng.

### Phase 1 — Studio room + Gemini + session

- `StudioRoom`, mode `studio`, capability.
- `X-Studio-Session`, owner check, quota.
- Upload/crop, Gemini draft, review table.
- Validate + preview + export bundle.
- Mở `open_beta`.

**Gate**: một người dùng thật upload ảnh, sửa draft, lưu spec, nghe preview, export bundle mà không sửa code.

### Phase 2 — Suite Popular Brasileira + runtime interpreter

- Audit Villa figure: pattern nào có span thật.
- Chọn movement đầu tiên; tạo pattern spec + meter variants.
- Ít nhất một pattern `runtime: "interpreter"` để chứng minh runtime đọc spec.
- Các pattern khác `runtime: "code"`.
- Compiler sinh registration checklist; test drift.

**Gate**: thêm một movement với meter đúng; ít nhất một pattern chạy từ spec.

### Phase 3 — Thư viện + auth thật

- Library UI theo composer/status/meter coverage.
- Auth + entitlement thật; thay session namespace.
- Publish flow qua PR/GitHub App.
- Backup/migration.

---

## 14. Tiêu chí nghiệm thu

1. **Meter exact**: spec lưu `MeterSpec`; so cấu trúc, không so string.
2. **Meter sau retarget**: spec khớp `active_meter()` sau `_guitar_meter` + `retarget_torroba_meter`.
3. **12/8 fail-closed**: không fallback `"other"` → 4/4.
4. **Không meter per-bar**: không dùng `kind_at` làm meter.
5. **Figure parent**: figure không có parent/meter hợp lệ bị từ chối.
6. **Authored round-trip**: cùng pitch/beat/duration/voice/staff/tie/slur/accent/staccato.
7. **Rendered golden**: cùng input + cùng seed → cùng hash/snapshot; velocity không so tuyệt đối.
8. **Preview = slice_score**: preview lấy từ render thật, không interpreter riêng.
9. **Storage bền**: DB/upload/preview nằm trên `/data`, sống qua deploy; backup có.
10. **Publish artifact**: server không ghi repo; test data-driven.
11. **Session owner/quota**: không xoá/sửa spec của session khác; Gemini có quota.
12. **Codegen drift**: `gen_pattern_registry --check` + pytest gate.
13. **Title uniqueness**: không trùng title toàn cục.
14. **Runtime proof**: ít nhất một pattern `runtime: "interpreter"` ở Phase 2.

---

## 15. Rủi ro

| Rủi ro | Cách giảm |
|---|---|
| 12/8 fallback 4/4 | MeterSpec + fail-closed + test âm tính |
| 3/4 ↔ 6/8 khác accent | `accent_remap` tường minh, nghe thử |
| 4/4 → 12/8 không tương đương | `triplet_subdivision` + duyệt tay; không tự động |
| 2/4 không có trong engine | `fold: 2`; tiền lệ `galop` |
| Figure Villa không tồn tại | Phase 0 pattern-only; audit trước |
| Velocity bị coi là authored | Tách authored/derived/rendered |
| `assert_playable` che spec xấu | `assert_authored_playable` trước repair |
| Preview lệch bản đầy đủ | `slice_score` của render thật |
| MuseScore slot tranh nhau | Queue/slot riêng + cache + latency UI |
| Fly mất dữ liệu | `/data` + chung DB + backup |
| Publish ghi repo | Export bundle; PR do người/agent |
| Gemini đốt quota | Session quota + rate limit + cache |
| Gemini bị safety block | Báo lỗi rõ, cho nhập tay, không retry mù |
| Trùng title | Test uniqueness |
| Checklist bỏ sót | `traits` + codegen + pytest drift |
| Scope creep | Phase gate rõ; không làm DAW |

---

## 16. Câu hỏi còn mở

1. **Movement nào làm trước?**
   Đề xuất Mazurka-Choro (3/4, gần `castillo`/`valsa`) hoặc Choros No. 1 (4/4, gần `villa_pattern`).
2. **12/8 xử lý thế nào?**
   (a) thêm materializer 12/8 thật; (b) cấm 12/8 cho Studio pattern và fail-closed; (c) `triplet_subdivision` có duyệt tay. Đề xuất (b) trước, (a) sau.
3. **Villa figure audit ở Phase 2 hay Phase 1?**
   Đề xuất Phase 2, sau khi round-trip pattern đã ổn.
4. **Session token sống bao lâu?**
   Đề xuất 90 ngày, lưu AsyncStorage; hết hạn tạo mới, spec cũ vẫn thuộc owner cũ nếu có auth sau này.
5. **Preview audio slot**
   Tăng `VSTOCK_MUSESCORE_SLOTS` hay queue riêng? Đề xuất queue riêng cho Studio, không chiếm slot Nghe.

---

## 17. Phụ lục A — Những chỗ revision 1 mô tả sai

| Revision 1 | Thực tế |
|---|---|
| “Engine chỉ có 3/4, 4/4, 6/8” | `form.py` có 4/4, 3/4, 6/8, 12/8, 5/4, 6/4, 7/8; guitar dùng 12/8 qua param |
| “2/4 gộp hai ô, đúng cách `olite`” | Không có meter 2/4 trong `form.py`; tiền lệ là `galop` trong `guitar_sor.py:303` |
| “`olite` scheduler chỉ 4/4” | `"other"` fallback về 4/4 row, nên Olite vẫn có thể được chọn ở meter lạ |
| “`ctx.kind` là meter của movement/bar” | Chỉ movement/per-render; `kind_at` là section kind |
| “Trùng tên in, `PATTERN_NAMES` nhận nhầm pattern của nhà khác” | Đúng với TS global set; Python `pattern_title` keyed theo id + ensemble |
| `when.mood: ["calm", "selloff"]` | Có 4 character: `calm/rally/selloff/volatile` |
| `when.tempo: [0, 132]` độc lập | Torroba tempo floor là hàm của `(mood, meter)` |
| `routing.regime: root_or_fifth` | `Regime` là market regime; guitar bass nghiêng I/V |
| `assert_playable` chứng minh spec playable | Nó chạy sau repair; cần `assert_authored_playable` |
| App dùng `MusicalizeApp` là đủ | Phải đi qua `src/api/client.ts` `getApiBaseUrl`/`absoluteApiUrl` |

---

## 18. Phụ lục B — Đối chiếu review

| Review | Trạng thái trong revision 2 |
|---|---|
| B1 meter thật, 12/8 | §4.1–4.4, §14.3 |
| B2 không meter per-bar | §4.6 |
| B3 meter là materialization | §3.1, §4.4 |
| B4 retarget trước khi so | §4.3 |
| B5 authored/derived/rendered | §6 |
| B6 preview = slice_score | §8 |
| B7 Torroba figure int, Villa chưa có | §5 |
| C1 `/data`, backup | §11.1 |
| C2 publish artifact | §11.2 |
| C3 session/owner/quota | §10.2 |
| C4 reuse Gemini client | §9.1 |
| C5 audio slot, không MIDI | §8.2 |
| D1 codegen registry | §12.2 |
| D2 traits/checklist | §12.1, §12.4 |
| D3 title uniqueness | §3.2, §12.3 |

---

## 19. Phụ lục C — Tham chiếu code

- `backend/app/sonify/form.py`: `Meter`, `METER_44/34/68/128/54/64/78`, `active_meter`, `compose_meter`.
- `backend/app/sonify/guitar_patterns.py`: `_meter_kind`, `_Ctx`, `render_patterned_voices`, `assert_playable`.
- `backend/app/sonify/guitar_torroba.py`: `_FIGURES`, `_REAL_TORROBA_FIGURES`, `_castillo_spans`, `_danza_spans`, `_torroba_bass`.
- `backend/app/sonify/guitar_villa.py`: `_render_villa_bar`, `_render_thumb`, `_render_etude1_bar`, `_render_etude11_bar`.
- `backend/app/sonify/span.py`: `_guitar_meter`, `retarget_torroba_meter`, `retarget_torroba_tempo`, `slice_score`.
- `backend/app/sonify/model.py`: `NoteEvent`.
- `backend/app/sonify/guitar_wave.py`: `PROFILES`, `apply_guitar_wave`.
- `backend/app/sonify/audio.py`: `EXPORT_SLOTS`, `AUDIO_MAX_AGE_DAYS`.
- `backend/app/sonify/params.py`: meter choices (`4/4`, `3/4`, `6/8`, `12/8`).
- `backend/app/store/db.py`: `SCHEMA`, `db_path`, `init_db`.
- `backend/fly.toml`: volume `/data`, `VSTOCK_DB_PATH`.
- `scripts/gen_params_schema.py`: codegen + `--check`.
- `src/sonify/program.ts`: `PATTERN_NAMES` global set.
- `src/api/client.ts`: `getApiBaseUrl`, `absoluteApiUrl`.
- `docs/sonify-pattern-names.md`: luật tên pattern.
