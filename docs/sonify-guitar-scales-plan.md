# Kế Hoạch Thiết Kế & Triển Khai Scale Engine Cho Guitar Cổ Điển (`docs/sonify-guitar-scales-plan.md`)

> **Tài liệu tham chiếu**: [`docs/sonify-classical-guitar.md`](./sonify-classical-guitar.md), [`docs/sonify-guitar-improvement-plan.md`](./sonify-guitar-improvement-plan.md), [`docs/sonify-guitar-bach-plan.md`](./sonify-guitar-bach-plan.md), [`docs/sonify-guitar-phase2-brouwer-plan.md`](./sonify-guitar-phase2-brouwer-plan.md)
> **Mục tiêu**: Xây dựng cơ chế phát hiện sóng tăng/giảm giá đột ngột (ngắn sub-bar hoặc dài 1–4 ô nhịp có `retreat` thực tế ở giữa) và chạy Scale nhanh trên toàn bộ **5 composer** của biến thể `guitar` (`bach`, `classic`/Sor, `villa`, `barrios`, `brouwer`), đồng bộ kiến trúc từ tầng dữ liệu gốc (`phrasing.py`, `render.py`, `guitar.py`) xuống bộ lập lịch Guitar (`guitar_patterns.py`), giới hạn mật độ tối đa **30%** bản nhạc, và hòa quyện mượt mà (`mix well`) với các pattern liền trước và liền sau.

---

## 1. Phân Tích Hiện Trạng & Các Lỗ Hổng Kiến Trúc Trong Codebase Hiện Tại

Hiện tại, cơ chế phát hiện chuyển động giá và chạy scale trong `render.py`, `phrasing.py`, `guitar.py` và `guitar_patterns.py` đang tồn tại **5 hạn chế cốt lõi**:

1. **Mất dấu dữ liệu gốc `raw_pitches` khi đi vào Guitar (`render.py` $\rightarrow$ `guitar.py` $\rightarrow$ `guitar_patterns.py`)**:
   - Trong `render.py`, `raw_pitches` là chuỗi cao độ ánh xạ 1:1 từ giá đóng cửa (`close`), sau đó đi qua `quantize_strong_beats` để tạo thành `pitches` (đã kéo các nốt phách mạnh vào âm hợp âm).
   - Tuy nhiên, `render_guitar_score` trong `guitar.py` chỉ nhận `pitches` (không nhận `raw_pitches` thật), rồi chạy `_place_melody` (dịch octave theo từng `Phrase`, nén `_compress_monotone`, và `quantize_strong_beats` lần thứ 2) để tạo `melody`, sau đó truyền `raw_pitches=list(pitches)` xuống `render_patterned_voices`.
   - Hệ quả: `ctx.raw` trong `guitar_patterns.py` thực chất là chuỗi đã bị lượng tử hóa theo hợp âm. Việc kéo phách mạnh vào nốt hợp âm có thể **tạo ra `retreat` giả** (giá thật đi ngang/tăng nhẹ nhưng đổi hợp âm làm cao độ phách mạnh tụt xuống) hoặc **nuốt mất `retreat` thật** (nhịp lùi rơi vào phách mạnh bị kéo ngược lên âm hợp âm).
2. **Mâu thuẫn với bộ cắt câu `plan_phrases` (`phrasing.py`) và biến dạng tại biên câu (`_place_melody`)**:
   - Bộ cắt câu `plan_phrases` (`phrasing.py`) cắt câu ngay tại nốt giữ $\ge 4$ móc đơn (`PERIOD`), $\ge 3$ móc đơn (`COMMA`), hoặc $\ge 2$ móc đơn (`BEAT_EIGHTHS`) theo sau bởi bước nhảy $\ge 5$ bán cung (`LEAP_SEMITONES`).
   - Do đó, một đợt sóng dài (2–4 ô nhịp) có nhịp **chững lại / `retreat` 1 phách (2–3 eighths)** ở giữa rồi bứt tốc vọt lên tiếp sẽ bị `plan_phrases` **chặt đôi thành 2 `Phrase` riêng biệt** ngay tại điểm `retreat`.
   - Vì `_allocate_overlays` hiện chỉ duyệt bên trong từng `Phrase` độc lập (`dict[phrase_index, ...]`), nó không bao giờ nhìn thấy con sóng tổng thể `Up – Retreat – Up` (hoặc `Down – Retreat – Down`) vắt qua 2 `Phrase`. Đồng thời, `_place_melody` có thể chọn 2 mức dịch octave khác nhau cho 2 `Phrase` đó, làm gãy độ dốc của con sóng.
3. **Điều kiện kích hoạt rời rạc, thiên lệch chiều tăng và khóa cứng theo composer (`_allocate_overlays`)**:
   - `Phrase` trong `model.py` mới chỉ có `apex` và `rise = apex.midi - min(...)`, hoàn toàn thiếu thuộc tính đối xứng cho chiều giảm (`trough` và `fall`).
   - Trong `_allocate_overlays`, Sor (`classic`) chỉ chạy scale khi đạt `Grand Solo level 2` (và bị chặn ở `1D` `88 BPM` do ngưỡng cứng `BARRIOS_TREMOLO_MIN_BPM = 90`); Villa-Lobos (`villa`) chỉ chạy khi `mood == "volatile"` và `band == "f"`; Brouwer (`brouwer`) và phần lớn pattern của Bach (`bach`) chưa tham gia bộ lập lịch scale chung.
