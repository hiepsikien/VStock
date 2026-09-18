# Deploy VStock Backend lên Google Cloud (GCE)

> **Trạng thái:** Production HTTPS qua Caddy (`https://vstock-api.antunai.com`). Không dùng nginx host — Docker Caddy đã bind 80/443.  
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
    ├── Caddy (Docker, 80/443, Let's Encrypt)
    └── docker compose
            └── vstock-api container (angi_net)
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

### SSH từ Mac (terminal)

**Nguyên nhân lỗi thường gặp:** Ubuntu 22.04 trên GCE thường **từ chối khóa RSA** (`google_compute_engine`). Dùng **ed25519**.

**Một lần — setup:**

```bash
gcloud auth login
gcloud config set project vstock-prod
cd ~/Projects/VStock
chmod +x scripts/setup-gce-ssh.sh
./scripts/setup-gce-ssh.sh
```

**Vào VM hàng ngày:**

```bash
# User có repo VStock + docker (khuyến nghị deploy)
ssh -i ~/.ssh/gce_vstock_ed25519 anh_nguyendinh_cs@34.124.179.140

# Hoặc qua gcloud (user = username Mac)
gcloud compute ssh vstock-api \
  --zone=asia-southeast1-a \
  --project=vstock-prod \
  --ssh-key-file=~/.ssh/gce_vstock_ed25519
```

**Lưu ý:** Khóa RSA mặc định (`google_compute_engine`) thường **không work** trên Ubuntu 22 — dùng `gce_vstock_ed25519` ở trên.

---

Trên VM (sau khi SSH được):

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

## Bước 5 — HTTPS qua Caddy (đã có trên VM)

VM đã chạy `deploy-caddy-1` (`caddy:2-alpine`) bind **80/443**. Source of truth: `check-food/deploy/Caddyfile` trên mạng `angi_net`. **Không** cài nginx host / certbot — sẽ conflict với Caddy.

### 5.1 DNS

```
vstock-api.antunai.com  →  A  →  34.124.179.140
```

### 5.2 Site Caddy

Trong `check-food/deploy/Caddyfile`:

```
vstock-api.antunai.com {
	encode gzip
	reverse_proxy vstock-api-1:8000
}
```

Container VStock phải nằm trên `angi_net` (mất sau `docker compose up` nếu quên):

```bash
sudo docker network connect angi_net vstock-api-1
sudo docker exec deploy-caddy-1 caddy reload --config /etc/caddy/Caddyfile
curl -sS https://vstock-api.antunai.com/health
```

Caddy tự cấp Let's Encrypt. Host nginx nên `disabled`.

---

## Bước 6 — Cấu hình app Expo

Trên máy dev, file `.env` ở thư mục gốc repo:

```bash
EXPO_PUBLIC_API_URL=https://vstock-api.antunai.com
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
sudo docker network connect angi_net vstock-api-1 2>/dev/null || true
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

## Companion AI (Gemini)

Chat/nudge gọi Vertex/Gemini **chỉ từ backend** — không đưa key vào Expo app.

> **Trạng thái:** GCE hiện chạy `main` cũ → `/v1/companion/*` trả **404** cho đến khi pull branch có Companion và rebuild Docker.

### Deploy Companion lên VM (checklist)

**Trên Mac (một lần):** merge `feature/companion-ai` → `main`, push GitHub.

**Trên VM (SSH):**

```bash
cd ~/VStock
git pull origin main          # sau khi main đã có Companion
cp .env.gce.example .env      # nếu chưa có .env
nano .env                     # điền GEMINI_API_KEY (hoặc GCP_PROJECT)
chmod +x scripts/deploy-companion-gce.sh
./scripts/deploy-companion-gce.sh
```

Hoặc tạm deploy từ feature branch (chưa merge main):

```bash
DEPLOY_BRANCH=feature/companion-ai ./scripts/deploy-companion-gce.sh
```

**Smoke từ Mac:**

```bash
curl -s https://vstock-api.antunai.com/v1/companion/health
curl -s -X POST https://vstock-api.antunai.com/v1/companion/chat \
  -H 'Content-Type: application/json' \
  -d '{"messages":[{"role":"user","content":"FPT giá bao nhiêu?"}],"stream":false,"context":{"screen":"Watchlist","watchlistSymbols":["FPT"]}}'
```

App Expo: `EXPO_PUBLIC_DEVICE_API_URL=https://vstock-api.antunai.com` (đã có trong `.env.development`).

**Local**

```bash
cd backend
export GEMINI_API_KEY='...'   # Google AI Studio
uvicorn app.main:app --reload --port 8000
# smoke: curl -s localhost:8000/v1/companion/health
```

**GCE (Vertex ADC — khuyến nghị production)**

1. Trên VM / service account gắn role `roles/aiplatform.user`.
2. Export env trước `docker compose up` (hoặc file `.env` cạnh compose):

```bash
export GCP_PROJECT="$(gcloud config get-value project)"
export GCP_LOCATION=asia-southeast1
# Không cần GEMINI_API_KEY nếu dùng ADC + Vertex
docker compose up -d --build
curl -s "http://127.0.0.1:8000/v1/companion/health"
```

3. App trỏ `EXPO_PUBLIC_API_URL` về API VM như bình thường.

**Smoke nhanh**

```bash
curl -s http://127.0.0.1:8000/v1/companion/health
curl -s -X POST http://127.0.0.1:8000/v1/companion/nudge \
  -H 'Content-Type: application/json' \
  -d '{"events":[{"type":"view_detail","symbol":"HAG","ts":'"$(($(date +%s)*1000))"'},{"type":"view_detail","symbol":"HAG","ts":'"$(($(date +%s)*1000-1000))"'},{"type":"view_detail","symbol":"HAG","ts":'"$(($(date +%s)*1000-2000))"'}],"context":{"screen":"Detail","symbol":"HAG"}}'
```

---

## Tài liệu liên quan trong repo

| File | Mô tả |
|------|--------|
| `docker-compose.yml` | Orchestration production |
| `backend/Dockerfile` | Image API |
| `docs/DEPLOY.md` | Tổng quan deploy (Fly.io, Railway, Docker chung) |

---

## Ghi chú khi triển khai thật

```
Project ID:     (xem: gcloud config get-value project)
VM name:        vstock-api
Zone:           asia-southeast1-a
Machine type:   n2-standard-2 (2 vCPU, 8 GB) — nâng từ e2-small 2026-07-31
External IP:    34.124.179.140
Domain:         vstock-api.antunai.com
API URL:        https://vstock-api.antunai.com
App .env:       EXPO_PUBLIC_API_URL=https://vstock-api.antunai.com
Deploy date:    2026-07-20
Backup:         cron Chủ nhật 03:00 VN → ~/backups/ (scripts/backup-sqlite.sh)
Firewall:       allow-vstock-api (TCP 8000) + HTTP/HTTPS tags
EAS / alerts:   Config sẵn — chờ Apple Developer rồi làm theo docs/EAS-DEV-BUILD.md
```

> IP ephemeral có thể đổi nếu stop/start VM — cập nhật lại dòng External IP / API URL / `.env` nếu đổi.
