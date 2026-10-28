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

- **Thẩm mỹ**: bản guitar của prelude lute và cello. Hai bè. Bass ngân. Bè cao là một dòng móc kép liên tục. Không có bè giữa chạy móc kép: lớp đó nghe như Preludio của Barrios.
- **Bè cao là price action.** Mỗi móc đơn của giá thành hai móc kép trên Voice 1. Móc kép chẵn của nhóm (phách của móc đơn) là đúng `_melody_at` của móc đơn đó. Móc kép lẻ là một bậc phụ, rồi nhóm sau trở về nốt giá kế. Hình này lặp mỗi nửa ô. `_render_bach_prelude_bar` dùng `divisions = 4`.
- **Bậc phụ cùng chiều với quãng giá.** Giá lên hoặc giá xuống: bậc phụ nằm trong quãng nối nốt giá này tới nốt giá sau, một bậc thuận thang. Giá đứng: bậc trên. Bậc phụ không đảo chiều đường giá.
- **Bass.** Một attack Voice 3 ở đầu mỗi nửa ô, ngân hết nửa ô (`4/4`: 4 móc đơn, `duration_beats = 2`; `3/4` và `6/8`: 3 móc đơn, `duration_beats = 1.5`). Nửa đầu bậc `0`, nửa sau bậc `2` hoặc `1`. Bass và nốt giá được phép cùng đánh ở móc kép đầu nửa ô. Bass không thay một nốt của dòng bè cao.
- **`4/4`**: nửa ô là eighth `0` và eighth `4`, mỗi nửa 4 nốt giá và 4 bậc phụ. **`3/4` và `6/8`**: nửa ô là eighth `0` và eighth `3`, mỗi nửa 3 nốt giá và 3 bậc phụ. Prelude vẫn chia đôi ô. Trên `3/4` bass ở eighth `3`, không dời sang eighth `4`.
- **Bè giữa, tùy chọn và thưa.** Tối đa một nốt Voice 2 trong một nửa ô, chỉ khi bass và các nốt giá của nửa ô đó chưa có bậc 3 của hợp âm. Nốt đó ngân đến hết nửa ô, nhẹ hơn nốt giá cùng lúc. Không gảy bè giữa theo móc kép.
- **Cửa `_prelude_roll`**: cùng hai bè. Slot 0 là bass ngân hết nửa ô. Mọi móc kép sau là Voice 1, một dòng âm hợp âm, không có Voice 2 chạy trong vòng. Ô outro cuối viết `_bach_block` vẫn là hợp âm chủ ngân hết ô.
- **Thế tay**: mỗi móc kép, nốt đang kêu đi qua `_playable`. Hết chỗ thì hạ bass, không đổi nốt giá trên phách.

### 2.2. `bach_allemande` — *Style Brisé & Sixteenth Anacrusis* (BWV 996 / BWV 995)

- **Thẩm mỹ & Kết cấu**:
  - Vũ điệu `4/4` legato. Không `staccato` như Bourrée hay Gavotte.
  - Hai dấu hiệu:
    1. **Đối vị bù nhịp**: Lead ngân từ 2 móc đơn trở lên thì Bass đi bộ và Support được phép vào, một nốt quãng 3 hoặc 6, lệch phách. Lead đi từng móc đơn thì Bass giữ và Support im.
    2. **Bốn móc kép lấy đà**: ở hai móc đơn cuối của ô mở (`bar == 0`) hoặc ô mà hợp âm/phrase đổi ở `bar + 1`, Lead chạy đúng 4 móc kép liền bậc.
- **Scheduler chỉ đặt Allemande trên `4/4`**. Lưới `3/4` và `6/8` vẫn có, để một id bị gọi ép vẫn chơi được. Không chép offset của `3/4` sang `6/8`.
- **Lưới `_render_bach_allemande_bar`**:
  - **Voice 1**: `_sustain` trên lưới móc đơn. Khi `_allemande_passes(ctx, bar, start, epb)` đúng (`bar == 0` hoặc câu/hợp âm đổi ở ô sau), hai eighth cuối (`epb - 2` và `epb - 1`) chạy đúng 4 móc kép `_fitting_scale` vào nốt đầu của `bar + 1`.
  - **Voice 3**, không `staccato`. Nếu `_hold_at(lead, ...) >= 2` tại phách đó, nửa sau phách đi bộ `_walk`:
    - `4/4`: gốc ở eighth `0`, bậc 5 hoặc bậc 3 ở eighth `4`.
    - `3/4`: gốc ở eighth `0`, bậc 5 hoặc bậc 3 ở eighth `4` (trọng phụ).
    - `6/8`: gốc ở eighth `0`, bậc 5 hoặc bậc 3 ở eighth `3` (phách chấm thứ hai).
  - **Voice 2** chỉ viết tại offset mà `_hold_at(lead, eighth, epb) >= 2`. Cao độ là quãng 3 hoặc 6 (`_parallel`, rồi `_choose_inner`), vào một móc đơn sau bass và ngân trong khoảng lead đang giữ. Lead đang chạy từng móc đơn thì danh sách support của phách đó rỗng.
  - Khi `_allemande_passes`, Lead chiếm hai eighth cuối. Support và Bass không ngân vào chùm đó:
    - `4/4`: Support ở eighth `5` rút còn 1 eighth. Nốt `1.0` phách cũ sẽ phủ eighth `6`, đúng chỗ pickup bắt đầu. Bass ở eighth `4` ngân 2 eighth và hết đúng lúc eighth `6`.
    - `3/4`: bỏ Bass eighth `4` và Support eighth `5`, vì pickup chính là eighth `4` và `5`. Bass eighth `0` vẫn ngân 2 eighth.
    - `6/8`: bỏ Support eighth `4`. Bass eighth `3` rút còn 1 eighth. Pickup là eighth `4` và `5`.