4. **Đường nét một chiều và độ dài cố định (`_scale_line`, `_run_slots`)**:
   - Chỉ tạo một chuỗi ngắn 4–6 nốt lùi ngược một chiều từ `target`, chưa bao phủ được các con sóng kéo dài **từ dưới 1 ô nhịp (sub-bar) đến 1, 2, 3 hoặc tối đa 4 ô nhịp**, chưa nội suy qua các mốc `waypoint` có `retreat` thực tế, và chưa kiểm tra quy tắc thế tay `_quarter_ok` cho mọi phách móc kép ngoài module Bach.
5. **Ngân sách tách rời & Xung đột hậu xử lý (`_apply_scale_run`, `_smooth_boundaries`, `_shape_dynamics`)**:
   - Ngân sách overlay đang giới hạn cứng ở `15%` số ô nhịp và `_cap_accents(..., limit=2)`, đồng thời chưa tính gộp các câu chạy scale nội tại (intrinsic scales) của Bach (`bach_gigue`, `bach_chaconne`, `bach_sarabande`), Brouwer (`sarabande` modal swarm) và Barrios (`perpetual`).
   - Khi ghép scale vào (`_splice`), phần bè trầm (`low`) và bè trung (`support`) chỉ xử lý riêng cho Barrios (`_pulse_bass`), và đoạn scale ở cuối section có nguy cơ bị `_relax_texture` (trong `_smooth_boundaries`) hoặc `_shape_dynamics` ghi đè làm hỏng kết cấu và đường cong lực gảy.

---

## 2. Thiết Kế Chi Tiết: Tính Âm Nhạc & Thuật Toán Phát Hiện Sóng Có Retreat

### 2.1. Phạm Vi Áp Dụng & Màu Sắc Thang Âm Theo Từng Composer (5 Guitar Variants)

Cơ chế phát hiện sóng tăng/giảm đột ngột và bộ khung chạy scale được dùng chung cho tất cả **5 composer** trong biến thể `guitar`, nhưng cách chọn các bậc thang âm nối giữa các mốc giá sẽ mang bản sắc riêng của từng tác gia:

| Composer (`ensemble`) | Phong cách & Màu sắc Scale (`scale flavor`) | Quy tắc chọn nốt đi qua (Passing / Retreat Notes) |
|---|---|---|
| **J.S. Bach (`bach`)** | **Baroque Diatonic / Melodic Minor** | Chạy liền bậc chuẩn xác kiểu *tirata* / *Chaconne*; ở giọng Thứ (`mode == "minor"`), khi hướng cục bộ đi lên ($d_e = +1$) nâng bậc 6, 7 (*Melodic Minor*) để dẫn về chủ âm, và hạ về tự nhiên (*Natural Minor*) khi hướng cục bộ đi xuống ($d_e = -1$). |
| **Fernando Sor (`classic`)** | **Classical Diatonic / Harmonic Accent** | Thang âm Diatonic cổ điển trong sáng, rõ nét kiểu *Grand Solo* và *Variations Op. 9*; khóa chặt các nốt hợp âm (`chord_at[bar]`) trên mọi phách mạnh đi qua và lấp đầy phách yếu bằng các bậc thang âm chuẩn mực. |
| **Heitor Villa-Lobos (`villa`)** | **Brazilian Open-String & Modal Diatonic** | Phóng khoáng kiểu *Étude No. 7*; ưu tiên khai thác các bậc thang âm đi qua dây buông cộng hưởng (`_OPENS`) và âm màu modal (`sus2`, `add9`, `7sus4`) của hợp âm đang vang. |
| **Agustín Barrios (`barrios`)** | **Romantic Latin & Chromatic Approach** | Lãng mạn Mỹ-Latin; đi liền bậc diatonic kết hợp **nốt dẫn nửa cung (chromatic passing / leading approach)** sát trước nốt trụ hoặc nốt đích (`target`) trên phách mạnh. |
| **Leo Brouwer (`brouwer`)** | **Modern Afro-Cuban Modal** | Mang màu sắc *Estudios Sencillos* / *Elogio de la Danza*; kết hợp bước lướt liền bậc 1–2 bán cung (`_swarm_line`) với thang âm Modal (Dorian, Phrygian / Spanish flavor) và hòa âm treo (`sus2`, `add9`, `bVII`). |

> **Lưu ý tương thích Pattern**: Các pattern có cơ chế khóa lưới riêng biệt như `etude1`, `etude11` (lưới sextuplet/16-note cycle cố định của Villa-Lobos) hoặc phần canto chấm dôi đặc trưng đang khóa của *La Catedral Preludio* (`_catedral_preludio(ctx)`) vẫn giữ quy tắc bảo vệ riêng để không phá vỡ kết cấu đặc thù.

---

### 2.2. Hai Cấp Độ Độ Dài & Lựa Chọn Mật Độ Hạt Nốt (Eighths vs Sixteenths)

