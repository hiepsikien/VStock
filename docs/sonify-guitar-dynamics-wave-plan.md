# Kế Hoạch Thiết Kế Filter Uốn Sóng Động Lực Học (Wave) & Mở Rộng Biên Độ ($ppp \to f$) Cho 5 Đại Sư Guitar

> **Mục tiêu**: Đưa tiếng đàn guitar cổ điển thoát khỏi dải hẹp $mp - mf$ (`44..78`) hiện tại bằng cách **thay thế (rebase) vận tốc đã viết quanh `64/72` bằng con sóng Cường Độ Khớp Lệnh (Smoothed Per-Candle Market Volume Intensity) làm đường bao trần trực tiếp**, mở rộng chiều sâu về phía **thì thầm / gần gũi ($ppp - pp$, velocity `18..38`)**, giữ **100% các nốt sóng thường trong vùng dây nylon ấm (`<= 63` trước humanize, `<= 64` sau humanize)**, và cấp phát ngân sách **ép dây hiếm (`66..76`, tính theo từng section khi biên độ giá $\alpha_{\text{price}} \ge 0.25$)** chỉ cho đúng những cú nhấn thuộc các pattern thực sự cần lực tì dây.
>
> **Liên kết**: [`docs/sonify-classical-guitar.md`](./sonify-classical-guitar.md), [`docs/sonify-barrios-tremolo-dynamics.md`](./sonify-barrios-tremolo-dynamics.md), [`docs/sonify-humanize-preset-plan.md`](./sonify-humanize-preset-plan.md).

---

## 1. Chẩn Đoán Hiện Trạng Trong Codebase

Qua khảo sát toàn bộ pipeline guitar (`guitar.py`, `guitar_patterns.py`, `guitar_barrios.py`, `guitar_villa.py`, `guitar_frame.py`, `dynamics.py`, `humanize.py`), lực gảy hiện tại đang bị nén trong dải hẹp do **4 nguyên nhân**:

| Điểm nghẽn trong Code | Vị trí & Con số thực tế đang chạy | Hệ quả âm thanh |
|---|---|---|
| **1. Nền giai điệu & đệm đặt sẵn ngay sát ngưỡng ép dây (`65`)** | • `_MELODY = 64`, `_MELODY_APEX = 72`<br>• `_SWELL_OPEN = 60`, `_SWELL_MID = 68`, `_SWELL_CLOSE = 62`<br>• `_BAND_SUPPORT = 50..60`, `_BAND_BASS = 54..64`<br>• `etude1` / `etude11`: `_ETUDE_OPEN = 60`, `_ETUDE_PEAK = 72`, sàn nốt giữa `44`, mỗi phách đen của `etude11` đều gắn `accent=True` | Ngay từ lúc sinh nốt, giai điệu đã đứng ở `60..72` (ngay sát hoặc vượt ngưỡng móng `65`). Không có nốt nào được viết ở $ppp$ (`~18..26`) hay $pp$ (`~28..36`). |
| **2. `_shape_dynamics` cộng thêm lên nền `64` và kẹp cứng `[44, 78]`** | `guitar_patterns.py` dòng 2906–2931:<br>• `if event.velocity >= _MELODY_APEX: continue`<br>• `velocity = max(44, min(78, event.velocity + delta + extra))`<br>• `_punch` cộng `+8` hoặc `+12` rồi kẹp `min(88, ...)`<br>• *La Catedral* khóa `lead` ở `54..64`, `support` ở `48..55` | • Lấy `event.velocity` (`~64`) làm tâm rồi cộng `_BAND_DELTA` (`-12..+4`) và `extra` (`0..+4`), cộng thêm sàn `44`, khiến bản nhạc không thể xuống được $ppp - pp$.<br>• Nếu chỉ gỡ `max(44, min(78, ...))` mà không rebase lại tâm thì chỉ đẩy thêm nốt lên vùng móng.<br>• `etude1`, `etude11`, `tremolo` đang đứng ngoài `_shape_dynamics`. |
| **3. Volume thị trường bị lượng tử hóa quá thô thành 4 bậc thang đứt đoạn** | `dynamics.py` & `render.py`:<br>• Gom volume theo cửa sổ 4–6 ô (`LIQUIDITY_WINDOWS`), ép vào 4 chữ `"p", "mp", "mf", "f"`.<br>• Khi `high / low < 2.0` (`MIN_SPAN_RATIO`), toàn bộ bài bị gán cứng thành `"mf"`.<br>• `guitar_patterns.py` chỉ truyền `band_at: dict[int, str]` vào `_Ctx`, chưa truyền cường độ volume liên tục của từng ô nhịp. | • Volume trên thị trường vốn giật cục theo từng phút (răng cưa), nhưng khi gom cửa sổ 6 ô rồi cắt thành 4 bậc thang thì lại mất hết con sóng thủy triều tự nhiên của dòng tiền (sôi động đầu phiên $\to$ lắng trũng giữa trưa $\to$ cuộn sóng chiều). |
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

## 2. Mô Hình Toán Học: Sóng Cường Độ Volume Làm Trần Trực Tiếp & Rebase Vận Tốc (`guitar_wave.py`)

### 2.1. Vị trí trong Pipeline & Đại lượng Cường Độ Khớp Lệnh (`bar_volumes`)

Trong `render.py`, hàm `average_liquidity([_window_candles(bars, groups, b, 1) for b in range(musical_bars)])` trả về **volume trung bình trên mỗi nến (per-candle trading intensity) trong ô nhịp `b`**, sau khi đã loại bỏ nến ATO/ATC và kẹp spike ở `CLIP_MULTIPLE = 4.0` lần trung vị dương của cả bài.
- Đây chính xác là **đại lượng muốn nghe**: đo cường độ khớp lệnh thực tế tại thời điểm đó mà không bị sai lệch khi số lượng nến gộp vào mỗi ô nhịp (`len(groups[b])`) chênh nhau 1 nến do làm tròn.

```text
render.py (_compose)
  ├── Tính bar_volumes: list[float] = average_liquidity([_window_candles(bars, groups, b, 1) for b in range(musical_bars)])
  └── Truyền bar_volumes (tùy chọn, default None) vào render_guitar_score() -> render_patterned_voices() -> _Ctx
        ├── Nếu bar_volumes được truyền vào: dùng chuỗi cường độ khớp lệnh thực của từng ô nhịp.
        └── Nếu bar_volumes is None (trong các synthetic test fixture): khôi phục từ ctx.band_at theo {"p": 1.0, "mp": 2.0, "mf": 4.0, "f": 8.0}.
```

Thứ tự chạy cuối pipeline guitar:
```text
render_patterned_voices()
  ├── 1. Sinh nốt theo Pattern & Frame (giữ nguyên cấu trúc tương đối giữa các ngón p-i-m-a)
  ├── 2. _repair() & _resolve() & _slur()
  ├── 3. apply_guitar_wave()  <-- Rebase toàn bộ velocity theo Sóng Volume vào [V_floor, V_ceil <= 63] + Snap [66..76]
  └── 4. humanize(score)      <-- Ở audio.py (hoặc cuối humanize cho variant=="guitar"):
                                  • Nếu written_velocity <= 64: heard_velocity = min(64, heard_velocity)
                                  • Nếu written_velocity >= 65: heard_velocity = max(66, min(76, heard_velocity))
```

---

### 2.2. Quy Trình 4 Bước Làm Mượt Cường Độ Volume Thành Đường Bao Trần $U_{\text{vol}}(t) \in [0.0, 1.0]$

Với mỗi `FormSection` thân bài `[sec_start, sec_end)`:

#### Bước A — Nén Logarit trên `bar_volumes` đã kẹp spike (`Log-Intensity Compression`)
- Lấy $v(b) = \max(0.0,\; \text{bar\_volumes}[b])$ cho $b \in [\text{sec\_start}, \text{sec\_end})$.
- Đưa về miền logarit:
  $$\ell(b) = \ln\big(1 + v(b)\big)$$

