# Musicalize — Tinh chỉnh dạng mixer

> **Trạng thái:** đề xuất, chưa triển khai.
>
> **Liên kết:** [`musicalize-ui-redesign.md`](./musicalize-ui-redesign.md),
> [`sonify-params-profile-plan.md`](./sonify-params-profile-plan.md),
> [`sonify-params-tier-bc-roadmap.md`](./sonify-params-tier-bc-roadmap.md).

Tài liệu này chốt hướng nâng cấp UI cho `TuningPanel` sau khi các knob đã chạy
ổn. Mục tiêu không phải thêm tham số mới, mà làm cho panel dễ đọc và dễ thao tác
hơn trên PC, đồng thời giữ nguyên toàn bộ hành vi lưu profile, hash và URL.

## 1. Hiện trạng

- `TuningPanel` là **một cột rộng 380px** (`DRAWER_WIDTH`).
- Trên PC:
  - `>= 1280px`: drawer đẩy chart sang trái (`RoomFrame` giữ chỗ `DRAWER_WIDTH`).
  - `960–1280px`: drawer nổi dạng modal.
  - Mobile: bottom sheet.
- Mỗi field số là một slider ngang giống nhau: nút `−`, track, nút `+`, vạch
  default và vạch giữa.
- Vạch giữa luôn ở 50% track. Đúng với phần lớn field, nhưng sai với `noise`
  (default `0.1` trên range `0–0.5`) và không diễn tả được “ít hơn / nhiều hơn”
  quanh giá trị hiện tại.
- Các field `0–2` đang hiển thị số thô `0.00–2.00`.
- Nhóm `Guitar` (Bè cao/trung/bass) đang hiện ở mọi thể loại, nhưng backend chỉ
  áp dụng khi `variant === 'guitar'`. Kéo các knob này ở thể loại khác không tạo
  ra thay đổi âm thanh.
- App **không có dữ liệu FFT/level realtime**. Chỉ có `params` và `peaks` của
  timeline. Vì vậy sóng thấp/trung/cao phải là **phổ ước lượng từ tham số**,
  không phải đo audio thật.

## 2. Mục tiêu

1. Trên PC, panel rộng hơn và có cảm giác như một mixer.
2. Bố cục chia khu vực rõ: mixer bè, trình diễn, chất liệu, hòa âm, dáng.
3. Các field `0–1–2` hiển thị như trục âm/dương quanh giá trị hiện tại.
4. Field nào có cách biểu diễn trực quan hơn thì đổi UI, không rập khuôn slider.
5. Không đổi schema, backend, `paramsKey`, hash, URL `p=`, logic profile.

## 3. Panel rộng và cách chia cột

### 3.1 Chiều rộng

```ts
drawerWidth = clamp(560, round(windowWidth * 0.46), 760)
```

| Cửa sổ | Drawer | Ghi chú |
|---|---|---|
| 960 | 560 | overlay |
| 1280 | 589 | overlay |
| 1366 | 628 | overlay |
| 1440 | 662 | push |
| 1920 | 760 | push, đúng gấp đôi hiện tại |

Chỉ push chart khi chart còn đủ rộng:

```ts
push = windowWidth - COLUMN_WIDTH - drawerWidth >= 440
```

- `>= 1440px`: push. Ở 1440 chart còn khoảng 466px.
- `960–1366px`: drawer nổi từ phải, có backdrop. Không bóp chart xuống dưới
  ngưỡng đọc.

### 3.2 Bố cục hai cột

Chia hai cột khi `drawerWidth >= 560`.

```text
┌──────────────────────────────────────────────────────────────┐
│ TINH CHỈNH   PROFILE                 Default · đã sửa    ✕  │
├───────────────────────────────┬──────────────────────────────┤
│ CÂN BẰNG                      │ TRÌNH DIỄN                   │
│  sóng thấp / trung / cao      │  Nhịp        −   0   +        │
│                               │  Người       −   0   +        │
│  ┌───┐  ┌───┐  ┌───┐          │  Hơi thở     −   0   +        │
│  │ ▓ │  │ ▓ │  │ ▓ │          │  Màu         −   0   +        │
│  │ ▓ │  │ ▓ │  │ ▓ │          │                              │
│  └───┘  └───┘  └───┘          │ CHẤT LIỆU                    │
│  Cao    Trung   Bass          │  Tương phản / Nhiễu / Mật độ │
│  Vùng âm   [──●──]            │ HÒA ÂM / DÁNG                │
├───────────────────────────────┴──────────────────────────────┤
│ [Reset]                                             [Lưu]    │
└──────────────────────────────────────────────────────────────┘
```

- Cột trái là khu “mixer”: sóng + 3 fader dọc + `Vùng âm`.
- Cột phải là các nhóm tham số còn lại.
- Mobile vẫn một cột, thứ tự: mixer → trình diễn → chất liệu → hòa âm → dáng.
- Header và footer dính; phần thân cuộn một lần, không lồng nhiều `ScrollView`.

