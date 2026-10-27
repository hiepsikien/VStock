# Kế Hoạch Filter Sóng Volume (Affine) Cho Động Lực Học Guitar

> **Mục tiêu**: Đưa tiếng đàn guitar cổ điển từ dải hẹp `44..78` vào cửa sổ âm sắc của từng genre, bằng một **bộ lọc affine** trên vận tốc đã viết. Sóng volume đã làm mượt chỉ dời cả khối nốt. Mọi chênh lệch vi mô đã có trong bản nhạc — swell trong câu, accent, offset trong ô, khoảng cách giữa các bè — được giữ nguyên tỉ lệ.
>
> **Liên kết**: [`docs/sonify-classical-guitar.md`](./sonify-classical-guitar.md), [`docs/sonify-barrios-tremolo-dynamics.md`](./sonify-barrios-tremolo-dynamics.md), [`docs/sonify-humanize-preset-plan.md`](./sonify-humanize-preset-plan.md).

---

## 1. Chẩn Đoán

Pipeline guitar (`guitar.py`, `guitar_patterns.py`, `guitar_barrios.py`, `guitar_villa.py`, `guitar_frame.py`, `dynamics.py`, `humanize.py`) đang nén lực gảy vì bốn lý do:

| Điểm nghẽn | Con số đang chạy | Hệ quả |
|---|---|---|
| **1. Nền viết sẵn sát ngưỡng móng** | `_MELODY = 64`, `_MELODY_APEX = 72`, `_INNER = 56`, `_BASS = 60`. Swell `60 / 68 / 62`. Etude mở `60`, đỉnh `72`. | Giai điệu đứng ở `60..72`. Chưa có nốt viết ở $ppp$ (`~18..26`) hay $pp$ (`~28..36`). |
| **2. `_shape_dynamics` cộng band rồi kẹp `[44, 78]`** | `_BAND_DELTA = {p: -12, mp: -6, mf: 0, f: +4}`, cộng `extra` của câu (`0..+4`), rồi `max(44, min(78, ...))`. Nốt `>= 72` được bỏ qua. *La Catedral* khóa lead `54..64`, support `48..55`. | Band 4 bậc là thủy triều thô. Sàn `44` chặn $ppp$. Vi mô thật sự nằm trong vận tốc pattern và trong `extra`. |
| **3. Volume bị cắt thành 4 chữ** | `dynamics.py` gom cửa sổ 4–6 ô thành `"p" / "mp" / "mf" / "f"`. Khi `high / low < 2` cả bài thành `"mf"`. | Mất sóng thanh khoản liên tục (đầu phiên → trũng giữa phiên → cuối phiên). |
| **4. Humanize chưa biết trần nylon** | `humanize` nhích `{-2..+2}` và chỉ kẹp `1..127`. | Nốt ấm `63` có thể thành `65` (tiếng móng). Cụm snap `76` có thể bị đẩy vượt `76`. |

### Ba vùng âm sắc trên MS Basic Nylon

`NoteEvent.velocity` xuất ra MusicXML thành `<note dynamics="V * 100 / 90">`.

1. **Thì thầm — $ppp$ đến $pp$ (`18..38`)**: dây nylon mềm, *sul tasto*.
2. **Ấm — $p$ đến $mp+$ (`40..64`, nghiêm ngặt `< 65`)**: mọi nốt không snap dừng ở **`<= 63` trước `humanize`** và **`<= 64` sau `humanize`**.
3. **Ép dây hiếm — $mf+$ đến $f$ (`66..76`, tuyệt đối `<= 76`)**: chỉ các cú đã qua Cổng Snap trên pattern có kỹ thuật tì / giật dây thật.

### Bản trên nhánh hiện tại

`apply_guitar_wave()` đang **thay** `_shape_dynamics` và gán vận tốc mới từ đường bao $V_{\text{hat}}(t)$. `_assign_generic` bỏ `event.velocity`. Bốn pattern `tremolo`, `etude1`, `etude11`, `preludio` dựng lại một vài offset cứng từ bảng. Những hình đã viết mà không nằm trong bảng bị mất. Thiết kế dưới đây thay bước gán đó.

---

## 2. Mô Hình: Sóng Là Thủy Triều, Vi Mô Là Vận Tốc Đã Viết

### 2.1. Vị trí trong pipeline

