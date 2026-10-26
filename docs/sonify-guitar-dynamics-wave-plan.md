# Kế Hoạch Thiết Kế Filter Uốn Sóng Động Lực Học (Wave) & Mở Rộng Biên Độ ($ppp \to f$) Cho 5 Đại Sư Guitar

> **Mục tiêu**: Đưa tiếng đàn guitar cổ điển thoát khỏi dải hẹp $mp - mf$ (`44..78`) hiện tại bằng cách **thay thế (rebase) vận tốc đã viết quanh `64/72` bằng đường sóng động lực học**, mở rộng chiều sâu về phía **thì thầm / gần gũi ($ppp - pp$, velocity `18..38`)**, giữ **100% các nốt sóng thường trong vùng dây nylon ấm (`<= 63` trước humanize, `<= 64` sau humanize)**, và cấp phát ngân sách **ép dây hiếm (`66..76`, tính theo từng section)** chỉ cho đúng những cú nhấn thuộc các pattern thực sự cần lực tì dây.
>
> **Liên kết**: [`docs/sonify-classical-guitar.md`](./sonify-classical-guitar.md), [`docs/sonify-barrios-tremolo-dynamics.md`](./sonify-barrios-tremolo-dynamics.md), [`docs/sonify-humanize-preset-plan.md`](./sonify-humanize-preset-plan.md).

---

## 1. Chẩn Đoán Hiện Trạng Trong Codebase

Qua khảo sát toàn bộ pipeline guitar (`guitar.py`, `guitar_patterns.py`, `guitar_barrios.py`, `guitar_villa.py`, `guitar_frame.py`, `humanize.py`), lực gảy hiện tại đang bị nén trong dải hẹp do **4 nguyên nhân**:

| Điểm nghẽn trong Code | Vị trí & Con số thực tế đang chạy | Hệ quả âm thanh |
|---|---|---|
| **1. Nền giai điệu & đệm đặt sẵn ngay sát ngưỡng ép dây (`65`)** | • `_MELODY = 64`, `_MELODY_APEX = 72`<br>• `_SWELL_OPEN = 60`, `_SWELL_MID = 68`, `_SWELL_CLOSE = 62`<br>• `_BAND_SUPPORT = 50..60`, `_BAND_BASS = 54..64`<br>• `etude1` / `etude11`: `_ETUDE_OPEN = 60`, `_ETUDE_PEAK = 72`, sàn nốt giữa `44`, mỗi phách đen của `etude11` đều gắn `accent=True` | Ngay từ lúc sinh nốt, giai điệu đã đứng ở `60..72` (ngay sát hoặc vượt ngưỡng móng `65`). Không có nốt nào được viết ở $ppp$ (`~18..26`) hay $pp$ (`~28..36`). |
| **2. `_shape_dynamics` cộng thêm lên nền `64` và kẹp cứng `[44, 78]`** | `guitar_patterns.py` dòng 2906–2931:<br>• `if event.velocity >= _MELODY_APEX: continue`<br>• `velocity = max(44, min(78, event.velocity + delta + extra))`<br>• `_punch` cộng `+8` hoặc `+12` rồi kẹp `min(88, ...)`<br>• *La Catedral* khóa `lead` ở `54..64`, `support` ở `48..55` | • Lấy `event.velocity` (`~64`) làm tâm rồi cộng `_BAND_DELTA` (`-12..+4`) và `extra` (`0..+4`), cộng thêm sàn `44`, khiến bản nhạc không thể xuống được $ppp - pp$.<br>• Nếu chỉ gỡ `max(44, min(78, ...))` mà không rebase lại tâm thì chỉ đẩy thêm nốt lên vùng móng.<br>• `etude1`, `etude11`, `tremolo` đang đứng ngoài `_shape_dynamics`. |
| **3. Thiếu sóng thở theo dữ liệu giá ở cấp Section** | • `swell(phrase, onset)` là tam giác tuyến tính trong 1 câu ngắn (2–4 ô), chỉ cộng `round(4 * swell)`.<br>• Khung `guitar_frame.py` viết cứng `_PP = 46`, `_P = 50`, `_MP = 56`, `_MF = 64` (stab của Brouwer cũng là `_MF = 64`) và các ô pedal bị `_shape_dynamics` bỏ qua. | Các đoạn dài 30 ô (`1D`) hay 80–200 ô (`1W`, `1M`, `3M`, `1Y`) thiếu độ lượn theo đường giá vĩ mô và thiếu độ mở/tắt tự nhiên ở biên section. |
| **4. Chưa tách bạch 3 ngưỡng trần: Trần Thường (`<= 63`), Trần Sau Humanize (`<= 64`) và Trần Snap (`66..76`)** | `humanize.py` dùng chung cho cả 5 dòng nhạc, nhích `{-2, -1, 0, +1, +2}` và chỉ kẹp `1..127`, không biết ngưỡng `65` của nylon hay trần snap `76`. | Một nốt ấm ở `63–64` khi qua `humanize` cộng `+2` sẽ trượt sang `65–66` (bật tiếng móng ngoài ý muốn); hoặc một cụm snap ở `75–76` nếu thành plateau có thể bị đẩy vượt `76`. |

### Quy ước 3 vùng âm sắc trên MS Basic Nylon (`MuseScore_General.sf3`)

Trên MS Basic, `NoteEvent.velocity` xuất ra MusicXML thành `<note dynamics="V * 100 / 90">`:
1. **Vùng Thì Thầm / Intimate — $ppp$ đến $pp$ (`velocity 18..38`)**: Tiếng dây nylon mềm, tròn, ấm (*sul tasto / dolcissimo*).
2. **Vùng Tự Sự Ấm — $p$ đến $mp+$ (`velocity 40..64`, nghiêm ngặt `< 65`)**:
   - **Mọi nốt không gắn cờ Snap** bắt buộc dừng ở **`<= 63` trước `humanize`** và được kẹp cứng ở **`<= 64` sau `humanize`**.
   - Khi mở đáy xuống `18..32`, chỉ riêng dải ấm `18..63` đã rộng hơn **40 đơn vị MIDI** mà không hề chạm vào tiếng móng gắt.
3. **Vùng Ép Dây Hiếm — $mf+$ đến $f$ (`velocity 66..76`, tuyệt đối `<= 76` cả trước và sau `humanize`)**:
   - Chỉ dành cho các cú nhấn đã lọt qua **Cổng Snap (`Rare Snap Gate`)** trên những pattern có kỹ thuật tì dây / giật dây thật (*Bartók slap*, *Tresillo*, *Etude 11 climax*, *Choro / Hemiola sync*, *Tremolo climax*, *Grand Solo fanfare*, *Chaconne scale arrival*).

---

## 2. Mô Hình Toán Học & Cơ Chế Rebase Của Filter (`guitar_wave.py`)

### 2.1. Vị trí trong Pipeline & Tương tác với `humanize`

