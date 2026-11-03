# Backlog — shape dynamics cho guitar

Phần P0–P5 của [shape dynamics](sonify-guitar-shape-dynamics-plan.md) đã vào `main`. Tài liệu này giữ lại những việc **cố ý chưa làm** trong PR đó, kèm điều kiện để được phép làm.

Không có mục nào ở đây là bug. Mỗi mục là một thay đổi hành vi hoặc một quyết định sản phẩm chưa chốt.

## Trạng thái

| # | Việc | Loại | Chặn bởi |
|---|---|---|---|
| 1 | P6 — in dynamics theo section | notation + playback | chưa test MuseScore, chưa chốt score dành cho ai |
| 2 | P7 — cache `phrase_at` / `_bar_pattern` / `_pedal_regions`, `lipschitz` O(n) | hiệu năng | chỉ cần benchmark, không đổi âm nhạc |
| 3 | `MIN_TIDE` theo thể loại | âm nhạc | `SPEECH` chặn ở các row floor thấp |
| 4 | `_limit_steps`: minorant → majorant hoặc projection đối xứng | âm nhạc | chỉ đổi nếu nghe seam bị dìm |
| 5 | Tách `window_for(min_tide=...)` thành `body_window()` / `pedal_window()` | đọc code | không cần cho PR này |
| 6 | Đo lại DFI/PAFI guitar | metric | `_dynamic_gain` đọc `score.dynamics`, guitar không in |
| 7 | Đo per-section thay vì per-piece trong script/CI | đo lường | metric hiện tại gộp cả piece |
| 8 | Review reflection của `smooth_ell` ở section ngắn | âm nhạc | P5 đã rút `W`, nhưng reflection vẫn lặp biên |

---

## 1. P6 — in dynamics theo section

### Hiện tại

`musicxml._guitar_part` chỉ in **một chữ `mp` ở ô 0** (trừ `barrios`). Toàn bộ dynamics nghe được nằm ở `<note dynamics>` từng nốt. `score.dynamics` không được dùng cho guitar.

Hệ quả:

- Người đọc score không thấy đoạn nào to/nhỏ.
- `dfi._dynamic_gain` đọc `score.dynamics` nên metric lệch với tai nghe.

### Việc phải làm trước khi in

1. Chốt score để **nghe** hay để **người chơi đọc**. Nếu chỉ để nghe, velocity-only là đủ và nên sửa DFI thay vì in.
2. Chọn nguồn nhãn: lấy từ **tâm `C(b)` thực tế**, không lấy band window cũ.
3. In rất thưa: một chữ mỗi section, hairpin cho vòng cung dài, không in từng ô.
4. Test playback MuseScore Basic nylon: chữ `<dynamics>` có thể **nhân đôi** với `<note dynamics>`, làm đoạn `p` nhỏ hơn dự kiến hoặc reset velocity.
5. Quyết định in ở biên section hay ở bar có `C` đổi ≥ 2 bậc.

### Nghiệm thu

- A/B một bản Bach và một bản Torroba: không có bar nào lệch quá 2 velocity so với bản không in.
- `score.dynamics` khớp với `C(b)` trung bình từng section.
- Test `_guitar_part` khẳng định số chữ dynamics = số section được in, và không in trùng với `mp` ô 0.
- DFI guitar tính lại trên score mới.

---

## 2. P7 — dọn hiệu năng

Không đổi một nốt nào. Chỉ làm khi có benchmark chứng minh đáng làm, và tách PR riêng.

### Các điểm nóng

| Hàm | Vấn đề |
|---|---|
| `_phrase_at(ctx, eighth)` | duyệt `ctx.phrases` tuyến tính, gọi trong `_phrase_breath`, `_apply_snaps`, `_shape_dynamics` cũ |
| `_bar_pattern(ctx, bar, patterns)` | gọi lại cho cùng bar ở `_written_deviations`, `breath_skip`, `_phrase_breath`, `_apply_snaps` |
| `_pedal_regions(ctx)` | tính lại nhiều lần trong một render |
| `lipschitz()` / `shape_u()` | O(n²): mỗi bar so với toàn bộ bar còn lại |
| `humanize._pairs` | bucket O(n²) toàn bộ nốt |

### Cách làm

- Precompute `phrase_by_bar: dict[int, Phrase]` và `pattern_by_bar: dict[int, str]` một lần mỗi render.
- Tính `_pedal_regions` một lần rồi truyền xuống.
- `lipschitz` hai pass O(n):

  ```python
  for i in range(1, n):
      out[i] = min(out[i], out[i - 1] + step)
  for i in range(n - 2, -1, -1):
      out[i] = min(out[i], out[i + 1] + step)
  ```

- `humanize._pairs` bucket theo `(bar, voice)`.

### Nghiệm thu

- Toàn bộ test hiện có pass **không sửa một assertion nào** (đây là refactor thuần).
- Benchmark trước/sau trên một movement 152 bar và một suite dài; ghi thời gian render.
- Nếu `lipschitz` đổi kết quả dù chỉ một bar, coi là thay đổi hành vi và phải re-pin test riêng.

---

## 3. `MIN_TIDE` theo thể loại

Hiện `MIN_TIDE = 8` cho mọi row, và per-section tide đo được là **8.0** trên cả 152 bar của `VNM 1W` movement 0. Con số per-piece p90−p10 = 7.0 thấp hơn vì các section nằm ở mức tuyệt đối khác nhau.

