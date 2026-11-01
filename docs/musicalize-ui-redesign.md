# Musicalize — nâng cấp giao diện

Tài liệu này chốt hướng làm đẹp và làm hữu dụng mặt nghe Musicalize. Nó bổ sung cho
`docs/musicalize-plan.md`, không thay các luật ở đó (thứ tự màn nghe, hành vi
playhead, sóng `peaks` chỉ trên thanh Phiên, tên bài nằm ngoài `Sparkline`).

## Phạm vi

Chỉ đụng `src/musicalize/` và thêm prop tuỳ chọn cho `src/components/Sparkline.tsx`.
Không đổi terminal cổ phiếu, không đổi `PriceChart`, `PieceTitle`, `SessionRecap`,
`src/theme.ts`. Không đổi backend, `seek.ts`, `program.ts`, `recapCursor.ts`.

Mục tiêu, theo thứ tự ưu tiên:

1. **Hữu dụng.** Đọc được trạng thái trong 1 giây, thao tác bằng bàn phím, cột trái
   có thông tin thật thay vì lặp một nhãn.
2. **Nguy hiểm.** Cảm giác "buồng điều khiển ban đêm": tối, viền mảnh, số mono,
   neon chỉ nằm ở chỗ đang chạy.
3. **Sexy.** Nhịp điệu thị giác, chữ có chủ đích, chuyển động ngắn và dứt khoát.

## 1. Chẩn đoán hiện tại

| # | Vấn đề | Bằng chứng | Hậu quả |
|---|---|---|---|
| 1 | Không có hệ thứ bậc | `Controls.tsx:265-308` — mọi chip và nút cùng `borderRadius: 8`, cùng `palette.surface` | Mắt không có điểm neo; "Nghe", thể loại và nhạc cụ nặng như nhau |
| 2 | Magenta bị lạm phát | `SymbolColumn.tsx:309`, `Controls.tsx:272`, `:298` — tô kín hàng, chip, nút | Màu nhấn mất nghĩa nhấn; nhìn rẻ |
| 3 | Sân khấu trống | `Stage.tsx:104-146`, `Sparkline.tsx` — một nét 2.25px, không lưới, không tick | Cảm giác đang tải, không phải đang diễn |
| 4 | Nhãn đè nhau ở góc phải | Ảnh chụp: `1Y:0315` chồng lên trục; do `cursorLabel` (`top: 6`) và `axis` (`top: 8`) cùng neo trên | Trông như lỗi |
| 5 | Cột trái vô dụng | `SymbolColumn.tsx:121-124` — `detail` = `span`, nên 10 hàng đều in `1M` | 300px không mang thông tin |
| 6 | Brand yếu nhất trên màn | `SymbolColumn.tsx:189-195` — 13px, `textMuted` | Tên sản phẩm đọc như nhãn debug |
| 7 | Hai scrubber trùng vai | `Controls.tsx:110-136` — Phiên/Chương + Tác phẩm | Hai khối cao, người nghe phải chọn não |
| 8 | Đồng hồ vượt thời lượng | Ảnh chụp: `4:23 / 4:20` | Mất tin cậy |
| 9 | Không chuyển động, không bàn phím | `reanimated` có trong `package.json` nhưng `src/musicalize/` không dùng; không có `keydown` | Thiếu cảm giác "nhạc cụ"; web không thao tác nhanh được |
| 10 | Panel điều khiển cuộn trong | `RoomFrame.tsx:62-67` — `maxHeight: '46%'` + `ScrollView` | Hai thanh cuộn lồng nhau, dock bị cắt |

## 2. Nguyên tắc

- **Ba màu nhấn giữ nguyên** theo `musicalize-plan.md`: cyan `#3EE0E0` là dữ liệu,
  magenta `#E040A0` là tiếng, amber `#F5B942` là chỗ đang nghe. Không thêm màu
  nhấn thứ tư.
- **Magenta không bao giờ làm nền một khối lớn hơn một hàng hoặc nút play.** Chỗ
  đang chọn đánh dấu bằng vạch 2px + surface sáng hơn.
- **Amber chỉ ở playhead và đếm ngược nghỉ.** Không dùng amber cho nút.
- **Sóng `peaks` chỉ trên timeline.** Không vẽ lại trong khung giá ở bất kỳ độ mờ
  hay màu nào — luật ở `musicalize-plan.md` là về nội dung, không về màu.
- **Viền mảnh thay vì bóng đổ.** Không gradient trang trí, không đổ bóng, không đĩa than.
- **Số luôn mono, tabular.** Mã, giờ, BPM, phần trăm.
- **Chuyển động 120–240ms.** Không hiệu ứng dài hơn 400ms ngoài zoom chart đã có (900ms).

## 3. Design tokens

