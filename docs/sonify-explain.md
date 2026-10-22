# Tổng hợp Hiện trạng & Kế hoạch Nhịp điệu / Cấu trúc theo Tính cách Thị trường

> **Trạng thái tài liệu & Liên kết thiết kế**:
> - **Mục 1 – 3 (Hiện trạng)**: Bản tổng hợp tra cứu nhanh đã đối chiếu trực tiếp với code tại ngày `2026-10-22`. Nguồn thiết kế chi tiết nằm ở [`docs/sonify-long-form.md`](./sonify-long-form.md) (form đa chương & 12 hợp âm mở rộng), [`docs/sonify-meter-frame.md`](./sonify-meter-frame.md) (nhịp điệu & khung warm-up/cool-down), [`docs/sonify-sonata-mode.md`](./sonify-sonata-mode.md) (giọng nhà & lật Trưởng/Thứ cùng tên), [`docs/sonify-ambient.md`](./sonify-ambient.md) và [`docs/sonify-instrument-sets.md`](./sonify-instrument-sets.md). Các thông số đồng hồ, số ô và hóa biểu trong mục 1–3 đang được khóa bởi `backend/tests/test_sonify_plan.py` và `backend/tests/test_sonify_stream.py`.
> - **Mục 4 (Đề xuất nâng cấp — Chưa triển khai)**: Đặc tả kỹ thuật nhằm đa dạng hóa nhịp điệu/cấu trúc nội tại và gắn kết chặt với tính cách thị trường (`Character` & `Regime`) trên cả 5 khung `1D`, `1W`, `1M`, `3M`, `1Y`.

Dưới đây là bức tranh tổng thể về **Giọng & Hòa âm gốc (Key, Mode, Tonic)** và **Nhịp điệu (Time Signature, Tempo, Swing, Khung Warm-up/Cool-down)** cho cả **4 variants** (`Giao hưởng`, `Jazz`, `Tối giản`, `Ambient`) trên **5 khung thời gian** (`1D`, `1W`, `1M`, `3M`, `1Y`):

---

## 1. Giọng nhà (Home Key) theo mã cổ phiếu

Mỗi mã cổ phiếu có một **giọng nhà cố định** trên vòng 5 giọng (`Mi♭ – Si♭ – Đô – Rê – La` nối tròn, định nghĩa tại `backend/app/sonify/keys.py`):
- **Đô (`C`, 0 dấu hóa)**: `VNM`, `MSN`, `SAB`, `GAS`, `POW`, `REE`, `PLX`, `BVH`
- **Rê (`D`, +2 cung, 2♯)**: `FPT`, `MWG`, `DGW`, `FRT`, `PNJ`, `CTR`, `CMG`
- **Mi♭ (`Eb`, +3 cung, 3♭)**: `HPG`, `HSG`, `NKG`, `VIC`, `VHM`, `VRE`, `NVL`, `KDH`, `SSI`, `VND`, `HCM`, `VCI`
- **Si♭ (`Bb`, -2 cung, 2♭)**: `VCB`, `BID`, `CTG`, `TCB`, `MBB`, `ACB`, `VPB`, `STB`, `HDB`, `TPB`
- **La (`A`, -3 cung, 3♯)**: `GMD`, `HAH`, `DGC`, `DPM`, `DCM`, `VHC`, `ANV`, `PTB`
- *(Các mã khác băm ổn định bằng `crc32` vào 1 trong 5 giọng này).*

---

## 2. Hòa âm gốc & Chuyển giọng theo Khung thời gian và Variant

### A. Quy tắc lật Trưởng / Thứ cùng gốc (Parallel Major / Minor — áp dụng từ `1M` trở lên cho Giao hưởng, Jazz, Ambient)
Thay vì nhảy sang La thứ giữa bài khi thị trường giảm, cả chương giữ nguyên gốc của giọng chương đó và chọn **Mode** theo tính cách biến động giá của chương (`docs/sonify-sonata-mode.md`):
- **Trưởng (`major`)**: khi chương là `rally` (tăng), `calm` (đi ngang), hoặc `volatile` nhưng kết thúc không phải downtrend.
  - Chủ âm đạp (Intro, đầu câu, Outro, Warm-up/Cool-down): **Bậc I trưởng** (`I`, `Imaj7` — trong không gian Đô là `C`, `Cmaj7`; Jazz/Ambient nâng thành `Cmaj9`). `Am` chỉ đóng vai hợp âm bậc `vi` đi qua giữa câu.
