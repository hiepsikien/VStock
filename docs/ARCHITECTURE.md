# VStock — Kiến trúc hệ thống & kế hoạch tách Ingestion / Serving

> Tài liệu tham chiếu cho việc refactor backend nhằm tách bạch ingestion và serving,
> hỗ trợ thay đổi nguồn dữ liệu khi external APIs không ổn định.

---

## 1. Kiến trúc hiện tại (đã triển khai)

```
Mobile App (Expo)
    │
    ▼
client.ts  ──fetch──▶  FastAPI Backend (/v1/*)
                            │
              ┌─────────────┴─────────────┐
              ▼                           ▼
         Repositories                 Services (fallback live)
              │                           │
              ▼                           ▼
         SQLite store              External APIs (7 nguồn)
         (backend/data/vstock.db)
              ▲
              │
         Ingestion jobs (APScheduler)
```

### Luồng dữ liệu

**Serving:** Request → Router → Repository → SQLite (hoặc service fallback nếu store trống)

**Ingestion:** Scheduler → Provider(s) → Normalizer → SQLite. Chạy nền theo interval; không phụ thuộc request client.

Backend đã tách **ingestion / store / serving**. API contract `/v1/*` giữ nguyên; client không cần biết nguồn gốc dữ liệu.

> **Lưu ý:** SQLite nằm trên **máy chủ backend**, không phải trên thiết bị. App mobile chưa có offline cache đầy đủ — khi API down vẫn dùng `FALLBACK_WATCHLIST` hardcoded.

### External data sources

| Nguồn | URL | Dùng cho | Service file |
|-------|-----|----------|--------------|
| **VPS Datafeed** | `bgapidatafeed.vps.com.vn` | Live quotes (batch) | `services/quotes.py` |
| **Entrade / DNSE** | `services.entrade.com.vn/chart-api` | OHLCV history, sparklines | `services/history.py` |
| **Entrade / DNSE** | `services.entrade.com.vn/chart-api` | VN-Index, HNX-Index | `services/indices.py` |
| **VNDirect Finfo** | `api-finfo.vndirect.com.vn/v4/stocks` | Company names, floors, symbols | `services/fundamentals.py`, `services/symbols.py` |
| **VNDirect Finfo** | `api-finfo.vndirect.com.vn/v4/news` | Market + symbol news | `services/news.py` |
| **SSI iBoard** | `iboard-query.ssi.com.vn` | Symbol universe (primary) | `services/symbols.py` |
| **SSI iBoard** | `iboard-query.ssi.com.vn/stock/{symbol}` | Listed shares, name fallback | `services/fundamentals.py` |
| **KBS** | `kbbuddywts.kbsec.com.vn` | PE ratio, market cap override | `services/fundamentals.py` |

### Cache hiện tại (in-memory, mất khi restart)

| Cache key | TTL | Service |
|-----------|-----|---------|
| `quote:{symbol}` | 15s | quotes |
| `hist:{symbol}:{range}` | 1 hour | history |
| `fund:{symbol}` | 6 hours | fundamentals |
| `profile:{symbol}` | 24 hours | fundamentals |
| `symbols:all` | 6 hours | symbols |
| `indices:market` | 30s | indices |
| `news:market:{limit}` | 15 min | news |
| `news:symbol:{sym}:{limit}` | 15 min | news |

### Client-side

- Tất cả data qua `src/api/client.ts` → backend (không gọi thẳng external)
- News cache: in-memory + AsyncStorage (15 min TTL, stale-while-revalidate)
- User state: AsyncStorage (watchlist, alerts)
- Polling: 30s quotes khi market open + screen focused
- Background price alerts: `expo-background-task` (cần dev build)
- Fallback offline: `FALLBACK_WATCHLIST` hardcoded + banner lỗi API
- Màn **Nguồn dữ liệu** (`HealthScreen`): gọi `GET /v1/health/sources`

---

## 2. Vấn đề khi nguồn không ổn định