`average_liquidity` trong `render.py` trả về **cường độ khớp lệnh trên mỗi nến** của ô nhịp `b`, sau khi bỏ nến ATO/ATC và kẹp spike ở `CLIP_MULTIPLE = 4.0` lần trung vị dương của cả bài.

```text
render.py (_compose)
  ├── bar_volumes[b] = average_liquidity(nến của ô b)
  └── truyền vào render_guitar_score() → render_patterned_voices() → _Ctx
        ├── có bar_volumes: dùng chuỗi thật
        └── bar_volumes is None (fixture): khôi phục từ band_at
              {"p": 1.0, "mp": 2.0, "mf": 4.0, "f": 8.0}
```

Thứ tự guitar:

```text
render_patterned_voices()
  ├── 1. Sinh nốt theo pattern và frame
  │      Vận tốc pattern (offset trong ô, accent, cung etude, chữ V, tremolo)
  │      đã là vi mô.
  ├── 2. _repair() & _resolve() & _slur()
  ├── 3. _shape_dynamics()
  │      Giữ `extra` của câu nhạc (0..+4) trên vận tốc đã viết.
  │      Bỏ _BAND_DELTA. Thủy triều thuộc về sóng volume, để band 4 bậc
  │      không bị cộng một lần nữa.
  ├── 4. apply_guitar_wave()
  │      Một phép affine cho mọi nốt sounding trong ô:
  │      V_ra = round(C(U) + M * (V_đã_viết - 64))
  │      Rồi Cổng Snap nâng một vài cú đã chọn vào 66..76.
  └── 5. humanize()
         written <= 64  →  heard = min(64, heard)
         written >= 65  →  heard = max(66, min(76, heard))
```

`64` là `_MELODY`, tâm vận tốc đã viết. Mọi bè dùng cùng tâm này.

### 2.2. Làm mượt volume thành $U(b) \in [0, 1]$

Với mỗi `FormSection` thân bài `[sec_start, sec_end)`:

**Bước A — log.** $v(b) = \max(0,\; \text{bar\_volumes}[b])$, rồi

$$\ell(b) = \ln\big(1 + v(b)\big)$$

Log nằm ở đây để một phiên gấp nhiều lần volume chỉ nhích $\ell$, không kéo $C$ văng khỏi cửa sổ genre.

**Bước B — trung bình trượt của các ô gần nhất.** Cửa sổ $W = 5$, lấy lùi về phía các ô đã qua trong cùng section (ô hiện tại tính vào cửa sổ). Đầu section dùng số ô đang có:

$$\tilde{\ell}(b) = \frac{1}{|W_b|} \sum_{j \in W_b} \ell(j), \qquad W_b = \{\,j \mid \max(\text{sec\_start},\; b - W + 1) \le j \le b\,\}$$

Một giá trị cho cả ô. Vi mô trong ô nằm ở $V_{\text{đã viết}}$, nên không nội suy $U$ theo từng móc đơn.

**Bước C — chuẩn hóa trong section.**

- Nếu $\max \tilde{\ell} - \min \tilde{\ell} \le 10^{-6}$ (volume phẳng): $U(b)$ lấy theo band của ô, `{"p": 0.15, "mp": 0.40, "mf": 0.65, "f": 0.90}`. $C$ gần như đứng yên. Vi mô giữ nguyên.
- Nếu có biến thiên:

$$U(b) = \frac{\tilde{\ell}(b) - \min \tilde{\ell}}{\max \tilde{\ell} - \min \tilde{\ell}} \in [0, 1]$$

Ô thanh khoản đã làm mượt thấp nhất nhận $U = 0$. Ô cao nhất nhận $U = 1$.

### 2.3. Cửa sổ genre và ba hằng số

`PatternWaveProfile` khóa cửa sổ đầu ra theo `(ensemble, pattern)`. $\alpha_{\text{warm}}$ của section chọn một cửa sổ nằm giữa hai đầu calm / wide:

$$\begin{aligned}
\alpha_{\text{price}} &= \mathrm{clamp}\left(\frac{\text{rel\_span}_{\text{sec}} - 0.004}{0.024 - 0.004},\; 0,\; 1\right) \\
\alpha_{\text{vol}} &= \mathrm{clamp}\left(\frac{\ln(\text{vol\_ratio}_{\text{sec}}) - \ln 1.35}{\ln 3.50 - \ln 1.35},\; 0,\; 1\right) \\
\alpha_{\text{warm}} &= \max(\alpha_{\text{price}},\; 0.75 \cdot \alpha_{\text{vol}})
\end{aligned}$$