#### Bước B — Bộ Lọc Đối Xứng Không Pha Trễ (`Zero-Phase 5-Tap Smoothing`)
- Áp dụng bộ lọc đối xứng bán kính 2 ô nhịp (kernel `[1, 4, 6, 4, 1] / 16`, phản xạ biên tại `sec_start` và `sec_end - 1`) để khử răng cưa từng phút mà giữ nguyên vị trí ô nhịp đạt đỉnh thanh khoản:
  $$\tilde{\ell}(b) = \frac{1 \cdot \ell(b-2) + 4 \cdot \ell(b-1) + 6 \cdot \ell(b) + 4 \cdot \ell(b+1) + 1 \cdot \ell(b+2)}{16}$$

#### Bước C — Khóa Biên Độ Trên Chính Sóng Volume (`Volume Range-Lock` $[0.0, 1.0]$)
- Đặt $q_{05} = \text{percentile}(\tilde{\ell}, 0.05)$ và $q_{95} = \text{percentile}(\tilde{\ell}, 0.95)$ trên các ô trong section:
  - **Trường hợp suy biến ($q_{95} - q_{05} \le 10^{-6}$ — toàn bộ section có volume bằng nhau)**:
    Đặt $u(b) = \text{band\_val}(\text{band}(b))$ với `{"p": 0.15, "mp": 0.40, "mf": 0.65, "f": 0.90}`.
  - **Trường hợp có biến thiên ($q_{95} > q_{05}$)**:
    Kéo dãn $\tilde{\ell}(b)$ theo $[q_{05}, q_{95}]$ rồi khóa chính xác $\min_b u(b) = 0.0$ và $\max_b u(b) = 1.0$:
    $$u_{\text{raw}}(b) = \text{clamp}\left(\frac{\tilde{\ell}(b) - q_{05}}{q_{95} - q_{05}},\; 0.0,\; 1.0\right), \qquad u(b) = \frac{u_{\text{raw}}(b) - \min u_{\text{raw}}}{\max u_{\text{raw}} - \min u_{\text{raw}}} \in [0.0, 1.0]$$
- **Hệ quả**: Do kẹp theo phân vị $[q_{05}, q_{95}]$, trên section dài có thể có một **tập các ô cực đại** $\mathcal{B}_{\max} = \{b \mid u(b) == 1.0\}$ (khoảng $\le 5\%$ số ô) và một **tập các ô cực tiểu** $\mathcal{B}_{\min} = \{b \mid u(b) == 0.0\}$. Mọi ô $b^* \in \mathcal{B}_{\max}$ đều đạt $u(b^*) = 1.0$, và mọi ô $b_* \in \mathcal{B}_{\min}$ đều đạt $u(b_*) = 0.0$.

#### Bước D — Nội Suy Cosine Liên Tục Hai Chiều Qua Vạch Nhịp & Giữ Phẳng Ô Cực Trị (`Continuous Barline Interpolation`)
- Để vừa giữ phẳng toàn bộ các móc đơn trong mọi ô cực trị $b \in \mathcal{B}_{\min} \cup \mathcal{B}_{\max}$, vừa **liên tục tuyệt đối ở cả hai chiều bước vào và bước ra khỏi ô cực trị** (không nhảy cóc từ `0.80 -> 1.0` khi vào đỉnh, và không lệch `0.989` ở móc đơn đầu khi rời đỉnh):
  - Với mỗi ô $b \in [\text{sec\_start}, \text{sec\_end})$, xác định **điểm đầu ô $u_{\text{start}}(b)$** và **điểm cuối ô $u_{\text{end}}(b)$** bằng đệ quy từ trái sang phải:
    $$\begin{aligned}
    u_{\text{start}}(b) &= \begin{cases}
    u(b), & \text{nếu } b == \text{sec\_start} \text{ hoặc } u(b) \in \{0.0,\; 1.0\} \\
    u_{\text{end}}(b - 1), & \text{ngược lại}
    \end{cases} \\
    u_{\text{end}}(b) &= \begin{cases}
    u(b), & \text{nếu } u(b) \in \{0.0,\; 1.0\} \\
    u(b + 1), & \text{nếu } b + 1 < \text{sec\_end} \text{ và } u(b + 1) \in \{0.0,\; 1.0\} \\
    u(b), & \text{ngược lại}
    \end{cases}
    \end{aligned}$$
  - Tại móc đơn thứ $k \in \{0, 1, \dots, \text{epb} - 1\}$ bên trong ô $b$ (với $t = b \cdot \text{epb} + k$), đặt tỉ lệ vị trí móc đơn trên đoạn $[0, 1]$ là:
    $$r(k) = \begin{cases}
    0.0, & \text{nếu } \text{epb} \le 1 \\
    \dfrac{k}{\text{epb} - 1}, & \text{nếu } \text{epb} > 1 \quad \big(\text{tức } r(0) = 0.0 \text{ tại đầu ô và } r(\text{epb} - 1) = 1.0 \text{ tại cuối ô}\big)
    \end{cases}$$
  - Giá trị sóng volume tại móc đơn $t$ là:
    $$U_{\text{vol}}(t) = u_{\text{start}}(b) + \dfrac{1 - \cos\big(\pi \cdot r(k)\big)}{2} \cdot \big(u_{\text{end}}(b) - u_{\text{start}}(b)\big) \in [0.0, 1.0]$$
- **Kiểm chứng tính liên tục tuyệt đối ở cả hai chiều**:
  - **Trên mọi ô cực trị ($u(b) \in \{0.0, 1.0\}$)**: $u_{\text{start}}(b) = u_{\text{end}}(b) = u(b) \implies$ mọi móc đơn $k = 0 \dots \text{epb}-1$ đều giữ phẳng $U_{\text{vol}}(t) = u(b)$.
  - **Chiều bước vào ô cực trị ($u(8) = 0.60 \to u(9) = 0.80 \to u(10) = 1.0$)**: Vì ô `9` đứng sát trước ô cực trị `10` ($u(10) = 1.0$), nên $u_{\text{start}}(9) = 0.60$ và **$u_{\text{end}}(9) = u(10) = 1.0$**. Móc đơn đầu ô `9` ($k = 0 \implies r = 0.0$) bằng đúng `0.60`, và móc đơn cuối ô `9` ($k = \text{epb} - 1 \implies r = 1.0$) chạm đúng **`1.0`**, nối liền mạch vào cao nguyên phẳng `1.0` của ô `10`! (Cùng quy tắc khi đi vào đáy $u = 0.0$: móc đơn cuối của ô đứng trước đáy chạm đúng `0.0`).
  - **Chiều bước ra khỏi ô cực trị ($u(10) = 1.0 \to u(11) = 0.72 \to u(12) = 0.55$)**: Trên ô `11`, $u_{\text{start}}(11) = u_{\text{end}}(10) = 1.0$ và $u_{\text{end}}(11) = u(11) = 0.72$. Tại móc đơn đầu ô `11` ($k = 0 \implies r = 0.0$), $U_{\text{vol}}$ bằng **đúng `1.0`** (không bị hụt xuống `0.989`), và tại móc đơn cuối ô `11` ($k = \text{epb} - 1 \implies r = 1.0$), $U_{\text{vol}}$ hạ về **đúng `0.72`**, khớp với $u_{\text{start}}(12) = 0.72$!

---

### 2.3. Tách Bạch $\alpha_{\text{vol}}$ (Mở Sóng Ấm), $\alpha_{\text{price}}$ (Mở Cổng Snap) & Hệ Số Đoạn Nội Tâm $\kappa_{\text{sec}}$

