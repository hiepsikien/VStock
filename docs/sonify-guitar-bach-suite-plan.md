# Kế Hoạch Mở Rộng Tổ Khúc Baroque Của J.S. Bach: Prelude, Allemande & Courante

> **Tài liệu liên kết**: [`docs/sonify-guitar-bach-plan.md`](./sonify-guitar-bach-plan.md), [`docs/sonify-classical-guitar.md`](./sonify-classical-guitar.md), [`docs/sonify-guitar-frame-variations.md`](./sonify-guitar-frame-variations.md), [`docs/sonify-guitar-dynamics-wave-plan.md`](./sonify-guitar-dynamics-wave-plan.md), [`docs/sonify-guitar-scales-plan.md`](./sonify-guitar-scales-plan.md)
> **Mẫu giai điệu và nhịp scheduler là hai việc khác nhau**:
> - **`bach_prelude`** lấy vòm rải từ *Prélude* BWV 998, BWV 999 và BWV 1007.
> - **`bach_allemande`** lấy *style brisé* từ Allemande của lute suite BWV 996 và BWV 995, không lấy Allemande của BWV 1007.
> - **`bach_courante`** lấy cú nhảy mở ô, bốn móc kép giữa ô và hemiola từ Courante BWV 1007 (nhịp `3/4`). Scheduler vẫn có thể đặt Courante vào chương `4/4` hoặc `6/8`. Lưới `4/4` ở Mục 2.3 là lưới của scheduler, không phải nhịp của tổng phổ.
> **Mục tiêu**:
> 1. Bổ sung **3 pattern** còn thiếu ở đầu tổ khúc: **`bach_prelude`**, **`bach_allemande`**, **`bach_courante`**. Bach đi từ 6 pattern lên **9 pattern**.
> 2. Mỗi pattern có một nhà. `1D` chỉ nghe 7 pattern vì ngày luôn là `4/4`: Sarabande và Gigue ở các chương `3/4` và `6/8`. Một chương dài nghe 2 pattern khi có 2 hoặc 3 vùng, và nghe phần tử thứ ba của palette khi có từ 4 vùng (`1W` 4–5 phiên). Form `A–B–A` lặp pattern mở. Một `character` không đi hết 9 pattern trong một lần phát.
> 3. **`1D` (34 ô, `4/4`, 96 BPM, có khung)**: một pattern cho cả thân bài (30 ô).
> 4. **Chương có khung và `ctx.bars > 40`**: một hàng tổ khúc, kể cả chương đã có `bridge` hoặc `trio`. Ví dụ tên chương: `Prelude — Allemande — Prelude`, `Allemande — Courante — Allemande`, `Gigue — Courante — Gigue`, `Bourree — Fugue — Bourree`, `Sarabande — Chaconne — Sarabande`.

---

## 1. Chẩn Đoán: Vì Sao Cách Bố Trí Hiện Tại Của Bach Bị Lệch Và Đơn Điệu?

Trong `backend/app/sonify/guitar_bach.py` và `backend/app/sonify/guitar_patterns.py`, cách chọn pattern hiện tại của Bach có 3 hạn chế lớn:

1. **Thiếu Prelude, Allemande và Courante**:
   - Một Lute Suite (BWV 995–1000) hay Cello Suite (BWV 1007–1012) mở bằng Prelude, sang Allemande, rồi Courante, trước Sarabande, các *galanteries* (Gavotte, Bourrée) và Gigue hoặc Chaconne.
   - Vì thiếu 3 pattern này, chương `4/4` calm rơi vào `bach_gavotte` và chương `4/4` rally rơi vào `bach_bourree`.
2. **Chương dài một mood thì một pattern, và chương có contrast chỉ có cặp A/B cũ**:
   - Trong `span.py`, chương chậm (`1M` II, `3M` II, `1Y` giữa) có `bridge=True`. Scherzo (`1M` III, `1Y` tháng 3, 6, 9) có `trio=True`. Những chương đó đi nhánh `_has_contrast_section` trong `_assign_macro`, rồi `_bach_contrast`: `3/4` đối `bach_chaconne`, `6/8` calm đối `bach_bourree`, `6/8` khác calm đối `bach_fuga`.
   - Chương `4/4` của variant `guitar` có `bridge=False` và `trio=False`: `1M` I (3 vùng), `1M` IV (3 vùng), `3M` I (3 vùng), `3M` III (3 vùng), `1Y` tháng mở (2 vùng), `1Y` tháng 12 (3 vùng). Chúng rơi vào vòng `regime_slot` ở `_assign_macro` (`guitar_patterns.py`, khoảng dòng 1207–1219). Barrios đã có `_barrios_palette`. Bach gọi `_dominant_pattern` trên từng slot với cùng `character`, nên cả chương một pattern. `3M` chương I dài 192 ô.
   - Hàng mới ở Mục 3.3 phải được gán **trước** cả nhánh contrast lẫn vòng slot. Sửa riêng vòng slot thì chương chậm và scherzo giữ cặp cũ.
