# Musicalize — Tinh chỉnh dạng mixer

> **Trạng thái:** đã triển khai trong PR #141.
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
  - `960–1279px`: drawer nổi dạng modal trong suốt.
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

1. Trên PC, panel rộng 50–67% màn hình và có cảm giác như một mixer.
2. Bố cục chia khu vực rõ: mixer bè, trình diễn, chất liệu, hòa âm, dáng.
3. Các field `0–1–2` hiển thị như trục âm/dương quanh giá trị hiện tại.
4. Field nào có cách biểu diễn trực quan hơn thì đổi UI, không rập khuôn slider.
5. Không đổi schema, backend, `paramsKey`, hash, URL `p=`, logic profile.

## 3. Panel rộng và cách chia cột

### 3.1 Chiều rộng

Panel chiếm **50–67% chiều rộng viewport**, không full-width. Giữ dạng drawer
phải, nền `panel`, viền trái `hairlineStrong`. Modal hiện tại trong suốt; đợt này
**thêm backdrop tối mới** cho chế độ focus, không phải “đã có sẵn”.

```ts
// clamp(value, min, max)
panelWidthFor(w) = clamp(round(w * 0.60), 640, 1280)
contentWidth = min(panelWidth - 48, 1040)
```

| Cửa sổ | Panel | Tỉ lệ | `contentWidth` | `visibleChart` | Chế độ |
|---|---|---|---|---|---|
| 960 | 640 | 66.7% | 592 | 8 | overlay |
| 1024 | 640 | 62.5% | 592 | 72 | overlay |
| 1280 | 768 | 60.0% | 720 | 200 | overlay |
| 1366 | 820 | 60.0% | 772 | 234 | overlay |
| 1440 | 864 | 60.0% | 816 | 264 | overlay |
| 1879 | 1127 | 60.0% | 1040 | 440 | bắt đầu push |
| 1920 | 1152 | 60.0% | 1040 | 456 | push |
| 2560 | 1280 | 50.0% | 1040 | 968 | push |

Header, status strip, body và footer bọc trong một `contentFrame`:
`maxWidth = 1040 + 2×24 = 1088`, `width: 100%`, `alignSelf: center`.
Padding 24px hai bên nên nội dung thật = **1040px**. Ở 1920 panel 1152px,
contentFrame 1088px, hai bên panel còn 32px đệm; không rộng lê thê.

Định nghĩa:

```ts
chartArea   = windowWidth - COLUMN_WIDTH
visibleChart = chartArea - panelWidth       // overlay che, push co lại: cùng số
push        = visibleChart >= 440
```

**Sửa lập luận cũ:** overlay **không** làm chart rộng hơn push. Nó chỉ tránh
reflow khi mở/đóng. Ở 1280–1440, visible chart chỉ còn 200–264px, không đủ để
tua/đọc chart. Vì vậy:

- `>= ~1879px`: push. Chart còn >=440px, dùng được.
- `960–1878px`: **focus mode**. Panel overlay + backdrop tối; chart bị che gần
  hết và không phải bề mặt thao tác trong lúc panel mở. Có nút `Thu gọn` / `Esc`
  để quay lại chart.
- Nếu sau này bắt buộc chart vẫn dùng được khi panel mở, cần **compact mode**:
  `panelWidth <= chartArea - 440`. Ở 1440, trần là 688px (47.8%); ở 1280 là
  528px (41.3%) — tức phải phá quy tắc 50–67%. Vì vậy compact mode là tuỳ chọn
  riêng, không phải mặc định.

### 3.2 Bố cục một màn hình cho Guitar trên PC

Mục tiêu: ở **viewport** `1366×660`, `1440×800`, `1920×980`, panel Guitar mở ra
là thấy toàn bộ knob, **không phải cuộn**. Dùng `window.innerHeight` (qua
`useWindowDimensions().height`), không dùng chiều cao vật lý của màn hình.

Cấu trúc:

1. **Header dính** gồm tab + profile line. Profile line rời khỏi `TuningTab`
   và lên header để chiều cao body cố định. Dense 64px = tab 40 + profile 20
   + border 4; thoáng 76px = tab 44 + profile 24 + border 4.
2. **Status strip 24px** dưới header: một dòng cảnh báo/ghi chú, ellipsis.
   `Default note`, `hiddenChanged`, server notes gộp vào đây; bấm để mở popover,
   không làm body cao thêm.
