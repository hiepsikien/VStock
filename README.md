# VStock

App chứng khoán Việt Nam (HOSE/HNX), phong cách Apple Stocks — Expo (iOS/Android) + FastAPI backend lấy data từ nguồn mở.

## Chạy nhanh

### 1. Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 2. App

```bash
cp .env.example .env   # chỉnh EXPO_PUBLIC_API_URL nếu cần
npm start
```

- Simulator iOS: `localhost:8000` ổn.
- Device thật / Android emulator: dùng LAN IP máy (vd. `http://192.168.x.x:8000`).

## API

| Endpoint | Mô tả |
|----------|--------|
| `GET /health` | Healthcheck |
| `GET /v1/symbols` | Toàn bộ mã HOSE + HNX (~700) |
| `GET /v1/symbols/search?q=FPT` | Tìm mã / tên |
| `GET /v1/watchlist?symbols=VNM,FPT` | Batch quotes + sparkline |
| `GET /v1/stocks/{symbol}` | Quote + fundamentals |
| `GET /v1/stocks/{symbol}/history?range=1D` | OHLCV closes |

Nguồn: SSI/VNDirect (danh sách mã), VPS (quotes), Entrade (history), VNDirect/SSI (+ KBS khi có) cho tên / vốn hóa / P/E.

## Research

Bộ lọc cổ phiếu chạy thành một process riêng. Nó đọc nến, chỉ tiêu, công bố, dòng tiền khối
ngoại và dữ liệu vĩ mô, ghi kết quả vào database của nó, và không đặt lệnh.

```bash
cd research
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.web:app --host 127.0.0.1 --port 8010 --reload
```

`--reload` để uvicorn tự nạp lại khi sửa file trong `research/app` và `research/templates`; thiếu
cờ này thì tiến trình đang chạy vẫn giữ bảng tuyến cũ và một trang mới thêm sẽ trả
`{"detail":"Not Found"}` cho tới khi khởi động lại.

Mở http://127.0.0.1:8010. Trong Docker Compose, cổng host là `RESEARCH_PORT` (mặc định 8010)
và chỉ gắn vào localhost.

### Chạy từ dashboard

Dashboard có nút **Chạy phiên**: nó tải nến, chỉ tiêu, công bố, dòng tiền ngoại và dữ liệu vĩ mô
cho cả danh sách, chấm lại toàn bộ, đánh dấu vị thế giấy và gửi cảnh báo. Danh sách 30 mã mất
khoảng 15 giây. Thêm/bỏ mã và ghi xác nhận, bỏ qua cũng làm được ngay trên trang web. Trang
`/backtest` tính lại bảng đo khi mở lần đầu sau mỗi phiên rồi giữ nguyên kết quả; bấm
**Tính lại** (`/backtest?fresh=1`) nếu muốn chạy lại bằng tay. Hiện chưa có lịch chạy tự động —
muốn tự chạy hằng ngày thì thêm một lệnh `curl -X POST http://127.0.0.1:8010/run` vào cron
sau giờ đóng cửa.

### Các lớp đang chấm

| Lớp | Nguồn | Ghi chú |
|---|---|---|
| Vĩ mô | Yahoo chart: DXY, USD/VND, S&P 500, dầu WTI | Khối `mở`/`cần theo dõi`; chỉ **chặn** khi DXY trên MA20 (biên 0,5%) **và** đang tăng, cùng lúc tỷ giá trên MA20. S&P 500 dưới MA20 hoặc dầu tăng quá 15% trong 20 phiên chỉ đưa vào diện theo dõi. Thiếu một trong hai chân chặn, hoặc tải lỗi, thì coi như chưa có số và hạ lệnh sắp vào xuống Theo dõi |
| Cơ bản | VNDirect Finfo ratios + `fundamentals` của backend | Ngân hàng, chứng khoán, bảo hiểm và doanh nghiệp có bộ cổng riêng |
| Định giá | `fundamentals.pe` từ kho thị trường | Trần P/E 30. Chỉ áp ở phiên trực tiếp, backtest bỏ qua vì là ảnh chụp hiện tại |
| Dòng tiền lớn | VNDirect Finfo `foreigns` | Tải 60 phiên net volume/net value/room; cổng chấm đọc **10 phiên** gần nhất, nghi bán vào đà tăng thì hạ cấp |
| Nền giá, mô hình | Entrade nến ngày | Nền phẳng 20 phiên (sâu ≤15%, nhịp tăng trước nền ≥15%) phải phá đỉnh bằng nến khối lượng ≥1.5× nền; ZigZag theo ATR, nhận diện Đáy đôi, VCP, Cờ, ABCD |
| Tiền tệ | TradingView scanner (lãi liên ngân hàng qua đêm, lợi suất TPCP 10 năm), Yahoo chart (USD/VND), bảng NHNN ghi tay (lãi tái cấp vốn) | Cổng AND với cổng VN-Index trên MA200; mỗi phiên lưu một điểm cho mỗi chuỗi, trang `/market` |
| Điểm tổng hợp | Tính nội bộ | 0–100 (cơ bản 30, dòng tiền 25, nền giá 25, sức mạnh 10, tin 10) |

