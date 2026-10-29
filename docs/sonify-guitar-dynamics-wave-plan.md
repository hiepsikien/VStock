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

### Sau khi nghe Barrios

Bản affine giữ vi mô trong ô và dời cả khối theo sóng. Nghe Barrios cho ba chỉnh, và các mục dưới đã tính theo số mới. Nửa đầu NWG khung 1M là đoạn sóng thấp dùng làm mốc của đáy.

1. **Tương phản của sóng giảm vì đáy lên, đỉnh giữ nguyên.** Trần giữ số của bảng nghe trước, nên $C_{\text{hi}}$ đứng yên. Andante wide dùng sàn `+4`: thủy triều `8 → 4`, nốt `64` đi `48 → 52`, nốt `72` ở đỉnh vẫn `60`. Calm có trần từ `54` trở lên, cùng gavotte wide và cantabile wide, dùng sàn `+2`. Nhát `+4` trên các dòng đó để lại thủy triều `2`, và humanize `±2` nuốt mức ấy. Andante calm là `26..54`: tâm nốt `64` đi `42 → 46`, đỉnh cũ `46` đứng yên, đáy lên `2` so với `main`, chuông `44` ở đáy ghi `22`. Noviembre calm có trần `52`. Giữ trần thì không có sàn nào vừa để thủy triều `4` vừa đưa chuông tới `22`. Bảng chọn sóng: sàn `24`, tâm `40 → 44`. Chuông ở đáy ghi `20`, và một dải humanize có thể về `18`. Phía kia, sàn `26`, tâm `42 → 44`, chuông ở đáy là `22`, thủy triều còn `2`.
2. **Đáy thân bài là sàn đó.** Nốt viết `48` ở ô $U = 0$ cao hơn đúng nhát cắt của dòng: `4` ở andante wide, `2` ở các calm vừa nói. Đoạn volume thấp đi theo $C_{\text{lo}}$ mới.
3. **Chu kỳ làm mượt theo loại nhạc.** Trung bình đối xứng lấy $W$ của profile: `9` cho câu ngân, `5` cho câu chạy, `3` cho điệu. Một cửa sổ 5 ô không còn dùng cho cả bảng.

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
  │      V_thô = round(C(b)) + (V_đã_viết - 64)
  │      Thân bài, nốt không snap và không phải stab khung: chỉ kẹp trần V_ceil ≤ 63.
  │      Nốt viết 48 chạm sàn nhờ C_lo. Chuông 44 ở đáy thấp hơn sàn 4 bậc.
  │      Ô intro / outro: không kẹp từng nốt vào F. Tâm là một đường theo L ở mục 4,
  │      rồi kéo nốt vượt 63 về 63.
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

**Bước B — trung bình đối xứng $W$ điểm.** $W$ lấy ở cột làm mượt của profile (mục 5). $W$ lẻ. Nửa cửa sổ là $h = (W - 1) / 2$. Mỗi ô lấy chính nó và $h$ ô mỗi bên, phản xạ tại `sec_start` và `sec_end - 1` để cửa sổ luôn đủ $W$ điểm:

$$\tilde{\ell}(b) = \frac{1}{W} \sum_{k=-h}^{h} \ell(b+k)$$

Một giá trị cho cả ô. Vi mô trong ô nằm ở $V_{\text{đã viết}}$.

$W$ là chu kỳ cường độ của loại nhạc, tính bằng ô. Câu ngân thở dài, nên nhìn xa. Điệu đổi cường độ theo cụm ngắn, nên nhìn gần. Cùng một chuỗi volume, hai profile khác $W$ có thể đặt đỉnh $\tilde{\ell}$ ở hai ô khác nhau.

Ô nóng đứng một mình trên nền phẳng cho cao nguyên $W$ ô cân quanh nó, và ô nóng nằm trong cực đại của $\tilde{\ell}$.

Khi sau ô nóng là một vai cao, cực đại của $\tilde{\ell}$ nằm trên vai, không nằm trên ô $\ell$ lớn nhất. Với $W = 5$ và $\ell = (0, 0, 5, 4, 4, 4, 4)$:

- Ô giá trị `5` có cửa sổ $(0, 0, 5, 4, 4)$, trung bình `2.6`.
- Ô giữa vai có cửa sổ $(5, 4, 4, 4, 4)$, trung bình `4.2`.

Bước D nâng các ô lân cận của đỉnh $\tilde{\ell}$. Bước đó không kéo cực đại về ô `5`. Đỉnh $C$ là đỉnh của chuỗi đã làm mượt bằng đúng $W$ của profile.

**Bước C — chuẩn hóa trong section.**

- Nếu $\max \tilde{\ell} - \min \tilde{\ell} \le 10^{-6}$ (volume phẳng): $U(b)$ lấy theo band của ô, `{"p": 0.15, "mp": 0.40, "mf": 0.65, "f": 0.90}`. $C$ đứng yên trong section.
- Nếu có biến thiên, kéo $\tilde{\ell}$ về $[0, 1]$:

$$U_{\text{raw}}(b) = \frac{\tilde{\ell}(b) - \min \tilde{\ell}}{\max \tilde{\ell} - \min \tilde{\ell}} \in [0, 1]$$

**Bước D — chặn bước giữa hai ô kề.** $C$ là một số trong cả ô, nên hai ô kề có $U$ cách xa thì cả khối nhảy đúng $C_{\text{hi}} - C_{\text{lo}}$ tại vạch nhịp. Với cửa sổ trong bảng, quãng đó khoảng `3..8` bậc. Chặn bước của $C$ ở `4` bậc MIDI:

$$\Delta_U = \frac{4}{C_{\text{hi}} - C_{\text{lo}}}, \qquad U(b) = \max_{j \in \text{section}}\left(U_{\text{raw}}(j) - \Delta_U \cdot \lvert b - j \rvert\right)$$

$C_{\text{lo}}$ và $C_{\text{hi}}$ lấy ở mục 2.3, tính trước bước này. $U$ là hàm Lipschitz nhỏ nhất nằm trên $U_{\text{raw}}$ với bước tối đa $\Delta_U$. Ô đang là đỉnh của $U_{\text{raw}}$ (tức đỉnh của $\tilde{\ell}$) giữ nguyên $U = 1$. Ô trũng sát một vách đứng được nâng thành đường dốc `4` bậc mỗi ô. Khi $U_{\text{raw}}$ đã thoải hơn mức này, $U = U_{\text{raw}}$. Hệ quả trên thủy triều:

$$\lvert C(b) - C(b-1) \rvert \le 4$$

Bậc ghi vào nốt là $\lvert \mathrm{round}(C(b)) - \mathrm{round}(C(b-1)) \rvert$. Python làm tròn half-to-even. Hai mức cách nhau đúng 4 và cùng đuôi `.5` có phần nguyên cùng tính chẵn, nên cả hai bị đẩy về cùng một phía và bậc sau làm tròn vẫn là `4`.

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

Mọi cửa sổ trong bảng mục 5, kể cả đầu calm, đầu wide, và đoạn `trio` / `bridge` (kéo về calm), đều có $V_{\text{ceil}} - V_{\text{floor}} \ge 27 > 24$. Vậy $M = 1$ trên mọi section của 28 profile. Hiệu MIDI trong một ô không bị co. Với $M = 1$:

$$C_{\text{lo}} = V_{\text{floor}} + 16, \qquad C_{\text{hi}} = V_{\text{ceil}} - 8, \qquad C(b) = C_{\text{lo}} + U(b) \cdot (C_{\text{hi}} - C_{\text{lo}})$$

Quãng thủy triều $C_{\text{hi}} - C_{\text{lo}} = (V_{\text{ceil}} - V_{\text{floor}}) - 24$ nằm trong khoảng `3..8` bậc. Trần giữ nguyên, nên $C_{\text{hi}}$ giữ nguyên. Sàn andante wide cao hơn `4` bậc và quãng của dòng đó ngắn `4`. Sàn các calm có trần từ `54`, cùng gavotte wide và cantabile wide, cao hơn `2` bậc. Mười một cửa sổ wide còn lại sau sàn `+4` ở thủy triều `3`: bourrée, fuga, gigue, galop, tremolo, choro, polca, hemiola, thumb Villa, etude 1, etude 11. $C$ đổi theo ô, và là một số cho mọi nốt trong ô đó.

### 2.4. Phép lọc

Với mọi nốt sounding (có `midi`, có `velocity`, không phải `tie_stop`) trong ô $b$:

$$d = V_{\text{đã viết}} - 64, \qquad V_{\text{thô}} = \mathrm{round}\big(C(b)\big) + d$$

`round` là half-to-even của Python, gọi một lần cho cả ô. Cộng $d$ nguyên phía sau. Hai nốt trong cùng một ô giữ đúng hiệu đã viết, kể cả khi $C$ có đuôi `.5`:

$$V_{\text{thô}}(e_1) - V_{\text{thô}}(e_2) = V_{\text{đã viết}}(e_1) - V_{\text{đã viết}}(e_2)$$

`round(C + d)` không cho hiệu đó. Với $C = 40.5$, Python làm tròn `40.5 → 40` và `41.5 → 42`. Hai nốt viết cách nhau 1 bậc (`64` và `65`) ra `40` và `42`. Công thức trên làm tròn $C$ thành `40` trước, rồi ra `40` và `41`.

Hai nốt khác ô lệch thêm bậc thủy triều đã làm tròn:

$$V_{\text{thô}}(e_1) - V_{\text{thô}}(e_2) = \big(V_{\text{đã viết}}(e_1) - V_{\text{đã viết}}(e_2)\big) + \big(\mathrm{round}\,C(b_1) - \mathrm{round}\,C(b_2)\big)$$

