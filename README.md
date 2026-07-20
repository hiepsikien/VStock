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

Sau deploy, set `EXPO_PUBLIC_API_URL=https://your-api-url` trong `.env`.

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