3. **Bốn pattern gánh gần hết lịch**:
   - `3/4` hoặc `bpm <= 72` vào `bach_sarabande`, trừ `selloff` có `rel_span >= 0.016` và không có contrast thì vào `bach_chaconne`.
   - `6/8` calm và rally vào `bach_gigue` (`volatile` và `selloff` đã được trả về sớm hơn, thành Fugue và Chaconne).
   - `4/4` calm vào `bach_gavotte`, `4/4` rally vào `bach_bourree`.

---

## 2. Thiết Kế Âm Nhạc & Kỹ Thuật Cho 3 Pattern Mới

### 2.1. `bach_prelude` — *Prélude Harpeggiato / Moto Perpetuo* (BWV 998 / BWV 999 / BWV 1007)

- **Thẩm mỹ & Kết cấu**:
  - Dòng móc kép liên hoàn qua 3 tầng dây (trầm `p`, trung `i, m`, cao `a`).
  - Bass tấn công đúng một lần ở đầu mỗi nửa ô và ngân hết nửa ô đó. Các móc kép sau trải trung rồi cao. Nốt giá nằm ở đỉnh vòm, không chồng attack với Bass.
- **Một attack mới mỗi móc kép**. Nốt đang ngân không tính là attack mới. `_render_bach_prelude_bar` dùng `divisions = 4`.
- **Nhịp `4/4` (`epb = 8`, 16 móc kép)**: hai chu kỳ 8 móc kép, `origin16 = 0` và `origin16 = 8`. Trong mỗi chu kỳ:
  - `slot 0`: chỉ Voice 3 (`low`). Bass `_bach_bass` (bậc `0` ở nửa đầu ô, bậc `2` hoặc `1` ở nửa sau), `duration_beats = 2.0`. Lead không attack ở slot này.
  - `slot 1, 2`: Voice 2 (`support`) đi `low_mid` rồi `upper_mid`.
  - `slot 3`: Voice 1 (`lead`) attack `_melody_at(ctx, eighth + 1)`, `duration_beats = 0.5`, ngân qua `slot 4`.
  - `slot 4, 5`: Voice 2 attack `low_mid` rồi `upper_mid` trong lúc Lead còn ngân.
  - `slot 6`: Voice 1 attack `_melody_at(ctx, eighth + 3)`.
  - `slot 7`: Voice 2 khép bằng `upper_mid` hoặc `low_mid`.
- **Nhịp `3/4` và `6/8` (`epb = 6`, 12 móc kép)**: hai chu kỳ 6 móc kép.
  - `slot 0`: chỉ Voice 3, ngân 6 móc kép (`1.5` phách).
  - `slot 1, 2`: Voice 2, `low_mid` rồi `upper_mid`.
  - `slot 3`: Voice 1 hát nốt giá.
  - `slot 4`: Voice 2 `low_mid`.
  - `slot 5`: Voice 2 `upper_mid`. Một attack, không chọn Lead hay Support tùy lúc.
- **Thế tay**: tại mỗi móc kép, tập nốt đang kêu (attack mới và nốt ngân) đi qua `_playable`, với `bass < low_mid <= upper_mid < lead`.

### 2.2. `bach_allemande` — *Style Brisé & Sixteenth Anacrusis* (BWV 996 / BWV 995)

- **Thẩm mỹ & Kết cấu**:
  - Vũ điệu `4/4` legato. Không `staccato` như Bourrée hay Gavotte.
  - Hai dấu hiệu:
    1. **Đối vị bù nhịp**: Lead ngân dài thì Bass và Support đi liền bậc. Lead đi móc đơn thì Bass giữ và Support vào lệch phách.
    2. **Bốn móc kép lấy đà**: ở hai móc đơn cuối của ô mở (`bar == 0`) hoặc ô mà hợp âm/phrase đổi ở `bar + 1`, Lead chạy đúng 4 móc kép liền bậc.
