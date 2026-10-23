# Guitar cổ điển: một nhạc cụ, ba bè, năm họ pattern

> **Trạng thái** (2026-10-24): một tài liệu. Phần nền và dialect Villa đã chạy trong code. Ba phase bên dưới là phần còn lại. Mỗi phase nghe được một mình.
>
> Pattern có cửa tempo riêng. Tremolo chỉ hợp lệ từ 90 đến 140 BPM, rõ nhất ở 100–120, và luôn là lưới đầy `p–a–m–i` trên từng nốt đen. Dưới 90, cách hát là thánh ca của nhà đó. Chương không tăng tempo để cứu một pattern.
>
> **Liên kết**: [`docs/sonify-explain.md`](./sonify-explain.md), [`docs/sonify-instrument-sets.md`](./sonify-instrument-sets.md), [`docs/sonify-long-form.md`](./sonify-long-form.md).

---

## Đã xong

Khung nghe được hôm nay, trong `backend/app/sonify/guitar.py` và các đường đã nối.

- Variant `guitar`, một part nylon `Acoustic Nylon`, ba voice trên một khuông, `<backup>` giữa các voice, `octave-change -1` cùng `written_shift +12`. UI: **Sor**, **Barrios**, **Lobos**. Hàng guitar của minimalist là **Guitar thép**.
- BPM bản ngày: Sor 88, Villa 100, Barrios 120. Bản dài giữ số ô và BPM của giao hưởng, hoán 6/8 với 3/4. Không swing, không rubato, không đổi nhịp giữa chương.
- Nén đường giá vào cửa sổ bè Cao, dịch {+12, 0, −12, −24}, rồi lượng tử hóa lại. Biên viết guitar dịch cả hai chiều theo giọng nhà.
- Dialect **Villa đã đăng ký**. Sor và Barrios còn `COMMON`. Vòng Viterbi gọi `transition` cho mọi cặp; `None` thì Markov cũ chạy; số dương không nhân 2.
- Ba texture thô, **chưa có bộ chọn theo câu**:
  - Sor, Villa, và Barrios dưới 90 BPM: arpeggio móc đơn. Villa cuộn dày hơn và được nhấn 3+3+2 tối đa hai ô `volatile` ở `mf`/`f`, meter 4/4.
  - Barrios từ 90 BPM trở lên: **tremolo cả bài**, trừ ô pedal. Lưới đã khóa bởi test: mỗi nốt đen là một trùm bốn móc kép cùng cao độ; 6/8 có ba trùm trong ô (ngón cái ở đầu mỗi nốt đen, không gom theo phách chấm); mọi móc kép đều hát. Ngón cái 58 đánh gốc và quãng 5 cùng lúc, ngân hết nốt đen, không nhường phách cho bè Trung. Bè lặp `a m i a` = 52, 55, 54, 52. Ô đổi hợp âm: nốt màu Trung vào cùng đầu ô, ngón cái vẫn giữ gốc.
  - Dưới 90: giữ nguyên BPM, `divisions = 2`, không tremolo. Hiện vẫn là arpeggio chung, chưa phải thánh ca.
- Ép ngón tối đa 4% số lần đánh giai điệu, chỉ vào nốt nhấn sau câu mở, không ép trên móc tremolo.
- Ô pedal: bass gốc ngân, không tremolo.

Chỗ code còn lệch so với hợp đồng bên dưới: Barrios nhanh tremolo mọi câu, kể cả câu nốt chạy và câu mở. Chương chậm hát bằng arpeggio, chưa hát bằng thánh ca.

## Sẽ làm

### Phase 1 — Bộ chọn, và hai cách hát

Nghe được: câu ngân từ 90 BPM là tremolo; chương dưới 90 là thánh ca của nhà đó; câu chạy và câu mở vẫn là arpeggio đang có. Chưa có điệu Nam Mỹ, chưa có dialect Barrios, chưa có scale.

- Hàm chọn pattern theo thứ tự mục 3. Cửa tempo lọc trước sở thích của nhà.
- Tremolo chỉ khi được chọn. Giữ nguyên lưới, lực, và việc ngón cái không nhường phách. Không viết lại thành phách chấm ở 6/8.
- Thánh ca: Andante của Barrios, chord-melody của Villa, Élégiaque của Sor, đúng mục 6.
- Sau hai câu tremolo liên tiếp, câu kế là thánh ca. Luật này chỉ chạy khi tremolo đang hợp lệ.
- Mở bài và câu chạy nhanh vẫn gọi arpeggio hiện tại. Chuông Preludio và vòng étude để Phase 3.

### Phase 2 — Dialect Barrios và điệu nhanh

Nghe được: thứ đi được vòng quãng 5 trên nốt thuộc thang; trưởng đi được chuỗi át bảy khi giá ngồi trên Đô, La hoặc Rê; câu nốt chạy trên 100 BPM ở 4/4 hoặc 6/8 là choro hoặc polca. Câu đang ngân vẫn tremolo.

- Đầu phase, đọc tổng phổ và khóa số móc mục 9.1 và 9.2. Lệch thì sửa bảng trong file này trước khi viết renderer.
- `BarriosDialect`, bốn hợp âm thứ, các cạnh, `quality_group` của `+6`, và luật một ô `"augmented-sixth"` trong `form.py`. Không sửa `minor_bias`.
- Điệu chỉ khi bộ chọn đã trả `dance`. Hemiola là bản to của polca, không phải cách thay tremolo.

### Phase 3 — Scale dùng chung, và nốt còn lại của từng biến thể