3. **Mixer ngang toàn panel**: sóng low/mid/high bên trái, 3 fader dọc bên phải,
   hàng dưới gồm `Vùng âm` + `Màu` + `Đưa 3 bè về 0`. Khi không phải Guitar,
   mixer thu còn ~164/188px thay vì giữ chỗ fader rãnh.
4. **Controls chia cột**:
   - `windowWidth < 1100`: **1 cột** — gồm mobile và cửa sổ hẹp kiểu mobile.
   - `1100–1279` (panel 660–763): 2 cột.
   - `>= 1280` (panel >= 768): 3 cột.
   - `Hòa âm` và `Guitar` dùng chung một header `Hòa âm / Guitar` để không
     tốn thêm label row.
5. **Dáng full-width** ở dưới controls: `Khung` và `Tiết nhịp` đặt cạnh nhau
   khi `contentWidth >= 640`; dưới ngưỡng thì xếp dọc.
6. **Compact row trên PC**:
   - Dense: row **50px** = top line 16px (label + value + `↺`) + gap 2px +
     control line 26px (`−` 24px + track + `+` 24px) + padding 6px.
   - Thoáng: row **60px**, track 34px.
   - Không dùng `paramFoot` trên PC. BPM nằm trong value cell
     (`+8% · 104 BPM`, dùng `monoSmall` nếu cần); hint/cảnh báo nằm trong
     status strip.
   - Value cell rộng tối đa 96px, `numberOfLines={1}`, ellipsis.
   - `−`/`+` hitSlop 12; slider hit 26px + `hitSlop` 12; help/reset
     hitSlop 14. Tổng vùng chạm >=44.
   - Mobile giữ row 2 tầng + `paramFoot`, track 34px, có scroll.
   - `?` mở **HelpCard** cố định phía trên footer: nền đục, có scroll, không bị
     row/ScrollView cắt; hiện `helpText(field)` (copy UI mới, không dùng
     description 0/1/2 cũ trong schema), giá trị, detail và nhãn hai đầu.
7. **Dense mode theo viewport height**:
   - `height < 740`: row 50px, mixer 192px, group gap 8px, body gap 14px.
   - `height >= 740`: row 60px, mixer 210px, group gap 8px, body gap 14px.

```text
┌──────────────────────────────────────────────────────────────────────┐
│ TINH CHỈNH   PROFILE                    Default · đã sửa         ✕  │
│ Default · 2 thay đổi ẩn                                  [chi tiết] │ 24
├──────────────────────────────────────────────────────────────────────┤
│ CÂN BẰNG BÈ                                                          │
│  ┌────────────────────────────────┐   ┌─────┐ ┌─────┐ ┌─────┐       │
│  │      sóng thấp/trung/cao       │   │  ▓  │ │  ▓  │ │  ▓  │       │
│  │   THẤP      TRUNG      CAO     │   │  ▓  │ │  ▓  │ │  ▓  │       │
│  └────────────────────────────────┘   └─────┘ └─────┘ └─────┘       │
│                                       Bass    Trung   Cao           │
│  Vùng âm [──●──]   Màu [──●──]        [Đưa 3 bè về 0]                │
├────────────────────────┬────────────────────────┬────────────────────┤
│ TRÌNH DIỄN             │ CHẤT LIỆU              │ HÒA ÂM / GUITAR    │
│  Nhịp       +8%·104BPM↺│  Tương phản  −50%   ↺  │  Màu hòa âm  −40%  │
│  − ─────●───── +       │  − ─────●───── +       │  − ─────●───── +    │
│  Người      −40%     ↺ │  Nhiễu       0.10%     │  Nhịp hòa âm 0     │
│  − ─────●───── +       │  − ─────●───── +       │  − ─────●───── +    │
│  Hơi thở    −25%     ↺ │  Mật độ      0%        │  Kỹ thuật    0     │
│  − ─────●───── +       │  − ─────●───── +       │  − ─────●───── +    │
├────────────────────────┴────────────────────────┴────────────────────┤
│ DÁNG   Khung [Tự động | Không | Ngắn | Dài]   Tiết nhịp [seg 5 mục]  │
├──────────────────────────────────────────────────────────────────────┤
│                                              [Reset]      [Lưu]      │
└──────────────────────────────────────────────────────────────────────┘
```