### 2.3. `bach_courante` — *Compound Leap, Running Sixteenths & Hemiola* (mẫu BWV 1007)

- **Thẩm mỹ**: một giai điệu cello viết cho guitar. Bè cao mang cả ô. Nửa đầu ô là giai điệu. Nửa sau là nhịp. Bass một nốt đầu ô, ngân hết ô. Thân ô không có bè giữa.
- **Nửa giai điệu** (`4/4`: eighth `0..3`; `3/4` và `6/8`: eighth `0..2`). Mỗi móc đơn là `_melody_at` của móc đó, `duration = 1` eighth. Hai nốt đầu trùng cao độ thì eighth `1` nhảy một quãng 3 thuận thang `_treble_step(ctx, sung, 2)`, `staccato=True`. Hai nốt đã khác nhau thì hát đúng giá, kể cả khi giá xuống.
- **Nửa nhịp** (`4/4`: eighth `4..7`; `3/4` và `6/8`: eighth `3..5`). Nốt mở nửa này là giá tại eighth đầu. Nốt tới là giá tại eighth áp chót của nửa ô (`4/4`: eighth `6`; `3/4` và `6/8`: eighth `4`). Các móc kép ở giữa nối hai nốt đó cùng chiều quãng. Không viết bốn lần cùng một cao độ: hai đầu bằng nhau thì móc kép thứ hai và thứ ba là một bậc phụ. Eighth cuối của ô (`4/4`: eighth `7`; `3/4` và `6/8`: eighth `5`) bước một bậc thuận thang về phía nốt giá đầu `bar + 1`, chiều bậc là chiều quãng sang ô sau.
- **Bass**: một attack ở eighth `0`, `accent=True`, `duration` hết ô. Không thêm bass giữa ô.
- **`phrase.closes`**: nửa nhịp bỏ móc kép, hát nốt giá bằng móc đơn. `3/4` nhấn eighth `0` và `3`. `6/8` nhấn eighth `0`, `2` và `4`. `4/4` không hemiola. Trên ô kết, một nốt Voice 2 ngân cùng bass khi hợp âm còn thiếu bậc 3. Thân các ô không kết không có Voice 2.
- **`_tirata_line` không còn fallback `[arrival] * count`.**

### 2.4. Kiểm tra hai bè và price action

Scheduler, Fugue, và ô outro `_bach_block` giữ nguyên. Sửa mọi test đang bắt Prelude hoặc Courante có support chạy móc kép, hoặc bắt Allemande có support khi lead đang đi từng móc đơn.

- Prelude, `4/4`: bass chỉ ở eighth `0` và `4`, mỗi nốt ngân 2 phách. Mỗi móc đơn có một móc kép lead đúng bằng giá của móc đó, và một móc kép bậc phụ. Giá đi xuống thì bậc phụ không cao hơn nốt giá vừa hát. Support rỗng khi hợp âm đã có bậc 3 trong bass và các nốt giá.
- Prelude, hai giá liền nhau khác nhau: móc kép mạnh giữ đúng hai cao độ đó.
- Courante, giá bằng ở eighth `0` và `1`: eighth `1` cao hơn một quãng 3 và `staccato`. Giá giảm: eighth `1` thấp hơn eighth `0`. Giá tăng: eighth `1` là nốt giá.
- Courante, `4/4`: eighth `0..3` là móc đơn theo giá. Eighth `4` là giá tại đó. Eighth `6` là giá tại đó. Eighth `7` là một bậc về phía ô sau. Bass chỉ một nốt, dài cả ô. Support của ô không kết là rỗng.
- Courante, `phrase.closes` trên `6/8`: lead không có móc kép. Accent ở eighth `0`, `2`, `4`.
- Allemande, lead chạy từng móc đơn: support của ô đó rỗng, bass không đi bộ. Lead ngân từ 2 móc đơn: support có tối đa một nốt trong khoảng ngân, bass được đi bộ. Bốn móc kép lấy đà vẫn ở hai eighth cuối khi `_allemande_passes`.
- Cửa `_prelude_roll`: sau slot bass, mọi attack là Voice 1. Voice 2 không có mặt trong vòng rải.

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
| `3M` calm hẹp hoặc nhiều nốt ngân | Prelude, Allemande, Sarabande, Gavotte, Bourrée | Courante, Gigue, Fugue, Chaconne. `3M` không có scherzo `6/8`, nên Courante không được mời từ Gigue |
| `3M` calm còn lại | Allemande, Courante, Sarabande, Prelude, Gavotte, Bourrée | Gigue, Fugue, Chaconne. Gavotte của hàng Allemande là `palette[2]`, không kêu; Gavotte kêu vì là primary của finale |
| `3M` rally không `wide` | Allemande, Courante, Sarabande, Prelude, Bourrée, Fugue | Gavotte, Gigue, Chaconne |
| `3M` rally `wide` | Bourrée, Gavotte, Sarabande, Prelude, Fugue | Allemande, Courante, Gigue, Chaconne |
| `3M` volatile | Fugue, Allemande, Sarabande, Courante, Prelude | Bourrée, Gavotte, Gigue, Chaconne |
| `3M` selloff | Chaconne, Sarabande, Fugue | Prelude, Allemande, Courante, Bourrée, Gavotte, Gigue. Gavotte của `1M` selloff đến từ scherzo, mà `3M` không có scherzo |
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

