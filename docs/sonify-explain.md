Dưới đây là bức tranh tổng thể về **Giọng & Hòa âm gốc (Key, Mode, Tonic)** và **Nhịp điệu (Time Signature, Tempo, Swing, Khung Warm-up/Cool-down)** cho cả **4 variants** (`Giao hưởng`, `Jazz`, `Tối giản`, `Ambient`) trên **5 khung thời gian** (`1D`, `1W`, `1M`, `3M`, `1Y`) hiện tại:

---

## 1. Giọng nhà (Home Key) theo mã cổ phiếu

Mỗi mã cổ phiếu có một **giọng nhà cố định** trên vòng 5 giọng (`Mi♭ – Si♭ – Đô – Rê – La` nối tròn):
- **Đô (`C`, 0 dấu hóa)**: `VNM`, `MSN`, `SAB`, `GAS`, `POW`, `REE`, `PLX`, `BVH`
- **Rê (`D`, +2 cung, 2♯)**: `FPT`, `MWG`, `DGW`, `FRT`, `PNJ`, `CTR`, `CMG`
- **Mi♭ (`Eb`, +3 cung, 3♭)**: `HPG`, `HSG`, `NKG`, `VIC`, `VHM`, `VRE`, `NVL`, `KDH`, `SSI`, `VND`, `HCM`, `VCI`
- **Si♭ (`Bb`, -2 cung, 2♭)**: `VCB`, `BID`, `CTG`, `TCB`, `MBB`, `ACB`, `VPB`, `STB`, `HDB`, `TPB`
- **La (`A`, -3 cung, 3♯)**: `GMD`, `HAH`, `DGC`, `DPM`, `DCM`, `VHC`, `ANV`, `PTB`
- *(Các mã khác băm ổn định bằng `crc32` vào 1 trong 5 giọng này).*

---

## 2. Hòa âm gốc & Chuyển giọng theo Khung thời gian và Variant

### A. Quy tắc lật Trưởng / Thứ cùng gốc (Parallel Major / Minor — áp dụng từ `1M` trở lên cho Giao hưởng, Jazz, Ambient)
Thay vì nhảy sang La thứ giữa bài khi thị trường giảm, cả chương giữ nguyên gốc của giọng chương đó và chọn **Mode** theo tính cách biến động giá của chương:
- **Trưởng (`major`)**: khi chương là `rally` (tăng), `calm` (đi ngang), hoặc `volatile` nhưng kết thúc không phải downtrend.
  - Chủ âm đạp (Intro, đầu câu, Outro, Warm-up/Cool-down): **Bậc I trưởng** (`I`, `Imaj7` — trong không gian Đô là `C`, `Cmaj7`; Jazz/Ambient nâng thành `Cmaj9`). `Am` chỉ đóng vai hợp âm bậc `vi` đi qua giữa câu.
- **Thứ tự nhiên cùng tên (`minor`, thêm 3 dấu giáng vào hóa biểu)**: khi chương là `selloff` (giảm) hoặc `volatile` kết bằng downtrend.
  - Chủ âm đạp: **Bậc i thứ** (`i`, `im7` — trong không gian Đô là `Cm`, `Cm7`; Jazz/Ambient nâng thành `Cm9`).
  - Bộ hợp âm trong chương thứ: `i (Cm, Cm7)`, `iv (Fm, Fm7)`, `ii° (Dm7♭5)`, `V (G, G7)`, `♭VI (A♭, A♭maj7)`, `♭III (E♭, E♭maj7)`, và hợp âm đi qua 1 ô `F♯°7` trước `G`.
  - Giai điệu hát thang thứ tự nhiên (`C–D–E♭–F–G–A♭–B♭`), và **chỉ nâng `B♭` thành `B` tự nhiên (âm dẫn) trên đúng ô có hợp âm `G` / `G7` / `G9`**.

---

### B. Chi tiết Hòa âm theo từng Khung thời gian (`1D` → `1Y`)

1. **`1D` (1 chương — Tiểu phẩm 34 ô: 2 warm-up + 30 thân + 2 cool-down)**:
   - **Giọng**: Giọng nhà (Trưởng).
   - **Hòa âm**: 12 hợp âm diatonic chuẩn (`C, F, Dm, G, Am, Em` và hợp âm 7). Chủ âm theo regime của phiên (`uptrend`/`sideway` đạp `C`/`Cmaj7`, `downtrend` đạp `Am`/`Am7`).
2. **`1W` (1 chương — 32 ô mỗi phiên, tối đa 160 ô cho 5 phiên, không có khung ngoài)**:
   - **Giọng**: Giọng nhà (Trưởng) xuyên suốt cả tuần.
   - **Hòa âm**: Mở thêm 12 hợp âm mượn/secondary dominant (`D7, E7, A7, C7, Fm, Gm, A♭, B♭, B♭7, E♭, Bm7♭5, F♯°7`) lọc theo regime từng phiên.