- **Lưới `_render_bach_allemande_bar`**:
  - **Voice 1**: `_sustain` trên lưới móc đơn. Khi `_allemande_passes(ctx, bar, start, epb)` đúng (`bar == 0` hoặc câu/hợp âm đổi ở ô sau), đoạn `epb - 2` chạy `_fitting_scale` 4 móc kép vào nốt đầu của `bar + 1`.
  - **Voice 3**: gốc ở `offset 0`, bậc 5 hoặc bậc 3 ở phách giữa (`offset 4` khi `4/4`, `offset 3` khi `6/8`, `offset 4` khi `3/4`). Không `staccato`. Nếu `_hold_at(lead, ...) >= 2` tại phách đó, nửa sau phách đi bộ `_walk`.
  - **Voice 2**: vào móc đơn ngay sau Bass (`offset 1` và `offset 5` ở `4/4`; `offset 1` và `offset 4` ở `3/4` và `6/8`), quãng 3 hoặc 6 (`_parallel`, rồi `_choose_inner`), ngân `1.0` phách.

### 2.3. `bach_courante` — *Compound Leap, Running Sixteenths & Hemiola* (mẫu BWV 1007)

- **Thẩm mỹ**: Courante cello suite số 1, đối lập Sarabande. Ba dấu ấn của BWV 1007:
  1. **Cú nhảy mở ô**: `eighth 0` có Bass gốc `accent=True` và Lead chạm nốt giá. Đây là hai attack cùng móc đơn, khác luật một attack của Prelude. `eighth 1` là Lead bật lên, `staccato=True` (mô-típ `G2 -> G3`). Nếu nốt `eighth 1` trùng nốt `eighth 0`, Lead bước một quãng 3 thuận thang qua `_treble_step(ctx, sung, 2)`.
  2. **Bốn móc kép ở phách giữa**: phách 2 khi `epb = 6`, phách 3 khi `epb = 8`.
  3. **Lấy đà cuối ô**. Hemiola (Bass ở eighth `0` và `3`) chỉ khi `phrase.closes` và nhịp là `3/4` hoặc `6/8`.
- **Lưới `_render_bach_courante_bar`, `divisions = 4`**:
  - **`3/4` và `6/8` (`epb = 6`)**:
    - `eighth 0`: Bass `duration = 2` eighths, `accent=True`; Lead `duration = 1` eighth, `accent=True`.
    - `eighth 1`: Lead staccato; Support điểm âm ở giữa.
    - `eighth 2, 3` (móc kép `4..7`): Lead chạy `_fitting_scale` 4 nốt tới cao độ phách 3. Bass bậc 5 hoặc bước liền bậc ở `eighth 2`, `duration = 2` eighths. Khi `phrase.closes`, Bass bỏ `eighth 2` và đánh `eighth 3`.
    - `eighth 4`: Lead `staccato=True`; Support quãng 3 hoặc 6 bên dưới. `eighth 5`: Lead và Bass lấy đà sang `bar + 1`.
  - **`4/4` (`epb = 8`)**, dùng khi Courante là khách của một chương `4/4`:
    - `eighth 0, 1`: cùng cú nhảy mở ô, Support ở `eighth 1`.
    - `eighth 2, 3`: Lead giữ nốt giá `duration = 2` eighths; Bass đi ở `eighth 2`; Support ở `eighth 3`.
    - `eighth 4, 5` (móc kép `8..11`): Lead chạy 4 móc kép; Bass bậc 5 ở `eighth 4`.
    - `eighth 6, 7`: Lead `eighth 6` staccato, `eighth 7` lấy đà cùng Bass và Support.
  - Trên `4/4` không có hemiola eighth `0` và `3`.

---

## 3. Quy Hoạch Pattern Theo Quãng Thời Gian

### 3.1. Cổng chọn lịch

Đo chung, cùng cách với `_daily_barrios_pattern` trừ ngưỡng hẹp của calm:

- `hold_ratio = holds / len(phrases)` với `holds` đếm `_has_hold`. Không có câu thì tỷ lệ là `0`.
- `activity = min(_raw_activity(ctx, bars), _melody_activity(ctx, bars))`.
- `BACH_NARROW_SPAN = 0.008`. Ngưỡng này mới, chỉ tách calm.
- `wide = ctx.rel_span >= 0.014`. Mốc `0.014` là mốc rally của `_daily_barrios_pattern`.
- `lively = activity >= 0.35`. Cờ này chỉ tách rally rộng của `1D`.

Ba cửa, theo thứ tự:

1. **Không khung** (`not _framed(ctx)`): giữ `_bach_primary` và `_bach_contrast` như hiện tại. Calm `4/4` là Gavotte, rally `4/4` là Bourrée, contrast của Bourrée là Fugue, contrast của `3/4` là Chaconne, contrast của `6/8` calm là Bourrée.
2. **`1D` có khung**: `bars == 34`, `bpm == 96`, `kind == "4/4"`. Một pattern theo Mục 3.2. `bars <= 40` nên không đi palette.
3. **Chương có khung và `ctx.bars > 40`**: trước nhánh `_has_contrast_section` và trước vòng slot, lấy primary từ vùng đầu, rồi `_bach_palette` + cùng luật vùng với `_barrios_region_patterns`:
   - 2 vùng: `palette[0]`, `palette[1]`.
   - 3 vùng: `palette[0]`, `palette[1]`, `palette[0]`. `palette[2]` không kêu.
   - 4 vùng: `palette[0]`, `palette[1]`, `palette[2]`, `palette[0]`.
   - 5 vùng: `palette[0]`, `palette[1]`, `palette[2]`, `palette[1]`, `palette[0]`.
4. **`1W` một phiên** là 32 ô, `bars <= 40`, một pattern. Primary dùng menu mở `4/4` ở Mục 3.3, không dùng luật Gavotte-trên-rally của `1D`.

`_is_suite_finale` (`_trailing_pedal_length >= 10`, tính cả outro và cooldown sau `attach_frame`) chọn menu finale. `1M` IV, `3M` III và `1Y` tháng 12 đạt mốc này. Chương mở không đạt. Context không có field span, nên không nhận finale bằng số chương.

### 3.2. Bản `1D` có khung

| Mood | Điều kiện | Pattern cả thân bài |
|---|---|---|
| `calm` | `hold_ratio >= 0.3` hoặc `rel_span < 0.008` | `bach_prelude` |
| `calm` | phần calm còn lại | `bach_allemande` |
| `rally` | `rel_span < 0.014` | `bach_bourree` |
| `rally` | `wide` và `lively` | `bach_courante` |
| `rally` | `wide` và không `lively` | `bach_gavotte` |
| `volatile` | mọi phiên volatile | `bach_fuga` |
| `selloff` | mọi phiên selloff | `bach_chaconne` |

Gavotte trên rally chỉ có ở fingerprint `1D` này. `bach_sarabande` và `bach_gigue` không có cửa trên `1D`.

### 3.3. Primary và palette khi có khung

Primary đọc mood của vùng đầu. Rally của chương dài chỉ tách bằng `wide`. Cờ `lively` không đẩy Courante lên làm primary.

| Chương | Primary | Palette | Tên khi 3 vùng | Tên khi 2 vùng |
|---|---|---|---|---|
| `4/4` mở (`1W`, `1M` I, `3M` I, `1Y` tháng 1, 4, 7, 10) | calm hẹp hoặc nhiều nốt ngân: `bach_prelude`. Calm còn lại: `bach_allemande`. Rally không `wide`: `bach_allemande`. Rally `wide`: `bach_bourree`. Volatile: `bach_fuga`. Selloff: `bach_chaconne` | prelude: `(prelude, allemande, bourree)`. Allemande: `(allemande, courante, gavotte)`. Bourrée: `(bourree, gavotte, fuga)`. Fugue: `(fuga, allemande, bourree)`. Chaconne: `(chaconne, sarabande, fuga)` | `Prelude — Allemande — Prelude`, `Allemande — Courante — Allemande`, `Bourree — Gavotte — Bourree`, `Fugue — Allemande — Fugue`, `Chaconne — Sarabande — Chaconne` | bỏ tên thứ ba, vì vùng 2 là `palette[1]` và không có tái hiện |
| `3/4` chậm, có bridge (`1M` II 72 BPM, `3M` II 60 BPM, `1Y` tháng 2, 5, 8, 11 ở 66 BPM) | `bach_sarabande` với mọi mood, kể cả selloff | calm hoặc rally: `(sarabande, prelude)`. Volatile: `(sarabande, courante)`. Selloff: `(sarabande, chaconne)` | `Sarabande — Prelude — Sarabande`, `Sarabande — Courante — Sarabande`, `Sarabande — Chaconne — Sarabande` | cùng cặp, không lặp |
| `6/8` scherzo, có trio (`1M` III 120 BPM, `1Y` tháng 3, 6, 9 ở 108 BPM) | rally: `bach_gigue`. Calm: `bach_courante`. Volatile: `bach_fuga`. Selloff: `bach_chaconne` | gigue: `(gigue, courante)`. Courante: `(courante, gigue)`. Fugue: `(fuga, courante)`. Chaconne: `(chaconne, gavotte)` | `Gigue — Courante — Gigue`, `Courante — Gigue — Courante`, `Fugue — Courante — Fugue`, `Chaconne — Gavotte — Chaconne` | cùng cặp |
| `4/4` finale | calm: `bach_gavotte`. Rally, kể cả rally `wide`: `bach_bourree`. Volatile: `bach_fuga`. Selloff: `bach_chaconne` | gavotte: `(gavotte, bourree)`. Bourrée: `(bourree, fuga)`. Fugue: `(fuga, prelude)`. Chaconne: `(chaconne, fuga)` | `Gavotte — Bourree — Gavotte`, `Bourree — Fugue — Bourree`, `Fugue — Prelude — Fugue`, `Chaconne — Fugue — Chaconne` | cùng cặp |