- **Thứ tự nhiên cùng tên (`minor`, thêm 3 dấu giáng vào hóa biểu)**: khi chương là `selloff` (giảm) hoặc `volatile` kết bằng downtrend.
  - Chủ âm đạp: **Bậc i thứ** (`i`, `im7` — trong không gian Đô là `Cm`, `Cm7`; Jazz/Ambient nâng thành `Cm9`).
  - Bộ hợp âm trong chương thứ (`MINOR_CATALOG`): `i (Cm, Cm7)`, `iv (Fm, Fm7)`, `ii° (Dm7♭5)`, `V (G, G7)`, `♭VI (A♭, A♭maj7)`, `♭III (E♭, E♭maj7)`, và hợp âm đi qua 1 ô `F♯°7` trước `G`.
  - Giai điệu hát thang thứ tự nhiên (`C–D–E♭–F–G–A♭–B♭`), và **chỉ nâng `B♭` thành `B` tự nhiên (âm dẫn) trên đúng ô có hợp âm `G` / `G7` / `G9`**.

---

### B. Chi tiết Hòa âm theo từng Khung thời gian (`1D` → `1Y`)

1. **`1D` (1 chương — Tiểu phẩm 34 ô: 2 warm-up + 30 thân + 2 cool-down)**:
   - **Giọng**: Giọng nhà (Trưởng).
   - **Cấu trúc thân (`DAILY_ENSEMBLE_SPEC` & `DAILY_AMBIENT_SPEC` trong `form.py`)**: 2 ô đầu (`0–2`) và 2 ô cuối (`32–34`) là khung pedal chủ âm ngoài thân giá (playhead giữ ở nến đầu và nến cuối qua `ambientDailyCandleIndexAt`); **toàn bộ 30 ô thân (`2–32`) đều là các đoạn `phrase` bám theo giá và thanh khoản `p–f` từng cửa sổ 2 ô**.
   - **Hòa âm**: 12 hợp âm diatonic chuẩn (`C, F, Dm, G, Am, Em` và hợp âm 7, `borrowed=False`). Chủ âm theo regime của phiên (`uptrend`/`sideway` đạp `C`/`Cmaj7`, `downtrend` đạp `Am`/`Am7`).
2. **`1W` (1 chương — 32 ô mỗi phiên, tối đa 160 ô cho 5 phiên, chưa có khung ngoài)**:
   - **Giọng**: Giọng nhà (Trưởng) xuyên suốt cả tuần.
   - **Hòa âm**: Mở thêm 12 hợp âm mượn/secondary dominant (`D7, E7, A7, C7, Fm, Gm, A♭, B♭, B♭7, E♭, Bm7♭5, F♯°7`) lọc theo regime từng phiên, kèm `character` cấp toàn tuần.
3. **`1M` (Sonata 4 chương: I, II, III, IV — nghỉ 6s giữa các chương)**:
   - **Giao hưởng**: Giữ **1 giọng nhà duy nhất** cho cả 4 chương; từng chương tự chọn Trưởng hoặc Thứ cùng tên theo tuần đó.
   - **Jazz (Set 4 bài: Head, Ballad, Bài ngắn, Finale)**:
     - Chương I, II, IV ở **giọng nhà** (Trưởng/Thứ theo tuần).
     - Riêng **Chương III (Bài ngắn)** bước **1 bậc trên vòng giọng** (tuần tăng đi lên vòng, tuần giảm/ngang đi xuống vòng).
     - **Bridge hòa âm**: Trong Chương I, II và IV, đoạn giữa là *Bridge* (`bridge=True`) — phách đầu đoạn giữa ưu tiên về **bậc IV** (`F`/`Fmaj7` ở bài trưởng, `Fm`/`Fm7` ở bài thứ), 2 ô cuối đoạn giữa (`bridge_cadence`) ưu tiên **bậc V (`G`/`G7`)** để hút về **bậc I** ở đoạn tái hiện.
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

## 4. Kế hoạch nâng cấp (Đề xuất): Đa dạng hóa Nhịp điệu / Cấu trúc gắn liền với Tính cách Thị trường (`1D`, `1W`, `1M`, `3M`, `1Y`)

### A. Triết lý thiết kế & Phân định "Đã có vs. Đề xuất mới"

Mục tiêu là **cân bằng cả hai yếu tố**:
1. **Tính âm nhạc & Đa dạng cấu trúc**: Tránh sự lặp lại đều đều (monotony) khi nghe các bản dài từ 7 phút (`1W`) tới 47 phút (`1Y`), đồng thời giải quyết các đoạn `outro` đạp lì 1 hợp âm quá lâu ở các chương cuối.
2. **Phản ánh trung thực Tính cách Thị trường (Market Character & Regime)**: Mọi sự thay đổi về Groove (nhịp điệu nội tại), Mật độ phối khí (Texture), Tốc độ chuyển hợp âm (Harmonic Rhythm) và Cấu trúc câu (Form) đều xuất phát từ dữ liệu giá và thanh khoản thực tế, kèm **nhãn hiển thị rõ trên UI** để người nghe hiểu ý nghĩa của sự thay đổi đó.

