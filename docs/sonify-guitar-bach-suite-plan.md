# Kế Hoạch Mở Rộng Tổ Khúc Baroque Của J.S. Bach: Prelude, Allemande & Courante (BWV 1007)

> **Tài liệu liên kết**: [`docs/sonify-guitar-bach-plan.md`](./sonify-guitar-bach-plan.md), [`docs/sonify-classical-guitar.md`](./sonify-classical-guitar.md), [`docs/sonify-guitar-frame-variations.md`](./sonify-guitar-frame-variations.md), [`docs/sonify-guitar-dynamics-wave-plan.md`](./sonify-guitar-dynamics-wave-plan.md), [`docs/sonify-guitar-scales-plan.md`](./sonify-guitar-scales-plan.md)
> **Mục tiêu**:
> 1. Bổ sung **3 pattern cốt lõi còn thiếu** của một Tổ khúc Bach chuẩn mực: **`bach_prelude`** (*Prelude*), **`bach_allemande`** (*Allemande*), và **`bach_courante`** (*Courante* kiểu *BWV 1007*), nâng tổng số pattern của Bach từ 6 lên **9 pattern**.
> 2. Thiết kế lại bộ lập lịch của Bach trên toàn bộ các quãng thời gian (`1D`, `1W`, `1M`, `3M`, `1Y`) sao cho:
>    - **9 pattern được phân bố đều**, mỗi pattern đều có vị trí xuất hiện tự nhiên trong thực tế, không pattern nào bị chìm hoặc độc chiếm.
>    - **`1D` (34 ô, 4/4, 96 BPM)**: Giữ nguyên nguyên tắc **Monothematic (1 pattern chủ đạo duy nhất xuyên suốt 100% thân bài)** để tiểu phẩm ~1.5 phút liền mạch, không bị vụn.
>    - **`1W`, `1M`, `3M`, `1Y` (các bản dài từ 2 vùng / nhiều chương)**: Cho phép **phối hợp nhiều pattern hợp lý ngay trong cùng một chương** theo đúng cấu trúc **Tổ khúc Baroque (*Bach Suite Row*)** (ví dụ: *Prelude — Allemande — Prelude*, *Prelude — Fugue — Prelude*, *Allemande — Courante — Allemande*, *Courante — Sarabande — Courante*, *Gigue — Courante — Gigue*).

---

## 1. Chẩn Đoán: Vì Sao Cách Bố Trí Hiện Tại Của Bach Bị Lệch Và Đơn Điệu?

Trong `backend/app/sonify/guitar_bach.py` và `backend/app/sonify/guitar_patterns.py`, cách chọn pattern hiện tại của Bach có 3 hạn chế lớn:

1. **Thiếu 3 mắt xích mở đầu của Tổ khúc Baroque chuẩn (*Prelude – Allemande – Courante*)**:
   - Một Lute Suite (*BWV 995–1000*) hay Cello Suite (*BWV 1007–1012*) của Bach luôn mở đầu bằng **Prelude**, đi vào **Allemande** (nhịp `4/4` đa âm đan xen *style brisé*), rồi sang **Courante** (nhịp `3/4` hoặc dịch nhịp linh hoạt có bước nhảy quãng rộng và chùm móc kép lướt như *BWV 1007*) trước khi lắng xuống *Sarabande*, điểm các *Galanteries* (*Gavotte*, *Bourrée*) và khép bằng *Gigue* / *Chaconne*.
   - Vì thiếu 3 pattern này, mọi chương `4/4` ở `calm` hoặc `rally` của Bach đều rơi vào `bach_gavotte` hoặc `bach_bourree` (hai điệu nhảy ngắn có `staccato` ở phách 2), làm mất đi vẻ trầm mặc liên hoàn của *Prelude* và chất đối vị mềm mại của *Allemande*.
2. **Các bản dài (`1M` chương I & IV, `3M` chương I & III, `1Y` tháng mở & kết, `1W`) chưa phối được các pattern trong cùng một chương**:
   - Trong `span.py`, chỉ có chương chậm (`1M` II, `3M` II, `1Y` giữa — có `bridge=True`) và chương Scherzo (`1M` III, `1Y` khép — có `trio=True`) mới bật cờ `_has_contrast_section(ctx) == True`.
   - Các chương lớn nhịp `4/4` như **`1M` Chương I** (3 vùng `slot 0, 1, 2`), **`1M` Chương IV** (3 vùng), **`3M` Chương I** (3 vùng), **`3M` Chương III** (3 vùng), **`1Y` Tháng mở** (2 vùng `slot 0, 1`) và **`1Y` Tháng 12** (3 vùng) đều có `bridge = False, trio = False` chovariant `guitar`.
   - Trong `_assign_macro` (`guitar_patterns.py` dòng 1207–1219), khi `_has_contrast_section(ctx) == False`, chỉ riêng Barrios mới có `_barrios_palette` để đi qua chuỗi pattern (`Prelude — Andante — Prelude`), còn **Bach gọi lặp lại `_dominant_pattern` trên từng `slot` với cùng một `ctx.character` của cả chương**. Hệ quả là cả một chương Sonata dài 4–8 phút của Bach chỉ đánh độc **1 pattern duy nhất từ đầu đến cuối** (ví dụ: 192 ô `bach_bourree` liên tục ở `3M` Chương I), và tên chương chỉ hiện `Bourree` thay vì một cấu trúc tổ khúc có mở – giữa – tái hiện.
3. **Phân bố tần suất bị lệch nặng về 4 pattern**:
   - Mọi chương `3/4` hoặc `bpm <= 72` đều bị gom vào `bach_sarabande` (trừ trường hợp hẹp `selloff` không có contrast).
   - Mọi chương `6/8` ở `rally` và `calm` đều chỉ ra `bach_gigue`.
   - `bach_gavotte` và `bach_bourree` gánh toàn bộ nhịp `4/4` `calm` và `rally`.

