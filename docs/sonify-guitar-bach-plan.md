# Kế Hoạch Thiết Kế & Triển Khai Variant Baroque: J.S. Bach (`ensemble = "bach"`)

> **Tài liệu tham chiếu**: [`guitar_bach.txt`](../guitar_bach.txt), [`docs/sonify-guitar-improvement-plan.md`](./sonify-guitar-improvement-plan.md)
> **Mục tiêu**: Hoàn thiện Trục 5 Đại Sư Lịch Sử Guitar (`Bach | Sor | Barrios | Lobos | Brouwer`) bằng việc đưa J.S. Bach (thời kỳ Baroque) đứng đầu danh sách Guitar.

---

## 1. Giao Diện & Đăng Ký Hệ Thống (`src/api/client.ts`, `model.py`, `ensemble.py`, `guitar.py`, `schemas.py`)
- **Frontend (`src/api/client.ts`)**:
  - Thêm `'bach'` vào `RecapEnsemble`.
  - Cập nhật `ENSEMBLE_ROWS.guitar` với `Bach` đứng trước `Sor`:
    `[ { id: 'bach', label: 'Bach' }, { id: 'classic', label: 'Sor' }, { id: 'barrios', label: 'Barrios' }, { id: 'villa', label: 'Lobos' }, { id: 'brouwer', label: 'Brouwer' } ]`.
- **Backend (`model.py`, `ensemble.py`, `schemas.py`, `guitar.py`)**:
  - Thêm `"bach"` vào `Ensemble` và `ENSEMBLES`, `_ROWS[("guitar", "bach")] = (_NYLON,)`, `_ALLOWED["guitar"]`.
  - Tempo `1D` của Bach: `GUITAR_BPM["bach"] = 96` (*Allegro moderato* chuẩn Baroque).

---

## 2. Bộ Hòa Âm Baroque Của J.S. Bach (`BachDialect` trong `backend/app/sonify/harmony.py`)
1. **Danh mục hợp âm Baroque (`allowed` & `extra`)**:
   - **Cấm tuyệt đối**: Các hợp âm treo hiện đại (`sus2`, `sus4`, `add9`, `madd9`, `7sus4`), các hợp âm `maj7` kiểu Lounge Jazz ở giọng thứ (`Ebmaj7`, `Abmaj7`), và `Cmaj7`/`Em7` trên phách mở/pedal.
   - **Giọng Trưởng (`mode == "major"`)**:
     - Hợp âm thuận thang & chuỗi quãng 5 Baroque: `C (I)`, `Dm (ii)`, `Dm7 (ii7)`, `Em (iii)`, `F (IV)`, `Fmaj7 (IVmaj7` trong chuỗi quãng 5), `G (V)`, `G7 (V7)`, `Am (vi)`, `Am7 (vi7)`, `Bm7b5 (vii°7)`.
     - Hợp âm Át phụ & Giảm bảy dẫn hướng (`BORROWED`): `D7 (V7/V)`, `E7 (V7/vi)`, `A7 (V7/ii)`, `C7 (V7/IV)`, `F#dim7 (vii°7/V)`.
   - **Giọng Thứ (`mode == "minor"`)**:
     - Hợp âm nền tảng Baroque Minor: `Cm (i)`, `Dm7b5 (ii°7)`, `Eb (III)`, `Fm (iv)`, `Fm7 (iv7)`, `G (V)`, `G7 (V7)`, `Ab (VI)`, `F#dim7 (vii°7)`.
     - Hợp âm mở rộng (`extra("minor")`): `Bb (VII)`, `Bb7 (V7/III -> Eb)`, `D7 (V7/V -> G/G7)`.
2. **Ma trận chuyển tiếp Vòng Quãng 5 Liên Hoàn (`transition`)**:
   - **Giọng Trưởng**: Ưu tiên cao (`0.42 – 0.62`) cho vòng quãng 5 `C -> F/Fmaj7 -> Bm7b5 -> Em -> Am/Am7 -> Dm/Dm7 -> G/G7 -> C` và chuỗi Át phụ `E7 -> Am/A7 -> Dm/D7 -> G/G7 -> C`.
   - **Giọng Thứ**: Ưu tiên cao cho vòng quãng 5 thứ `Cm -> Fm/Fm7 -> Bb/Bb7 -> Eb -> Ab -> Dm7b5/F#dim7 -> G/G7 -> Cm` và tiến trình *Chaconne* `Cm -> G/G7 -> Ab -> Fm -> Dm7b5/F#dim7 -> G7 -> Cm`.

---

## 3. Bộ 5 Pattern Vũ Điệu / Phức Điệu Cốt Lõi & Engine *Chaconne* (`backend/app/sonify/guitar_patterns.py`)

1. **`bach_fuga` — Phức Điệu Đối Âm 2–3 Bè (*Lag 2 Bars + Tonal Adaptation 1:1*)**:
   - **Bè Cao (`Voice 1` — Soprano)**: Hát trực tiếp dữ liệu Price Action hiện tại tại ô `bar`.
   - **Bè Trầm (`Voice 3` — Bass Subject/Answer)**:
     - Đọc lại hình thái tiết tấu (1:1, không kéo giãn x2/x4, không đảo ngược Retrograde) và hướng đi từng bước (`Δstep`) của bè Cao ở **`bar - 2`** (hoặc `bar - 1` ở ô thứ 2 của thân bài).
     - Thực hiện **Tonal Adaptation & Consonant Retargeting**: Khóa các nốt phách mạnh về âm hợp âm (`Root`, `3rd`, `5th`) của hợp âm hiện tại (`chord_at[bar]`) trong dải Trầm (`40..53`), và đi các nốt phách yếu liền bậc theo thang âm hiện tại đúng hướng đi của Motif quá khứ.
   - **Bè Trung (`Voice 2`)**: Điểm thưa ở phách mạnh hoặc lúc bè Cao ngân dài để giữ sự phân tách tần số rõ ràng giữa Soprano và Bass.