## 4. Các khu vực

### 4.1 Cân bằng

- Sóng low/mid/high co giãn theo chiều rộng cột.
- 3 fader dọc cho `Bè cao / Bè trung / Bè bass`.
- Fader chỉ hiện khi `variant === 'guitar'`.
- Khi không phải Guitar: hiện ghi chú “Bè guitar chỉ mở ở thể loại Guitar”,
  không hiện fader chết.
- Nút `Cân bằng lại` đưa cả ba bè về `0`.
- `Vùng âm` nằm trong cùng khu vì nó điều khiển độ nghiêng của phổ.

### 4.2 Trình diễn

- `Nhịp`, `Người`, `Hơi thở`, `Màu`.

### 4.3 Chất liệu

- `Tương phản`, `Nhiễu`, `Mật độ`.

### 4.4 Hòa âm

- `Màu hòa âm`, `Nhịp hòa âm`.

### 4.5 Dáng

- `Khung`, `Tiết nhịp`.
- Dùng segmented control thay vì các nút rời.

### 4.6 Guitar

- `Kỹ thuật` chỉ hiện khi field thật sự áp dụng.
- Ba bè đã chuyển sang khu Cân bằng.

## 5. Field `0–1–2` thành trục âm/dương

### 5.1 Nguyên tắc

- Field `0–2`: lấy **`1` làm tâm** vì `1` là “bản hiện tại”, `0` và `2` là hai
  cực ít/nhiều.
- Field đã có `0` là tâm (`guitar_high/mid/bass`): giữ `0` làm tâm.
- `noise`: neo `0` vì `0` = không nhiễu.
- Chỉ đổi cách hiển thị. Giá trị gửi backend, hash, URL và profile không đổi.
- Slider tô từ tâm ra, không tô từ trái.
- Vạch default nằm đúng tâm.
- Khi giá trị khác default, hiện nút `↺` nhỏ để trả về mặc định.

### 5.2 Bảng hiển thị

| Field | Tâm | Trái → phải | Hiển thị |
|---|---|---|---|
| `tempo` | `1.0` | Chậm ← 0 → Nhanh | `−8%` / `0` / `+8%`, kèm `88 BPM` |
| `humanize` | `1.0` | Ít ← 0 → Nhiều | `−40%` / `0` / `+40%` |
| `breath` | `1.0` | Đều ← 0 → Cong câu | `−40%` / `0` / `+40%` |
| `color` | `1.0` | Khô ← 0 → Đậm | `−40%` / `0` / `+40%` |
| `dynamics` | `1.0` | Phẳng ← 0 → Tương phản | `−30%` / `0` / `+30%` |
| `density` | `1.0` | Thưa ← 0 → Dày | `−40%` / `0` / `+40%` |
| `harmony` | `1.0` | Tối giản ← 0 → Nhiều màu | `−40%` / `0` / `+40%` |
| `motion` | `1.0` | Giữ lâu ← 0 → Dồn dập | `−40%` / `0` / `+40%` |
| `register` | `1.0` | Thấp/ấm ← 0 → Cao/sáng | `−40%` / `0` / `+40%` |
| `technique` | `1.0` | Dễ ← 0 → Điêu luyện | `−40%` / `0` / `+40%` |
| `guitar_high/mid/bass` | `0` | Nhỏ ← 0 → Lớn | `−3` / `0` / `+3` |
| `noise` | `0` | Sạch → Nhiễu | `0.15%` tuyệt đối |

Ví dụ:

```text
Người        −40%  ·  0.60     ↺
              Ít hơn        Nhiều hơn
```

- `tempo` hiện thêm BPM ngay dưới.
- `humanize` / `breath` hiện cảnh báo mềm ngay trong hàng khi vượt ngưỡng.
- Giá trị thô có thể hiện nhỏ cạnh phần trăm để người quen số cũ vẫn đọc được.

### 5.3 Field đổi UI khác

| Field | UI mới | Lý do |
|---|---|---|
| `frame`, `meter` | segmented control | 4–5 lựa chọn, nhìn là biết đang chọn gì |
| `noise` | thanh neo 0 + `%` tuyệt đối | `0` có nghĩa thật là “sạch” |
| `guitar_*` | fader dọc | đúng ẩn dụ mixer, thấy tương quan ba bè |
| `tempo` | `%` + BPM | nhạc công đọc BPM nhanh hơn hệ số |
| `humanize` / `breath` | signed % + hint | biết ngay đang ít/nhiều hơn bản hiện tại |

## 6. Sóng low/mid/high

### 6.1 Nguồn dữ liệu

Không có FFT realtime. Sóng là **phổ ước lượng từ tham số**, cập nhật ngay khi
kéo:

```text
register 0–2  →  nghiêng phổ thấp ↔ cao
guitar_bass   →  cộng vào dải thấp
guitar_mid    →  cộng vào dải trung
guitar_high   →  cộng vào dải cao
```

Ví dụ:

```ts
low  = 0.55 - (register - 1) * 0.30 + guitar_bass / 12 * 0.22
mid  = 0.55                            + guitar_mid  / 12 * 0.22
high = 0.55 + (register - 1) * 0.30 + guitar_high / 12 * 0.22
```

Clamp `0.08–0.95`.

### 6.2 Cách vẽ

- Đường cong mượt qua 3 điểm, tô gradient magenta `palette.sound`.
- 3 nhãn `THẤP / TRUNG / CAO`.
- Vạch nền mảnh, không dùng màu nhấn thứ tư.
- Ghi rõ dưới card: **“Phổ ước lượng từ tham số, không phải phân tích audio.”**
- Không dùng `peaks` của timeline; không đụng rule “peaks chỉ nằm trên timeline”.

Nếu sau này muốn sóng thật, cần Web Audio `AnalyserNode`/FFT. Đó là việc riêng,
không làm trong đợt UI này.

## 7. Kỹ thuật

### 7.1 File dự kiến

| File | Việc |
|---|---|
| `src/musicalize/TuningPanel.tsx` | layout 2 cột, fader dọc, slider bipolar, segmented control |
| `src/musicalize/TuningSpectrum.tsx` | sóng low/mid/high bằng `react-native-svg` |
| `src/musicalize/tuningDisplay.ts` | helper thuần: tâm field, text hiển thị, spectrum levels, drawer width |
| `src/musicalize/tuningDisplay.test.ts` | test helper |
| `src/musicalize/RoomFrame.tsx` | dùng drawer width/push động |
| `package.json` | thêm test mới vào `test:musicalize` |

### 7.2 Không đổi

- Backend.
- `paramsSchema.generated.ts`.
- `paramsKey`, hash, URL `p=`.
- Logic lưu/ chọn/ xoá profile.
- `liveSynth.ts`, `seek.ts`, `program.ts`, `recapCursor.ts`.

### 7.3 Helper thuần

`tuningDisplay.ts` nên có:

- `fieldCenter(field)` → giá trị tâm.
- `anchorRatio(field)` → vị trí tâm trên track.
- `paramDisplay(field, value)` → `{ primary, secondary, negativeLabel, positiveLabel }`.
- `spectrumLevels(params, variant)` → `[low, mid, high]`.
- `drawerWidthFor(windowWidth)`.
- `drawerPushes(windowWidth)`.

Test tối thiểu:

- Mọi field `0–2` có tâm `1`; `guitar_*` có tâm `0`; `noise` neo `0`.
- Text `tempo`, `guitar_*`, `noise` đúng dấu và đơn vị.
- `spectrumLevels` ở default, ở hai cực `register`, và khi guitar offset bị clamp.
- `drawerWidthFor` / `drawerPushes` ở các mốc 960, 1280, 1440, 1920.

## 8. Rủi ro

1. **Fader dọc vs ScrollView**: cần `PanResponder` capture đúng để kéo fader không
   cuộn panel. Test trên web và native.
2. **Ngưỡng push**: hiện `>=1280` đã push. Panel rộng gấp đôi khiến chart quá hẹp
   ở 1280; đề xuất `>=1440` mới push, nhỏ hơn dùng overlay.
3. **Guitar đang hiện sai thể loại**: ẩn fader khi không phải Guitar. Nếu muốn
   triệt để, thêm `appliesTo: ['guitar']` cho 3 field trong backend ở việc riêng.
4. **Sóng là ước lượng**: phải ghi chú rõ để không gây hiểu nhầm là phân tích audio.
5. **A11y**: fader dọc phải là `adjustable`, có `accessibilityValue`, action
   increment/decrement, và hỗ trợ phím lên/xuống/Home/End trên web.

## 9. Thứ tự triển khai

1. `tuningDisplay.ts` + test.
2. `TuningSpectrum.tsx`.
3. Layout 2 cột + drawer width động.
4. Fader dọc + slider bipolar + segmented control.
5. Rà 960 / 1280 / 1440 / 1920, web + native.
6. Chạy `npm run test:musicalize`.

## 10. Tiêu chí xong

- Ở 1920px, panel rộng 760px, hai cột, chart vẫn dùng được.
- Ở 1280px, panel nổi 589px, không bóp chart xuống dưới 440px.
- Kéo `Bè cao/trung/bass` thấy fill từ tâm và sóng đổi tương ứng.
- Các field `0–2` hiện `−% / 0 / +%`; `noise` hiện `%` tuyệt đối.
- Không có slider guitar chết ở thể loại không phải Guitar.
- `Reset` / `Lưu` vẫn hoạt động như cũ.
- Không đổi hash, URL hay dữ liệu profile đã lưu.
