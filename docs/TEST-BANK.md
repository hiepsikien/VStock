# VStock — Bộ Test Bank

> Tài liệu kiểm thử thủ công (manual QA) và tham chiếu test tự động cho toàn bộ tính năng app VStock.  
> Cập nhật: 2026-09-18

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
# Device thật: EXPO_PUBLIC_API_URL=http://<LAN-IP>:8000
npm start
```

| Biến môi trường | Ghi chú |
|-----------------|---------|
| `EXPO_PUBLIC_API_URL` | URL backend |
| `GEMINI_API_KEY` (backend) | Bắt buộc cho Companion chat live |
| `APP_VARIANT=development` | Dev client cho background alerts |

### 2.3. Thiết bị khuyến nghị

| # | Thiết bị | Lý do |
|---|----------|-------|
| 1 | iOS Simulator | Luồng cơ bản, localhost |
| 2 | iPhone thật (dev build) | Push notification / background alerts |
| 3 | Android emulator hoặc device | `10.0.2.2` / LAN IP |

### 2.4. Dữ liệu test chuẩn

| Loại | Giá trị | Ghi chú |
|------|---------|---------|
| Mã HOSE phổ biến | `FPT`, `VNM`, `VCB`, `HPG` | Có quote + fundamentals |
| Mã biến động | Tuỳ phiên | Dùng khi test sort / nudge |
| Chỉ số | `VNINDEX`, `HNX` | Detail dạng index |
| Hàng hóa | `XAU`, `WTI` | Chart USD, poll ngoài phiên VN |
| Tìm kiếm | `fpt`, `FPT`, `Vinamilk` | Case-insensitive / tên công ty |
| Mã không tồn tại | `ZZZZZ` | Lỗi / empty |
| Watchlist mặc định | Theo `DEFAULT_SYMBOLS` trong client | Sau cài mới |

### 2.5. Phiên giao dịch (VN)

| Khung giờ | Hành vi mong đợi |
|-----------|------------------|
| **Trong phiên** (T2–T6, 9:00–11:30 & 13:00–14:45) | Poll quotes ~30s khi màn hình focus |
| **Ngoài phiên** | Không poll tự động; pull-to-refresh vẫn hoạt động |
| Label phiên | Hiển thị trạng thái (vd. "Đang giao dịch" / "Nghỉ trưa") |

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

\* P0 trên dev build có notification; Expo Go = logic only.  
\** P0 khi `GEMINI_API_KEY` đã cấu hình trên server.

---

## 4. Test cases — Watchlist (Màn Theo dõi)

### VS-WL-001 — Khởi động lần đầu
| | |
|---|---|
| **Priority** | P0 |
| **Precondition** | Cài app mới / xóa data app |
| **Steps** | 1. Mở app lần đầu<br>2. Chờ load xong |
| **Expected** | Hiển thị watchlist mặc định; VN-Index/HNX strip; giá + % thay đổi; sparkline; không crash |

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
| **Expected** | Giá/sparkline cập nhật định kỳ (~30s); label phiên "live" |

### VS-WL-004 — Không poll ngoài phiên
| | |
|---|---|
| **Priority** | P1 |
| **Precondition** | Ngoài giờ giao dịch |
| **Steps** | Giữ màn 2 phút không refresh |
| **Expected** | Giá không tự đổi; pull-to-refresh vẫn fetch được |

### VS-WL-005 — Chỉ số thị trường (VNINDEX / HNX)
| | |
|---|---|
| **Priority** | P1 |
| **Steps** | Tap chip VN-Index hoặc HNX trên summary strip |
| **Expected** | Navigate Detail; chart + OHLC; không có nút cảnh báo giá |

### VS-WL-006 — Hàng hóa (XAU / WTI)
| | |
|---|---|
| **Priority** | P2 |
| **Steps** | Tap XAU hoặc WTI trên strip |
| **Expected** | Detail với giá USD; chart load; poll ngay cả ngoài phiên VN |

### VS-WL-007 — Sort theo biến động
| | |
|---|---|
| **Priority** | P1 |
| **Steps** | Chọn sort "Biến động" (mặc định) |
| **Expected** | Section "Tăng giá" / "Giảm giá" / "Đi ngang"; mã ghim ở section "Đã ghim" |

### VS-WL-008 — Sort theo mã
| | |
|---|---|
| **Priority** | P2 |
| **Steps** | Chọn sort "Mã" |
| **Expected** | Danh sách A→Z; ghim vẫn lên đầu |

### VS-WL-009 — Ghim mã (swipe trái)
| | |
|---|---|
| **Priority** | P1 |
| **Steps** | Swipe trái trên một dòng → "Ghim" |
| **Expected** | Mã lên section "Đã ghim"; swipe lại → "Bỏ ghim" hoạt động |

### VS-WL-010 — Cảnh báo từ swipe (swipe phải)
| | |
|---|---|
| **Priority** | P1 |
| **Steps** | Swipe phải → "Cảnh báo" |
| **Expected** | Mở AlertSheet với giá hiện tại; lưu được alert |

### VS-WL-011 — Xóa mã (swipe phải)
| | |
|---|---|
| **Priority** | P1 |
| **Steps** | Swipe phải → "Xóa" |
| **Expected** | Mã biến mất khỏi list active; persist sau kill app |

### VS-WL-012 — Chế độ sửa (edit)
| | |
|---|---|
| **Priority** | P2 |
| **Steps** | Bật edit mode từ summary/header |
| **Expected** | UI edit; xóa mã bằng nút − hoạt động |

### VS-WL-013 — Tìm kiếm thêm mã
| | |
|---|---|
| **Priority** | P0 |
| **Steps** | 1. Tap ⌕ (tìm)<br>2. Gõ `FPT`<br>3. Tap kết quả để thêm |
| **Expected** | Kết quả search hiện tên + sàn; tap toggle thêm/bỏ; list cập nhật |

### VS-WL-014 — Tìm kiếm theo tên công ty
| | |
|---|---|
| **Priority** | P1 |
| **Steps** | Gõ `Vinamilk` hoặc `FPT` (chữ thường) |
| **Expected** | Trả về `VNM` / `FPT` tương ứng |

### VS-WL-015 — Tìm mã không tồn tại
| | |
|---|---|
| **Priority** | P2 |
| **Steps** | Gõ `ZZZZZ` |
| **Expected** | Empty state / không crash |

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
| **Expected** | Mở in-app browser nếu có URL; hoặc Detail mã liên quan |

### VS-WL-018 — "Xem tất cả tin"
| | |
|---|---|
| **Priority** | P1 |
| **Steps** | Tap link sang màn News |
| **Expected** | Navigate News với animation slide |

### VS-WL-019 — Nhiều watchlist — tạo mới
| | |
|---|---|
| **Priority** | P1 |
| **Steps** | Menu ⋯ → Quản lý danh sách → Tạo list mới |
| **Expected** | List mới xuất hiện trên picker; có thể đặt tên |

### VS-WL-020 — Chuyển watchlist active
| | |
|---|---|
| **Priority** | P1 |
| **Steps** | Tap chip watchlist khác trên picker |
| **Expected** | Symbol list + giá đổi theo list; activeId persist |

### VS-WL-021 — Đổi tên / xóa watchlist
| | |
|---|---|
| **Priority** | P2 |
| **Steps** | Quản lý danh sách → rename / delete |
| **Expected** | Rename hiển thị ngay; delete chuyển sang list còn lại (không xóa list cuối?) |

### VS-WL-022 — Banner API lỗi
| | |
|---|---|
| **Priority** | P1 |
| **Precondition** | Tắt backend hoặc sai `EXPO_PUBLIC_API_URL` |
| **Steps** | Mở Watchlist |
| **Expected** | Banner lỗi + nút "Thử lại"; fallback data mẫu nếu chưa từng fetch OK |

### VS-WL-023 — Offline cache
| | |
|---|---|
| **Priority** | P1 |
| **Precondition** | Đã load thành công ít nhất 1 lần |
| **Steps** | Ngắt mạng → mở lại Watchlist |
| **Expected** | Banner "Dữ liệu đã lưu · cập nhật …"; hiển thị cache |

### VS-WL-024 — Cảnh báo khi mã chưa có giá
| | |
|---|---|
| **Priority** | P2 |
| **Precondition** | Mã `unavailable` hoặc price = 0 |
| **Steps** | Swipe → Cảnh báo |
| **Expected** | Alert "Chưa có giá" — không mở sheet |

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

### VS-DTL-004 — Recent symbols
| | |
|---|---|
| **Priority** | P2 |
| **Steps** | Mở 3 mã khác nhau → quay Watchlist / mở lại Detail |
| **Expected** | Row "Gần đây" hiện các mã vừa xem |

### VS-DTL-005 — Tin theo mã
| | |
|---|---|
| **Priority** | P1 |
| **Steps** | Scroll tin trên Detail; tap bài |
| **Expected** | Browser mở URL; không crash khi thiếu URL |

### VS-DTL-006 — Đặt cảnh báo từ Detail
| | |
|---|---|
| **Priority** | P1 |
| **Steps** | Tap nút cảnh báo (bell) → chọn above/below + giá → Lưu |
| **Expected** | Alert lưu AsyncStorage; hiện trong Quản lý cảnh báo |

### VS-DTL-007 — Detail chỉ số VNINDEX
| | |
|---|---|
| **Priority** | P1 |
| **Steps** | Mở `VNINDEX` |
| **Expected** | Stats Mở/Cao/Thấp/Đóng; **không** có P/E; **không** bell alert |

### VS-DTL-008 — Detail hàng hóa XAU
| | |
|---|---|
| **Priority** | P2 |
| **Steps** | Mở `XAU` |
| **Expected** | Giá `$`; poll ngoài phiên VN |

### VS-DTL-009 — KQKD / income block
| | |
|---|---|
| **Priority** | P2 |
| **Steps** | Mở mã có income (vd. FPT, VNM) |
| **Expected** | Block doanh thu / lợi nhuận hiển thị số hoặc "—" nếu thiếu data |

### VS-DTL-010 — Back navigation
| | |
|---|---|
| **Priority** | P0 |
| **Steps** | Tap ← Quay lại |
| **Expected** | Về Watchlist; state watchlist giữ nguyên |

### VS-DTL-011 — Offline cache detail
| | |
|---|---|
| **Priority** | P1 |
| **Steps** | Load FPT online → offline → mở lại FPT |
| **Expected** | Cache detail + banner tuổi cache |

---

## 6. Test cases — Tin tức (News)

### VS-NEWS-001 — Load tin thị trường
| | |
|---|---|
| **Priority** | P1 |
| **Steps** | Mở News từ Watchlist |
| **Expected** | Danh sách tin load; skeleton biến mất |

### VS-NEWS-002 — Filter chips
| | |
|---|---|
| **Priority** | P1 |
| **Steps** | Lần lượt chọn: Tất cả, Chứng khoán, Kinh tế, Doanh nghiệp, Vàng & hàng hóa, BĐS, Công bố |
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
| **Steps** | ← Quay lại |
| **Expected** | Về Watchlist |

---

## 7. Test cases — Cảnh báo giá (Price Alerts)

> **Lưu ý:** Background push cần **EAS dev build** (`docs/EAS-DEV-BUILD.md`). Expo Go chỉ test logic + UI.

### VS-ALT-001 — Tạo alert "trên" (above)
| | |
|---|---|
| **Priority** | P0 |
| **Steps** | Đặt alert FPT above giá = giá hiện tại + 5% |
| **Expected** | Lưu thành công; hiện trong sheet Quản lý cảnh báo |

### VS-ALT-002 — Tạo alert "dưới" (below)
| | |
|---|---|
| **Priority** | P0 |
| **Steps** | Đặt alert below giá −5% |
| **Expected** | Lưu OK |

### VS-ALT-003 — Bật / tắt alert
| | |
|---|---|
| **Priority** | P1 |
| **Steps** | Toggle enabled trong ManageAlertsSheet |
| **Expected** | Trạng thái persist; tắt = không trigger |

### VS-ALT-004 — Sửa ngưỡng giá
| | |
|---|---|
| **Priority** | P1 |
| **Steps** | Đổi price threshold |
| **Expected** | `lastSeenPrice` reset khi bật lại (arming lại) |

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
| **Steps** | Poll giá cho đến khi vượt ngưỡng |
| **Expected** | Notification / in-app feedback (tuỳ build) |

### VS-ALT-007 — Trigger background (dev build)
| | |
|---|---|
| **Priority** | P0* |
| **Precondition** | Dev build + quyền notification |
| **Steps** | Đặt alert → đưa app background → chờ giá cross |
| **Expected** | Local push notification |

### VS-ALT-008 — Không trigger khi đã qua ngưỡng lúc tạo
| | |
|---|---|
| **Priority** | P1 |
| **Steps** | Tạo alert above với giá **thấp hơn** giá hiện tại |
| **Expected** | Không fire ngay; chờ uptick từ dưới lên |

### VS-ALT-009 — Menu Quản lý cảnh báo
| | |
|---|---|
| **Priority** | P1 |
| **Steps** | Watchlist ⋯ → Quản lý cảnh báo |
| **Expected** | Sheet liệt kê tất cả alerts |

---

## 8. Test cases — Companion AI (Vy)

> Backend cần `GEMINI_API_KEY`. Không có key → chat trả 503 (expected local).

### VS-CMP-001 — Mở chat từ FAB
| | |
|---|---|
| **Priority** | P0 |
| **Steps** | Tap FAB Vy góc màn hình |
| **Expected** | Modal CompanionChat slide từ dưới; greeting lần đầu |

### VS-CMP-002 — Welcome back
| | |
|---|---|
| **Priority** | P2 |
| **Precondition** | Đã chat trước đó; đóng app > gap (WELCOME_BACK_GAP) |
| **Steps** | Mở lại chat |
| **Expected** | Bubble welcome back thay vì greeting mới |

### VS-CMP-003 — Gửi tin nhắn text
| | |
|---|---|
| **Priority** | P0 |
| **Steps** | Nhập "Xin chào" → Gửi |
| **Expected** | Presence: reading → fetching → typing; reply stream/reveal; không crash |

### VS-CMP-004 — 5 câu hỏi lõi (quick chips)
| | |
|---|---|
| **Priority** | P0 |
| **Steps** | Tap lần lượt các chip gợi ý:<br>• Watchlist hôm nay thế nào?<br>• Tại sao {mã} biến động?<br>• Tin đáng chú ý?<br>• {mã} định giá / KQKD?<br>• Nên giữ hay gỡ mã nào? |
| **Expected** | Vy trả lời có context thị trường; không bịa số khi thiếu data; không khuyến nghị mua/bán cứng |

### VS-CMP-005 — Nudge trên Watchlist
| | |
|---|---|
| **Priority** | P1 |
| **Precondition** | Có biến động watchlist / recall event |
| **Steps** | Quan sát bubble nudge phía trên FAB |
| **Expected** | Message + quick replies; tap chip mở chat với seed message |

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
| **Expected** | Bio, expertise, bond info |

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
| **Expected** | Pop-up confirm; **Chấp nhận** → mã vào list; **Huỷ** → không đổi |

### VS-CMP-011 — Propose xóa mã
| | |
|---|---|
| **Priority** | P0 |
| **Steps** | Chat "Xóa FPT khỏi watchlist" |
| **Expected** | Confirm sheet; chỉ xóa khi user đồng ý |

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
| **Expected** | Từ chối khuyến nghị; góc nhìn tham khảo |

### VS-CMP-016 — Lỗi API / không Gemini key
| | |
|---|---|
| **Priority** | P1 |
| **Steps** | Chat khi backend 503 |
| **Expected** | Error message trong UI; không treo busy vô hạn |

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
| **Steps** | Watchlist ⋯ → Nguồn dữ liệu |
| **Expected** | Load `GET /v1/health/sources` |

### VS-HLT-002 — Hiển thị provider status
| | |
|---|---|
| **Priority** | P1 |
| **Steps** | Xem danh sách providers |
| **Expected** | Màu ok / degraded / error; last fetch time |

### VS-HLT-003 — Store counts
| | |
|---|---|
| **Priority** | P2 |
| **Steps** | Kiểm tra số quotes, symbols, news trong DB |
| **Expected** | Số > 0 sau ingestion chạy |

### VS-HLT-004 — Pull refresh Health
| | |
|---|---|
| **Priority** | P2 |
| **Steps** | Kéo refresh |
| **Expected** | Data cập nhật |

### VS-HLT-005 — API URL hiển thị
| | |
|---|---|
| **Priority** | P2 |
| **Steps** | Kiểm tra footer hiện `getApiUrl()` |
| **Expected** | Khớp env đang dùng |

---

## 10. Test cases — Backend API

Chạy khi backend local port 8000. Có thể dùng `curl` hoặc Postman.

### VS-API-001 — Health
```bash
curl -s http://localhost:8000/health
```
**Expected:** `200`, body có trạng thái OK.

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
curl -s "http://localhost:8000/v1/market/indices"
```
**Expected:** VNINDEX, HNX quotes.