Phân bổ cột:

| Cửa sổ | Controls | Cột 1 | Cột 2 | Cột 3 | Dáng |
|---|---|---|---|---|---|
| `< 1100` | 1 cột | Trình diễn (3) → Chất liệu (3) → Hòa âm/Guitar (3) | — | — | full-width |
| `1100–1279` | 2 cột | Trình diễn (3) + Chất liệu (3) | Hòa âm (2) + Guitar (1), chung header | — | full-width |
| `>= 1280` | 3 cột | Trình diễn (3) | Chất liệu (3) | Hòa âm (2) + Guitar (1), chung header | full-width |

`Dáng` luôn full-width vì `meter` có 5 lựa chọn. Nếu chỉ một trong hai field
visible, field còn lại chiếm toàn bộ hàng.

Chiều cao 3 cột: **3 hàng + 1 label row** mỗi cột. `Hòa âm / Guitar` dùng chung
label nên không phát sinh label thứ hai.

Ước lượng chiều cao (3 cột, worst case 3 hàng):

| Vùng | Dense (`height < 740`) | Thoáng (`height >= 740`) |
|---|---|---|
| Header + profile dính | 64 | 76 |
| Status strip | 24 | 24 |
| Mixer ngang panel | 192 | 222 |
| Body gap (mixer → cột → Dáng) | 28 | 28 |
| Controls (3 hàng + 1 label + gaps) | 194 | 228 |
| Dáng full-width | 64 | 76 |
| Footer | 50 | 50 |
| Padding body | 28 | 28 |
| **Tổng** | **644** | **732** |

- Viewport `1366×660`: 3 cột + dense, tổng 644 → vừa, còn 16px.
- Viewport `1440×800`: 3 cột + thoáng, tổng 732 → vừa, còn 68px.
- Viewport `1920×980`: 3 cột + thoáng, `contentWidth` 1040 → rất thoáng.
- Viewport `1280×600`: 3 cột + dense, tổng 644 → **có thể scroll**; không hứa
  no-scroll.
- Viewport `1024×620`: **1 cột** + dense, `Dáng` xếp dọc; 3 group nối tiếp +
  Dáng 124 → **~1112**, scroll. Đây là chấp nhận: 1024×768 không nằm trong nhóm
  “một màn hình”; ưu tiên 1 cột dễ đọc trên cửa sổ hẹp.
- Không dùng `panelLayout` để đoán `scroll`. `scrollEnabled` lấy từ đo thật:
  `onLayout` của khung + `onContentSizeChange` của nội dung.
- Mobile vẫn một cột cuộn: mixer → Trình diễn → Chất liệu → Hòa âm → Guitar →
  Dáng.
- Header, status strip và footer dính; không lồng nhiều `ScrollView`.

### 3.3 Vì sao không đặt mixer làm một cột riêng?

Nếu mixer nằm trong một cột dọc, cột đó cao khoảng 500px, trong khi cột controls
còn lại khoảng 870px → vẫn phải cuộn. Đưa mixer thành **dải ngang toàn panel**
trên cùng và tách `Dáng` thành hàng full-width giúp cột controls cao nhất chỉ
còn 3 hàng. Đây là lý do bố cục một màn hình khả thi ở viewport 660px.

## 4. Các khu vực

### 4.1 Cân bằng

- Là dải **ngang toàn panel** trên cùng, không nằm trong một cột dọc và không
  tràn ra ngoài bề rộng panel.
- Trái: sóng low/mid/high co giãn theo chiều rộng còn lại.
- Phải: 3 fader dọc theo thứ tự **Bè bass → Bè trung → Bè cao**, khớp trái→phải với dải tần THẤP → TRUNG → CAO.
- Fader chỉ hiện khi `variant === 'guitar'`.
- Khi không phải Guitar: hiện ghi chú “Bè guitar chỉ mở ở thể loại Guitar”,
  không hiện fader chết; mixer thu còn ~164/188px thay vì giữ chỗ fader rãnh.
- Dưới cùng: hàng `Vùng âm` + `Màu` + nút `Đưa 3 bè về 0`.
- `Vùng âm` điều khiển độ nghiêng của phổ; `Màu` nằm cùng hàng để giảm một hàng
  controls và để hai knob “chất liệu không gian” cạnh nhau.

### 4.2 Trình diễn