#### A. Hai cấp độ độ dài theo thời gian thực của đợt biến động giá
Trên trục thời gian của bản nhạc, mỗi ô nhịp (`bar`) chứa `epb` móc đơn (`8` ở nhịp `4/4`, `6` ở nhịp `3/4` và `6/8`). Bộ dò quét trên chuỗi cao độ giá gốc (`raw_pitches`) ngoài vùng đệm `_PEDAL` (`intro`/`outro`/`warmup`/`cooldown`) để phát hiện các cửa sổ biến động từ ngắn đến dài:

1. **Cấp độ Sub-bar (Không đủ 1 khuôn / dưới 1 ô nhịp: từ `2` đến `epb - 1` móc đơn, thường 1–2 phách)**:
   - Xảy ra khi giá cổ phiếu giật tăng vọt hoặc rơi nhanh trong vài nến ngắn ngủi rồi chững lại ngay trong lòng một ô nhịp (hoặc vắt qua vạch nhịp vào phách mạnh đầu ô kế tiếp).
   - Được map thành một **câu chạy lướt ngắn (pickup run / tirata)** từ `2` đến `epb - 1` móc đơn (tương ứng 4–8 nốt móc kép hoặc 3–6 nốt móc đơn tùy tempo), xuất phát ngay sau phách mạnh liền trước và đáp thẳng vào đỉnh/đáy của cú giật giá.
2. **Cấp độ Multi-bar (1, 2, 3 hoặc tối đa 4 ô nhịp — từ `1 * epb` đến `4 * epb` móc đơn)**:
   - Xảy ra khi cổ phiếu có một đợt sóng tăng tốc (rally surge) hoặc bán tháo (selloff plunge) kéo dài liên tục qua 1, 2, 3 hoặc 4 ô nhịp (có thể đi thẳng hoặc chứa 1–2 nhịp `retreat` ngắn ở giữa).
   - Nếu một xu hướng kéo dài hơn 4 ô nhịp ($> 4 \times \text{epb}$ eighths), thuật toán dùng cửa sổ trượt cắt lấy **đoạn tối đa 4 ô nhịp** có điểm số độ dốc và biên độ biến thiên lớn nhất để câu scale luôn giữ được sự cô đọng, kịch tính.

#### B. Lựa chọn Móc đơn (Eighths) hay Móc kép (Sixteenths) theo Nhịp, Tempo và Độ dài vật lý
Thời lượng vật lý của đoạn scale được tính theo công thức:
$$\text{Duration (seconds)} = \text{eighths} \times \frac{30}{\text{bpm}}$$

Quy tắc chọn mật độ hạt nốt (subdivision):
- **Móc kép (`sixteenths`, `0.25` beat — 2 nốt trên mỗi eighth)**:
  - Áp dụng cho các đoạn **Sub-bar (< 1 ô nhịp)** hoặc **1–2 ô nhịp** khi $\text{BPM} \ge 88$ (hạ ngưỡng từ `90` xuống `88 BPM` để bao phủ cả Sor `1D` ở `88 BPM`; trừ nhịp `6/8` quá nhanh trên `116 BPM` nếu kéo dài nhiều ô), nơi thời gian vật lý ngắn (~1–4 giây) và cần mật độ nốt nhanh để tạo cảm giác bứt tốc của ngón đàn guitar.
  - Cũng áp dụng cho **ô nhịp cuối (climax bar)** của một đoạn scale dài 3–4 ô nhịp khi giá bứt phá mạnh về đích.
- **Móc đơn (`eighths`, `0.5` beat — 1 nốt trên mỗi eighth) hoặc Kết hợp Tăng tốc (`8th -> 16th` Rhythmic Acceleration)**:
  - Áp dụng khi tempo chậm ($\text{BPM} < 88$), ở nhịp `6/8` nhanh kéo dài, hoặc ở **các ô mở đầu của đoạn scale dài 3–4 ô nhịp** (khi tổng thời gian vật lý kéo dài ~6–10 giây) để câu chạy rõ hạt, có đà tăng tốc tự nhiên (mở bằng móc đơn ở nửa đầu, bung ra móc kép ở nửa sau / ô cuối) thay vì biến thành chuỗi móc kép đều đều quá dài.
  - Tại những bước giá nhảy vọt giữa 2 eighth liền kề ($\left|\text{melody}[e+1] - \text{melody}[e]\right| \ge 3$ bán cung) trong vùng đang đi móc đơn, cho phép chẻ cục bộ eighth đó thành 2 móc kép để lấp đầy bậc thang âm nối giữa 2 mức giá mà không tạo bước nhảy hẫng.

---

### 2.3. Thuật Toán Phát Hiện Sóng Ngắn/Dài Có Retreat Thực Tế (`Multi-Scale Impulse & Retreat Detector`)

Để phát hiện chính xác cả sóng tăng/giảm ngắn (sub-bar) lẫn sóng dài (1–4 bars) có `retreat` ở giữa mà **không phụ thuộc vào biên cắt câu của `plan_phrases`** và **không tạo `retreat` nhân tạo**, hệ thống sử dụng thuật toán 4 bước trên `raw_pitches` trong từng section thân bài `[sec_start, sec_end)`:

#### Bước 1: Phân rã chuỗi giá thành các Nhịp Đơn Điệu Cơ Sở (`Primitive Legs`)
Từ chuỗi `raw_pitches`, gom các bước di chuyển liên tiếp thành các nhịp cơ sở:
- **Up-leg ($d = +1$)**: Chuỗi các bước liên tiếp có $\Delta p_e = \text{raw}[e+1] - \text{raw}[e] \ge 0$, có ít nhất 1 bước $\Delta p_e > 0$, và không chứa khoảng đi ngang (`flat`) nội tại nào kéo dài $\ge \text{PERIOD}$ (`4` eighths).
- **Down-leg ($d = -1$)**: Chuỗi các bước liên tiếp có $\Delta p_e \le 0$, có ít nhất 1 bước $\Delta p_e < 0$, và không chứa khoảng đi ngang nội tại $\ge 4$ eighths.
- **Flat-hold ($d = 0$)**: Đoạn giá đứng yên ($\Delta p_e = 0$) kéo dài $\ge 4$ eighths (điểm nghỉ / tích lũy tách biệt các đợt sóng).

#### Bước 2: Quy tắc gộp sóng có `Retreat` (`Wave Coalescing with Data-True Retreat`)
Một chuỗi nhịp liên tiếp dạng **`Impulse Leg 1` ($d$) $\rightarrow$ `Retreat Leg` ($-d$) $\rightarrow$ `Impulse Leg 2` ($d$)** (và tối đa thêm 1 cặp `Retreat 2` $\rightarrow$ `Impulse 3` cho sóng 3–4 bars) được gộp thành **một con sóng hợp nhất (`Composite Wave`)** cùng hướng $d \in \{+1, -1\}$ khi và chỉ khi thỏa mãn đồng thời **5 điều kiện bất biến**:

1. **Giới hạn thời lượng Retreat (`Duration Cap`)**:
   $$\text{len}(\text{retreat}) \le \min\left(3\text{ eighths},\ \lfloor 0.35 \times \text{len}(\text{wave}) \rfloor\right)$$
   *(Nhịp hồi kỹ thuật chỉ kéo dài 1–3 móc đơn, tức $\le 1.5$ phách đen; nếu kéo dài $\ge 4$ eighths = `PERIOD` thì đó là một câu nghỉ hoặc đảo chiều xu hướng thật sự).*
2. **Giới hạn độ sâu thoái lui (`Retracement Depth Cap <= 50%`)**:
   $$\left|\Delta\text{pitch}(\text{retreat})\right| \le 0.50 \times \left|\Delta\text{pitch}(\text{impulse\_before})\right|$$
   *(Nhịp retreat không được xóa quá 50% biên độ của nhịp đẩy liền trước nó).*
3. **Bảo toàn cấu trúc đỉnh/đáy khởi phát (`Higher-Low / Lower-High Guard`)**:
   - Với sóng tăng ($d = +1$): Đáy của nhịp retreat phải cao hơn điểm xuất phát của con sóng ($\min(\text{retreat}) > \text{raw}[\text{wave\_start}]$).
   - Với sóng giảm ($d = -1$): Đỉnh của nhịp retreat phải thấp hơn điểm xuất phát của con sóng ($\max(\text{retreat}) < \text{raw}[\text{wave\_start}]$).
4. **Xác nhận phá đỉnh/đáy sau Retreat (`Continuation Breakout`)**:
   - Nhịp đẩy kế tiếp (`Impulse Leg 2`) phải vượt qua đỉnh của nhịp đẩy trước (với sóng tăng: $\text{end\_pitch}(\text{impulse}_2) > \text{peak}(\text{impulse}_1)$) hoặc phá đáy của nhịp đẩy trước (với sóng giảm: $\text{end\_pitch}(\text{impulse}_2) < \text{trough}(\text{impulse}_1)$).
5. **Giới hạn số nhịp Retreat theo độ dài con sóng**:
   - **Sub-bar (`2 .. epb - 1` eighths)**: Tối đa **0 hoặc 1** nhịp retreat dài `1` eighth.
   - **Sóng 1–2 ô nhịp (`epb .. 2 * epb` eighths)**: Tối đa **1** nhịp retreat (`1–2` eighths).
   - **Sóng 3–4 ô nhịp (`2 * epb + 1 .. 4 * epb` eighths)**: Tối đa **2** nhịp retreat (mỗi nhịp `1–3` eighths), phản ánh cấu trúc sóng 5 nhịp (`Impulse 1 – Retreat 1 – Impulse 2 – Retreat 2 – Impulse 3`).

