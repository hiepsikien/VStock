# Kế Hoạch Thiết Kế & Triển Khai Scale Engine Cho Guitar Cổ Điển (`docs/sonify-guitar-scales-plan.md`)

> **Tài liệu tham chiếu**: [`docs/sonify-classical-guitar.md`](./sonify-classical-guitar.md), [`docs/sonify-guitar-improvement-plan.md`](./sonify-guitar-improvement-plan.md), [`docs/sonify-guitar-bach-plan.md`](./sonify-guitar-bach-plan.md), [`docs/sonify-guitar-phase2-brouwer-plan.md`](./sonify-guitar-phase2-brouwer-plan.md)
> **Mục tiêu**: Xây dựng cơ chế phát hiện sóng tăng/giảm giá đột ngột (ngắn sub-bar hoặc dài 1–4 ô nhịp có `retreat` thực tế ở giữa) và chạy Scale nhanh trên toàn bộ **5 composer** của biến thể `guitar` (`bach`, `classic`/Sor, `villa`, `barrios`, `brouwer`), đồng bộ từ chuỗi giá gốc `raw_pitches` xuống bộ lập lịch Guitar, bảo toàn các kết cấu/scale nội tại của từng pattern, giới hạn ngân sách ở mức **30%** phần thân bài, và hòa quyện mượt mà (`mix well`) với các pattern liền trước và liền sau.

---

## 1. Phân Tích Hiện Trạng Trong Codebase

Hiện tại, cơ chế phát hiện chuyển động giá và chạy scale trong `render.py`, `guitar.py` và `guitar_patterns.py` có các điểm nghẽn sau:

1. **`render_guitar_score` chưa nhận `raw_pitches` gốc (`render.py` $\rightarrow$ `guitar.py` $\rightarrow$ `guitar_patterns.py`)**:
   - Trong `render.py`, `raw_pitches` là chuỗi cao độ ánh xạ 1:1 từ giá đóng cửa (`close`), sau đó đi qua `quantize_strong_beats` để tạo `pitches`.
   - `render_guitar_score` trong `guitar.py` chỉ nhận `pitches` (đã lượng tử hóa phách mạnh), rồi `_place_melody` dịch octave/nén theo từng `Phrase` và gọi `quantize_strong_beats` thêm một lần nữa trước khi truyền `raw_pitches=list(pitches)` xuống `render_patterned_voices`.
   - Vì `ctx.raw` thực chất là `pitches` đã bị kéo về âm hợp âm trên phách mạnh, nó có thể **tạo ra `retreat` giả** (khi giá đi ngang/tăng nhẹ nhưng đổi hợp âm kéo nốt phách mạnh tụt xuống) hoặc **xóa mất `retreat` thật** (khi nhịp lùi rơi vào phách mạnh bị kéo ngược lên nốt hợp âm).
2. **Đường chạy một chiều, ngắn cố định và làm mất nhịp `retreat` (`_scale_line`, `_run_slots`)**:
   - Bộ cắt câu `plan_phrases` (`phrasing.py`) chỉ cắt khi một cao độ đứng yên đủ lâu (`PERIOD = 4` eighths khi câu đã dài $\ge \text{MIN\_EIGHTHS} = 8$ eighths; nhánh `COMMA = 3` và bước nhảy `LEAP_SEMITONES = 5` chỉ chạy khi câu chạm trần `MAX_EIGHTHS = 32` eighths). Do đó, một nhịp `retreat` ngắn 1–3 eighths (có đổi cao độ) **vẫn nằm trong cùng một `Phrase`**, không bị `plan_phrases` chặt đôi.
   - Sóng `Up – Retreat – Up` (hoặc `Down – Retreat – Down`) hiện bị biến mất là vì `_scale_line` và `_run_slots` chỉ lấy 4 nốt móc đơn hoặc 4–6 nốt móc kép ở cuối câu rồi lùi thẳng một chiều từ `target`, hoàn toàn không đi qua các mốc `waypoint` của dữ liệu giá, cộng với việc `ctx.raw` đã bị kéo về hợp âm.
   - Riêng khi một đợt sóng dài (2–4 ô nhịp) đi ngang qua điểm cắt trần `MAX_EIGHTHS = 32` (hoặc sau một nốt nghỉ $\ge 4$ eighths), `_choose_shifts` trong `_place_melody` tuy đã phạt đảo chiều biên câu (`_REVERSAL_COST = 80` và `_LARGE_LEAP_COST = 400` khi đảo chiều $\ge 9$ bán cung), nhưng vẫn có thể: (a) chọn 2 mức `shift` khác nhau nếu bước qua biên không đảo dấu trực tiếp, hoặc (b) một câu giữ nguyên (`exact=True`) còn câu kế bị nén qua `_compress_monotone`, làm bẻ gãy độ dốc giữa hai nửa con sóng.
3. **Điều kiện kích hoạt khóa hẹp theo từng composer và vướng ngưỡng `BARRIOS_TREMOLO_MIN_BPM = 90`**:
   - Sor (`classic`) có tempo mặc định ở bản `1D` là `GUITAR_BPM["classic"] = 88`, trong khi `_grand_levels` trả về rỗng khi `bpm < BARRIOS_TREMOLO_MIN_BPM` (`90`) và `_allocate_overlays` chỉ cấp scale cho `classic` khi `Grand Solo level == 2`. Hệ quả là Sor `1D` (`88 BPM`) không bao giờ có scale.
   - *Lưu ý quan trọng*: **Không được hạ `BARRIOS_TREMOLO_MIN_BPM` từ `90` xuống `88`**, vì hằng số này còn đang khóa `Grand Solo`, `_fanfare_bars`, `perpetual` và `tremolo` (nếu hạ xuống 88 sẽ làm bật cả lớp figuration `Grand Solo` trên bản `1D` của Sor). Thay vào đó, cần tách một hằng số riêng `SCALE_SIXTEENTH_MIN_BPM = 88` chỉ phục vụ việc chọn hạt nốt móc kép cho scale.
   - Villa-Lobos (`villa`) hiện chỉ vào nhánh `mood == "volatile"` và `band == "f"`; Bach (`bach`) và Brouwer (`brouwer`) chưa có nhánh trong `_allocate_overlays`.
4. **Hai cổng giới hạn chồng nhau (`15%` theo section và `limit=2` cho bài ngắn có khung)**:
   - Trong `_allocate_overlays`, `limit = int((end - begin) * 0.15 + 1e-9)` là trần số ô nhịp trong từng section (luôn chạy).
   - Ngoài ra, trong `render_patterned_voices`, khi `_framed(ctx) and ctx.bars <= 40`, hàm `_cap_accents(..., limit=2)` chạy thêm một lần nữa để cắt tổng số đoạn `scale` + `perpetual` của cả bài xuống tối đa `2`.
