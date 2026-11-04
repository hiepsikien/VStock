# Texture Studio — thư viện texture guitar trong Musicalize

> **Trạng thái**: đề xuất, revision 3 sau review code lần 2. **Chưa code.**
> **Phạm vi đợt đầu**: Villa-Lobos (`ensemble = "villa"`), texture lấy từ *Suite Popular Brasileira*.
> **Nơi chạy**: trong app Musicalize (room mới), backend FastAPI phía sau.
> **Mở cho tất cả bây giờ**, nhưng có session namespace và seam quyền truy cập để sau này giới hạn.
> **Liên quan**: [`sonify-classical-guitar.md`](./sonify-classical-guitar.md), [`sonify-pattern-names.md`](./sonify-pattern-names.md), [`sonify-guitar-torroba-plan.md`](./sonify-guitar-torroba-plan.md), [`sonify-guitar-torroba-castillos-frames.md`](./sonify-guitar-torroba-castillos-frames.md).

---

## 0. Revision 3 sửa gì

Revision 2 đóng được 15 điểm của review đầu, nhưng sinh ra 6 mâu thuẫn nội bộ và 4 lỗ hổng cấu trúc. Revision 3 chốt lại:

| Vấn đề revision 2 | Cách sửa trong revision 3 |
|---|---|
| `meter_variants` keyed bằng string, nhưng lại nói “so cấu trúc” | `meter_variants` là **list**; key canonical là tuple 6 field; `id` chỉ hiển thị |
| Lẫn “subset” và “equality” | Figure `meter` phải **thuộc** danh sách variant của pattern, so bằng canonical key |
| Preview “khác là bug” nhưng `slice_score` cố ý cắt tie | Định nghĩa diff hợp lệ tại 2 biên; chỉ tie biên được phép khác |
| `assert_authored_playable` kiểm string/fret nhưng `authored` không có | Thêm `string`/`fret` optional vào `authored`; không thêm vào `NoteEvent` |
| Phase 0 fail-closed 12/8 nhưng runtime không đổi | Phase 0 **không sửa runtime**; Studio từ chối spec 12/8; fix runtime ở Phase 3 |
| “humanize seed” không tồn tại | Dùng `params` hash + `SPAN_REVISION` + `RECAP_REVISION` |
| `bass_tilt` dùng market regime cho Villa | `bass_tilt` là **Torroba-only**; Villa bass là chord root |
| `_RETAINED_DOORS` ghi sai file; `waltz` gọi là id | Sửa sang `guitar_frame.py`; tách rõ id và title |
| Voice 1–4 nói chung cho mọi variant | Ghi rõ guitar-only; variant khác dùng voice 5/staff 2 |
| Preview cache thiếu revision | Thêm `SPAN_REVISION`, `RECAP_REVISION`, `params` hash, `candle_count` |
| “Movement = pattern” làm hỏng movement line | Suite là **palette pattern**, không phải piece 5 movement; có test movement line |
| `active_meter()` default `METER_44` | Compiler chỉ dùng `resolve_runtime_meter()`; cấm `active_meter()` ngoài context |
| Materializer code-backed chỉ là lời khai | Thêm **ma trận test pattern × meter** làm artifact Phase 0 |
| `fold: 2` nằm trong materializer | `fold` thuộc `FormSpec`/`SourceForm`, quyết định trước khi author |
| Rev2 bỏ API table, DDL, post-Gemini validate | Khôi phục đầy đủ |
| Spec thiếu profile/wave profile | Thêm `profiles.render` + `profiles.wave` |

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

Revision 1 để mở “renderer hiện tại **hoặc** interpreter chung”. Revision 2/3 chốt:

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
- **Điều kiện gọi**: meter của pattern phải khớp meter runtime; figure `meter` phải **thuộc** danh sách `meter_variants` của pattern, so bằng canonical key (không so string, không so `id`).
- Mỗi cặp `(pattern, meter)` phải có **materializer** tường minh. Không có base grid ngầm.

### 3.2. *Suite Popular Brasileira* — danh sách movement

Năm movement, nhưng trong engine chúng là **pattern thuộc palette Villa**, không phải 5 movement của một piece. Cột nhịp là nhịp **cần đối chiếu lại với bản nhạc** trước khi khoá spec.

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
- Id đã tồn tại: `choro`, `vals`, `bach_gavotte`. Không dùng lại.
- Title đã tồn tại: `Waltz` (của `vals`), `Gavotte` (của `bach_gavotte`), `Choro` (của `choro`). Không dùng lại.
- `waltz` là **title**, không phải id. Đừng đưa nó vào danh sách id.