1. **Hệ số biến động giá $\alpha_{\text{price}} \in [0.0, 1.0]$ (Quyết định Cổng Snap & Mở trần kịch tính)**:
   Tính từ `_section_rel_span(bars, groups, sec_start, sec_end)`:
   $$\alpha_{\text{price}} = \text{clamp}\left(\frac{\text{rel\_span}_{\text{sec}} - 0.004}{0.024 - 0.004},\; 0.0,\; 1.0\right)$$

2. **Hệ số tương phản dòng tiền $\alpha_{\text{vol}} \in [0.0, 1.0]$ (Đo trên chuỗi volume đã làm mượt $\tilde{v}(b) = \exp(\tilde{\ell}(b)) - 1$)**:
   Đặt $\text{vol\_ratio}_{\text{sec}} = \frac{\text{percentile}(\tilde{v}, 0.90)}{\max(\text{percentile}(\tilde{v}, 0.10),\; 10^{-6})}$:
   $$\alpha_{\text{vol}} = \text{clamp}\left(\frac{\ln(\text{vol\_ratio}_{\text{sec}}) - \ln(1.35)}{\ln(3.50) - \ln(1.35)},\; 0.0,\; 1.0\right)$$
   *(Nếu fixture có volume hằng số $\text{vol\_ratio}_{\text{sec}} \le 1.01$, đặt $\alpha_{\text{vol}} = \alpha_{\text{price}}$).*

3. **Ánh xạ vào Cửa sổ Ấm $[V_{\text{floor}}, V_{\text{ceil}}]$ và Hệ số đoạn nội tâm (`trio` / `bridge`)**:
   - Đặt $\alpha_{\text{warm}} = \max(\alpha_{\text{price}},\; 0.75 \cdot \alpha_{\text{vol}})$.
   - Với section thường (`A` hoặc thân bài `1D`):
     $$\begin{aligned}
     V_{\text{floor}} &= \text{round}\big(P.\text{floor\_calm} + \alpha_{\text{warm}} \cdot (P.\text{floor\_wide} - P.\text{floor\_calm})\big) \\
     V_{\text{ceil}}  &= \text{round}\big(P.\text{ceil\_calm}  + \alpha_{\text{warm}} \cdot (P.\text{ceil\_wide}  - P.\text{ceil\_calm})\big) \le 63
     \end{aligned}$$
   - **Với đoạn giữa nội tâm (`section.trio` hoặc `section.bridge`)**:
     Thay vì nhân $\kappa = 0.65$ vào $W(t)$ (làm $W(t) \le 0.65$ khiến đoạn `trio`/`bridge` không bao giờ chạm tới trần thiết kế của nó và không bao giờ qua được ngưỡng snap `0.70`), việc làm dịu đoạn nội tâm được thực hiện bằng cách **hạ $\alpha_{\text{warm}}$ của section đó đi nhân tử $\kappa_{\text{sec}} = 0.50$** (tức kéo $[V_{\text{floor}}, V_{\text{ceil}}]$ của đoạn `trio`/`bridge` về sát $[P.\text{floor\_calm}, P.\text{ceil\_calm}]$), trong khi sóng chuẩn hóa $U_{\text{vol}}(t)$ bên trong section đó **vẫn chạy đủ `[0.0, 1.0]`**!
   - **Không nhân $T_{\text{edge}}$ lên thân bài**:
     Mờ biên (emergence / morendo) **chỉ áp dụng cho vùng khung Pedal (`intro`/`warmup` và `cooldown`/`outro`, Mục 4)**. Toàn bộ các ô thuộc thân bài giữ nguyên $U_{\text{vol}}(t)$ để **đỉnh thanh khoản lúc mở cửa (ATO/đầu phiên) và đóng cửa (cuối phiên) ở hai đầu thân bài được giữ nguyên 100%, không bị dìm xuống `0.25`**!

---

### 2.4. Đường Bao Trần `U_vol(t)` & Hơi Thở Nội Bộ Câu Nhạc (Đỉnh Thanh Khoản Luôn Là Đỉnh Tiếng)

Để đảm bảo hai tính chất toán học nghiêm ngặt:
1. **Tại ô đỉnh thanh khoản ($u(b^*) = 1.0$), vận tốc giai điệu chắc chắn chạm đúng $V_{\text{ceil}}$** (không đòi hỏi đỉnh volume phải tình cờ trùng với đỉnh câu nhạc hay độ dốc giá).
2. **Không một đỉnh câu nhạc nào ở ô có volume thấp hơn có thể vượt qua đường bao trần của ô có volume cao hơn**:

Ta tách **Đường Bao Trần Тео Volume ($V_{\text{env}}(t)$)** và **Độ Nhấn Nhá Nội Bộ Câu Nhạc ($\Delta_{\text{phrase}}(t) \le 0$)**:

1. **Đường Bao Trần Theo Sóng Volume $V_{\text{env}}(t) \in [V_{\text{floor}}, V_{\text{ceil}}]$**:
   Sóng volume $U_{\text{vol}}(t) \in [0.0, 1.0]$ sau khi uốn qua $E_{\text{vol}}(t) = \big(U_{\text{vol}}(t)\big)^{\gamma}$ xác định trực tiếp **Trần Đường Bao** tại thời điểm $t$:
   $$V_{\text{env}}(t) = V_{\text{floor}} + E_{\text{vol}}(t) \cdot \big(V_{\text{ceil}} - V_{\text{floor}}\big)$$
   - Tại ô trũng thanh khoản nhất ($U_{\text{vol}} = 0.0 \implies E_{\text{vol}} = 0.0$): $V_{\text{env}} = V_{\text{floor}}$.
   - Tại ô đỉnh thanh khoản nhất ($U_{\text{vol}} = 1.0 \implies E_{\text{vol}} = 1.0$): **$V_{\text{env}} = V_{\text{ceil}}$** (luôn đạt đúng $V_{\text{ceil}}$ tại mọi ô có $u(b^*) = 1.0$, bất kể vị trí trong section!).

2. **Độ Thở Nội Bộ Câu Nhạc Nằm Bên Dưới Đường Bao ($\Delta_{\text{phrase}}(t) \in [-D_{\max}, 0]$)**:
   - Trong mỗi câu nhạc `phrase`, đặt hàm thở chuẩn hóa $C_{\text{phrase}}(t) = \frac{1 - \cos(\pi \cdot s(t))}{2} \in [0.0, 1.0]$ (bằng `0.0` ở hai biên câu và bằng `1.0` tại đỉnh câu `phrase.apex`; nếu câu chỉ có 1 run phẳng thì $s(t)$ tính tới tâm câu để giữa câu vẫn bằng `1.0`).
   - Thay vì cộng vượt lên trên $V_{\text{env}}(t)$, hai đầu câu nhạc **lùi nhẹ xuống dưới đường bao $V_{\text{env}}(t)$ một khoảng tối đa $D_{\max} = 3$ đơn vị** (hoặc $D_{\max} = 1$ khi câu phẳng), và tại đỉnh câu ($C_{\text{phrase}} = 1.0$) hoặc tại tâm của ô đỉnh thanh khoản ($u(b^*) = 1.0$), độ lùi bằng `0` (chạm đúng đường bao $V_{\text{env}}(t)$):
     $$\Delta_{\text{phrase}}(t) = -D_{\max} \cdot \big(1 - C_{\text{phrase}}(t)\big) \cdot \big(1 - U_{\text{vol}}(t)^4\big) \in [-3.0,\; 0.0]$$
   - Khi đó, đường vận tốc chuẩn của Bè Hát Chính là:
     $$V_{\text{hat}}(t) = \text{clamp}\Big(\text{round}\big(V_{\text{env}}(t) + \Delta_{\text{phrase}}(t)\big),\; V_{\text{floor}},\; V_{\text{ceil}}\Big)$$

