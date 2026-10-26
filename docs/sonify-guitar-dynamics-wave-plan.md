# Kế Hoạch Thiết Kế Filter Uốn Sóng Động Lực Học (Wave) & Mở Rộng Biên Độ ($ppp \to f$) Cho 5 Đại Sư Guitar

> **Mục tiêu**: Đưa tiếng đàn guitar cổ điển thoát khỏi dải hẹp $mp - mf$ (`44..78`) hiện tại bằng cách **mở rộng chiều sâu về phía thì thầm / gần gũi ($ppp - pp$, velocity `20..38`)**, giữ **90–95% thời lượng bản nhạc trong vùng dây nylon ấm (`<= 64`, dưới ngưỡng ép dây của MS Basic)**, và **kiểm soát chặt trần ép dây (`66..76`)** để tiếng ép dây (*apoyando / nail-snap*) trở nên **hiếm, đắt giá và chỉ xuất hiện ở đúng những thể loại thực sự cần lực tì mạnh**.
>
> **Liên kết**: [`docs/sonify-classical-guitar.md`](./sonify-classical-guitar.md), [`docs/sonify-barrios-tremolo-dynamics.md`](./sonify-barrios-tremolo-dynamics.md), [`docs/sonify-humanize-preset-plan.md`](./sonify-humanize-preset-plan.md).

---

## 1. Chẩn Đoán Hiện Trạng: Vì Sao Guitar Đang Kẹt Ở Quãng $mp - mf$ Và Dễ Bị Đanh Tiếng?

Qua khảo sát toàn bộ pipeline guitar (`guitar.py`, `guitar_patterns.py`, `guitar_barrios.py`, `guitar_villa.py`, `guitar_frame.py`, `humanize.py`), lực gảy hiện tại đang gặp **4 vấn đề kỹ thuật**:

| Điểm nghẽn trong Code | Vị trí hiện tại | Hệ quả âm thanh |
|---|---|---|
| **1. Nền giai điệu & đệm đặt sẵn ngay sát ngưỡng ép dây (`65`)** | • `_MELODY = 64`, `_MELODY_APEX = 72`<br>• `_SWELL_OPEN = 60`, `_SWELL_CLOSE = 62`<br>• `_BAND_SUPPORT = 50..60`, `_BAND_BASS = 54..64` | Ngay từ lúc sinh nốt, giai điệu đã đứng ở `64` (chỉ cách ngưỡng gắt móng `65` đúng 1 đơn vị!). Chỉ cần cộng `extra` từ `swell` hoặc `band == "f"` là hàng loạt nốt giai điệu nhảy lên `66..72`, làm tiếng ép dây kêu liên tục. Trong khi đó, không có nốt nào được viết ở $ppp$ (`~20`) hay $pp$ (`~32`). |
| **2. Chốt chặn cứng `[44, 78]` trong `_shape_dynamics`** | `guitar_patterns.py` dòng 2906–2931:<br>• `if event.velocity >= _MELODY_APEX: continue`<br>• `velocity = max(44, min(78, ...))`<br>• *La Catedral* khóa `lead` ở `54..64`, `support` ở `48..55` | • Sàn `44` chặn đứng toàn bộ dải $ppp - pp$ (`20..42`).<br>• Vì thiếu dải nhỏ `20..42`, bản nhạc buộc phải đẩy lên `60..78` mới có chút chênh lệch, dẫn tới vừa phẳng vừa nhiều tiếng ép dây.<br>• `etude1` và `etude11` bị loại trừ hoàn toàn khỏi `_shape_dynamics`. |
| **3. Thiếu sóng thở vĩ mô (Macro Wave)** | • `swell(phrase, onset)` là tam giác tuyến tính trong 1 câu ngắn (2–4 ô), chỉ cộng `round(4 * swell)` ($\pm 4$ velocity).<br>• Chỉ `tremolo` mới có `_tremolo_region_arch` ($\sin(\pi t)$, biên $+6$). | Các đoạn dài 30 ô (`1D`) hay 80–200 ô (`1W`, `1M`, `3M`, `1Y`) đi ngang một mức năng lượng từ đầu chí cuối, không có sóng cuộn (wave) qua các đoạn. |
| **4. Chưa tách bạch "Trần Sóng Thường" và "Ngân Sách Ép Dây Hiếm"** | Mọi pattern dùng chung một công thức cộng `delta + extra` và cùng một trần `78`. | Những bản cần ấm áp tuyệt đối (*Cantabile*, *La Catedral*, *Un Día de Noviembre*) và những bản cần điểm xuyết cú tì dây thật (*Bartók pizzicato*, *Choro*, *Tresillo*, *Chaconne*) chưa có trần riêng. |

### Nguyên lý âm học trên MS Basic Nylon (`MuseScore_General.sf3`) & Triết lý "Ép Dây Hiếm"