---

## 2. Thiết Kế Âm Nhạc & Kỹ Thuật Cho 3 Pattern Mới

### 2.1. `bach_prelude` — *Prélude Harpeggiato / Moto Perpetuo* (*BWV 998 / BWV 999 / BWV 1007*)

- **Thẩm mỹ & Kết cấu**:
  - Dòng chảy móc kép liên hoàn (*moto perpetuo*) cuộn sóng qua cả 3 tầng dây (Trầm `p` – Trung `i, m` – Cao `a`).
  - Nốt Bass mở đầu mỗi chu kỳ nửa ô nhịp và ngân dài làm bàn đạp hòa âm (*pedal/basso continuo*), trong khi bè Trung và bè Cao đan xen móc kép sao cho mỗi móc kép trong ô đều có đúng 1 tiếng đàn vang lên, và nốt giai điệu giá luôn nằm ở đỉnh vòm rải.
- **Lưới tiết tấu trong `_render_bach_prelude_bar(ctx, bar, apex, phrase)` (`divisions = 4`)**:
  - **Nhịp `4/4` (`epb = 8`, 16 móc kép)**: Chia làm 2 chu kỳ 8 móc kép (`origin16 = 0` và `origin16 = 8`):
    - `slot 0`: **Voice 3 (`low`)** đánh nốt Bass (`_bach_bass`, bậc `0` ở đầu ô, bậc `2` hoặc bậc `1` ở nửa sau ô) ngân suốt 8 móc kép (`duration_beats = 2.0`); đồng thời **Voice 1 (`lead`)** chạm nhẹ hoặc giữ nốt giai điệu giá `_melody_at(ctx, eighth)`.
    - `slot 1, 2`: **Voice 2 (`support`)** leo từ `low_mid` lên `upper_mid` (2 âm hợp âm trong `[ctx.mid_low, ctx.mid_high]` thỏa `_playable` với Bass và Lead).
    - `slot 3`: **Voice 1 (`lead`)** gảy nốt giai điệu giá `_melody_at(ctx, eighth + 1)` (hoặc nốt đỉnh của nửa ô), ngân qua `slot 3..4` (`duration_beats = 0.5`) hoặc đánh móc kép.
    - `slot 4, 5`: **Voice 2 (`support`)** quay lại `low_mid -> upper_mid`.
    - `slot 6`: **Voice 1 (`lead`)** hát nốt giai điệu giá `_melody_at(ctx, eighth + 3)`.
    - `slot 7`: **Voice 2 (`support`)** khép vòm bằng `upper_mid` (hoặc `low_mid`), nối mượt sang chu kỳ kế tiếp.
  - **Nhịp `3/4` và `6/8` (`epb = 6`, 12 móc kép)**: Chia làm 2 chu kỳ 6 móc kép (`0..5` và `6..11`):
    - `slot 0`: Voice 3 (`low`) ngân 6 móc kép (`1.5` phách).
    - `slot 1, 2`: Voice 2 (`low_mid -> upper_mid`).
    - `slot 3`: Voice 1 (`lead` hát nốt giá).
    - `slot 4`: Voice 2 (`low_mid`).
    - `slot 5`: Voice 1 (`lead`) hoặc Voice 2 (`upper_mid`) dẫn sang nửa sau.
- **Quy tắc thế tay**: Mọi tổ hợp `(bass, inner, lead)` tại từng móc kép đều lọc qua `_playable` và giữ nghiêm ngặt `bass < low_mid <= upper_mid < lead`.

### 2.2. `bach_allemande` — *Style Brisé & Sixteenth Anacrusis* (*Allemande BWV 996 / BWV 995*)

- **Thẩm mỹ & Kết cấu**:
  - Vũ điệu mở đầu Suite ở nhịp `4/4` khoan thai, trầm ấm và giàu chất đối vị ngầm (*style brisé* — các bè chuyền tay nhau liên tục, hoàn toàn **legato**, không đánh `staccato` nảy như *Bourrée* hay *Gavotte*).
  - Hai dấu hiệu nhận diện đặc trưng:
    1. **的对 vị bù nhịp (*Complementary Counterpoint*)**: Khi bè Cao ngân nốt trắng/nốt đen, bè Trầm và bè Trung bước liền bậc tạo dòng chảy; khi bè Cao đi móc đơn, bè Trầm giữ nốt trụ dài và bè Trung điểm lệch phách (*broken style*).
    2. **Chùm móc kép lấy đà cuối ô (*Allemande Sixteenth Pickup*)**: Ở phách cuối của ô mở câu hoặc ô chuẩn bị chuyển hợp âm/đổi câu, bè Cao vuốt một chùm **2–4 móc kép liền bậc (`_fitting_scale`)** dẫn mềm mại vào phách 1 của ô kế tiếp.
