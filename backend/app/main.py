from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.ingestion.jobs.news import ingest_news
from app.ingestion.jobs.quotes import ingest_quotes
from app.ingestion.scheduler import start_scheduler, stop_scheduler
from app.routers.health import router as health_router
from app.routers.news import router as news_router
from app.routers.stocks import router as stocks_router
from app.schemas import HealthResponse
from app.store.db import close_db, init_db


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await init_db()
    await ingest_quotes(force=True)
    await ingest_news(force=True)
    start_scheduler()
    yield
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


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")