Nghe được: đỉnh câu có một đoạn chạy rơi đúng nốt giá; Preludio có chuông; Grand Solo dày lên khi câu lặp; vòng Villa tách khỏi arpeggio đều của Sor.

- Scale là lớp phủ bè Cao, grammar một, giá trị nốt theo tempo. Đệm phía dưới vẫn của pattern chủ.
- Chuông Preludio, biến tấu Grand Solo, vòng Étude 1, campanella.
- `assert_playable` theo profile, mô hình dây và phím. Trần ba bè giữ nguyên; ngoại lệ tremolo đã nghe (gốc và quãng 5 cùng voice Trầm) không bị siết lại.

---

## 1. Ba tầng

Người nghe vẫn chọn một nhà: `classic` (Sor), `villa`, `barrios`. Bên trong có ba tầng tách nhau.

**Dialect hòa âm** chọn hợp âm. Sor ở catalog chung. Villa có sus, add9 và hai hợp âm trượt. Barrios, từ Phase 2, có vòng quãng 5 thứ và chuỗi át trưởng. Dialect không biết tremolo hay choro.

**Pattern** là cách tay phải đi trong ô. Mỗi pattern khai cửa tempo, meter được đứng, bè nào hát, bè nào giữ nhịp, và cách band `p–f` làm nó thưa hay dày. Band đổi mật độ trong pattern. Band không đổi họ pattern.

**Palette** là danh sách pattern của một nhà, cộng thứ tự khi nhiều pattern cùng hợp lệ. Bộ chọn lọc cửa trước, rồi mới xét thứ tự.

Một chương có một BPM và một meter. Pattern nằm ngoài cửa thì không phải ứng viên. Không nâng tempo chương chậm để tremolo hợp lệ.

## 2. Năm họ

Một phách trong tài liệu này là một nốt đen: hai móc đơn, hoặc bốn móc kép.

| Họ | Cửa | Bè hát | Bè nhịp | Chung đến đâu |
|---|---|---|---|---|
| Arpeggio | Mọi tempo trên bản đồ | Cao, trên lưới nốt giá | Trầm và Trung đi vòng hợp âm | Chung hợp đồng. Ba vòng: Sor đều, Villa cuộn, Barrios Preludio |
| Thánh ca | Nhà của chương dưới 90, và câu nghỉ tai khi tremolo đã chạy hai câu | Cao là nốt trên, đánh cùng hợp âm | Trầm thuộc hợp âm | Chung vai hát. Lưới và hợp âm là của từng nhà |
| Tremolo | 90–140, rõ ở 100–120 | `a–m–i` lặp một nốt đen | Ngón cái mỗi trùm, gốc và quãng 5 | Một lưới. Palette hiện chỉ Barrios có |
| Scale | Mọi tempo; giá trị nốt đổi theo tempo | Cao, một mình | Trầm của pattern chủ, hoặc nghỉ | Chung grammar. Đệm không dùng chung |
| Điệu | Mỗi điệu một cửa | Cao vẫn là nốt giá | Dáng đi ở Trầm và Trung | Không dùng chung |

Arpeggio là phương án còn lại: tempo nào cũng đứng được. Tremolo không có bản thưa. 96 và 108 vẫn là lưới đầy. Dưới 90, họ này vắng mặt. 140 là trần cửa, không phải BPM của chương nào trên bản đồ.

Điệu nhanh của Barrios đứng từ trên 100 BPM, ở 4/4 hoặc 6/8, khi giai điệu đang chạy và character khác `calm`. 3/4 không có điệu đó. Hành khúc chấm dôi của Sor là dáng đi chậm, nằm trong Élégiaque, không dùng cửa của choro.

## 3. Bộ chọn

Khóa theo câu. Band của câu là band ô chứa nốt đỉnh (`phrase.apex`). Scale và nốt dẫn của điệu được chiếm một đoạn trong câu mà không đổi pattern của cả câu.

Lọc rồi mới xếp. Một pattern ngoài cửa tempo, ngoài meter, hoặc trái hình câu thì bị loại trước khi xét thứ tự.

1. Ô khung mở (`intro`, `warmup`) hoặc câu đầu chương → arpeggio khai của nhà đó.
2. Câu có nốt giai điệu giữ từ hai phách đen (≥ 4 móc đơn liền cùng cao độ trên đường giai điệu đã nén), và palette có tremolo, và BPM nằm trong 90–140 → tremolo. Đã có hai câu tremolo liền trước thì câu này là thánh ca.
3. Câu đang ở vai hát: Barrios khi BPM dưới 90; Sor khi chương chậm (`bpm <= 72`), `selloff`, hoặc đoạn `trio` ở thứ; Villa khi chương chậm (`bpm <= 72`), band `p`, hoặc `calm` → thánh ca của nhà đó.
4. Câu đang chạy (mọi nốt trong câu đều ngắn hơn hai phách đen), character khác `calm`, BPM trên 100, meter 4/4 hoặc 6/8, và palette có điệu của meter đó → dance. Phase 1 chưa có nhánh này: câu chạy rơi xuống bước 5.
5. Còn lại → arpeggio của nhà đó.

Scale không tranh cả câu. Phase 3 phủ một đoạn ở đỉnh hoặc ở hai phách cuối câu đóng, trên pattern đã chọn, khi còn ngân sách.

Hệ quả trên bản đồ đang chạy:

| Chỗ | BPM, meter | Barrios | Sor | Villa |
|---|---|---|---|---|
| `1D` | 120 / 100 / 88, 4/4 | Ngân: tremolo. Chạy, từ Phase 2: choro. Mở: arpeggio | Arpeggio. 88 nằm dưới cửa tremolo | Arpeggio. `calm` và band `p`: thánh ca |
| `1W` | 90, 4/4 | Tremolo ở sàn cửa, chỉ câu ngân | Arpeggio hoặc Élégiaque nếu `selloff` | Arpeggio hoặc chord-melody |
| Chương 96 BPM, 4/4 | 96 | Tremolo nếu câu ngân. Chạy: arpeggio, vì điệu chỉ từ trên 100 | Theo character | Theo character |
| Chương chậm `1M` II, `3M` II, tháng giữa `1Y` | 72, 60, 66, đều 3/4 | Thánh ca. Không tremolo, không choro | Élégiaque | Chord-melody |
| Scherzo `1M`, tháng khép `1Y` | 120 và 108, 6/8 | Ngân: tremolo đầy, ba trùm nốt đen. Chạy, từ Phase 2: polca; band `f` là hemiola của polca | Élégiaque khi `selloff` hoặc `trio` ở thứ; còn lại arpeggio | Arpeggio; `calm` thì chord-melody |
| Chương III `3M` | 108, 4/4 | Như `1D` của Barrios | Theo character | Theo character |

`1M` I và IV, tháng mở và tháng 12 của `1Y` là các chương 96 BPM. `3M` I là 4/4 cùng họ với chúng.

## 4. Bản đồ nhịp

Đã code trong `span.py`. Guitar hoán meter cùng số móc đơn mỗi ô, giữ số ô và BPM.

| Khung | Chương | Meter guitar | BPM |
|---|---|---|---|
| `1M` | I, IV | 4/4 | 96 |
| `1M` | II | 3/4 | 72 |
| `1M` | III | 6/8 | 120 |
| `3M` | I, III | 4/4 | như giao hưởng |
| `3M` | II | 3/4 | 60 |
| `1Y` | Tháng mở, tháng 12 | 4/4 | 100 và 96 |
| `1Y` | Tháng giữa | 3/4 | 66 |
| `1Y` | Tháng khép | 6/8 | 108 |

`1D` giữ 4/4, 34 ô. `1W` giữ 4/4, 90 BPM. Cờ `trio` trên scherzo và tháng khép vẫn còn, vì Élégiaque đọc cờ đó. Đồng hồ guitar trùng giao hưởng: `(970.0, 1530.0, 2840.1)`, trần `1Y` là `47:21`.

Trong chương, 4/4 có thể nhấn 3+3+2. Luật này đã có cho Villa: ô `mf`/`f`, character `volatile`, tối đa hai ô liền, chỉ 4/4. Các nhà khác chưa dùng. Hemiola 6/8 (nhấn móc đơn 0, 2, 4) là bản band `f` của polca, Phase 2, không phải một lớp accent chung.

## 5. Arpeggio

Hợp đồng chung: bè Cao là đường giá đã nén, trên lưới móc đơn. Vòng chỉ gồm Trầm và Trung, nằm dưới giai điệu đang vang. Không nốt Trung nào trùng hoặc cao hơn Cao. Band làm vòng thưa hoặc dày, không đổi họ.

**Đang chạy.** Một vòng dùng chung. Bass gốc ở các phách mạnh của meter, gập vào dải Trầm. Trung lấy âm hợp âm, số nốt theo band; ô `p` một nốt. Villa (`rolling`) dày hơn và có tresillo như mục 4. Ô pedal chỉ bass gốc.

**Phase 1** vẫn gọi hàm này cho câu mở và câu không rơi vào tremolo hay thánh ca. Chưa tách ba vòng.

**Phase 3** tách vòng:

- Sor study: 4/4 như bảng band hiện có (gốc móc 0, quãng 5 móc 4, arpeggio các móc yếu khi `mf`/`f`). 6/8 nhóm ở móc 0 và 3. 3/4 phách mạnh móc 0, trọng phụ móc 4.
- Villa: vòng cố định dưới giai điệu. 4/4 đủ tám móc khi `mf`/`f`. 6/8 một vòng, nhấn móc 0 và 3. 3/4 band `f` nhấn móc 0 và 3, đó là hemiola của vòng này, không phải điệu Barrios. Nốt bass cuối ô ở band `f` được là dẫn bán cung về gốc ô sau. Bè Trung lấy âm màu khi hợp âm là sus hoặc add9. Không gọi `jazz_chord`.
- Barrios Preludio: arpeggio chậm hơn vòng Villa, bass gốc mỗi hai ô, velocity vòng thấp hơn giai điệu khoảng 8. Chuông là tham số của biến thể này: tối đa một nốt mỗi hai ô, cao độ lấy từ dữ liệu, vang không quá 83, chỉ khi `bell_budget` còn. Phiên phẳng (biên độ ≤ 0.5%) không có chuông. Harmonics thật chỉ xuất nếu sample trả lời; mặc định là nốt cao ngân.

## 6. Thánh ca — Phase 1

Ba biến thể, cùng vai: giai điệu là nốt trên, hợp âm đánh cùng nó ở phách mạnh của meter, bè Trung thưa và được ngân, bass thuộc hợp âm. Khối đúng ba nốt, Trung dưới Cao. Ở 3/4, cú khối chuẩn chỉ móc 0. Móc 4 chỉ thêm ở ô đỉnh câu hoặc ô kết câu.

### 6.1. Barrios — Andante

Nhà của mọi chương Barrios dưới 90, và của câu nghỉ sau hai câu tremolo. Hợp âm ngân cùng giai điệu ở phách mạnh. Giữa phách, Trung không gảy nốt mới. Bass gốc, thưa. Chưa viết luật đảo 6/3: tổng phổ Andante có planing, tài liệu này không lấy đó làm hợp âm mới và cũng chưa khóa thành luật bè.