3. **`1M` (Sonata 4 chương: I, II, III, IV — nghỉ 6s giữa các chương)**:
   - **Giao hưởng**: Giữ **1 giọng nhà duy nhất** cho cả 4 chương; từng chương tự chọn Trưởng hoặc Thứ cùng tên theo tuần đó.
   - **Jazz (Set 4 bài: Head, Ballad, Bài ngắn, Finale)**:
     - Chương I, II, IV ở **giọng nhà** (Trưởng/Thứ theo tuần).
     - Riêng **Chương III (Bài ngắn)** bước **1 bậc trên vòng giọng** (tuần tăng đi lên vòng, tuần giảm/ngang đi xuống vòng).
     - **Bridge hòa âm**: Trong Chương I, II và IV, đoạn giữa là *Bridge* — phách đầu đoạn giữa ưu tiên về **bậc IV** (`F`/`Fmaj7` ở bài trưởng, `Fm`/`Fm7` ở bài thứ), 2 ô cuối đoạn giữa ưu tiên **bậc V (`G`/`G7`)** để hút về **bậc I** ở đoạn tái hiện.
   - **Ambient**: Giữ **1 giọng nhà duy nhất** cho cả 4 chương (Trưởng/Thứ theo tuần). Ở **đoạn giữa** của cả 4 chương, bè **Drone (Contrabass)** ghim cố định 1 nốt chủ âm bậc I làm pedal (tạo hợp âm slash khi Halo/Kính đổi hợp âm phía trên); ngoài đoạn giữa Drone đi theo gốc hợp âm từng ô.
   - **Tối giản**: Giữ nguyên kiểu bước giọng trên vòng và luôn ở **mode Trưởng**: Chương I giọng nhà $\rightarrow$ Chương II bước sang giọng kề $\rightarrow$ Chương III sang giọng kề phía bên kia $\rightarrow$ Chương IV về giọng nhà.
4. **`3M` (Concerto / Symphony 3 chương: I, II, III — nghỉ 8s giữa các chương)**:
   - **Giao hưởng & Ambient**: Giữ **giọng nhà** cả 3 chương, lật Trưởng/Thứ theo từng tháng (Ambient vẫn giữ pedal Drone chủ âm ở đoạn giữa).
   - **Jazz (Set 3 bài: Mở, Ballad, Khép)**: Giữ **giọng nhà** cả 3 chương (không có bài ngắn nên không bước vòng), lật Trưởng/Thứ theo tháng. Riêng **Chương II (Ballad)** có Bridge về bậc IV $\rightarrow$ V $\rightarrow$ I.
   - **Tối giản**: Chương I giọng nhà $\rightarrow$ Chương II bước 1 giọng kề $\rightarrow$ Chương III về giọng nhà (luôn Trưởng).
5. **`1Y` (Tổ khúc 4 mùa — 12 chương theo tháng lịch — nghỉ 4s trong mùa, 8s khi đổi mùa)**:
   - **Mọi variant**: Đi theo **mùa trên vòng giọng**: Tháng đầu tiên, tháng cuối cùng, Mùa Xuân (Q1: tháng 1–3) và Mùa Đông (Q4: tháng 10–12) ở **giọng nhà**. Mùa Hạ (Q2: tháng 4–6) và Mùa Thu (Q3: tháng 7–9) bước sang giọng kề trên vòng.
   - **Mode**: Giao hưởng, Jazz, Ambient lật Trưởng/Thứ theo từng tháng; Tối giản giữ Trưởng. Jazz có Bridge ở các tháng giữa mùa (tháng 2, 5, 8, 11); Ambient giữ pedal Drone ở đoạn giữa mọi tháng.

---

## 3. Nhịp điệu, Tempo & Khung chương (Meter, BPM, Swing, Frame)

### Bảng tổng hợp Nhịp & BPM theo Khung thời gian và Variant

