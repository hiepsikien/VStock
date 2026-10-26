# Kế Hoạch Thiết Kế Filter Uốn Sóng Động Lực Học (Wave) & Mở Rộng Biên Độ ($ppp \to f$) Cho 5 Đại Sư Guitar

> **Mục tiêu**: Đưa tiếng đàn guitar cổ điển thoát khỏi dải hẹp $mp - mf$ (`44..78`) hiện tại bằng cách **thay thế (rebase) vận tốc đã viết quanh `64/72` bằng đường sóng động lực học**, mở rộng chiều sâu về phía **thì thầm / gần gũi ($ppp - pp$, velocity `20..38`)**, giữ **100% các nốt sóng thường trong vùng dây nylon ấm (`<= 63` trước humanize, `<= 64` sau humanize)**, và cấp phát ngân sách **ép dây hiếm (`66..76`, $\le 3-5\%$ số cú tấn công của bè hát)** chỉ cho đúng những cú nhấn thuộc các pattern thực sự cần lực tì dây.
>
> **Liên kết**: [`docs/sonify-classical-guitar.md`](./sonify-classical-guitar.md), [`docs/sonify-barrios-tremolo-dynamics.md`](./sonify-barrios-tremolo-dynamics.md), [`docs/sonify-humanize-preset-plan.md`](./sonify-humanize-preset-plan.md).

---

## 1. Chẩn Đoán Hiện Trạng Trong Codebase

Qua khảo sát toàn bộ pipeline guitar (`guitar.py`, `guitar_patterns.py`, `guitar_barrios.py`, `guitar_villa.py`, `guitar_frame.py`, `humanize.py`), lực gảy hiện tại đang bị nén trong dải hẹp do **4 nguyên nhân**:

| Điểm nghẽn trong Code | Vị trí & Con số thực tế đang chạy | Hệ quả âm thanh |
|---|---|---|
| **1. Nền giai điệu & đệm đặt sẵn ngay sát ngưỡng ép dây (`65`)** | • `_MELODY = 64`, `_MELODY_APEX = 72`<br>• `_SWELL_OPEN = 60`, `_SWELL_MID = 68`, `_SWELL_CLOSE = 62`<br>• `_BAND_SUPPORT = 50..60`, `_BAND_BASS = 54..64`<br>• `etude1` / `etude11`: `_ETUDE_OPEN = 60`, `_ETUDE_PEAK = 72`, sàn nốt giữa `44`, mỗi phách đen của `etude11` đều gắn `accent=True` | Ngay từ lúc sinh nốt, giai điệu đã đứng ở `60..72` (ngay sát hoặc vượt ngưỡng móng `65`). Không có nốt nào được viết ở $ppp$ (`~20..26`) hay $pp$ (`~28..36`). |
| **2. `_shape_dynamics` cộng thêm lên nền `64` và kẹp cứng `[44, 78]`** | `guitar_patterns.py` dòng 2906–2931:<br>• `if event.velocity >= _MELODY_APEX: continue`<br>• `velocity = max(44, min(78, event.velocity + delta + extra))`<br>• `_punch` cộng `+8` hoặc `+12` rồi kẹp `min(88, ...)`<br>• *La Catedral* khóa `lead` ở `54..64`, `support` ở `48..55` | • Lấy `event.velocity` (`~64`) làm tâm rồi cộng `_BAND_DELTA` (`-12..+4`) và `extra` (`0..+4`), cộng thêm sàn `44`, khiến bản nhạc không thể xuống được $ppp - pp$.<br>• Nếu chỉ gỡ `max(44, min(78, ...))` mà không rebase lại tâm thì chỉ đẩy thêm nốt lên vùng móng.<br>• `etude1`, `etude11`, `tremolo` đang đứng ngoài `_shape_dynamics`. |
| **3. Thiếu sóng thở theo dữ liệu giá ở cấp Section** | • `swell(phrase, onset)` là tam giác tuyến tính trong 1 câu ngắn (2–4 ô), chỉ cộng `round(4 * swell)`.<br>• Khung `guitar_frame.py` viết cứng `_PP = 46`, `_P = 50`, `_MP = 56`, `_MF = 64` (stab của Brouwer cũng là `_MF = 64`) và các ô pedal bị `_shape_dynamics` bỏ qua. | Các đoạn dài 30 ô (`1D`) hay 80–200 ô (`1W`, `1M`, `3M`, `1Y`) thiếu độ lượn theo đường giá vĩ mô và thiếu độ mở/tắt tự nhiên ở biên section. |
| **4. Chưa tách bạch 3 ngưỡng trần: Trần Thường (`<= 63`), Trần Sau Humanize (`<= 64`) và Trần Snap (`66..76`)** | `humanize.py` dùng chung cho cả 5 dòng nhạc, nhích `{-2, -1, 0, +1, +2}` và chỉ kẹp `1..127`, không biết ngưỡng `65` của nylon. | Một nốt ấm ở `63–64` khi qua `humanize` cộng `+2` sẽ trượt sang `65–66`, vô tình kích hoạt lớp sample móng gắt trên MS Basic. |

### Quy ước 3 vùng âm sắc trên MS Basic Nylon (`MuseScore_General.sf3`)