5. **Xử lý bè đệm & hậu xử lý chưa đồng bộ cho 5 composer**:
   - Trong `_apply_scale_run`, phần bè trầm (`low`) chỉ được gọi `_pulse_bass` khi `ctx.ensemble == "barrios"`.
   - Các pass hậu xử lý chạy sau `_apply_scale_run` như `_relax_texture` (trong `_smooth_boundaries`) và `_shape_dynamics` chưa nhận biết vùng đang chạy scale để bảo vệ kết cấu và đường cong lực gảy.

---

## 2. Thiết Kế Chi Tiết: Tính Âm Nhạc, Bảo Toàn Pattern & Thuật Toán Dò Sóng

### 2.1. Màu Sắc Thang Âm 5 Composer & Quy Tắc Bảo Toàn Pattern / Scale Nội Tại

#### A. Bảng màu sắc thang âm theo từng Composer (`scale flavor`)

| Composer (`ensemble`) | Phong cách & Màu sắc Scale | Quy tắc chọn nốt đi qua (Passing / Retreat Notes) |
|---|---|---|
| **J.S. Bach (`bach`)** | **Baroque Diatonic / Melodic Minor** | Chạy liền bậc kiểu *tirata*; ở giọng Thứ (`mode == "minor"`), **không đổi thang âm theo từng bước `d_e` đơn lẻ** (tránh đổi chính tả `Ab/A`, `Bb/B` liên tục ở mỗi móc của nhịp retreat 1 nốt), mà bám theo **hướng chủ đạo của cả con sóng (`impulse.direction`)** hoặc chỉ nâng bậc 6, 7 (*Melodic Minor*) ở các nốt tiến sát về chủ âm (`tonic`), giữ *Natural Minor* khi đi xuống. |
| **Fernando Sor (`classic`)** | **Classical Diatonic / Harmonic Accent** | Thang âm Diatonic cổ điển trong sáng kiểu *Grand Solo* và *Op. 9*; giữ chặt các nốt hợp âm trên phách mạnh và lấp đầy phách yếu bằng bậc thang âm chuẩn mực. |
| **Heitor Villa-Lobos (`villa`)** | **Brazilian Open-String & Modal Diatonic** | Phóng khoáng kiểu *Étude No. 7*; ưu tiên đi qua dây buông cộng hưởng (`_OPENS`) và âm màu modal (`sus2`, `add9`, `7sus4`), nhưng **bắt buộc hậu kiểm `_quarter_ok`**: vì `_quarter_ok` chỉ miễn kiểm tra thế tay khi 2 nốt liền kề cách nhau $> 4$ bán cung, nếu việc chèn dây buông vào đường liền bậc làm chùm 4 móc kép trượt `_position_ok` (`> 5` ngăn phím), phải bỏ dây buông đó và dùng nốt bấm trên thang âm. |
| **Agustín Barrios (`barrios`)** | **Romantic Latin & Chromatic Approach** | Đi liền bậc diatonic kết hợp **nốt dẫn nửa cung (chromatic passing / leading approach)** ngay trước phách mạnh hoặc trước nốt đích (`target`). |
| **Leo Brouwer (`brouwer`)** | **Modern Afro-Cuban Modal** | Kết hợp bước lướt liền bậc 1–2 bán cung (`_swarm_line`) với màu sắc Modal (Dorian / Phrygian) và âm màu treo (`sus2`, `add9`, `bVII`). |

#### B. Phân loại 3 nhóm Pattern để không phá vỡ kết cấu và Scale nội tại (`Intrinsic Scales`)
Trong codebase hiện tại, một số pattern đã có sẵn các chùm chạy scale/swarm nội tại (như `bach_gigue`, `bach_chaconne`, `bach_sarabande`, Brouwer `sarabande`) hoặc có lưới ngón tay phải cố định. Để cơ chế scale mới **không bao giờ phá hỏng cấu trúc nhận diện của pattern đang chạy**, toàn bộ các pattern được chia thành **3 nhóm rõ ràng**:

1. **Nhóm 1 — Các Pattern khóa lưới hoặc đảo vai bè (Loại trừ hoàn toàn khỏi Overlay Scale)**:
   - **`tremolo` (Barrios)**: Ghép scale vào `tremolo` sẽ cắt đứt lưỡi lặp `p-a-m-i` liên tục. Do đó `tremolo` nằm trong danh sách loại trừ cùng với `etude1`, `etude11` và `preludio` có khung (`_catedral_preludio(ctx)`). (`tremolo` chỉ nhận `perpetual` trên các ô giữ giá phẳng ở `band == "f"`, `mood == "volatile"`).
   - **`etude1` & `etude11` (Villa-Lobos)**: Khóa chặt vòng 16 móc kép (*Étude No. 1*) và 4 chùm sextuplet (*Étude No. 11*).
   - **`preludio` khi `_catedral_preludio(ctx) == True` (Barrios)**: Khóa chặt giai điệu canto chấm dôi đan với sóng chữ V ở bè Trung.
   - **`thumb_cantabile` (Villa-Lobos / Barrios)**: Giai điệu chính nằm ở bè Trầm (`Voice 3`, ngón cái `p` hát ở vùng Cello `48..64`) trong khi `Voice 1` và `Voice 2` chỉ chập hợp âm phách yếu; không chèn scale ở `Voice 1` đè lên câu hát của ngón cái.