| Khung | Chương / Vị trí | Giao hưởng | Jazz | Tối giản | Ambient |
|---|---|---|---|---|---|
| **`1D`** | 1 chương (30 ô thân + 2+2 ô khung = 34 ô) | **4/4** · `90 BPM`<br>*(1:28 cả khung)* | **4/4 (Swing)** · `82 BPM`<br>*(1:39 cả khung)* | **4/4** · `118 BPM`<br>*(1:09 cả khung)* | **4/4** · `60 BPM`<br>*(2:16 cả khung)* |
| **`1W`** | 1 chương (32 ô/phiên, tối đa 160 ô, không khung) | **4/4** · `90 BPM`<br>*(7:07 đủ 5 phiên)* | **4/4 (Swing)** · `90 BPM`<br>*(7:07)* | **4/4** · `90 BPM`<br>*(7:07)* | **4/4** · `90 BPM`<br>*(7:07)* |
| **`1M`**<br>*(nghỉ 6s)* | **I** – Mở / Head (`96 BPM`)<br>**II** – Chậm / Ballad (`72 BPM`)<br>**III** – Scherzo / Bài ngắn (`120 BPM`)<br>**IV** – Finale (`96 BPM`) | **I:** 4/4 (96+8 ô)<br>**II:** **6/8** (96+12 ô)<br>**III:** **3/4** (96+12 ô)<br>**IV:** 4/4 (96+8 ô)<br>*Tổng: **16:10*** | **I:** 4/4 Swing (96+8 ô)<br>**II:** **12/8** Straight (48+6 ô)<br>**III:** **3/4 Swing** (96+12 ô)<br>**IV:** 4/4 Swing (96+8 ô)<br>*Tổng: **16:10*** | **I:** **5/4** (76+8 ô)<br>**II:** 4/4 (72+8 ô)<br>**III:** **7/8** (82+10 ô)<br>**IV:** 4/4 (96+8 ô)<br>*Tổng: **16:08*** | **I:** 4/4 (96+8 ô)<br>**II:** **6/4** (48+6 ô)<br>**III:** **3/4** (96+12 ô)<br>**IV:** 4/4 (96+8 ô)<br>*Tổng: **16:10*** |
| **`3M`**<br>*(nghỉ 8s)* | **I** – Mở (`96 BPM`)<br>**II** – Chậm / Ballad (`60 BPM`)<br>**III** – Khép nhanh (`108 BPM`) | **I:** 4/4 (192+8 ô)<br>**II:** **6/8** (160+12 ô)<br>**III:** 4/4 (216+8 ô)<br>*Tổng: **25:30*** | **I:** 4/4 Swing (192+8 ô)<br>**II:** **12/8** Straight (80+6 ô)<br>**III:** 4/4 Swing (216+8 ô)<br>*Tổng: **25:30*** | **I:** **5/4** (153+8 ô)<br>**II:** 4/4 (120+8 ô)<br>**III:** **7/8** (246+10 ô)<br>*Tổng: **25:29*** | **I:** 4/4 (192+8 ô)<br>**II:** **6/4** (80+6 ô)<br>**III:** 4/4 (216+8 ô)<br>*Tổng: **25:30*** |
| **`1Y`**<br>*(nghỉ 4s/8s)* | **Mở mùa** (T1, 4, 7, 10 · `100 BPM`)<br>**Giữa mùa** (T2, 5, 8, 11 · `66 BPM`)<br>**Khép mùa** (T3, 6, 9 · `108 BPM`)<br>**Finale** (T12 · `96 BPM`) | **Mở:** 4/4 (80+4 ô)<br>**Giữa:** **6/8** (96+6 ô)<br>**Khép:** 4/4 (84+4 ô)<br>**T12:** 4/4 (108+4 ô)<br>*Tổng: **47:21*** | **Mở:** 4/4 Swing (80+4 ô)<br>**Giữa:** **12/8** Straight (48+2 ô)<br>**Khép:** 4/4 Swing (84+4 ô)<br>**T12:** 4/4 Swing (108+4 ô)<br>*Tổng: **46:59*** | **Mở:** **5/4** (64+4 ô)<br>**Giữa:** 4/4 (72+4 ô)<br>**Khép:** **7/8** (96+4 ô)<br>**T12:** 4/4 (108+4 ô)<br>*Tổng: **47:20*** | **Mở:** 4/4 (80+4 ô)<br>**Giữa:** **6/4** (48+2 ô)<br>**Khép:** 4/4 (84+4 ô)<br>**T12:** 4/4 (108+4 ô)<br>*Tổng: **46:59*** |

*(Ghi chú số ô trong ngoặc ở `1M`, `3M`, `1Y`: `số ô thân + tổng số ô warm-up & cool-down ở 2 đầu`).*

---

### C. Đặc trưng nhịp điệu & phối khí của từng Variant

1. **Giao hưởng (`symphony` — Không swing)**:
   - **`4/4`** (nhanh/finale): Phách mạnh ở móc `0, 4`. Bass đi nốt tròn (`p`), trắng (`mp`), đen (`mf`), 8 móc đơn (`f`).
   - **`6/8`** (chương chậm pastorale): 6 móc/ô, 2 phách đen chấm (nhấn móc `0` và `3`). Bass `mp` đi 2 nốt đen chấm; Piano tay trái giữ gốc 3 phách, tay phải đặt guide tone 1 đen chấm ở đầu ô, fill rải ở móc `3, 4, 5`.
   - **`3/4`** (scherzo 1M-III): 6 móc/ô, phách mạnh ở móc `0` (thêm trọng số phụ `0.8` ở móc `4` tức phách 3 để đỡ bước nhảy qua vạch ô). Bass `mp` đi trắng + đen, `mf` đi 3 phách đen.
   - **Khung chương**: Nửa đầu warm-up chỉ có Bass & Cello vào từ `p`; nửa sau Violin mới nhập vào kèm crescendo `p < mp` tới đầu thân bài. Cool-down cả 3 bè dây giữ chủ âm lắng dần về `ppp`.