Trên MS Basic, `NoteEvent.velocity` xuất ra MusicXML thành `<note dynamics="V * 100 / 90">`:
1. **Vùng Thì Thầm / Intimate — $ppp$ đến $pp$ (`velocity 20..38`)**: Tiếng dây nylon mềm, tròn, ấm (*sul tasto / dolcissimo*).
2. **Vùng Tự Sự Ấm — $p$ đến $mp+$ (`velocity 40..64`, nghiêm ngặt `< 65`)**:
   - **Mọi nốt không gắn cờ Snap** bắt buộc dừng ở **`<= 63` trước `humanize`** và được kẹp cứng ở **`<= 64` sau `humanize`**.
   - Khi mở đáy xuống `20..32`, chỉ riêng dải ấm `20..63` đã rộng hơn **40 đơn vị MIDI** mà không hề chạm vào tiếng móng gắt.
3. **Vùng Ép Dây Hiếm — $mf+$ đến $f$ (`velocity 66..76`, tuyệt đối `<= 76`)**:
   - Chỉ dành cho các cú nhấn đã lọt qua **Cổng Snap (`Rare Snap Gate`)** trên những pattern có kỹ thuật tì dây / giật dây thật (*Bartók slap*, *Tresillo*, *Etude 11 climax*, *Choro / Hemiola sync*, *Tremolo climax*, *Grand Solo fanfare*, *Chaconne scale arrival*).

---

## 2. Mô Hình Toán Học & Cơ Chế Rebase Của Filter (`guitar_wave.py`)

### 2.1. Vị trí trong Pipeline & Tương tác với `humanize`

```text
render_patterned_voices()
  ├── 1. Sinh nốt theo Pattern & Frame (giữ nguyên cấu trúc tương đối giữa các ngón p-i-m-a)
  ├── 2. _repair() & _resolve() & _slur()
  ├── 3. apply_guitar_wave()  <-- Rebase toàn bộ velocity vào cửa sổ [V_floor, V_ceil <= 63] + cấp phát Snap [66..76]
  └── 4. humanize(score)      <-- Ở audio.py: sau khi humanize, chạy bước clamp hậu kiểm cho guitar:
                                  mọi nốt có velocity_trước_humanize <= 64 đều bị kẹp min(64, velocity_sau_humanize)
```

> **Lưu ý về Unit Test hiện hữu (`test_sonify_guitar.py`)**:
> Mọi lệnh gọi `render(..., variant="guitar")` đều đi qua cuối `render_patterned_voices()`. Do đó, khi thay `_shape_dynamics` bằng `apply_guitar_wave()`, các test trong `test_sonify_guitar.py` đang khóa cứng số tuyệt đối (`56`, `60`, `64`, `72`) trên kết quả `render()` **sẽ thay đổi và cần được cập nhật** sang kiểm tra: (a) delta tương đối bên trong vòm/cụm ngón, (b) bất biến thứ tự giữa các bè trong cùng một cú đánh, và (c) biên độ nằm trong cửa sổ của `PatternWaveProfile`.

---

### 2.2. Bước 1: Tính Hệ Số Mở Biên $\alpha_{\text{sec}} \in [0.0, 1.0]$ Theo Từng Section

Không dùng một `rel_span` của cả bài cho các bản dài (`1W`, `1M`, `3M`, `1Y`), vì biên độ cả tuần/tháng luôn vượt `2.8%` và sẽ làm $\alpha = 1.0$ bão hòa suốt cả chương. Thay vào đó, tính $\alpha_{\text{sec}}$ riêng cho **từng `FormSection` thân bài** (dùng `_section_rel_span(bars, groups, section.start, section.end)` đã có trong `render.py`; với bài `1D` chỉ có 1 thân bài thì chính là `rel_span` của phiên):

$$\alpha_{\text{sec}} = \text{clamp}\left(\frac{\text{rel\_span}_{\text{sec}} - 0.004}{0.024 - 0.004},\; 0.0,\; 1.0\right)$$

**Quy tắc co giãn cửa sổ $[V_{\text{floor}}, V_{\text{ceil}}]$ đồng nhất (Phiên êm thu về phía thì thầm, phiên sóng nới sàn lên `pp` và mở trần tới `ceil_wide <= 63`)**:

Với hồ sơ `P = PatternWaveProfile` của pattern đang chạy tại ô nhịp đó (trong đó `P.floor_calm <= P.floor_wide` và `P.ceil_calm <= P.ceil_wide <= 63`):

$$\begin{aligned}
V_{\text{floor}}(\alpha_{\text{sec}}) &= \text{round}\big(P.\text{floor\_calm} + \alpha_{\text{sec}} \cdot (P.\text{floor\_wide} - P.\text{floor\_calm})\big) \\
V_{\text{ceil}}(\alpha_{\text{sec}})  &= \text{round}\big(P.\text{ceil\_calm}  + \alpha_{\text{sec}} \cdot (P.\text{ceil\_wide}  - P.\text{ceil\_calm})\big) \\
V_{\text{snap}}(\alpha_{\text{sec}})  &= \begin{cases}
\text{None}, & \text{nếu } P.\text{snap\_wide} \text{ là None} \\
\text{round}\big(P.\text{snap\_calm} + \alpha_{\text{sec}} \cdot (P.\text{snap\_wide} - P.\text{snap\_calm})\big), & \text{ngược lại}
\end{cases}
\end{aligned}$$

