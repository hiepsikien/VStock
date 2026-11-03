# Kế hoạch mở rộng Shape Dynamics cho Guitar

> **Trạng thái**: P0–P5 đã vào `main`; P6 (in dynamics) chưa. P7 đã xong phần cache guitar và bucket `humanize._pairs` (PR #133); phần `lipschitz` O(n) đã bỏ vì đổi kết quả float. Các việc còn lại nằm ở [`docs/sonify-guitar-shape-dynamics-backlog.md`](./sonify-guitar-shape-dynamics-backlog.md).
>
> **Liên kết**: [`docs/sonify-guitar-shape-dynamics-backlog.md`](./sonify-guitar-shape-dynamics-backlog.md), [`docs/sonify-guitar-dynamics-wave-plan.md`](./sonify-guitar-dynamics-wave-plan.md), [`docs/sonify-guitar-phrase-coverage-plan.md`](./sonify-guitar-phrase-coverage-plan.md), [`docs/sonify-guitar-scale-dynamics-plan.md`](./sonify-guitar-scale-dynamics-plan.md), [`docs/sonify-barrios-tremolo-dynamics.md`](./sonify-barrios-tremolo-dynamics.md), [`docs/sonify-symphony-dynamics.md`](./sonify-symphony-dynamics.md).
>
> **Mục tiêu**: tăng biên độ volume cảm nhận được trên guitar mà vẫn giữ nguyên cấu trúc âm nhạc — within-bar interval, thứ tự bè, accent, tremolo, etude arch, hairpin, seam giữa section.

---

## 0. Trạng thái implement

| Mục | Trạng thái | Ghi chú |
|---|---|---|
| **P0** | đã xong | `MIN_TIDE = 8`; `window_for` chỉ hạ floor, không xuống dưới `SPEECH = 22`. Pedal `F` giữ floor **trước** P0. |
| **P1** | đã sửa | `_written_deviations` đo 1%/99% theo wave row; cần ≥ 24 attack mới trim. `_make_wave` chỉ trim **đáy** (`d_lo`); `d_hi` giữ profile vì là headroom timbre, không phải phân vị runtime. `MAX_TIDE = 16` chặn tide. Audit: [`sonify-guitar-p1-tide-audit.md`](./sonify-guitar-p1-tide-audit.md). |
| **P2** | đã xong | `soft_ceiling` exponential knee 3 bậc, áp cho cả body và pedal |
| **P3** | đã xong | `_section_anchor` (beta 4, cap ±5, median chỉ trên body) + `_limit_body_seams` bước 4 xuyên section/row |
| **P4** | đã xong | `_phrase_breath` nằm trong `C(b)`, clamp **một chiều lên** ở `c_hi` (không kéo center xuống); bar có eighth `relaxed` bị skip; `_shape_dynamics` thành seam no-op |
| **P5** | đã xong | `_make_wave` thu `W` về độ dài section, giữ lẻ |
| **P6** | chưa | score vẫn velocity-only, chỉ in `mp` ở ô 0 |
| **P7** | một phần | cache `phrase_at`/`_bar_pattern`/`_pedal_regions` và bucket `humanize._pairs` (PR #133); `lipschitz` giữ direct max vì hai pass làm lệch float 1 ULP |

Các test cũ có assertion số tuyệt đối đã được đổi sang bất biến hoặc giá trị mới:

- `tests/test_guitar_wave.py`: 30 test, gồm test mới cho `soft_ceiling`, `phrase_breath`, `section_anchor`, `_limit_steps`, `_written_deviations` (guard 24), `MAX_TIDE`, bar `relaxed`, body-only median, breath không kéo center xuống, và `test_p1_keeps_the_profiles_upper_headroom_on_every_row` (quét cả 38 row).
- `tests/test_sonify_guitar.py`, `tests/test_sonify_guitar_torroba.py`, `tests/test_sonify_guitar_scale_passages.py`: cập nhật các chỗ dựa vào extra cũ hoặc clamp cứng, re-pin giá trị mới thay vì nới thành bất đẳng thức.
- Toàn bộ backend trên bản merge `main` sau PR #133: **827 passed**.

### 0.1. Khác với bản đề xuất ban đầu

- **P0** không viết lại bảng `PROFILES`. `window_for` giữ floor/ceil gốc và chỉ hạ floor khi cần đủ `MIN_TIDE`. Như vậy mọi row cũ vẫn còn làm mốc, và `SPEECH` là chặn dưới. `pedal_floor` giữ floor trước P0 để `L` của intro/outro không tụt theo body tide.
- **P1** đo runtime theo **wave row** của từng bản, không hardcode bảng đo, nhưng chỉ áp dụng cho **đáy**. `d_hi` của profile là headroom tới trần timbre: hạ nó làm mọi nốt thường trong row dâng lên, và bè nào chạm trần trước sẽ đổi tương quan với các bè còn lại. Audit 4 phiên × 6 ensemble = 24 tổ hợp (`docs/sonify-guitar-p1-tide-audit.md`) cho thấy chỉ `tremolo` và `etude11` có `d_hi` đo dưới 8, với `c_hi` tăng tới +4; mọi row khác không đổi. Ngưỡng mẫu 24 attack để fixture nhỏ không tự thu hẹp window. `MAX_TIDE` là guard cho trường hợp trim mở hết cửa sổ, không phải nguồn tide chính.
- **P2** áp cho cả pedal, không chỉ body. Nếu pedal dùng clamp cứng `min(63, raw)` trong khi body dùng soft-knee, seam body→outro lệch 1 bậc.
- **P3** anchor bị kẹp trong hard note bounds (`v_floor - d_lo`, `v_ceil - d_hi`), và step limit chạy trên từng đoạn body liền nhau, không chỉ trong một `_Wave`. Median của anchor chỉ tính bar body, không tính pedal/frame. `_limit_steps` là **minorant** (hạ đỉnh), không phải majorant; đây là chủ ý để không tự nâng bar yên tĩnh lên.
- **P4** `_shape_dynamics` trở thành seam no-op; `_phrase_breath` đọc câu tại **đầu ô**, không theo từng eighth. Đây là lựa chọn có chủ đích: `C` là một số cho cả ô, nên breath cũng phải một số cho cả ô. Câu mở giữa ô vẫn được xử lý bởi bug 0.4 ở PR #124 (per-eighth cho `_note_velocity`), không phải bởi breath. Breath chỉ đẩy center **lên**, clamp ở `c_hi`; không kéo center xuống khi anchor đã vượt `c_hi` (MAX_TIDE active). Bar có eighth `relaxed` bị skip để không shape hai lần.
- **P5** `W = min(profile.smooth, 2*floor((len-1)/2)+1)`. Với section 7 ô, cantabile dùng `W = 7` thay vì 9; đỉnh smoothed có thể lệch một ô so với bảng cũ.

### 0.2. Kết quả đo trên `VNM 1W` movement 0 (Bach)

Cùng dữ liệu cache, so `origin/main` (`d0385c0`) với bản đã merge ở PR #125 sau khi tách pedal floor, body median, và clamp breath:

| Metric | Trước | Sau |
|---|---:|---:|
| `C(b)` body, p90 − p10 | **5.06** | **7.00** |
| Số tâm `C` nguyên khác nhau | **10** | **13** |
| `C` min..max | 44..53 | 41..53 |
| Lead bar-mean, p90 − p10 | 12.00 | 13.30 |

Diễn giải: biên độ macro tăng khoảng **38%**, số mức nghe được tăng **30%**; lead bar-mean tăng ít hơn vì arch 12 bậc viết sẵn vẫn chi phối. Đây là mức gần target 8–12 của P0; các pattern có floor thấp hơn (noviembre, cantabile) bị `SPEECH` chặn nên tide tối đa 6–8.

Lưu ý metric: trên movement này, `c_hi - c_lo` của **từng section** là **8.0** cho cả 152 bar. Con số p90−p10 = 7.0 là đo **toàn piece**, nên thấp hơn vì các section nằm ở mức tuyệt đối khác nhau. Target 8–12 của plan là per-section, không phải per-piece. `MIN_TIDE = 8` được giữ thay vì tăng theo thể loại vì các row floor thấp đã chạm `SPEECH`; tăng nữa sẽ làm nốt trầm mất tiếng.

---

## 1. Chẩn đoán

> Mục 1–3 giữ nguyên chẩn đoán ban đầu. Code hiện tại đã đổi theo mục 0: `_shape_dynamics` không còn cộng extra, breath nằm trong `C(b)`, và `apply_guitar_wave` có thêm anchor/seam/soft-knee.

### 1.1. Cách chạy hiện tại

Tầng dynamics của guitar là hai bước nối tiếp trong `guitar_patterns.render_patterned_voices`:

```text
_shape_dynamics()                    guitar_patterns.py:4203
  └── cộng extra của câu: round(4 * swell) = 0..+4
      Bỏ qua pedal, etude1, etude11, tremolo, protected, relaxed.

apply_guitar_wave()                  guitar_wave.py:1188
  ├── resolve_bar_volumes()          volume mỗi ô, fallback band
  ├── _make_wave()                   log → trung bình W → min-max section → Lipschitz
  ├── _apply_affine()                V = round(C) + (V_written - 64)
  ├── _apply_snaps()                 ghi đè 66..76 cho vài cú được chọn
  └── _sync_ties()
```

Các hằng số quyết định biên độ:

```text
d_lo = -16, d_hi = +8     # dải lệch viết sẵn mà bộ lọc giữ
DEVIATION = 24
STEP = 4                  # bước tối đa giữa hai ô
WARM_LIMIT = 63           # trần ấm của body
snap = 66..76             # lớp ép dây, rất hiếm
```

Cửa sổ genre và tide suy ra như sau:

```text
C_lo = floor - d_lo
C_hi = ceil  - d_hi
tide = C_hi - C_lo = (ceil - floor) - 24
```

### 1.2. Số đo hiện tại

| Pattern (calm) | floor..ceil | C_lo..C_hi | Tide |
|---|---:|---:|---:|
| Bach sarabande | 28..56 | 44..48 | **4** |
| Cantabile | 26..54 | 42..46 | **4** |
| Brouwer noviembre | 24..52 | 40..44 | **4** |
| Barrios andante | 26..54 | 42..46 | **4** |
| Torroba castillo | 34..58 | 42..50 | **8** |
| Torroba fandanguillo | 40..63 | 47.7..55.3 | **7.7** |

Hai quan sát quan trọng:

1. **Torroba đang động hơn hẳn** chỉ vì profile dùng `d_lo = -8` thay vì `-16`. Các ensemble khác đang dành gần như toàn bộ cửa sổ cho phần vi mô chưa dùng hết.
2. **`alpha_warm` từ calm → wide thường nâng cả floor lẫn ceil.** Ví dụ Bach sarabande `28..56 → 34..62`: cả khối dịch lên 6 bậc, nhưng tide vẫn là 4. Cơ chế "wide" hiện tại làm section **to hơn**, không làm section **rộng hơn**.

### 1.3. Lớp nghe thực tế

- `musicxml._guitar_part` (`musicxml.py:1221`) **không in `score.dynamics`**.
- Nó chỉ in `MELODY_DYNAMIC` (`mp`) ở ô 0 (`musicxml.py:1243`), và với Barrios một `mp` mỗi bè (`musicxml.py:1286`).
- Vì vậy tai người nghe chỉ có **velocity**, không có lớp chữ p/mp/mf/f hỗ trợ.

Hệ quả: mọi cải thiện volume phải nằm trong velocity, hoặc phải bật lại printed dynamics một cách có kiểm soát và có test playback.

### 1.4. Kết luận

**Cấu trúc: 9/10. Biểu cảm volume: khoảng 4/10.**

- Tide 3–5 bậc MIDI trên nylon chỉ vào cỡ **~0,5–0,8 dB** (theo bậc độ lớn đo trong `docs/sonify-symphony-dynamics.md`; guitar có thể khác nhưng cùng bậc). Ngưỡng nghe trong bản nhiều bè khoảng **1 dB**.
- Trần `V_ceil ≤ 63` + `min(v_ceil, raw)` làm phẳng đúng chỗ cao trào: nốt viết 72/76/80 dễ dồn về cùng một số.
- Min-max theo từng section xóa mức tuyệt đối; không có anchor toàn bài.
- Snap `66..76` quá hiếm để tạo thành một **vùng f**; nó chỉ là vài nốt lẻ.

---

## 2. Điểm mạnh cần giữ

1. **Affine là abstraction đúng.** `V = round(C) + (V_written - 64)` giữ nguyên hiệu MIDI trong ô, kể cả khi `C` có đuôi `.5`. Đây là điều kiện then chốt để không phá cấu trúc.
2. **Tách macro và micro rất kỷ luật.** Sóng chỉ dời cả khối; pattern/accent/tremolo/etude vẫn là micro viết sẵn. Band không bị cộng hai lần.
3. **Log + cửa sổ W theo thể loại.** `smooth_ell` làm phẳng nhiễu; `W = 3/5/9` cho điệu / câu chạy / câu ngân hợp lý về mặt âm nhạc.
4. **Chặn bước Lipschitz 4 bậc.** Khi tide đủ lớn, nó tránh cú nhảy cả khối tại vạch nhịp.
5. **Intro/outro có đường `L` và speech floor 22.** Không đẩy nốt xuống dưới mức còn nghe, không kẹp từng nốt vào `F`.
6. **Snap có ngân sách.** Không biến mọi nốt thành accent; giữ được sự quý hiếm của lớp ép dây.
7. **Test bất biến rất tốt.** Các invariant về within-bar difference, seam, pedal speech, snap budget được ghi rõ trong `test_guitar_wave.py`.

---

## 3. Điểm yếu

### 3.1. Cao

1. **Tide 3–5 bậc là quá nhỏ.** Đây là yếu tố số một. Với phần lớn profile, `ceil - floor` gần như bị ăn hết bởi `d_lo = -16`.
2. **`alpha_warm` dịch cửa sổ thay vì mở rộng cửa sổ.** "Wide" nên là tăng range, không chỉ tăng level.
3. **Trần `≤63` + clamp làm phẳng cao trào.** Nốt viết trên `d_hi` dồn về cùng một số; càng lên đỉnh càng mất tương phản.
4. **Min-max theo section xóa mức tuyệt đối.** Section to và section nhỏ có thể có cùng độ gợn; thiếu đường cong lớn xuyên section.
5. **Không khống chế liên tục giữa các section/row.** Mỗi `_Wave` được chuẩn hóa riêng; Lipschitz chỉ chạy bên trong wave. Seam có thể nhảy quá 4 bậc.

### 3.2. Trung bình

6. **`W = 9` trên section ngắn + reflection.** Section 2–3 ô gần như phẳng; reflection có thể tạo đỉnh giả ở biên.
7. **Lipschitz vô hiệu khi tide ≤ 4.** `delta_U = 4 / tide ≥ 1`, nên C có thể nhảy từ đáy lên đỉnh ngay một vạch.
8. **`_shape_dynamics` bỏ câu phẳng và chỉ +0..+4.** `phrase_at()` yêu cầu `phrase.rise > 0`; câu phẳng không có arch. Coverage hiện tại: `danza` 69%, `preludio`/`torroba_tremolo` 76%, `bach_prelude` 67%.
9. **Phrase extra có thể phá within-bar interval.** Extra cộng theo event/eighth, không theo ô, và bỏ qua `relaxed`/`protected`. Trừ các pattern trong `_WHOLE_BAR_EXTRA`, hai nốt cùng ô có thể nhận extra khác nhau.
10. **Snap quá hiếm để tạo "vùng f".** Ngân sách `0.045 × số attack`, tối đa 4 unit/section.

### 3.3. Thấp, nhưng đáng sửa

11. **Bậc 64/65 là "vách đá".** `humanize._clamp_guitar` (`humanize.py:292`) buộc nốt viết `≤64` ở `≤64`, nốt viết `>64` vào `≥69`. Một cặp 64/65 trong cùng ô có thể thành 64/69 — mất 5 bậc.
12. **DFI có thể chấm sai lớp dynamics.** `dfi._dynamic_gain` (`dfi.py:662`) giả định chữ dynamics được phát, nhưng `_guitar_part` chỉ in `mp`. Cần xác nhận lại metric trước khi dùng DFI để đánh giá guitar.
13. **Hiệu năng.** `phrase_at()` quét tuyến tính cho từng event; `_bar_pattern` gọi 2 lần/event; `_pedal_regions` tính 2 lần; `lipschitz` là O(n²).

---

## 4. Mô hình đề xuất

Giữ đúng tinh thần hiện tại, chỉ tách ba thành phần:

```text
C(b) = anchor(section) + tide(volume) + breath(phrase)
V    = soft_clip( round(C(b)) + (V_written - 64), ceiling )
```

Trong đó:

- **`anchor`**: section này to/nhỏ hơn toàn bài bao nhiêu.
- **`tide`**: đường cong volume bên trong section.
- **`breath`**: vòng cung câu nhạc, **một số cho cả ô**, không cộng từng nốt.
- **`soft_clip`**: giữ được vài bậc cuối thay vì dồn hết về trần.

Tất cả đều là hàm của ô, nên **mọi nốt trong ô vẫn nhận cùng một shift**; within-bar interval được bảo toàn tuyệt đối.

---

## 5. Kế hoạch sửa

### P0 — Tái phân bổ cửa sổ, đừng nâng floor khi "wide"

Đây là thay đổi ít rủi ro nhất và cho kết quả lớn nhất.

- Thiết kế lại profile theo **range trước, floor sau**:

```text
range = ceil - floor - (d_hi - d_lo)
floor = ceil - range - (d_hi - d_lo)
```

- Với Bach sarabande, thay vì `calm 28..56`, `wide 34..62` (tide 4), dùng `wide 28..62` (tide 10). Đáy vẫn là 44, đỉnh lên 54; **không thêm nốt mới, không đổi timbre trần**.
- Hoặc thêm trường `range_calm/range_wide` vào `PatternWaveProfile`, rồi suy `floor` từ `ceil` và `range`.
- Đặt **tide tối thiểu 6–8 bậc** cho mọi body section, kể cả ngày volume phẳng.

Lưu ý: hạ floor của wide sẽ hạ luôn `F` dùng cho intro/outro `L`. Nên tách `F` của pedal khỏi `v_floor` của body, hoặc giữ `F` ở mức cũ.

### P1 — Đo `d_lo` thực tế theo pattern; giữ `d_hi` của profile

- Sau `_shape_dynamics`, đo phân vị 1%/99% của `V_written - 64` **trên cả ba bè** cho từng pattern. Phân vị 99% vẫn được ghi để chẩn đoán, nhưng không áp vào trần.
- Chỉ dùng phân vị **1%** để đặt `d_lo`, thay vì `-16` cố định. `d_hi` giữ nguyên giá trị trong `PROFILES`.
- `d_hi` không phải là một phân vị để đo lại theo bản: nó là **headroom của trần timbre**. Hạ `d_hi` làm `c_hi = v_ceil - d_hi` dâng lên, kéo mọi nốt thường trong row lên cùng một center. Bè nào có velocity viết cao hơn sẽ chạm `v_ceil` / soft-knee trước, nên tương quan giữa các bè đổi dù phép dời là affine.
- Ví dụ pattern chỉ viết thấp nhất 56 (`d=-8`): đặt `d_lo=-8`; `c_lo` hạ xuống, tide rộng thêm 8 bậc về phía yên tĩnh, còn `c_hi` không đổi. Đây là hướng mở tide an toàn vì không đẩy bè nào vào trần.
- Nếu một pattern thật sự cần trần thấp hơn, phải sửa `ceil_calm/ceil_wide` hoặc `d_hi` trong `PROFILES` và nghe lại; không suy ra từ dữ liệu của một phiên.
- Audit rộng: [`sonify-guitar-p1-tide-audit.md`](./sonify-guitar-p1-tide-audit.md). Trong 4 phiên × 6 ensemble (24 tổ hợp), chỉ `tremolo` (Δc_hi trung bình +2,5, tối đa +4) và `etude11` (+1) bị ảnh hưởng; 28 pattern còn lại có `d_hi` đo ≥ 8 nên P1 không đổi trần.
- Nốt hiếm nằm ngoài khoảng đo **đáy** sẽ bị kẹp; chấp nhận nếu tỷ lệ dưới ~0,5%.

### P2 — Soft-knee ở trần

Thay `min(v_ceil, raw)` bằng một hàm monotone:

```python
def soft_ceiling(raw: int, ceil: int, knee: int | None = None) -> int:
    knee = ceil - 3 if knee is None else knee
    if raw <= knee:
        return raw
    span = ceil - knee
    return knee + round(span * (1 - math.exp(-(raw - knee) / span)))
```

- Giữ được ít nhất 3 mức trong 6 bậc cuối, thay vì tất cả về 63.
- Không đổi thứ tự, không đổi timbre trần, nhưng cứu được đỉnh của câu.
- Test: monotone; hiệu preserved cho `raw <= knee`; không có hai nốt khác nhau bị dồn về cùng số nếu còn chỗ.

### P3 — Anchor toàn bài + seam liên tục

- Giữ min-max trong section cho **shape**, nhưng thêm offset tuyệt đối:

```text
anchor(section) = clamp(beta * (log_vol_section - log_vol_piece), -A, +A)
```

- `A` khoảng 4–6 bậc. Section to hơn sẽ thực sự to hơn, dù tỷ lệ nội bộ nhỏ.
- Buộc `|C(b) - C(b-1)| ≤ 4` **xuyên seam**, không chỉ trong từng wave. Có thể chạy một pass Lipschitz toàn bài sau khi ghép các wave, hoặc truyền tâm cuối của section trước làm điều kiện đầu của section sau.
- Với `trio/bridge`, thay vì nhân `alpha_warm` cho 0.5 (thu hẹp range), hãy hạ `anchor` và giữ range — đoạn contrast vẫn có không gian thở.

### P4 — Hợp nhất lớp phrase

Hiện có ba cơ chế chồng nhau: `_note_velocity` viết arch, `_shape_dynamics` cộng extra, `phrase_curve` chỉ để xếp hạng snap. Nên:

- Một hàm `phrase_breath(phrase, bar)` duy nhất, trả 0..1, **dùng cho câu phẳng lẫn câu có rise**. Đưa nó vào `C(b)` như một số hạng, không cộng vào từng nốt.
- Pattern nào đã tự viết contour (etude, tremolo, preludio) thì **không nhận breath lần nữa**; pattern còn lại nhận.
- Điều này sửa luôn `danza`/`preludio`/`bach_prelude` mà không cần mở `_shape_dynamics` cho từng event.

### P5 — W thích ứng và bỏ reflection ở section ngắn

```python
width = min(profile.smooth, max(1, 2 * ((len(levels) - 1) // 2) + 1))
```

- Section ngắn hơn `W` thì dùng fit tuyến tính cục bộ hoặc không làm mượt, thay vì reflection.
- Reflection hiện tại lặp biên, có thể tạo peak giả; với section 2–3 ô, nó làm phẳng gần như toàn bộ.

### P6 — Nếu muốn score "nói" volume

Hiện `_guitar_part` chỉ in `mp`. Có hai hướng:

- **Giữ velocity-only** (như hiện tại) và mở rộng velocity như P0–P3. Đây là hướng an toàn, không sợ MuseScore nhân đôi dynamics.
- **In dynamics theo section** (p/mp/mf/f) tại đầu section, lấy từ **tâm C thực tế** chứ không phải band window cũ. Phải test playback vì MuseScore có thể reset/scale note velocity khi gặp chữ mới. Nếu in, nên in rất thưa (1 chữ/section) và dùng wedge cho vòng cung, tránh in từng ô.

### P7 — Dọn hiệu năng (không đổi âm nhạc)

Đã làm trong PR #133:

- Cache `phrase_at` theo bar/eighth, `_bar_pattern` theo bar, và `_pedal_regions` một lần mỗi render trên `_Ctx`.
- `humanize._pairs` bucket theo start bar thay vì quét toàn bộ cặp; pair set và thứ tự không đổi.
- Đo trên score 152 bar (5 phiên 32/32/32/32/24, median 7 lần): render guitar/barrios **599.4 → 596.7 ms** (cache guitar dưới 1%); `humanize()` guitar/barrios **88.2 → 13.6 ms**, symphony **27.3 → 12.5 ms**, minimalist **489.8 → 121.5 ms**; suite 4 movement guitar **1055.1 → 1045.3 ms**.

Không làm:

- `lipschitz` hai pass O(n). Hai pass chỉ giữ được một trong các term nên có thể lệch **1 ULP** so với direct max; với input dạng band-derived, 6/30.000 mảng lệch và có thể vi phạm ràng buộc chênh lệch kề. Đo render cho thấy chỉ tiết kiệm **~0.01–0.02 ms/render** (5–9 lần gọi, section ~30 bar), nên giữ direct max. Test `test_lipschitz_matches_the_direct_cone_envelope` pin hợp đồng này.

---

## 6. Đo lường và test

### 6.1. Metric trước/sau

| Metric | Mục tiêu |
|---|---|
| `p90(heard) - p10(heard)` trên lead attack, mỗi section | **≥ 8–12 bậc** body, **≥ 12–16** ở cao trào |
| Số tâm `C` nguyên khác nhau / section | **≥ 8** thay vì 3–5 |
| `max |C(b) - C(b-1)|` xuyên seam | **≤ 4** |
| Tỷ lệ cặp nốt cùng ô giữ đúng hiệu | **100%** cho nốt không bị kẹp |
| Số nốt body < 22 hoặc > 63 (trừ snap/peak window) | **0** |
| `lead > bass > support` sau humanize | **100%** |
| DFI/PAFI guitar | Đo lại sau khi xác nhận `_dynamic_gain` |

### 6.2. Bất biến cần thêm test

1. Với mọi pattern, `tide ≥ 6` ở body.
2. `C` liên tục qua seam giữa hai section/row.
3. Soft-knee monotone và giữ ≥3 mức cuối.
4. Breath là một số cho cả ô, không đổi within-bar interval.
5. Nốt 64 và 65 trong cùng ô vẫn cách nhau 1 sau humanize (nếu writer sinh ra 65).
6. Intro/outro vẫn nối đúng `C` của body và không tụt dưới speech floor.

### 6.3. Nghe A/B

Mỗi thay đổi nghe tối thiểu:

- Một movement Bach có cả calm và wide.
- Một Barrios tremolo (kiểm tra arch trong ô không bị bẹt).
- Một Torroba `castillo` và `fandanguillo` (so với baseline đang 8 bậc).
- Một bản volume phẳng (kiểm tra tide tối thiểu không tạo cảm giác "gợn giả").

---

## 7. Thứ tự thực hiện

1. **P0 + P2 + test + đo** — 1–2 ngày, rủi ro thấp, gần như chắc chắn nghe khác rõ.
2. **P1 (d_lo/d_hi theo pattern)** — đo phân vị, cập nhật bảng, nghe lại từng ensemble.
3. **P3 (anchor + seam)** — thay đổi kiến trúc nhỏ, cần nghe kỹ transition.
4. **P4 (hợp nhất phrase)** — sửa coverage `danza`/`preludio`/`bach_prelude`.
5. **P5, P7** — dọn dẹp.
6. **P6** — quyết định có in dynamics hay không, sau khi nghe và đo.

---

## 8. Việc không làm

- Không thêm accent ngẫu nhiên hoặc tăng velocity từng nốt.
- Không đổi cao độ, duration, slur, pattern, tempo trong đợt này.
- Không đổi trần timbre `WARM_LIMIT` của body (trừ khi P6 được duyệt).
- Không mở `_shape_dynamics` cho pedal hoặc tremolo/etude đã có contour riêng.
- Không in thêm chữ dynamics khi chưa test playback chống nhân đôi.

---

## 9. Câu hỏi cần nghe/duyệt

1. Section "wide" có được phép có đáy thấp bằng section "calm" không? Nếu không, phải chọn giữa **range** và **mức to tuyệt đối**.
2. Có chấp nhận nốt hiếm nằm ngoài `d_lo/d_hi` bị kẹp để đổi lấy tide lớn hơn không? Tỷ lệ tối đa là bao nhiêu?
3. Có muốn một "vùng f" 1–2 ô ở cao trào (66–68) hay chỉ giữ snap lẻ như hiện tại?
4. Score có cần in dynamics để người đọc thấy volume, hay tiếp tục velocity-only?
