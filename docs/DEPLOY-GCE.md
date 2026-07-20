# Deploy VStock Backend lên Google Cloud (GCE)

> **Trạng thái:** Kế hoạch đã chốt — triển khai khi sẵn sàng.  
> **Phương án:** Compute Engine VM + Docker Compose (không dùng Cloud Run).

---

## Tại sao GCE, không phải Cloud Run?

| Yêu cầu VStock | GCE VM | Cloud Run |
|----------------|--------|-----------|
| Scheduler 15s (quotes) chạy 24/7 | ✅ Máy luôn bật | ❌ Scale-to-zero, job nền không ổn |
| SQLite `vstock.db` persistent | ✅ Docker volume / disk VM | ⚠️ Cần refactor + Cloud SQL |
| Deploy `docker compose` hiện có | ✅ Copy y chang local | ❌ Cần thiết kế lại |

**Kết luận:** GCE = VPS của Google. Phù hợp stack hiện tại, không cần sửa backend.

---

## Kiến trúc mục tiêu

```
Internet
    │
    ▼
[Firewall GCP] — allow 443 (HTTPS), 22 (SSH)
    │
    ▼
GCE VM (asia-southeast1 — Singapore)
    ├── nginx + Let's Encrypt (HTTPS)
    └── docker compose
            └── vstock-api container
                    └── volume → /data/vstock.db
```

**Region khuyến nghị:** `asia-southeast1` (Singapore) — gần VN, latency tốt.

**Chi phí ước tính:** e2-small ~ **$12–15/tháng** (Singapore).  
(e2-micro free tier chỉ áp dụng một số region US — không dùng cho SG.)

---

## Checklist trước khi deploy

