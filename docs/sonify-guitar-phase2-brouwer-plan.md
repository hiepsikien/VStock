# Kế Hoạch Giai Đoạn 2: Mở Rộng Sor (Op. 9 & Galop Op. 32), Cân Bằng *La Catedral Preludio* & Ma Trận 1D, Bổ Sung Variant Leo Brouwer

> **Tài liệu tham chiếu**: [`docs/brouwer.txt`](./brouwer.txt), [`docs/sonify-improve.txt`](./sonify-improve.txt), [`docs/sonify-guitar-improvement-plan.md`](./sonify-guitar-improvement-plan.md)

---

## 1. Bổ Sung Pattern Tươi Vui & Biến Tấu Cổ Điển Cho Fernando Sor (`classic`)
1. **`galop` (*Galop Op. 32 No. 6*) — Tươi vui, rộn rã, bật nảy**:
   - **Kết cấu**: Vũ khúc Galop cổ điển châu Âu. Bè Bass (`p`) đánh nốt gốc và bậc 5 nảy gọn (`staccato`) ở phách mạnh (`0, 4` trong 4/4; `0, 3` trong 6/8; `0, 4` trong 3/4), bè Trung (`i-m`) đáp hợp âm giòn ở các móc đơn phách yếu (`1, 3, 5, 7`), bè Cao (`a`) hát đường giá với các nốt chấm dôi / lướt tươi sáng ở giọng Trưởng.
   - **Kích hoạt**: Các phiên/chương Tăng mạnh (`rally` có biên độ tốt / `strong_rally`) hoặc chương kết tươi sáng của Sor.
2. **Introduction *Biến tấu Cây sáo thần Mozart (Op. 9)* & Pattern `mozart_var`**:
   - **Intro Frame Sor (`guitar_frame.py`)**: Nâng cấp phần mở đầu của Sor theo đúng tinh thần *Introduction Op. 9*: Mở đầu bằng hợp âm khối 3 bè uy nghi kèm tiết tấu chấm dôi Pháp (*French Overture dotted rhythm*) tiến về hợp âm Át (`V7`), tiếp nối bằng câu lướt arpeggio/scale thanh lịch dẫn vào thân bài.
   - **Pattern `mozart_var` (*Op. 9 Variations*)**: Dành cho các phiên/chương Giằng co sôi động (`volatile`) của Sor — bè Cao và bè Trung đan xen đối vị với các nốt lướt liền bậc hoa mỹ trên nền bass cổ điển chuẩn mực.

---

## 2. Ma Trận Phân Loại Ngày `1D` Đa Chiều & Khai Thác Tối Đa *La Catedral Preludio* (Barrios)
1. **Khắc phục hiện tượng 90% ngày `1D` bị rơi vào `calm` (`keys.py`, `guitar_patterns.py`)**:
   - Nâng cấp phân loại phiên `1D`: Hạ ngưỡng hợp lý cho thị trường HOSE trong `movement_character` (`1D`: trend `0.0045` ~ `0.45%`, volatility `0.013` ~ `1.3%`, đồng thời xét vị trí đóng cửa trong biên độ ngày `close_pos = (close - low) / (high - low)` khi biên độ $\ge 1.0\%$: `close_pos >= 0.72` → `"rally"`, `close_pos <= 0.28` → `"selloff"`).
   - Bên trong bộ chọn Guitar (`_dominant_pattern`), phân biệt rõ **Tăng/Giảm êm (`steady` / biên độ vừa)** với **Tăng/Giảm bùng nổ (`strong_rally` / `volatile` / `rel_span` cao)** và đo độ chạy thực tế trên `raw` pitches thay vì chỉ đếm `_has_hold` (vốn luôn đạt 85–100% sau khi lượng tử hóa).
2. **Đặt `preludio` (*La Catedral — Preludio Saudade*) vào vị trí trung tâm cho Barrios**:
   - **Ở các bộ nhiều chương (`1M`, `3M`, `1Y`)**:
     - **Chương I (Chương mở đầu 4/4 `96–100 BPM`)**: Luôn ưu tiên **`preludio` (*La Catedral*)** làm pattern chủ đạo (bass ngân 2 ô nhịp + bè trung rải đối âm 4 nốt + chuông cao `76–83`), mở ra không gian thánh đường đặc trưng của Barrios.
     - **Chương II (Chậm 3/4 `60–72 BPM`)**: **`andante`** (*Andante Religioso*) + **`thumb_cantabile`** (*Julia Florida*) ở đoạn giữa `bridge`.
     - **Chương III (Nhanh 6/8 Scherzo `108–120 BPM`)**: Điệu nhảy Nam Mỹ **`polca` / `hemiola`** ở phần A + **`vals`** (*Vals Op. 8*) hoặc **`thumb_cantabile`** ở đoạn giữa `trio`.
     - **Chương IV / Chương cuối (`1M` IV, `3M` III)**: Dành trọn cho **`tremolo`** (*Ultimo Tremolo*) hoặc **`choro`** làm đỉnh cao khép lại bộ Suite.
   - **Ở bản ngắn `1D`**:
     - Phiên đi ngang (`calm`) hoặc phiên tăng/giảm biên độ vừa (`rel_span < 0.016`): **`preludio` (*La Catedral*)** (hoặc `andante` khi biên độ cực phẳng).
     - Phiên tăng/giảm mạnh có sóng giữ giá (`rally` / `selloff` với `rel_span >= 0.016`): **`tremolo`**.
     - Phiên giằng co nhảy giá liên tục (`volatile`): **`choro`**.

