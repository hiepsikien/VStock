# Kế Hoạch Thiết Kế & Triển Khai Scale Engine Cho Guitar Cổ Điển (`docs/sonify-guitar-scales-plan.md`)

> **Tài liệu tham chiếu**: [`docs/sonify-classical-guitar.md`](./sonify-classical-guitar.md), [`docs/sonify-guitar-improvement-plan.md`](./sonify-guitar-improvement-plan.md), [`docs/sonify-guitar-bach-plan.md`](./sonify-guitar-bach-plan.md), [`docs/sonify-guitar-phase2-brouwer-plan.md`](./sonify-guitar-phase2-brouwer-plan.md)
> **Mục tiêu**: Xây dựng cơ chế chạy Scale nhanh cho những đoạn **tăng giá và giảm giá đột ngột** trên toàn bộ 5 composer của biến thể `guitar` (`bach`, `classic`/Sor, `villa`, `barrios`, `brouwer`), phản ánh trung thực nhịp hồi/điều chỉnh (`retreat`) thực tế của giá cổ phiếu, giới hạn mật độ tối đa **30%** bản nhạc, và hòa quyện mượt mà (`mix well`) với các pattern liền trước và liền sau.

---

## 1. Phân Tích Hiện Trạng Trong Codebase (`backend/app/sonify/guitar_patterns.py`)

Hiện tại, cơ chế chạy scale trong phần Guitar đang tồn tại các hạn chế sau:
1. **Điều kiện kích hoạt rời rạc và quá hẹp (`_allocate_overlays`)**:
   - Chỉ nhìn tổng biên độ của cả câu (`rise = peak - min >= MIN_RISE`) kết hợp với `band in {"mf", "f"}` thay vì phát hiện trực tiếp các **đợt tăng/giảm giá dốc, đột ngột** (surge / plunge).
   - Bị khóa cứng theo từng composer: Sor (`classic`) chỉ chạy khi đạt `Grand Solo level 2`; Villa-Lobos (`villa`) chỉ chạy khi `mood == "volatile"` và `band == "f"`; Brouwer (`brouwer`) và phần lớn các pattern của Bach (`bach`) chưa dùng chung bộ lập lịch scale overlay này.
2. **Đường nét một chiều và độ dài cố định (`_scale_line`, `_run_slots`)**:
   - Chỉ tạo một chuỗi ngắn 4–6 nốt đi thẳng một chiều vào phách mạnh mục tiêu (`target`), chưa bao phủ được các con sóng kéo dài **từ dưới 1 ô nhịp (sub-bar) đến 1, 2, 3 hoặc tối đa 4 ô nhịp**.
   - Chưa phản ánh được cấu trúc **"tiến – retreat ngắn – tiến tiếp"** (hoặc ngược lại ở chiều giảm) sinh ra từ chính những nhịp chốt lời / hồi kỹ thuật thật của giá cổ phiếu.
3. **Ngân sách & Hòa quyện kết cấu (`_apply_scale_run`)**:
   - Đang giới hạn cứng ở `15%` số ô nhịp mỗi section và tối đa `2` lần trong bản ngắn (`_cap_accents(..., limit=2)`).
   - Khi ghép scale vào (`_splice`), phần bè trầm (`low`) và bè trung (`support`) hoặc bị cắt đột ngột hoặc chỉ xử lý riêng cho Barrios (`_pulse_bass`), thiếu cơ chế chuyển tiếp mượt ở Điểm Vào (Entry), Phần Đệm (Underpinning) và Điểm Ra (Landing/Exit) cho cả 5 composer.

---

## 2. Thiết Kế Chi Tiết Theo Yêu Cầu Đã Xác Nhận

### 2.1. Phạm Vi Áp Dụng & Màu Sắc Thang Âm Theo Từng Composer (5 Guitar Variants)

Cơ chế phát hiện sóng tăng/giảm đột ngột và bộ khung chạy scale được dùng chung cho tất cả **5 composer** trong biến thể `guitar`, nhưng cách chọn các bậc thang âm nối giữa các mốc giá sẽ mang bản sắc riêng của từng tác gia:

| Composer (`ensemble`) | Phong cách & Màu sắc Scale (`scale flavor`) | Quy tắc chọn nốt đi qua (Passing / Retreat Notes) |
|---|---|---|
| **J.S. Bach (`bach`)** | **Baroque Diatonic / Melodic Minor** | Chạy liền bậc chuẩn xác kiểu *tirata* / *Chaconne*; ở giọng Thứ (`mode == "minor"`), khi hướng cục bộ đi lên có thể nâng bậc 6, 7 (*Melodic Minor*) để dẫn về chủ âm, và hạ về tự nhiên (*Natural Minor*) khi đi xuống. |
| **Fernando Sor (`classic`)** | **Classical Diatonic / Harmonic Accent** | Thang âm Diatonic cổ điển trong sáng, rõ nét kiểu *Grand Solo* và *Variations Op. 9*; giữ chặt các nốt hợp âm trên phách mạnh/phách trụ và lấp đầy bằng các bậc thang âm chuẩn mực. |
| **Heitor Villa-Lobos (`villa`)** | **Brazilian Open-String & Modal Diatonic** | Phóng khoáng kiểu *Étude No. 7*; ưu tiên khai thác các bậc thang âm đi qua dây buông cộng hưởng và màu sắc modal (Mixolydian / Dorian tùy hợp âm đang vang). |
| **Agustín Barrios (`barrios`)** | **Romantic Latin & Chromatic Approach** | Lãng mạn Mỹ-Latin; đi liền bậc diatonic kết hợp **nốt dẫn nửa cung (chromatic passing / leading approach)** sát trước nốt trụ hoặc nốt đích (`target`) trên phách mạnh. |
| **Leo Brouwer (`brouwer`)** | **Modern Afro-Cuban Modal** | Mang màu sắc *Estudios Sencillos* / *Elogio de la Danza*; kết hợp thang âm Modal (Dorian, Phrygian / Spanish flavor) và các bước lướt sắc gọn theo hòa âm treo (`sus2`, `add9`, `bVII`). |

> **Lưu ý tương thích Pattern**: Các pattern có cơ chế khóa lưới riêng biệt như `etude1`, `etude11` (lưới sextuplet/16-note cycle cố định của Villa-Lobos) hoặc phần canto chấm dôi đặc trưng đang khóa của *La Catedral Preludio* vẫn giữ quy tắc bảo vệ riêng hoặc chỉ nhận scale ở các vị trí chuyển câu/bứt phá phù hợp để không phá vỡ kết cấu đặc thù.

---

### 2.2. Phát Hiện Tăng/Giảm Đột Ngột & Độ Dài Linh Hoạt (Từ Dưới 1 Ô Nhịp Đến Tối Đa 4 Ô Nhịp)

#### A. Hai cấp độ độ dài theo thời gian thực của đợt biến động giá
Trên trục thời gian của bản nhạc, mỗi ô nhịp (`bar`) chứa `epb` móc đơn (`8` ở nhịp `4/4`, `6` ở nhịp `3/4` và `6/8`). Bộ dò quét trên chuỗi giá (`raw_pitches` và `melody`) ngoài vùng đệm `intro`/`outro` để phát hiện các cửa sổ có tốc độ biến thiên giá lớn ($\left|\Delta \text{pitch}\right|$ cao):

1. **Cấp độ Sub-bar (Không đủ 1 khuôn / dưới 1 ô nhịp: từ `2` đến `epb - 1` móc đơn, thường 1–2 phách)**:
   - Xảy ra khi giá cổ phiếu giật tăng vọt hoặc rơi nhanh trong vài nến ngắn ngủi rồi chững lại ngay trong lòng một ô nhịp (hoặc vắt qua vạch nhịp vào phách mạnh đầu ô kế tiếp).
   - Được map thành một **câu chạy lướt ngắn (pickup run / tirata)** từ `2` đến `epb - 1` móc đơn (tương ứng 4–8 nốt móc kép hoặc 3–6 nốt móc đơn tùy tempo), xuất phát ngay sau phách mạnh liền trước và đáp thẳng vào đỉnh/đáy của cú giật giá.
