# Audit P1: trim trần của `_written_deviations`

> **Trạng thái**: đã đo ngày 2026-11-03 trên `main` trước bản sửa. Kết luận: P1 chỉ được trim **đáy**; `d_hi` phải giữ theo profile. Bản sửa nằm trong `_make_wave`.

## 1. Câu hỏi

P1 (`_written_deviations`) đo phân vị 1%/99% của `V_written - 64` theo wave row rồi thay `d_lo/d_hi` của profile. Việc này có thể làm `c_hi = v_ceil - d_hi` dâng lên. Câu hỏi: nó ảnh hưởng những pattern nào, và có phải chỉ bass không?

## 2. Cách đo

A/B trên cùng một movement:

- **Before**: code trước bản sửa, P1 trim cả `d_lo` và `d_hi`. Tái lập bằng `scripts/p1_audit.py <out> --mode before`.
- **Baseline**: `_written_deviations` trả `{}`, tức dùng `d_lo/d_hi` gốc của profile.
- Sau bản sửa, chạy lại A/B với **Baseline**: phần trần phải trùng baseline, phần đáy chỉ khác ở các row có `d_lo` được trim.
- `humanize=False` để cô lập sóng; sau đó so từng nốt theo `(part, bar, beat, midi)`.
- Ghi `c_lo/c_hi` của từng `_Wave`, và phân vị velocity theo pattern × bè.

Corpus:

| Trục | Giá trị |
|---|---|
| Phiên | `AAA 1M`, `ACB 1M`, `VNM 1W`, `VCB 3M` |
| Ensemble | `classic`, `bach`, `barrios`, `villa`, `brouwer`, `torroba` |
| Movement | tất cả movement của mỗi phiên |

Tổng: 4 phiên × 6 ensemble = 24 tổ hợp, 38 wave row.

## 3. Kết quả

### 3.1. Chỉ hai pattern bị trim trần

| Pattern | Số wave | Δc_hi trung bình | Δc_hi lớn nhất |
|---|---:|---:|---:|
| `tremolo` | 8 | **+2,50** | **+4,00** |
| `etude11` | 9 | **+1,00** | **+1,00** |
| 28 pattern còn lại | — | 0,00 | 0,00 |

`d_hi` đo được:

| Row | Số mẫu | `d_lo` median | `d_hi` median | Mẫu có `d_hi < 8` |
|---|---:|---:|---:|---:|
| `tremolo` | 4 | -18 | **+6** | **4/4** |
| `etude11` | 3 | -17 | **+7** | **3/3** |
| 28 row còn lại | — | — | ≥ +8 | 0 |

Vì `_make_wave` lấy `d_hi = min(profile.d_hi, measured)`, chỉ hai row này thực sự hạ trần. Các row khác có `d_hi` đo ≥ 8 nên không đổi.

### 3.2. Không phải chỉ bass dâng

`tremolo`:

| Bè | Số nốt | Δ trung bình | Δ lớn nhất | Mean mới | Mean cũ | Max mới | Max cũ |
|---|---:|---:|---:|---:|---:|---:|---:|
| support | 162 | +2,14 | +4 | 46,3 | 44,2 | 56 | 54 |
| lead | 6048 | +2,10 | +4 | 46,2 | 44,1 | 72 | 70 |
| low | 2973 | +2,09 | +4 | 50,8 | 48,7 | 72 | 72 |

Cả ba bè dùng chung một center và một soft-knee, nên P1 dời đều cả ba. Bass nổi hơn không phải vì nó được cộng riêng, mà vì nó **vốn là bè to nhất** (`low` mean 50,8 so với lead 46,2) và mỗi phách có hai nốt (root + quãng 5) ngân một beat. Trần dâng +4 làm đỉnh thumb từ khoảng 55 lên 59, trong khi lead thường vẫn dưới 50.

`etude11`: cả ba bè +1, không có bè nào bị chặn riêng.

### 3.3. Hệ quả

- `tremolo` là row duy nhất có tide trần tăng đáng kể: trung vị `c_hi` tăng **+2**, lớn nhất **+4** (các wave đo `d_hi ≈ +6`, nên `c_hi` lên `v_ceil - 6`; wave viết hẹp hơn lên `v_ceil - 4`).
- Với Barrios movement 4, `c_hi` hiện tại là 59 thay vì 55; các bar to của thumb tăng +2 đến +4. Đây đúng là hiện tượng “bass tremolo hơi to hơn cần thiết”.
- `etude11` chỉ +1, nghe nhẹ hơn nhưng cùng cơ chế.

## 4. Kết luận và bản sửa

`d_hi` không phải là một phân vị để đo lại theo bản. Nó là **headroom của trần timbre**: `c_hi = v_ceil - d_hi`. Hạ `d_hi` làm mọi nốt thường trong row dâng lên; bè nào chạm trần trước sẽ đổi tương quan. Vì vậy P1 chỉ nên trim **đáy**:

```python
d_lo = max(profile.d_lo, deviation[0])
d_hi = profile.d_hi          # headroom, not a measured tail
```

Hướng này:

- Giữ lợi ích của P1: row viết thấp hơn `-16` vẫn được hạ `c_lo`, tide rộng về phía yên tĩnh.
- Không đẩy bất kỳ bè nào vào trần; `c_hi` trở về `v_ceil - profile.d_hi` cho **mọi** row.
- Không cần ngoại lệ riêng cho `tremolo` hay `_OWN_CONTOUR`; quy tắc là toàn cục, nên pattern mới không tái phạm.
- Nếu một pattern thật sự cần trần thấp hơn, sửa `ceil_calm/ceil_wide` hoặc `d_hi` trong `PROFILES` và nghe lại.

## 5. Bass −2 sau P1

P1 trả đỉnh tremolo về profile, nhưng tai vẫn nghe thumb quá to. Đây là vấn đề cân bằng nhạc, không phải P1: `TREMOLO_BASS_TRIM = 2` hạ `low` và nốt màu `support` hai bậc **sau** `_apply_snaps` / `_apply_stabs` và trước `_sync_ties`. Đặt sau snap vì đỉnh thumb bị `_apply_snaps` ghi lại. Lead fill giữ nguyên, nên giai điệu tách khỏi bass thêm 2 bậc. Chi tiết ở `docs/sonify-barrios-tremolo-dynamics.md`.

Vì vậy nếu chạy `p1_audit.py` trên HEAD, cột note delta của `tremolo` `low`/`support` sẽ là **-2**; đó là trim nhạc có chủ đích, không phải P1. Cột `Δc_hi` vẫn phải là 0.

Nghiệm thu:

- `tests/test_guitar_wave.py::test_p1_keeps_the_profiles_upper_headroom_on_every_row` quét cả 38 row.
- Re-run `backend/scripts/p1_audit.py` sau bản sửa P1 (trước trim bass −2): Δc_hi = 0 ở **cả 30 pattern**; `tremolo` và `etude11` trở về đúng profile (note delta 0,0). Các row có `d_lo` được trim chỉ đổi ở phía yên tĩnh, mean ≤ 0,63 bậc và max 0.
- Barrios movement 4, sau P1: bass bar 42 là `45, 51, 55` (trước sửa `49, 55, 59`); bar 76 là `50, 52, 69, 58, 53` (trước sửa `54, 56, 69, 61, 59`). Sau thêm `TREMOLO_BASS_TRIM`: bar 42 `44, 49, 53`; bar 76 `48, 48, 52, 64, 56, 53`.