3. **Kiểm chứng toán học của công thức Đường Bao Trần**:
   - **Cực đại toàn Section luôn đạt trên toàn bộ tập ô đỉnh thanh khoản ($\mathcal{B}_{\max} = \{b^* \mid u(b^*) == 1.0\}$)**: Vì mọi móc đơn trong mọi ô $b^* \in \mathcal{B}_{\max}$ đều có $U_{\text{vol}}(t^*) = 1.0 \implies \big(1 - U_{\text{vol}}(t^*)^4\big) = 0 \implies \Delta_{\text{phrase}}(t^*) = 0 \implies V_{\text{hat}}(t^*) = V_{\text{env}}(t^*) = V_{\text{ceil}}$ **trên toàn bộ các ô thuộc $\mathcal{B}_{\max}$**, bất kể ô đó nằm ở mở cửa, giữa bài hay đóng cửa, và bất kể đang ở đầu câu hay đỉnh câu!
   - **Cực tiểu toàn Section luôn đạt trên tập ô đáy thanh khoản ($\mathcal{B}_{\min} = \{b_* \mid u(b_*) == 0.0\}$)**: $V_{\text{env}}(t_*) = V_{\text{floor}}$, và do $\Delta_{\text{phrase}}(t_*) \le 0$ được kẹp ở $V_{\text{floor}}$, nên **$V_{\text{hat}}(t_*) = V_{\text{floor}}$** (chạm đúng đáy $ppp - pp$).
   - **Quan hệ giữa các ô trung gian ($0.0 < U_{\text{vol}}(t) < 1.0$)**: Tại mỗi thời điểm $t$, vận tốc thực tế luôn thỏa $V_{\text{hat}}(t) \le V_{\text{env}}(t) \le V_{\text{ceil}}$. Lưu ý: giữa hai ô trung gian có volume gần nhau, một ô có volume hơi thấp hơn nhưng đang ở đỉnh câu ($\Delta_{\text{phrase}} = 0$) có thể lớn hơn tối đa **`3` đơn vị MIDI (đúng bằng $D_{\max} = 3$)** so với một ô có volume nhỉnh hơn nhưng đang ở biên câu ($\Delta_{\text{phrase}} = -3$); tuy nhiên **cực đại tuyệt đối của cả section luôn đạt tại tập ô $\mathcal{B}_{\max}$ ($u(b^*) = 1.0 \implies V_{\text{ceil}}$) và không một ô nào có $u(b) < 1.0$ vượt qua được $V_{\text{ceil}}$**.

---

### 2.5. Bảo Toàn Cấu Trúc Vi Mô, Cổng Snap & Bất Biến 3 Bè

#### A. Ba đường cong cơ sở (`V_hat`, `V_bass_curve`, `V_sup_curve`)

$$\begin{aligned}
V_{\text{hat}}(t)        &= \text{clamp}\Big(\text{round}\big(V_{\text{env}}(t) + \Delta_{\text{phrase}}(t)\big),\; V_{\text{floor}},\; V_{\text{ceil}} \le 63\Big) \\
V_{\text{bass\_curve}}(t) &= \text{round}\Big(P.\text{bass\_floor} + E_{\text{vol}}(t)^{1.05} \cdot \big(P.\text{bass\_ceil} - P.\text{bass\_floor}\big)\Big) \\
V_{\text{sup\_curve}}(t)  &= \text{round}\Big(P.\text{sup\_floor} + E_{\text{vol}}(t)^{1.20} \cdot \big(P.\text{sup\_ceil} - P.\text{sup\_floor}\big)\Big)
\end{aligned}$$

#### B. Bảo toàn Tuyệt Đối Cấu Trúc Nội Bộ Cho 4 Pattern Đặc Thù (`tremolo`, `etude1`, `etude11`, `preludio`)

> **Quy tắc quan trọng**: 4 pattern này có cấu trúc phân bè và bậc thang riêng biệt (`tremolo` đặt ngón cái ở `low` lớn hơn fill `a-m-i` ở `lead`; `etude11` có nốt nhắc lại `lead` ở nửa sau phách thấp hơn `bass` đầu phách). Do đó, 4 pattern này **dùng trực tiếp quy tắc rebase riêng bên dưới và KHÔNG đi qua pass ép `lead > low > support` chung**!