Trên MS Basic, `NoteEvent.velocity` xuất ra MusicXML thành `<note dynamics="V * 100 / 90">`, chia thành **3 vùng âm sắc**:

1. **Vùng Thì Thầm / Intimate — $ppp$ đến $pp$ (`velocity 20..38`)**:
   - Dây nylon kêu cực kỳ mềm, tròn, ấm (giống ngón thịt vuốt ở *sul tasto* / *dolcissimo*). Đây là vùng tạo ra chiều sâu nội tâm và khoảng lặng cho người nghe.
2. **Vùng Tự Sự Ấm — $p$ đến $mp+$ (`velocity 40..64`, dưới ngưỡng `65`)**:
   - Tiếng gảy rõ nét, tròn trịa nhưng **chưa kích hoạt lớp sample móng gắt**.
   - **Nguyên tắc cốt lõi**: Khi đã mở đáy xuống `20..32`, chỉ cần sóng dâng từ `24` lên `64` là chúng ta đã có **biên độ động 40 đơn vị MIDI** (rộng gấp 3–4 lần hiện tại) mà tiếng đàn vẫn **ấm 100%, không hề bị ép dây**.
3. **Vùng Ép Dây Có Kiểm Soát — $mf+$ đến $f$ (`velocity 65..76`, tuyệt đối không vượt `76`)**:
   - Từ `65` trở lên, MS Basic pha tiếng móng/ép dây (*apoyando / punta*).
   - Thay vì dùng tràn lan hay cắt cứng ở `70` cho mọi bài, vùng `65..76` được quản lý như một **"Ngân sách hiếm" (Rare Snap Budget — dưới 3–5% số nốt)**:
     - **Các thể loại trữ tình / cổ điển thuần túy**: Trần tối đa chỉ chạm **`63..68`** ở đúng đỉnh cao nhất của cả bài.
     - **Các thể loại cần lực tì dây thật** (*Bartók pizzicato* của Brouwer, *Tresillo / Animé* của Villa-Lobos, *Choro / Hemiola* hoặc đỉnh *Ultimo Tremolo* của Barrios, đỉnh *Chaconne* của Bach): Được phép vượt lên **`70..76`** tại đúng các nhát nhấn đặc trưng (syncopated accent / slap / climax apex), rồi lập tức lùi ngay về dưới `64`.

---

## 2. Kiến Trúc Tổng Thể Của Filter (`guitar_wave.py` / Post-compose Filter)

### 2.1. Vị trí đặt Filter trong Pipeline

Để không phá vỡ các unit test cấp pattern hiện có (nhiều test trong `test_sonify_guitar.py` gọi trực tiếp các hàm nội bộ hoặc `render(..., framed=False)` và kiểm tra các con số `56`, `60`, `64`, `72`), Filter được đặt làm **bước hoàn thiện động lực học của Guitar**:

```text
render_patterned_voices()
  ├── 1. Sinh nốt theo Pattern & Frame (giữ nguyên tỉ lệ nội bộ giữa các ngón p-i-m-a)
  ├── 2. _repair() & _resolve() & _slur()
  ├── 3. _shape_dynamics()  <-- Nâng cấp thành / gọi qua Guitar Wave & Expander Filter
  └── 4. humanize(score)    <-- Giữ nguyên ở audio.py: nhích ±2 trên các plateau còn lại
```

> **Lưu ý với `humanize.py`**:
> - Khi một nốt đang đứng ở `63–64` (ngay sát dưới ngưỡng ép dây `65`), nếu `humanize` cộng `+2` sẽ vô tình đẩy nốt đó sang `65–66` (bật tiếng ép dây ngoài ý muốn).
> - Do đó, trên các nốt không được đánh dấu ép dây (`velocity <= 64`), đường sóng thường nên giữ trần ở `62–63` (để kể cả khi `humanize` nhích `+1..+2` cũng không vượt quá `64`), chỉ những nốt đỉnh thực sự mới bước qua `65`.

---

### 2.2. Mô Hình Toán Học 3 Tầng Của Filter

Với mỗi nốt tại vị trí thời gian $t$ (tính bằng móc đơn `eighth` hoặc phách `beat`), Filter tính toán lực gảy qua **3 bước**:

#### Bước 1: Tính Biên Độ Sóng Thường $[V_{\text{floor}}, V_{\text{ceil}}]$ & Trần Ép Dây $V_{\text{snap}}$ Theo Bản Nhạc

Mỗi bản nhạc có hai ngưỡng trần tách biệt dựa trên **biên độ giá tương đối `rel_span = (high - low) / low`**, **tính cách phiên `character`** (`calm`, `rally`, `selloff`, `volatile`) và **Hồ sơ Tác gia / Pattern (`PatternWaveProfile`)**:

1. **Hệ số mở biên theo biến động dữ liệu $\alpha \in [0.0, 1.0]$**:
   $$\alpha = \text{clamp}\left(\frac{\text{rel\_span} - 0.004}{0.028 - 0.004},\; 0.0,\; 1.0\right)$$
   - Khi phiên đi ngang hẹp ($\text{rel\_span} \le 0.4\%$ hoặc `character == "calm"`): $\alpha$ nhỏ ($\approx 0.0 - 0.25$). Bản nhạc ở chế độ **Intimate / Whisper**: sàn hạ sâu xuống $ppp - pp$ (`20..30`), trần giữ hoàn toàn dưới ngưỡng ép dây (`56..63`).
   - Khi phiên biến động lớn ($\text{rel\_span} \ge 2.8\%$ hoặc `volatile` / `rally` mạnh): $\alpha \to 1.0$. Sàn vẫn giữ ở $pp$ (`24..32`) cho các đoạn lắng, trần sóng thường chạm `64..68`, và riêng các nốt nhấn đặc trưng được mở tới $V_{\text{snap}}$ (`70..76` tùy thể loại).

2. **Cửa sổ Sóng Thường $[V_{\text{floor}}, V_{\text{ceil}}]$ và Trần Ép Dây $V_{\text{snap}}$**:
   $$\begin{aligned}
   V_{\text{floor}} &= \text{round}\big(P.\text{floor\_calm} - \alpha \cdot (P.\text{floor\_calm} - P.\text{floor\_wide})\big) \\
   V_{\text{ceil}}  &= \text{round}\big(P.\text{ceil\_calm}  + \alpha \cdot (P.\text{ceil\_wide}  - P.\text{ceil\_calm})\big) \\
   V_{\text{snap}}  &= \text{round}\big(P.\text{snap\_calm}  + \alpha \cdot (P.\text{snap\_wide}  - P.\text{snap\_calm})\big)
   \end{aligned}$$
   - Trong đó $V_{\text{ceil}}$ (trần cho 95% các nốt giai điệu) luôn nằm quanh **`58 .. 68`**.
   - Còn $V_{\text{snap}}$ (`68 .. 76`) **chỉ cấp phát cho các nốt thỏa điều kiện Ép Dây Hiếm** (xem Bước 3).

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
     - **Outro**: Uốn đường cong tan dần (*morendo* / *al niente*) từ mức cuối thân bài lịm dần xuống $ppp$ (`W = 0.0 -> V = 20..26`) ở hợp âm/harmonics cuối cùng.

2. **Sóng Câu Nhạc $W_{\text{phrase}}(t) \in [0, 1]$ (Raised-Cosine Phrase Wave)**:
   - Thay thế hàm tam giác tuyến tính gãy khúc hiện tại bằng **đường cong Raised-Cosine (Hann arch)** nối từ đầu câu `phrase.start` lên đỉnh `phrase.apex` rồi thu về cuối câu `phrase.end`:
     $$W_{\text{phrase}}(t) = \frac{1 - \cos(\pi \cdot s(t))}{2}$$
     *(với $s(t)$ là vị trí chuẩn hóa từ đầu câu tới đỉnh và từ đỉnh về cuối câu).*
   - Ngay cả khi câu nhạc có cao độ đi ngang (`phrase.rise < MIN_RISE` — trường hợp mà code hiện tại đang gán phẳng `swell = 0`), câu phẳng vẫn nhận một nhịp thở nhẹ `0.35 * W_phrase(t)` để nốt mở câu và nốt khép câu lắng xuống tự nhiên.

3. **Sóng Thanh Khoản Làm Mượt $W_{\text{band}}(t) \in [0, 1]$ (Smoothed Liquidity Wave)**:
   - Thay bước nhảy bậc thang `_BAND_DELTA` tại vạch nhịp bằng nội suy mượt (cosine interpolation bán kính 1–2 ô nhịp quanh ranh giới cửa sổ thanh khoản) trên thang `{"p": 0.0, "mp": 0.33, "mf": 0.67, "f": 1.0}`.

---

#### Bước 3: Đường Cong Gamma ($\gamma > 1$), Cổng Ép Dây Hiếm (Snap Gate) & Phân Tầng 3 Bè

1. **Hệ số uốn Gamma ($\gamma = 1.25 .. 1.50$) giữ 90–95% bài dưới ngưỡng `65`**:
   $$E(t) = \big(W(t)\big)^{\gamma}$$
   - Vì $\gamma > 1.0$, đường cong năng lượng **võng sâu xuống vùng ấm**: ngay cả khi $W(t) = 0.70$, với $\gamma = 1.40$ thì $E(t) = 0.70^{1.40} \approx 0.60$. Nhờ đó, phần lớn thời lượng bản nhạc nằm gọn trong dải **`24 .. 60`** ($ppp \to mp$), tiếng đàn cực kỳ mềm và tự nhiên.
   - Chỉ khi cả 3 sóng (Đỉnh Section + Đỉnh Phrase + Band `f`) hội tụ ($W(t) \ge 0.88$), $E(t)$ mới tiến gần `1.0` để chạm tới $V_{\text{ceil}}$ (`64..68`).