### 3.3. Suite là palette, không phải piece 5 movement

Đây là quyết định bắt buộc, vì `pattern_form()` chỉ in tối đa 3 title và `month_specs()` khai guitar chỉ có **4 movement slot/piece** (opener/center/closer/finale). Nếu coi 5 movement của Suite là 5 movement của cùng một piece, chart sẽ in:

```
Mazurka-Choro — Valsa-Choro — Gavotta-Choro
```

như thể piece đổi movement 3 lần, và slot thứ 5 không có chỗ.

Quyết định:

- **Suite là palette pattern**, không phải một `FormSpec` 5 movement.
- Mỗi movement là một pattern id trong palette Villa; một piece Villa vẫn có tối đa 4 movement slot.
- Các pattern Suite có metadata `suite: { name, movement }` để nhóm trong UI, nhưng `pattern_form()` không đọc metadata này.
- Movement line có thể in tối đa 3 title; đây là hành vi hiện có của `pattern_form()`, phải có test in tên.
- Nếu sau này muốn Suite là một piece 5 movement, đó là việc của `span.py`/`FormSpec`/`guitar_movement_name`, không phải pattern. Mở một PR riêng.

Hệ quả cần test:

1. Một piece Villa dùng 5 pattern Suite không làm `pattern_form()` vỡ; nó in tối đa 3 title.
2. `guitar_movement_name` vẫn in đúng nhịp/BPM của slot.
3. `PATTERN_NAMES` nhận cả 5 title.
4. Không có test nào giả định guitar có 5 movement slot.

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

Spec lưu **đủ 6 field** của `form.Meter`:

```json
{
  "id": "3/4",
  "beats": 3,
  "beat_type": 4,
  "eighths_per_bar": 6,
  "strong_eighths": [0],
  "subbar_breaks": [4],
  "extra_weights": [[4, 0.8]]
}
```

- `id` chỉ là nhãn hiển thị. Nó không phải identity.
- `extra_weights` không phải field trang trí: `METER_34` thật có `((4, 0.8),)`; `quantize.py:141` dùng nó để tính accent, `form.py:653` truyền lại. Bỏ field này thì 3/4 mất trọng số phách 4 và round-trip sai accent.
- Canonical key là tuple:

```
(beats, beat_type, eighths_per_bar, strong_eighths, subbar_breaks, extra_weights)
```

- Mọi so sánh meter dùng canonical key. Không so `id`, không so string.
- `composer.meters` là danh sách `MeterSpec`.
- `pattern.meter_variants` là **list**, không phải map keyed bằng string.
- `figure.meter` là một `MeterSpec`; nó phải **thuộc** `parent_pattern.meter_variants` theo canonical key.

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

Nếu spec được viết từ `FormSpec` gốc mà bỏ qua hai bước trên, test meter gate sẽ test sai meter.

`resolve_runtime_meter(variant, ensemble, character, requested)` là **cửa duy nhất**. Compiler không được gọi `active_meter()` trực tiếp; nếu cần render, nó phải bọc trong `compose_meter(resolved)`.

Lý do: `active_meter()` có default `METER_44` (`form.py:137`). Gọi ngoài `compose_meter` sẽ im lặng trả 4/4, đúng lớp bug đang muốn diệt. `texture_registry.py` chỉ dùng `resolve_runtime_meter()`.

Test bắt buộc:

- `resolve_runtime_meter()` trả đúng cho 3/4, 4/4, 6/8, 12/8.
- Compiler không gọi `active_meter()` ngoài `compose_meter`; test assert mọi lời gọi render của compiler đều nằm trong `compose_meter(resolved)`.
- Phase 3 mới đổi `active_meter()` default thành `None`/raise; Phase 0/1 không sửa runtime.

### 4.4. Meter variants và chuyển đổi

`meter_variants` là list. Mỗi phần tử có `meter` đầy đủ:

```json
"meter_variants": [
  {
    "meter": {
      "id": "3/4",
      "beats": 3,
      "beat_type": 4,
      "eighths_per_bar": 6,
      "strong_eighths": [0],
      "subbar_breaks": [4],
      "extra_weights": [[4, 0.8]]
    },
    "materializer": "grid_3_4",
    "transform": "none",
    "figures": ["walk", "cadence"]
  },
  {
    "meter": {
      "id": "4/4",
      "beats": 4,
      "beat_type": 4,
      "eighths_per_bar": 8,
      "strong_eighths": [0, 4],
      "subbar_breaks": [4],
      "extra_weights": []
    },
    "materializer": "grid_4_4",
    "transform": "none",
    "figures": ["arada", "float"]
  }
]
```