Trên thân bài, nốt viết `72` chạm đúng $V_{\text{ceil}}$ ở ô $U = 1$. Nốt viết `48` chạm đúng $V_{\text{floor}}$ chỉ ở ô còn $U = 0$. Bước D nâng mọi ô trũng đứng gần đỉnh, nên ô $U = 0$ chỉ còn khi ô $\tilde{\ell}$ nhỏ nhất cách ô $\tilde{\ell}$ lớn nhất ít nhất

$$\left\lceil \frac{C_{\text{hi}} - C_{\text{lo}}}{4} \right\rceil$$

ô. Quãng `5` đến `8` cần khoảng cách `2` ô. Quãng `3` hoặc `4` đã nằm trong bước `4`, nên hai ô kề vẫn có thể là $U = 0$ và $U = 1$. Section có đỉnh và đáy sát hơn khoảng đó không có ô $U = 0$, và nốt viết `48` không chạm $V_{\text{floor}}$.

Nốt thân bài viết ngoài khoảng đó vẫn cộng cùng $\mathrm{round}(C(b))$. Sau phép cộng, nốt thân bài không được Cổng Snap chọn và không phải stab khung (mục 4) chỉ kẹp trần

$$V_{\text{ceil}} \le 63$$

Nốt viết `48` chạm $V_{\text{floor}}$ nhờ $C_{\text{lo}} = V_{\text{floor}} + 16$, không nhờ kẹp sàn. Chuông viết `44` ở đáy giữ bước đó và thấp hơn sàn `4` bậc.

Ô intro và outro không kẹp từng nốt vào $F$, và không cộng một $K$ riêng mỗi ô. $K$ từng ô khử $\mathrm{round}(C)$: chuông `44, 50, 46` ra cùng một bộ số cho mọi tâm. Đường tâm dùng $L$ của mục 4. Sau đường đó, nốt nào vượt `63` bị kéo về `63`. Hiệu trong ô giữ nguyên cho tới khi một nốt chạm trần. Humanize trừ tối đa `2` trên một dải nốt cùng vận tốc. Chuông noviembre ở đáy ghi `20`, nên dải đó có thể xuống `18`.

Trên ô đỉnh của ví dụ dưới, nốt viết `80` ra `52 + 16 = 68`, rồi kẹp về `60`. Humanize nhìn thấy `60`, đi nhánh `<= 64`, và dừng ở `<= 64`. Nó không bị kéo vào `66..76`. Trên ô trũng, `80` ra `48 + 16 = 64`, rồi kẹp về `60`. Đỉnh của nốt `72` vẫn là `60`, đúng trần cũ. Quãng thủy triều ngắn hơn nên nốt viết trên `72` chạm trần ở cả hai đầu; các nốt trong `48..72` vẫn giữ hiệu đã viết.

**Ví dụ.** Andante Barrios, cửa sổ wide `[32, 60]`. So với cửa sổ wide cũ `[28, 60]`, sàn lên `4`, trần giữ `60`. Quãng tâm của nốt `64` từ `8` bậc (`44 → 52`) còn `4` bậc (`48 → 52`).

$$M = 1, \quad C_{\text{lo}} = 48, \quad C_{\text{hi}} = 52$$

| Nốt đã viết | $d$ | Ô trũng $C = 48$ | Ô đỉnh $C = 52$ |
|---|---|---|---|
| Giai điệu 64 | 0 | 48 | 52 |
| Đỉnh 72 | +8 | 56 | 60 |
| Bè trong 48 | −16 | 32 | 36 |
| Viết 80, trước kẹp | +16 | 64 → kẹp `60` | 68 → kẹp `60` |

Trong từng ô, chênh `72 − 64 = 8` và `64 − 48 = 16` đứng yên khi chưa chạm kẹp. Giữa ô trũng và ô đỉnh, cùng một nốt `64` lệch thêm `52 − 48 = 4`. Bước D giữ mỗi vạch nhịp trong mức `4` bậc, nên quãng `4` này đã nằm trong một vạch: hai ô kề có thể là đáy và đỉnh.

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

Các ô `pedal` (`intro`, `warmup`, `outro`, `cooldown`) dùng $\mathrm{round}(C) + d$, rồi kéo nốt vượt `63` về `63`. Trong một ô, hiệu MIDI của cử chỉ giữ nguyên cho tới khi một nốt chạm trần đó. Các ô này không kẹp sàn $V_{\text{floor}}$.

$F$ là sàn cửa sổ của ô thân bài đang nối: ô thân bài đầu với intro, ô thân bài cuối với outro. Với mỗi ô pedal,

$$L(b) = \max(F,\; 22) - \min(V - 64)$$

`22` là sàn “nốt còn kêu”, dùng chung. $F$ là sàn của thể loại. Mọi sàn trong bảng đều trên `22`, nên $L(b) = F - \min(V - 64)$. Một lần kéo tâm cho cả ô. Nốt intro không bị kẹp vào $F$ sau phép cộng: kiểu kẹp đó làm chuông `44, 50, 46` ra cùng một bộ số cho mọi tâm.