### 6.2. Villa — chord-melody

Chương chậm, và chương nhanh khi band câu là `p` hoặc character là `calm`. Nốt Trung là âm 3 hoặc âm 7; với `suspended` thì là quãng 2, quãng 4 hoặc b7. Lưới khối: 4/4 ở móc 0 và 4; 6/8 ở móc 0 và 3; 3/4 ở móc 0, cộng móc 4 ở ô đỉnh hoặc ô kết. Câu đang lên ở 4/4 được dồn cú từ cách 4 móc xuống cách 2 móc. Ở 6/8 và 3/4, dồn không chèn cú vào móc yếu: 6/8 chỉ thêm đầu nhóm còn lại, 3/4 chỉ dày lên giữa các ô. Một hairpin theo cả câu.

Riêng câu chương chậm, band `f`, `volatile`, có breakout: Phase 3 mới phủ scale. Phase 1 câu đó vẫn là chord-melody.

### 6.3. Sor — Élégiaque

Bật khi chương chậm (`bpm <= 72`), hoặc `selloff`, hoặc section mang `trio` ở mode thứ. Scherzo 120 và tháng khép 108 đều đi cửa `trio` này. `3M` không có trio.

Bass hành khúc, theo meter:

- 4/4: mỗi nửa ô, móc 0 dài 3, móc 3 ngắn 1 đi xuống liền bậc.
- 3/4: móc 0 dài 3, móc 3 ngắn 1 đi xuống, móc 4 dài 2. Ô kết câu, bass ngân từ móc 0.
- 6/8: móc 0 dài 2, móc 2 ngắn 1, móc 3 dài 2, móc 5 ngắn 1.

Hai ô cuối câu đóng ở thứ: bass ưu tiên đi xuống liền bậc theo thang, khi hợp âm chứa những bậc đó. Trung thưa hơn study một bậc. Appoggiatura: tối đa một mỗi câu, khi nốt phách mạnh được giữ từ hai móc và nốt dữ liệu kế lệch đúng một bậc thang. Móc đầu của nốt phách mạnh là nốt thang ngoài hợp âm, cách nốt giải quyết một bậc theo hướng ngược, rồi móc sau trả về đúng nốt dữ liệu. Không có fill kết câu.

## 7. Tremolo — lưới đã chạy, cửa là Phase 1

Palette chỉ có Barrios. Cửa 90–140. Lưới dưới đây đã khóa trong `test_sonify_guitar.py`. Phase 1 đổi lúc nào gọi nó, không đổi trùm.

Một trùm là một nốt đen: bốn móc kép cùng một cao độ giai điệu. Cao độ chỉ đổi theo lưới móc đơn của dữ liệu, tức ở biên trùm. 4/4 có bốn trùm. 3/4 có ba. 6/8 cũng có ba, vì ô dài ba nốt đen; test scherzo 120 đòi mọi móc kép đều hát và ngón cái mở trùm ở beat 0, 1 và 2. Không gom 6/8 thành hai phách chấm với một ngón cái và năm lần lặp.

Ngón cái, velocity 58, đánh gốc và quãng 5 cùng lúc, ngân hết nốt đen. Hai nốt đó cùng voice Trầm. Bè lặp 52, 55, 54, 52. Ô đổi hợp âm: Trung đánh một nốt màu dưới giai điệu ở đầu ô, cùng lúc với ngón cái. Phách đó có bốn cao độ. Đó là ngoại lệ đã nghe, không siết về ba cao độ trong Phase 1 hay Phase 3.

Ô pedal không tremolo: giai điệu ngân theo câu, bass gốc. Hai phách cuối câu đóng tắt tremolo, trả về arpeggio kết, hoặc về đoạn scale khi Phase 3 đã có.

Ép ngón giữ luật đang chạy: dưới 4%, không ở câu đầu, không trên móc kép tremolo.

## 8. Scale — Phase 3

Một grammar cho cả ba nhà. Bè Cao chạy liền bậc giữa hai mốc dữ liệu. Nốt đích trùng nốt giá hoặc nốt đỉnh. Nốt đầu được lệch 3–5 bậc thang để lấy đà, và phải thuộc thang. Nốt ở phách mạnh trong đoạn giữ nguyên cao độ so với bản không chạy. Hướng chạy cùng hướng câu, trừ đoạn đi xuống ở hai phách cuối câu đóng.

Giá trị nốt theo tempo của chương. Dưới 90, chạy bằng móc đơn (2–4 móc đơn mỗi đoạn). Từ 90, được dùng móc kép (4–8 móc kép mỗi đoạn; riêng perpetual tới 16 móc kép một ô). Cùng một luật «liền bậc, rơi đúng mốc».

Ngân sách: tối đa một đoạn mỗi câu, số ô có chạy không quá khoảng 15% ô của section, mỗi section còn ít nhất một câu không chạy. Âm lấy từ thang của mode. Barrios được một nốt dẫn bán cung ở móc kép ngay trước đích, tối đa một mỗi đoạn. Sor và Villa không lấy nốt đó trong đoạn scale.

Đệm không dùng chung. Sor và Villa giữ bass của pattern chủ, Trung nghỉ trong lúc chạy. Barrios: Trung nghỉ, bass gốc ở phách 1 và 3. Dạng chạy cả ô (perpetual) chỉ Barrios, chỉ khi giá đứng yên từ một ô, band `f`, `volatile`, tối đa hai ô: mốc dữ liệu neo ở móc kép 0 của mỗi phách, móc kép 2 là nốt chạy, rồi quay về đúng nốt đang giữ.

