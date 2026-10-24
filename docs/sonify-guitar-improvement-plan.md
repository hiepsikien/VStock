# Kế Hoạch Cải Thiện Guitar Sonification: Khung "One-Pattern Flow", Intro/Outro 3 Tác Gia & Tinh Chỉnh Pattern

> **Tài liệu tham chiếu**: [`docs/sonify-improve.txt`](./sonify-improve.txt), [`docs/sonify-classical-guitar.md`](./sonify-classical-guitar.md)
> **Mục tiêu**: Khắc phục 4 vấn đề cốt lõi khi nghe thực tế phần Guitar cổ điển (Sor, Barrios, Villa-Lobos):
> 1. Phần Intro vào có từ 4 nốt trở lên đánh mạnh, lặp lại và thiếu tính âm nhạc.
> 2. Bản nhạc ngắn `1D` (~1.2–1.5 phút) chuyển quá nhiều pattern khiến cấu trúc bị vỡ vụn.
> 3. Việc chuyển tiếp giữa các pattern còn gượng, gãy cục.
> 4. Bản thân các pattern chưa đủ rõ nét và sắc sảo về thế bấm/ngón đàn.

---

## Phần 1: Phân Tích Nguyên Nhân Gốc Rễ Trong Code Hiện Tại

### 1.1. Nguyên nhân Intro đánh mạnh và lặp lại ≥ 4 nốt (`render.py`, `guitar.py`, `guitar_patterns.py`)
Trong code hiện tại có **3 lỗi chồng lên nhau** ở các ô mở đầu (`intro` / `warmup`):

1. **Dữ liệu phẳng ở vùng đệm mở đầu (`backend/app/sonify/render.py`)**:
   - Hàm `assign_daily_ambient_bars` và `_assign_framed` để trống các ô `intro`/`warmup` (`group = []`, gồm 2 ô đầu ở `1D` và 4–6 ô đầu ở `1M`/`3M`/`1Y`).
   - Khi lấy cao độ (`render.py` dòng 1039–1050), các ô trống lấy `closes = [held_close]` (`bars[0].close`), khiến **toàn bộ 2–6 ô đầu lặp đi lặp lại duy nhất 1 cao độ phẳng**, và cao độ đó tiếp tục lặp sang cả đầu ô thân bài (`bar 2` ở `1D` hoặc `bar 4` ở `1M`).
2. **Lỗi gán nhầm lực đánh cực đại (`_MELODY_APEX = 72`) cho toàn bộ Intro (`backend/app/sonify/guitar.py`)**:
   - Hàm `_apex_eighths(phrases)` đánh dấu toàn bộ `phrase.apex` của mỗi câu để gán `velocity = _MELODY_APEX = 72` (mức mạnh nhất của guitar, thay vì `_MELODY = 64` hay `p = 48`).
   - Vì cả câu `intro` chỉ có 1 cao độ phẳng duy nhất (1 `Run` kéo dài hết vùng `intro`), `phrase.apex` chính là **toàn bộ `Run` đó**. Hệ quả là mọi móc đơn trong `intro` đều bị coi là đỉnh (`apex`) và bị đánh ở `velocity = 72`.
3. **Cắt rời từng ô không nối `tie`, biến thành 4–6 cú bổ mạnh liên tiếp (`backend/app/sonify/guitar_patterns.py`)**:
   - Khác với Symphony/Jazz/Minimalist đi qua `apply_daily_frame` / `apply_span_frame` (nối `tie` mượt từ `p -> mp`), Guitar bị loại trừ (`if variant != "guitar":` ở `render.py:1142`) và chỉ chạy nhánh `"pedal"` cắt rời theo từng ô nhịp (`_sustain(ctx.melody, bar * epb, (bar + 1) * epb, ...)`).
   - Kết hợp với việc Barrios chèn thêm chuông (`_insert_bells`) cắt đôi nốt giữ để gõ ở `velocity = 72`, tai người nghe bị dội **4–6 phát gảy mạnh cùng một cao độ liên tiếp** ngay khi mở bài.