Các loại chuyển đổi được phép:

| Nguồn → đích | Điều kiện | Transform | Ghi chú |
|---|---|---|---|
| 3/4 ↔ 6/8 | Cùng 6 eighth | `accent_remap` | Phải khai lại `strong_eighths`/`extra_weights`; không dùng chung accent |
| 4/4 → 12/8 | 8 → 12 eighth | `triplet_subdivision` | Không tự động; cần nghe thử và duyệt |
| Meter khác | 5/4, 6/4, 7/8… | `none` | Fail closed nếu không có materializer |

`fold: 2` **không** nằm trong bảng này. Gộp hai ô 2/4 thành một ô 4/4 đổi `bars`, `bar_beats`, BPM và mapping day ↔ bar, nên nó thuộc `FormSpec`/`SourceForm`, quyết định **trước** khi author spec. Xem §4.4.1.

Quy tắc:

1. Không có `transform` tường minh thì không được gọi pattern/figure ở meter đó.
2. `transform != "none"` phải có test nghe/so sánh, không chỉ test schema.
3. **Phase 0/1 không sửa runtime.** Studio compiler từ chối spec 12/8; runtime giữ nguyên hành vi hiện tại (kể cả fallback `"other"` → 4/4). Việc sửa 12/8 là Phase 3: hoặc bỏ choice khỏi `params.py` + regenerate schema, hoặc thêm materializer 12/8 thật.
4. Không được để một spec 12/8 “tự động” dùng materializer 4/4 mà không có `triplet_subdivision` được duyệt.

### 4.4.1. `fold` thuộc `FormSpec`, không thuộc pattern

Với Schottish-Choro 2/4, engine không có `Meter(2,4,...)`. Cách xử lý là gộp hai ô 2/4 thành một ô 4/4 ở tầng form:

```json
"source_form": {
  "meter": {
    "id": "2/4",
    "beats": 2,
    "beat_type": 4,
    "eighths_per_bar": 4,
    "strong_eighths": [0],
    "subbar_breaks": [2],
    "extra_weights": []
  },
  "fold": 2,
  "result_meter": "4/4"
}
```

`resolve_runtime_form()` chịu trách nhiệm:

- `bars` giảm một nửa;
- `bar_beats` đổi từ 2 → 4;
- BPM quarter-based giữ nguyên hoặc quy đổi tường minh;
- mapping day ↔ bar (`assign_source_bars`) đổi theo;
- `slice_score` và DFI dùng bars mới.

Pattern không thấy 2/4; nó chỉ thấy 4/4 sau fold. Test bắt buộc: độ dài movement, số bar, DFI window, và tiền lệ `galop` (`guitar_sor.py:303`).

### 4.5. Validate meter

1. `pattern.meter_variants` không rỗng; mỗi phần tử có `MeterSpec` hợp lệ.
2. Tập canonical key của `pattern.meter_variants` ⊆ tập canonical key của `composer.meters`.
3. `figure.meter` phải **thuộc** `parent_pattern.meter_variants` (canonical key), không phải “xấp xỉ”, không so `id`.
4. `figure.parent` tồn tại; figure không phải ứng viên cấp cao nhất.
5. Figure chỉ được gọi khi pattern active **và** `meter_key(resolved_meter) == meter_key(figure.meter)`.
6. Nếu pattern không có materializer cho `resolved_meter`, fail; không fallback.
7. Test âm tính: gọi figure ở meter sai phải trả `[]` hoặc raise, không render.

### 4.5.1. Ma trận test `pattern × meter`

Với pattern `runtime: "code"`, `meter_variants` chỉ là lời khai. Enforcement thật là một ma trận sinh từ code hiện tại:

```
for pattern in code_patterns:
    for meter in composer.meters:
        notes = render_pattern_for_test(pattern, meter)
        assert notes is not None and notes != "other" and notes != []
```

- Sinh `backend/tests/fixtures/meter_matrix.json` ở Phase 0.
- `backend/tests/test_texture_meter_matrix.py` so matrix mới với fixture.
- Cặp nào trả `"other"`/rỗng/không render được phải fail, trừ khi spec khai `unsupported: true` có lý do.
- Đây là artifact bắt buộc, không chỉ là gate bằng lời.