2. **Nhóm 2 — Các Pattern có Cửa Sổ Scale Nội Tại (`bach_chaconne`, `bach_gigue`, `bach_sarabande`, Brouwer `sarabande`) — Cơ chế Phân Tầng 2 Cấp (`Two-Tier Threshold`)**:
   - Ở 4 pattern này, câu chạy scale đã là **một thành phần cấu trúc nằm trong chính ô nhịp của pattern**:
     - `bach_chaconne`: Nửa đầu ô nhịp (`0 .. scale_at`, tức 2 phách đầu ở `4/4` hoặc 1 phách đầu ở `3/4`) là hợp âm trụ + móc kép *bariolage* đan dây; nửa sau (`scale_at .. epb * 2`) là cửa sổ chạy `_fitting_scale` khi `breakout`.
     - `bach_gigue`: Nửa đầu ô nhịp (`0 .. scale_at`) là tiết tấu hợp âm gãy đặc trưng của điệu Gigue (`down`, `pickup`, `inner`); nửa sau (`scale_at .. epb * 2`) là cửa sổ chạy `_fitting_scale` khi câu đi lên.
     - `bach_sarabande` & Brouwer `sarabande`: Phách 1 và **trọng âm Phách 2 (`accent`)** (kèm mordent ở Bach) là dấu hiệu nhận diện sống còn của điệu Sarabande; phần đuôi ô nhịp sau phách 2 (`passing .. epb` ở Bach, `figure_at .. epb` ở Brouwer) là cửa sổ chạy passing scale / modal swarm.
   - **Cấp 1 — Khi biến động nhỏ / vừa ($L < \text{epb}$ hoặc $\text{net\_span} < 6$ bán cung)**:
     - **Không cắt đè `ScalePassage` ngắn lên đầu ô nhịp của Nhóm 2**: giữ nguyên 100% phần *bariolage* đầu ô của `bach_chaconne`, nhịp hợp âm gãy đầu ô của `bach_gigue`, và trọng âm phách 2 của `bach_sarabande` / Brouwer `sarabande`.
     - Nếu ô Nhóm 2 có biến động giảm (`downward plunge`) trong phạm vi 1 ô mà điều kiện `_rises(phrase)` cũ bỏ sót, chỉ kích hoạt scale ngay bên trong **cửa sổ nội tại sẵn có ở nửa sau ô nhịp** (`scale_at .. epb * 2` cho Chaconne/Gigue, hoặc sau phách 2 cho Sarabande).
   - **Cấp 2 — Khi biến động là Sóng Lớn (`Major Bridge Impulse`: $L \ge \text{epb}$ từ 1 đến 4 ô nhịp VÀ $\text{net\_span} \ge 6$ bán cung)**:
     - Đúng như truyền thống *Chaconne (BWV 1004)*, *Les Doubles* của Bach và *El Decamerón Negro* của Brouwer, một đợt sóng lớn ($L \ge \text{epb}, \text{net\_span} \ge 6$) **được phép mở thành một `ScalePassage` dài (1–4 ô nhịp) làm đoạn nối (connecting bridge / passaggio) ở giữa cho cả Nhóm 2 lẫn Nhóm 3** thay vì bị băm vụn từng nửa ô nhịp, với **3 quy tắc giữ bản sắc Pattern**:
       1. **Thiết lập Pattern trước khi mở Đoạn nối (`Establish Pattern First`)**: Trên Nhóm 2, đoạn nối `ScalePassage` dài chỉ được phép bắt đầu **sau khi pattern của section đó đã vang lên ít nhất 1 ô nhịp trọn vẹn** (`passage.start >= section.start * epb + epb`) để tai người nghe đã nhận diện rõ *Chaconne*, *Gigue* hoặc *Sarabande*, và ngay khi đáp xuống `passage.target` thì pattern Nhóm 2 lập tức quay trở lại.
       2. **Giữ "Nhịp mạch Bass đặc trưng" của Pattern bên dưới Đoạn nối (`Characteristic Bass Underpinning`)**: Trong lúc bè Cao (`Voice 1`) chạy đoạn nối scale xuyên 1–4 ô nhịp (bao gồm cả các nhịp `retreat` thật), bè Trầm (`Voice 3`) giữ nguyên hình thái nhịp đặc trưng của chính pattern Nhóm 2 đó (ground bass bước xuống ở `_chaconne_bass_slots` cho `bach_chaconne`; nhấn **phách 1 và trọng âm Phách 2 `accent`** cho `bach_sarabande` / Brouwer `sarabande`; nhịp chấm dôi + pickup cuối ô cho `bach_gigue`), tất cả đều lọc qua `_playable` với các nốt scale phía trên.
       3. **Thay thế trực tiếp trong Ngân sách 30%**: Tại các ô nhịp Nhóm 2 mà đoạn nối `ScalePassage` đi qua, `ScalePassage` thay thế luôn câu scale nội tại nửa ô của những ô nhịp đó (chỉ tính số eighths của `ScalePassage` một lần vào ngân sách $\le 30\%\ \text{body\_eighths}$, không tính trùng).
3. **Nhóm 3 — Các Pattern nhận Overlay Scale ở cả cấp độ Sub-bar ($2 \le L < \text{epb}$) và Multi-bar ($1–4$ ô nhịp)**:
   - **Bach (`bach`)**: `bach_bourree`, `bach_gavotte`, `bach_fuga` *(riêng trên `bach_fuga`, khi bè Cao `Voice 1` chạy scale, bè Trầm `Voice 3` **giữ nguyên chủ đề đối âm trễ 2 ô `_fuga_motif`** thay vì bị thay bằng nốt bass nhịp đơn giản, đảm bảo mạch phức điệu 2 bè không bị đứt)*.
   - **Sor (`classic`)**: `study`, `galop`, `mozart_var`, `elegiaque`, `cantabile`.
   - **Villa-Lobos (`villa`)**: `villa_pattern`, `chord_melody`.
   - **Barrios (`barrios`)**: `andante`, `choro`, `polca`, `hemiola`, `vals`, và `preludio` không khung.
   - **Brouwer (`brouwer`)**: `noviembre`, `brouwer_etude`, `elogio_pizz` *(trên `elogio_pizz`, nếu ô nhịp có cú Bartók slap `staccato + accent` tại eighth 3 thì giữ nguyên cú slap đối với scale ngắn sub-bar, hoặc chỉ cho phép đoạn nối dài $\ge 1$ bar với $\text{net\_span} \ge 6$ đi xuyên qua)*.

---

### 2.2. Định Nghĩa Thống Nhất Độ Dài $L$ & Mật Độ Hạt Nốt (Eighths vs Sixteenths)

#### A. Định nghĩa độ dài $L$ (không chồng lấn biên)
Mỗi ô nhịp (`bar`) chứa `epb` móc đơn (`8` ở `4/4`, `6` ở `3/4` và `6/8`). Một đoạn scale bắt đầu tại móc đơn `start` và kết thúc (đáp đích) tại móc đơn `target` có **độ dài bước chạy** là:
$$L = \text{target} - \text{start} \quad (\text{đơn vị: eighths})$$
- Khi chạy trên lưới **móc đơn (`eighths`)**: gồm $L$ nốt móc đơn trên khoảng `[start, target)` và đáp vào nốt đích tại `target` (tổng cộng $L + 1$ điểm tấn công liên tiếp).
- Khi chạy trên lưới **móc kép (`sixteenths`)**: gồm $2L$ nốt móc kép trên khoảng `[start * 2, target * 2)` và đáp vào nốt đích tại `target * 2` (tổng cộng $2L + 1$ điểm tấn công liên tiếp).

