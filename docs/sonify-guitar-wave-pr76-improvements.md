# Phần còn lại để nghe thấy sóng — sàn, chu kỳ smooth

[PR 76](https://github.com/hiepsikien/VStock/pull/76) đã nằm trên `main`. `fit_intro` / `fit_outro` và đường nói `22` đã chạy. Merge một PR chỉ có tài liệu không đổi tiếng đàn: `PROFILES` và `smooth_ell` trên `main` vẫn là sàn cũ và cửa sổ 5 ô.

Việc sửa code, trên `main`, theo bảng mục 5 của plan:

- Andante wide: sàn `+4`, cửa sổ `32..60`. Trần giữ `60`.
- Calm có trần từ `54`, cùng gavotte wide và cantabile wide: sàn `+2`. Trần giữ nguyên.
- Noviembre calm: sàn `+2`, cửa sổ `24..52`. Thủy triều `4`. Chuông ở đáy ghi `20`.
- Thêm `smooth` và để `smooth_ell` dùng $W$ của profile, sau khi thủy triều những dòng đó còn nghe được.
- Giữ `fit_intro` / `fit_outro`, kể cả nhánh `return list(centers)`. Đổi mốc $L$ sang sàn $F$ của ô thân bài đang nối: $L = \max(F, 22) - \min(V - 64)$. Không kẹp từng nốt intro vào $F$.

Snap, humanize, phép affine `round(C) + (V − 64)`, và đầu nối thân bài giữ nguyên. Công thức đầy đủ nằm ở `docs/sonify-guitar-dynamics-wave-plan.md`.

---

## 1. Nâng đáy, giữ đỉnh

Sàn nghe thấy thấp, và quãng thủy triều rộng hơn mức muốn. Trần giữ nguyên, nên $C_{\text{hi}}$ đứng yên.

Andante wide dùng sàn `+4`: từ `8` còn `4`, đỉnh giữ `52`. Calm có trần từ `54` trở lên dùng sàn `+2`, nên thủy triều còn `4` trở lên. Gavotte wide và cantabile wide cùng nhát `+2`. Nhát `+4` trên các dòng đó để lại thủy triều `2`, và humanize `±2` nuốt mức ấy.

Andante calm là `26..54`. Tâm nốt `64` đi `42 → 46`. Đỉnh cũ `46` đứng yên. Đáy lên `2` so với `main`. Chuông `44` ở đáy ghi `22`.

Noviembre calm có trần `52`, đỉnh nốt `64` là `44`. Sàn `+4` (`26`) cho tâm `42 → 44`: chuông ở đáy còn nói, thủy triều còn `2`. Sàn `+2` (`24`) cho tâm `40 → 44`: thủy triều còn `4`, chuông ở đáy ghi `20` và humanize có thể kéo xuống `18`. Giữ trần `52` thì không có sàn nào làm được cả hai. Bảng chọn sóng, sàn `24`. Các calm trần từ `54` không kẹt như vậy.

Mười một wide sau sàn `+4` còn thủy triều `3`: bourrée, fuga, gigue, galop, tremolo, choro, polca, hemiola, thumb Villa, etude 1, etude 11. $W = 9$ và $W = 3$ nghe khác nhau khi thủy triều còn khoảng `4` trở lên. $W = 9$ san một ô nóng thành cao nguyên 9 ô và có thể đặt đỉnh $C$ lên vai sau ô nóng. Mức đỉnh giữ nguyên. Vị trí đỉnh trễ và dài hơn cửa sổ 5.

`M` vẫn là `1` khi cửa sổ còn rộng ít nhất `27`. Quãng tâm của bảng nằm trong `3..8`.

$$C_{\text{lo}} = V_{\text{floor}} + 16, \qquad C_{\text{hi}} = V_{\text{ceil}} - 8$$

Andante Barrios, cửa sổ wide. PR đang `[28, 60]`, tâm nốt `64` đi `44 → 52` (8 bậc). Cửa sổ mới `[32, 60]`: trần giữ `60`, `C_lo = 48`, `C_hi = 52`, tâm đi `48 → 52` (4 bậc).

| Nốt đã viết | Ô trũng `C = 48` | Ô đỉnh `C = 52` |
|---|---|---|
| 64 | 48 | 52 |
| 72 | 56 | 60 |
| 48 | 32 | 36 |
| 80 | 64, kẹp `60` | 68, kẹp `60` |

Nốt trong `48..72` giữ hiệu đã viết. Đỉnh nốt `72` vẫn là `60`. Nốt `80` chạm trần `60` ở cả hai đầu.

Cửa sổ dưới đây là bảng mục 5: `floor..ceil` calm, rồi wide. Cột đầu là số đang nằm trong `PROFILES` trên `main`. Trần hai cột trùng nhau.

| Khóa | PR 76 | Cửa sổ mới | $W$ |
|---|---|---|---|
| `bach_sarabande` | `26..56` → `30..62` | `28..56` → `34..62` | 9 |
| `bach_gavotte` | `28..58` → `32..62` | `30..58` → `34..62` | 5 |
| `bach_bourree` | `28..58` → `32..63` | `30..58` → `36..63` | 5 |
| `bach_fuga` | `28..58` → `32..63` | `30..58` → `36..63` | 9 |
| `bach_gigue` | `28..58` → `32..63` | `30..58` → `36..63` | 3 |
| `bach_chaconne` | `26..58` → `30..63` | `28..58` → `34..63` | 9 |
| `cantabile` | `24..54` → `28..58` | `26..54` → `30..58` | 9 |
| `elegiaque` | `24..56` → `28..62` | `26..56` → `32..62` | 9 |
| `study` | `26..56` → `30..63` | `28..56` → `34..63` | 5 |
| `mozart_var` | `26..56` → `30..62` | `28..56` → `34..62` | 5 |
| `galop` | `28..58` → `32..63` | `30..58` → `36..63` | 3 |
| `preludio` | `26..56` → `30..62` | `28..56` → `34..62` | 5 |
| `andante` | `24..54` → `28..60` | `26..54` → `32..60` | 9 |
| `barrios thumb_cantabile` | `26..56` → `30..62` | `28..56` → `34..62` | 9 |
| `tremolo` | `28..58` → `32..63` | `30..58` → `36..63` | 9 |
| `choro` | `28..58` → `32..63` | `30..58` → `36..63` | 3 |
| `polca` | `28..58` → `32..63` | `30..58` → `36..63` | 3 |
| `hemiola` | `28..58` → `32..63` | `30..58` → `36..63` | 3 |
| `vals` | `26..58` → `30..62` | `28..58` → `34..62` | 3 |
| `chord_melody` | `24..54` → `28..60` | `26..54` → `32..60` | 9 |
| `villa thumb_cantabile` | `28..58` → `32..63` | `30..58` → `36..63` | 9 |
| `villa_pattern` | `26..58` → `30..63` | `28..58` → `34..63` | 3 |
| `etude1` | `28..58` → `32..63` | `30..58` → `36..63` | 5 |
| `etude11` | `28..58` → `32..63` | `30..58` → `36..63` | 5 |
| `noviembre` | `22..52` → `26..58` | `24..52` → `30..58` | 9 |
| `brouwer sarabande` | `24..56` → `28..62` | `26..56` → `32..62` | 9 |
| `brouwer_etude` | `24..58` → `28..63` | `26..58` → `32..63` | 3 |
| `elogio_pizz` | `24..56` → `28..62` | `26..56` → `32..62` | 3 |

`ceil_calm` lớn nhất vẫn là `58`. `ceil_wide` lớn nhất vẫn là `63`. Quãng tâm dài nhất là brouwer_etude calm: sàn `26`, trần `58`, thủy triều `8`. Đáy $C_{\text{lo}}$ thấp nhất là noviembre calm: sàn `24`, trần `52`, $C_{\text{lo}} = 40$.

---

## 2. Chu kỳ smooth theo loại nhạc

`smooth_ell` trên PR lấy trung bình đều `5` điểm cho mọi pattern. Mỗi profile nhận thêm `smooth` (`W`), và trung bình đối xứng dùng đúng số đó. `W` lẻ. Nửa cửa sổ `h = (W − 1) / 2`. Mỗi ô lấy chính nó và `h` ô mỗi bên, phản xạ tại hai biên section.

- **`W = 9` — câu ngân.** Sarabande, fuga, chaconne, cantabile, elegiaque, andante, thumb cantabile, tremolo, chord melody, noviembre. Cường độ đi theo cả câu.
- **`W = 5` — câu chạy.** Gavotte, bourrée, study, biến tấu Mozart, preludio, etude 1, etude 11.
- **`W = 3` — điệu.** Gigue, galop, choro, polca, hemiola, vals, tresillo Villa, etude Brouwer, pizz. Cường độ đổi theo cụm vài ô.

Đỉnh của `C` là đỉnh của chuỗi đã làm mượt $\tilde{\ell}$, với đúng `W` của profile. Cùng một chuỗi volume, hai `W` khác nhau có thể đặt đỉnh ở hai ô khác nhau.

Ô nóng đứng một mình trên nền phẳng thành cao nguyên `W` ô cân quanh nó. Với vai sau ô nóng, `W = 5` và $\ell = (0, 0, 5, 4, 4, 4, 4)$: ô `5` trung bình `2.6`, ô giữa vai trung bình `4.2` và là đỉnh `C`. Lipschitz nâng ô lân cận của đỉnh đã mượt. Bước đó giữ nguyên ô có $\tilde{\ell}$ lớn nhất.

---

## 3. Intro lấy sàn của thân bài

Sàn `22` là sàn nốt còn kêu, dùng chung. Intro dài của gigue, galop, choro, polca, hemiola, bourrée, fuga, tremolo và etude đang mở ở `22`, thấp hơn sàn wide `36` của chính nó. Intro một hoặc hai ô, và thể loại ngân như andante hay noviembre, không lệch kiểu đó.

Nhánh `return list(centers)` không gây ra việc này. Nhánh đó giữ đường thì thầm từ `27` khi mọi ô đã trên $L$, và nhánh này ở lại. Chỗ lệch là nhánh kia: đường từ `27` chui dưới $L$, rồi đầu đoạn chỉ được nâng tới $L$ của sàn `22`.

$F$ là sàn cửa sổ của ô thân bài đang nối. $L(b) = \max(F, 22) - \min(V - 64)$. Một lần kéo tâm cho cả ô. Nốt intro không kẹp vào $F$ sau phép cộng.

- Gigue `6/8` wide, sáu ô, nốt viết `50`, $F = 36$: $L = 50$. Tâm thân bài `52..55` cao hơn $L$. Ô mở đứng ở tâm `50`. Nốt `50` nghe được là `36`, rồi đường tâm đi lên tâm thân bài.
- Choro wide, bốn ô, chuông `44, 50, 46`: $L = 56$, tâm thân bài `52..55` thấp hơn $L$, cả intro đứng ở tâm thân bài. Ở tâm `52`, chuông nghe được là `32, 38, 34`. Nốt `44` vẫn thấp hơn sàn `4` bậc.
- Andante calm, chuông, band `mf`, tâm `44.6`, $L = 46$: cả 8 ô đứng ở `44.6`. `round(44.6) = 45`, nốt `44` là `25` trên mọi ô. Dãy `22, 22, 23, …, 25` không còn.
- Outro dùng cùng $L$. Điệu sàn `36` không còn xuống `23`.

Chuông viết `44` ở đáy thủy triều vẫn thấp hơn sàn `4` bậc. Ô toàn nốt viết `50` hết lệch: tâm mở `50`, nốt nghe `36`. Intro Sor của galop có nốt `_PP` = `46` trong cùng ô. Wide thì $L = 54$. Tâm thân bài `52` hoặc `53` thấp hơn $L$, cả intro đứng ở tâm đó, và nốt `46` nghe được là `34` hoặc `35`, vẫn dưới sàn `36`. Stab `70 / 66 / 62` gán sau bộ lọc.