#### Bước 3: Cắt tỉa biên, Lọc hiệu suất đường đi & Khớp phách mạnh (`Trimming, Efficiency & Metric Snapping`)
1. **Cắt tỉa đầu/đuôi phẳng (`Trim Flat Edges`)**: Loại bỏ các eighths đi ngang ($\Delta p = 0$) ở rìa đầu trước khi giá thực sự nhúc nhích và ở rìa cuối sau khi giá đã chạm cực trị (`peak` cho $d = +1$, `trough` cho $d = -1$).
2. **Cửa sổ trượt tối đa 4 ô nhịp (`Max 4-Bar Window`)**: Nếu sóng gộp dài hơn $4 \times \text{epb}$ eighths, xét các cửa sổ con hợp lệ độ dài $\le 4 \times \text{epb}$ (bắt đầu tại đầu một impulse leg và kết thúc tại cực trị của một impulse leg) và chọn cửa sổ có điểm số cao nhất.
3. **Ngưỡng biên độ & Hiệu suất đường đi (`Scale-Aware Thresholds & Path Efficiency`)**:
   - Định nghĩa **Biên độ ròng**: $\text{net\_span} = \left|\text{raw}[\text{end}] - \text{raw}[\text{start}]\right|$ và **Tổng quãng đường**: $\text{total\_path} = \sum_{e=\text{start}}^{\text{end}-1} \left|\text{raw}[e+1] - \text{raw}[e]\right|$.
   - **Hiệu suất đường đi (`Path Efficiency`)**:
     $$\text{efficiency} = \frac{\text{net\_span}}{\max(1,\ \text{total\_path})} \ge 0.45$$
     *(Tiêu chí này loại bỏ hoàn toàn các vùng giằng co đi ngang răng cưa `choppy whipsaw` có tổng dao động lớn nhưng biên độ ròng nhỏ).*
   - **Ngưỡng kích hoạt theo quy mô**:
     - **Sub-bar (`2 .. epb - 1` eighths)**: $\text{net\_span} \ge 4$ bán cung (hoặc $\ge 3$ bậc thang) và tốc độ $\text{slope} = \frac{\text{net\_span}}{\text{length}} \ge 1.0$ bán cung/eighth.
     - **1 ô nhịp (`epb .. 2*epb - 1` eighths)**: $\text{net\_span} \ge 5$ bán cung.
     - **2–4 ô nhịp (`2*epb .. 4*epb` eighths)**: $\text{net\_span} \ge 6$ bán cung.
4. **Khớp điểm đáp vào Phách Mạnh (`Target Strong-Beat Alignment`)**:
   - Điểm kết thúc `target` ưu tiên neo vào một phách mạnh (`eighth % epb in strong_eighths`) tại đúng cực trị của con sóng, hoặc nếu cực trị rơi ngay trước phách mạnh 1 eighth và giữ nguyên mức giá đó sang phách mạnh kế tiếp thì kéo `target` vào đúng phách mạnh đó để câu scale đáp xuống vững chãi.

#### Bước 4: Dựng đường Scale qua các Waypoint Giá Thật (`Waypoint Interpolation`)
- Mỗi mốc eighth-note $e \in [\text{start}, \text{target}]$ trong đoạn scale giữ vai trò là **mốc dẫn hướng (`waypoint`)** từ `melody` kết hợp với dấu hướng thực tế của `raw_pitches`:
  - Khi $\text{raw}[e+1] > \text{raw}[e]$: đường scale bước đi lên theo thang âm của composer.
  - Khi $\text{raw}[e+1] < \text{raw}[e]$ (**real retreat** trong sóng lên, hoặc nhịp rơi trong sóng xuống): đường scale **đổi chiều bước lùi xuống đúng theo nhịp giảm của giá**.
  - Khi $\text{raw}[e+1] == \text{raw}[e]$ nằm giữa hai nhịp cùng chiều đang lao đi: thay vì đứng im làm đứt mạch chạy ngón, cho phép bước qua bậc thang âm kế cận trong cùng thế tay rồi hội tụ về `melody[e+1]`.
  - Mọi nốt rơi vào phách mạnh (`strong_eighths`) trên đường chạy đều neo đúng vào cao độ `melody[eighth]` (hoặc âm hợp âm tương ứng), và nốt cuối cùng tại `target` trùng khớp 100% với `melody[target]`.

---

### 2.4. Ngân Sách Tối Đa 30% Toàn Cục (`Unified Budget Cap <= 30%`)

- **Đơn vị tính chính xác theo `eighths` và hợp nhất toàn bộ các nguồn Scale**:
  - Hạn mức **tối đa 30%** được tính trên tổng số eighths của phần thân bài (`body_eighths`) và kiểm tra trong từng section thân bài:
    $$\text{max\_scale\_eighths} = \lfloor 0.30 \times \text{body\_eighths} \rfloor$$
  - **Đồng bộ ngân sách giữa Intrinsic Scales và Overlay Scales**:
    - Các câu chạy ngón nội tại của pattern (như nửa sau ô nhịp của `bach_gigue`, đoạn breakout của `bach_chaconne`, passing scale cuối ô của `bach_sarabande`, modal swarm của Brouwer `sarabande`, và `perpetual` của Barrios) được tính chung vào hạn mức `max_scale_eighths` (hoặc được điều phối bởi cùng danh sách `PriceImpulse`) để tổng thời lượng chạy scale của bất kỳ composer nào cũng không bao giờ vượt quá **30%**.
- **Hàm chấm điểm ưu tiên (`Impulse Ranking Score`)**:
  $$\text{Score} = \text{net\_span} \times \left(1.0 + 0.5 \times \frac{\text{net\_span}}{\text{length}}\right) \times \text{efficiency} + \text{retreat\_bonus}$$
  *(trong đó `retreat_bonus = 1.5` khi con sóng có nhịp retreat thực tế hợp lệ rồi phá đỉnh/đáy đi tiếp, giúp ưu tiên các con sóng có cấu trúc giàu kịch tính âm nhạc).*
