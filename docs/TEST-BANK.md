# VStock — Bộ Test Bank

> Tài liệu kiểm thử thủ công (manual QA) và tham chiếu test tự động cho toàn bộ tính năng app VStock.  
> Cập nhật: 2026-09-18 (đối chiếu code sau merge `main`: background alerts PR #5/#8)

Copy UI, hướng swipe, path API và expected dưới đây khớp implementation hiện tại. Tester chạy theo đúng chữ trên màn hình — không suy diễn “bell”, “Biến động”, hay path REST cũ.

---

## 1. Mục đích & phạm vi

| Hạng mục | Mô tả |
|----------|--------|
| **App mobile** | Expo (iOS / Android) — Watchlist, Detail, News, Companion (Vy), Cảnh báo giá, Health |
| **Backend** | FastAPI `/v1/*` — quotes, history, news, symbols, companion |
| **Ngoài phạm vi** | Portfolio, nhân vật Companion thứ 2/3 (backlog), thanh toán |

**Mục tiêu:** Một tester có thể chạy tuần tự các case dưới đây để xác nhận regression trước release (TestFlight / production).

---

## 2. Môi trường & chuẩn bị

### 2.1. Backend local

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Kiểm tra nhanh: `curl http://localhost:8000/health` → `200`.

### 2.2. App mobile

```bash
cp .env.example .env
# Simulator: EXPO_PUBLIC_API_URL=http://localhost:8000
# Device thật (LAN): EXPO_PUBLIC_API_URL=http://<LAN-IP>:8000
npm start
```

| Biến môi trường | Ghi chú |
|-----------------|---------|
| `EXPO_PUBLIC_API_URL` | URL backend (dòng active trong `.env.example`) |
| `EXPO_PUBLIC_DEVICE_API_URL` | Optional — device thật khi Metro tunnel; không bắt buộc nếu đã set LAN IP |
| `GEMINI_API_KEY` | Backend process env (không phải Expo `.env`) — bắt buộc cho Companion chat live |
| `APP_VARIANT=development` | **Process env** cho script/EAS (`npm run start:dev`, `ios:dev`, …) — **không** có trong `.env.example` |

**Android emulator:** client tự rewrite `localhost` → `http://10.0.2.2:8000`. Không cần set tay `10.0.2.2` trừ khi muốn override.

**Dev client (background alerts):** `APP_VARIANT=development npm run start:dev` (hoặc `ios:dev` / `android:dev`). Expo Go chỉ test logic + in-app `Alert`.

### 2.3. Thiết bị khuyến nghị

| # | Thiết bị | Lý do |
|---|----------|-------|
| 1 | iOS Simulator | Luồng cơ bản, localhost |
| 2 | iPhone thật (dev build) | Push notification / background alerts |
| 3 | Android emulator hoặc device | Emulator dùng `10.0.2.2` tự động; device dùng LAN IP |

### 2.4. Dữ liệu test chuẩn

| Loại | Giá trị | Ghi chú |
|------|---------|---------|
| Mã HOSE phổ biến | `FPT`, `VNM`, `VCB`, `HPG` | Có quote + fundamentals |
| Mã biến động | Tuỳ phiên | Dùng khi test sort / nudge |
| Chỉ số | `VNINDEX`, `HNX` | Detail dạng index-like |
| Hàng hóa | `XAU`, `WTI` | Strip label **Vàng** / **Dầu**; Detail USD, index-like (không nút cảnh báo) |
| Tìm kiếm | `fpt`, `FPT`, `Vinamilk` | Case-insensitive / tên công ty — dùng FAB **+** (add mode) |
| Mã không tồn tại | `ZZZZZ` | Empty / 404 |
| Watchlist mặc định | `VNM`, `FPT`, `VIC`, `HPG`, `MWG`, `VCB`, `TCB`, `MBB`, `GAS`, `MSN` | `DEFAULT_SYMBOLS` sau cài mới |

### 2.5. Phiên giao dịch (VN)

| Khung giờ | Hành vi mong đợi |
|-----------|------------------|
| **Trong phiên** (T2–T6, 9:00–11:30 & 13:00–14:45, `Asia/Ho_Chi_Minh`) | Poll quotes ~30s khi màn hình focus |
| **Ngoài phiên** | Watchlist **không** poll tự động; pull-to-refresh vẫn fetch. Detail hàng hóa (XAU/WTI) vẫn poll |
| Label phiên (client) | `đang giao dịch` / `ngoài giờ` (`marketSessionLabel`) |
| Strip Watchlist | Trong phiên: **`Live · 30s`**. Ngoài phiên: **`ngoài giờ`**. Cache/fallback: **`Offline`**. Không có label “Nghỉ trưa” |

---

## 3. Ma trận ưu tiên

| Mức | Ý nghĩa |
|-----|---------|
| **P0** | Blocker — không ship nếu fail |
| **P1** | Quan trọng — fix trước release |
| **P2** | Nên có — có thể defer ngắn hạn |

| Module | P0 | P1 | P2 |
|--------|----|----|-----|
| Watchlist & tìm kiếm | ✓ | ✓ | ✓ |
| Chi tiết mã / chart | ✓ | ✓ | ✓ |
| Tin tức | | ✓ | ✓ |
| Cảnh báo giá | ✓* | ✓ | |
| Companion Vy | ✓** | ✓ | ✓ |
| Health / API | ✓ | | |
| Offline / cache | | ✓ | ✓ |

\* P0 trên dev build có notification; Expo Go = logic + in-app Alert.  
\** P0 khi `GEMINI_API_KEY` đã cấu hình trên server.

---

## 4. Test cases — Watchlist (Màn Theo dõi)

### VS-WL-001 — Khởi động lần đầu
| | |
|---|---|
| **Priority** | P0 |
| **Precondition** | Cài app mới / xóa data app |
| **Steps** | 1. Mở app lần đầu<br>2. Chờ load xong |
| **Expected** | Watchlist mặc định (`VNM`…`MSN`); strip VNINDEX / HNX / Vàng / Dầu; giá + % thay đổi; sparkline; không crash |

### VS-WL-002 — Pull to refresh
| | |
|---|---|
| **Priority** | P0 |
| **Steps** | Kéo xuống refresh trên Watchlist |
| **Expected** | Spinner refresh; giá cập nhật; tin preview (nếu có) reload |

### VS-WL-003 — Poll trong phiên
| | |
|---|---|
| **Priority** | P1 |
| **Precondition** | Trong phiên giao dịch, màn Watchlist đang focus |
| **Steps** | Giữ màn ~1 phút, quan sát giá |
| **Expected** | Giá/sparkline cập nhật định kỳ (~30s); strip hiện **`Live · 30s`** |

### VS-WL-004 — Không poll ngoài phiên
| | |
|---|---|
| **Priority** | P1 |
| **Precondition** | Ngoài giờ giao dịch |
| **Steps** | Giữ màn 2 phút không refresh |
| **Expected** | Giá watchlist không tự đổi; strip **`ngoài giờ`** (hoặc `Offline` nếu cache); pull-to-refresh vẫn fetch được |

### VS-WL-005 — Chỉ số thị trường (VNINDEX / HNX)
| | |
|---|---|
| **Priority** | P1 |
| **Steps** | Tap chip VNINDEX hoặc HNX trên summary strip |
| **Expected** | Navigate Detail; chart + OHLC; **không** có nút `Cảnh báo` |

### VS-WL-006 — Hàng hóa (XAU / WTI)
| | |
|---|---|
| **Priority** | P2 |
| **Steps** | Tap chip **Vàng** (`XAU`) hoặc **Dầu** (`WTI`) trên strip |
| **Expected** | Detail giá `$`; chart load; **không** có nút `Cảnh báo` (index-like). Trên Detail, quote/chart 1D **poll cả ngoài phiên VN**. Strip Watchlist **không** poll hàng hóa độc lập ngoài phiên — chỉ refresh cùng poll watchlist / pull-to-refresh |

### VS-WL-007 — Sort theo % thay đổi
| | |
|---|---|
| **Priority** | P1 |
| **Steps** | Chọn chip sort **`% Thay đổi`** (mặc định) |
| **Expected** | Section **Tăng giá** / **Giảm giá** / **Đi ngang**; mã ghim ở **Đã ghim** |

### VS-WL-008 — Sort theo mã
| | |
|---|---|
| **Priority** | P2 |
| **Steps** | Chọn chip sort **`Mã`** |
| **Expected** | Một section **Danh sách theo dõi**; ghim lên đầu, phần còn lại A→Z |

### VS-WL-009 — Ghim mã (vuốt phải)
| | |
|---|---|
| **Priority** | P1 |
| **Steps** | Vuốt **phải** trên một dòng → **Ghim** |
| **Expected** | Mã lên section **Đã ghim**; vuốt phải lại → **Bỏ ghim** hoạt động |

### VS-WL-010 — Cảnh báo từ swipe (vuốt trái)
| | |
|---|---|
| **Priority** | P1 |
| **Steps** | Vuốt **trái** → **Cảnh báo** |
| **Expected** | Mở AlertSheet với giá hiện tại; điều kiện **Trên mức** / **Dưới mức**; lưu được alert |

### VS-WL-011 — Xóa mã (vuốt trái)
| | |
|---|---|
| **Priority** | P1 |
| **Steps** | Vuốt **trái** → **Xóa** |
| **Expected** | Mã biến mất khỏi list active; persist sau kill app |

### VS-WL-012 — Chế độ sửa (edit)
| | |
|---|---|
| **Priority** | P2 |
| **Steps** | Tap **Sửa** trên hàng sort chips (đổi thành **Xong** khi đang edit) |
| **Expected** | UI edit; xóa mã bằng nút **−** hoạt động |

### VS-WL-013 — Thêm mã (FAB +)
| | |
|---|---|
| **Priority** | P0 |
| **Steps** | 1. Tap FAB **`+`** (góc phải, mở add mode)<br>2. Placeholder **Thêm mã từ HOSE / HNX…**<br>3. Gõ `FPT`<br>4. Trên `SearchResultRow`, tap nút **`+` bên phải** để thêm (không tap cả dòng) |
| **Expected** | Kết quả hiện tên + sàn; hint `N kết quả · chạm + để thêm`. Nút **`+`** thêm vào list (đổi thành **✓**); tap **✓** gỡ khỏi list. **Tap dòng** (tên/mã) mở Detail — không thêm mã |

### VS-WL-014 — Tìm kiếm theo tên công ty
| | |
|---|---|
| **Priority** | P1 |
| **Steps** | FAB **+** → gõ `Vinamilk` hoặc `fpt` (chữ thường) |
| **Expected** | Trả về `VNM` / `FPT` tương ứng |

### VS-WL-015 — Tìm mã không tồn tại
| | |
|---|---|
| **Priority** | P2 |
| **Steps** | FAB **+** → gõ `ZZZZZ` |
| **Expected** | 0 kết quả / không crash |

### VS-WL-016 — Mở chi tiết mã
| | |
|---|---|
| **Priority** | P0 |
| **Steps** | Tap một dòng cổ phiếu |
| **Expected** | Navigate Detail với đúng symbol |

### VS-WL-017 — Preview tin tức (5 bài)
| | |
|---|---|
| **Priority** | P1 |
| **Steps** | Scroll tới section tin; tap một bài |
| **Expected** | Mở in-app browser nếu có URL; hoặc Detail mã liên quan nếu không URL nhưng có `symbols` |

### VS-WL-018 — "Xem tất cả"
| | |
|---|---|
| **Priority** | P1 |
| **Steps** | Tap link **Xem tất cả** sang màn News |
| **Expected** | Navigate News với animation `slide_from_right` |

### VS-WL-019 — Nhiều watchlist — tạo mới
| | |
|---|---|
| **Priority** | P1 |
| **Steps** | Menu ⋯ → **Quản lý danh sách** → Tạo list mới |
| **Expected** | List mới xuất hiện trên picker; tên mặc định dạng `Danh sách N`; có thể đặt tên |

### VS-WL-020 — Chuyển watchlist active
| | |
|---|---|
| **Priority** | P1 |
| **Steps** | Tap chip watchlist khác trên picker |
| **Expected** | Symbol list + giá đổi theo list; `activeId` persist |

### VS-WL-021 — Đổi tên / xóa watchlist
| | |
|---|---|
| **Priority** | P2 |
| **Steps** | Quản lý danh sách → rename / delete |
| **Expected** | Rename hiển thị ngay. Delete list đang active → chuyển sang list còn lại (`lists[0]`). **Không xóa được list cuối** (`lists.length <= 1` bị chặn; UI ẩn nút xóa) |

### VS-WL-022 — Banner API lỗi
| | |
|---|---|
| **Priority** | P1 |
| **Precondition** | Tắt backend hoặc sai `EXPO_PUBLIC_API_URL`; chưa có cache |
| **Steps** | Mở Watchlist |
| **Expected** | Banner **Không kết nối được máy chủ — đang hiển thị dữ liệu mẫu** + **Thử lại**; fallback `FALLBACK_WATCHLIST` |

### VS-WL-023 — Offline cache
| | |
|---|---|
| **Priority** | P1 |
| **Precondition** | Đã load thành công ít nhất 1 lần |
| **Steps** | Ngắt mạng → mở lại Watchlist |
| **Expected** | Banner **Dữ liệu đã lưu · cập nhật …**; hiển thị cache |

### VS-WL-024 — Cảnh báo khi mã chưa có giá
| | |
|---|---|
| **Priority** | P2 |
| **Precondition** | Mã `unavailable` hoặc price = 0 |
| **Steps** | Vuốt trái → **Cảnh báo** |
| **Expected** | `Alert.alert('Chưa có giá', 'Không đặt cảnh báo khi mã chưa có dữ liệu live.')` — không mở sheet |

### VS-WL-025 — Lọc list hiện tại (header ⌕)
| | |
|---|---|
| **Priority** | P1 |
| **Steps** | 1. Tap ⌕ trên header (label: Tìm trong danh sách)<br>2. Placeholder **Lọc danh sách theo dõi…**<br>3. Gõ prefix một mã đang có trong list |
| **Expected** | Chỉ lọc list hiện tại — **không** mở search toàn thị trường / không thêm mã mới. Huỷ đóng ô lọc |

---

## 5. Test cases — Chi tiết mã (Detail)

### VS-DTL-001 — Load detail cổ phiếu
| | |
|---|---|
| **Priority** | P0 |
| **Steps** | Mở Detail `FPT` |
| **Expected** | Tên công ty, giá, % đổi, chart 1D, stats (P/E, P/B, EPS, ROE…), tin theo mã |

### VS-DTL-002 — Chart range 1D / 1W / 1M / 3M / 1Y / 5Y
| | |
|---|---|
| **Priority** | P0 |
| **Steps** | Lần lượt chọn từng range trên chart |
| **Expected** | Chart vẽ lại; loading ngắn lần đầu; lần sau dùng cache |

### VS-DTL-003 — Poll chart 1D trong phiên
| | |
|---|---|
| **Priority** | P1 |
| **Precondition** | Trong phiên, range = 1D |
| **Steps** | Giữ Detail ~6 phút |
| **Expected** | Chart 1D refresh ~5 phút |

### VS-DTL-004 — Recent symbols (chưa có UI)
| | |
|---|---|
| **Priority** | P2 |
| **Steps** | Mở 3 mã khác nhau → quay Watchlist / mở lại Detail |
| **Expected** | **Không** có row “Gần đây” / “Xem gần đây” trên UI (`RecentSymbolsRow` chưa mount). App không crash. Storage `vstock.recent.symbols` vẫn ghi (tối đa 10) — backlog UI, **không file bug thiếu row** |

### VS-DTL-005 — Tin theo mã
| | |
|---|---|
| **Priority** | P1 |
| **Steps** | Scroll tin trên Detail; tap bài |
| **Expected** | In-app browser (page sheet) nếu có URL; không crash khi thiếu URL |

### VS-DTL-006 — Đặt cảnh báo từ Detail
| | |
|---|---|
| **Priority** | P1 |
| **Steps** | Tap nút text **Cảnh báo** (không phải icon bell) → chọn **Trên mức** / **Dưới mức** + giá → **Lưu cảnh báo** |
| **Expected** | Alert lưu AsyncStorage; hiện trong **Quản lý cảnh báo**; `lastSeenPrice` gắn giá live lúc lưu |

### VS-DTL-007 — Detail chỉ số VNINDEX
| | |
|---|---|
| **Priority** | P1 |
| **Steps** | Mở `VNINDEX` |
| **Expected** | Stats Mở/Cao/Thấp/Đóng; **không** P/E / KQKD; **không** nút `Cảnh báo` |

### VS-DTL-008 — Detail hàng hóa XAU
| | |
|---|---|
| **Priority** | P2 |
| **Steps** | Mở `XAU` (từ chip Vàng) |
| **Expected** | Giá `$`; poll ngoài phiên VN; OHLC-only (index-like); **không** nút `Cảnh báo`, **không** P/E / KQKD. WTI tương tự |

### VS-DTL-009 — KQKD / income block
| | |
|---|---|
| **Priority** | P2 |
| **Steps** | Mở mã cổ phiếu có income (vd. FPT, VNM) |
| **Expected** | Heading **Kết quả kinh doanh**; Doanh thu / LNST hiện số hoặc **—** nếu thiếu data |

### VS-DTL-010 — Back navigation
| | |
|---|---|
| **Priority** | P0 |
| **Steps** | Tap **‹ Watchlist** |
| **Expected** | Về Watchlist; state watchlist giữ nguyên |

### VS-DTL-011 — Offline cache detail
| | |
|---|---|
| **Priority** | P1 |
| **Steps** | Load FPT online → offline → mở lại FPT |
| **Expected** | Cache detail + banner **Dữ liệu đã lưu · cập nhật …** |

---

## 6. Test cases — Tin tức (News)

### VS-NEWS-001 — Load tin thị trường
| | |
|---|---|
| **Priority** | P1 |
| **Steps** | Mở News từ Watchlist (**Xem tất cả**) |
| **Expected** | Danh sách tin load; skeleton biến mất |

### VS-NEWS-002 — Filter chips
| | |
|---|---|
| **Priority** | P1 |
| **Steps** | Lần lượt chọn: **Tất cả**, **Chứng khoán**, **Kinh tế**, **Doanh nghiệp**, **Vàng · HH**, **BĐS**, **Công bố** |
| **Expected** | List lọc đúng category; haptic khi đổi filter |

### VS-NEWS-003 — Pull to refresh
| | |
|---|---|
| **Priority** | P1 |
| **Steps** | Kéo refresh |
| **Expected** | Tin mới fetch (bypass cache 15 phút khi refresh) |

### VS-NEWS-004 — Mở bài báo
| | |
|---|---|
| **Priority** | P1 |
| **Steps** | Tap một NewsRow có URL |
| **Expected** | In-app browser (page sheet) |

### VS-NEWS-005 — Tin không URL → Detail
| | |
|---|---|
| **Priority** | P2 |
| **Precondition** | Item có `symbols` nhưng không URL |
| **Steps** | Tap item |
| **Expected** | Navigate Detail symbol đầu tiên |

### VS-NEWS-006 — Back về Watchlist
| | |
|---|---|
| **Priority** | P0 |
| **Steps** | Tap **‹ Theo dõi** |
| **Expected** | Về Watchlist |

---

## 7. Test cases — Cảnh báo giá (Price Alerts)

> **Lưu ý:** Background push cần **EAS dev build** (`docs/EAS-DEV-BUILD.md`). Expo Go: in-app `Alert` khi app **active**; **không** local push.

Hai đường background (dev build):
1. **AppState** — `useBackgroundPriceAlerts`: khi rời foreground (`next === 'background'`, gồm iOS `inactive → background`) chạy một pass `runPriceAlertCheck` ngay.
2. **OS background task** — `PRICE_ALERT_BACKGROUND_TASK`, `minimumInterval: 15` phút, chỉ khi có alert enabled + notification permission.

Android channel: `channelId = price-alerts`, tên **Cảnh báo giá**.

### VS-ALT-001 — Tạo alert "trên" (above)
| | |
|---|---|
| **Priority** | P0 |
| **Steps** | Đặt alert FPT **Trên mức** = giá hiện tại + 5% |
| **Expected** | Lưu thành công; hiện trong sheet **Quản lý cảnh báo** |

### VS-ALT-002 — Tạo alert "dưới" (below)
| | |
|---|---|
| **Priority** | P0 |
| **Steps** | Đặt alert **Dưới mức** giá −5% |
| **Expected** | Lưu OK |

### VS-ALT-003 — Bật / tắt alert
| | |
|---|---|
| **Priority** | P1 |
| **Steps** | Toggle enabled trong ManageAlertsSheet |
| **Expected** | Trạng thái persist; tắt = không trigger |

### VS-ALT-004 — Sửa ngưỡng / bật lại (re-arm)
| | |
|---|---|
| **Priority** | P1 |
| **Steps** | 1. Đổi price threshold và lưu<br>2. Tắt rồi bật lại alert |
| **Expected** | Cả hai thao tác **re-arm** `lastSeenPrice` từ giá live hiện tại (không fire ngay nếu giá đã qua ngưỡng) |

### VS-ALT-005 — Xóa alert
| | |
|---|---|
| **Priority** | P1 |
| **Steps** | Xóa từ sheet |
| **Expected** | Biến mất; không notify |

### VS-ALT-006 — Trigger trong app (foreground)
| | |
|---|---|
| **Priority** | P1 |
| **Precondition** | Alert above với ngưỡng gần giá thị trường |
| **Steps** | Poll giá cho đến khi **cắt qua** ngưỡng (từ phía còn lại) |
| **Expected** | Dev build: local notification. Expo Go + app active: in-app `Alert` (`Cảnh báo {symbol}`) |

### VS-ALT-007 — Trigger khi đưa app ra background (dev build)
| | |
|---|---|
| **Priority** | P0* |
| **Precondition** | Dev build + quyền notification; alert gần cross |
| **Steps** | Đặt alert → đưa app **background** (iOS: home / app switcher, đi qua `inactive` rồi `background`) → chờ giá cross **hoặc** cross sẵn rồi background ngay |
| **Expected** | Pass AppState chạy ngay khi vào `background` → local push nếu đủ điều kiện cross. Không phụ thuộc đợi 15 phút |

### VS-ALT-008 — Không trigger khi đã qua ngưỡng lúc tạo
| | |
|---|---|
| **Priority** | P1 |
| **Steps** | Tạo alert **Trên mức** với giá **thấp hơn** giá hiện tại |
| **Expected** | Không fire ngay. Sheet cảnh báo: *Giá hiện tại đã qua mức này. Cảnh báo sẽ chờ giá cắt lại từ phía còn lại.* (đúng mức: *Giá đang đúng mức này. Cảnh báo sẽ báo khi giá cắt qua, không báo ngay.*) |

### VS-ALT-009 — Menu Quản lý cảnh báo
| | |
|---|---|
| **Priority** | P1 |
| **Steps** | Watchlist ⋯ → **Quản lý cảnh báo** |
| **Expected** | Sheet liệt kê tất cả alerts |

### VS-ALT-010 — Background task 15 phút (dev build)
| | |
|---|---|
| **Priority** | P1 |
| **Precondition** | Dev build, có ≥1 alert enabled, đã cấp notification |
| **Steps** | Để app bị OS suspend lâu (không chỉ AppState mới rời foreground) |
| **Expected** | Task `vstock-price-alert-check` có thể chạy theo `minimumInterval` 15 phút. Không alert enabled → task unregister |

### VS-ALT-011 — Delivery: Expo Go vs native vs Android channel
| | |
|---|---|
| **Priority** | P1 |
| **Steps** | So sánh cùng alert trên Expo Go và EAS dev build (iOS + Android) |
| **Expected** | Expo Go: **không** push, chỉ in-app Alert khi active. Dev build: native notification. Android: channel **Cảnh báo giá** (`price-alerts`) |

---

## 8. Test cases — Companion AI (Vy)

> Backend cần `GEMINI_API_KEY`. Không có key → chat trả 503 (expected local).

### VS-CMP-001 — Mở chat từ FAB
| | |
|---|---|
| **Priority** | P0 |
| **Steps** | Tap FAB Vy **góc trái** (FAB **+** ở góc phải) |
| **Expected** | Modal CompanionChat `slide_from_bottom`; greeting lần đầu |

### VS-CMP-002 — Welcome back
| | |
|---|---|
| **Priority** | P2 |
| **Precondition** | Đã chat trước đó; đóng app > **8 giờ** (`WELCOME_BACK_GAP_MS`) |
| **Steps** | Mở lại chat |
| **Expected** | Bubble welcome back thay vì greeting mới |

### VS-CMP-003 — Gửi tin nhắn text
| | |
|---|---|
| **Priority** | P0 |
| **Steps** | Nhập "Xin chào" → Gửi |
| **Expected** | Presence lần lượt **đang đọc…** → **đang lấy giá…** → **đang gõ…** (idle: **đang online**); reply stream/reveal; không crash |

### VS-CMP-004 — 5 câu hỏi lõi (gõ tay)
| | |
|---|---|
| **Priority** | P0 |
| **Steps** | **Gõ tay** lần lượt (chat **không** render quick-suggestion chips — backend có `suggestions` tối đa 4 nhưng UI chưa dùng):<br>• Watchlist hôm nay thế nào?<br>• Tại sao {mã} biến động?<br>• Tin đáng chú ý?<br>• {mã} định giá / KQKD?<br>• Nên giữ hay gỡ mã nào? |
| **Expected** | Vy trả lời có context thị trường; không bịa số khi thiếu data; không khuyến nghị mua/bán cứng |

### VS-CMP-005 — Nudge trên Watchlist
| | |
|---|---|
| **Priority** | P1 |
| **Precondition** | Có biến động watchlist / recall event |
| **Steps** | Quan sát bubble nudge phía trên FAB Vy (trái) |
| **Expected** | Message + quick replies (có thể gồm mood **Bình thường** / **Hơi lo** / **Khỏe**); tap chip mở chat với seed message |

### VS-CMP-006 — Nudge trên Detail
| | |
|---|---|
| **Priority** | P1 |
| **Steps** | Xem Detail một mã vài lần → quan sát nudge |
| **Expected** | Nudge liên quan symbol / recall |

### VS-CMP-007 — Profile Vy
| | |
|---|---|
| **Priority** | P2 |
| **Steps** | Tap avatar/header → mở profile modal |
| **Expected** | Bio, expertise, bond info (ô “Vy gọi mình là”) |

### VS-CMP-008 — Đặt nickname ("gọi tôi là …")
| | |
|---|---|
| **Priority** | P2 |
| **Steps** | Chat "Gọi tôi là Minh" hoặc set trong profile |
| **Expected** | Bond nickname lưu local; Vy dùng tên trong các phiên sau |

### VS-CMP-009 — Activity history
| | |
|---|---|
| **Priority** | P2 |
| **Steps** | Thêm/xóa mã qua Vy (có confirm) → xem profile activity |
| **Expected** | Activity log cập nhật |

### VS-CMP-010 — Propose thêm mã (confirm sheet)
| | |
|---|---|
| **Priority** | P0 |
| **Steps** | Chat "Thêm VCB vào watchlist" |
| **Expected** | Sheet **Xác nhận thao tác**. Confirm = nút label hành động (vd. **Thêm VCB vào “…”**) — **không** có nút “Chấp nhận”. **Huỷ** → không đổi list |

### VS-CMP-011 — Propose xóa mã
| | |
|---|---|
| **Priority** | P0 |
| **Steps** | Chat "Xóa FPT khỏi watchlist" |
| **Expected** | Sheet **Xác nhận xóa mã**; chỉ xóa khi tap nút hành động; **Huỷ** giữ nguyên |

### VS-CMP-012 — Tạo watchlist mới qua Vy
| | |
|---|---|
| **Priority** | P1 |
| **Steps** | "Tạo list mới tên Bluechips" |
| **Expected** | Picker/confirm → list mới trên app |

### VS-CMP-013 — Intent guard — performance ≠ status
| | |
|---|---|
| **Priority** | P1 |
| **Steps** | Hỏi "Watchlist hôm nay thế nào?" |
| **Expected** | Trả lời phân tích, **không** hiện pop-up mutate watchlist |

### VS-CMP-014 — Intent guard — KQKD ≠ xóa mã
| | |
|---|---|
| **Priority** | P1 |
| **Steps** | Hỏi "FPT KQKD thế nào?" |
| **Expected** | Giải thích số liệu; không trigger remove |

### VS-CMP-015 — Không khuyến nghị mua/bán
| | |
|---|---|
| **Priority** | P0 |
| **Steps** | Hỏi "Nên mua FPT không?" |
| **Expected** | Từ chối khuyến nghị; góc nhìn tham khảo. UI có disclaimer Vy không đưa khuyến nghị mua/bán |

### VS-CMP-016 — Lỗi API / không Gemini key
| | |
|---|---|
| **Priority** | P1 |
| **Steps** | Chat khi backend 503 |
| **Expected** | Error bubble trong UI; `busy` được clear — không treo vô hạn |

### VS-CMP-017 — Đóng chat
| | |
|---|---|
| **Priority** | P0 |
| **Steps** | Swipe down / nút đóng |
| **Expected** | Về màn trước; lịch sử chat persist |

### VS-CMP-018 — FlatList khi stream dài
| | |
|---|---|
| **Priority** | P2 |
| **Steps** | Hỏi câu dài trigger multi-bubble |
| **Expected** | Scroll mượt; bubble reveal tuần tự |

---

## 9. Test cases — Nguồn dữ liệu (Health)

### VS-HLT-001 — Mở màn Health
| | |
|---|---|
| **Priority** | P1 |
| **Steps** | Watchlist ⋯ → **Nguồn dữ liệu** |
| **Expected** | Load `GET /v1/health/sources`. Back: **← Quay lại** |

### VS-HLT-002 — Hiển thị provider status
| | |
|---|---|
| **Priority** | P1 |
| **Steps** | Xem card **Tổng quan** rồi danh sách **Providers** |
| **Expected** | Tổng quan **Trạng thái** in hoa: **OK** / **DEGRADED** / **DOWN** / **UNKNOWN** (`toUpperCase()`). Từng provider hiện **chữ thường**: `ok` / `degraded` / `down` / `unknown` (xanh / cam / đỏ). Có thể kèm `· stale` và `lastError` |

### VS-HLT-003 — Store counts
| | |
|---|---|
| **Priority** | P2 |
| **Steps** | Kiểm tra kho SQLite: Giá, Tin tức, Chỉ số, Lịch sử, Mã CK, Cơ bản |
| **Expected** | Số > 0 sau ingestion chạy |

### VS-HLT-004 — Pull refresh Health
| | |
|---|---|
| **Priority** | P2 |
| **Steps** | Kéo refresh |
| **Expected** | Data cập nhật; card Phiên **Đang mở** / **Đóng cửa**; Jobs nền nếu có |

### VS-HLT-005 — API URL khi lỗi
| | |
|---|---|
| **Priority** | P2 |
| **Precondition** | Backend down / sai URL |
| **Steps** | Mở Nguồn dữ liệu |
| **Expected** | Error box **Không kết nối được máy chủ** + dòng **`API: {getApiUrl()}`**. Khi healthy, **không** có footer URL thường trực |

---

## 10. Test cases — Backend API

Chạy khi backend local port 8000. Có thể dùng `curl` hoặc Postman.

### VS-API-001 — Health
```bash
curl -s http://localhost:8000/health
```
**Expected:** `200`, body `{"status":"ok","service":"vstock-api"}`.

### VS-API-002 — Symbols list
```bash
curl -s "http://localhost:8000/v1/symbols" | head -c 200
```
**Expected:** ~700 mã HOSE+HNX.

### VS-API-003 — Symbol search
```bash
curl -s "http://localhost:8000/v1/symbols/search?q=FPT"
```
**Expected:** FPT trong kết quả.

### VS-API-004 — Watchlist batch
```bash
curl -s "http://localhost:8000/v1/watchlist?symbols=VNM,FPT,HPG"
```
**Expected:** 3 items, price + sparkline.

### VS-API-005 — Stock detail
```bash
curl -s "http://localhost:8000/v1/stocks/FPT"
```
**Expected:** quote + fundamentals fields.

### VS-API-006 — History ranges
```bash
for r in 1D 1W 1M 3M 1Y 5Y; do
  curl -s -o /dev/null -w "$r: %{http_code}\n" \
    "http://localhost:8000/v1/stocks/FPT/history?range=$r"
done
```
**Expected:** Tất cả `200`, mảng closes.

### VS-API-007 — Market indices
```bash
curl -s "http://localhost:8000/v1/indices"
```
**Expected:** Quotes **VNINDEX**, **HNX**, **XAU**, **WTI** trong `items`. (**Không** dùng `/v1/market/indices`.)

### VS-API-008 — Market news
```bash
curl -s "http://localhost:8000/v1/news/market?limit=5"
```
**Expected:** Array NewsItem.

### VS-API-009 — Symbol news
```bash
curl -s "http://localhost:8000/v1/news/symbols/FPT?limit=5"
```
**Expected:** Tin liên quan FPT.

### VS-API-010 — Health sources
```bash
curl -s "http://localhost:8000/v1/health/sources"
```
**Expected:** providers + store stats.

### VS-API-011 — Companion health
```bash
curl -s "http://localhost:8000/v1/companion/health"
```
**Expected:** `200`, gemini configured flag.

### VS-API-012 — Companion nudge
Nudge chỉ `show: true` khi đủ điều kiện (`should_offer_nudge`): **3× `view_detail` cùng mã trong 15 phút**, hoặc mover `|changePercent| ≥ 2%`, hoặc `avgChange ≥ 1.5%`, hoặc `nudgeKind=recall`. Một event `ts` cũ (vd. 2023) → thường `show: false`.

Copy payload `smoke_companion.py` (3 event `now`):

```bash
now=$(($(date +%s) * 1000))
curl -s -X POST "http://localhost:8000/v1/companion/nudge" \
  -H "Content-Type: application/json" \
  -d "{\"events\":[
    {\"type\":\"view_detail\",\"symbol\":\"HAG\",\"ts\":$now},
    {\"type\":\"view_detail\",\"symbol\":\"HAG\",\"ts\":$((now-1000))},
    {\"type\":\"view_detail\",\"symbol\":\"HAG\",\"ts\":$((now-2000))}
  ],\"context\":{\"screen\":\"Detail\",\"symbol\":\"HAG\"}}"
```
**Expected:** `200`, `show: true`, có `message`.

### VS-API-013 — Companion chat (non-stream)
```bash
curl -s -X POST "http://localhost:8000/v1/companion/chat" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"xin chào"}],"stream":false}'
```
**Expected:** `200` nếu có Gemini key; `503` nếu không.

### VS-API-014 — Invalid / unavailable symbol
```bash
curl -s -o /dev/null -w "%{http_code}\n" "http://localhost:8000/v1/stocks/ZZZZZ"
```
**Expected:**
- Symbol không có trong meta: **`404`** `Symbol not found`
- Có meta, chưa có quote: **`200`** với `price: 0`, `unavailable: true`
- History rỗng: **`404`** `No history for …`

### VS-API-015 — Market status
```bash
curl -s "http://localhost:8000/v1/market/status"
```
**Expected:** `200`; `open` boolean; `session` label backend (`open`/`closed`).

---

## 11. Test tự động (Automated)

### 11.1. Frontend — Price alert logic

```bash
npm run test:alerts
```

**Phạm vi:** `roundAlertPrice`, `shouldTriggerPriceAlert`, cross detection, merge alerts.

### 11.2. Backend — Companion intent

```bash
cd backend && python -m pytest tests/test_companion_intent.py -q
```

**Phạm vi:** Parse intent, gate tools, confidence rules.

### 11.3. Backend — Companion core answers

```bash
cd backend && python -m pytest tests/test_companion_core_answers.py -q
```

**Phạm vi:** Knowledge pack, news payload, quick suggestions, intent guards.

### 11.4. Backend — Companion smoke

```bash
cd backend && python scripts/smoke_companion.py
```

**Phạm vi:** Health, nudge, scrub advice, chat status.

### 11.5. Chạy tất cả automated

```bash
npm run test:alerts && \
(cd backend && python -m pytest tests/ -q && python scripts/smoke_companion.py)
```

---

## 12. Regression checklist (Pre-release)

Đánh dấu ✅ sau khi pass trên **iOS dev build** + **backend production/staging**:

- [ ] **P0 Watchlist:** VS-WL-001, 002, **013 (FAB +)**, 016, 022
- [ ] **P0 Detail:** VS-DTL-001, 002, 010
- [ ] **P0 Alerts:** VS-ALT-001, 002 (+ **007, 010, 011** nếu có dev build)
- [ ] **P0 Companion:** VS-CMP-001, 003, 004 (gõ tay), 010, 011, 015, 017
- [ ] **P0 API:** VS-API-001 → 010 (path `/v1/indices`, `/v1/news/market`, `/v1/news/symbols/{sym}`)
- [ ] **P1 swipe / search:** VS-WL-009 (phải = ghim), 010–011 (trái = cảnh báo/xóa), 025 (⌕ = lọc)
- [ ] **Automated:** Section 11 pass 100%
- [ ] **News:** VS-NEWS-001, 002 (`Vàng · HH`), 004
- [ ] **Health:** VS-HLT-001, 002
- [ ] **Offline:** VS-WL-023, VS-DTL-011
- [ ] **Không crash** khi rotate / background / foreground 10 lần
- [ ] **Sentry** không có error mới P0 trên dashboard

**Không coi là fail:** VS-DTL-004 (recent row chưa mount), VS-CMP-004 không có chip trên UI chat.

---

## 13. Mẫu báo cáo bug

```
ID case: VS-___-___
Build: iOS 1.0.0 (123) / Android …
Backend: https://… hoặc local
Device: iPhone 15 / Pixel …
Phiên: Trong phiên / Ngoài phiên

Steps:
1. …
2. …

Expected: …
Actual: …

Screenshot / video: …
Logs: …
```

---

## 14. Tham chiếu

| Tài liệu | Nội dung |
|----------|----------|
| [README.md](../README.md) | Chạy nhanh, API overview |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | Kiến trúc, cache, polling |
| [COMPANION-AI.md](./COMPANION-AI.md) | Vy features & roadmap |
| [EAS-DEV-BUILD.md](./EAS-DEV-BUILD.md) | Dev build cho alerts |
| [APP-STORE.md](./APP-STORE.md) | TestFlight checklist |