Grand Solo của Sor dùng đoạn scale này khi câu ở lớp arpeggio dày, `phrase.rise` đủ, band `mf`/`f`. Biến tấu theo lần lặp cũng thuộc Phase 3: hai câu cùng họ khi cùng pitch-class gốc ô mở, cùng dấu hướng, đỉnh lệch không quá hai bậc, độ dài lệch không quá bốn móc đơn. Mức figuration tăng một bậc trong họ, đặt lại khi sang section không phải tái hiện. Khung nốt phách mạnh không đổi giữa các lần. Đầu section ở band `f`, ô mở của Grand Solo đánh hợp âm khối ba nốt (Trầm + Trung + Cao cùng lúc); trước câu chứa đỉnh cao nhất của section, nếu câu trước đó đóng, cả ba bè được lặng một móc đơn (caesura) để lấy hơi kịch tính.

## 9. Điệu — Phase 2

Điệu không đổi `slots` và không đổi ký hiệu nhịp. Giai điệu giá đứng trên móc kép chẵn. Móc lẻ là đệm. Cụm cùng vang tối đa ba nốt, đi qua luật gập bass và thứ tự bè đang có.

Chỉ chọn khi bước 4 của bộ chọn đạt: câu không giữ hai phách, character khác `calm`, BPM trên 100, meter 4/4 hoặc 6/8. Câu ngân ở scherzo 120 band `f` vẫn là tremolo.

### 9.1. Choro, meter 4/4

`divisions = 4`. Một ô là hai levada tám móc kép. Trong mỗi nửa ô, tính từ đầu nửa đó:

| Móc kép | Bè | Nội dung |
|---|---|---|
| 0 | Trầm + Cao | Gốc. Cao là nốt dữ liệu |
| 3 | Trung | Một âm hợp âm đã tỉa |
| 4 | Trầm + Cao | Quãng 5. Cao là nốt dữ liệu |
| 6 | Trung, và Cao nếu trùng nốt dữ liệu | Âm bảy hoặc âm ba |
| 7 | Trung | Một nốt hợp âm, lệch trước phách sau |

Nửa sau cộng 8. Móc 15, khi gốc ô sau thấp hơn đúng một quãng 5, là một nốt Trầm dẫn bán cung dưới gốc ô sau. Ô không rơi quãng 5 thì móc 15 giữ nốt Trung. Maxixe dùng cùng mẫu, không tách điệu.

Số móc này là đề xuất. Đầu Phase 2 đọc một ô *Choro da Saudade* và sửa bảng nếu lệch.

### 9.2. Polca, meter 6/8

Một ô là 12 móc kép. Bản thường:

| Móc đơn | Móc kép | Bè |
|---|---|---|
| 0 | 0 | Trầm gốc + Cao |
| 1 | 2 | Trung |
| 2 | 4 | Trung, và Cao nếu có nốt dữ liệu |
| 3 | 6 | Trầm quãng 5 + Cao |
| 4 | 8 | Trung |
| 5 | 10 | Trung, và Cao nếu có nốt dữ liệu |

Band `f` là bản khác, không phải polca bị khoét. Đệm chỉ ở móc đơn 0, 2, 4. Đó là hemiola: nhấn 0, 2, 4 như mục 4. Cao vẫn hát nếu lưới dữ liệu có nốt ở móc đơn lẻ. Nốt dẫn bán cung, cùng điều kiện quãng 5, là nốt Trầm mới ở móc kép 11, có ở cả hai bản. Ô không rơi quãng 5 thì móc 11 nghỉ.

Đầu Phase 2 đọc *Danza Paraguaya* và sửa bảng nếu lệch. Profile `barrios_dance` nhận nốt dẫn này. Profile `study` báo lỗi trên cùng nốt đó.

## 10. Dialect hòa âm

Vỏ `HarmonyDialect` đã có. `dialect_for` trả `COMMON` khi ensemble không nằm trong `DIALECTS`. `color_credit` của `COMMON` là 0. Hợp âm ngoài `extra()` vẫn đi `_borrowed_allowed`. Ô pedal chỉ hợp âm chủ.

### 10.1. Villa — đã code

Khóa bởi `backend/tests/test_villa_dialect.py`. Ba phase không đổi các số này.

Sus và add9 phải có mặt lúc Viterbi chọn, trước `quantize_strong_beats`. `jazz_chord` không chạy trên slot villa. Khoản màu 0.70 chỉ khi đã có hợp âm trước, cùng gốc, một phách mạnh là âm màu, và lần đổi đi từ hợp âm ba cha. 0.60 không giữ được sus trước F ở `rally`. Ô đầu bài và ô khác gốc không được khoản. Âm màu chỉ tính khi gốc đó đang được giữ.

`shares_root` đúng khi cùng `root_step` và `alter`, và một bên là `"suspended"`. Add9 ở nhóm `"major"`, không cần cửa này. `degrees` trên `Chord` để `transpose_chord` viết sus đúng chữ. Quãng 5 vẫn ở `pitches[2]`.

Catalog đã lọc, không gian Đô:

| | Trưởng | Thứ tự nhiên |
|---|---|---|
| sus2 | C, D, F, G, A | C, E♭, F, A♭ |
| sus4 | C, D, E, G, A | C, D, E♭, F, G |
| add9 | C, F, G | `Cm add9`, `Fm add9` |
| 7sus4 | G, D, A, `E7sus4` | C, D, F, G |