Calm `6/8` có khung mở bằng Courante, khách là Gigue. Hôm nay `_bach_contrast` của Gigue calm là Bourrée. Không còn hàng `(gigue, bourree)` cho calm, vì primary calm không còn là Gigue. Bản không khung vẫn đi contrast cũ.

`palette[2]` chỉ kêu ở `1W` 4 hoặc 5 phiên. `pattern_form` với hơn 3 tên giữ tên đầu, tên giữa và tên cuối. Tuần 5 phiên mở Prelude nghe Prelude, Allemande, Bourrée, Allemande, Prelude, còn tiêu đề là `Prelude — Bourree — Prelude`. Allemande có trong nhạc và vắng trên tiêu đề. Đó là luật `pattern_form` hiện có.

Sarabande là khách của hàng Chaconne `4/4`. Renderer Sarabande giữ trọng âm riêng của nó trên lưới `4/4` sẵn có. Chương không bị đổi sang `3/4`.

Hàng selloff chậm `(sarabande, chaconne)` trùng contrast hiện tại. `test_bach_slow_selloff_with_a_contrast_stays_sarabande` gọi `framed=False` và kỳ vọng `Sarabande — Chaconne — Sarabande`. Cả hai cửa đều ra cặp đó.

### 3.4. Một mood nghe được những pattern nào

Các số dưới đây là một chương hoặc cả span cùng một mood. Vùng 3 không chơi `palette[2]`. `3M` không có chương `6/8`, nên Gigue không xuất hiện ở `3M`.

| Span và mood | Pattern thực sự kêu | Không kêu |
|---|---|---|
| `1D`, mọi mood trong Mục 3.2 | đúng 1 pattern trong 7 pattern của bảng `1D` | Sarabande, Gigue |
| `1W`, 1 phiên | 1 pattern của menu mở `4/4` | Courante không làm primary. Gavotte, Sarabande, Gigue không làm primary |
| `1W`, 2–3 phiên | 2 pattern, `palette[0]` và `palette[1]` | `palette[2]` |
| `1W`, 4–5 phiên | 3 pattern của palette, vùng cuối lặp pattern mở | pattern ngoài hàng đó |
| `1M` calm | Prelude, Allemande, Sarabande, Courante, Gigue, Gavotte, Bourrée | Fugue, Chaconne |
| `1M` rally không `wide` | Allemande, Courante, Sarabande, Prelude, Gigue, Bourrée, Fugue | Gavotte, Chaconne |
| `1M` rally `wide` | Bourrée, Gavotte, Sarabande, Prelude, Gigue, Courante, Fugue | Allemande, Chaconne |
| `1M` volatile | Fugue, Allemande, Sarabande, Courante, Prelude | Bourrée, Gavotte, Gigue, Chaconne |
| `1M` selloff | Chaconne, Sarabande, Gavotte, Fugue | Prelude, Allemande, Courante, Bourrée, Gigue |
| `3M` calm | Prelude, Allemande, Sarabande, Gavotte, Bourrée | Courante, Gigue, Fugue, Chaconne |
| `3M` rally không `wide` | Allemande, Courante, Sarabande, Prelude, Bourrée, Fugue | Gavotte, Gigue, Chaconne |
| `3M` rally `wide` | Bourrée, Gavotte, Sarabande, Prelude, Fugue | Allemande, Courante, Gigue, Chaconne |
| `1Y` calm | 7 pattern, cùng tập với `1M` calm | Fugue, Chaconne |
| `1Y` mà các tháng `6/8` là volatile hoặc selloff | Gigue vắng, vì hai mood đó không mở Gigue và không mời Gigue | Gigue |