- **Khi section êm ($\alpha_{\text{sec}} \approx 0$)**: Cửa sổ hạ thấp về phía thì thầm $[P.\text{floor\_calm},\; P.\text{ceil\_calm}]$ (ví dụ `22..54` hoặc `26..56`), và ngân sách snap bằng `0` khi $\alpha_{\text{sec}} < 0.25$ (trừ cú slap cố định của `elogio_pizz`).
- **Khi section có sóng lớn ($\alpha_{\text{sec}} \to 1$)**: Sàn giữ ở mức $pp$ rõ nét (`P.floor_wide`, ví dụ `26..32`), trần sóng thường mở lên `P.ceil_wide` (**luôn `<= 63`**), và mở ngân sách snap tại mức $V_{\text{snap}} \in [66, 76]$.

---

### 2.3. Bước 2: Tổng Hợp Sóng Đa Tầng $W(t) \in [0.0, 1.0]$

Tại mỗi vị trí thời gian $t$ (tính theo móc đơn thực `eighth = bar * epb + beat * 2`), năng lượng sóng là tổ hợp của 3 thành phần:

$$W(t) = \text{clamp}\Big(w_{\text{macro}} \cdot W_{\text{macro}}(t) \;+\; w_{\text{phrase}} \cdot W_{\text{phrase}}(t) \;+\; w_{\text{band}} \cdot W_{\text{band}}(t),\; 0.0,\; 1.0\Big)$$

với trọng số cố định $w_{\text{macro}} = 0.45,\; w_{\text{phrase}} = 0.35,\; w_{\text{band}} = 0.20$:

1. **Sóng Vĩ Mô $W_{\text{macro}}(t) \in [0, 1]$ (Đi theo Đường Giá Đã Làm Mượt + Mờ Biên Section)**:
   - Không dùng $0.65 \cdot \sin(\pi \tau)$ làm nguồn năng lượng chính (vì $\sin(\pi \tau)$ ép mọi section `selloff` hay cao trào đầu đoạn phải phình to ở chính giữa).
   - Thay vào đó, **nguồn năng lượng vĩ mô là đường bao giá làm mượt $\widetilde{\text{PriceEnv}}(t) \in [0, 1]$** (trung bình trượt cửa sổ 3 ô nhịp của cao độ giai điệu chuẩn hóa trong section; ở section `selloff` nơi giá lao dốc tạo kịch tính, lấy $\max\big(\widetilde{\text{PriceEnv}}(t),\; 0.75 \cdot (1 - \widetilde{\text{PriceEnv}}(t))\big)$ để đáy bán tháo sâu vẫn có năng lượng sóng mà không ép đỉnh ở giữa section).
   - Hàm hình thang bo tròn bằng cosine ở hai biên $T_{\text{edge}}(\tau) \in [0, 1]$ chỉ đóng vai trò **làm mờ 2 ô đầu và 2 ô cuối của section** (tăng từ `0.25 -> 1.0` ở 2 ô đầu và hạ `1.0 -> 0.25` ở 2 ô cuối):
     $$W_{\text{macro}}(t) = \kappa_{\text{sec}} \cdot T_{\text{edge}}(\tau_{\text{section}}) \cdot \Big(0.25 + 0.75 \cdot \widetilde{\text{PriceEnv}}(t)\Big)$$
   - Hệ số $\kappa_{\text{sec}} = 0.65$ khi section là `trio` hoặc `bridge` mang pattern nội tâm (`cantabile`, `thumb_cantabile`, `noviembre`, `andante`), ngược lại $\kappa_{\text{sec}} = 1.0$.

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
     $$\text{score}(\text{bar}) = \text{ clamp}\Big(\text{band\_val}\big(\text{band}(\text{bar})\big) + \text{mood\_nudge}\big(\text{mood}(\text{bar})\big),\; 0.0,\; 1.0\Big)$$
     với `band_val = {"p": 0.0, "mp": 0.33, "mf": 0.67, "f": 1.0}` và `mood_nudge = {"calm": -0.10, None: 0.0, "selloff": +0.05, "rally": +0.10, "volatile": +0.15}` (đọc từ `ctx.mood(bar)` tức đã gồm `character_at[bar]`).

---

### 2.4. Bước 3: Công Thức Rebase Vận Tốc, Bảo Toàn Vòm Vi Mô & Cổng Snap

Với hệ số uốn $\gamma = P.\gamma$ của pattern đang chạy, năng lượng sau uốn là:

$$E(t) = \big(W(t)\big)^{\gamma} \in [0.0, 1.0]$$

#### A. Rebase đường chuẩn Bè Hát Chính (`V_hat`) vào cửa sổ ấm `[V_floor, V_ceil <= 63]`

Sóng **thay thế hoàn toàn** nền `64/72` cũ theo công thức:

$$V_{\text{hat}}(t) = V_{\text{floor}} + E(t) \cdot \big(V_{\text{ceil}} - V_{\text{floor}}\big)$$

Trong đó **Bè Hát Chính** là:
- Voice 3 (`low`) đối với pattern `thumb_cantabile`.
- Voice 1 (`lead`) đối với tất cả các pattern còn lại.

#### B. Bảo toàn Delta Vi Mô ($\Delta_{\text{micro}}$) và Tách Cổng Snap khỏi Nốt Đệm trong Cụm