- **Lưới tiết tấu trong `_render_bach_allemande_bar(ctx, bar, apex, phrase)`**:
  - **Voice 1 (`lead`)**:
    - Hát đường giá trên lưới móc đơn (`_sustain`), giữ nguyên độ ngân tự nhiên.
    - Khi ô nhịp là ô mở đầu (`bar == 0`), hoặc hợp âm/phrase sắp đổi ở `bar + 1` (`_allemande_passes(ctx, bar, start, epb)`): phách cuối của ô (`last_two_eighths = epb - 2`) chạy 4 móc kép liền bậc (`_fitting_scale`) tiến vào nốt đầu của `bar + 1`.
  - **Voice 3 (`low`)**:
    - Đặt gốc hợp âm tại phách 1 (`offset 0`) và bậc 5/bậc 3 tại phách 3 (`offset 4` ở `4/4`, `offset 3` ở `6/8`, `offset 4` ở `3/4`), **không gắn `staccato`**.
    - Nếu Soprano đang ngân dài tại phách 1 hoặc phách 3 (`_hold_at(lead, ...) >= 2`), Bass tách nửa sau phách đó thành bước đi bộ liền bậc (`_walk` hướng về mục tiêu kế tiếp).
  - **Voice 2 (`support` — *Style brisé*)**:
    - Thay vì chập trùng phách mạnh với Bass như hợp âm khối, Voice 2 vào ở **móc đơn thứ hai sau Bass** (`offset 1` và `offset 5` ở `4/4`; `offset 1` và `offset 4` ở `3/4` & `6/8`), chọn quãng 3 hoặc quãng 6 thuận thang (`_parallel` rồi fallback `_choose_inner`) và ngân 2 móc đơn (`1.0` phách) tạo hiệu ứng âm thanh đan chồng ấm áp.

### 2.3. `bach_courante` — *Compound Leap, Running Sixteenths & Hemiola* (*Courante BWV 1007*)

- **Thẩm mỹ & Kết cấu**:
  - Lấy nguyên mẫu từ **Courante — Cello Suite No. 1 in G major, BWV 1007**: nhịp ba linh hoạt, hào sảng và giàu động năng, đối lập hoàn toàn với vẻ trang nghiêm tĩnh tại của *Sarabande*.
  - Ba dấu ấn nhận diện từ tổng phổ *BWV 1007*:
    1. **Cú nhảy quãng mở ô (*The BWV 1007 Opening Leap*)**: Phách 1 mở bằng nốt Bass gốc có trọng âm (`accent=True`) rồi bật nhảy lên nốt giai điệu ở móc đơn thứ hai với `staccato=True` (như mô-típ `G2 -> G3 (staccato)` mở đầu *Courante BWV 1007*).
    2. **Chùm 4 móc kép lướt ở phách giữa (*Running Sixteenth Tirata*)**: Phách 2 (ở `3/4` và `6/8`) hoặc phách 3 (ở `4/4`) tuôn một chùm **4 móc kép liền bậc (`_scale_cell` / `_fitting_scale`)** kết nối mượt giữa hai mốc giá.
    3. **Nhịp lấy đà cuối ô & Đảo phách *Hemiola***: Phách cuối ô nhịp (`eighth 4, 5` ở `3/4` & `6/8`; `eighth 6, 7` ở `4/4`) đánh hai móc đơn (nốt áp cuối `staccato`) lấy đà nhảy vào phách 1 ô kế tiếp; riêng ở ô cuối phrase trước khi đổi hợp âm, Bass nhấn đảo phách `0` và `3` (*hemiola* `6/8` đè lên `3/4`).
- **Lưới tiết tấu trong `_render_bach_courante_bar(ctx, bar, apex, phrase)` (`divisions = 4`)**:
  - **Trên nhịp `3/4` và `6/8` (`epb = 6`, 12 móc kép)**:
    - *Phách 1 (`eighth 0, 1`)*:
      - `eighth 0`: Voice 3 (`low`) đánh gốc hợp âm (`duration = 2` eighths, `accent=True`); Voice 1 (`lead`) chạm nốt giá mở ô (`duration = 1` eighth, `accent=True`).
      - `eighth 1`: Voice 1 (`lead`) bật lên nốt giá `_melody_at(ctx, start + 1)` (nếu trùng `eighth 0` thì bước lên 1 quãng 3 thuận thang qua `_treble_step(ctx, sung, 2)`) với `staccato=True`; Voice 2 (`support`) điểm âm hợp âm ở giữa.
    - *Phách 2 (`eighth 2, 3` — móc kép `4, 5, 6, 7`)*:
      - Voice 1 (`lead`) chạy **4 móc kép liền bậc (`_fitting_scale(ctx, 4, target_beat3, 4)`)** hướng tới cao độ của phách 3.
      - Voice 3 (`low`) đánh nốt Bass bậc 5 hoặc bước liền bậc tại `eighth 2` (`duration = 2` eighths; nếu ô đang ở cuối câu đóng `phrase.closes`, Bass chuyển sang đánh ở `eighth 3` tạo nhịp *hemiola* `0 - 3`).
    - *Phách 3 (`eighth 4, 5`)*:
      - Voice 1 (`lead`) đánh 2 móc đơn tại `eighth 4` và `eighth 5` (với `eighth 4` có `staccato=True` và `eighth 5` là nốt lấy đà vào `bar + 1`); Voice 2 (`support`) đỡ quãng 3/6 dưới `eighth 4`; Voice 3 (`low`) gảy móc đơn lấy đà tại `eighth 5`.
  - **Trên nhịp `4/4` (`epb = 8`, 16 móc kép)**:
    - *Phách 1 (`eighth 0, 1`)*: Cú nhảy mở ô *Courante Leap* (`eighth 0` nhấn `accent`, `eighth 1` bật quãng 3 `staccato=True` kèm `support`).
    - *Phách 2 (`eighth 2, 3`)*: Voice 1 giữ nốt giá phách 2 (`duration = 2` eighths), Voice 3 bước Bass liền bậc ở `eighth 2`, Voice 2 điểm ở `eighth 3`.
    - *Phách 3 (`eighth 4, 5` — móc kép `8, 9, 10, 11`)*: Voice 1 chạy **4 móc kép liền bậc (`_fitting_scale`)** trên nền Bass bậc 5 tại `eighth 4`.
    - *Phách 4 (`eighth 6, 7`)*: 2 móc đơn lấy đà (`eighth 6` `staccato=True`, `eighth 7` anacrusis cùng Bass và Support) đẩy vào đầu ô kế tiếp.

