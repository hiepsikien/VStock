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
   - **Quy tắc toàn vẹn Passage**: Nếu khoảng `[passage.start, passage.target]` chạm vào bất kỳ ô nhịp nào thuộc Nhóm 1, **loại bỏ toàn bộ `ScalePassage` đó** (tuyệt đối không khoét rỗng riêng ô Nhóm 1 làm đứt đôi câu chạy).
2. **Nhóm 2 — Các Pattern có Cửa Sổ Scale Nội Tại (`bach_chaconne`, `bach_gigue`, `bach_sarabande`, Brouwer `sarabande`) — Cơ chế Phân Tầng 2 Cấp (`Two-Tier Threshold`)**:
   - Ở 4 pattern này, câu chạy scale đã là **một thành phần cấu trúc nằm trong chính ô nhịp của pattern**:
     - `bach_chaconne`: Nửa đầu ô nhịp (`0 .. scale_at`, tức 2 phách đầu ở `4/4` hoặc 1 phách đầu ở `3/4`) là hợp âm trụ + móc kép *bariolage* đan dây; nửa sau (`scale_at .. epb * 2`) là cửa sổ chạy `_fitting_scale` khi `breakout`.
     - `bach_gigue`: Nửa đầu ô nhịp (`0 .. scale_at`) là tiết tấu hợp âm gãy đặc trưng của điệu Gigue (`down`, `pickup`, `inner`); nửa sau (`scale_at .. epb * 2`) là cửa sổ chạy `_fitting_scale` khi câu đi lên.
     - `bach_sarabande` & Brouwer `sarabande`: Phách 1 và **trọng âm Phách 2 (`accent`)** (kèm mordent ở Bach) là dấu hiệu nhận diện sống còn của điệu Sarabande; phần đuôi ô nhịp sau phách 2 (`passing .. epb` ở Bach, `figure_at .. epb` ở Brouwer) là cửa sổ chạy passing scale / modal swarm.
   - **Cấp 1 — Khi biến động nhỏ / vừa ($L < \text{epb}$ hoặc $\text{net\_span} < 6$ bán cung)**:
     - **Không cắt đè `ScalePassage` ngắn lên đầu ô nhịp của Nhóm 2**: giữ nguyên 100% phần *bariolage* đầu ô của `bach_chaconne`, nhịp hợp âm gãy đầu ô của `bach_gigue`, và trọng âm phách 2 của `bach_sarabande` / Brouwer `sarabande`.
     - Nếu ô Nhóm 2 có biến động giảm (`downward plunge`) trong phạm vi 1 ô mà điều kiện `_rises(phrase)` cũ bỏ sót, **không gọi `_fitting_scale`** (vì `_fitting_scale` chỉ xây đường đi lên) mà dùng `_realize_scale_passage` cắt đúng vào **cửa sổ nội tại sẵn có ở nửa sau ô nhịp** (`scale_at .. epb * 2` cho Chaconne/Gigue, hoặc `passing .. epb` / `figure_at .. epb` cho Sarabande).
     - Cửa sổ giảm Cấp 1 này **không tham gia tính khoảng thở `Minimum Cooldown Gap`** (nên nếu nằm ở nửa sau ô nhận diện thì vẫn cho phép đoạn nối `Major Bridge Impulse` mở ngay ở đầu ô kế tiếp), và được cấp phát ở **bước cuối cùng trong quy trình 4 bước ngân sách ở Mục 2.4**: chỉ giữ các cửa sổ Cấp 1 không bị `ScalePassage` nào thay thế, theo thứ tự `score`, cho đến khi đầy phần `room` còn lại (nếu `room == 0` thì không giữ cửa sổ Cấp 1 nào).
   - **Cấp 2 — Khi biến động là Sóng Lớn (`Major Bridge Impulse`: $L \ge \text{epb}$ từ 1 đến 4 ô nhịp VÀ $\text{net\_span} \ge 6$ bán cung)**:
     - Đúng như truyền thống *Chaconne (BWV 1004)*, *Les Doubles* của Bach và *El Decamerón Negro* của Brouwer, một đợt sóng lớn ($L \ge \text{epb}, \text{net\_span} \ge 6$) **được phép mở thành một `ScalePassage` dài (1–4 ô nhịp) làm đoạn nối (connecting bridge / passaggio) ở giữa cho cả Nhóm 2 lẫn Nhóm 3** thay vì bị băm vụn từng nửa ô nhịp, với **3 quy tắc giữ bản sắc Pattern**:
       1. **Thiết lập Pattern trước khi mở Đoạn nối (`Establish Pattern First`)**: Trên một vùng liên tiếp mang cùng một pattern Nhóm 2, đoạn nối `ScalePassage` dài chỉ được phép bắt đầu **sau khi chính pattern Nhóm 2 đó đã vang lên ít nhất 1 ô nhịp trọn vẹn** (tính từ ô đầu tiên mà pattern Nhóm 2 đó xuất hiện, không phải từ `section.start` nếu đầu section là pattern khác), và ngay khi đáp xuống `passage.target` thì pattern lập tức quay trở lại.
       2. **Giữ "Nhịp mạch Bass đặc trưng" theo từng ô nhịp bên dưới Đoạn nối (`Per-Bar Characteristic Bass Underpinning`)**: Trong lúc bè Cao (`Voice 1`) chạy đoạn nối scale xuyên 1–4 ô nhịp (bao gồm cả các nhịp `retreat` thật), bè Trầm (`Voice 3`) được xác định **theo pattern của từng ô nhịp `bar`** mà đoạn nối đi qua: ô thuộc `bach_chaconne` giữ ground bass ở `_chaconne_bass_slots`; ô thuộc `bach_sarabande` / Brouwer `sarabande` nhấn **phách 1 và trọng âm Phách 2 `accent`**; ô thuộc `bach_gigue` giữ nhịp chấm dôi + pickup cuối ô; và nếu đoạn nối đi sang ô thuộc Nhóm 3 (như `bach_bourree`), ô đó lấy gốc hoặc bậc 5 trên `ctx.strong` (hoặc giữ `_fuga_motif` nếu ô đó là `bach_fuga`), tất cả đều lọc qua `_playable` với các nốt scale phía trên.
       3. **Thay thế trực tiếp và Kiểm tra Ngân sách ròng (`room`)**: Tại các ô nhịp Nhóm 2 mà đoạn nối `ScalePassage` đi qua, `ScalePassage` thay thế câu scale có sẵn nửa ô của những ô nhịp đó (và thay thế luôn ứng viên cửa sổ Cấp 1 nếu có trên các ô đó; vì cửa sổ Cấp 1 chưa nằm trong `base_intrinsic_eighths` ở Bước 3 của Mục 2.4, nên $\Delta\text{cost} = \text{passage\_eighths} - \text{replaced\_base\_intrinsic\_eighths}$). Nếu phần `room` còn lại không đủ cho $\Delta\text{cost}$ này (hoặc khi `room == 0`), đoạn nối đó bị loại.