| Vấn đề | Chi tiết |
|--------|----------|
| **Gắn cứng nguồn** | `quotes.py` → VPS, `history.py` → Entrade. Đổi nguồn = sửa từng file |
| **Fetch-on-request** | Client poll 30s → backend gọi lại external mỗi lần cache hết. Nguồn chậm/down → app chậm/lỗi |
| **Multi-source merge trong code** | `fundamentals.py` chain VNDirect → SSI → KBS inline. Thay 1 nguồn = ảnh hưởng logic merge |
| **Cache mất khi restart** | In-memory TTL, không persist. Restart = cold cache, burst request lên external |
| **Không biết nguồn nào down** | Fail silently → fallback placeholder. Không có health per source |
| **Client phụ thuộc schema backend** | DTO ổn định (`Stock`, `NewsItem`) — điểm tốt, nhưng backend chưa tách domain khỏi provider |

### Điểm tốt hiện có

- Client chỉ gọi backend, không gọi thẳng external
- Pydantic schemas (`schemas.py`) là contract ổn định
- Client có fallback offline
- News đã có stale-while-revalidate trên client

---

## 3. Kiến trúc mục tiêu: Ingestion ↔ Store ↔ Serving

```
┌─────────────────────────────────────────────────┐
│  INGESTION LAYER (background jobs)              │
│                                                 │
│  Scheduler ──▶ Provider ──▶ Normalizer ──▶ DB  │
│                                                 │
│  providers/                                     │
│    ├── vps_quotes.py      (primary)             │
│    ├── fiin_quotes.py     (fallback)            │
│    ├── entrade_history.py                       │
│    ├── vndirect_news.py                         │
│    ├── ssi_symbols.py                           │
│    └── ...                                      │
└──────────────────────┬──────────────────────────┘
                       │ write
                       ▼
              ┌─────────────────┐
              │  DATA STORE     │
              │  SQLite/Postgres│
              └────────┬────────┘
                       │ read
                       ▼
┌─────────────────────────────────────────────────┐
│  SERVING LAYER (API — contract không đổi)       │
│                                                 │
│  FastAPI /v1/* ──▶ Repository ──▶ Store         │
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
              ┌─────────────────┐
              │  Mobile App     │
              │  client.ts      │
              └─────────────────┘
```

**Nguyên tắc:**

- **Ingestion** — job nền pull từ external, normalize, ghi store. External down không ảnh hưởng API ngay.
- **Store** — nguồn sự thật nội bộ. API đọc từ đây, không gọi external trực tiếp.
- **Serving** — API ổn định, contract không đổi. Client không cần biết nguồn gốc.

---

## 4. Cấu trúc thư mục đề xuất

```
backend/
├── app/
│   ├── main.py                    # FastAPI entry (serving only)
│   ├── schemas.py                 # API contract (giữ nguyên)
│   │
│   ├── routers/                   # SERVING — thin, chỉ đọc store
│   │   ├── stocks.py
│   │   └── news.py
│   │
│   ├── repositories/              # NEW — đọc/ghi store, không biết nguồn
│   │   ├── quotes_repo.py
│   │   ├── history_repo.py
│   │   ├── news_repo.py
│   │   ├── symbols_repo.py
│   │   └── indices_repo.py
│   │
│   ├── domain/                    # NEW — canonical models (nội bộ)
│   │   ├── quote.py               # Quote(symbol, price, change, ...)
│   │   ├── candle.py
│   │   ├── news_article.py
│   │   └── symbol_info.py
│   │
│   └── ingestion/                 # NEW — pull + normalize + persist
│       ├── scheduler.py           # APScheduler / cron
│       ├── runner.py              # orchestrate jobs
│       │
│       ├── providers/             # Interface per data type
│       │   ├── base.py            # QuoteProvider ABC
│       │   ├── vps_quotes.py      # VPS implementation
│       │   ├── entrade_history.py
│       │   ├── vndirect_news.py
│       │   ├── ssi_symbols.py
│       │   └── ...                # Thêm provider mới = file mới
│       │
│       └── normalizers/           # Raw JSON → domain model
│           ├── vps.py
│           ├── entrade.py
│           └── vndirect.py
│
├── store/                         # DB schema + migrations
│   ├── models.py                  # SQLAlchemy / SQLModel tables
│   └── migrations/
│
└── config/
    └── providers.yaml             # Bật/tắt provider, priority, TTL
```

---

## 5. Provider abstraction