| Pattern | Công thức Rebase ở vùng ấm (khớp 100% với từng dòng code hiện tại) | Quy tắc khi Cú Mốc được Snap (`66..74`) |
|---|---|---|
| **`tremolo`**<br>(`guitar.py:64`:<br>`4/4: (-4, 0, +4, +1)`<br>`3/4 & 6/8: (-4, +4, 0)`) | • **Lấy một mốc chung cho cả ô nhịp `bar`**: Đặt $V_{\text{bar}} = \text{clamp}\big(V_{\text{hat}}(t_{\text{bar\_mid}}),\; P.\text{floor\_calm} + 4,\; 59\big)$ trước khi cộng offset phách.<br>• Nhờ dùng **một mốc $V_{\text{bar}}$ duy nhất trong ô** và kẹp $V_{\text{bar}} \le 59$, cả 4 phách trong ô 4/4 nhận:<br>$V_{\text{thumb}}(q) = V_{\text{bar}} + (-4,\; 0,\; +4,\; +1)[q] \in [P.\text{floor\_calm},\; 63]$<br>*(và 3 phách ở 3/4, 6/8 nhận $V_{\text{bar}} + (-4,\; +4,\; 0)[q]$) — **bảo toàn chính xác tuyệt đối hiệu số `(-4, 0, +4, +1)` giữa các phách trong mọi ô ấm**!*<br>• Nốt màu đầu ô đổi hợp âm (`support`, ở `q = 0`) nhận đúng $V_{\text{thumb}}(0)$.<br>• 4 móc kép `a-m-i-a` (`lead`) của phách $q$ nhận đúng `_TREMOLO_FILL_OFFSETS = (-6, -3, -4, -6)`:<br>$V_{\text{fill}}(q, r) = \max\big(18,\; V_{\text{thumb}}(q) + (-6, -3, -4, -6)[r]\big) \le 60$. | Khi phách đỉnh $q^*$ (phách mạnh nhất của ô đỉnh) lọt Cổng Snap với lực $V_{\text{snapped}} \in [68, 72]$:<br>• Ngón cái `low` tại $q^*$ nhận $V_{\text{snapped}}$.<br>• Ngón `m` (`r == 1` trên `lead`) nhận $\min(V_{\text{snapped}} - 3,\; 69)$.<br>• Ba móc kép `a, i, a` (`r == 0, 2, 3` trên `lead`) và nốt màu `support` **bị kẹp cứng ở `<= 63`**: `i` nhận $\min(63,\; V_{\text{snapped}} - 4)$ và `a` nhận $\min(61,\; V_{\text{snapped}} - 6)$ (giữ nghiêm ngặt `thumb > m > i > a`). |
| **`etude1`**<br>(`guitar_villa.py:339`:<br>`_ETUDE1_ARC` `{-2, 0, +2}`) | • Hai nốt hát (`index 7, 9` trên `lead`) nhận $V_{\text{lead}}(7) = V_{\text{hat}}(t_7)$ và $V_{\text{lead}}(9) = V_{\text{hat}}(t_9) \in [V_{\text{floor}}, V_{\text{ceil}} \le 63]$.<br>• 13 móc kép bè trung (`support`) có tâm ô là $V_{\text{sup\_mid}} = \text{clamp}\big(V_{\text{sup\_curve}}(t_{\text{bar}}),\; P.\text{sup\_floor} + 2,\; \min(P.\text{sup\_ceil} - 2,\; \min(V_{\text{lead}}) - 8)\big)$. Nhờ tâm cách biên ít nhất `2`, từng móc kép thứ $i$ nhận:<br>$V_{\text{sup}}(i) = V_{\text{sup\_mid}} + \text{\_ETUDE1\_ARC}[i]$<br>*(Bảo toàn nguyên vẹn bậc thang `-2, 0, +2, 0, -2` không bị kẹp phẳng).*<br>• Bass đầu ô (`low`) nằm giữa đỉnh bè trung của ô đó và nốt hát:<br>$V_{\text{bass}} = \min\Big(61,\; \max\big(\max_{i} V_{\text{sup}}(i) + 2,\; \min(V_{\text{lead}}) - 4\big)\Big)$. | Khi câu chứa ô đỉnh lọt Cổng Snap với $V_{\text{snapped}} \in [68, 70]$:<br>• Chỉ **một nốt hát duy nhất trong ô đỉnh** (nốt `index 9` ngân dài 1.75 phách, hoặc nốt có cao độ cao hơn giữa `7` và `9`) nhận $V_{\text{snapped}}$, đúng quy tắc **1 cú tấn công mỗi đơn vị ngân sách**! Nốt hát còn lại trong ô giữ ở $\min(63,\; V_{\text{snapped}} - 5)$.<br>• Bass đầu ô giữ ở $\min(61,\; V_{\text{snapped}} - 6) \le 61$.<br>• 13 móc kép `support` giữ nguyên `<= 52`. |
| **`etude11`**<br>(`guitar_villa.py:476`:<br>`_etude11_middle_vel`) | • Gỡ `accent=True` mặc định trên các phách thường (`quarter 0..3`).<br>• Cú 1 của phách (`lead` tại `beat = q`) nhận `hairpin` mới là $V_{\text{q}} = V_{\text{hat}}(t_q) \in [V_{\text{floor}}, V_{\text{ceil}} \le 63]$.<br>• Cú 4 nhắc lại (`lead` tại `beat = q + 0.5`) nhận $V_{\text{echo}} = \max(P.\text{sup\_floor} + 6,\; V_{\text{q}} - 8)$.<br>• Bass đầu phách (`low`, ngân cả phách `1.0` beat) nhận $V_{\text{bass}} = \max(V_{\text{echo}} + 2,\; V_{\text{q}} - 4) \le 59$.<br>• 4 nốt sextuplet giữa (`slot in (1, 2, 4, 5)` trên `support`) **giữ nguyên 100% quy trình 4 bước của hàm `_etude11_middle_vel(hairpin, slot, band)` đang chạy**:<br>1) `echo = max(P.sup_floor, V_q - 8)`<br>2) `ceiling = max(P.sup_floor, echo if band == "f" else echo - 1)`<br>3) `shaped = min(ceiling, max(P.sup_floor, V_q + arch[slot] + band_nudge))`<br>4) `vel = max(P.sup_floor, shaped + _ETUDE11_TILT[slot])`<br>*(Ở `hairpin = 60` trên band `mf`, `echo = 52`, `ceiling = 51`, `shaped = [50, 51, 51, 50]`, cộng `_ETUDE11_TILT = {-1, -1, 0, +1}` ra đúng **`49, 50, 51, 51`** dưới trần `echo = 52`, và luôn `<= P.sup_ceil` là `55`).* | Khi phách đỉnh $q^*$ lọt Cổng Snap với $V_{\text{snapped}} \in [70, 74]$:<br>• Chỉ **cú 1 của `lead`** tại $q^*$ nhận $V_{\text{snapped}}$ và `accent=True`.<br>• Bass tại $q^*$ nhận $\min(62,\; V_{\text{snapped}} - 6)$ (kèm `accent=True`).<br>• Cú 4 `echo` nhận $\min(60,\; V_{\text{snapped}} - 10)$.<br>• 4 nốt sextuplet `support` truyền `hairpin = min(63, V_q)` vào công thức 4 bước trên nên vẫn nằm dưới trần `echo` (`<= 55`) và giữ nguyên hình bậc thang `49, 50, 51, 51`. |
| **`preludio`**<br>(*La Catedral*) | • Nốt Canto 1 (`pitch_a`, móc kép `0`) nhận $V_{\text{canto1}} = V_{\text{hat}}(t) \in [V_{\text{floor}}, V_{\text{ceil}} \le 62]$.<br>• Nốt Canto 2 (`pitch_b`, móc kép `6`) nhận $V_{\text{canto2}} = \max(P.\text{floor\_calm} - 2,\; V_{\text{canto1}} - 2)$.<br>• 6 móc kép sóng chữ V (`support`) nhận mức miệng chữ V là $V_{\text{v\_top}} = \min\big(V_{\text{sup\_curve}}(t),\; V_{\text{canto2}} - 8\big) \in [20, 46]$, và đáy chữ V (`slot 3`) nhận $V_{\text{v\_top}} - 2 \ge 18$.<br>• Bass ngân 2 ô (`low`) nhận $\min(V_{\text{canto2}} - 4,\; \max(V_{\text{v\_top}} + 3,\; V_{\text{bass\_curve}}(t)))$. | Khi nốt Canto 1 tại đỉnh bài lọt Cổng Snap (`66..68`):<br>• Chỉ **Canto 1 (`pitch_a`)** nhận $V_{\text{snapped}} \in [66, 68]$.<br>• Canto 2 (`pitch_b`) giữ ở $\min(62,\; V_{\text{snapped}} - 4)$.<br>• Sóng chữ V `support` giữ nguyên `<= 46`. |

#### C. Công Thức Cổng Ép Dây Hiếm (`Rare Snap Gate` — Theo Từng Section, Luôn Rơi Vào `[66, V_snap]`)

1. **Tín hiệu kích hoạt Snap $S_{\text{snap}}(t) \in [0.0, 1.0]$**:
   Kết hợp sóng thanh khoản $U_{\text{vol}}(t)$ và hơi thở câu nhạc $C_{\text{phrase}}(t)$:
   $$S_{\text{snap}}(t) = 0.70 \cdot U_{\text{vol}}(t) + 0.30 \cdot C_{\text{phrase}}(t) \in [0.0, 1.0]$$
   Một cú gảy (hoặc cụm nhát nhấn) tại thời điểm $t$ trong `section` được đưa vào danh sách ứng viên khi thỏa **cả 4 điều kiện**:
   - Pattern tại ô đó có $P.\text{snap\_wide} \ne \text{None}$ (tức $V_{\text{snap}}(\alpha_{\text{price}}) \in [66, 76]$).
   - Section chứa ô đó có **biên độ giá $\alpha_{\text{price}} \ge 0.25$** (riêng pattern `elogio_pizz` của Brouwer: nếu $\alpha_{\text{price}} < 0.25$, vẫn cho phép cú *Bartók slap* nhưng giới hạn trần $K_{\text{sec}} = 1$ cú duy nhất tại đỉnh $S_{\text{snap}}(t)$ cao nhất của cả section với $V_{\text{snap}} = P.\text{snap\_calm} = 72$).
   - Tín hiệu tại thời điểm đó thỏa **$S_{\text{snap}}(t) \ge 0.70$** *(đảm bảo cả trên đoạn `trio`/`bridge` khi $\alpha_{\text{price}} \ge 0.25$, nơi $U_{\text{vol}}(t)$ và $C_{\text{phrase}}(t)$ vẫn chạy đủ `[0.0, 1.0]`, đỉnh của đoạn vẫn qua được ngưỡng `0.70`!)*.
   - Cú đó khớp với quy tắc `snap_targets` của pattern (xem Bảng Mục 3).

