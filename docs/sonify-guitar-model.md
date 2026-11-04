# Mô hình âm nhạc của lớp guitar — Topic / Texture / Procedure / Sentence / Plan

> **Trạng thái**: căn bản cho refactor renderer. **Đã migrate:** `castillo` 3/4 (PR #147), `castillo` 4/4 (PR #148), `sonatina` (PR #149), `fandanguillo` + `danza` 3/4 & 6/8 (PR #150). **Còn ở code:** `galop` (cần plan theo run) và `danza` 4/4 (cố ý không có spelling).
> **Phạm vi**: lớp `guitar` trong `backend/app/sonify/` (villa, torroba, barrios, brouwer, bach, classic).
> **Liên quan**: [`sonify-texture-studio.md`](./sonify-texture-studio.md), [`sonify-pattern-names.md`](./sonify-pattern-names.md), [`sonify-classical-guitar.md`](./sonify-classical-guitar.md), [`sonify-guitar-torroba-plan.md`](./sonify-guitar-torroba-plan.md).
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
| **`name_source`** (metadata hiển thị) | Cái tên đến từ đâu: `dance` / `work` / `genre` / `form` / `function` / `character` / `tempo` / `device`. **Không phải cơ chế** | `Sarabande` = dance; `Castillo` = work; `Etude` = genre; `Fugue` = form; `Prelude` = function; `Cantabile` = character; `Andante` = tempo; `Hemiola` = device |
| **Texture** (âm hình) | Cách **điền một ô**: voicing, rhythm cell, articulation | arpeggio/campanella, chord-melody, tremolo, bariolage, galop cell |
| **Procedure** (thủ pháp) | **Phép biến đổi sinh ra chất liệu** từ melody/harmony | **imitation** (fuga). Chaconne **không** phải ground bass, xem §4.1 |
| **Sentence** | **Texture-span template**: N ô + vai + slot, chọn theo length/`n`, có archetype đọc `closes` | castillo walk/cadence (9 ô, theo `n % 2`), arada/float, type6 4 ô, galop period 4+4 |
| **Cell** | Biến thể của texture, không phải đơn vị độc lập | galop 1 / galop 2. (castillo type 7/8 là **sentence archetype**, không phải cell) |
| **Plan** | Quan hệ giữa các đơn vị theo thời gian: scope, candidate, post-pass | A–B–A, contrast/trio, avoid-repeat, khoá một pattern |

`sentence` ở đây là **texture-span template**, không phải "sentence" theo nghĩa nhạc lý 8 ô (presentation–continuation–cadence) và không phải `Phrase` (`model.py`) — `Phrase` là phrase giai điệu do price tạo. Quan hệ: một `Phrase` được chia thành các `sentence` span, mỗi span gồm các slot texture.

### 2.1. Movement là level **trên** pattern, không phải một giá trị của `level`

Movement không phải một loại pattern. Nó là **đơn vị biểu diễn** chứa 1..N pattern, có hình thức/độ dài/nhịp/tông riêng.

| | **Movement** | **Pattern** |
|---|---|---|
| Là gì | đơn vị biểu diễn: bản 1D, chương I–IV của 1M, một tuần | slot filler trong một movement |
| Có gì **hiện tại** | `Movement`: `label`, `spec`, `session_count`, `rest_after`, `title` (`span.py`); `PreparedMovement`: thêm `bars`, `groups`, `key`, `character`, `mode`, `title`… | `level`, topic, texture, procedure, sentence, wave profile, family, door |
| Có gì **sẽ thêm** | `plan` (chưa có; plan đang suy từ `_patterns`) | — |
| Chứa | **1..N pattern** | 0..N sentence |
| Quyết định | hình thức, độ dài, nhịp, tông, tên in của chương | cách điền ô, nhãn, thủ pháp, câu |

Bằng chứng trong code:

- Movement = `PreparedMovement` (`span.py:835`), dựng từ `Movement` (`span.py:794`). Số movement theo span: `plan_week` trả **1** (`span.py:801`), `plan_month` trả **4** (I–IV, `:806`), `plan_quarter` trả **3** (`:818`), **1Y = 12** (`year_specs`, `:588`).
- **1D không có `Movement`/`PreparedMovement`.** Nó đi thẳng qua `audio._render`, với `title=f"{symbol} {day.isoformat()}"`. Từ naming release, tên in của 1D lấy từ `movement_titles.movement_title(ensemble, "1D", 0)`; `_compose` vẫn dựng A–B–A row qua `_written_dance(found, forms, ensemble)` nhưng row đó vào `formDescription`, **không in**. Helper test `program.guitar_form_description` trả row đó; không phải đường in.
- **1D không phải "1 movement = 1 pattern".** 1D = 34 bar (`DAILY_ENSEMBLE_SPEC`, `form.py:292`; hằng số `:261-265`). `_assign_macro` có nhánh riêng cho Barrios 1D (`bars == 34`, 120 BPM, 4/4) **đi từng phrase qua `_select_body`** (`guitar_patterns.py:1593-1612`), nên một ngày Barrios có thể chứa nhiều pattern. Từ naming release, 1D calm của Barrios vẫn là row texture (không in) và tên chương là `Ultimo Tremolo` từ bảng; test `test_barrios_day_form_row_drops_textures` khoá cả hai.
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
- `stored` do đường production `_written_dance(found, forms, ensemble)` dựng: `pattern_form(forms[0])`, fallback `pattern_title(found[0])` — **tối đa 3 tên pattern** (`program.py:60-95`).

Nghĩa là hôm nay "tên chương" của guitar **là `form_pattern_ids`/`headline_id`**, không phải identity của movement. Bốn mắt xích phải sửa cùng lúc:

1. **Backend:** thêm `title` cho `Movement` (dựng ở `span.py:353, 803, 813, 825`) **và** `PreparedMovement` (`:1090, 1148, 1281`), cộng đường 1D (`audio._render`). Thiếu 4 chỗ `Movement` thì title rỗng trước khi tới `PreparedMovement`; 1D không có `Movement` nên cũng phải xử lý riêng.
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
| **Post-pass** | `_settle_galop` (`:1691`) | sửa row sau khi chọn. `_paint` là helper, `_has_contrast_section` là predicate — không phải tầng |

Vì vậy "Villa 1D dùng `_select_body`" là **sai**: 1D framed đi macro → `_dominant_pattern_auto`. Chỉ Barrios 1D mới đi `_select_body`.

`1Y` cũng framed: **12 movement** (`year_specs`, `span.py:588`) → macro path, không phải phrase path.

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
| `guitar_patterns.py:989` `_patterns` | **Plan scope switch**: framed → macro, unframed → phrase |
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
| `guitar_torroba.py:1824` `torroba_figure_plan` | **Sentence plan** (bar → slot) |
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
| Cùng một texture, hai title: `thumb_cantabile` | barrios "Cantabile", villa "Prelude" (`program.py:55` special-case) | `level: texture`, title null cho cả hai; registry id-keyed là đủ |
| `pattern` không khai `level` | 38 id, không phân biệt topic với texture | thêm `level` + `name_source` |

**Ghi chú taxonomy:** enum `name_source` có thêm `tempo` và `device`, nên `andante` = tempo, `hemiola` = device. `elegiaque` (Elegy) xếp `genre` theo tên in, không theo mood chọn pattern.

Chỉ **3** pattern texture đang in tên: `villa_pattern`, `tremolo`, `chord_melody`. **`pedal` chưa từng in**: `form_pattern_ids` trả `[]` khi primary là `pedal` (`guitar_patterns.py:3323-3324`), `headline_id`/`contrast_id` skip `pedal`, `_region_pattern_ids` skip (`:1291`).

### 8.1. Đề xuất tên cho các nhãn đang sai

Tiêu chí: nhãn phải là **tên đơn vị** (điệu, thể loại, character, hoặc idiom mượn tên tác phẩm). Nếu pattern là **texture thuần** thì `level: texture`, `title = null`, và **không in** — tên chương do `Movement.title` in.

`thumb_cantabile` là **cùng một texture** (`_render_thumb`) dùng cho hai tác phẩm, nên `level: texture` và title null cho cả hai. Registry id-keyed là đủ vì cả hai ensemble đều không in tên; chỉ khi nào title khác theo ensemble mới cần key `(ensemble, id)` như `PROFILES` (`guitar_wave.py:108`).

| Pattern | Hiện tại | Đề xuất | Lý do |
|---|---|---|---|
| `villa_pattern` | "Arpeggio" | `level: texture`, title null | kỹ thuật; tên chương lấy từ `Movement.title` |
| `tremolo` (barrios) | "Tremolo" | `level: texture`, title null | kỹ thuật; tên tác phẩm thuộc `Movement.title` |
| `chord_melody` | "Chord Melody" | `level: texture`, title null | kỹ thuật |
| `thumb_cantabile` | "Cantabile" / "Prelude" | `level: texture`, title null; key `(ensemble, id)` | cùng một texture cho hai tác phẩm |
| `pedal` | — (không in) | `level: texture` | đã đúng; chỉ khai để registry đầy đủ |

**Checklist migration `Movement.title` — 4 mắt xích + 3 quyết định, phải làm cùng lúc:**

- [x] **Backend:** `title` cho `Movement` và `PreparedMovement`, cộng đường 1D; bảng curated `movement_titles.TITLES` theo `(ensemble, span, index)` + `CHARACTER_TITLES` cho `1D`/`1W`.
- [ ] **Frontend:** `src/sonify/program.ts` — `PATTERN_NAMES`, `isPatternForm`, `workForm`, `pieceCopy`; title tự do phải qua được `formatMovement`, và 1D phải giữ tên bài trong **title**. Test: `src/sonify/program.test.ts:185-192`.
- [x] **Cache:** bump `SPAN_REVISION` + `RECAP_REVISION`. `movementName` nằm trong payload, cache key không chứa tên.
- [x] **Name golden:** `test_name_parity.py` khoá tên in; `test_program.py` khoá row A–B–A (non-printed). **Không** dùng Score hash.

**Ba chỗ sẽ gãy nếu chỉ set `title = null`:**

1. **Có hai đường in tên.** `_written_dance` (`program.py:89-95`) ưu tiên `pattern_form(forms[0])`, nhưng **fallback** sang `pattern_title(found[0])`. Chỉ set title null sẽ chặn đường 1, đường 2 vẫn in nếu `found` còn phần tử. Phải chặn ở **cả hai** hoặc bỏ fallback.
2. **Lọc texture khỏi `pattern_form` sẽ làm mất A–B–A.** Row `[preludio, tremolo, preludio]` lọc còn `[preludio, preludio]` → collapse thành `"Cathedral"`. Khi texture không in, `pattern_form` **không còn mô tả hình thức**; phải quyết A–B–A hiển thị ở đâu (mô tả riêng cạnh `Movement.title`, tooltip, hay chart section) hoặc chấp nhận mất.
3. **Movement line có thể đã rỗng trước khi render.** `span_movement_name` trả `stored`; `stocks.py:646` truyền `cached.movement_name if cached else ""`. Movement chưa render audio → `""`. Vậy hôm nay line đã có thể rỗng, không cần đợi bỏ in texture — lý do mạnh hơn để `Movement.title` **derive từ spec**, không phụ thuộc render.

- [x] Chặn cả hai đường in tên: `pattern_form` lọc `level == texture`; fallback `pattern_title` chỉ dùng khi id là topic.
- [x] Chốt chỗ hiển thị A–B–A: `formDescription`, **không in**; `Movement.title` mới là `name`.
- [x] `Movement.title` derive từ bảng curated (không cần render), nên manifest có tên cả khi audio chưa có.

Lưu ý: `data_digest` (`dfi.py:52`) chỉ hash bar, `scale_fingerprint` (`span.py:858`) không chứa tên → **DFI không đổi** khi đổi nhãn, và parity audio không bắt được lỗi tên. Đây là lý do phải có name golden riêng.

### 8.2. Bốn câu hỏi nội dung cần chốt

> Q1 cũ (7 pattern Torroba là movement hay topic) **đã chốt**: `topic`. Movement là level trên pattern (§2.1), nên câu hỏi đó không còn.

| # | Câu hỏi | Vì sao cần chốt | Khuyến nghị |
|---|---|---|---|
| 1 | `study` (classic) in "Etude" ở mọi đoạn mặc định: giữ `topic` hay chuyển `texture`? | "Etude" là thể loại, không phải kỹ thuật → được phép in; nhưng `study` là fallback mặc định nên in "Etude" ở mọi đoạn có thể là nhiễu | giữ `topic` + "Etude" (đúng thể loại); chỉ đổi nếu nghe thấy nhiễu |
| 2 | `mozart_var` in "Variations" nhưng code chỉ là bass + counter-melody | Tên gợi `procedure: variation` nhưng **không có procedure** trong code | giữ nhãn, khai `procedure: none`, ghi backlog "variations thật" |
| 3 | `bach_gigue` có nên dùng `procedure: imitation`? | Gigue ngoài đời thường fugal; code hiện không imitation | không, ở giai đoạn này — thêm là **thay đổi hành vi**, cần nghe duyệt |
| 4 | `Movement.title` lấy từ đâu, và 1D lấy gì? | `FormSpec` **không có** `title`; `month_specs` dùng chung cho mọi symbol, nên title theo bài không thể nằm trong spec. `pieceCopy` là hàm hiển thị frontend, không phải nguồn dữ liệu | **Đã chốt (A):** bảng curated `(ensemble, span, index) → title` trong `movement_titles.py`, total cho 6 ensemble × 4 span; 1D dùng `("1D", 0)`. `1D`/`1W` đọc thêm `character` qua `CHARACTER_TITLES` (calm/rally/selloff/volatile) để giữ variety. 1Y tái dùng chương trình `1M` theo tháng. |

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
2. **Hai lớp đã có**: `sentence` (texture-span template, §13) và **`Movement.title`** (guitar, `movement_titles.py`). `Movement.title` là điều kiện để bỏ in texture; `formDescription` giữ A–B–A không in.
3. **`procedure` là executable; `form` trên pattern chỉ là metadata — cơ chế hình thức thuộc movement.** Đừng để spec khai `form` rồi tưởng engine hiểu.
4. **Plan có ba scope, không phải hai bản luật.** Phrase (`_select_body`), macro (`_assign_macro`), region row (`_barrios_palette`/`_bach_region_patterns`), cộng post-pass (`_settle_galop`). Phrase/macro tách nhau là **by design** (framed vs unframed). Cái trùng lặp thật là **per-ensemble primary chooser** (`_dominant_pattern_auto` vs các `_*_primary`), và chỉ nên thu hẹp chỗ đó.
5. **Parity phải tách làm hai**: `audio parity` (Score hash trên ma trận ensemble × meter × mood × band × bpm × span) và `name parity` (golden `form_pattern_ids`/`_written_dance`). Score hash **không** bắt được lỗi tên.
6. **Chưa có parity/golden cho guitar pattern/name.** Trong `backend/tests` chỉ có golden humanize (`test_humanize.py:1219 test_vintage_golden_bytes_do_not_drift`), không liên quan pattern/tên. Parity cho guitar là deliverable R1, không phải giả định.
7. **Bảng inventory, registry, parity, `sentence` và `Movement.title` đều đã có.** Việc còn lại: frontend nhận `name` tự do + `formDescription`, và `procedure` cho Bach.

---

## 11. Câu hỏi mở

1. **`Movement.title` là identity hay mô tả?** Nếu là identity (`"Suite Popular Brasileira — Mazurka-Choro"`), A–B–A của 3 phần sống ở đâu — trong `FormSpec.sections` hay trong title? Nếu là mô tả, nó chỉ là `pattern_form` đổi tên.
2. **Tên `sentence`**: giữ `sentence` (đã dùng trong PR #142) với định nghĩa hẹp "texture-span template", hay đổi thành `archetype`/`phrase_template` để khỏi lẫn với `Phrase` và với "sentence" nhạc lý 8 ô?
3. **`form.functions[]`** (exposition/episode/stretto, real vs tonal answer) có nằm trong phạm vi Phase 2–3, hay để sau?
4. **Motif pitch-cell** có cần mô hình hoá, hay chỉ giữ contour như fuga hiện nay?
5. **A–B–A hiển thị ở đâu khi texture không in?** **Đã chốt:** `Movement.title` là identity; row A–B–A (texture đã lọc) thành `formDescription`, **không in**, để tooltip/subtitle dùng nếu muốn. Manifest trả `name` = title và `formDescription` = row.

---

## 12. Phụ lục A — Inventory pattern (39 dòng)

Nguồn: `PROFILES` = **38 dòng** `(ensemble, id)` nhưng chỉ **37 id unique** (`thumb_cantabile` có ở cả barrios và villa); `_FAMILY` = **38 id** (gồm `pedal`), nên bảng có **39 dòng** = 38 dòng `PROFILES` + `pedal`. `level` đã chốt trong `pattern_registry.py`; `?` còn lại chỉ là câu hỏi nội dung (procedure/level của `study`). Texture lấy từ docstring của renderer tương ứng.

Bảng `level` + `name_source` theo id hiện nằm trong `backend/app/sonify/pattern_registry.py`: **38 id = 33 topic + 5 texture**. Bảng dưới có 39 dòng vì `thumb_cantabile` xuất hiện ở hai ensemble. `validate()` kiểm coverage với `_FAMILY`, enum `name_source`, và title cho mọi dòng `(ensemble, id)` của topic.

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
| torroba | `alcaniz` | Alcaniz | topic | figure 10/11 (không phải slot) | none | null — single-figure, không phải sentence |
| torroba | `castillo` | Castillo | topic | figure 7/8/13/14 (không phải slot) | none | **3/4: 2 archetype walk/cadence theo `n % 2`, tile 9; 4/4: type 7 (5 ô) / type 8 (2 ô) / type 1 (1 ô)** |
| torroba | `danza` | Danza | topic | type6 slots | none | **4 ô (type6)** |
| torroba | `fandanguillo` | Fandanguillo | topic | figure 5 (4 ô) / figure 2 (2 ô) | none | **cần `rise >= 1`; `closes` đổi `room`** |
| torroba | `olite` | Olite | topic | olite onsets (`_olite_onsets`) | none | null — single-figure (12) |
| torroba | `sonatina` | Sonatina | topic | sonatina slots | none | **open/close spans** |
| torroba | `torroba_tremolo` | Juglar | topic | tremolo slots | none | null — single-figure (9) |
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

> **`SentenceSpec`** = template N ô: span + vai (role) + slot, chọn theo `(length, n, closes, rise, meter)`. `previous_figure` là post-pass của `select_torroba_spans`, không phải input của planner. Mỗi slot là **một realizer**: texture (cách điền ô) hoặc, về sau, procedure (phép biến đổi).

Quan hệ với các khái niệm khác:

- `Phrase` (`model.py`): phrase giai điệu do price tạo. Một `Phrase` có thể được **chia** thành 1..N sentence span.
- `Texture`: cách điền một ô. Sentence chỉ **chọn** texture/figure, không điền ô.
- `Procedure`: phép biến đổi sinh voice khác. Một slot có thể trỏ tới procedure thay vì texture (dùng cho exposition của fugue sau này).
- `Plan`: chọn pattern cho từng phrase/region. Sentence là chuyện **bên trong** một pattern đã được chọn.

### 13.2. Schema

| Field | Nghĩa |
|---|---|
| `select.length` | `[min, max]`; `max: null` = không chặn |
| `select.n_parity` | `any \| even \| odd` — nhánh `n % 2` |
| `select.n_mod` | `{mod, value}` — nhánh `n % 3` (sonatina open), không dùng `n_parity` cùng lúc |
| `select.closes` | **selector branch**: `null` = không đọc; `open`/`close` chọn archetype |
| `select.rise_min` | `fandanguillo` cần `rise >= 1` |
| `span.tile` | độ dài template lặp; `null` khi `exact: true` |
| `span.remainder` | `same_figure` (lặp cùng figure) \| `truncate_cycle` (galop) \| `exact` |
| `span.cycle` | lặp trên run bất kỳ (galop) |
| `span.exact` | slots phủ đúng `length`, không lặp (castillo 4/4, sonatina, fandanguillo, danza) |
| `span.truncate_to_length` | tile dài hơn `length` bị cắt theo length (castillo 3/4). Span `exact` không dùng field này; `_slots` luôn clip slot theo length |
| `slots[].start`, `bars`, `figure`, `anchor` | vị trí + độ dài + cell id; `anchor="start"` (mặc định) dùng `start` trực tiếp; `anchor="end"` đặt slot tại `length - bars` (sonatina close); `anchor="middle"` đặt slot tại `length // 2 + start` (fandanguillo n lẻ, `start=-1`) |

**Phase 1–4 (PR #147, #148, #149, #150) — subset đã code** trong `backend/app/sonify/sentence_specs.py`:

| Doc §13 | Code Phase 1 |
|---|---|
| `plan_sentences(pattern, specs, ...)` | `plan_sentence(pattern, meter, length, n, *, closes=False, rise=0)`; specs tra registry `(pattern, meter)` |
| `Select.length = [min, max]` | `Select.length_min`, `length_max` |
| `Select.n_parity` / `n_mod` / `closes` / `rise_min` | đã có đủ |
| `Span.tile` / `remainder` / `truncate_to_length` / `cycle` / `exact` | đã có đủ |
| `Slot.realizer {kind, figure}` | `Slot.figure: int` (cell id); `kind: procedure` chưa có |
| `previous_figure` trong contract | **không** truyền vào planner; rotation nằm ở `select_torroba_spans` |
| `None` vs `[]` | `None` = chưa có data cho cặp pattern/meter; `[]` = có data nhưng length/select không khớp |

`register()` validate `tile >= 1`, slot bounds/overlap, `n_parity`/`n_mod`/`closes`/`remainder`, **`figure` phải có trong `_FIGURES`** (owner truyền `valid_figures`), id trùng; re-register giống hệt là no-op nên reload an toàn. `guitar_torroba` gọi register **sau khi mọi `_FIGURES` entry tồn tại**, kể cả 9–12 thêm muộn. `plan_sentence()` load các module trong `_OWNER_MODULES` khi registry rỗng — thêm module owner khi migrate family mới (galop → `guitar_sor`).

`cycle`/`remainder` là **declarative**: `_tile` lặp mọi span non-exact và truncate chunk cuối; `exact` và `truncate_to_length` mới là công tắc tiling. `truncate_cycle` buộc `cycle=True`, và `cycle=True` buộc `truncate_cycle`.

**Castillo 3/4** — một figure 9 ô, `n % 2` chọn WALK/CADENCE, length nhỏ bị cắt:

```json
{
  "id": "castillo_34_walk",
  "pattern": "castillo",
  "meter": { "id": "3/4", "beats": 3, "beat_type": 4, "eighths_per_bar": 6,
             "strong_eighths": [0], "subbar_breaks": [4], "extra_weights": [[4, 0.8]] },
  "select": { "length": [2, null], "n_parity": "even", "closes": null, "rise_min": 0,
              "unsupported_lengths": [1] },
  "span": { "unit": "bar", "tile": 9, "remainder": "same_figure", "truncate_to_length": true },
  "slots": [{ "role": "walk", "start": 0, "bars": 9, "realizer": { "kind": "texture", "figure": "castillo_walk" } }]
}
```

`length = 2` → span thực `(0,1)`; `length = 10` → 9 ô + 1 ô, cả hai cùng figure. `coverage` suy ra là **full** vì union phủ hết `min(tile, length)`.

**Castillo 4/4, length >= 8 lẻ** — slot **không liền nhau**, coverage suy ra là **partial**:

```json
{
  "id": "castillo_44_long_odd",
  "pattern": "castillo",
  "meter": { "id": "4/4", "beats": 4, "beat_type": 4, "eighths_per_bar": 8,
             "strong_eighths": [0, 4], "subbar_breaks": [4], "extra_weights": [] },
  "select": { "length": [8, null], "n_parity": "odd", "closes": null, "rise_min": 0 },
  "span": { "unit": "bar", "tile": null, "exact": true },
  "slots": [
    { "role": "arada_a", "start": 0, "bars": 2, "realizer": { "kind": "texture", "figure": "castillo_8" } },
    { "role": "arada_b", "start": 4, "bars": 2, "realizer": { "kind": "texture", "figure": "castillo_8" } },
    { "role": "link",    "start": 2, "bars": 1, "realizer": { "kind": "texture", "figure": "castillo_1" } }
  ]
}
```

Bar 3, 6, 7… rơi về base grid. `castillo 4/4` có **9 archetype**: short 2–3; pair even/odd L4; type 7 L5; pairs at 3 L5–6 odd; type 7 L6; type 7 L7; long even 8+; long odd 8+ — xem bảng §13.6.

**Sonatina open, length 4, `n % 3 == 0`** — `n_parity` không đủ:

```json
{
  "id": "sonatina_open_4_turn0",
  "pattern": "sonatina",
  "meter": { "id": "4/4", "beats": 4, "beat_type": 4, "eighths_per_bar": 8,
             "strong_eighths": [0, 4], "subbar_breaks": [4], "extra_weights": [] },
  "select": { "length": [4, 4], "n_mod": { "mod": 3, "value": 0 }, "closes": "open", "rise_min": 0 },
  "span": { "unit": "bar", "tile": null, "exact": true },
  "slots": [
    { "role": "pair", "start": 0, "bars": 2, "realizer": { "kind": "texture", "figure": "sonatina_4" } },
    { "role": "link", "start": 3, "bars": 1, "realizer": { "kind": "texture", "figure": "sonatina_1" } }
  ]
}
```

Turn 0/1/2 là **ba archetype riêng** cho length 2–4; length 5–6 dùng `n_parity`; length >= 7 cố định.

**Galop** — cycle 8 ô trên run:

```json
{
  "id": "galop_cycle",
  "pattern": "galop",
  "select": { "length": [1, null], "n_parity": "any", "closes": null, "rise_min": 0 },
  "span": { "unit": "bar", "tile": 8, "cycle": true, "remainder": "truncate_cycle" },
  "slots": [
    { "role": "cell1", "start": 0, "bars": 4, "realizer": { "kind": "texture", "cell": "galop1" } },
    { "role": "cell2", "start": 4, "bars": 4, "realizer": { "kind": "texture", "cell": "galop2" } }
  ]
}
```

### 13.3. Selector contract

```
plan_sentence(pattern, meter, length, n, *, closes=False, rise=0)
    -> [(figure, (bar, ...))] | None
```

- `specs` tra từ registry `(pattern, meter)`, fallback key `(pattern, "*")` cho family không phụ thuộc meter (`sonatina`, `fandanguillo`). `None` = cặp này chưa migrate, caller dùng code cũ; `[]` = đã migrate nhưng length/select không khớp.
- Input đủ: `length`, `n`, `closes`, `rise`, `meter`. **`previous_figure` không phải input** (xem dưới).
- **Avoid-repeat là post-pass ở tầng pattern**, không phải field của archetype: sau khi chọn, nếu `first_realizer == previous_figure` thì tính lại **một lần** với `n + 1` (`select_torroba_spans`, `guitar_torroba.py:1795-1800`). Vì rotation đổi cả `n % 2` lẫn `n % 3`, nó phải nằm trong contract, không thể "xử lý sau".
- Không fallback: sai meter/length/parity/closes/rise → `[]`.
- Deterministic.

### 13.4. Validator

1. `slots[].start` bắt buộc. Slot `anchor="start"` chiếm `[start, start+bars)`; slot `anchor="end"` chiếm `[length-bars, length)` (chỉ với span `exact`); slot `anchor="middle"` chiếm `[length//2 + start, length//2 + start + bars)` (chỉ với span `exact`, `start` được phép âm). Không chồng nhau; `start + bars <= effective`, với `effective = min(tile, remaining)` cho cycle/truncate, hoặc `length` khi `exact`. Slot `middle` phải **nằm sau toàn bộ slot `start`** tại `length_min`; nếu không, nó sẽ trôi vào start slot ở length lớn hơn. Với điều kiện đó, `middle`/`end` chỉ trượt ra xa start, và `end` trượt nhanh hơn `middle`, nên overlap của `middle`/`end` kiểm một lần tại **`length_min`** là đủ.
2. **Coverage suy ra từ slots, không khai trong JSON:** `covered = union([start, start+bars))`; `full = covered == set(range(effective))`; nếu không full thì là `partial`, bar trống rơi về base grid (`uncovered: base_grid`). Vì vậy `coverage` không thể là field tĩnh của archetype — cùng một archetype có thể full ở L2 và partial ở L3.
3. **Per-cycle, không phải toàn cục:** với `length = 18, tile = 9` có hai cycle; mỗi cycle phủ `min(tile, remaining)`. Không đòi `sum(bars) == tile` khi `length < tile`.
4. `truncate_to_length`: chỉ áp cho tile lặp (castillo 3/4). Span `exact` luôn clip slot theo length trong `_slots`; plan trả `(start, min(bars, length - start))`.
5. `remainder`/`cycle`/`exact` phải khớp kiểu archetype.
6. `unsupported`: list tĩnh **hoặc** predicate `unsupported_when` cho trường hợp phụ thuộc input (`fandanguillo`: `rise == 0`, `room < 4` khi `n` chẵn, `room < 2` hoặc `start + 1 >= room` khi `n` lẻ; `danza`: meter 4/4, `length < 4`, `closes && length == 4`).
7. `n` coverage: với mỗi length, **mọi** residue của `mod` (2 hoặc 3) phải có archetype, hoặc khai unsupported.
8. `sentence.meter` thuộc `pattern.meter_variants`; realizer tồn tại; plan golden.

Phase 1: `register()` đã enforce tile/slot/parity/remainder; coverage per-cycle và `unsupported_lengths` vẫn là việc của test, chưa phải validator runtime.

### 13.5. Test matrix

- `meter × length (1..12) × n (0..5) × closes (open/close/null) × rise (0/1/2) × previous_figure (null + mỗi figure)` → plan.
- Derived coverage: castillo 4/4 length **3..9** (L2 full), sonatina open length 2..8 (`n % 3`; L2 t0/t1 full, t2 partial), fandanguillo (`rise` 0/1, closes, length 2/3/4/6/7 cho middle anchor), castillo 3/4 (length 2, 9, 10, 18), galop run 1..30.
- Negative: danza 4/4 (unsupported meter), danza L1–3, `closes && L==4`; fandanguillo `rise == 0`; sonatina open L1; castillo L1.
- Anchor: `middle` tại `length // 2 - 1` (fandanguillo L2/3/4/6/7); `middle` ngoài phrase tại `length_min`; `middle` đứng trước slot `start` bị từ chối (sẽ trôi vào ở length lớn hơn); `middle` chồng slot `start`; `middle` chồng `end`; hai `middle` chồng nhau; `end` chồng slot `start`; `end`/`middle` trên span lặp bị từ chối.
- Avoid-repeat: cùng length, `previous_figure` = figure đầu → plan xoay đúng một lần.
- Golden: `backend/tests/fixtures/sentence_plan.json` — **path mới**, thư mục chưa tồn tại.
- Negative: sai meter → `[]`; unsupported predicate đúng → `[]`; realizer thiếu → validation error.

### 13.6. Inventory archetype Torroba + status

**Đã migrate:** `castillo` 3/4 (PR #147), toàn bộ 4/4 (PR #148), `sonatina` open/close (PR #149), `fandanguillo` (2 archetype: even type 5, odd type 2 giữa phrase) và `danza` 3/4 + 6/8. Torroba đã xong; `plan_sentence` còn trả `None` cho `danza` 4/4 (không có spelling, cố ý không register) và `castillo` 6/8 (chỉ register 3/4 + 4/4). Galop (Sor) vẫn ở code và cần một plan theo **run**, không phải theo `length`/`n` của phrase (xem ghi chú cuối bảng).

| Family | Select | Span | Slots (start, bars, figure) |
|---|---|---|---|
| ✓ `castillo` 3/4 walk | L>=2, n even | tile 9, same_figure, truncate | `(0, 9, walk)` |
| ✓ `castillo` 3/4 cadence | L>=2, n odd | tile 9, same_figure, truncate | `(0, 9, cadence)` |
| ✓ `castillo` 4/4 short | L 2–3 | exact | `(0, 2, 8)` |
| ✓ `castillo` 4/4 pair even | L 4, n even | exact | `(0, 2, 8)` |
| ✓ `castillo` 4/4 pair odd | L 4, n odd | exact | `(1, 2, 8)` |
| ✓ `castillo` 4/4 type7 (L5) | L 5, n even | exact | `(0, 5, 7)` |
| ✓ `castillo` 4/4 pairs at 3 | L 5–6, n odd | exact | `(0, 2, 8), (3, 2, 8)` |
| ✓ `castillo` 4/4 type7 (L6) | L 6, n even | exact | `(0, 5, 7)` |
| ✓ `castillo` 4/4 type7 (L7) | L 7 | exact | `(0, 5, 7)` |
| ✓ `castillo` 4/4 long even | L>=8, n even | exact | `(0, 5, 7)` |
| ✓ `castillo` 4/4 long odd | L>=8, n odd | exact | `(0,2,8), (4,2,8), (2,1,1)` |
| ✓ `sonatina` open L2 t0 | L2, `n%3=0` | exact | `(0,2,4)` |
| ✓ `sonatina` open L2 t1 | L2, `n%3=1` | exact | `(0,2,2)` |
| ✓ `sonatina` open L2 t2 | L2, `n%3=2` | exact | `(0,1,1)` |
| ✓ `sonatina` open L3 t0 | L3, `n%3=0` | exact | `(0,2,4)` |
| ✓ `sonatina` open L3 t1 | L3, `n%3=1` | exact | `(1,2,2)` |
| ✓ `sonatina` open L3 t2 | L3, `n%3=2` | exact | `(0,2,1)` |
| ✓ `sonatina` open L4 t0 | L4, `n%3=0` | exact | `(0,2,4),(3,1,1)` |
| ✓ `sonatina` open L4 t1 | L4, `n%3=1` | exact | `(1,2,2),(3,1,1)` |
| ✓ `sonatina` open L4 t2 | L4, `n%3=2` | exact | `(0,1,1),(2,2,4)` |
| ✓ `sonatina` open L5 even | n even | exact | `(0,2,4), (3,1,1)` |
| ✓ `sonatina` open L5 odd | n odd | exact | `(0,2,4), (3,2,2)` |
| ✓ `sonatina` open L6 even | n even | exact | `(0,2,4), (3,2,2)` |
| ✓ `sonatina` open L6 odd | n odd | exact | `(0,2,2), (3,2,4)` |
| ✓ `sonatina` open L>=7 | any n | exact | `(0,2,4), (3,1,1), (5,2,2)` |
| ✓ `sonatina` close L<=3 | any n | exact, clip theo length | `(0, 3, 3)` |
| ✓ `sonatina` close L4–L5 | any n | exact | `(L-3, 3, 3)` |
| ✓ `sonatina` close L6 | any n | exact | `(0,1,1), (3,3,3)` |
| ✓ `sonatina` close L>=7 | any n | exact | `(0,2,4), (L-3,3,3)` |
| ✓ `fandanguillo` n even | `room>=4`, rise>=1 → open L>=4, close L>=5 | exact | `(0,4,5)` |
| ✓ `fandanguillo` n odd | `room>=2`, rise>=1 → open L>=2, close L>=3 | exact | `(L//2-1, 2, 2)`, anchor `middle` |
| ✓ `danza` 3/4 & 6/8 | L>=4, not(closes && L==4) | exact | `(0,4,6)` |
| `galop` | L>=1 | tile 8, cycle | `(0,4,1),(4,4,2)` (cell, không phải figure) |

`room = length - 1` khi `closes`, ngược lại `length`; `length_min` của mỗi archetype là chỗ guard đầu tiên qua, nên không cần `unsupported_lengths` cho fandanguillo. Figure numbering: castillo 1/7/8/13/14; sonatina 1/2/3/4; fandanguillo 5/2; danza 6.

`unsupported_lengths`: castillo (3/4 và 4/4) `[1]`; sonatina open `[1]`; sonatina close không có (L1 vẫn render); danza `[1,2,3]` + toàn bộ 4/4 (`plan_sentence` trả `None`, code path trả `[]`); fandanguillo không dùng list — `rise == 0` và các `length_min` ở bảng trên đã bao hết predicate.

**Galop (chưa migrate) — cần PR riêng.** `_render_galop_dance` (`guitar_sor.py:413-456`) chọn `_galop1_cell`/`_galop2_cell` bằng `index % 8`, trong đó `index = _galop_body_index(...)` đếm bar trong **run** (reset ở pedal/study bar), và còn dùng `index == 0` cho `variant`. `Slot.figure` trỏ vào `_FIGURES` của `guitar_torroba`, còn galop là **cell** được resolve ngay trong `guitar_sor`, không đi qua `render_torroba_figure`. Vì vậy migrate galop cần: (a) một `Slot`/`Span` realizer kiểu `cell` (và metadata `variant`), (b) API plan theo run (`plan_run`/`plan_cycle`) trả cell cho từng bar trong run, và (c) thêm `app.sonify.guitar_sor` vào `_OWNER_MODULES` cùng một consumption path mới trong `_render_galop_dance`. Đó là thay đổi schema + bar renderer, không phải chuyển if-ladder thành data, nên tách khỏi PR Torroba này.

Status theo composer:

| Composer | Sentence hiện có | Việc | Ghi chú |
|---|---|---|---|
| **Torroba** | 4 family (castillo 3/4 + 4/4, sonatina, fandanguillo, danza 3/4 + 6/8) | **xong** (Phase 0/1) | bảng trên là toàn bộ archetype; `fandanguillo` cần `rise` + anchor `middle`; `sonatina` cần `n % 3`; danza 4/4 cố ý `None` |
| **Sor/Classic** | cycle 8 ô trong galop | **defer** sang PR riêng | `_galop_body_index` đếm run; cần plan theo run + realizer `cell` |
| **Bach** | không | **authoring** + `procedure` | exposition = sentence của entry |
| **Barrios** | không | **authoring**; cần figure variants | period *La Catedral* |
| **Villa** | không | **authoring**; pilot texture trước | ostinato |
| **Brouwer** | không | **authoring**; ưu tiên thấp | ostinato |

### 13.7. Quy tắc migration

1. Mỗi archetype một commit; parity plan phải xanh trước khi sang archetype tiếp.
2. Không đổi `n`/`closes`/`rise`/avoid-repeat semantics trong lúc migrate — chỉ chuyển if-ladder thành data. Mỗi nhánh là một archetype/branch, không gộp; `previous_figure` là post-pass và phải giữ nguyên.
3. Figure đơn (thin) **không** được nâng thành sentence.
4. `sentence: null` là hợp lệ; không ép composer phải có sentence.
5. Chỉ authoring khi renderer đã có realizer cần thiết; nếu chưa, đó là việc viết figure/texture mới, không phải việc của registry.

### 13.8. Điều này KHÔNG cần interpreter

Torroba đã chứng minh: bar renderer vẫn code, chỉ **chọn slot** là data (`torroba_figure_plan` → `_render_torroba_bar`). Vì vậy sentence pipeline chạy được ở Phase 0/1:

- `runtime: "code"` + sentence registry → `plan_sentences()` trả plan, renderer code dùng plan.
- Không cần `runtime: "interpreter"` cho sentence.
- Chỉ khi muốn realizer mới **chưa có code** mới cần interpreter (hoặc viết figure).

### 13.9. Hệ quả cho Texture Studio

- `SentenceSpec` trong Studio = schema này; `sentence_code`/figure id trỏ tới registry.
- Studio authoring một sentence = chọn archetype + slots; preview chạy `plan_sentences` + render code hiện có.
- Checklist khi thêm sentence: archetype vào registry, slot realizer tồn tại, plan golden cập nhật, test negative meter.
- Sentence cho composer mới **không** làm thay đổi `PATTERN_NAMES`/`Movement.title` — nó là lớp trong pattern.


---

## 14. Door pipeline (intro/outro)

### 14.1. Định nghĩa

> **Door** = script điền **vùng pedal** ở đầu/cuối movement, gắn theo `(ensemble, pattern)`. Nó không phải Texture (không điền body), không phải Sentence (không có slot/role trong body), và **không in tên**.

`intro`/`outro` là **section kind** của `FormSpec`, không phải tên của door. `warmup`/`cooldown` cũng là door region:

```python
Section = Literal["intro", "phrase", "outro", "warmup", "cooldown"]   # form.py:108
_PEDAL = frozenset({"intro", "outro", "warmup", "cooldown"})          # form.py:109
```

### 14.2. Code hiện tại

- **Vùng:** `_pedal_regions(ctx)` (`guitar_patterns.py:3986`) trả `leading` (từ bar 0 đến hết `_PEDAL`) và `trailing` (từ cuối lên). Door chỉ chạm hai vùng này.
- **Chọn door:** `_dispatch` (`guitar_frame.py:135-142`) lấy `_extra_doors().get((ctx.ensemble, pattern))`; không có thì rơi về **composer frame** (`_frame_composer`, `:85`).
- **`pattern` của door là body pattern ở biên**, không phải `headline_id`: `_paint_frames` (`guitar_patterns.py:4081-4092`) gọi `_joined_body_pattern(ctx, leading[-1] + 1, patterns)` cho intro và `... trailing[0] - 1 ...` cho outro. Row `[preludio, tremolo, preludio]` → intro/outro dùng `preludio`; nếu biên là `tremolo` thì door là `tremolo`.
- **Chữ ký door:** `door(ctx, bar, role, *, steps, closing, index)`. `steps` là **bucket 2 hoặc 4**, không phải độ dài region: `steps = 2 if len(bars) <= 2 else 4` (`_render_region`, `:61`). `length = len(bars)` chỉ được truyền vào `_gesture`; region 1 bar đi `_compressed` (`:111`). `role` lấy từ `frame_roles(length)` (`:29`), tối đa 4 bước `0..3`.
- **Hợp nhất registry:** `_extra_doors()` (`:623`) merge `guitar_frame_bach_sor.DOORS` → `guitar_frame_rest.DOORS` → `guitar_torroba_doors.DOORS` (update vào `_RETAINED_DOORS`), rồi `_RETAINED_DOORS` **thắng khi trùng**.
- **Profile:** `door_profile(name)` = `_PROFILE.get(name, "study")`. Door chơi idiom của body ở biên nên dùng profile của body; không còn bảng riêng (PR #146).
- **Không in tên:** `form_pattern_ids` bỏ qua `pedal` (`:3323-3324`), nên đổi nhãn texture không ảnh hưởng door.

### 14.3. Schema

```json
{
  "id": "villa_thumb_door",
  "ensemble": "villa",
  "pattern": "thumb_cantabile",
  "sections": ["intro", "outro", "warmup", "cooldown"],
  "steps": { "short": 2, "long": 4, "threshold": 2, "compress_one_bar": true },
  "roles": [0, 1, 2, 3],
  "profile": "derived_from_pattern",
  "fallback": "policy_none",
  "status": "reviewed"
}
```

- `sections` phải là tập con của `_PEDAL`; **cùng một door** `(ensemble, pattern)` phục vụ cả 4 kind (`intro`, `outro`, `warmup`, `cooldown`). `intro`/`outro` chỉ là tên phía body.
- `steps` là bucket: `short = 2` khi region <= `threshold`, `long = 4` khi dài hơn. **Không** phải độ dài region; region length chỉ dùng để chọn `_compressed`/`frame_roles`.
- `roles` trong schema là **tập giá trị** `0..3`, không phải list theo bar. Role từng bar do `frame_roles(length)` quyết định: 2 → `[0,1]`; 3 → `[0,2,3]`; 4 → `[0,1,2,3]`; **>4 thì lặp** theo `min(3, index * 4 // length)`, bar cuối luôn 3 (5 → `[0,0,1,2,3]`; 6 → `[0,0,1,2,2,3]`; 8 → `[0,0,1,1,2,2,3,3]`). Length 1 đi `_compressed` và gọi role 0 rồi 1.
- `fallback`: code **luôn** rơi về `_frame_composer` khi không có door; `policy_none` chỉ là policy validation (cảnh báo/fail nếu thiếu), không phải hành vi mặc định.
- `profile`: **derive** từ `_PROFILE[pattern]`; `derived_from_pattern` là placeholder, không phải key tra cứu. Chỉ thêm override nếu sau này cửa cần trần khác body.

### 14.4. Inventory hiện tại

Toàn bộ **38 dòng `PROFILES`** đều có door (không có pattern nào rơi về composer frame):

| Module | Số door | Key |
|---|---|---|
| `guitar_frame_rest.DOORS` | 13 | barrios 7 (andante, tremolo, choro, polca, hemiola, vals, thumb_cantabile); villa 4 (chord_melody, thumb_cantabile, etude1, etude11); brouwer 2 (brouwer_etude, sarabande) |
| `guitar_frame_bach_sor.DOORS` | 10 | bach 7 (gavotte, gigue, sarabande, chaconne, prelude, allemande, courante); classic 3 (cantabile, elegiaque, galop) |
| `guitar_torroba_doors.DOORS` | 7 | castillo, sonatina, fandanguillo, danza, torroba_tremolo, alcaniz, olite |
| `_RETAINED_DOORS` | 8 literal → **15** sau `_extra_doors()` | classic (study, mozart_var); barrios (preludio); villa (villa_pattern); brouwer (noviembre, elogio_pizz); bach (bourree, fuga); `_extra_doors()` update thêm 7 torroba |

**Gap và cách sửa (PR #146):** bảng cũ `_PEDAL_DOOR_PROFILE` có **10 key**, trùng `_PROFILE` từng entry, phủ 11/38 dòng; **27 dòng còn lại trước đây** rơi về `"study"`. Nay bảng đã bị **xoá** và `door_profile(name)` dùng `_PROFILE.get(name, "study")`. Test khoá: **door coverage 38/38 dòng**, **profile resolve 38/38** (đều qua `_PROFILE`), và fallback `"study"` chỉ cho tên lạ. Không còn khái niệm "entry explicit".

### 14.5. Validator và test

1. Door chỉ phủ bar có `kind_at in _PEDAL`; không overlap body.
2. Mỗi `(ensemble, pattern)` có tối đa một door; trùng key phải khai rõ module nào thắng (hiện `_RETAINED_DOORS` thắng).
3. `door_profile(name)` phải resolve qua `_PROFILE[name]`; chỉ unknown mới về `"study"`.
4. Region 1 bar phải đi `_compressed`; region dài dùng `steps = 4` (bucket), không phải `steps = length`.
5. Golden riêng cho door theo `(ensemble, pattern, section kind, length, roles)`: note table, không dùng Score hash. `steps` chỉ 2/4 nên không đủ phân biệt length 3 và 4.
6. Negative: door xuất hiện trong body → fail; pattern **không có trong `_PROFILE`** → fail (thiếu profile không còn là khái niệm, vì profile derive từ body).

### 14.6. Checklist khi thêm pattern

- [ ] `traits.has_door` — **field đề xuất** trong PR #142, **chưa có trong code**; không đi tìm nó trên branch này.
- [ ] Nếu có: viết hàm door, đăng ký vào module (`guitar_frame_rest.DOORS`, `guitar_frame_bach_sor.DOORS`, hoặc `guitar_torroba_doors.DOORS`) **hoặc** `_RETAINED_DOORS`.
- [ ] Không cần thêm entry: door tự dùng `_PROFILE[pattern]`. Chỉ thêm **override table** nếu cửa cần trần register/velocity khác body, kèm test cho phép khác.
- [ ] Door golden cho `(ensemble, pattern)` × `intro/outro` × `length`/`roles` (không chỉ `steps` 2/4).
- [ ] Nếu pattern không có cửa (hiếm), khai `fallback: composer_frame` và test rằng frame composer chạy được.

### 14.7. Non-goals

- Door **không** phải Texture, **không** phải Sentence; không đưa vào `PATTERN_NAMES`, không in tên, không vào `Movement.title`.
- Door không tham gia `plan_sentences`.
- Refactor pattern/topic/texture/sentence **không đổi** door; chỉ khi thêm pattern mới cần checklist trên.
