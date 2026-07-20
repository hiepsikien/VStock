from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ChartRange = Literal["1D", "1W", "1M", "3M", "1Y", "5Y"]

DEFAULT_WATCHLIST = [
    "VNM",
    "FPT",
    "VIC",
    "HPG",
    "MWG",
    "VCB",
    "TCB",
    "MBB",
    "GAS",
    "MSN",
]


class WatchlistItem(BaseModel):
    symbol: str
    name: str
    exchange: str
    price: float
    change: float
    changePercent: float
    volume: int
    currency: str = "₫"
    sparkline: list[float] = Field(default_factory=list)


class StockDetail(BaseModel):
    symbol: str
    name: str
    exchange: str
    price: float
    change: float
    changePercent: float
    open: float
    high: float
    low: float
    volume: int
    marketCap: str
    pe: float | None
    currency: str = "₫"
    sparkline: list[float] = Field(default_factory=list)


class HistoryResponse(BaseModel):
    symbol: str
    range: ChartRange
    prices: list[float]


class HealthResponse(BaseModel):
    status: str
    service: str = "vstock-api"


class ProviderHealth(BaseModel):
    kind: str
    name: str
    status: str
    lastSuccessAt: str | None = None
    lastErrorAt: str | None = None
    lastError: str | None = None
    lastItemCount: int = 0
    stale: bool = False


class StoreHealth(BaseModel):
    quotesCount: int = 0
    quotesLatestAt: str | None = None
    newsCount: int = 0
    newsLatestAt: str | None = None
    indicesCount: int = 0
    indicesLatestAt: str | None = None
    historyCount: int = 0
    historyLatestAt: str | None = None
    symbolsCount: int = 0
    symbolsLatestAt: str | None = None
    fundamentalsCount: int = 0
    fundamentalsLatestAt: str | None = None


class JobHealth(BaseModel):
    name: str
    lastRunAt: str | None = None
    lastSuccessAt: str | None = None
    lastErrorAt: str | None = None
    lastError: str | None = None
    lastItemCount: int = 0


class SourceHealthResponse(BaseModel):
    status: str
    checkedAt: str
    marketOpen: bool
    store: StoreHealth
    providers: list[ProviderHealth]
    jobs: list[JobHealth]


class MarketStatusResponse(BaseModel):
    open: bool
    session: str
    timezone: str = "Asia/Ho_Chi_Minh"
    quoteCacheTtlSeconds: int = 15


class SymbolInfo(BaseModel):
    symbol: str
    name: str
    exchange: str


class SymbolsResponse(BaseModel):
    count: int
    symbols: list[SymbolInfo]


class NewsItem(BaseModel):
    id: str
    title: str
    summary: str
    source: str
    publishedAt: str
    url: str
    imageUrl: str | None = None
    symbols: list[str] = Field(default_factory=list)
    category: str = "news"


class NewsResponse(BaseModel):
    items: list[NewsItem]


class IndexQuote(BaseModel):
    symbol: str
    name: str
    exchange: str
    price: float
    change: float
    changePercent: float


class IndicesResponse(BaseModel):
    items: list[IndexQuote]