Toàn bộ các đoạn ứng viên được chia thành **3 phân khúc độ dài rời nhau (Disjoint Tiers)**:
1. **Cấp độ Sub-bar (dưới 1 ô nhịp)**: $2 \le L < \text{epb}$ (tức `2..7` eighths ở `4/4`, `2..5` eighths ở `3/4` và `6/8`).
2. **Cấp độ Multi-bar ngắn (`1–2` ô nhịp)**: $\text{epb} \le L \le 2 \times \text{epb}$ (tức `8..16` eighths ở `4/4`, `6..12` eighths ở `3/4` và `6/8`).
3. **Cấp độ Multi-bar dài (`>2–4` ô nhịp)**: $2 \times \text{epb} < L \le 4 \times \text{epb}$ (tức `17..32` eighths ở `4/4`, `13..24` eighths ở `3/4` và `6/8`).

#### B. Lựa chọn Móc đơn (`eighths`) hay Móc kép (`sixteenths`)
Thời lượng vật lý của $L$ eighths là $\text{Duration (s)} = L \times \frac{30}{\text{bpm}}$ (do MusicXML luôn ghi đơn vị phách là nốt đen). Với hằng số độc lập `SCALE_SIXTEENTH_MIN_BPM = 88`:
- **Móc kép (`sixteenths`, `0.25` beat)**:
  - Áp dụng cho các đoạn **Sub-bar ($2 \le L < \text{epb}$)** và **1–2 ô nhịp ($\text{epb} \le L \le 2 \times \text{epb}$)** khi $\text{BPM} \ge \text{SCALE\_SIXTEENTH\_MIN\_BPM}$ (`88`), trừ nhịp `6/8` quá nhanh ($\text{BPM} > 116$) khi kéo dài $> \text{epb}$.
  - Áp dụng cho **nửa sau / ô nhịp cuối (`climax bar`)** của đoạn scale dài `>2–4` ô nhịp ($2 \times \text{epb} < L \le 4 \times \text{epb}$) khi $\text{BPM} \ge 88$.
- **Móc đơn (`eighths`, `0.5` beat) hoặc Tăng tốc (`8th -> 16th`)**:
  - Áp dụng khi $\text{BPM} < 88$, ở nhịp `6/8` nhanh kéo dài, hoặc ở **các ô mở đầu của đoạn scale dài `>2–4` ô nhịp** để câu chạy có đà tăng tốc tự nhiên thay vì dàn trải móc kép quá dài.
  - Trong phần đang đi móc đơn, nếu giữa hai mốc eighth liền kề có khoảng nhảy $\left|\text{melody}[e+1] - \text{melody}[e]\right| \ge 3$ bán cung và chỉ cách nhau 1 eighth, chẻ cục bộ eighth $e$ đó thành 2 móc kép để bước qua bậc thang âm ở giữa.

---

### 2.3. Thuật Toán Dò Sóng Có Retreat (`detect_price_impulses`) & Thứ Tự Ưu Tiên Waypoint

#### A. Thuật toán 4 bước phát hiện sóng trên `raw_pitches`
Hàm dò quét trên `raw_pitches` bên trong từng vùng thân bài `[sec_start, sec_end)` (bỏ qua các ô `_PEDAL`):

1. **Bước 1 — Phân rã các Nhịp Đơn Điệu Cơ Sở (`Primitive Legs`)**:
   - **Up-leg ($d = +1$)**: Chuỗi các bước liên tiếp có $\Delta p_e = \text{raw}[e+1] - \text{raw}[e] \ge 0$, có ít nhất 1 bước $> 0$, và không chứa đoạn phẳng (`flat`) nội tại nào dài $\ge \text{PERIOD}$ (`4` eighths).
   - **Down-leg ($d = -1$)**: Chuỗi các bước liên tiếp có $\Delta p_e \le 0$, có ít nhất 1 bước $< 0$, và không chứa đoạn phẳng nội tại $\ge 4$ eighths.
   - **Flat-hold ($d = 0$)**: Đoạn giá đứng yên ($\Delta p_e = 0$) kéo dài $\ge 4$ eighths.
2. **Bước 2 — Gộp sóng có `Retreat` (`Wave Coalescing`)**:
   Một chuỗi `Impulse Leg 1` ($d$) $\rightarrow$ `Retreat Leg` ($-d$) $\rightarrow$ `Impulse Leg 2` ($d$) (và tối đa thêm 1 cặp `Retreat 2` $\rightarrow$ `Impulse 3`) được gộp ứng viên khi nhịp `Retreat` thỏa mãn 4 điều kiện cục bộ:
   - **Độ dài cục bộ**: $1 \le \text{len}(\text{retreat}) \le 3$ eighths và $\text{len}(\text{retreat}) \le \text{len}(\text{impulse\_before})$.
   - **Độ sâu thoái lui ($\le 50\%$)**: $\left|\Delta\text{pitch}(\text{retreat})\right| \le 0.50 \times \left|\Delta\text{pitch}(\text{impulse\_before})\right|$.
   - **Không thủng mốc khởi phát**: $\min(\text{retreat}) > \text{raw}[\text{wave\_start}]$ (khi $d = +1$) hoặc $\max(\text{retreat}) < \text{raw}[\text{wave\_start}]$ (khi $d = -1$).
   - **Phá đỉnh/đáy sau Retreat**: $\text{end\_pitch}(\text{impulse\_after}) > \text{peak}(\text{impulse\_before})$ (khi $d = +1$) hoặc $< \text{trough}(\text{impulse\_before})$ (khi $d = -1$).