2. **Cấp độ Multi-bar (1, 2, 3 hoặc tối đa 4 ô nhịp — từ `1 * epb` đến `4 * epb` móc đơn)**:
   - Xảy ra khi cổ phiếu có một đợt sóng tăng tốc (rally surge) hoặc bán tháo (selloff plunge) kéo dài liên tục qua 1, 2, 3 hoặc 4 ô nhịp.
   - Nếu một xu hướng kéo dài hơn 4 ô nhịp, thuật toán cắt lấy **cửa sổ tối đa 4 ô nhịp** có độ dốc và biên độ biến thiên lớn nhất ($\max \left|\Delta \text{pitch}\right|$) để câu scale luôn giữ được sự cô đọng, kịch tính.

#### B. Lựa chọn Móc đơn (Eighths) hay Móc kép (Sixteenths) theo Nhịp, Tempo và Độ dài vật lý
Thời lượng vật lý của đoạn scale được tính theo công thức:
$$\text{Duration (seconds)} = \text{eighths} \times \frac{30}{\text{bpm}}$$

Quy tắc chọn mật độ hạt nốt (subdivision):
- **Móc kép (`sixteenths`, `0.25` beat — 2 nốt trên mỗi eighth)**:
  - Áp dụng cho các đoạn **Sub-bar (< 1 ô nhịp)** hoặc **1–2 ô nhịp** khi $\text{BPM} \ge 88$ (trừ nhịp `6/8` quá nhanh trên `116 BPM` nếu kéo dài nhiều ô), nơi thời gian vật lý ngắn (~1–4 giây) và cần mật độ nốt nhanh để tạo cảm giác bứt tốc của ngón đàn guitar.
  - Cũng áp dụng cho **ô nhịp cuối (climax bar)** của một đoạn scale dài 3–4 ô nhịp khi giá bứt phá mạnh về đích.
- **Móc đơn (`eighths`, `0.5` beat — 1 nốt trên mỗi eighth) hoặc Kết hợp Tăng tốc (8th $\rightarrow$ 16th)**:
  - Áp dụng khi tempo chậm ($\text{BPM} < 88$), ở nhịp `6/8` nhanh kéo dài, hoặc ở **các ô mở đầu của đoạn scale dài 3–4 ô nhịp** (khi tổng thời gian vật lý kéo dài ~6–10 giây) để câu chạy rõ hạt, có đà tăng tốc tự nhiên thay vì biến thành chuỗi móc kép đều đều quá dài.
  - Tại những bước giá nhảy vọt giữa 2 eighth liền kề ($\left|\text{melody}[e+1] - \text{melody}[e]\right| \ge 3$ bán cung), có thể chẻ cục bộ eighth đó thành 2 móc kép để lấp đầy bậc thang âm nối giữa 2 mức giá mà không tạo bước nhảy hẫng.

---

### 2.3. Cấu Trúc "Up – Retreat – Up" & "Down – Retreat – Down" Bám Sát Dữ Liệu Giá Thật (Không Nhân Tạo)

1. **Nguyên tắc trung thực với dữ liệu (Data-True Retreat)**:
   - **Không tự bịa retreat nhân tạo** nếu chuỗi giá trong đoạn đó tăng hoặc giảm thẳng tắp một chiều.
   - Khi quét tìm các đoạn tăng/giảm đột ngột (đặc biệt ở các cửa sổ từ 1 đến 4 ô nhịp), bộ dò đánh giá dựa trên **biên độ ròng (Net Span = $\text{end\_pitch} - \text{start\_pitch}$) và độ dốc tổng thể**, cho phép bên trong con sóng chứa **1–2 nhịp điều chỉnh / hồi giá ngắn thực tế** của cổ phiếu:
     - **Chiều đi lên (Upward Surge with Pullback)**: Xu hướng chính đi lên mạnh ($\text{net rise} \ge \text{threshold}$), ở giữa có những điểm giá cổ phiếu giảm nhẹ ngắn hạn ($\text{pitch}[k] < \text{pitch}[k-1]$ trong 1–3 eighths) rồi lập tức vượt đỉnh đi lên tiếp.
     - **Chiều đi xuống (Downward Plunge with Rebound)**: Xu hướng chính đi xuống mạnh ($\text{net drop} \ge \text{threshold}$), ở giữa có những điểm giá cổ phiếu nảy hồi kỹ thuật ngắn ($\text{pitch}[k] > \text{pitch}[k-1]$ trong 1–3 eighths) rồi tiếp tục rơi sâu hơn.