2. **Jazz (`jazz` — Bật Swing 2:1 ở `4/4` và `3/4`, tắt Swing ở `12/8`)**:
   - **`4/4` (Swing)**: Walking bass 2-feel (`p`) hoặc 4 phách đen có nốt dẫn (`mp–f`); Rhodes đánh Charleston (phách 1 đen chấm + móc đơn ở phách 2 rưỡi).
   - **`3/4` (Jazz Waltz, Swing)**: Walking bass đi trắng + đen (`p`) hoặc 3 phách đen với phách 3 là nốt dẫn (`mp–f`). Rhodes đánh Waltz Charleston ở ô chẵn (phách 1 đen chấm + móc đơn ở 1.5) và phách 1 + phách 3 ở ô lẻ.
   - **`12/8` (Slow Ballad / Blues, Straight — tắt Swing)**: 12 móc/ô chia 4 nhóm 3 móc (phách mạnh `0, 3, 6, 9`). Walking bass `mp–f` đi 4 phách đen chấm kèm **móc đơn pickup dẫn ở móc `5` và móc `11`**. Rhodes điểm hợp âm ở móc `3` và móc `9` (phách 2 và 4), mỗi tiếng ngân dài 1 đen chấm.
   - **Khung chương**: Warm-up có Bass đạp chủ âm và Rhodes đánh figure theo nhịp của chương; Cool-down nối tiếp nốt Saxophone đang chạm biên rồi lắng về `ppp`.

3. **Tối giản (`minimalist` — Không swing, độ phân giải móc kép `divisions=4`)**:
   - **`4/4`** (chương chậm & finale): Sub-bass 4 nốt đen *four-on-the-floor*, Arpeggio 8 móc đơn, Pulse tăng mật độ từ trắng (`p`) lên 16 móc kép (`f`) kèm clap ở phách 2 & 4.
   - **`5/4`** (chương mở 1M-I, 3M-I, tháng mở 1Y): 10 móc/ô chia nhóm **3+2** (`6+4` móc, nhấn móc `0` và `6`). Arpeggio 10 móc đơn (accent ở móc `0` và nhẹ hơn ở móc `6`); Sub-bass 5 nốt đen (tenuto ở phách 1 và phách 4); Stab khuông dưới đóng nhịp ở phách 2 và phách 5.
   - **`7/8`** (scherzo 1M-III, khép 3M-III, tháng khép 1Y): 7 móc/ô chia nhóm **2+2+3** (nhấn móc `0, 2, 4`). Sub-bass đạp **3 xung bất đối xứng** (đen + đen + đen chấm = `2 + 2 + 3` móc); Arpeggio 7 móc đơn nhấn `0, 2, 4`; Pulse mức `f` chạy 14 móc kép nhấn ở móc kép `0, 4, 8`.
   - **Khung chương**: Tắt Arpeggio và Pulse, chỉ giữ mạch Sub-bass đều trên chủ âm (3 xung `2+2+3` nếu là `7/8`) và Pad ngân lắng dần về `ppp`.

4. **Ambient (`ambient` — Không swing)**:
   - **`4/4`** (mở/khép/finale, 8 móc/ô), **`6/4`** (chương chậm, 12 móc/ô, phách mạnh `0, 4, 8`), **`3/4`** (scherzo 1M-III, 6 móc/ô).
   - Các hằng số hơi thở quy đổi theo số móc đơn rồi làm tròn vào vạch ô để tốc độ thở không bị kéo giãn hay dồn cục khi đổi nhịp:
     - Hơi kính (`GLASS_HOLD` / `FLAT_HOLD`): 32 móc ở `4/4` (4 ô) $\rightarrow$ 30 móc ở `3/4` (5 ô) $\rightarrow$ 36 móc ở `6/4` (3 ô).
     - Khoảng cách trụ (`PILLAR_GAP`): luôn giữ **24 móc đơn** (3 ô `4/4`, 4 ô `3/4`, 2 ô `6/4`).
     - Tiếng nở French Horn (`SWELL_HOLD`): 16 móc ở `4/4` (2 ô) $\rightarrow$ 12 móc ở `3/4` (2 ô) và `6/4` (1 ô, hai nốt trắng chấm buộc nhau).
   - **Khung chương**: Kính (Alto Flute) ngân chủ âm từ đầu warm-up và buộc thẳng vào câu đầu nếu cùng cao độ; Cool-down kéo nốt kính đang chạm biên cho tới hết khung và lắng về `ppp`.

---

## 4. Kế hoạch nâng cấp: Đa dạng hóa Nhịp điệu / Cấu trúc gắn liền với Tính cách Thị trường (`1D`, `1W`, `1M`, `3M`, `1Y`)

### A. Triết lý thiết kế: "Thị trường dẫn dắt Hình thức & Nhịp điệu"

Mục tiêu là **cân bằng cả hai yếu tố**:
1. **Tính âm nhạc & Đa dạng cấu trúc**: Tránh sự lặp lại đều đều (monotony) khi nghe các bản dài từ 7 phút (`1W`) tới 47 phút (`1Y`), giúp mỗi khung thời gian và mỗi chương có hình thức âm nhạc (Musical Form) rõ ràng.
2. **Phản ánh trung thực Tính cách Thị trường (Market Character & Regime)**: Mọi sự thay đổi về Groove (nhịp điệu nội tại), Mật độ phối khí (Texture), Tốc độ chuyển hợp âm (Harmonic Rhythm) và Cấu trúc câu (Form) đều phải xuất phát từ dữ liệu giá và thanh khoản thực tế, không thay đổi ngẫu nhiên thuần trang trí.

