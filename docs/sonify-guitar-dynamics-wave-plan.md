# Kế Hoạch Filter Sóng Volume (Affine) Cho Động Lực Học Guitar

> **Mục tiêu**: Đưa tiếng đàn guitar cổ điển từ dải hẹp `44..78` vào cửa sổ âm sắc của từng genre, bằng một **bộ lọc affine** trên vận tốc đã viết. Sóng volume đã làm mượt chỉ dời cả khối nốt. Trong một ô, `C` và `M` là một số, nên swell trong câu, accent, bậc tremolo, cung etude và khoảng cách giữa các bè giữ đúng hiệu MIDI đã viết.
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

`apply_guitar_wave()` trên nhánh này vẫn **thay** `_shape_dynamics` và gán vận tốc mới từ đường bao $V_{\text{hat}}(t)$. `_assign_generic` bỏ `event.velocity`. Bốn pattern `tremolo`, `etude1`, `etude11`, `preludio` dựng lại một vài offset cứng từ bảng. Bản nghe vì vậy chưa đổi. Thiết kế dưới đây thay bước gán đó; code `guitar_wave.py` vẫn là bản rebase cho đến khi mục 7 được thực hiện.

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
  │      V_ra = round(C(b) + (V_đã_viết - 64))
  │      Nốt không được snap, và không phải stab khung, kẹp vào [V_floor, V_ceil] ≤ 63.
  │      Rồi Cổng Snap nâng một vài cú đã chọn vào 66..76.
  └── 5. humanize()
         written <= 64  →  heard = min(64, heard)
         written >= 65  →  heard = max(66, min(76, heard))
         Nhánh >= 65 chỉ còn nốt snap và stab khung, vì bước 4 đã kẹp mọi nốt khác xuống ≤ 63.