- [ ] Tài khoản [Google Cloud](https://console.cloud.google.com/) + billing enabled
- [ ] Cài [gcloud CLI](https://cloud.google.com/sdk/docs/install) (tùy chọn, có thể làm qua Console)
- [ ] Domain (tùy chọn, vd. `api.yourdomain.com`) — HTTPS cho app mobile
- [ ] GitHub repo `VStock` accessible từ VM (public hoặc deploy key)
- [ ] Ghi chú `EXPO_PUBLIC_API_URL` sau khi có URL production

---

## Bước 1 — Tạo project GCP

1. [Console](https://console.cloud.google.com/) → **Select project** → **New project**
2. Tên gợi ý: `vstock-prod`
3. **Billing** → link billing account

Hoặc CLI:

```bash
gcloud projects create vstock-prod --name="VStock Production"
gcloud config set project vstock-prod
gcloud services enable compute.googleapis.com
```

---

## Bước 2 — Tạo VM

### Qua Console (dễ nhất lần đầu)

1. **Compute Engine** → **VM instances** → **Create instance**
2. Cấu hình gợi ý:

| Field | Giá trị |
|-------|---------|
| Name | `vstock-api` |
| Region | `asia-southeast1` (Singapore) |
| Zone | `asia-southeast1-a` |
| Machine type | `e2-small` (2 vCPU, 2 GB) |
| Boot disk | Ubuntu 22.04 LTS, **20 GB** balanced PD |
| Firewall | ✅ Allow HTTP, ✅ Allow HTTPS |

3. **Create**

### Qua gcloud CLI

```bash
gcloud compute instances create vstock-api \
  --project=vstock-prod \
  --zone=asia-southeast1-a \
  --machine-type=e2-small \
  --image-family=ubuntu-2204-lts \
  --image-project=ubuntu-os-cloud \
  --boot-disk-size=20GB \
  --tags=http-server,https-server

gcloud compute firewall-rules create allow-vstock-http \
  --allow=tcp:80,tcp:443 \
  --target-tags=http-server,https-server \
  --description="HTTP/HTTPS for VStock API"
```

Ghi lại **External IP** của VM (vd. `34.xxx.xxx.xxx`).

---

## Bước 3 — SSH vào VM & cài Docker

```bash
gcloud compute ssh vstock-api --zone=asia-southeast1-a
```

Trên VM:

```bash
# Cập nhật hệ thống
sudo apt-get update && sudo apt-get upgrade -y

# Cài Docker (official script)
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER

# Logout + login lại để dùng docker không cần sudo
exit
```

SSH lại, kiểm tra:

```bash
docker --version
docker compose version
```

---

## Bước 4 — Clone repo & chạy backend

```bash
# Trên VM
git clone https://github.com/hiepsikien/VStock.git
cd VStock

# Build và chạy (volume SQLite tự tạo)
docker compose up -d --build

# Kiểm tra
docker compose ps
docker compose logs -f api   # Ctrl+C để thoát
curl http://localhost:8000/health
curl http://localhost:8000/v1/health/sources
```

Từ máy local (thay `EXTERNAL_IP`):

```bash
curl http://EXTERNAL_IP:8000/health
```

> **Firewall:** Nếu không truy cập được từ ngoài, mở port 8000 tạm thời hoặc chỉ dùng nginx (bước 5).  
> Khuyến nghị: **không** expose 8000 public lâu dài — chỉ 443 qua nginx.

---

## Bước 5 — HTTPS với nginx + Let's Encrypt

App mobile nên dùng **HTTPS**. Cần domain trỏ A record → External IP VM.

### 5.1 DNS

Tại nhà cung cấp domain:

```
api.yourdomain.com  →  A  →  EXTERNAL_IP
```

### 5.2 Cài nginx + certbot trên VM

```bash
sudo apt-get install -y nginx certbot python3-certbot-nginx

sudo tee /etc/nginx/sites-available/vstock <<'EOF'
server {
    listen 80;
    server_name api.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/vstock /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# SSL (thay domain thật)
sudo certbot --nginx -d api.yourdomain.com
```

Certbot tự renew. Kiểm tra:

```bash
curl https://api.yourdomain.com/health
```

### Không có domain (chỉ test)

Dùng tạm `http://EXTERNAL_IP:8000` — **chỉ dev**, device thật có thể gặp hạn chế (no HTTPS).

---

## Bước 6 — Cấu hình app Expo

Trên máy dev, file `.env` ở thư mục gốc repo:

```bash
EXPO_PUBLIC_API_URL=https://api.yourdomain.com
```

Restart Expo:

```bash
npx expo start -c
```

Trong app: **⋯ → Nguồn dữ liệu** — kiểm tra providers `ok`, store counts > 0.

---

## Bước 7 — Cập nhật deploy (lần sau)

SSH vào VM:

```bash
cd ~/VStock
git pull origin main
docker compose up -d --build
docker compose logs -f api
```

SQLite nằm trong Docker volume `vstock-data` — **không mất** khi rebuild container.

---

## Backup SQLite

Script trong repo: [`scripts/backup-sqlite.sh`](../scripts/backup-sqlite.sh)  
Cài cron: [`scripts/install-backup-cron.sh`](../scripts/install-backup-cron.sh)

### Cài một lần trên VM

```bash
cd ~/VStock
git pull origin main
chmod +x scripts/backup-sqlite.sh scripts/install-backup-cron.sh

# Timezone VN (khuyến nghị — cron 03:00 = 3h sáng giờ VN)
sudo timedatectl set-timezone Asia/Ho_Chi_Minh

# Chạy backup thử ngay
./scripts/backup-sqlite.sh
ls -lh ~/backups/

# Cài cron: mỗi Chủ nhật 03:00, giữ file ~14 ngày
./scripts/install-backup-cron.sh
```

Backup nằm tại `~/backups/vstock-YYYYMMDD-HHMMSS.db`, log: `~/backups/backup.log`.

### Tùy chọn — upload lên Google Cloud Storage

```bash
# Tạo bucket một lần (đổi tên nếu trùng)
gsutil mb -l asia-southeast1 gs://vstock-backups-$USER || true
gsutil cp ~/backups/vstock-*.db gs://vstock-backups-$USER/
```

### Khôi phục từ backup

```bash
cd ~/VStock
docker compose stop api
# Thay FILE bằng path backup
docker run --rm -v vstock_vstock-data:/data -v "$HOME/backups:/backups:ro" \
  busybox cp /backups/FILE /data/vstock.db
docker compose start api
```

---

## Giám sát & vận hành

| Việc | Lệnh |
|------|------|
| Log API | `docker compose logs -f api` |
| Restart | `docker compose restart api` |
| Disk usage | `df -h` / `docker system df` |
| Health | `curl -s localhost:8000/v1/health/sources \| python3 -m json.tool` |
| VM reboot | Docker Compose `restart: unless-stopped` tự chạy lại |

**Startup lần đầu:** ingest symbols/fundamentals có thể mất 1–2 phút — bình thường.

---

## Troubleshooting

| Triệu chứng | Nguyên nhân / xử lý |
|-------------|---------------------|
| `curl EXTERNAL_IP:8000` timeout | Firewall GCP chưa mở; hoặc chỉ listen localhost — dùng nginx:443 |
| Store counts = 0 | External API chặn IP datacenter; xem `docker compose logs api` |
| App không kết nối | Sai `EXPO_PUBLIC_API_URL`; cần HTTPS trên device thật |
| Mất data sau `docker compose down` | Không dùng `docker compose down -v` (xóa volume) |
| Hết disk | Tăng boot disk hoặc prune: `docker system prune` |

---

## Tài liệu liên quan trong repo

| File | Mô tả |
|------|--------|
| `docker-compose.yml` | Orchestration production |
| `backend/Dockerfile` | Image API |
| `docs/DEPLOY.md` | Tổng quan deploy (Fly.io, Railway, Docker chung) |

---

## Ghi chú khi triển khai thật

Điền vào đây sau khi deploy:

```
Project ID:     ___________________
VM name:        vstock-api
Zone:           asia-southeast1-a
External IP:    ___________________
Domain:         ___________________
API URL:        https://___________________
Deploy date:    ___________________
```