Thêm vào `src/musicalize/palette.ts`. Giữ nguyên tên cũ để không phải sửa toàn bộ.

| Token | Giá trị | Dùng cho |
|---|---|---|
| `background` | `#08090C` (đổi từ `#0D0F12`) | nền app, dock |
| `panel` | `#0F1319` (mới) | cột trái, topbar, popover |
| `surface` | `#171C24` (đổi từ `#14181E`) | chip, hàng, nút phụ |
| `surfaceActive` | `#1E242E` (mới) | hàng đang chọn, hover |
| `hairline` | `rgba(244, 241, 234, 0.08)` (mới) | viền 1px mọi panel |
| `hairlineStrong` | `rgba(244, 241, 234, 0.16)` (mới) | focus, divider, tick chương |
| `text` | `#F4F1EA` (giữ) | chữ chính |
| `textMuted` | `#9AA3AD` (giữ) | chữ phụ |
| `textFaint` | `#5C6572` (mới) | nhãn mục, mã hàng chưa chọn |
| `data` | `#3EE0E0` (giữ) | đường giá, dải khối lượng |
| `dataFill` | `rgba(62, 224, 224, 0.14)` (mới) | vùng tô |
| `sound` | `#E040A0` (giữ) | nút play, thanh đã phát, vạch đang chọn |
| `soundSoft` | `rgba(224, 64, 160, 0.16)` (mới) | nền nhẹ, tick chương đã qua |
| `playhead` | `#F5B942` (giữ) | playhead, đếm ngược nghỉ |
| `track` | `#2A313A` (giữ) | rãnh timeline |

Khoảng cách: `4 / 8 / 12 / 16 / 24 / 32`. Bo góc: `2` (vạch, tick), `4` (chip nhỏ,
badge, popover), `8` (nút, tile), `999` (pill chế độ, nút play).

### Chữ

Không thêm `expo-font` ở P0/P1. Dùng font hệ thống, khai trong
`src/musicalize/type.ts` (mới):

| Vai trò | Web | iOS | Android | Size / lineHeight | Weight | Tracking |
|---|---|---|---|---|---|---|
| `display` | `Georgia, 'Palatino Linotype', Palatino, 'Times New Roman', 'Noto Serif', serif` | `Georgia` | `serif` | 34 / 38 (wide), 26 / 30 (narrow) | 600 | −0.6 |
| `sans` | `-apple-system, 'SF Pro Text', 'Segoe UI', Roboto, sans-serif` | `System` | `sans-serif` | 14 / 20 | 500 | 0 |
| `wordmark` | `sans` | `sans` | `sans` | 13 / 16 | 700 | 3.0, uppercase |
| `section` | `sans` | `sans` | `sans` | 11 / 14 | 700 | 1.2, uppercase |
| `meta` | `mono` | `Menlo` | `monospace` | 12 / 16 | 500 | 0.6, uppercase |
| `mono` | `ui-monospace, SFMono-Regular, Menlo, monospace` | `Menlo` | `monospace` | 12–13 / 16 | 500 | 0, `tabular-nums` |

`display` là serif: đây là thay đổi tạo khác biệt lớn nhất so với công sức. Nếu sau
này muốn font riêng thì thêm `expo-font` ở P2, không đổi cấu trúc `type.ts`.

**Kiểm tra tiếng Việt trước khi chốt font (đã làm trên macOS).** Georgia, Palatino,
Times New Roman và Baskerville đều có đủ `ạ ế đ ư ơ ộ ỹ ấ`; Charter thiếu `ư ơ`.
Georgia đứng đầu vì được vẽ cho màn hình (x-height lớn, tương phản nét thấp) và
đủ dấu tiếng Việt. Đã kiểm bằng `fc-query` trên chính file font trong
`/System/Library/Fonts`. Menlo thiếu `ế` và `ấ`, nên **không bao giờ đặt câu tiếng
Việt ở vai `mono`** — dùng `section` hoặc `sans`.

## 4. Bố cục

Wide (≥ 960px). Topbar mới cao 56. Cột trái 312. Dock điều khiển cao cố định,
không cuộn trong.