Có khung, `finale = _suite(3, "bach", character="rally")` trong cùng test:

- Score này đã `attach_frame`, `bars > 40`, nên đi palette mới.
- Khách duy nhất của rally finale là Fugue: `("bach_bourree", "bach_fuga")`. Không có hàng Gavotte song song.
- Ô 12 là ô đầu của phrase slot 0 sau warmup 4 ô và intro 8 ô, vẫn thuộc vùng Bourrée. Hai assert `_sixteenths(finale.lead, 12)` và `_sixteenths(finale.support, 12)` giữ `[]`.
- `_render_bach_fuga_bar` đi `_sustain`, lưới móc đơn, cùng họ với Bourrée và cửa Bourrée. `divisions` của cả score lên 4 khi bất kỳ voice nào, kể cả passage Nhóm 3 trong vùng Fugue, viết một móc kép. Fixture này dùng `_bars()` 48 nến. Khi triển khai, chạy đúng score đó: nếu không có móc kép thì giữ `finale.divisions == 2`; nếu có thì đổi mỗi assert đó thành `== 4`. Không đổi palette để giữ số 2.

`test_a_mixed_sor_movement_keeps_the_patterns_beside_galop` chỉ gọi `_settle_galop` trên Sor. Test đó không khóa hàng Bach.

### 4.2. Sóng Volume Affine & Cổng Snap (`backend/app/sonify/guitar_wave.py`)

Thêm 3 dòng vào `PROFILES`. Comment trong `guitar_wave.py` đang ghi đúng 28 dòng. Sau khi thêm là **31 dòng**, và comment đó sửa theo. Mỗi dòng cần một nhánh mới trong `_is_target`.

`_is_target` lấy `eighth = int(round(beat * 2))`. Prelude snap vào móc kép mạnh của mỗi cặp giá, tức slot chẵn `int(round(beat * 4))`, khi nốt đó thuộc `phrase.apex` và `rise >= 3`. Không còn khóa riêng slot 3 và 11.

| Khóa `(ensemble, pattern)` | Cửa sổ calm → wide | $W$ | Snap | Hạn mức `(phrase, sec)` | Cú được snap |
|---|---|---|---|---|---|
| `("bach", "bach_prelude")` | `28..56` → `34..62` | `5` | `66..68` | `(1, 2)` | Lead ở móc kép mạnh của mỗi cặp giá (slot chẵn), khi nốt đó thuộc `phrase.apex` và `rise >= 3`. |
| `("bach", "bach_allemande")` | `28..56` → `34..62` | `9` | `66..68` | `(1, 2)` | Lead tại `phrase.apex` khi `rise >= 3`. |
| `("bach", "bach_courante")` | `30..58` → `36..63` | `3` | `68..70` | `(1, 3)` | Lead `accent=True` của cú nhảy khi hai nốt giá đầu trùng nhau, hoặc Lead tại `phrase.apex` khi `rise >= 3`. |

Cả ba thỏa `ceil - floor >= 27`, nên `gain == 1`. Courante wide là `63 - 36 = 27`, nên Courante gia nhập bộ khóa đang assert `ceiling - floor == 27` ở thủy triều mở `1.0` trong `test_guitar_wave.py`.

`test_same_bar_differences_follow_one_rounded_center` có dict `windows` và `assert set(windows) == set(PROFILES)`. Thêm ba tuple `(floor_calm, ceil_calm, floor_wide, ceil_wide, smooth)`: Prelude `(28, 56, 34, 62, 5)`, Allemande `(28, 56, 34, 62, 9)`, Courante `(30, 58, 36, 63, 3)`. Chỉ sửa `_EXPECTED` thì assert này vẫn đỏ.

### 4.3. Cửa Intro / Outro (`backend/app/sonify/guitar_frame_bach_sor.py` & [`docs/sonify-guitar-frame-variations.md`](./sonify-guitar-frame-variations.md))