```text
render_patterned_voices()
  ├── 1. Sinh nốt theo Pattern & Frame (giữ nguyên cấu trúc tương đối giữa các ngón p-i-m-a)
  ├── 2. _repair() & _resolve() & _slur()
  ├── 3. apply_guitar_wave()  <-- Rebase toàn bộ velocity vào cửa sổ [V_floor, V_ceil <= 63] + cấp phát Snap [66..76]
  └── 4. humanize(score)      <-- Ở audio.py (hoặc cuối humanize cho variant=="guitar"):
                                  • Nếu written_velocity <= 64: heard_velocity = min(64, heard_velocity)
                                  • Nếu written_velocity >= 65: heard_velocity = max(66, min(76, heard_velocity))
```

> **Lưu ý về Unit Test hiện hữu (`test_sonify_guitar.py`)**:
> Mọi lệnh gọi `render(..., variant="guitar")` đều đi qua cuối `render_patterned_voices()`. Do đó, khi thay `_shape_dynamics` bằng `apply_guitar_wave()`, các test trong `test_sonify_guitar.py` đang khóa cứng số tuyệt đối (`56`, `60`, `64`, `72`) trên kết quả `render()` **sẽ thay đổi và cần được cập nhật** sang kiểm tra: (a) delta tương đối bên trong vòm/cụm ngón, (b) bất biến thứ tự giữa các bè trong cùng một cú đánh, và (c) biên độ nằm trong cửa sổ của `PatternWaveProfile`.

---

### 2.2. Bước 1: Tính Hệ Số Mở Biên $\alpha_{\text{sec}} \in [0.0, 1.0]$ Theo Từng Section

Không dùng một `rel_span` của cả bài cho các bản dài (`1W`, `1M`, `3M`, `1Y`), vì biên độ cả tuần/tháng luôn vượt `2.4%` và sẽ làm $\alpha = 1.0$ bão hòa suốt cả chương. Thay vào đó, tính $\alpha_{\text{sec}}$ riêng cho **từng `FormSection` thân bài** (dùng `_section_rel_span(bars, groups, section.start, section.end)` đã có trong `render.py`; với bài `1D` chỉ có 1 thân bài thì chính là `rel_span` của phiên):

$$\alpha_{\text{sec}} = \text{clamp}\left(\frac{\text{rel\_span}_{\text{sec}} - 0.004}{0.024 - 0.004},\; 0.0,\; 1.0\right)$$

*(Ngưỡng dưới là `0.4%` và ngưỡng bão hòa trên là `2.4%`).*

**Quy tắc co giãn cửa sổ $[V_{\text{floor}}, V_{\text{ceil}}]$ đồng nhất theo khóa `(ensemble, pattern)`**:

Tra cứu hồ sơ `P = PROFILE_BY_KEY[(ctx.ensemble, pattern)]` (trong đó mọi dòng đều thỏa `P.floor_calm <= P.floor_wide` và `P.ceil_calm <= P.ceil_wide <= 63`, cùng `P.snap_calm >= 66` nếu có):

$$\begin{aligned}
V_{\text{floor}}(\alpha_{\text{sec}}) &= \text{round}\big(P.\text{floor\_calm} + \alpha_{\text{sec}} \cdot (P.\text{floor\_wide} - P.\text{floor\_calm})\big) \\
V_{\text{ceil}}(\alpha_{\text{sec}})  &= \text{round}\big(P.\text{ceil\_calm}  + \alpha_{\text{sec}} \cdot (P.\text{ceil\_wide}  - P.\text{ceil\_calm})\big) \\
V_{\text{snap}}(\alpha_{\text{sec}})  &= \begin{cases}
\text{None}, & \text{nếu } P.\text{snap\_wide} \text{ là None} \\
\text{round}\big(P.\text{snap\_calm} + \alpha_{\text{sec}} \cdot (P.\text{snap\_wide} - P.\text{snap\_calm})\big), & \text{ngược lại}
\end{cases}
\end{aligned}$$

- **Khi section êm ($\alpha_{\text{sec}} < 0.25$)**: Cửa sổ hạ thấp về phía thì thầm $[P.\text{floor\_calm},\; P.\text{ceil\_calm}]$, và **section đó không mở cổng Snap** ($K_{\text{sec}} = 0$, ngoại trừ cú slap cố định của `elogio_pizz`).
- **Khi section có sóng ($\alpha_{\text{sec}} \ge 0.25$)**: Sàn tiến dần về mức $pp$ rõ nét (`P.floor_wide`), trần sóng thường mở lên `P.ceil_wide <= 63`, và cho phép cấp phát Snap trong chính section đó tới mức $V_{\text{snap}}(\alpha_{\text{sec}}) \in [66, 76]$.

---

### 2.3. Bước 2: Tổng Hợp Sóng Đa Tầng $W(t) \in [0.0, 1.0]$

Tại mỗi vị trí thời gian $t$ (tính theo móc đơn thực `eighth = bar * epb + beat * 2`), năng lượng sóng là tổ hợp của 3 thành phần:

$$W(t) = \text{clamp}\Big(w_{\text{macro}} \cdot W_{\text{macro}}(t) \;+\; w_{\text{phrase}} \cdot W_{\text{phrase}}(t) \;+\; w_{\text{band}} \cdot W_{\text{band}}(t),\; 0.0,\; 1.0\Big)$$

với trọng số cố định $w_{\text{macro}} = 0.45,\; w_{\text{phrase}} = 0.35,\; w_{\text{band}} = 0.20$:

1. **Sóng Vĩ Mô $W_{\text{macro}}(t) \in [0, 1]$ (Đi theo Đường Giá Đã Làm Mượt + Mờ Biên Section An Toàn)**:
   - **Đường bao giá chuẩn hóa $\widetilde{\text{PriceEnv}}(t) \in [0, 1]$**:
     - Lấy trung bình trượt cửa sổ 3 ô nhịp của cao độ giai điệu $m(t)$ trong phạm vi section `[sec_start, sec_end)`.
     - Đặt $m_{\min} = \min(m)$, $m_{\max} = \max(m)$ trên section đó.
     - **Trường hợp suy biến ($m_{\max} == m_{\min}$ — section phẳng chỉ có 1 cao độ)**: Đặt cứng $\widetilde{\text{PriceEnv}}(t) = 0.5$ (không chia cho `0`).
     - Khi $m_{\max} > m_{\min}$: chuẩn hóa $p(t) = \frac{\bar{m}(t) - m_{\min}}{m_{\max} - m_{\min}} \in [0, 1]$. Ở section có `majority_mood == "selloff"`, lấy $\widetilde{\text{PriceEnv}}(t) = \max\big(p(t),\; 0.75 \cdot (1 - p(t))\big)$ để đáy bán tháo sâu vẫn có năng lượng sóng mà không ép đỉnh ở giữa section.
   - **Hàm mờ biên $T_{\text{edge}}(t) \in [0.25, 1.0]$ (Không chồng lấp khi section ngắn `< 4` ô)**:
     - Đặt độ dài section theo móc đơn là $L_{\text{sec}} = (\text{sec\_end} - \text{sec\_start}) \cdot \text{epb}$, và độ dài đoạn mờ biên là:
       $$R = \min\big(2 \cdot \text{epb},\; \lfloor L_{\text{sec}} / 2 \rfloor\big)$$
     - Nếu $R \le 0$: $T_{\text{edge}}(t) = 1.0$.
     - Nếu $R > 0$: trong $R$ móc đơn đầu section ($d_{\text{in}} = t - t_{\text{sec\_start}} < R$), $T_{\text{edge}}$ tăng cosine từ `0.25` lên `1.0`; trong $R$ móc đơn cuối section ($d_{\text{out}} = t_{\text{sec\_end}} - t < R$), $T_{\text{edge}}$ hạ cosine từ `1.0` về `0.25`; ở khoảng giữa $T_{\text{edge}} = 1.0$. Nhờ $R \le L_{\text{sec}} / 2$, hai đoạn mờ đầu và cuối **không bao giờ chồng lên nhau** ngay cả trên fixture 1–3 ô nhịp.
   - **Công thức gộp**:
     $$W_{\text{macro}}(t) = \kappa_{\text{sec}} \cdot T_{\text{edge}}(t) \cdot \Big(0.25 + 0.75 \cdot \widetilde{\text{PriceEnv}}(t)\Big)$$
     với $\kappa_{\text{sec}} = 0.65$ khi section là `trio` hoặc `bridge` mang pattern nội tâm (`cantabile`, `thumb_cantabile`, `noviembre`, `andante`), ngược lại $\kappa_{\text{sec}} = 1.0$.