3. **Nhóm 3 — Các Pattern nhận Overlay Scale ở cả cấp độ Sub-bar ($2 \le L < \text{epb}$) và Multi-bar ($1–4$ ô nhịp)**:
   - **Bach (`bach`)**: `bach_bourree`, `bach_gavotte`, `bach_fuga` *(riêng trên `bach_fuga`, khi bè Cao `Voice 1` chạy scale, bè Trầm `Voice 3` **giữ nguyên chủ đề đối âm trễ 2 ô `_fuga_motif`** thay vì bị thay bằng nốt bass nhịp đơn giản, đảm bảo mạch phức điệu 2 bè không bị đứt)*.
   - **Sor (`classic`)**: `study`, `galop`, `mozart_var`, `elegiaque`, `cantabile`.
   - **Villa-Lobos (`villa`)**: `villa_pattern`, `chord_melody`.
   - **Barrios (`barrios`)**: `andante`, `choro`, `polca`, `hemiola`, `vals`, và `preludio` không khung.
   - **Brouwer (`brouwer`)**: `noviembre`, `brouwer_etude`, `elogio_pizz` *(trên `elogio_pizz`: với đoạn nối dài $L \ge \text{epb}$, `ScalePassage` thay thế luôn nốt Bartók slap tại eighth 3 của ô đó; với đoạn chạy ngắn sub-bar $L < \text{epb}$, `ScalePassage` phải vòng tránh eighth 3 để giữ nguyên cú slap `staccato + accent`)*.

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
   - **Khớp `target` vào phách mạnh có hậu kiểm (`Validated Strong-Beat Snap`)**: Nếu cực trị gốc `raw_target` chưa rơi vào phách mạnh nhưng giữ nguyên cao độ sang phách mạnh kế cận `snapped_target`, thử kéo sang `snapped_target` (lúc này $L' = \text{snapped\_target} - \text{start}$ có thể tăng và nhảy phân khúc, ví dụ ở nhịp `3/4` chỉ có phách mạnh tại eighth `0`). Kiểm tra lại `snapped_target` với Bảng Điều Kiện Bất Biến ở phân khúc $L'$ mới: nếu đạt thì dùng `snapped_target`; **nếu bản đã kéo không đạt điều kiện của phân khúc mới thì giữ nguyên cực trị gốc `raw_target`** dù không nằm trên phách mạnh.
   - Sau khi đã chốt cố định $L = \text{target} - \text{start}$, kiểm tra một lần duy nhất theo **Bảng Điều Kiện Bất Biến** (với sub-bar, gộp chung độ dốc $\ge 1.0$ và biên độ $\ge 4$ thành một ngưỡng duy nhất $\text{net\_span} \ge \max(4, L)$):

     | Phân khúc $L = \text{target} - \text{start}$ | Số Retreat tối đa | Độ dài tối đa 1 Retreat | Tổng eighths Retreat tối đa | Biên độ ròng $\text{net\_span}$ | Hiệu suất đường đi $\text{efficiency} = \frac{\text{net\_span}}{\text{total\_path}}$ |
     |---|---|---|---|---|---|
     | **Sub-bar ngắn**: $2 \le L \le 3$ | `0` | `0` | `0` | $\ge \max(4, L)$ bán cung | $\text{efficiency} = 1.0$ |
     | **Sub-bar vừa**: $4 \le L < \text{epb}$ | `1` | `1` eighth | `1` eighth | $\ge \max(4, L)$ bán cung | $\text{efficiency} \ge 0.50$ |
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
- **Quy trình phân bổ ngân sách 1 lượt gồm 4 bước (không phụ thuộc vòng tròn giữa Cửa sổ Cấp 1 và Đoạn nối)**:
  1. **Bước 1 — Đếm `base_intrinsic_eighths`**: `base_intrinsic_eighths` là tổng số eighths chạy scale có sẵn của bản thân pattern ở Nhóm 2 (nửa sau `bach_gigue`, breakout `bach_chaconne`, passing của `bach_sarabande`, modal swarm của Brouwer `sarabande`). Phần này tại các ô không bị đoạn nối thay thế **luôn được giữ nguyên 100% dù tự thân đã vượt trần `max_scale_eighths`**.
  2. **Bước 2 — Tính `room` còn trống**:
     $$\text{room} = \max\left(0,\ \text{max\_scale\_eighths} - \text{base\_intrinsic\_eighths}\right)$$
     Nếu `room == 0` thì dừng ngay: **không giữ bất kỳ cửa sổ giảm Cấp 1 nào và không cấp phát bất kỳ `ScalePassage` hay `perpetual` nào**.
  3. **Bước 3 — Chọn `ScalePassage` trước theo `score`, rồi mới đến `perpetual`**:
     - Duyệt các ứng viên `ScalePassage` (cả trên Nhóm 3 và đoạn nối `Major Bridge Impulse` trên Nhóm 2) theo thứ tự `score` giảm dần; sau khi xét hết mọi `ScalePassage` mới xét các ô `perpetual` (vì `perpetual` là ô giữ giá phẳng không có `score`, mỗi ô `perpetual` tốn đúng `epb` eighths của nó với `replaced_base_intrinsic_eighths = 0`).
     - Với mỗi ứng viên, chi phí ròng chỉ trừ đi phần scale có sẵn (`base_intrinsic_eighths`) mà ứng viên đó sẽ đè lên:
       $$\Delta\text{cost} = \text{passage\_eighths} - \text{replaced\_base\_intrinsic\_eighths}$$
       *(Các ứng viên cửa sổ giảm Cấp 1 mà passage đó sẽ thay thế chưa nằm trong `base_intrinsic_eighths` nên không trừ trong $\Delta\text{cost}$, mà tự động bị loại bỏ khi passage được chọn).*
     - Nếu $\Delta\text{cost} \le \text{room}$ (và với `ScalePassage` thì thỏa thêm khoảng thở `Minimum Cooldown Gap` với các `ScalePassage` đã chọn), chấp nhận ứng viên đó và cập nhật $\text{room} \leftarrow \text{room} - \Delta\text{cost}$.
  4. **Bước 4 — Giữ các cửa sổ giảm Cấp 1 trong phần `room` còn lại**:
     - Sau khi danh sách `ScalePassage` và `perpetual` đã chốt xong, duyệt các ứng viên cửa sổ giảm Cấp 1 trên Nhóm 2 **không bị bất kỳ `ScalePassage` nào thay thế**, theo thứ tự `score` giảm dần, và giữ lại chừng nào độ dài `tier1_eighths` của cửa sổ đó còn $\le \text{room}$ (cập nhật $\text{room} \leftarrow \text{room} - \text{tier1\_eighths}$).
- **Khoảng thở tối thiểu chỉ tính giữa hai `ScalePassage` (`Minimum Cooldown Gap`)**:
  - Khoảng thở chỉ kiểm tra giữa hai đoạn `ScalePassage` độc lập được chọn ở Bước 3 ($P_1$ trước, $P_2$ sau):
    $$P_2.\text{start} - P_1.\text{target} \ge \text{epb}$$
  - **Không tính khoảng thở đối với các cửa sổ scale nội tại và cửa sổ giảm Cấp 1 của Nhóm 2**: Ô nhận diện Nhóm 2 ngay trước đoạn nối (ví dụ ô đầu của `bach_gigue` có scale nội tại hoặc cửa sổ giảm Cấp 1 ở eighth `4..7` ngay trước khi đoạn nối bắt đầu tại eighth `8`) không tham gia kiểm tra khoảng thở; và mọi cửa sổ Cấp 1 nằm trùng ô với một `ScalePassage` đã chọn ở Bước 3 sẽ bị bỏ ở Bước 4.

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
- **Vuốt lực gảy**: bè Cao của đoạn scale đi một hairpin một chiều, biên rộng hơn mức nói của pattern (`60…72`). Cửa sổ `soft` / `loud`, cách lấy điểm vào và điểm ra, và pattern nào dùng cửa sổ nào nằm ở Mục 2.6. Bass và bè giữa không đi theo hairpin này.

#### 2. Trong Khi Chạy Scale (Accompaniment & Texture — Theo đúng Pattern từng ô & `meter.strong_eighths`)
- **Bè Trầm (`low` - Voice 3) duy trì nhịp mạch đặc trưng theo từng ô nhịp (`bar`)**:
  - Với mỗi ô nhịp `bar` mà đoạn scale đi qua, cách đặt Bass phụ thuộc vào `_bar_pattern(ctx, bar, patterns)` của chính ô nhịp đó:
    - Nếu `bar` là `bach_fuga`: **giữ nguyên đường Bass đối âm trễ 2 ô (`_fuga_motif`)** của Fuga (chỉ kiểm tra `_bach_keep_bass_below` để không vượt lên trên các nốt scale).
    - Nếu `bar` thuộc **Nhóm 2** (khi đoạn nối `Major Bridge Impulse` đi qua): giữ nguyên nhịp mạch Bass đặc trưng của chính vũ điệu đó tại `bar` (ground bass ở `_chaconne_bass_slots` cho `bach_chaconne`; nhấn **phách 1 và trọng âm Phách 2 `accent`** cho `bach_sarabande` & Brouwer `sarabande`; nhịp chấm dôi + pickup cuối ô cho `bach_gigue`), lọc qua `_playable` với các nốt scale phía trên.
    - Nếu `bar` thuộc các pattern **Nhóm 3** còn lại: trên các mốc phách mạnh đọc trực tiếp từ `ctx.strong` (`meter.strong_eighths` — tức eighth `(0, 4)` ở `4/4`, eighth `(0, 3)` ở `6/8`, và eighth `(0,)` ở `3/4`), bè Bass gảy nốt Gốc (`Root`) hoặc Bậc 5 (`Fifth`) của `chord_at[bar]` thỏa mãn `_playable` với toàn bộ các nốt scale vang trong phách mạnh đó.
- **Bè Giữa (`support` - Voice 2) nhường đường theo mật độ hạt nốt từng eighth**:
  - Tại các eighths trong `[passage.start, passage.target)` mà bè Cao chạy **móc kép (`sixteenths`)**: lược bỏ các nốt `support` trùng thời điểm (`_drop_overlap`) để giải phóng ngón `i-m-a`, chỉ giữ tối đa 1 nốt hợp âm bè Trung tại đúng điểm mở đầu `passage.start` nếu thuộc phách mạnh và thỏa `_playable`.
  - Tại các eighths trong `[passage.start, passage.target)` mà bè Cao đi bằng **móc đơn (`eighths`)** (ví dụ nửa đầu của đoạn scale dài 3–4 ô nhịp hoặc khi $\text{BPM} < 88$): lược bỏ `support` trên các móc đơn yếu, nhưng **giữ tối đa 1 nốt `support` trên mỗi phách mạnh (`eighth % epb in ctx.strong`)** nếu thỏa `_playable` với nốt Bass và nốt scale tại phách mạnh đó.

#### 3. Điểm Ra (Landing & Exit — Cho cả trường hợp `target` ở Phách Mạnh hoặc Phách Yếu)
- **Hội tụ vào `ctx.melody[passage.target]` và khóa velocity đích của Mục 2.6**:
  - Tại đúng mốc đích `passage.target` (dù `passage.target` rơi vào phách mạnh hay giữ nguyên ở phách yếu `raw_target` khi snap bị từ chối): cao độ của bè Cao (`lead`) luôn bằng `ctx.melody[passage.target]` (giữ nguyên độ ngân của nốt `melody` thuộc pattern phía sau từ `passage.target` trở đi). Velocity đích theo Mục 2.6.C: sóng lên chỉ chạm `loud` tại đúng `passage.target` (`slots[-1]`); cú sát đích `slots[-2]` thấp hơn. Sóng xuống để cú sát đích về `soft` khi nốt đích là trụ, và nốt trụ đó không được nhỏ hơn bass. Eighth `passage.target` vẫn nằm trong `scale_eighths` để `_shape_dynamics` không kéo nốt đó về `_MELODY_APEX` (`72`).
- **Tiếp quản Bè Trầm (`low`) và Bè Giữa (`support`) theo đúng lưới của Pattern sau**:
  - Bè Trầm (`low`) và Bè Giữa (`support`) của pattern phía sau từ `passage.target` trở đi **giữ nguyên lịch gảy theo lưới `ctx.strong` của chính pattern đó**: nếu `passage.target` trùng phách mạnh (`passage.target % epb in ctx.strong`) thì Bass của pattern sau đánh đồng thời với nốt đích của scale; nếu `passage.target` là phách yếu (do snap bị từ chối) thì Bass đang ngân từ phách mạnh trước đó tiếp tục ngân qua `passage.target` và không tự chèn thêm một cú Bass lệch phách, còn `support` tự động hoạt động trở lại từ `passage.target` theo đúng lịch của pattern.

---

### 2.6. Biên Độ Cường Độ Của Scale (Hairpin Theo Pattern)

Câu giai điệu thường của guitar nằm trong khoảng nói `60` (mở) … `68` (giữa) … `72` (đỉnh `_MELODY_APEX`) … `62` (kết). Engine scale hiện vuốt trong khoảng `66…72` khi đi lên và `64…72` khi đi xuống, tức chỉ `6–8` bậc velocity. Nghe trên chương chậm của Brouwer (`1M`, `sarabande`, `72 BPM`, `3/4`) đoạn chạy gần như phẳng.

Đoạn scale là một cử chỉ riêng: **một** chiều, **trơn**, và **rộng hơn** câu nói xung quanh, nhưng trần và sàn vẫn nằm trong giọng của pattern đó. Không dùng một cửa sổ chung cho cả 5 composer.

#### A. Ba cửa sổ

Velocity MIDI. `span = loud - soft`. Pattern lấy theo số eighth chiếm nhiều nhất trong `[passage.start, passage.target)`; hòa thì lấy pattern tại `passage.start`.

| Giọng | `soft` | `loud` | Span | Pattern |
|---|---:|---:|---:|---|
| **Hát** | 52 | 82 | 30 | `bach_sarabande`, Brouwer `sarabande`, `elegiaque`, `cantabile`, `andante`, `noviembre`, `chord_melody`, `preludio`, `bach_fuga` |
| **Baroque** | 54 | 84 | 30 | `bach_bourree`, `bach_gavotte`, `bach_gigue`; riêng `bach_chaconne` là `52…88` (span 36) vì breakout của Chaconne to hơn vũ điệu |
| **Động năng** | 46 | 90 | 44 | `study`, `galop`, `mozart_var`, `villa_pattern`, `choro`, `polca`, `hemiola`, `vals`, `brouwer_etude`; riêng `elogio_pizz` là `44…92` (span 48) |

`bach_fuga` ở nhóm Hát để chủ đề trầm còn nghe rõ dưới tirata. `elogio_pizz` tách khỏi nhóm Động năng vì cú slap và đoạn chạy thay slap cần đỉnh cao hơn etude.

Chương `1M` của Brouwer rơi vào `sarabande` nên dùng cửa sổ Hát `52…82`: mở dưới mức nói `60`, đáp trên đỉnh pattern `72`, chưa chạm trần punch `88`.

#### B. Dịch theo band của ô mở

Band lấy tại ô của `passage.start`. Cộng cùng một lượng vào cả hai đầu:

| Band | Dịch |
|---|---:|
| `p` | −8 |
| `mp` | −4 |
| `mf` | 0 |
| `f` | +4 |

Sau khi dịch, chỉ kẹp `soft = max(40, soft)` và `loud = min(96, loud)`. Không đẩy đầu kia để giữ span. Vùng `p` được phép co span, vì trần của một đoạn piano phải thấp hơn *mezzo-forte*. `_BAND_DELTA["p"] = -12` đã kéo giai điệu nền về khoảng `52…60`; một câu Động năng vẫn bung tới `84…88` giữa vùng đó sẽ phá chỗ tĩnh.

Ví dụ sau kẹp, span gốc trong ngoặc:

| Cửa sổ | `mf` | `p` | `f` |
|---|---|---|---|
| Hát `52…82` (30) | `52…82` | `44…74` (30) | `56…86` (30) |
| Động năng `46…90` (44) | `46…90` | `40…82` (42) | `50…94` (44) |
| Elogio `44…92` (48) | `44…92` | `40…84` (44) | `48…96` (48) |

#### C. Điểm vào, đường cong, nhịp lùi, và nốt đậu

Gọi `prev` là velocity của nốt `lead` đang ngân ngay trước `passage.start` (`_MELODY = 64` nếu đoạn mở đầu bài). `open` và `arrival` là hai đầu của ramp. Sóng lên lấy `arrival = loud` và tính ramp trên cả nốt đích. Sóng xuống lấy `arrival = soft`; nốt đích chỉ đứng ngoài ramp khi nó là nốt trụ.

- **Sóng lên — lấy đà (*subito piano*)**: `open = min(prev, soft)`, `arrival = loud`. Nếu `prev` đã nhỏ hơn `soft`, giữ `prev` để nốt đầu không bật to rồi mới crescendo. Nếu `prev` đang ở `72` hoặc cao hơn, nốt đầu **xuống** `soft` rồi chỉ đi lên. Bước xuống một cú ở vạch vào là cách lấy đà; ngoài các nhịp `retreat` ở dưới, bên trong đoạn không có chiều giảm.
- **Sóng xuống — không *sforzando* trên câu hát**: mở thẳng tại `loud` chỉ khi pattern thuộc nhóm Động năng, `elogio_pizz`, hoặc `bach_chaconne`, **và** `passage.start` là phách mạnh (`passage.start % epb in ctx.strong`). Mọi trường hợp còn lại (nhóm Hát, Baroque vũ điệu `bach_bourree` / `bach_gavotte` / `bach_gigue`, và mọi pattern khi mở ở phách yếu) mở tại
  $$v_{\text{open}} = \min(\text{loud},\ \max(\text{prev} + 8,\ \text{\_MELODY\_APEX}))$$
  Câu trước đang ở `58…62` thì nốt đầu rơi quanh `72`, không nhảy lên `82` hay `90`. Nếu `prev` đã là một cao trào (`prev + 8` chạm `loud`), công thức này tự mở tại `loud`. `arrival` của ramp là `soft`.

Ramp đi trên **thứ tự cú đánh** của bè Cao (mỗi móc kép là một bước), khớp `slots` đã có: `n = len(slots) - 1` là số cú trong `slots[:-1]`, trước `passage.target`. `N = n + 1` là toàn bộ cú, kể cả `slots[-1]` tại `passage.target`.

- **Sóng lên**: ramp từ `open` lên `loud` trên cả `N` cú. $t = i / (N - 1)$ với $i$ từ `0` đến `N - 1`, và `arrival = loud`. Chỉ $i = N - 1$ bằng `loud`. Cú sát đích (`slots[-2]`) luôn thấp hơn `loud`, nên hai nốt cuối không bao giờ là (`loud`, `loud`): bước nhích cuối đi từ nốt dẫn vào nốt đích.
- **Sóng xuống, nốt đích là phách yếu và ngân dưới `2` eighths**: ramp từ `open` về `soft` cũng trên cả `N` cú, cùng $t$, `arrival = soft`. Chỉ nốt đích chạm `soft`.
- **Sóng xuống, nốt đích là trụ** (phách mạnh, hoặc `melody` giữ cùng cao độ ít nhất `2` eighths kể từ `target`): ramp từ `open` về `soft` chỉ trên `n` cú `slots[:-1]`. $t = i / (n - 1)$ với $i$ từ `0` đến `n - 1`. Nốt đích đứng ngoài ramp.

- **$L \le \text{epb}$** (sub-bar hoặc một ô): tuyến tính, $v = \text{open} + (\text{arrival} - \text{open})\, t$.
- **$L > \text{epb}$** (2–4 ô, kể cả câu mở móc đơn rồi chuyển móc kép): mũ `1.3`, $v = \text{open} + (\text{arrival} - \text{open})\, t^{1.3}$. Giữa quãng ramp mới đi khoảng `41%` quãng velocity, nên nửa đầu còn ở vùng ấm `52…68` (dưới ngưỡng móng nylon `65+`) và lực dồn vào nửa sau. Với sóng xuống có nốt trụ, mũ này chỉ phủ `n` cú trước đích; nốt trụ là sàn riêng, không phải $t = 1$.

Khi mẫu số bằng `0` thì không chia. Đó là `N < 2` (sóng lên, hoặc sóng xuống trên phách yếu ngắn) và `n < 2` (sóng xuống có nốt trụ, kể cả cửa sổ giảm Cấp 1 đi móc đơn khi $\text{BPM} < 88$ và chỉ có một cú trước đích). Cú duy nhất trước đích, nếu có, lấy `open`. Nốt đích lấy đúng giá trị đậu ở dưới.

Làm tròn số nguyên. Ép không giảm (sóng lên) hoặc không tăng (sóng xuống). Nếu sau bước đó còn cú nào **trước nốt cuối của ramp** đã chạm `arrival` (sóng lên chạm `loud`, sóng xuống ngắn chạm `soft`), kéo cả khúc đó ra `1` bậc (`loud - 1` hoặc `soft + 1`, vẫn nằm trong `[open, arrival]`) rồi ép đơn điệu lại. Chỉ nốt cuối của ramp giữ `arrival`. Sóng xuống có nốt trụ không áp bước này: cú sát đích được phép bằng `soft`. Làm các bước này **trước** nhịp lùi.

**Nhịp `retreat`**: sau khi đã có đường hairpin, mỗi cú có `slot.retreat` (eighth nằm trong `retreat_spans`) chùng `3` bậc **ngược** chiều hairpin (sóng lên thì trừ `3`, sóng xuống thì cộng `3`), kẹp trong `[soft, loud]`. Cú kế tiếp không thuộc retreat trở lại đúng đường cong, nên đây là một gợn `tăng – lùi – bứt phá`, không phải một đỉnh mới. Nốt đích không bị chùng.

**Nốt đậu tại `passage.target` (`slots[-1]`)**:

- Sóng lên: velocity của nốt đích là `loud`. Cú sát đích nhỏ hơn `loud`.
- Sóng xuống, phách yếu ngắn (`< 2` eighths): nốt đích là `soft`, và là bước duy nhất chạm `soft`.
- Sóng xuống, nốt trụ: khi `n ≥ 2`, cú sát đích đã ở `soft`. Sàn của nốt đích là $\max(\text{soft},\ \text{\_BASS} + 2)$ với `_BASS = 56`, tức không dưới `58`. Khi `n < 2` không có cú nào để đưa về `soft`; cú trước đích (nếu có) giữ `open`, nốt đích vẫn lấy sàn này. Sàn ngang mức đóng câu `_SWELL_CLOSE` (`62`) về vai trò: giai điệu ngân không nhỏ hơn bass `10…16` bậc. Nó cũng chặn `_shape_dynamics` của `villa_pattern`, vì pass đó kẹp bass và bè giữa theo `sounding_lead_vel` (`lead_vel - 1` hoặc `- 2`, sàn `44`). Một nốt đích `40…46` ngân qua nửa ô sẽ kéo cả vòng arpeggio xuống sàn đó.

Bass (`_BASS`) và bè giữa (`_INNER`) của đoạn scale giữ mức của pattern. Hairpin chỉ ở bè Cao.

`scale_eighths` tiếp tục chặn `_shape_dynamics` trên chính các eighth của scale. Nếu không chặn, pass đó kẹp hầu hết nốt về `44…78` và kéo đỉnh `loud` về `_MELODY_APEX`. Eighth của `_modal_figure` không có sẵn trong `ScalePlan.scale_eighths`; chúng được hợp vào tập của `clear_scale_slurs` và `_shape_dynamics` theo Mục 2.6.D.

#### D. Phạm vi

- Mọi `ScalePassage` và cửa sổ giảm Cấp 1 của engine mới dùng Mục 2.6.
- Swarm nội tại của Brouwer `sarabande` (`_modal_figure`) dùng cùng cửa sổ Hát, theo chiều của swarm. Chương chậm `1M` nghe figuration này ở nửa sau các ô đang chuyển động, kể cả khi ngân sách không cấp `ScalePassage`. `line` nằm gọn trong ô (từ `figure_at` đến hết ô) và không có `passage.target` tách ở đầu ô sau, nên ramp phủ thẳng `len(line)` nốt, không tách `slots[:-1]` với `slots[-1]`. Mở theo luật sóng lên / sóng xuống của Mục 2.6.C. Figuration không dài hơn một ô, nên dùng nhánh tuyến tính. Nốt cuối `line` là bước cuối của ramp: sóng lên chạm `loud`; sóng xuống kết tại $\max(\text{soft},\ \text{\_BASS} + 2)$, không dùng nhánh phách yếu ngắn, vì nốt đó đóng ô và còn ngân dưới bass của sarabande. `prev` lấy theo luật punch ở dưới, không lấy mức đi bộ `±1` hiện đang viết trong `_modal_figure`.
- **Chặn band lần hai trên eighth của swarm.** `ScalePlan.scale_eighths` chỉ gom `[start, target]` của `passages` và `tier1`. `_shape_dynamics` chỉ chạy khi `_framed(ctx)` (đúng chương `1M`): nốt `lead` có `velocity >= 72` được giữ nguyên, còn nốt `< 72` bị cộng `_BAND_DELTA` (`p` −12, `mp` −6, `mf` 0, `f` +4) cùng `extra` của câu (`0…4`) rồi kẹp `44…78`, trừ khi eighth đã nằm trong tập bảo vệ. Hairpin đã dịch band ở Mục 2.6.B, nên lần cộng này gãy ramp `6…12` bậc đúng ngưỡng `72`. Nhánh giữ nguyên nốt `velocity >= 72` không thay được tập bảo vệ: nửa dưới cửa sổ Hát nằm dưới ngưỡng đó. Sau khi `_smooth_boundaries` và `_caesura_eighths` đã chạy, hợp các eighth của swarm còn ngân — ô `sarabande` mà `ScalePassage` hoặc cửa sổ Cấp 1 không đè — vào tập đưa cho `clear_scale_slurs` và `_shape_dynamics`. Không nhét các eighth này vào `ScalePlan.scale_eighths` sớm hơn bước đó. `_smooth_boundaries` vẫn trồng pickup ở eighth cuối của ô biên, và caesura vẫn được nghỉ. `sarabande` không thuộc `bell_bars`, nên không trừ ô này khỏi chuông.
- **`prev` là accent sau `_punch`, và `_punch` không cộng vào giữa swarm.** `_render_sarabande_bar` gọi `_modal_figure` trước khi bè Cao của ô tồn tại. Nốt accent do `_sustain` viết sau, rồi `_punch(..., amount=8)` đưa velocity lên `min(88, _note_velocity + 8)`. Câu phẳng: `64 + 8 = 72`. Accent nằm trong apex: `72 + 8 = 80`. Câu đang lên dùng `_melody_swell` rồi cộng `8`, vẫn trần `88`. Swarm thường mở sau accent (`figure_at > accent`, eighth `2` ở `3/4` và eighth `3` ở `6/8`): `prev` là giá trị sau punch, không phải mức `_sustain` chưa punch. Nhánh hiếm khi nửa đầu ô nhảy quãng và swarm mở từ đầu ô (`origin16 == bar_start * 2`, phủ qua accent): chỉ `_punch` accent khi `_start16(figure[0]) > (bar * epb + accent) * 2`. Cú swarm trùng accent là một bước của hairpin, không cộng `8`. Punch của bass và bè giữa trên hợp âm accent giữ nguyên. Khi swarm đã phủ accent, `prev` là nốt `lead` đang ngân ngay trước cú đầu của `line`; nếu cú đó ở eighth `0` thì lấy nốt cuối ô trước, không có thì `_MELODY` (`64`).
- Scale nội tại của Bach (`_fitting_scale` trên `bach_gigue`, `bach_chaconne`, `bach_sarabande`) **giữ** swell câu `60…72`. Đó là dấu nhận của điệu, không phải đoạn chạy impulse. Chỉ đoạn nối `ScalePassage` đè lên các ô đó mới dùng cửa sổ Baroque / Chaconne ở trên.

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
│  • `_place_melody` chạy Bước A một lần cho cả `[impulse.start, target]`      │
│    (kiểm tra biên vào ở câu đầu và biên ra ở câu cuối); nếu thất bại thì     │
│    chạy Bước B lần lượt từng vạch câu theo chuẩn `seam_ok`, rồi gắn          │
│    `impulses` lên `_Ctx`.                                                    │
└───────────────────────────────────────┬──────────────────────────────────────┘
                                        ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                     3. guitar_patterns.py & 5 Module Composer                │
│  • Với biến động nhỏ/vừa: giữ nguyên 100% figuration nội tại của Nhóm 2      │
│    (`bach_chaconne`, `bach_gigue`, `bach_sarabande`, Brouwer `sarabande`).   │
│  • Với sóng lớn (`Major Bridge Impulse`: L >= epb, net_span >= 6, sau 1 ô    │
│    nhận diện của chính pattern đó): cho phép `ScalePassage` dài (1–4 ô nhịp) │
│    làm đoạn nối ở giữa cả Nhóm 2 và Nhóm 3 trên nền Bass đặc trưng theo từng │
│    ô nhịp.                                                                   │
│  • Ngân sách 4 bước từ `room = max(0, max_scale_eighths - base_intrinsic)`:  │
│    chọn `ScalePassage` -> `perpetual` -> cửa sổ Cấp 1 trong `room` còn lại.  │
│    Bảo vệ `[start, target]` trong `scale_eighths`.                           │
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
   - Trong `_place_melody`: nếu một `PriceImpulse` trong `impulses` cắt qua một hoặc nhiều vạch câu $P_0 | P_1 | \dots | P_m$ (với $P_0$ là câu chứa `impulse.start` và $P_m$ là câu chứa `impulse.target`):
     - Gọi một cặp nối bất kỳ $(e, e+1)$ là **hợp lệ (`seam_ok`)** khi hướng đặt $(\text{placed}[e+1] - \text{placed}[e])$ giữ đúng dấu hướng của $(\text{raw}[e+1] - \text{raw}[e])$ và khoảng nhảy $\left|\text{placed}[e+1] - \text{placed}[e]\right| < 12$ bán cung.
     - **Không gộp toàn bộ `[P0.start, Pm.end)`** để không bẻ các nốt nằm ngoài con sóng.
     - **Bước A (Chạy đúng 1 lần cho toàn bộ đoạn sóng `[impulse.start, impulse.target]`)**:
       - Thử áp dụng một mức `shift` chung cho toàn bộ `[impulse.start, impulse.target]`.
       - **Biên vào** chỉ kiểm tra tại cặp nốt $(\text{impulse.start} - 1,\ \text{impulse.start})$ nằm trong câu đầu $P_0$ khi `impulse.start > P0.start`, hoặc tại cặp $(\text{P\_prev.end} - 1,\ \text{P0.start})$ khi `impulse.start == P0.start` và còn câu đứng trước $P_{\text{prev}}$ ngoài impulse (chỉ khi sóng bắt đầu tại đúng eighth đầu của bản — không còn câu trước — thì biên vào mới tự động đạt `seam_ok`).
       - **Biên ra** chỉ kiểm tra tại cặp nốt $(\text{impulse.target},\ \text{impulse.target} + 1)$ nằm trong câu cuối $P_m$ khi `impulse.target < Pm.end - 1`, hoặc tại cặp $(\text{Pm.end} - 1,\ \text{P\_next.start})$ khi `impulse.target == Pm.end - 1` và còn câu kế tiếp $P_{\text{next}}$ ngoài impulse (chỉ khi không còn câu sau thì biên ra mới tự động đạt `seam_ok`).
       - Các vạch câu ở giữa ($P_0 | P_1, \dots, P_{m-1} | P_m$) nằm trọn trong cùng một mức `shift` chung nên không thử riêng. Chỉ khi **cả biên vào lẫn biên ra đều đạt `seam_ok`** thì mới giữ mức `shift` chung đó cho toàn đoạn sóng.
     - **Bước B (Chỉ chạy khi Bước A thất bại, duyệt lần lượt từng vạch câu $P_{\text{left}} | P_{\text{right}}$ từ trái sang phải)**:
       1. Câu bên trái $P_{\text{left}}$ giữ nguyên mức `shift` đang có ở cuối câu đó (`P_left.end - 1`).
       2. Phần đoạn sóng nằm trong câu bên phải $P_{\text{right}}$ là `[P_right.start, seg_end]` với `seg_end = min(P_right.end - 1, impulse.target)`.
       3. **Xác định điều kiện biên ra của `P_right`**:
          - **Nếu `impulse.target` còn nằm ở câu sau `P_right` (`impulse.target >= P_right.end`)**: Phương án B.1 và B.2 **không kiểm tra biên ra** tại cuối `P_right` (hai phương án chỉ cần vượt qua vạch đang xét `P_left.end - 1 -> P_right.start`, còn vạch sang câu sau sẽ do vòng lặp kế tiếp xử lý).
          - **Nếu `impulse.target` nằm trong `P_right` (`impulse.target < P_right.end`)**: Biên ra thực sự chỉ kiểm tra tại câu chứa đích này — là cặp `(impulse.target, impulse.target + 1)` trong $P_{\text{right}}$ khi `impulse.target < P_right.end - 1`, hoặc là cặp `(P_right.end - 1, P_next.start)` khi `impulse.target == P_right.end - 1` và còn câu sau $P_{\text{next}}$ ngoài impulse (vì `shift` của $P_{\text{next}}$ không còn bị Bước B đổi; nếu không còn câu sau thì biên ra tự động đạt `seam_ok`).
       4. **Phương án B.1 (Thử `shift` của câu trái $P_{\text{left}}$)**: Áp mức `shift` của $P_{\text{left}}$ lên đoạn `[P_right.start, seg_end]`, sau đó **vẫn đo trực tiếp `seam_ok` trên cặp nốt qua vạch đang xét `P_left.end - 1 -> P_right.start`** (vì cùng `shift` chỉ giữ nguyên khoảng của hai cao độ gốc; nếu khoảng đó bị đảo chiều so với `raw` hoặc nhảy $\ge 12$ bán cung thì `seam_ok` vẫn gãy) cùng điều kiện biên ra ở mục 3 (chỉ thêm vào phép kiểm này khi câu phải $P_{\text{right}}$ đang chứa đích `impulse.target`). Nếu đạt thì chốt mức `shift` đó cho `[P_right.start, seg_end]` và sang vạch kế tiếp.
       5. **Phương án B.2 (Thử `shift` của chính câu phải $P_{\text{right}}$)**: Nếu Phương án B.1 gãy `seam_ok` (dù ở vạch `P_left.end - 1 -> P_right.start` hay ở biên ra khi $P_{\text{right}}$ chứa đích), thử dùng mức `shift` của chính $P_{\text{right}}$ cho `[P_right.start, seg_end]` và kiểm tra lại chính vạch `P_left.end - 1 -> P_right.start` cùng điều kiện biên ra ở mục 3 (khi $P_{\text{right}}$ chứa đích). Nếu đạt thì chốt mức `shift` của $P_{\text{right}}$ và sang vạch kế tiếp.
       6. **Hủy khóa từ vạch gãy trở đi**: Nếu cả Phương án B.1 lẫn B.2 đều gãy `seam_ok`, **bỏ khóa `shift` từ vạch $P_{\text{left}} | P_{\text{right}}$ đó trở đi** — câu $P_{\text{right}}$ và mọi câu phía sau trong impulse giữ nguyên mức `shift` mà `_choose_shifts` (với `_boundary_cost` hiện có) đã chọn.
   - Gắn `raw_pitches` và `impulses` lên `_Ctx` trong `render_patterned_voices` (không gọi lại `detect_price_impulses` trong `guitar_patterns.py`).

### 3.4. `backend/app/sonify/guitar_patterns.py` & 5 Module Composer
- Loại trừ hoàn toàn Nhóm 1 (`tremolo`, `etude1`, `etude11`, `_catedral_preludio` `preludio`, `thumb_cantabile`): nếu `[passage.start, passage.target]` chạm bất kỳ ô Nhóm 1 nào thì **bỏ toàn bộ `ScalePassage` đó**.
- Với Nhóm 2 (`bach_chaconne`, `bach_gigue`, `bach_sarabande`, Brouwer `sarabande`) và Nhóm 3, chạy đúng quy trình ngân sách 4 bước của Mục 2.4:
  - Bước 1–2: giữ nguyên 100% `base_intrinsic_eighths` có sẵn của Nhóm 2 (ở các ô không bị đoạn nối thay thế) và tính `room = max(0, max_scale_eighths - base_intrinsic_eighths)`.
  - Bước 3: chọn các `ScalePassage` (bao gồm cả **Sóng Lớn `Major Bridge Impulse`**: $L \ge \text{epb}$ từ 1–4 ô nhịp, $\text{net\_span} \ge 6$ bán cung, bắt đầu sau khi chính pattern Nhóm 2 đó đã vang ít nhất 1 ô nhịp trọn vẹn, giữ Bass đặc trưng theo từng ô nhịp) theo `score` giảm dần trước, rồi mới xếp các ô `perpetual` sau mọi `ScalePassage` (mỗi ô `perpetual` có `replaced_base_intrinsic_eighths = 0`), khi $\Delta\text{cost} = \text{passage\_eighths} - \text{replaced\_base\_intrinsic\_eighths} \le \text{room}$.
  - Bước 4: sau khi chốt xong `ScalePassage` và `perpetual`, giữ các cửa sổ giảm Cấp 1 trên Nhóm 2 không bị `ScalePassage` nào thay thế theo `score` cho đến khi đầy phần `room` còn lại (cửa sổ Cấp 1 không tham gia khoảng thở).
- Khi áp dụng `ScalePassage` trên Nhóm 2 và Nhóm 3:
  - Loại các ô có `ScalePassage` khỏi `bell_bars`.
  - Đánh dấu toàn bộ khoảng đóng `[passage.start, passage.target]` (bao gồm cả eighth đích `passage.target`) vào tập `scale_eighths` để `_relax_texture` (trong `_smooth_boundaries`), `_shape_dynamics` và `_slur` không ghi đè hairpin Mục 2.6 và không kéo nốt đích về `_MELODY_APEX` (`72`).

### 3.5. `backend/tests/test_sonify_guitar.py`
- Bổ sung và cập nhật bộ kiểm thử:
  1. **Test `detect_price_impulses`**:
     - Kiểm tra cả 3 phân khúc rời nhau: Sub-bar ($2 \le L < \text{epb}$), 1–2 ô nhịp ($\text{epb} \le L \le 2 \times \text{epb}$), và >2–4 ô nhịp ($2 \times \text{epb} < L \le 4 \times \text{epb}$) trên các nhịp `4/4` (`epb=8`), `3/4` (`epb=6`), `6/8` (`epb=6`, `strong_eighths=(0, 3)`).
     - Kiểm tra sóng có `retreat` thật (`Up – Retreat – Up` và `Down – Retreat – Down`) được nhận diện đúng và đạt `Score` cao nhờ `adjusted_efficiency`, trong khi vùng sideway răng cưa (`efficiency < 0.45`) hoặc thoái lui sâu ($> 50\%$) bị loại bỏ.
     - Kiểm tra mỗi sóng gộp dài $> 4 \times \text{epb}$ chỉ phát ra tối đa 1 cửa sổ $\le 4 \times \text{epb}$, và khoảng thở giữa hai `ScalePassage` luôn thỏa $P_2.\text{start} - P_1.\text{target} \ge \text{epb}$.
  2. **Test Bảo toàn Pattern, Scale Nội Tại & Đoạn Nối Sóng Lớn (`Major Bridge Impulse`)**:
     - Kiểm tra bất kỳ `ScalePassage` nào chạm vào một ô Nhóm 1 (`tremolo`, `etude1`, `etude11`, `_catedral_preludio` và `thumb_cantabile`) đều bị loại bỏ trọn vẹn (không khoét lẻ ô làm đứt câu chạy).
     - Kiểm tra Nhóm 2 (`bach_chaconne`, `bach_gigue`, `bach_sarabande` và Brouwer `sarabande`) giữ nguyên phần mở đầu ô nhịp (bariolage / hợp âm gãy / trọng âm phách 2) ở **ô đầu của vùng pattern Nhóm 2 đó** và trước các biến động nhỏ ($L < \text{epb}$ hoặc $\text{net\_span} < 6$), nhưng cho phép **Sóng Lớn ($L \ge \text{epb}, \text{net\_span} \ge 6$)** bắt đầu **sau ô đầu của vùng pattern Nhóm 2** chạy `ScalePassage` dài (1–4 ô nhịp, có `retreat`) làm đoạn nối ở giữa (kể cả ngay sau ô nhận diện có scale nội tại hoặc cửa sổ giảm Cấp 1) trên nền Bass đặc trưng theo từng ô nhịp rồi đáp về lại pattern tại `target`.
     - Kiểm tra `bach_fuga` giữ nguyên chủ đề đối âm trễ 2 ô ở bè Trầm (`low`) bên dưới câu scale của bè Cao.
  3. **Test 5 Composer, Sor `1D` (`88 BPM`) & `assert_playable`**:
     - Kiểm tra Sor ở `88 BPM` chạy được scale móc kép nhờ `SCALE_SIXTEENTH_MIN_BPM = 88` mà **không** kích hoạt nhầm `Grand Solo` (`BARRIOS_TREMOLO_MIN_BPM` vẫn ở `90`).
     - Kiểm tra toàn bộ 5 composer vượt qua `assert_playable` (bao gồm `_quarter_ok` trên mọi chùm 4 móc kép, đặc biệt khi Villa-Lobos fallback khỏi dây buông không hợp thế tay) trên cả 5 giọng (`C, D, Eb, A, Bb`).
  4. **Test Ngân sách `<= 30% body_eighths` (Quy trình 4 bước) & Mix Well**:
     - Kiểm tra quy trình 4 bước: `room = max(0, max_scale_eighths - base_intrinsic_eighths)`; khi `room == 0` thì không giữ cửa sổ Cấp 1 và không cấp `ScalePassage` / `perpetual`; khi `room > 0` thì ưu tiên chọn `ScalePassage` và `perpetual` trước, sau đó mới giữ các cửa sổ Cấp 1 không bị thay thế trong phần `room` còn lại sao cho tổng không bao giờ vượt `max_scale_eighths`.
     - Kiểm tra hairpin Mục 2.6. Sóng lên lấy đà ở `soft` rồi chỉ tăng, trừ gợn `−3` trên `slot.retreat`. Chỉ `passage.target` bằng `loud`; `slots[-2]` nhỏ hơn `loud`. Sóng xuống của nhóm Hát, khi `prev` quanh `60` và mở ở phách yếu, mở quanh `_MELODY_APEX` (`72`) chứ không nhảy lên `loud`. Động năng hoặc Chaconne mở ở phách mạnh thì mở tại `loud`. Band `p` của Elogio kẹp thành `40…84`, không đẩy `loud` lên `88` để giữ span `48`. Câu $L > \text{epb}$ đi lên có velocity giữa câu thấp hơn đường tuyến tính. Nốt đích sóng xuống trên phách mạnh không dưới `58`, và trong lúc nốt đó ngân, bass của `villa_pattern` không bị kẹp xuống `44`. Cửa sổ Cấp 1 đi móc đơn với đúng một cú trước đích (`n = 1`) không chia cho `0`: cú đó lấy `open`, nốt đích lấy `loud` hoặc sàn trụ. `_modal_figure` vuốt cả `len(line)` theo cửa sổ Hát. `prev` là accent sau `_punch` (`min(88, _note_velocity + 8)`: câu phẳng mở từ `72`), và nốt cuối của swarm đi xuống không dưới `58`. Eighth swarm còn ngân, khi không bị `ScalePassage` đè, nằm trong tập của `clear_scale_slurs` và `_shape_dynamics` sau `_smooth_boundaries`: band `p` không cộng `_BAND_DELTA` lần hai dưới `72`. Swarm mở từ đầu ô không bị `_punch` cộng `8` vào cú trùng accent. `_shape_dynamics` không ghi đè các eighth trong `scale_eighths`. Cao độ tại `passage.target` trùng `melody[target]`. Bass và bè giữa của pattern sau giữ lịch `ctx.strong`.