```python
# ingestion/providers/base.py
class QuoteProvider(ABC):
    name: str
    priority: int          # 1 = primary, 2 = fallback

    async def fetch_quotes(self, symbols: list[str]) -> list[Quote]:
        ...

# ingestion/providers/vps_quotes.py
class VpsQuoteProvider(QuoteProvider):
    name = "vps"
    priority = 1
    # Chỉ biết VPS URL + parse VPS JSON

# ingestion/providers/fiin_quotes.py  (ví dụ nguồn mới)
class FiinQuoteProvider(QuoteProvider):
    name = "fiin"
    priority = 2
    # Chỉ biết Fiin URL + parse Fiin JSON
```

**Đổi nguồn** = thêm file provider mới + cập nhật `providers.yaml`.
Không sửa router, repository, hay client.

### Config mẫu

```yaml
# config/providers.yaml
quotes:
  primary: vps
  fallback: fiin          # tự chuyển khi primary fail
  interval_seconds: 15

history:
  primary: entrade
  fallback: null
  interval_seconds: 3600

news:
  primary: vndirect
  interval_seconds: 900

symbols:
  primary: ssi
  fallback: vndirect
  interval_seconds: 21600
```

---

## 6. Ingestion schedule

| Job | Interval | Nguồn hiện tại | Ghi chú |
|-----|----------|----------------|---------|
| **Quotes** | 15s (trong phiên) | VPS | Job quan trọng nhất |
| **Indices** | 30s (trong phiên) | Entrade | VN-Index, HNX-Index |
| **History 1D** | 5 phút (trong phiên) | Entrade | Sparkline + chart |
| **History dài hạn** | 1 lần/ngày | Entrade | 1W, 1M, 3M, 1Y, 5Y |
| **News** | 15 phút | VNDirect | 4 category queries |
| **Symbols** | 6 giờ | SSI + VNDirect | Universe + search |
| **Fundamentals** | 24 giờ | VNDirect/SSI/KBS | PE, market cap, tên |

Ngoài giờ giao dịch: quotes/indices có thể giảm xuống 5–15 phút hoặc tắt.

---

## 7. Serving layer (API — gần như không đổi)

Router chỉ đọc store qua repository:

```python
# routers/stocks.py (sau refactor)
@router.get("/v1/watchlist")
async def watchlist(symbols: str, repo: QuoteRepo = Depends()):
    syms = symbols.split(",")
    quotes = await repo.get_latest(syms)       # đọc DB, không gọi external
    profiles = await repo.get_profiles(syms)
    sparklines = await repo.get_sparklines(syms)
    return [WatchlistItem(...) for ...]
```

**Client (`client.ts`) không cần thay đổi** — contract `/v1/*` giữ nguyên.

---

## 8. Lộ trình triển khai

### Phase 1 — Provider interface + config ✅

- [x] Tách parser thành `providers/` + `normalizers/`
- [x] `providers.yaml` cho priority/fallback
- [x] Fetch-on-request qua interface (trước khi có DB)

### Phase 2 — SQLite store + ingestion jobs ✅

- [x] SQLite tại `backend/data/vstock.db`
- [x] APScheduler: quotes, news, indices, history, symbols, fundamentals
- [x] API đọc từ DB; service fallback khi store trống

### Phase 3 — Health monitoring + fallback ✅

- [x] `GET /v1/health/sources` — trạng thái provider + store counts
- [x] Auto-failover primary → fallback (quotes, symbols, news merge)
- [x] Màn Health trên app mobile

### Phase 4 — Background alerts ✅

- [x] Local push qua Expo background task (client-side, không server-side alerts)

### Chưa làm / ngoài phạm vi

- [ ] Offline cache đầy đủ trên thiết bị
- [ ] Portfolio management

---

## 9. So sánh

| | **Hiện tại** | **Sau tách** |
|---|---|---|
| Đổi nguồn quotes | Sửa `quotes.py` | Thêm `fiin_quotes.py` + config |
| External down | API 502 / fallback rỗng | API vẫn trả data cũ từ store |
| Restart backend | Cold cache, burst external | Data vẫn trong DB |
| Thêm nguồn mới | Sửa nhiều file | 1 provider + 1 normalizer |
| Client impact | — | Không đổi |
| Complexity | Thấp (~16 files) | Trung bình (~30 files + DB) |