2. **Sóng Câu Nhạc $W_{\text{phrase}}(t) \in [0, 1]$ (Raised-Cosine Phrase Wave)**:
   - Nối mượt từ đầu câu `phrase.start` lên `phrase.apex` rồi về `phrase.end` bằng đường cong Raised-Cosine:
     $$C_{\text{phrase}}(t) = \frac{1 - \cos(\pi \cdot s(t))}{2}$$
   - Hệ số biên độ câu (chỉ nhân **một lần duy nhất** tại đây, không giảm `w_phrase`):
     $$W_{\text{phrase}}(t) = \begin{cases}
     C_{\text{phrase}}(t), & \text{nếu } \text{phrase.rise} \ge \text{MIN\_RISE} \\
     0.35 \cdot C_{\text{phrase}}(t), & \text{nếu } \text{phrase.rise} < \text{MIN\_RISE} \text{ (câu đi ngang vẫn thở nhẹ)}
     \end{cases}$$

3. **Sóng Thanh Khoản & Tính Cách Ô $W_{\text{band}}(t) \in [0, 1]$**:
   - Nội suy cosine mượt (bán kính 1 ô nhịp quanh ranh giới cửa sổ thanh khoản) trên điểm số của từng ô `bar`:
     $$\text{score}(\text{bar}) = \text{clamp}\Big(\text{band\_val}\big(\text{band}(\text{bar})\big) + \text{mood\_nudge}\big(\text{mood}(\text{bar})\big),\; 0.0,\; 1.0\Big)$$
     với `band_val = {"p": 0.0, "mp": 0.33, "mf": 0.67, "f": 1.0}` và `mood_nudge = {"calm": -0.10, None: 0.0, "selloff": +0.05, "rally": +0.10, "volatile": +0.15}`.

---

### 2.4. Bước 3: Công Thức Rebase Vận Tốc, Bảo Toàn Vòm Vi Mô & Cổng Snap

Với hệ số uốn $\gamma = P.\gamma$ của pattern đang chạy, năng lượng sau uốn là:

$$E(t) = \big(W(t)\big)^{\gamma} \in [0.0, 1.0]$$

#### A. Rebase đường chuẩn Bè Hát Chính (`V_hat`), Bè Trầm (`V_bass_curve`) và Bè Trung (`V_sup_curve`)

Sóng **thay thế hoàn toàn** nền `64/72` cũ bằng 3 đường cong đồng bộ theo $E(t)$:

$$\begin{aligned}
V_{\text{hat}}(t)        &= \text{round}\Big(V_{\text{floor}} + E(t) \cdot \big(V_{\text{ceil}} - V_{\text{floor}}\big)\Big) \in [V_{\text{floor}},\; V_{\text{ceil}} \le 63] \\
V_{\text{bass\_curve}}(t) &= \text{round}\Big(P.\text{bass\_floor} + E(t)^{1.05} \cdot \big(P.\text{bass\_ceil} - P.\text{bass\_floor}\big)\Big) \\
V_{\text{sup\_curve}}(t)  &= \text{round}\Big(P.\text{sup\_floor} + E(t)^{1.20} \cdot \big(P.\text{sup\_ceil} - P.\text{sup\_floor}\big)\Big)
\end{aligned}$$

Trong đó **Bè Hát Chính** là:
- Voice 3 (`low`) đối với pattern `thumb_cantabile`.
- Voice 1 (`lead`) đối với tất cả các pattern còn lại.

#### B. Bảo toàn Delta Vi Mô ($\Delta_{\text{micro}}$) cho 4 Pattern Có Vòm Nội Bộ

Với 4 pattern có vòm nội bộ (`tremolo`, `etude1`, `etude11`, `preludio`), mỗi nốt được tính từ đường cong đã rebase tại thời điểm đó cộng với độ lệch vi mô gốc trong code:

| Pattern | Công thức Rebase ở vùng ấm (khớp 100% với cấu trúc trong code) | Quy tắc khi Cú Mốc được Snap (`66..74`) |
|---|---|---|
| **`tremolo`**<br>(`guitar.py:64`:<br>`4/4: (-4, 0, +4, +1)`<br>`3/4 & 6/8: (-4, +4, 0)`) | • Tại phách đen thứ $q$, lấy độ lệch phách $\Delta_{\text{quarter}}(q)$ đúng từ `_TREMOLO_QUARTER_OFFSETS` (`(-4, 0, +4, +1)` cho 4 phách; `(-4, +4, 0)` cho 3 phách).<br>• Ngón cái (`low`) và nốt màu đầu ô đổi hợp âm (`support`, nếu có):<br>$V_{\text{thumb}}(q) = \text{clamp}\big(V_{\text{hat}}(t_q) + \Delta_{\text{quarter}}(q),\; P.\text{ floor\_calm},\; 63\big)$<br>*(Nếu chạm trần `63` ở phách `q=2`, dịch cả 4 phách của ô đó xuống để giữ nguyên hiệu số `(-4, 0, +4, +1)`).*<br>• 4 móc kép `a-m-i-a` (`lead`) nhận đúng `_TREMOLO_FILL_OFFSETS = (-6, -3, -4, -6)`:<br>$V_{\text{fill}}(q, r) = \max\big(18,\; V_{\text{thumb}}(q) + (-6, -3, -4, -6)[r]\big) \le 60$. | Khi phách đỉnh $q^*$ lọt Cổng Snap với lực $V_{\text{snapped}} \in [68, 72]$:<br>• Ngón cái `low` tại $q^*$ nhận $V_{\text{snapped}}$.<br>• Ngón `m` (`r == 1`) nhận $\min(V_{\text{snapped}} - 3,\; 69)$.<br>• Ba móc kép `a, i, a` (`r == 0, 2, 3`) và nốt màu `support` **bị kẹp cứng ở `<= 63`**: cụ thể `i` nhận $\min(63,\; V_{\text{snapped}} - 4)$ và `a` nhận $\min(61,\; V_{\text{snapped}} - 6)$ (vẫn giữ nghiêm ngặt `thumb > m > i > a` mà `a, i` không vượt ngưỡng `65`!). |
| **`etude1`**<br>(`guitar_villa.py:339`:<br>`_ETUDE1_ARC` `{-2, 0, +2}`) | • Hai nốt hát (`index 7, 9` trên `lead`) nhận $V_{\text{lead}}(t) = V_{\text{hat}}(t) \in [V_{\text{floor}}, V_{\text{ceil}} \le 63]$.<br>• 13 móc kép bè trung (`support`) có tâm ô là $V_{\text{sup\_mid}}(t) = \min\big(V_{\text{sup\_curve}}(t),\; \min(V_{\text{lead}}) - 8\big)$, và từng móc kép thứ $i$ nhận:<br>$V_{\text{sup}}(i) = \text{clamp}\big(V_{\text{sup\_mid}}(t) + \text{\_ETUDE1\_ARC}[i],\; P.\text{sup\_floor},\; P.\text{sup\_ceil}\big)$<br>*(Bảo toàn tuyệt đối bậc thang `-2, 0, +2, 0, -2` quanh tâm bè trung).*<br>• Bass đầu ô (`low`) luôn nằm **giữa đỉnh bè trung của ô đó và nốt hát**:<br>$V_{\text{bass}} = \min\Big(61,\; \max\big(\max_{i} V_{\text{sup}}(i) + 2,\; \min(V_{\text{lead}}) - 4\big)\Big)$<br>*(Khi `lead` thì thầm ở `32` và `support` ở `22..26`, `bass` sẽ ở `28`, giữ đúng `lead (32) > bass (28) > support (22..26)`!).* | Khi ô đỉnh lọt Cổng Snap với $V_{\text{snapped}} \in [68, 70]$:<br>• Hai nốt hát (`index 7, 9`) nhận $V_{\text{snapped}}$.<br>• Bass đầu ô giữ ở $\min(61,\; V_{\text{snapped}} - 6) \le 61$.<br>• 13 móc kép `support` giữ nguyên dưới `P.sup_ceil` (`<= 52`). |
| **`etude11`**<br>(`guitar_villa.py:473`:<br>`arch = {1:-10, 2:-6, 4:-7, 5:-10}`<br>`+ _ETUDE11_TILT = {1:-1, 2:-1, 4:0, 5:+1}`) | • Gỡ `accent=True` mặc định trên các phách thường (`quarter 0..3`).<br>• Cú 1 của phách (`lead` tại `beat = q`) nhận $V_{\text{q}} = V_{\text{hat}}(t_q) \in [V_{\text{floor}}, V_{\text{ceil}} \le 63]$.<br>• Cú 4 nhắc lại (`lead` tại `beat = q + 0.5`) nhận $V_{\text{echo}} = \max(P.\text{sup\_floor} + 6,\; V_{\text{q}} - 8)$.<br>• Bass đầu phách (`low`, gỡ `accent=True` ở phách thường) nhận $V_{\text{bass}} = \max(V_{\text{echo}} + 2,\; V_{\text{q}} - 4) \le 59$.<br>• 4 nốt sextuplet giữa (`slot in (1, 2, 4, 5)` trên `support`) giữ **đầy đủ cả `arch` lẫn `_ETUDE11_TILT`** (tức tổng độ lệch $\Delta_{\text{slot}} = \{-11, -7, -7, -9\}$ rồi cộng `band_nudge` và nghiêng `tilt` sao cho `slot 1 < slot 2 == slot 4 < slot 5` hoặc đúng bậc thang `arch + tilt` dưới trần `min(P.sup_ceil, V_echo - 2)`):<br>$V_{\text{sup}}(\text{slot}) = \text{clamp}\big(V_{\text{q}} + \text{arch}[\text{slot}] + \text{band\_nudge} + \text{tilt}[\text{slot}],\; P.\text{sup\_floor},\; \min(P.\text{sup\_ceil},\; V_{\text{echo}} - 2)\big)$. | Khi phách đỉnh $q^*$ lọt Cổng Snap với $V_{\text{snapped}} \in [70, 74]$:<br>• Chỉ **cú 1 của `lead`** tại $q^*$ nhận $V_{\text{snapped}}$ và giữ `accent=True`.<br>• Bass tại $q^*$ kẹp ở $\min(62,\; V_{\text{snapped}} - 6)$ (có `accent=True`).<br>• Cú 4 nhắc lại `lead` kẹp ở $\min(60,\; V_{\text{snapped}} - 10)$.<br>• 4 nốt sextuplet `support` tính từ `min(63, V_q)` nên vẫn nằm trọn `<= 50` và giữ nguyên hình vòm `arch + tilt`. |
| **`preludio`**<br>(*La Catedral*) | • Nốt Canto 1 (`pitch_a`, móc kép `0`) nhận $V_{\text{canto1}} = V_{\text{hat}}(t) \in [V_{\text{floor}}, V_{\text{ceil}} \le 62]$.<br>• Nốt Canto 2 (`pitch_b`, móc kép `6`) nhận $V_{\text{canto2}} = \max(P.\text{floor\_calm} - 2,\; V_{\text{canto1}} - 2)$.<br>• 6 móc kép sóng chữ V (`support`) nhận mức miệng chữ V là $V_{\text{v\_top}} = \min\big(V_{\text{sup\_curve}}(t),\; V_{\text{canto2}} - 8\big) \in [20, 46]$, và đáy chữ V (`slot 3`) nhận $V_{\text{v\_top}} - 2 \ge 18$.<br>• Bass ngân 2 ô (`low`) nhận $\min(V_{\text{canto2}} - 4,\; \max(V_{\text{v\_top}} + 3,\; V_{\text{bass\_curve}}(t)))$. | Khi nốt Canto 1 tại đỉnh bài lọt Cổng Snap (`66..68`):<br>• Chỉ **Canto 1 (`pitch_a`)** nhận $V_{\text{snapped}} \in [66, 68]$.<br>• Canto 2 (`pitch_b`) giữ ở $\min(62,\; V_{\text{snapped}} - 4)$.<br>• Sóng chữ V `support` giữ nguyên `<= 46`. |

#### C. Công Thức Cổng Ép Dây Hiếm (`Rare Snap Gate` — Theo Từng Section, Luôn Rơi Vào `[66, V_snap]`)