- **Khoảng thở tối thiểu giữa hai đoạn Scale (`Minimum Cooldown Gap`)**:
  - Hai đoạn scale được chọn phải cách nhau ít nhất $\ge \text{epb}$ eighths (**1 ô nhịp thở**) ở giữa để bản nhạc luôn có sự tương phản rõ rệt giữa phần pattern nền và phần bứt tốc chạy ngón.

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
- **Bè Trầm (`low` - Voice 3) duy trì nhịp mạch hợp âm (Harmonic Pulse) cho cả 5 Composer**:
  - Trên các phách mạnh (`strong_eighths`, ví dụ phách 1 và phách 3 trong `4/4`, phách 1 và phách 4 trong `6/8`), bè Bass gảy nốt Gốc (`Root`) hoặc Bậc 5 (`Fifth`) của hợp âm hiện tại (`chord_at[bar]`), được kiểm tra qua `_playable` để luôn nằm dưới đường scale và trong cùng thế tay (5 ngăn phím) với các nốt scale phía trên.
  - Với Bach (`bach`): giữ nốt bass đối vị trên phách mạnh dưới câu scale.
  - Với Brouwer (`brouwer`) / Villa-Lobos (`villa`): giữ nốt bass phách đầu (ưu tiên dây buông nếu hợp hợp âm) ngân ấm dưới đường chạy ngón.
- **Bè Giữa (`support` - Voice 2) nhường đường thông minh (Selective Thinning)**:
  - Trong suốt khoảng thời gian bè Cao (`lead`) chạy móc kép dày đặc, các nốt rải `support` nằm trùng thời điểm được lược bỏ (`_drop_overlap`) để giải phóng ngón `i-m-a` của tay phải cho câu scale.
  - Riêng tại **phách mạnh đầu tiên mở đầu đoạn scale** (hoặc khi đoạn scale tạm đi bằng móc đơn ở nhịp đầu), giữ 1 nốt hợp âm bè Trung hợp thế tay để tiếng vào dày dặn.

#### 3. Điểm Ra (Landing & Exit — Từ Scale trở lại Pattern sau)
- **Hội tụ chính xác vào Nốt Trụ trên Phách Mạnh (Target Downbeat / Strong-Beat Resolution)**:
  - Nốt kết thúc của đoạn scale luôn đáp đúng vào **nốt giai điệu chính (`melody[target]`) tại một phách mạnh** (đầu ô nhịp kế tiếp hoặc phách mạnh giữa ô nhịp).
  - Ngay tại phách mạnh đáp đích đó, **pattern phía sau lập tức tiếp quản đồng bộ**: bè Bass của pattern sau đánh phách mạnh cùng lúc với nốt đích của scale, và bè Trung (`support`) bắt đầu chu kỳ rải ngón từ ngay phách yếu kế tiếp.
- **Vuốt động lực học (Dynamic Bridging) & Nhịp thở (Post-Scale Breath)**:
  - **Crescendo khi đi lên**: Lực gảy (`velocity`) của đoạn scale đi lên khởi đầu ngang với mức velocity của pattern liền trước và tăng dần đều (`swell`) lên tới `_MELODY_APEX` (`72`) tại nốt đích trên phách mạnh.
  - **Shaping khi đi xuống**: Đoạn scale đi xuống khởi đầu rõ nét tại đỉnh rơi và vuốt về mức lực nền của pattern kế tiếp (hoặc nhấn nhẹ ở đáy nếu rơi vào hợp âm kịch tính của `selloff`), tránh bị gắt hoặc rơi tõm.
  - Nếu nốt đích của scale rơi vào một điểm kết câu (`phrase.closes`), nốt đích được **ngân dài tự nhiên** trên nền rải arpeggio nhẹ của pattern mới, tạo khoảng thở âm nhạc hoàn chỉnh.

---

## 3. Kiến Trúc Thống Nhất & Các Thay Đổi Cụ Thể Trong Codebase

Để cơ chế phát hiện sóng tăng/giảm có `retreat` và bộ chạy scale hoạt động thống nhất xuyên suốt từ dữ liệu giá đến bản tổng phổ Guitar, kiến trúc pipeline được chuẩn hóa qua **5 tầng**:

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                     1. model.py & phrasing.py (Core Layer)                   │
│  • Bổ sung `Phrase.trough`, `Phrase.fall` và dataclass `PriceImpulse`.       │
│  • Hàm `detect_price_impulses(raw_pitches, ...)` quét trực tiếp trên         │
│    `raw_pitches` (độc lập với biên cắt của `plan_phrases`), trả về các       │
│    đoạn tăng/giảm Sub-bar & 1–4 bars kèm danh sách `retreat_spans` thật.     │
└───────────────────────────────────────┬──────────────────────────────────────┘
                                        ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                     2. render.py & guitar.py (Data & Register Layer)         │
│  • `render.py` truyền `raw_pitches` thật (chưa bị `quantize_strong_beats`    │
│    làm méo) và `impulses` vào `render_guitar_score`.                         │
│  • `_place_melody` trong `guitar.py` khóa chung mức dịch octave cho các      │
│    `Phrase` nằm trong cùng một `PriceImpulse` dài để không làm gãy độ dốc    │
│    hoặc đảo chiều nhịp `retreat` tại biên `Phrase`.                          │
└───────────────────────────────────────┬──────────────────────────────────────┘
                                        ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│            3. guitar_patterns.py & 5 Composer Modules (Scale Engine)         │