Ba cửa mới nằm trong `DOORS` của `backend/app/sonify/guitar_frame_bach_sor.py` và đi qua `_run(builder, ctx, bar, role, steps=steps, closing=closing, index=index)`. `_extra_doors` trong `guitar_frame.py` đã merge dict đó. Bourrée và Fugue tiếp tục ở `_RETAINED_DOORS`. Không thêm Prelude, Allemande, Courante vào `_RETAINED_DOORS`.

#### Quy tắc gắn cửa, bậc thang lực và thế tay tại biên

- **Pattern kề pedal quyết định cửa**:
  - `intro_pattern` đọc ô thân bài đầu (`leading[-1] + 1`); `outro_pattern` đọc ô thân bài cuối (`trailing[0] - 1`).
  - Ở chương 3 vùng (`A – B – A`) hoặc 4–5 vùng (`A – B – C – A` / `A – B – C – B – A`), vùng cuối tái hiện `primary`, nên intro và outro cùng mở/khép bằng cửa của `primary`.
  - Ở chương 2 vùng (`1Y` tháng mở `4/4`, hoặc `1W` 2 phiên) đi `A – B` không tái hiện: intro mở bằng cửa của `palette[0]` (ví dụ `bach_prelude` hoặc `bach_allemande`), còn outro khép bằng cửa của `palette[1]` (ví dụ `bach_allemande` hoặc `bach_courante`).
  - Khi `bach_prelude` hoặc `bach_courante` chỉ làm khách giữa chương 3 vùng (như `Sarabande — Prelude — Sarabande` hay `Sarabande — Courante — Sarabande`), biên `A | B` ở giữa thân bài không đi qua `render_intro` / `render_outro`; cửa riêng của Prelude và Courante phát khi chúng đứng ở `1D` hoặc ở vùng đầu / vùng cuối của chương dài.
- **Độ dài kịch bản (`steps` và `frame_roles`)**:
  - Mỗi `role` của kịch bản ngắn là **cả một ô**. `1D` có 2 ô cửa, nên `role = 0` rồi `role = 1`.
  - 1 ô: `_compressed` không phải một kịch bản thứ ba. Nó giữ phần `offset < epb // 2` của `role = 0`, và dựng phần đầu của `role = 1` vào nửa sau. Pickup đi vào thân bài phải nằm ở `role = 1`, với `offset >= epb // 2`, để bản 2 ô giữ được nó. Bản 1 ô bỏ nửa sau của `role = 0`.
  - Từ 4 ô trở lên (`1W`, `1M`, `3M`, `1Y`): kịch bản dài (`steps == 4`), kéo giãn qua `frame_roles` (`role in {0, 1, 2, 3}`, ô cuối luôn là `role = 3`).
- **Hòa âm & Kết điệu**:
  - Hợp âm đi qua `_harmony`. `"I"` và `"IV"` đã hạ bậc 3 khi `ctx.mode == "minor"` ở cả `_harmony` lẫn `frame._function`. `_bach_block` và `_bach_arpeggiato` nhận `"I"`, không nhận `"i"`: tên lạ trong `_function` rơi về hợp âm trưởng.
  - **Không dùng Picardy (`I+`)** cho cả `bach_prelude`, `bach_allemande` và `bach_courante` (Picardy của Bach chỉ giữ riêng ở `bach_fuga`).
- **Lưới móc kép & Kiểm tra `study` trên vùng pedal**:
  - Móc kép trong cửa viết bằng offset nửa móc đơn (`at = eighth + 0.5`, `length = 0.5`), khớp với `_bariolage` và `_mordent` trong `guitar_frame_bach_sor.py`. Không viết móc ba mươi hai.
  - `profiles_for` gán ô warmup/intro và outro/cooldown theo `_PEDAL_DOOR_PROFILE` (mặc định `"study"`). Profile `study` giữ trần bass `53 - ctx.semitones` và từ chối cả bass tiếp cận nửa cung (`_is_approach`) lẫn bass lament (`_is_lament`). Mọi spec trả về từ `_prelude_specs`, `_allemande_specs`, `_courante_specs` đều đi qua `_finish(..., allow_lament=False)` để `_fix_bass` và `_drop_crossed` lọc cữ tay và tự sửa mọi bước bass vi phạm trước khi kiểm `assert_playable`.
  - Ô pedal không đi qua `_plant_pickup` của `_smooth_boundaries`; móc đơn/móc kép cuối của bước intro cuối thuộc trọn về cửa để dẫn vào ô thân bài đầu.

---

#### 1. `("bach", "bach_prelude"): bach_prelude` (`_prelude_specs`)

- **Đặc trưng**: Mở và khép bằng một dòng móc kép trên bass ngân nửa ô (`half = _half(ctx.epb)`: `4` ở `4/4`, `3` ở `3/4` và `6/8`). Không có bè giữa trong vòng rải.
- **Helper nội bộ `_prelude_roll(frame, ctx, pcs, start, span, velocity, *, lead_aim=None, eighth_grid=False)`**:
  - Slot 0: chỉ Voice 3, bass ngân hết `span`. Các móc kép sau là Voice 1, một dòng âm hợp âm. Voice 2 không attack trong vòng này.
  - Khi `eighth_grid == False`: lead móc kép, `length = 0.5`. `lead_aim` chỉ đặt trên Voice 1 của nốt lead cuối, một bậc về phía `_approach_pitch`. Không đưa nốt đó xuống Voice 3.
  - Khi `eighth_grid == True`: mỗi eighth một attack Voice 1, dài `1`, sau nốt bass mở đầu. Dừng khi hết nửa ô.