1. **Điều kiện đủ để một cú gảy trở thành Ứng viên Snap (`Snap Candidate`)**:
   Một cú gảy (hoặc cụm nhát nhấn) tại thời điểm $t$ trong `section` chỉ được đưa vào danh sách ứng viên khi thỏa **cả 4 điều kiện**:
   - Pattern tại ô đó có $P.\text{snap\_wide} \ne \text{None}$ (tức $V_{\text{snap}}(\alpha_{\text{sec}}) \in [66, 76]$).
   - Section chứa ô đó có **$\alpha_{\text{sec}} \ge 0.25$** (các section đi ngang êm $\alpha_{\text{sec}} < 0.25$ có ngân sách snap bằng `0`, trừ trường hợp duy nhất là cú slap đặc trưng của `elogio_pizz`).
   - Năng lượng sóng tại thời điểm đó thỏa **$W(t) \ge 0.70$** *(bỏ điều kiện `or band == "f"` đứng riêng lẻ để không bao giờ xảy ra $W(t) < 0.70$ làm tử số âm)*.
   - Cú đó khớp với quy tắc `snap_targets` của pattern (xem Bảng Mục 3).

2. **Đơn vị Ngân sách (`Snap Unit`) & Hạn mức trên từng Section ($K_{\text{sec}}$)**:
   - **Một Đơn vị Ngân sách (`1 Snap Unit`)**:
     - Thông thường: là **1 cú tấn công trên Bè Hát Chính** (hoặc 1 khối hợp âm Fanfare / Sarabande beat 2 / Slap).
     - Với **`villa_pattern` (*Tresillo* `{0, 3, 6}`)**: cả bộ 3 nhát nhấn `{0, 3, 6}` trong cùng một ô `tresillo` được tính gộp là **1 đơn vị ngân sách (`1 Snap Unit`)** để không cắt cụt nhịp `3+3+2`.
   - **Ngân sách của từng Section có $\alpha_{\text{sec}} \ge 0.25$**:
     Đếm $N_{\text{mel, sec}}$ là số cú tấn công có cao độ của Bè Hát Chính **bên trong chính section đó** (`midi is not None and not tie_stop`; với `tremolo`, mỗi phách đen tính là 1 cú). Số đơn vị Snap tối đa của section đó là:
     $$K_{\text{sec}} = \min\Big(P.\text{max\_units\_per\_sec},\; \max\big(1,\; \lfloor 0.045 \cdot N_{\text{mel, sec}} \rfloor\big)\Big)$$
     *(Nhờ tính riêng trên từng section có $\alpha_{\text{sec}} \ge 0.25$, một chương `1M` có 2 section êm và 1 section sóng sẽ không bao giờ lấy số nốt của 2 section êm cộng dồn sang section sóng, và các section êm giữ đúng 0% snap).*
   - **Thứ tự lọc ứng viên trong mỗi Section**:
     1. Trong mỗi `Phrase` thuộc section, giữ tối đa `P.max_units_per_phrase` đơn vị ứng viên (mặc định `1`) có $W(t)$ cao nhất.
     2. Trên toàn section, xếp hạng các đơn vị ứng viên theo $W(t)$ giảm dần và giữ tối đa $K_{\text{sec}}$ đơn vị.

3. **Công thức tính $V_{\text{snapped}}$ (Bảo đảm luôn thuộc `[66, V_snap]`)**:
   Vì $W(t) \in [0.70, 1.00]$ và $V_{\text{snap}}(\alpha_{\text{sec}}) \ge 66$, đặt $V_{\text{snap\_min}} = \min\big(66,\; V_{\text{snap}}(\alpha_{\text{sec}})\big) = 66$:

   $$V_{\text{snapped}}(t) = \text{round}\left(66 + \big(V_{\text{snap}}(\alpha_{\text{sec}}) - 66\big) \cdot \frac{\text{clamp}(W(t), 0.70, 1.00) - 0.70}{0.30}\right) \in \big[66,\; V_{\text{snap}}(\alpha_{\text{sec}})\big]$$

   - Tại đúng ngưỡng mở cổng $W(t) = 0.70$: $V_{\text{snapped}} = 66$ (vượt qua ngưỡng `65` đúng 1 bậc, không bao giờ tụt xuống `63`).
   - Tại đỉnh sóng $W(t) = 1.00$: $V_{\text{snapped}} = V_{\text{snap}}(\alpha_{\text{sec}}) \in [66, 76]$.

#### D. Quy Tắc Xếp Tầng 3 Bè Khi Chạm Sàn `18` (`Simultaneous Voice Ordering & Floor Compression`)

Tại mọi thời điểm phát âm $t$, gọi $(v_{\text{top}}, v_{\text{mid}}, v_{\text{bot}})$ là 3 mức lực theo thứ tự phân cấp của pattern:
- Với pattern thường: $(\text{top}, \text{mid}, \text{bot}) = (\text{lead}, \text{low}, \text{support})$.
- Với `thumb_cantabile`: $(\text{top}, \text{mid}, \text{bot}) = (\text{low}, \text{lead}, \text{support})$.

Để vừa đảm bảo thứ tự nghiêm ngặt $v_{\text{top}} > v_{\text{mid}} > v_{\text{bot}}$ trên các cú gảy thường, vừa **không bao giờ đẩy nốt dưới đáy `18`** khi giai điệu thì thầm ở `22..24` (như `noviembre` hay `cantabile`):
1. **Khoảng cách mục tiêu thích ứng theo độ cao của $v_{\text{top}}$**:
   - Khi $v_{\text{top}} \ge 30$: yêu cầu $v_{\text{mid}} \le v_{\text{top}} - 3$ và $v_{\text{bot}} \le v_{\text{mid}} - 2$.
   - Khi $22 \le v_{\text{top}} < 30$ (vùng thì thầm $ppp$): thu khoảng cách tối thiểu về `2` đơn vị ($v_{\text{mid}} \le v_{\text{top}} - 2$ và $v_{\text{bot}} \le v_{\text{mid}} - 2$).
   - Nếu $v_{\text{top}} < 22$ mà tại đúng thời điểm đó có đủ cả 3 bè cùng kêu: nâng nhẹ $v_{\text{top}} = \max(v_{\text{top}}, 22)$, $v_{\text{mid}} = \min(v_{\text{mid}}, v_{\text{top}} - 2) \ge 20$, $v_{\text{bot}} = \min(v_{\text{bot}}, v_{\text{mid}} - 2) \ge 18$. (Nếu chỉ có 1 hoặc 2 bè cùng kêu, $v_{\text{top}}$ được xuống tới `20` và bè kia ở `18`).
2. **Ba ngoại lệ hợp lệ của thứ tự bè**:
   - **`bach_fuga`**: cho phép $\text{lead} \ge \text{low}$ (khoảng cách `>= 0` khi Bass đang hát Subject/Answer và Soprano giữ nốt dài, hoặc `lead >= low + 1` khi cả hai cùng gảy), và cả hai luôn $\ge \text{support} + 2$.
   - **`thumb_cantabile` dyad**: $\text{low} \ge \text{lead} + 4$ và giữa hai nốt dyad chập phách yếu: $\text{lead} \ge \text{support} + 1$ (khi $\text{lead} \ge 20$, $\text{support} \ge 18$).
   - **Khối chập accent đồng thời (Block Accent / Frame Chord)**: khi cả 3 bè cùng là một cú hợp âm khối đồng bộ (Fanfare của Sor, Stab/Slap của Brouwer, hoặc hợp âm khối trong `guitar_frame.py`), cho phép $v_{\text{top}} \ge v_{\text{mid}} \ge v_{\text{bot}}$.