Với các pattern có vòm nội bộ được thiết kế sẵn trong ô/phách, mỗi nốt được tách thành **Mức chuẩn của ô/cụm ($V_{\text{anchor}}$)** cộng với **Độ lệch vi mô ($\Delta_{\text{micro}} \le 0$)**:

| Pattern | Nốt mốc $V_{\text{anchor}}$ trong code gốc | Độ lệch vi mô $\Delta_{\text{micro}}$ của các nốt còn lại trong cụm | Quy tắc Rebase ở vùng ấm & Quy tắc khi Mốc được Snap |
|---|---|---|---|
| **`tremolo`** | Ngón cái `thumb` của phách đó (`level = 54, 58, 62, 59` + arch) | • Nốt màu đổi hợp âm (`support`): `0`<br>• 4 móc kép `a-m-i-a` (`lead`): `(-6, -3, -4, -6)` | • Vùng ấm: Ngón cái nhận $V_{\text{thumb}} = \text{round}(V_{\text{hat}}(t) + \Delta_{\text{beat}})$ với $\Delta_{\text{beat}} \in \{-4, 0, +3, +1\}$, kẹp `<= 63`. Fill nhận $V_{\text{thumb}} + (-6, -3, -4, -6) \le 60$.<br>• **Khi phách đỉnh được Snap (`70..72`)**: Chỉ **ngón cái (`low`)** và **ngón `m` (`repeat == 1`, ở `V_snap - 3`)** được vượt `63`; ba móc kép `a, i, a` còn lại và nốt `support` **bị kẹp cứng ở `<= 63`** (giữ thứ tự `a < i <= 63`) để cả cụm không bị kéo sang tiếng móng! |
| **`etude1`** | Hai nốt hát (`index 7, 9`, viết ở `60..72`) | • Bass đầu ô (`low`): `-4` so với nốt hát<br>• 13 móc kép `support`: vòm `_ETUDE1_ARC` `{-2, 0, +2}` quanh tâm bè trung | • Hai nốt hát nhận $V_{\text{hat}}(t) \in [V_{\text{floor}}, V_{\text{ceil}}]$.<br>• Bass nhận $\max(V_{\text{sup\_ceil}} + 2,\; V_{\text{lead}} - 4) \le 61$.<br>• 13 nốt `support` nhận $V_{\text{sup\_center}}(t) + \text{arc}[i]$, luôn `<= P.sup_ceil` (`52`). |
| **`etude11`** | Nốt hát đầu mỗi phách đen (`quarter 0..3`, viết ở `hairpin 60..72`) | • Nốt hát nhắc lại (`+0.5` beat): `-8`<br>• Bass đầu phách (`low`): `-4`<br>• 4 nốt sextuplet giữa (`support`): vòm + `_ETUDE11_TILT` (`-1, -1, 0, +1`) | • Gỡ `accent=True` mặc định trên mọi phách thường: phách thường nhận $V_{\text{hat}}(t) \le 63$, nốt nhắc lại $V_{\text{hat}}(t) - 8$, bass $V_{\text{hat}}(t) - 4 \le 60$, 4 nốt sextuplet nhận $V_{\text{sup\_center}}(t) + \text{tilt}[s] \in [24, 50]$.<br>• **Chỉ khi phách đỉnh lọt Cổng Snap (`70..74`)**: Chỉ **cú 1 của `lead`** nhận $V_{\text{snap}}$ (và `accent=True`); bass dừng ở `<= 63`, nốt nhắc lại ở `<= 62`, và 4 nốt sextuplet giữa giữ nguyên `<= 52`. |
| **`preludio`** (*La Catedral*) | Nốt Canto 1 (`pitch_a`, móc kép `0`) | • Nốt Canto 2 (`pitch_b`, móc kép `6`): `-2`<br>• 6 móc kép sóng chữ V (`support`): đáy chữ V `-2` so với miệng chữ V | • Canto 1 nhận $V_{\text{hat}}(t)$, Canto 2 nhận $V_{\text{hat}}(t) - 2$.<br>• Sóng chữ V `support` đi theo đường bao bè Trung $V_{\text{sup}}(t) \in [20, 50]$ (đáy chữ V `-2`), cách Canto ít nhất `10–12` đơn vị. |
| **Các pattern khác** | Nốt giai điệu `lead` (hoặc `low` ở `thumb_cantabile`) | Theo quan hệ 3 bè bên dưới | Giai điệu nhận $V_{\text{hat}}(t) \le 63$ (trừ cú được Snap). |

#### C. Quy tắc Cổng Ép Dây Hiếm (`Rare Snap Gate`) & Ngân Sách `3–5%`

1. **Tập ứng viên Snap (Snap Candidates)**:
   Một cú gảy chỉ được xét làm ứng viên Snap nếu pattern có $V_{\text{snap}} \ne \text{None}$ và cú đó thuộc đúng danh sách **`snap_targets`** của pattern (xem Bảng Mục 3), đồng thời nằm ở vùng sóng cao ($W(t) \ge 0.70$ hoặc `band == "f"`).