3. **Bước 3 — Cắt tỉa biên phẳng, Chọn duy nhất 1 cửa sổ $\le 4$ ô nhịp & Kiểm tra Bảng Điều Kiện Bất Biến**:
   - Cắt bỏ các eighths phẳng ($\Delta p = 0$) ở đầu sóng trước khi giá nhúc nhích và ở đuôi sóng sau khi đã chạm cực trị.
   - Nếu một sóng gộp dài $> 4 \times \text{epb}$ eighths, trượt cửa sổ con hợp lệ độ dài $L \le 4 \times \text{epb}$ (bắt đầu tại điểm mở một impulse leg và kết thúc tại cực trị của một impulse leg) và **chỉ giữ lại tối đa 1 cửa sổ có `Score` cao nhất trên mỗi sóng gộp**.
   - Khớp `target` vào phách mạnh (`target % epb in meter.strong_eighths`) nếu cực trị nằm tại phách mạnh hoặc giữ nguyên cao độ sang phách mạnh kế cận.
   - Sau khi đã chốt cố định $L = \text{target} - \text{start}$, kiểm tra một lần duy nhất theo **Bảng Điều Kiện Bất Biến** (thống nhất một nghĩa cho mọi phân khúc $L$):

     | Phân khúc $L = \text{target} - \text{start}$ | Số Retreat tối đa | Độ dài tối đa 1 Retreat | Tổng eighths Retreat tối đa | Biên độ ròng $\text{net\_span}$ | Độ dốc & Hiệu suất đường đi $\text{efficiency} = \frac{\text{net\_span}}{\text{total\_path}}$ |
     |---|---|---|---|---|---|
     | **Sub-bar ngắn**: $2 \le L \le 3$ | `0` | `0` | `0` | $\ge 4$ bán cung | $\frac{\text{net\_span}}{L} \ge 1.0$, $\text{efficiency} = 1.0$ |
     | **Sub-bar vừa**: $4 \le L < \text{epb}$ | `1` | `1` eighth | `1` eighth | $\ge 4$ bán cung | $\frac{\text{net\_span}}{L} \ge 1.0$, $\text{efficiency} \ge 0.50$ |
     | **1–2 ô nhịp**: $\text{epb} \le L \le 2 \times \text{epb}$ | `1` | `2` eighths | $\lfloor 0.30 \times L \rfloor$ | $\ge 5$ bán cung | $\text{efficiency} \ge 0.45$ |
     | **>2–4 ô nhịp**: $2 \times \text{epb} < L \le 4 \times \text{epb}$ | `2` | `3` eighths | $\lfloor 0.30 \times L \rfloor$ | $\ge 6$ bán cung | $\text{efficiency} \ge 0.45$ |

4. **Bước 4 — Chấm điểm xếp hạng (`Score`) với Hiệu suất Hiệu chỉnh cho Retreat**:
   - Vì một nhịp retreat hợp lệ làm tăng mẫu số `total_path` thêm $2 \times \left|\Delta\text{pitch}(\text{retreat})\right|$, nếu nhân trực tiếp với `efficiency` thô thì sóng có retreat luôn bị tụt điểm nhiều hơn một hằng số cộng nhỏ.
   - Do đó, ta dùng **Hiệu suất hiệu chỉnh (`adjusted_efficiency`)** (bù lại đúng quãng đường của các nhịp retreat hợp lệ, nhưng vẫn phạt nặng mọi dao động nhiễu ngoài retreat) kết hợp với hệ số nhân `retreat_multiplier`:
     $$\text{adjusted\_efficiency} = \min\left(1.0,\ \frac{\text{net\_span} + 2 \times \sum_{r \in \text{retreats}} \left|\Delta\text{pitch}(r)\right|}{\text{total\_path}}\right)$$
     $$\text{retreat\_multiplier} = \begin{cases} 1.15 & \text{nếu có } \ge 1 \text{ retreat hợp lệ} \\ 1.00 & \text{nếu đi thẳng 1 chiều} \end{cases}$$
     $$\text{Score} = \text{net\_span} \times \left(1.0 + 0.5 \times \frac{\text{net\_span}}{L}\right) \times \text{adjusted\_efficiency} \times \text{retreat\_multiplier}$$

#### B. Thứ tự ưu tiên khi dựng Waypoint (`Waypoint Resolution Hierarchy`)
Người nghe thực tế nghe đường giai điệu `melody` trên nền hợp âm `chord_at[bar]`. Để các ràng buộc không xung đột nhau khi `melody` đã được lượng tử hóa hợp âm và đặt tầm cữ, bộ dựng nốt `_realize_scale_passage` giải quyết theo **thứ tự ưu tiên nghiêm ngặt từ 1 đến 5**:

1. **Ưu tiên 1 — Nốt Đích (`target`) và Phách Mạnh (`meter.strong_eighths`) luôn giữ đúng `melody`**:
   - Tại `target` và tại mọi mốc phách mạnh (`eighth % epb in meter.strong_eighths`) nằm trong đoạn scale, cao độ phải bằng đúng `ctx.melody[eighth]`.
   - Nếu tại một phách mạnh mà `ctx.melody[eighth]` đi ngược chiều `raw_pitches` (do `quantize_strong_beats` kéo về nốt hợp âm), đường scale **chấp nhận bước vào nốt hợp âm đó của `melody`**.
2. **Ưu tiên 2 — Khớp Điểm Vào ($\le 2$ bán cung) và Thế tay Khả thi (`_quarter_ok` & `_playable`)**:
   - Nốt đầu tiên của đoạn scale phải trùng với nốt `melody` đang ngân ngay trước `start` hoặc cách nó $\le 2$ bán cung.
   - Mọi chùm móc kép trong từng phách đen phải thỏa mãn `_quarter_ok` (kiểm tra trên cao độ vang `[pitch + ctx.semitones for pitch in group]`) và thỏa mãn `_playable` với nốt Bass đang ngân.
3. **Ưu tiên 3 — Các Phách Yếu đi theo hướng `raw_pitches` (bao gồm `retreat` thật)**:
   - Giữa các mốc phách mạnh, các nốt trên phách yếu bước liền bậc theo hướng của `raw_pitches`: bước lên khi `raw` tăng, và **đổi chiều bước xuống tại đúng `retreat_spans`** khi `raw` giảm (hoặc ngược lại ở sóng giảm).
4. **Ưu tiên 4 — Nốt hoa mỹ khi giá đứng yên tạm thời (`raw[e+1] == raw[e]`)**:
   - Khi hai mốc eighth liền kề có giá đứng yên nằm giữa con sóng, việc nhích sang bậc thang âm kế cận được coi là **hoa mỹ (ornamental neighbor)** chứ không phải dữ liệu giá: **chỉ được lệch tối đa 1 bậc thang âm** ở nửa sau phách và **bắt buộc phải quay về đúng `ctx.melody[e+1]`** ở móc đơn kế tiếp.
5. **Ưu tiên 5 — Cơ chế Hủy Bỏ An Toàn (`Graceful Abort`)**:
   - Nếu hai phách mạnh liền kề trong `ctx.melody` cách nhau một quãng quá rộng mà số hạt nốt ở giữa không đủ để nối liền bậc (mỗi bước $\le 2$ bán cung) hoặc không có phương án nào thỏa `_quarter_ok` / `_playable`, bộ dựng **hủy bỏ `ScalePassage` đó** (giữ nguyên `melody` của pattern gốc) và chuyển ngân sách cho ứng viên kế tiếp.

---

### 2.4. Ngân Sách 30% Thống Nhất & Quy Tắc Giữ Nguyên Figuration Nội Tại

