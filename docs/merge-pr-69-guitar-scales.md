# Merge PR 69 vào main

Mở một nhánh từ `main` hiện tại, merge `cursor/guitar-scales-plan-4114` vào, và gỡ ba file conflict bằng cách giữ cả sóng volume lẫn xung giá. PR 70 và PR 72 đã nằm trong nhánh đó, không merge riêng.

## Điểm xuất phát

- `main` đang ở `cf5bfb7`.
- Nhánh scale ở `5b11a97`, tách từ `a2492a1`.
- Merge nháp chỉ conflict ở `backend/app/sonify/render.py`, `guitar.py`, và `guitar_patterns.py`.
- 14 file còn lại tự gộp, gồm `guitar_scales.py`, `guitar_scale_passages.py`, `PriceImpulse`, và toàn bộ test guitar của `main`. `TempoEvent` giữ nguyên.
- File chưa theo dõi `docs/intro-outro.txt` để nguyên, không đưa vào commit.

## Các bước

1. Tạo nhánh mới từ `main`, ví dụ `cursor/merge-guitar-scales-69`. Không commit thẳng lên nhánh cũ của PR 69, vì PR đó đã đóng.
2. `git merge cursor/guitar-scales-plan-4114`. Không rebase 25 commit.
3. Gỡ ba file theo mục dưới. Xong thì không còn marker `<<<<<<<`.
4. Chạy test guitar. Sửa đúng chỗ hairpin bị sóng volume bẹt nếu test đỏ, rồi commit merge.
5. Mở PR mới vào `main`. Không reopen PR 69.

## Gỡ conflict

`render.py` và `guitar.py` giữ cả bốn tham số. `render.py` vẫn tính `bar_volumes` và `section_rel_spans`, đồng thời gọi `detect_price_impulses` một lần trên giá đóng, rồi truyền đủ `bar_volumes`, `section_rel_spans`, `raw_pitches`, `impulses` vào `render_guitar_score`. Chữ ký và `voice_kwargs` trong `guitar.py` nhận cả bốn. Nhánh `if impulses is None` giữ nguyên: chỉ tự dò xung khi người gọi không truyền sẵn.

`guitar_patterns.py` thêm cả hai cặp field vào `_Ctx`, vào chữ ký `render_patterned_voices`, và vào chỗ tạo `_Ctx`. Đường render sau merge đã gọi `apply_scale_passages` và không còn gọi ngân sách 15%. `_allocate_overlays` và `_cap_accents` để nguyên trong file, không xóa trong lần merge này.

Bốn chỗ phải chọn tay:

- `_paint_frames` dùng chữ ký của `main`: `_paint_frames(ctx, patterns, lead, support, low)`. Lời gọi ba tham số của PR 69 bỏ, vì `render_intro` / `render_outro` trên `main` cần pattern cửa.
- `_smooth_boundaries` truyền thêm `scale_eighths`, để không nới texture đúng trên đoạn scale.
- Pickup bass lấy cả hai điều kiện: không đặt trên ô pedal, và không đặt khi móc cuối là nốt đáp scale.

```python
if (
    pattern not in {"etude1", "etude11"}
    and ctx.kind_at.get(bar, "phrase") not in _PEDAL
    and (bar + 1) * ctx.epb - 1 not in protected
):
```

- Sau slur, thứ tự là `clear_scale_slurs`, rồi `_shape_dynamics(..., protected_eighths)` trên mọi bài, rồi `apply_guitar_wave`, rồi in lại hairpin. `_shape_dynamics` giữ thân của `main`: chỉ cộng extra của câu, vì band thuộc sóng volume. Thêm tham số `scale_eighths`. `shape` nhận `voice` và được gọi `shape(lead, "lead")`. Nhánh bỏ qua móc `protected` chỉ áp cho bè cao. Dòng git tự gộp `if voice == "lead"` nằm trong `shape(events)` không có `voice` sẽ `NameError` ở nốt đầu tiên.

## Ba chỗ bổ sung

**`_shape_dynamics`.** Hunk conflict chỉ gồm dòng `def` và câu đầu docstring. Phần thân bên dưới marker là bản git đã trộn: có `protected = scale_eighths` và `if voice == "lead"`, trong khi `shape(events)` không có `voice`. Giữ thân của `main`, thêm `scale_eighths`, và đưa `voice` vào `shape`.

**Test swarm.** `test_sonify_guitar_scale_passages.py` import `_BAND_DELTA`, và auto-merge đã bỏ hằng đó vì `main` thay bằng `_TREMOLO_BAND`. File fail ngay lúc import. Trong `test_framed_swarm_eighths_skip_the_second_band_pass`, dùng hằng cục bộ `old_band_p = -12` cho assert `kinked_if_bare`. Assert đó chỉ chứng minh một lần cộng band trần sẽ làm gãy nốt, không đòi `_shape_dynamics` còn cộng band.

**Hairpin sau sóng.** `apply_guitar_wave` cộng `round(C) - 64` cho cả ô, rồi kẹp trần pattern. Trần sarabande tối đa là 62, nên nốt viết 72 trở lên bị hạ. Bỏ nốt lead khỏi lần kẹp vẫn để sóng dời velocity khi tâm ô khác 64. In lại hairpin sau sóng mới giữ các số của `test_modal_figure_ramps_the_hat_window_and_a_bar_opening_is_not_punched`. Swarm sarabande in lại trước, passage và tier-1 in lại sau, cả hai lấy velocity mở từ lead trước sóng.

Cache: hai nhánh đều ở `RECAP_REVISION = "65"` và `SPAN_REVISION = "51"`, nên auto-merge của `audio.py` giữ số của `main`. Sau khi hairpin và sóng volume cùng nằm trên score, tăng thành `"66"` và `"52"`.

## Kiểm tra

Chạy năm file:

- `backend/tests/test_sonify_guitar.py`
- `backend/tests/test_sonify_guitar_impulses.py`
- `backend/tests/test_sonify_guitar_melody_shift.py`
- `backend/tests/test_sonify_guitar_scale_passages.py`
- `backend/tests/test_guitar_wave.py`

Hairpin được in lại sau `apply_guitar_wave`. Không bỏ nốt lead khỏi lần kẹp của sóng: cách đó vẫn dời velocity khi tâm ô khác 64.