---

## 3. Bảng Khóa Thông Số Theo Từng `(ensemble, pattern)` (`PatternWaveProfile`) Cho 5 Đại Sư

Khóa tra cứu là tuple **`(ensemble, pattern)`** (để tách biệt hoàn toàn `("barrios", "thumb_cantabile")` và `("villa", "thumb_cantabile")`). Mọi dòng đều thỏa `floor_calm <= floor_wide` và `ceil_calm <= ceil_wide <= 63`:

```python
@dataclass(frozen=True)
class PatternWaveProfile:
    floor_calm: int            # Sàn bè hát khi section êm (alpha = 0), >= 20
    floor_wide: int            # Sàn bè hát khi section sóng lớn (alpha = 1), >= floor_calm
    ceil_calm: int             # Trần ấm bè hát khi section êm (alpha = 0), <= 60
    ceil_wide: int             # Trần ấm bè hát khi section sóng lớn (alpha = 1), <= 63
    snap_calm: int | None      # Trần ép dây khi vừa qua ngưỡng (None nếu cấm ép dây, >= 66 nếu có)
    snap_wide: int | None      # Trần ép dây tối đa khi alpha = 1 (68..76)
    bass_floor: int            # Sàn bè trầm (hoặc bè lead đệm ở thumb_cantabile)
    bass_ceil: int             # Trần ấm bè trầm (<= 60)
    sup_floor: int             # Sàn bè trung (>= 18)
    sup_ceil: int              # Trần ấm bè trung (<= 52)
    gamma: float               # Độ võng đường cong E(t) = W(t)^gamma
    max_units_per_phrase: int  # Số đơn vị Snap tối đa trong 1 Phrase (0 hoặc 1)
    max_units_per_sec: int     # Trần tuyệt đối số đơn vị Snap trong 1 Section (0..4)
    snap_targets: str          # Quy tắc chọn cú được phép qua cổng Snap
```

### Bảng Đầy Đủ 26 Khóa `(ensemble, pattern)` Của 5 Đại Sư

| Khóa `(ensemble, pattern)` | Bè Hát `[floor_calm..ceil_calm]` $\to$ `[floor_wide..ceil_wide]` | Trần Snap `[snap_calm..snap_wide]` | Bè Trầm `[bass_floor..bass_ceil]` | Bè Trung `[sup_floor..sup_ceil]` | $\gamma$ | Hạn mức `(per_phrase, per_sec)` | Danh sách cú được phép Snap (`snap_targets`) |
|---|---|---|---|---|---|---|---|
| `("bach", "bach_sarabande")` | `26 .. 56` $\to$ `30 .. 62` | `None` *(0% snap)* | `24 .. 56` | `20 .. 46` | `1.30` | `(0, 0)` | Không ép dây; phách 2 + mordent nở ấm tối đa ở `62`. |
| `("bach", "bach_gavotte")` | `28 .. 58` $\to$ `32 .. 62` | `66 .. 68` | `26 .. 58` | `22 .. 48` | `1.20` | `(1, 2)` | Chỉ phách 1 đầu câu đỉnh khi `phrase.rise >= 3`. |
| `("bach", "bach_bourree")` | `28 .. 58` $\to$ `32 .. 63` | `66 .. 68` | `26 .. 58` | `22 .. 48` | `1.15` | `(1, 3)` | Chỉ nốt `phrase.apex` sau cặp lấy đà khi `rise >= 3`. |
| `("bach", "bach_fuga")` | `28 .. 58` $\to$ `32 .. 63` | `66 .. 68` | `26 .. 61` *(Subject)* | `20 .. 46` | `1.15` | `(1, 2)` | Chỉ đỉnh `phrase.apex` của Soprano ở câu cao trào. |
| `("bach", "bach_gigue")` | `28 .. 58` $\to$ `32 .. 63` | `68 .. 70` | `26 .. 58` | `22 .. 50` | `1.15` | `(1, 3)` | Nốt đầu câu chạy scale hoặc phách mạnh `down` tại đỉnh. |
| `("bach", "bach_chaconne")` | `26 .. 58` $\to$ `30 .. 63` | `68 .. 70` | `24 .. 58` | `20 .. 48` | `1.25` | `(1, 3)` | Duy nhất nốt đích cuối câu chạy scale breakout (`accent=True`). |
| `("classic", "cantabile")` | `24 .. 54` $\to$ `28 .. 58` | `None` *(0% snap)* | `20 .. 46` | `18 .. 48` *(3rd/6th)* | `1.35` | `(0, 0)` | Không ép dây; song thanh quãng 3/6 ấm tuyệt đối. |
| `("classic", "elegiaque")` | `24 .. 56` $\to$ `28 .. 62` | `66 .. 68` | `22 .. 56` | `18 .. 46` | `1.30` | `(1, 2)` | Chỉ nốt tựa *appoggiatura* (`accent=True`) ở câu đỉnh. |
| `("classic", "study")` | `26 .. 56` $\to$ `30 .. 63` | `68 .. 70` | `24 .. 58` | `20 .. 50` | `1.20` | `(1, 2)` | Khối Fanfare mở đoạn `f` hoặc đích scale `Grand Solo level 2` (hoặc `phrase.apex` khi `rally`). |
| `("classic", "mozart_var")` | `26 .. 56` $\to$ `30 .. 62` | `66 .. 68` | `24 .. 56` | `20 .. 50` | `1.20` | `(1, 2)` | Chỉ đỉnh `phrase.apex` khi câu leo dốc mạnh (`rise >= 3`). |
| `("classic", "galop")` | `28 .. 58` $\to$ `32 .. 63` | `68 .. 70` | `26 .. 58` | `22 .. 50` | `1.10` | `(1, 3)` | Phách mạnh mở câu đỉnh ở phiên `rally` biên độ rộng. |
| `("barrios", "preludio")` | `26 .. 56` $\to$ `30 .. 62` | `66 .. 68` | `22 .. 54` | `18 .. 46` *(V-wave)* | `1.40` | `(1, 2)` | Tối đa 2 nốt Canto 1 (`pitch_a`) tại đỉnh cao nhất của section. |
| `("barrios", "andante")` | `24 .. 54` $\to$ `28 .. 60` | `None` *(0% snap)* | `22 .. 54` | `18 .. 46` | `1.35` | `(0, 0)` | Thánh ca nhà thờ ấm áp, không ép dây. |
| `("barrios", "thumb_cantabile")` | `26 .. 56` $\to$ `30 .. 62` *(trên `low`)* | `66 .. 68` *(trên `low`)* | `20 .. 44` *(trên `lead`)* | `18 .. 40` | `1.35` | `(1, 2)` | Chỉ 1–2 nốt ngón cái `low` tại đỉnh câu cao trào. |
| `("barrios", "tremolo")` | `28 .. 58` $\to$ `32 .. 63` *(trên `thumb`)* | `68 .. 72` *(chỉ `thumb` & `m`)* | *(đi theo `thumb`)* | `22 .. 50` | `1.30` | `(1, 2)` | Phách đỉnh của ô cao trào nhất; `a, i` kẹp cứng `<= 63`. |
| `("barrios", "choro")` | `28 .. 58` $\to$ `32 .. 63` | `70 .. 74` | `26 .. 58` | `22 .. 50` | `1.15` | `(1, 4)` | Cú nhấn lệch phách `accent=True` / `phrase.apex` tại đỉnh sóng. |
| `("barrios", "polca")` | `28 .. 58` $\to$ `32 .. 63` | `70 .. 72` | `26 .. 58` | `22 .. 50` | `1.15` | `(1, 3)` | Cú nhấn lệch phách `accent=True` tại đỉnh sóng. |
| `("barrios", "hemiola")` | `28 .. 58` $\to$ `32 .. 63` | `70 .. 74` | `26 .. 58` | `22 .. 50` | `1.15` | `(1, 4)` | Phách hemiola `accent=True` tại đỉnh sóng. |
| `("barrios", "vals")` | `26 .. 58` $\to$ `30 .. 62` | `68 .. 72` | `24 .. 56` | `20 .. 48` | `1.20` | `(1, 3)` | Phách syncopation beat 2 (`eighth == 4`, `accent=True`) tại đỉnh sóng. |
| `("villa", "chord_melody")` | `24 .. 54` $\to$ `28 .. 60` | `None` *(0% snap)* | `22 .. 54` | `18 .. 48` | `1.35` | `(0, 0)` | Hợp âm khối ngân ấm, không ép dây. |
| `("villa", "thumb_cantabile")` | `28 .. 58` $\to$ `32 .. 63` *(trên `low`)* | `68 .. 70` *(trên `low`)* | `22 .. 46` *(trên `lead`)* | `20 .. 42` | `1.25` | `(1, 2)` | Đỉnh câu ngón cái `low` ở phiên biến động lớn. |
| `("villa", "villa_pattern")` | `26 .. 58` $\to$ `30 .. 63` | `68 .. 72` | `24 .. 58` | `20 .. 50` | `1.20` | `(1, 3)` | Bộ 3 nhát *Tresillo* `{0, 3, 6}` (tính gộp là 1 đơn vị) hoặc `phrase.apex`. |
| `("villa", "etude1")` | `28 .. 58` $\to$ `32 .. 63` | `68 .. 70` | `24 .. 58` | `22 .. 52` | `1.20` | `(1, 2)` | Nốt hát (`index 7, 9`) tại đúng ô đỉnh cao trào của section. |
| `("villa", "etude11")` | `28 .. 58` $\to$ `32 .. 63` | `70 .. 74` | `24 .. 58` | `22 .. 50` *(sextuplets)* | `1.20` | `(1, 3)` | Chỉ cú 1 `lead` tại phách `phrase.apex` (các phách khác gỡ `accent`). |
| `("brouwer", "noviembre")` | `22 .. 52` $\to$ `26 .. 58` | `None` *(0% snap)* | `20 .. 50` | `18 .. 42` | `1.45` | `(0, 0)` | Tuyệt đối 0% ép dây (`22 > 20 > 18` khớp sàn 3 bè). |
| `("brouwer", "sarabande")` | `24 .. 56` $\to$ `28 .. 62` | `68 .. 72` | `22 .. 56` | `18 .. 48` | `1.35` | `(1, 2)` | Chỉ hợp âm nhấn phách 2 tại đỉnh cao trào; swarm giữ `<= 62`. |
| `("brouwer", "brouwer_etude")` | `24 .. 58` $\to$ `28 .. 63` | `68 .. 72` | `22 .. 58` *(tumbao)* | `20 .. 50` | `1.15` | `(1, 3)` | Cú nhấn downbeat/tumbao (`accent=True`) ở các ô đỉnh sóng. |
| `("brouwer", "elogio_pizz")` | `24 .. 56` $\to$ `28 .. 62` | `72 .. 76` *(Bartók slap)* | `22 .. 56` | `20 .. 48` | `1.15` | `(1, 4)` | Cú vỗ *Bartók slap* ở móc đơn thứ 3 (`slap = start + 3`, `lead 72..76, low 68..70, sup 64..66`). |