### 1.2. Nguyên nhân bản ngắn `1D` bị vỡ vụn do đổi quá nhiều pattern (`guitar_patterns.py`)
- Hàm `plan_phrases` cắt một bản `1D` (30 ô thân bài) thành **8 đến 12 câu (`Phrase`) ngắn**, mỗi câu chỉ dài 2–4 ô nhịp (khoảng **4–8 giây**).
- Hàm `_patterns` và `_select_body` (`guitar_patterns.py` dòng 398–479) đang **chọn lại pattern trên TỪNG `Phrase` riêng lẻ**:
  - Câu 1 (bắt buộc ở `bpm >= 90`): `preludio` / `villa_pattern` / `study`.
  - Câu 2 (có 1 nốt giữ $\ge 4$ móc đơn): nhảy sang `tremolo`.
  - Câu 3 (các nốt đều $< 4$ móc đơn): nhảy sang `choro` (dance).
  - Câu 4 & 5: quay lại `tremolo`.
  - Câu 6: bị luật *"sau 2 câu tremolo liên tiếp phải nghỉ"* ép nhảy sang `andante` (hợp âm khối nhà thờ).
  - Cộng thêm lớp phủ `scale` và `perpetual` cắt ngang câu.
- Với **Villa-Lobos**, bất kỳ câu 2 ô nào có cửa sổ thanh khoản rơi vào `band == "p"` là lập tức nhảy từ `villa_pattern` sang `chord_melody`, tới ô sau lên `mp` lại nhảy về `villa_pattern`.
- Điều này tạo ra hiện tượng *"fragmented noise"*, đi ngược lại nguyên lý **"One Pattern – Multi Dimensions"** (80–90% thời lượng của một tiểu phẩm Guitar cổ điển giữ 1 Pattern chủ đạo).

### 1.3. Nguyên nhân chuyển pattern còn gượng và gãy cục (`guitar_patterns.py`)
- Hàm `_transitions` (`dòng 2393–2425`) xử lý biên giữa 2 pattern bằng cách **xóa trắng móc đơn cuối cùng của câu trước** (`_silence(lead, eighth)` và `_silence(support, eighth)`) rồi sang đầu ô sau đổi đột ngột sang kết cấu tay phải mới. Trên MIDI/MuseScore, việc cả bè giai điệu lẫn bè đệm đột ngột câm 1 móc đơn trước vạch nhịp nghe như bị "vấp đĩa" (stutter) thay vì lấy hơi tự nhiên.
- Hàm `_taper` của Tremolo (`dòng 2427–2457`) cắt 4 móc đơn cuối và thay bằng vòng `_pool` thô với nguyên mức âm lượng `_MELODY` / `_BASS`, thiếu sự giảm tốc/giảm lực (`decrescendo`) và thiếu **Dây buông neo (Open-String Anchor)** hoặc **Bội âm (Harmonics)**.

### 1.4. Nguyên nhân các pattern chưa rõ nét và thiếu chiều sâu (`guitar_patterns.py`)
1. **Đường giai điệu phẳng, thiếu biểu cảm câu nhạc**: Hầu hết các pattern đều gọi `_sustain(ctx.melody)` với velocity phẳng `64` (và `72` ở đỉnh), không có đường cong lực gảy (`swell` từ đầu câu lên đỉnh câu rồi lắng xuống cuối câu).
2. **Thế bấm tay phải (`p-i-m-a`) chưa ra chất đặc trưng của từng tác gia**:
   - **`villa_pattern` (*Étude No. 1*)**: Hiện chỉ là `_render_study_bar` cộng thêm 1 nốt bè Trung lấp chỗ trống (`dòng 619–637`), nghe đều đều trên 1 dây trong thay vì một **chuỗi arpeggio cuộn sóng lên-xuống liên tục** qua các tầng dây trầm – trung – cao với độ nhấn phách rõ nét.
   - **`preludio` (*La Catedral*)**: Bè Trung (`_preludio_inner`, `dòng 2282–2293`) đang gảy lặp đi lặp lại 1 nốt hợp âm dưới giai điệu suốt 8 móc đơn, chưa tạo được **mô-típ rải dây 6 nốt / 8 nốt trầm mặc, giàu tính đối âm** dưới nốt giai điệu ngân dài của Barrios.
   - **`elegiaque` (*March chấm dôi của Sor*)**: Nhịp chấm dôi (`dài 3 móc – ngắn 1 móc`) mới chỉ nằm đơn độc ở nốt Bass, trong khi bè Trung lại rải móc đơn lệch ra ngoài (`_inner_eighths`), làm nhòe mất nhịp hành khúc chấm dôi uy nghi.
   - **`chord_melody` (Villa) & `andante` (Barrios)**: Các hợp âm khối chập xuống cùng một mức velocity phẳng (`60 / 56 / 64`), thiếu sự phân tầng lực ngón tay (làm nổi rõ bè giai điệu trên cùng) và thiếu độ co giãn mật độ/lực đánh theo biến động dữ liệu.

---

## Phần 2: Phương Án & Lộ Trình Triển Khai (2 Bước)