---

## 3. Bổ Sung Variant Thứ 4 Cho Guitar Cổ Điển: Leo Brouwer (`brouwer`)
1. **UI & Hệ thống Variant/Ensemble (`src/api/client.ts`, `model.py`, `ensemble.py`, `guitar.py`)**:
   - Thêm `"brouwer"` vào `Ensemble` và `ENSEMBLES`, hiển thị nút **`Brouwer`** trên hàng chọn nghệ sĩ Guitar (`Sor | Barrios | Lobos | Brouwer`).
   - Tempo `1D` của Brouwer: `108 BPM`.
2. **Hòa âm Hiện đại & Jazz-Afro-Cuban (`BrouwerDialect` trong `harmony.py`)**:
   - Kết hợp các hợp âm màu Jazz (`Cmaj7`, `Fmaj7`, `Am7`, `Dm7`, `Em7`, `Bb7`, `Abmaj7`, `Bm7b5`, `Dm7b5`) và các hợp âm treo/quãng 2 hiện đại (`Csus2`, `Dsus2`, `Esus4`, `Fsus2`, `G7sus4`, `Bbsus2`, `Ebsus2`, `Cmadd9`, `Fmadd9`) từ *12 Estudios Sencillos* và *Un Día de Noviembre*.
3. **4 Pattern chủ đạo của Leo Brouwer (`guitar_patterns.py`)**:
   - **`noviembre` (*Un Día de Noviembre* — Cinematic Lyricism)**: Giai điệu tự sự trữ tình trên nền Bass nhịp đôi nhẹ nhàng (`phách 1, 3`) và bè Trung rải arpeggio màu `maj7 / add9 / m7` ấm áp (dành cho `calm` / đoạn nghỉ).
   - **`brouwer_etude` (*Estudios Sencillos No. 1, No. 5, No. 6* — Afro-Cuban Syncopated Bass & Open-String Motor)**: Ngón cái `p` đánh đường Bass lệch phách kiểu Cuba (`tumbao`: móc đơn `0, 3, 6` trong 4/4) xen kẽ các chùm hợp âm/arpeggio dây buông ở ngón `i-m-a` (dành cho `rally` / xu hướng tăng).
   - **`elogio_pizz` (*Elogio de la Danza & Estudio No. 10/11* — Staccato Ostinato & Bartók Pizzicato)**: Hợp âm khối quãng nghịch nhẹ đánh ngắt âm giòn (`staccato=True`) trên nhịp lệch, điểm các nhát nhấn mạnh (`accent=True` kiểu *Bartók pizzicato / golpe*) khi biến động mạnh (`volatile`).
   - **`sarabande` (*Sarabanda de Śnieg & El Decamerón Negro* — Neo-Sarabande & Chromatic/Modal Swarm)**: Nhấn trọng âm hợp âm màu vào phách 2 (đặc trưng điệu Sarabande tân cổ điển ở nhịp `3/4` hoặc phiên `selloff`), kết hợp các câu lướt nhanh về phách mạnh.
4. **Bộ Intro & Outro 2 ô / 4 ô của Leo Brouwer (`guitar_frame.py`)**:
   - **Option A (Kịch tính / Biến động mạnh — `volatile`, `selloff`)**: Intro mở bằng cú chập hợp âm quãng 2/4 ngắt gọn (`staccato` + `accent`) và câu lướt `staccato` 4 nốt lên cao; Outro dập 2 cú hợp âm khối lệch phách (`Stab & Mute End`) rồi ngắt gọn.
   - **Option B (Trữ tình điện ảnh — `calm`, `rally`)**: Intro mở bằng nốt Bass dây buông ngân dài + Harmonics và câu rải hợp âm `m9 / sus2` mềm mại; Outro lắng dần (`Acoustic Dissolve`) kết bằng hợp âm Picardy Third + Harmonics.