2. **Đơn vị Ngân sách (`Snap Unit`) & Hạn mức trên từng Section ($K_{\text{sec}}$)**:
   - **Một Đơn vị Ngân sách (`1 Snap Unit`)**:
     - Thông thường: là **1 cú tấn công đơn lẻ trên Bè Hát Chính** (trên `etude1`, chỉ lấy 1 nốt hát cao nhất trong ô đỉnh; hoặc 1 khối hợp âm Fanfare / Sarabande beat 2 / Slap).
     - Với **`villa_pattern` (*Tresillo* `{0, 3, 6}`)**: cả bộ 3 nhát nhấn `{0, 3, 6}` trong cùng một ô `tresillo` được tính gộp là **1 đơn vị ngân sách (`1 Snap Unit`)**.
   - **Ngân sách của từng Section**:
     - Khi $\alpha_{\text{price}} < 0.25$: $K_{\text{sec}} = 1$ nếu `pattern == "elogio_pizz"`, ngược lại $K_{\text{sec}} = 0$.
     - Khi $\alpha_{\text{price}} \ge 0.25$: Đếm $N_{\text{mel, sec}}$ là số cú tấn công có cao độ của Bè Hát Chính **bên trong chính section đó** (`midi is not None and not tie_stop`; với `tremolo`, mỗi phách đen tính là 1 cú). Số đơn vị Snap tối đa của section đó là:
       $$K_{\text{sec}} = \min\Big(P.\text{max\_units\_per\_sec},\; \max\big(1,\; \lfloor 0.045 \cdot N_{\text{mel, sec}} \rfloor\big)\Big)$$
   - **Thứ tự lọc ứng viên trong mỗi Section**:
     1. Trong mỗi `Phrase` thuộc section, giữ tối đa `P.max_units_per_phrase` đơn vị ứng viên (mặc định `1`) có $S_{\text{snap}}(t)$ cao nhất.
     2. Trên toàn section, xếp hạng các đơn vị ứng viên theo $S_{\text{snap}}(t)$ giảm dần và giữ tối đa $K_{\text{sec}}$ đơn vị.

3. **Công thức tính $V_{\text{snapped}}$ (Bảo đảm luôn thuộc `[66, V_snap]`)**:
   $$V_{\text{snapped}}(t) = \text{round}\left(66 + \big(V_{\text{snap}}(\alpha_{\text{price}}) - 66\big) \cdot \frac{\text{clamp}(S_{\text{snap}}(t), 0.70, 1.00) - 0.70}{0.30}\right) \in \big[66,\; V_{\text{snap}}(\alpha_{\text{price}})\big]$$

#### D. Phạm Vi Áp Dụng Pass Xếp Tầng 3 Bè (`Simultaneous Voice Ordering`)

Pass xếp tầng 3 bè tại cùng một thời điểm phát âm $t$ chỉ chạy trên các pattern thông thường, với quy tắc phân nhánh rõ ràng theo từng loại pattern:
1. **Bỏ qua (Exempt) đối với `tremolo` và `etude11`**:
   - Vì `tremolo` có `low (thumb) > lead (fill a-m-i)` và `etude11` có `low (bass đầu phách) > lead (cú echo nửa sau phách)`, hai pattern này đã được khóa thứ tự nội bộ tại Mục 2.5B và không chạy qua pass `lead > low`.
2. **Với `thumb_cantabile`**:
   - Thứ tự là $\text{low} > \text{lead} \ge \text{support}$: cụ thể $\text{low} \ge \text{lead} + 4$ và giữa hai nốt dyad chập phách yếu: $\text{lead} \ge \text{support} + 1$ (khi $\text{lead} \ge 20$, $\text{support} \ge 18$).
3. **Với `bach_fuga` và các khối chập đồng thời (Block Accent / Frame Chord)**:
   - Trên `bach_fuga`: $\text{lead} \ge \text{low}$ và $\min(\text{lead}, \text{low}) \ge \text{support} + 2$.
   - Trên các khối chập hợp âm đồng thời (Fanfare, Stab, Slap, Block chord trong `guitar_frame.py`): $\text{lead} \ge \text{low} \ge \text{support}$.
4. **Với tất cả các pattern còn lại (`lead` hát giai điệu)**:
   - Thứ tự nghiêm ngặt tại cùng một thời điểm phát âm là $\text{lead} > \text{low} > \text{support}$:
     - Khi $\text{lead} \ge 30$: $\text{low} \le \text{lead} - 3$ và $\text{support} \le \text{low} - 2$.
     - Khi $22 \le \text{lead} < 30$ (vùng thì thầm $ppp$): thu khoảng cách tối thiểu về `2` đơn vị ($\text{low} \le \text{lead} - 2$ và $\text{support} \le \text{low} - 2$).
     - Nếu $\text{lead} < 22$ mà có đủ cả 3 bè cùng kêu: nâng nhẹ $\text{lead} = 22, \text{low} = 20, \text{support} = 18$.

---

## 3. Bảng Khóa Thông Số Theo Từng `(ensemble, pattern)` (`PatternWaveProfile`) Cho 5 Đại Sư

Khóa tra cứu là tuple **`(ensemble, pattern)`**. Mọi dòng đều thỏa `floor_calm <= floor_wide` và `ceil_calm <= ceil_wide <= 63`:

```python
@dataclass(frozen=True)
class PatternWaveProfile:
    floor_calm: int            # Sàn bè hát khi section êm (alpha_warm = 0), >= 20
    floor_wide: int            # Sàn bè hát khi section sóng lớn (alpha_warm = 1), >= floor_calm
    ceil_calm: int             # Trần ấm bè hát khi section êm (alpha_warm = 0), <= 60
    ceil_wide: int             # Trần ấm bè hát khi section sóng lớn (alpha_warm = 1), <= 63
    snap_calm: int | None      # Trần ép dây khi vừa qua ngưỡng (None nếu cấm ép dây, >= 66 nếu có)
    snap_wide: int | None      # Trần ép dây tối đa khi alpha_price = 1 (68..76)
    bass_floor: int            # Sàn bè trầm (hoặc bè lead đệm ở thumb_cantabile)
    bass_ceil: int             # Trần ấm bè trầm (<= 60)
    sup_floor: int             # Sàn bè trung (>= 18)
    sup_ceil: int              # Trần ấm bè trung (<= 55)
    gamma: float               # Độ võng đường cong E_vol(t) = U_vol(t)^gamma
    max_units_per_phrase: int  # Số đơn vị Snap tối đa trong 1 Phrase (0 hoặc 1)
    max_units_per_sec: int     # Trần tuyệt đối số đơn vị Snap trong 1 Section (0..4)
    snap_targets: str          # Quy tắc chọn cú được phép qua cổng Snap
```

### Bảng Đầy Đủ 28 Khóa `(ensemble, pattern)` Của 5 Đại Sư

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
| `("villa", "etude1")` | `28 .. 58` $\to$ `32 .. 63` | `68 .. 70` | `24 .. 58` | `22 .. 52` | `1.20` | `(1, 2)` | 1 nốt hát cao nhất (`index 9` hoặc `7`) tại đúng ô đỉnh cao trào của section. |
| `("villa", "etude11")` | `28 .. 58` $\to$ `32 .. 63` | `70 .. 74` | `24 .. 58` | `22 .. 55` *(sextuplets)* | `1.20` | `(1, 3)` | Chỉ cú 1 `lead` tại phách `phrase.apex` (các phách khác gỡ `accent`; 4 nốt giữa dưới trần `echo <= 55`). |
| `("brouwer", "noviembre")` | `22 .. 52` $\to$ `26 .. 58` | `None` *(0% snap)* | `20 .. 50` | `18 .. 42` | `1.45` | `(0, 0)` | Tuyệt đối 0% ép dây (`22 > 20 > 18` khớp sàn 3 bè). |
| `("brouwer", "sarabande")` | `24 .. 56` $\to$ `28 .. 62` | `68 .. 72` | `22 .. 56` | `18 .. 48` | `1.35` | `(1, 2)` | Chỉ hợp âm nhấn phách 2 tại đỉnh cao trào; swarm giữ `<= 62`. |
| `("brouwer", "brouwer_etude")` | `24 .. 58` $\to$ `28 .. 63` | `68 .. 72` | `22 .. 58` *(tumbao)* | `20 .. 50` | `1.15` | `(1, 3)` | Cú nhấn downbeat/tumbao (`accent=True`) ở các ô đỉnh sóng. |
| `("brouwer", "elogio_pizz")` | `24 .. 56` $\to$ `28 .. 62` | `72 .. 76` *(Bartók slap)* | `22 .. 56` | `20 .. 48` | `1.15` | `(1, 4)` | Cú vỗ *Bartók slap* ở móc đơn thứ 3 (`slap = start + 3`, `lead 72..76, low 68..70, sup 64..66`; khi $\alpha_{\text{price}} < 0.25$ thì $K_{\text{sec}} = 1$). |