Điểm tổng hợp dùng để **xếp hạng và tô màu nhãn**: ngưỡng 75 chỉ đổi màu chứ không cấp quyền vào.
Trạng thái **Được vào** do các cổng cứng (vĩ mô, cơ bản, tin, nền giá) quyết định, không cần
`score_ok`; mã đạt cổng mà điểm thấp vẫn vào được và chỉ hiện nhãn nhạt hơn.

Về F-Score: VNDirect không cung cấp mã số biên lợi nhuận gộp và phải thu, nên bảng điểm dùng
8 tiêu chí suy ra từ chỉ tiêu có thật; hàng tồn kho và biên dòng tiền thay cho soát phải thu.
Thiếu dưới 6 tiêu chí thì không chấm điểm thay vì chấm thiếu.

Cổng định giá đọc `fundamentals.pe` trong `backend/data/vstock.db`, nên mã không nằm trong
`ingestion.quote_symbols` của `backend/config/providers.yaml` sẽ hiện "Chưa có số" và được bỏ qua
chứ không bị chặn. Giữ danh sách đó khớp với `DEFAULT_UNIVERSE` trong `research/app/config.py`
(hiện 30 mã), rồi khởi động lại backend — lúc khởi động nó chạy ingestion với `force=True` nên
lấy P/E cho đủ ngay. Có một test đối chiếu hai danh sách này trong `tests/test_layers.py`.

Kho research gộp `DEFAULT_UNIVERSE` vào danh sách đang có khi khởi động: kho trắng nhận đủ 30 mã,
kho đã có danh sách thì giữ nguyên và chỉ nhận thêm mã vừa được thêm vào `DEFAULT_UNIVERSE`. Lần
khởi động đầu sau khi nâng cấp cũng vậy, nên mã bạn đã bỏ bằng tay không quay lại.

### Vị thế giấy (đo tiến)

Bấm "Xác nhận sẽ vào" ở một mã **Được vào** sẽ mở một suất vốn giấy. Mỗi phiên chạy, hệ thống
đánh dấu theo giá đóng cửa và thoát theo đúng luật của backtest: dừng lỗ đáy nền, chốt 1/3 tại
+1R rồi kéo dừng lỗ theo MA20 (mức kéo tính từ nến đã đóng, nên chỉ nằm trong sổ từ phiên sau),
đóng cửa dưới đỉnh nền lúc vào (phá nền thất bại), đóng khi tiền chết 30 phiên, có công bố chặn,
hoặc dòng tiền ngoại đảo chiều. Sổ đi lần lượt từng nến sau phiên đã chấm, nên bấm chạy lại trong
cùng ngày không cộng thêm phiên và một phiên bị lỡ vẫn được chấm đủ, kể cả phiên chạm dừng lỗ;
phiên mà luật đóng tại giá đóng cửa kết thúc suất vẫn được tính vào cột "Phiên". Trang `/backtest`
so lãi bình quân của các suất với VN-Index trong đúng cửa sổ nắm giữ; suất vừa xác nhận chưa có
phiên mark nào thì chưa có cửa sổ để so nên không vào bình quân, và alpha chỉ tính trên những suất
có đủ cả hai vế.

### Cổng tiền tệ

Cổng tiền tệ đứng cạnh cổng VN-Index trên MA200 và là cổng **AND**: VN-Index trên MA200 *và*
tiền chưa thắt thì danh sách mới được xét tiếp. Nó trả lời tiền đang thừa hay thiếu, chứ không
chấm điểm bài báo nào.

Năm chuỗi, ngưỡng khai báo trong `research/app/config.py` và in ra ở trang `/market`:

| Chuỗi | Nguồn | Ngưỡng khóa |
|---|---|---|
| Lãi liên ngân hàng qua đêm | TradingView scanner, `ECONOMICS:VNINBR` | Cao hơn trung bình 20 phiên quá 1 điểm % |
| Lợi suất TPCP 10 năm | TradingView scanner, `TVC:VN10Y` | Cao hơn trung bình 20 phiên quá 0.5 điểm % |
| Tỷ giá USD/VND | TradingView scanner `FX_IDC:USDVND`, lỗi thì Yahoo chart `USDVND=X` | Trên trung bình 20 phiên cộng 1.0% đủ 5 phiên liên tiếp |
| Lãi suất tái cấp vốn | Bảng ghi tay `POLICY_RATE_HISTORY` trong `config.py` | Có mốc mới trong 90 ngày gần nhất |
| NHNN hút/bơm ròng | Chưa có nguồn công khai, điền tay vào `market_points` | Hút ròng 5 phiên liên tiếp, tổng từ 5.000 tỷ |

Bốn chuỗi đầu là **bắt buộc**. Mỗi chuỗi phải có điểm **đúng phiên đang chấm**: thiếu số, hoặc
trong kho chỉ có điểm của phiên trước (feed chết trong phiên), hoặc chưa đủ 5 phiên đã lưu đều đưa
cổng về **Chưa chấm**, và không mã nào bị tự loại vì chuyện tiền tệ. Chuỗi NHNN chưa có nguồn
nên nằm ngoài danh sách bắt buộc, nhưng ngưỡng đã khai báo trước nên nó khóa được ngay khi có số.

Mỗi phiên pipeline lấy một điểm cho mỗi chuỗi rồi lưu vào bảng `market_points`; hàm chấm chỉ đọc
các điểm tới hết ngày đang chấm, nên chấm lại một phiên cũ luôn ra cùng kết quả và số của hôm nay
không bao giờ rơi vào một phiên đã qua. Chuỗi giá còn phải có điểm của chính phiên đang chấm: nguồn
chết đúng phiên đó thì cổng đứng "Chưa chấm" thay vì dùng lại số của phiên trước. Scanner chỉ trả
giá hiện tại, nên chuỗi bắt đầu từ ngày bật tính năng: cổng đứng "Chưa chấm" cho tới khi đủ 5 phiên
đã lưu (khoảng một tuần), rồi mới mở hoặc khóa được. Bảng quyết định lãi điều hành là chuỗi bậc
thang có sẵn, nên chuỗi này có số ngay.

### Cảnh báo phiên

Đặt `TELEGRAM_BOT_TOKEN` và `TELEGRAM_CHAT_ID` để nhận tin khi có mã đổi trạng thái (Được vào,
Loại, Khóa) hoặc khi một vị thế giấy đóng. Không đặt thì hệ thống chỉ ghi nhật ký.

### Test

```bash
cd research
.venv/bin/python -m unittest tests.test_rules tests.test_prune tests.test_patterns tests.test_layers tests.test_money tests.test_chart
```


## Làm mới dữ liệu

| Thành phần | Chiến lược |
|---|---|
| Giá watchlist / detail | Poll **30s** khi màn hình đang mở + **trong phiên** (9:00–11:30, 13:00–14:45 T2–T6) |
| Chart 1D (detail) | Refresh **5 phút** trong phiên |
| Chart 1W+ | Cache **1 giờ** (fetch khi đổi range) |
| Backend quote cache | **15 giây** |
| Danh sách mã / fundamentals | **6–24 giờ** |

Ngoài giờ giao dịch: không poll tự động; kéo xuống để refresh thủ công.

## Deploy backend

| Tài liệu | Mô tả |
|----------|--------|
| **[docs/DEPLOY-GCE.md](docs/DEPLOY-GCE.md)** | **Google Cloud GCE** (kế hoạch chính — VM + Docker) |
| [docs/DEPLOY.md](docs/DEPLOY.md) | Tổng quan: Docker Compose, Fly.io, Railway |

```bash
docker compose up -d --build   # chạy trên VM / VPS
```

Sau deploy, set `EXPO_PUBLIC_API_URL=https://vstock-api.antunai.com` trong `.env`.

## Development build (alerts)

Expo Go không đủ cho background alerts. Dùng EAS dev client:

→ **[docs/EAS-DEV-BUILD.md](docs/EAS-DEV-BUILD.md)**

```bash
eas login && eas init
npm run build:ios:dev          # iPhone thật (cần Apple Developer)
# hoặc
npm run build:ios:sim          # Simulator
npm run start:dev
```

## Stack

Expo SDK 54 · React Native · React Navigation · FastAPI · httpx · EAS Build