│  • Thay `plans: dict[phrase_idx, tuple]` bằng `passages: list[ScalePassage]` │
│    với ngân sách thống nhất `<= 30% body_eighths` (tính gộp cả intrinsic     │
│    scales của Bach/Brouwer/Barrios và bỏ trần cũ 15% / `limit=2`).           │
│  • `_realize_scale_passage`: nội suy qua các `waypoint` giữ nguyên nhịp      │
│    `retreat` thật, áp dụng thang âm của từng Composer, kiểm tra `_quarter_ok`│
│    trên cao độ thực (`pitch + ctx.semitones`), và bảo vệ đoạn scale khỏi bị  │
│    `_relax_texture` / `_shape_dynamics` ghi đè.                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 3.1. `backend/app/sonify/model.py` & `backend/app/sonify/phrasing.py`
1. **Trong `backend/app/sonify/model.py`**:
   - Bổ sung `@property def trough(self) -> Run` (run thấp nhất trong câu) và `@property def fall(self) -> int` (`max(run.midi for run in self.runs) - self.trough.midi`) trên `Phrase` để đối xứng hóa với `apex` và `rise`.
   - Định nghĩa cấu trúc dữ liệu `PriceImpulse`:
     ```python
     @dataclass(frozen=True)
     class PriceImpulse:
         start: int                                      # eighth bắt đầu đợt biến động
         target: int                                     # eighth kết thúc / đáp đích (ưu tiên strong beat)
         direction: Literal["up", "down"]                # hướng chủ đạo của con sóng
         net_span: int                                   # biên độ ròng |raw[target] - raw[start]| (semitones)
         efficiency: float                               # net_span / total_path (>= 0.45)
         score: float                                    # điểm xếp hạng độ đột ngột & kịch tính
         retreat_spans: tuple[tuple[int, int], ...] = () # các khoảng (r_start, r_end) hồi giá thật ở giữa
         sub_bar: bool = False                           # True nếu target - start < epb
     ```
2. **Trong `backend/app/sonify/phrasing.py`**:
   - Triển khai hàm `detect_price_impulses(raw_pitches: Sequence[int], section_starts: tuple[int, ...], *, epb: int = 8, strong_eighths: tuple[int, ...] = (0, 4), pedal_bars: frozenset[int] = frozenset()) -> tuple[PriceImpulse, ...]` theo đúng thuật toán 4 bước ở Mục 2.3.

### 3.2. `backend/app/sonify/render.py` & `backend/app/sonify/guitar.py`
1. **Truyền đúng `raw_pitches` gốc**:
   - Trong `render.py` (nhánh `if variant == "guitar":`), truyền thêm `raw_pitches=raw_pitches` vào `render_guitar_score(...)`.
   - Trong `guitar.py`, `render_guitar_score` nhận `raw_pitches: list[int] | None = None` (fallback về `list(pitches)` khi các unit test cũ gọi trực tiếp không truyền `raw_pitches`) và truyền `raw_pitches` thật đó xuống `render_patterned_voices` cũng như `_place_thumb`.
2. **Bảo toàn hình dạng sóng qua biên `Phrase` trong `_place_melody` (`guitar.py`)**:
   - Trong `_choose_shifts`, khi hai `Phrase` liên tiếp $P_{i-1}$ và $P_i$ cùng nằm trong phạm vi `[impulse.start, impulse.target]` của một `PriceImpulse`, áp dụng chi phí phạt cao nếu hai `Phrase` chọn hai mức dịch `shift` khác nhau làm biến dạng độ dốc hoặc đảo dấu hướng đi giữa `P_{i-1}` và `P_i`.

### 3.3. `backend/app/sonify/guitar_patterns.py`
1. **Cấu trúc `ScalePassage` & Bộ điều phối `_allocate_scale_passages`**:
   - Thay thế `_allocate_overlays` (vốn khóa theo `phrase_index` và giới hạn 15%) và bỏ hàm cắt cứng `_cap_accents(..., limit=2)` đối với scale bằng `_allocate_scale_passages(ctx, patterns, levels) -> tuple[list[ScalePassage], dict[int, list[int]]]`.
   - Quét các `PriceImpulse` từ `detect_price_impulses(ctx.raw, ...)`:
     - Loại trừ các ô thuộc `_PEDAL`, các ô đang chạy `etude1`, `etude11`, hoặc `preludio` khi `_catedral_preludio(ctx)` bật.
     - Tính tổng ngân sách `max_scale_eighths = int(0.30 * body_eighths)` (và tối đa 30% trong mỗi section).
     - Khấu trừ hoặc hợp nhất với số eighths chạy scale nội tại của Bach (`bach_gigue`, `bach_chaconne`, `bach_sarabande`), Brouwer (`sarabande` modal swarm) và Barrios (`perpetual`) để tổng thời lượng scale toàn bài luôn $\le 30\%$.
     - Chọn các `ScalePassage` theo thứ tự `impulse.score` giảm dần, đảm bảo khoảng cách tối thiểu $\ge \text{epb}$ eighths giữa hai passage bất kỳ.