Đủ 9 pattern chỉ khi các chương trong cùng một span mang các mood bù lỗ cho nhau. Form `A–B–A` cố ý lặp pattern mở.

---

## 4. Đồng Bộ Với Các Hệ Thống Phụ Trợ Trong Codebase

### 4.1. Test không khung và finale rally có khung

`_framed` đúng khi có section `intro`, `outro`, `warmup` hoặc `cooldown`.

Không khung:

- Calm `4/4` vẫn `bach_gavotte`.
- Rally `4/4` vẫn `bach_bourree`.
- `_bach_contrast` của `bach_bourree` vẫn `bach_fuga`.
- Nửa đầu `test_bach_trio_answers_the_bourree_with_the_fugue` là hai section `phrase`, `trio=True`, không pedal. Nửa đó vẫn Bourrée rồi Fugue, Bass ô 2 là nốt tròn.

Có khung, `finale = _suite(3, "bach", character="rally")` trong cùng test, assertion ở dòng 4376–4378:

- Score này đã `attach_frame`, `bars > 40`, nên đi palette mới.
- Hàng rally finale là `("bach_bourree", "bach_fuga")`. Không đổi khách thành Gavotte.
- Ô 12 nằm trong phrase slot 0, tức vùng A. Lead và Support ô 12 không có móc kép vì Bourrée đi lưới móc đơn.
- `finale.divisions == 2` chỉ còn đúng nếu cả chương, kể cả vùng Fugue, không viết móc kép nào. Fugue tự thân dùng `_sustain`. Scale Nhóm 3 có thể thêm móc kép và kéo `divisions` của cả score lên 4, vì `divisions` nhìn mọi voice. Nếu fixture này sinh móc kép ngoài ô 12, giữ hai assert `_sixteenths(..., 12)` và sửa assert `divisions` theo nốt thực viết. Không đổi hàng palette để ép `divisions == 2`.

`test_a_mixed_sor_movement_keeps_the_patterns_beside_galop` chỉ gọi `_settle_galop` trên Sor. Test đó không khóa hàng Bach.

### 4.2. Sóng Volume Affine & Cổng Snap (`backend/app/sonify/guitar_wave.py`)

Thêm 3 dòng vào `PROFILES`. File đang có 28 dòng. Sau khi thêm là **31 dòng**. Mỗi dòng cần một mã snap mới trong bộ phân loại `_is_target`: `prelude`, `allemande`, `courante`.

| Khóa `(ensemble, pattern)` | Cửa sổ calm → wide | $W$ | Snap | Hạn mức `(phrase, sec)` | Cú được snap |
|---|---|---|---|---|---|
| `("bach", "bach_prelude")` | `28..56` → `34..62` | `5` | `66..68` | `(1, 2)` | Lead mở chu kỳ rải (`eighth in {0, 4}` ở `4/4`, `eighth in {0, 3}` ở `3/4` và `6/8`) khi nốt đó thuộc `phrase.apex` và `rise >= 3`. |
| `("bach", "bach_allemande")` | `28..56` → `34..62` | `9` | `66..68` | `(1, 2)` | Lead tại `phrase.apex` khi `rise >= 3`. |
| `("bach", "bach_courante")` | `30..58` → `36..63` | `3` | `68..70` | `(1, 3)` | Attack `accent=True` của cú nhảy mở ô, hoặc Lead tại `phrase.apex` khi `rise >= 3`. |

Cả ba thỏa `ceil - floor >= 27`, nên `gain == 1`. Courante wide là `63 - 36 = 27`.

### 4.3. Cửa Intro / Outro

Ba cửa mới nằm trong `DOORS` của `backend/app/sonify/guitar_frame_bach_sor.py`. `_extra_doors` trong `guitar_frame.py` đã merge dict đó. Bourrée và Fugue tiếp tục ở `_RETAINED_DOORS`. Không thêm Prelude, Allemande, Courante vào `_RETAINED_DOORS`.

