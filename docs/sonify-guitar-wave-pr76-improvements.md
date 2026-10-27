# Cải PR 76 — nâng cường độ, chu kỳ smooth, intro nhỏ

Ba việc còn lại trên [PR 76](https://github.com/hiepsikien/VStock/pull/76) (`cursor/affine-guitar-volume-wave-754a`, `ad89a89`), sau khi nghe Barrios. Công thức đầy đủ nằm ở `docs/sonify-guitar-dynamics-wave-plan.md`. File này chỉ khóa phần code của PR còn lệch spec đó.

PR đang có sàn thấp hơn `4` bậc, trần đúng mức cần giữ, `smooth_ell` cố định `5` điểm, và `fit_intro` / `fit_outro` còn nhánh `return list(centers)`. Nhánh đó trả lại đường đã tính sẵn: intro thì thầm `27 → C` và outro `max(23, C − 4·i)`.

Snap, humanize, phép affine `round(C) + (V − 64)`, và đầu nối thân bài giữ nguyên.

---

## 1. Nâng đáy, giữ đỉnh

Sàn nghe thấy thấp, và quãng thủy triều rộng hơn mức muốn. Mỗi `floor_calm` và `floor_wide` cộng `4`. Mỗi `ceil_calm` và `ceil_wide` giữ nguyên, nên $C_{\text{hi}}$ đứng yên. Quãng tâm ngắn đi đúng `4` bậc.

`M` vẫn là `1`: mọi cửa sổ mới có `V_ceil − V_floor ≥ 26 > 24`. Quãng tâm `C_hi − C_lo` nằm trong `2..7`.

$$C_{\text{lo}} = V_{\text{floor}} + 16, \qquad C_{\text{hi}} = V_{\text{ceil}} - 8$$

Andante Barrios, cửa sổ wide. PR đang `[28, 60]`, tâm nốt `64` đi `44 → 52` (8 bậc). Cửa sổ mới `[32, 60]`: trần giữ `60`, `C_lo = 48`, `C_hi = 52`, tâm đi `48 → 52` (4 bậc).

| Nốt đã viết | Ô trũng `C = 48` | Ô đỉnh `C = 52` |
|---|---|---|
| 64 | 48 | 52 |
| 72 | 56 | 60 |
| 48 | 32 | 36 |
| 80 | 64, kẹp `60` | 68, kẹp `60` |

Nốt trong `48..72` giữ hiệu đã viết. Đỉnh nốt `72` vẫn là `60`. Nốt `80` chạm trần `60` ở cả hai đầu.

Cửa sổ dưới đây là `floor..ceil` calm, rồi `floor..ceil` wide. Cột PR là số đang nằm trong `PROFILES`.

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

## 3. Intro nhỏ

Ô pedal (`intro`, `warmup`, `outro`, `cooldown`) dùng `round(C) + (V − 64)`, rồi kéo nốt vượt `63` về `63`. Các ô này không kẹp `V_floor` và không cộng `K` từng ô.

Ngưỡng ghi là `22`, để một dải humanize `−2` còn nghe ở `20`. Với mỗi ô, `L(b) = 22 − min(V − 64)` trên các nốt sounding. Chuông `44, 50, 46` có `d_min = −20`, nên `L = 42`, và tại tâm đó chuông là `22, 28, 24`.

So sánh `C` thân bài với `L`, kể cả mốc bằng:

- `C ≥ L`: một đường thẳng, đầu nối giữ `C` thân bài, mỗi vạch tối đa `4` bậc. `C = L` thì đường đó là một mức phẳng tại `C`.
- `C < L`: cả đoạn pedal đứng ở `C` thân bài. Vạch nối không đổi.

Đường thì thầm từ `27` và đường outro xuống `23` chỉ còn khi mọi ô đã nằm trên `L`. Nhánh `return list(centers)` trong `fit_intro` và `fit_outro` đang trả lại hai đường đó. Nhánh này bỏ đi.

Đáy thấp nhất của bảng mới là noviembre calm, `C_lo = 42`, đúng bằng `L` của chuông `44`. Mốc `40` nằm dưới mọi `C_lo`, nên chuông `44` không đi vào nhánh `C < L`. Nhánh đó còn khi một ô viết mềm hơn `44`.

**Intro 8 ô, chuông, nối vào đáy `C = 42`.** Cả 8 ô đứng ở `42`. Chuông là `22, 28, 24` suốt đoạn. Nốt viết `64` trên ô intro cuối bằng nốt viết `64` trên ô thân bài. Dãy tâm `27, 29, 32, 34, 37, 39, 42` không còn.

**Intro 8 ô, chuông, nối vào andante phẳng calm, band `mf`.** $C_{\text{lo}} = 44$, $C_{\text{hi}} = 46$, $U = 0.65$, nên $C = 45.3$. Quãng tâm nghe được là `42 → 45.3`. Ô đầu là `22, 28, 24`. Sau làm tròn, nốt `44` đi `22, 22, 23, 23, 24, 24, 25, 25`. Nốt viết `64` trên ô cuối bằng thân bài.

**Outro rời đáy `42`.** Cả outro đứng ở `42`. Nốt `44` là `22`. Chuông là `22, 28, 24`. Dãy `42, 38, 34, 30, 26, 23` và dãy nốt `44` thành `22, 18, 14, 10, 6, 3` không còn.

**Outro toàn nốt `64`.** `L = 22`. Từ `C = 55`, hai ô kết ở `51`. Chín ô kết ở `23`. Ô đầu vẫn là `55`.

**Outro có nốt `44` rời đỉnh `55`.** Đường giảm đều tới `42`. Nốt `44` kết ở `22`.

Intro một ô nhận `C` của ô thân bài đầu. Intro từ hai ô giữ ô cuối ở `C` thân bài.