```
┌────────────────────────────────────────────────────────────────────────┐
│ MUSICALIZE ▪        [ Nghe lại ○ Đang phát ]      ⌘K        ● TRỰC TIẾP │ 56
├────────────────┬───────────────────────────────────────────────────────┤
│ THỊ TRƯỜNG     │  Suite MBB 1M in B-flat                    (display)  │
│ [ Lọc mã    ⌘K]│  MBB · 1M · E-FLAT · 96 BPM · 15:12          (meta)    │
│ 1D 1W 1M 3M 1Y │                                                       │
│ Th5 Th6 Th7 …  │      ╱╲        ╱╲╱╲         ╱╲                        │
│                │     ╱  ╲      ╱    ╲       ╱  ╲      ┃ playhead       │
│ MBB ▲1.2% ▁▂▅  │    ╱    ╲____╱      ╲_____╱    ╲     ┃                │
│ FPT ▼0.4% ▅▂▁  │   ╱                              ╲    ┃                │
│ VIC ▲2.1% ▁▃▆  │  ▁▂▃▅▂▁▃▅▂▁▃▅  (dải khối lượng)       ┃                │
│ …              │  MÃ   PHIÊN   GIỌNG   NHỊP   BPM   THỜI LƯỢNG  (bar) │
├────────────────┴───────────────────────────────────────────────────────┤
│ GIAO HƯỞNG  JAZZ  TỐI GIẢN  AMBIENT  GUITAR        (shelf 5 tile)      │
│ Dây · Gỗ · Đồng               Torroba · Bach · Sor · Lobos   ⚙         │
│ (▶)  ⟲    0:42 ────────────────────────────── 15:12                    │
│ ▁▂▃▅▂▁▃▅▂▁▃▅▂▁▃▅▂▁▃▅▂▁▃▅  │1────────│2────────│3────────│     (timeline)│
└────────────────────────────────────────────────────────────────────────┘
```

Narrow (< 960px): thứ tự mới là topbar → stage (44vh, dính trên) → dock điều khiển
(dính dưới) → danh sách mã. Danh sách mã đổi thành dải chip ngang cuộn được, mỗi
chip một mã kèm phần trăm. Bỏ `narrowChooser: height: 460` của `RoomFrame.tsx`,
vì hiện tại người dùng phải cuộn hết danh sách mới thấy chart.

## 5. Spec từng vùng

### 5.1 Topbar (`TopBar.tsx`, mới)

- Cao 56, nền `panel`, viền dưới `hairline`, padding ngang 16.
- Trái: `MUSICALIZE` (`wordmark`, màu `text`) + một ô vuông 6px magenta cách 8px.
  Không dùng chữ xám 13px như hiện tại.
- Phải: pill chế độ `Nghe lại ○ / Đang phát ●` — pill bo 999, viền `hairline`,
  vế đang bật có chấm magenta + chữ `text`, vế kia `textFaint`. Đây là công tắc
  `mode` hiện có, chỉ đổi vỏ.
- Web: nút `⌘K` (mono, viền `hairline`, cao 28) mở command palette ở P2; P0 chỉ
  focus ô lọc mã.
- Live: chấm magenta 6px nhấp nháy (opacity 1 → 0.25, 1.6s) + `TRỰC TIẾP` (`section`).
  Replay: `PHÒNG NGHE` (`section`, `textFaint`).

### 5.2 Cột trái (`SymbolColumn.tsx`)

- Rộng 312, nền `panel`, viền phải `hairline`, padding 12.
- Nhãn mục `THỊ TRƯỜNG` (`section`, `textFaint`), cách 8px.
- Ô lọc: cao 32, bo 4, nền `background`, viền `hairline`, chữ `sans` 13. Bên phải
  trong ô là gợi ý `⌘K` (`mono` 11, `textFaint`) khi rỗng. Đây là `TextInput` hiện
  có, chỉ đổi vỏ.
- Hàng khung `1D 1W 1M 3M 1Y`: 5 ô bằng nhau, cao 28, bo 4, **không nền**. Ô bật:
  chữ `text` + vạch dưới 2px magenta. Ô tắt: `textFaint`.
- Chip ngày (`1D`): giữ chiều cao thấp như hiện tại (`SESSION_CHIP_HEIGHT`), bật =
  chữ `text` + viền `hairlineStrong`, không tô magenta.
- Hàng mã, cao 44, padding ngang 10, grid: `MBB` (`mono` 14/600) · tên công ty
  (`sans` 11, `textFaint`, 1 dòng, cắt đuôi) · sparkline 44×18 · `▲1.2%` (`mono` 11).
  - Đang chọn: vạch trái 2px magenta + nền `surfaceActive`. Không tô kín.
  - Dữ liệu: `fetchWatchlist(visibleSymbols)` đã có sẵn trong `src/api/client.ts`
    (trả `price`, `changePercent`, `sparkline`). Gọi một lần khi mount và mỗi 30s
    khi `document.visibilityState === 'visible'` (web) — **không** dùng
    `useMarketPolling` vì hook đó phụ thuộc `useFocusEffect` của react-navigation.
    Giới hạn 12 mã đang hiện. Lỗi thì ẩn cột phụ, hàng vẫn bấm được.
  - Màu phần trăm: **đơn sắc** (đã chốt, xem mục 13) — dấu `▲/▼` + `text` cho
    tăng, `textMuted` cho giảm; hướng đọc lấy từ độ dốc sparkline.