2. **Cổng Ép Dây Hiếm (Rare Snap Gate — Khi nào một nốt được vượt `68` lên `70..76`?)**:
   Một nốt chỉ được phép nhận cộng thêm lực ép dây (tiến tới $V_{\text{snap}} \in [70, 76]$) khi thỏa **đồng thời**:
   - Thuộc một **Pattern có kỹ thuật ép dây** (như *Bartók pizzicato / staccato stab* của Brouwer, *Tresillo / Etude 11 accent* của Villa-Lobos, *Syncopated Dance / Climax Tremolo* của Barrios, *Grand Solo Fanfare* của Sor, hoặc *Chaconne Breakout* của Bach).
   - Nằm tại **đúng điểm nhấn cấu trúc**: có cờ `event.accent == True` (hoặc là nốt đỉnh `apex` của câu có `phrase.rise >= MIN_RISE`) **VÀ** nằm trong vùng năng lượng cao của sóng ($W(t) \ge 0.75$ hoặc `band == "f"`).
   - **Giới hạn mật độ (Budget Cap)**: Tối đa không quá **3–5% tổng số nốt giai điệu** trong bài được vượt ngưỡng `65`. Nếu một đoạn có nhiều nốt `accent` liên tiếp (như `etude11` đánh `accent` mỗi phách đen), chỉ những phách nằm ngay tại **đỉnh câu (`phrase.apex`)** của các câu cao trào mới được chạm `70..73`, còn các phách `accent` khác trong câu giữ ở `46..64`.

3. **Bảo toàn cấu trúc vi mô của ngón đàn (Micro-pattern Offset Preservation)**:
   - Tách mỗi nốt trong các pattern có vòm nội bộ (`tremolo`, `etude1`, `etude11`, `catedral preludio`) thành:
     $$V_{\text{written}} = V_{\text{ref}}(\text{voice}, \text{bar}) + \Delta_{\text{micro}}$$
   - Filter uốn đường chuẩn $V_{\text{ref}}$ theo sóng $E(t)$, đồng thời giữ nguyên thứ tự tương đối $\Delta_{\text{micro}}$ giữa các ngón.

4. **Bất biến Phân tầng 3 Bè (Three-Voice Balance Invariant)**:
   - **Bè Trung (`support` — rải arpeggio)**: Luôn có trần cứng **`<= 56`** (tuyệt đối không bao giờ chạm ngưỡng ép dây `65`, trừ trường hợp duy nhất là cú chập hợp âm *Bartók slap / staccato stab* của Brouwer nơi cả khối hợp âm cùng bật lên `64..68`). Ở vùng lắng, bè Trung lùi sâu xuống **`18 .. 32` ($ppp$)**.
   - **Bè Trầm (`low` — ngón cái `p`)**: Nằm ở **`22 .. 64`** (chỉ trong `thumb_cantabile`, `bach_fuga` climax hoặc cú slap mới chạm `66..70`), luôn thấp hơn Bè Hát Chính ít nhất `3–4` đơn vị và cao hơn Bè Trung ít nhất `2–4` đơn vị.

---

## 3. Hồ Sơ Động Lực Học Chi Tiết Cho 5 Đại Sư (Đã Hiệu Chỉnh Trần Ép Dây)

### Bảng Tổng Hợp Biên Độ 5 Đại Sư (MIDI Velocity: `ppp ≈ 20`, `pp ≈ 32`, `p ≈ 46`, `mp ≈ 58`, Ngưỡng ép dây `= 65`)

