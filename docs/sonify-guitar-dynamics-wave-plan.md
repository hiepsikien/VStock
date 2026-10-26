# Kế Hoạch Thiết Kế Filter Uốn Sóng Động Lực Học (Wave) & Mở Rộng Biên Độ ($ppp \to ff$) Cho 5 Đại Sư Guitar

> **Mục tiêu**: Đưa tiếng đàn guitar cổ điển thoát khỏi dải hẹp $mp - mf$ (`44..78`) hiện tại, mở rộng chiều sâu về phía **thì thầm / gần gũi ($ppp - pp$, velocity `22..38`)** và mở trần có kiểm soát lên **$f - ff$ (`76..90`)** thông qua một **Dynamic Wave & Amplitude Expander Filter** tùy biến theo từng bản nhạc (`rel_span`, `character`, `band_at`) và phong cách của cả **5 Đại Sư (`Bach | Sor | Barrios | Lobos | Brouwer`)**.
>
> **Liên kết**: [`docs/sonify-classical-guitar.md`](./sonify-classical-guitar.md), [`docs/sonify-barrios-tremolo-dynamics.md`](./sonify-barrios-tremolo-dynamics.md), [`docs/sonify-humanize-preset-plan.md`](./sonify-humanize-preset-plan.md).

---

## 1. Chẩn Đoán Hiện Trạng: Vì Sao Guitar Đang Kẹt Ở Quãng $mp - mf$?

Qua khảo sát toàn bộ pipeline guitar (`guitar.py`, `guitar_patterns.py`, `guitar_barrios.py`, `guitar_villa.py`, `guitar_frame.py`, `humanize.py`), lực gảy hiện tại đang bị nén trong một dải rất hẹp do **4 nguyên nhân kỹ thuật**:

| Điểm nghẽn trong Code | Vị trí hiện tại | Hệ quả âm thanh |
|---|---|---|
| **1. Nền giai điệu & đệm đặt sẵn ở $mp - mf$** | • `_MELODY = 64`, `_MELODY_APEX = 72`<br>• `_SWELL_OPEN = 60`, `_SWELL_CLOSE = 62`<br>• `_BAND_SUPPORT = 50..60`, `_BAND_BASS = 54..64` | Ngay từ lúc sinh nốt, giai điệu chỉ dao động `60..72` và bè đệm chỉ dao động `46..64`. Không có nốt nào được viết ở $ppp$ (`~22`) hay $pp$ (`~34`). |
| **2. Chốt chặn cứng `[44, 78]` và bỏ qua nốt đỉnh trong `_shape_dynamics`** | `guitar_patterns.py` dòng 2906–2931:<br>• `if event.velocity >= _MELODY_APEX: continue`<br>• `velocity = max(44, min(78, ...))`<br>• *La Catedral* khóa `lead` ở `54..64`, `support` ở `48..55` | • Sàn `44` chặn đứng toàn bộ dải $ppp - pp$ (`22..42`).<br>• Nốt đỉnh `72` bị bỏ qua không được cộng `delta` khi vào vùng `band == "f"`.<br>• `etude1` và `etude11` bị loại trừ hoàn toàn khỏi `_shape_dynamics`. |
| **3. Thiếu sóng thở vĩ mô (Macro Wave)** | • `swell(phrase, onset)` là tam giác tuyến tính trong 1 câu ngắn (2–4 ô), chỉ cộng `round(4 * swell)` ($\pm 4$ velocity).<br>• Chỉ `tremolo` mới có `_tremolo_region_arch` ($\sin(\pi t)$, biên $+6$). | Các đoạn dài 30 ô (`1D`) hay 80–200 ô (`1W`, `1M`, `3M`, `1Y`) đi ngang một mức năng lượng phẳng lì từ đầu chí cuối, không có sóng cuộn (wave) qua các đoạn. |
| **4. Nỗi sợ tầng sample móng gắt (`65+`) trên MS Basic** | Ghi chú tại `audio.py:780` và `guitar_barrios.py:880`: MS Basic chuyển sang tiếng móng sáng từ `velocity >= 65`. | Để tránh tiếng móng gắt kêu liên tục, code hiện tại chọn giải pháp ép trần xuống `63–72`, nhưng lại **quên mở sàn xuống `22–38`**, làm mất khoảng tương phản động lực học tự nhiên của đàn nylon. |

### Nguyên lý âm học trên MS Basic Nylon (`MuseScore_General.sf3`)

Trên MS Basic, `NoteEvent.velocity` được xuất ra MusicXML thành `<note dynamics="V * 100 / 90">`:
- **Vùng $ppp - pp$ (`velocity 20..38`, tương đương `22%..42%` forte)**: Dây nylon kêu cực kỳ mềm, tròn, ấm (giống ngón thịt vuốt ở *sul tasto* / *dolcissimo*). Đây chính là vùng tạo ra **sự gần gũi (intimacy)** đặc trưng của guitar.
- **Vùng $p - mp$ (`velocity 40..63`, tương đương `44%..70%` forte)**: Tiếng gảy tự nhiên, rõ nét nhưng chưa gắt móng — vùng làm việc chủ đạo của giai điệu tự sự.
- **Vùng $mf - ff$ (`velocity 65..90`, tương đương `72%..100%` forte)**: Tầng sample có tiếng móng rõ và sắc (*punta / metallico*). Nếu cả bài đánh ở vùng này sẽ bị đanh và mệt tai; nhưng nếu **chỉ xuất hiện ở đỉnh sóng (crest of the wave), nốt nhấn syncopation, Bartók pizzicato hoặc đỉnh cao trào**, nó lại tạo ra độ bùng nổ rất thật của đàn guitar.