- **Chốt một mẫu số duy nhất (`body_eighths`)**:
  - Gọi `body_eighths` là tổng số móc đơn của tất cả các ô thân bài (các ô không thuộc `_PEDAL`; với các synthetic test fixture không có `_PEDAL` thì `body_eighths == total_eighths`).
  - Trần thời lượng scale tối đa của toàn bài là:
    $$\text{max\_scale\_eighths} = \lfloor 0.30 \times \text{body\_eighths} \rfloor$$
- **Quy tắc phân bổ giữa Figuration nội tại và Overlay (`ScalePassage` + `perpetual`)**:
  1. Các figuration chạy ngón nhận dạng của bản thân pattern ở Nhóm 2 (nửa sau `bach_gigue`, breakout `bach_chaconne`, passing của `bach_sarabande`, modal swarm của Brouwer `sarabande`) tại các ô không có đoạn nối `Major Bridge Impulse` **luôn được giữ nguyên 100%**, kể cả khi tự thân chúng đã vượt quá `max_scale_eighths`.
  2. Bộ điều phối đếm số eighths thực tế của các figuration nội tại trên những ô Nhóm 2 giữ nguyên (`intrinsic_scale_eighths`), và khi một ứng viên `ScalePassage` là **Sóng Lớn (`Major Bridge Impulse`: $L \ge \text{epb}, \text{net\_span} \ge 6$, nằm sau ô mở đầu section)** đi qua các ô Nhóm 2, chi phí ngân sách tăng thêm chỉ là phần chênh lệch `passage_eighths - replaced_intrinsic_eighths` trên các ô đó.
  3. Ngân sách còn lại dành cho bộ allocate thêm (`ScalePassage` và `perpetual` của Barrios) đảm bảo tổng số eighths chạy scale toàn bài (cả `ScalePassage`, `perpetual` và `unreplaced_intrinsic_scale_eighths`) luôn $\le \text{max\_scale\_eighths}$. Nếu bản thân `intrinsic_scale_eighths` ban đầu đã $\ge \text{max\_scale\_eighths}$, `overlay_budget == 0` (không chèn thêm `ScalePassage` mới làm tăng tổng số eighths).
- **Khoảng thở tối thiểu giữa hai đoạn chạy (`Minimum Cooldown Gap`)**:
  - Hai đoạn `ScalePassage` được chọn $P_1$ (trước) và $P_2$ (sau) không được giao nhau và phải cách nhau ít nhất 1 ô nhịp tính từ điểm đáp của đoạn trước đến điểm mở của đoạn sau:
    $$P_2.\text{start} - P_1.\text{target} \ge \text{epb}$$
  - Đồng thời, một `ScalePassage` cũng phải giữ khoảng cách $\ge \text{epb}$ eighths với bất kỳ ô nhịp Nhóm 2 nào có phát sinh scale nội tại nằm ngoài passage đó.

---

### 2.5. Giải Pháp Kỹ Thuật Để Đoạn Scale "Mix Well" Với Pattern Trước Và Sau Nó

```
[ Pattern Trước ] ──(1. Điểm Vào / Entry)──► [ Đoạn Scale (2. Bè Đệm / Underpinning) ] ──(3. Điểm Ra / Exit)──► [ Pattern Sau ]
```

#### 1. Điểm Vào (Seamless Entry — Từ Pattern trước đi vào Scale)
- **Khớp nối cao độ liền bậc (Stepwise Pitch Handoff)**:
  - Nốt mở đầu của đoạn scale bắt đầu ngay tại cao độ giai điệu đang ngân của pattern trước tại điểm cắt, hoặc cách $\le 2$ bán cung hướng về phía con sóng.
- **Giữ nguyên phần mở đầu ô nhịp khi Scale vào ở giữa ô (Sub-bar Dovetail)**:
  - Nếu `passage.start` nằm sau phách mạnh đầu ô nhịp (`passage.start % epb != 0`), toàn bộ các nốt Bass (`low`) và nốt rải (`support`) của pattern trước ở đầu ô nhịp đó được giữ nguyên và ngân tiếp làm bàn đạp hòa âm.
- **Vuốt lực gảy Điểm Vào (Entry Velocity Clamping)**:
  - Khi đi lên (crescendo về `_MELODY_APEX = 72`), nếu pattern liền trước đã ở mức velocity $\ge 68$ (hoặc $\ge 72$), việc giữ nguyên mức đó sẽ làm câu scale mất đà tăng lực hoặc đi lùi. Do đó, velocity khởi đầu của câu scale đi lên được lấy bằng:
    $$v_{\text{start}} = \min(\text{prev\_velocity},\ \text{\_MELODY\_APEX} - 6) = \min(\text{prev\_velocity},\ 66)$$
    rồi mới vuốt tăng dần đều (`swell`) lên tới `_MELODY_APEX` (`72`) tại `target`.
  - Khi đi xuống, câu scale mở đầu tại $\min(\max(\text{prev\_velocity}, \text{\_MELODY}), \text{\_MELODY\_APEX})$ và vuốt mềm về mức nền của pattern kế tiếp.

#### 2. Trong Khi Chạy Scale (Accompaniment & Texture — Theo đúng Pattern & `meter.strong_eighths`)
- **Bè Trầm (`low` - Voice 3) duy trì nhịp mạch đặc trưng của Pattern**:
  - Với `bach_fuga`: **giữ nguyên đường Bass đối âm trễ 2 ô (`_fuga_motif`)** của Fuga (chỉ kiểm tra `_bach_keep_bass_below` để không vượt lên trên các nốt scale).
  - Với các đoạn nối `Major Bridge Impulse` ($L \ge \text{epb}, \text{net\_span} \ge 6$) chạy qua **Nhóm 2**: giữ nguyên nhịp mạch Bass đặc trưng của chính vũ điệu đó bên dưới câu scale (ground bass ở `_chaconne_bass_slots` cho `bach_chaconne`; nhấn **phách 1 và trọng âm Phách 2 `accent`** cho `bach_sarabande` & Brouwer `sarabande`; nhịp chấm dôi + pickup cuối ô cho `bach_gigue`), được kiểm tra qua `_playable` với các nốt scale phía trên.
  - Với các pattern Nhóm 3 khác trên cả 5 composer: trên các mốc phách mạnh đọc trực tiếp từ `ctx.strong` (`meter.strong_eighths` — tức eighth `(0, 4)` ở `4/4`, eighth `(0, 3)` ở `6/8`, và eighth `(0,)` ở `3/4`), bè Bass gảy nốt Gốc (`Root`) hoặc Bậc 5 (`Fifth`) của `chord_at[bar]` thỏa mãn `_playable` với toàn bộ các nốt scale vang trong phách mạnh đó.