---

## 4. Đường Cong Riêng Cho Khung Intro & Outro (`guitar_frame.py`)

Trong code hiện tại, `guitar_frame.py` đặt `_PP = 46`, `_P = 50`, `_MP = 56`, `_MF = 64` (kể cả `_edge_stab` và `_stab_and_ring` của Brouwer cũng đang viết ở `_MF = 64`), và các ô `pedal` bị `_shape_dynamics` bỏ qua.

Khi đưa vào `apply_guitar_wave()`:
1. **Các ô `pedal` (`intro`, `warmup`, `outro`, `cooldown`) đi đường bao riêng (Frame Envelope), không đi qua Cổng Snap của thân bài**:
   - Bảo toàn cấu trúc chênh lệch tương đối giữa các nốt bên trong từng cử chỉ của `guitar_frame.py` (ví dụ contour chuông `44, 50, 46` hay cantabile `46 -> 52` của Barrios).
   - **Intro (`leading` bars)**: Ánh xạ từ mức khởi âm **$ppp - pp$ (`22..32` ở đầu ô 0)** tăng dần lên khớp với mức mở đầu thân bài ($V_{\text{hat}}(t_{\text{body\_start}}) \approx 34..48$). Không một nốt thường nào trong Intro vượt quá `56`.
   - **Outro (`trailing` bars)**: Áp dụng hàm suy giảm mũ (**Morendo Curve**) từ mức cuối thân bài hạ dần về **`20..26` ($ppp$)** ở ô cuối cùng (hợp âm chuông / Picardy third tan dần).
2. **Một bộ số thống nhất cho các cú Stab kịch tính trong Frame (`70 / 66 / 62`, thấp hơn Bartók slap `72..76` của thân bài)**:
   - Tại nhánh kịch tính `edge == True` của Brouwer (`_edge_stab` ở đầu Intro và `_stab_and_ring` ở cuối Outro) và nhánh `bright == True` (`_stabs` ở cuối Outro của Villa): các nốt mang đồng thời `staccato=True` và `accent=True` (hoặc thuộc `_stabs` cuối bài) được gán **một bộ số duy nhất**:
     - `lead`: **`70`**
     - `low`: **`66`**
     - `support`: **`62`** (giữ dưới ngưỡng `65`)
   - Nhờ đó, cú stab ở khung Intro/Outro sắc gọn (`70 / 66 / 62`) nhưng luôn đứng thấp hơn cú vỗ *Bartók slap* ở đỉnh thân bài `elogio_pizz` (`72..76 / 68..70 / 64..66`).

---

## 5. Lộ Trình Triển Khai 5 Bước (Implementation Order)

