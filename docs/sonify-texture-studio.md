# Texture Studio — thư viện texture guitar trong Musicalize

> **Trạng thái**: **sentence authoring MVP đã code** (JSON `SentenceSpec`, validate/preview/audio/publish/rollback, UI Studio) + **Phase 0 schema core** (`MeterSpec`/`TextureSpec` validator) + **sentence-level selection/render matrices** + **compiler bundle JSON** + **upload/Gemini draft/session quota**.
> **Phạm vi đã code**: Torroba/Sor (5 pattern, 38 spec) + candidate preview-only Villa/Barrios/Brouwer; Barrios có production path sau flag default-off. Bach exposition mới có preview prototype.
> **Nơi chạy**: trong app Musicalize (room Studio), backend FastAPI phía sau.
> **Auth:** chưa có. `X-Studio-Session` + `owner_id` + quota upload/analyze đã có; sentence specs cũng đã có `owner_id` + `visibility private/public` (publish/list/get/rollback/export scoped, private foreign id → 404). Đây vẫn là namespace, không phải auth.
> **Liên quan**: [`sonify-guitar-model.md`](./sonify-guitar-model.md), [`sonify-classical-guitar.md`](./sonify-classical-guitar.md), [`sonify-pattern-names.md`](./sonify-pattern-names.md), [`sonify-guitar-torroba-plan.md`](./sonify-guitar-torroba-plan.md), [`sonify-guitar-torroba-castillos-frames.md`](./sonify-guitar-torroba-castillos-frames.md).

---

## 0. Sentence MVP đã code

Pilot **Torroba + Sor**, chạy trên nhánh `v2` (chưa merge `main`):

| Mảng | Đã có |
|---|---|
| JSON | `backend/app/studio/specs/*.json` — 7 file / 38 spec, wrapper `{schema_version, runtime: "code", specs}` |
| Export | `python3 -m app.studio.export` và `--check` (stale detector) |
| Compiler | `POST /v1/studio/sentence/export` + `.../specs/{id}/export`; bundle JSON `spec/fixture/rendered/registration`, **không ghi file** từ server |
| Loader | `sentence_specs.load_specs(path, replace=False)`; reload giống hệt là no-op, đổi spec cần `replace=True` |
| Validate | `POST /v1/studio/sentence/validate` → `{ok, errors: [{path, message}]}`; dispatch theo pattern (Torroba/Sor, Villa, Barrios, Brouwer) |
| Preview | `POST /v1/studio/sentence/preview` body `{spec, fixture}` → plan/row/notes/renderHash/matrix; cùng một response shape cho mọi family |
| Examples | `GET /v1/studio/sentence/examples[/{pattern}]` trả spec đã commit (38 Torroba/Sor + 3 candidate) để UI không copy JSON tay |
| Publish | `POST /v1/studio/sentence/publish`, `GET .../specs`, `GET .../specs/{id}`; SQLite `studio_sentence_specs`, version tăng theo `(pattern, meter)` |
| Rollback | `POST .../specs/{id}/rollback`: validate lại payload cũ rồi republish thành version mới, `rollbackOf` = id nguồn; row cũ bất biến, không xoá/sửa |
| Audio | `POST /v1/studio/sentence/audio` → WAV ngắn (synth code-only, cache theo `renderHash`); `GET .../audio/{key}.wav` |
| Procedure | `Slot.procedure` + `PROCEDURES` + JSON round-trip; production chỉ chạy `bach_imitation`; `bach_exposition` có **preview-only** module + test, **chưa có endpoint/UI** (examples API bỏ qua procedure candidate) |
| Candidates | **Villa** `villa_arpeggio_aba`, **Barrios** `barrios_cathedral_period`, **Brouwer** `brouwer_etude_noviembre_aba`; preview-only, đi qua endpoint chung. Barrios có thêm production path sau flag `VSTOCK_BARRIOS_PERIOD` (default off) |
| UI | Studio room: JSON editor, Validate, Preview, Play preview (web), Publish + version list, Rollback inline; examples từ API; **upload/xoá ảnh (web) + crop web + Gemini draft + notes table + TextureSpec draft panel/validate**; analyze cũ bị abort khi đổi ảnh (native picker chưa) |
| Vision/session | `GET /v1/musicalize/studio/access`, `POST /uploads`, `GET /uploads/{id}?t=`, `DELETE /uploads/{id}`, `POST /analyze`; `X-Studio-Session` → `owner_id`, quota/ngày, blob dedupe, signed media token |
| Schema | `app/studio/texture_spec.py`: `MeterSpec`, `PitchRef`, `AuthoredEvent`, `MeterVariant`, `TextureSpec`, validator offline (per-voice duration, publish gate) |
| Matrix | `tests/guitar_fixture.py` + `sentence_selection_matrix.json` (2.016 dòng) + `pattern_selection_matrix.json` (39 row) + `render_matrix.json` (41 row); pattern-level matrix có 1 `expected_empty` có lý do |
| Sandbox | Preview plan/render trong `sentence_specs.use_registry` (ContextVar) trên **bản copy registry**; không mutate `SENTENCE_SPECS` |
| Runtime | Vẫn code-backed; `runtime` bắt buộc `"code"`; không interpreter |

Fixture preview: `pattern`, `meter`, `length` (hoặc `run_length` cho cell/cycle), `n`, `closes`, `rise`, `bars`, `character`, `mode`, `bpm`, `profile`, `matrix`. Render tối đa 16 bar; matrix mặc định 288 dòng, chỉ dòng fixture có `renderHash`.

**Chưa làm:** wire Villa/Brouwer vào production plan (Barrios đã có flag off), Bach exposition **production** (mới có preview prototype), Phase 2 interpreter, Suite Popular Brasileira, `texture_registry.py`, native picker/crop, preview queue. TextureSpec draft đã apply/validate offline nhưng chưa render/register/publish.

### 0.1. Đối chiếu nhanh với proposal trong thân bài

| Vùng | Code hiện tại | Proposal trong doc |
|---|---|---|
| Sentence | `app/studio/sentence_spec.py`: `id/pattern/meter/select/span/slots`, JSON round-trip | §13 sentence pipeline — ✅ khớp |
| `TextureSpec` | **Schema + validator** trong `app/studio/texture_spec.py`; authoring runtime vẫn là `SentenceSpec` | §6 `authored/derived/rendered`, pitch resolution, `assert_authored_playable` — **một phần** |
| Meter | `MeterSpec` 6 field + canonical key đã có; sentence registry vẫn dùng `meter` string | §4 `resolve_runtime_meter`, materializer/12-8 policy — **chưa** |
| Validation | Validator theo family + fixture bounds + procedure refusal | §4/§6 validator đầy đủ — **một phần** |
| Preview | Render bounded `_Ctx` bằng realizer thật | §8.1 `slice_score` của render đầy đủ — **khác thiết kế** |
| Audio | Synth code-only 22.05 kHz, 96 BPM, cache theo `renderHash` | §8.2 MuseScore + global queue — **chưa** |
| Publish | SQLite version bất biến + rollback `rollbackOf`; compiler trả bundle JSON | §11 PR automation + `preview.wav` — **chưa** |
| UI | Studio pill, editor, validate/preview/audio/publish/rollback, examples, upload/crop ảnh web, Gemini draft + notes table, TextureSpec draft/validate | §10 native picker/crop, apply SentenceSpec — **chưa** |
| Candidates | Villa/Barrios/Brouwer preview; Barrios flag off; Bach exposition preview | §3.2 Suite 5 movement + §13 Phase 2 — **chưa** |
| Matrix/codegen/registry | Sentence + pattern + render matrix; registry codegen + `PATTERN_NAMES` derived; `texture_registry.py` chưa | §7.2 — **một phần** |
| Session/quota | `X-Studio-Session`, `owner_id`, access/quota upload/analyze, signed media token, spec `owner_id`/`visibility` + scoped publish/list/get/rollback/export | preview queue — **một phần** |
| Runtime | Code-backed; không interpreter | §1.1 Phase 2/3 — **chưa** |

Đọc thân bài: mọi câu “Đề xuất/Phase/Gate” là **kế hoạch**, không phải mô tả code hiện tại. Chỉ §0, §13.1–13.5 (sentence) và §13.6 (Barrios flag) phản ánh code hôm nay.

---

## 0. Revision 3–4 sửa gì

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
| Materializer code-backed chỉ là lời khai | Thêm **selection matrix + render matrix** làm artifact Phase 0 |
| `fold: 2` nằm trong materializer | `fold` thuộc `FormSpec`/`SourceForm`, quyết định trước khi author |
| Rev2 bỏ API table, DDL, post-Gemini validate | Khôi phục đầy đủ |
| Spec thiếu profile/wave profile | Thêm `profiles.render` + `profiles.wave` |

### 0.1. Revision 4 sửa gì (sau review 3)

| Vấn đề revision 3 | Cách sửa trong revision 4 |
|---|---|
| Ma trận `pattern × meter` không chạy được | Tách **selection matrix** và **render matrix**; fixture chung `guitar_fixture.py`; thêm `unsupported` |
| Cộng duration tất cả voice | **Per-voice** duration; guitar có 3–4 voice |
| `pitch.source: "_melody_at"` | Declarative `kind` (`price`, `chord_degree`, `literal_midi`…), cấm tên hàm Python |
| Checklist tham chiếu mục đã xoá | Chép lại checklist đầy đủ vào §12.4 |
| Thiếu `selection`/`family` | Thêm `traits.family` + `selection`; test dead code |
| Thiếu confidence/conflict/review | Thêm metadata vào authored event; publish chặn `pending` |
| `accent_remap` sai tầng | Bỏ khỏi pattern transform; `_guitar_meter` là form-level |
| DDL PK toàn cục, thiếu ảnh, media không header | UUID + `UNIQUE(owner_id, slug)`; `GET /uploads/{id}`; signed media token |
| Registry không version gate | Allowlist schema, `renderer_version`, fail-soft |
| `METER_34` snippet thiếu `extra_weights` | Sửa snippet |
| `_MAX_FRET[string]` off-by-one | `_MAX_FRET[6 - string]` |
| Title test enumerate sai | Enumerate từ `_FAMILY` × palette, filter rỗng |
| `visibility` mơ hồ | `private` mặc định; `public` sau publish |
| `/access` thiếu shape/quota/telemetry | Thêm `StudioAccess` + quota + event list |
| `resolve_runtime_form()` vô chủ | Ghi rõ owner `span.py`/`FormSpec`, chạy trước khi dựng form |

### 0.2. Revision 5 sửa gì (sau review 4)

| Vấn đề revision 4 | Cách sửa trong revision 5 |
|---|---|
| Title uniqueness fail trên `main` | Đổi thành **coverage test**; uniqueness chỉ theo ensemble; 4 title trùng toàn cục là hợp lệ |
| `pitch: price` không resolve tất định | Đổi thành `melody_eighth` (index vào melody đã render); spec không sở hữu price→melody |
| Checklist thiếu `guitar_villa.py` | Thêm renderer file vào đầu checklist |
| `selection` nói “sinh nhánh” nhưng runtime không codegen | Chốt: compiler sinh **matrix + checklist**, người sửa `_select_body`; matrix là gate |
| `source.image` là path | Đổi sang `source.upload_id`; resolve path sau owner check |
| Fixture thiếu `first_body`/`previous`/`section` | Thêm vào `pattern_case()` |
| Ví dụ `calm → suite_valsa` sai code hiện tại | Ghi rõ là kỳ vọng **sau patch**, không phải behavior hôm nay |
| Preview concurrency chỉ per-session | Thêm **global Studio queue** + render ngoài event loop |
| `review` default chặn spec nhập tay | Gemini = `pending`; người nhập = `edited` |
| `parent_id`/upload dedupe mơ hồ | `parent_slug`; `studio_blobs` + refcount |
| P2 nhỏ | Bỏ “hoặc form_resolve.py”; codegen dùng `PROFILES`; render matrix key; thêm `written/sounding_pitch` example |

### 0.3. Revision 6 sửa gì (sau review 5)

| Vấn đề revision 5 | Cách sửa trong revision 6 |
|---|---|
| `melody_eighth` làm round-trip pitch thành vòng tròn | Hạ pitch resolution xuống `derived`; authored round-trip chỉ kiểm **placement + pitch reference**; cao độ tuyệt đối do **golden render hash** kiểm |
| §1 gọi spec là “nguồn chân lý” quá rộng | Đổi thành nguồn chân lý cho **placement/voice/routing/meter/selection**, không phải cao độ tuyệt đối |
| Chỉ cảnh báo `melody_eighth` thiếu context | Nói rõ **toàn bộ pitch layer** là render-context-relative; chỉ `literal_midi` standalone |
| Validate tưởng offline được | Validate dùng **cùng render executor** với preview; thiếu melody context trả `partial: true` + `skipped_checks` |
| `melody_eighth.offset` clamp | Out-of-range là **validation error**, không clamp |
| Preview pending không có status | `GET /previews/{id}` trả 404/409/200 theo trạng thái |
| Upload refcount chưa có luật xoá | `DELETE /uploads/{id}` trả 409 nếu còn spec trỏ tới; refcount chỉ giảm khi spec xoá |
| Coverage probe `"classic"` | Lặp qua ensemble sở hữu pattern; chỉ fallback `"classic"` cho `_FAMILY`-only |