- **Bè Giữa (`support` - Voice 2) nhường đường thông minh (Selective Thinning)**:
  - Trong khoảng `[passage.start, passage.target)` khi bè Cao chạy móc kép, lược bỏ các nốt `support` trùng thời điểm (`_drop_overlap`) để giải phóng ngón `i-m-a`, chỉ giữ tối đa 1 nốt hợp âm bè Trung tại đúng điểm mở đầu `passage.start` nếu thuộc phách mạnh và thỏa `_playable`.

#### 3. Điểm Ra (Landing & Exit — Từ Scale trở lại Pattern sau)
- **Hội tụ vào Nốt Trụ tại `target` & Tiếp quản đồng bộ**:
  - Khoảng ghi đè (`_splice` trên `lead` và `_drop_overlap` trên `support`) chỉ kéo dài trên nửa khoảng mở `[passage.start, passage.target)` đối với các nốt dẫn, và nốt đích tại đúng `passage.target` hòa nhập trực tiếp vào phách mạnh của pattern phía sau (bè Bass đánh phách mạnh tại `target` cùng lúc với nốt đích của scale, và bè Trung rải lại bình thường từ ngay móc đơn/móc kép kế tiếp).

---

## 3. Kiến Trúc Pipeline & Các File Thay Đổi Cụ Thể

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                     1. model.py & guitar_scales.py                           │
│  • `model.py`: Bổ sung dataclass `PriceImpulse` (không thêm API thừa vào     │
│    `Phrase`).                                                                │
│  • `guitar_scales.py` (module riêng cho Guitar, tách khỏi `phrasing.py`):    │
│    Chứa `SCALE_SIXTEENTH_MIN_BPM = 88`, `detect_price_impulses(...)` (nhận   │
│    `epb` và `strong_eighths = meter.strong_eighths`), `_allocate_scale_...`  │
│    và `_realize_scale_passage(...)`.                                         │
└───────────────────────────────────────┬──────────────────────────────────────┘
                                        ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                     2. render.py & guitar.py                                 │
│  • `render.py` gọi `detect_price_impulses(raw_pitches, ...)` ĐÚNG 1 LẦN và   │
│    truyền `raw_pitches` + `impulses` xuống `render_guitar_score`.            │
│  • Nếu test cũ gọi trực tiếp `render_guitar_score` mà không truyền           │
│    `raw_pitches`, đặt `impulses = ()` (tuyệt đối không dò lại trên `pitches` │
│    đã lượng tử hóa).                                                         │
│  • `_place_melody` dùng `impulses` để gộp chung phép đặt tầm cữ / nén        │
│    (`_compress_monotone`) cho các `Phrase` bị cắt ngang giữa 1 `PriceImpulse`│
│    dài, rồi gắn `impulses` lên `_Ctx` cho `render_patterned_voices`.         │
└───────────────────────────────────────┬──────────────────────────────────────┘
                                        ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                     3. guitar_patterns.py & 5 Module Composer                │
│  • Với biến động nhỏ/vừa: giữ nguyên 100% figuration nội tại của Nhóm 2      │
│    (`bach_chaconne`, `bach_gigue`, `bach_sarabande`, Brouwer `sarabande`).   │
│  • Với sóng lớn (`Major Bridge Impulse`: L >= epb, net_span >= 6, sau ô mở   │
│    đầu section): cho phép `ScalePassage` dài (1–4 ô nhịp) làm đoạn nối ở     │
│    giữa cả Nhóm 2 và Nhóm 3 trên nền Bass đặc trưng của chính pattern đó.    │
│  • Tổng thời lượng scale (cả nội tại lẫn đoạn nối/overlay) <= 30%            │
│    `body_eighths`; bảo vệ `ScalePassage` trước `_insert_bells`,              │
│    `_relax_texture`, `_shape_dynamics` và `_slur`.                           │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 3.1. `backend/app/sonify/model.py`
- Bổ sung dataclass `PriceImpulse` (không thêm `Phrase.trough` / `Phrase.fall`):
  ```python
  @dataclass(frozen=True)
  class PriceImpulse:
      start: int                                      # eighth bắt đầu
      target: int                                     # eighth đáp đích
      direction: Literal["up", "down"]                # hướng chủ đạo ("up" | "down")
      net_span: int                                   # |raw[target] - raw[start]| (semitones)
      adjusted_efficiency: float                      # hiệu suất đường đi đã hiệu chỉnh retreat
      score: float                                    # điểm xếp hạng
      retreat_spans: tuple[tuple[int, int], ...] = () # các khoảng (r_start, r_end) hồi giá thật
      sub_bar: bool = False                           # True nếu target - start < epb
  ```

### 3.2. `backend/app/sonify/guitar_scales.py` (Module mới cho Guitar Scale Engine)
- Đặt toàn bộ logic dò sóng và dựng scale của Guitar tại đây (không đặt trong `phrasing.py` để không kéo luật scale của Guitar sang `symphony`, `jazz`, `minimalist`, `ambient`):
  - Hằng số `SCALE_SIXTEENTH_MIN_BPM = 88` (giữ nguyên `BARRIOS_TREMOLO_MIN_BPM = 90` cho Grand Solo và Tremolo).
  - Hàm `detect_price_impulses(raw_pitches: Sequence[int], section_starts: tuple[int, ...], *, epb: int, strong_eighths: tuple[int, ...], pedal_bars: frozenset[int] = frozenset()) -> tuple[PriceImpulse, ...]` (không đặt default `strong_eighths=(0, 4)`; caller truyền `meter.eighths_per_bar` và `tuple(meter.strong_eighths)`).
  - Hàm `_allocate_scale_passages(ctx, patterns, levels, intrinsic_scale_bars)` và `_realize_scale_passage(ctx, passage, patterns, lead, support, low)` tuân thủ thứ tự ưu tiên Waypoint 1–5 và cơ chế `Graceful Abort`.

### 3.3. `backend/app/sonify/render.py` & `backend/app/sonify/guitar.py`
1. **Trong `backend/app/sonify/render.py`**:
   - Nhánh `if variant == "guitar":` gọi `impulses = detect_price_impulses(raw_pitches, ...)` **một lần duy nhất** trên `raw_pitches` gốc và truyền cả `raw_pitches=raw_pitches` lẫn `impulses=impulses` vào `render_guitar_score(...)`.