---

## 3. Quy Hoạch Phân Bố Đều 9 Pattern & Phối Hợp Hợp Lý Theo Quãng Thời Gian (`1D`, `1W`, `1M`, `3M`, `1Y`)

### 3.1. Nguyên tắc kiến trúc
1. **Bản `1D` (34 ô, `4/4`, `96 BPM`) — Giữ 1 Pattern duy nhất cho cả thân bài**:
   - Tiểu phẩm `1D` dài ~1.5 phút chỉ có 30 ô thân bài. Giữ đúng triết lý *"One-Pattern Flow"*: chọn **1 pattern duy nhất** phù hợp nhất với `mood`, biên độ (`rel_span`) và độ hoạt động của giai điệu (`_melody_activity` / `_has_hold`) trong ngày hôm đó.
2. **Các bản dài (`1W` $\ge 2$ phiên, `1M`, `3M`, `1Y`) — Phối hợp theo Tổ khúc (*Bach Suite Row & Contrast*)**:
   - Ngoại trừ `1D` (và `1W` chỉ có đúng 1 phiên 32 ô), mọi chương dài của Bach (`ctx.bars > 40`) đều có từ **2 đến 5 vùng cấu trúc (`regions`)** (theo `regime_slot` hoặc `trio`/`bridge`).
   - Thay vì lặp lại một pattern cho mọi `regime_slot` khi không có cờ `trio`/`bridge`, Bach sử dụng **Hàng Tổ Khúc (`_bach_palette` + `_bach_region_patterns`)** cho các chương đa vùng và **Cặp Đối Đáp (`_bach_contrast`)** cho các chương `A – B – A`, đảm bảo mỗi chương trong `1W`, `1M`, `3M`, `1Y` là một sự kết hợp hài hòa giữa 2–3 pattern tương phản về mật độ và tiết tấu.

---

### 3.2. Phân bổ chi tiết trên bản `1D` (1 Pattern duy nhất xuyên suốt thân bài)

Trên bản `1D` (`4/4`, `96 BPM`, `bars == 34`), để các pattern của Bach được phân bố đều theo diễn biến thực tế của phiên giao dịch:

| Trạng thái phiên (`mood`) | Điều kiện chi tiết trên dữ liệu phiên | Pattern được khóa cho cả bản `1D` | Lý do âm nhạc |
|---|---|---|---|
| **`calm`** (Đi ngang / Tích lũy) | Giai điệu nhiều nốt ngân (`holds >= 30%` số câu) **hoặc** biên độ rất hẹp (`rel_span < 0.008`) | **`bach_prelude`** (*Prelude*) | Giá tĩnh tại nhường không gian cho sóng arpeggio 16 móc kép *harpeggiato* chảy êm ả dưới nốt ngân. |
| **`calm`** (Đi ngang / Nhịp nhàng) | Giai điệu di chuyển đều đặn (`holds < 30%` và `rel_span >= 0.008`) | **`bach_allemande`** (*Allemande*) | Đường giá đi bộ khoan thai khớp với kết cấu đa âm đan xen *style brisé* và nhịp lấy đà mềm mại. |
| **`rally`** (Tăng giá vừa phải) | Biên độ tăng vừa (`rel_span < 0.014`) | **`bach_bourree`** (*Bourree*) | Nhịp tăng vừa phải, bước đi *basso continuo* nốt đen xen cặp móc đơn lấy đà tươi sáng. |
| **`rally`** (Tăng giá mạnh / Sôi động) | Biên độ tăng rộng (`rel_span >= 0.014`) và giai điệu nảy liên tục (`_melody_activity >= 0.35`) | **`bach_courante`** (*Courante*) | Phiên bứt phá mạnh mẽ: cú nhảy quãng đầu ô + chùm 4 móc kép cuốn theo đà tăng giá. |
| **`rally`** (Tăng giá bền vững) | Biên độ tăng rộng (`rel_span >= 0.014`) và có nhịp nghỉ tích lũy (`_melody_activity < 0.35`) | **`bach_gavotte`** (*Gavotte*) | Nhịp tăng khúc chiết, đĩnh đạc với 2 nốt đen mở ô và 4 móc đơn song thanh quãng 3/6. |
| **`volatile`** (Giằng co / Biến động mạnh) | Mọi phiên `volatile` | **`bach_fuga`** (*Fugue*) | Hai lực cung – cầu giằng co được tái hiện bằng hai bè Soprano và Bass rượt đuổi đối âm (*lag 2 bars*). |
| **`selloff`** (Bán tháo / Giảm điểm) | Mọi phiên `selloff` | **`bach_chaconne`** (*Chaconne*) | Dòng bass *Chaconne* bước xuống bi tráng dưới sóng *bariolage* móc kép và scale bứt phá. |

*(Lưu ý: Hai pattern nhịp `3/4` chậm và `6/8` nhanh là **`bach_sarabande`** và **`bach_gigue`** là linh hồn của các chương Chậm và Scherzo ở `1M / 3M / 1Y`, đồng thời vẫn xuất hiện trên các bài `3/4` và `6/8`).*

---

### 3.3. Phối hợp Pattern trong các bản dài (`1W`, `1M`, `3M`, `1Y`)

Giống như `_barrios_palette` của Barrios nhưng tuân thủ nghiêm ngặt **trật tự Tổ khúc Baroque của J.S. Bach**, khi `ctx.ensemble == "bach"` và `ctx.bars > 40`:

#### A. Quy tắc Hàng Tổ Khúc (`_bach_palette(ctx, primary)`) cho các chương nhiều vùng (`regions >= 2`)
Khi chương có từ 2 vùng trở lên (`_group_slots(ctx, body)`):
- **2 vùng (`A – B`)**: Vùng 1 chơi `palette[0]` (mở đầu), Vùng 2 chuyển sang `palette[1]` (khách tương phản).
- **3 vùng (`A – B – A`)**: Vùng 1 chơi `palette[0]`, Vùng 2 chơi `palette[1]`, Vùng 3 tái hiện `palette[0]`.
- **4 vùng (`A – B – C – A`)**: Vùng 1 chơi `palette[0]`, Vùng 2 chơi `palette[1]`, Vùng 3 chơi `palette[2]`, Vùng 4 tái hiện `palette[0]`. (Tương tự cho 5 vùng của `1W`: `A – B – C – B – A`, rút gọn tên hiển thị qua `pattern_form` thành `A — C — A`).

Bảng **`_bach_palette(ctx, primary)`** theo nhịp, tempo và vị trí chương:

| Nhịp & Loại chương | Pattern mở đầu (`primary` ở Vùng 1) | Chuỗi phối hợp (`_bach_palette`) | Cấu trúc tên chương tiêu biểu (`pattern_form`) | Ý nghĩa âm nhạc Baroque |
|---|---|---|---|---|
| **1. Nhịp `4/4` Mở đầu Suite & Bản Tuần**<br>(`1W` 90 BPM, `1M` I 96 BPM, `3M` I 96 BPM, `1Y` Tháng 1, 4, 7, 10 ở 100 BPM) | • `calm`: **`bach_prelude`**<br>• `rally` êm: **`bach_allemande`**<br>• `rally` mạnh: **`bach_bourree`**<br>• `volatile`: **`bach_fuga`**<br>• `selloff`: **`bach_chaconne`** | • Mở `bach_prelude`:<br>  `("bach_prelude", "bach_allemande", "bach_bourree")`<br>• Mở `bach_allemande`:<br>  `("bach_allemande", "bach_courante", "bach_gavotte")`<br>• Mở `bach_bourree`:<br>  `("bach_bourree", "bach_gavotte", "bach_fuga")`<br>• Mở `bach_fuga`:<br>  `("bach_fuga", "bach_allemande", "bach_bourree")`<br>• Mở `bach_chaconne`:<br>  `("bach_chaconne", "bach_sarabande", "bach_fuga")` | • 2 vùng (`1Y` mở, `1W` 2 phiên):<br>  `Prelude — Allemande`<br>  `Allemande — Courante`<br>• 3 vùng (`1M` I, `3M` I):<br>  `Prelude — Allemande — Prelude`<br>  `Allemande — Courante — Allemande`<br>  `Bourree — Gavotte — Bourree`<br>• 4–5 vùng (`1W` 4–5 phiên):<br>  `Prelude — Bourree — Prelude`<br>  `Allemande — Gavotte — Allemande` | Đúng chuẩn mở đầu một *Lute Suite / Partita*: từ **Prelude** bước sang **Allemande**, từ **Allemande** bước sang **Courante**, hoặc hai *Galanteries* **Bourrée & Gavotte** đối đáp nhau. |
| **2. Nhịp `3/4` Chương Chậm (`bridge=True`)**<br>(`1M` II 72 BPM, `3M` II 60 BPM, `1Y` Tháng 2, 5, 8, 11 ở 66 BPM) | • Mặc định (`calm`, `rally`, `volatile`, `selloff` có contrast):<br>  **`bach_sarabande`** | • Khi `mood in {"calm", "rally"}`:<br>  `("bach_sarabande", "bach_prelude")`<br>• Khi `mood == "volatile"`:<br>  `("bach_sarabande", "bach_courante")`<br>• Khi `mood == "selloff"`:<br>  `("bach_sarabande", "bach_chaconne")` | • `Sarabande — Prelude — Sarabande`<br>• `Sarabande — Courante — Sarabande`<br>• `Sarabande — Chaconne — Sarabande` *(giữ nguyên test đã khóa)* | Chương chậm mở bằng *Sarabande* nhấn phách 2; đoạn `bridge` ở giữa mở ra sóng rải *Prelude* êm ái, nhịp *Courante* linh hoạt, hoặc cao trào *Chaconne* khi bán tháo. |
| **3. Nhịp `6/8` Chương Scherzo / Tháng Khép (`trio=True`)**<br>(`1M` III 120 BPM, `1Y` Tháng 3, 6, 9 ở 108 BPM) | • `rally`: **`bach_gigue`**<br>• `calm`: **`bach_courante`**<br>• `volatile`: **`bach_fuga`**<br>• `selloff`: **`bach_chaconne`** | • Mở `bach_gigue`:<br>  - `rally`: `("bach_gigue", "bach_courante")`<br>  - `calm`: `("bach_gigue", "bach_bourree")`<br>• Mở `bach_courante`:<br>  `("bach_courante", "bach_gigue")`<br>• Mở `bach_fuga`:<br>  `("bach_fuga", "bach_courante")`<br>• Mở `bach_chaconne`:<br>  `("bach_chaconne", "bach_gavotte")` | • `Gigue — Courante — Gigue`<br>• `Courante — Gigue — Courante`<br>• `Fugue — Courante — Fugue`<br>• `Chaconne — Gavotte — Chaconne` | Trên nhịp 6/8 nhanh (`108–120 BPM`), **Courante BWV 1007** và **Gigue** tạo thành cặp vũ điệu nhịp ba sôi động bậc nhất của Bach: một bên nhảy quãng + lướt 4 móc kép, một bên rải hợp âm gãy 6/8. |
| **4. Nhịp `4/4` Chương Kết / Finale**<br>(`1M` IV 96 BPM, `3M` III 108 BPM, `1Y` Tháng 12 ở 96 BPM) | • `calm`: **`bach_gavotte`**<br>• `rally`: **`bach_bourree`**<br>• `volatile`: **`bach_fuga`**<br>• `selloff`: **`bach_chaconne`** | • Mở `bach_gavotte`:<br>  `("bach_gavotte", "bach_bourree")`<br>• Mở `bach_bourree`:<br>  `("bach_bourree", "bach_fuga")` *(giữ nguyên test `finale` đã khóa: phần A là Bourrée `divisions=2`)*<br>• Mở `bach_fuga`:<br>  `("bach_fuga", "bach_prelude")`<br>• Mở `bach_chaconne`:<br>  `("bach_chaconne", "bach_fuga")` | • `Finale: Gavotte — Bourree — Gavotte`<br>• `Finale: Bourree — Fugue — Bourree`<br>• `Finale: Fugue — Prelude — Fugue`<br>• `Finale: Chaconne — Fugue — Chaconne` | Chương kết khép lại tác phẩm bằng năng lượng tổng hợp của *Gavotte en Rondeau*, *Bourrée*, *Fugue* và *Chaconne*. |

