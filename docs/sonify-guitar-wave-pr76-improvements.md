# Phần còn lại để nghe thấy sóng — sàn, chu kỳ smooth

[PR 76](https://github.com/hiepsikien/VStock/pull/76) đã nằm trên `main`. `fit_intro` / `fit_outro` và đường nói `22` đã chạy. Merge một PR chỉ có tài liệu không đổi tiếng đàn: `PROFILES` và `smooth_ell` trên `main` vẫn là sàn cũ và cửa sổ 5 ô.

Việc sửa code, trên `main`:

- Mỗi `floor_calm` / `floor_wide` cộng `4` ở những cửa sổ còn nghe được sóng. Trần giữ nguyên.
- Thêm `smooth` và để `smooth_ell` dùng $W$ của profile.
- Giữ nguyên `fit_intro` / `fit_outro`, kể cả nhánh `return list(centers)`.

Snap, humanize, phép affine `round(C) + (V − 64)`, và đầu nối thân bài giữ nguyên. Công thức đầy đủ nằm ở `docs/sonify-guitar-dynamics-wave-plan.md`.

---

## 1. Nâng đáy, giữ đỉnh

Sàn nghe thấy thấp, và quãng thủy triều rộng hơn mức muốn. Trần giữ nguyên, nên $C_{\text{hi}}$ đứng yên. Sàn `+4` rút thủy triều đúng `4` bậc.

Andante wide từ `8` còn `4` là mức còn nghe sóng, đỉnh giữ `52`. Cùng nhát cắt đó để nhiều calm, cùng gavotte wide và cantabile wide, ở thủy triều `2`. Humanize nhích `±2`, nên sóng `2` bậc hòa vào nhiễu. Mở `alpha_warm` trên hai dòng wide đó chỉ kéo cả khối lên, không nới sóng.

Các dòng còn `2` chưa khóa. Nghe một calm (andante hoặc noviembre) và một điệu $W = 3$ trước. Nếu calm mất sóng, hạ nhát cắt ở những dòng đó cho thủy triều còn ít nhất `4`, và vẫn giữ đỉnh. $W = 9$ và $W = 3$ chỉ nghe khác nhau khi thủy triều còn khoảng `4` trở lên, tức chủ yếu ở wide. Thủy triều `≤ 4` thì chặn bước `4` không còn việc để làm: hai ô kề có thể là đáy và đỉnh. Điệu $W = 3$ khi đó vừa nhỏ vừa gắt. $W = 9$ san một ô nóng thành cao nguyên 9 ô và có thể đặt đỉnh $C$ lên vai sau ô nóng. Mức đỉnh giữ nguyên. Vị trí đỉnh trễ và dài hơn cửa sổ 5.

`M` vẫn là `1` khi cửa sổ còn rộng ít nhất `26`. Quãng tâm sau sàn `+4` nằm trong `2..7`.

$$C_{\text{lo}} = V_{\text{floor}} + 16, \qquad C_{\text{hi}} = V_{\text{ceil}} - 8$$

Andante Barrios, cửa sổ wide. PR đang `[28, 60]`, tâm nốt `64` đi `44 → 52` (8 bậc). Cửa sổ mới `[32, 60]`: trần giữ `60`, `C_lo = 48`, `C_hi = 52`, tâm đi `48 → 52` (4 bậc).

| Nốt đã viết | Ô trũng `C = 48` | Ô đỉnh `C = 52` |
|---|---|---|
| 64 | 48 | 52 |
| 72 | 56 | 60 |
| 48 | 32 | 36 |
| 80 | 64, kẹp `60` | 68, kẹp `60` |

Nốt trong `48..72` giữ hiệu đã viết. Đỉnh nốt `72` vẫn là `60`. Nốt `80` chạm trần `60` ở cả hai đầu.

Cửa sổ dưới đây là ứng viên sàn `+4`, trần giữ nguyên: `floor..ceil` calm, rồi wide. Cột đầu là số đang nằm trong `PROFILES` trên `main`. Dòng nào sau cắt còn thủy triều `2` thì chưa khóa.

| Khóa | PR 76 | Cửa sổ mới | $W$ |
|---|---|---|---|
| `bach_sarabande` | `26..56` → `30..62` | `30..56` → `34..62` | 9 |
| `bach_gavotte` | `28..58` → `32..62` | `32..58` → `36..62` | 5 |
| `bach_bourree` | `28..58` → `32..63` | `32..58` → `36..63` | 5 |
| `bach_fuga` | `28..58` → `32..63` | `32..58` → `36..63` | 9 |
| `bach_gigue` | `28..58` → `32..63` | `32..58` → `36..63` | 3 |
| `bach_chaconne` | `26..58` → `30..63` | `30..58` → `34..63` | 9 |
| `cantabile` | `24..54` → `28..58` | `28..54` → `32..58` | 9 |
| `elegiaque` | `24..56` → `28..62` | `28..56` → `32..62` | 9 |
| `study` | `26..56` → `30..63` | `30..56` → `34..63` | 5 |
| `mozart_var` | `26..56` → `30..62` | `30..56` → `34..62` | 5 |
| `galop` | `28..58` → `32..63` | `32..58` → `36..63` | 3 |
| `preludio` | `26..56` → `30..62` | `30..56` → `34..62` | 5 |
| `andante` | `24..54` → `28..60` | `28..54` → `32..60` | 9 |
| `barrios thumb_cantabile` | `26..56` → `30..62` | `30..56` → `34..62` | 9 |
| `tremolo` | `28..58` → `32..63` | `32..58` → `36..63` | 9 |
| `choro` | `28..58` → `32..63` | `32..58` → `36..63` | 3 |
| `polca` | `28..58` → `32..63` | `32..58` → `36..63` | 3 |
| `hemiola` | `28..58` → `32..63` | `32..58` → `36..63` | 3 |
| `vals` | `26..58` → `30..62` | `30..58` → `34..62` | 3 |
| `chord_melody` | `24..54` → `28..60` | `28..54` → `32..60` | 9 |
| `villa thumb_cantabile` | `28..58` → `32..63` | `32..58` → `36..63` | 9 |
| `villa_pattern` | `26..58` → `30..63` | `30..58` → `34..63` | 3 |
| `etude1` | `28..58` → `32..63` | `32..58` → `36..63` | 5 |
| `etude11` | `28..58` → `32..63` | `32..58` → `36..63` | 5 |
| `noviembre` | `22..52` → `26..58` | `26..52` → `30..58` | 9 |
| `brouwer sarabande` | `24..56` → `28..62` | `28..56` → `32..62` | 9 |
| `brouwer_etude` | `24..58` → `28..63` | `28..58` → `32..63` | 3 |
| `elogio_pizz` | `24..56` → `28..62` | `28..56` → `32..62` | 3 |

`ceil_calm` lớn nhất vẫn là `58`. `ceil_wide` lớn nhất vẫn là `63`. Quãng tâm dài nhất là brouwer_etude wide: sàn `32`, trần `63`, thủy triều `7`. Đáy `C_lo` thấp nhất là noviembre calm: sàn `26`, trần `52`, `C_lo = 42`.

---

## 2. Chu kỳ smooth theo loại nhạc

`smooth_ell` trên PR lấy trung bình đều `5` điểm cho mọi pattern. Mỗi profile nhận thêm `smooth` (`W`), và trung bình đối xứng dùng đúng số đó. `W` lẻ. Nửa cửa sổ `h = (W − 1) / 2`. Mỗi ô lấy chính nó và `h` ô mỗi bên, phản xạ tại hai biên section.

- **`W = 9` — câu ngân.** Sarabande, fuga, chaconne, cantabile, elegiaque, andante, thumb cantabile, tremolo, chord melody, noviembre. Cường độ đi theo cả câu.
- **`W = 5` — câu chạy.** Gavotte, bourrée, study, biến tấu Mozart, preludio, etude 1, etude 11.
- **`W = 3` — điệu.** Gigue, galop, choro, polca, hemiola, vals, tresillo Villa, etude Brouwer, pizz. Cường độ đổi theo cụm vài ô.

Đỉnh của `C` là đỉnh của chuỗi đã làm mượt $\tilde{\ell}$, với đúng `W` của profile. Cùng một chuỗi volume, hai `W` khác nhau có thể đặt đỉnh ở hai ô khác nhau.

Ô nóng đứng một mình trên nền phẳng thành cao nguyên `W` ô cân quanh nó. Với vai sau ô nóng, `W = 5` và $\ell = (0, 0, 5, 4, 4, 4, 4)$: ô `5` trung bình `2.6`, ô giữa vai trung bình `4.2` và là đỉnh `C`. Lipschitz nâng ô lân cận của đỉnh đã mượt. Bước đó giữ nguyên ô có $\tilde{\ell}$ lớn nhất.

---

## 3. Intro giữ nguyên thuật toán

`fit_intro` / `fit_outro` trên `main` đã có đường nói `22`. Nhánh `return list(centers)` giữ đường đã tính sẵn khi mọi ô nằm trên $L$: intro thì thầm từ `27`, outro toàn nốt `64` vẫn xuống `23`. Nhánh này ở lại. Xóa nó rồi kéo mọi intro về đường nói đưa nốt viết `64` từ `27` xuống `22`.

Dãy intro `22, 22, 23, 23, 24, 24, 25, 25` chỉ xuất hiện sau khi sàn mới đẩy $C$ andante calm `mf` lên `45.3`. Thuật toán không đổi. Công thức $\max(23,\; C - 4\cdot i)$ là đường tính trước bước fit. Gán thẳng công thức đó thì chuông `44` thành `22, 18, 14, 10, 6, 3`.