Theo xác nhận, kế hoạch được chia làm **2 bước tuần tự** để kiểm tra và nghe thực tế sau mỗi bước:
- **Bước 1**: Kiến trúc lại Intro/Outro (3 tác gia × 2/4 ô), áp dụng khung **Monothematic `1D` / One-Pattern Flow** và làm mượt cơ chế chuyển đoạn.
- **Bước 2**: Đi sâu tinh chỉnh ngón đàn (`p-i-m-a`), voicing và độ động biểu cảm của từng nhóm Pattern.

---

### BƯỚC 1: Kiến Trúc Intro/Outro (3 Tác Gia × 2/4 Ô), Khung "One-Pattern Flow" & Chuyển Đoạn Mượt

#### 1. Thiết kế bộ Intro & Outro chuẩn mực theo 3 Tác gia (2 ô cho `1D`/`1Y`, 4 ô cho `1M`/`3M`)
Loại bỏ hoàn toàn nhánh `"pedal"` lặp nốt đánh mạnh `velocity 72` và áp dụng quy tắc **Safety Buffer** (`docs/sonify-improve.txt` dòng 190–395), không đọc dữ liệu phẳng ở vùng đệm:

| Tác gia (`ensemble`) | Intro 2 Ô nhịp (`1D`, `1Y`) | Intro 4 Ô nhịp (`1M`, `3M`) | Outro 2 Ô nhịp (`1D`, `1Y`) | Outro 4 Ô nhịp (`1M`, `3M`) |
|---|---|---|---|---|
| **Fernando Sor (`classic`)**<br>*Cổ điển, chuẩn mực, khúc chiết* | **Direct Classical Entry**:<br>• **Ô 1**: Dậm Bass Chủ (`I`, `p`) ở phách đầu, rải nhẹ quãng đôi/hợp âm thanh thoát.<br>• **Ô 2**: Qua Át (`V7`, `mp`) kèm câu dẫn ngắn 3–4 nốt vào thẳng nốt đầu thân bài. | **Formal Sor Cadence**:<br>• **Ô 1**: Hợp âm Chủ (`I`) gọn gàng ở dải trung (`p`).<br>• **Ô 2**: Bass bước xuống liền bậc kết hợp hợp âm phụ.<br>• **Ô 3**: Hợp âm `V7` với nhịp chấm dôi nhẹ (`mp`).<br>• **Ô 4**: Giải về `I` ngân nhẹ đón thân bài. | **Direct Cadential End**:<br>• **Ô 1**: Chuyển dứt khoát sang `V7` dạng hợp âm gọn.<br>• **Ô 2**: Dậm hợp âm Chủ (`I`) trọn vẹn ở phách 1 rồi ngắt gọn. | **Formal Sonata Coda**:<br>• **Ô 1**: Bass bước chắc chắn `I → IV → V`.<br>• **Ô 2–3**: Chuỗi `V7` nhịp chấm dôi nén ở dải cao.<br>• **Ô 4**: Giải thoát về hợp âm Chủ (`I`) ngân tự do. |
| **Agustín Barrios (`barrios`)**<br>*Lãng mạn, thánh đường, bội âm* | **Harmonic Bell Entry**:<br>• **Ô 1**: Chạm nhẹ 2–3 nốt **Bội âm (Harmonics)** cao trong trẻo (`p`, vel `48–52`) ngân tự do.<br>• **Ô 2**: Bass trầm dậm nhẹ nốt gốc dưới nền bội âm đang ngân → ngón rải đầu tiên mở ra êm ái. | **Chant & Arpeggio Prelude**:<br>• **Ô 1**: Nốt Harmonics cao ngân dài 2 phách đầu (`p`).<br>• **Ô 2**: Bè Bass đi một nét giai điệu trầm (`Cantabile`) từ trầm lên trung.<br>• **Ô 3**: Rải nhẹ hợp âm màu (m9 / dim7) hơi thưa.<br>• **Ô 4**: Ổn định nhịp nối khớp vào Pattern chính. | **Ethereal Harmonics End**:<br>• **Ô 1**: Pattern chính chậm lại (`Ritardando`), Bass trầm gảy 1 lần ngân dài.<br>• **Ô 2**: Điểm Hợp âm Bội âm (Harmonics) mỏng manh tan dần (`Morendo`, `pp`). | **Sacred Chant Outro**:<br>• **Ô 1**: Pattern chính thưa dần thành arpeggio chậm (`p → pp`).<br>• **Ô 2**: Câu giai điệu trầm (`Cantabile`) thì thầm.<br>• **Ô 3**: Hợp âm m9/dim ngập ngừng.<br>• **Ô 4**: Giải về hợp âm Trưởng chủ (**Picardy Third**) dạng Harmonics ngân dài. |
| **Heitor Villa-Lobos (`villa`)**<br>*Hiện đại Brazil, dây buông, giàu sức sống* | **Open-String Voicing Entry**:<br>• **Ô 1**: Rải nhẹ một hợp âm mở đặc trưng (`Em9 / Am9 / Cmaj9`) từ trầm lên cao (`p`).<br>• **Ô 2**: Nhấn nhẹ 2 nhịp hợp âm chặn lệch nhịp (`Syncopation`, `mp`) → thả về Bass buông kích hoạt thân bài. | **Choro / Étude Movement Entry**:<br>• **Ô 1**: Hợp âm mở dải tần rộng (`p`).<br>• **Ô 2**: Dịch chuyển nguyên khối hợp âm song song (`Parallel voicing`) trên nền dây buông.<br>• **Ô 3**: Rải vút ngón tăng dần từ trầm lên trung.<br>• **Ô 4**: Nhấn hợp âm phách 1 tạo đà cho thân bài. | **Abrupt Choro / Open Resolve**:<br>• **Ô 1**: Rải vút lên cao hoặc lùi hợp âm.<br>• **Ô 2**: 2 cú hợp âm chặn lệch nhịp (`Syncopation`) hoặc hợp âm mở dứt khoát. | **Parallel Slide & Open Ring-out**:<br>• **Ô 1**: Dịch khối hợp âm song song lùi dần từ cao xuống thấp.<br>• **Ô 2**: Xả áp lực về các dây buông trầm ngân tự do.<br>• **Ô 3**: Rải dày đầy đặn trên hợp âm chủ mở.<br>• **Ô 4**: Ngân hợp âm chủ + điểm 1 nốt Harmonics trầm khép bài. |