2. **Mẫu số tính ngân sách và Thứ tự cắt (Pruning Order)**:
   - **Mẫu số ($N_{\text{mel}}$)**: Đếm tổng số **cú tấn công có cao độ của Bè Hát Chính** trong thân bài (`midi is not None and not tie_stop` trên `lead`, hoặc trên `low` với `thumb_cantabile`; đối với `tremolo`, mỗi cụm 1 phách đen tính là **1 cú tấn công giai điệu**, không đếm 4 lần lặp móc kép; hoàn toàn không đếm 13 nốt đệm của `etude1` hay 16 nốt sextuplet của `etude11` vào mẫu số).
   - **Ngân sách tối đa ($K_{\max}$)**:
     $$K_{\max} = \max\big(1,\; \lfloor 0.045 \cdot N_{\text{mel}} \rfloor\big) \quad (\text{khi } \alpha_{\text{sec}} \ge 0.25)$$
   - **Thứ tự lọc khi số ứng viên vượt $K_{\max}$**:
     1. Trong mỗi `Phrase`, giữ **tối đa 1 cú ứng viên** có điểm ưu tiên $\big(\text{is\_structural\_accent},\; W(t),\; \text{pitch}\big)$ cao nhất.
     2. Xếp hạng các ứng viên còn lại trên toàn bài theo $W(t)$ giảm dần và chỉ giữ đúng $K_{\max}$ cú đứng đầu.
     3. Các ứng viên bị loại trở về mức trần ấm $V_{\text{ceil}} \le 63$.
3. **Cách gán lực tại cú được Snap**:
   - Chỉ đúng **nốt chủ đạo của cú nhấn đó** nhận:
     $$V_{\text{snapped}} = \text{round}\Big(V_{\text{ceil}} + \big(V_{\text{snap}} - V_{\text{ceil}}\big) \cdot \frac{W(t) - 0.70}{1.0 - 0.70}\Big) \in [66,\; V_{\text{snap}}]$$
   - Các nốt bè đệm (`support`, `low`) kêu cùng lúc với cú Snap **bị khóa ở `<= 63`**, ngoại trừ **3 trường hợp hợp âm khối đặc biệt** được phép đi cùng nhau theo bảng:
     - Cú vỗ *Bartók slap* và *staccato stab* của Brouwer (`elogio_pizz`, `_edge_stab`, `_stab_and_ring`): `lead` `72..76`, `low` `68..70`, `support` `64..66`.
     - Hợp âm *Fanfare* đầu đoạn `f` của Sor (`Grand Solo`): `lead` `68..70`, `low` `64`, `support` `60`.
     - Nhát nhấn *Tresillo* `{0, 3, 6}` của `villa_pattern` hoặc *Syncopated Dance* của Barrios: nốt nào mang `accent=True` tại đúng phách lệch đó được lên `68..73`, nhưng tổng số cú vượt `65` trên cả 3 bè vẫn nằm trong ngân sách $K_{\max}$.

#### D. Bất biến Phân Tầng 3 Bè Trên Cùng Một Thời Điểm (`Simultaneous Voice Ordering`)

Tại mọi thời điểm phát âm $t$, giữa các nốt đang kêu cùng lúc:
1. **Chế độ Chuẩn (Standard Mode — `lead` hát giai điệu)**:
   - Với các nốt thông thường: $\text{lead} \ge \text{low} + 3$ và $\text{low} \ge \text{support} + 2$ (suy ra $\text{lead} > \text{low} > \text{support}$).
   - **Ngoại lệ 1 (`bach_fuga`)**: Khi bè Trầm (`low`) đang hát Subject/Answer, cho phép $\text{lead} \ge \text{low} + 1$ (hoặc $\text{low}$ ngang $\text{lead}$ khi `lead` đang giữ nốt ngân dài còn `low` đổi nốt), nhưng cả hai luôn $> \text{support} + 4$.
   - **Ngoại lệ 2 (Khối chập accent đồng thời — Fanfare, Stab, Block chord trong khung Intro/Outro)**: Cho phép $\text{lead} \ge \text{low} \ge \text{support}$ (có thể bằng nhau ở các khối đồng âm trong `guitar_frame.py`, hoặc lệch `lead > low > support` sau khi qua filter).
2. **Chế độ Ngón Cái Hát (`thumb_cantabile`)**:
   - Ngón cái ở bè Trầm (`low`) là bè hát chính: $\text{low} \ge \text{lead} + 4 \ge \text{support} + 4$ (với hai nốt dyad chập phách yếu: $\text{lead} \ge \text{support}$).

---

## 3. Bảng Khóa Thông Số Theo Từng Pattern (`PatternWaveProfile`) Cho 5 Đại Sư

Thay vì dùng một profile gộp cho mỗi tác gia, hệ thống định nghĩa trực tiếp **`PatternWaveProfile` cho từng pattern** (với mọi $V_{\text{ceil\_calm}} \le V_{\text{ceil\_wide}} \le 63$):

```python
@dataclass(frozen=True)
class PatternWaveProfile:
    floor_calm: int        # Sàn bè hát khi section êm (alpha = 0)
    floor_wide: int        # Sàn bè hát khi section sóng lớn (alpha = 1), luôn >= floor_calm
    ceil_calm: int         # Trần ấm bè hát khi section êm (alpha = 0), luôn <= 60
    ceil_wide: int         # Trần ấm bè hát khi section sóng lớn (alpha = 1), luôn <= 63
    snap_calm: int | None  # Trần ép dây khi alpha nhỏ (None nếu pattern cấm ép dây)
    snap_wide: int | None  # Trần ép dây tối đa khi alpha = 1 (66..76)
    bass_floor: int        # Sàn bè trầm (hoặc bè đệm trên ở thumb_cantabile)
    bass_ceil: int         # Trần ấm bè trầm (<= 60)
    sup_floor: int         # Sàn bè trung (18..24)
    sup_ceil: int          # Trần ấm bè trung (<= 52)
    gamma: float           # Độ võng đường cong E(t) = W(t)^gamma
    snap_targets: str      # Quy tắc chọn cú được phép qua cổng Snap
```

