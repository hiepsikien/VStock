# VStock API

FastAPI backend that aggregates open Vietnam market data for the Expo app.

## Sources (public, no API key)

| Data | Source |
|------|--------|
| Quotes | VPS `bgapidatafeed.vps.com.vn` |
| OHLCV history | Entrade / DNSE chart API |
| Name / shares / market cap | VNDirect + SSI (KBS PE when available) |

Intended for personal / educational use. Respect upstream terms and rate limits.

## Run (local)

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Mac + MuseScore + Metro

Hai terminal, cùng Wi-Fi với điện thoại. Không dùng `expo start --tunnel` (điện thoại sẽ không tới được uvicorn).

```bash
brew install --cask musescore
brew install ffmpeg
backend/scripts/run_local.sh
```

Terminal kia, ở thư mục gốc repo:

```bash
npm run start:local
```

`start:local` bật `EXPO_PUBLIC_LOCAL_API=1`. Simulator dùng `http://localhost:8000`. Máy thật lấy IP LAN của Metro và gọi `http://<ip-metro>:8000`. Lần đầu macOS có thể hỏi cho phép mạng nội bộ và kết nối đến cổng 8000.

Mở MuseScore một lần và đóng hộp thoại khởi động trước khi bấm Nghe. App tìm binary trong `/Applications/MuseScore 4.app`. Đổi ngày chỉ tải nến; MuseScore chạy khi bấm Nghe. Audio cache: `backend/var/audio` (hoặc `VSTOCK_AUDIO_DIR`).

MuseScore 3 nhận `MUSESCORE_SOUNDFONT` qua `-c`: `synthesizer.xml` chọn file, `MuseScore3.ini` thêm thư mục chứa font vào đường tìm. MuseScore 4 không có `--config-folder`, nên biến đó không đổi font — app dùng soundfont đi kèm. Một tiến trình export tại một thời điểm (`VSTOCK_MUSESCORE_SLOTS`, mặc định 1).

## Deploy (production)

**Google Cloud GCE (kế hoạch chính):** **[docs/DEPLOY-GCE.md](../docs/DEPLOY-GCE.md)**

Tổng quan các phương án khác (Docker, Fly.io): **[docs/DEPLOY.md](../docs/DEPLOY.md)**

```bash
docker compose up -d --build
```

SQLite path: `VSTOCK_DB_PATH` (mặc định trong container: `/data/vstock.db`).

## Sentry

Set `SENTRY_DSN` (project Python riêng với mobile). Optional: `SENTRY_ENVIRONMENT`, `SENTRY_TRACES_SAMPLE_RATE`.

Tạm verify: `SENTRY_DEBUG_ENDPOINT=1` rồi `curl .../sentry-debug` — tắt biến ngay sau khi thấy event trên Sentry.

## Endpoints

- `GET /health`
- `GET /v1/watchlist?symbols=VNM,FPT`
- `GET /v1/stocks/{symbol}`
- `GET /v1/stocks/{symbol}/history?range=1D|1W|1M|3M|1Y|5Y`
- `GET /v1/stocks/{symbol}/sessions?limit=7` — bảy phiên gần nhất
- `GET /v1/stocks/{symbol}/sessions/{date}` — nến 1 phút của phiên đó
- `GET /v1/stocks/{symbol}/sessions/{date}/recap?variant=symphony|jazz|minimalist` — soạn nhạc khi bấm Nghe, rồi trả manifest (peaks, thời lượng, số nến)
- `GET /v1/stocks/{symbol}/sessions/{date}/recap/audio?variant=symphony|jazz|minimalist&v={số nến}` — chỉ trả file đã soạn; 404 nếu chưa có đúng số nến đó

## Nhạc phiên (MuseScore)

Ảnh Docker cài `musescore3`, `ffmpeg`, và soundfont miễn phí **MuseScore General** (`musescore-general-soundfont`, file `/usr/share/sounds/sf3/MuseScore_General_Full.sf3`). Export truyền font đó bằng thư mục cấu hình `-c` và `synthesizer.xml`, không chỉ ghi log.

Bấm Nghe mới soạn: nến 1 phút thành MusicXML, MuseScore xuất WAV ra file tạm, ffmpeg nén AAC, rồi đổi tên vào `{mã}_{ngày}_{biến thể}_{revision}_{số nến}.m4a`. Cùng số nến thì phát lại. Phiên đang mở giữ từng snapshot để lượt tải cũ không bị file mới ghi đè. Phiên đã đóng chỉ giữ snapshot cuối. File khác revision, và file cũ hơn `VSTOCK_AUDIO_MAX_AGE_DAYS` (mặc định 30 ngày), bị xóa. `VSTOCK_AUDIO_DIR` mặc định trong container là `/data/audio`.

Ba biến thể: `symphony`, `jazz`, `minimalist`. Bài dài khoảng 80 giây (30 nhịp, tempo 90). Vị trí phát map đều lên các nến của phiên.

Prices are in **nghìn đồng** (same display convention as typical VN board UIs).