$\text{vol\_ratio}_{\text{sec}}$ là phân vị 90 / phân vị 10 của $\tilde{v} = \exp(\tilde{\ell}) - 1$. Fixture volume hằng số ($\text{vol\_ratio} \le 1.01$) đặt $\alpha_{\text{vol}} = \alpha_{\text{price}}$.

$$\begin{aligned}
V_{\text{floor}} &= \mathrm{round}\big(P.\text{floor\_calm} + \alpha_{\text{warm}} \cdot (P.\text{floor\_wide} - P.\text{floor\_calm})\big) \\
V_{\text{ceil}} &= \mathrm{round}\big(P.\text{ceil\_calm} + \alpha_{\text{warm}} \cdot (P.\text{ceil\_wide} - P.\text{ceil\_calm})\big) \le 63
\end{aligned}$$

Đoạn `trio` / `bridge` nhân $\alpha_{\text{warm}}$ với $\kappa_{\text{sec}} = 0.50$ trước khi tính cửa sổ, nên cửa sổ co về phía calm. $U$ trong đoạn đó vẫn chạy đủ `[0, 1]`.

Dải lệch đã viết dùng để khóa biên, mặc định chung cho mọi genre:

$$d_{\text{lo}} = -16, \qquad d_{\text{hi}} = +8$$

Tức nốt mềm nhất mà bộ lọc hứa giữ hết độ lệch là `48` ($64 - 16$), nốt mạnh nhất là `72` ($64 + 8$, `_MELODY_APEX`). Một profile có bè viết thấp hơn `48` khai báo `d_lo` thấp hơn trên chính dòng đó, để hệ số $M$ hấp thụ khoảng này.

Ba hằng số của section, tính một lần từ cửa sổ và dải lệch:

$$\begin{aligned}
M &= \min\left(1,\; \frac{V_{\text{ceil}} - V_{\text{floor}}}{d_{\text{hi}} - d_{\text{lo}}}\right) \\
C_{\text{lo}} &= V_{\text{floor}} - M \cdot d_{\text{lo}} \\
C_{\text{hi}} &= V_{\text{ceil}} - M \cdot d_{\text{hi}}
\end{aligned}$$

$M$ là hằng số của **cả section**. $C$ đổi theo từng ô:

$$C(b) = C_{\text{lo}} + U(b) \cdot (C_{\text{hi}} - C_{\text{lo}})$$

### 2.4. Phép lọc

Với mọi nốt sounding (có `midi`, có `velocity`, không phải `tie_stop`) trong ô $b$:

$$d = V_{\text{đã viết}} - 64$$

$$V_{\text{ra}} = \mathrm{round}\big(C(b) + M \cdot d\big)$$

Cùng một $C(b)$ và cùng một $M$ cho lead, low và support. Hiệu giữa hai nốt trong section là hiệu đã viết nhân $M$:

$$V_{\text{ra}}(e_1) - V_{\text{ra}}(e_2) = \mathrm{round}(C + M d_1) - \mathrm{round}(C + M d_2)$$

Khi $M = 1$, hiệu MIDI giữ nguyên ở ô trũng và ở ô đỉnh. Khi cửa sổ genre hẹp hơn dải đã viết, $M < 1$: mọi lệch co cùng một tỉ lệ, thứ tự và dấu giữ nguyên.

Nốt nằm trong $[64 + d_{\text{lo}},\; 64 + d_{\text{hi}}]$ chạm đúng $V_{\text{floor}}$ ở ô $U = 0$ và đúng $V_{\text{ceil}}$ ở ô $U = 1$. Kẹp từng nốt không tham gia vào hình động lực. Kẹp `[1, 127]` chỉ là lan can cho nốt viết ngoài dải đã khai báo.

**Ví dụ.** Cửa sổ `[24, 63]`, $d_{\text{lo}} = -16$, $d_{\text{hi}} = +8$:

$$M = \min(1,\; 39 / 24) = 1, \quad C_{\text{lo}} = 40, \quad C_{\text{hi}} = 55$$

| Nốt đã viết | $d$ | Ô trũng $C = 40$ | Ô đỉnh $C = 55$ |
|---|---|---|---|
| Giai điệu 64 | 0 | 40 | 55 |
| Đỉnh 72 | +8 | 48 | 63 |
| Bè trong 48 | −16 | 24 | 39 |