- Chân cột: gợi ý phím (`Space phát/tạm dừng · ←→ tua`) `mono` 10 `textFaint`, và
  trạng thái `12 mã · HOSE` bên phải.
- Đang phát (live): hàng `BTCUSDT · đoạn ~90s` giữ nguyên vị trí theo plan; thêm
  chấm magenta ở hàng đang nghe.

### 5.3 Sân khấu (`Stage.tsx`)

- Khối tiêu đề neo trên-trái, padding 24/16, không căn giữa:
  - Tên bài `display`, 1–2 dòng, không cắt giữa từ.
  - Dòng `meta` uppercase: `MBB · 1M · E-FLAT · 96 BPM · 15:12`. Thứ tự lấy từ
    `pieceCopy` + `program.durationSec`; thiếu trường nào thì bỏ trường đó.
  - Badge mã: `mono` 11, viền `hairline`, bo 4, padding 2/6, đứng trước dòng meta.
- Chart:
  - Lưới 4 đường ngang `rgba(244,241,234,0.05)`, không lưới dọc.
  - Trục phải: 4 nhãn `mono` 11 `textFaint` (min, 1/3, 2/3, max) thay vì chỉ
    min/max dồn hai góc. Nhãn bắt đầu từ `top: 32` để **không đè pill playhead**.
  - Đoạn chưa phát: `opacity 0.22` (giữ `dimUnplayed`).
  - Đoạn đã phát: nét 2.5px + một nét nền 7px cùng màu `opacity 0.14` làm glow.
  - Vùng tô: gradient `dataFill` → trong suốt, clip theo playhead.
  - **Không vẽ `peaks` trong khung giá.** `docs/musicalize-plan.md` cấm theo nội
    dung, không theo màu: "Không vẽ `RecapManifest.peaks` trong cùng khung với
    đường cyan. Sóng `peaks` của phiên `1D` chỉ trên thanh Phiên", lặp ba lần.
    Sóng chỉ sống trên timeline (mục 5.4). Xem mục 13.
  - Không vẽ nến: API chỉ trả `close` (`prices`), không có OHLC. Ghi rõ để sau này
    không ai đi tìm `open/high/low`.
  - Dải khối lượng: cao 36, sát đáy, màu `rgba(62,224,224,0.22)`, phần đã phát
    `0.42`, có đường baseline `hairline`. Nhãn `KL` (`mono` 10, `textFaint`) ở trái.
    36 là **nới có chủ đích** từ ~30px của `musicalize-plan.md` để dải đọc được ở
    1440px; không đổi số liệu, vị trí hay luật "không in số khối lượng".
- Playhead: vạch 1px amber, chấm 6px ở giao điểm với đường, pill giờ `mono` 11
  (nền amber, chữ `background`) ở trên, `left` clamp trong `[8, width-64]`.
- Trạng thái:
  - Trống: khung `hairline`, chữ `CHỌN MỘT MÃ ĐỂ NGHE` (`section`, `textFaint`),
    giữa khung.
  - Đang soạn: shimmer 1.2s trên nền chart + `ĐANG SOẠN` (`section`) góc dưới trái.
  - Nghỉ giữa chương: chart `opacity 0.4`, cung đếm ngược 24px amber + `NGHỈ 0:03`
    (`mono`) ở giữa. Thay dòng status chữ hiện tại.
  - Live: chấm magenta nhấp nháy + `TRỰC TIẾP` ở góc trên-phải chart; banner lỗi
    giữ nguyên vị trí đáy nhưng dùng `surface` + viền `hairline`.
- Kéo playhead giữ nguyên hành vi (`seekable`, `onSeekRatio`). Chỉ đổi vỏ.

### 5.4 Dock điều khiển (`Controls.tsx`)

Cao cố định 232 (wide) / auto (narrow). Bỏ `ScrollView` trong `RoomFrame.tsx`.
Nền `panel`, viền trên `hairline`, padding 16.

**Hàng 1 — shelf thể loại.** `N` tile cao 56, chia đều, bo 8, nền `surface`, viền
`hairline`. `N` = số thể loại đang có: 5 ở replay (có Guitar), 4 ở live
(`STREAM_GENRES`). Tile bật: chữ `text`, vạch dưới 3px magenta, nền `surfaceActive`.
Mỗi tile có một motif 8×8 (`■` giao hưởng, `◍` jazz, `▤` tối giản, `◌` ambient, `≋`
guitar) màu `textFaint` để bật thì `sound`. Không dùng icon thư viện.

**Hàng 2 — nhạc cụ / nghệ sĩ.** Chữ thường, không chip: các lựa chọn cách nhau
bằng dấu `·`, bật = `text` + vạch dưới 1px `hairlineStrong`, tắt = `textFaint`.
Cao 32. Bên phải: nút `⚙` 32×32 mở popover.