- **Kịch bản 4 chế độ**:
  - **Intro ngắn (`steps == 2, closing == False`)**:
    - `role == 0`: Hai chu kỳ `_prelude_roll` trên `I` (`0..half` và `half..epb`), nửa đầu ở `_PP`, nửa sau lên `_P`.
    - `role == 1`: Cả hai nửa là hợp âm `V7`. Nửa đầu ở `_P`, nửa sau ở `_MP` và có `lead_aim`. Bass là bậc 1 của `I` chỉ khi mọi nốt `V7` đang kêu cùng bass đó vẫn qua `_playable_line`. Không thì bass là gốc của `V`. Nốt dẫn của `V7` không đặt sát bass.
  - **Intro dài (`steps == 4, closing == False`)**:
    - `role == 0`: `_prelude_roll` hai nửa ô trên `I` ở `_PP` → `_P`.
    - `role == 1`: `_prelude_roll` hai nửa ô trên `IV` ở `_P`. Bass giữ bậc 1 chỉ khi chồng với `IV` vẫn `_playable_line`; không thì bass là gốc của `IV`.
    - `role == 2`: `_prelude_roll` hai nửa ô trên `V7` ở `_MP`, cùng luật bass với intro ngắn `role == 1`.
    - `role == 3`: Cả ô ở trên `V7`. Nửa đầu `_MP`. Nửa sau velocity viết `58`, trong bậc `56..60` của bước intro cuối ở tài liệu cửa. `lead_aim` hướng vào ô thân bài. Không giải về `I` trong ô này: thân bài tự mở hợp âm của nó. `apply_guitar_wave` cộng `round(C) - 64` sau đó.
  - **Outro ngắn (`steps == 2, closing == True`)**:
    - `role == 0`: Nửa đầu `_prelude_roll` móc kép trên `V7` ở `_MP`; nửa sau chuyển sang `eighth_grid = True` (rải móc đơn giãn nhịp trên `V7`) ở `_P`.
    - `role == 1`: `frame._bach_block(ctx, bar, "I", frame._P)` — hợp âm `I` ba bè ngân trọn ô (thứ giữ `i`).
  - **Outro dài (`steps == 4, closing == True`)**:
    - `role == 0`: `_prelude_roll` móc kép hai nửa ô trên `IV` (hoặc `iv`) ở `_MP`, đón dòng móc kép từ ô thân bài cuối.
    - `role == 1`: Nửa đầu `_prelude_roll` móc kép trên `V7` ở `_P`, nửa sau giãn sang `eighth_grid = True` trên `V7` ở `_P`.
    - `role == 2`: `frame._bach_arpeggiato(ctx, bar, "I", frame._P)` — rải chậm từ trầm lên cao trên `I`.
    - `role == 3`: `frame._bach_block(ctx, bar, "I", frame._PP)` — hợp âm chủ ngân tĩnh ở `_PP`.

---

#### 2. `("bach", "bach_allemande"): bach_allemande` (`_allemande_specs`)

- **Đặc trưng**: Mở bằng chùm móc kép lấy đà (*anacrusis*) rồi đan *style brisé* legato (Bass ở đầu nửa ô, Support vào trễ 1 móc đơn và ngân chồng, hoàn toàn không có `staccato`); khép bằng *style brisé* nửa kết, treo `4–3` (*suspension*) và hợp âm chủ trầm ấm.
- **Helper nội bộ `_brise_cell(frame, ctx, bar, pcs, start, span, velocity, *, pickup_into=False)`**:
  - Lấy `(bass, inner, lead) = _stack_pitches(frame, ctx, pcs)`; tìm âm quãng 3 hoặc 6 dưới `lead` qua `_under_lead(frame, ctx, lead, bass, None)`.
  - Voice 3 (`bass`): đánh tại `start`, `length = max(1, span - (2 if pickup_into else 0))`, `velocity`, `flags = {}` (không `staccato`).
  - Voice 1 (`lead`): đánh tại `start`, `length = max(1, span - (2 if pickup_into else 0))`, `velocity`.
  - Voice 2 vào tại `start + 1`. Trường độ là `min(2, span - 1 - (2 if pickup_into else 0))`. Nếu trường độ đó `<= 0`, bỏ Support. Nửa ô `3/4` và `6/8` dài 3 eighth và pickup chiếm 2 eighth cuối, nên nửa ô đó không còn chỗ cho Support.
  - Khi `pickup_into == True` và `span >= 3`: hai eighth cuối (`tail = start + span - 2`) là 4 móc kép của Voice 1, mỗi nốt `length = 0.5`. Cửa tự viết 4 offset đó. `_scaled` và `_scale_into` trả về nốt móc đơn `length = 1`, không phải 4 móc kép. Cao độ là 4 bước liền bậc hướng tới giai điệu ô sau, nốt cuối dừng trước đích một bậc, và 4 nốt liền nhau qua `_position_ok`. Bass và Support kết thúc đúng tại `tail`.
  - Bass không bước xuống 1 hoặc 2 nửa cung sau một nốt bass dài từ 2 eighth. `_finish(..., allow_lament=False)` gặp bước đó thì gọi `_retime_bass`, và hình đi bộ đã viết không còn. Bước bass của cửa đi lên, hoặc nhảy từ quãng 3.
