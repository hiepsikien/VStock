# Mô hình âm nhạc của lớp guitar — Topic / Texture / Procedure / Sentence / Plan

> **Trạng thái**: đề xuất, dùng làm căn bản cho refactor renderer. **Chưa code.**
> **Phạm vi**: lớp `guitar` trong `backend/app/sonify/` (villa, torroba, barrios, brouwer, bach, classic).
> **Liên quan**: [`sonify-texture-studio.md`](./sonify-texture-studio.md) (PR #142), [`sonify-pattern-names.md`](./sonify-pattern-names.md), [`sonify-classical-guitar.md`](./sonify-classical-guitar.md), [`sonify-guitar-torroba-plan.md`](./sonify-guitar-torroba-plan.md).
> **Thứ tự**: doc này là điều kiện trước cho (a) refactor renderer và (b) Texture Studio khi thêm texture cho Villa-Lobos.

---

## 1. Vì sao cần doc này

Hai từ đang bị quá tải, và chính chỗ quá tải đó làm mọi cuộc tranh luận về cấu trúc bị lệch:

- **`pattern`** đang đồng thời là: tên in trên chart (topic), cách điền ô nhịp (texture), và đôi khi là cả hình thức của một câu (sentence). Ví dụ `preludio` của Barrios là **một tác phẩm**; `villa_pattern` là **một âm hình**; `galop` là **một điệu nhảy** — cả ba đều là `pattern id`.
- **`figure`** của Torroba không phải "figure" theo nghĩa nhạc lý (động cơ 2–5 nốt). Nó là **sentence archetype**: một template nhiều ô, mỗi ô là một texture, mang vai hình thức (walk = tiền đề, cadence = kết). Bằng chứng: việc chọn nó phụ thuộc **độ dài phrase, số thứ tự phrase, phrase có `closes` không** — `_castillo_spans` (`guitar_torroba.py:1660`), `_sonatina_open_spans`/`_sonatina_close_spans` (antecedent/consequent), `_danza_spans` (câu 4 ô cố định).

Kết luận đầu tiên: **`figure` nên đổi tên thành `sentence`**. Doc này dùng `sentence` từ đây.

---

## 2. Các trục

Âm nhạc ở đây được mô tả bằng các trục **trực giao**. Một đối tượng chỉ khai những trục có nghĩa với nó; trục không khai là rỗng, không phải "chưa làm".

| Trục | Trả lời | Ví dụ |
|---|---|---|
| **Pattern level** | Pattern tự đứng tên được (`topic`) hay chỉ là idiom kỹ thuật (`texture`) | `castillo` = topic; `tremolo` = texture |
| **Topic** (định danh) | **Tên in ra** của đơn vị: thể loại, điệu, chức năng, hoặc idiom mượn tên tác phẩm | `Fugue`, `Mazurka-Choro`, `Castillo`, `Cathedral` |
| **Topic source** (metadata) | Cái tên đến từ đâu: `dance` / `work` / `form` / `character` / `procedure` | `Sarabande` = dance; `Castillo` = work; `Fugue` = procedure |
| **Texture** (âm hình) | Cách **điền một ô**: voicing, rhythm cell, articulation | arpeggio/campanella, chord-melody, tremolo, bariolage, galop cell |
| **Procedure** (thủ pháp) | **Phép biến đổi sinh ra chất liệu** từ melody/harmony | imitation, ground bass, sequence, pedal, variation |
| **Sentence** (câu) | Template **nhiều ô** có vai hình thức và độ dài co giãn | walk→cadence (9 ô), Arada (5 ô), Float (2 ô), galop period 4+4 |
| **Cell** | Biến thể của texture, không phải đơn vị độc lập | galop 1 / galop 2, castillo type 7 / type 8 |
| **Plan** | Quan hệ giữa các đơn vị theo thời gian | A–B–A, contrast/trio, avoid-repeat, khoá một pattern |

### 2.1. Movement là level **trên** pattern, không phải một giá trị của `level`

Movement không phải một loại pattern. Nó là **đơn vị biểu diễn** chứa 1..N pattern, có hình thức/độ dài/nhịp/tông riêng.

| | **Movement** | **Pattern** |
|---|---|---|
| Là gì | đơn vị biểu diễn: bản 1D, chương I–IV của 1M, một tuần | slot filler trong một movement |
| Có gì | `FormSpec` (meter, tempo, bars, sections), key, character, plan, title | `level`, topic, texture, procedure, sentence, wave profile, family, door |
| Chứa | **1..N pattern** | 0..N sentence |
| Quyết định | hình thức, độ dài, nhịp, tông, tên in của chương | cách điền ô, nhãn, thủ pháp, câu |

Bằng chứng trong code:

- Movement = `PreparedMovement` (`span.py:835`): `label`, `spec` (`FormSpec`), `bars`, `groups`, `key`, `character`, `mode`…
- Số movement theo span: `plan_week` trả **1** movement (`span.py:800`), `plan_month` trả **4** (I–IV, `:805`), `plan_quarter` trả **3** (`:816`).
- **1D = 1 movement = 1 pattern.** `DAILY_ENSEMBLE_SPEC` = 2 + 30 + 2 = **34 bar** (`form.py:261-264`); `_assign_macro` thấy `bars <= 40` và không có contrast section → khoá **một** pattern cho cả body (`guitar_patterns.py:1537,1616`). Đây là lý do 1D "trùng tên": movement chỉ có một pattern nên tên pattern thành tên chương.
- **1W = 1 movement, nhiều pattern.** `week_spec` ghi rõ *"One continuous movement"* (`span.py:205`); 5 phiên ≈ 160 bar → vượt ngưỡng 40 → `_assign_macro` chia region / A–B–A.
- **1M/3M = nhiều movement, mỗi movement nhiều pattern.** 4 movement × 96 bar (1M), 3 movement (3M).

**Gap hiện tại (phải sửa trước khi bỏ in texture):** guitar chưa có tên movement độc lập.

- `movement_title()` trả **`None` cho guitar** (`span.py:943-947`: *"Guitar dances are named by the pattern picker, not by this table"*).
- `span_movement_name()` trả `stored` với guitar (`program.py:163-164`).
- `stored` do `guitar_movement_name` dựng từ `pattern_form()` — **tối đa 3 tên pattern** (`program.py:60-90`).

Nghĩa là hôm nay "tên chương" của guitar **là bản tóm tắt pattern**, không phải identity của movement. Hệ quả: bỏ in `villa_pattern`/`tremolo` sẽ để movement line rỗng. Vì vậy refactor phải thêm **`Movement.title`** thật (ví dụ `"Suite Popular Brasileira — Mazurka-Choro"`, `"1D Étude"`), và `pattern_form()` chỉ còn là mô tả hình thức, không phải tên.

Form (hình thức của cả chương) **không phải** thuộc tính của pattern. Form sống ở hai chỗ: `FormSpec.sections` (`span.py`) và Plan.

Bảng phân biệt gọn:

| | Trả lời | Thuộc về |
|---|---|---|
| **Topic** | "Đơn vị này **là gì**, in tên gì" | một pattern |
| **Movement** | "Đơn vị biểu diễn nào đang chứa nó" | movement (`FormSpec` + Plan + title) |
| **Form** | "Các đơn vị được **xếp** thế nào" | movement (`FormSpec` + Plan) |

---

## 3. Luật

1. **Pattern có Topic. Movement chứa 1..N pattern và có FormSpec/Plan riêng.** Topic là identity của pattern (một ngôi); Form là relation giữa các pattern (nhiều ngôi, có thứ tự).
2. **Nhãn (Topic) là tên đơn vị, không bao giờ là kỹ thuật.** `Arpeggio`, `Tremolo`, `Chord Melody` là kỹ thuật → `level: texture`, không in (xem §8). Tên mượn từ tác phẩm (`Castillo`, `Juglar`, `Cathedral`) là hợp lệ với `topic_source: work`.
3. **Chỉ khai cái code thực thi.** Với mỗi pattern hỏi: *"renderer làm gì mà pattern khác không làm?"* Câu trả lời là texture/procedure. Không có câu trả lời → đó là **label**, không phải cơ chế.
4. **Form là metadata của pattern, là cơ chế của movement.** Khai `form: "fugue"` trên pattern không làm engine hiểu fugue; muốn hiểu phải khai `form.functions[]` ở tầng movement.
5. **Cell không phải pattern; variation không phải lớp.** Biến thể trong ô là `texture.cells`; biến hoá giữa các câu là `plan`.
6. **Meter không phải pattern.** `ctx.kind` là per-render, và `_guitar_meter` (`span.py:288`) còn hoán đổi 3/4 ↔ 6/8. Meter thuộc `meter_variants` của texture.
7. **1D không phải ngoại lệ.** Nó là movement chỉ chứa một pattern, nên tên pattern trùng tên chương. Đừng suy ra "pattern = movement" từ trường hợp đó.

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

Chaconne cũng vậy — `_render_bach_chaconne_bar` (`:1464`): *"Chaconne **ground in the bass**, bariolage sixteenths above, and a breakout scale"* → procedure = **ground bass / ostinato**, texture = bariolage 16th.

Ghi chú: motif **contour** đã được mô hình hoá cho fuga (`(offset, length, direction)`); motif dạng **pitch cell** thì chưa.

### 4.2. Bảng Bach

| Pattern | Topic (label) | Nguồn tên | Procedure (executable) | Texture | Sentence |
|---|---|---|---|---|---|
| `bach_fuga` | Fugue | thủ pháp | **imitation** lag 2, contour 1:1, no retrograde | polyphony 3 bè | null |
| `bach_chaconne` | Chaconne | thủ pháp | **ground bass / ostinato** | bariolage 16th | null |
| `bach_prelude` | Prelude | chức năng | figuration (arpeggiation) | broken chord | null |
| `bach_allemande` / `courante` / `sarabande` / `bourree` / `gavotte` | tên điệu | thể loại | sequence (không tường minh) | polyphonic / homophonic | null |
| `bach_gigue` | Gigue | thể loại | — (chưa dùng imitation) | polyphonic | null |

---

## 5. Ba chỗ hay nhầm, đã chốt

| Trường hợp | Không phải | Là |
|---|---|---|
| **Galop 1 / Galop 2** (Sor) | hai sentence, hai topic, hai pattern | **hai cell** trong một texture. `_galop1_cell` (`guitar_sor.py:291`), `_galop2_cell` (`:349`); `_render_galop_dance` (`:413`) chọn theo `index % 8 >= 4` — 4 ô "câu hỏi", 4 ô "câu trả lời" |
| **Tremolo** (Barrios) | sentence | **texture**. Chọn theo điều kiện giai điệu (`hold` + 90 ≤ bpm ≤ 140) trong `_select_body` (`guitar_patterns.py:940`) |
| **Arpeggio** | topic | **họ texture** (`_ARPEGGIO`, `_FAMILY`); việc `villa_pattern` in "Arpeggio" là lỗi nhãn (§8) |
| **Cathedral Preludio** (Barrios) | sentence | **movement-level**: `_catedral_preludio` (`guitar_barrios.py:19`) chọn texture (16th thật nếu movement có frame, 8th nếu fixture) |
| **Perpetual tremolo** (Barrios, `_perpetual_bars` `:571`) | pattern thứ hai | **variation của texture** trong cùng topic: 2 bar khi `band == "f"` và `mood == "volatile"` |

---

## 6. Bảng 6 composer theo trục thực thi

| | Topic | Texture | Procedure | Sentence | Plan |
|---|---|---|---|---|---|
| **Villa** | 5 pattern | ✓ + meter variants | none | null | `_select_body` |
| **Torroba** | 7 pattern | ✓ | none | **✓** walk/cadence, arada/float, type6 | `_torroba_primary/_contrast` |
| **Barrios** | 8 pattern | ✓ + perpetual overlay | none | null | `_select_body` |
| **Sor / Classic** | 5 pattern | ✓ + cells | none | **period 4+4** (galop) | `_assign_macro` + `_settle_galop` |
| **Bach** | 9 pattern | ✓ | **✓** imitation, ground bass | null | `_bach_primary/_contrast` |
| **Brouwer** | 4 pattern | ✓ | none | null | `_brouwer_primary/_contrast` |

Bảng này nói đúng bản chất: **chỉ Bach có procedure, chỉ Torroba có sentence, chỉ galop có period tường minh**; phần còn lại là texture + plan.

---

## 7. Ánh xạ code → trục

| Code | Trục |
|---|---|
| `span.py:288` `_guitar_meter`, `span.py:299 retarget_torroba_meter` | form-level retarget (không phải pattern/procedure) |
| `guitar_patterns.py:318` `_meter_kind` | bucket meter → **materialization**, không phải identity |
| `guitar_patterns.py:48` `_FAMILY` | họ texture (không phải palette) |
| `guitar_patterns.py:88` `_PROFILE` | profile playability theo pattern |
| `guitar_wave.py:108` `PROFILES` | velocity contour theo `(ensemble, pattern)` |
| `program.py:53` `pattern_title` | **Topic** (in ra) |
| `program.py:60` `pattern_form` | **Form** của movement (in `A — B — A`, tối đa 3 title) |
| `guitar_patterns.py:894` `_select_body` | **Plan** (theo phrase) |
| `guitar_patterns.py:1118` `_dominant_pattern_auto` | **Plan** (macro: cả body/section/session) |
| `guitar_patterns.py:1378` `_contrast_pattern` | **Plan** (tương phản) |
| `guitar_patterns.py:1537` `_assign_macro` | **Plan/Form** (khoá 1 pattern, A–B–A, per-region) |
| `guitar_patterns.py:1691` `_settle_galop` | **Plan/Form** (đặt galop giữa các region) |
| `guitar_torroba.py:3403` `_FIGURES` | **Texture của slot** trong sentence |
| `guitar_torroba.py:1660` `_castillo_spans` | **Sentence** (chọn archetype theo length/parity/closes) |
| `guitar_torroba.py:1826` `torroba_figure_plan` | **Sentence plan** (bar → slot) |
| `guitar_sor.py:291/349` galop cells | **Cell** |
| `guitar_barrios.py:571` `_perpetual_bars` | **Texture variation** |
| `guitar_bach.py:490` `_fuga_motif`, `:603` `_compose_fuga_bass` | **Procedure** (imitation) |
| `guitar_bach.py:1464` chaconne | **Procedure** (ground bass) + texture |
| `guitar_frame.py:1233` `_RETAINED_DOORS`, `guitar_torroba_doors.py:946` `DOORS` | **Plan** (intro/outro), không phải texture |

---

## 8. Vi phạm hiện tại

| Vi phạm | Bằng chứng | Sửa |
|---|---|---|
| Nhãn là kỹ thuật: `villa_pattern` in **"Arpeggio"** | `_PATTERN_TITLE["villa_pattern"] = "Arpeggio"` (`program.py`) | đổi thành tên tác phẩm/chương, hoặc để trống và để `level: texture` không in |
| Nhãn là kỹ thuật: `tremolo` in **"Tremolo"** | `_PATTERN_TITLE["tremolo"] = "Tremolo"` | như trên |
| Tên "figure" cho một sentence archetype | §1 | đổi từ vựng sang `sentence` |
| `pattern` không khai `level` | 38 pattern, 3 mức trộn lẫn | thêm `level` |

Hai lỗi nhãn này không sửa bằng luật chung được: chúng là quyết định nội dung (in gì trên chart), phải chọn tên cụ thể.

### 8.1. Đề xuất tên cho các nhãn đang sai

Tiêu chí: nhãn phải là **tên đơn vị** (điệu, thể loại, character, hoặc idiom mượn tên tác phẩm). Nếu pattern là **texture thuần** thì `level: texture` và **không in** — tên chương do `Movement.title` in.

**Điều kiện:** hiện guitar chưa có `Movement.title` (§2.1 gap) — `movement_title()` trả `None` cho guitar và tên đang được dựng từ `pattern_form()`. Vì vậy **phải thêm `Movement.title` trước** khi bỏ in texture, nếu không movement line rỗng.

| Pattern | Hiện tại | Đề xuất | Lý do |
|---|---|---|---|
| `villa_pattern` | in **"Arpeggio"** | `level: texture`, **title = null** (không in) | "Arpeggio" là kỹ thuật. Đây là âm hình mặc định của Villa (campanella/arpeggio), dùng cho nhiều đoạn; nó không phải tên một chương. Tên chương lấy từ `Movement.title` (ví dụ `"Suite Popular Brasileira — Mazurka-Choro"`). |
| `tremolo` (barrios) | in **"Tremolo"** | `level: texture`, **title = null** (không in) | "Tremolo" là kỹ thuật. Nếu movement là một tác phẩm tremolo (*El Último Trémolo*, *Una Limosna*), tên đó thuộc `Movement.title`, không phải pattern. |
| `chord_melody` | in **"Chord Melody"** | `level: texture`, **title = null** | cùng lỗi: tên kỹ thuật đội lốt chương. |
| `thumb_cantabile` | barrios: "Cantabile"; villa: "Prelude" | cả hai là `topic`, nhưng **phải tách id** (hoặc cho phép title theo ensemble) | **cùng một id đang có hai title**. Một topic không thể vừa là character vừa là tác phẩm; đây là vi phạm nặng hơn ba lỗi trên. |

Hệ quả migration (phải là một release có chủ ý, không phải refactor im lặng):

- Thêm `Movement.title` (từ `pieceCopy`/`FormSpec`/spec) và cho `span_movement_name()` dùng nó thay vì `stored` dựng từ pattern.
- `pattern_form()` chỉ in pattern `level: topic`; texture không in. Movement line vẫn có tên nhờ `Movement.title`.
- Metadata audio, DFI signature, và test golden in tên đều đổi theo → cần chạy lại parity/golden và ghi rõ trong changelog.

### 8.2. Bốn câu hỏi nội dung cần chốt

> Q1 cũ (7 pattern Torroba là movement hay topic) **đã chốt**: `topic`. Movement là level trên pattern (§2.1), nên câu hỏi đó không còn.

| # | Câu hỏi | Vì sao cần chốt | Khuyến nghị |
|---|---|---|---|
| 1 | `study` (classic) in "Etude" ở mọi đoạn mặc định: giữ `topic` hay chuyển `texture`? | "Etude" là thể loại, không phải kỹ thuật → được phép in; nhưng `study` là fallback mặc định nên in "Etude" ở mọi đoạn có thể là nhiễu | giữ `topic` + "Etude" (đúng thể loại); chỉ đổi nếu nghe thấy nhiễu |
| 2 | `mozart_var` in "Variations" nhưng code chỉ là bass + counter-melody | Tên gợi `procedure: variation` nhưng **không có procedure** trong code | giữ nhãn, khai `procedure: none`, ghi backlog "variations thật" |
| 3 | `bach_gigue` có nên dùng `procedure: imitation`? | Gigue ngoài đời thường fugal; code hiện không imitation | không, ở giai đoạn này — thêm là **thay đổi hành vi**, cần nghe duyệt |
| 4 | `Movement.title` lấy từ đâu? | Guitar chưa có tên movement độc lập (§2.1) | `FormSpec`/spec mang `title`; 1D lấy topic của pattern duy nhất, 1W/1M/3M lấy tên chương do Studio/pieceCopy khai |

---

## 9. Cây phân loại cho mọi thứ mới

0. Có `FormSpec` riêng (meter/tempo/bars/sections), key, character, và chứa 1..N pattern? → **Movement** (không phải pattern).
1. Đơn vị có **tự đứng tên** được (điệu/thể loại/character/idiom mượn tên tác phẩm)? → `level: topic` + `topic_source`.
2. Chỉ nói **cách điền trong ô**, tên là kỹ thuật, giữ nguyên qua nhiều phrase? → `level: texture` (+ `cells`), không in.
3. Chiếm **N ô với vai tiền đề/kết**, độ dài co giãn? → `sentence`.
4. Chỉ là **2–5 nốt** và được nhắc lại/biến hình? → `motif`.
5. Là **phép biến đổi** sinh voice khác? → `procedure`.

Lưu ý: câu 0 hỏi *đơn vị*, câu 1–2 hỏi *pattern*. Một movement 1D chỉ có một pattern nên tên trùng nhau — đó là trường hợp thu hẹp, không phải định nghĩa.

---

## 10. Hệ quả cho refactor

1. **Không promote variation thành pattern.** Nhánh per-bar (`band`, `tresillo`, `approach`, `perpetual`) thuộc texture; promote sẽ vi phạm contract "pattern chọn theo phrase".
2. **Hai lớp còn thiếu tên**: `sentence` (Torroba) và **`Movement.title`** (guitar). Cái thứ hai là điều kiện trước để bỏ in texture, vì hiện tên chương đang dựng từ `pattern_form()`.
3. **`procedure` là executable**; `form` là metadata của pattern, là cơ chế của movement. Đừng để spec khai `form` rồi tưởng engine hiểu.
4. **Nên data-hoá Plan.** `_select_body` và `_dominant_pattern_auto` đang là **hai bản luật song song** cho Villa, lệch nhau ở `trio/bridge`, `first_body`, majority band. Tách thành một bảng luật, giữ hai mode (`phrase`/`macro`), lock bằng parity — chưa hội tụ hành vi.
5. **Điều kiện tiên quyết**: harness parity (`Score` hash trên ma trận `ensemble × meter × mood × band × bpm × span`) để chứng minh mọi bước refactor không đổi output.
6. **Bảng inventory đã có** (§12). Việc tiếp theo là registry (`level`/`topic`/`topic_source`) + parity, rồi mới tới `sentence` và `Movement.title`.

---

## 11. Câu hỏi mở

1. **`Movement.title`** cho guitar: lấy từ đâu (spec, `FormSpec`, hay `pieceCopy`)? 1D có lấy topic của pattern duy nhất không?
2. **Nhãn thay thế** cho `villa_pattern`/`tremolo`/`chord_melody`: đã đề xuất **không in**; còn câu hỏi chart có nên in texture bao giờ không (mặc định: không).
3. **`bach_gigue`** có nên dùng `procedure: imitation` (gigue thường fugal) hay giữ "sequence không tường minh"?
4. **`form.functions[]`** (exposition/episode/stretto, real vs tonal answer) có nằm trong phạm vi Phase 2–3, hay để sau?
5. **Motif pitch-cell** có cần mô hình hoá, hay chỉ giữ contour như fuga hiện nay?

---

## 12. Phụ lục A — Inventory 38 pattern

Nguồn: `PROFILES` (37 cặp `(ensemble, pattern)`), `_FAMILY` (38, thêm `pedal`), `_PATTERN_TITLE`, dispatch `render_patterned_voices`. Cột `level` là **đề xuất**; `?` = cần chốt (§8.2). Texture lấy từ docstring của renderer tương ứng.

| Ensemble | id | Title hiện tại | Level | Texture (+cells) | Procedure | Sentence |
|---|---|---|---|---|---|---|
| bach | `bach_allemande` | Allemande | topic | style brisé bè 8, pickup 4×16 | none | null |
| bach | `bach_bourree` | Bourree | topic | treble = price; bass quarter đáp 8th | none | null |
| bach | `bach_chaconne` | Chaconne | topic | bariolage 16 trên bass | **ground bass / ostinato** | null |
| bach | `bach_courante` | Courante | topic | melody 8th + rhythm theo price; bass ngân cả ô | none | null |
| bach | `bach_fuga` | Fugue | topic | soprano = price; bass trễ 2 ô | **imitation** (lag 2, contour 1:1, no retro) | null |
| bach | `bach_gavotte` | Gavotte | topic | quarter, staccato quarter, 4×8 song song 3/6 | none | null |
| bach | `bach_gigue` | Gigue | topic | broken chord + scale khi line lên | none (`?` §8.2.4) | null |
| bach | `bach_prelude` | Prelude | topic | 2 bè; mỗi price 8 + neighbor; bass attack | none | null |
| bach | `bach_sarabande` | Sarabande | topic | beat 2 roll chord; beat cuối pass/sing | none | null |
| barrios | `andante` | Andante | topic | block-chord (chorale) | none | null |
| barrios | `choro` | Choro | topic | dance grid | none | null |
| barrios | `hemiola` | Hemiola | topic | dance grid, hemiola | none | null |
| barrios | `polca` | Polka | topic | dance grid | none | null |
| barrios | `preludio` | Prelude | topic | 3 bè: high / lower-middle / upper-middle | none | null |
| barrios | `thumb_cantabile` | Cantabile | topic | thumb melody (`_render_thumb`) | none | null |
| barrios | `tremolo` | Tremolo | **texture** | tremolo grid (`_tremolo`) | none | null |
| barrios | `vals` | Waltz | topic | dance grid | none | null |
| brouwer | `brouwer_etude` | Etude | topic | tumbao 3+3+2, inner voice off-eighths | none | null |
| brouwer | `elogio_pizz` | Dance | topic | staccato ostinato + Bartók slap | none | null |
| brouwer | `noviembre` | Ballade | topic | ballad pulse 2 phách + pickup + color arpeggio | none | null |
| brouwer | `sarabande` | Sarabande | topic | beat 2 heavy chord + swarm trên price | none | null |
| classic | `cantabile` | Cantabile | topic | phrase-level cantabile | none | null |
| classic | `elegiaque` | Elegy | topic | elegy bar | none | null |
| classic | `galop` | Galop | topic (Op. 32 No. 6) | galop cell **1 / 2** | none | **period 4+4** |
| classic | `mozart_var` | Variations | topic (Op. 9) | classical bass + counter-melody 8th | none (`?` §8.2.3) | null |
| classic | `study` | Etude | topic (`?`) | arpeggio; `character is None` → plain arpeggio | none | null |
| torroba | `alcaniz` | Alcaniz | topic | campanella slots (`_FIGURES` 10/11) | none | spans (opening/soft) |
| torroba | `castillo` | Castillo | topic | campanella slots (`_FIGURES` 7/8/13/14) | none | **walk→cadence (3/4, 9 ô); type7 5 ô / type8 2 ô (4/4)** |
| torroba | `danza` | Danza | topic | type6 slots | none | **4 ô (type6)** |
| torroba | `fandanguillo` | Fandanguillo | topic | fandanguillo slots | none | spans |
| torroba | `olite` | Olite | topic | olite onsets (`_olite_onsets`) | none | thin (12) |
| torroba | `sonatina` | Sonatina | topic | sonatina slots | none | **open/close spans** |
| torroba | `torroba_tremolo` | Juglar | topic | tremolo slots | none | thin (9) |
| villa | `chord_melody` | Chord Melody | **texture** | block-chord + melody | none | null |
| villa | `etude1` | Etude 1 | topic | 16-note RH cycle; thumb root 1 lần | none | null |
| villa | `etude11` | Etude 11 | topic | 4 sextuplet arches; open-E pedal | none | null |
| villa | `thumb_cantabile` | Prelude | topic (**khác barrios**) | thumb melody | none | null |
| villa | `villa_pattern` | Arpeggio | **texture** | arpeggio/campanella roll (`_render_villa_bar`) | none | null |
| (mọi) | `pedal` | Pedal | texture | pedal/frame bar (không có wave profile) | none | null |

Tổng hợp:

| Level | Số pattern | Ghi chú |
|---|---|---|
| `topic` | 35 | tất cả pattern tự đứng tên: 9 Bach, 8 Barrios, 4 Brouwer, 5 Classic (`study` còn `?` §8.2), 7 Torroba, 5 Villa (trừ `villa_pattern` texture) |
| `texture` | 4 | `villa_pattern`, `chord_melody`, `tremolo`, `pedal` |
| `procedure` khác none | **2** | `bach_fuga` (imitation), `bach_chaconne` (ground bass) |
| `sentence` khác null | **8** | 7 Torroba + `galop` (period 4+4) |

39 dòng = 38 cặp trong `PROFILES` + `pedal` (không có wave profile).

Ba kết luận từ bảng:

1. **`procedure` gần như trống.** Chỉ Bach có procedure thực thi. Đây là lý do đừng xây cơ chế procedure chung trước khi có pattern thứ ba cần nó.
2. **`sentence` chỉ có ở Torroba + galop.** Villa/Barrios/Brouwer/Classic thuần texture + plan — đúng bản chất nhạc của họ, không phải thiếu sót.
3. **4 pattern `texture` đang in tên như chương** (`villa_pattern`, `chord_melody`, `tremolo`, `pedal`) — nhóm vi phạm cần xử lý trước, nhưng chỉ sau khi có `Movement.title` (§2.1 gap), nếu không movement line sẽ rỗng.
4. **Movement không nằm trong bảng này.** 1D = 1 movement/1 pattern; 1W = 1 movement/N pattern; 1M = 4 movement; 3M = 3 movement. Bảng trên chỉ là pattern.