---

## 4. Đường Cong Riêng Cho Khung Intro & Outro (`guitar_frame.py`)

Trong code hiện tại, `guitar_frame.py` đặt `_PP = 46`, `_P = 50`, `_MP = 56`, `_MF = 64` (kể cả `_edge_stab` và `_stab_and_ring` của Brouwer cũng đang viết ở `_MF = 64`), và các ô `pedal` bị `_shape_dynamics` bỏ qua.

Khi đưa vào `apply_guitar_wave()`:
1. **Chỉ các ô `pedal` (`intro`, `warmup`, `outro`, `cooldown`) mới đi đường bao mờ biên (Frame Emergence / Morendo Envelope)**:
   - Phần thân bài hoàn toàn không bị nhân mờ biên $T_{\text{edge}}$, giúp bảo toàn nguyên vẹn đỉnh thanh khoản lúc mở cửa (ATO/đầu phiên) và đóng cửa (cuối phiên).
   - Trong vùng `pedal`, bảo toàn cấu trúc chênh lệch tương đối giữa các nốt bên trong từng cử chỉ của `guitar_frame.py` (ví dụ contour chuông `44, 50, 46` hay cantabile `46 -> 52` của Barrios).
   - **Intro (`leading` pedal bars)**:
     - Đặt mục tiêu nối biên $V_{\text{join}} = V_{\text{hat}}(t_{\text{body\_start}}) \in [V_{\text{floor}}, V_{\text{ceil}} \le 63]$ là mức vận tốc của móc đơn đầu tiên trong thân bài (nếu ô đầu thân bài là đỉnh thanh khoản thì $V_{\text{join}} = V_{\text{ceil}}$ lên tới `63`).
     - Các ô Intro đứng trước ô nối cuối cùng (`bar < last_intro_bar`, với `last_intro_bar = leading[-1]`) được dịch theo đường bao khởi âm từ **$ppp - pp$ (`22..32` ở đầu ô 0)** lên tối đa **`<= 56`** (giữ nguyên độ lệch tương đối bên trong từng cử chỉ như chuông `44, 50, 46` hay cantabile `46 -> 52`).
     - **Trên ô nối cuối cùng của Intro (`last_intro_bar = leading[-1]`) — Dịch nguyên cử chỉ để giữ khoảng cách nội bộ và neo nốt cuối bằng đúng $V_{\text{join}}$**:
       Không nội suy phẳng làm mất hình dáng cử chỉ của `last_intro_bar`; thay vào đó, tính một độ dịch chung $\Delta_{\text{join}} = V_{\text{join}} - V_{\text{written\_last}}$ (với $V_{\text{written\_last}}$ là velocity viết sẵn của nốt cuối cùng trên bè hát trong `last_intro_bar`), rồi cộng $\Delta_{\text{join}}$ cho toàn bộ các nốt của cử chỉ trong `last_intro_bar` (kẹp sàn `>= 20` và kẹp trần `<= max(56, V_join)`). Nhờ đó, **nốt cuối cùng của Intro bằng đúng $V_{\text{join}}$** trong khi các nốt đứng trước trong cùng cử chỉ của `last_intro_bar` vẫn **giữ nguyên 100% khoảng cách tương đối** so với nốt cuối!
   - **Outro (`trailing` pedal bars)**: Áp dụng hàm suy giảm mũ (**Morendo Curve**) bắt đầu từ đúng mức cuối thân bài $V_{\text{hat}}(t_{\text{body\_end}})$ hạ dần về **`20..26` ($ppp$)** ở ô cuối cùng (hợp âm chuông / Picardy third tan dần).
2. **Một bộ số thống nhất cho các cú Stab kịch tính trong Frame (`70 / 66 / 62`, thấp hơn Bartók slap `72..76` của thân bài)**:
   - Tại nhánh kịch tính `edge == True` của Brouwer (`_edge_stab` ở đầu Intro và `_stab_and_ring` ở cuối Outro) và nhánh `bright == True` (`_stabs` ở cuối Outro của Villa): các nốt mang đồng thời `staccato=True` và `accent=True` (hoặc thuộc `_stabs` cuối bài) được gán **một bộ số duy nhất**:
     - `lead`: **`70`**
     - `low`: **`66`**
     - `support`: **`62`** (giữ dưới ngưỡng `65`)
   - Nhờ đó, cú stab ở khung Intro/Outro sắc gọn (`70 / 66 / 62`) nhưng luôn đứng thấp hơn cú vỗ *Bartók slap* ở đỉnh thân bài `elogio_pizz` (`72..76 / 68..70 / 64..66`).

---

## 5. Lộ Trình Triển Khai 5 Bước (Implementation Order)

1. **Bước 1 — Truyền `bar_volumes` (cường độ mỗi nến) và khóa bảng `PatternWaveProfile` trong `backend/app/sonify/guitar_wave.py`**:
   - Tính `bar_volumes: list[float]` theo từng ô nhịp trong `render.py` (`average_liquidity([_window_candles(bars, groups, b, 1) for b in range(musical_bars)])`) và truyền vào `render_guitar_score()` $\to$ `render_patterned_voices()` $\to$ `_Ctx` (fallback về `band_at` khi `bar_volumes is None`).
   - Khai báo đầy đủ 28 cặp `(ensemble, pattern)` của 5 đại sư với `floor_calm <= floor_wide`, `ceil_calm <= ceil_wide <= 63`, `snap_calm / snap_wide`, `max_units_per_phrase`, `max_units_per_sec`, `gamma`, và `snap_targets`.
   - Viết bộ làm mượt Volume 4 bước: $\ln(1+V)$ $\to$ 5-tap zero-phase filter `[1, 4, 6, 4, 1]/16` $\to$ **Range-Lock trực tiếp trên $u(b) \in [0.0, 1.0]$** $\to$ nội suy cosine từng móc đơn $U_{\text{vol}}(t)$.
   - Đặt **Đường bao trần trực tiếp theo Volume** $V_{\text{env}}(t) = V_{\text{floor}} + U_{\text{vol}}(t)^\gamma \cdot (V_{\text{ceil}} - V_{\text{floor}})$, và chỉ cho câu nhạc thở lùi nhẹ bên dưới đường bao $\Delta_{\text{phrase}}(t) = -D_{\max} \cdot (1 - C_{\text{phrase}}(t)) \cdot (1 - U_{\text{vol}}(t)^4) \le 0$. Nhờ đó, tại mọi ô đỉnh thanh khoản ($u(b^*) = 1.0$, kể cả ở mở cửa hay đóng cửa), $V_{\text{hat}}(t^*)$ luôn chạm đúng $V_{\text{ceil}}$ và không một ô volume thấp hơn nào có thể vượt qua!