---

## 2. Kiến Trúc Tổng Thể Của Filter (`guitar_wave.py` / Post-compose Filter)

### 2.1. Vị trí đặt Filter trong Pipeline

Để không phá vỡ các unit test cấp pattern hiện có (nhiều test trong `test_sonify_guitar.py` gọi trực tiếp các hàm nội bộ hoặc `render(..., framed=False)` và kiểm tra các con số `56`, `60`, `64`, `72`), hay nhất là đặt Filter làm **bước hoàn thiện động lực học của Guitar**:

```text
render_patterned_voices()
  ├── 1. Sinh nốt theo Pattern & Frame (giữ nguyên tỉ lệ nội bộ giữa các ngón p-i-m-a)
  ├── 2. _repair() & _resolve() & _slur()
  ├── 3. _shape_dynamics()  <-- Nâng cấp thành / gọi qua Guitar Wave & Expander Filter
  └── 4. humanize(score)    <-- Giữ nguyên ở audio.py: nhích ±2 trên các plateau còn lại
```

> **Lưu ý kiến trúc**:
> - Có thể tách thành module riêng `backend/app/sonify/guitar_dynamics.py` (hoặc `guitar_wave.py`) được gọi ở cuối `render_patterned_voices` khi `_framed(ctx) == True` (mọi bản nhạc thực tế `1D`, `1W`, `1M`, `3M`, `1Y`), hoặc mở cờ tham số `wave: bool = True`.
> - Trong `humanize.py`: Hiện tại `_movable()` đóng băng mọi plateau nếu nốt kề lệch `<= 2`. Khi có Wave Filter uốn mượt từng ô/phách, các chuỗi nốt dài đã tự có độ nghiêng tự nhiên; những chỗ còn giữ plateau (như các nốt cùng phách hoặc câu phẳng) vẫn được `humanize` nhích nhẹ.

---

### 2.2. Mô Hình Toán Học 3 Tầng Của Filter

Với mỗi nốt tại vị trí thời gian $t$ (tính bằng móc đơn `eighth` hoặc phách `beat`), Filter tính toán lực gảy qua **3 bước**:

#### Bước 1: Tính Biên Độ Đích Của Bản Nhạc $[V_{\text{floor}}, V_{\text{ceil}}]$ (Piece-level Adaptive Span)

Biên độ tổng thể của bản nhạc không cố định mà co giãn theo **biên độ giá tương đối `rel_span = (high - low) / low`**, **tính cách phiên `character`** (`calm`, `rally`, `selloff`, `volatile`) và **Hồ sơ Tác gia (`ComposerDynamicProfile`)**:

1. **Hệ số mở biên theo biến động dữ liệu $\alpha \in [0.0, 1.0]$**:
   $$\alpha = \text{clamp}\left(\frac{\text{rel\_span} - 0.004}{0.028 - 0.004},\; 0.0,\; 1.0\right)$$
   - Khi phiên đi ngang hẹp ($\text{rel\_span} \le 0.4\%$ hoặc `character == "calm"`): $\alpha$ nhỏ ($\approx 0.0 - 0.25$). Bản nhạc nghiêng về **Intimate / Whisper mode**: sàn hạ sâu xuống $ppp - pp$, trần giữ ấm dưới ngưỡng móng gắt ($mp - mf$).
   - Khi phiên biến động lớn ($\text{rel\_span} \ge 2.8\%$ hoặc `volatile` / `rally` mạnh): $\alpha \to 1.0$. Bản nhạc mở **Full Concert Span**: sàn vẫn lùi về $pp$ ở những vùng lặng, còn đỉnh sóng vươn tới $f - ff$.

2. **Cửa sổ biên độ $[V_{\text{floor}}, V_{\text{ceil}}]$ của Bè Hát Chính (Lead / Singing Thumb)**:
   $$\begin{aligned}
   V_{\text{floor}} &= \text{round}\big(P.\text{floor\_calm} - \alpha \cdot (P.\text{floor\_calm} - P.\text{floor\_wide})\big) \\
   V_{\text{ceil}}  &= \text{round}\big(P.\text{ceil\_calm}  + \alpha \cdot (P.\text{ceil\_wide}  - P.\text{ceil\_calm})\big)
   \end{aligned}$$
   *(Trong đó $P$ là profile của từng tác gia & pattern ở Mục 3).*

---

#### Bước 2: Tổng Hợp Sóng Đa Tầng $W(t) \in [0.0, 1.0]$ (Multi-scale Wave)

Thay vì một đường thẳng hay bậc thang đứt đoạn theo từng ô nhịp, năng lượng tại thời điểm $t$ là sự giao thoa của **3 con sóng mượt**:

$$W(t) = \text{clamp}\Big(w_{\text{macro}} \cdot W_{\text{macro}}(t) \;+\; w_{\text{phrase}} \cdot W_{\text{phrase}}(t) \;+\; w_{\text{band}} \cdot W_{\text{band}}(t),\; 0.0,\; 1.0\Big)$$

Trong đó (với trọng số mặc định $w_{\text{macro}} = 0.45,\; w_{\text{phrase}} = 0.35,\; w_{\text{band}} = 0.20$):