---

## 10. Khuyến nghị

1. **Bắt đầu Phase 1** — tách provider interface. Chi phí thấp, lợi ích lớn khi VPS/Entrade/VNDirect thay đổi.
2. **SQLite cho Phase 2** — đủ cho single-server, không cần Postgres ngay.
3. **Giữ API contract** — client không đổi.
4. **Chưa cần message queue** — APScheduler + SQLite đủ cho volume hiện tại.

---

## 11. Nguồn quotes thay thế (research)

> Cập nhật: 2026-07. Dùng cho Phase 1 provider abstraction + fallback chain.
> Phân loại theo **chi phí**, **độ ổn định**, và **mức độ chính thức**.

### 11.1. Tóm tắt nhanh

| Nguồn | Free? | API key? | Realtime? | Batch? | Ghi chú |
|-------|-------|----------|-----------|--------|---------|
| **VPS** (đang dùng) | ✅ | ❌ | ✅ | ✅ | Unofficial, dễ đổi/chặn |
| **SSI iboard-query** | ✅ | ❌ | ~✅ | ❌ (1 mã/request) | Đã dùng trong `fundamentals.py` (`matchedPrice`) |
| **Entrade last bar** | ✅ | ❌ | ❌ (delay) | ✅ | Lấy nến cuối làm giá tạm — fallback khi VPS down |
| **KBS historical** | ✅ | ❌ | ❌ (delay) | ❌ | Đã dùng cho PE; có thể lấy giá đóng gần nhất |
| **SSI GraphQL** | ✅ | ❌ | ✅ | ✅ (theo sàn) | Unofficial (`gateway-iboard.ssi.com.vn/graphql`), dễ break |
| **VCI** (via vnstock) | ✅ | ❌* | ✅ | ✅ | Public endpoint bọc bởi thư viện vnstock; không official |
| **VietCap REST** | ✅ | ❌ | ✅ | ✅ | Một số toolkit JS dùng; cần verify endpoint |
| **SSI FastConnect** | ✅† | ✅ | ✅ | ✅ | †Cần mở TK SSI + đăng ký FC Data trên iBoard |
| **vnstock API** | Freemium | ✅ | ✅ | ✅ | Đăng ký free tại vnstocks.com; rate limit |
| **TCBS OpenAPI** | ✅† | ✅ | ✅ | ✅ | †Cần TK TCBS + API key; TCBS MCP ≠ REST API |
| **FMP / iTick** | Freemium/Paid | ✅ | ✅ | ✅ | Trả phí nếu scale; không ưu tiên cho app cá nhân |

\* vnstock gọi public endpoints VCI/KBS phía sau; API key vnstock là cho tier cao hơn.
† Miễn phí cho khách hàng/đăng ký, không phải anonymous public API.

---

### 11.2. Tier A — Ưu tiên cho fallback (free, không key)

#### VPS (primary hiện tại)

```
GET https://bgapidatafeed.vps.com.vn/getliststockdata/{SYMBOL1,SYMBOL2,...}
```

- **Ưu:** Batch nhiều mã, realtime trong phiên, đơn giản
- **Nhược:** Unofficial, không SLA, có thể chặn IP / đổi schema
- **VStock:** `services/quotes.py`

#### SSI iboard-query (fallback #1 — đã có sẵn trong codebase)

```
GET https://iboard-query.ssi.com.vn/stock/{SYMBOL}
```

- **Trả về:** `matchedPrice`, `exchange`, `companyName`, `listedShare`
- **Ưu:** Đang hoạt động trong VStock (`fundamentals.py`), không cần key
- **Nhược:** 1 request / mã (watchlist 10 mã = 10 calls), không batch
- **Dùng khi:** VPS down, cần giá từng mã

#### Entrade last close (fallback #2 — stale quote)

```
GET https://services.entrade.com.vn/chart-api/v2/ohlcs/stock?symbol={SYMBOL}&resolution=1D&from=...&to=...
```