Hệ thống đọc **2 tầng tín hiệu thị trường** trên mọi khung thời gian:
- **Tầng Vĩ mô (`Character` của Phiên / Tuần / Tháng)**:
  - `rally` (Tăng trưởng / Kéo giá)
  - `selloff` (Bán tháo / Giảm sâu)
  - `volatile` (Biến động mạnh / Giằng co 2 chiều, rũ bỏ hoặc phân phối)
  - `calm` (Đi ngang tích lũy / Biên độ hẹp)
- **Tầng Vi mô (`Regime Transition` giữa các đoạn bên trong chương)**:
  - **Đảo chiều rút chân (`downtrend` $\rightarrow$ `uptrend`)**: Giảm đầu kỳ, kéo ngược cuối kỳ (V-shape recovery).
  - **Đảo chiều xả hàng / Bull-trap (`uptrend` $\rightarrow$ `downtrend`)**: Tăng hưng phấn đầu kỳ, áp lực bán dội xuống cuối kỳ.
  - **Bứt phá / Cao trào thanh khoản (`Breakout` + Volume band `f`)**: Giá vượt đỉnh/đáy kèm dòng tiền lớn.
  - **Nén giá / Cạn cung (`sideway` + Volume band `p`)**: Thị trường nín thở chờ xu hướng.

---

### B. Kế hoạch cho `1D` (1 Phiên — 34 ô: 2 Warm-up + 30 Thân + 2 Cool-down)

Hiện tại `1D` dùng một khung tĩnh (`borrowed=False`, chưa có `session_character`, 3 phrase 8 ô đánh cùng một kiểu groove, và 4 ô Outro đạp lì 1 hợp âm chủ âm). Dù ngắn (~1:30), một phiên giao dịch có đủ 3 hồi kịch tính (**Mở cửa ATO & Phiên sáng** $\rightarrow$ **Giữa phiên** $\rightarrow$ **Cuối chiều & Đóng cửa ATC**).

1. **Định danh Tính cách Phiên (`session_character` cho `1D`)**:
   - Áp dụng ngưỡng trong ngày: `trend = ±1.2%`, `volatility = 2.0%`.
   - Mở khóa **hợp âm mượn có kiểm soát** cho `1D` khi phiên không phải là `calm`:
     - Phiên `selloff` hoặc `volatile` đóng giảm: mở `Fm`, `E7`, `Bm7♭5` để nghe rõ sức nặng bán tháo.
     - Phiên `rally`: mở `D7` (`V/V`) và `C7` (`V/IV`) làm bàn đạp đẩy năng lượng giữa câu.
2. **Groove biến chuyển theo 3 khung giờ trong phiên**:
   - **Phrase 1 (Phiên sáng — 8 ô)**: Nếu mở cửa ở trạng thái `sideway` và thanh khoản `p`/`mp` (thăm dò sau ATO), bè đệm giữ **Half-feel** (Giao hưởng Bass đi nốt trắng, Jazz Walking Bass đi *2-feel*, Tối giản đóng thấp filter) để tạo không gian mở phiên từ tốn.
   - **Phrase 2 (Giữa phiên — 8 ô)**: Nếu phiên là `volatile` hoặc `Regime` ở Phrase 2 đảo chiều so với Phrase 1:
     - Bè đệm chuyển sang **Groove đảo phách `3+3+2` (Tresillo / Syncopation)** ở các ô có biên độ nến lớn (nhấn móc `0, 3, 6` trên nền `4/4`), tái hiện trực tiếp cảm giác giằng co mua–bán trên bảng điện.
   - **Phrase 3 & Outro (Đóng cửa & ATC — 8 ô + 4 ô Outro)**:
     - Thay vì 4 ô Outro đạp lì 1 hợp âm chủ âm: chia thành **2 ô ATC Cadence + 2 ô Tonic Pedal**.
     - Nếu cuối phiên kéo xanh mạnh (`uptrend`) hoặc đạp ATC (`downtrend`), 2 ô đầu Outro thực hiện vòng kết (`IV – V7 – I` hoặc `iv – V7 – vi/i`) nâng đỡ đúng nhịp nến ATC trước khi ngân Pedal ở 2 ô cuối và vào Cool-down.

---

### C. Kế hoạch cho `1W` (1 Tuần — Bản dài 1 chương liền mạch, tối đa 5 phiên)

Bản `1W` dài hơn 7 phút (160 ô thân khi đủ 5 phiên) thực chất là một **Giao hưởng thơ 1 chương (Through-Composed Symphonic Poem)** đi qua 5 ngày giao dịch, có các bước nhảy Gap qua đêm và sự chuyển pha tâm lý từ Thứ Hai đến Thứ Sáu.

1. **Bổ sung Khung Warm-up (2 ô) & Cool-down (2 ô) cho `1W`**:
   - Đưa `1W` về cùng chuẩn cấu trúc với `1D` và `1M+` (tổng 164 ô khi đủ 5 phiên), giúp bản nhạc 7 phút có điểm vào và điểm kết trọn vẹn.