Trượt song song chỉ ở trưởng: `Csus2` → `Bbsus2` và `Fsus2` → `Ebsus2` cửa 0.22; `Bbsus2` → `F` và `Ebsus2` → `F` cửa 0.34. Mọi cặp khác có một đầu là hợp âm trượt trưởng trả 0. Ở thứ, `Ebsus2` là sus thuận thang, không thuộc danh sách trượt.

Thứ tự `transition`: hợp âm trượt trưởng; về hợp âm ba cha bằng 0.40; cùng gốc với một màu villa bằng 0.30; rồi cửa `_ROOT_TRANSITIONS` của gốc đích hoặc gốc nguồn; còn lại 0 nếu một đầu thuộc `extra()`, `None` nếu không. `bias` tuyệt đối dưới 0.1, chỉ khi phách mạnh là âm màu, cộng lên sàn 0.08. Không bias nào bù phạt phách mạnh 2.5.

Tỉa: hợp âm bốn nốt bỏ quãng 5 trước. Sus không có âm ba để giữ; quãng 2 hoặc 4 chiếm chỗ âm ba.

### 10.2. Barrios — Phase 2

Hòa âm chức năng. Không sus, không add9. `color_credit` trả 0. Giai điệu thứ trên thứ tự nhiên, trưởng trên Đô trưởng. Fa♯, Rê♭ và Đô♯ không có trong `raw_pitches`; nốt ngoài thang làm `bar_quantization_loss` ném lỗi. Nốt đặc trưng ngoài thang có trong tổng phổ (Napolitaine, Đô♯°7, giảm bảy đi qua ở trưởng) không vào `extra()`.

`DIALECTS` thêm `"barrios"`. `dialect_for("classic")` và symphony vẫn là `COMMON`. Thứ thêm bốn hợp âm. Trưởng không thêm hợp âm; chuỗi át dùng `BORROWED` sẵn có và ba cạnh mới.

| Tên | Nguồn | `root_step`, `alter` | Nốt | Vai |
|---|---|---|---|---|
| `Bb` | `BF` | B, −1 | Si♭–Rê–Fa | ♭VII |
| `Bb7` | `BF7` | B, −1 | Si♭–Rê–Fa–La♭ | ♭VII7 |
| `D7` | `D7` sẵn có | D, 0 | Rê–Fa♯–La–Đô | V/V. Trên thang thứ chỉ Rê và Đô |
| `Ab+6` | mới | A, −1 | La♭–Đô–Mi♭–Fa♯ | sext tăng Đức, vào V |

```python
Chord(
    "Ab+6", "A", KIND_OTHER, "+6", (68, 72, 75, 78),
    alter=-1, degrees=(0, 2, 4, 5),
    tones=((8, "A", -1), (3, "E", -1), (6, "F", 1)),
)
```

`(68, 72, 75, 78)` là La♭4–Đô5–Mi♭5–Fa♯5. Thiếu `degrees`, nốt thứ tư bị viết thành Sol♭. `quality_group` trả `"augmented-sixth"` khi `kind_text == "+6"`, trước nhánh `"major"`. Nhóm này để luật một ô bắt được hợp âm. Rơi vào `"major"` thì La♭ → `Ab+6` thành đổi chất giá 0.50.

Trong `form.py`, điều kiện một ô đang dành cho `"diminished"` (`target_held != 1`) nhận thêm `"augmented-sixth"`, trước nhánh đổi tự thân thành `BORROWED_HOLD_PROB` 0.16. `Ab+6` cùng gốc với La♭, nhánh cùng gốc đòi `target_held == 2`, luật một ô cấm `target_held == 2`, nên `Ab+6` không đi từ La♭ hay La♭maj7 và không đứng hai ô.

`shares_root` trả `False`. `transition` trả số khi một đầu thuộc `extra()` của mode đang chạy, hoặc khi cặp nằm trong ba cạnh chuỗi át trưởng. Không có trong bảng mà một đầu thuộc `extra()` thì trả 0. Cặp khác trả `None`. Bắt buộc có số tường minh vì `Bb` không có hàng trong `_ROOT_TRANSITIONS`, và `D7` thứ trùng `root_step` với ii. Trọng số đưa thẳng vào `−0.6·ln`, không nhân 2. Ô thứ hai của một gốc (`prev_held == 1`, không mở section) vẫn dùng `SECOND_BAR_STAY_COST` 0.15, cạnh không vào giá.

Tỉa bốn nốt: bỏ `pitches[2]`. `Ab+6` còn La♭–Đô–Fa♯. `D7` còn Rê–Fa♯–Đô. `Bb7` còn Si♭–Rê–La♭. Ống sửa Phase 3 phải coi Fa♯ của `Ab+6` là âm được giữ, cùng chỗ với âm 7, không bỏ như nốt lạ. Không gọi `jazz_chord`.

**Cạnh thứ, vòng xuống quãng 5**

| Cặp | Trọng số |
|---|---|
| `Fm` / `Fm7` → `Bb` | 0.42 |
| `Fm` / `Fm7` → `Bb7` | 0.34 |
| `Cm` / `Cm7` → `Bb` | 0.12 |
| `Bb` → `Eb` | 0.42 |
| `Bb` → `Ebmaj7` | 0.26 |
| `Bb7` → `Eb` | 0.50 |
| `Bb7` → `Ebmaj7` | 0.34 |
| `Bb` → `G` | 0.22 |
| `Bb` → `G7` | 0.26 |
| `Bb` → `Bb` | 0.18 |
| `Bb` → `Bb7`, `Bb7` → `Bb` | 0.24 |
| `Bb7` → `Bb7` | 0.14 |