Chênh `72 − 64 = 8` và `64 − 48 = 16` đứng yên. Sóng chỉ dời khối từ `40` lên `55`.

**Ví dụ $M < 1$.** Cửa sổ rộng `20` đơn vị, cùng dải lệch `24`: $M = 20 / 24$. Một lệch đã viết `+8` thành `+6.67` ở mọi ô của section.

### 2.5. Những gì bộ lọc giữ nguyên

- Offset trong ô đã viết: tremolo `(-4, 0, +4, +1)` và fill `(-6, -3, -4, -6)`, cung Etude 1, sextuplet Etude 11, sóng chữ V của Preludio, accent, `extra` của câu.
- Khoảng cách giữa các bè, vì cả ba bè nhận cùng $C$ và cùng $M$.
- Hình intro / outro đã viết trong `guitar_frame.py`. Khung chỉ trượt $C$ (mục 4).

Bộ lọc không dựng lại các offset từ bảng, và không chạy một pass viết lại vận tốc để ép `lead > low > support`. Thứ tự bè sau lọc là thứ tự đã viết, nhân $M$.

---

## 3. Cổng Snap

Snap là bước **sau** phép affine. Chỉ những cú được chọn đổi vận tốc. Các nốt còn lại trong ô giữ $V_{\text{ra}}$.

### 3.1. Ứng viên

$$S_{\text{snap}}(b) = 0.70 \cdot U(b) + 0.30 \cdot C_{\text{phrase}}(b)$$

$C_{\text{phrase}}(b) \in [0, 1]$ là hơi thở câu **đã có** trên phrase (`0` ở hai biên, `1` tại `phrase.apex`). Đại lượng này chỉ để xếp hạng ứng viên. Nó không cộng vào $V_{\text{ra}}$.

Một cú vào danh sách khi đủ bốn điều kiện:

- Pattern có `snap_wide` khác `None`.
- $\alpha_{\text{price}} \ge 0.25$. Riêng `elogio_pizz`: khi $\alpha_{\text{price}} < 0.25$ vẫn cho đúng một cú Bartók slap tại $S_{\text{snap}}$ cao nhất, với $V_{\text{snap}} = P.\text{snap\_calm} = 72$.
- $S_{\text{snap}}(b) \ge 0.70$. Đoạn `trio` / `bridge` vẫn đạt ngưỡng này khi $\alpha_{\text{price}} \ge 0.25$, vì $U$ của đoạn vẫn chạy đủ `[0, 1]`.
- Cú khớp `snap_targets` của pattern (bảng mục 5).

### 3.2. Ngân sách

- **1 snap unit** = 1 cú tấn công trên bè hát. `villa_pattern` (*Tresillo* `{0, 3, 6}`) tính cả bộ ba trong một ô là 1 unit. `etude1` chỉ lấy một nốt hát trong ô đỉnh.
- $\alpha_{\text{price}} < 0.25$: $K_{\text{sec}} = 1$ nếu `elogio_pizz`, ngược lại $K_{\text{sec}} = 0$.
- $\alpha_{\text{price}} \ge 0.25$: $N_{\text{mel, sec}}$ là số cú tấn công có cao độ của bè hát trong section (`tremolo`: mỗi phách đen là 1 cú).

$$K_{\text{sec}} = \min\big(P.\text{max\_units\_per\_sec},\; \max(1,\; \lfloor 0.045 \cdot N_{\text{mel, sec}} \rfloor)\big)$$

Trong mỗi phrase giữ tối đa `max_units_per_phrase` ứng viên có $S$ cao nhất, rồi trên cả section giữ tối đa $K_{\text{sec}}$.

### 3.3. Lực snap

$$V_{\text{snapped}} = \mathrm{round}\left(66 + \big(V_{\text{snap}}(\alpha_{\text{price}}) - 66\big) \cdot \frac{\mathrm{clamp}(S_{\text{snap}},\; 0.70,\; 1) - 0.70}{0.30}\right)$$

$V_{\text{snap}}(\alpha_{\text{price}})$ nội suy `snap_calm .. snap_wide`. Kết quả luôn nằm trong `[66,\; V_{\text{snap}}]`.

Nốt đi kèm trong cùng cụm (fill tremolo, echo etude, canto 2, sóng chữ V) **giữ** $V_{\text{ra}}$ của phép affine. Nếu giá trị đó vượt `63`, kẹp về `63` để cụm snap không kéo nốt đệm qua tiếng móng. Kẹp này chỉ chạm nốt đã vượt trần ấm.