```

`64` là `_MELODY`, tâm vận tốc đã viết. Mọi bè dùng cùng tâm này.

### 2.2. Làm mượt volume thành $U(b) \in [0, 1]$

Với mỗi `FormSection` thân bài `[sec_start, sec_end)`:

**Bước A — log.** $v(b) = \max(0,\; \text{bar\_volumes}[b])$, rồi

$$\ell(b) = \ln\big(1 + v(b)\big)$$

Log nằm ở đây để một phiên gấp nhiều lần volume chỉ nhích $\ell$, không kéo $C$ văng khỏi cửa sổ genre.

**Bước B — trung bình đối xứng 5 điểm.** Mỗi ô lấy chính nó và hai ô hai bên, phản xạ tại `sec_start` và `sec_end - 1` để cửa sổ luôn đủ 5 điểm:

$$\tilde{\ell}(b) = \frac{\ell(b-2) + \ell(b-1) + \ell(b) + \ell(b+1) + \ell(b+2)}{5}$$

Ô volume nóng đạt cực đại của $\tilde{\ell}$. Một ô nóng đứng một mình cho cao nguyên 5 ô cân quanh nó: hai ô trước, ô nóng, hai ô sau. Trung bình lùi 5 ô đặt cao nguyên đó từ ô nóng kéo sang bốn ô phía sau, nên tâm đỉnh nằm sau ô volume nóng. Một giá trị cho cả ô. Vi mô trong ô nằm ở $V_{\text{đã viết}}$.

**Bước C — chuẩn hóa trong section.**

- Nếu $\max \tilde{\ell} - \min \tilde{\ell} \le 10^{-6}$ (volume phẳng): $U(b)$ lấy theo band của ô, `{"p": 0.15, "mp": 0.40, "mf": 0.65, "f": 0.90}`. $C$ đứng yên trong section.
- Nếu có biến thiên, kéo $\tilde{\ell}$ về $[0, 1]$:

$$U_{\text{raw}}(b) = \frac{\tilde{\ell}(b) - \min \tilde{\ell}}{\max \tilde{\ell} - \min \tilde{\ell}} \in [0, 1]$$

**Bước D — chặn bước giữa hai ô kề.** $C$ là một số trong cả ô, nên hai ô kề có $U$ cách xa thì cả khối nhảy đúng $C_{\text{hi}} - C_{\text{lo}}$ tại vạch nhịp. Với cửa sổ rộng, quãng đó khoảng `12..15` bậc. Chặn bước của $C$ ở `4` bậc MIDI:

$$\Delta_U = \frac{4}{C_{\text{hi}} - C_{\text{lo}}}, \qquad U(b) = \max_{j \in \text{section}}\left(U_{\text{raw}}(j) - \Delta_U \cdot \lvert b - j \rvert\right)$$

$C_{\text{lo}}$ và $C_{\text{hi}}$ lấy ở mục 2.3, tính trước bước này. $U$ là hàm Lipschitz nhỏ nhất nằm trên $U_{\text{raw}}$ với bước tối đa $\Delta_U$. Ô đang là đỉnh của $U_{\text{raw}}$ giữ nguyên $U = 1$. Ô trũng sát một vách đứng được nâng thành đường dốc `4` bậc mỗi ô, nên đỉnh không bị đẩy sang ô sau. Khi $U_{\text{raw}}$ đã thoải hơn mức này, $U = U_{\text{raw}}$. Hệ quả trên thủy triều:

$$\lvert C(b) - C(b-1) \rvert \le 4$$

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

Dải lệch đã viết dùng để khóa biên, chung cho mọi dòng trong bảng:

$$d_{\text{lo}} = -16, \qquad d_{\text{hi}} = +8$$

Nốt `48` ($64 - 16$) và nốt `72` ($64 + 8$, `_MELODY_APEX`) là hai đầu mà bộ lọc giữ hết độ lệch. Khoảng này dài `24` bậc.

Ba hằng số của section:

$$\begin{aligned}
M &= \min\left(1,\; \frac{V_{\text{ceil}} - V_{\text{floor}}}{24}\right) \\
C_{\text{lo}} &= V_{\text{floor}} - M \cdot d_{\text{lo}} \\
C_{\text{hi}} &= V_{\text{ceil}} - M \cdot d_{\text{hi}}
\end{aligned}$$

Mọi cửa sổ trong bảng mục 5, kể cả đầu calm, đầu wide, và đoạn `trio` / `bridge` (kéo về calm), đều có $V_{\text{ceil}} - V_{\text{floor}} \ge 30 > 24$. Vậy $M = 1$ trên mọi section của 28 profile. Hiệu MIDI trong một ô không bị co. Với $M = 1$:

$$C_{\text{lo}} = V_{\text{floor}} + 16, \qquad C_{\text{hi}} = V_{\text{ceil}} - 8, \qquad C(b) = C_{\text{lo}} + U(b) \cdot (C_{\text{hi}} - C_{\text{lo}})$$

Quãng thủy triều $C_{\text{hi}} - C_{\text{lo}} = (V_{\text{ceil}} - V_{\text{floor}}) - 24$ nằm trong khoảng `6..15` bậc. $C$ đổi theo ô, và là một số cho mọi nốt trong ô đó.

### 2.4. Phép lọc

Với mọi nốt sounding (có `midi`, có `velocity`, không phải `tie_stop`) trong ô $b$:

$$d = V_{\text{đã viết}} - 64, \qquad V_{\text{thô}} = \mathrm{round}\big(C(b) + d\big)$$

Cùng một $C(b)$ cho lead, low và support. Vì $d$ nguyên và $M = 1$, hai nốt **trong cùng một ô** giữ đúng hiệu đã viết:

$$V_{\text{thô}}(e_1) - V_{\text{thô}}(e_2) = V_{\text{đã viết}}(e_1) - V_{\text{đã viết}}(e_2)$$

Hai nốt **khác ô** lệch thêm phần thủy triều:

$$V_{\text{thô}}(e_1) - V_{\text{thô}}(e_2) = \big(V_{\text{đã viết}}(e_1) - V_{\text{đã viết}}(e_2)\big) + \big(\mathrm{round}\,C(b_1) - \mathrm{round}\,C(b_2)\big)$$

Nốt viết trong `[48, 72]` chạm đúng $V_{\text{floor}}$ ở ô $U = 0$ và đúng $V_{\text{ceil}}$ ở ô $U = 1$.

Nốt viết ngoài khoảng đó vẫn cộng cùng $C(b)$, rồi bị trần ấm giữ lại. Sau phép cộng, mọi nốt không được Cổng Snap chọn và không phải stab khung (mục 4) kẹp vào

$$[V_{\text{floor}},\; V_{\text{ceil}}], \qquad V_{\text{ceil}} \le 63$$

Trên ô đỉnh của ví dụ dưới, nốt viết `80` ra $\mathrm{round}(55 + 16) = 71$, rồi kẹp về `63`. Humanize nhìn thấy `63`, đi nhánh `<= 64`, và dừng ở `<= 64`. Nó không bị kéo vào `66..76`. Nốt `72` trên cùng ô cũng ra `63`: phần viết trên `72` chỉ mất ở những ô đã chạm trần. Trên ô trũng, `80` ra `40 + 16 = 56`, còn dưới `63`, và vẫn cách nốt `72` đúng `8` bậc.

**Ví dụ.** Cửa sổ `[24, 63]`:

$$M = 1, \quad C_{\text{lo}} = 40, \quad C_{\text{hi}} = 55$$

| Nốt đã viết | $d$ | Ô trũng $C = 40$ | Ô đỉnh $C = 55$ |
|---|---|---|---|
| Giai điệu 64 | 0 | 40 | 55 |
| Đỉnh 72 | +8 | 48 | 63 |
| Bè trong 48 | −16 | 24 | 39 |
| Viết 80, trước kẹp | +16 | 56 | 71 → kẹp `63` |

Trong từng ô, chênh `72 − 64 = 8` và `64 − 48 = 16` đứng yên. Giữa ô trũng và ô đỉnh, cùng một nốt `64` lệch thêm `55 − 40 = 15`. Bước D giữ mỗi vạch nhịp trong mức `4` bậc, nên quãng `15` này trải ít nhất bốn vạch.

### 2.5. Những gì bộ lọc giữ nguyên

- Offset trong ô đã viết: tremolo `(-4, 0, +4, +1)` và fill `(-6, -3, -4, -6)`, cung Etude 1, sextuplet Etude 11, sóng chữ V của Preludio, accent, `extra` của câu.
- Khoảng cách giữa các bè trong cùng một ô, vì cả ba bè nhận cùng $C$.
- Hình intro / outro đã viết trong `guitar_frame.py`. Khung chỉ trượt $C$ (mục 4).

Bộ lọc không dựng lại các offset từ bảng, và không chạy một pass viết lại vận tốc để ép `lead > low > support`. Thứ tự bè trong một ô sau lọc là thứ tự đã viết.

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

Nốt đi kèm trong cùng cụm (fill tremolo, echo etude, canto 2, sóng chữ V) giữ kết quả affine đã kẹp ở mục 2.4, nên dừng ở $\le 63$.

`tie_stop` nhận vận tốc của `tie_start` sau khi affine và snap đã xong.

---

## 4. Intro và outro

Các ô `pedal` (`intro`, `warmup`, `outro`, `cooldown`) dùng cùng phép $C + d$ trên vận tốc frame đã viết. Trong một ô, hiệu MIDI của cử chỉ giữ nguyên.

- **Intro**: $C_{\text{whisper}}$ là mức làm nốt viết `64` rơi vào `27` (giữa `22..32`). $C(b_{\text{body}})$ là $C$ của ô thân bài đầu tiên. Có $M_{\text{lead}}$ ô pedal dẫn, chỉ số $i = 0 \dots M_{\text{lead}} - 1$.

  - $M_{\text{lead}} = 1$: ô đó chính là ô pedal cuối, nhận $C(b_{\text{body}})$. Công thức $i / (M_{\text{lead}} - 1)$ không dùng cho trường hợp này, vì mẫu số bằng 0 và giá trị thay thế $C_{\text{whisper}}$ sẽ để ô nối đứng ở `27`.
  - $M_{\text{lead}} \ge 2$:

$$C_{\text{intro}}(i) = C_{\text{whisper}} + \big(C(b_{\text{body}}) - C_{\text{whisper}}\big) \cdot \frac{i}{M_{\text{lead}} - 1}$$

  Ô $i = M_{\text{lead}} - 1$ nhận đúng $C(b_{\text{body}})$. Vạch nhịp vào thân bài nối tiếp về $C$. Phần nhảy còn lại là nhảy của vận tốc đã viết. Các ô trước đó đi từ `27` lên mức mở của ô nối. Bước giữa hai ô intro kề cũng bị chặn `4` bậc, cùng quy tắc mục 2.2D: nếu $C(b_{\text{body}}) - C_{\text{whisper}} > 4 \cdot (M_{\text{lead}} - 1)$, các ô đầu được nâng để đường dốc không vượt `4` mỗi vạch, và ô cuối vẫn là $C(b_{\text{body}})$.

- **Outro**: $C$ đi từ $C$ của ô thân bài cuối xuống tâm morendo, nơi nốt viết `64` rơi vào `23` (giữa `20..26`). Một ô outro duy nhất là ô sát thân bài, nhận $C$ của ô thân bài cuối. Morendo chỉ trải trên chuỗi có từ hai ô; ô cuối của chuỗi đó về `23`, và mỗi vạch cũng không nhảy quá `4` bậc.

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

`floor_*` và `ceil_*` là cửa sổ đầu ra của **cả khối nốt**, không phải ba đường cong thay thế lead / bass / support. Với $d_{\text{lo}} = -16$, $d_{\text{hi}} = +8$, mọi dòng dưới đây có $V_{\text{ceil}} - V_{\text{floor}} \ge 30$, nên $M = 1$. $C_{\text{lo}}$ và $C_{\text{hi}}$ suy ra theo mục 2.3.

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

Nhánh `>= 65` chỉ đúng với nốt Cổng Snap đã ghi `66..76` và stab khung `70` / `66`. Mọi nốt còn lại rời `apply_guitar_wave` ở $\le 63$, kể cả nốt pattern viết trên `72`. Một nốt viết `80` trên ô đỉnh không còn đường vào `66..76` khi cổng snap không chọn nó.

---

## 7. Thứ tự sửa code

1. **Sóng $U(b)$.** Trong `guitar_wave.py`, thay bộ làm mượt hiện tại bằng log → trung bình đối xứng 5 điểm → min–max trong section → chặn bước $\Delta_U = 4 / (C_{\text{hi}} - C_{\text{lo}})$ (mục 2.2). Band fallback khi volume phẳng. $C$ vẫn là một số cho cả ô.
2. **Hằng số.** Giữ 28 profile ở mục 5. Bỏ các trường đường cong bass / support / gamma khỏi công thức vận tốc. Với bảng này $M = 1$. Tính $C_{\text{lo}}$, $C_{\text{hi}}$ theo mục 2.3 cho từng section.
3. **`_shape_dynamics`.** Giữ `extra` của câu. Bỏ `_BAND_DELTA` và bỏ kẹp `[44, 78]` trên đường đi vào bộ lọc, để band thô không cộng dồn với $C$.
4. **`apply_guitar_wave`.** Một vòng trên mọi nốt sounding: $V_{\text{thô}} = \mathrm{round}(C(b) + (V - 64))$, rồi kẹp nốt không snap vào $[V_{\text{floor}}, V_{\text{ceil}}] \le 63$. Xóa `_assign_generic`, `_assign_tremolo`, `_assign_etude1`, `_assign_etude11`, `_assign_preludio` và pass xếp tầng ba bè. Intro một ô nhận $C(b_{\text{body}})$ (mục 4). Stab khung vẫn gán `70 / 66 / 62` sau bước kẹp.
5. **Snap.** Giữ ngân sách và $V_{\text{snapped}}$. Chỉ ghi đè cú được chọn, sau bước kẹp trần ấm.
6. **Humanize.** Giữ chốt mục 6. Nhánh `>= 65` không nhận nốt affine.
7. **Test.** Đổi `test_guitar_wave.py` sang các bất biến ở mục 8. Các assertion số tuyệt đối cũ trong `test_sonify_guitar.py` chuyển sang kiểm tra hiệu trong cùng một ô và cửa sổ genre.

---

## 8. Bất biến cần test

1. **Hiệu trong cùng một ô.** Mọi cặp nốt sounding cùng ô giữ đúng $V_i - V_j$ sau lọc khi cả hai còn trong $[V_{\text{floor}}, V_{\text{ceil}}]$, kể cả tremolo, etude, preludio và các pattern thường. Hai nốt khác ô lệch thêm $\mathrm{round}\,C(b_1) - \mathrm{round}\,C(b_2)$. Trên 28 profile, $M = 1$.
2. **Khóa biên.** Nốt viết `48` tại ô $U = 0$ ra đúng $V_{\text{floor}}$. Nốt viết `72` tại ô $U = 1$ ra đúng $V_{\text{ceil}} \le 63$. Nốt viết `80` tại ô $U = 1$ ra `63` trước humanize và `<= 64` sau humanize.
3. **Đỉnh và bước vạch nhịp.** Ô volume nóng (đỉnh của $\ell$ trước khi làm mượt) có $C$ bằng cực đại của section. $|C(b) - C(b-1)| \le 4$. $C$ không đổi bên trong một ô.
4. **Volume phẳng.** Cả section một mức volume thì mọi ô cùng một $C$ lấy từ band fallback. Hiệu trong ô giữ nguyên.
5. **Band không cộng hai lần.** Một nốt viết `64` trên band `p` và trên band `f`, cùng $U$, ra cùng $V_{\text{ra}}$.
6. **Snap hiếm.** Pattern `snap_wide is None`: không nốt nào vượt `64` sau humanize, kể cả nốt viết trên `72`. Pattern có snap, $\alpha_{\text{price}} \ge 0.50$: có ít nhất một unit trong `[66, snap_wide]`, không quá $K_{\text{sec}}$, không nốt nào sau humanize vượt `76`. Nốt không được chọn trong cùng ô giữ kết quả affine đã kẹp `<= 63`.
7. **Theo section.** Chương nhiều section: section $\alpha_{\text{price}} = 0$ có $K_{\text{sec}} = 0$ (trừ tối đa một slap `elogio_pizz`). `trio` / `bridge` dùng $\alpha_{\text{warm}}$ đã nhân `0.50`, nên cửa sổ và quãng chạy của $C$ hẹp hơn phần A cùng profile. $M$ của đoạn đó vẫn là `1`.
8. **Intro / outro.** Hiệu trong một cử chỉ của cùng một ô frame giữ nguyên. Intro một ô nhận $C$ của ô thân bài đầu, không nhận `27`. Intro từ hai ô: ô cuối nhận $C(b_{\text{body}})$. Outro một ô nhận $C$ của ô thân bài cuối. Stab khung ra `70 / 66 / 62`.