- **Ưu:** Đã dùng cho history; ổn định hơn VPS
- **Nhược:** Không realtime — giá đóng phiên / nến cuối, delay vài phút đến 1 ngày
- **Dùng khi:** Tất cả nguồn realtime fail; hiển thị giá cũ + badge "trễ"

#### KBS latest bar (fallback #3)

```
GET https://kbbuddywts.kbsec.com.vn/sas/kbsv-stock-data-store/stock/{SYMBOL}/historical-quotes?from=...&to=...
```

- **Ưu:** Đã tích hợp; có thêm PE, market cap
- **Nhược:** Historical, không intraday realtime
- **Dùng khi:** Cần giá + fundamentals từ cùng nguồn

---

### 11.3. Tier B — Free, không key, unofficial (cân nhắc cẩn thận)

#### SSI GraphQL gateway

```
POST https://iboard.ssi.com.vn/gateway/graphql
query stockRealtimes($exchange: String) { stockRealtimes(exchange: $exchange) { ... matchedPrice ... } }
```

- **Ưu:** Batch theo sàn (HOSE/HNX/UPCOM), full order book
- **Nhược:** Reverse-engineered, không documented, có thể 403/block bất cứ lúc nào
- **Khuyến nghị:** Chỉ dùng fallback cuối cùng, không primary

#### VCI (public endpoints qua vnstock)