2. **Biến thiên Groove & Hòa âm theo từng Phiên (`SessionCharacter` cho mỗi cụm 32 ô)**:
   - Thay vì cả 160 ô đánh một kiểu đệm đều đặn, mỗi cụm 32 ô (1 phiên) được chấm `session_character` riêng (`rally`, `selloff`, `volatile`, `calm`):
     - **Ngày Tích lũy / Cạn thanh khoản (`calm`)**: Tự động chuyển sang **Trio / Chamber Texture** ở 16 ô giữa phiên (Giao hưởng lược bớt tay phải Piano, Cello giữ nốt dài; Jazz Bass về *2-feel*; Tối giản tắt tiếng clap phách 2–4; Ambient giãn thưa trụ kính). Người nghe nhận ra ngay một phiên giao dịch trầm lắng giữa tuần.
     - **Ngày Rung lắc / Phân phối (`volatile`)**: Kích hoạt **Syncopated Groove `3+3+2`** trên Bass/Comp/Ostinato và giảm `bar_change_penalty` để hợp âm đổi theo từng nhịp giật của giá.
     - **Ngày Bán tháo giữa tuần (`selloff`)**: Cho phép mượn màu **Thứ cùng tên (Modal Mixture: `Fm`, `A♭`, `E♭`, `G7`)** đậm hơn ngay trong phiên đó mà không cần đổi giọng của cả tuần.
     - **Ngày Bùng nổ theo đà (`rally`)**: Mở rộng âm vực bè đệm (Bass đánh quãng 8 năng động, Piano/Rhodes thêm fill dẫn hướng lên ở cuối mỗi phrase 8 ô).
3. **Nâng cấp "Ô thứ 32" thành Cầu nối qua đêm (Overnight Gap Bridge)**:
   - Hiện tại ô 32 của phiên $k$ chỉ ghim tĩnh giá đóng cửa chờ sang phiên $k+1$.
   - **Cải tiến**: So sánh giá đóng cửa phiên $k$ với giá mở cửa phiên $k+1$ (Overnight Gap):
     - Nếu sáng hôm sau **Gap Up (Mở tăng)**: Ô 32 đặt hợp âm dẫn mở (`G7` hoặc `D7 -> G7`) kèm crescendo nhẹ, tạo lực hút đẩy vào phách 1 của phiên mới.
     - Nếu sáng hôm sau **Gap Down (Mở giảm)**: Ô 32 dùng hợp âm căng/hạ (`E7` hoặc `Fm` / `Bm7♭5`) kèm dấu ngắt để người nghe cảm nhận cú hẫng qua đêm.
     - Nếu **Mở tham chiếu (Flat open)**: Giữ hợp âm tĩnh ngân qua vạch phiên như hiện tại.
4. **Coda Tổng kết Tuần (8 ô cuối của Phiên cuối cùng)**:
   - Chia 8 ô Outro cuối tuần thành **4 ô Weekly Summary Cadence** (xét `finale_outro` giữa phiên đầu tuần và phiên cuối tuần để khẳng định tuần tăng hay giảm) + **4 ô Tonic Pedal** dẫn vào Cool-down.

---

### D. Kế hoạch cho `1M`, `3M`, `1Y` (Đa dạng hóa Nhịp điệu & Hình thức Đa chương theo Thị trường)

#### 1. Bổ sung Nhịp điệu mới cho `1Y` và tạo tương phản cho `3M`

- **Ở `1Y` (Tổ khúc 4 mùa — 12 chương, ~47 phút)**:
  - **Vấn đề hiện tại**: Giao hưởng, Jazz và Ambient dùng nhịp `4/4` cho cả Tháng Mở mùa (`T1, 4, 7, 10`), Tháng Khép mùa (`T3, 6, 9`) và Tháng 12 (`T12`) — tức 8/12 chương đều là `4/4`.
  - **Nâng cấp**: Chuyển các **Tháng Khép mùa (`T3, T6, T9` · `108 BPM`)** sang nhịp **`3/4`** cho Giao hưởng (*Scherzo 3/4*), Jazz (*Jazz Waltz 3/4 Swing*) và Ambient (*Floating 3/4*), trong khi Tối giản giữ `7/8`.
    - Số ô thân của Tháng Khép mùa `3/4` đặt bằng **112 ô** (`112 × 6 = 672` móc đơn, bằng đúng `84 × 8 = 672` móc đơn của `4/4` hiện tại), cộng `3+3` ô khung, giúp **thời lượng 3:07 của tháng khép mùa không lệch một giây nào**.
    - Khi đó, **mỗi Quý (Mùa)** trong `1Y` đều có **3 nhịp khác nhau hoàn toàn** ở cả 4 variants:
      - **Giao hưởng**: Mở mùa `4/4` (`100 BPM`) $\rightarrow$ Giữa mùa `6/8` (`66 BPM`) $\rightarrow$ Khép mùa **`3/4`** (`108 BPM`).
      - **Jazz**: Mở mùa `4/4 Swing` $\rightarrow$ Giữa mùa `12/8 Ballad` $\rightarrow$ Khép mùa **`3/4 Jazz Waltz`**.
      - **Tối giản**: Mở mùa `5/4` $\rightarrow$ Giữa mùa `4/4` $\rightarrow$ Khép mùa `7/8`.
      - **Ambient**: Mở mùa `4/4` $\rightarrow$ Giữa mùa `6/4` $\rightarrow$ Khép mùa **`3/4`**.
    - Riêng **Tháng 12 (Finale)** quay về **`4/4` (`96 BPM`, 108 ô)** để khép lại năm bằng nhịp chẵn bề thế.