### 4.6. Không có meter per-bar

Revision 2/3 bỏ hoàn toàn giả định “meter của bar/phrase”. Nếu sau này cần đổi meter giữa movement, đó là refactor `render.py`/`Score` (thêm meter per-section), không phải việc của `guitar_*`.

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
  "meter": {
    "id": "4/4",
    "beats": 4,
    "beat_type": 4,
    "eighths_per_bar": 8,
    "strong_eighths": [0, 4],
    "subbar_breaks": [4],
    "extra_weights": []
  },
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

Revision 1 trộn tất cả vào `events`. Revision 2/3 tách:

| Tầng | Chứa gì | Có phải nguồn chân lý? | Dùng trong round-trip? |
|---|---|---|---|
| `authored` | bar, beat, duration, voice, pitch, tie, slur, accent, staccato, staff; optional `string`/`fret` | Có | Có |
| `derived` | velocity band, hairpin rule, humanize policy, dynamics policy | Không | Chỉ khi cùng input |
| `rendered` | `NoteEvent` sau `_resolve`, `apply_guitar_wave`, humanize | Không | Golden artifact riêng |

`rendered` không nằm trong `TextureSpec`. Nó là file `rendered.json` hoặc hash, sinh từ một render thật.

`string`/`fret` là **metadata xác thực** trong `authored`, không phải field của `NoteEvent`. Chúng có mặt khi nguồn là tab hoặc khi Gemini đọc được tab; nếu không có, validation bỏ qua phần string/fret.

### 6.2. `NoteEvent` tương ứng

`NoteEvent` trong `model.py:121` có:

- `bar`, `beat`, `midi`, `duration_beats`, `voice`
- `staff`, `tie_start`, `tie_stop`, `slur_start`, `slur_stop`
- `accent`, `velocity`, `tenuto`, `staccato`, `hairpin`, `pinned`

Spec `authored` phải cover: `bar`, `beat`, `midi`/pitch, `duration_beats`, `voice`, `staff`, `tie_start/stop`, `slur_start/stop`, `accent`, `tenuto`, `staccato`.
Spec `authored` **có thể** cover thêm `string`, `fret`, `written_pitch`, `sounding_pitch` khi nguồn là tab; đây là metadata, không phải `NoteEvent`.
Spec `derived` cover: `velocity`, `hairpin`, `pinned`, dynamics.
Spec không cover: `Score.lead_wedges`, `support_wedges`, `dynamics`, `harmonies` — đây là artifact của render, không phải event.

### 6.3. Voice

Trong phạm vi guitar, voice thật có **1/2/3/4**:

- 1 = lead
- 2 = support
- 3 = bass/low
- 4 = Preludio upper middle (được `assert_playable` giữ riêng, không gộp vào 2)

Spec dùng `voice: 1|2|3|4`, không dùng `"lead"|"mid"|"bass"` làm runtime value. Có thể có `role` để hiển thị, nhưng `voice` là số.

**Scope**: đây là schema guitar-only. Các variant khác có thể dùng `voice=5, staff=2` (`daily_frame.py:459,483`); `render.py:1285` chỉ áp dụng một số luật cho `variant != "guitar"`. Texture Studio không mô hình hoá các voice đó.

### 6.4. Routing

Revision 1 viết `routing.regime: { voice: "bass", mode: "root_or_fifth" }`. Sai ngữ nghĩa:

- `Regime` trong code là **market regime** `uptrend/downtrend/sideway` (`regime.py`), dùng để chọn chord slot.
- Chỉ **Torroba** dùng regime để nghiêng bass bậc I (uptrend) hoặc V (downtrend): `_torroba_bass` (`guitar_torroba.py:223-255`).
- **Villa không đọc `regime_at`**. `guitar_villa.py` không có `regime`; `_villa_bass` lấy chord root. Vì vậy `bass_tilt` là field Torroba-only, không dùng cho target Phase 0–2.

Sửa thành:

```json
"routing": {
  "price":   { "voice": 1, "source": "_melody_at" },
  "volume":  { "voice": 2, "mode": "velocity_band", "source": "liquidity" },
  "bass":    { "voice": 3, "mode": "chord_root" },
  "density": { "voice": 2, "mode": "eighth_grid" },
  "bass_tilt": {
    "voice": 3,
    "mode": "degree_i_or_v",
    "source": "market_regime",
    "applies_to": ["torroba"]
  }
}
```