| Đại sư (`ensemble`) | Triết lý Động lực học & Mức độ Ép Dây | Sóng Thường Bè Hát<br>`[V_floor .. V_ceil]`<br>*(Phiên êm $\to$ Phiên sóng lớn)* | Trần Ép Dây Hiếm `V_snap`<br>*(Chỉ $\le 3-5\%$ nốt đỉnh/nhấn)* | Bè Trầm (`low`) | Bè Trung Rải (`support`) | Độ uốn $\gamma$ |
|---|---|---|---|---|---|---|
| **1. J.S. Bach (`bach`)** | **Đối vị Baroque điềm đạm** — Rõ nét từng bè, hầu như không ép dây; chỉ nhấn nhẹ ở đỉnh câu chạy *Chaconne* hoặc phách mạnh *Gigue*. | • Êm: `32 .. 60`<br>• Sóng lớn: `28 .. 65` | **`68 .. 70`**<br>*(Chỉ tại nốt đích scale *Chaconne* / đầu câu *Gigue* ở band `f`)* | `26 .. 62`<br>*(Fuga: `28 .. 63`)* | `22 .. 52` | $\gamma = 1.20$ |
| **2. Fernando Sor (`classic`)** | **Cổ điển Châu Âu trong sáng** — Tiếng đàn tròn, thanh lịch, tránh tiếng móng gắt; chỉ nhói nhẹ ở hợp âm *Fanfare* của *Grand Solo* hoặc nốt tựa *Élégiaque*. | • Êm: `28 .. 58`<br>• Sóng lớn: `26 .. 64` | **`68 .. 70`**<br>*(Chỉ tại khối *Fanfare* mở đoạn `f`, đỉnh *Galop* hoặc *Appoggiatura* đỉnh)* | `24 .. 60` | `20 .. 50` | $\gamma = 1.25$ |
| **3. Agustín Barrios (`barrios`)** | **Lãng mạn Thánh đường & Vũ khúc Nam Mỹ** — *Preludio* và *Julia Florida* ấm hoàn toàn; chỉ đỉnh cao trào *Tremolo* và cú giật *Choro / Hemiola* mới ép dây. | • Êm: `24 .. 60`<br>• Sóng lớn: `22 .. 66` | • *Preludio / Andante*: **`66..68`**<br>• *Tremolo climax*: **`70..72`**<br>• *Choro / Hemiola*: **`72..74`** | `22 .. 64` | `18 .. 52` | $\gamma = 1.35$ |
| **4. Heitor Villa-Lobos (`villa`)** | **Hiện đại Brazil giàu sức sống** — Sóng arpeggio cuộn rộng từ rì rào ($ppp$) lên ấm đầy ($mp+$); cú nhấn *Tresillo* `3+3+2` và đỉnh *Étude 11* được tì dây thật. | • Êm: `28 .. 62`<br>• Sóng lớn: `26 .. 66` | • *Etude 1 / Thumb*: **`68..70`**<br>• *Tresillo / Etude 11 climax*: **`72..74`** | `26 .. 64`<br>*(Thumb: `30 .. 70`)* | `20 .. 54` | $\gamma = 1.25$ |
| **5. Leo Brouwer (`brouwer`)** | **Cực đại Điện ảnh vs Avant-Garde** — *Noviembre* thì thầm tuyệt đối dưới `58`; ngược lại cú vỗ *Bartók pizzicato* trong *Elogio* được phép ép dây sắc lạnh. | • *Noviembre*: `20 .. 58`<br>• *Etude / Elogio*: `24 .. 65` | • *Noviembre*: **Không ép (`<= 60`)**<br>• *Sarabande / Etude*: **`70..72`**<br>• *Elogio Bartók slap*: **`74..76`** | `20 .. 64`<br>*(Slap: `70`)* | `18 .. 52`<br>*(Slap: `66`)* | $\gamma = 1.45$ (êm)<br>$\gamma = 1.10$ (nhịp) |

---

### 3.1. J.S. Bach (`bach`) — Trần Thường `60..65`, Đỉnh Hiếm `68..70`

- **`bach_sarabande`** (Nhịp 3/4 chậm):
  - Hoàn toàn không ép dây: phách 1 lắng ở $pp$ (`28..38`), **phách 2** (trọng âm Sarabande cùng nốt hoa mỹ *mordent*) nở ấm lên **`46..63`** (ngay dưới ngưỡng `65`), và câu lướt phách 3 vuốt nhẹ giảm dần (`34..52`).
- **`bach_fuga`** (Phức điệu 2–3 bè):
  - Bè Soprano (`lead`) đi trong `30..64`, bè Trầm (`low` — giữ Subject/Answer ở `bar - 2`) bám sát ở `28..62` (khoảng cách `gap_bass = 2`), bè Trung (`support`) điểm nhẹ ở `22..48`. Cả ba bè đối vị rõ ràng mà không bè nào bị gắt móng.
- **`bach_chaconne`, `bach_bourree`, `bach_gavotte`, `bach_gigue`**:
  - Chu kỳ bariolage 4 ô của *Chaconne* khởi đầu từ $pp$ (`lead 32`, `support 22..26`, `bass 28`), cuộn dần lên `62..65`; chỉ duy nhất **nốt đích cuối cùng của câu chạy scale bứt phá** (hoặc phách nhấn đầu câu đỉnh của *Gigue*) mới được chạm **`68..70`**.

---

### 3.2. Fernando Sor (`classic`) — Trần Thường `58..64`, Đỉnh Hiếm `68..70`