- **Ở `3M` (3 chương — ~25 phút)**:
  - Chương I (`96 BPM`) và Chương III (`108 BPM`) của Giao hưởng, Jazz, Ambient cùng ở `4/4`.
  - **Nâng cấp**: Giữ `4/4` ở Chương III nhưng áp dụng **kiểu đánh Rondo / Alla Breve (`2/2` feel) kết hợp Groove theo `MovementCharacter` của Tháng thứ 3**:
    - Với **Jazz**: Đoạn giữa (Development/Bridge) của Chương III chuyển sang **Straight-8th Latin / Bossa Groove (nhấn bass `3+3+2`)** khi tháng có sóng (`rally`/`volatile`), rồi bung trở lại **4/4 Swing** ở đoạn Recap cuối chương.
    - Với **Giao hưởng**: Đoạn mở và khép Chương III dùng mẫu Bass/Piano nhấn 2 phách lớn (*Alla breve* năng động), tách bạch hoàn toàn với chất trữ tình của Chương I.

#### 2. Cấu trúc Nội tại của từng Chương (Internal Musical Form) theo Tính cách Thị trường

Thay vì mọi chương trong `1M`, `3M`, `1Y` đều chạy công thức phẳng `Intro → Phrase 1 → Phrase 2 → Phrase 3 → Outro`, mỗi vai chương sẽ có cấu trúc nội tại phản ứng với dữ liệu thị trường của chương đó:

| Vai chương | Cấu trúc mới | Phản ứng theo Tính cách Thị trường (`Character` & `Regime`) |
|---|---|---|
| **Chương Mở / Head**<br>*(`1M-I`, `3M-I`, `1Y` Mở mùa)* | **Sonata thu nhỏ**<br>*(Trình bày – Phát triển – Tái hiện)* | • **Đoạn giữa (Phát triển / `Phrase 2`)**: Nếu chương là `volatile` hoặc `Regime` đoạn giữa ngược chiều đoạn mở, bật **Groove đảo phách `3+3+2`** và tăng tốc độ đổi hợp âm (giảm `bar_change_penalty` từ `0.60` xuống `0.35`).<br>• **Đoạn Tái hiện (`Phrase 3`)**: Trả lại groove ổn định và thưởng thêm cho chủ âm ở đầu câu để tạo cảm giác "trở về nhà". |
| **Chương Chậm / Ballad**<br>*(`1M-II`, `3M-II`, `1Y` Giữa mùa)* | **Ternary `A – B – A'` có Điểm lắng (Caesura)** | • **Ô cuối của Đoạn B (trước khi về `A'`)**: Thêm **1 ô Cầu nối / Half-cadence (`V7`)** với mật độ đệm rút mỏng (chỉ giữ hợp âm ngân, tắt chạy bass) như một nhịp lấy hơi sâu trước khi giai điệu bước vào đoạn tái hiện.<br>• Nếu tuần/tháng là `calm`: mở rộng khoảng thở giữa các câu hát, giảm một bậc mật độ đệm (`mf` $\rightarrow$ `mp`). |
| **Chương Scherzo / Bài ngắn / Khép mùa**<br>*(`1M-III`, `1Y` T3, 6, 9)* | **Scherzo – Trio – Scherzo (`A – B – A`)** | • **Đoạn giữa (`Trio`)**: Mỏng hóa phối khí (tắt bớt bè trầm nặng hoặc Pulse phụ).<br>• **Hiệu ứng "Bear-market Bounce" (Hồi phục trong thị trường giá xuống)**: Nếu cả chương đang ở giọng **Thứ (`selloff`)** nhưng đoạn giữa có `regime = uptrend`, đoạn Trio tự động xoay trục tạm thời về **bậc `♭III` (`E♭maj7`) hoặc `♭VI` (`A♭maj7`)** mang màu Trưởng ấm áp, trước khi rơi về lại chủ âm Thứ ở đoạn Scherzo cuối. |
| **Chương Kết / Finale**<br>*(`1M-IV`, `3M-III`, `1Y-T12`)* | **Coda 2 tầng**<br>*(Summary Cadence + Tonic Pedal)* | • Các chương lớn hiện có Outro rất dài (16 ô ở `1M-IV`, 40–45 ô ở `3M-III`) chỉ đạp 1 hợp âm chủ âm trong lúc giá vẫn biến động.<br>• **Tầng 1 (`coda_drive` — nửa đầu Outro)**: Cho phép chạy tiến trình **Tổng kết xu hướng** (`IV – V – I` nếu kết tăng; `iv – ♭VI – V7 – i` nếu kết giảm; `♭VII – IV – I` nếu đi ngang) để hòa âm vẫn đi cùng những cây nến cuối.<br>• **Tầng 2 (`outro` pedal — 6 đến 8 ô cuối)**: Đạp cố định chủ âm bậc I/i và lắng dần vào khung `cooldown`. |