`Cm` → `Fm` giữ 0.26. `Eb` → `Ab` giữ cửa E→A = 0.34. Từ Fa thứ, {Si♭, Rê, Fa} ra `Bb`; thêm La♭ ở phách mạnh thì ra `Bb7`. Ô chỉ Si♭, `prev_held == 1`, ở lại `Bb`. Sau khi `Bb` đã giữ hai ô, ra `G` hoặc `G7`. `sing_leading` cho Sol và Sol7 hát Si♭ với phát xạ 0. Nốt Si tự nhiên trên giai điệu thì lượng tử hóa ném lỗi.

**Khép vòng**

| Cặp | Trọng số |
|---|---|
| `Ab` / `Abmaj7` → `D7` | 0.48 / 0.40 |
| `Dm7b5` → `D7` | 0.40 |
| `D7` → `G` | 0.46 |
| `D7` → `G7` | 0.55 |
| `D7` → `D7` | 0.12 |

Không có hợp âm ba Rê trưởng. Ô {Rê, Đô} ở lần giữ thứ hai ở lại `Dm7b5` (0.15 cộng bias 0.06), vì đổi sang `D7` tốn 0.50 cộng sàn 0.13. Cạnh 0.40 chỉ thắng từ ô thứ ba. Phách mạnh Rê sau La♭ thì `D7` thắng (cửa 0.48, giá khoảng 0.57). Phách mạnh La♭ thì `D7` mất 2.5.

**Sext tăng**

| Cặp | Trọng số |
|---|---|
| `Fm` / `Fm7` → `Ab+6` | 0.24 / 0.20 |
| `Cm` / `Cm7` → `Ab+6` | 0.06 |
| `Ab+6` → `G` | 0.62 |
| `Ab+6` → `G7` | 0.55 |

`Ab+6` vào từ hạ át, giữa câu, khi gốc Fa đã giữ từ hai ô, ô không phải phách đầu câu và không phải pedal, và đường kết tại ô đó hoặc ô sau ngồi trên {Sol, Rê}. Ô thứ hai của gốc Fa thì `Fm7` chứa {La♭, Đô, Mi♭} với giá đổi chất 0.50 và thắng. Ba ô liền toàn {La♭, Đô, Mi♭} không mở sext tăng, vì Sol mất 2.5 ở ô kế. Fa ở phách mạnh của ô sau thì ô đó là `G7`. Không quá ba móc yếu Fa: móc thứ tư, hoặc móc 4 của 3/4 (trọng 0.8), đảo sang `G7`. Cửa từ chủ 0.06 không thắng một ô thuận thang. Không đăng ký `Db` và `C#dim7`.

**Ba cạnh trưởng**

| Cặp | Trọng số |
|---|---|
| `E7` → `A7` | 0.55 |
| `A7` → `D7` | 0.55 |
| `D7` → `G7` | 0.55 |

`A7` → `Dm` vẫn 0.40. `D7` → `G` vẫn 0.46. Phách mạnh Đô, La hoặc Rê thì chuỗi rẻ hơn về thứ khoảng 0.17. Phách mạnh Fa thì về hợp âm thứ. Không khóa bằng Fa♯.

`allowed` trả `True` với hợp âm không thuộc `extra()`. Mọi `extra()` trả `False` ở pedal và ở phách đầu câu. `Bb` được đứng từ ô thứ hai. `bias` cộng thêm, tuyệt đối dưới 0.1: `volatile` trừ 0.06 cho `Bb`, `Bb7`, `D7`; `rally` trừ 0.04 cho `D7` và `Bb7`. Không mức nào bù phạt 2.5, cũng không bù cửa 0.26 vào Fa thứ khi nốt thang đã nằm trong Fa thứ.

Hợp âm `extra()` nhận sàn 0.08, rồi hợp âm bốn nốt cộng 0.05. `Bb` dừng ở 0.08. `Bb7`, `D7`, `Ab+6` thành 0.13. `minor_bias` không chạy cho `extra()`. `root_step` B không có trong bảng bias thứ; gọi thẳng `minor_bias(Bb)` vẫn lỗi, và đường chọn hợp âm không gọi nó. Không sửa `minor_bias`.

## 11. Âm vực và part

Đã code. Bè tính trên cao độ vang; renderer so số viết với biên đã trừ `semitones`.

| Bè | Vang cho phép | Ghi chú |
|---|---|---|
| Trầm | 40–53 | Gập pitch-class vào dải trước khi viết |
| Trung | 50–65 | Khối ở vùng cao, Phase 3, được vượt 65 nếu còn trong thế tay với giai điệu |
| Cao | 59–81 | Trần đường giá 81. Vang 82–83 chỉ cho chuông Preludio, Phase 3 |
| Trần cứng | 83 | |

Ba voice: Cao 1, Trung 2, Trầm 3. Khi cùng vang, Trầm thấp hơn Trung, Trung thấp hơn Cao. Tremolo được xếp gốc và quãng 5 trong cùng voice Trầm. Part, giọng Muse và transpose đã khóa trong `musicxml.py` và `audio.py`.

Phase 3 thêm mô hình dây (buông 40, 45, 50, 55, 59, 64), phím tối đa 12 / 17 / 19, khoảng phím ≤ 5 cho nốt cùng vang, và khoảng phím theo từng thế bốn móc kép cho đoạn scale. `assert_playable` chỉ báo, không sửa. Profile theo pattern đang chạy: `study`, `elegiaque`, `villa_pattern`, `villa_chord`, `barrios_tremolo`, `barrios_chorale`, `barrios_dance`. Luật bass của profile này không áp cho profile khác.

## 12. Test theo phase