- **`cantabile`** (*Op. 6 No. 10* — Song thanh quãng 3 / quãng 6 khi `calm`):
  - Giữ thuần khiết 100% trong vùng dây ấm: bè Cao hát ở **`26..58`**, bè Trung đi bóng quãng 3/6 ngay sát dưới ở **`20..48`**, nốt Bass điểm khẽ ở **`22..46`**. Hoàn toàn không có tiếng ép dây.
- **`elegiaque`** (*Fantaisie élégiaque* — Hành khúc tang chấm dôi):
  - Những đoạn mở và kết câu đóng ở giọng Thứ chìm xuống $pp$ (`lead 28..42`, `bass 24..36`, `support 20..30`). Khi câu leo lên đỉnh bi tráng, sóng mở lên `lead 60..65`; chỉ riêng **nốt tựa *appoggiatura* tại câu đỉnh** mới nhói lên **`68..70`** rồi dịu xuống ngay ở móc đơn giải (`58..62`).
- **`study` & `Grand Solo`** (`level 0 -> 1 -> 2`):
  - `level 0` (câu mở đầu): Trong trẻo ở $pp - mp-$ (`28..56`).
  - `level 1` (lần lặp biến tấu): Mở lên $p - mp+$ (`36..62`).
  - `level 2` (đỉnh tái hiện + scale + fanfare): Sóng thường lên `64`, và chỉ đúng **hợp âm khối Fanfare mở đầu section band `f`** hoặc **nốt đích của câu chạy scale sau `caesura`** mới chạm **`68..70`**.

---

### 3.3. Agustín Barrios (`barrios`) — Thánh Đường Êm Ái (`<= 68`) & Vũ Khúc / Tremolo Có Đỉnh (`70..74`)

1. **`preludio` (*La Catedral — Preludio Saudade*)**:
   - Bản Preludio mang tính chất trầm mặc, nội tâm nên **hạn chế tối đa tiếng ép dây**:
   - **Bè Canto (`lead`)**: Mở bài và những đoạn lắng lùi sâu về **$pp$ (`32..40`)**; khi câu nhạc dâng lên theo $W_{\text{macro}}(t)$ và $W_{\text{phrase}}(t)$, tiếng canto nở ấm áp qua $mp$ (`52..63`), và chỉ tại **1–2 nốt đỉnh cao nhất của toàn bài** mới chạm nhẹ **`66..68`** (vừa đủ ngân vang *Ben marcato il canto* mà không bị đanh).
   - **Bè Trung sóng chữ V 6 móc kép (`support`)**: Thấp hơn Canto `10–14` đơn vị, rải như tiếng vọng từ **`20..28` ($ppp$)** ở vùng lặng lên tối đa **`44..50`** ở vùng đỉnh.
   - **Bè Trầm ngân 2 ô (`low`)**: Đi từ `26` ($pp$) đến `56` ($mp$).

2. **`tremolo` (*El Último Tremolo*)**:
   - Suốt 90% thời lượng bản nhạc, mức chuẩn `L` của ngón cái uốn mượt theo sóng từ **`34` ($pp$, fill `a-m-i` thì thầm ở `28, 31, 30, 28`)** đến **`64` ($mp+$, fill `a-m-i` ở `58, 61, 60, 58`)** — tức cả chuỗi lặp `a-m-i` nằm trọn dưới ngưỡng `65`, nghe liền như tiếng vĩ cầm mà không bị lạch cạch tiếng móng!
   - Chỉ tại **đúng đỉnh vòm cao trào nhất của chương ($W(t) \ge 0.90$)**, ngón cái `L` mới vươn lên **`70..72`**, kéo ngón `m` của phách đỉnh chạm nhẹ **`67..69`** trong 1–2 ô nhịp rồi lùi lại về vùng ấm.

3. **`thumb_cantabile` (*Julia Florida*) vs Điệu nhảy (`choro`, `polca`, `hemiola`, `vals`)**:
   - *Julia Florida* (`thumb_cantabile`): Ngón cái hát ấm ở **`32..66`** (đỉnh hiếm `68`), hai nốt đệm chập phách yếu phía trên lùi sâu xuống **`20..42`** ($ppp - p$).
   - *Điệu nhảy Nam Mỹ* (`choro`, `polca`, `hemiola`, `vals`): Đây là thể loại cần độ nảy dân gian thực sự. Các nốt giai điệu và đệm thường đi ở **`32..62`**, nhưng các **cú giật syncopation (`sync=True`) ở vùng cao trào** được phép bật lên **`70..74`** để tạo sức bật nhịp điệu.

---

### 3.4. Heitor Villa-Lobos (`villa`) — Sóng Arpeggio (`26..66`) & Nhát Nhấn Tresillo / Animé (`70..74`)