#### 2. Quy tắc Phân bổ Pattern theo Thời lượng ("One-Pattern Flow")
- **`1D` (Micro-piece ~1.2–1.5 phút, 30 ô thân bài) — Monothematic (1 Pattern Chủ Đạo duy nhất)**:
  - Giữ **1 Pattern chủ đạo xuyên suốt 100% thân bài** (không nhảy qua lại giữa các câu 2–4 ô nhịp, bỏ luật cắt tremolo sau 2 câu ở `1D`, bỏ luật nhảy sang `chord_melody` chỉ vì 1 cửa sổ có `band == "p"`):
    - **Sor (`classic`)**: `elegiaque` (nếu phiên `selloff` giảm sâu), `cantabile` (nếu phiên `calm` đi ngang biên độ hẹp), `study` (các phiên `rally` / `volatile` hoặc mặc định).
    - **Villa-Lobos (`villa`)**: `chord_melody` (nếu toàn phiên `calm` thanh khoản thấp), `villa_pattern` (*Étude No. 1* xuyên suốt cho các phiên có sóng).
    - **Barrios (`barrios`)**: `tremolo` (*Ultimo Tremolo* xuyên suốt nếu phiên có xu hướng/nốt giữ chủ đạo), `choro` (nếu toàn phiên `volatile` nhảy giá liên tục ở `bpm > 100`), hoặc `preludio` (*La Catedral* xuyên suốt nếu phiên êm đềm/tích lũy).
- **`1M`, `3M`, `1Y` (Standard Chapter ~2.5–4 phút) — Binary/Ternary Form (A – B – A, tối đa 2 Pattern)**:
  - **Phần A (70–80% thời lượng — Đoạn mở & Đoạn tái hiện)**: Duy trì **1 Pattern chính** xuyên suốt toàn bộ section.
  - **Phần B (20–30% thời lượng — Đoạn giữa `section.trio` / `section.bridge`)**: Chuyển sang **1 Pattern tương phản** (VD: `thumb_cantabile` hát ngón cái ở bè trầm, hoặc `vals` / `andante` / `elegiaque`), sau đó quay lại **Pattern A**.
- **`1W` (Extended Suite ~5–6 phút, 5 phiên)**:
  - Khóa pattern theo từng **Phiên ngày (32 ô/phiên)** dựa trên `character_at` của phiên đó (tối đa 2–3 pattern đối lập trên toàn bộ 5 phiên), không đổi vụn bên trong từng phiên.

#### 3. Biến đổi Đa chiều bên trong Pattern chủ đạo (Tỷ lệ 80 / 15 / 5)
- **80% Khung gầm cố định (Core Identity)**: Duy trì hình thái ngón tay phải ổn định để tai người nghe vào trạng thái thư giãn (Flow state).
- **15% Biến đổi theo Dữ liệu (Data-driven Variations)**:
  - **Biến động giá (Price Action)** điều khiển tiến trình hợp âm (`ChordSlot`) và độ mở âm vực (giá tăng → voicing mở lên cao; giá giảm → chìm xuống âm vực trầm/thứ).
  - **Thanh khoản (`band` `p → f`) và Đường cong câu (`Phrase Swell`)** điều khiển lực gảy (`velocity`) và mật độ nốt đệm bên trong cùng pattern đó.