- `Nhịp`, `Người`, `Hơi thở`. `Màu` đã chuyển xuống mixer.

### 4.3 Chất liệu

- `Tương phản`, `Nhiễu`, `Mật độ`.

### 4.4 Hòa âm

- `Màu hòa âm`, `Nhịp hòa âm`.

### 4.5 Dáng

- `Khung`, `Tiết nhịp`.
- Là **hàng full-width** dưới controls.
- `contentWidth >= 640`: hai field cạnh nhau, mỗi field ~50%.
- `contentWidth < 640`: xếp dọc, mỗi field full-width.
- Dùng segmented control thay vì các nút rời.
- `meter` có 5 lựa chọn; full-width (hoặc 50% khi >=640) bảo đảm không wrap.

### 4.6 Guitar

- `Kỹ thuật` chỉ hiện khi field thật sự áp dụng (`bach`, `torroba`, tier C).
- Ba bè đã chuyển sang khu Cân bằng và chỉ hiện khi `variant === 'guitar'`.
- Trong cột 3, `Hòa âm` và `Guitar` dùng chung header `Hòa âm / Guitar` để
  không tốn thêm label row.

### 4.7 Profile tab

- Giữ một cột, `maxWidth: 560`, canh giữa trong panel.
- Không áp layout 2/3 cột của tab Tinh chỉnh.
- Danh sách profile, editor tên và các nút giữ nguyên hành vi hiện tại.

### 4.8 Mobile

- Một cột cuộn.
- Mixer: sóng full-width, 3 fader nằm ngang bên dưới, rồi `Vùng âm`.
- Controls: Trình diễn → Chất liệu → Hòa âm → Guitar → Dáng.
- Fader dọc vẫn dùng được, nhưng track thấp hơn (~120px) để không chiếm màn hình.
- Sheet có 2 snap (`half`/`full`); **chạm tay cầm để mở/thu**, kéo tay cầm
  vẫn hoạt động, và khi cuộn nội dung tới đáy thì tự mở sang `full` để
  footer `Reset | Lưu` lộ ra. Tay cầm cao 36px trọng vùng chạm.

## 5. Field `0–1–2` thành trục âm/dương

### 5.1 Nguyên tắc

- Field `0–2`: lấy **`1` làm tâm** vì `1` là “bản hiện tại”, `0` và `2` là hai
  cực ít/nhiều.
- Field đã có `0` là tâm (`guitar_high/mid/bass`): giữ `0` làm tâm.
- `noise`: neo `0` vì `0` = không nhiễu. Default `0.1` nằm ở **20%** track,
  không phải tâm.
- Chỉ đổi cách hiển thị. Giá trị gửi backend, hash, URL và profile không đổi.
- Slider tô từ **anchor**:
  - field centered: anchor = tâm = default;
  - `noise`: anchor = 0.
- Vạch default:
  - field centered: ở tâm;
  - `noise`: ở 20% track.
- Khi giá trị khác default, hiện nút `↺` nhỏ để trả về mặc định.

### 5.2 Bảng hiển thị

| Field | Range | Tâm / anchor | Trái → phải | Hiển thị |
|---|---|---|---|---|
| `tempo` | `0.75–1.25` | `1.0` | Chậm ← 0 → Nhanh | `−25% … +25%`, kèm BPM |
| `humanize` | `0–2` | `1.0` | Ít ← 0 → Nhiều | `−100% … +100%` |
| `breath` | `0–2` | `1.0` | Đều ← 0 → Cong câu | `−100% … +100%` |
| `color` | `0–2` | `1.0` | Khô ← 0 → Đậm | `−100% … +100%` |
| `dynamics` | `0.5–1.5` | `1.0` | Phẳng ← 0 → Tương phản | `−50% … +50%` |
| `density` | `0–2` | `1.0` | Thưa ← 0 → Dày | `−100% … +100%` |
| `harmony` | `0–2` | `1.0` | Tối giản ← 0 → Nhiều màu | `−100% … +100%` |
| `motion` | `0–2` | `1.0` | Giữ lâu ← 0 → Dồn dập | `−100% … +100%` |
| `register` | `0–2` | `1.0` | Thấp/ấm ← 0 → Cao/sáng | `−100% … +100%` |
| `technique` | `0–2` | `1.0` | Dễ ← 0 → Điêu luyện | `−100% … +100%` |
| `guitar_high/mid/bass` | `−12–+12` | `0` | Nhỏ ← 0 → Lớn | `−12 … +12` |
| `noise` | `0–0.5%` | anchor `0`, default `0.1` | Sạch → Nhiễu | `0.00% … 0.50%` tuyệt đối |