1. **`etude1` (*Étude No. 1*) — Dịch chuyển cả vòng 16 móc kép trong vùng ấm**:
   - Cả guồng máy 16 móc kép lướt theo sóng $E(t)$:
     - Ở những ô đầu bài hoặc vùng tích lũy ($pp$): lùi xuống rì rào ở **`24..30` (support)**, **`36..42` (lead)**, **`32..38` (bass)**.
     - Khi sóng dâng lên đỉnh: cuộn lên **`46..54` (support)**, **`62..66` (lead)**, **`58..62` (bass)** — chỉ riêng 1–2 ô cực đỉnh của phiên `rally` mạnh thì hai nốt giai điệu mới chạm **`68..70`**. Toàn bộ 13 nốt bè trung giữ nguyên hình vòm `-2, 0, +2, 0, -2` dưới ngưỡng `54`, nên nghe rất mượt và dày.

2. **`etude11` (*Étude No. 11 — Animé*) & `villa_pattern` (*Tresillo* `3+3+2`)**:
   - Trong `etude11`, hiện tại mọi phách đen đều gắn `accent=True` với `hairpin` lên `72`, làm cả bài kêu tiếng ép dây liên tục.
   - **Điều chỉnh lại**: Cho `hairpin` của các phách thường uốn trong **`38 .. 63`** (dưới ngưỡng ép dây `65`, với 4 nốt sextuplet giữa ở **`26 .. 50`**). Chỉ tại **phách chứa đỉnh câu (`phrase.apex`) khi sóng $W(t) \ge 0.80$**, cú bổ đầu chùm mới được ép dây thật ở **`70..74`** (giảm từ `84` xuống).
   - Tương tự trong `villa_pattern`, chỉ đúng **3 nhát nhấn *tresillo* `{0, 3, 6}` ở các ô `volatile` band `f`** mới được bật lên **`70..73`**, còn sóng arpeggio xung quanh giữ ở `24..62`.

---

### 3.5. Leo Brouwer (`brouwer`) — Phân Cực Rõ Giữa Ballad Ấm (`<= 58`) Và Cú Slap Hiện Đại (`72..76`)

1. **`noviembre` (*Un Día de Noviembre*) — 0% Ép Dây**:
   - Đường cong **Intimate Ballad Curve** ($\gamma = 1.45$) khóa trần cứng ở **`58..60`**:
   - Mở câu và kết câu ở **`20..30` ($ppp - pp$)**, bè Trung rải màu `add9 / maj7` mỏng nhẹ ở **`18..36`**, nốt Bass pickup cuối ô bước khẽ (`20..32`). Đỉnh câu chỉ nở ấm áp tới **`56..60`**, hoàn toàn không bao giờ chạm ngưỡng `65`.
2. **`sarabande` (*El Decamerón Negro / Sarabanda*)**:
   - Phách 1 vào thật khẽ (`24..36`, $pp$), **phách 2** (hợp âm màu sus2/add9) ngân sâu ở **`52..66`** (chỉ ở đỉnh cao trào của phiên `selloff` mới chạm **`70..72`**), sau đó câu lướt *modal swarm* ở nửa sau ô nhịp uốn mượt trong **`24..62`** (hoàn toàn không ép dây trên chuỗi móc kép chạy nhanh).
3. **`brouwer_etude` (*Estudio Sencillo No. 6*) & `elogio_pizz` (*Elogio de la Danza*)**:
   - Đây là nơi duy nhất trên guitar cần tiếng **ép dây / giật dây thật (*Bartók pizzicato / slap*)**:
   - Các ô ostinato staccato bình thường được ghìm xuống **`26..56`** ($pp \to mp$) như tiếng nhịp ngầm căng thẳng.
   - Nhưng tại **móc đơn thứ 3 (`slap`) của `elogio_pizz`** ở các ô biến động mạnh (hoặc cú stab cuối của `_stab_and_ring`), Filter cho phép vọt lên **`72..76`** (giảm từ `84..90` xuống `72..76` để tiếng bật đanh gọn mà không bị vỡ tiếng).

---

## 4. Khung Intro & Outro (`guitar_frame.py`): Khởi Âm Từ $ppp$ Và Tan Vào Im Lặng (*Morendo*)

1. **Intro (`leading` pedal bars)**:
   - Ô 1 mở đầu từ vùng **$ppp - pp$ (`22..34`)** (tiếng chuông Harmonics đầu bài của Barrios hoặc nốt dây buông của Brouwer/Villa ngân lên từ `24–30` thay vì `44–50`).
   - Qua các ô tiếp theo của Intro, đường bao tăng dần để khớp mượt với velocity đầu thân bài (`~36..48`), không có nốt nào trong Intro vượt quá `58` (trừ intro `_edge_stab` kịch tính của Brouwer được phép chập 1 cú đầu ở `68..70`).