### Bảng Đầy Đủ Các Pattern Của 5 Đại Sư

| Đại sư | Pattern (`id`) | Bè Hát `[floor_calm..ceil_calm]` $\to$ `[floor_wide..ceil_wide]` | Trần Snap `[snap_calm..snap_wide]` | Bè Trầm `[bass_floor..bass_ceil]` | Bè Trung `[sup_floor..sup_ceil]` | $\gamma$ | Danh sách cú được phép Snap (`snap_targets`) |
|---|---|---|---|---|---|---|---|
| **1. Bach**<br>(`bach`) | `bach_sarabande` | `26 .. 56` $\to$ `30 .. 62` | `None` *(0% snap)* | `24 .. 56` | `20 .. 46` | `1.30` | Không ép dây; phách 2 + mordent nở ấm tối đa ở `62`. |
| | `bach_gavotte` | `28 .. 58` $\to$ `32 .. 62` | `66 .. 68` | `26 .. 58` | `22 .. 48` | `1.20` | Chỉ phách 1 đầu câu đỉnh ở band `f`. |
| | `bach_bourree` | `28 .. 58` $\to$ `32 .. 63` | `66 .. 68` | `26 .. 58` | `22 .. 48` | `1.15` | Chỉ nốt `phrase.apex` sau cặp lấy đà khi `rise >= 3`. |
| | `bach_fuga` | `28 .. 58` $\to$ `32 .. 63` | `66 .. 68` | `26 .. 61` *(Subject)* | `20 .. 46` | `1.15` | Chỉ đỉnh `phrase.apex` của Soprano ở câu cao trào nhất. |
| | `bach_gigue` | `28 .. 58` $\to$ `32 .. 63` | `68 .. 70` | `26 .. 58` | `22 .. 50` | `1.15` | Nốt đầu câu chạy scale hoặc phách mạnh `down` tại đỉnh. |
| | `bach_chaconne` | `26 .. 58` $\to$ `30 .. 63` | `68 .. 70` | `24 .. 58` | `20 .. 48` | `1.25` | Duy nhất nốt đích cuối câu chạy scale breakout (`accent=True`). |
| **2. Sor**<br>(`classic`) | `cantabile` | `24 .. 54` $\to$ `28 .. 58` | `None` *(0% snap)* | `22 .. 46` | `20 .. 48` *(3rd/6th)* | `1.35` | Không ép dây; song thanh quãng 3/6 ấm tuyệt đối. |
| | `elegiaque` | `24 .. 56` $\to$ `28 .. 62` | `66 .. 68` | `22 .. 56` | `18 .. 46` | `1.30` | Chỉ nốt tựa *appoggiatura* (`accent=True`) ở câu đỉnh. |
| | `study` *(level 0/1/2)* | `26 .. 56` $\to$ `30 .. 63` | `68 .. 70` | `24 .. 58` | `20 .. 50` | `1.20` | Khối Fanfare mở đoạn `f` hoặc đích scale `Grand Solo level 2`. |
| | `mozart_var` | `26 .. 56` $\to$ `30 .. 62` | `66 .. 68` | `24 .. 56` | `22 .. 50` | `1.20` | Chỉ đỉnh `phrase.apex` khi câu leo dốc mạnh. |
| | `galop` | `28 .. 58` $\to$ `32 .. 63` | `68 .. 70` | `26 .. 58` | `22 .. 50` | `1.10` | Phách mạnh mở câu đỉnh ở phiên `rally` biên độ rộng. |
| **3. Barrios**<br>(`barrios`) | `preludio` (*La Catedral*) | `26 .. 56` $\to$ `30 .. 62` | `66 .. 68` | `24 .. 54` | `18 .. 46` *(V-wave)* | `1.40` | Tối đa 1–2 nốt Canto 1 tại đỉnh cao nhất của cả bài. |
| | `andante` | `24 .. 54` $\to$ `28 .. 60` | `None` *(0% snap)* | `22 .. 54` | `20 .. 46` | `1.35` | Thánh ca nhà thờ ấm áp, không ép dây. |
| | `thumb_cantabile` | `26 .. 56` $\to$ `30 .. 62` *(trên `low`)* | `66 .. 68` *(trên `low`)* | `20 .. 44` *(trên `lead`)* | `18 .. 40` | `1.35` | Chỉ 1–2 nốt ngón cái `low` tại đỉnh câu cao trào. |
| | `tremolo` | `28 .. 58` $\to$ `32 .. 63` *(trên `thumb`)* | `68 .. 72` *(chỉ `thumb` & `m`)* | *(đi theo `thumb`)* | `22 .. 50` | `1.30` | Chỉ phách đỉnh của ô cao trào nhất ($W \ge 0.88$); `a, i` kẹp `<= 63`. |
| | `choro` / `polca` / `hemiola` / `vals` | `28 .. 58` $\to$ `32 .. 63` | `70 .. 74` | `26 .. 58` | `22 .. 50` | `1.15` | Các cú nhấn lệch phách `sync=True` / `accent=True` tại đỉnh sóng. |
| **4. Lobos**<br>(`villa`) | `chord_melody` | `24 .. 54` $\to$ `28 .. 60` | `None` *(0% snap)* | `22 .. 54` | `20 .. 48` | `1.35` | Hợp âm khối ngân ấm, không ép dây. |
| | `thumb_cantabile` | `28 .. 58` $\to$ `32 .. 63` *(trên `low`)* | `68 .. 70` *(trên `low`)* | `22 .. 46` *(trên `lead`)* | `20 .. 42` | `1.25` | Đỉnh câu ngón cái `low` ở phiên biến động lớn. |
| | `villa_pattern` | `26 .. 58` $\to$ `30 .. 63` | `68 .. 72` | `24 .. 58` | `20 .. 50` | `1.20` | Chỉ 3 cú nhấn *Tresillo* `{0, 3, 6}` ở các ô `volatile` band `f`. |
| | `etude1` | `28 .. 58` $\to$ `32 .. 63` | `68 .. 70` | `24 .. 58` | `22 .. 52` | `1.20` | Nốt hát (`index 7, 9`) tại đúng ô đỉnh cao trào của bài. |
| | `etude11` | `28 .. 58` $\to$ `32 .. 63` | `70 .. 74` | `24 .. 58` | `22 .. 50` *(sextuplets)* | `1.20` | Chỉ cú 1 `lead` tại phách `phrase.apex` (các phách khác gỡ `accent`). |
| **5. Brouwer**<br>(`brouwer`) | `noviembre` | `20 .. 52` $\to$ `24 .. 58` | `None` *(0% snap)* | `18 .. 50` | `18 .. 42` | `1.45` | Tuyệt đối 0% ép dây; ballad điện ảnh thì thầm. |
| | `sarabande` | `22 .. 56` $\to$ `26 .. 62` | `68 .. 72` | `20 .. 56` | `18 .. 48` | `1.35` | Chỉ hợp âm nhấn phách 2 tại đỉnh cao trào; swarm giữ `<= 62`. |
| | `brouwer_etude` | `24 .. 58` $\to$ `28 .. 63` | `68 .. 72` | `22 .. 58` *(tumbao)* | `20 .. 50` | `1.15` | Cú nhấn downbeat/tumbao ở các ô đỉnh sóng. |
| | `elogio_pizz` | `24 .. 56` $\to$ `26 .. 62` | `72 .. 76` *(Bartók slap)* | `22 .. 56` | `20 .. 48` | `1.15` | Cú vỗ *Bartók slap* ở móc đơn thứ 3 (`slap = start + 3`). |