- `price` → voice 1 (hoặc voice 3 với `thumb_cantabile`).
- `volume` → velocity band của voice 2/3.
- `bass` → chord root; đây là hành vi Villa.
- `bass_tilt` → chỉ Torroba; nếu `applies_to` không chứa composer hiện tại, compiler bỏ qua và **không** thêm field vào spec Villa.
- `density` → grid dày/thưa.

### 6.5. Round-trip so gì

- So `authored`: cùng `bar`, `beat`, `duration_beats`, `voice`, `staff`, `midi`, tie/slur/accent/staccato; nếu có `string`/`fret` thì so thêm.
- Không so `velocity` tuyệt đối. Velocity do `apply_guitar_wave()` + `resolve_bar_volumes()` + liquidity + humanize quyết định; nó không thuộc spec.
- Nếu muốn so `rendered`, phải dùng **cùng price path, cùng volume path, cùng chord slots, cùng liquidity bands, cùng `params` hash, cùng `SPAN_REVISION`/`RECAP_REVISION`**. Khi đó so hash hoặc snapshot, không so ±2.
- Không có “humanize seed”. `humanize()` nhận `params`, `offset_at`, `fan_hold`; tính deterministic qua `_stable_unit`, cố ý không dùng `hash()`. Vì vậy cache/so sánh dùng `params` hash + `SPAN_REVISION`.
- `rendered` là golden artifact, không phải input của spec.

### 6.6. `assert_playable` không chứng minh spec playable

`assert_playable` chạy trên score **đã được repair** (`_resolve`, `_fit`, renderer sửa voicing trước khi ghi). Nó không chứng minh `authored` playable.

Cần thêm:

- `assert_authored_playable(authored, profile)`:
  - luôn kiểm: MIDI range, register guitar, voice order (`bass < mid < lead`), duration sum theo meter, không overlap cùng voice;
  - nếu có `string`/`fret`: string 1–6, `0 <= fret <= _MAX_FRET[string]`, pitch khớp string+fret, hand span ≤ 5, không trùng dây;
  - nếu không có `string`/`fret`: chỉ kiểm pitch/register/voice/duration; playability vật lý để `assert_playable` sau repair.
- `assert_playable(score, profile)`: kiểm tra output sau repair, như hiện tại.
- Publish yêu cầu cả hai; spec không có string/fret vẫn publish được nếu `assert_authored_playable` phần pitch/register pass.

### 6.7. Schema tối thiểu của `TextureSpec`

```json
{
  "id": "suite_mazurka",
  "composer": "villa",
  "kind": "pattern",
  "parent": null,
  "runtime": "code",
  "status": "draft",
  "suite": { "name": "Suite Popular Brasileira", "movement": 1 },

  "source": {
    "piece": "Suite Popular Brasileira — Mazurka-Choro",
    "bars": [1, 8],
    "image": "uploads/<sha256>.jpg",
    "crop": { "x": 120, "y": 340, "w": 900, "h": 420 },
    "notation": "standard+tab"
  },

  "profiles": {
    "render": "villa_pattern",
    "wave": {
      "floor_calm": 28,
      "floor_wide": 34,
      "ceil_calm": 58,
      "ceil_wide": 63,
      "snap_calm": 68,
      "snap_wide": 72,
      "per_phrase": 1,
      "per_sec": 3,
      "targets": "tresillo",
      "smooth": 3,
      "d_lo": -8,
      "d_hi": 8
    }
  },

  "meter_variants": [
    {
      "meter": {
        "id": "3/4",
        "beats": 3,
        "beat_type": 4,
        "eighths_per_bar": 6,
        "strong_eighths": [0],
        "subbar_breaks": [4],
        "extra_weights": [[4, 0.8]]
      },
      "materializer": "grid_3_4",
      "transform": "none",
      "figures": []
    }
  ],

  "authored": {
    "events": [
      {
        "bar": 0,
        "beat": 0.0,
        "duration_beats": 1.5,
        "voice": 1,
        "pitch": { "kind": "price", "source": "_melody_at" },
        "tie": "none",
        "slur": "none",
        "accent": true,
        "staccato": false,
        "staff": 1,
        "string": 1,
        "fret": 5
      },
      {
        "bar": 0,
        "beat": 0.0,
        "duration_beats": 1.0,
        "voice": 3,
        "pitch": { "kind": "chord_root" },
        "tie": "next_bar",
        "slur": "none",
        "accent": false,
        "staccato": false,
        "staff": 1
      }
    ]
  },

  "derived": {
    "velocity_band": { "voice": 1, "source": "liquidity" },
    "hairpin": "phrase",
    "humanize": "params"
  },

  "routing": {
    "price": { "voice": 1, "source": "_melody_at" },
    "volume": { "voice": 2, "mode": "velocity_band", "source": "liquidity" },
    "bass": { "voice": 3, "mode": "chord_root" },
    "density": { "voice": 2, "mode": "eighth_grid" }
  },

  "traits": {
    "kinetic": true,
    "narrow_rows": [6, 24, 80],
    "scale_host": false,
    "plucked": false,
    "loud_down": true,
    "has_door": false,
    "pedal_door": false,
    "figure_registry": "none"
  },

  "provenance": {
    "model": "gemini-3.5-flash",
    "prompt_version": "studio-v1",
    "schema_version": "texture-spec-1",
    "confidence": 0.82,
    "reviewed_by": "human"
  }
}
```