Chuông có $\min(V - 64) = -20$, nên $L = F + 20$. Gigue wide, $F = 36$, nốt viết `50`: $L = 50$, và tại tâm đó nốt `50` là `36`.

Đường intro và outro tính trước, với bước `4` và hai đầu nối như dưới. So sánh $C$ thân bài với $L$ gồm cả mốc bằng:

- $C \ge L$: vẽ một đường thẳng. Đầu nối giữ $C$ thân bài. Bước không quá `4`. Khi $C = L$, đường đó là một mức phẳng tại $C$.
- $C < L$: cả đoạn pedal đứng yên ở đúng $C$ thân bài. Vạch nối không đổi.

Đường thì thầm từ `27`, và đường outro xuống `23`, không được dùng khi một ô còn dưới $L$. Noviembre calm là đáy thấp nhất: sàn `24`, trần `52`, $C_{\text{lo}} = 40$, $C_{\text{hi}} = 44$. Chuông `44` ở ô $U = 0$ ghi `20`. Giữ trần `52` thì không có sàn nào vừa để thủy triều `4` vừa đưa chuông đó tới `22`. Các calm trần từ `54` trở lên không kẹt như vậy: andante calm sàn `26`, trần `54`, tâm nốt `64` đi `42 → 46`, chuông ở đáy là `22`.

- **Intro**: $C_{\text{whisper}}$ là mức làm nốt viết `64` rơi vào `27` (giữa `22..32`). $C(b_{\text{body}})$ là $C$ của ô thân bài đầu tiên. Có $M_{\text{lead}}$ ô pedal dẫn, chỉ số $i = 0 \dots M_{\text{lead}} - 1$.

  - $M_{\text{lead}} = 1$: ô đó chính là ô pedal cuối, nhận $C(b_{\text{body}})$. Công thức $i / (M_{\text{lead}} - 1)$ không dùng cho trường hợp này, vì mẫu số bằng 0 và giá trị thay thế $C_{\text{whisper}}$ sẽ để ô nối đứng ở `27`.
  - $M_{\text{lead}} \ge 2$:

$$C_{\text{intro}}(i) = C_{\text{whisper}} + \big(C(b_{\text{body}}) - C_{\text{whisper}}\big) \cdot \frac{i}{M_{\text{lead}} - 1}$$

  Ô $i = M_{\text{lead}} - 1$ nhận đúng $C(b_{\text{body}})$. Vạch nhịp vào thân bài nối tiếp về $C$. Phần nhảy còn lại là nhảy của vận tốc đã viết. Các ô trước đó đi từ `27` lên mức mở của ô nối. Bước giữa hai ô intro kề cũng bị chặn `4` bậc, cùng quy tắc mục 2.2D: nếu $C(b_{\text{body}}) - C_{\text{whisper}} > 4 \cdot (M_{\text{lead}} - 1)$, các ô đầu được nâng để đường dốc không vượt `4` mỗi vạch, và ô cuối vẫn là $C(b_{\text{body}})$.

  Khi đường này chui xuống dưới $L$ mà $C(b_{\text{body}}) > L$, đầu đoạn được nâng và quãng từ đầu mới tới $C(b_{\text{body}})$ trải đều trên mọi ô intro. Nhánh `return list(centers)` chỉ giữ đường thì thầm từ `27` khi mọi ô đã nằm trên $L$. Điệu sàn cao không đi nhánh đó: đường từ `27` chui dưới $L$ mới, và đầu đoạn được nâng tới $L$ của $F$.

  Mỗi ô intro cách ô kế tối đa `4` bậc. Một ô nhận đúng $C$ thân bài. Hai ô chỉ thấp hơn thân bài tối đa `4`. Bốn ô có `12` bậc để đi xuống. Sáu ô có `20` bậc.

  Gigue `6/8` wide, sáu ô, nốt viết `50`, $F = 36$. $L = 50$. Tâm thân bài nằm trong `52..55`, cao hơn $L$. Ô mở đứng ở tâm `50`, nốt `50` là `36`, đúng sàn wide, rồi đi lên tâm thân bài. Sàn nói `22` sẽ chặn tâm mở ở `36` và để cả ô pickup ra `22`.

  Choro wide, bốn ô, chuông `44, 50, 46`, $F = 36$, $L = 56$. Tâm thân bài `52..55` thấp hơn $L$, nên cả intro đứng ở tâm thân bài. Ở tâm `52`, chuông nghe được là `32, 38, 34`. Nốt `44` vẫn thấp hơn sàn `4` bậc. Chuông không ra `22, 28, 24`.

  Andante calm, chuông `44`, $F = 26$, $L = 46$. Tâm thân bài phẳng, band `mf`, là `44.6`. Cả 8 ô đứng ở `44.6`. `round(44.6) = 45`, nốt `44` là `25` trên mọi ô. Dãy `22, 22, 23, 23, 23, 24, 24, 25` không còn. Nốt viết `64` trên ô intro cuối vẫn bằng ô thân bài.

  Khi $C(b_{\text{body}}) = L$, đường là một mức phẳng tại $C$. Nốt viết `64` vẫn nối đúng ô thân bài. Đường `27 → C` không được dùng khi một ô còn dưới $L$.