**Hàng 3 — transport.** Trái: nút play tròn 56 (nền `sound`, icon `▶`/`❚❚` màu
`background`), nút `⟲` 36 (viền `hairline`, icon `textMuted`). Giữa: `0:42`
(`mono` 13, `text`) + `/ 15:12` (`mono` 13, `textFaint`). Phải (chỉ wide): tên
chương hiện tại (`section`, `textFaint`) + `4/6`.
- Bỏ hẳn ba nút chữ ngang hàng `Controls.tsx:100-109`.
- Nút play disabled: `opacity 0.35`, không đổi màu nền.
- Đang phát: nút đổi icon, không đổi kích thước; thêm vòng ngoài 1px `soundSoft`.

**Hàng 4 — timeline gộp (`Scrubber.tsx`).**
- Một thanh duy nhất thay hai thanh `Chương` + `Tác phẩm`.
- Rãnh 4px bo 2 `track`; phần đã phát `sound`; chấm kéo 10px amber.
- `1D`: giữ `peaks` làm cột 36px phía sau rãnh, cột đã phát `sound`, chưa phát
  `track`.
- Nhiều chương: chia rãnh theo `workSegments(movements)` — đoạn `audio` vẽ `track`,
  đoạn `rest` vẽ `hairline`. Nhãn chương chỉ hiện khi hover (web) hoặc khi rê ngón
  (native): tooltip `surface` + viền `hairline`, nội dung `Tên chương · 3:12`.
- Giờ hiển thị dùng `clockText(time, duration)` (hàm thuần trong `labels.ts`).
  Chỉ có **một** đồng hồ, nằm ở hàng transport; timeline chỉ có nhãn và rãnh.
- Touch target 44px (đã có `flatHit: height 28` → tăng vùng chạm, không tăng rãnh).

**Ánh xạ thời gian và hành vi kéo.** Đây là phần rủi ro nhất của đợt, không phải
"chạm nhẹ" vào `ReplayRoom`.

- **Hàm ánh xạ đã có sẵn** trong `seek.ts`: `workSegments`, `workDuration`,
  `placeOnWork`, `workSecondsAt`. Không viết lại, không sửa `seek.ts`.
  `ReplayRoom.onWorkScrub` hiện đã dùng đúng chuỗi đó, nên timeline gộp tái dùng
  nguyên vẹn:
  `placeOnWork(movements, scrubberSeek(workDuration(movements), ratio))`.
- `1D` là **một** đoạn `audio`, nên `placeOnWork` trả `{ index: 0, offset }`; `peaks`
  vẽ trên cùng thanh đó.
- **Kéo vào đoạn nghỉ:** dừng tại nghỉ, `offset = t - segment.start`, hiện cung đếm
  ngược; hết nghỉ thì sang chương sau. Đây là hành vi hiện tại
  (`beginRest(place.afterIndex, restAfterSec, place.offset)`), giữ nguyên.
- **Kéo vắt qua nghỉ:** không nhảy thẳng sang chương sau; thả tay trong nghỉ vẫn
  tính là đang nghỉ. Lý do: khớp `onWorkScrub` hôm nay và khớp `parked` +
  `restOffset` đã có trong `ReplayRoom`.
- **Thả tay khi đang không phát:** `onWorkScrub` hiện `clearRest()` sau `beginRest`,
  tức là không tự chạy tiếp. Giữ nguyên.
- **Bỏ** `onMovementScrub` và thanh Chương. `onStageRatio` vẫn là đường tua trong
  chương đang phóng — không đổi.
- **Test** (mở rộng `src/musicalize/seek.test.ts`): `workDuration` gồm nghỉ nhưng
  dừng ở nốt cuối; `placeOnWork` tại biên `start`/`end` của `audio` và `rest`;
  `workSecondsAt` clamp `restOffset`. Phần clamp hiển thị tách thành
  `clockText` và test ở `labels.test.ts` (mục 11).

**Popover `⚙` (`OptionsPopover.tsx`, mới).** `Humanize`, `Màu`, và (P2) `Chép liên
kết`. Nền `panel`, viền `hairline`, bo 4, rộng 240, neo dưới nút. Đóng bằng `Esc`,
bấm ra ngoài, hoặc chọn xong. Thay `disclosure` đang làm reflow cả dock.

### 5.5 Live (`LiveRoom.tsx`)

Không đổi logic. Chỉ dùng chung Topbar/Stage/Dock mới. Bỏ Guitar khỏi shelf (đã
đúng). Nút play khi chưa nối: chữ `NGHE ĐÀI`. Trạng thái `Đang nối…` chuyển thành
chữ `sans` 12 màu `textMuted` ở hàng transport, không dùng banner. Không đặt câu
tiếng Việt ở vai `mono` vì Menlo thiếu `ế/ấ` (xem mục 3).

## 6. Chuyển động

