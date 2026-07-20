from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_QUOTE_PROVIDERS: list[dict[str, Any]] = [
    {"name": "vps", "priority": 1, "type": "realtime", "batch": True},
    {"name": "ssi_iboard", "priority": 2, "type": "realtime", "batch": False},
    {"name": "entrade_stale", "priority": 3, "type": "stale", "batch": True},
    {"name": "kbs_stale", "priority": 4, "type": "stale", "batch": False},
]

DEFAULT_QUOTE_SYMBOLS = [
    "VNM", "FPT", "VIC", "HPG", "MWG", "VCB", "TCB", "MBB", "GAS", "MSN",
]

DEFAULT_NEWS_PROVIDERS: list[dict[str, Any]] = [
    {
        "name": "vndirect",
        "priority": 1,
        "groups": [
            "stock_news",
            "macro_news",
            "company_news",
            "disclosure",
            "commodity_news",
            "real_estate_news",
        ],
    },
    {
        "name": "vnexpress_rss",
        "priority": 2,
        "url": "https://vnexpress.net/rss/kinh-doanh.rss",
        "source": "VnExpress",
        "category": "stock_news",
    },
    {
        "name": "thanhnien_rss",
        "priority": 3,
        "url": "https://thanhnien.vn/rss/kinh-te.rss",
        "source": "Thanh Niên",
        "category": "macro_news",
    },
]


@dataclass(frozen=True)
class IngestionSettings:
    quote_symbols: tuple[str, ...]
    quote_interval_open_seconds: int
    quote_interval_closed_seconds: int
    skip_when_market_closed: bool
    news_interval_seconds: int
    news_market_limit: int
    news_max_rows: int
    indices_interval_seconds: int
    history_intraday_interval_seconds: int
    history_daily_hour: int
    history_daily_minute: int
    symbols_interval_seconds: int
    fundamentals_interval_seconds: int


def _config_path() -> Path:
    return Path(__file__).resolve().parents[2] / "config" / "providers.yaml"


def _load_yaml() -> dict[str, Any]:
    path = _config_path()
    if not path.exists():
        return {}

    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError:
        return {}

    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return raw if isinstance(raw, dict) else {}


def load_news_providers() -> list[dict[str, Any]]:
    raw = _load_yaml()
    providers = raw.get("news", {}).get("providers")
    if not isinstance(providers, list) or not providers:
        return DEFAULT_NEWS_PROVIDERS

    cleaned: list[dict[str, Any]] = []
    for item in providers:
        if not isinstance(item, dict) or not item.get("name"):
            continue
        cleaned.append(item)

    return cleaned or DEFAULT_NEWS_PROVIDERS


def load_quote_providers() -> list[dict[str, Any]]:
    raw = _load_yaml()
    providers = raw.get("quotes", {}).get("providers")
    if not isinstance(providers, list) or not providers:
        return DEFAULT_QUOTE_PROVIDERS

    cleaned: list[dict[str, Any]] = []
    for item in providers:
        if not isinstance(item, dict) or not item.get("name"):
            continue
        cleaned.append(item)

    return cleaned or DEFAULT_QUOTE_PROVIDERS


def load_ingestion_settings() -> IngestionSettings:
    raw = _load_yaml()
    ingestion = raw.get("ingestion") if isinstance(raw.get("ingestion"), dict) else {}
    quotes = raw.get("quotes") if isinstance(raw.get("quotes"), dict) else {}
    news = raw.get("news") if isinstance(raw.get("news"), dict) else {}

    symbols_raw = ingestion.get("quote_symbols")
    if isinstance(symbols_raw, list) and symbols_raw:
        symbols = tuple(str(s).upper() for s in symbols_raw if str(s).strip())
    else:
        symbols = tuple(DEFAULT_QUOTE_SYMBOLS)

    open_interval = int(ingestion.get("quote_interval_open_seconds") or quotes.get("interval_seconds") or 15)
    closed_interval = int(ingestion.get("quote_interval_closed_seconds") or 300)
    skip_closed = bool(ingestion.get("skip_when_market_closed", True))
    news_interval = int(ingestion.get("news_interval_seconds") or news.get("ttl_seconds") or 900)
    news_limit = int(ingestion.get("news_market_limit") or 50)
    news_max_rows = int(ingestion.get("news_max_rows") or 1000)
    indices_interval = int(ingestion.get("indices_interval_seconds") or 30)
    history_intraday = int(ingestion.get("history_intraday_interval_seconds") or 300)
    history_daily_hour = int(ingestion.get("history_daily_hour") or 18)
    history_daily_minute = int(ingestion.get("history_daily_minute") or 0)
    symbols_interval = int(ingestion.get("symbols_interval_seconds") or 21600)
    fundamentals_interval = int(ingestion.get("fundamentals_interval_seconds") or 21600)

    return IngestionSettings(
        quote_symbols=symbols,
        quote_interval_open_seconds=max(5, open_interval),
        quote_interval_closed_seconds=max(30, closed_interval),
        skip_when_market_closed=skip_closed,
        news_interval_seconds=max(60, news_interval),
        news_market_limit=max(20, news_limit),
        news_max_rows=max(100, news_max_rows),
        indices_interval_seconds=max(15, indices_interval),
        history_intraday_interval_seconds=max(60, history_intraday),
        history_daily_hour=max(0, min(23, history_daily_hour)),
        history_daily_minute=max(0, min(59, history_daily_minute)),
        symbols_interval_seconds=max(3600, symbols_interval),
        fundamentals_interval_seconds=max(3600, fundamentals_interval),
    )