Ví dụ:

```text
Người        −40%  ·  0.60     ↺
              Ít hơn        Nhiều hơn
```

- `tempo`: primary `+8%`, secondary `104 BPM`, detail `1.08× · 104 BPM`
  (BPM lấy từ `effectiveBpm(baseBpm, value)`).
- `guitar_*`: primary `+3`, secondary `3 velocity`.
- `noise`: primary `0.10%`, secondary `mặc định`, detail `mặc định 0.10%`.
- `humanize` / `breath` hiện cảnh báo mềm trong status strip khi
  `humanize > 1.10` hoặc `breath > 1.20` (đúng hằng số
  `HUMANIZE_SOFT_WARNING` / `BREATH_SOFT_WARNING`).
- Row PC chỉ hiện `primary` (tempo kèm BPM). `detail`, giá trị thô và nhãn hai
  đầu (`Chậm ← 0 → Nhanh`, `Khô ← 0 → Đậm`…) nằm trong **HelpCard** khi bấm `?`.

### 5.3 Field đổi UI khác

| Field | UI mới | Lý do |
|---|---|---|
| `frame`, `meter` | segmented control trong hàng `Dáng` full-width | 4–5 lựa chọn, nhìn là biết đang chọn gì |
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
guitar_bass   →  cộng vào dải thấp   (chỉ khi variant === 'guitar')
guitar_mid    →  cộng vào dải trung  (chỉ khi variant === 'guitar')
guitar_high   →  cộng vào dải cao    (chỉ khi variant === 'guitar')
```

Ví dụ:

```ts
const guitar = variant === 'guitar';
low  = 0.55 - (register - 1) * 0.30 + (guitar ? guitar_bass / 12 * 0.22 : 0);
mid  = 0.55                            + (guitar ? guitar_mid  / 12 * 0.22 : 0);
high = 0.55 + (register - 1) * 0.30 + (guitar ? guitar_high / 12 * 0.22 : 0);
```

Clamp `0.08–0.95`.

### 6.2 Cách vẽ

- Đường cong mượt qua 3 điểm, tô gradient magenta `palette.sound`.
- 3 cột bar mờ tại từng band, cao/thấp so với đường reference 55% để thấy
  chênh lệch ngay cả khi curve chỉ nhích nhẹ.
- Đường reference 55% nét đứt; bar nằm trên/dưới cho biết band đang tăng/giảm.
- Preview phóng đại độ lệch 1.5× cho dễ đọc trong strip 66px; số % dưới mỗi
  band vẫn là giá trị ước lượng thật.
- 3 nhãn `THẤP / TRUNG / CAO`, mỗi nhãn kèm % ước lượng.
- Vạch nền mảnh, không dùng màu nhấn thứ tư.
- Ghi rõ dưới card: **“Phổ ước lượng từ tham số, không phải phân tích audio.”**
- Không dùng `peaks` của timeline; không đụng rule “peaks chỉ nằm trên timeline”.

Nếu sau này muốn sóng thật, cần Web Audio `AnalyserNode`/FFT. Đó là việc riêng,
không làm trong đợt UI này.

## 7. Kỹ thuật

### 7.1 File dự kiến

| File | Việc |
|---|---|
| `src/musicalize/TuningPanel.tsx` | mixer ngang toàn panel + controls 2/3 cột + Dáng full-width, fader dọc, slider bipolar, segmented control |
| `src/musicalize/TuningSpectrum.tsx` | sóng low/mid/high bằng `react-native-svg` |
| `src/musicalize/tuningDisplay.ts` | helper thuần: tâm field, text hiển thị, spectrum levels, panel width/layout |
| `src/musicalize/tuningDisplay.test.ts` | test helper |
| `src/musicalize/RoomFrame.tsx` | dùng panel width/push động |
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
- `fieldAnchor(field)` → giá trị anchor (`center` hoặc `0` cho `noise`).
- `anchorRatio(field)` → vị trí anchor trên track; `noise` = 0, default tick
  của `noise` = 20%.
- `helpText(field)` → copy HelpCard theo UI signed %; fallback về
  `field.description` cho field chưa có override.
- `paramDisplay(field, value, { baseBpm })` →
  `{ primary, secondary, detail, negativeLabel, positiveLabel }`.
  Row PC chỉ dùng `primary` (tempo kèm BPM). `detail`, giá trị thô và nhãn hai
  đầu nằm trong HelpCard.
- `panelColumns(context, columns)` → cột đã gộp `Hòa âm / Guitar`, đã bỏ
  `register`/`color` khỏi groups.
- `spectrumLevels(params, variant)` → `[low, mid, high]`; guitar offsets chỉ
  cộng khi `variant === 'guitar'`.
- `panelWidthFor(windowWidth)`.
- `panelPushes(windowWidth)`.
- `panelLayout(windowWidth, windowHeight, context)` →
  `{ columns, dense, rowHeight, contentWidth, dangStacked, estimatedHeight }`,
  **không** trả `scroll`.
  `context = { variant, span, ensemble, tiers }`.
  `estimatedHeight` chỉ để test/ước lượng; runtime vẫn đo thật.

Visibility và đếm thay đổi:

- `panelFields(context)` = `visibleFields(...)` rồi lọc thêm:
  - `guitar_high/mid/bass` chỉ giữ khi `variant === 'guitar'`.
- `changedCount` dùng `panelFields`, không dùng `visibleFields` trực tiếp.
- `hiddenChanged` đếm mọi `PARAM_FIELDS` đã đổi nhưng không nằm trong
  `panelFields` (gồm guitar field khi không phải Guitar).
- `paramSummary` gộp cả hidden: `Default`, `N thay đổi`, `N ẩn`, hoặc
  `N thay đổi · M ẩn`.
- Telemetry: thay `changedKeys(params)` bằng
  `changedKeysForPanel(params, context)` + `hiddenChangedKeys(params, context)`.
  Nhờ vậy `profile_save` / `knob_change` không đếm guitar field như knob đang
  hoạt động khi thể loại không phải Guitar.

Không sửa `appliesTo` backend thành `['guitar']`: token `guitar` khớp cả
`variant === 'guitar'` lẫn ensemble `guitar` của Minimalist, nơi backend không
chạy `apply_voice_balance`. Đây là lọc UI, không phải schema.

Test tối thiểu:

- Mọi field `0–2` có tâm `1`; `guitar_*` có tâm `0`; `noise` anchor `0`,
  default tick ở 20%.
- Text `tempo`, `guitar_*`, `noise` đúng dấu, range và đơn vị:
  `tempo` ±25%, `dynamics` ±50%, field `0–2` ±100%, guitar ±12.
- `spectrumLevels` ở default, ở hai cực `register`, khi guitar offset bị clamp,
  và khi `variant !== 'guitar'` thì offset guitar không được cộng.
- `panelWidthFor`:
  - 960 → 640 (clamped, 66.7%);
  - 1024 → 640 (clamped, 62.5%);
  - 1440 → 864;
  - 1920 → 1152;
  - 2560 → 1280 (clamped, 50%).
- `contentWidth`: 1920 → 1040; 2560 → 1040.
- `panelPushes`: 1878 → false; 1879 → true; 1920 → true.
- `panelLayout` cho Guitar (width/height là viewport, không phải độ phân giải
  màn hình):
  - `1024×620` → 1 cột, dense, `rowHeight = 50`, `dangStacked = true`,
    `estimatedHeight = 1112`.
  - `1280×600` → 3 cột, dense, `rowHeight = 50`.
  - `1366×660` → 3 cột, dense, `rowHeight = 50`, `estimatedHeight = 644`.
  - `1440×800` → 3 cột, thoáng, `rowHeight = 60`, `estimatedHeight = 732`.
  - `1920×980` → 3 cột, thoáng, content 1040, `estimatedHeight = 732`.
  - `2560×1400` → 3 cột, content 1040.
  - Mobile → 1 cột, row 2 tầng có `paramFoot`.
- `dangStacked`: `contentWidth` 592 → true; 720 và 1040 → false.
- `Dáng` stacked cao 124px; side-by-side 64/76px.
- `panelColumns` 3 cột: `Hòa âm / Guitar` chung một header; `color` không nằm
  trong `Trình diễn`.
- `statusStrip` luôn 24px và đã nằm trong `estimatedHeight`; `Default` note,
  `hiddenChanged`, server notes gộp một dòng ellipsis nên không cộng thêm.
- `panelFields`: Guitar visible khi `variant === 'guitar'`; ẩn ở `symphony`;
  `changedCount` và `hiddenChanged` khớp.
- Telemetry: `changedKeysForPanel` bỏ guitar field ở `symphony`;
  `hiddenChangedKeys` vẫn thấy chúng.
- `meter` 5 lựa chọn không wrap: `contentWidth` 592 → xếp dọc full-width;
  720 và 1040 → cạnh nhau, mỗi field 50%, vẫn đủ chỗ.

### 7.4 Runtime

- `drawerX` phải là `Animated.Value(panelWidth)` và cập nhật khi `panelWidth`
  đổi:
  - đóng: `drawerX.setValue(panelWidth)`;
  - mở: `drawerX.setValue(0)`.
  Nếu resize từ 380 → 820 mà không set lại, drawer đóng vẫn lệch.
- `scrollEnabled` đo thật:
  - `onLayout` khung cuộn → `availableHeight` (đã trừ header, status strip,
    footer);
  - `onContentSizeChange` → `contentHeight`;
  - `scrollEnabled = contentHeight > availableHeight + 1`.
- Status strip mở chi tiết bằng popover/overlay, không đẩy body và không làm
  `scrollEnabled` bật.
- `Animated.timing` đóng/mở dùng `panelWidth` hiện tại, không dùng hằng 380.

## 8. Rủi ro

1. **Fader dọc vs ScrollView**: cần `PanResponder` capture đúng để kéo fader
   không cuộn panel. Test trên web và native.
2. **Chart bị che ở focus mode**: overlay không làm chart rộng hơn push. Ở
   1280–1440 visible chart chỉ 200–264px; phải ghi rõ là focus mode, có nút
   `Thu gọn`/`Esc`, không quảng cáo “chart vẫn dùng được”. Push chỉ từ ~1879px.
3. **Guitar field ngoài Guitar**: lọc UI, không dùng `appliesTo: ['guitar']` vì
   khớp cả ensemble `guitar` của Minimalist. Phải cập nhật `changedCount`,
   `hiddenChanged`, `spectrumLevels`.
4. **Sóng là ước lượng**: phải ghi chú rõ để không gây hiểu nhầm là phân tích
   audio.
5. **A11y**: fader dọc phải là `adjustable`, có readout, `accessibilityValue`,
   action increment/decrement, và hỗ trợ phím lên/xuống/Home/End trên web.
6. **`drawerX` dynamic width**: resize khi panel đóng/mở phải set lại
   `Animated.Value`; nếu không drawer lệch.
7. **`meter` 5 lựa chọn**: đã xử lý bằng hàng `Dáng` full-width. Nếu sau này
   chuyển `Dáng` vào cột, phải test wrap ở 224–264px.
8. **Chiều cao thật**: dùng `innerHeight`, không dùng 768/900 của màn hình.
   `1024×768` và `1280×720` có thể scroll; đừng đưa vào tiêu chí no-scroll.
9. **Row compact 50px**: phải viết lại `ParamSlider` cho PC. Nếu giữ row 2 tầng
   62px hiện tại, `1366×660` sẽ vượt màn hình. Đây là điều kiện bắt buộc của
   tiêu chí no-scroll.
10. **Status strip**: note/cảnh báo phải gộp một dòng ellipsis + popover. Nếu
    render nhiều dòng inline như `TuningTab` hiện tại, 44px margin sẽ mất.

## 9. Thứ tự triển khai

1. `tuningDisplay.ts` + test: panel width/layout, panel fields, display text,
   spectrum, visibility/count.
2. `TuningSpectrum.tsx`.
3. Layout mixer ngang toàn panel + controls 2/3 cột + Dáng full-width +
   panel width động.
4. Compact row PC 50/60px (không `paramFoot`), fader dọc, slider bipolar,
   segmented control, readout/a11y.
5. Header profile dính + status strip 24px + popover chi tiết.
6. Runtime scroll measurement + `drawerX` resize handling + telemetry
   `changedKeysForPanel` / `hiddenChangedKeys`.
7. Rà viewport `1024×620`, `1280×600`, `1366×660`, `1440×800`, `1920×980`,
   web + native.
8. Chạy `npm run test:musicalize`.

## 10. Tiêu chí xong

- Panel PC rộng 50–67% viewport, không full-width; `contentWidth` có trần 1040.
- Guitar trên PC, viewport `1366×660`: panel 820, 3 cột + dense, row 50px,
  `Dáng` full-width, tổng 644, **không cuộn**.
- Guitar trên PC, viewport `1440×800`: panel 864, 3 cột thoáng, row 60px,
  tổng 732, **không cuộn**.
- Guitar trên PC, viewport `1920×980`: panel 1152, `contentWidth` 1040, 3 cột,
  **không cuộn**.
- `1024×768` và `1280×720`: chấp nhận scroll; `1024×620` dùng 1 cột,
  `Dáng` stacked ~1112. Không hứa no-scroll.
- PC row 50px không dùng `paramFoot`; BPM nằm trong value cell, hint/cảnh báo
  nằm trong status strip 24px.
- Status strip gộp `Default` note, `hiddenChanged`, server notes một dòng
  ellipsis + popover; không đẩy body.
- `humanize`/`breath` cảnh báo ở `>1.10` / `>1.20`.
- Ở 1280–1440, panel là focus mode: chart bị che còn 200–264px, có `Thu gọn`/
  `Esc`. Không viết “overlay giúp chart vẫn dùng được”.
- Chỉ push từ ~1879px; khi đó chart còn >=440px.
- `meter` 5 lựa chọn nằm một hàng trong `Dáng` full-width.
- Kéo `Bè bass/trung/cao` thấy fill từ anchor, bar và % của đúng band đổi theo;
  thứ tự fader trái→phải là Bass → Trung → Cao.
- Các field hiện đúng range: `tempo` ±25%, `dynamics` ±50%, field `0–2`
  ±100%, guitar ±12, `noise` `0.00–0.50%` (default `0.10%`).
- Guitar field ẩn ngoài thể loại Guitar; `changedCount` / `hiddenChanged` /
  `spectrumLevels` khớp.
- Telemetry không đếm guitar field như knob đang hoạt động ngoài Guitar;
  `changedKeysForPanel` + `hiddenChangedKeys` khớp UI.
- `drawerX` cập nhật theo panel width khi resize.
- `Reset` / `Lưu` vẫn hoạt động như cũ; `Đưa 3 bè về 0` chỉ đổi ba field guitar,
  không thay `Reset` profile.
- Không đổi hash, URL hay dữ liệu profile đã lưu.

## 11. Trạng thái triển khai

Đã triển khai trong PR #141:

| File | Nội dung |
|---|---|
| `src/musicalize/tuningDisplay.ts` | panel width/layout, panel fields, display text, spectrum, changed/hidden keys |
| `src/musicalize/tuningDisplay.test.ts` | test pure helpers |
| `src/musicalize/TuningSpectrum.tsx` | phổ ước lượng low/mid/high |
| `src/musicalize/TuningPanel.tsx` | header profile, status strip, mixer, fader dọc, compact row, 2/3 cột, Dáng full-width, Profile tab |
| `src/musicalize/RoomFrame.tsx` | push theo `panelPushes`, giữ chỗ theo `panelWidthFor` |
| `src/musicalize/tuning.tsx` | telemetry `changedKeysForPanel` + `hiddenChangedKeys` |
| `package.json` | thêm `tuningDisplay.test.ts` vào `test:musicalize` |

Đã kiểm:

- `npx tsc --noEmit`
- `npm run test:unit`
- `npx expo export --platform web`

Ghi chú triển khai:

- Row compact 50px dùng top line 16 + control line 26; mobile quay lại row 2 tầng
  có `paramFoot` và scroll.
- Ở viewport hẹp (`1024`, `1280×600`) panel vẫn scroll; đúng như tiêu chí đã chốt.
- `TuningSpectrum` chỉ là preview từ tham số, không dùng `peaks` hay audio thật.
- Fader guitar xếp Bass → Trung → Cao; spectrum có bar + reference 55% + % từng band.
- HelpCard dùng `helpText()` override để bỏ copy 0/1/2 cũ trong schema generated.
- Content được bọc trong `contentFrame` max 1088px để nội dung thật dừng ở 1040px.
- `Màu` nằm cùng hàng `Vùng âm` trong mixer; `Hòa âm / Guitar` dùng chung header.