2. **Outro (`trailing` pedal bars)**:
   - Áp dụng hàm suy giảm mũ (**Exponential Morendo Curve**) từ mức cuối thân bài xuống **`18..24` ($ppp$)** ở ô cuối cùng.
   - Riêng trường hợp kết kịch tính của Brouwer (`_stab_and_ring` khi `volatile`/`selloff`) hoặc Villa (`bright` outro): cú chập dứt khoát cuối bài dừng ở **`68..72`** (thay vì `78` như trước).

---

## 5. Bảo Toàn Bất Biến Kỹ Thuật & Tương Thích Hệ Thống

1. **Không làm câm nốt và không vượt trần ép dây**:
   - Sàn tuyệt đối sau mọi phép tính là `velocity >= 18` ($ppp$), trần sóng thường là `<= 64..68`, và trần ép dây hiếm là `velocity <= 76`.
2. **Bảo toàn 100% `assert_playable`**:
   - Filter chỉ biến đổi `NoteEvent.velocity` (không chạm vào `midi`, `beat`, `duration_beats`, `voice`, `tie_start`, `tie_stop`), nên mọi quy tắc thế tay, dây đàn và `assert_playable` giữ nguyên 100%.
3. **Đồng bộ các nốt nối dây (`tie_start` / `tie_stop`)**:
   - Một nốt nối qua vạch nhịp (`tie_stop=True`) luôn mang cùng `velocity` với cú gảy đầu tiên (`tie_start=True`) của chuỗi nối đó.
4. **Tương thích với `humanize.py` (Chống trượt qua ngưỡng `65`)**:
   - Với các nốt không thuộc diện ép dây (`velocity <= 64`), nếu `humanize` cộng `+1..+2` làm vượt `64` thì kẹp lại ở `64` để `humanize` không tự ý kích hoạt lớp sample móng gắt.
5. **Tương thích với `preset.py` (Audio Gate & Noise Bed)**:
   - `_GUITAR_GATE = 0.01` trong `preset.py` chỉ tắt lớp nhiễu nền analog (`_GUITAR_NOISE = 0.0003`) khi đàn nghỉ, không cắt tín hiệu của đàn, nên các nốt $ppp$ (`velocity 18..30`) vẫn ngân trọn vẹn.

---

## 6. Lộ Trình Triển Khai Đề Xuất (Khi Bắt Đầu Code)

1. **Bước 1 — Tạo module `backend/app/sonify/guitar_wave.py` (hoặc nâng cấp `_shape_dynamics` trong `guitar_patterns.py`)**:
   - Định nghĩa `ComposerWaveProfile` cho 5 đại sư (`bach`, `classic`, `barrios`, `villa`, `brouwer`) với bộ 3 thông số `(V_floor, V_ceil, V_snap)` và cổng `Rare Snap Gate` (chỉ mở `68..76` cho $\le 3-5\%$ số nốt ở đúng các pattern cần ép dây).
   - Cài đặt bộ tính sóng 3 tầng: `macro_wave`, `phrase_wave` (raised-cosine), `band_wave` (smoothed liquidity) với hệ số uốn $\gamma = 1.20 .. 1.45$.
2. **Bước 2 — Mở khóa các chốt chặn cứng trong từng module tác gia**:
   - Gỡ bỏ `if event.velocity >= _MELODY_APEX: continue` và `max(44, min(78, ...))` trong `_shape_dynamics`.
   - Đưa `etude1`, `etude11` và `tremolo` vào hệ thống dịch chuyển vòm (arch-preserving wave shift), đồng thời hạ các phách thường của `etude11` xuống dưới `64` (chỉ ép dây ở đỉnh câu).
   - Mở rộng đáy của *La Catedral Preludio* (`guitar_barrios.py`) xuống $ppp - pp$ (`20..34`) trong khi giữ trần Canto êm ái (`<= 68`), và nối mượt đường cong Intro / Outro (`guitar_frame.py`).
3. **Bước 3 — Cập nhật Test & Revision**:
   - Thêm bộ test `backend/tests/test_guitar_wave.py` kiểm tra:
     - Phiên `calm` biên độ hẹp có nốt xuống vùng $ppp - pp$ (`<= 34`) và **100% số nốt nằm dưới ngưỡng ép dây (`<= 64`)**.
     - Phiên `rally`/`volatile` biên độ rộng mở sâu xuống $pp$ (`<= 34`), có sóng uốn qua các ô nhịp, **tỷ lệ nốt vượt ngưỡng `65` chiếm dưới 5%**, và không có nốt nào vượt quá `76` (hoặc `70` với Bach/Sor).
     - Bất biến thứ tự 3 bè (`lead > low > support`, và `low > lead >= support` cho `thumb_cantabile`) luôn đúng trên cả 5 đại sư.
   - Tăng `RECAP_REVISION` và `SPAN_REVISION` trong `backend/app/sonify/audio.py`.
