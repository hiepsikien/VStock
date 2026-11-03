# Deploy VStock Backend

Backend FastAPI + APScheduler + SQLite. Cần **volume persistent** cho `vstock.db` (ingestion chạy nền 24/7).

**Google Cloud (GCE) — kế hoạch chính:** xem **[DEPLOY-GCE.md](./DEPLOY-GCE.md)** (hướng dẫn chi tiết từng bước).

---

## Yêu cầu

| Biến | Mặc định | Mô tả |
|------|----------|--------|
| `VSTOCK_DB_PATH` | `backend/data/vstock.db` (local) / `/data/vstock.db` (Docker) | Đường dẫn SQLite |
| `PORT` | `8000` | Cổng HTTP của API |
| `RESEARCH_PORT` | `8010` | Cổng web research trên localhost |
| `NEWS_FILING_DAYS` | `1460` | Số ngày giữ công bố. Khi có biến này, backend dùng nó thay cho `news_filing_days` trong `providers.yaml`; Compose chuyển cùng giá trị sang research |
| `SENTRY_DSN` | (trống = tắt) | DSN project Python trên Sentry |
| `SENTRY_ENVIRONMENT` | `production` | Tag môi trường trên Sentry |
| `SENTRY_TRACES_SAMPLE_RATE` | `0.1` | Tỷ lệ sample performance |
| `VSTOCK_SONIFY_EVENTS_DB` | `backend/data/sonify-events.sqlite3` (local) / `/data/sonify-events.sqlite3` (Docker) | Kho telemetry nghe nhạc. Trong Docker đã nằm trên volume `vstock-data`; nhiều instance phải trỏ cùng volume/store |
| `VSTOCK_SONIFY_EVENT_LOG` | (trống = tắt) | Mirror JSONL tùy chọn cho log collector |
| `VSTOCK_SONIFY_EVENTS_RATE_PER_MIN` | `120` | Rate limit batch event theo IP tại process; proxy vẫn nên giới hạn toàn cục |
| `VSTOCK_SONIFY_PIN_RATE_PER_MIN` | `600` | Rate limit pin cache A/B theo IP |
| `FORWARDED_ALLOW_IPS` | `*` (Docker Compose) | Uvicorn chỉ tin `X-Forwarded-For` từ các IP này. Giữ port API private; nếu proxy khác, đặt đúng IP/subnet của proxy |

Healthcheck: `GET /health`  
Ingestion status: `GET /v1/health/sources`

### Telemetry nghe nhạc

`POST /v1/sonify/events` ghi vào SQLite (`VSTOCK_SONIFY_EVENTS_DB`) và trả `accepted`. Batch trùng `eventId` trả `accepted: 0`, nên client có thể xoá buffer sau khi retry. Báo cáo gate (số session replay, tỷ lệ A/B, profile có knob B/C):

```bash
cd backend
.venv/bin/python scripts/sonify_events_report.py --since 2026-11-01
# Nhiều instance: lặp --db cho từng file
.venv/bin/python scripts/sonify_events_report.py --db /data/a.sqlite3 --db /data/b.sqlite3 --json
# Docker: script đã có trong image
docker compose exec api python scripts/sonify_events_report.py --since 2026-11-01
# Retention: chạy định kỳ, ví dụ cron 90 ngày
docker compose exec api python scripts/sonify_events_report.py --prune-days 90
```

Rate limit dùng `request.client.host`; khi đứng sau Caddy/nginx phải bật `--proxy-headers` (Dockerfile đã bật) và đặt `FORWARDED_ALLOW_IPS` đúng proxy, nếu không mọi client sẽ chung một bucket IP của proxy. Endpoint không có auth; chỉ mở API qua proxy và giữ port 8000 private.

---

## 1. Docker Compose (VPS / máy chủ riêng)

Phù hợp VPS Việt Nam, homelab, hoặc bất kỳ máy nào có Docker.

```bash
# Từ thư mục gốc repo
docker compose up -d --build

# Xem log
docker compose logs -f api

# Kiểm tra
curl http://localhost:8000/health
curl http://localhost:8000/v1/health/sources
curl http://127.0.0.1:8010/health
```

Web research nằm trong cùng Compose và chỉ publish trên `127.0.0.1`.

Dữ liệu SQLite nằm trong volume Docker `vstock-data`. Backup dùng SQLite backup API để lấy cả phần đang nằm trong WAL:

```bash
# Từ máy đang chạy Compose. Đổi VSTOCK_DIR nếu repo không ở ~/VStock.
VSTOCK_DIR="$(pwd)" ./scripts/backup-sqlite.sh
```

File lưu tại `~/backups/vstock-YYYYMMDD-HHMMSS.db`.

**Reverse proxy (nginx)** — ví dụ `api.yourdomain.com`:

```nginx
server {
    listen 443 ssl;
    server_name api.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## 2. Fly.io (khuyến nghị — volume + HTTPS miễn phí)

Region **sin** (Singapore) gần VN.

```bash
# Cài flyctl: https://fly.io/docs/flyctl/install/
cd backend

# Lần đầu — đổi tên app trong fly.toml nếu cần
fly launch --no-deploy --copy-config

# Tạo volume persistent (1GB)
fly volumes create vstock_data --region sin --size 1

# Deploy
fly deploy

# Kiểm tra
fly open /health
fly logs
```

URL sau deploy: `https://vstock-api.fly.dev` (hoặc tên app bạn chọn).

**Lưu ý:** `auto_stop_machines = off` trong `fly.toml` để scheduler quotes 15s không bị tắt.

---

## 3. Railway

1. New Project → Deploy from GitHub repo
2. Root directory: `backend`
3. Dockerfile: auto-detect `backend/Dockerfile`
4. Thêm **Volume** mount `/data`
5. Env: `VSTOCK_DB_PATH=/data/vstock.db`
6. Generate domain → copy URL

---

## 4. Cấu hình app mobile

Sau khi deploy, cập nhật `.env` ở thư mục gốc app:

```bash
EXPO_PUBLIC_API_URL=https://vstock-api.antunai.com
```

Rebuild / restart Expo:

```bash
npx expo start -c
```

- **Simulator:** dùng URL production hoặc `localhost` khi dev local
- **Device thật:** bắt buộc HTTPS URL public (không dùng `localhost`)

### Sentry (TestFlight / production)

Tạo **2 project** trên [sentry.io](https://sentry.io): React Native (`vstock-mobile`) và Python (`vstock-api`).

| Biến | Ở đâu | Ghi chú |
|------|--------|---------|
| `EXPO_PUBLIC_SENTRY_DSN` | EAS env / `.env` | DSN project mobile |
| `SENTRY_AUTH_TOKEN` | EAS secret (sensitive) | Upload source maps khi `eas build` |
| `organization` / `project` | `app.config.ts` plugin `@sentry/react-native/expo` | Org/project Sentry |
| `SENTRY_DSN` | GCE / docker `.env` | DSN project Python (khác mobile) |

```bash
# EAS (DSN + auth token)
eas env:create --name EXPO_PUBLIC_SENTRY_DSN --value 'https://...@o....ingest.sentry.io/...' --environment production
eas env:create --name SENTRY_AUTH_TOKEN --value 'sntrys_...' --environment production --visibility sensitive

# Backend GCE / compose
# SENTRY_DSN=...  trong .env cạnh docker-compose.yml
# Verify (tạm): SENTRY_DEBUG_ENDPOINT=1 rồi GET /sentry-debug — tắt ngay sau khi thấy event
```

Native plugin cần **rebuild** TestFlight (`eas build`) sau khi thêm `@sentry/react-native`.

---

## 5. Kiểm tra sau deploy

```bash
curl -s https://YOUR_API/health
curl -s https://YOUR_API/v1/health/sources | python3 -m json.tool
curl -s "https://YOUR_API/v1/watchlist?symbols=VNM,FPT" | python3 -m json.tool
```

Trong app: menu **⋯ → Nguồn dữ liệu** — trạng thái `ok`, store counts > 0 sau vài phút.

---

## Troubleshooting

| Vấn đề | Cách xử lý |
|--------|------------|
| Store counts = 0 | Xem `fly logs` / `docker compose logs`; external API có thể chặn IP datacenter |
| App không kết nối | Kiểm tra `EXPO_PUBLIC_API_URL`, HTTPS, CORS (backend cho phép `*`) |
| Mất data sau redeploy | Chưa mount volume — cấu hình lại `/data` |
| Startup chậm | Bình thường — lần đầu chạy ingest symbols + fundamentals (~1–2 phút) |