### VS-API-008 — Market news
```bash
curl -s "http://localhost:8000/v1/news?limit=5"
```
**Expected:** Array NewsItem.

### VS-API-009 — Symbol news
```bash
curl -s "http://localhost:8000/v1/news/FPT?limit=5"
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
```bash
curl -s -X POST "http://localhost:8000/v1/companion/nudge" \
  -H "Content-Type: application/json" \
  -d '{"events":[{"type":"view_detail","symbol":"HAG","ts":1695000000000}],"context":{"screen":"Detail","symbol":"HAG"}}'
```
**Expected:** `show: true`, có `message`.

### VS-API-013 — Companion chat (non-stream)
```bash
curl -s -X POST "http://localhost:8000/v1/companion/chat" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"xin chào"}],"stream":false}'
```
**Expected:** `200` nếu có Gemini key; `503` nếu không.

### VS-API-014 — Invalid symbol
```bash
curl -s -o /dev/null -w "%{http_code}\n" "http://localhost:8000/v1/stocks/ZZZZZ"
```
**Expected:** `404` hoặc fallback có cấu trúc (theo implementation).

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

- [ ] **P0 Watchlist:** VS-WL-001, 002, 013, 016, 022
- [ ] **P0 Detail:** VS-DTL-001, 002, 010
- [ ] **P0 Alerts:** VS-ALT-001, 002 (+ 007 nếu có dev build)
- [ ] **P0 Companion:** VS-CMP-001, 003, 004, 010, 011, 015, 017
- [ ] **P0 API:** VS-API-001 → 010
- [ ] **Automated:** Section 11 pass 100%
- [ ] **News:** VS-NEWS-001, 002, 004
- [ ] **Health:** VS-HLT-001, 002
- [ ] **Offline:** VS-WL-023, VS-DTL-011
- [ ] **Không crash** khi rotate / background / foreground 10 lần
- [ ] **Sentry** không có error mới P0 trên dashboard

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