**Phân biệt rõ cơ chế đã có trong code và phần mở rộng mới**:
- **Đã có sẵn ở tầng Chương (`1W–1Y`) trong `form.py`**:
  - Phân loại `MovementCharacter` (`rally`, `selloff`, `volatile`, `calm`) trên toàn chương (`keys.py`).
  - Trọng số đổi hợp âm theo character `_CHARACTER_BAR_CHANGE` (`volatile: 0.45`, `rally/selloff: 0.60`, `calm: 0.80`), thiên lệch hợp âm `_DIATONIC_DELTA` và `_BORROWED_DELTA` (`form.py`).
  - Mật độ tiết tấu theo thanh khoản `p–f` trên từng cửa sổ 2 ô (`LIQUIDITY_WINDOWS` / `liquidity_windows_for`).
  - Thưởng `bridge_cadence` về `G`/`G7` ở 2 ô cuối của section có `bridge=True` (`form.py`).
- **Đề xuất mở rộng mới trong kế hoạch này**:
  1. **Rút gọn `outro` pedal dài lê thê** ở các chương lớn (`3M-III`, `1M-IV`, `1Y-T12`, `1W`) bằng cách chuyển nửa đầu `outro` thành `phrase` đi theo giá thực tế cuối kỳ.
  2. **Hạ cơ chế `Character` xuống cho `1D` và từng phiên 32 ô của `1W`** (kèm điều chỉnh groove của bè đệm theo character và sự đảo chiều `Regime` giữa các phrase).
  3. **Bổ sung hình thức nội tại cho chương giữa**: đoạn *Trio mỏng phối khí + Bear-market Bounce (`♭III`/`♭VI`)* cho chương Scherzo, và *1 ô lắng Caesura* ở cuối Bridge của chương Chậm.
  4. **Đưa nhịp `3/4` vào các Tháng Khép mùa (`T3, 6, 9`) của `1Y`** với số ô thân điều chỉnh (`111` ô) để không vượt trần thời lượng `47:21`.
  5. **Hiển thị nhãn Tính cách Thị trường (`characterLabel`) trên Player UI** (`SessionRecap.tsx` & `SpanRecap.tsx`).

---

### B. Kế hoạch cho `1D` (1 Phiên — 34 ô: 2 Warm-up + 30 Thân + 2 Cool-down)

Hiện tại trong `DAILY_ENSEMBLE_SPEC` (`form.py`), 2 ô đầu (`0–2`) và 2 ô cuối (`32–34`) là khung pedal chủ âm ngoài thân giá, còn **cả 30 ô thân (`2–32`, chia thành các đoạn `2 + 8 + 8 + 8 + 4`) đều đã là `phrase` bám theo giá và thanh khoản `p–f`**. Tuy nhiên, `1D` hiện chưa gọi `movement_character` (`character=None`), khóa `borrowed=False`, và chưa có phản ứng groove khi thị trường đảo chiều gắt trong phiên.

1. **Định danh Tính cách Phiên (`session_character` cho `1D`) dựa trên Phân vị Thực nghiệm**:
   - Biên độ trong ngày `(max - min) / min` của cổ phiếu HOSE lớn hơn nhiều so với biến động nến đóng cửa, nên nếu áp ngưỡng cảm tính (như `2.0%`) thì nhãn `volatile` sẽ chiếm đa số phiên và mất tính phân biệt.
   - **Cách xác định ngưỡng chuẩn**: Chạy thống kê phân vị (percentiles) trên dữ liệu nến 1 phút của rổ mã chuẩn trong app (`VNM, FPT, HPG, VCB, GMD, VIC, SSI, MWG...`) để chọn cặp ngưỡng `(trend_1d, vol_1d)` sao cho 4 nhãn `rally`, `selloff`, `volatile`, `calm` phân bố cân đối (~20%–30% mỗi nhóm) trước khi ghi vào `_SPAN_THRESHOLD["1D"]` trong `keys.py`.
   - Mở `borrowed=True` cho `DAILY_ENSEMBLE_SPEC` và `DAILY_AMBIENT_SPEC`: khi đó cơ chế `_BORROWED_DELTA` và `_borrowed_allowed` đã có sẵn trong `form.py` sẽ tự động mở các hợp âm màu (`Fm, E7, Bm7♭5` khi giảm; `D7, C7` khi tăng; `B♭, F♯°7` khi đi ngang) mà không cần viết bảng mới.