- **Outro**: giữ ô đầu, tức ô sát thân bài, ở $C$ của ô thân bài cuối. Bước D chỉ nâng chỗ trũng; nó không kéo một đầu đã cao xuống `23`. Có $N$ ô outro, chỉ số $i = 0 \dots N - 1$, mỗi vạch tối đa `4` bậc:

$$C_{\text{outro}}(i) = \max\big(23,\; C(b_{\text{body}}) - 4 \cdot i\big)$$

  $N = 1$: ô duy nhất nhận $C(b_{\text{body}})$. $N = 2$ chỉ có một vạch, nên từ $C = 55$ ô cuối là `51`, không phải `23`. Khoảng `55 → 23` là `32` bậc, cần `8` vạch, tức $N = 9$, thì ô cuối mới bằng `23` khi nốt trong ô còn nói được ở tâm `23`. Giữ ô cuối ở `23` sẽ làm ô đầu rời $C$ thân bài; thiết kế này không chọn đầu đó.

  Outro dùng cùng $L$. Nốt viết `64` có $L = F$. Điệu sàn `36` không xuống tâm `23`: cuối đoạn đứng ở `36` khi đường tính trước chui dưới $L$. Outro hai ô từ tâm `55`, toàn nốt `64`, vẫn kết ở `51`, vì `51` nằm trên $L$. Outro chín ô toàn nốt `64` chỉ tới `23` khi $F \le 23$. Các sàn trong bảng đều trên `23`, nên cuối đoạn là $F$. Ô có chuông dùng $L = F + 20$. Khi tâm thân bài còn trên mức đó, đường giảm tới $L$ và nốt `44` kết ở $F$. Khi tâm thân bài thấp hơn $L$, cả outro đứng ở tâm thân bài. Gán thẳng `42, 38, 34, 30, 26, 23` không được dùng; nốt `44` không thành `22, 18, 14, 10, 6, 3`. Nốt viết `64` trên ô đầu vẫn bằng ô thân bài.

  Chuông viết `44` ở đáy thủy triều của thân bài vẫn thấp hơn sàn `4` bậc: nốt đó nằm `20` dưới mốc `64`, còn $C_{\text{lo}}$ chỉ cao hơn sàn `16`. Ô toàn nốt viết `50` hết lệch này ở intro: tâm mở `50`, nốt nghe `36`. Intro Sor của galop có nốt `_PP` = `46` trong cùng ô. Wide thì $L = 54$. Tâm thân bài `52` hoặc `53` thấp hơn $L$, cả intro đứng ở tâm đó, và nốt `46` nghe được là `34` hoặc `35`, vẫn dưới sàn `36`. Stab khung gán sau bộ lọc, giữ `70 / 66 / 62`.

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

`floor_*` và `ceil_*` là cửa sổ đầu ra của **cả khối nốt**, không phải ba đường cong thay thế lead / bass / support. Với $d_{\text{lo}} = -16$, $d_{\text{hi}} = +8$, mọi dòng dưới đây có $V_{\text{ceil}} - V_{\text{floor}} \ge 27$, nên $M = 1$. $C_{\text{lo}}$ và $C_{\text{hi}}$ suy ra theo mục 2.3. Trần giữ nguyên. Andante wide cộng sàn `4`. Calm có trần từ `54`, cùng gavotte wide và cantabile wide, cộng sàn `2`. Noviembre calm cộng sàn `2` và nhận thủy triều `4`.

$W$ là chu kỳ cường độ, và là số điểm của trung bình đối xứng:

- **`9` — câu ngân.** Sarabande, fuga, chaconne, cantabile, elegiaque, andante, thumb cantabile, tremolo, chord melody, noviembre. Cường độ đi theo cả câu.
- **`5` — câu chạy.** Gavotte, bourrée, study, biến tấu Mozart, preludio, hai etude Villa.
- **`3` — điệu.** Gigue, galop, choro, polca, hemiola, vals, tresillo Villa, etude Brouwer, pizz. Cường độ đổi theo cụm vài ô.