`tie_stop` nhận vận tốc của `tie_start` sau khi affine và snap đã xong.

---

## 4. Intro và outro

Các ô `pedal` (`intro`, `warmup`, `outro`, `cooldown`) dùng cùng phép $C + M \cdot d$ trên vận tốc frame đã viết. $M$ lấy của thân bài kế bên, để một cử chỉ bước qua vạch nhịp không đổi tỉ lệ.

- **Intro**: có $M_{\text{lead}}$ ô pedal dẫn, chỉ số $i = 0 \dots M_{\text{lead}} - 1$. $C$ đi từ một tâm thì thầm tới $C$ của ô thân bài đầu tiên:

$$C_{\text{intro}}(i) = C_{\text{whisper}} + \big(C(b_{\text{body}}) - C_{\text{whisper}}\big) \cdot \frac{i}{\max(1,\; M_{\text{lead}} - 1)}$$

  $C_{\text{whisper}}$ chọn sao cho nốt viết `64` rơi vào `27` (giữa `22..32`). Ô pedal cuối dùng đúng $C(b_{\text{body}})$, nên vạch nhịp nối tiếp về $C$, và phần nhảy còn lại là nhảy của vận tốc đã viết.

- **Outro**: $C$ đi từ $C$ của ô thân bài cuối xuống một tâm morendo, nơi nốt viết `64` rơi vào `23` (giữa `20..26` ở ô pedal cuối).

Cú stab kịch tính (`staccato` và `accent` ở `_edge_stab` / `_stab_and_ring` của Brouwer, và `_stabs` cuối outro Villa khi `bright`) gán sau bộ lọc, một bộ số:

| Bè | Vận tốc |
|---|---|
| lead | 70 |
| low | 66 |
| support | 62 |

Bộ này đứng dưới Bartók slap của `elogio_pizz` (`72..76` / `68..70` / `64..66`).

---

## 5. Bảng `PatternWaveProfile`

Khóa là `(ensemble, pattern)`. Mọi dòng thỏa `floor_calm <= floor_wide` và `ceil_calm <= ceil_wide <= 63`.

`floor_*` và `ceil_*` là cửa sổ đầu ra của **cả khối nốt**, không phải ba đường cong thay thế lead / bass / support. $M$, $C_{\text{lo}}$, $C_{\text{hi}}$ suy ra theo mục 2.3. Dải lệch mặc định $d_{\text{lo}} = -16$, $d_{\text{hi}} = +8$.

```python
@dataclass(frozen=True)
class PatternWaveProfile:
    floor_calm: int            # sàn cửa sổ khi alpha_warm = 0, >= 20
    floor_wide: int            # sàn cửa sổ khi alpha_warm = 1
    ceil_calm: int             # trần ấm khi alpha_warm = 0, <= 60
    ceil_wide: int             # trần ấm khi alpha_warm = 1, <= 63
    snap_calm: int | None      # None nếu cấm ép dây; >= 66 nếu có
    snap_wide: int | None      # trần snap khi alpha_price = 1, trong 68..76
    max_units_per_phrase: int  # 0 hoặc 1
    max_units_per_sec: int     # 0..4
    snap_targets: str
    d_lo: int = -16            # lệch dưới tâm 64 mà bộ lọc giữ hết
    d_hi: int = 8              # lệch trên tâm 64 mà bộ lọc giữ hết
```