### Vì sao chưa tăng

`SPEECH = 22` là sàn nghe được. Với row có `ceil` thấp và `d_lo = -16`:

```text
max tide = ceil - SPEECH - (d_hi - d_lo)
```

| Row | ceil | max tide | Ghi chú |
|---|---:|---:|---|
| `noviembre` calm | 52 | **6** | đã chạm `SPEECH`, tăng `MIN_TIDE` vô ích |
| `cantabile` calm | 54 | **8** | đúng bằng `MIN_TIDE` hiện tại |
| `bach_sarabande` calm | 56 | **10** | còn dư 2 bậc |
| `torroba castillo` | 58 | **20** | floor profile 34, không cần hạ sâu |

Tăng `MIN_TIDE` toàn cục sẽ không thêm range cho row thấp, chỉ làm nốt trầm mất tiếng.

### Cách làm nếu muốn

- Thêm `min_tide` vào `PatternWaveProfile`, mặc định 8.
- Chỉ đặt > 8 cho row có `max tide > 8` **sau khi P1 trim**.
- Đo lại từng row trước khi chốt; không đổi toàn bộ cùng lúc.

### Nghiệm thu

- Không nốt body nào < `SPEECH` sau khi đổi.
- Per-section tide của row được đổi tăng thật, không chỉ đổi profile.
- Test khẳng định row `noviembre` vẫn giữ tide 6.

---

## 4. `_limit_steps`: minorant hay majorant

Hiện `_limit_steps` là **minorant**: hàm lớn nhất nằm dưới dữ liệu gốc, bước ≤ `step`.

```text
input:  [40, 50, 40]   step = 4
output: [40, 44, 40]
```

Đỉnh bị hạ, đáy giữ nguyên. Chủ ý: **không tự bịa ra độ to**.

### Khi nào đổi

Chỉ đổi nếu nghe thấy section to bị "dìm" quá ở 1–2 bar sát seam.

| Phương án | Kết quả với `[40, 50, 40]` | Đánh đổi |
|---|---|---|
| minorant (hiện tại) | `[40, 44, 40]` | giữ đáy, mất đỉnh |
| majorant | `[46, 50, 46]` | giữ đỉnh, **nâng bar yên tĩnh** |
| projection đối xứng | mỗi bên dịch một nửa | seam mượt hơn, cả hai đầu đều đổi |
| step lớn hơn (6–8) | ít hạ đỉnh hơn | seam gắt hơn |

### Nghiệm thu

- Đo `max |C(b) − C(b−1)|` xuyên seam vẫn ≤ step.
- Test khẳng định bar yên tĩnh không bị nâng nếu giữ minorant.
- A/B nghe trước khi chốt; đây là quyết định âm nhạc, không phải sửa lỗi.

---

## 5. API `window_for`

`window_for(profile, opened, *, min_tide: bool = True)` khó đọc ở call site. Có thể tách:

```python
def body_window(profile, opened) -> tuple[int, int]: ...
def pedal_window(profile, opened) -> tuple[int, int]: ...
```

Không cần làm trong PR shape dynamics; làm khi có người thứ hai đọc file này.

---

## 6. DFI/PAFI guitar

`dfi._dynamic_gain` đọc `score.dynamics`. Guitar không in dynamic event nào, nên metric có thể lệch với tai nghe sau P0–P5.

Hai hướng, chọn một:

- Sửa DFI để guitar chỉ chấm trên `<note dynamics>`.
- Làm P6 trước, rồi DFI đọc `score.dynamics` như các nhạc cụ khác.

Chưa chốt hướng nào; đừng đổi DFI trước khi có A/B nghe.

---

## 7. Đo lường per-section

Script đo hiện tại báo p90−p10 **toàn piece**. Với shape dynamics, metric đúng là **per-section**: mỗi section có tide riêng, nên gộp cả piece làm con số thấp hơn thực tế (7.0 so với 8.0).

Việc cần làm:

- Thêm mode per-section vào script đo.
- Ghi rõ trong output là per-section hay per-piece.
- Nếu dùng làm CI gate, gate trên per-section vì đó mới là thứ P0–P3 tác động trực tiếp.

---

## 8. Reflection ở section ngắn

P5 đã rút `W` xuống bằng độ dài section (giữ lẻ), nên section 7 bar dùng `W = 7` thay vì 9. Nhưng `smooth_ell` vẫn dùng reflection ở biên, có thể lặp biên và tạo peak giả ở section 2–3 bar.

Chưa đổi vì:

- Section ngắn nhất trong các suite hiện tại đủ dài để reflection không tạo peak rõ.
- Đổi sang fit tuyến tính cục bộ hoặc không mượt sẽ đổi `C` của mọi section ngắn — cần re-pin test.

Chỉ làm khi có một bản thật sự nghe thấy peak giả ở intro/outro ngắn.

---

## Không nằm trong backlog

- **Snap và stab**: `_apply_snaps` / `_apply_stabs` giữ nguyên; snap budget và giá trị `70/66/62` không đổi.
- **Trần timbre** `WARM_LIMIT = 63` giữ nguyên cho body; chỉ mở khi P6 được duyệt.
- **Humanize** và clamp 64/65 không đổi.
- **`_written_deviations` gộp ba bè**: bass thường giữ `d_lo = -16`, trim chủ yếu mở phía trần. Đây là hành vi đã ghi trong docstring, không phải việc còn treo.
