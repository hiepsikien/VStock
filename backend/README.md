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
- `GET /v1/stocks/{symbol}/sessions/{date}/recap?variant=symphony|jazz|minimalist` — manifest nhạc (peaks, thời lượng)
- `GET /v1/stocks/{symbol}/sessions/{date}/recap/audio?variant=symphony|jazz|minimalist` — file audio

## Nhạc phiên (MuseScore)

Ảnh Docker cài `musescore3`, `ffmpeg`, và soundfont miễn phí **MuseScore General** (`musescore-general-soundfont`, file `MuseScore_General_Full.sf3`). Gói này đăng ký font làm soundfont mặc định của MuseScore.

Lần đầu một mã + ngày + biến thể được soạn từ nến 1 phút ra MusicXML, MuseScore xuất WAV, rồi ffmpeg nén AAC. File nằm ở `VSTOCK_AUDIO_DIR` (mặc định `/data/audio`). Lần sau cùng số nến thì phát lại file đó. Phiên đang mở được soạn lại khi có thêm nến.

Ba biến thể: `symphony`, `jazz`, `minimalist`. Bài dài khoảng 80 giây (30 nhịp, tempo 90). Vị trí phát map đều lên các nến của phiên.

Prices are in **nghìn đồng** (same display convention as typical VN board UIs).
