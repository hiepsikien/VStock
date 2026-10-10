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
uvicorn app.web:app --host 127.0.0.1 --port 8010
```

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
| Vĩ mô | Yahoo chart: DXY, USD/VND, S&P 500, dầu WTI | Khối `mở`/`cần theo dõi`; chỉ chặn khi DXY **và** tỷ giá cùng trên MA20 |
| Cơ bản | VNDirect Finfo ratios + `fundamentals` của backend | Ngân hàng, chứng khoán, bảo hiểm và doanh nghiệp có bộ cổng riêng |
| Định giá | `fundamentals.pe` từ kho thị trường | Trần P/E 30. Chỉ áp ở phiên trực tiếp, backtest bỏ qua vì là ảnh chụp hiện tại |
| Dòng tiền lớn | VNDirect Finfo `foreigns` | Net volume/net value/room 60 phiên; nghi bán vào đà tăng thì hạ cấp |
| Nền giá, mô hình | Entrade nến ngày | ZigZag theo ATR, nhận diện Đáy đôi, VCP, Cờ, ABCD |
| Điểm tổng hợp | Tính nội bộ | 0–100 (cơ bản 30, dòng tiền 25, nền giá 25, sức mạnh 10, tin 10) |

Về F-Score: VNDirect không cung cấp mã số biên lợi nhuận gộp và phải thu, nên bảng điểm dùng
8 tiêu chí suy ra từ chỉ tiêu có thật; hàng tồn kho và biên dòng tiền thay cho soát phải thu.
Thiếu dưới 6 tiêu chí thì không chấm điểm thay vì chấm thiếu.

Cổng định giá đọc `fundamentals.pe` trong `backend/data/vstock.db`, nên mã không nằm trong
`ingestion.quote_symbols` của `backend/config/providers.yaml` sẽ hiện "Chưa có số" và được bỏ qua
chứ không bị chặn. Giữ danh sách đó khớp với `DEFAULT_UNIVERSE` trong `research/app/config.py`
(hiện 30 mã), rồi khởi động lại backend — lúc khởi động nó chạy ingestion với `force=True` nên
lấy P/E cho đủ ngay.

### Vị thế giấy (đo tiến)

Bấm "Xác nhận sẽ vào" ở một mã **Được vào** sẽ mở một suất vốn giấy. Mỗi phiên chạy, hệ thống
đánh dấu theo giá đóng cửa và thoát theo đúng luật của backtest: dừng lỗ đáy nền, chốt 1/3 tại
+1R rồi kéo dừng lỗ theo MA20, đóng khi tiền chết 30 phiên, có công bố chặn, hoặc dòng tiền
ngoại đảo chiều. Trang `/backtest` so lãi bình quân của các suất với VN-Index trong đúng cửa sổ
nắm giữ.

### Cảnh báo phiên

Đặt `TELEGRAM_BOT_TOKEN` và `TELEGRAM_CHAT_ID` để nhận tin khi có mã đổi trạng thái (Được vào,
Loại, Khóa) hoặc khi một vị thế giấy đóng. Không đặt thì hệ thống chỉ ghi nhật ký.

### Test

```bash
cd research
.venv/bin/python -m unittest tests.test_rules tests.test_prune tests.test_patterns tests.test_layers
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