```python
@dataclass(frozen=True)
class PatternWaveProfile:
    floor_calm: int            # sàn cửa sổ khi alpha_warm = 0, >= 24
    floor_wide: int            # sàn cửa sổ khi alpha_warm = 1
    ceil_calm: int             # trần ấm khi alpha_warm = 0, <= 60
    ceil_wide: int             # trần ấm khi alpha_warm = 1, <= 63
    snap_calm: int | None      # None nếu cấm ép dây; >= 66 nếu có
    snap_wide: int | None      # trần snap khi alpha_price = 1, trong 68..76
    max_units_per_phrase: int  # 0 hoặc 1
    max_units_per_sec: int     # 0..4
    snap_targets: str
    smooth: int                # W lẻ: 9 câu ngân, 5 câu chạy, 3 điệu
    d_lo: int = -16            # lệch dưới tâm 64 mà bộ lọc giữ hết
    d_hi: int = 8              # lệch trên tâm 64 mà bộ lọc giữ hết
```

| Khóa `(ensemble, pattern)` | Cửa sổ calm → wide | $W$ | Snap | Hạn mức `(phrase, sec)` | Cú được snap |
|---|---|---|---|---|---|
| `("bach", "bach_sarabande")` | `28..56` → `34..62` | 9 | không | `(0, 0)` | Phách 2 và mordent ở trong cửa sổ ấm. |
| `("bach", "bach_gavotte")` | `30..58` → `34..62` | 5 | `66..68` | `(1, 2)` | Phách 1 đầu câu đỉnh khi `phrase.rise >= 3`. |
| `("bach", "bach_bourree")` | `30..58` → `36..63` | 5 | `66..68` | `(1, 3)` | `phrase.apex` sau cặp lấy đà khi `rise >= 3`. |
| `("bach", "bach_fuga")` | `30..58` → `36..63` | 9 | `66..68` | `(1, 2)` | `phrase.apex` của soprano ở câu cao trào. |
| `("bach", "bach_gigue")` | `30..58` → `36..63` | 3 | `68..70` | `(1, 3)` | Nốt đầu câu chạy scale, hoặc phách mạnh tại đỉnh. |
| `("bach", "bach_chaconne")` | `28..58` → `34..63` | 9 | `68..70` | `(1, 3)` | Nốt đích cuối câu scale breakout (`accent=True`). |
| `("classic", "cantabile")` | `26..54` → `30..58` | 9 | không | `(0, 0)` | Song thanh quãng 3/6 nằm trong cửa sổ ấm. |
| `("classic", "elegiaque")` | `26..56` → `32..62` | 9 | `66..68` | `(1, 2)` | Appoggiatura (`accent=True`) ở câu đỉnh. |
| `("classic", "study")` | `28..56` → `34..63` | 5 | `68..70` | `(1, 2)` | Fanfare mở đoạn `f`, hoặc đích Grand Solo, hoặc `phrase.apex` khi rally. |
| `("classic", "mozart_var")` | `28..56` → `34..62` | 5 | `66..68` | `(1, 2)` | `phrase.apex` khi `rise >= 3`. |
| `("classic", "galop")` | `30..58` → `36..63` | 3 | không | `(0, 0)` | Câu phi tự dâng trong ô. Phách 0 là đáy, không snap. |
| `("barrios", "preludio")` | `28..56` → `34..62` | 5 | `66..68` | `(1, 2)` | Tối đa 2 nốt Canto 1 tại đỉnh section. |
| `("barrios", "andante")` | `26..54` → `32..60` | 9 | không | `(0, 0)` | Không ép dây. |
| `("barrios", "thumb_cantabile")` | `28..56` → `34..62` | 9 | `66..68` | `(1, 2)` | 1–2 nốt ngón cái `low` tại đỉnh câu. |
| `("barrios", "tremolo")` | `30..58` → `36..63` | 9 | `68..72` | `(1, 2)` | Phách đỉnh của ô cao trào. Fill giữ $V_{\text{ra}}$, kẹp `<= 63` nếu vượt. |
| `("barrios", "choro")` | `30..58` → `36..63` | 3 | `70..74` | `(1, 4)` | Nhấn lệch phách `accent=True` hoặc `phrase.apex`. |
| `("barrios", "polca")` | `30..58` → `36..63` | 3 | `70..72` | `(1, 3)` | Nhấn lệch phách `accent=True` tại đỉnh sóng. |
| `("barrios", "hemiola")` | `30..58` → `36..63` | 3 | `70..74` | `(1, 4)` | Phách hemiola `accent=True` tại đỉnh sóng. |
| `("barrios", "vals")` | `28..58` → `34..62` | 3 | `68..72` | `(1, 3)` | Phách 2 (`eighth == 4`, `accent=True`) tại đỉnh sóng. |
| `("villa", "chord_melody")` | `26..54` → `32..60` | 9 | không | `(0, 0)` | Hợp âm khối ngân trong cửa sổ ấm. |
| `("villa", "thumb_cantabile")` | `30..58` → `36..63` | 9 | `68..70` | `(1, 2)` | Đỉnh câu ngón cái `low`. |
| `("villa", "villa_pattern")` | `28..58` → `34..63` | 3 | `68..72` | `(1, 3)` | Bộ Tresillo `{0, 3, 6}` (1 unit) hoặc `phrase.apex`. |
| `("villa", "etude1")` | `30..58` → `36..63` | 5 | `68..70` | `(1, 2)` | 1 nốt hát trong ô đỉnh. |
| `("villa", "etude11")` | `30..58` → `36..63` | 5 | `70..74` | `(1, 3)` | Cú 1 của `lead` tại phách `phrase.apex`. |
| `("brouwer", "noviembre")` | `24..52` → `30..58` | 9 | không | `(0, 0)` | Không ép dây. Sàn calm `+2`: thủy triều `4`, chuông ở đáy ghi `20`. |
| `("brouwer", "sarabande")` | `26..56` → `32..62` | 9 | `68..72` | `(1, 2)` | Hợp âm nhấn phách 2 tại đỉnh. |
| `("brouwer", "brouwer_etude")` | `26..58` → `32..63` | 3 | `68..72` | `(1, 3)` | Downbeat / tumbao `accent=True` ở ô đỉnh. |
| `("brouwer", "elogio_pizz")` | `26..56` → `32..62` | 3 | `72..76` | `(1, 4)` | Bartók slap tại móc đơn thứ 3. $\alpha_{\text{price}} < 0.25$ thì $K_{\text{sec}} = 1$. |