### 0.4. Từ vựng chuẩn

Revision 1–6 dùng `pattern` và `figure` với nghĩa quá tải. Từ revision 7 (chưa sửa toàn văn), từ vựng chuẩn lấy từ [`sonify-guitar-model.md`](./sonify-guitar-model.md):

| Từ trong doc này (rev 1–6) | Trục chuẩn | Ghi chú |
|---|---|---|
| `pattern` | **scheduler slot** | vẫn giữ làm id; khai thêm `level` (`topic` / `texture`), `name_source` và `texture` |
| Hình thức in ra của movement | **Movement** (level trên pattern) | `PreparedMovement` + `FormSpec` + plan + `title`; 1D = 1 movement/1 pattern, 1W = 1 movement/N pattern, 1M = 4 movement |
| Hình thức in ra của pattern | **Topic** | tên tác phẩm/chương/thể loại/điệu; **không** phải kỹ thuật |
| `figure` | **Sentence** | template nhiều ô, có vai hình thức (walk/cadence, arada/float, period 4+4) |
| “variation bên trong pattern” | **Texture** (+ `cells`) hoặc **Plan** | không phải một lớp riêng |
| `meter_variants` | **Texture materialization** | meter là per-render, không phải pattern |
| `selection`, `_select_body`, `_contrast_pattern` | **Plan** | không phải hình thức của pattern |
| `form` | **Movement** (`FormSpec.sections` + Plan) | không phải thuộc tính của pattern |

Hai hệ quả bắt buộc khi implement:

1. `FigureSpec` trong doc này đọc là **`SentenceSpec`**; `figure_code` là id của texture trong slot.
2. Một pattern chỉ được in tên nếu `level` là `topic`; `level: texture` thì không in. Tên chương thuộc `Movement.title`, **không** phải pattern — guitar đã có field này (`movement_titles.py`), và `formDescription` giữ A–B–A không in (xem [`sonify-guitar-model.md`](./sonify-guitar-model.md) §2.1, §8).
3. Field đã đổi tên trong doc: `FigureSpec`→`SentenceSpec`, `meter_variants[].figures`→`sentences`, `selected_figure`→`selected_sentence`, `traits.figure_registry`→`traits.sentence_registry`. **Slot realizer vẫn map vào `_FIGURES` int** (`figure` trong slot, không phải `sentence_code`). Code hiện tại vẫn dùng `figure`/`_FIGURES` — đổi code là PR riêng, không trộn vào PR này.
4. Inventory **39 dòng** = 38 dòng `PROFILES` + `pedal` (`level` / `topic` / `texture` / `procedure` / `sentence`) và các quyết định tên: [`sonify-guitar-model.md`](./sonify-guitar-model.md) §8, §12, §13.

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
TextureSpec (JSON) — nguồn chân lý cho placement/voice/routing/meter/selection
    ↓
compiler: preview, fixture, registry, checklist
    ↓
renderer hiện tại (Phase 0/1) hoặc interpreter (Phase 2)
```

Điểm cốt lõi: **ảnh bản nhạc chỉ là ví dụ, không phải spec**. Engine không phát lại một bản nhạc cố định; nó biến chuỗi giá/volume thành nốt. Artifact trung tâm là **quy tắc ánh xạ**, không phải bản phiên âm.

Spec **không sở hữu cao độ tuyệt đối**. Pitch của voice 1 là kết quả của `_melody_scale → register → _choose_shifts → _place_melody`; spec chỉ tham chiếu (`melody_eighth`) hoặc ghi quan hệ (`chord_degree`, `scale_step`, `literal_midi`). Vì vậy:

- Authored round-trip kiểm **placement + pitch reference**, không kiểm absolute MIDI.
- Cao độ tuyệt đối do **golden render hash** kiểm với cùng render context.
- Nếu spec dùng `literal_midi`, pitch mới thực sự standalone và có thể so trực tiếp.

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
| Đơn vị | **Sentence nằm trong pattern**. Pattern/sentence đều có meter riêng và chỉ được gọi khi khớp |
| Nơi chạy | **Trong app Musicalize**, backend FastAPI + UI trong app |
| Quyền | **Mở cho tất cả bây giờ**, chưa cần login; có session namespace để sau này giới hạn |
| Đầu vào | **Ảnh phổ + tab** |
| Runtime | Code-backed mặc định; interpreter chỉ ở Phase 2 cho pattern được chọn |

### 3.1. Hệ quả của “sentence nằm trong pattern”

```
Composer
└── Pattern
    ├── meter variant A
    │   ├── base grid
    │   ├── Sentence A1
    │   └── Sentence A2
    ├── meter variant B
    │   ├── base grid
    │   └── Sentence B1
    └── Door (intro/outro)
```

- Scheduler không bao giờ chọn sentence trực tiếp. Nó chọn pattern trước, rồi trong pattern mới chọn sentence.
- **Mỗi pattern khai `level`**: `topic` (tự đứng tên, in ra) hoặc `texture` (kỹ thuật, không in). **Movement là level trên pattern**, không phải một giá trị `level` (xem [`sonify-guitar-model.md`](./sonify-guitar-model.md) §2.1, §8.1).
- Sentence không có tên in trên chart, không có `_PATTERN_TITLE`, không vào `PATTERN_NAMES`.
- Pattern có meter riêng; sentence cũng có meter riêng.
- **Điều kiện gọi**: meter của pattern phải khớp meter runtime; sentence `meter` phải **thuộc** danh sách `meter_variants` của pattern, so bằng canonical key (không so string, không so `id`).
- Mỗi cặp `(pattern, meter)` phải có **materializer** tường minh. Không có base grid ngầm.

### 3.2. *Suite Popular Brasileira* — danh sách movement

Năm movement, nhưng trong engine chúng là **pattern thuộc palette Villa**, không phải 5 movement của một piece. Cột nhịp là nhịp **cần đối chiếu lại với bản nhạc** trước khi khoá spec.

| Movement | Nhịp engine (audit) | Id đề xuất | Tên in đề xuất |
|---|---|---|---|
| Mazurka-Choro | `METER_34` — chắc chắn | `suite_mazurka` | Mazurka-Choro |
| Schottish-Choro | `METER_44` sau `fold: 2` từ 2/4 — **chưa chắc** | `suite_schottish` | Schottish-Choro |
| Valsa-Choro | `METER_34` — chắc chắn | `suite_valsa` | Valsa-Choro |
| Gavotta-Choro | `METER_44` — pickup/bar 0 **chưa chắc** | `suite_gavotta` | Gavotta-Choro |
| Choros No. 1 | `METER_44` tạm — 2/4 vs 4/4 **chưa chốt** | `suite_choros1` | Choros No. 1 |

Audit data-only: `backend/app/studio/villa_suite_audit.py` + `tests/test_villa_suite_audit.py`. Đề xuất movement đầu: **Mazurka-Choro 3/4**; chưa có candidate JSON/pattern registration.

Quy tắc tên:

- Dùng **tên đầy đủ của movement**, không dùng `Mazurka`, `Valsa`, `Gavotta` trần.
- `PATTERN_NAMES` trong `src/sonify/program.ts` là `ReadonlySet<string>` derive từ registry `level=topic`; `isPatternForm` chỉ kiểm **membership**. Trùng title giữa hai nhà là **vô hại**: Set collapse, không “nhận nhầm pattern của nhà khác”.
- Hiện đã có 4 title trùng toàn cục và chúng **hợp lệ**: `Cantabile` (classic/barrios), `Etude` (classic/villa/brouwer), `Prelude` (villa/bach/barrios), `Sarabande` (bach/brouwer). Không đổi tên các pattern đang chạy.
- Lý do dùng tên đầy đủ `Mazurka-Choro`, `Valsa-Choro`, `Gavotta-Choro` là **thẩm mỹ + luật trong `docs/sonify-pattern-names.md`**, không phải vì TS nhận nhầm.
- Test đúng: **coverage** (mọi pattern có title không rỗng) + **uniqueness theo ensemble** (trong cùng một palette không trùng).
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
- Nếu sau này muốn Suite là một piece 5 movement, đó là việc của `span.py`/`FormSpec`/`Movement.title` (`movement_titles.py`), không phải pattern. Mở một PR riêng.

Hệ quả cần test:

1. Một piece Villa dùng 5 pattern Suite không làm `pattern_form()` vỡ; nó in tối đa 3 title.
2. `Movement.title` (qua `formatMovement`) vẫn in đúng nhịp/BPM của slot.
3. `PATTERN_NAMES` nhận cả 5 title.
4. Không có test nào giả định guitar có 5 movement slot.

---

## 4. Meter: mô hình đúng

> **Trạng thái code:** `MeterSpec` 6 field + canonical key **đã có**; `app/studio/meter_runtime.py` có `resolve_runtime_meter()` (dùng thật `_guitar_meter` + `retarget_torroba_meter`), `resolve_meter_variant()` và chain check. Runtime vẫn không đổi; `SentenceSpec` vẫn dùng `meter` string, 12/8 fail-closed trừ variant `triplet_subdivision` được duyệt. Việc sửa fallback 12/8 trong runtime vẫn là Phase 3.

### 4.1. Thực tế trong code

`form.py` có nhiều meter thật:

```python
METER_44  = Meter(4, 4, 8,  (0, 4), (4,))
METER_34  = Meter(3, 4, 6,  (0,),   (4,), ((4, 0.8),))
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
- 12/8 trả `"other"`. `_torroba_primary` fallback `table.get(ctx.kind, table["4/4"])`, nên 12/8 chạy như 4/4 (Olite). Sentence 4/4 không bắn vì `_castillo_spans` gate `kind == "4/4"`. Đây là bug runtime, không phải hành vi để spec bắt chước.
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
- `sentence.meter` là một `MeterSpec`; nó phải **thuộc** `parent_pattern.meter_variants` theo canonical key.

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
    "unsupported": false,
    "sentences": ["walk", "cadence"]
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
    "unsupported": false,
    "sentences": ["arada", "float"]
  }
]
```

Các loại chuyển đổi được phép:

| Nguồn → đích | Điều kiện | Transform | Ghi chú |
|---|---|---|---|
| 4/4 → 12/8 | 8 → 12 eighth | `triplet_subdivision` | Không tự động; cần nghe thử và duyệt |
| Meter khác | 5/4, 6/4, 7/8… | `none` | Fail closed nếu không có materializer |

`3/4 ↔ 6/8` **không** phải pattern transform. `_guitar_meter()` (`span.py:288`) hoán đổi 3/4 ↔ 6/8 ở tầng form, vô điều kiện cho guitar, trước khi pattern được chọn. Pattern không bao giờ thấy meter “kia”. Vì vậy mỗi meter là một variant riêng; không khai `accent_remap` trong spec. Nếu cần đổi accent, khai `strong_eighths`/`extra_weights` của variant đó.

`fold: 2` **không** nằm trong bảng này. Gộp hai ô 2/4 thành một ô 4/4 đổi `bars`, `bar_beats`, BPM và mapping day ↔ bar, nên nó thuộc `FormSpec`/`SourceForm`, quyết định **trước** khi author spec. Xem §4.4.1.

Quy tắc:

1. Không có `transform` tường minh thì không được gọi pattern/sentence ở meter đó.
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

Nơi đặt: `backend/app/sonify/span.py` (cùng chỗ `_guitar_meter`/`retarget_torroba_meter`). **Owner là `span.py`/`FormSpec`**, không phải pattern. `resolve_runtime_form()` chạy **trước** khi `FormSpec` được dựng; pattern chỉ nhận meter đã fold.

Pattern không thấy 2/4; nó chỉ thấy 4/4 sau fold. Test bắt buộc: độ dài movement, số bar, DFI window, và tiền lệ `galop` (`guitar_sor.py` `_galop1_cell`/`_galop2_cell`).

### 4.5. Validate meter

1. `pattern.meter_variants` không rỗng; mỗi phần tử có `MeterSpec` hợp lệ và `unsupported: boolean`.
2. Tập canonical key của `pattern.meter_variants` (trừ `unsupported: true`) ⊆ tập canonical key của `composer.meters`.
3. `sentence.meter` phải **thuộc** `parent_pattern.meter_variants` (canonical key), không phải “xấp xỉ”, không so `id`.
4. `sentence.parent` tồn tại; sentence không phải ứng viên cấp cao nhất.
5. Sentence chỉ được gọi khi pattern active **và** `meter_key(resolved_meter) == meter_key(sentence.meter)`.
6. Nếu pattern không có materializer cho `resolved_meter`, fail; không fallback.
7. Test âm tính: gọi sentence ở meter sai phải trả `[]` hoặc raise, không render.

### 4.5.1. Hai ma trận: selection và render

Với pattern `runtime: "code"`, `meter_variants` chỉ là lời khai. Không có hàm `render_pattern_for_test()` tách rời: render cần `_Ctx` đầy đủ (melody/raw/chord_at/phrases/bands/register/sections). Vì vậy phải tách **hai** artifact:

1. **Selection matrix** — `_select_body` / `_dominant_pattern` / `_castillo_spans` chọn pattern/sentence gì cho một input cố định.
2. **Render matrix** — pattern đã được chọn render ra note gì với một fixture `_Ctx` cố định.

#### Fixture dùng chung

Tạo `backend/tests/guitar_fixture.py`:

```python
def pattern_case(
    pattern: str,
    meter: Meter,
    *,
    ensemble: str,
    mood: str,
    band: str,
    bpm: int,
    bars: int = 8,
    first_body: bool = True,
    previous: list[str] | None = None,
    section=None,
) -> tuple[_Ctx, list[Phrase]]:
    ...