`profiles.wave` mirror đủ 12 field của `guitar_wave._profile()`; compiler dùng nó để sinh `PROFILES[("villa", id)]` và `_EXPECTED`. `profiles.render` map vào `_PROFILE`.

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
- `slice_score()` **cố ý** clear `tie_stop` ở `start` và `tie_start` ở `end - 1`. Vì vậy định nghĩa diff hợp lệ:
  - So tất cả note trong `[start, end)`.
  - Bỏ qua `tie_start`/`tie_stop` tại đúng hai biên.
  - Nếu tie vắt qua biên, ghi `preview_boundary_tie=true` và không coi là bug.
  - Mọi khác biệt khác (pitch/beat/duration/voice/staff/accent/staccato/slur) là bug.
- Tốt nhất là slice tại biên phrase không có tie vắt; nếu không được, dùng luật trên.

### 8.2. Audio, không phải MIDI

- App dùng `expo-audio`, không có MIDI player.
- Guitar audio đi qua `audio.py` → MuseScore.
- `EXPORT_SLOTS` mặc định 1 (`audio.py:61`), nên preview sẽ tranh slot với nút Nghe.
- Cần:
  - cache preview theo `SPAN_REVISION`/`RECAP_REVISION` + `params` hash + `candle_count` + `ensemble` + `instrument` + tempo + sample rate;
  - TTL như `AUDIO_MAX_AGE_DAYS`;
  - hàng đợi riêng hoặc `VSTOCK_MUSESCORE_SLOTS` tăng cho Studio;
  - UI hiển thị “đang chờ MuseScore” thay vì treo.
- Không hứa “MIDI nhẹ” khi app không có MIDI player.
- Không dùng “humanize seed”: cache dùng `cache_mark(values)` như `audio.py`.

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

### 9.5. Validate sau Gemini

Trước khi lưu `draft`:

- Tổng trường độ mỗi ô khớp `MeterSpec`.
- `tie_start`/`tie_stop` có đầu có cuối; `slur_start`/`slur_stop` có đầu có cuối.
- `written_pitch` và `sounding_pitch` lệch đúng 12 nửa cung, trừ khi capo/scordatura được khai.
- Nếu có `string`/`fret`: string 1–6, `0 <= fret <= _MAX_FRET[string]`, pitch khớp string+fret, hand span ≤ 5.
- Không có hai nốt cùng voice chồng nhau.
- Voice order: bass < mid < lead (trừ texture khai đảo vai).
- Nốt confidence thấp phải được đánh dấu, không tự nhận.
- `conflict=true` giữa phổ và tab phải có quyết định của người.

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

Không được viết “backend vẫn kiểm tra quyền” nếu chưa có owner check. Revision 2/3 nói rõ: Phase 1 có owner check theo session, chưa có auth.

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
│                  │                   │ bass → voice 3        │
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
- `VSTOCK_STUDIO_DB_PATH` mặc định `${VSTOCK_DB_PATH.parent}/musicalize_studio.db` (tức `/data/musicalize_studio.db`), hoặc dùng chung `/data/vstock.db` với schema riêng.
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

### 11.3. Backend layout và API

```
backend/app/routers/musicalize_studio.py
backend/app/studio/
  __init__.py
  schema.py       # MeterSpec, TextureSpec, AuthoredEvent, ...
  store.py        # SQLite + file upload + owner/session
  vision.py       # prompt + Gemini parse (reuse gemini client)
  validate.py     # meter, figure parent, authored playable
  compiler.py     # fixture, registration, registry patch
  preview.py      # slice_score + audio queue
  export.py       # bundle export
```