---

### 3.4. Bảng kiểm chứng độ phủ của 9 Pattern qua tất cả các Span

Nhờ việc tách vai trò giữa **Chương mở đầu (`Opener`)**, **Chương giữa (`Slow 3/4`)**, **Chương ba (`Scherzo 6/8`)**, và **Chương kết (`Finale 4/4`)**, một người nghe khi bật `1M` (4 chương), `3M` (3 chương) hoặc `1Y` (12 chương) sẽ đi qua **trọn vẹn cả 9 pattern của Bach** mà không bị lặp:

| Quãng thời gian (`Span`) | Chương I / Mở | Chương II / Giữa | Chương III / Scherzo | Chương IV / Kết | Tổng số Pattern Bach được nghe |
|---|---|---|---|---|---|
| **`1D`** (1 chương, 34 ô) | 1 pattern duy nhất (`Prelude`, `Allemande`, `Courante`, `Bourree`, `Gavotte`, `Fugue`, hoặc `Chaconne`) | — | — | — | **1 pattern** (Monothematic) |
| **`1W`** (1 chương, 2–5 phiên) | Phiên 1: `Prelude` / `Allemande` / `Bourree` / `Fugue` | Phiên 2–4: Đan xen `Allemande`, `Courante`, `Bourree`, `Gavotte` theo chuỗi `_bach_palette` | — | Phiên cuối: Tái hiện pattern mở | **2 – 3 pattern** phối trong 1 mạch tuần |
| **`1M`** (4 chương Sonata) | **Chương I (`4/4`, 96 BPM)**:<br>`Prelude — Allemande — Prelude` *(hoặc `Allemande — Courante — Allemande`)* | **Chương II (`3/4`, 72 BPM)**:<br>`Sarabande — Prelude — Sarabande` *(hoặc `Sarabande — Chaconne — Sarabande`)* | **Chương III (`6/8`, 120 BPM)**:<br>`Gigue — Courante — Gigue` *(hoặc `Courante — Gigue — Courante`)* | **Chương IV (`4/4`, 96 BPM)**:<br>`Finale: Bourree — Fugue — Bourree` *(hoặc `Gavotte — Bourree — Gavotte`)* | **7 – 9 pattern** trải đều qua 4 chương |
| **`3M`** (3 chương Concerto) | **Chương I (`4/4`, 96 BPM)**:<br>`Prelude — Allemande — Prelude` *(hoặc `Allemande — Courante — Allemande`)* | **Chương II (`3/4`, 60 BPM)**:<br>`Sarabande — Prelude — Sarabande` *(hoặc `Sarabande — Chaconne — Sarabande`)* | — | **Chương III (`4/4`, 108 BPM)**:<br>`Finale: Bourree — Fugue — Bourree` *(hoặc `Gavotte — Bourree — Gavotte`)* | **6 – 7 pattern** trải đều qua 3 chương |
| **`1Y`** (12 chương Bốn Mùa) | **Tháng 1, 4, 7, 10 (`4/4`, 100 BPM)**:<br>`Prelude — Allemande` / `Allemande — Courante` | **Tháng 2, 5, 8, 11 (`3/4`, 66 BPM)**:<br>`Sarabande — Prelude — Sarabande` / `Sarabande — Chaconne — Sarabande` | **Tháng 3, 6, 9 (`6/8`, 108 BPM)**:<br>`Gigue — Courante — Gigue` / `Courante — Gigue — Courante` | **Tháng 12 (`4/4`, 96 BPM)**:<br>`Finale: Bourree — Fugue — Bourree` / `Gavotte — Bourree — Gavotte` | **Đủ 9/9 pattern** trong chu kỳ năm |

---

## 4. Đồng Bộ Với Các Hệ Thống Phụ Trợ Trong Codebase

### 4.1. Bảo toàn tuyệt đối các Unit Test không khung (`not _framed(ctx)`)
Các unit test hiện có trong `backend/tests/test_sonify_guitar.py` gọi `_bach(...)` trực tiếp mà không truyền `intro`/`outro` (`_framed(ctx) == False`), hoặc truyền 2 section `phrase` với `trio=True`. Để **100% các test hiện tại giữ nguyên kết quả**:
- Khi `not _framed(ctx)`:
  - `mood == "calm"` ở `4/4` giữ `bach_gavotte` trừ khi caller yêu cầu rõ hoặc truyền form có khung.
  - `mood == "rally"` ở `4/4` giữ `bach_bourree`, và `_bach_contrast` của `bach_bourree` giữ `bach_fuga` (bảo toàn `test_bach_trio_answers_the_bourree_with_the_fugue`).
  - Ở `test_a_mixed_sor_movement_keeps_the_patterns_beside_galop` và `finale = _suite(3, "bach", character="rally")`: ở Chương IV (`_is_suite_finale(ctx) == True` vì `trailing_pedal_length >= 10`), phần A của `rally` vẫn là `bach_bourree` và ô 12 thuộc phần A vẫn có `divisions == 2` khi toàn chương là Bourrée, hoặc giữ không có móc kép tại ô 12. *(Cụ thể: trong `test_bach_trio_answers_the_bourree_with_the_fugue`, dòng 4214 kiểm tra `finale = _suite(3, "bach", character="rally"); assert finale.divisions == 2; assert _sixteenths(finale.lead, 12) == []` — vì `bach_bourree` và `bach_gavotte` đều chỉ dùng lưới móc đơn `divisions == 2`, nên khi hàng của Chương IV `rally` là `("bach_bourree", "bach_gavotte")`, cả chương kết hợp `Bourree — Gavotte — Bourree` vẫn giữ `finale.divisions == 2` và `_sixteenths(finale.lead, 12) == []`!).*