- **Kịch bản 4 chế độ**:
  - **Intro ngắn (`steps == 2, closing == False`)**:
    - `role == 0`: Nửa đầu (`0..half`) `_brise_cell` trên `I` ở `_P` (`pickup_into = False`); nửa sau (`half..epb`) `_brise_cell` trên `I` ở `_P` có `pickup_into = True` (4 móc kép cuối ô dẫn sang bước 1).
    - `role == 1`: Nửa đầu (`0..half`) `_brise_cell` trên `IV` ở `_P`; nửa sau (`half..epb`) `_brise_cell` trên `V7` ở `_MP` có `pickup_into = True` (4 móc kép lấy đà cuối ô dẫn thẳng vào phách 1 của thân bài).
  - **Intro dài (`steps == 4, closing == False`)**:
    - `role == 0`: Nửa đầu chỉ Bass `I` ngân ở `_PP`, nửa sau 4 móc kép pickup của Voice 1 ở `_P` dẫn vào hợp âm `I` của bước 1.
    - `role == 1`: Nửa đầu `_brise_cell` trên `I` ở `_P`. Nửa sau `_brise_cell` trên `IV` ở `_P`. Bass nửa sau không bước xuống 1–2 nửa cung từ bass nửa đầu.
    - `role == 2`: Nửa đầu `_brise_cell` trên `V7` ở `_MP`. Mordent bắt đầu tại `half`, không tại eighth `0`, nếu không nó đè nửa đầu. Gọi `_mordent(..., eighth=half, sustain_to=epb)`.
    - `role == 3`: Nửa đầu `_brise_cell` trên `I` ở `_MP`; nửa sau `_brise_cell` trên `V7` ở `_MP` với `pickup_into = True` (4 móc kép cuối ô trao đà cho ô thân bài đầu).
  - **Outro ngắn (`steps == 2, closing == True`)**:
    - `role == 0`: Hai nửa ô `_brise_cell` nửa kết `IV -> V7` ở `_MP` (`pickup_into = False`, giữ lưới móc đơn legato).
    - `role == 1`: `frame._bach_block(ctx, bar, "I", frame._P)` — hợp âm `I` ngân đầy (thứ giữ `i`).
  - **Outro dài (`steps == 4, closing == True`)**:
    - `role == 0`: Hai nửa ô `_brise_cell` trên `IV` rồi `I` ở `_P`.
    - `role == 1`: Nửa đầu `_brise_cell` trên `V7` ở `_MP`, nửa sau `_mordent` trên `V7` ở `_MP`.
    - `role == 2`: `_suspension(frame, ctx, bar, frame._P)` — Bass giữ chủ âm `I`, Lead treo bậc 4 giải xuống bậc 3 kèm Support quãng 3/6 bên dưới ở `_P`.
    - `role == 3`: `frame._bach_block(ctx, bar, "I", frame._PP)` — hợp âm chủ ngân êm ở `_PP`.

---

#### 3. `("bach", "bach_courante"): bach_courante` (`_courante_specs`)