---

## 4. Đường Cong Riêng Cho Khung Intro & Outro (`guitar_frame.py`)

Trong code hiện tại, `guitar_frame.py` đặt `_PP = 46`, `_P = 50`, `_MP = 56`, `_MF = 64` (kể cả `_edge_stab` và `_stab_and_ring` của Brouwer cũng đang viết ở `_MF = 64`), và các ô `pedal` bị `_shape_dynamics` bỏ qua.

Khi đưa vào `apply_guitar_wave()`:
1. **Các ô `pedal` (`intro`, `warmup`, `outro`, `cooldown`) đi đường bao riêng (Frame Envelope), không đi qua Cổng Snap chung**:
   - Bảo toàn cấu trúc chênh lệch tương đối giữa các nốt bên trong từng cử chỉ của `guitar_frame.py` (ví dụ contour chuông `44, 50, 46` hay cantabile `46 -> 52` của Barrios).
   - **Intro (`leading` bars)**: Ánh xạ tuyến tính/cosine từ mức khởi âm **$ppp - pp$ (`22..32` ở đầu ô 0)** tăng dần lên khớp với mức mở đầu thân bài ($V_{\text{hat}}(t_{\text{body\_start}}) \approx 34..48$). Không một nốt thường nào trong Intro vượt quá `56`.
   - **Outro (`trailing` bars)**: Áp dụng hàm suy giảm mũ (**Morendo Curve**) từ mức cuối thân bài hạ dần về **`20..26` ($ppp$)** ở ô cuối cùng (hợp âm chuông / Picardy third tan dần).
2. **Ngoại lệ duy nhất trong Frame được phép Snap**:
   - Nhánh kịch tính `edge == True` của Brouwer (`_edge_stab` ở đầu Intro và `_stab_and_ring` ở cuối Outro) và nhánh `bright == True` (`_stabs` ở cuối Outro của Villa): các nốt mang đồng thời `staccato=True` và `accent=True` giữ lực chập sắc gọn ở **`68..72`** (với `lead` `70..72`, `low` `66..68`, `support` `62..64`), không bị hàm Morendo kéo về $ppp$.

---

## 5. Lộ Trình Triển Khai 5 Bước (Implementation Order)

1. **Bước 1 — Khóa bảng `PatternWaveProfile` trong module mới `backend/app/sonify/guitar_wave.py`**:
   - Khai báo đầy đủ 25 pattern của 5 đại sư với `floor_calm <= floor_wide`, `ceil_calm <= ceil_wide <= 63`, `snap_calm / snap_wide`, `gamma`, và danh sách `snap_targets`.
   - Viết hàm tính $\alpha_{\text{sec}}$ theo từng `FormSection` (qua `_section_rel_span`), sóng $W_{\text{macro}}(t)$ bám theo đường giá làm mượt + mờ biên section, sóng câu $W_{\text{phrase}}(t)$ (raised-cosine), và sóng thanh khoản $W_{\text{band}}(t)$.