2. **Cách dựng đường Scale qua các mốc giá thật (Waypoint Interpolation)**:
   - Mỗi mốc eighth-note $e$ trong đoạn scale giữ vai trò là **mốc dẫn hướng (waypoint)** từ dữ liệu giá (`raw_pitches` / `melody`).
   - Giữa các mốc waypoint liên tiếp:
     - Khi mốc giá đi lên ($\text{waypoint}[i+1] > \text{waypoint}[i]$): đường scale bước đi lên theo thang âm của composer.
     - Khi mốc giá thật sự lùi xuống ($\text{waypoint}[i+1] < \text{waypoint}[i]$ — **real retreat**): đường scale **đổi chiều bước lùi xuống đúng theo nhịp giảm của giá**.
     - Khi mốc giá quay đầu đi lên tiếp: đường scale lập tức **đảo chiều bước lên tiếp** hướng về đỉnh.
     - Khi 2 mốc eighth liền kề có giá đi ngang tạm thời ($\text{waypoint}[i+1] == \text{waypoint}[i]$) nằm giữa hai nhịp cùng chiều đang lao đi: thay vì đứng im làm đứt mạch chạy ngón, cho phép nối mượt qua bậc thang âm kế cận trong cùng thế tay để giữ dòng chảy đến mốc giá tiếp theo.

---

### 2.4. Ngân Sách Tối Đa 30% Bản Nhạc (`Budget Cap <= 30%`)

- **Đơn vị tính chính xác theo `eighths`**:
  - Vì một đoạn scale có thể ngắn dưới 1 ô nhịp (ví dụ 4 eighths) hoặc dài 1–4 ô nhịp (8–32 eighths), hạn mức **tối đa 30%** được tính chính xác trên **tổng số eighths của phần thân bài (body eighths, hoặc theo từng section)** và đồng thời kiểm tra trên tổng số eighths toàn bản nhạc:
    $$\text{max\_scale\_eighths} = \lfloor 0.30 \times \text{total\_eighths} \rfloor$$
- **Xếp hạng ưu tiên (Ranking by Suddenness / Steepness)**:
  - Mọi ứng viên (sub-bar và 1–4 bars) được chấm điểm theo:
    $$\text{Score} = \left|\Delta \text{pitch}\right| \times \text{steepness\_factor} + \text{natural\_retreat\_bonus}$$
  - Các đợt biến động đột ngột mạnh nhất được chọn trước.
  - Hai đoạn scale được chọn phải **cách nhau ít nhất 1 khoảng nghỉ tối thiểu** (ví dụ $\ge \text{epb}$ eighths / 1 ô nhịp thở ở giữa) để bản nhạc có sự tương phản giữa phần pattern nền và phần bứt tốc chạy ngón.

---

### 2.5. Giải Pháp Kỹ Thuật Để Đoạn Scale "Mix Well" Với Pattern Trước Và Sau Nó

Để đoạn scale hòa nhập hoàn toàn vào dòng chảy của bản nhạc mà không gây cảm giác cắt ghép đột ngột, hệ thống xử lý đồng bộ ở **3 vùng tiếp giáp**:

```
[ Pattern Trước ] ──(1. Điểm Vào / Entry)──► [ Đoạn Scale (2. Bè Đệm / Underpinning) ] ──(3. Điểm Ra / Exit)──► [ Pattern Sau ]
```