- **5% Điểm nhấn / Trang điểm (Accents & Embellishments)**: Chỉ xuất hiện ở cực điểm (`Breakout` / `Apex` cao nhất của bài): một câu chạy `Scale` ngắn lao vào đỉnh hoặc nhấn lệch nhịp `Tresillo` / `Hemiola` 1–2 ô rồi trở về ngay dòng chảy chính.

#### 4. Kỹ thuật Chuyển đoạn mượt (Transition Bridges)
1. **Bỏ cơ chế đục lỗ câm (`_silence`) cứng nhắc** ở cuối mỗi câu.
2. **Dây buông neo (Open-String Bass Anchor)**: Tại biên chuyển giữa Intro → Body, A → B → A, và Body → Outro, giữ nốt Bass trầm (ưu tiên dây buông hoặc gốc/bậc 5) ngân làm cầu nối hoặc dẫn liền bậc mượt vào phách 1 của đoạn mới.
3. **Giảm tốc kết cấu tự nhiên (Gradual Textural Tapering)**: Ở ô cuối cùng trước khi khép đoạn hoặc chuyển từ mật độ cao (`tremolo` / `dance`) sang đoạn tĩnh (`B` hoặc `Outro`), giãn dần tiết tấu (`16th → 8th → quarter`) kèm giảm nhẹ lực gảy (`decrescendo`).

---

### BƯỚC 2: Làm Sâu Và Sắc Sảo Hóa Từng Nhóm Pattern (Sau khi nghe duyệt Bước 1)

1. **Nhóm Arpeggio (`study`, `villa_pattern`, `preludio`)**:
   - **`villa_pattern` (*Étude No. 1*)**: Thiết kế vòng dây cuộn lên-xuống liên tục qua 3 tầng (Trầm `p` – Trung thấp `i` – Trung cao `m` – Cao `a`), kết hợp ngân chồng `campanella` trên các dây khác nhau và nhấn `tresillo` `3+3+2` sắc nét khi biến động mạnh.
   - **`preludio` (*La Catedral*)**: Tạo mô-típ rải dây đối âm liên tục ở bè Trung (thay vì lặp 1 nốt phẳng) bên dưới nốt giai điệu ngân dài và trên nền Bass trầm ngân 2 ô nhịp.
   - **`study` (Sor)**: Rõ nét hóa đối đáp giữa Bass phách mạnh (`1, 3`), bè Trung đi quãng 3/quãng 6 mềm mại và bè Cao hát đường giá có đường cong `swell`.
2. **Nhóm Thánh ca & Hành khúc (`elegiaque`, `chord_melody`, `andante`, `cantabile`, `thumb_cantabile`)**:
   - **`elegiaque` (Sor)**: Đồng bộ nhịp hành khúc chấm dôi (`dài 3 móc – ngắn 1 móc`) giữa cả Bass và hợp âm bè Trung để tạo bước đi uy nghi, kết hợp đường bass lament đi xuống liền bậc và nốt tựa `appoggiatura` biểu cảm.
   - **`chord_melody` (Villa) & `andante` (Barrios)**: Phân tầng lực gảy trong mỗi khối hợp âm (bè giai điệu nổi lên trên nền hợp âm đệm ấm phía dưới), mở rộng voicing dọc cần đàn theo đà tăng của giá.
   - **`thumb_cantabile` (Villa/Barrios) & `cantabile` (Sor)**: Tối ưu hóa khoảng cách âm vực giữa ngón cái `p` hát ở vùng Cello (`48–64`) và hợp âm điểm phách yếu phía trên để không bị chồng lấp tần số.
3. **Nhóm Tremolo & Điệu nhảy (`tremolo`, `choro`, `polca`, `vals`)**:
   - **`tremolo` (Barrios)**: Bổ sung đường cong động lực học (`phrase swell` và `dynamic breathing` từ `p` đến `ff`) cho chuỗi `a-m-i` thay vì giữ cứng một mức `52-55-54-52` xuyên suốt cả bài.
   - **`choro`, `polca`, `vals` (Barrios)**: Tinh chỉnh độ nảy syncopation của bè Trung và đường Bass đi bộ/dẫn bán cung để ra đúng chất dân gian Nam Mỹ.