Prefix: `/v1/musicalize/studio`.

| Method | Path | Việc |
|---|---|---|
| `GET` | `/access` | Capability cho Studio |
| `POST` | `/uploads` | Upload ảnh (multipart) |
| `POST` | `/analyze` | Ảnh + crop + metadata → Gemini draft |
| `GET` | `/specs` | Danh sách spec |
| `POST` | `/specs` | Tạo spec |
| `GET` | `/specs/{id}` | Đọc spec |
| `PUT` | `/specs/{id}` | Lưu spec |
| `DELETE` | `/specs/{id}` | Xoá spec nháp |
| `POST` | `/specs/{id}/validate` | Validate |
| `POST` | `/specs/{id}/preview` | Render preview |
| `POST` | `/specs/{id}/export` | Xuất bundle |
| `GET` | `/exports/{id}` | Tải bundle |
| `GET` | `/previews/{id}` | Nghe preview |

Tất cả endpoint (trừ `/access`) đọc `X-Studio-Session`, resolve `owner_id`, kiểm tra `visibility`, và áp quota.

### 11.4. DDL tối thiểu

```sql
CREATE TABLE IF NOT EXISTS studio_uploads (
  id TEXT PRIMARY KEY,
  sha256 TEXT NOT NULL,
  path TEXT NOT NULL,
  width INTEGER,
  height INTEGER,
  owner_id TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS studio_specs (
  id TEXT PRIMARY KEY,
  composer TEXT NOT NULL,
  kind TEXT NOT NULL,
  parent_id TEXT,
  status TEXT NOT NULL,
  owner_id TEXT NOT NULL,
  visibility TEXT NOT NULL DEFAULT 'private',
  json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_studio_specs_owner
  ON studio_specs(owner_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_studio_specs_composer
  ON studio_specs(composer, status);
```

`studio_exports` có thể là bảng hoặc chỉ là thư mục; Phase 1 dùng thư mục `/data/studio/exports/<id>/`.

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
- `backend/app/sonify/guitar_patterns.py`: `_PEDAL_DOOR_PROFILE`.
- `backend/app/sonify/guitar_frame.py`: `_RETAINED_DOORS` (không phải `guitar_patterns.py`).
- `backend/app/sonify/guitar_torroba.py`: `_REAL_TORROBA_FIGURES` nếu figure mới.
- `backend/app/sonify/guitar_wave.py`: `PROFILES[("villa", id)]` sinh từ `profiles.wave`.
- `backend/app/sonify/guitar_patterns.py`: `_PROFILE[id]` sinh từ `profiles.render`.
- `backend/tests/test_guitar_wave.py`: `_EXPECTED`.
- Tests hardcode id: `test_humanize.py`, `test_sonify_guitar.py`, `test_sonify_guitar_scale_passages.py`.
- `backend/app/sonify/audio.py`: nếu preview/export.
- `backend/tests/test_texture_meter_matrix.py` + fixture `meter_matrix.json`.
- `backend/tests/test_texture_movement_line.py`: 5 pattern Suite không làm vỡ `pattern_form()`.

---

## 13. Lộ trình

### Phase 0 — Chứng minh schema, chưa UI, chưa Gemini

- `schema.py` với `MeterSpec` (6 field), `authored/derived`, `profiles`.
- `resolve_runtime_meter()` dùng chung; cấm `active_meter()` ngoài `compose_meter`.
- `validate.py`: meter variants, figure parent, voice order, authored playable.
- Spec tay cho `chord_melody` (dễ) và `villa_pattern` (khó).
- Round-trip `authored` với renderer hiện tại.
- Preview bằng `slice_score` + `audio.py` (nếu môi trường có MuseScore), hoặc `rendered.json` nếu chưa.
- Sinh `meter_matrix.json` + `test_texture_meter_matrix.py`.
- **Không sửa runtime**: Studio từ chối spec 12/8; runtime giữ hành vi hiện tại. Ghi rõ đây là known bug, fix ở Phase 3.

**Gate**: round-trip đúng; meter gate âm tính; matrix đầy đủ; Studio từ chối 12/8; không có thay đổi runtime.

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
- Suite là palette pattern; test movement line với 5 pattern (tối đa 3 title).
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