#### 1. Điểm Vào (Seamless Entry — Từ Pattern trước đi vào Scale)
- **Khớp nối cao độ liền bậc (Stepwise Pitch Handoff)**:
  - Nốt mở đầu của đoạn scale bắt đầu ngay tại cao độ giai điệu đang ngân của pattern trước tại điểm cắt, hoặc cách đúng 1 bậc thang âm (`<= 2` bán cung) hướng về phía con sóng. Tuyệt đối không tạo bước nhảy quãng lớn giữa nốt cuối của pattern trước và nốt đầu của đoạn scale.
- **Giữ nguyên phần mở đầu ô nhịp khi Scale vào ở giữa ô (Sub-bar Dovetail)**:
  - Nếu đoạn scale bắt đầu sau phách 1 (ví dụ từ phách 2 hoặc phách 3), toàn bộ các nốt Bass (`low`) và nốt rải (`support`) của pattern trước ở đầu ô nhịp được **giữ nguyên và ngân tiếp** làm bàn đạp hòa âm cho câu scale cất lên.
- **Lấy đà tiết tấu (Rhythmic Gradation)**:
  - Nếu pattern trước đang ở trạng thái tĩnh/chậm (như `cantabile`, `noviembre`, `andante`) và đi vào một đoạn scale dài $\ge 2$ ô nhịp, phách đầu tiên của đoạn scale có thể mở bằng 2 nốt móc đơn (eighths) trước khi cuốn vào guồng móc kép (sixteenths).

#### 2. Trong Khi Chạy Scale (Accompaniment & Texture — Giữ "Hơi thở" của Composer)
Thay vì xóa trắng toàn bộ bè dưới làm tiếng đàn bị hụt hẫng, hoặc giữ nguyên toàn bộ khiến bị đụng ngón tay:
- **Bè Trầm (`low` - Voice 3) duy trì nhịp mạch hợp âm (Harmonic Pulse)**:
  - Trên các phách mạnh (`strong_eighths`, ví dụ phách 1 và phách 3 trong `4/4`, phách 1 và phách 4 trong `6/8`), bè Bass vẫn gảy nốt Gốc (`Root`) hoặc Bậc 5 (`Fifth`) của hợp âm hiện tại (`chord_at[bar]`), được kiểm tra qua `_playable` để luôn nằm trong cùng thế tay (5 ngăn phím) với các nốt scale phía trên.
  - Với Bach (`bach`): giữ nốt bass đối vị trên phách mạnh dưới câu scale.
  - Với Brouwer (`brouwer`) / Villa-Lobos (`villa`): giữ nốt bass phách đầu (và dây buông nếu hợp hợp âm) ngân ấm dưới đường chạy ngón.
- **Bè Giữa (`support` - Voice 2) nhường đường thông minh (Selective Thinning)**:
  - Trong suốt khoảng thời gian bè Cao (`lead`) chạy móc kép dày đặc, các nốt rải `support` nằm trùng thời điểm được lược bỏ (`_drop_overlap`) để giải phóng ngón `i-m-a` của tay phải cho câu scale.
  - Riêng tại **phách mạnh đầu tiên mở đầu đoạn scale** (hoặc khi đoạn scale tạm đi bằng móc đơn ở nhịp đầu), có thể giữ 1 nốt hợp âm bè Trung hợp thế tay để tiếng vào dày dặn.

#### 3. Điểm Ra (Landing & Exit — Từ Scale trở lại Pattern sau)
- **Hội tụ chính xác vào Nốt Trụ trên Phách Mạnh (Target Downbeat / Strong-Beat Resolution)**:
  - Nốt kết thúc của đoạn scale luôn đáp đúng vào **nốt giai điệu chính (`melody[target]`) tại một phách mạnh** (đầu ô nhịp kế tiếp hoặc phách mạnh giữa ô nhịp).
  - Ngay tại phách mạnh đáp đích đó, **pattern phía sau lập tức tiếp quản đồng bộ**: bè Bass của pattern sau đánh phách mạnh cùng lúc với nốt đích của scale, và bè Trung (`support`) bắt đầu chu kỳ rải ngón từ ngay phách yếu kế tiếp.