1. **`("bach", "bach_prelude"): bach_prelude`**:
   - **Intro ngắn (2 bước)**: Bước 0, Bass `I` ngân dưới vòng rải móc kép ở `_P`. Bước 1, rải móc kép trên `V7`, Bass chủ giữ `_MP`.
   - **Intro dài (4 bước)**: `I` ở `_P`, `IV` ở `_P`, `V7` trên pedal ở `_MP`, rồi rải `V7 -> I` ở `_MP` nối vào thân bài.
   - **Outro ngắn (2 bước)**: rải giãn thành móc đơn trên `V7` ở `_MP`, rồi hợp âm `I` ngân ở `_P`.
   - **Outro dài (4 bước)**: `IV` ở `_MP`, `V7` ở `_P`, `_bach_arpeggiato` trên `I` ở `_P`, block `I` ở `_PP`.
2. **`("bach", "bach_allemande"): bach_allemande`**:
   - **Intro ngắn**: pickup móc kép vào `I` kiểu *style brisé* ở `_P`, rồi đi bộ qua `V7` với 4 móc kép cuối ô ở `_MP`.
   - **Intro dài**: pickup vào `I` ở `_P`, *style brisé* `I -> IV` ở `_P`, `_bach_mordent` trên `V7` ở `_MP`, bốn móc kép từ `V7` vào thân bài ở `_MP`.
   - **Outro ngắn**: *style brisé* `IV -> V7` ở `_MP`, block `I` ở `_P`.
   - **Outro dài**: `IV` ở `_P`, `V7` kèm mordent ở `_MP`, treo `I` ở `_P`, block `I` ở `_PP`.
3. **`("bach", "bach_courante"): bach_courante`**:
   - **Intro ngắn**: cú nhảy trên `I` (phách 1 `accent`, móc đơn 2 `staccato`) ở `_P`, rồi bốn móc kép trên `V7` và hai móc đơn lấy đà ở `_MP`.
   - **Intro dài**: nhảy trên `I` ở `_P`, nhảy và lướt trên `IV` ở `_P`, bốn móc kép trên `V7` ở `_MP`, lấy đà vào thân bài ở `_MP`.
   - **Outro ngắn**: hemiola eighth `0` và `3` trên `V7` ở `_MP`, hợp âm `I` ở phách 1 ngân hết ô ở `_P`.
   - **Outro dài**: Courante trên `IV` ở `_MP`, bốn móc kép trên `V7` ở `_MP`, hemiola `I -> V7` ở `_P`, block `I` ở `_P`.

### 4.4. Scale Engine (`backend/app/sonify/guitar_scale_passages.py`)

`bach_group2_window` và `bach_group2_intrinsic_eighths` hiện trả `None` khi pattern không thuộc `{bach_gigue, bach_chaconne, bach_sarabande}`. Thêm Courante vào frozenset `_BACH_GROUP2` mà không sửa hai hàm đó thì Courante không có cửa sổ nội tại.

- **`bach_courante` thuộc Nhóm 2**. Cửa sổ eighth bao của bốn móc kép giữa ô, inclusive:
  - `epb == 6`: `(bar * epb + 2, bar * epb + 3)`.
  - `epb == 8`: `(bar * epb + 4, bar * epb + 5)`.
  - Các eighth đó là intrinsic vì lưới Courante luôn viết tirata, khác Gigue chỉ viết scale khi `_rises`. Eighth `0` và `1` nằm ngoài cửa sổ, nên biến động nhỏ không đè cú nhảy mở ô.
  - Sóng lớn (`L >= epb` và `net_span >= 6`) chỉ mở sau một ô Courante trọn của vùng, cùng luật *establish pattern first*.
  - Bass dưới passage: eighth `0` vẫn là gốc hợp âm, `accent=True`. Ô `phrase.closes` ở `3/4` hoặc `6/8` vẫn có Bass ở eighth `3`. Không thay bằng Bass gốc/bậc 5 chung của Nhóm 3.
- **`bach_allemande` không vào `_BACH_GROUP2`**. Allemande là Nhóm 3, nên nhận scale sub-bar và multi-bar. Hairpin nằm trong `_HAT_PATTERNS`, cửa `52..82`. Bass dưới passage giữ Bass Allemande: gốc ở offset `0`, bậc 5 hoặc 3 ở phách giữa, không staccato, đi bộ khi Lead ngân. Không rút Bass thành nốt ngắn trên `ctx.strong`.
- **`bach_prelude` không vào `_BACH_GROUP2`**. Prelude cũng là Nhóm 3. `_BAROQUE_PATTERNS` chỉ đặt cửa hairpin `54..84`. Set đó không cấp và không cấm scale. Bass dưới passage giữ pedal nửa ô: attack ở eighth `0` và `4` khi `4/4`, eighth `0` và `3` khi `3/4` hoặc `6/8`, ngân hết nửa ô. Không đổi pedal này thành gốc ngắn trên phách mạnh.

