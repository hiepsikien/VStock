# Deploy VStock Backend

Backend FastAPI + APScheduler + SQLite. Cần **volume persistent** cho `vstock.db` (ingestion chạy nền 24/7).

**Google Cloud (GCE) — kế hoạch chính:** xem **[DEPLOY-GCE.md](./DEPLOY-GCE.md)** (hướng dẫn chi tiết từng bước).

---

## Yêu cầu

| Biến | Mặc định | Mô tả |
|------|----------|--------|
| `VSTOCK_DB_PATH` | `backend/data/vstock.db` (local) / `/data/vstock.db` (Docker) | Đường dẫn SQLite |
| `PORT` | `8000` | Cổng HTTP |

Healthcheck: `GET /health`  
Ingestion status: `GET /v1/health/sources`

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
```

Dữ liệu SQLite nằm trong volume Docker `vstock-data`. Backup:

```bash
docker compose exec api python -c "
from pathlib import Path
import shutil, os
src = Path(os.environ['VSTOCK_DB_PATH'])
shutil.copy2(src, '/tmp/vstock-backup.db')
print('copied', src)
"
docker cp $(docker compose ps -q api):/tmp/vstock-backup.db ./vstock-backup.db
```

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
EXPO_PUBLIC_API_URL=https://api.yourdomain.com
```

Rebuild / restart Expo:

```bash
npx expo start -c
```

- **Simulator:** dùng URL production hoặc `localhost` khi dev local
- **Device thật:** bắt buộc HTTPS URL public (không dùng `localhost`)

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