1. **Sóng Vĩ Mô $W_{\text{macro}}(t) \in [0, 1]$ (Section / Movement Breathing Wave)**:
   - Mỗi section (hoặc toàn bộ thân bài 30 ô của `1D`) có một đường bao vĩ mô đi từ `0.0` ở đầu đoạn, uốn qua các đỉnh/đáy của đường giá vĩ mô (smoothed price envelope qua cửa sổ trượt 3–4 ô nhịp kết hợp hình vòm $\sin(\pi \cdot \tau)$), rồi lắng dần về `0.0` ở cuối đoạn:
     $$W_{\text{macro}}(t) = 0.65 \cdot \sin(\pi \cdot \tau_{\text{section}}) + 0.35 \cdot \widetilde{\text{PriceNorm}}(t)$$
   - Ở đoạn giữa (`section.trio` hoặc `section.bridge`), nếu là pattern nội tâm (`cantabile`, `thumb_cantabile`, `noviembre`, `andante`), $W_{\text{macro}}(t)$ được nhân hệ số dịu xuống `0.65` để cả đoạn giữa lùi sâu vào không gian $pp$ trước khi phần tái hiện (Recapitulation A') mở rộng trở lại.
   - Ở vùng khung **Intro (`warmup`/`intro`)** và **Outro (`cooldown`/`outro`)**:
     - **Intro**: Uốn đường cong khởi âm (emergence curve) từ $ppp/pp$ (`W = 0.08`) nở dần vào khớp với mức đầu thân bài.
     - **Outro**: Uốn đường cong tan dần (*morendo* / *al niente*) từ mức cuối thân bài lịm dần xuống $ppp$ (`W = 0.0 -> V = 22..28`) ở hợp âm/harmonics cuối cùng.

2. **Sóng Câu Nhạc $W_{\text{phrase}}(t) \in [0, 1]$ (Raised-Cosine Phrase Wave)**:
   - Thay thế hàm tam giác tuyến tính gãy khúc hiện tại bằng **đường cong Raised-Cosine (Hann arch)** nối từ đầu câu `phrase.start` lên đỉnh `phrase.apex` rồi thu về cuối câu `phrase.end`:
     $$W_{\text{phrase}}(t) = \frac{1 - \cos(\pi \cdot s(t))}{2}$$
     *(với $s(t)$ là vị trí chuẩn hóa từ đầu câu tới đỉnh và từ đỉnh về cuối câu).*
   - Ngay cả khi câu nhạc có cao độ đi ngang (`phrase.rise < MIN_RISE` — trường hợp mà code hiện tại đang gán phẳng `swell = 0`), người chơi guitar thật **vẫn luôn thở theo câu**: câu phẳng vẫn nhận một nhịp thở nhẹ `0.35 * W_phrase(t)` để nốt mở câu và nốt khép câu lắng xuống tự nhiên.

3. **Sóng Thanh Khoản Làm Mượt $W_{\text{band}}(t) \in [0, 1]$ (Smoothed Liquidity Wave)**:
   - Hiện tại `_BAND_DELTA` nhảy bậc thang đột ngột tại vạch nhịp khi đổi cửa sổ thanh khoản (`p: -12`, `mp: -6`, `mf: 0`, `f: +4`).
   - Thay bằng nội suy mượt (cosine interpolation bán kính 1–2 ô nhịp quanh ranh giới cửa sổ thanh khoản) trên thang `{"p": 0.0, "mp": 0.33, "mf": 0.67, "f": 1.0}`.

---

#### Bước 3: Ánh Xạ Phi Tuyến (S-Curve / Gamma) & Bảo Toàn Phân Tầng 3 Bè

1. **Hệ số uốn Gamma ($\gamma$) tạo không gian Intimate**:
   $$E(t) = \big(W(t)\big)^{\gamma}$$
   - Khi $\gamma > 1.0$ (ví dụ $\gamma = 1.25 - 1.40$ cho các bài trữ tình): Đường cong võng xuống, giữ phần lớn thời gian của bản nhạc nằm ở vùng ấm áp $pp - mp$ (`30..58`), và chỉ khi cả 3 sóng (Macro + Phrase Apex + Band `f`) cùng hội tụ ($W(t) \to 1.0$), lực gảy mới vọt lên vùng móng sắc $f - ff$ (`76..88`).
   - Khi $\gamma < 1.0$ (ví dụ $\gamma = 0.85$ cho các điệu nhảy dồn dập hoặc *Galop*): Đường cong đầy đặn, giàu năng lượng hơn.

2. **Bảo toàn cấu trúc vi mô của ngón đàn (Micro-pattern Offset Preservation)**:
   - Nhiều pattern của guitar đã có cấu trúc lực vi mô rất tinh tế giữa các ngón trong cùng một phách/ô (ví dụ: cụm tremolo `p` mạnh hơn `m > i > a`; vòm 16 móc kép của `etude1`; vòm sextuplet nghiêng của `etude11`; sóng chữ V của `catedral preludio`).
   - Filter **không ghi đè phẳng** lên các nốt đó, mà tách mỗi nốt thành:
     $$V_{\text{written}} = V_{\text{ref}}(\text{voice}, \text{bar}) + \Delta_{\text{micro}}$$
   - Filter uốn đường chuẩn $V_{\text{ref}}$ theo sóng $E(t)$, đồng thời **co giãn nhẹ $\Delta_{\text{micro}}$** (scale factor `0.75..1.15` tùy theo độ mở của sóng) để ở vùng $pp$ các ngón rải nghe mượt như lụa, còn ở vùng $f$ độ nhấn phách sắc nét hơn.

3. **Bất biến Phân tầng 3 Bè (Three-Voice Balance Invariant)**:
   Tại mọi thời điểm $t$, sau khi uốn sóng:
   - **Với mọi pattern thông thường** (Bè `lead` hát giai điệu):
     $$\begin{aligned}
     V_{\text{lead}}(t)    &= V_{\text{floor}} + \big(V_{\text{ceil}} - V_{\text{floor}}\big) \cdot E(t) + \Delta_{\text{micro, lead}} \\
     V_{\text{bass}}(t)    &= \min\Big(V_{\text{lead}}(t) - \text{gap}_{\text{bass}},\; V_{\text{bass\_floor}} + \big(V_{\text{bass\_ceil}} - V_{\text{bass\_floor}}\big) \cdot E(t)^{\gamma_{\text{bass}}}\Big) \\
     V_{\text{support}}(t) &= \min\Big(V_{\text{bass}}(t) - \text{gap}_{\text{sup}},\; V_{\text{sup\_floor}} + \big(V_{\text{sup\_ceil}} - V_{\text{sup\_floor}}\big) \cdot E(t)^{\gamma_{\text{sup}}}\Big)
     \end{aligned}$$
     - Bè Trung (`support` — arpeggio/rải dây) luôn có trần thấp hơn và hệ số $\gamma_{\text{sup}} \ge 1.35$, giúp **bè rải lùi sâu xuống $ppp - pp$ (`22..34`) khi lắng và chỉ lên tối đa `56..62` khi cao trào** (không bao giờ vượt ngưỡng `65` gây đanh tiếng của MS Basic, trừ các cú chập staccato/pizzicato cố ý).
   - **Với pattern đảo bè `thumb_cantabile`** (*Prélude No. 1* / *Julia Florida*):
     - Ngón cái `low` (voice 3) nhận đường cong của **Bè Hát Chính** $[V_{\text{floor}}, V_{\text{ceil}}]$, trong khi hai bè chập phía trên (`lead` và `support`) nhận đường cong **Bè Đệm Thì Thầm** (`24..50`), giữ đúng khoảng cách `low >= max(lead, support) + 6`.

---

## 3. Thiết Kế Chi Tiết Cho Từng Đại Sư Trong 5 Tác Gia

Mỗi tác gia có một thẩm mỹ âm thanh, kỹ thuật tay phải (*toque*) và biên độ động lực học hoàn toàn khác nhau:

### Tổng Quan Bảng Biên Độ 5 Đại Sư (MIDI Velocity trên thang `1..127`, với `ppp ≈ 20`, `pp ≈ 32`, `p ≈ 46`, `mp ≈ 60`, `mf ≈ 72`, `f ≈ 82`, `ff ≈ 90`)

| Đại sư (`ensemble`) | Triết lý Động lực học & Màu âm | Bè Hát Chính<br>*(Phiên êm `calm` $\to$ Phiên sóng lớn)* | Bè Trầm (`low`) | Bè Trung Rải (`support`) | Độ uốn $\gamma$ & Đặc trưng Wave |
|---|---|---|---|---|---|
| **1. J.S. Bach (`bach`)** | **Kiến trúc đa âm & Bậc thang thở (Polyphonic Architecture)** — Rõ từng bè đối vị, cao trào xây theo tầng (chaconne/fugue), tránh sướt mướt nhưng có những đoạn nội tâm rất sâu ở Sarabande. | • Êm: `34 .. 64` ($pp \to mp+$)<br>• Sóng lớn: `30 .. 82` ($pp \to f$) | `28 .. 72`<br>*(Ở `bach_fuga`, khi Bass đang giữ Subject thì được nâng ngang tầm Soprano `- 2`)* | `24 .. 58` | $\gamma = 1.10$<br>Sóng vĩ mô rõ theo cấu trúc câu và chuỗi quãng 5; giữ độ rõ nét của bè Bass đối vị. |
| **2. Fernando Sor (`classic`)** | **Cổ điển Châu Âu thanh lịch (Classical Chiaroscuro)** — Cân đối kiểu Mozart/Haydn, đối đáp sáng–tối (*forte / piano echo*), sắc thái từ tiếng thì thầm của *Cantabile / Élégiaque* đến rộn rã của *Galop / Grand Solo*. | • Êm: `30 .. 62` ($pp \to mp$)<br>• Sóng lớn: `28 .. 80` ($pp \to f$) | `26 .. 68` | `22 .. 56` | $\gamma = 1.15$<br>Nhấn rõ tương phản câu hỏi – câu trả lời và hiệu ứng *subito piano* sau fanfare. |
| **3. Agustín Barrios (`barrios`)** | **Lãng mạn Thánh đường & Kịch tính Nam Mỹ (Romantic Cathedral)** — Biên độ rộng nhất: từ tiếng chuông/rải *ppp* mỏng như sương khói đến đỉnh *Ultimo Tremolo* và *Choro / Danza* bùng nổ *ff*. | • Êm: `26 .. 63` ($ppp+ \to mp$)<br>• Sóng lớn: `24 .. 86` ($ppp \to ff-$) | `24 .. 74` | `20 .. 58` | $\gamma = 1.30$<br>Độ võng sâu tạo *intimacy* tối đa; sóng tremolo và preludio cuộn dài nhiều ô nhịp. |
| **4. Heitor Villa-Lobos (`villa`)** | **Hiện đại Brazil nồng nhiệt (Brazilian Modernist Surge)** — Tiếng ngón cái (`p`) dày như Cello, sóng arpeggio cuộn trào từ rì rào ($pp$) lên cao trào dồn dập ($ff$). | • Êm: `30 .. 64` ($pp \to mp+$)<br>• Sóng lớn: `28 .. 86` ($pp \to ff-$) | `28 .. 76`<br>*(Trong `thumb_cantabile`: `32 .. 82`)* | `22 .. 60` | $\gamma = 1.15$<br>Mở khóa `_shape_dynamics` cho cả `etude1` và `etude11` bằng cách dịch cả vòm theo sóng. |
| **5. Leo Brouwer (`brouwer`)** | **Tương phản Cực đại Thế kỷ 20 (Cinematic & Avant-Garde)** — Đối lập gay gắt nhất giữa lời thì thầm điện ảnh (*Un Día de Noviembre*, $ppp$) và những cú vỗ nhịp Cuba / *Bartók pizzicato* (*Elogio de la Danza*, $ff$). | • Êm: `22 .. 58` ($ppp \to mp-$)<br>• Sóng lớn: `20 .. 90` ($ppp \to ff$) | `20 .. 78` | `18 .. 60`<br>*(Riêng cú slap/stab: tới `84`)* | $\gamma = 1.40$ (trữ tình) / $0.90$ (percussive)<br>Biên độ cực đại từ `18` ($ppp$) tới `90` ($ff$). |

---

### 3.1. J.S. Bach (`bach`) — Đối Vị Đa Âm & Sóng Kiến Trúc

Hiện tại các pattern của Bach (`bach_fuga`, `bach_bourree`, `bach_gavotte`, `bach_sarabande`, `bach_gigue`, `bach_chaconne`) viết giai điệu ở `64/72`, bass ở `56`, inner ở `46`.
Khi qua Wave Filter:
- **`bach_sarabande`** (Nhịp 3/4 chậm hoặc `selloff` nhẹ):
  - Mở đầu và phách 1 lắng ở $pp$ (`32..42`), **phách 2** (trọng âm Sarabande cùng nốt hoa mỹ *mordent*) nở ấm lên (`48..68` tùy vị trí trên Macro Wave), và câu lướt phách 3 vuốt nhẹ giảm dần hoặc dẫn đà sang ô kế tiếp.
- **`bach_fuga`** (Phức điệu 2–3 bè):
  - Đặc thù của Fugue là **bè Trầm (`low`) đóng vai Subject/Answer ngang hàng với Soprano (`lead`)**. Do đó, riêng ở `bach_fuga`, khoảng cách `gap_bass` được thu hẹp chỉ còn `2` đơn vị (thay vì `6–8`), để câu trả lời của bè Trầm ở `bar - 2` nổi rõ trong vùng `36..72`, trong khi bè Trung (`support`) lùi hẳn về `24..50`.
- **`bach_chaconne`** (*Chaconne in D minor*):
  - Sóng vĩ mô $W_{\text{macro}}(t)$ xây dựng theo từng chu kỳ biến tấu 4 ô nhịp: các ô đầu chu kỳ bariolage có thể lùi sâu về $pp$ (`lead 34`, `support 24..28`, `bass 30` — tạo tiếng rải bariolage mờ ảo), sau đó dâng dần lên $f$ (`lead 78..82`) ở câu chạy scale bứt phá cuối chu kỳ.
- **`bach_bourree`, `bach_gavotte`, `bach_gigue`**:
  - Giữ độ nảy nhịp điệu Baroque: các nốt lấy đà (*anacrusis* 2 móc đơn của Bourrée, 2 phách giữa ô của Gavotte) bước từ nhẹ lên mạnh ($\text{crescendo}$ ngắn $+6..+8$ velocity vào phách 1 của ô sau).

---

### 3.2. Fernando Sor (`classic`) — Tinh Tế Cổ Điển & Hiệu Ứng Sáng–Tối (*Chiaroscuro*)

- **`cantabile`** (*Op. 6 No. 10* — Song thanh quãng 3 / quãng 6 khi `calm`):
  - Đây là pattern *intimate* nhất của Sor. Cả bài được kéo về vùng $ppp - mp$: bè Cao hát ở `28..58`, bè Trung đi bóng quãng 3/6 ngay sát dưới ở `22..50` (luôn mềm hơn bè Cao `6–8` đơn vị để nghe như hai ngón `m-i` vuốt nhẹ trên dây), và nốt Bass điểm rất khẽ ở `24..48`.
- **`elegiaque`** (*Fantaisie élégiaque* — Hành khúc tang chấm dôi):
  - Những đoạn mở và kết câu đóng ở giọng Thứ chìm xuống $pp$ (`lead 30..44`, `bass 26..38`, `support 22..32`). Khi câu leo lên đỉnh bi tráng, sóng mở lên `lead 72..78`, tiếng bass chấm dôi trầm hùng ở `62..66`. Nốt tựa *appoggiatura* ở phách mạnh được nhấn nhói lên (`+6` so với nốt giải sau nó) rồi dịu xuống ngay ở móc đơn giải.
- **`study` & `Grand Solo`** (`level 0 -> 1 -> 2`):
  - Gắn trực tiếp bậc figuration `level` của Grand Solo vào biên độ sóng:
    - `level 0` (câu mở đầu): Trong trẻo ở $pp - mp$ (`32..60`).
    - `level 1` (lần lặp biến tấu): Mở lên $p - mf$ (`40..70`).
    - `level 2` (đỉnh tái hiện + scale + fanfare): Mở tới $mf - f$ (`48..80`). Ngay sau khe thở kịch tính `caesura`, câu đỉnh vươn lên cực đại.
- **`mozart_var` & `galop`**:
  - Trong `mozart_var`, bè đối vị liền bậc ở `support` uốn lượn theo đúng chiều lên/xuống của bước đi (`+1` mỗi bước đi lên, `-1` mỗi bước đi xuống trong khoảng `26..54`). Trong `galop`, các nốt nhảy quãng 3 *sparkle* staccato ở móc đơn thứ 2 nhẹ và nảy hơn nốt gốc phách mạnh (`-6` velocity) như tiếng chuông nhỏ.

---

### 3.3. Agustín Barrios (`barrios`) — Chiều Sâu Thánh Đường & Sóng Tremolo Rộng

Barrios là tác gia hưởng lợi nhiều nhất từ việc mở dải $ppp \to ff$:

1. **`preludio` (*La Catedral — Preludio Saudade*)**:
   - **Gỡ bỏ cái kẹp cứng `54..64` (lead) và `48..55` (support)** hiện tại trong `guitar_barrios.py` và `_shape_dynamics`.
   - Thay bằng **Sóng Thánh Đường (Cathedral Wave)**:
     - **Bè Canto (`lead`)**: Mở bài và những đoạn lắng lùi về **$pp$ (`34..42`)**; khi câu nhạc dâng lên theo $W_{\text{macro}}(t)$ và $W_{\text{phrase}}(t)$, tiếng canto nở ấm áp qua $mp$ (`56..63`) và tại đỉnh cao trào lớn nhất của bài được phép chạm **`68..74`** ($mf+$) để tiếng dây 1 ngân vang đúng chỉ dẫn *Ben marcato il canto*.
     - **Bè Trung sóng chữ V 6 móc kép (`support`)**: Luôn giữ vai trò "tiếng vọng dưới mái vòm", thấp hơn Canto ít nhất `10–14` đơn vị. Ở vùng $pp$, sóng chữ V rải ở **`22..30` ($ppp$)** (đáy chữ V ở móc kép thứ 3 chạm `20..22`); ở đỉnh sóng, sóng chữ V cũng chỉ lên tới **`46..54`** — tạo độ sâu không gian 3D tách bạch hoàn toàn khỏi tiếng Canto.
     - **Bè Trầm ngân 2 ô (`low`)**: Đi từ `28` ($pp$) đến `60` ($mp+$).

2. **`tremolo` (*Una Limosna por el Amor de Dios / El Último Tremolo*)**:
   - Hiện tại `_tremolo` đang bị kẹp ngón cái trong `44..72` với vòm vùng chỉ cộng tối đa `+6` và độ lệch theo band chỉ `-6..+3`.
   - **Mở rộng vòm Tremolo**:
     - Giữ nguyên cấu trúc ngón trong từng phách: ngón cái `L`, và 4 móc kép `p-a-m-i` lệch `(-6, -3, -4, -6)` (hoặc thu hẹp độ lệch thành `(-4, -2, -3, -4)` khi ở vùng $ppp$ để nốt `a` không bị câm dưới `18`).
     - Cho phép mức chuẩn `L` của ngón cái uốn theo $W_{\text{macro}}(t) + W_{\text{phrase}}(t)$ từ **`34` ($pp$, khi đó fill `a-m-i` thì thầm ở `28, 31, 30, 28`)** lên tới **`78` ($f+$, khi đó fill `a-m-i` ngân rực rỡ ở `72, 75, 74, 72`)** tại đỉnh cao trào của chương!
     - Giữ nguyên quy tắc an toàn: trong mỗi cụm 1 phách, ngón cái luôn lớn hơn ngón `m` của chính cụm đó ít nhất `3` đơn vị.

3. **`andante`, `thumb_cantabile` (*Julia Florida*) và Điệu nhảy (`choro`, `polca`, `hemiola`, `vals`)**:
   - Trong *Julia Florida* (`thumb_cantabile`), ngón cái hát ở `34..74`, còn hai nốt chập phách yếu phía trên lùi sâu xuống vùng `22..44` ($ppp - p$), xóa hẳn cảm giác hợp âm phụ gõ đều đều.
   - Trong `choro`, `polca`, `vals`: mở biên độ giữa các phách thường (`34..56`) và các cú nhấn syncopation (`62..82`), giúp điệu nhảy có độ lắc (groove) rất rõ.

---

### 3.4. Heitor Villa-Lobos (`villa`) — Sóng Cuộn Arpeggio & Mở Khóa Hai Bản Étude

Hiện tại `etude1` và `etude11` đang bị chặn không cho đi qua `_shape_dynamics` vì sợ làm hỏng bậc thang nội bộ của ô nhịp (`50, 52, 54` của `etude1` và vòm sextuplet của `etude11`).

Cách giải quyết triệt để trong Filter mới:
1. **`etude1` (*Étude No. 1*) — Dịch chuyển cả vòng 16 móc kép theo Sóng**:
   - Bảo toàn 100% bậc thang tương đối bên trong ô nhịp: hai nốt giai điệu (`index 7` và `9`) đứng cao nhất, bass đứng dưới giai điệu `4` đơn vị, và 13 nốt bè trung giữ đúng hình vòm `-2, 0, +2, 0, -2`.
   - Nhưng **tâm của cả ô nhịp** không còn đứng chết ở `52 / 60..72` suốt 30 ô nữa, mà lướt theo sóng $E(t)$:
     - Ở những ô đầu bài hoặc vùng tích lũy ($pp$): cả guồng máy 16 móc kép lùi xuống rì rào ở **`26..32` (support)**, **`38..44` (lead)**, **`34..40` (bass)**.
     - Khi sóng dâng lên đỉnh ($f$): cả guồng máy cuộn lên **`50..58` (support)**, **`74..84` (lead)**, **`68..74` (bass)**.
   - Hiệu ứng nghe được đúng như cách các nghệ sĩ guitar chơi *Étude No. 1* ngoài đời: cả chuỗi arpeggio to dần rồi nhỏ dần như sóng biển.

2. **`etude11` (*Étude No. 11 — Animé*)**:
   - Tương tự `etude1`, giữ nguyên độ nghiêng `_ETUDE11_TILT = {1: -1, 2: -1, 4: 0, 5: +1}` và khoảng cách giữa nốt giai điệu phách mạnh, nốt nhắc lại (`-8`) và 4 nốt trang trí ở giữa, nhưng cho phép `hairpin` gốc của mỗi phách uốn rộng từ **`40` ($p-$) đến `84` ($f+$)** theo sóng của bản nhạc (với sàn của 4 nốt sextuplet giữa mở xuống `26` thay vì khóa cứng ở `44`).

3. **`villa_pattern`, `chord_melody`, `thumb_cantabile`**:
   - Với `villa_pattern`, các nốt ngân chồng *campanella* ở bè Trung được vuốt nhẹ ở `24..54`, trong khi các ô có nhấn *tresillo* `3+3+2` ở vùng `volatile` bật rõ 3 đỉnh `{0, 3, 6}` lên `68..82`.

---

### 3.5. Leo Brouwer (`brouwer`) — Tương Phản Điện Ảnh & Nhịp Điệu Thế Kỷ 20

Brouwer cần sự phân cực mạnh nhất giữa **Tĩnh ($ppp$)** và **Động ($ff$)**:

1. **`noviembre` (*Un Día de Noviembre*)**:
   - Thiết kế riêng đường cong **Intimate Ballad Curve** ($\gamma = 1.45$):
   - Mở câu và kết câu ở **`22..32` ($ppp - pp$)**, bè Trung rải màu `add9 / maj7` mỏng nhẹ ở **`18..38`**, nốt Bass pickup cuối ô bước rất khẽ (`22..34`). Ngay cả ở đỉnh câu trong phiên `calm`, giai điệu cũng chỉ nở ấm áp tới `56..62` ($mp$), giữ trọn vẹn chất điện ảnh trầm mặc.
2. **`sarabande` (*El Decamerón Negro / Sarabanda*)**:
   - Tương phản ngay trong từng ô nhịp: phách 1 vào thật khẽ (`26..38`, $pp$), **phách 2** (hợp âm màu sus2/add9) dậm sâu và ngân vang (`56..78`), sau đó câu lướt *modal swarm* (8 móc đơn hoặc 16 móc kép) ở nửa sau ô nhịp **uốn một đường sóng động lực học liên tục** (tăng dần khi swarm đi lên, hoặc giảm dần về $ppp$ `24` khi swarm đi xuống).
3. **`brouwer_etude` (*Estudio Sencillo No. 6*) & `elogio_pizz` (*Elogio de la Danza*)**:
   - Ở các ô ostinato bình thường, dải động có thể nén xuống $pp - p$ (`28..48`) như tiếng gõ nhịp ngầm; nhưng tại các nhát cắt syncopation hoặc **cú vỗ *Bartók pizzicato* (móc đơn thứ 3 của `elogio_pizz`)**, filter cho phép xuyên qua trần thường để vọt lên **`80..90` ($ff$)**, tạo cú giật mình (dynamic shock) đúng phong cách đương đại của Brouwer.

---

## 4. Khung Intro & Outro (`guitar_frame.py`): Khởi Âm Từ $ppp$ Và Tan Vào Im Lặng (*Morendo*)

Hiện tại `guitar_frame.py` đang dùng 4 hằng số cố định `_PP = 46`, `_P = 50`, `_MP = 56`, `_MF = 64` và `_shape_dynamics` đang **bỏ qua toàn bộ các ô `pedal` (`intro`, `warmup`, `outro`, `cooldown`)**.

Khi áp dụng Wave Filter:
1. **Hạ chuẩn nền của `guitar_frame.py` hoặc cho phép Wave Envelope ôm trọn cả Intro và Outro**:
   - **Intro (`leading` pedal bars)**:
     - Ô 1 mở đầu từ vùng **$ppp - pp$ (`24..36`)** (ví dụ: tiếng chuông Harmonics đầu bài của Barrios hoặc nốt dây buông của Brouwer/Villa ngân lên từ `26–32` thay vì `44–50`).
     - Qua các ô tiếp theo của Intro, đường bao tăng dần (dẫn hướng vào `V7` hoặc câu scale lấy đà) để khớp mượt với velocity đầu thân bài (`~38..52`).
   - **Outro (`trailing` pedal bars)**:
     - Áp dụng hàm suy giảm mũ (**Exponential Morendo Curve**) từ mức cuối thân bài xuống **`20..26` ($ppp$)** ở ô cuối cùng.
     - Riêng trường hợp kết kịch tính của Brouwer (`_stab_and_ring` khi `volatile`/`selloff`) hoặc Villa (`bright` outro): giữ nguyên cú chập dứt khoát $mf - f$ (`68..78`) theo đúng ý đồ tác gia, không bị ép giảm về $ppp$.

---

## 5. Bảo Toàn Bất Biến Kỹ Thuật & Tương Thích Hệ Thống

Để đảm bảo việc mở rộng biên độ $ppp \to ff$ không gây lỗi phụ ở các tầng khác, Filter tuân thủ **5 quy tắc an toàn**:

1. **Không làm câm nốt hay méo MIDI**:
   - Sàn tuyệt đối sau mọi phép tính là `velocity >= 18` ($ppp$, tương đương `20%` trên `<note dynamics>`), trần tuyệt đối là `velocity <= 96` ($ff$).
2. **Bảo toàn 100% `assert_playable`**:
   - Filter chỉ biến đổi `NoteEvent.velocity` (và không chạm vào `midi`, `beat`, `duration_beats`, `voice`, `tie_start`, `tie_stop`), nên mọi quy tắc thế tay, dây đàn và `assert_playable` đều giữ nguyên 100%.
3. **Đồng bộ các nốt nối dây (`tie_start` / `tie_stop`)**:
   - Trên guitar (nhạc cụ gảy tắt dần, không thổi hơi thêm giữa nốt như sáo hay kéo vĩ như violin), một nốt nối qua vạch nhịp (`tie_stop=True`) phải **mang cùng `velocity` với cú gảy đầu tiên (`tie_start=True`)** của chuỗi nối đó. Filter luôn gán velocity theo thời điểm phát âm đầu tiên (`attack onset`) và chép sang các mảnh `tie_stop`.
4. **Tương thích với `humanize.py`**:
   - `humanize` chạy sau cùng ở `audio.py` đã có cơ chế `_repair(hits, offsets, bar_beats)` đảm bảo không đảo thứ tự lớn/nhỏ giữa hai bè đang kêu cùng lúc (`lead > low > support`) và không đảo thứ tự của hai cú gảy liên tiếp trong cùng một bè.
5. **Tương thích với `preset.py` (Audio Gate & Noise Bed)**:
   - Trong `preset.py`, `_GUITAR_GATE = 0.01` chỉ dùng để tắt lớp nhiễu nền analog rất nhỏ (`_GUITAR_NOISE = 0.0003`) khi đàn nghỉ, **không phải** là noise gate cắt tín hiệu âm thanh của đàn. Do đó, các nốt $ppp$ (`velocity 20..30`) vẫn ngân trọn vẹn, sạch sẽ và không bị cắt đuôi.

---

## 6. Lộ Trình Triển Khai Đề Xuất (Khi Bắt Đầu Code)

1. **Bước 1 — Tạo module `backend/app/sonify/guitar_wave.py` (hoặc nâng cấp `_shape_dynamics` trong `guitar_patterns.py`)**:
   - Định nghĩa `ComposerWaveProfile` cho 5 đại sư (`bach`, `classic`, `barrios`, `villa`, `brouwer`) và các override theo pattern (`preludio`, `tremolo`, `etude1`, `etude11`, `cantabile`, `thumb_cantabile`, `noviembre`, `elogio_pizz`, `sarabande`).
   - Cài đặt bộ tính sóng 3 tầng: `macro_wave`, `phrase_wave` (raised-cosine), `band_wave` (smoothed liquidity) và bộ ánh xạ theo `rel_span` + `character`.
2. **Bước 2 — Mở khóa các chốt chặn cứng trong từng module tác gia**:
   - Gỡ bỏ `if event.velocity >= _MELODY_APEX: continue` và `max(44, min(78, ...))` trong `_shape_dynamics`.
   - Đưa `etude1`, `etude11` và `tremolo` vào hệ thống dịch chuyển vòm (arch-preserving wave shift) thay vì bỏ qua hoặc chỉ cộng `[-6..+3]`.
   - Mở rộng cửa sổ của *La Catedral Preludio* (`guitar_barrios.py`) và nối mượt đường cong Intro / Outro (`guitar_frame.py`).
3. **Bước 3 — Cập nhật Test & Revision**:
   - Giữ nguyên hành vi cho các unit test không khung (`framed=False`) nếu các test đó đang kiểm tra hằng số thô của từng pattern, hoặc cập nhật các assertion kiểm tra ngưỡng velocity của bài có khung (`framed=True`).
   - Thêm bộ test `backend/tests/test_guitar_wave.py` kiểm tra:
     - Phiên `calm` biên độ hẹp có nốt xuống vùng $ppp - pp$ (`<= 36`) và không vượt quá vùng ấm (`<= 66`).
     - Phiên `rally`/`volatile` biên độ rộng mở đủ dải từ $pp$ (`<= 38`) tới $f - ff$ (`>= 78`).
     - Bất biến thứ tự 3 bè (`lead > low > support`, và `low > lead >= support` cho `thumb_cantabile`) luôn đúng trên cả 5 đại sư.
   - Tăng `RECAP_REVISION` và `SPAN_REVISION` trong `backend/app/sonify/audio.py` để render lại cache âm thanh mới.
