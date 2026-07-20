# VStock API

FastAPI backend that aggregates open Vietnam market data for the Expo app.

## Sources (public, no API key)

| Data | Source |
|------|--------|
| Quotes | VPS `bgapidatafeed.vps.com.vn` |
| OHLCV history | Entrade / DNSE chart API |
| Name / shares / market cap | VNDirect + SSI (KBS PE when available) |

Intended for personal / educational use. Respect upstream terms and rate limits.

## Run

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Endpoints

- `GET /health`
- `GET /v1/watchlist?symbols=VNM,FPT`
- `GET /v1/stocks/{symbol}`
- `GET /v1/stocks/{symbol}/history?range=1D|1W|1M|3M|1Y|5Y`

Prices are in **nghìn đồng** (same display convention as typical VN board UIs).