- **Vuốt động lực học (Dynamic Bridging) & Nhịp thở (Post-Scale Breath)**:
  - **Crescendo khi đi lên**: Lực gảy (`velocity`) của đoạn scale đi lên khởi đầu ngang với mức velocity của pattern liền trước và tăng dần đều (`swell`) lên tới `_MELODY_APEX` (`72`) tại nốt đích trên phách mạnh.
  - **Shaping khi đi xuống**: Đoạn scale đi xuống khởi đầu rõ nét tại đỉnh rơi và vuốt về mức lực nền của pattern kế tiếp (hoặc nhấn nhẹ ở đáy nếu rơi vào hợp âm kịch tính của `selloff`), tránh bị gắt hoặc rơi tõm.
  - Nếu nốt đích của scale rơi vào một điểm kết câu (`phrase.closes`), nốt đích được **ngân dài tự nhiên** trên nền rải arpeggio nhẹ của pattern mới, tạo khoảng thở âm nhạc hoàn chỉnh.

---

## 3. Các File Dự Kiến Thay Đổi Khi Triển Khai Code

1. **`backend/app/sonify/guitar_patterns.py`**:
   - Nâng cấp bộ dò ứng viên scale trong `_allocate_overlays` (hoặc hàm chuyên biệt `_detect_scale_passages` & `_allocate_scale_overlays`) để quét các đợt tăng/giảm đột ngột từ **sub-bar (`2..epb-1` eighths)** đến **1–4 bars (`epb..4*epb` eighths)** cho cả **5 composer** (`bach`, `classic`, `villa`, `barrios`, `brouwer`).
   - Áp dụng ngân sách **tối đa 30%** (`<= 0.30 * total_eighths`) tính theo số eighths thực tế, xếp hạng theo độ dốc và biên độ.
   - Nâng cấp `_scale_line` và `_apply_scale_run` để:
     - Dựng đường scale bám sát các mốc giá thật trong cửa sổ (giữ nguyên các nhịp **retreat/hồi giá thật** của cổ phiếu).
     - Chọn móc đơn (`eighths`) / móc kép (`sixteenths`) dựa trên nhịp (`meter`), `bpm` và độ dài thời gian vật lý.
     - Áp dụng thang âm đặc trưng theo từng composer (`bach`, `classic`, `villa`, `barrios`, `brouwer`).
     - Đảm bảo **Mix Well** ở Điểm Vào (khớp cao độ & giữ phần đầu ô nhịp), Phần Đệm (bè Bass giữ phách mạnh hợp thế tay, bè Trung nhường đường) và Điểm Ra (đáp đúng phách mạnh của pattern kế tiếp + vuốt velocity mượt mà).
     - Đảm bảo mọi chùm móc kép luôn thỏa mãn `_quarter_ok` / `_position_ok` và vượt qua toàn bộ kiểm tra `assert_playable`.
2. **`backend/app/sonify/guitar_bach.py`, `guitar_sor.py`, `guitar_villa.py`, `guitar_barrios.py`, `guitar_brouwer.py`**:
   - Cung cấp các hàm quy tắc bậc thang âm / nốt dẫn riêng của từng composer (nếu cần tách biệt theo module) và phối hợp mượt với các câu scale nội tại của Bach (`gigue`, `chaconne`, `sarabande`) và Brouwer (`sarabande` modal swarm) để tổng thời lượng scale không vượt ngưỡng 30%.
3. **`backend/tests/test_sonify_guitar.py`**:
   - Cập nhật và bổ sung bộ kiểm thử cho:
     - Phát hiện sóng tăng/giảm đột ngột ở cả quy mô dưới 1 ô nhịp (sub-bar) và 1–4 ô nhịp.
     - Phản ánh đúng nhịp `retreat` thực tế từ dữ liệu giá cổ phiếu (không tạo retreat giả khi giá đi thẳng).
     - Áp dụng trên cả 5 composer với màu sắc thang âm đúng phong cách và giữ nguyên tính khả thi trên cần đàn (`assert_playable`).
     - Kiểm tra tổng thời lượng scale luôn $\le 30\%$ bản nhạc.
     - Kiểm tra tính liên tục và hòa quyện (`mix well`) tại biên vào/ra giữa pattern và đoạn scale.