2. **Bước 2 — Viết bộ Rebase `apply_guitar_wave()` thay thế `_shape_dynamics()` sau khi pattern đã sinh nốt**:
   - Xử lý riêng từng nhóm cấu trúc:
     - **`tremolo`**: lấy **một mốc $V_{\text{bar}} \in [P.\text{floor\_calm}+4, 59]$ chung cho cả ô**, cộng `_TREMOLO_QUARTER_OFFSETS` (`(-4, 0, +4, +1)` cho 4/4; `(-4, +4, 0)` cho 3/4 và 6/8) và `_TREMOLO_FILL_OFFSETS` (`(-6, -3, -4, -6)`).
     - **`etude1`**: giữ `_ETUDE1_ARC`, tính bass theo `min(61, max(max_sup_in_bar + 2, lead - 4))`, và khi snap chỉ lấy 1 nốt hát cao nhất trong ô đỉnh.
     - **`etude11`**: giữ nguyên quy trình 4 bước của `_etude11_middle_vel` (**kẹp trần `echo` trước rồi mới cộng `_ETUDE11_TILT`**) để ở `hairpin = 60` vẫn ra đúng `49, 50, 51, 51` dưới trần `echo = 52` (`<= 55`); gỡ `accent` ở các phách thường.
     - **`preludio`**, **`thumb_cantabile`** và các pattern thường: rebase theo 3 đường cong và chạy pass xếp tầng 3 bè (bỏ qua `tremolo` và `etude11`).
     - **Khung `pedal` (`intro`/`outro`)**: chạy đường bao Emergence / Morendo riêng; gán bộ số thống nhất `70 / 66 / 62` cho các cú stab kịch tính.
   - Chạy **Cổng Snap (`Rare Snap Gate`)** trên từng section khi $\alpha_{\text{price}} \ge 0.25$ (hoặc $K_{\text{sec}} = 1$ cho `elogio_pizz` khi $\alpha_{\text{price}} < 0.25$) và $S_{\text{snap}}(t) \ge 0.70$, ánh xạ vào `[66, V_snap]`, tính *Tresillo* `{0, 3, 6}` là 1 đơn vị ngân sách, và kẹp cứng các nốt đệm đi kèm trong cụm ở `<= 63`.
   - Đồng bộ toàn bộ các nốt nối dây (`tie_stop=True` nhận đúng velocity của cú `tie_start` mở chuỗi).

3. **Bước 3 — Thêm chốt chặn hậu kiểm sau `humanize()` cho cả 2 vùng Ấm và Snap**:
   - Trên đường guitar (`score.variant == "guitar"`):
     - Mọi nốt có `written_velocity <= 64` trước `humanize` được kẹp `heard_velocity = min(64, heard_velocity)`.
     - Mọi nốt đã được Snap (`written_velocity >= 65`) được kẹp `heard_velocity = max(66, min(76, heard_velocity))` để `humanize` không đẩy vượt trần `76` khi gặp một cụm snap đồng lực.

4. **Bước 4 — Viết `backend/tests/test_guitar_wave.py` và cập nhật `backend/tests/test_sonify_guitar.py`**:
   - Cập nhật các assertion số tuyệt đối cũ (`56, 60, 64, 72`) trong `test_sonify_guitar.py` sang kiểm tra khoảng động lực học mới và cấu trúc tương đối.
   - Trong `test_guitar_wave.py`, kiểm tra đủ 7 tiêu chí:
     1. **Làm mượt Volume & Cực Đại/Cực Tiểu Trên Tập Ô Cực Trị Của Section (kể cả ở biên mở/đóng cửa)**: một chuỗi volume trên section tạo ra tập ô đáy $\mathcal{B}_{\min} = \{b_* \mid u(b_*) == 0.0\}$ đều chạm đúng **$V_{\text{floor}}$** và tập ô đỉnh $\mathcal{B}_{\max} = \{b^* \mid u(b^*) == 1.0\}$ (đặt ở đầu phiên, giữa phiên hoặc cuối phiên) **tất cả đều bằng đúng $V_{\text{ceil}}$**; cả hai chiều bước vào (móc đơn cuối của ô đứng trước $b^*$ chạm đúng `1.0`) và bước ra (móc đơn đầu của ô đứng sau $b^*$ mở đúng tại `1.0` theo $r(k) = k / (\text{epb} - 1)$ rồi hạ về $u_{\text{end}}$ ở móc đơn cuối) đều liên tục qua vạch nhịp; và giữa hai ô trung gian có volume sát nhau, độ lệch ngược chiều tối đa không vượt quá **`3` đơn vị MIDI (đúng bằng $D_{\max} = 3$)** khi một ô ở đỉnh câu ($\Delta = 0$) và ô kia ở biên câu ($\Delta = -3$).
     2. **Phiên `calm` biên độ giá hẹp ($\alpha_{\text{price}} < 0.25$) nhưng có sóng Volume chữ U**: sóng ấm vẫn mở rộng từ $ppp - pp$ (`<= 34`) lên `56..63` theo $\alpha_{\text{warm}}$, nhưng **Cổng Snap đóng hoàn toàn (`0%` nốt vượt `64` sau `humanize`)** trên mọi pattern trừ tối đa `1` cú slap của `elogio_pizz`.
     3. **Phiên biến động giá rộng ($\alpha_{\text{price}} \ge 0.50$) kiểm tra theo `PatternWaveProfile`**:
        - Với các pattern có `snap_wide is None` (`cantabile`, `andante`, `chord_melody`, `noviembre`, `bach_sarabande`): **0% số nốt vượt `64`** kể cả trong phiên `rally` / `volatile`.
        - Với các pattern có `snap_wide is not None`: có ít nhất `1` đơn vị Snap rơi vào `[66, P.snap_wide]`, số đơn vị Snap không vượt quá `K_sec`, và không nốt nào sau `humanize` vượt quá `76` (hoặc `70` với Bach/Sor).
     4. **Bảo toàn delta vi mô ở vùng ấm**: trong một ô `tremolo` ấm, 4 phách giữ **đúng hiệu số `(-4, 0, +4, +1)`** (hoặc `(-4, +4, 0)` ở 3/4, 6/8) và `thumb` lớn hơn `m` đúng `3`; trong `etude1`, bass luôn nằm giữa `support` và `lead` kể cả khi `lead` thì thầm ở `32`; trong `etude11`, 4 nốt sextuplet giữ nguyên hình bậc thang `arch + tilt` (như `49, 50, 51, 51` ở `hairpin = 60`, nằm dưới trần `echo = 52`).
     5. **Cụm Snap không kéo nốt đệm qua `65`**: tại phách `tremolo` hoặc `etude11` được snap (`68..74`), các móc kép `a, i` của tremolo và 4 nốt sextuplet giữa của `etude11` vẫn `<= 63` (và dưới trần `echo <= 55`); trên `etude1`, chỉ 1 nốt hát trong ô đỉnh nhận snap.
     6. **$\alpha_{\text{price}}$, $\alpha_{\text{vol}}$ và ngân sách Snap tách biệt theo từng section trên `1M`**: một chương `1M` có section đi ngang ($\alpha_{\text{price}} = 0$) và section biến động mạnh ($\alpha_{\text{price}} = 1$), cộng đoạn `trio`/`bridge` (nơi $\alpha_{\text{warm}}$ nhân `0.50` nhưng $U_{\text{vol}}$ vẫn chạy đủ `[0, 1]`), giữ đúng 0% snap ở section đi ngang và giữ cửa sổ ấm của `trio`/`bridge` dịu hơn phần A.
     7. **Bất biến thứ tự bè theo đúng phân loại pattern**: `lead > low > support` trên các pattern thường, `low (thumb) > lead (fill)` trên `tremolo`, `low > lead > support` trên `thumb_cantabile`, và cho phép `>=` trên các khối accent đồng thời / `bach_fuga`.

5. **Bước 5 — Thực nghiệm nghe 3 mốc `24 / 64 / 74` trên MS Basic Nylon trước khi bump Revision**:
   - Trước khi tăng `RECAP_REVISION` và `SPAN_REVISION` trong `backend/app/sonify/audio.py`, xuất WAV khô thử nghiệm với 3 mức velocity `24` ($ppp$), `64` (trần ấm), và `74` (đỉnh snap) qua `musescore_export` trên MS Basic Nylon để kiểm tra độ rõ trên nền `_GUITAR_NOISE = 0.0003` và độ tách lớp mẫu giữa `64` và `74`.