### 4.2. Sóng Volume Affine & Cổng Snap (`backend/app/sonify/guitar_wave.py`)
Bổ sung 3 dòng vào `PROFILES` (tổng cộng **31 dòng** trong `PROFILES`):

| Khóa `(ensemble, pattern)` | Cửa sổ calm → wide | $W$ | Snap | Hạn mức `(phrase, sec)` | Cú được snap (`_is_target`) |
|---|---|---|---|---|---|
| `("bach", "bach_prelude")` | `28..56` → `34..62` | `5` | `66..68` | `(1, 2)` | Nốt `lead` mở đầu chu kỳ rải (`eighth in {0, 4}` ở `4/4` hoặc `eighth in {0, 3}` ở `3/4, 6/8`) tại `phrase.apex` khi `rise >= 3`. |
| `("bach", "bach_allemande")` | `28..56` → `34..62` | `9` | `66..68` | `(1, 2)` | Nốt `lead` tại `phrase.apex` khi `rise >= 3`. |
| `("bach", "bach_courante")` | `30..58` → `36..63` | `3` | `68..70` | `(1, 3)` | Cú nhảy mở ô (`accent=True`) hoặc nốt `lead` tại `phrase.apex` khi `rise >= 3`. |

*(Mọi dòng đều thỏa $V_{\text{ceil}} - V_{\text{floor}} \ge 27 \Rightarrow M = 1$; riêng `("bach", "bach_courante")` ở wide có `63 - 36 = 27`, gia nhập nhóm wide ở thủy triều `3`).*

### 4.3. Cửa Intro / Outro Riêng (`backend/app/sonify/guitar_frame_bach_sor.py`)
Mỗi pattern mới có một cửa riêng trong `DOORS`:

1. **`("bach", "bach_prelude"): bach_prelude`**:
   - **Intro ngắn (2 bước)**: Bước 0 dậm Bass `I` ngân dài dưới vòng rải móc kép *harpeggiato* ở `_P`; Bước 1 rải móc kép trên `V7` trên nền Bass chủ (*Tonic Pedal*) ở `_MP` dẫn vào thân bài.
   - **Intro dài (4 bước)**: Bước 0 rải mở trên `I` (`_P`); Bước 1 rải trên `IV` (`_P`); Bước 2 rải trên `V7` trên nền pedal (`_MP`); Bước 3 rải móc kép `V7 -> I` (`_MP`) nối liền mạch vào ô thân bài đầu.
   - **Outro ngắn (2 bước)**: Bước 0 rải giãn về móc đơn trên `V7` (`_MP`); Bước 1 hợp âm `I` ngân đầy (`_P`).
   - **Outro dài (4 bước)**: Bước 0 rải trên `IV` (`_MP`); Bước 1 rải trên `V7` (`_P`); Bước 2 `_bach_arpeggiato` trên `I` (`_P`); Bước 3 block `I` ngân (`_PP`).
2. **`("bach", "bach_allemande"): bach_allemande`**:
   - **Intro ngắn (2 bước)**: Bước 0 mở bằng chùm móc kép lấy đà vào hợp âm `I` kiểu *style brisé* (`_P`); Bước 1 đi bộ *style brisé* qua `V7` kèm 2 móc kép lấy đà cuối ô (`_MP`).
   - **Intro dài (4 bước)**: Bước 0 pickup móc kép vào `I` (`_P`); Bước 1 *style brisé* bước qua `I -> IV` (`_P`); Bước 2 `_bach_mordent` trên `V7` (`_MP`); Bước 3 chùm móc kép lấy đà từ `V7` vào thân bài (`_MP`).
   - **Outro ngắn (2 bước)**: Bước 0 *style brisé* nửa kết `IV -> V7` (`_MP`); Bước 1 block `I` trầm ấm (`_P`).
   - **Outro dài (4 bước)**: Bước 0 *style brisé* trên `IV` (`_P`); Bước 1 `V7` kèm mordent (`_MP`); Bước 2 treo nhẹ trên `I` (`_P`); Bước 3 block `I` ngân (`_PP`).
3. **`("bach", "bach_courante"): bach_courante`**:
   - **Intro ngắn (2 bước)**: Bước 0 nhảy quãng *Courante leap* trên `I` (phách 1 nhấn `accent`, móc đơn 2 `staccato`) ở `_P`; Bước 1 chùm móc kép trên `V7` và 2 móc đơn lấy đà ở `_MP`.
   - **Intro dài (4 bước)**: Bước 0 nhảy quãng mở trên `I` (`_P`); Bước 1 nhảy quãng và lướt móc kép trên `IV` (`_P`); Bước 2 chùm móc kép trên `V7` (`_MP`); Bước 3 nhịp lấy đà *Courante* đẩy vào thân bài (`_MP`).
   - **Outro ngắn (2 bước)**: Bước 0 nhịp *hemiola* (`0, 3`) trên `V7` (`_MP`); Bước 1 hợp âm `I` ở phách 1 ngân hết ô (`_P`).
   - **Outro dài (4 bước)**: Bước 0 *Courante* trên `IV` (`_MP`); Bước 1 chùm móc kép trên `V7` (`_MP`); Bước 2 nhịp *hemiola* `I -> V7` (`_P`); Bước 3 block `I` ngân (`_P`).