1. **Meter exact**: spec lưu đủ 6 field `MeterSpec`; so canonical tuple, không so `id`/string.
2. **Meter sau retarget**: spec khớp `resolve_runtime_meter()` sau `_guitar_meter` + `retarget_torroba_meter`; compiler không gọi `active_meter()` ngoài `compose_meter`.
3. **12/8**: Studio từ chối spec 12/8; runtime Phase 0/1 **không đổi**. Phase 3 mới sửa fallback `"other"` → 4/4 hoặc thêm materializer 12/8.
4. **Không meter per-bar**: không dùng `kind_at` làm meter.
5. **Figure parent**: figure không có parent/meter hợp lệ bị từ chối; `figure.meter` phải thuộc variant list.
6. **Authored round-trip**: cùng pitch/beat/duration/voice/staff/tie/slur/accent/staccato; nếu có string/fret thì so thêm.
7. **Rendered golden**: cùng input + `params` hash + `SPAN_REVISION`/`RECAP_REVISION` → cùng hash/snapshot; velocity không so tuyệt đối; không có “humanize seed”.
8. **Preview = slice_score**: preview lấy từ render thật; diff hợp lệ chỉ ở tie biên `start`/`end - 1`.
9. **Storage bền**: DB/upload/preview nằm trên `/data`, sống qua deploy; backup có.
10. **Publish artifact**: server không ghi repo; test data-driven.
11. **Session owner/quota**: không xoá/sửa spec của session khác; Gemini có quota.
12. **Codegen drift**: `gen_pattern_registry --check` + pytest gate.
13. **Title uniqueness**: không trùng title toàn cục.
14. **Runtime proof**: ít nhất một pattern `runtime: "interpreter"` ở Phase 2.
15. **Movement line**: 5 pattern Suite không làm vỡ `pattern_form()`; tối đa 3 title; test in tên.
16. **API/storage contract**: 13 endpoint + DDL + post-Gemini validate có trong doc và test.
17. **Meter matrix**: `pattern × meter` fixture đầy đủ; cặp `"other"`/rỗng fail.

---

## 15. Rủi ro

| Rủi ro | Cách giảm |
|---|---|
| 12/8 fallback 4/4 | Phase 0 Studio từ chối spec 12/8; runtime không đổi; Phase 3 sửa |
| 3/4 ↔ 6/8 khác accent | `accent_remap` tường minh + `extra_weights`, nghe thử |
| 4/4 → 12/8 không tương đương | `triplet_subdivision` + duyệt tay; không tự động |
| 2/4 không có trong engine | `fold: 2` ở `FormSpec`; tiền lệ `galop`; test bars/DFI |
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
2. **12/8 xử lý thế nào ở Phase 3?**
   (a) bỏ choice khỏi `params.py` + regenerate `paramsSchema.generated.ts`; (b) thêm materializer 12/8 thật; (c) `triplet_subdivision` có duyệt tay. Phase 0/1 chỉ từ chối spec 12/8, không sửa runtime.
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

### B.1. Review 1

| Review | Trạng thái trong revision 2/3 |
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

### B.2. Review 2

| Review 2 | Trạng thái trong revision 3 |
|---|---|
| 1.1 key meter bằng structure, không string | §4.2, §4.4 |
| 1.2 membership thay equality | §3.1, §4.5 |
| 1.3 preview cắt tie ở biên | §8.1 |
| 1.4 string/fret trong authored | §6.1, §6.2, §6.6 |
| 1.5 12/8 không đổi runtime | §4.4, §13 Phase 0, §14.3 |
| 1.6 không có humanize seed | §6.5, §8.2 |
| 2.1 `extra_weights` | §4.2 |
| 2.2 `bass_tilt` Torroba-only | §6.4 |
| 2.3 `_RETAINED_DOORS` đúng file | §12.4 |
| 2.4 `waltz` là title | §3.2 |
| 2.5 voice 1–4 guitar-only | §6.3 |
| 2.6 cache thiếu revision | §8.2 |
| 3.1 movement line | §3.3, §13 Phase 2, §14.15 |
| 3.2 `active_meter()` default | §4.3, §14.2 |
| 3.3 materializer code-backed | §4.5.1, §14.17 |
| 3.4 `fold: 2` thuộc FormSpec | §4.4.1 |
| 3.5 API/DDL/validate bị bỏ | §9.5, §11.3, §11.4 |
| 3.6 profile/wave profile | §6.7, §12.4 |

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