**Đã có, giữ nguyên:** một part nylon; BPM 88 / 100 / 120; biên viết dịch hai chiều; hoán meter và cờ `trio`; nén câu không đảo hướng; tremolo đầy ở 4/4 và ở scherzo 6/8; ngón cái 58 giữ gốc, quãng 5 cùng trùm; chương 60 BPM không tremolo và không tăng tempo; dialect Villa và `dialect_for("barrios")` còn `COMMON`; ép ngón hiếm, không ở câu đầu.

**Phase 1**, trong `test_sonify_guitar.py`:

1. 120 BPM, giai điệu giữ từ hai phách, band `mf`: tremolo đầy. 6/8 vẫn ba trùm nốt đen, mọi móc kép hát.
2. 120 BPM, giai điệu đổi từng móc đơn: arpeggio, không tremolo, không dance.
3. Ô `intro` ở 120: arpeggio, không tremolo.
4. 72, 60 hoặc 66 BPM, 3/4: thánh ca của nhà đó, BPM không đổi, không một trùm tremolo.
5. Barrios, câu tremolo thứ ba liên tiếp: thánh ca.
6. Sor, chương chậm hoặc `selloff` hoặc `trio` ở thứ: bass đúng mẫu chấm của meter đó. Appoggiatura giải về đúng nốt dữ liệu, tối đa một mỗi câu.
7. Villa, chương chậm: ba bè cùng onset ở móc 0; ở 3/4 không có khối ở móc 2.
8. `calm` ở 6/8, 120, band `f`, giai điệu giữ nốt: tremolo, không hemiola.

**Phase 2**, harmony trong `test_harmony.py`, điệu trong `test_sonify_guitar.py`:

1. `dialect_for("barrios")` là `BarriosDialect`. `classic` và symphony ở thứ không sinh `Bb`, `Ab+6`, `D7`. `extra()` thứ đúng bốn tên. `extra()` trưởng rỗng. Villa vẫn sinh `Csus4` đúng các ca đã khóa.
2. Sàn `extra()`: `Bb` 0.08; `Bb7`, `D7`, `Ab+6` 0.13. Không test gọi `minor_bias(Bb)`.
3. Thứ, sau `Fm`, phách mạnh trong {Si♭, Rê, Fa}: `Bb`. Thêm La♭: `Bb7`.
4. Thứ, sau `Ab`, phách mạnh Rê, móc khác trong {Rê, Đô}: `D7`. Phách mạnh La♭: không `D7`.
5. Thứ, {La♭, Đô, Mi♭}, giữa câu, gốc Fa đã giữ từ hai ô, ô sau trên {Sol, Rê} hoặc đường kết tại ô này: `Ab+6`. Ô thứ hai của gốc Fa: `Fm7`. Ô mở section: không `Ab+6`. `Ab+6` không đi từ `Ab` và không đứng hai ô. Ô sau là `G` hoặc `G7`.
6. Trưởng, sau `A7`, phách mạnh Đô, La hoặc Rê: `D7`. Phách mạnh Fa: `Dm` hoặc `Dm7`.
7. `color_credit` Barrios là 0. `transpose_chord` của `Ab+6` giữ Fa♯.
8. 4/4, trên 100, câu nốt chạy, `rally`: dance, đúng các móc đã khóa sau khi đọc tổng phổ. Cao trên móc chẵn trùng nốt dữ liệu. `calm`: không dance. 3/4: không dance.
9. 6/8, 120, band `mp`, câu ngân: tremolo, không polca. Cùng tempo, band `f`, câu nốt chạy: hemiola, đệm chỉ móc kép 0, 4, 8. Cùng tempo, band `f`, câu ngân: tremolo.
10. Ô dance rơi đúng một quãng 5: 4/4 móc kép 15, 6/8 móc kép 11, là Trầm nửa cung dưới gốc sau. Profile `study` báo lỗi; `barrios_dance` im.

**Phase 3:** nốt đích của scale trùng nốt dữ liệu; nốt đầu được lệch và test không đòi nó trùng dữ liệu; phách mạnh trong đoạn giữ cao độ; không section nào quá khoảng 15% ô chạy; chuông tính bằng `bell_budget`, tách khỏi hạn một nốt mỗi hai ô; cụm cùng vang gán được dây, khoảng phím ≤ 5, trừ ngoại lệ tremolo đã khóa; bass Élégiaque và nốt dẫn của Villa hoặc của `barrios_dance` đạt ở đúng profile và lỗi ở `study`.

## 13. Nghe

Phase 1: `1D` Barrios, câu ngân thì tremolo liền, bass đầu mỗi nốt đen; câu nốt ngắn vẫn arpeggio. Chương chậm 3/4 của cả ba nhà hát hợp âm, không tremolo, không bị kéo nhanh. Sor `selloff` nghe ra bass chấm. Mở bài Barrios chưa cần chuông.

Phase 2: phiên thứ, ô {Si♭, Rê, Fa} sau Fa thứ là một ô Si♭ rồi đi tiếp, không có ô Rê♭. Chuỗi át đi tiếp khi giá trên Đô, La hoặc Rê, và về thứ khi giá trên Fa. `1D` câu chạy ở `rally` nghe lệch phách; câu ngân không bị levada cắt. Scherzo band `f` chỉ nghe hemiola khi giai điệu đang chạy. `calm` không dày hơn Phase 1.

Phase 3: đoạn chạy rơi đúng phách mạnh, rồi còn nhận ra đường giá. Preludio có chuông khi phiên có biên độ, và nhường câu đầu. Vòng Villa không che nốt Cao. Lần lặp Grand Solo nghe dày hơn, khung phách mạnh vẫn là khung cũ.