---

## 6. Humanize

Trên `score.variant == "guitar"`:

- `written_velocity <= 64` → `heard_velocity = min(64, heard_velocity)`.
- `written_velocity >= 65` → `heard_velocity = max(66, min(76, heard_velocity))`.

Nốt ấm không trượt sang `65`. Cụm snap không vượt `76`.

Nhánh `>= 65` chỉ đúng với nốt Cổng Snap đã ghi `66..76` và stab khung `70` / `66`. Mọi nốt còn lại rời `apply_guitar_wave` ở $\le 63$, kể cả nốt pattern viết trên `72`. Một nốt viết `80` trên ô đỉnh không còn đường vào `66..76` khi cổng snap không chọn nó.

---

## 7. Thứ tự sửa code

1. **Sóng $U(b)$.** Trong `guitar_wave.py`, làm mượt bằng log → trung bình đối xứng $W$ điểm của profile → min–max trong section → chặn bước $\Delta_U = 4 / (C_{\text{hi}} - C_{\text{lo}})$ (mục 2.2). Band fallback khi volume phẳng. $C$ vẫn là một số cho cả ô.
2. **Hằng số.** Giữ 28 profile ở mục 5, với sàn, trần và $W$ của bảng đó. Bỏ các trường đường cong bass / support / gamma khỏi công thức vận tốc. Với bảng này $M = 1$. Tính $C_{\text{lo}}$, $C_{\text{hi}}$ theo mục 2.3 cho từng section.
3. **`_shape_dynamics`.** Giữ `extra` của câu. Bỏ `_BAND_DELTA` và bỏ kẹp `[44, 78]` trên đường đi vào bộ lọc, để band thô không cộng dồn với $C$.
4. **`apply_guitar_wave`.** Một vòng trên mọi nốt sounding: $V_{\text{thô}} = \mathrm{round}(C(b)) + (V - 64)$. Thân bài chỉ kẹp trần $V_{\text{ceil}} \le 63$. Nốt viết `48` chạm $V_{\text{floor}}$ nhờ $C_{\text{lo}} = V_{\text{floor}} + 16$. Chuông `44` ở đáy giữ bước và thấp hơn sàn `4` bậc. Intro và outro không cộng $K$ từng ô và không kẹp từng nốt vào $F$. $L(b) = \max(F, 22) - \min(V - 64)$, với $F$ là sàn cửa sổ của ô thân bài đang nối (mục 4). Giữ `fit_intro` / `fit_outro`, kể cả nhánh `return list(centers)`: nhánh đó giữ đường thì thầm từ `27` khi mọi ô đã trên $L$. Đổi mốc $L$, không xóa nhánh. Khi một ô còn dưới $L$: $C \ge L$ thì nâng đầu và trải tới $C$ thân bài, $C = L$ là mức phẳng, $C < L$ thì cả đoạn đứng ở $C$ thân bài. Rồi kéo nốt vượt `63` về `63`. Xóa `_assign_generic`, `_assign_tremolo`, `_assign_etude1`, `_assign_etude11`, `_assign_preludio` và pass xếp tầng ba bè. Intro một ô nhận $C(b_{\text{body}})$. Stab khung vẫn gán `70 / 66 / 62` sau bước kẹp.
5. **Snap.** Giữ ngân sách và $V_{\text{snapped}}$. Chỉ ghi đè cú được chọn, sau bước kẹp trần ấm.
6. **Humanize.** Giữ chốt mục 6. Nhánh `>= 65` không nhận nốt affine.
7. **Test.** Đổi `test_guitar_wave.py` sang các bất biến ở mục 8. Các assertion số tuyệt đối cũ trong `test_sonify_guitar.py` chuyển sang kiểm tra hiệu trong cùng một ô và cửa sổ genre.