- **Đặc trưng**: Cửa mang đúng 3 dấu ấn của *Courante BWV 1007*: cú nhảy mở ô (`eighth 0` `accent=True` rồi `eighth 1` `staccato=True`), chùm 4 móc kép *tirata* theo meter, và hemiola ở bước áp cuối của outro khi meter là `3/4` hoặc `6/8`. `4/4` khép bằng tirata trên `V7`, rồi hợp âm chủ.
- **Ba helper nội bộ theo đúng meter (`ctx.kind`)**:
  - **`_courante_leap_cell(frame, ctx, pcs, velocity)`** (phách mở ô, `eighth 0..1` ở `3/4` & `4/4`, `eighth 0..2` ở `6/8`):
    - Lấy `(bass, inner, lead) = _stack_pitches(frame, ctx, pcs)`. Tìm nốt nhảy `leap_lead` cao hơn `lead` một quãng 3 thuận thang qua `frame._step` (hoặc giữ `lead` ở `eighth 1` và đặt `low_lead` thấp hơn một quãng 3 ở `eighth 0` sao cho `bass < low_lead < leap_lead` và `_playable_line`).
    - `eighth 0`: Voice 3 (`bass`, `length = 3` khi `6/8`, `2` khi `3/4` hoặc `4/4`, `velocity`, `{"accent": True}`); Voice 1 (`low_lead`, `length = 1`, `velocity`, `{"accent": True}`).
    - `eighth 1`: Voice 1 bật lên `leap_lead` (`length = 1`, `velocity`, `{"staccato": True}`); Voice 2 điểm `inner` (`length = 1`, `velocity`).
    - Riêng ở `6/8` (`epb == 6`), `eighth 2` giữ `leap_lead` (`length = 1`) và Support điểm nhẹ để trọn phách chấm đầu (`0..2`).
  - **`_courante_tirata_cell(frame, ctx, bar, pcs, velocity, *, into_body=False)`** (phách giữa + lấy đà cuối ô):
    - Vị trí chùm 4 móc kép (`tirata_at`, dài `2` eighths = 4 móc kép `length = 0.5`):
      - `3/4`: `tirata_at = 2` (`eighth 2, 3`), Bass đánh bậc 5 ở `eighth 2` (`length = 2`); `eighth 4` Lead `staccato=True` kèm Support, `eighth 5` Lead và Bass đánh móc đơn lấy đà (`into_body` thì hướng về `_approach_pitch`).
      - `6/8`: `tirata_at = 3` (`eighth 3, 4`), Bass đánh bậc 5 ở `eighth 3` (`length = 2`, `{"accent": True}`); `eighth 5` Lead và Bass đánh móc đơn lấy đà.
      - `4/4`: `eighth 2, 3` Lead giữ nốt (`length = 2`), Bass ở `2`, Support ở `3`; `tirata_at = 4` (`eighth 4, 5`), Bass bậc 5 ở `4` (`length = 2`); `eighth 6` Lead `staccato=True`, `eighth 7` Lead và Bass lấy đà.
    - Chùm 4 móc kép ở `tirata_at` là bước liền bậc trong âm vực Lead, qua `_position_ok`. Helper này không viết eighth mà `_courante_leap_cell` đã giữ. Trên `6/8`, leap giữ bass suốt eighth `0..2`; tirata bắt đầu tại eighth `3`.
  - **`_courante_hemiola_bar(frame, ctx, pcs, velocity)`** chỉ cho `3/4` và `6/8`. Một lần gọi là một hợp âm `pcs`. `4/4` không có hemiola, kể cả trong cửa: thân bài `4/4` đã chốt điều đó, và nhóm `3+3+2` là nhịp của Villa.
    - `3/4`: accent tại eighth `0` (`length = 3`, hết đúng lúc eighth `3`) và eighth `3` (`length = 2`). Eighth `5` là móc đơn lấy đà. Hai nốt bass chạm nhau, không phủ nhau.
    - `6/8`: bỏ tirata. Accent tại eighth `0` và `2`, mỗi nốt `length = 2`. Accent tại eighth `4` chỉ dài `1`. Eighth `5` là móc đơn lấy đà. Ba accent `length = 2` sẽ phủ kín ô và nuốt eighth `5`.
- **Kịch bản 4 chế độ**:
  - **Intro ngắn (`steps == 2, closing == False`)**:
    - `role == 0`: `_courante_leap_cell` trên `I` ở `_P`. Phần ô sau khi bass của cú nhảy hết (`eighth 2` trên `3/4` và `4/4`, `eighth 3` trên `6/8`) giữ nốt móc đơn trên `I`. Không gọi tirata ở role này.
    - `role == 1`: `_courante_leap_cell` + `_courante_tirata_cell(..., into_body=True)` trên `V7` ở `_MP`, tuôn 4 móc kép ở phách giữa và móc đơn lấy đà cuối ô vào thân bài.
  - **Intro dài (`steps == 4, closing == False`)**:
    - `role == 0`: `_courante_leap_cell` trên `I` ở `_P`, phần còn lại của ô giữ nốt ngân nhẹ trên `I` (`_P`).
    - `role == 1`: `_courante_leap_cell` + `_courante_tirata_cell` trên `IV` (hoặc `iv`) ở `_P`.
    - `role == 2`: `_courante_leap_cell` + `_courante_tirata_cell` trên `V7` ở `_MP`.
    - `role == 3`: Trên `V7`, cú nhảy ở `_MP`, tirata và lấy đà `into_body=True` ở velocity viết `58` (bậc `56..60` của bước intro cuối).
  - **Outro ngắn (`steps == 2, closing == True`)**:
    - `role == 0`: `3/4` và `6/8` dùng `_courante_hemiola_bar` trên `V7` ở `_MP`. `4/4` dùng cú nhảy cộng tirata trên `V7` ở `_MP`, không hemiola.
    - `role == 1`: `_chord` trên `I` suốt ô, phách 1 có `accent`, velocity `_P`. `_function("I")` giữ hợp âm thứ khi điệu thứ.
  - **Outro dài (`steps == 4, closing == True`)**:
    - `role == 0`: cú nhảy cộng tirata trên `IV` ở `_MP`.
    - `role == 1`: cú nhảy cộng tirata trên `V7` ở `_MP`.
    - `role == 2`: `3/4` và `6/8` là hemiola trên `V7` ở `_P`. `4/4` lặp tirata trên `V7` ở `_P`. Một ô, một hợp âm.
    - `role == 3`: `frame._bach_block(ctx, bar, "I", frame._P)`.