2. **Bước 2 — Viết bộ Rebase `apply_guitar_wave()` thay thế `_shape_dynamics()` sau khi pattern đã sinh nốt**:
   - Xử lý riêng từng nhóm cấu trúc:
     - Nhóm có vòm nội bộ (`tremolo`, `etude1`, `etude11`, `preludio`): lấy delta so với nốt mốc của ô/phách rồi cộng lại sau khi đã rebase nốt mốc vào `[V_floor, V_ceil <= 63]`. Trên `etude11`, chỉ giữ `accent=True` ở phách đỉnh câu.
     - Nhóm thường & `thumb_cantabile`: rebase Bè Hát Chính, Bè Trầm, Bè Trung theo công thức phân tầng và kiểm tra bất biến thứ tự bè tại mỗi thời điểm phát âm.
     - Nhóm ô `pedal` (`intro`/`outro`): chạy đường bao Emergence / Morendo riêng, trừ các cú stab có `accent=True and staccato=True`.
   - Chạy **Cổng Snap (`Rare Snap Gate`)**: lọc ứng viên theo `snap_targets`, giới hạn tối đa 1 cú mỗi câu và tổng số cú $\le 4.5\%$ số cú tấn công của bè hát ($N_{\text{mel}}$), đồng thời **kẹp cứng mọi nốt đệm đi kèm trong cụm ở `<= 63`** (trừ 3 ngoại lệ khối chập).
   - Đồng bộ toàn bộ các nốt nối dây (`tie_stop=True` nhận đúng velocity của cú `tie_start` mở chuỗi).

3. **Bước 3 — Thêm chốt chặn hậu kiểm sau `humanize()` trên đường Guitar**:
   - Trong `humanize.py` (hoặc hàm bọc cho `score.variant == "guitar"`): với mọi nốt có `written_velocity <= 64` trước khi humanize, kẹp `heard_velocity = min(64, heard_velocity)` để offset `+1, +2` của `humanize` không bao giờ đẩy một nốt vùng ấm vượt qua ngưỡng `65`.

4. **Bước 4 — Viết `backend/tests/test_guitar_wave.py` và cập nhật `backend/tests/test_sonify_guitar.py`**:
   - Cập nhật các assertion số tuyệt đối cũ (`56, 60, 64, 72`) trong `test_sonify_guitar.py` sang kiểm tra khoảng động lực học mới và cấu trúc tương đối.
   - Trong `test_guitar_wave.py`, kiểm tra đủ 6 tiêu chí:
     1. **Phiên `calm` biên độ hẹp**: có nốt xuống vùng $ppp - pp$ (`<= 34`) và **100% số nốt sau `humanize` nằm ở `<= 64`** (0% ép dây).
     2. **Phiên `rally` / `volatile` biên độ rộng**: mở sâu xuống $pp$ (`<= 36`), tỷ lệ cú tấn công bè hát vượt `65` nằm trong `1..5%`, và tuyệt đối không nốt nào vượt `76` (hoặc `70` với Bach/Sor).
     3. **Bảo toàn delta vi mô ở vùng ấm**: trong một ô `tremolo` ấm, ngón cái lớn hơn `m` ít nhất `3` và `m > i > a`; trong `etude1` và `etude11`, bậc thang bè trung giữ nguyên hình vòm dưới `52`.
     4. **Cụm Snap không kéo nốt đệm qua `65`**: tại phách `tremolo` hoặc `etude11` được snap (`70..74`), các móc kép `a, i` của tremolo và 4 nốt sextuplet giữa của `etude11` vẫn `<= 63` (và `< 52`).
     5. **$\alpha_{\text{sec}}$ theo từng section trên `1M` / `1W`**: một chương `1M` có section đi ngang và section biến động mạnh phải có trần/sàn khác nhau giữa hai section, không bị bão hòa $\alpha = 1.0$ toàn bài.
     6. **Bất biến thứ tự bè đồng thời**: `lead > low > support` trên các cú gảy thường, cho phép `>=` trên các khối accent đồng thời, và `low > lead >= support` trên `thumb_cantabile`.

5. **Bước 5 — Thực nghiệm nghe 3 mốc `24 / 64 / 74` trên MS Basic Nylon trước khi bump Revision**:
   - Trước khi tăng `RECAP_REVISION` và `SPAN_REVISION` trong `backend/app/sonify/audio.py`, xuất WAV khô thử nghiệm với 3 mức velocity `24` ($ppp$), `64` (trần ấm), và `74` (đỉnh snap) qua `musescore_export` trên MS Basic Nylon:
     - Kiểm tra mức RMS/Peak dBFS ở `velocity = 24` có đủ nghe rõ trên nền nhiễu `_GUITAR_NOISE = 0.0003` hay không (nếu quá chìm, nâng sàn tối thiểu từ `18..20` lên `24..26`).
     - Kiểm tra sự khác biệt âm sắc và biên độ giữa `64` và `74` để tinh chỉnh lần cuối trước khi khóa revision cache.