1. **Bước 1 — Khóa bảng `PatternWaveProfile` theo khóa `(ensemble, pattern)` trong `backend/app/sonify/guitar_wave.py`**:
   - Khai báo đầy đủ 28 cặp `(ensemble, pattern)` của 5 đại sư với `floor_calm <= floor_wide`, `ceil_calm <= ceil_wide <= 63`, `snap_calm / snap_wide`, `max_units_per_phrase`, `max_units_per_sec`, `gamma`, và `snap_targets`.
   - Viết hàm tính $\alpha_{\text{sec}}$ theo từng `FormSection` (bão hòa ở `2.4%`), sóng $W_{\text{macro}}(t)$ (xử lý an toàn section ngắn `< 4` ô và section phẳng `PriceEnv = 0.5`), sóng câu $W_{\text{phrase}}(t)$ (raised-cosine, nhân `0.35` một lần cho câu phẳng), và sóng thanh khoản $W_{\text{band}}(t)$.

2. **Bước 2 — Viết bộ Rebase `apply_guitar_wave()` thay thế `_shape_dynamics()` sau khi pattern đã sinh nốt**:
   - Xử lý riêng từng nhóm cấu trúc:
     - **`tremolo`**: dùng đúng `_TREMOLO_QUARTER_OFFSETS` (`(-4, 0, +4, +1)` cho 4/4; `(-4, +4, 0)` cho 3/4 và 6/8) và `_TREMOLO_FILL_OFFSETS` (`(-6, -3, -4, -6)`).
     - **`etude1`**: giữ `_ETUDE1_ARC`, tính bass theo `min(61, max(max_sup_in_bar + 2, lead - 4))`.
     - **`etude11`**: giữ cả `arch = {1:-10, 2:-6, 4:-7, 5:-10}` lẫn `_ETUDE11_TILT = {1:-1, 2:-1, 4:0, 5:+1}`, gỡ `accent` ở các phách thường.
     - **`preludio`**, **`thumb_cantabile`** và các pattern thường: rebase theo 3 đường cong và chạy pass nén khoảng cách khi chạm sàn `18` (`gap = 2` ở vùng $ppp$).
     - **Khung `pedal` (`intro`/`outro`)**: chạy đường bao Emergence / Morendo riêng; gán bộ số thống nhất `70 / 66 / 62` cho các cú stab kịch tính.
   - Chạy **Cổng Snap (`Rare Snap Gate`)** trên từng section có $\alpha_{\text{sec}} \ge 0.25$ và $W(t) \ge 0.70$, ánh xạ vào `[66, V_snap]`, tính *Tresillo* `{0, 3, 6}` là 1 đơn vị ngân sách, và kẹp cứng các nốt đệm đi kèm trong cụm ở `<= 63`.
   - Đồng bộ toàn bộ các nốt nối dây (`tie_stop=True` nhận đúng velocity của cú `tie_start` mở chuỗi).

3. **Bước 3 — Thêm chốt chặn hậu kiểm sau `humanize()` cho cả 2 vùng Ấm và Snap**:
   - Trên đường guitar (`score.variant == "guitar"`):
     - Mọi nốt có `written_velocity <= 64` trước `humanize` được kẹp `heard_velocity = min(64, heard_velocity)`.
     - Mọi nốt đã được Snap (`written_velocity >= 65`) được kẹp `heard_velocity = max(66, min(76, heard_velocity))` để `humanize` không đẩy vượt trần `76` khi gặp một cụm snap đồng lực.

4. **Bước 4 — Viết `backend/tests/test_guitar_wave.py` và cập nhật `backend/tests/test_sonify_guitar.py`**:
   - Cập nhật các assertion số tuyệt đối cũ (`56, 60, 64, 72`) trong `test_sonify_guitar.py` sang kiểm tra khoảng động lực học mới và cấu trúc tương đối.
   - Trong `test_guitar_wave.py`, kiểm tra đủ 6 tiêu chí theo đúng `PatternWaveProfile`:
     1. **Phiên `calm` biên độ hẹp ($\alpha_{\text{sec}} < 0.25$)**: có nốt xuống vùng $ppp - pp$ (`<= 34`) và **100% số nốt sau `humanize` nằm ở `<= 64`** (trừ `elogio_pizz` slap).
     2. **Phiên biến động rộng ($\alpha_{\text{sec}} \ge 0.50$) kiểm tra theo `PatternWaveProfile`**:
        - Với các pattern có `snap_wide is None` (`cantabile`, `andante`, `chord_melody`, `noviembre`, `bach_sarabande`): **0% số nốt vượt `64`** kể cả trong phiên `rally` / `volatile`.
        - Với các pattern có `snap_wide is not None`: có ít nhất `1` đơn vị Snap rơi vào `[66, P.snap_wide]`, số đơn vị Snap không vượt quá `K_sec`, và không nốt nào sau `humanize` vượt quá `76` (hoặc `70` với Bach/Sor).
     3. **Bảo toàn delta vi mô ở vùng ấm**: trong một ô `tremolo` ấm, 4 phách giữ đúng hiệu số `(-4, 0, +4, +1)` (hoặc `(-4, +4, 0)` ở 3/4, 6/8) và ngón cái lớn hơn `m` đúng `3`; trong `etude1`, bass luôn nằm giữa `support` và `lead` kể cả khi `lead` thì thầm ở `32`; trong `etude11`, 4 nốt sextuplet giữ nguyên hình vòm `arch + tilt` dưới `50`.
     4. **Cụm Snap không kéo nốt đệm qua `65`**: tại phách `tremolo` hoặc `etude11` được snap (`68..74`), các móc kép `a, i` của tremolo và 4 nốt sextuplet giữa của `etude11` vẫn `<= 63` (và `<= 50`).
     5. **$\alpha_{\text{sec}}$ và ngân sách Snap tách biệt theo từng section trên `1M`**: một chương `1M` có section đi ngang ($\alpha_{\text{sec}} = 0$) và section biến động mạnh ($\alpha_{\text{sec}} = 1$) giữ 0% snap ở section đi ngang và không dồn ngân sách của section đi ngang sang section biến động.
     6. **Bất biến thứ tự bè đồng thời**: `lead > low > support` trên các cú gảy thường (kể cả khi chạm sàn `18..22` của `noviembre` và `cantabile`), cho phép `>=` trên các khối accent đồng thời / `bach_fuga`, và `low > lead > support` trên `thumb_cantabile`.

5. **Bước 5 — Thực nghiệm nghe 3 mốc `24 / 64 / 74` trên MS Basic Nylon trước khi bump Revision**:
   - Trước khi tăng `RECAP_REVISION` và `SPAN_REVISION` trong `backend/app/sonify/audio.py`, xuất WAV khô thử nghiệm với 3 mức velocity `24` ($ppp$), `64` (trần ấm), và `74` (đỉnh snap) qua `musescore_export` trên MS Basic Nylon để kiểm tra độ rõ trên nền `_GUITAR_NOISE = 0.0003` và độ tách lớp mẫu giữa `64` và `74`.