2. **Bộ sinh nốt `_realize_scale_passage` & Phần đệm `_underpin_scale_passage`**:
   - Nâng cấp `_scale_line` và `_apply_scale_run` thành `_realize_scale_passage`:
     - Xác định lưới hạt nốt (`eighths`, `sixteenths`, hoặc tăng tốc `8th -> 16th`) dựa trên `ctx.bpm`, `ctx.kind` (`4/4`, `3/4`, `6/8`) và độ dài `passage`.
     - Đi qua các mốc `waypoint` từ `passage.start` đến `passage.target`: giữ nguyên các bước đảo chiều tại `retreat_spans` thật từ `ctx.raw`, khóa nốt phách mạnh vào `ctx.melody[eighth]`, và gọi quy tắc bậc thang âm theo `ctx.ensemble`.
     - Kiểm tra `_quarter_ok([note + ctx.semitones for note in quarter_group])` cho từng phách đen chứa móc kép để đảm bảo luôn nằm trong 1 thế tay (`<= 5` ngăn phím).
     - Thiết kế dải `velocity` nối mượt từ velocity của pattern liền trước tại `passage.start` lên tới `_MELODY_APEX` (`72`) tại `passage.target` (khi đi lên) hoặc vuốt giảm dần về mức nền của pattern kế tiếp (khi đi xuống).
   - Chuẩn hóa `_underpin_scale_passage` cho cả **5 composer**:
     - Giữ nguyên `low` và `support` trước `passage.start` nếu bắt đầu giữa ô nhịp (*Sub-bar Dovetail*).
     - Lược bỏ `support` trùng với móc kép của scale, chỉ giữ 1 nốt hợp âm bè Trung ở phách mở đầu nếu hợp thế tay.
     - Giữ hoặc đặt nốt Bass (`Root` / `Fifth`) trên các phách mạnh (`ctx.strong`) trong suốt đoạn scale sao cho thỏa mãn `_playable` với toàn bộ các nốt scale trong phách đó.
3. **Đồng bộ thứ tự Pipeline hậu xử lý trong `render_patterned_voices`**:
   - Loại các ô đã có `ScalePassage` khỏi `bell_bars` trước khi gọi `_insert_bells`.
   - Đánh dấu các eighths thuộc `ScalePassage` vào tập `scale_protected_eighths` để:
     - `_relax_texture` (trong `_smooth_boundaries`) không xóa mất câu scale nếu `ScalePassage` kết thúc vào đầu ô tiếp theo.
     - `_shape_dynamics` giữ nguyên đường cong velocity đã được vuốt mượt của `ScalePassage`.
     - `_slur` không chèn hammer-on làm đứt hạt của chuỗi móc kép scale.

### 3.4. `backend/app/sonify/guitar_bach.py`, `guitar_sor.py`, `guitar_villa.py`, `guitar_barrios.py`, `guitar_brouwer.py`
- Cung cấp hàm chọn bậc thang âm / nốt dẫn đặc trưng theo từng composer (`_bach_scale_step`, `_sor_scale_step`, `_villa_scale_step`, `_barrios_scale_step`, `_brouwer_scale_step`).
- Đồng bộ các đoạn scale nội tại trong `guitar_bach.py` (`_render_bach_gigue_bar`, `_render_bach_chaconne_bar`, `_render_bach_sarabande_bar`) và `guitar_brouwer.py` (`_render_sarabande_bar`) với ngân sách scale 30% chung trong `guitar_patterns.py`.

### 3.5. `backend/tests/test_sonify_guitar.py`
- Cập nhật và bổ sung bộ kiểm thử toàn diện:
  1. **Test `detect_price_impulses`**:
     - Phát hiện đúng đợt tăng/giảm ngắn dưới 1 ô nhịp (`sub_bar = True`, 2–6 eighths) và đợt dài `1, 2, 3, 4` ô nhịp, kể cả khi con sóng vắt qua ranh giới 2 `Phrase` của `plan_phrases`.
     - Nhận diện đúng cấu trúc `Up – Retreat – Up` và `Down – Retreat – Down` khi nhịp retreat thỏa mãn 5 điều kiện bất biến, và tách thành 2 sóng riêng hoặc loại bỏ khi nhịp ngược chiều quá sâu ($> 50\%$), quá dài ($\ge 4$ eighths), hoặc là vùng sideway răng cưa (`efficiency < 0.45`).
  2. **Test Waypoint & Data-True Retreat**:
     - Khi dữ liệu giá tăng/giảm thẳng một chiều, đường scale đi thẳng một chiều (không tự bịa retreat nhân tạo).
     - Khi dữ liệu giá có nhịp retreat thật ở giữa, đường scale đổi chiều lùi theo đúng mốc eighth của nhịp retreat rồi vọt lên/xuống tiếp về đích `melody[target]`.
  3. **Test 5 Composer & Tính khả thi trên đàn (`assert_playable`)**:
     - Kiểm tra cả 5 composer (`bach`, `classic`, `villa`, `barrios`, `brouwer`) đều kích hoạt được scale trên sóng tăng/giảm đột ngột (bao gồm cả Sor `1D` ở `88 BPM`), mang đúng màu sắc thang âm đặc trưng và vượt qua `assert_playable` trên mọi giọng (`C, D, Eb, A, Bb`).
  4. **Test Ngân sách $\le 30\%$ & Mix Well**:
     - Tổng số eighths chạy scale (tính gộp cả overlay scale và intrinsic scale) luôn $\le 30\%$ `total_eighths`.
     - Kiểm tra khớp nối liền bậc ở Điểm Vào, duy trì Bass hợp thế tay ở Phần Đệm, và đáp đúng nốt giai điệu trên phách mạnh ở Điểm Ra.