### 4.5. Tên chương (`backend/app/sonify/program.py` và `src/sonify/program.ts`)

1. `_PATTERN_TITLE` thêm:

   ```python
   "bach_prelude": "Prelude",
   "bach_allemande": "Allemande",
   "bach_courante": "Courante",
   ```

2. `form_pattern_ids` đọc `_region_pattern_ids` khi `ctx.ensemble in {"barrios", "bach"}` và `ctx.bars > 40 and _framed(ctx)`. Cùng điều kiện với cổng palette trong `_assign_macro`. Bản Bach không khung, dù dài, vẫn đi headline và contrast cũ.
3. `src/sonify/program.ts`: thêm `'Allemande'` và `'Courante'` vào `PATTERN_NAMES`. `'Prelude'` đã có, vì Villa. `isPatternForm` tách bằng ` — `.

### 4.6. Chỗ phải đăng ký id mới

Mỗi id `bach_prelude`, `bach_allemande`, `bach_courante` cần có mặt ở:

- `_FAMILY` và `_PROFILE` trong `backend/app/sonify/guitar_patterns.py`.
- Nhánh render cạnh `bach_fuga` / `bach_bourree` trong cùng file, qua ba hàm `_render_bach_*_bar` import từ `guitar_bach.py` như sáu pattern Bach hiện có.
- `DOORS` ở Mục 4.3.
- `PROFILES` ở Mục 4.2.
- `_PATTERN_TITLE` và `PATTERN_NAMES` ở Mục 4.5.
- `_BACH_GROUP2` chỉ nhận `bach_courante`. `_HAT_PATTERNS` nhận `bach_allemande`. `_BAROQUE_PATTERNS` nhận `bach_prelude`.

Thiếu một map thì dispatcher rơi về Bourrée hoặc bỏ qua cửa sóng, cửa scale, cửa intro.

---

## 5. Danh Mục Kiểm Thử

1. **`backend/tests/test_sonify_guitar.py`**:
   - `test_bach_prelude_rolls_sixteenth_arpeggio_across_three_voices`: `divisions == 4`. Mỗi móc kép có đúng một attack mới ở Lead hoặc Support, trừ móc kép đầu mỗi nửa ô chỉ có attack Bass. Bass ngân hết nửa ô. Lead không attack cùng móc kép với Bass. `assert_playable(..., "bach")` trên tập nốt đang ngân.
   - `test_bach_allemande_weaves_style_brise_and_sixteenth_pickup`: Support vào sau Bass, Bass đi bộ khi Lead ngân, không `staccato`, đúng 4 móc kép ở hai eighth cuối khi `_allemande_passes`.
   - `test_bach_courante_leaps_on_beat_one_and_runs_sixteenths_on_the_middle_beat`: `accent` ở eighth `0`, `staccato` ở eighth `1`, 4 móc kép ở phách giữa, lấy đà cuối ô. Hemiola eighth `3` chỉ khi `phrase.closes` trên `3/4` hoặc `6/8`.
   - `test_bach_1d_stays_one_pattern_and_longer_spans_walk_suite_rows`: `1D` có khung một pattern suốt 30 ô thân bài. `1W` một phiên một pattern. `1W` từ 2 phiên, `1M`, `3M`, `1Y` đi đúng hàng Mục 3.3. Chương 3 vùng không chơi `palette[2]`.
   - Scherzo `6/8` calm có khung mở Courante và khách Gigue.
   - Giữ nguyên nửa không khung của `test_bach_trio_answers_the_bourree_with_the_fugue`. Ô 12 của finale rally có khung vẫn Bourrée, không móc kép. Assert `divisions` của finale theo Mục 4.1.
2. **`backend/tests/test_program.py` và `src/sonify/program.test.ts`**:
   - `pattern_title` của Prelude, Allemande, Courante.
   - Tên `Prelude — Allemande — Prelude`, `Allemande — Courante — Allemande`, `Gigue — Courante — Gigue`, `Bourree — Fugue — Bourree`.
   - `test_bach_slow_selloff_with_a_contrast_stays_sarabande` vẫn `Sarabande — Chaconne — Sarabande` khi `framed=False`.
3. **`backend/tests/test_guitar_wave.py`**:
   - Tập `PROFILES` đủ 31 khóa, thêm ba pattern Bach. Bất biến `ceil - floor >= 27` và `gain == 1` vẫn đúng.