| Khóa `(ensemble, pattern)` | Cửa sổ calm → wide | Snap | Hạn mức `(phrase, sec)` | Cú được snap |
|---|---|---|---|---|
| `("bach", "bach_sarabande")` | `26..56` → `30..62` | không | `(0, 0)` | Phách 2 và mordent ở trong cửa sổ ấm. |
| `("bach", "bach_gavotte")` | `28..58` → `32..62` | `66..68` | `(1, 2)` | Phách 1 đầu câu đỉnh khi `phrase.rise >= 3`. |
| `("bach", "bach_bourree")` | `28..58` → `32..63` | `66..68` | `(1, 3)` | `phrase.apex` sau cặp lấy đà khi `rise >= 3`. |
| `("bach", "bach_fuga")` | `28..58` → `32..63` | `66..68` | `(1, 2)` | `phrase.apex` của soprano ở câu cao trào. |
| `("bach", "bach_gigue")` | `28..58` → `32..63` | `68..70` | `(1, 3)` | Nốt đầu câu chạy scale, hoặc phách mạnh tại đỉnh. |
| `("bach", "bach_chaconne")` | `26..58` → `30..63` | `68..70` | `(1, 3)` | Nốt đích cuối câu scale breakout (`accent=True`). |
| `("classic", "cantabile")` | `24..54` → `28..58` | không | `(0, 0)` | Song thanh quãng 3/6 nằm trong cửa sổ ấm. |
| `("classic", "elegiaque")` | `24..56` → `28..62` | `66..68` | `(1, 2)` | Appoggiatura (`accent=True`) ở câu đỉnh. |
| `("classic", "study")` | `26..56` → `30..63` | `68..70` | `(1, 2)` | Fanfare mở đoạn `f`, hoặc đích Grand Solo, hoặc `phrase.apex` khi rally. |
| `("classic", "mozart_var")` | `26..56` → `30..62` | `66..68` | `(1, 2)` | `phrase.apex` khi `rise >= 3`. |
| `("classic", "galop")` | `28..58` → `32..63` | `68..70` | `(1, 3)` | Phách mạnh mở câu đỉnh ở phiên rally. |
| `("barrios", "preludio")` | `26..56` → `30..62` | `66..68` | `(1, 2)` | Tối đa 2 nốt Canto 1 tại đỉnh section. |
| `("barrios", "andante")` | `24..54` → `28..60` | không | `(0, 0)` | Không ép dây. |
| `("barrios", "thumb_cantabile")` | `26..56` → `30..62` | `66..68` | `(1, 2)` | 1–2 nốt ngón cái `low` tại đỉnh câu. |
| `("barrios", "tremolo")` | `28..58` → `32..63` | `68..72` | `(1, 2)` | Phách đỉnh của ô cao trào. Fill giữ $V_{\text{ra}}$, kẹp `<= 63` nếu vượt. |
| `("barrios", "choro")` | `28..58` → `32..63` | `70..74` | `(1, 4)` | Nhấn lệch phách `accent=True` hoặc `phrase.apex`. |
| `("barrios", "polca")` | `28..58` → `32..63` | `70..72` | `(1, 3)` | Nhấn lệch phách `accent=True` tại đỉnh sóng. |
| `("barrios", "hemiola")` | `28..58` → `32..63` | `70..74` | `(1, 4)` | Phách hemiola `accent=True` tại đỉnh sóng. |
| `("barrios", "vals")` | `26..58` → `30..62` | `68..72` | `(1, 3)` | Phách 2 (`eighth == 4`, `accent=True`) tại đỉnh sóng. |
| `("villa", "chord_melody")` | `24..54` → `28..60` | không | `(0, 0)` | Hợp âm khối ngân trong cửa sổ ấm. |
| `("villa", "thumb_cantabile")` | `28..58` → `32..63` | `68..70` | `(1, 2)` | Đỉnh câu ngón cái `low`. |
| `("villa", "villa_pattern")` | `26..58` → `30..63` | `68..72` | `(1, 3)` | Bộ Tresillo `{0, 3, 6}` (1 unit) hoặc `phrase.apex`. |
| `("villa", "etude1")` | `28..58` → `32..63` | `68..70` | `(1, 2)` | 1 nốt hát trong ô đỉnh. |
| `("villa", "etude11")` | `28..58` → `32..63` | `70..74` | `(1, 3)` | Cú 1 của `lead` tại phách `phrase.apex`. |
| `("brouwer", "noviembre")` | `22..52` → `26..58` | không | `(0, 0)` | Không ép dây. |
| `("brouwer", "sarabande")` | `24..56` → `28..62` | `68..72` | `(1, 2)` | Hợp âm nhấn phách 2 tại đỉnh. |
| `("brouwer", "brouwer_etude")` | `24..58` → `28..63` | `68..72` | `(1, 3)` | Downbeat / tumbao `accent=True` ở ô đỉnh. |
| `("brouwer", "elogio_pizz")` | `24..56` → `28..62` | `72..76` | `(1, 4)` | Bartók slap tại móc đơn thứ 3. $\alpha_{\text{price}} < 0.25$ thì $K_{\text{sec}} = 1$. |

---

## 6. Humanize

Trên `score.variant == "guitar"`:

- `written_velocity <= 64` → `heard_velocity = min(64, heard_velocity)`.
- `written_velocity >= 65` → `heard_velocity = max(66, min(76, heard_velocity))`.

Nốt ấm không trượt sang `65`. Cụm snap không vượt `76`.

---

## 7. Thứ tự sửa code

1. **Sóng $U(b)$.** Trong `guitar_wave.py`, thay bộ làm mượt hiện tại bằng log → trung bình trượt $W = 5$ → min–max trong section (band fallback khi phẳng). Bỏ nội suy cosine theo móc đơn.
2. **Hằng số.** Giữ 28 profile ở mục 5. Bỏ các trường đường cong bass / support / gamma khỏi công thức vận tốc. Tính $M$, $C_{\text{lo}}$, $C_{\text{hi}}$ theo mục 2.3 cho từng section.
3. **`_shape_dynamics`.** Giữ `extra` của câu. Bỏ `_BAND_DELTA` và bỏ kẹp `[44, 78]` trên đường đi vào bộ lọc, để band thô không cộng dồn với $C$.
4. **`apply_guitar_wave`.** Một vòng trên mọi nốt sounding: $V_{\text{ra}} = \mathrm{round}(C(b) + M \cdot (V - 64))$. Xóa `_assign_generic`, `_assign_tremolo`, `_assign_etude1`, `_assign_etude11`, `_assign_preludio` và pass xếp tầng ba bè. Intro / outro chỉ trượt $C$ (mục 4). Stab khung vẫn gán `70 / 66 / 62`.
5. **Snap.** Giữ ngân sách và $V_{\text{snapped}}$. Chỉ ghi đè cú được chọn. Nốt đi kèm giữ $V_{\text{ra}}$, kẹp `63` khi vượt trần ấm.
6. **Humanize.** Giữ chốt mục 6.
7. **Test.** Đổi `test_guitar_wave.py` sang các bất biến ở mục 8. Các assertion số tuyệt đối cũ trong `test_sonify_guitar.py` chuyển sang kiểm tra hiệu vận tốc và cửa sổ genre.

---

## 8. Bất biến cần test

1. **Cùng một hiệu ở ô trũng và ô đỉnh.** Với $M = 1$, mọi cặp nốt sounding trong một section giữ đúng $V_i - V_j$ sau lọc, kể cả tremolo, etude, preludio và các pattern thường. Với $M < 1$, hiệu mới bằng hiệu cũ nhân $M$ (sai số làm tròn 1 bậc).
2. **Khóa biên.** Nốt viết $64 + d_{\text{lo}}$ tại ô $U = 0$ ra đúng $V_{\text{floor}}$. Nốt viết $64 + d_{\text{hi}}$ tại ô $U = 1$ ra đúng $V_{\text{ceil}} \le 63$.
3. **$C$ đi theo $U$.** Ô $\tilde{\ell}$ nhỏ nhất có $C = C_{\text{lo}}$. Ô $\tilde{\ell}$ lớn nhất có $C = C_{\text{hi}}$. Các ô ở giữa nội suy tuyến tính theo $U$. $C$ không đổi bên trong một ô.
4. **Volume phẳng.** Cả section một mức volume thì mọi ô cùng một $C$ lấy từ band fallback. Hiệu vi mô giữ nguyên.
5. **Band không cộng hai lần.** Một nốt viết `64` trên band `p` và trên band `f`, cùng $U$, ra cùng $V_{\text{ra}}$.
6. **Snap hiếm.** Pattern `snap_wide is None`: không nốt nào vượt `64` sau humanize. Pattern có snap, $\alpha_{\text{price}} \ge 0.50$: có ít nhất một unit trong `[66, snap_wide]`, không quá $K_{\text{sec}}$, không nốt nào sau humanize vượt `76`. Nốt không được chọn trong cùng ô giữ đúng kết quả affine.
7. **Theo section.** Chương nhiều section: section $\alpha_{\text{price}} = 0$ có $K_{\text{sec}} = 0$ (trừ tối đa một slap `elogio_pizz`). `trio` / `bridge` dùng $\alpha_{\text{warm}}$ đã nhân `0.50`, nên cửa sổ và quãng chạy của $C$ hẹp hơn phần A cùng profile.
8. **Intro / outro.** Hiệu trong một cử chỉ frame giữ theo $M$ của thân bài. Ô pedal cuối của intro dùng cùng $C$ với ô thân bài đầu. Stab khung ra `70 / 66 / 62`.