---

### E. Bảng tóm tắt Ma trận Groove theo Tính cách Thị trường (Áp dụng xuyên suốt `1D` $\rightarrow$ `1Y`)

| Tính cách (`Character`) | Ý nghĩa Thị trường | Phản ứng Hòa âm (Markov / Chords) | Phản ứng Nhịp điệu & Phối khí (Groove & Texture) |
|---|---|---|---|
| **`rally`**<br>*(Tăng trưởng)* | Dòng tiền đẩy giá đi lên bền vững | • Mode **Trưởng** (`I`, `Imaj7`/`Imaj9`).<br>• Ưu tiên hợp âm hướng tiến (`IV`, `V`, `D7`, `C7`). | • **Drive thuận phách**: Bass mở rộng quãng 8 ở phách mạnh; Piano/Rhodes đánh thêm fill hướng lên ở cuối câu; Synth Arpeggio mở sáng filter (`OPEN_CUTOFF`). |
| **`selloff`**<br>*(Bán tháo)* | Áp lực cung áp đảo, giá xuyên thủng hỗ trợ | • Mode **Thứ cùng tên** (`1M+`) hoặc mượn đậm hợp âm thứ `Fm, A♭, E♭, E7, Bm7♭5` (`1D`, `1W`). | • **Trọng lượng dồn xuống (Downward weight)**: Bass đi trầm và liền bậc; hạn chế nhảy quãng 8 sáng; Violin/Sax ưu tiên nhường vùng trầm cho Cello/Tenor Sax; Filter của Tối giản khép tối. |
| **`volatile`**<br>*(Biến động / Giằng co)* | Biên độ dao động lớn, kéo xả liên tục trong kỳ | • Giảm `bar_change_penalty` (`0.45` $\rightarrow$ `0.35` ở đoạn giữa) để hợp âm đổi dồn dập.<br>• Tăng hợp âm đi qua (`F♯°7`, `Bm7♭5`, secondary dominants). | • **Syncopation / Tresillo `3+3+2`**: Trên nền nhịp chẵn (`4/4`), Bass và Comp nhấn lệch vào móc `0, 3, 6` ở các đoạn cao trào (`mf`, `f`), tạo cảm giác căng thẳng, bất ổn của thị trường. |
| **`calm`**<br>*(Tích lũy / Đi ngang)* | Biên độ hẹp, thanh khoản thấp hoặc cân bằng | • Mode **Trưởng**, ưu tiên hợp âm màu êm (`Imaj7`, `Fmaj7`, `B♭maj7` mixolydian).<br>• Tăng `bar_change_penalty` (`0.80`) để mỗi hợp âm ngân dài 2–4 ô. | • **Half-time / Chamber Texture**: Giảm 1 bậc mật độ tiết tấu của bè đệm ở nửa đầu câu (Jazz Bass đi *2-feel*, Giao hưởng dùng nốt trắng/tròn, Tối giản lược bớt xung phụ), tạo không gian tĩnh lặng. |

---

### F. Thứ tự triển khai đề xuất trong Codebase

1. **Bước 1 — Bổ sung Nhịp `3/4` cho Tháng Khép mùa (`T3, 6, 9`) của `1Y` trong `span.py`**:
   - Cập nhật `year_specs(variant)` để `closer` của `symphony`, `jazz`, `ambient` dùng `METER_34` với `112` ô thân (giữ nguyên `672` móc đơn = `3:07` ở `108 BPM`).
2. **Bước 2 — Chia Outro dài thành `coda_drive` + `outro` pedal trong `span.py` và `form.py`**:
   - Tránh việc 16–45 ô cuối của `1M-IV`, `3M-III`, `1Y-T12`, `1W` và `1D` bị đạp cứng 1 hợp âm quá lâu khi giá cuối kỳ vẫn đang di chuyển.
3. **Bước 3 — Cấu trúc nội tại chương (`Trio` cho Scherzo & `Caesura` cho Ballad/Chậm)**:
   - Đánh dấu đoạn giữa của Scherzo (`1M-III`, `1Y` Closer) để phối khí tự động rút gọn mật độ (Trio texture) và mở sáng về `♭III`/`♭VI` nếu đoạn giữa hồi phục trong chương Thứ.
4. **Bước 4 — Groove theo `Character` (`volatile` `3+3+2` syncopation & `calm` half-time) cho cả `1D`, `1W`, `1M`, `3M`, `1Y`**:
   - Bổ sung pattern Bass/Comp theo `character` vào `render.py`, `jazz.py`, `minimalist.py`.
5. **Bước 5 — Nâng cấp `1D` và `1W`**:
   - Thêm `session_character` cho `1D` và từng phiên 32 ô của `1W`; thêm khung warm-up/cool-down cho `1W` và xử lý ô thứ 32 của `1W` thành *Overnight Gap Bridge*.