2. **Groove biến chuyển theo 3 khung giờ trong phiên (`2+8`, `8`, `8+4` ô thân)**:
   - **Đầu phiên sáng (ô `2–12`)**: Nếu mở cửa ở trạng thái `sideway` và thanh khoản `p`/`mp` (thăm dò sau ATO), hạ 1 bậc mật độ tiết tấu bè đệm (*Half-feel*: Giao hưởng Bass đi nốt trắng, Jazz Walking Bass giữ *2-feel*, Tối giản đóng thấp filter) để tạo không gian mở phiên từ tốn.
   - **Giữa phiên (ô `12–20`)**: Nếu phiên là `volatile` hoặc `Regime` đoạn giữa đảo chiều ngược hẳn đoạn sáng (`uptrend` $\leftrightarrow$ `downtrend`), kích hoạt **Groove Giằng co** ở các cửa sổ thanh khoản `mf`/`f` (chi tiết tương thích từng variant ở Mục E).
   - **Cuối phiên & Đóng cửa ATC (4 ô `phrase` cuối thân `28–32` trước khi vào 2 ô `cooldown` `32–34`)**:
     - Giữ nguyên 4 ô `28–32` là `phrase` để **không đánh mất dữ liệu nến 14:15–14:45 & ATC** và không làm lệch `ambientDailyCandleIndexAt` trong `src/utils/recapCursor.ts`.
     - Chỉ bổ sung một thưởng nhẹ (*soft cadential bias*, tương tự `bridge_cadence` sẵn có) cho bậc `IV/iv` ở ô `28–29` và `V/V7` ở ô `30–31`: Viterbi chỉ chọn hợp âm dẫn kết khi nó vẫn khớp cao độ nến cuối phiên, tuyệt đối không ép cứng hợp âm như `_PEDAL`.

---

### C. Kế hoạch cho `1W` (1 Tuần — Bản dài 1 chương liền mạch, tối đa 5 phiên)

Bản `1W` dài hơn 7 phút (160 ô thân khi đủ 5 phiên) đi qua 5 ngày giao dịch liên tiếp. Hiện tại cả tuần chỉ có 1 `character` chung và mỗi phiên trừ phiên cuối ghim giá đóng cửa ở ô thứ 32.

1. **Bổ sung Khung Warm-up (2 ô) & Cool-down (2 ô) cho `1W`**:
   - Đưa `1W` qua `attach_frame(spec, "1W")` với 2 ô warm-up và 2 ô cool-down (tổng 164 ô khi đủ 5 phiên), đồng thời cập nhật `warmupSec` và `cooldownSec` trong manifest `1W` (hiện `SpanRecap` đã dùng `spanCandleIndexAt(elapsed, count, durationSec, warmupSec, cooldownSec)` nên playhead tự động đứng ở nến đầu/cuối trong khung mà không cần sửa logic frontend).
2. **Hạ `Character` xuống từng Phiên 32 ô (`session_characters` trong `1W`)**:
   - Thay vì dùng 1 `character` duy nhất cho cả 160 ô, chấm `character` riêng cho từng phiên 32 ô (`rally`, `selloff`, `volatile`, `calm`) và truyền mảng `character_by_bar` vào `plan_markov_chords` cũng như bộ render:
     - **Phiên Tích lũy (`calm`)**: Tự động rút gọn về **Chamber / Half-time Texture** ở 16 ô giữa phiên (Giao hưởng lược bớt tay phải Piano, Cello giữ nốt dài; Jazz Bass về *2-feel*; Tối giản tắt tiếng clap phách 2–4; Ambient giãn thưa trụ kính).
     - **Phiên Rung lắc (`volatile`)**: Giảm `bar_change_penalty` trong phiên đó và bật Groove Giằng co ở các cửa sổ `mf`/`f`.
     - **Phiên Bán tháo giữa tuần (`selloff`)**: Áp `_DIATONIC_DELTA["selloff"]` và `_BORROWED_DELTA["selloff"]` ngay trên 32 ô của phiên đó để nhuộm màu Thứ (`Fm, A♭, E♭, E7`) đúng ngày thị trường giảm.
3. **Nâng cấp "Ô thứ 32" thành Cầu nối qua đêm (Overnight Gap Bridge — Foreshadowing có lọc GDKHQ)**:
   - **Bản chất âm nhạc**: Trong `week_source_groups`, ô 32 của phiên $k$ (`k < last`) vốn có nhóm nguồn rỗng `[]` (ghim lại giá đóng cửa phiên $k$). Khi phát lại tuần lịch sử, ta dùng ô 32 này như một nhịp **báo trước có chủ đích (musical foreshadowing / attacca transition)** dẫn sang phách 1 của phiên $k+1$.
   - **Xử lý đặc thù dữ liệu HOSE (Nhiễu ATO & Ngày GDKHQ)**:
     - Khoảng cách giá mở cửa ở HOSE có thể bị nhiễu bởi lệnh ATO hoặc bị điều chỉnh kỹ thuật vào ngày Giao dịch không hưởng quyền (cổ tức, thưởng cổ phiếu) khiến giá giảm > 7% mà không phải bán tháo.
     - **Quy tắc lọc an toàn**:
       1. Tính `gap_pct` giữa giá đóng cửa phiên $k$ và **giá trung vị của 15 phút đầu sau ATO (09:15–09:30) của phiên $k+1$**.
       2. Chỉ kích hoạt *Overnight Gap Bridge* khi **`0.008 (0.8%) ≤ |gap_pct| ≤ 0.068 (6.8%)`** (nằm trong biên độ trần/sàn `±7%` của HOSE; mọi cú lệch `> 6.8%` được coi là điều chỉnh tham chiếu GDKHQ hoặc dữ liệu khuyết và sẽ giữ nguyên hợp âm tĩnh như hiện tại).
       3. Khi hợp lệ: **Gap Up (`+0.8%` đến `+6.8%`)** ưu tiên hợp âm dẫn mở (`G7` hoặc `D7`) ở ô 32 kèm crescendo nhẹ; **Gap Down (`-0.8%` đến `-6.8%`)** ưu tiên hợp âm căng (`E7`, `Fm` hoặc `Bm7♭5`) kèm diminuendo.