Dùng `react-native-reanimated` đã có. Tất cả ngắn, không nảy.

| Chỗ | Hiệu ứng | Thời lượng |
|---|---|---|
| Mọi `Pressable` | scale 0.97 → 1, opacity 0.9 | 120ms, ease-out |
| Đổi mã / khung / thể loại | chart crossfade + translateY 8 → 0 | 180ms |
| Chip đang chọn | vạch dưới scaleX 0 → 1 | 160ms |
| Playhead khi audible | chấm 6 → 8 → 6, 1.2s lặp | — |
| Dải khối lượng | cột mọc từ 0 mỗi lần đổi bài | 240ms, stagger 8ms |
| Nghỉ giữa chương | cung đếm ngược quét 360° | theo `restAfterSec` |
| Đang soạn | shimmer ngang | 1.2s lặp |
| Live | chấm opacity 1 ↔ 0.25 | 1.6s lặp |

Web: tôn trọng `prefers-reduced-motion` — tắt pulse/shimmer, giữ crossfade 0ms.

## 7. Bàn phím (web)

`src/musicalize/useKeyboard.ts` (mới). Gắn `window.addEventListener('keydown')` chỉ
khi `Platform.OS === 'web'`. Bỏ qua khi `event.target` là `input`, `textarea`,
`isContentEditable`, hoặc một phần tử tương tác (`button`, `[role="button"]`,
`[role="slider"]`, `a[href]`). Thiếu vế cuối thì `Space` trên một nút đang focus sẽ
vừa bấm nút vừa toggle play — toggle hai lần.

| Phím | Việc |
|---|---|
| `Space` / `K` | Phát / tạm dừng |
| `←` / `J` | Lùi 5 giây |
| `→` / `L` | Tới 5 giây |
| `Shift` + `←` / `→` | Chương trước / sau (chỉ khi nhiều chương) |
| `R` | Nghe lại |
| `1`–`5` | Chọn thể loại theo thứ tự shelf |
| `/` | Focus ô lọc mã |
| `M` | Tắt / bật tiếng |
| `Esc` | Đóng popover / bỏ focus |
| `⌘K` / `Ctrl+K` | Mở / đóng command palette |

Hiện gợi ý phím ở chân cột trái để người dùng biết mà dùng.

## 8. Deep link (P2)

`src/musicalize/link.ts` (mới). Chỉ web. Đọc/ghi `location.search` bằng
`history.replaceState`, không thêm router.

```
?s=MBB&r=1M&d=2026-10-30&g=guitar&e=torroba&h=1&c=1
```

| Khoá | Nghĩa | Mặc định |
|---|---|---|
| `s` | mã | `VNM` |
| `r` | khung `1D`–`1Y` | `1D` |
| `d` | ngày phiên (chỉ `1D`) | phiên mới nhất |
| `g` | thể loại | `symphony` |
| `e` | ensemble / nghệ sĩ | `classic` |
| `h` | humanize `1/0` | `1` |
| `c` | màu `1/0` | `1` |

Giá trị sai thì rơi về mặc định, không báo lỗi; `d` chỉ được đọc khi `r=1D`.
Ensemble không có trong `ENSEMBLE_ROWS[g]` thì về `classic`. Nút `Chép liên kết`
trong popover `⚙` ghi URL hiện tại vào clipboard, hiện `ĐÃ CHÉP` 2s, hoặc `THỬ LẠI`
khi trình duyệt chặn clipboard.

## 9. Dữ liệu

Không cần backend mới. Tái dùng:

| Việc | Nguồn đã có |
|---|---|
| Danh sách mã + tên + sàn | `fetchMarketSymbols()` → `MarketSymbol { symbol, name, exchange }` |
| Giá, %, sparkline cho cột trái | `fetchWatchlist(symbols)` → `Stock { price, changePercent, sparkline }` |
| Phiên, nến phút, khối lượng | `fetchSessions`, `fetchSessionMinutes` (đã dùng) |
| Chương, giọng, BPM | `fetchSpan`, `pieceCopy` (đã dùng) |
| `peaks` | `RecapManifest.peaks` (đã dùng) |

Thêm một request `fetchWatchlist` cho tối đa 12 mã, cache trong memory, 30s/lần.
Không đụng `fetchRecap`/`fetchSpan`.

## 10. Kế hoạch

### P0 — "hết wireframe" (~1–1,5 ngày)

Trọng tâm P0 là **cụm transport + tile thể loại** (phần "hết wireframe" chính).
Tick chương và tooltip dời sang P1 để P0 không phình.

