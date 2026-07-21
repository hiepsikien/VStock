from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.ingestion.jobs.fundamentals import ingest_fundamentals
from app.ingestion.jobs.history import ingest_history_daily, ingest_history_intraday
from app.ingestion.jobs.indices import ingest_indices
from app.ingestion.jobs.news import ingest_news
from app.ingestion.jobs.quotes import ingest_quotes
from app.ingestion.jobs.symbols import ingest_symbols
from app.ingestion.scheduler import start_scheduler, stop_scheduler
from app.routers.health import router as health_router
from app.routers.news import router as news_router
from app.routers.stocks import router as stocks_router
from app.routers.companion import router as companion_router
from app.schemas import HealthResponse
from app.store.db import close_db, init_db

logger = logging.getLogger(__name__)


async def _bootstrap_ingest() -> None:
    """Warm caches without blocking HTTP startup (local Companion can answer sooner)."""
    jobs = (
        ("quotes", ingest_quotes),
        ("news", ingest_news),
        ("indices", ingest_indices),
        ("history_intraday", ingest_history_intraday),
        ("history_daily", ingest_history_daily),
        ("symbols", ingest_symbols),
        ("fundamentals", ingest_fundamentals),
    )
    for name, job in jobs:
        try:
            await job(force=True)
        except Exception:
            logger.exception("Bootstrap ingest failed: %s", name)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await init_db()
    start_scheduler()
    bootstrap = asyncio.create_task(_bootstrap_ingest())
    yield
    bootstrap.cancel()
    try:
        await bootstrap
    except asyncio.CancelledError:
        pass
    stop_scheduler()
    await close_db()


app = FastAPI(
    title="VStock API",
    description="Vietnam equity data for the VStock app (quotes, history, fundamentals).",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(stocks_router)
app.include_router(news_router)
app.include_router(health_router)
app.include_router(companion_router)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")