```

`_select_body(ctx, phrase, *, first_body, previous, section)` cần đúng ba tham số này; thiếu chúng thì không dựng được selection matrix. Fixture phải expose cả ba.

- Chuyển `_many` / `_ctx` copy-paste từ `test_sonify_guitar_torroba.py`, `test_guitar_wave.py`, `test_sonify_guitar_scale_passages.py`, `test_torroba_lowered_melody.py` lên đây.
- Fixture phải deterministic: price path, chord slots, phrases, bands, regime, seed đều cố định.
- Không có `conftest.py` hiện tại; thêm `backend/tests/conftest.py` chỉ để export fixture, không chứa logic ẩn.

#### Selection matrix

```json
{
  "phase": "after_patch",
  "note": "Hôm nay Villa calm trả chord_melody; đây là kỳ vọng sau khi patch _select_body.",
  "input": {
    "ensemble": "villa",
    "mood": "calm",
    "band": "mp",
    "bpm": 100,
    "meter": "3/4",
    "phrase_bars": 8,
    "first_body": false,
    "previous": ["chord_melody"],
    "section": { "trio": false, "bridge": false }
  },
  "selected_pattern": "suite_valsa",
  "selected_sentence": null,
  "ctx_kind": "3/4"
}
```

- Sinh `backend/tests/fixtures/selection_matrix.json`.
- Test: mỗi spec pattern phải xuất hiện ít nhất một lần trong matrix; nếu không, pattern là dead code.
- `ctx_kind == "other"` là fail cho variant được khai là supported.
- Không dùng `notes != "other"`; `"other"` là `ctx.kind`, không phải output note.
- Entry có `phase: "after_patch"` là **kỳ vọng sau Phase 2**, không phải behavior hôm nay; matrix hiện tại phải tách khỏi entry này. Ví dụ `calm` hôm nay trả `chord_melody` (`guitar_patterns.py:949`), không phải `suite_valsa`.

#### Render matrix

```json
{
  "pattern": "suite_valsa",
  "meter": "3/4",
  "note_count": 42,
  "voice_counts": { "1": 8, "2": 16, "3": 6, "4": 0 },
  "rendered_hash": "sha256:..."
}
```

- Sinh `backend/tests/fixtures/render_matrix.json`.
- Chỉ render pattern mà selection matrix đã chọn; không render pattern ngoài cửa.
- Key/hash phải gồm: `renderer_version + params_hash + sample_rate + ensemble + pattern + meter + fixture_version`. Thiếu `params_hash`/`sample_rate` sẽ đỏ matrix mỗi lần đổi humanize/audio.
- Pattern có thể trả `[]` hợp lệ nếu selection không bao giờ chọn nó ở meter đó; khi đó ghi `expected_empty: true` + lý do, không fail oan.
- `unsupported` là field của **meter variant**, không phải của pattern:

```json
{
  "meter": { ... },
  "materializer": "grid_4_4",
  "unsupported": false
}
```

Nếu `unsupported: true`, phải có `reason`; selection matrix không được chọn variant đó.

#### Test

> **Trạng thái code:** đã có cả ba matrix: `sentence_selection_matrix.json` (2.016 dòng), `pattern_selection_matrix.json` (39 row = 38 `PROFILES` + `pedal`), `render_matrix.json` (41 row), với test drift. `pattern_selection_matrix` dùng real chooser (`_select_body` 33 row, `_patterns` 6 row); `(torroba, sonatina)` là `expected_empty` duy nhất vì không có rule chọn production. Không dùng `conftest.py`; fixture là module trực tiếp.

- `backend/tests/test_texture_selection_matrix.py`
- `backend/tests/test_texture_render_matrix.py`
- Cả hai so fixture với output mới; drift phải review, không tự update.
- Đây là artifact bắt buộc, không chỉ là gate bằng lời.

### 4.6. Không có meter per-bar

Revision 2/3 bỏ hoàn toàn giả định “meter của bar/phrase”. Nếu sau này cần đổi meter giữa movement, đó là refactor `render.py`/`Score` (thêm meter per-section), không phải việc của `guitar_*`.

Trong Phase 0–2:

- Meter là per-render/per-movement.
- Sentence `when.meter` là gate tĩnh, resolve lúc load spec.
- Không dùng `kind_at` làm meter.

---

## 5. Pattern, sentence, door

### 5.1. Torroba là mẫu tham chiếu

- `_FIGURES` (`guitar_torroba.py:3403`) là **slot realizer**: mỗi phần tử là một cách điền ô (int code).
- Gate `_REAL_TORROBA_FIGURES` (`guitar_torroba.py:32`) dùng ở `guitar_patterns.py:1862`.
- `SentenceSpec` là **template**: các slot trỏ tới figure code qua `figure_registry`; **không** có một `sentence_code` duy nhất cho cả câu.
- `SentenceSpec.id` là id authoring; figure code (int) là id runtime của từng slot.

Ví dụ:

```json
{
  "id": "castillo_34_walk_cadence",
  "composer": "torroba",
  "kind": "sentence",
  "parent": "castillo",
  "meter": {
    "id": "3/4",
    "beats": 3,
    "beat_type": 4,
    "eighths_per_bar": 6,
    "strong_eighths": [0],
    "subbar_breaks": [4],
    "extra_weights": [[4, 0.8]]
  },
  "select": { "length": [9, 18], "n_parity": "any", "closes": null },
  "span": { "unit": "bar", "tile": 9 },
  "slots": [
    { "role": "statement", "bars": 5, "realizer": { "kind": "texture", "figure": "castillo_walk" } },
    { "role": "answer",    "bars": 4, "realizer": { "kind": "texture", "figure": "castillo_cadence" } }
  ],
  "status": "reviewed"
}
```

`castillo_walk` → 13, `castillo_cadence` → 14, `arada` → 7, `float` → 8 trong `_FIGURES`. Chi tiết schema/selector/validator: [`sonify-guitar-model.md`](./sonify-guitar-model.md) §13.

### 5.2. Villa chưa có sentence registry

> **Trạng thái code:** `villa_pattern` vẫn là bar-level. Đã có **candidate preview-only** `villa_arpeggio_aba` (4/4) và **Suite audit data-only** trong `app/studio/villa_suite_audit.py` (đề xuất Mazurka-Choro 3/4). Chưa register, chưa có `suite_*` production pattern, chưa có candidate JSON/sentence registry.

Trong code hiện tại:

- `villa_pattern` là một hàm bar-level: `_render_villa_bar`.
- `etude1`, `etude11` là bar-level: `_render_etude1_bar`, `_render_etude11_bar`.
- `chord_melody`, `thumb_cantabile` là bar/phrase-level.
- Không có `_FIGURES`, không có span/slot, không có sentence registry.

Vì vậy:

- **Phase 0/1: Villa chỉ có `kind: "pattern"`.** Không bịa `SentenceSpec` cho Villa.
- Phase 2: audit từng movement của *Suite Popular Brasileira* để quyết định pattern nào thực sự có sentence span. Nếu chỉ là biến thể trong một hàm bar-level, nó là **texture variation / cell**, không phải sentence.
- Khi Villa có sentence registry, nó phải theo cùng mô hình Torroba: template + slot realizer trỏ tới figure code, có plan golden. Từ vựng và schema: [`sonify-guitar-model.md`](./sonify-guitar-model.md) §13.

Đây là câu trả lời cho câu hỏi “Villa tổ chức thế nào”: **chưa biết; phải audit, không suy từ Torroba.**

### 5.3. Door

`intro`/`outro` là **section kind** của `FormSpec`, không phải tên của door. `warmup`/`cooldown` cũng là door region (`Section` trong `form.py:108`, `_PEDAL` ở `:109`). Door là **script điền vùng pedal**, gắn theo `(ensemble, pattern)`; nó thuộc **Plan**, không phải Texture/Sentence, và **không in tên**.

Hôm nay **cả 38 dòng `PROFILES` đều có door** (13 trong `guitar_frame_rest`, 10 trong `guitar_frame_bach_sor`, 7 trong `guitar_torroba_doors`, 8 trong `_RETAINED_DOORS`), nên một pattern mới gần như chắc chắn cần một door.

Khi thêm pattern:

- [ ] `traits.has_door` — quyết định có cửa hay không.
- [ ] Hàm door + đăng ký vào module door hoặc `_RETAINED_DOORS` (key `(ensemble, pattern)`; `_RETAINED_DOORS` thắng khi trùng).
- [ ] `_PEDAL_DOOR_PROFILE[pattern]` nếu trần register/velocity khác `"study"` — hiện chỉ 10/38 pattern có entry, còn lại rơi về `"study"`.
- [ ] Door golden cho `(ensemble, pattern)` × intro/outro × steps ngắn/dài.

Chi tiết schema/validator/inventory: [`sonify-guitar-model.md`](./sonify-guitar-model.md) §14.

---

## 6. Spec model: authored / derived / rendered

> **Trạng thái code:** **schema + validator** đã có trong `app/studio/texture_spec.py`; `app/studio/texture_resolve.py` resolve 5 pitch kind, authored → `NoteEvent`, và check register/voice order/string-fret/written-sounding/hand span (checks thiếu data trả `skipped`/`partial`). Chưa có renderer-profile exceptions, string/fret-vs-pitch, `derived`/golden hash hay compiler đầy đủ. Authoring runtime hiện vẫn là `SentenceSpec`.

### 6.1. Ba tầng

Revision 1 trộn tất cả vào `events`. Revision 2/3 tách:

| Tầng | Chứa gì | Có phải nguồn chân lý? | Dùng trong round-trip? |
|---|---|---|---|
| `authored` | bar, beat, duration, voice, **pitch reference**, tie, slur, accent, staccato, staff; optional `string`/`fret`; optional **micro-velocity offset** | Có, cho **placement + reference + micro offset** | Có, nhưng không so absolute MIDI |
| `derived` | `resolved_midi`, realized velocity sau wave/humanize, hairpin rule, humanize policy, dynamics policy | Không | Chỉ khi cùng render context |
| `rendered` | `NoteEvent` sau `_resolve`, `apply_guitar_wave`, humanize | Không | Golden artifact riêng |

`pitch reference` là `melody_eighth`, `chord_degree`, `scale_step` hoặc `literal_midi`. Chỉ `literal_midi` là absolute; các kind còn lại resolve từ render context. Vì vậy `resolved_midi` thuộc `derived`, không thuộc `authored`.

**Micro-velocity offset** là ngoại lệ có chủ ý: nó thuộc `authored` nhưng **không phải velocity tuyệt đối**. Nó là delta optional trên level figure viết ra; realized velocity vẫn do wave/humanize quyết định. Không khai báo = offset 0.

`rendered` không nằm trong `TextureSpec`. Nó là file `rendered.json` hoặc hash, sinh từ một render thật.

**Hệ quả round-trip**: `melody_eighth` lấy `ctx.melody[index]` từ chính lần render đang so, nên nếu dùng nó để so `midi` thì hai vế luôn bằng nhau — đó là vòng tròn. Authored round-trip chỉ kiểm placement + reference; absolute pitch do golden hash kiểm.

`string`/`fret` là **metadata xác thực** trong `authored`, không phải field của `NoteEvent`. Chúng có mặt khi nguồn là tab hoặc khi Gemini đọc được tab; nếu không có, validation bỏ qua phần string/fret.

`confidence`, `conflict`, `review` cũng là **metadata của authored event**, không vào `NoteEvent`:

```json
{ "confidence": 0.91, "conflict": false, "review": "edited" }
```

- `review`: `pending | accepted | edited`.
- Default theo nguồn: event do Gemini tạo = `pending`; event người nhập tay = `edited`; spec nhập tay hoàn toàn bắt đầu ở `edited`.
- Publish từ chối nếu còn `pending` hoặc `confidence < 0.6` chưa được người accept/edit.
- `conflict=true` phải có quyết định của người, không tự chọn phổ hay tab.

### 6.2. `NoteEvent` tương ứng

`NoteEvent` trong `model.py:121` có:

- `bar`, `beat`, `midi`, `duration_beats`, `voice`
- `staff`, `tie_start`, `tie_stop`, `slur_start`, `slur_stop`
- `accent`, `velocity`, `tenuto`, `staccato`, `hairpin`, `pinned`

Spec `authored` phải cover: `bar`, `beat`, `pitch reference`, `duration_beats`, `voice`, `staff`, `tie_start/stop`, `slur_start/stop`, `accent`, `tenuto`, `staccato`.
Spec `authored` **có thể** cover thêm `string`, `fret`, `written_pitch`, `sounding_pitch` khi nguồn là tab; đây là metadata, không phải `NoteEvent`.
Spec `derived` cover: `resolved_midi`, `velocity`, `hairpin`, `pinned`, dynamics.
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
  "price":   { "voice": 1, "source": "melody" },
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

- **Authored round-trip** so placement + reference: `bar`, `beat`, `duration_beats`, `voice`, `staff`, tie/slur/accent/staccato, và `pitch.kind` + index/degree. Không so absolute `midi` nếu pitch là `melody_eighth`/`chord_degree`/`scale_step`; nếu là `literal_midi` thì so được.
- **Vì sao**: `melody_eighth` lấy `ctx.melody[index]` từ chính lần render đang so → so `midi` sẽ luôn pass, kể cả khi renderer đặt sai quãng. Đây là vòng tròn, không phải test.
- **Absolute pitch** do `rendered` golden kiểm: cùng price path, volume, chord slots, liquidity, `params` hash, `SPAN_REVISION`/`RECAP_REVISION`, cùng `renderer_version`. So hash/snapshot, không so ±2.
- Không so `velocity` tuyệt đối (realized). Velocity cuối do `apply_guitar_wave()` + `resolve_bar_volumes()` + liquidity + humanize quyết định. **Micro-velocity offset** thì so được, vì nó là authored data.
- Không có “humanize seed”. `humanize()` nhận `params`, `offset_at`, `fan_hold`; tính deterministic qua `_stable_unit`, cố ý không dùng `hash()`. Vì vậy cache/so sánh dùng `params` hash + `SPAN_REVISION`.
- `rendered` là golden artifact, không phải input của spec.

### 6.6. `assert_playable` không chứng minh spec playable

`assert_playable` chạy trên score **đã được repair** (`_resolve`, `_fit`, renderer sửa voicing trước khi ghi). Nó không chứng minh `authored` playable.

Cần thêm:

- `assert_authored_playable(authored, profile)`:
  - **offline** (không cần render): bar/beat/duration sum theo meter, không overlap cùng voice, tie/slur có đầu cuối, voice order nếu pitch là absolute, string/fret nếu có `literal_midi`;
  - **with render context**: resolved MIDI range, register guitar, voice order (`bass < mid < lead`), hand span, string/fret khớp pitch;
  - nếu không có `string`/`fret` hoặc pitch là reference: phần playability vật lý để `assert_playable` sau repair.
- `assert_playable(score, profile)`: kiểm tra output sau repair, như hiện tại.
- Publish yêu cầu cả hai; nếu validate chưa có melody context thì trả `partial: true` + `skipped_checks`, không silent pass.

### 6.7. Schema tối thiểu của `TextureSpec`

```json
{
  "id": "suite_mazurka",
  "composer": "villa",
  "kind": "pattern",
  "level": "topic",
  "parent": null,
  "runtime": "code",
  "status": "draft",
  "suite": { "name": "Suite Popular Brasileira", "movement": 1 },

  "source": {
    "piece": "Suite Popular Brasileira — Mazurka-Choro",
    "bars": [1, 8],
    "upload_id": "<uuid>",
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
      "unsupported": false,
      "reason": null,
      "sentences": []
    }
  ],

  "authored": {
    "events": [
      {
        "bar": 0,
        "beat": 0.0,
        "duration_beats": 1.5,
        "voice": 1,
        "pitch": { "kind": "melody_eighth", "eighth": 0 },
        "written_pitch": "E4",
        "sounding_pitch": "E3",
        "tie": "none",
        "slur": "none",
        "accent": true,
        "staccato": false,
        "staff": 1,
        "string": 1,
        "fret": 5,
        "confidence": 0.91,
        "conflict": false,
        "review": "edited"
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
    "resolved_midi": "from_render_context",
    "velocity_band": { "voice": 1, "source": "liquidity" },
    "hairpin": "phrase",
    "humanize": "params"
  },

  "routing": {
    "price": { "voice": 1, "source": "melody" },
    "volume": { "voice": 2, "mode": "velocity_band", "source": "liquidity" },
    "bass": { "voice": 3, "mode": "chord_root" },
    "density": { "voice": 2, "mode": "eighth_grid" }
  },

  "traits": {
    "family": "arpeggio",
    "kinetic": true,
    "narrow_rows": [6, 24, 80],
    "scale_host": false,
    "plucked": false,
    "loud_down": true,
    "has_door": false,
    "pedal_door": false,
    "sentence_registry": "none"
  },

  "selection": {
    "priority": 10,
    "mood": ["calm", "selloff"],
    "band": ["p", "mp", "mf", "f"],
    "bpm": [0, 132],
    "after": ["chord_melody"],
    "avoid_repeat": true,
    "contrast": "villa_pattern"
  },

  "provenance": {
    "model": "gemini-3.5-flash",
    "prompt_version": "studio-v1",
    "schema_version": "texture-spec-1",
    "renderer_version": "guitar-render-76",
    "confidence": 0.82,
    "reviewed_by": "human"
  }
}
```

`profiles.wave` mirror đủ 12 field của `guitar_wave._profile()`; compiler dùng nó để sinh `PROFILES[("villa", id)]` và `_EXPECTED`. `profiles.render` map vào `_PROFILE`.

`traits.family` map vào `_FAMILY[id]`. `selection` là **kỳ vọng dữ liệu**, không phải codegen: compiler sinh `selection_matrix.json` + checklist; người sửa if-ladder `_select_body`/`_dominant_pattern`/`_contrast_pattern` cho khớp, rồi matrix test làm gate. Phase 0/1 **không sinh Python source** và **không sửa runtime**. Không có `selection` thì pattern có thể tồn tại trong `PROFILES` nhưng **không bao giờ được chọn**.

- `priority`: số nhỏ được xét trước.
- `mood`, `band`, `bpm`: cửa lọc; `bpm` là khoảng đóng.
- `after`: pattern phải đứng sau các id này trong cùng section.
- `avoid_repeat`: không lặp cùng pattern ở hai câu sát nhau.
- `contrast`: pattern B khi A là pattern này.

Test bắt buộc:

- Mỗi spec `kind: "pattern"` phải có ít nhất một input trong `selection_matrix.json` mà `_select_body` trả về id của nó.
- Pattern không xuất hiện trong selection matrix bị coi là dead code và fail.
- `selection.bpm` là khoảng đóng; `selection.mood` dùng đúng 4 character `calm/rally/selloff/volatile`.

### 6.8. `pitch` phải declarative, không gọi tên hàm Python

Spec **không được** chứa tên hàm private như `_melody_at`. `pitch` chỉ dùng các kind sau:

```json
{ "kind": "melody_eighth", "eighth": 0 }
{ "kind": "melody_eighth", "eighth": 0, "offset": 2 }
{ "kind": "chord_degree", "degree": 1 }
{ "kind": "chord_root" }
{ "kind": "scale_step", "steps": -1 }
{ "kind": "literal_midi", "value": 57 }
```

Không chỉ `melody_eighth`: **toàn bộ tầng pitch là tương đối với render context**, trừ `literal_midi`.

| Kind | Cần gì để resolve |
|---|---|
| `melody_eighth` | `ctx.melody` (sau `_place_melody`) |
| `chord_degree` / `chord_root` | `chord_at` của bar hiện tại |
| `scale_step` | `mode` + `_melody_scale` + register |
| `literal_midi` | Không cần gì; standalone |

Quy tắc:

- `melody_eighth` **trích** `ctx.melody[eighth]` — mảng melody đã qua `_melody_scale`, register floors, `_choose_shifts`, `_place_melody`. Spec không tái tạo phép biến đổi price → melody; nó chỉ tham chiếu kết quả.
- `eighth` và `offset` phải nằm trong `[0, len(ctx.melody))`. **Out-of-range là validation error**, không clamp như `_melody_at` (hàm đó trả `melody[-1]`). Nếu không, nốt lấy đà cuối phrase sẽ lặng lẽ thành nốt cuối.
- `chord_degree` lấy bậc trong hợp âm hiện tại; `1` là gốc. `chord_root` là alias của degree 1.
- `scale_step` đi theo thang của mode hiện tại; cần register để clamp.
- `literal_midi` chỉ dùng khi spec thật sự cần một cao độ cố định; phải có lý do trong `provenance.notes`.
- Compiler resolve các kind này thành MIDI **trong cùng `_Ctx`** đã render; runtime không import `guitar_patterns` để hiểu spec.
- Không có kind `price`: price → melody là việc của engine, không phải của spec. Nếu Phase 2 interpreter cần resolve `melody_eighth`, nó phải nhận `melody` array từ cùng pipeline; spec một mình không đủ để resolve.
- Vì vậy `melody_eighth`/`chord_degree`/`scale_step` chỉ dùng cho `runtime: "code"` hoặc interpreter có contract context tường minh; không dùng cho spec publish độc lập chưa có context.
- Nếu cần escape hatch cho một gesture chưa biểu diễn được, dùng `literal_midi` + `runtime: "code"`, không thêm tên hàm.

### 6.9. Micro-velocity contour (optional, authored)

> **Trạng thái code:** **phần lớn**. `app/studio/micro_velocity.py` có data model + parse/validate + relative applier + pinned checker; `app/sonify/micro_velocity_contours.py` đã bóc tách Tremolo 4/4–3/4, Etude1, Etude11, Galop1/2, Cathedral; `SentenceSpec.Slot`/`TextureSpec`/`AuthoredEvent` đã parse/round-trip `microVelocity`/`velocityOffset`; preview trả `microVelocity: [{slot, contour}]`; UI có velocity lane + slot selector + save-to-spec. Writer integration **đã có sau flag `VSTOCK_MICRO_VELOCITY_WRITERS`** (default off) cho Tremolo/Etude1/Etude11/Galop1/2; flag off byte-identical. **Chưa wire**: Cathedral writer path, slot/texture override, preview áp contour vào notes. Schema dưới đây là contract hiện tại.

Mỗi figure/pattern/sentence có thể mang **offset velocity theo từng nốt**. Đây là layer **optional, authored**, không phải velocity tuyệt đối. Không khai báo = offset 0 cho mọi nốt, kể cả thumb. Offset 0 phải cho **NoteEvent byte-identical** với code hiện tại.

#### Carrier (nơi lưu)

| Tầng | Field | Ghi chú |
|---|---|---|
| Figure registry | `figure.microVelocity` | default contour của figure; code-owned, Studio bóc tách/ghi đè |
| Sentence | `SentenceSpec.slots[].microVelocity` | override contour cho slot đó; slot vẫn dùng `figure: int` |
| Pattern / TextureSpec | `TextureSpec.microVelocity` | pattern-level contour; dùng khi pattern không có sentence slot |
| Note-level | `AuthoredEvent.velocityOffset` | optional cho spec nhập tay; cùng nghĩa delta |

Không có field `figures[]` mới: figure id vẫn là `int` trong `Slot`; contour gắn vào slot/registry, không đổi realizer.

#### Toạ độ nốt

Mỗi entry dùng toạ độ **tương đối trong figure/slot**, không phải index toàn bài:

```json
{
  "bar": 0,
  "beat": 0.0,
  "voice": 1,
  "finger": "a",
  "offset": -6
}
```

- `bar`: 0-based, tương đối từ đầu figure/slot (Galop 8 bar dùng 0..7).
- `beat`: 0-based **quarter-note beat** trong bar; `0.25/0.5/0.75` là sixteenth, `1/3` là triplet.
- `voice`: 1–4; UI bắt buộc lane 1–3, lane 4 chỉ hiện khi figure thực sự dùng voice 4.
- `finger`: optional `p | a | m | i`; dùng cho tremolo/fingerstyle. Vắng `finger` thì offset áp theo `(bar, beat, voice)`, không phân biệt ngón.
- `offset`: delta trên level figure viết ra; **không** phải velocity tuyệt đối.
- `pinned: true` + `velocity`: attack do layer absolute kiểm soát (snap/stab/fan/tremolo trim) thì lưu velocity cuối, không lưu offset.

#### Hai dạng contour

```json
{
  "kind": "offsets",
  "notes": [
    { "bar": 0, "beat": 0.0, "voice": 1, "finger": "a", "offset": -6 },
    { "bar": 0, "beat": 0.25, "voice": 1, "finger": "m", "offset": -3 },
    { "bar": 0, "beat": 0.5, "voice": 1, "finger": "i", "offset": -4 },
    { "bar": 0, "beat": 0.75, "voice": 1, "finger": "a", "offset": -6 }
  ],
  "thumb": [
    { "bar": 0, "beat": 0.0, "voice": 3, "finger": "p", "offset": -4 }
  ]
}
```

```json
{
  "kind": "rule",
  "ruleId": "galop1",
  "ruleVersion": 1,
  "params": { "step": 2, "floor": 40 },
  "notes": []
}
```

- `thumb: []` hoặc vắng = thumb offset 0.
- `kind: "rule"` lưu rule/step table gốc; UI flatten thành per-note cho fixture đang chọn, nhưng dữ liệu lưu vẫn là rule. Mỗi `ruleId` phải khai `params` tối thiểu (ví dụ `galop1: {step, floor, peakQuarter}`) để flatten không phụ thuộc default ẩn.
- Với `TextureSpec`, offline validator chỉ bound **beat** trong bar; `bar` không bound vì spec không khai length/window — compiler/preview bound theo meter/window đã chọn. Nhiều meter variant cũng vì vậy không chọn hộ.
- `ruleVersion` phải bump khi writer mirror đổi (`_galop*_steps`, `_etude11_middle_vel`). `flatten_rule(base_at=...)` khi wire vào writer phải truyền **neutral level**, không dùng default `event.velocity` (chỉ dùng cho extraction harness).
- **renderHash và audio cache key đã gồm contour**: canonical mapping theo slot, entry sort `(bar, beat, voice, finger)`. Hai spec cùng plan/row/notes nhưng khác offset không dùng chung cache. Preview vẫn chưa áp contour vào notes/velocity; writer integration là bước riêng.
- Không có `base` áp vào velocity. Nếu UI cần mốc hiển thị, dùng level figure viết ra làm reference; không lưu/không cộng `base`.

#### Thứ tự render và exception

```
figure writer (level gốc)
  → relative micro offsets
  → apply_guitar_wave (center + (written - 64), giữ relative)
  → snap / stab / fan / tremolo trim (absolute, overwrite)
  → humanize
```

- Relative offsets chỉ áp cho attack **không pinned**.
- `_apply_snaps`, `_apply_stabs`, `_apply_fans`, `_apply_tremolo_bass_trim` là **absolute writers**. Chúng overwrite velocity; contour của các attack đó phải là `pinned: true` + `velocity` (không phải offset). `TREMOLO_BASS_TRIM=2` là một trong các exception này, không phải exception duy nhất.
- `restamp_passage_hairpins` / `_restamp_swarm_hairpins` chỉ đổi hairpin, không ghi velocity; nếu tương lai chúng ghi velocity, phải thêm vào danh sách pinned.
- Không layer nào được tự đặt lại offset của attack không pinned; chỉ dịch/clamp.

#### Zero-diff bắt buộc

- **Production patterns** (Tremolo, Galop, Cathedral, Etude1, Etude11) không có Studio `renderHash`. Zero-diff so **danh sách `NoteEvent`** (bar/beat/midi/voice/velocity/flags) và **golden digest/score-level artifact**, không phải `renderHash`.
- **Studio preview** có `renderHash`; ở đó mới so hash.
- Quy trình: baseline code → render fixture cố định → extract contour → render lại với contour → so từng NoteEvent + digest. Chỉ accept khi **identical**; nếu lệch, contour/schema sai, không được nới tolerance.
- Contour vắng hoặc offset 0 phải identical; đây là điều kiện rollout.
- Oracle hiện có: `backend/tests/micro_velocity_golden.py`, `backend/tests/fixtures/micro_velocity_golden.json`, `backend/tests/test_micro_velocity_golden.py`. Baseline lưu **full NoteEvent surface** (bar/beat/midi/duration/voice/velocity/staff/tie/slur/accent/tenuto/staccato/hairpin/pinned) + `fixture_digest`/`notes_digest`/`score_digest` (sha256), boundary là `render_patterned_voices` sau `apply_guitar_wave` trước humanize.
- Fixture ids: `tremolo_44`, `tremolo_34`, `galop_1`, `galop_2`, `catedral_preludio`, `etude1`, `etude11`; offset 0 phải reproduce đúng notes_digest đã commit, không có update mode/tolerance.

#### UI

- Click figure/slot → **velocity lane**: x = bar/beat/note, y = offset; nhóm voice 1–4; thumb lane riêng. Khi preview trả nhiều slot, có slot selector; **Save to spec** ghi vào `slots[slot].microVelocity`, empty thì bỏ field, pinned/rule được khoá; preview chưa trả slot bar origin nên `slot.start > 0` cần origin trước khi map đúng.
- Empty = 0; pinned attack hiện nhãn layer (snap/stab/fan/trim) và velocity tuyệt đối, không cho kéo offset.
- Toggle “authored offsets → sau wave/humanize” **chỉ để xem**, không đổi dữ liệu lưu và không tạo hai render mode.
- Sửa offset lưu vào figure/slot; không sửa velocity tuyệt đối của note thường. Preview notes cần `finger` (hoặc note-level `velocityOffset`) để match contour theo ngón; chưa có thì chỉ match entry không finger.

#### Nguồn để bóc tách (hardcode hiện tại)

| Figure | Nguồn offset trong code |
|---|---|
| Tremolo | thumb 4/4 `-4,0,+4,+1` quanh 58; fill `-6,-3,-4,-6`; trim 2 sau snap |
| Galop | `_galop1_steps` / `_galop2_steps` × `_GALOP_STEP=2`, floor 40; rule-based |
| Cathedral Preludio | role center + `_catedral_level` nudge, `_catedral_under(level,canto)=min(level,canto-6)`, whisper base 52/bottom-2 |
| Etude1 | `_ETUDE1_ARC` theo sixteenth (`-2/-2/-2/0/0/+2...`), middle 52, bass sung-4 |
| Etude11 | arch `-10/-6/-7/-10`, band nudge, `_ETUDE11_TILT`, lead hairpin/-8, bass hairpin-4 |

Đã bóc tách: `TREMOLO_44`, `TREMOLO_34` (offsets), `ETUDE1` (offsets), `ETUDE11`/`GALOP1`/`GALOP2`/`CATHEDRAL_PRELUDIO` (rules) trong `app/sonify/micro_velocity_contours.py`; zero-diff bằng `tests/micro_velocity_extract.py` + `tests/test_micro_velocity_contours.py`. Cathedral dùng `canto_at`/`raw_at`/`beats_per_bar` ở flatten time cho `min(level, canto-6)`; không lưu bar plan/offset bịa. `NEUTRAL_LEVELS` chỉ là metadata verify, không phải `base` trong contour.

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

> **Trạng thái code:** `backend/app/sonify/texture_registry.py` **đã có** (lazy, fail-soft, schema allowlist, `renderer_version` gate, duplicate/skip report). `backend/app/sonify/textures/` vẫn chưa có spec production; loader **chưa** được runtime/planner đọc. Runtime hiện vẫn đọc `SENTENCE_SPECS` code-backed.

Thêm loader:

```
backend/app/sonify/texture_registry.py
```

- `load_specs(root)` đọc `backend/app/sonify/textures/**/*.json`.
- Validate bằng `schema.py` + `validate.py`.
- Trả `PatternSpec` / `SentenceSpec`.
- Dùng bởi compiler/test **và** runtime chỉ cho pattern có `runtime: "interpreter"`.
- Pattern `runtime: "code"` vẫn đi qua `if/elif` hiện tại.

**Version gate**:

- `provenance.schema_version` phải nằm trong allowlist (`texture-spec-1`, ...). Ngoài allowlist: log + bỏ spec, không crash app.
- `provenance.renderer_version` bắt buộc cho spec `runtime: "interpreter"`; golden `rendered.json` ghi cùng version. Đổi renderer phải bump version.
- JSON hỏng, thiếu field, hoặc validate fail: **fail-soft**. Registry bỏ spec đó, log lỗi, app vẫn boot.
- Không load spec từ network; chỉ file trong repo đã merge.
- Registry đọc lazy (startup hoặc lần dùng đầu), không chặn `/health`.

`backend/app/sonify/textures/` hiện **không tồn tại**; đây là thư mục mới, chỉ chứa spec đã publish. Không có loader nào hôm nay, nên câu “publish xong ai đọc” phải trả lời bằng loader này.

### 7.3. Ai đọc spec publish?

| Giai đoạn | Người đọc | Mục đích |
|---|---|---|
| Phase 0 | `pytest` + compiler | Round-trip, fixture, docs |
| Phase 1 | Studio UI + compiler | Preview, validate, export |
| Phase 2 | `texture_registry.py` | Runtime cho `runtime: "interpreter"` |
| Phase 3 | Runtime + library UI | Chọn pattern/sentence theo meter |

Publish không ghi thẳng vào repo từ server. Publish tạo bundle để người/agent mở PR; sau khi merge, `texture_registry.py` mới đọc được.

---

## 8. Preview

### 8.1. Preview là `slice_score` của render thật

> **Trạng thái code:** MVP **không dùng `slice_score`**. `app/studio/preview.py` và các candidate preview dựng một `_Ctx` bounded rồi gọi realizer thật cho tối đa 16 bar. Đây là preview của realizer, chưa phải slice của render đầy đủ.

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

> **Trạng thái code:** validate/preview có **job queue** `app/studio/jobs.py`: in-memory 64 job, TTL 10 phút, một `ThreadPoolExecutor(max_workers=1)`, cap **8 active job/owner** (`VSTOCK_STUDIO_JOBS_PER_OWNER`, owner từ `X-Studio-Session`, thiếu header → `anonymous` dùng chung), `POST /v1/studio/jobs` (202) + `GET /v1/studio/jobs/{id}` (404/409/200; owner khác → 404). Job terminal giải phóng `spec/fixture`. Audio preview vẫn là synth code-only (`app/studio/audio.py`, 22.05 kHz, 96 BPM, `renderHash`, semaphore riêng); MuseScore/audio queue vẫn chưa.

- App dùng `expo-audio`, không có MIDI player.
- Guitar audio đi qua `audio.py` → MuseScore.
- `EXPORT_SLOTS` mặc định 1 (`audio.py:61`), nên preview sẽ tranh slot với nút Nghe.
- Cần:
  - cache preview theo `SPAN_REVISION`/`RECAP_REVISION` + `params` hash + `candle_count` + `ensemble` + `instrument` + tempo + sample rate;
  - TTL như `AUDIO_MAX_AGE_DAYS`;
  - **global Studio queue** 1 worker, tách khỏi `EXPORT_SLOTS` của nút Nghe; không chỉ giới hạn per-session;
  - render ngoài event loop (2 vCPU), API trả `202` + `preview_id` nếu chưa xong;
  - UI hiển thị “đang chờ MuseScore” thay vì treo.
- Không hứa “MIDI nhẹ” khi app không có MIDI player.
- Không dùng “humanize seed”: cache dùng `cache_mark(values)` như `audio.py`.

---

## 9. Gemini vision

> **Trạng thái code:** **backend + UI đã có**. `app/studio/vision.py`, upload/analyze/session/quota; UI upload + crop web (rect source px → `/analyze`) + notes table + TextureSpec draft/validate; validate/preview job queue (`jobs.py`). **Chưa có** native picker/crop, apply vào SentenceSpec editor, durable preview media.

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
- **micro-velocity offset** (Gemini có thể đọc accent/dynamic ký hiệu; người chuyển thành contour)
- micro-timing, velocity, humanize
- “nốt này ngân dài để nối bè”
- quãng bè trung
- meter của pattern/sentence
- điều kiện chọn pattern/sentence

### 9.5. Validate sau Gemini

Trước khi lưu `draft`:

- **Per-voice duration**, không cộng tất cả voice: trong mỗi voice, các note không overlap và tổng `duration_beats` của voice đó bằng `bar_beats` (`eighths_per_bar / 2`), hoặc phần thiếu là rest tường minh. Guitar có 3–4 voice đồng thời; cộng tất cả sẽ ra ~3× độ dài ô và từ chối mọi bar đúng.
- `tie_start`/`tie_stop` có đầu có cuối; `slur_start`/`slur_stop` có đầu có cuối.
- `written_pitch` và `sounding_pitch` lệch đúng 12 nửa cung, trừ khi capo/scordatura được khai.
- Nếu có `string`/`fret`: string 1–6, `0 <= fret <= _MAX_FRET[6 - string]` (mảng index 0 = dây 6), pitch khớp string+fret, hand span ≤ 5.
- Không có hai nốt cùng voice chồng nhau.
- Voice order: bass < mid < lead (trừ texture khai đảo vai).
- Nốt confidence thấp phải được đánh dấu, không tự nhận.
- `conflict=true` giữa phổ và tab phải có quyết định của người.
- `review` phải là `accepted` hoặc `edited` trước khi publish; `pending` bị từ chối. Gemini tạo `pending`; người nhập tay tạo `edited`.
- Validate dùng **cùng render executor/global Studio queue** với preview: pitch/register/string-fret cần render context. Nếu draft chưa có melody context, trả `partial: true` + `skipped_checks` (`pitch`, `register`, `playable`); không im lặng pass.
- `POST /specs/{slug}/validate` có thể trả `202 + validation_id` nếu phải render; UI poll trạng thái như preview.

---

## 10. Studio trong app Musicalize

### 10.1. App

Hiện tại:

- `src/musicalize/MusicalizeApp.tsx`: `Mode = 'replay' | 'live' | 'studio'`.
- `TopBar` đã có pill **Studio**, luôn hiện (chưa có capability gate).
- `src/studio/StudioRoom.tsx` (không phải `src/musicalize/StudioRoom.tsx`): JSON editor, examples API, Validate, Preview, Play preview (web), Publish + version list, Rollback.
- Chưa có upload ảnh, crop, Gemini draft hay bảng review nốt.

Đề xuất còn lại:

- Capability gate cho pill Studio.
- Upload/crop + Gemini draft + review table.
- Studio dùng layout riêng, không dùng `RoomFrame` của phòng nghe.
- Mọi HTTP đi qua `src/api/client.ts` (`getApiBaseUrl`, `absoluteApiUrl`). Không tạo fetch client thứ hai.

### 10.2. Session, không phải auth

> **Trạng thái code:** `X-Studio-Session` + hash `owner_id` + quota upload/analyze + signed media token **đã có**; sentence specs cũng đã có `owner_id` + `visibility private/public` trong `studio_sentence_specs`, và publish/list/get/rollback/export scope theo session. Thiếu `X-Studio-Session` → namespace `anonymous` để tương thích cũ. Không trả `ownerId` ra response.

Hiện tại backend **không có auth**; CORS `allow_origins=["*"]`. Vì vậy:

- Chưa cần login.
- Nhưng phải có `X-Studio-Session` do app sinh và lưu trong AsyncStorage.
- Server dùng hash session làm `owner_id`; `visibility` mặc định **`private`**. Spec chỉ chuyển `public` khi export/publish được duyệt.
- `GET/PUT/DELETE /specs/{id}` kiểm tra owner.
- `/uploads`, `/analyze`, `/preview` có quota theo session.
- Đây **không phải bảo mật** trước người cố tình; nó là namespace + chống xoá nhầm + chống đốt quota.
- Khi có auth thật, thay `owner_id` bằng user id; `visibility` enforce ở backend.

Không được viết “backend vẫn kiểm tra quyền” nếu chưa có owner check. Revision 2/3 nói rõ: Phase 1 có owner check theo session, chưa có auth.

### 10.2.1. `/access` shape, quota, telemetry

`GET /v1/musicalize/studio/access` trả:

```ts
type StudioAccess = {
  enabled: boolean;
  reason: 'open_beta' | 'entitled' | 'disabled';
  seats?: number;
  quota: {
    uploadsPerDay: number;
    analysesPerDay: number;
    specsPerDay: number;
    maxImageMb: number;
    previewsConcurrent: number;
  };
};
```

Phase 1 `open_beta`:

```json
{
  "enabled": true,
  "reason": "open_beta",
  "quota": {
    "uploadsPerDay": 20,
    "analysesPerDay": 100,
    "specsPerDay": 50,
    "maxImageMb": 20,
    "previewsConcurrent": 1
  }
}
```

- `enabled=false` ẩn pill Studio; backend vẫn trả 403.
- Quota đếm theo `owner_id` + ngày; vượt trả 429 kèm `retry_after`.
- `previewsConcurrent` là **per session**. Ngoài ra phải có **global Studio queue**: 1 render worker toàn cục, tách khỏi `EXPORT_SLOTS` của nút Nghe, để 10 session không đẩy 10 render vào cùng 2 vCPU.
- Render chạy ngoài event loop (thread/process pool); API trả `202` + `preview_id` nếu chưa xong, UI poll hoặc nhận signed URL.
- Telemetry dùng `src/musicalize/telemetry.ts`: `studio_open`, `studio_upload`, `studio_analyze`, `studio_validate_fail`, `studio_preview`, `studio_export`, `studio_publish`. Không gửi ảnh/nốt/giá trị nhạy cảm.

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
│                  │                   │ click figure → lane   │
│                  │                   │ velocity offset       │
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

> **Trạng thái code:** publish dùng bảng `studio_sentence_specs` trong DB chung (`app/store/db.py`, `VSTOCK_DB_PATH`). Upload dùng `VSTOCK_STUDIO_DIR` (default `backend/var/studio`, production `/data/studio`) + `studio_blobs`/`studio_uploads`. Chưa có preview job/queue hay export bundle trên đĩa.

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

> **Trạng thái code:** compiler trả **bundle JSON** qua `POST /v1/studio/sentence/export` và `.../specs/{id}/export`; `export_bundle` (library) ghi 4 file `spec/fixture/rendered/registration`. **Chưa có** `preview.wav`, `/data/studio/exports`, hay PR automation.

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

**Hiện tại:**

```
backend/app/routers/studio.py          # validate, preview, examples
backend/app/routers/studio_publish.py  # publish, specs, specs/{id}, rollback
backend/app/routers/studio_audio.py    # audio + WAV
backend/app/routers/studio_export.py   # compile/export bundle (JSON, no writes)
backend/app/routers/studio_vision.py   # access, uploads, analyze
backend/app/routers/studio_texture.py  # POST /texture/validate (offline)
backend/app/routers/studio_jobs.py     # POST /v1/studio/jobs, GET /jobs/{id}
backend/app/studio/                    # sentence_spec, texture_spec, preview, dispatch, compiler, jobs, publish, audio, session, quota, store, vision, candidates
```

Sentence prefix: `/v1/studio/sentence`; vision/session `/v1/musicalize/studio`; jobs `/v1/studio/jobs`. Job queue là **in-memory/process-local** (không durable): cap global 64, cap 8 active/owner, `GET` scope theo owner (owner khác → 404), terminal job giải phóng `spec/fixture`; vẫn chưa có crop server-side, audio/MuseScore queue hay export file trên đĩa.

**Vận hành MVP:** production nên set `VSTOCK_STUDIO_SECRET`; thiếu env thì server dùng secret random per-process (token chết sau restart, không còn hardcoded secret). Upload có `Content-Length` guard + chunk cap; ngoài quota per-owner còn global cap `VSTOCK_STUDIO_GLOBAL_UPLOADS_PER_DAY`/`..._ANALYSES_PER_DAY`/`..._SPECS_PER_DAY` để chặn session rotation; publish cũng enforce `specsPerDay` (429 + Retry-After). Vision cache prune theo `VSTOCK_STUDIO_VISION_CACHE_DAYS` (default 30).

**Đề xuất Phase 1:**

```
backend/app/routers/musicalize_studio.py
backend/app/studio/
  __init__.py
  schema.py       # MeterSpec, TextureSpec, AuthoredEvent, ...
  store.py        # SQLite + file upload + owner/session
  vision.py       # prompt + Gemini parse (reuse gemini client)
  validate.py     # meter, sentence parent, authored playable
  compiler.py     # fixture, registration, registry patch
  preview.py      # slice_score + audio queue
  export.py       # bundle export
```

Prefix: `/v1/musicalize/studio`.

| Method | Path | Việc |
|---|---|---|
| `GET` | `/access` | Capability + quota shape |
| `POST` | `/uploads` | Upload ảnh (multipart) |
| `GET` | `/uploads/{upload_id}` | Tải lại ảnh phổ, kiểm tra owner |
| `DELETE` | `/uploads/{upload_id}` | Xoá upload; `409` nếu còn spec trỏ tới |
| `POST` | `/analyze` | Ảnh + crop + metadata → Gemini draft |
| `GET` | `/specs` | Danh sách spec của session |
| `POST` | `/specs` | Tạo spec |
| `GET` | `/specs/{slug}` | Đọc spec của session |
| `PUT` | `/specs/{slug}` | Lưu spec |
| `DELETE` | `/specs/{slug}` | Xoá spec nháp |
| `POST` | `/specs/{slug}/validate` | Validate |
| `POST` | `/specs/{slug}/preview` | Render preview |
| `POST` | `/specs/{slug}/export` | Xuất bundle |
| `GET` | `/exports/{export_id}` | Tải bundle |
| `GET` | `/previews/{preview_id}` | Nghe preview |

`{slug}` được scope theo `owner_id`; không dùng pattern id toàn cục làm PK.

Tất cả endpoint (trừ `/access`) đọc `X-Studio-Session`, resolve `owner_id`, kiểm tra `visibility`, và áp quota.

**Media không gửi được header**: `<audio src>` và link tải không gửi `X-Studio-Session`. Vì vậy `GET /previews/{id}` và `GET /exports/{id}` nhận token ngắn hạn:

```
/previews/<id>?t=<signed-token>
/exports/<id>?t=<signed-token>
```

Token ký theo `owner_id + resource_id + expiry`, TTL 5–15 phút, revoke khi spec bị xoá. Không dùng session header cho media.

**Preview lifecycle**:

- `POST /specs/{slug}/preview` → `202` + `preview_id` nếu chưa có cache.
- `GET /previews/{preview_id}`:
  - `404` nếu chưa có job/cache;
  - `409` nếu đang render (kèm `Retry-After`);
  - `200` nếu ready, trả audio (signed URL hoặc bytes).
- Validate dùng **cùng global Studio queue**; nếu đang chờ render, trả `202 + validation_id`; nếu thiếu context, trả `200` với `partial: true` + `skipped_checks`.

### 11.4. DDL tối thiểu

**Hiện tại:** bảng publish thật là `studio_sentence_specs(id, pattern, meter, version, payload, status, created_at, rollback_of, owner_id, visibility)` với `UNIQUE(pattern, meter, version)`; `owner_id` default `anonymous`, `visibility` default `private`, version vẫn global theo `(pattern, meter)`. Upload/blob dùng bảng riêng `studio_blobs`/`studio_uploads`/`studio_quota`. Phần DDL dưới đây là **đề xuất Phase 1**.

```sql
CREATE TABLE IF NOT EXISTS studio_blobs (
  sha256 TEXT PRIMARY KEY,
  path TEXT NOT NULL,
  refcount INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS studio_uploads (
  id TEXT PRIMARY KEY,              -- UUID upload
  owner_id TEXT NOT NULL,
  blob_sha256 TEXT NOT NULL REFERENCES studio_blobs(sha256),
  width INTEGER,
  height INTEGER,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS studio_specs (
  id TEXT PRIMARY KEY,              -- UUID, không phải pattern id
  slug TEXT NOT NULL,               -- suite_mazurka, do người đặt
  owner_id TEXT NOT NULL,
  composer TEXT NOT NULL,
  kind TEXT NOT NULL,
  parent_slug TEXT,                 -- pattern id, không phải UUID
  status TEXT NOT NULL,
  visibility TEXT NOT NULL DEFAULT 'private',
  json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(owner_id, slug)
);

CREATE INDEX IF NOT EXISTS idx_studio_specs_owner
  ON studio_specs(owner_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_studio_specs_composer
  ON studio_specs(composer, status);
```

Lý do: Studio mở cho tất cả. Nếu `id` là pattern id và là PK toàn cục, hai session không thể cùng nháp `suite_mazurka`; `PUT` của người thứ hai trả 409 và lộ sự tồn tại spec người khác. Dùng UUID + `UNIQUE(owner_id, slug)`.

`studio_uploads` đã có `owner_id` ở trên; `GET /uploads/{id}` phải kiểm tra owner trước khi trả file. Không lưu path trực tiếp trong spec; lưu `upload_id`.

`parent_slug` là **pattern id** (`suite_mazurka`, `castillo`), không phải UUID; sentence dùng nó để trỏ parent pattern. Khi publish, compiler resolve parent theo slug trong cùng composer.

`studio_blobs` dedupe theo `sha256`; `refcount` tăng khi upload, giảm khi xoá upload/spec. File chỉ bị xoá khi `refcount = 0`. Không xoá file của owner khác khi một owner xoá upload của họ.

`DELETE /uploads/{id}`:

- nếu còn bất kỳ spec nào (của owner đó) trỏ `source.upload_id` tới upload này → `409 upload_in_use`;
- nếu không, xoá row `studio_uploads`, giảm `studio_blobs.refcount`;
- file vật lý chỉ xoá khi `refcount = 0`.

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
  "sentence_registry": "torroba_int"
}
```

- `narrow_rows` là dữ liệu, không suy đoán.
- `sentence_registry` quyết định pattern có sentence template hay không; mỗi slot realizer map vào figure code.
- Compiler sinh checklist từ traits + một danh sách “review sites” cố định.
- Phần không suy được ghi là **review**, không phải **auto**.

### 12.2. Registry codegen

> **Trạng thái code:** compiler checklist **đã có** (`app/studio/compiler.py`, `registration.md`); codegen **đã có** `scripts/gen_pattern_registry.py` + `src/sonify/patternRegistry.generated.ts` (39 row, `level`/`nameSource`, `--check` + pytest gate). `PATTERN_NAMES` **đã derive** từ registry, chỉ `level === 'topic'`; `Pedal` và texture names không vào set.

Repo đã có tiền lệ: `scripts/gen_params_schema.py` sinh `paramsSchema.generated.ts` và có `--check`.

Đề xuất:

- `scripts/gen_pattern_registry.py` đọc:
  - `_PATTERN_TITLE`, `_FAMILY`, `_PROFILE`
  - `PROFILES` trong `guitar_wave.py`
  - **không** đọc `_EXPECTED` từ file test; `test_guitar_wave.py` đã assert `set(PROFILES) == _EXPECTED`, nên `PROFILES` là nguồn đủ
- sinh `src/sonify/patternRegistry.generated.ts` (thay hoặc bổ sung `PATTERN_NAMES`).
- `--check` phát hiện drift.
- Repo **không có CI** (`.github/` không tồn tại), nên thêm `backend/tests/test_pattern_registry.py` gọi logic `--check`; pytest là gate thật.

### 12.3. Title coverage, không phải uniqueness toàn cục

`PATTERN_NAMES` là set toàn cục theo title, derive từ registry `level === 'topic'`: **30 title** distinct từ 33 topic row. Toàn bộ registry có 39 row / 34 title (gồm `Pedal`); 38 wave-profile row cho 33 title. **Không test uniqueness toàn cục** — 4 title trùng hợp lệ (`Cantabile`, `Etude`, `Prelude`, `Sarabande`). Test đúng là **coverage + uniqueness theo ensemble**:

```python
from collections import defaultdict

from app.sonify.guitar_patterns import _FAMILY
from app.sonify.guitar_wave import PROFILES
from app.sonify.program import pattern_title

# 1. Coverage: mọi pattern phải có title. Đây là lỗi thật cần bắt.
owners: dict[str, set[str]] = defaultdict(set)
for ensemble, pattern in PROFILES:
    owners[pattern].add(ensemble)

missing_profiles = [(e, p) for e, p in sorted(PROFILES) if not pattern_title(p, e)]
missing_family = [
    p
    for p in sorted(_FAMILY)
    if not any(pattern_title(p, e) for e in (owners.get(p) or {"classic"}))
]
assert not missing_profiles, missing_profiles
assert not missing_family, missing_family

# 2. Uniqueness trong cùng một ensemble, không phải toàn cục.
by_ensemble: dict[str, list[str]] = defaultdict(list)
for ensemble, pattern in PROFILES:
    title = pattern_title(pattern, ensemble)
    if title:
        by_ensemble[ensemble].append(title)
for ensemble, titles in by_ensemble.items():
    assert len(titles) == len(set(titles)), (ensemble, titles)

# 3. Trùng title toàn cục là hợp lệ; Set membership không "nhận nhầm".
```

- `PROFILES` là registry wave profile `(ensemble, pattern)`, không phải palette đầy đủ; `_FAMILY` có thể có pattern không có wave profile. Dùng **hợp** `_FAMILY ∪ PROFILES` cho coverage.
- Với pattern chỉ có trong `_FAMILY`, probe qua ensemble sở hữu trong `PROFILES`; nếu không có, fallback `"classic"`. Giả định: `_PATTERN_TITLE` không phụ thuộc ensemble, trừ `thumb_cantabile`; nếu assumption này đổi, test phải cập nhật.
- `pattern_title()` trả `""` cho id lạ; coverage test phải **fail** khi rỗng, không `filter(None, ...)`.
- Với *Suite Popular Brasileira*, dùng tên đầy đủ `Mazurka-Choro`, `Schottish-Choro`, `Valsa-Choro`, `Gavotta-Choro`, `Choros No. 1`.

### 12.4. Checklist đầy đủ cho pattern mới

Không tham chiếu revision cũ. Đây là danh sách đầy đủ, compiler sinh từ `traits` + `selection`:

**Renderer**

- `backend/app/sonify/guitar_villa.py`: renderer + helper cho pattern mới (`_render_villa_bar`, `_render_thumb`, `_render_etude1_bar`, `_render_etude11_bar` là các hàm hiện có; pattern mới thêm hàm riêng).

**Đăng ký và scheduler**

- `backend/app/sonify/guitar_patterns.py`: `_FAMILY[id]` (boundary/`different_family`).
- `backend/app/sonify/guitar_patterns.py`: nhánh `ctx.ensemble == "villa"` trong `_select_body` để pattern mới **thực sự được chọn**.
- `backend/app/sonify/guitar_patterns.py`: `_dominant_pattern`, `_contrast_pattern`, các fallback dict của Villa.
- `backend/app/sonify/guitar_patterns.py`: dispatch trong `render_patterned_voices`.
- `backend/app/sonify/guitar_patterns.py`: `_PROFILE[id]` sinh từ `profiles.render`.
- `backend/app/sonify/program.py`: `_PATTERN_TITLE[id]` — **chỉ thêm khi `level` là `topic`**. `level: texture` không có title (vi phạm hiện tại: `villa_pattern` → "Arpeggio", `tremolo` → "Tremolo"; xem [`sonify-guitar-model.md`](./sonify-guitar-model.md) §8.1).
- `backend/app/sonify/guitar_wave.py`: `PROFILES[("villa", id)]` sinh từ `profiles.wave`.
- `backend/tests/test_guitar_wave.py`: `_EXPECTED`.

**Frame, scales, velocity**

- `backend/app/sonify/guitar_frame.py`: `_RETAINED_DOORS` nếu có cửa.
- `backend/app/sonify/guitar_frame_rest.py`: cửa của Villa/Barrios/Brouwer (etude11 nằm ở đây).
- `backend/app/sonify/guitar_scale_passages.py`: `_KINETIC_PATTERNS`, `_LOUD_DOWN_PATTERNS`, `_NARROW_ROWS`, `_HOST`.
- `backend/app/sonify/guitar_patterns.py`: `_PEDAL_DOOR_PROFILE`.
- `backend/app/sonify/humanize.py`: `_clamp_guitar` nếu trần velocity khác.
- `backend/app/sonify/guitar_torroba.py`: `_REAL_TORROBA_FIGURES` nếu sentence mới.

**Đăng ký tên và docs**

- `src/sonify/program.ts`: `PATTERN_NAMES` sinh từ codegen, không thêm tay.
- `docs/sonify-pattern-names.md`: cập nhật luật tên và bảng tên.
- `docs/sonify-classical-guitar.md`: cập nhật palette/trạng thái.

**Test**

- `backend/tests/test_sonify_guitar.py`
- `backend/tests/test_humanize.py`
- `backend/tests/test_sonify_guitar_scale_passages.py`
- `backend/tests/test_texture_selection_matrix.py` + `selection_matrix.json`
- `backend/tests/test_texture_render_matrix.py` + `render_matrix.json`
- `backend/tests/test_texture_movement_line.py`: 5 pattern Suite không làm vỡ `pattern_form()`.
- `backend/tests/test_pattern_registry.py`: codegen drift + title coverage + per-ensemble uniqueness.
- Chạy lại cả hai matrix nếu có meter variant mới.

**Không cần cho pattern mới**

- `model.py` `Ensemble`, `ensemble.py` `_ROWS`, `schemas.py` Literal, `src/api/client.ts` `ENSEMBLE_ROWS`: chỉ khi thêm **composer**, không phải pattern.
- `params.py` + `paramsSchema.generated.ts`: chỉ khi đổi meter choice (Phase 3).

---

## 13. Lộ trình

**Trạng thái sau refactor sentence:**

| Phase | Đã có | Còn thiếu |
|---|---|---|
| 0 | Sentence schema/JSON, loader/export, validate/preview per family; `MeterSpec`/`TextureSpec` schema + offline validator; `meter_runtime` resolver; `texture_resolve` pitch/playability bridge; sentence + pattern + render matrices; compiler bundle; registry codegen + derived `PATTERN_NAMES` | renderer-profile playability, Phase 3 runtime 12/8 |
| 1 | Studio room, editor, examples, validate/preview, audio, publish/rollback; session/owner/quota, upload + signed media, Gemini analyze/cache, UI upload + **crop web** + draft table + TextureSpec draft/validate, **in-memory preview/validate job queue**, export bundle JSON, spec owner/visibility | native picker/crop, durable preview media, `preview.wav`/export files, PR automation |
| 2 | Candidate preview Villa/Barrios/Brouwer; Barrios production flag off; Bach exposition preview | Suite Popular Brasileira, Villa sentence audit, `texture_registry.py`, interpreter, codegen |
| 3 | — | Library UI, auth thật, publish qua PR/GitHub App |

### Phase 0 — Chứng minh schema, chưa UI, chưa Gemini (một phần)

- `schema.py` với `MeterSpec` (6 field), `authored/derived`, `profiles`.
- `resolve_runtime_meter()` dùng chung; cấm `active_meter()` ngoài `compose_meter`.
- `validate.py`: meter variants, sentence parent, voice order, authored playable.
- Spec tay cho `chord_melody` (dễ) và `villa_pattern` (khó).
- Round-trip `authored` với renderer hiện tại.
- Preview bằng `slice_score` + `audio.py` (nếu môi trường có MuseScore), hoặc `rendered.json` nếu chưa.
- Sinh `selection_matrix.json` + `render_matrix.json` + hai test tương ứng.
- **Không sửa runtime**: Studio từ chối spec 12/8; runtime giữ hành vi hiện tại. Ghi rõ đây là known bug, fix ở Phase 3.

**Gate**: authored round-trip **placement + pitch reference** đúng; golden hash kiểm absolute pitch; meter gate âm tính; matrix đầy đủ; Studio từ chối 12/8; không có thay đổi runtime.

### Phase 1 — Studio room + Gemini + session (một phần)

- `StudioRoom`, mode `studio`, capability.
- `X-Studio-Session`, owner check, quota.
- Upload/crop, Gemini draft, review table.
- Validate + preview + export bundle.
- Mở `open_beta`.

**Gate**: một người dùng thật upload ảnh, sửa draft, lưu spec, nghe preview, export bundle mà không sửa code.

### Phase 2 — Suite Popular Brasileira + runtime interpreter (chưa)

- Sentence pipeline theo [`sonify-guitar-model.md`](./sonify-guitar-model.md) §13: migrate Torroba (4 archetype) + galop (period 4+4) trước, rồi authoring cho composer còn lại.
- Audit Villa sentence: pattern nào có span thật.
- Chọn movement đầu tiên; tạo pattern spec + meter variants.
- Suite là palette pattern; test movement line với 5 pattern (tối đa 3 title).
- Ít nhất một pattern `runtime: "interpreter"` để chứng minh runtime đọc spec.
- Các pattern khác `runtime: "code"`.
- Compiler sinh registration checklist; test drift.

**Gate**: thêm một movement với meter đúng; ít nhất một pattern chạy từ spec.

### Phase 3 — Thư viện + auth thật (chưa)

- Library UI theo composer/status/meter coverage.
- Auth + entitlement thật; thay session namespace.
- Publish flow qua PR/GitHub App.
- Backup/migration.

---

### 13.11. Quy trình `v2` (chốt 2026-11)

- `v2` là **nhánh tích hợp + chạy local nội bộ**, không phải nhánh chờ merge và không deploy production trong giai đoạn này.
- Feature branch merge **local vào `v2`** sau review + full test; không mở PR `main`.
- Phase 1 xong **không** merge `main`; đánh dấu bằng tag `v2-studio-phase1` (và các tag phase sau).
- Chạy `v2` local nội bộ (backend + `npm run web`) một thời gian, thu feedback, sửa lỗi trực tiếp trên `v2`.
- Chỉ mở **một** PR `main ← v2` khi người phụ trách xác nhận `v2` ổn định; PR #163 đã đóng để tránh merge nhầm.
- Tiêu chí ổn định tối thiểu: full backend + frontend tests xanh, không lỗi P0/P1 trong thời gian chạy local nội bộ, không regression ngoài Studio.

---

## 14. Tiêu chí nghiệm thu

> Đây là **gate của toàn bộ Texture Studio**, không phải checklist đã pass. Đã pass phần sentence (JSON round-trip/plan, validate/preview/publish/rollback, candidates preview, Barrios flag off), **schema/validator** `MeterSpec`/`TextureSpec`, **meter runtime resolver**, **sentence + pattern + render matrices**, **compiler bundle JSON**, **registry codegen + derived `PATTERN_NAMES`**, **session/quota/upload/Gemini analyze**, **spec owner/visibility** và UI draft. Các mục preview `slice_score`, durable preview queue/media, native crop, renderer-profile playability/derived golden, interpreter và Suite vẫn là **mục tiêu**.

1. **Meter exact**: spec lưu đủ 6 field `MeterSpec`; so canonical tuple, không so `id`/string.
2. **Meter sau retarget**: spec khớp `resolve_runtime_meter()` sau `_guitar_meter` + `retarget_torroba_meter`; compiler không gọi `active_meter()` ngoài `compose_meter`.
3. **12/8**: Studio từ chối spec 12/8; runtime Phase 0/1 **không đổi**. Phase 3 mới sửa fallback `"other"` → 4/4 hoặc thêm materializer 12/8.
4. **Không meter per-bar**: không dùng `kind_at` làm meter.
5. **Sentence parent**: sentence không có parent/meter hợp lệ bị từ chối; `sentence.meter` phải thuộc variant list.
6. **Authored round-trip**: cùng placement (bar/beat/duration/voice/staff/tie/slur/accent/staccato) + **pitch reference** (`kind`/index/degree); không so absolute MIDI cho `melody_eighth`/`chord_degree`/`scale_step`; nếu `literal_midi` thì so được.
7. **Rendered golden**: cùng render context + `params` hash + `SPAN_REVISION`/`RECAP_REVISION` + `renderer_version` → cùng hash/snapshot; đây là nơi kiểm absolute pitch. Velocity không so tuyệt đối; không có “humanize seed”.
8. **Preview = slice_score**: preview lấy từ render thật; diff hợp lệ chỉ ở tie biên `start`/`end - 1`.
9. **Storage bền**: DB/upload/preview nằm trên `/data`, sống qua deploy; backup có.
10. **Publish artifact**: server không ghi repo; test data-driven.
11. **Session owner/quota**: không xoá/sửa spec của session khác; Gemini có quota.
12. **Codegen drift**: `gen_pattern_registry --check` + pytest gate.
13. **Title coverage**: mọi pattern trong `_FAMILY ∪ PROFILES` có title không rỗng; uniqueness chỉ theo ensemble. 4 title trùng toàn cục hiện có là hợp lệ.
14. **Runtime proof**: ít nhất một pattern `runtime: "interpreter"` ở Phase 2.
15. **Movement line**: 5 pattern Suite không làm vỡ `pattern_form()`; tối đa 3 title; test in tên.
16. **API/storage contract**: 16 endpoint + DDL + post-Gemini validate có trong doc và test.
17. **Selection + render matrix**: mỗi pattern có ít nhất một input được chọn; render matrix chỉ render pattern đã chọn; `ctx_kind == "other"` fail; `expected_empty` phải có lý do.
18. **Per-voice duration**: mỗi voice không overlap và tổng duration = `bar_beats` hoặc có rest tường minh; không cộng tất cả voice.
19. **Pitch declarative**: spec không chứa tên hàm Python; chỉ dùng `melody_eighth`/`chord_degree`/`scale_step`/`literal_midi`; toàn bộ pitch layer là render-context-relative, chỉ `literal_midi` standalone; `melody_eighth` out-of-range là lỗi.
20. **Publish gate**: `review=pending` hoặc `confidence < 0.6` chưa accept/edit bị từ chối; Gemini tạo `pending`, người nhập tay tạo `edited`.
21. **Registry version gate**: schema ngoài allowlist hoặc JSON hỏng bị bỏ, app vẫn boot; `renderer_version` bắt buộc cho interpreter.
22. **Media token**: preview/export dùng signed token ngắn hạn; `GET /uploads/{id}` kiểm tra owner.
23. **Global preview queue**: 1 worker Studio, render ngoài event loop, tách khỏi `EXPORT_SLOTS`; `previewsConcurrent` chỉ là per-session.
24. **Level/nhãn**: mỗi pattern khai `level` (`topic` / `texture`) + `name_source`; chỉ `topic` được in tên. **Movement** là level trên pattern (`FormSpec` + plan + `title`), không phải `level`. Inventory 39 dòng và các quyết định tên nằm ở [`sonify-guitar-model.md`](./sonify-guitar-model.md) §2.1, §8, §12.
25. **Parent/upload identity**: `parent_slug` là pattern id; upload dedupe qua `studio_blobs.refcount`, xoá 1 owner không xoá file của owner khác.
26. **Pitch context**: `melody_eighth`/`chord_degree`/`scale_step` resolve từ render context; `eighth`/`offset` out-of-range là validation error, không clamp; chỉ `literal_midi` standalone.
27. **Validate queue/partial**: validate dùng cùng global Studio queue với preview; thiếu melody context trả `partial: true` + `skipped_checks`, không silent pass.

28. **Micro-velocity optional:** mỗi figure/slot có thể có contour offset theo nốt; vắng/empty = 0 (kể cả thumb); layer sau chỉ dịch/clamp **trừ attack `pinned`** do absolute writer (snap/stab/fan/trim); Studio click figure → velocity lane và cho sửa.
29. **Extraction zero-diff:** Tremolo 4/4–3/4, Galop 1/2, Etude1, Etude11, **Cathedral Preludio** phải cho cùng danh sách NoteEvent + golden digest/score artifact (production) hoặc renderHash (Studio preview); test baseline vs contour bắt buộc, không được “gần đúng”. Cathedral dùng rule context `canto_at`/`raw_at`/`beats_per_bar`, không lưu offset bịa.
30. **Writer zero-diff:** `VSTOCK_MICRO_VELOCITY_WRITERS` default off; off byte-identical. On: Tremolo 4/4–3/4, Etude1, Etude11, Galop1/2 apply extracted contours before the wave and pinned checks after the last absolute writer; every NoteEvent/golden digest identical. Cathedral writer path and slot/texture overrides remain open.

---

## 15. Rủi ro

| Rủi ro | Cách giảm |
|---|---|
| 12/8 fallback 4/4 | Phase 0 Studio từ chối spec 12/8; runtime không đổi; Phase 3 sửa |
| 3/4 ↔ 6/8 khác accent | Hai variant riêng; `_guitar_meter` form-level; khai `strong_eighths`/`extra_weights` |
| 4/4 → 12/8 không tương đương | `triplet_subdivision` + duyệt tay; không tự động |
| 2/4 không có trong engine | `fold: 2` ở `FormSpec`; tiền lệ `galop`; test bars/DFI |
| Sentence Villa không tồn tại | Phase 0 pattern-only; audit trước |
| Velocity bị coi là authored | Tách authored/derived/rendered |
| Round-trip pitch thành vòng tròn | Authored chỉ so placement/reference; absolute pitch do golden hash |
| Validate tưởng offline được | Dùng render executor; `partial: true` + `skipped_checks` |
| `melody_eighth.offset` clamp âm thầm | Out-of-range là validation error |
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
3. **Villa sentence audit ở Phase 2 hay Phase 1?**
   Đề xuất Phase 2, sau khi round-trip pattern đã ổn.
4. **Session token sống bao lâu?**
   Đề xuất 90 ngày, lưu AsyncStorage; hết hạn tạo mới, spec cũ vẫn thuộc owner cũ nếu có auth sau này.
5. **Preview audio slot**
   **Đã chốt cho MVP:** dùng synth code-only riêng (`app/studio/audio.py`), không đi qua MuseScore nên không tranh slot Nghe. Nếu sau này chuyển sang MuseScore thì mở queue riêng, không tăng `VSTOCK_MUSESCORE_SLOTS`.

---

## 17. Phụ lục A — Những chỗ revision 1 mô tả sai

| Revision 1 | Thực tế |
|---|---|
| “Engine chỉ có 3/4, 4/4, 6/8” | `form.py` có 4/4, 3/4, 6/8, 12/8, 5/4, 6/4, 7/8; guitar dùng 12/8 qua param |
| “2/4 gộp hai ô, đúng cách `olite`” | Không có meter 2/4 trong `form.py`; tiền lệ là `galop` trong `guitar_sor.py` (`_galop1_cell`/`_galop2_cell`) |
| “`olite` scheduler chỉ 4/4” | `"other"` fallback về 4/4 row, nên Olite vẫn có thể được chọn ở meter lạ |
| “`ctx.kind` là meter của movement/bar” | Chỉ movement/per-render; `kind_at` là section kind |
| “Trùng tên in, `PATTERN_NAMES` nhận nhầm pattern của nhà khác” | **Sai**: Set membership collapse, trùng title vô hại; Python `pattern_title` keyed theo id + ensemble. 4 title trùng hiện có là hợp lệ. |
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

| Review 2 | Trạng thái trong revision 4 |
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

### B.3. Review 3

| Review 3 | Trạng thái trong revision 4 |
|---|---|
| 1.1 selection/render matrix | §4.5.1 |
| 1.2 per-voice duration | §9.5 |
| 1.3 pitch declarative | §6.8 |
| 1.4 checklist đầy đủ | §12.4 |
| 2.1 selection/family | §6.7 |
| 2.2 confidence/conflict/review | §6.2, §9.5 |
| 2.3 bỏ `accent_remap` khỏi pattern | §4.4 |
| 2.4 UUID/slug, upload, signed media | §11.3, §11.4 |
| 2.5 registry version gate | §7.2 |
| 3.1 `METER_34` snippet | §4.1 |
| 3.2 `_MAX_FRET` index | §6.6, §9.5 |
| 3.3 title test enumerate | §12.3 |
| 3.4 visibility private | §10.2 |
| 3.5 `unsupported` | §4.4, §4.5.1, §6.7 |
| 3.6 `/access` shape/quota/telemetry | §10.2.1 |
| 3.7 `resolve_runtime_form` owner | §4.4.1 |

### B.4. Review 4

| Review 4 | Trạng thái trong revision 5 |
|---|---|
| 1 title uniqueness fail | §3.2, §12.3, §14.13 |
| 2 `price` không resolve | §6.8, §6.7 |
| 3 checklist thiếu `guitar_villa.py` | §12.4 |
| 4.1 selection vs codegen | §6.7 |
| 4.2 `source.image` path | §6.7 |
| 5.1 fixture signature | §4.5.1 |
| 5.2 ví dụ calm → suite | §4.5.1 |
| 5.3 preview concurrency | §8.2, §10.2.1 |
| 5.4 review default | §6.2, §9.5 |
| 5.5 `parent_slug`/upload dedupe | §11.4 |
| P2.1 bỏ “hoặc form_resolve.py” | §4.4.1 |
| P2.2 codegen dùng `PROFILES` | §12.2 |
| P2.3 render matrix key | §4.5.1 |
| P2.4 written/sounding example | §6.7 |
| P2.5 endpoint count | §11.3, §14.16 (16 sau khi thêm `DELETE /uploads/{id}`) |

---

### B.5. Review 5

| Review 5 | Trạng thái trong revision 6 |
|---|---|
| 1 `melody_eighth` round-trip vòng tròn | §6.1, §6.5, §14.6 |
| 2 pitch layer phụ thuộc render context | §1, §6.8 |
| 3 validate cần render executor | §9.5, §11.3 |
| 4.1 out-of-range không clamp | §6.8 |
| 4.2 preview 404/409/200 | §11.3 |
| 4.3 `DELETE /uploads` + refcount | §11.4 |
| 4.4 coverage probe ensemble | §12.3 |
| 4.5 endpoint count | §11.3, §14.16 (16 sau khi thêm `DELETE /uploads/{id}`) |

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