- [x] `palette.ts`: thêm `panel`, `surfaceActive`, `hairline`, `hairlineStrong`, `textFaint`, `dataFill`, `soundSoft`; đổi `background`, `surface`.
- [x] `type.ts` mới: font role + scale theo bảng mục 3.
- [x] `TopBar.tsx` mới, gắn vào `RoomFrame.tsx`; bỏ `brand` khỏi `SymbolColumn`.
- [x] `Controls.tsx`: transport thành play tròn + `⟲` + clock; bỏ `ChipRow` lớn cho thể loại, thay tile; options vào popover.
- [x] `SymbolColumn.tsx`: hàng có tên công ty + sparkline + %, vạch trái khi chọn; bỏ `detail = span`.
- [x] `Scrubber.tsx`: gộp timeline (theo ánh xạ ở 5.4), `clockText` + `labels.test.ts`.
- [x] `Stage.tsx`: khối tiêu đề trên-trái, trục 4 nhãn bắt đầu `top: 32`, pill playhead clamp.
- [x] `useKeyboard.ts` + `useQuotes.ts`.
- [x] `Sparkline.tsx`: thêm prop tuỳ chọn `grid?: boolean`, `glow?: boolean`; mặc định `false` để terminal không đổi.
- [x] **A11y ngay khi tạo component:** `accessibilityLabel` + `accessibilityState` cho mọi `Pressable` mới, touch target ≥ 44. Không dồn sang P1.

**Xong khi:** không còn khối magenta nào lớn hơn một hàng; `Space` phát/tạm dừng;
đổi mã thấy tên công ty và %; không còn nhãn đè nhau; dock không có thanh cuộn;
`4:23 / 4:20` không còn; component mới đều có label.

### P1 — "nguy hiểm" (2–3 ngày)

- [x] Serif cho tên bài + dòng meta mono; badge mã.
- [x] Chart: lưới, 4 nhãn trục, glow đoạn đã phát, gradient theo playhead, dải khối lượng mới.
- [x] Tick chương + tooltip tên chương trên timeline; đoạn nghỉ vẽ rãnh `hairline`.
- [x] Trạng thái: trống, đang soạn (shimmer), nghỉ (cung đếm ngược), live (chấm + `TRỰC TIẾP`).
- [x] Motion theo mục 6, gồm `prefers-reduced-motion` (`motion.tsx`).
- [x] Narrow: stage 44vh trên, dock dính dưới, danh sách mã thành dải chip ngang.
- [x] Rà a11y toàn mặt nghe: focus ring 2px `hairlineStrong` trên web (`a11y.ts`), touch target ≥ 44, label/`accessibilityState` đã có từ P0.

**Xong khi:** ảnh chụp màn hình ở 1440px đọc được "phòng thu", không cần đọc chữ
vẫn biết đang phát hay dừng; chuyển mã có crossfade; mobile thấy chart ngay khi mở.

### P2 — "đắt tiền" (2 ngày)

- [x] Deep link + `Chép liên kết`: `link.ts` đọc/ghi `s/r/d/g/e/h/c`, `d` chỉ có nghĩa khi `1D`, giá trị sai rơi về mặc định; `replaceState` giữ URL luôn chia sẻ được; native giữ mặc định. `Chép liên kết` chỉ hiện khi có clipboard API.
- [x] Command palette `⌘K` (mã, thể loại, khung, ngày): `CommandPalette.tsx`; tìm không dấu (`foldText`); `↑↓` chọn, `↵` mở, `esc` đóng; mở từ nút `⌘K` trên TopBar hoặc `Meta/Ctrl+K`; `/` vẫn focus ô lọc.
- [ ] Cue legend (giai điệu / thanh khoản / breakout / scale) khi backend có cue track — đúng thứ tự ở `musicalize-plan.md`. **Hoãn:** không có track `cue` trong `backend/app` lẫn response recap/span, nên không dựng legend giả.
- [ ] Tuỳ chọn `expo-font` nếu muốn font display riêng. **Không cần:** stack Georgia-first ở `type.ts` đã phủ đủ dấu tiếng Việt; thêm font chỉ tăng bundle.
- [x] `M` tắt tiếng: `ReplayPlayer` nhận thêm prop `muted` (gán `player.muted` của expo-audio), nút loa cạnh `⟲`, label đổi `Tắt tiếng` / `Bật tiếng`.

## 11. File map