---

## 8. Bất biến cần test

1. **Hiệu trong cùng một ô.** $V_{\text{thô}} = \mathrm{round}(C(b)) + (V - 64)$. Mọi cặp nốt sounding cùng ô giữ đúng $V_i - V_j$ khi cả hai chưa chạm kẹp, kể cả lúc $C = 40.5$ (nốt viết `64` và `65` ra cách nhau `1`, không phải `2`), và kể cả tremolo, etude, preludio, pattern thường. Hai nốt khác ô lệch thêm $\mathrm{round}\,C(b_1) - \mathrm{round}\,C(b_2)$. Trên 28 profile, $M = 1$.
2. **Khóa biên trên thân bài.** Nốt viết `72` tại ô $U = 1$ ra đúng $V_{\text{ceil}} \le 63$. Nốt viết `48` ra đúng $V_{\text{floor}}$ chỉ khi ô $\tilde{\ell}$ nhỏ nhất cách ô $\tilde{\ell}$ lớn nhất ít nhất $\lceil (C_{\text{hi}} - C_{\text{lo}}) / 4 \rceil$ ô (với quãng `6` hoặc `7`, là `2` ô). Section ngắn hơn khoảng đó không có ô $U = 0$, và nốt `48` không chạm $V_{\text{floor}}$. Andante Barrios wide: nốt `64` ở đáy là `48`, ở đỉnh là `52`. Nốt viết `80` tại ô $U = 1$ ra đúng $V_{\text{ceil}} = 60$ trước humanize và `<= 64` sau humanize.
3. **Đỉnh của chuỗi đã làm mượt, và bước vạch nhịp.** Ô có $\tilde{\ell}$ lớn nhất có $C$ bằng cực đại của section. $\tilde{\ell}$ dùng $W$ của profile. Với $W = 5$ và $\ell = (0, 0, 5, 4, 4, 4, 4)$, cực đại nằm ở ô trung bình `4.2`, không ở ô thô `5`. Cùng chuỗi đó, profile $W = 3$ và profile $W = 9$ mỗi bên lấy đỉnh của trung bình của chính nó. $|\mathrm{round}(C(b)) - \mathrm{round}(C(b-1))| \le 4$. $C$ không đổi bên trong một ô.
4. **Volume phẳng.** Cả section một mức volume thì mọi ô cùng một $C$ lấy từ band fallback. Hiệu trong ô giữ nguyên.
5. **Band không cộng hai lần.** Một nốt viết `64` trên band `p` và trên band `f`, cùng $U$, ra cùng $V_{\text{ra}}$.
6. **Snap hiếm.** Pattern `snap_wide is None`: không nốt nào vượt `64` sau humanize, kể cả nốt viết trên `72`. Pattern có snap, $\alpha_{\text{price}} \ge 0.50$: có ít nhất một unit trong `[66, snap_wide]`, không quá $K_{\text{sec}}$, không nốt nào sau humanize vượt `76`. Nốt không được chọn trong cùng ô giữ kết quả affine đã kẹp `<= 63`.
7. **Theo section.** Chương nhiều section: section $\alpha_{\text{price}} = 0$ có $K_{\text{sec}} = 0$ (trừ tối đa một slap `elogio_pizz`). `trio` / `bridge` dùng $\alpha_{\text{warm}}$ đã nhân `0.50`, nên cửa sổ và quãng chạy của $C$ hẹp hơn phần A cùng profile. $M$ của đoạn đó vẫn là `1`.
8. **Intro / outro.** Hiệu trong một cử chỉ của cùng một ô frame giữ nguyên khi chưa nốt nào chạm `63`, và không nốt intro nào bị kẹp vào $F$. $L = \max(F, 22) - \min(V - 64)$. Gigue wide, sáu ô, nốt viết `50`: $L = 50$, ô mở đứng ở tâm `50`, nốt `50` nghe được là `36`, rồi đường tâm đi lên tâm thân bài `52..55`. Choro wide, bốn ô, chuông `44, 50, 46`: $L = 56$, cả intro đứng ở tâm thân bài `52..55`, không ra `22, 28, 24`; ở tâm `52` chuông nghe `32, 38, 34`. Andante calm, chuông, band `mf`, $C = 44.6$: cả 8 ô đứng ở `44.6`, `round(44.6) = 45`, nốt `44` là `25`. Galop wide, intro Sor có nốt `_PP` = `46`: $L = 54$, tâm thân bài `52` hoặc `53` thấp hơn $L$, cả intro đứng ở tâm đó, nốt `46` nghe `34` hoặc `35`. Intro một ô nhận $C$ của ô thân bài đầu. Intro hai ô thấp hơn thân bài tối đa `4`. Outro giữ ô đầu ở $C$ thân bài. Outro hai ô toàn nốt `64` từ tâm `55` kết ở `51`. Điệu sàn `36` không kết outro ở `23`. Stab khung ra `70 / 66 / 62`.