### 4.4. Scale Engine (`backend/app/sonify/guitar_scale_passages.py`)

`bach_group2_window` và `bach_group2_intrinsic_eighths` hiện trả `None` khi pattern không thuộc `{bach_gigue, bach_chaconne, bach_sarabande}`. Thêm Courante vào frozenset `_BACH_GROUP2` mà không sửa hai hàm đó thì Courante không có cửa sổ nội tại.

- **`bach_courante` thuộc Nhóm 2**. `bach_group2_window` phân theo `ctx.kind`, không theo `epb`, vì `3/4` và `6/8` cùng `epb == 6` mà tirata không đứng cùng eighth. Cửa sổ inclusive:
  - `3/4`: `(bar * epb + 2, bar * epb + 3)`.
  - `6/8`: `(bar * epb + 3, bar * epb + 4)`.
  - `4/4`: `(bar * epb + 4, bar * epb + 5)`.
  - Ô không `phrase.closes` viết tirata sẵn, nên các eighth đó là intrinsic. Ô `phrase.closes` ở `6/8` bỏ tirata, intrinsic của ô đó là rỗng. Eighth `0` và `1` luôn ngoài cửa sổ, nên biến động nhỏ không đè cú nhảy mở ô.
  - Sóng lớn (`L >= epb` và `net_span >= 6`) chỉ mở sau một ô Courante trọn của vùng, cùng luật *establish pattern first*.
  - Bass dưới passage: eighth `0` vẫn là gốc hợp âm, `accent=True`. Ô `phrase.closes` ở `3/4` vẫn có Bass ở eighth `3`. Ô `phrase.closes` ở `6/8` giữ Bass ở eighth `0`, `2` và `4`. Không thay bằng Bass gốc/bậc 5 chung của Nhóm 3.
- **`bach_allemande` không vào `_BACH_GROUP2`**. Allemande là Nhóm 3, nên nhận scale sub-bar và multi-bar. Hairpin nằm trong `_HAT_PATTERNS`, cửa `52..82`. Bass dưới passage giữ offset Mục 2.2, không staccato, đi bộ khi Lead ngân. Không rút Bass thành nốt ngắn trên `ctx.strong`.
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

- `_FAMILY` và `_PROFILE` trong `backend/app/sonify/guitar_patterns.py`. Cả ba id map tới `"bach"`. Thiếu `_PROFILE` thì `profiles_for` kiểm thân bài bằng `study`.
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
   - `test_bach_courante_leaps_on_beat_one_and_runs_sixteenths_on_the_middle_beat`: `accent` ở eighth `0`, `staccato` ở eighth `1`, lấy đà cuối ô. Tirata ở eighth `2, 3` khi `3/4`, eighth `3, 4` khi `6/8`, eighth `4, 5` khi `4/4`. Hemiola `phrase.closes`: `3/4` thêm Bass eighth `3` và bỏ Bass eighth `2`; `6/8` bỏ tirata và nhấn eighth `0`, `2`, `4`.
   - `test_bach_1d_stays_one_pattern_and_longer_spans_walk_suite_rows`: `1D` có khung một pattern suốt 30 ô thân bài. `1W` một phiên một pattern. `1W` từ 2 phiên, `1M`, `3M`, `1Y` đi đúng hàng Mục 3.3. Chương 3 vùng không chơi `palette[2]`.
   - Scherzo `6/8` calm có khung mở Courante và khách Gigue.
   - `test_bach_prelude_allemande_courante_doors_frame_short_and_long_pedals`: kiểm tra `render_intro` và `render_outro` cho `bach_prelude`, `bach_allemande`, `bach_courante` ở cả kịch bản ngắn (`2` ô) và dài (`4` ô) trên `4/4`, `3/4`, `6/8`; chương 2 vùng (`A – B`) mở bằng cửa `palette[0]` và khép bằng cửa `palette[1]`; mọi ô pedal vượt qua `assert_playable(..., "study")` và không dùng Picardy ở điệu thứ.
   - Giữ nguyên nửa không khung của `test_bach_trio_answers_the_bourree_with_the_fugue`. Ô 12 của finale rally có khung vẫn Bourrée, không móc kép. Assert `divisions` của finale theo Mục 4.1.
2. **`backend/tests/test_program.py` và `src/sonify/program.test.ts`**:
   - `pattern_title` của Prelude, Allemande, Courante.
   - Tên `Prelude — Allemande — Prelude`, `Allemande — Courante — Allemande`, `Gigue — Courante — Gigue`, `Bourree — Fugue — Bourree`.
   - `test_bach_slow_selloff_with_a_contrast_stays_sarabande` vẫn `Sarabande — Chaconne — Sarabande` khi `framed=False`.
3. **`backend/tests/test_guitar_wave.py`**:
   - Tập `PROFILES` đủ 31 khóa, comment “28 dòng” sửa theo, và dict `windows` trong `test_same_bar_differences_follow_one_rounded_center` thêm ba tuple Mục 4.2. Courante nằm trong bộ khóa `ceiling - floor == 27`. Bất biến `gain == 1` vẫn đúng.