### 4.4. Scale Engine (`backend/app/sonify/guitar_scale_passages.py`)
- **Phân nhóm Pattern**:
  - **`bach_courante`**: Gia nhập `_BACH_GROUP2` (cùng `bach_chaconne`, `bach_gigue`, `bach_sarabande`) vì phách giữa của *Courante* đã có sẵn chùm 4 móc kép nội tại (`bach_group2_window` trả về phách móc kép đó). Nhờ vậy, biến động nhỏ giữ nguyên cú nhảy mở ô của *Courante*, còn Sóng Lớn (`Major Bridge Impulse`: $L \ge \text{epb}, \text{net\_span} \ge 6$) sau ô đầu vùng được phép mở đoạn nối scale dài 1–4 ô nhịp trên nền Bass đặc trưng của *Courante*.
  - **`bach_prelude` và `bach_allemande`**:
    - `bach_allemande` thuộc **Nhóm 3** (nhận cả scale ngắn `sub-bar` lẫn `multi-bar`), cửa sổ hairpin thuộc `_HAT_PATTERNS` (`52..82`).
    - `bach_prelude` thuộc `_BAROQUE_PATTERNS` (`54..84`), cho phép phủ câu chạy *tirata* liền bậc khi có xung giá và tự động giữ nốt Bass đầu mỗi nửa ô.

### 4.5. Hiển thị Tên Chương & Формат Tổ Khúc (`backend/app/sonify/program.py` & `src/sonify/program.ts`)
1. Trong `backend/app/sonify/program.py`:
   - Thêm vào `_PATTERN_TITLE`:
     ```python
     "bach_prelude": "Prelude",
     "bach_allemande": "Allemande",
     "bach_courante": "Courante",
     ```
   - Trong `form_pattern_ids(ctx, patterns)` (`backend/app/sonify/guitar_patterns.py`):
     - Mở rộng điều kiện đọc `_region_pattern_ids(ctx, patterns)` từ `ctx.ensemble == "barrios"` thành `ctx.ensemble in {"barrios", "bach"}` khi `ctx.bars > 40 and _framed(ctx)`.
     - Nhờ đó, một chương dài của Bach phối nhiều pattern sẽ tự động xuất tên tổ khúc đa phần như:
       - `"Prelude — Allemande"` (trên chương 2 vùng như `1Y` opener hoặc `1W` 2 phiên)
       - `"Prelude — Allemande — Prelude"` hoặc `"Allemande — Courante — Allemande"` (trên `1M` I, `3M` I)
       - `"Gigue — Courante — Gigue"` (trên `1M` III, `1Y` closer)
       - `"Bourree — Gavotte — Bourree"` (trên `1M` IV, `3M` III, `1Y` finale)
2. Trong `src/sonify/program.ts`:
   - Thêm `'Allemande'` và `'Courante'` vào `PATTERN_NAMES` (`'Prelude'` đã có sẵn) để `isPatternForm` nhận diện đúng cả tên đơn lẫn chuỗi `"Prelude — Allemande — Prelude"`, `"Allemande — Courante — Allemande"`, `"Gigue — Courante — Gigue"`.

---

## 5. Danh Mục Kiểm Thử (`Tests`)

1. **`backend/tests/test_sonify_guitar.py`**:
   - `test_bach_prelude_rolls_sixteenth_arpeggio_across_three_voices`: kiểm tra `divisions == 4`, mỗi móc kép trong ô `4/4` và `3/4` có attack ở `lead` hoặc `support`, Bass ngân mỗi nửa ô, vượt qua `assert_playable(..., "bach")`.
   - `test_bach_allemande_weaves_style_brise_and_sixteenth_pickup`: kiểm tra `support` vào trễ sau Bass (không chập cứng đầu ô), Bass đi bộ khi Lead ngân và không có `staccato`, phách cuối chạy móc kép lấy đà vào ô kế tiếp.
   - `test_bach_courante_leaps_on_beat_one_and_runs_sixteenths_on_the_middle_beat`: kiểm tra cú nhảy mở ô có `accent` ở phách 1 và `staccato` ở móc đơn thứ 2, chùm 4 móc kép liền bậc ở phách giữa, và móc đơn lấy đà cuối ô theo mẫu *BWV 1007*.
   - `test_bach_1d_ stays_one_pattern_and_longer_spans_walk_suite_rows`: kiểm tra `1D` giữ 1 pattern duy nhất xuyên suốt 30 ô thân bài, trong khi `1W` ($\ge 2$ phiên), `1M`, `3M`, `1Y` phối các pattern theo đúng bảng Tổ khúc Mục 3.3.
2. **`backend/tests/test_program.py` & `src/sonify/program.test.ts`**:
   - Kiểm tra `pattern_title` và `guitar_movement_name` cho `"Prelude"`, `"Allemande"`, `"Courante"`, và các chuỗi `"Prelude — Allemande — Prelude"`, `"Allemande — Courante — Allemande"`, `"Gigue — Courante — Gigue"`.
3. **`backend/tests/test_guitar_wave.py`**:
   - Cập nhật bảng 31 profile (thêm `bach_prelude`, `bach_allemande`, `bach_courante`) và kiểm tra bất biến $M = 1$, cửa sổ tầng ấm và cổng snap.