2. **Trong `backend/app/sonify/guitar.py`**:
   - `render_guitar_score` nhận `raw_pitches: list[int] | None = None` và `impulses: tuple[PriceImpulse, ...] | None = None`.
   - Khi `impulses is None`: nếu `raw_pitches is not None` thì gọi `detect_price_impulses(raw_pitches, ...)` một lần; nếu `raw_pitches is None` (các unit test cũ gọi trực tiếp không truyền `raw_pitches`) thì đặt `impulses = ()` để không bao giờ dò sóng lại trên `pitches` đã qua `quantize_strong_beats`.
   - Trong `_place_melody`: nếu một `PriceImpulse` trong `impulses` vắt qua biên giữa hai `Phrase` liên tiếp (do chạm trần `MAX_EIGHTHS = 32` hoặc nốt nghỉ), gộp chung dải `[p1.start, p2.end)` khi tính `shift` và `_compress_monotone` để cả hai `Phrase` dùng chung một ánh xạ bậc thang âm, không bị bẻ gãy độ dốc tại biên câu.
   - Gắn `raw_pitches` và `impulses` lên `_Ctx` trong `render_patterned_voices` (không gọi lại `detect_price_impulses` trong `guitar_patterns.py`).

### 3.4. `backend/app/sonify/guitar_patterns.py` & 5 Module Composer
- Loại trừ hoàn toàn Nhóm 1 (`tremolo`, `etude1`, `etude11`, `_catedral_preludio` `preludio`, `thumb_cantabile`) khỏi `ScalePassage`.
- Với Nhóm 2 (`bach_chaconne`, `bach_gigue`, `bach_sarabande`, Brouwer `sarabande`):
  - Giữ nguyên 100% figuration nội tại ở các ô có biến động nhỏ/vừa ($L < \text{epb}$ hoặc $\text{net\_span} < 6$) và ở ô mở đầu mỗi section.
  - Cho phép các **Sóng Lớn (`Major Bridge Impulse`: $L \ge \text{epb}$ từ 1–4 ô nhịp VÀ $\text{net\_span} \ge 6$ bán cung, bắt đầu sau ô mở đầu section)** tạo `ScalePassage` làm đoạn nối ở giữa cả Nhóm 2 lẫn Nhóm 3, giữ nguyên nhịp mạch Bass đặc trưng của pattern Nhóm 2 bên dưới câu scale và tính phần chênh lệch `passage_eighths - replaced_intrinsic_eighths` vào ngân sách `<= 30% body_eighths`.
- Khi áp dụng `ScalePassage` trên Nhóm 2 và Nhóm 3:
  - Loại các ô có `ScalePassage` khỏi `bell_bars`.
  - Đánh dấu các eighths của `ScalePassage` vào tập `scale_eighths` để `_relax_texture` (trong `_smooth_boundaries`), `_shape_dynamics` và `_slur` không ghi đè hoặc làm biến dạng đường cong velocity và hạt nốt của đoạn scale.

### 3.5. `backend/tests/test_sonify_guitar.py`
- Bổ sung và cập nhật bộ kiểm thử:
  1. **Test `detect_price_impulses`**:
     - Kiểm tra cả 3 phân khúc rời nhau: Sub-bar ($2 \le L < \text{epb}$), 1–2 ô nhịp ($\text{epb} \le L \le 2 \times \text{epb}$), và >2–4 ô nhịp ($2 \times \text{epb} < L \le 4 \times \text{epb}$) trên các nhịp `4/4` (`epb=8`), `3/4` (`epb=6`), `6/8` (`epb=6`, `strong_eighths=(0, 3)`).
     - Kiểm tra sóng có `retreat` thật (`Up – Retreat – Up` và `Down – Retreat – Down`) được nhận diện đúng và đạt `Score` cao nhờ `adjusted_efficiency`, trong khi vùng sideway răng cưa (`efficiency < 0.45`) hoặc thoái lui sâu ($> 50\%$) bị loại bỏ.
     - Kiểm tra mỗi sóng gộp dài $> 4 \times \text{epb}$ chỉ phát ra tối đa 1 cửa sổ $\le 4 \times \text{epb}$, và khoảng thở giữa hai passage luôn thỏa $P_2.\text{start} - P_1.\text{target} \ge \text{epb}$.
  2. **Test Bảo toàn Pattern, Scale Nội Tại & Đoạn Nối Sóng Lớn (`Major Bridge Impulse`)**:
     - Kiểm tra Nhóm 1 (`tremolo`, `etude1`, `etude11`, `_catedral_preludio` và `thumb_cantabile`) không bị chèn `ScalePassage`.
     - Kiểm tra Nhóm 2 (`bach_chaconne`, `bach_gigue`, `bach_sarabande` và Brouwer `sarabande`) giữ nguyên phần mở đầu ô nhịp (bariolage / hợp âm gãy / trọng âm phách 2) ở ô đầu section và trước các biến động nhỏ ($L < \text{epb}$ hoặc $\text{net\_span} < 6$), nhưng cho phép **Sóng Lớn ($L \ge \text{epb}, \text{net\_span} \ge 6$)** sau ô mở đầu section chạy `ScalePassage` dài (1–4 ô nhịp, có `retreat`) làm đoạn nối ở giữa trên nền Bass đặc trưng của chính vũ điệu đó rồi đáp về lại pattern tại `target`.
     - Kiểm tra `bach_fuga` giữ nguyên chủ đề đối âm trễ 2 ô ở bè Trầm (`low`) bên dưới câu scale của bè Cao.
  3. **Test 5 Composer, Sor `1D` (`88 BPM`) & `assert_playable`**:
     - Kiểm tra Sor ở `88 BPM` chạy được scale móc kép nhờ `SCALE_SIXTEENTH_MIN_BPM = 88` mà **không** kích hoạt nhầm `Grand Solo` (`BARRIOS_TREMOLO_MIN_BPM` vẫn ở `90`).
     - Kiểm tra toàn bộ 5 composer vượt qua `assert_playable` (bao gồm `_quarter_ok` trên mọi chùm 4 móc kép, đặc biệt khi Villa-Lobos fallback khỏi dây buông không hợp thế tay) trên cả 5 giọng (`C, D, Eb, A, Bb`).
  4. **Test Ngân sách `<= 30% body_eighths` & Mix Well**:
     - Kiểm tra `overlay_budget` không bao giờ làm tổng eighths chạy scale vượt quá $\lfloor 0.30 \times \text{body\_eighths} \rfloor$ (trừ trường hợp bản thân intrinsic figuration của pattern đã $\ge 30\%$, khi đó `overlay_budget == 0`).
     - Kiểm tra vận tốc Điểm Vào luôn crescendo lên `_MELODY_APEX` (`72`) mà không bị đi lùi khi pattern trước đang ở velocity cao, và Điểm Ra đáp đúng vào `melody[target]` trên phách mạnh.
