# Mô hình âm nhạc của lớp guitar — Topic / Texture / Procedure / Sentence / Plan

> **Trạng thái**: đề xuất, dùng làm căn bản cho refactor renderer. **Chưa code.**
> **Phạm vi**: lớp `guitar` trong `backend/app/sonify/` (villa, torroba, barrios, brouwer, bach, classic).
> **Liên quan**: [`sonify-texture-studio.md`](./sonify-texture-studio.md) (PR #142 — file nằm ở nhánh `docs/texture-studio`), [`sonify-pattern-names.md`](./sonify-pattern-names.md), [`sonify-classical-guitar.md`](./sonify-classical-guitar.md), [`sonify-guitar-torroba-plan.md`](./sonify-guitar-torroba-plan.md).
> **Thứ tự**: doc này là điều kiện trước cho (a) refactor renderer và (b) Texture Studio khi thêm texture cho Villa-Lobos.

---

## 1. Vì sao cần doc này

Hai từ đang bị quá tải, và chính chỗ quá tải đó làm mọi cuộc tranh luận về cấu trúc bị lệch:

- **`pattern`** đang đồng thời là: tên in trên chart (topic), cách điền ô nhịp (texture), và đôi khi là cả hình thức của một câu (sentence). Ví dụ `preludio` của Barrios là **một tác phẩm**; `villa_pattern` là **một âm hình**; `galop` là **một điệu nhảy** — cả ba đều là `pattern id`.
- **`figure`** của Torroba không phải "figure" theo nghĩa nhạc lý (động cơ 2–5 nốt). Nó là **texture-span template**: một template nhiều ô, mỗi ô là một texture, chọn theo **độ dài phrase và số thứ tự phrase**. Không phải mọi archetype đọc `closes`:
  - `castillo`: `_castillo_spans` chọn type theo **length**, và `_castillo_34_spans` chọn `WALK`/`CADENCE` theo **`n % 2`** (`guitar_torroba.py:1650`) — không theo `closes`, nên `CADENCE` **không** phải "kết".
  - `sonatina`, `fandanguillo`, `danza`: `_phrase_spans` (`:1763-1774`) mới đọc `phrase.closes`.
  - `torroba_tremolo`, `alcaniz`, `olite`: **không** có template nhiều ô; mỗi phrase một figure đơn qua `_castillos_figure_plan` (`:3687`).

Kết luận đầu tiên: **`figure` nên đổi tên thành `sentence`**. Doc này dùng `sentence` từ đây, với định nghĩa hẹp: **texture-span template**, khác với `Phrase` (`model.py`) là phrase giai điệu. Xem §13.

---

## 2. Các trục

Âm nhạc ở đây được mô tả bằng các trục **trực giao**. Một đối tượng chỉ khai những trục có nghĩa với nó; trục không khai là rỗng, không phải "chưa làm".

| Trục | Trả lời | Ví dụ |
|---|---|---|
| **Pattern level** | Pattern tự đứng tên được (`topic`) hay chỉ là idiom kỹ thuật (`texture`) | `castillo` = topic; `tremolo` = texture |
| **Topic** (định danh) | **Tên in ra** của đơn vị | có trong code: `Fugue`, `Castillo`, `Etude`; **target-state, chưa có**: `Cathedral` (`preludio` vẫn in "Prelude"), `Mazurka-Choro` |
| **`name_source`** (metadata hiển thị) | Cái tên đến từ đâu: `dance` / `work` / `genre` / `form` / `function` / `character`. **Không phải cơ chế** | `Sarabande` = dance; `Castillo` = work; `Etude` = genre; `Fugue` = form; `Prelude` = function; `Cantabile` = character |
| **Texture** (âm hình) | Cách **điền một ô**: voicing, rhythm cell, articulation | arpeggio/campanella, chord-melody, tremolo, bariolage, galop cell |
| **Procedure** (thủ pháp) | **Phép biến đổi sinh ra chất liệu** từ melody/harmony | **imitation** (fuga). Chaconne **không** phải ground bass, xem §4.1 |
| **Sentence** | **Texture-span template**: N ô + vai + slot, chọn theo length/`n`, có archetype đọc `closes` | castillo walk/cadence (9 ô, theo `n % 2`), arada/float, type6 4 ô, galop period 4+4 |
| **Cell** | Biến thể của texture, không phải đơn vị độc lập | galop 1 / galop 2, castillo type 7 / type 8 |
| **Plan** | Quan hệ giữa các đơn vị theo thời gian: scope, candidate, post-pass | A–B–A, contrast/trio, avoid-repeat, khoá một pattern |

`sentence` ở đây là **texture-span template**, không phải "sentence" theo nghĩa nhạc lý 8 ô (presentation–continuation–cadence) và không phải `Phrase` (`model.py`) — `Phrase` là phrase giai điệu do price tạo. Quan hệ: một `Phrase` được chia thành các `sentence` span, mỗi span gồm các slot texture.

### 2.1. Movement là level **trên** pattern, không phải một giá trị của `level`

Movement không phải một loại pattern. Nó là **đơn vị biểu diễn** chứa 1..N pattern, có hình thức/độ dài/nhịp/tông riêng.

| | **Movement** | **Pattern** |
|---|---|---|
| Là gì | đơn vị biểu diễn: bản 1D, chương I–IV của 1M, một tuần | slot filler trong một movement |
| Có gì **hiện tại** | `Movement`: `label`, `spec`, `session_count`, `rest_after` (`span.py:794`); `PreparedMovement`: thêm `bars`, `groups`, `key`, `character`, `mode`… (`:835`) | `level`, topic, texture, procedure, sentence, wave profile, family, door |
| Có gì **sẽ thêm** | `title` (chưa có), `plan` (chưa có; plan đang suy từ `_patterns`) | — |
| Chứa | **1..N pattern** | 0..N sentence |
| Quyết định | hình thức, độ dài, nhịp, tông, tên in của chương | cách điền ô, nhãn, thủ pháp, câu |

Bằng chứng trong code:

- Movement = `PreparedMovement` (`span.py:835`), dựng từ `Movement` (`span.py:794`). Số movement theo span: `plan_week` trả **1** (`span.py:800`), `plan_month` trả **4** (I–IV, `:805`), `plan_quarter` trả **3** (`:816`).
- **1D không có `Movement`/`PreparedMovement`.** Nó đi thẳng qua `audio._render` (`audio.py:1696-1712`), với `title=f"{symbol} {day.isoformat()}"`; tên bài (`dance`) do `guitar_movement_name` sinh rồi lưu vào `movementName` của payload audio.
- **1D không phải "1 movement = 1 pattern".** 1D = 34 bar (`DAILY_ENSEMBLE_SPEC`, `form.py:292`; hằng số `:261-265`). `_assign_macro` có nhánh riêng cho Barrios 1D (`bars == 34`, 120 BPM, 4/4) **đi từng phrase qua `_select_body`** (`guitar_patterns.py:1593-1612`), nên một ngày Barrios có thể chứa nhiều pattern. Test hiện có: `test_program.py::test_barrios_day_names_the_pattern_the_writer_picks` — 1D calm in "Tremolo" dù mở đầu là Preludio.
- **Tên của 1D là `headline_id`, không phải cả row.** `form_pattern_ids` trả `[primary]` khi không có contrast section (`guitar_patterns.py:3295-3340`); `primary = headline_id(...)` (`:3330`) là pattern chiếm đa số. Vì vậy một movement nhiều pattern vẫn có thể in một tên.
- **1D không có movement line.** Frontend `pieceCopy`/`workForm` (`src/sonify/program.ts:338-416`): guitar lấy `form = count > 1 ? 'Suite' : dance`; với 1D (`count === 1`) tên pattern đi vào **title**, `movement = null`.
- **1W:** `week_spec` là *"One continuous movement"* (`span.py:205`). **1 phiên = 32 bar thường** bị nhánh `bars <= 40` khoá một pattern (comment ngay tại `guitar_patterns.py:1593-1596`). Ngoại lệ: **classic + galop** có thể bị `_settle_galop` tách thành study/galop dù 32 bar — nên nói "thường", không tuyệt đối. Từ 2 phiên (64 bar) mới vượt ngưỡng và đi macro/region.
- **1M/3M:** 1M = 4 movement, 3M = 3 movement; mỗi movement nhiều pattern.

**Đường chạy thật (đo bằng runtime, không phải suy từ span):** `_patterns` (`guitar_patterns.py:991-1000`) chỉ gọi `_select_body` khi **unframed**. Mọi movement thật (`1W`, `1M`, `3M`, `1Y`) đều framed → `_assign_macro` → `_dominant_pattern_auto` / region row. Vì vậy **macro path mới là đường chính của sản phẩm**; phrase path chỉ dùng cho fixture và Barrios 1D.

| Case | Body row (rút gọn) | Tên in |
|---|---|---|
| barrios 1D calm | `pedal, preludio, tremolo, tremolo, andante, tremolo, tremolo, andante, tremolo, pedal` | **Tremolo** (`headline_id`) |
| villa 1D calm | toàn body `chord_melody` | **Chord Melody** |
| villa 1M I calm | toàn body `chord_melody` | movement line **Chord Melody** |
| villa 1W 5 phiên rally | toàn body `etude1` | **Etude 1** |
| barrios 1W 5 phiên rally | `preludio … andante … preludio` | **Prelude — Andante — Prelude** |
| villa 1W 1 phiên | body `etude1` | **Etude 1** |

Hệ quả: **`chord_melody` không phải "âm hình dùng cho nhiều đoạn"** — với Villa 1M I calm nó là **toàn bộ chương**. Bỏ in nó sẽ làm rỗng movement line, không phải chỉ mất một nhãn phụ.

**Gap hiện tại (phải sửa trước khi bỏ in texture):** guitar chưa có tên movement độc lập.

- `movement_title()` trả **`None` cho guitar, và cho cả 1D/1W** (`span.py:943-947`) — không chỉ guitar.
- `span_movement_name()` trả `stored` (`program.py:163-164`), tức tên đã ghi lúc render.
- `stored` do `guitar_movement_name` dựng từ `pattern_form()` — **tối đa 3 tên pattern** (`program.py:60-90`).

Nghĩa là hôm nay "tên chương" của guitar **là `form_pattern_ids`/`headline_id`**, không phải identity của movement. Bốn mắt xích phải sửa cùng lúc:

1. **Backend:** thêm `title` cho `Movement` và `PreparedMovement`, thread qua 3 chỗ dựng (`span.py:1090, 1148, 1281`) **và** đường 1D (`audio._render`). 1D không có `Movement`, nên chỉ thêm field là không đủ.
2. **Frontend:** `src/sonify/program.ts` — `PATTERN_NAMES`, `isPatternForm` (`:350-355`) chỉ nhận khi **mọi** phần ` — ` nằm trong `PATTERN_NAMES`, nên title tự do kiểu `"Suite Popular Brasileira — Mazurka-Choro"` sẽ bị `formatMovement` bỏ và chỉ còn meter. Phải sửa `workForm`/`pieceCopy` (`:338-416`) + `program.test.ts` (`:185-192`).
3. **Cache:** `movementName` nằm trong payload; cache key `_stem(... len(bars), ensemble, values)` **không chứa tên** (`audio.py:1142-1206`). Đổi `_PATTERN_TITLE` sẽ phục vụ tên cũ từ cache → phải bump `SPAN_REVISION` (`audio.py:58`).
4. **Parity tên:** `data_digest` (`dfi.py:52`) chỉ hash bar; `scale_fingerprint` (`span.py:858`) không chứa tên. Vì vậy **parity bằng Score hash không bắt được regression về tên** → cần golden riêng cho `form_pattern_ids`/`_written_dance`.

Ví dụ `"Suite Popular Brasileira — Mazurka-Choro"` trong doc này là **target-state**, không phải tên đang có trong code.

Form (hình thức của cả chương) **không phải** thuộc tính của pattern. Form sống ở hai chỗ: `FormSpec.sections` (`span.py`) và Plan.

Bảng phân biệt gọn:

| | Trả lời | Thuộc về |
|---|---|---|
| **Topic** | "Đơn vị này **là gì**, in tên gì" | một pattern |
| **Movement** | "Đơn vị biểu diễn nào đang chứa nó" | movement (`FormSpec` + Plan + title) |
| **Form** | "Các đơn vị được **xếp** thế nào" | movement (`FormSpec` + Plan) |

---

## 3. Luật

1. **Pattern có `level`; nếu `level: topic` thì có Topic.** Movement chứa 1..N pattern và có `FormSpec`/Plan riêng. Topic là identity của pattern; Form là relation giữa các pattern.
2. **Nhãn (Topic) là tên đơn vị, không bao giờ là kỹ thuật.** `Arpeggio`, `Tremolo`, `Chord Melody` là kỹ thuật → `level: texture`, không in (xem §8). Tên mượn từ tác phẩm (`Castillo`, `Juglar`) là hợp lệ với `name_source: work`.
3. **Chỉ khai cái code thực thi.** Với mỗi pattern hỏi: *"renderer làm gì mà pattern khác không làm?"* Câu trả lời là texture/procedure. Không có câu trả lời → đó là **label**, không phải cơ chế.
4. **Form là metadata của pattern; cơ chế hình thức thuộc movement.** Khai `form: "fugue"` trên pattern không làm engine hiểu fugue; muốn hiểu phải khai `form.functions[]` ở tầng movement.
5. **Cell không phải pattern; variation không phải lớp.** Biến thể trong ô là `texture.cells`; biến hoá giữa các câu là `plan`.
6. **Meter không phải pattern.** `ctx.kind` là per-render, và `_guitar_meter` (`span.py:288`) còn hoán đổi 3/4 ↔ 6/8. Meter thuộc `meter_variants` của texture.
7. **1D không "trùng tên vì một pattern".** 1D là movement **không có movement line**; tên của nó là `headline_id`, và với Barrios 1D có thể là hỗn hợp nhiều pattern (§2.1).

---

## 4. Bach: counterpoint là **procedure**, không phải texture hay form

Counterpoint (đối âm) là **tên gọi chung của một họ thủ pháp**: imitation, canon, invertible counterpoint, sequence… Nó chỉ thành "texture" khi dùng như tính từ (*contrapuntal texture* = bề mặt nhiều bè độc lập). Vì cùng một từ dùng cho cả luật lẫn kết quả, nó mới trượt.

Định nghĩa thực dụng trong code:

> **Procedure = hàm nhận melody/harmony rồi sinh ra voice khác.**

Fugue không phải cái hộp "form"; nó là **quá trình sinh hình thức**:

```
subject → answer (real/tonal) → countersubject → episode (sequence) → stretto
```

### 4.1. Code Bach thực sự làm gì

`_render_bach_fuga_bar` (`guitar_bach.py:668`):

```
"""Soprano sings the price now. The bass answers two bars later, 1:1, on this chord."""
```

- `_fuga_motif` (`:490`): *"(offset, length, direction) of the lagged subject, **1:1 and never retrograde**"* → subject được rút thành **contour**, mỗi run một hướng.
- `_compose_fuga_bass` (`:603`): voice 3 đáp subject từ **2 ô trước**, từng bậc một, không retrograde.
- Answer được hoà âm lại theo hợp âm hiện tại ("on this chord") → **tonal adaptation**, không phải real answer.

Vậy `bach_fuga` thực thi đúng **một procedure: imitation (lag 2 ô, contour 1:1, không retrograde, không inversion)**. Nó không có exposition, episode, countersubject, stretto, hay key plan. Tên `bach_fuga` là **nhãn thể loại**, không phải mô hình.

Chaconne **không** phải ground-bass procedure. `_render_bach_chaconne_bar` (`:1464`) mô tả "ground in the bass", nhưng code chỉ có `_chaconne_bass_slots` (`:1444-1449`) trả **vị trí** `[0,8]` / `[0,6]` / `[0,4]`, rồi lấy pitch từ `_bach_bass(ctx, chord, …)` **từng ô theo hợp âm hiện tại**. Đây là **ostinato nhịp** (vị trí lặp), **không** phải ground bass **hoà âm** (pitch đổi theo hợp âm từng ô), và cũng không có biến hình trên bass cố định. Nên `procedure: none`; nếu muốn gọi là procedure thì phải định nghĩa procedure rộng hơn ("lặp nhịp cũng là procedure"), nhưng khi đó mất tính executable.

Ghi chú: motif **contour** đã được mô hình hoá cho fuga (`(offset, length, direction)`); motif dạng **pitch cell** thì chưa.

### 4.2. Bảng Bach

| Pattern | Topic (label) | `name_source` | Procedure (executable) | Texture | Sentence |
|---|---|---|---|---|---|
| `bach_fuga` | Fugue | form | **imitation** lag 2, contour 1:1, no retrograde | polyphony 3 bè | null |
| `bach_chaconne` | Chaconne | form | **none** — bass cell, không phải ground bass | bariolage 16th trên bass | null |
| `bach_prelude` | Prelude | function | **none** — label "figuration" không executable | broken chord | null |
| `bach_allemande` / `courante` / `sarabande` / `bourree` / `gavotte` | tên điệu | dance | **none** — "sequence" chỉ là nhận xét, không có hàm | polyphonic / homophonic | null |
| `bach_gigue` | Gigue | dance | **none** | polyphonic | null |

Toàn bộ code chỉ có **một** procedure executable: `imitation` ở `bach_fuga`.

---

## 5. Sáu chỗ hay nhầm, đã chốt

> **Đường chạy:** các điều kiện dưới đây là **phrase path** (`_select_body`), chỉ dùng khi movement **unframed** và cho Barrios 1D. Đường chính của sản phẩm là **macro path** (`_assign_macro` → `_dominant_pattern_auto`), xem §6. Đừng đọc bảng này như luật chọn của 1W/1M/3M.

| Trường hợp | Không phải | Là |
|---|---|---|
| **Galop 1 / Galop 2** (Sor) | hai sentence, hai topic, hai pattern | **hai cell** trong một texture. `_galop1_cell` (`guitar_sor.py:291`), `_galop2_cell` (`:349`); `_render_galop_dance` (`:413`) chọn theo `index % 8 >= 4` — 4 ô "câu hỏi", 4 ô "câu trả lời" |
| **Tremolo** (Barrios) | sentence | **texture**. Trong **phrase path** nó được chọn theo điều kiện giai điệu (`hold` + 90 ≤ bpm ≤ 140, `guitar_patterns.py:940`); ở macro path nó là ứng viên của `_dominant_pattern_auto` |
| **Arpeggio** | topic | **họ texture** trong `_FAMILY`. `_ARPEGGIO` (`guitar_patterns.py:47`) là **dead code** — chỉ có dòng định nghĩa, không được dùng; đừng trích nó làm bằng chứng. Việc `villa_pattern` in "Arpeggio" là lỗi nhãn (§8) |
| **Cathedral Preludio** (Barrios) | sentence | **movement-level**: `_catedral_preludio` (`guitar_barrios.py:19`) chọn texture (16th thật nếu movement có frame, 8th nếu fixture) |
| **Perpetual tremolo** (Barrios, `_perpetual_bars` `:571`) | pattern thứ hai | **variation của texture** trong cùng topic: 2 bar khi `band == "f"` và `mood == "volatile"` |
| **Alcaniz / Olite / Juglar** (Torroba) | sentence nhiều ô | **single-figure trải hết phrase** qua `_castillos_figure_plan` (`guitar_torroba.py:3687-3723`), không có template slot. Chỉ `castillo`, `sonatina`, `fandanguillo`, `danza` nằm trong `_TORROBA_PATTERNS` và đi `select_torroba_spans` |

---

## 6. Bảng 6 composer theo trục thực thi

38 dòng `PROFILES` (không tính `pedal`):

| | Pattern (topic / texture) | Procedure | Sentence | Plan scope |
|---|---|---|---|---|
| **Villa** | 5 (2 / 3) | none | null | framed (1D/1W/1M/3M) → macro; unframed → phrase |
| **Torroba** | 7 (7 / 0) | none | **4 template** (castillo, sonatina, fandanguillo, danza) + **3 single-figure texture** | macro `_torroba_primary/_contrast` |
| **Barrios** | 8 (6 / 2) | none | null | 1D 34/120/4/4 → phrase; framed dài → region row; còn lại macro |
| **Sor / Classic** | 5 (5 / 0) | none | **period 4+4** (galop) | macro + post `_settle_galop` |
| **Bach** | 9 (9 / 0) | **imitation** (chỉ `bach_fuga`) | null | framed dài → region row; còn lại macro |
| **Brouwer** | 4 (4 / 0) | none | null | macro `_brouwer_primary/_contrast` |

Plan không phải một tầng duy nhất; nó có ba scope và hai post-pass:

| Scope | Hàm | Khi nào |
|---|---|---|
| **Phrase** | `_select_body` (`guitar_patterns.py:894`) | chỉ khi **unframed** (`_patterns`, `:999`), cộng nhánh Barrios 1D đặc biệt (`:1593-1612`) |
| **Macro** | `_assign_macro` (`:1537`) | framed: khoá một pattern (`bars <= 40`), A–B–A khi có contrast, hoặc region row |
| **Candidate chooser** | `_dominant_pattern_auto` (`:1118`), `_classic_macro`, `_torroba_primary`, `_bach_primary`, `_brouwer_primary` | chọn ứng viên cho một scope |
| **Region row** | `_barrios_palette` (`:1248`), `_bach_region_patterns` (`:1323`) | framed dài (>40 bar) |
| **Post-pass** | `_settle_galop` (`:1691`), `_paint`, `_has_contrast_section` | sửa lại row sau khi chọn |

Vì vậy "Villa 1D dùng `_select_body`" là **sai**: 1D framed đi macro → `_dominant_pattern_auto`. Chỉ Barrios 1D mới đi `_select_body`.

---

## 7. Ánh xạ code → trục

| Code | Trục |
|---|---|
| `span.py:288` `_guitar_meter`, `span.py:299 retarget_torroba_meter` | form-level retarget (không phải pattern/procedure) |
| `guitar_patterns.py:318` `_meter_kind` | bucket meter → **materialization**, không phải identity |
| `guitar_patterns.py:48` `_FAMILY` | **behavioral family**, không phải taxonomy: quyết định có approach note (`:3976`) và có silence cuối phrase (`:4419`). Đổi family = **đổi audio**, parity phải cover |
| `guitar_patterns.py:47` `_ARPEGGIO` | **dead code**: chỉ có dòng định nghĩa, không dùng. Bỏ khỏi mọi lập luận |
| `guitar_patterns.py:88` `_PROFILE` | profile playability theo pattern |
| `guitar_wave.py:108` `PROFILES` | velocity contour theo `(ensemble, pattern)` — **registry đúng key**, không theo id đơn |
| `program.py:53` `pattern_title` | **Topic** (tra nhãn theo `(pattern, ensemble)`) |
| `program.py:60` `pattern_form` | **label renderer**: nối chuỗi + collapse + tối đa 3. **Không phải** logic hình thức |
| `guitar_patterns.py:3295` `form_pattern_ids` | **Form/Plan row** (1 tên, A–B–A, hoặc region row) |
| `guitar_patterns.py:3330` `headline_id` | **Plan**: pattern chiếm đa số |
| `guitar_patterns.py:3266` `contrast_id` | **Plan**: pattern ở trio/bridge |
| `guitar_patterns.py:971` `_patterns` | **Plan scope switch**: framed → macro, unframed → phrase |
| `guitar_patterns.py:894` `_select_body` | **Plan** (scope phrase, chỉ unframed + Barrios 1D) |
| `guitar_patterns.py:1118` `_dominant_pattern_auto` | **Plan** (macro candidate chooser) |
| `guitar_patterns.py:1378` `_contrast_pattern` | **Plan** (tương phản) |
| `guitar_patterns.py:1537` `_assign_macro` | **Plan** (macro scope: khoá 1, A–B–A, region) |
| `guitar_patterns.py:1248` `_barrios_palette`, `:1323` `_bach_region_patterns` | **Plan** (region row) |
| `guitar_patterns.py:1691` `_settle_galop` | **Plan** post-pass |
| `guitar_torroba.py:3403` `_FIGURES` | **Texture của slot** trong sentence |
| `guitar_torroba.py:1660` `_castillo_spans` | **Sentence**: length + `n % 2`; **không** đọc `closes` |
| `guitar_torroba.py:1763` `_phrase_spans` | **Sentence**: sonatina/fandanguillo/danza mới đọc `closes` |
| `guitar_torroba.py:3687` `_castillos_figure_plan` | **Figure đơn**, không phải sentence |
| `guitar_torroba.py:1826` `torroba_figure_plan` | **Sentence plan** (bar → slot) |
| `guitar_sor.py:291/349` galop cells | **Cell** |
| `guitar_barrios.py:571` `_perpetual_bars` | **Texture variation** |
| `guitar_bach.py:490` `_fuga_motif`, `:603` `_compose_fuga_bass` | **Procedure** (imitation) |
| `guitar_bach.py:1444` `_chaconne_bass_slots` | **Bass texture cell**, không phải procedure |
| `guitar_frame.py:1233` `_RETAINED_DOORS`, `guitar_torroba_doors.py:946` `DOORS` | **Plan** (intro/outro), không phải texture |

---

## 8. Vi phạm hiện tại

| Vi phạm | Bằng chứng | Sửa |
|---|---|---|
| Nhãn là kỹ thuật: `villa_pattern` in **"Arpeggio"** | `_PATTERN_TITLE["villa_pattern"] = "Arpeggio"` (`program.py`) | `level: texture`, không in; tên chương do `Movement.title` |
| Nhãn là kỹ thuật: `tremolo` in **"Tremolo"** | `_PATTERN_TITLE["tremolo"] = "Tremolo"` | như trên |
| Nhãn là kỹ thuật: `chord_melody` in **"Chord Melody"** | `_PATTERN_TITLE["chord_melody"]` | như trên |
| Cùng một texture, hai title: `thumb_cantabile` | barrios "Cantabile", villa "Prelude" (`program.py:55` special-case) | `level: texture`, title null cho cả hai; registry key `(ensemble, id)` |
| `pattern` không khai `level` | 38 id, không phân biệt topic với texture | thêm `level` + `name_source` |

Chỉ **3** pattern texture đang in tên: `villa_pattern`, `tremolo`, `chord_melody`. **`pedal` chưa từng in**: `form_pattern_ids` trả `[]` khi primary là `pedal` (`guitar_patterns.py:3323-3324`), `headline_id`/`contrast_id` skip `pedal`, `_region_pattern_ids` skip (`:1291`).

### 8.1. Đề xuất tên cho các nhãn đang sai

Tiêu chí: nhãn phải là **tên đơn vị** (điệu, thể loại, character, hoặc idiom mượn tên tác phẩm). Nếu pattern là **texture thuần** thì `level: texture`, `title = null`, và **không in** — tên chương do `Movement.title` in.

`thumb_cantabile` là **cùng một texture** (`_render_thumb`) dùng cho hai tác phẩm, nên `level: texture` và title null cho cả hai. Cách sạch nhất không phải tách id mà là **registry key `(ensemble, id)`** — đúng như `PROFILES` đã làm (`guitar_wave.py:110`). `pattern_title` đã special-case ensemble (`program.py:55`), nên đây chỉ là chính thức hoá hiện trạng, không phải bước lùi.

| Pattern | Hiện tại | Đề xuất | Lý do |
|---|---|---|---|
| `villa_pattern` | "Arpeggio" | `level: texture`, title null | kỹ thuật; tên chương lấy từ `Movement.title` |
| `tremolo` (barrios) | "Tremolo" | `level: texture`, title null | kỹ thuật; tên tác phẩm thuộc `Movement.title` |
| `chord_melody` | "Chord Melody" | `level: texture`, title null | kỹ thuật |
| `thumb_cantabile` | "Cantabile" / "Prelude" | `level: texture`, title null; key `(ensemble, id)` | cùng một texture cho hai tác phẩm |
| `pedal` | — (không in) | `level: texture` | đã đúng; chỉ khai để registry đầy đủ |

**Checklist migration `Movement.title` — 4 mắt xích + 3 quyết định, phải làm cùng lúc:**

- [ ] **Backend:** `title` cho `Movement` và `PreparedMovement`; thread qua `span.py:1090, 1148, 1281` **và** đường 1D `audio._render` (`audio.py:1696-1712`). 1D không có `Movement`, nên chỉ thêm field là không đủ.
- [ ] **Frontend:** `src/sonify/program.ts` — `PATTERN_NAMES`, `isPatternForm`, `workForm`, `pieceCopy`; title tự do phải qua được `formatMovement`, và 1D phải giữ tên bài trong **title**. Test: `src/sonify/program.test.ts:185-192`.
- [ ] **Cache:** bump `SPAN_REVISION` (`audio.py:58`). `movementName` nằm trong payload, cache key không chứa tên.
- [ ] **Name golden:** golden riêng cho `form_pattern_ids`/`_written_dance` (1D headline, 1W row, 1M A–B–A, Torroba row). **Không** dùng Score hash.

**Ba chỗ sẽ gãy nếu chỉ set `title = null`:**

1. **Có hai đường in tên.** `_written_dance` (`program.py:89-95`) ưu tiên `pattern_form(forms[0])`, nhưng **fallback** sang `pattern_title(found[0])`. Chỉ set title null sẽ chặn đường 1, đường 2 vẫn in nếu `found` còn phần tử. Phải chặn ở **cả hai** hoặc bỏ fallback.
2. **Lọc texture khỏi `pattern_form` sẽ làm mất A–B–A.** Row `[preludio, tremolo, preludio]` lọc còn `[preludio, preludio]` → collapse thành `"Cathedral"`. Khi texture không in, `pattern_form` **không còn mô tả hình thức**; phải quyết A–B–A hiển thị ở đâu (mô tả riêng cạnh `Movement.title`, tooltip, hay chart section) hoặc chấp nhận mất.
3. **Movement line có thể đã rỗng trước khi render.** `span_movement_name` trả `stored`; `stocks.py:646` truyền `cached.movement_name if cached else ""`. Movement chưa render audio → `""`. Vậy hôm nay line đã có thể rỗng, không cần đợi bỏ in texture — lý do mạnh hơn để `Movement.title` **derive từ spec**, không phụ thuộc render.

- [ ] Chặn cả hai đường in tên (`pattern_form` + fallback `pattern_title`) hoặc bỏ fallback.
- [ ] Chốt chỗ hiển thị A–B–A khi texture không in.
- [ ] `Movement.title` derive từ spec (không cần render), vì `stored` có thể rỗng.

Lưu ý: `data_digest` (`dfi.py:52`) chỉ hash bar, `scale_fingerprint` (`span.py:858`) không chứa tên → **DFI không đổi** khi đổi nhãn, và parity audio không bắt được lỗi tên. Đây là lý do phải có name golden riêng.

### 8.2. Bốn câu hỏi nội dung cần chốt

> Q1 cũ (7 pattern Torroba là movement hay topic) **đã chốt**: `topic`. Movement là level trên pattern (§2.1), nên câu hỏi đó không còn.

| # | Câu hỏi | Vì sao cần chốt | Khuyến nghị |
|---|---|---|---|
| 1 | `study` (classic) in "Etude" ở mọi đoạn mặc định: giữ `topic` hay chuyển `texture`? | "Etude" là thể loại, không phải kỹ thuật → được phép in; nhưng `study` là fallback mặc định nên in "Etude" ở mọi đoạn có thể là nhiễu | giữ `topic` + "Etude" (đúng thể loại); chỉ đổi nếu nghe thấy nhiễu |
| 2 | `mozart_var` in "Variations" nhưng code chỉ là bass + counter-melody | Tên gợi `procedure: variation` nhưng **không có procedure** trong code | giữ nhãn, khai `procedure: none`, ghi backlog "variations thật" |
| 3 | `bach_gigue` có nên dùng `procedure: imitation`? | Gigue ngoài đời thường fugal; code hiện không imitation | không, ở giai đoạn này — thêm là **thay đổi hành vi**, cần nghe duyệt |
| 4 | `Movement.title` lấy từ đâu, và 1D lấy gì? | `FormSpec` **không có** `title` (`form.py:171-181`: bars/bpm/sections/chunks/borrowed/meter); `Movement`/`PreparedMovement` cũng không. `month_specs` dùng chung cho mọi symbol, nên title theo bài không thể nằm trong spec. `pieceCopy` là hàm hiển thị frontend, không phải nguồn dữ liệu | **(A) bảng curated `(variant, span, ensemble, index, character) → title`** ở tầng plan/router, giống `_home(symbol)`; 1D dùng bảng này hoặc giữ `headline_id` làm tên bài. **(B) `headline_id`** chỉ là `pattern_form` đổi tên, không giải quyết identity. **(C) spec mang title** — sai vì spec dùng chung cho mọi symbol |

---

## 9. Cây phân loại cho mọi thứ mới

0. Có `FormSpec` riêng (meter/tempo/bars/sections) và chứa 1..N pattern? → **Movement** (không phải pattern).
1. Đơn vị có **tự đứng tên** được (điệu/thể loại/character/idiom mượn tên tác phẩm)? → `level: topic` + `name_source`.
2. Chỉ nói **cách điền trong ô**, tên là kỹ thuật, giữ nguyên qua nhiều phrase? → `level: texture` (+ `cells`), không in.
3. Chiếm **N ô với vai**, chọn theo length/`n`/`closes`? → `sentence` (texture-span template).
4. Chỉ là **2–5 nốt** và được nhắc lại/biến hình? → `motif`.
5. Là **phép biến đổi** sinh voice khác? → `procedure`.

Lưu ý: câu 0 hỏi *đơn vị*, câu 1–2 hỏi *pattern*. 1D là movement không có movement line, tên là `headline_id` — không phải bằng chứng "pattern = movement".

---

## 10. Hệ quả cho refactor

1. **Không promote variation thành pattern.** Nhánh per-bar (`band`, `tresillo`, `approach`, `perpetual`) thuộc texture; promote sẽ vi phạm contract "pattern chọn theo phrase".
2. **Hai lớp còn thiếu**: `sentence` (texture-span template, §13) và **`Movement.title`** (guitar). Cái thứ hai là điều kiện trước để bỏ in texture.
3. **`procedure` là executable; `form` là metadata của pattern và là cơ chế của movement.** Đừng để spec khai `form` rồi tưởng engine hiểu.
4. **Plan có ba scope, không phải hai bản luật.** Phrase (`_select_body`), macro (`_assign_macro`), region row (`_barrios_palette`/`_bach_region_patterns`), cộng post-pass (`_settle_galop`). Phrase/macro tách nhau là **by design** (framed vs unframed). Cái trùng lặp thật là **per-ensemble primary chooser** (`_dominant_pattern_auto` vs các `_*_primary`), và chỉ nên thu hẹp chỗ đó.
5. **Parity phải tách làm hai**: `audio parity` (Score hash trên ma trận ensemble × meter × mood × band × bpm × span) và `name parity` (golden `form_pattern_ids`/`_written_dance`). Score hash **không** bắt được lỗi tên.
6. **Harness chưa tồn tại.** Không có test parity/golden nào trong `backend/tests`. Đây là deliverable R1, không phải giả định.
7. **Bảng inventory đã có** (§12). Việc tiếp theo: registry (`level`/`name_source`) + R1 parity, rồi `sentence` (§13) và `Movement.title`.

---

## 11. Câu hỏi mở

1. **`Movement.title` là identity hay mô tả?** Nếu là identity (`"Suite Popular Brasileira — Mazurka-Choro"`), A–B–A của 3 phần sống ở đâu — trong `FormSpec.sections` hay trong title? Nếu là mô tả, nó chỉ là `pattern_form` đổi tên.
2. **Tên `sentence`**: giữ `sentence` (đã dùng trong PR #142) với định nghĩa hẹp "texture-span template", hay đổi thành `archetype`/`phrase_template` để khỏi lẫn với `Phrase` và với "sentence" nhạc lý 8 ô?
3. **`form.functions[]`** (exposition/episode/stretto, real vs tonal answer) có nằm trong phạm vi Phase 2–3, hay để sau?
4. **Motif pitch-cell** có cần mô hình hoá, hay chỉ giữ contour như fuga hiện nay?
5. **A–B–A hiển thị ở đâu khi texture không in?** Nếu lọc texture khỏi `pattern_form`, row `[preludio, tremolo, preludio]` mất dấu B. Khuyến nghị: `Movement.title` là identity, thêm `form_description` (không in) để tooltip/subtitle giữ A–B–A; hoặc in A–B–A ở chart section riêng.

---

## 12. Phụ lục A — Inventory pattern (39 dòng)

Nguồn: `PROFILES` = **38 dòng** `(ensemble, id)` nhưng chỉ **37 id unique** (`thumb_cantabile` có ở cả barrios và villa); `_FAMILY` = **38 id** (gồm `pedal`), nên bảng có **39 dòng** = 38 dòng `PROFILES` + `pedal`. Cột `level` là **đề xuất**; `?` = cần chốt (§8.2). Texture lấy từ docstring của renderer tương ứng.

| Ensemble | id | Title hiện tại | Level | Texture (+cells) | Procedure | Sentence |
|---|---|---|---|---|---|---|
| bach | `bach_allemande` | Allemande | topic | style brisé bè 8, pickup 4×16 | none | null |
| bach | `bach_bourree` | Bourree | topic | treble = price; bass quarter đáp 8th | none | null |
| bach | `bach_chaconne` | Chaconne | topic | bariolage 16 trên bass; bass ostinato **nhịp**, không phải ground bass hoà âm | none | null |
| bach | `bach_courante` | Courante | topic | melody 8th + rhythm theo price; bass ngân cả ô | none | null |
| bach | `bach_fuga` | Fugue | topic | soprano = price; bass trễ 2 ô | **imitation** (lag 2, contour 1:1, no retro) | null |
| bach | `bach_gavotte` | Gavotte | topic | quarter, staccato quarter, 4×8 song song 3/6 | none | null |
| bach | `bach_gigue` | Gigue | topic | broken chord + scale khi line lên | none (`?` §8.2.3) | null |
| bach | `bach_prelude` | Prelude | topic | 2 bè; mỗi price 8 + neighbor; bass attack | none | null |
| bach | `bach_sarabande` | Sarabande | topic | beat 2 roll chord; beat cuối pass/sing | none | null |
| barrios | `andante` | Andante | topic | block-chord (chorale) | none | null |
| barrios | `choro` | Choro | topic | dance grid | none | null |
| barrios | `hemiola` | Hemiola | topic | dance grid, hemiola | none | null |
| barrios | `polca` | Polka | topic | dance grid | none | null |
| barrios | `preludio` | Prelude | topic | 3 bè: high / lower-middle / upper-middle | none | null |
| barrios | `thumb_cantabile` | Cantabile | **texture** | thumb melody (`_render_thumb`) | none | null |
| barrios | `tremolo` | Tremolo | **texture** | tremolo grid (`_tremolo`) | none | null |
| barrios | `vals` | Waltz | topic | dance grid | none | null |
| brouwer | `brouwer_etude` | Etude | topic | tumbao 3+3+2, inner voice off-eighths | none | null |
| brouwer | `elogio_pizz` | Dance | topic | staccato ostinato + Bartók slap | none | null |
| brouwer | `noviembre` | Ballade | topic | ballad pulse 2 phách + pickup + color arpeggio | none | null |
| brouwer | `sarabande` | Sarabande | topic | beat 2 heavy chord + swarm trên price | none | null |
| classic | `cantabile` | Cantabile | topic | phrase-level cantabile | none | null |
| classic | `elegiaque` | Elegy | topic | elegy bar | none | null |
| classic | `galop` | Galop | topic (Op. 32 No. 6) | galop cell **1 / 2** | none | **period 4+4** |
| classic | `mozart_var` | Variations | topic (Op. 9) | classical bass + counter-melody 8th | none (`?` §8.2.2) | null |
| classic | `study` | Etude | topic (`?` §8.2.1) | arpeggio; `character is None` → plain arpeggio | none | null |
| torroba | `alcaniz` | Alcaniz | topic | campanella slots (`_FIGURES` 10/11) | none | null — figure đơn (10/11), không phải sentence |
| torroba | `castillo` | Castillo | topic | campanella slots (`_FIGURES` 7/8/13/14) | none | **walk/cadence theo `n % 2` (3/4, 9 ô); type7 5 ô / type8 2 ô (4/4)** |
| torroba | `danza` | Danza | topic | type6 slots | none | **4 ô (type6)** |
| torroba | `fandanguillo` | Fandanguillo | topic | fandanguillo slots | none | spans |
| torroba | `olite` | Olite | topic | olite onsets (`_olite_onsets`) | none | null — figure đơn (12) |
| torroba | `sonatina` | Sonatina | topic | sonatina slots | none | **open/close spans** |
| torroba | `torroba_tremolo` | Juglar | topic | tremolo slots | none | null — figure đơn (9) |
| villa | `chord_melody` | Chord Melody | **texture** | block-chord + melody | none | null |
| villa | `etude1` | Etude 1 | topic | 16-note RH cycle; thumb root 1 lần | none | null |
| villa | `etude11` | Etude 11 | topic | 4 sextuplet arches; open-E pedal | none | null |
| villa | `thumb_cantabile` | Prelude | **texture** | thumb melody | none | null |
| villa | `villa_pattern` | Arpeggio | **texture** | arpeggio/campanella roll (`_render_villa_bar`) | none | null |
| (mọi) | `pedal` | Pedal | texture | pedal/frame bar (không có wave profile) | none | null |

Tổng hợp:

| Level | Số dòng | Ghi chú |
|---|---|---|
| `topic` | 33 | 9 Bach, 6 Barrios, 4 Brouwer, 5 Classic (`study` còn `?` §8.2.1), 7 Torroba, 2 Villa (`etude1`, `etude11`) |
| `texture` | 6 | `villa_pattern`, `chord_melody`, `thumb_cantabile` (×2: barrios + villa), `tremolo`, `pedal` |
| `procedure` khác none | **1** | `bach_fuga` (imitation) |
| `sentence` khác null | **5** | 4 Torroba (`castillo`, `sonatina`, `fandanguillo`, `danza`) + `galop` (period 4+4); 3 pattern Torroba còn lại là **single-figure texture**, không tính |

**Đơn vị:** 39 dòng = 38 dòng `PROFILES` + `pedal`; 38 id unique (`_FAMILY`); 37 id có wave profile. Nếu tính `thumb_cantabile` là topic (cách trước), topic = **35** (9+7+4+5+7+3); theo quyết định texture, topic = **33** (9+6+4+5+7+2).

Bốn kết luận từ bảng:

1. **`procedure` gần như trống.** Chỉ `bach_fuga` có procedure thực thi. Đừng xây procedure engine khi chỉ có một user.
2. **`sentence` chỉ có ở 4 pattern Torroba + galop.** Villa/Barrios/Brouwer/Classic thuần texture + plan — đúng bản chất nhạc của họ, không phải thiếu sót. Ba pattern Torroba còn lại (`alcaniz`, `olite`, `torroba_tremolo`) là figure đơn, không phải sentence.
3. **3 pattern texture đang in tên như chương**: `villa_pattern`, `tremolo`, `chord_melody`. `pedal` chưa từng in. Nhóm này chỉ sửa được sau khi có `Movement.title` + frontend + cache bump (§8.1).
4. **Movement không nằm trong bảng này.** 1D là movement không có movement line, tên là `headline_id`; 1W = 1 movement (1 phiên 32 bar vẫn khoá 1 pattern); 1M = 4 movement; 3M = 3 movement.


---

## 13. Sentence pipeline

Mục tiêu: **thêm sentence cho bất kỳ composer nào** mà không phải viết lại renderer, và không phải chờ runtime interpreter.

### 13.1. Định nghĩa

> **`SentenceSpec`** = template N ô: span + vai (role) + slot, chọn theo `(length, n, closes, meter)`. Mỗi slot là **một realizer**: texture (cách điền ô) hoặc, về sau, procedure (phép biến đổi).

Quan hệ với các khái niệm khác:

- `Phrase` (`model.py`): phrase giai điệu do price tạo. Một `Phrase` có thể được **chia** thành 1..N sentence span.
- `Texture`: cách điền một ô. Sentence chỉ **chọn** texture/figure, không điền ô.
- `Procedure`: phép biến đổi sinh voice khác. Một slot có thể trỏ tới procedure thay vì texture (dùng cho exposition của fugue sau này).
- `Plan`: chọn pattern cho từng phrase/region. Sentence là chuyện **bên trong** một pattern đã được chọn.

### 13.2. Schema

```json
{
  "id": "castillo_34_walk_cadence",
  "pattern": "castillo",
  "meter": { "id": "3/4", "beats": 3, "beat_type": 4, "eighths_per_bar": 6,
             "strong_eighths": [0], "subbar_breaks": [4], "extra_weights": [[4, 0.8]] },
  "select": { "length": [9, 18], "n_parity": "any", "closes": null },
  "span": { "unit": "bar", "tile": 9 },
  "roles": ["statement", "answer"],
  "slots": [
    { "role": "statement", "bars": 5, "realizer": { "kind": "texture", "figure": "castillo_walk" } },
    { "role": "answer",    "bars": 4, "realizer": { "kind": "texture", "figure": "castillo_cadence" } }
  ]
}
```

Galop (period 4+4):

```json
{
  "id": "galop_period",
  "pattern": "galop",
  "select": { "length": [8, 8], "n_parity": "any", "closes": null },
  "span": { "unit": "bar", "tile": 8 },
  "slots": [
    { "role": "question", "bars": 4, "realizer": { "kind": "texture", "cell": "galop1" } },
    { "role": "answer",   "bars": 4, "realizer": { "kind": "texture", "cell": "galop2" } }
  ]
}
```

Quy ước:

- `select.length` là khoảng độ dài phrase mà archetype phục vụ. `tile` cho biết mẫu lặp lại (castillo 9 ô; galop 8 ô).
- `select.n_parity` thay cho "n % 2" hard-code: `any | even | odd`.
- `select.closes`: `null` = không đọc `closes` (castillo), `true/false` = chỉ khớp khi phrase đóng/mở (sonatina, fandanguillo, danza).
- `realizer.kind`: `texture` (figure/cell đã có) hoặc `procedure` (dùng cho exposition sau này).

### 13.3. Selector contract

Một hàm duy nhất, thay cho `select_torroba_spans` + `_castillo_spans` + …:

```
plan_sentence(pattern, sentence_spec, meter_key, length, n, closes) -> [(realizer_id, slots)] | []
```

Yêu cầu:

- Trả `[]` khi meter không khớp, length ngoài `select.length`, parity/closes không khớp — **không fallback**.
- Khi khớp: slot phải **tile kín** `[0, length)`, không hở, không chồng.
- Kết quả deterministic, không phụ thuộc thứ tự duyệt dict.

### 13.4. Validator

1. Slot tile kín span; `sum(bars) == length` (hoặc `tile` chia hết length).
2. `sentence.meter` phải thuộc `pattern.meter_variants` (canonical key).
3. Mỗi `realizer` phải tồn tại: `figure`/`cell` có trong registry (code-backed: `_FIGURES`; interpreter: registry), hoặc `procedure` đã khai.
4. Với mỗi meter supported của pattern: với **mọi** `length` trong `[1, 12]` phải có ít nhất một archetype khớp, hoặc khai `unsupported` có lý do. Thiếu = fail (đây là lỗi "mất sentence").
5. Không archetype nào được khai cho meter mà pattern không hỗ trợ.

### 13.5. Test matrix

- `sentence × meter × length (1..12) × closes (false/true) × n (0..3)` → plan JSON.
- Golden: `backend/tests/fixtures/sentence_plan.json`; so khớp, drift phải review.
- Negative: sai meter → `[]`; length ngoài range → `[]`; realizer không tồn tại → validation error.
- Migration zero-diff: hash plan **trước và sau** khi chuyển code → data phải bằng nhau. Đây là test riêng, **không** dùng Score hash (Score hash không thấy khác biệt plan nếu texture trùng).

### 13.6. Trạng thái theo composer

| Composer | Sentence hiện có | Việc | Ghi chú |
|---|---|---|---|
| **Torroba** | 4 full (`castillo`, `sonatina`, `fandanguillo`, `danza`) | **migrate** sang data | `castillo` chọn theo length + `n % 2`, **không** `closes`; `sonatina/fandanguillo/danza` đọc `closes` |
| **Sor/Classic** | period 4+4 trong galop | **migrate** (ca thứ hai, chứng minh tổng quát) | `_render_galop_dance` chọn cell theo `index % 8` |
| **Bach** | không | **authoring** + `realizer.kind: procedure` | exposition = sentence của các entry (subject/answer), chưa làm |
| **Barrios** | không | **authoring**; cần figure variants trước | period của *La Catedral* là ứng viên |
| **Villa** | không | **authoring**; pilot texture trước | ostinato/figuration, sentence không bắt buộc |
| **Brouwer** | không | **authoring**; ưu tiên thấp | ostinato |

Ba pattern Torroba còn lại (`alcaniz`, `olite`, `torroba_tremolo`) **không** có sentence: chúng là figure đơn mỗi phrase qua `_castillos_figure_plan`. Có thể khai `sentence: null` và `figure_policy: per_phrase`, hoặc để nguyên code.

### 13.7. Quy tắc migration

1. Mỗi archetype một commit; parity plan phải xanh trước khi sang archetype tiếp.
2. Không đổi `n`/`closes` semantics trong lúc migrate — chỉ chuyển if-ladder thành data.
3. Figure đơn (thin) **không** được nâng thành sentence.
4. `sentence: null` là hợp lệ; không ép composer phải có sentence.
5. Chỉ authoring khi renderer đã có realizer cần thiết; nếu chưa, đó là việc viết figure/texture mới, không phải việc của registry.

### 13.8. Điều này KHÔNG cần interpreter

Torroba đã chứng minh: bar renderer vẫn code, chỉ **chọn slot** là data (`torroba_figure_plan` → `_render_torroba_bar`). Vì vậy sentence pipeline chạy được ở Phase 0/1:

- `runtime: "code"` + sentence registry → `plan_sentence()` trả plan, renderer code dùng plan.
- Không cần `runtime: "interpreter"` cho sentence.
- Chỉ khi muốn realizer mới **chưa có code** mới cần interpreter (hoặc viết figure).

### 13.9. Hệ quả cho Texture Studio

- `SentenceSpec` trong Studio = schema này; `sentence_code`/figure id trỏ tới registry.
- Studio authoring một sentence = chọn archetype + slots; preview chạy `plan_sentence` + render code hiện có.
- Checklist khi thêm sentence: archetype vào registry, slot realizer tồn tại, plan golden cập nhật, test negative meter.
- Sentence cho composer mới **không** làm thay đổi `PATTERN_NAMES`/`Movement.title` — nó là lớp trong pattern.
