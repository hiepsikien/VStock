from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter

from app.health import state as health_state
from app.ingestion.config import load_news_providers, load_quote_providers
from app.repositories.indices_repo import IndicesRepository
from app.repositories.news_repo import NewsRepository
from app.repositories.quotes_repo import QuotesRepository
from app.schemas import JobHealth, ProviderHealth, SourceHealthResponse, StoreHealth
from app.services.market_session import is_market_open

router = APIRouter(prefix="/v1/health")

_quotes_repo = QuotesRepository()
_news_repo = NewsRepository()
_indices_repo = IndicesRepository()

_QUOTE_STALE_SECONDS = 300
_NEWS_STALE_SECONDS = 1800
_INDICES_STALE_SECONDS = 120


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _is_stale(value: str | None, max_age_seconds: int) -> bool:
    parsed = _parse_iso(value)
    if parsed is None:
        return True
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    age = (datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).total_seconds()
    return age > max_age_seconds


def _provider_stale(record: health_state.ProviderRecord) -> bool:
    if record.kind == "quotes":
        max_age = _QUOTE_STALE_SECONDS
    elif record.kind == "indices":
        max_age = _INDICES_STALE_SECONDS
    else:
        max_age = _NEWS_STALE_SECONDS
    if record.status != "ok":
        return record.status != "unknown"
    return _is_stale(record.last_success_at, max_age)


@router.get("/sources", response_model=SourceHealthResponse)
async def get_source_health() -> SourceHealthResponse:
    quote_stats = await _quotes_repo.stats()
    news_stats = await _news_repo.stats()
    indices_stats = await _indices_repo.stats()
    market_open = is_market_open()

    store = StoreHealth(
        quotesCount=int(quote_stats["count"]),
        quotesLatestAt=quote_stats.get("latestUpdatedAt"),
        newsCount=int(news_stats["count"]),
        newsLatestAt=news_stats.get("latestUpdatedAt"),
        indicesCount=int(indices_stats["count"]),
        indicesLatestAt=indices_stats.get("latestUpdatedAt"),
    )

    providers: list[ProviderHealth] = []

    for row in load_quote_providers():
        name = str(row.get("name", "")).strip()
        if name:
            health_state.ensure_provider("quotes", name)
    for row in load_news_providers():
        name = str(row.get("name", "")).strip()
        if name:
            health_state.ensure_provider("news", name)
    health_state.ensure_provider("indices", "entrade")

    for record in health_state.list_providers():
        stale = _provider_stale(record)
        status = record.status
        if status == "ok" and stale:
            status = "degraded"
        providers.append(
            ProviderHealth(
                kind=record.kind,
                name=record.name,
                status=status,
                lastSuccessAt=record.last_success_at,
                lastErrorAt=record.last_error_at,
                lastError=record.last_error,
                lastItemCount=record.last_item_count,
                stale=stale,
            )
        )

    jobs = [
        JobHealth(
            name=job.name,
            lastRunAt=job.last_run_at,
            lastSuccessAt=job.last_success_at,
            lastErrorAt=job.last_error_at,
            lastError=job.last_error,
            lastItemCount=job.last_item_count,
        )
        for job in health_state.list_jobs()
    ]

    overall = "ok"
    if any(p.status == "down" for p in providers):
        overall = "degraded"
    if market_open and _is_stale(store.quotesLatestAt, _QUOTE_STALE_SECONDS):
        overall = "degraded"
    if market_open and _is_stale(store.indicesLatestAt, _INDICES_STALE_SECONDS):
        overall = "degraded"
    if _is_stale(store.newsLatestAt, _NEWS_STALE_SECONDS):
        overall = "degraded"
    if store.quotesCount == 0 and store.newsCount == 0 and store.indicesCount == 0:
        overall = "down"

    return SourceHealthResponse(
        status=overall,
        checkedAt=datetime.now(timezone.utc).isoformat(),
        marketOpen=market_open,
        store=store,
        providers=providers,
        jobs=jobs,
    )