2. **`bach_bourree` — Vũ Điệu Nhịp Đôi & Walking Bass Lấy Đà (*Bourrée in E minor BWV 996*)**:
   - Đối vị 2 bè *Basso Continuo* sắc nét: Khi bè Cao đi móc đơn, bè Trầm đi nốt đen chắc chắn; khi bè Cao ngân nốt đen, bè Trầm chạy 2 nốt móc đơn bước liền bậc làm nhịp lấy đà (*Anacrusis*) đẩy vào phách mạnh tiếp theo; bè Trung điểm nhẹ quãng 3/6 thuận thang.
3. **`bach_gavotte` — Vũ Điệu Cung Đình Khúc Chiết (*Gavotte en Rondeau BWV 1006a*)**:
   - Nhịp đôi thanh lịch bắt đầu bằng **nhịp lấy đà 2 phách giữa ô (phách 3 & 4 dẫn về phách 1)**, bè Trung đi song thanh quãng 3/6 ở nửa sau ô nhịp, bè Bass đánh gốc và quãng 5 gọn gàng.
4. **`bach_sarabande` — Vũ Điệu Trang Trọng Nhấn Phách 2 & Câu Lướt *Chaconne* (*Sarabande BWV 995 / BWV 1004*)**:
   - Nhịp `3/4` (hoặc chương chậm), nhấn trọng âm ở **Phách 2** bằng hợp âm rải mềm (*Arpeggiato*) + nốt hoa mỹ, và ở **Phách 3 cuối ô nhịp** vuốt một câu **Passing Scale 2–4 nốt** nối mượt sang phách 1 của ô sau.
5. **`bach_gigue` — Vũ Điệu Bùng Nổ Nhịp `6/8` (*Gigue BWV 996 / BWV 997*)**:
   - Nhịp `6/8` nhanh: Arpeggio gãy (*Broken Arpeggiation*) cuộn xoáy qua các dây theo nhóm 3 móc đơn / 6 móc kép, kết hợp câu chạy Scale lao vào phách mạnh.
6. **`bach_chaconne` — Arpeggio Bariolage & Scale Engine (*Chaconne in D minor BWV 1004*)**:
   - Vừa là pattern độc lập cho các phiên/chương bán tháo hoặc biến động lớn (`selloff`), với nốt Bass đi tiến trình *Chaconne* bước xuống và bè Trung + Cao đan xen móc kép *Bariolage* liên hoàn qua các dây; vừa cung cấp lớp phủ Scale móc kép Baroque ở các điểm bứt phá (`Breakout`).

---

## 4. Bộ Intro & Outro 2 Ô / 4 Ô Của J.S. Bach (`backend/app/sonify/guitar_frame.py`)
- **Nhóm 1: Vũ điệu Nhanh / Lấy Đà (`rally`, `calm` — Bourrée, Gavotte, Gigue)**:
  - *Intro 2 ô*: Ô 1 Bass dậm Chủ (`I`) + 3 nốt móc đơn lấy đà cuối ô; Ô 2 hợp âm `V7` + câu lấy đà vào thẳng thân bài.
  - *Intro 4 ô*: Ô 1 hợp âm `I` gọn (`staccato`); Ô 2 Bass bước xuống liền bậc (`Do -> Ti -> La -> Sol`); Ô 3 hợp âm `V7` kèm nốt hoa mỹ (*Mordent*); Ô 4 câu lấy đà 3 nốt vào thân bài.
  - *Outro 2 ô*: Ô 1 nén hòa âm `ii/IV -> V7`; Ô 2 khóa hợp âm Chủ (`I`) dứt khoát.
  - *Outro 4 ô*: Ô 1 Bass bước xuống; Ô 2 `V7` + câu Arpeggio đi lên; Ô 3 nốt hoa mỹ trên `V7`; Ô 4 hợp âm Chủ (`I`) dứt khoát.
- **Nhóm 2: Phức điệu / Trang trọng (`volatile`, `selloff` — Fuga, Sarabande, Chaconne)**:
  - *Intro 2 ô*: Ô 1 Bass Pedal trầm ngân dài + hợp âm cổ điển; Ô 2 qua `V7` kèm hoa mỹ dẫn vào thân bài.
  - *Intro 4 ô (Polyphonic Subject Prelude)*: Ô 1 Bè Cao xướng *Subject* 4 nốt đơn âm; Ô 2 Bè Trầm vào *Answer* đáp lại ở bậc 5 dưới; Ô 3 hai bè giao thoa nén về `V7`; Ô 4 giải về `I`.
  - *Outro 2 ô (Tierce de Picardie)*: Ô 1 Bass trầm + câu nhạc chậm lại; Ô 2 giải về **Hợp âm Trưởng chủ (*Picardy Third*)** ngân rộng.
  - *Outro 4 ô (Pedal Point & Arpeggiato Coda)*: Ô 1–2 Bass giữ *Tonic Pedal Point* khi bè trên dịch chuyển `V7 -> I`; Ô 3 rải chậm *Arpeggiato* qua các dây; Ô 4 hợp âm Trưởng *Picardy Third* ngân tan dần.