| File | Việc |
|---|---|
| `src/musicalize/palette.ts` | sửa — thêm token |
| `src/musicalize/type.ts` | mới — font + scale |
| `src/musicalize/TopBar.tsx` | mới — nút `⌘K` mở palette |
| `src/musicalize/OptionsPopover.tsx` | mới — humanize, màu, `Chép liên kết` |
| `src/musicalize/useKeyboard.ts` | mới — thêm `⌘K`, `M` |
| `src/musicalize/useQuotes.ts` | mới |
| `src/musicalize/link.ts` | mới (P2) — parse/format/read/write deep link |
| `src/musicalize/link.test.ts` | mới (P2) — test parse/format/fallback |
| `src/musicalize/motion.tsx` | mới (P1) — press/rise/crossfade/pulse + `prefers-reduced-motion` |
| `src/musicalize/a11y.ts` | mới (P1) — focus ring web `:focus-visible` |
| `src/musicalize/CommandPalette.tsx` | mới (P2) — palette mã / thể loại / khung / ngày |
| `src/musicalize/RoomFrame.tsx` | sửa — topbar, bỏ scroll dock, narrow mới |
| `src/musicalize/SymbolColumn.tsx` | sửa — hàng có dữ liệu, chip không tô |
| `src/musicalize/Controls.tsx` | sửa — shelf, transport, nút tắt tiếng, popover |
| `src/musicalize/Scrubber.tsx` | sửa — timeline gộp, tick chương, tooltip, rãnh nghỉ, `clockText` |
| `src/musicalize/Stage.tsx` | sửa — tiêu đề, trục, playhead, glow/gradient, trạng thái |
| `src/musicalize/labels.ts` | sửa — thêm `clockText`, `foldText` (hàm thuần) |
| `src/musicalize/labels.test.ts` | mới — test clamp giờ, bỏ dấu |
| `package.json` | sửa — `test:musicalize` chạy thêm `labels.test.ts`, `link.test.ts` |
| `src/components/Sparkline.tsx` | sửa — thêm prop optional, mặc định không đổi |
| `src/musicalize/ReplayRoom.tsx` | sửa — deep link, palette, mute; bỏ `onMovementScrub`, truyền `movements` cho timeline; giữ `onWorkScrub`/`onStageRatio` |
| `src/musicalize/ReplayPlayer.tsx` | sửa additive — prop `muted`, không đổi luồng phát/tua |
| `src/musicalize/LiveRoom.tsx` | chạm nhẹ — nhãn trạng thái |

Không sửa: `liveSynth.ts`, `seek.ts`, `program.ts`, `recapCursor.ts`, `backend/`.
`ReplayPlayer.tsx` chỉ nhận thêm prop `muted`; logic seek/finish giữ nguyên.

## 12. Rủi ro

- **Timeline gộp là rủi ro số một của đợt**, không phải việc trang trí. Ánh xạ dùng
  lại `seek.ts` nên không phải viết toán mới, nhưng hành vi kéo qua nghỉ, `parked`
  và `restOffset` phải khớp đúng mục 5.4 trước khi xoá `onMovementScrub`.
- **`Sparkline` dùng chung với terminal.** Mọi prop mới phải optional và mặc định
  giữ đúng hành vi cũ (`grid: false`, `glow: false`). Terminal không được đổi một pixel.
- **Thêm request cho cột trái.** Chỉ 12 mã, 30s, chỉ khi tab visible, lỗi thì ẩn.
  Không chặn render danh sách.
- **Không có OHLC** nên không có nến. Đừng thiết kế quanh nến.
- **Không có `expo-font`** nên serif là font hệ thống. Trên Android sẽ là `serif`
  thô hơn; chấp nhận ở P1, nâng ở P2.
- **`useMarketPolling` không dùng được** trong Musicalize (cần navigator).
- **Lệch đồng hồ `4:23 / 4:20`** có thể là lỗi thật trong `onTime`. P0 chỉ clamp
  hiển thị; nếu P1 vẫn thấy thì mở việc riêng, không vá trong tài liệu này.

## 13. Quyết định và câu hỏi mở

Đã chốt sau review:

1. **Phần trăm tăng/giảm dùng đơn sắc.** Dấu `▲/▼`, `text` khi tăng và `textMuted`
   khi giảm; hướng đọc lấy từ độ dốc sparkline. Không thêm xanh/đỏ, giữ đúng luật
   ba màu. Nếu sau này cần đọc nhanh bằng màu thì đó là một token mới trong
   `palette.ts`, không đổi bố cục.
2. **`peaks` không vào khung giá.** `docs/musicalize-plan.md` cấm theo nội dung,
   không theo màu: "Không vẽ `RecapManifest.peaks` trong cùng khung với đường cyan.
   Sóng `peaks` của phiên `1D` chỉ trên thanh Phiên", lặp ba lần. Bản này giữ
   nguyên luật đó: sóng chỉ sống trên timeline. Muốn vẽ nền sau đường giá thì phải
   sửa `musicalize-plan.md` trước, và đó là PR riêng — không nằm trong đợt này.

Còn mở:

3. ~~**Serif cho tên bài:**~~ Đã chốt: serif cổ điển, **Georgia** đứng đầu (đủ dấu
   tiếng Việt, vẽ cho màn hình), rồi Palatino và Times New Roman. Xem bảng chữ ở
   mục 3 và ghi chú kiểm tra `ạ ế đ ư ơ ộ ỹ ấ`.