- Thư viện [vnstock](https://github.com/thinh-vu/vnstock) / [lotusmarket](https://github.com/ducnhd/lotusmarket) wrap endpoint VCI
- `Trading(source="VCI").price_board(symbols_list=[...])` — 77 cột, realtime trong phiên
- **Ưu:** Chi tiết, batch, community maintain
- **Nhược:** Endpoint có thể đổi; vnstock docs ghi TCBS deprecated (2026)
- **Khuyến nghị:** Reverse-engineer endpoint trực tiếp hoặc dùng vnstock như reference implementation

#### VietCap REST

- Một số toolkit (vd. vnstock-js) chuyển sang VietCap REST thay GraphQL
- **Khuyến nghị:** Research thêm trước khi implement; ưu tiên thấp hơn SSI/VCI

---

### 11.4. Tier C — Free với đăng ký (khi cần ổn định hơn)

#### SSI FastConnect Data (official)

```
REST:  https://fc-data.ssi.com.vn/v2.0/Market/...
Stream: wss://fc-datahub.ssi.com.vn/v2.0
Auth:   consumerID + consumerSecret (lấy từ iBoard → API Service)
```

- **Ưu:** API chính thức, documented, WebSocket realtime, batch
- **Nhược:** Cần mở tài khoản SSI + đăng ký FC Data; token expire 8h
- **Docs:** https://guide.ssi.com.vn/ssi-products/fastconnect-data
- **Khuyến nghị:** Nguồn **primary chính thức** nếu VPS không ổn định lâu dài

#### vnstock API key

- Đăng ký free: https://vnstocks.com/login
- Wrapper thống nhất VCI/KBS; có rate limit
- **Khuyến nghị:** Hữu ích cho prototyping; phụ thuộc bên thứ ba

#### TCBS OpenAPI

- Cần tài khoản TCBS + API key + OTP
- `GetStockPrices(symbols)` — official REST
- TCBS MCP Server (Claude connector) **không phải** REST API cho app
- **Khuyến nghị:** Chỉ nếu user đã có TK TCBS; không anonymous

---

### 11.5. Tier D — Trả phí (không ưu tiên)

| Nguồn | Ghi chú |
|-------|---------|
| **FMP** (Financial Modeling Prep) | Global, có VN symbols hạn chế; trả phí |
| **iTick** | Tier free hạn chế; paid cho production |
| **Bloomberg/Refinitiv** | Overkill cho app cá nhân |

---

### 11.6. Fallback chain đề xuất cho Phase 1

```yaml
# config/providers.yaml — quotes
quotes:
  providers:
    - name: vps
      priority: 1
      type: realtime
      batch: true
    - name: ssi_iboard_query
      priority: 2
      type: realtime
      batch: false          # 1 request / symbol
    - name: entrade_last_close
      priority: 3
      type: stale
      batch: true
      max_age_minutes: 1440 # chấp nhận giá tối đa 1 ngày cũ
    - name: kbs_latest
      priority: 4
      type: stale
      batch: false

  strategy: failover        # thử lần lượt theo priority
  interval_seconds: 15      # ingestion job (Phase 2)
```

**Luồng failover:**

```
VPS batch ──fail──▶ SSI per-symbol ──fail──▶ Entrade last close ──fail──▶ KBS latest
     │                    │                         │                      │
     └─ OK → normalize → domain Quote → store/API ←┘
```

**Lưu ý hiển thị UI (Phase 2+):**
- Realtime: không badge
- Stale (> 5 phút): badge "Trễ {n} phút"
- Fallback source: badge nhỏ tên nguồn (optional, debug)

---

### 11.7. So sánh nguồn cho VStock use case

| Tiêu chí | VPS | SSI query | Entrade stale | SSI FC Data |
|----------|-----|-----------|---------------|-------------|
| Setup effort | ✅ Có sẵn | ✅ Có sẵn | ✅ Có sẵn | ⚠️ Cần đăng ký |
| Batch watchlist | ✅ | ❌ | ✅ | ✅ |
| Realtime phiên | ✅ | ✅ | ❌ | ✅ |
| Ổn định lâu dài | ⚠️ | ⚠️ | ✅ | ✅ |
| Official / legal | ❌ | ❌ | ❌ | ✅ |
| Bid/ask depth | ✅ | ❌ | ❌ | ✅ |

**Kết luận:** Giữ VPS primary, thêm **SSI iboard-query** + **Entrade stale** làm fallback free ngay trong Phase 1. Khi cần ổn định production → đăng ký **SSI FastConnect Data** làm primary official.

---

### 11.8. Tham khảo open-source

| Project | Nguồn quotes | Ghi chú |
|---------|--------------|---------|
| [lotusmarket](https://github.com/ducnhd/lotusmarket) | VPS primary, Entrade backup | `stock_with_fallback()` pattern |
| [vnstock](https://github.com/thinh-vu/vnstock) | VCI, KBS | Unified API; TCBS deprecated 2026 |
| [vnstock-js](https://github.com/ttqteo/vnstock-js) | VietCap REST, SSI WS | TypeScript reference |
| [ssi-fc-data](https://pypi.org/project/ssi-fc-data/) | SSI FastConnect official | Python SDK |

---

## Phụ lục: Backend file map hiện tại

| File | Mô tả |
|------|-------|
| `app/main.py` | FastAPI entry, CORS, router mounting |
| `app/schemas.py` | Pydantic models (API contract) |
| `app/routers/stocks.py` | Stock/market/symbol/index/watchlist/history endpoints |
| `app/routers/news.py` | Market and per-symbol news endpoints |
| `app/services/cache.py` | In-memory TTL cache |
| `app/services/http_utils.py` | Browser/Entrade headers, type coercion |
| `app/services/quotes.py` | VPS quote fetching |
| `app/services/history.py` | Entrade OHLCV + sparkline |
| `app/services/fundamentals.py` | Multi-source profile (VNDirect → SSI → KBS) |
| `app/services/indices.py` | VN-Index / HNX-Index from Entrade |
| `app/services/symbols.py` | Full symbol list + search |
| `app/services/news.py` | VNDirect news aggregation |
| `app/services/market_session.py` | Local VN market hours |

## Phụ lục: Client file map

| File | Mô tả |
|------|-------|
| `src/api/client.ts` | API client, tất cả endpoints |
| `src/hooks/useMarketPolling.ts` | Poll quotes khi focused + market open |
| `src/hooks/usePriceAlerts.ts` | Check alerts khi stocks update |
| `src/storage/newsCache.ts` | News cache (memory + AsyncStorage) |
| `src/storage/watchlist.ts` | Watchlist persistence |
| `src/storage/alerts.ts` | Price alerts persistence (local) |
| `src/utils/marketSession.ts` | VN market hours, poll intervals |
| `src/types.ts` | Stock, ChartRange domain types |
| `src/types/news.ts` | NewsItem, NewsFilter types |
| `src/screens/HealthScreen.tsx` | Dev health — trạng thái ingestion / providers |
| `src/components/ApiStatusBanner.tsx` | Banner lỗi API + nút thử lại |