---

### D. Kế hoạch cho `1M`, `3M`, `1Y` (Đa dạng hóa Nhịp điệu & Hình thức Đa chương theo Thị trường)

#### 1. Bổ sung Nhịp `3/4` cho Tháng Khép mùa (`T3, 6, 9`) của `1Y` (Giữ trần `47:21`)

- **Vấn đề hiện tại**: Trong `1Y`, Giao hưởng, Jazz và Ambient dùng nhịp `4/4` cho cả Tháng Mở mùa (`T1, 4, 7, 10`), Tháng Khép mùa (`T3, 6, 9`) và Tháng 12 (`T12`) — tức 8/12 chương đều là `4/4`.
- **Tái sử dụng `METER_34` đã có của Scherzo `1M-III`**:
  - Chuyển các **Tháng Khép mùa (`T3, T6, T9` · `108 BPM`)** sang nhịp **`3/4`** cho Giao hưởng (*Scherzo 3/4*), Jazz (*Jazz Waltz 3/4 Swing*) và Ambient (*Floating 3/4*), trong khi Tối giản giữ `7/8`.
- **Bài toán đồng hồ & khung chương (`frame_bars_for`)**:
  - Hiện tại tháng khép mùa `4/4` có `84` ô thân + `2+2` ô khung = `88` ô `4/4` = **`704` móc đơn** (`195.56s` ở `108 BPM`).
  - Trong `span.py`, `frame_bars_for(METER_34, "1Y")` quy định **3 ô mỗi đầu** (`3+3 = 6` ô khung `3/4` = **`36` móc đơn**). Nếu lấy `112` ô thân (`672` móc đơn) thì tổng tháng sẽ là `672 + 36 = 708` móc đơn (dư `+4` móc đơn/tháng = `+3.33s` cả năm, đẩy Giao hưởng lên `47:24`, vượt trần `47:21` trong `docs/sonify-long-form.md` và làm gãy `test_piece_clocks_include_the_frame_and_the_rests`).
  - **Giải pháp chính xác**: Đặt thân Tháng Khép mùa `3/4` bằng **`111` ô** (`666` móc đơn thân + `36` móc đơn khung `3+3` = **`702` móc đơn tổng**, tức `195.00s` ở `108 BPM`, chỉ ngắn hơn `0.56s` mỗi tháng so với `4/4`).
    - Chia đoạn của `closer` `3/4` (`111` ô thân): `8 intro + 42 phrase 0 + 42 phrase 1 + 11 phrase 2 (coda_drive) + 8 outro = 111 ô`, cụm xuất `(50, 111)`.
    - **Tổng thời lượng `1Y` sau nâng cấp**:
      - **Giao hưởng**: `2839.3s` (**`47:19`**, nằm dưới trần `47:21`).
      - **Tối giản**: giữ nguyên `2840.6s` (**`47:20`**).
      - **Jazz & Ambient**: `2818.0s` (**`46:58`**).
  - Nhờ đó, **mỗi Quý (Mùa)** trong `1Y` đều có **3 nhịp khác nhau hoàn toàn** ở cả 4 variants (`4/4 → 6/8 → 3/4` cho Giao hưởng; `4/4 Swing → 12/8 Ballad → 3/4 Waltz` cho Jazz; `5/4 → 4/4 → 7/8` cho Tối giản; `4/4 → 6/4 → 3/4` cho Ambient), rồi **Tháng 12 (Finale)** quay về `4/4` (`96 BPM`).

#### 2. Giải quyết "Đoạn chết" ở Coda dài & Cấu trúc Nội tại của từng Chương

Thay vì thêm một loại `Section` mới vào `_PEDAL` (sẽ kéo theo sửa `liquidity_windows_for` và con trỏ phát nhạc), mọi cải tiến cấu trúc nội tại đều **giữ nguyên tổng số ô của chương** và tận dụng trực tiếp cơ chế `FormSection` hiện có:

| Vai chương | Vấn đề hiện tại & Giải pháp Cấu trúc | Cơ chế kỹ thuật & Phản ứng theo Thị trường |
|---|---|---|
| **Chương Kết / Finale**<br>*(`1M-IV`, `3M-III`, `1Y-T12`, `1W`)* | • Hiện tại `outro` (thuộc `_PEDAL`, khóa cứng 1 hợp âm chủ âm) quá dài: `1M-IV` có `16` ô outro, `3M-III` có tới **`40` ô outro** (`45` ô ở Tối giản) đạp lì 1 hợp âm trong lúc giá vẫn biến động.<br>• **Giải pháp (Coda 2 tầng)**: Giữ `outro` pedal đúng **8 ô cuối**, chuyển toàn bộ số ô dư phía trước (`8` ô ở `1M-IV`, `32` ô ở `3M-III`, `37` ô ở `3M-III` Tối giản, `4` ô ở `1Y-T12`) thành một `FormSection(..., kind="phrase", regime_slot=2)`. | • Vì mang `kind="phrase"`, nửa đầu Coda tự động được Viterbi chọn hợp âm bám theo những cây nến cuối kỳ và tự động chia cửa sổ thanh khoản 2 ô trong `liquidity_windows_for`.<br>• 2 ô cuối của đoạn `phrase` này nhận thưởng `V/V7` để đổ về 8 ô `outro` Pedal chủ âm (vẫn tôn trọng `finale_outro` override giữa đầu kỳ và cuối kỳ).<br>• Không làm thay đổi tổng số ô hay logic `spanCandleIndexAt` trong `recapCursor.ts`. |
| **Chương Scherzo / Bài ngắn / Khép mùa**<br>*(`1M-III`, `1Y` T3, 6, 9)* | • Chưa có sự tương phản về phối khí ở đoạn giữa như hình thức **Scherzo – Trio – Scherzo (`A – B – A`)** cổ điển. | • Đánh dấu đoạn giữa (`regime_slot=1`) là **Trio**: rút nhẹ 1 bậc mật độ bè trầm/percussion ở nửa đầu đoạn giữa để tạo khoảng sáng.<br>• **Hiệu ứng "Bear-market Bounce"**: Nếu cả chương đang ở mode **Thứ (`minor`)** nhưng đoạn giữa có `regime == "uptrend"`, `minor_bias` tại đoạn giữa giảm cost cho **`♭III` (`E♭`, `E♭maj7`) và `♭VI` (`A♭`, `A♭maj7`)** (vốn đã có sẵn trong `MINOR_CATALOG`), đồng thời thưởng phách đầu đoạn giữa cho `E♭`/`E♭maj7`. Người nghe cảm nhận rõ nhịp hồi phục ấm áp giữa thị trường giá xuống trước khi quay về chủ âm Thứ ở đoạn A cuối. |
| **Chương Chậm / Ballad**<br>*(`1M-II`, `3M-II`, `1Y` Giữa mùa)* | • Chuyển từ đoạn giữa (B) về đoạn tái hiện (A') chưa có điểm lắng lấy hơi. | • **Tận dụng `bridge=True` và `bridge_cadence` sẵn có**: Bật `bridge=True` cho đoạn giữa của Chương Chậm ở cả Giao hưởng (hiện mới bật cho Jazz và Ambient).<br>• **Caesura tại ô cuối cùng của đoạn Bridge (`section.end - 1`)**: Không chèn thêm ô mới ngoài lưới; ngay tại ô cuối cùng của Bridge (nơi `bridge_cadence` đã ưu tiên hợp âm `G`/`G7`), bộ render (`render.py`, `jazz.py`, `minimalist.py`) ngắt chạy bass/fill ở nửa sau ô và chỉ ngân hợp âm `V7` để tạo nhịp lấy hơi trước khi vào phách 1 của câu tái hiện. |

---

### E. Ma trận Groove theo Tính cách Thị trường & Quy tắc Tương thích với Swing

> **Quy tắc bất biến với Swing của Jazz**: Trong `form.py`, `swing_for("jazz", meter)` bật Swing 2:1 toàn chương cho `4/4` và `3/4` (`musicxml.py` xuất `<swing>`). Việc áp tiết tấu Tresillo `3+3+2` (nhấn móc `0, 3, 6`) lên lưới móc đơn đang bị Swing 2:1 bẻ chẵn–lẻ sẽ làm móc lẻ `3` bị trễ và nghe như lỗi nhịp. Do đó, **Tresillo `3+3+2` chỉ áp dụng cho các variant Straight (`symphony`, `minimalist` ở `4/4`)**, còn **`jazz` dùng Syncopated Swing Comping chuẩn Hard-Bop** trên đúng lưới Swing 2:1.

| Tính cách (`Character`) | Nhãn UI (`characterLabel`) | Phản ứng Hòa âm (`form.py`) | Phản ứng Nhịp điệu & Phối khí theo từng Variant |
|---|---|---|---|
| **`rally`** | `Tăng giá` | • Mode **Trưởng** (`1M+`).<br>• Ưu tiên `I, IV, V, D7, C7` (đã có trong `_DIATONIC_DELTA` / `_BORROWED_DELTA`). | • **Giao hưởng**: Bass mở rộng quãng 8 ở phách mạnh (`mf`, `f`); Piano thêm fill hướng lên cuối câu.<br>• **Jazz**: Walking bass 4 phách năng động, Rhodes thêm fill dẫn ở cuối phrase.<br>• **Tối giản**: Arpeggio mở sáng filter (`OPEN_CUTOFF`).<br>• **Ambient**: Giữ nguyên độ thưa chuẩn, ưu tiên trụ kính ở quãng sáng. |
| **`selloff`** | `Bán tháo` | • Mode **Thứ cùng tên** (`1M+`) hoặc mượn đậm `Fm, A♭, E♭, E7, Bm7♭5` (`1D`, `1W`). | • **Giao hưởng & Jazz**: Bass đi vùng trầm liền bậc, hạn chế nhảy quãng 8 sáng; Violin/Alto Sax nhường sớm vùng trung-trầm cho Cello/Tenor Sax.<br>• **Tối giản**: Filter khép tối (`CLOSED_CUTOFF`), tắt bớt accent sáng.<br>• **Ambient**: Swell French Horn dày hơn ở vùng trầm. |
| **`volatile`** | `Giằng co` | • Giảm `bar_change_penalty` (`0.45`, riêng đoạn giữa hạ xuống `0.35`) để hợp âm đổi dồn dập theo từng nhịp giật của giá. | • **Giao hưởng (`4/4` Straight)**: Ở cửa sổ `mf`/`f` của đoạn biến động, Bass & Piano nhấn mẫu **Tresillo `3+3+2`** (móc `0, 3, 6`, tức đen chấm + đen chấm + đen).<br>• **Tối giản (`4/4` Straight)**: Sub-bass và Stab khuông dưới nhấn mẫu **`3+3+2`** (`0, 3, 6`) thay vì four-on-the-floor đều.<br>• **Jazz (`4/4` Swing 2:1)**: **Không dùng `3+3+2`**; Rhodes đánh **Hard-Bop Syncopation** (móc `0`, móc `3` "and of 2", và móc `7` "and of 4" dẫn qua vạch ô — hoàn toàn khớp lưới Swing 2:1), Walking bass thêm nốt dẫn nửa cung (*chromatic approach*).<br>• **Ambient**: Không đảo phách; rút ngắn `SWELL_GAP_BARS` từ 4 xuống 3 ô để tiếng kèn nở dồn hơn. |
| **`calm`** | `Tích lũy` | • Mode **Trưởng**, `bar_change_penalty = 0.80` để mỗi hợp âm ngân dài 2–4 ô. | • **Mọi variant (Half-time / Chamber Texture)**: Ở nửa đầu mỗi câu có thanh khoản `p`/`mp`, hạ 1 bậc mật độ tiết tấu bè đệm (Giao hưởng Bass đi nốt tròn/trắng; Jazz Bass giữ *2-feel*; Tối giản tắt clap phách 2–4; Ambient tăng `PILLAR_GAP` thêm 1 ô). |

---

### F. Hiển thị Tính cách Thị trường trên UI & Thứ tự triển khai (Ưu tiên theo Tần suất Sử dụng)

#### 1. Chú giải Tính cách Thị trường trên Player UI
Để người nghe hiểu ngay mối liên hệ giữa âm nhạc (nhịp dồn dập, màu thứ trầm, hay nhịp thưa tĩnh lặng) với dữ liệu thị trường thay vì tưởng là hiệu ứng ngẫu nhiên:
- **Backend (`backend/app/routers/sonify.py`, `stream.py`, `replay.py`)**:
  - Trả thêm `character: MovementCharacter` và `characterLabel: str` (`"Tăng giá" | "Bán tháo" | "Giằng co" | "Tích lũy"`) trong `RecapManifest` (`1D`) và `SpanMovementResponse` (`1W, 1M, 3M, 1Y`).
- **Frontend (`src/api/client.ts`, `src/components/SessionRecap.tsx`, `src/components/SpanRecap.tsx`)**:
  - Ở `SpanRecap.tsx`: hiển thị nhãn tính cách ngay trên nút phát và trạng thái chuẩn bị, ví dụ: `Tạm dừng · I · Rê thứ · Bán tháo` hoặc `Tiếp tục · II · Đô trưởng · Tích lũy`.
  - Ở `SessionRecap.tsx` (`1D`): hiển thị dòng chú giải nhỏ cạnh thông tin phiên/nút Nghe (ví dụ: `Đô trưởng · Giằng co`).

#### 2. Thứ tự triển khai trong Codebase (Từ tác động cao nhất & tần suất nghe nhiều nhất)

1. **Bước 1 — Coda 2 tầng (Sửa đoạn `outro` đạp lì dài ở `1M-IV`, `3M-III`, `1Y-T12` và `1W`)**:
   - **Phạm vi file**: `backend/app/sonify/span.py`, `backend/app/sonify/form.py`, `backend/tests/test_sonify_plan.py`.
   - Rút `outro` pedal về đúng 8 ô cuối ở các chương Finale, chuyển các ô phía trước thành `phrase` đi theo giá cuối kỳ kèm thưởng `V/V7` ở 2 ô sát `outro`.
2. **Bước 2 — `Character` & Groove cho `1D` và `1W` + Nhãn UI trên Player (Tần suất sử dụng hằng ngày cao nhất)**:
   - **Phạm vi file**: `backend/app/sonify/keys.py`, `backend/app/sonify/form.py`, `backend/app/sonify/span.py`, `backend/app/sonify/render.py`, `backend/app/sonify/jazz.py`, `backend/app/sonify/minimalist.py`, `backend/app/sonify/ambient.py`, `backend/app/routers/sonify.py`, `src/api/client.ts`, `src/components/SessionRecap.tsx`, `src/components/SpanRecap.tsx`.
   - Chạy thống kê phân vị trên dữ liệu phiên HOSE để chốt `_SPAN_THRESHOLD["1D"]`; bật `borrowed=True` và `character` cho `1D`; chấm `character` theo từng phiên 32 ô của `1W` + thêm khung `2+2` và *Overnight Gap Bridge* (lọc `0.8% ≤ |gap| ≤ 6.8%`); bổ sung pattern Groove (`3+3+2` cho Giao hưởng/Tối giản, *Hard-Bop syncopation* cho Jazz, *Half-feel* cho `calm`) và hiển thị `characterLabel` trên UI.
3. **Bước 3 — Cấu trúc nội tại `Trio` (Scherzo) & `Caesura` (Chương Chậm) cho `1M`, `3M`, `1Y`**:
   - **Phạm vi file**: `backend/app/sonify/form.py`, `backend/app/sonify/chords.py`, `backend/app/sonify/span.py`, `backend/app/sonify/render.py`, `backend/app/sonify/jazz.py`, `backend/app/sonify/minimalist.py`.
   - Thêm thiên lệch *Bear-market Bounce* (`♭III` / `♭VI`) và rút mỏng phối khí ở đoạn giữa của Scherzo; bật `bridge=True` cho chương chậm Giao hưởng và tạo điểm lắng *Caesura* ở nửa sau ô cuối đoạn Bridge.
4. **Bước 4 — Nhịp `3/4` cho Tháng Khép mùa (`T3, 6, 9`) của `1Y`**:
   - **Phạm vi file**: `backend/app/sonify/span.py`, `backend/tests/test_sonify_plan.py`.
   - Cập nhật `closer` của `year_specs` sang `METER_34` với `111` ô thân + `3+3` ô khung (`702` móc đơn), giữ tổng thời lượng `1Y` ở `47:19` (Giao hưởng) và `46:58` (Jazz/Ambient), nằm dưới trần `47:21`.

---

### G. Tiêu chí Nghiệm thu (Acceptance Criteria & Kiểm thử)

1. **Kiểm thử Tự động (`pytest` trong `backend/tests/test_sonify_plan.py` & `test_sonify_stream.py`)**:
   - **Khóa đồng hồ**: Tổng thời lượng `1M`, `3M`, `1Y` của cả 4 variants không vượt trần `47:21` (`2841s`); riêng `1Y` Giao hưởng sau khi đổi `closer` sang `111` ô `3/4` đạt `2839.3s ± 1.5s`.
   - **Khóa lưới nhịp & Swing**: Score Jazz `4/4` ở trạng thái `volatile` vẫn giữ `swing=True` và mọi nốt Rhodes/Walking Bass nằm hợp lệ trong độ dài ô; Score Giao hưởng/Tối giản `4/4` ở trạng thái `volatile` xuất đúng mẫu `3+3+2` (`0, 3, 6`) trên các ô `mf`/`f`.
   - **Khóa Coda & Playhead**: Số ô `outro` pedal của `3M-III` giảm từ `40` xuống `8` ô (các ô trước đó có `section == "phrase"` và có mặt trong `liquidity_windows_for`); `span_candle_index` và `ambientDailyCandleIndexAt` không bị lệch biên warm-up/cool-down.
   - **Khóa bộ lọc Gap `1W`**: Cú lệch qua đêm `> 6.8%` (mô phỏng ngày GDKHQ chia cổ tức/cổ phiếu) không kích hoạt hợp âm bán tháo ở ô thứ 32.
2. **Nghiệm thu Nghe đối chứng (Listening Benchmark `5 mã × 4 tính cách`)**:
   - Xuất MusicXML & MP4/M4A và nghe kiểm tra trực tiếp trên 5 mã đại diện cho 5 giọng nhà (`VNM` – Đô, `FPT` – Rê, `HPG` – Mi♭, `VCB` – Si♭, `GMD` – La) qua 4 mẫu thị trường thực tế (`rally`, `selloff`, `volatile`, `calm`) ở `1D`, `1W` và `1M` để xác nhận chuyển tiếp tự nhiên, không gắt phách trước khi merge từng bước.
