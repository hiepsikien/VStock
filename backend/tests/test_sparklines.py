from __future__ import annotations

import array
import asyncio
import wave
from pathlib import Path

import aiosqlite

from app.ingestion.providers.entrade_indices import ENTRADE_INDEX
from app.services import history, symbols as symbols_service
from app.services.cache import cache
from app.services.sessions import ENTRADE_OHLC, _ohlc_url
from app.sonify.audio import waveform_peaks_with_level


class FakeHistoryRepo:
    def __init__(self, stored: dict[tuple[str, str], list[float]]):
        self.stored = stored
        self.calls: list[tuple[tuple[str, ...], str]] = []

    async def get_many(self, symbols: list[str], chart_range: str) -> dict[str, list[float]]:
        self.calls.append((tuple(symbols), chart_range))
        return {
            symbol: prices
            for symbol in symbols
            if (prices := self.stored.get((symbol, chart_range)))
        }

    async def range_coverage(self) -> dict[str, list[str]]:
        return {}


def test_fallback_ranges_only_go_shorter() -> None:
    assert history._fallback_ranges("1D") == ["1D"]
    assert history._fallback_ranges("1M") == ["1M", "1W", "1D"]
    assert history._fallback_ranges("1Y") == ["1Y", "3M", "1M", "1W", "1D"]


def test_fetch_sparklines_falls_back_per_symbol(monkeypatch) -> None:
    fake = FakeHistoryRepo(
        {
            ("VNM", "1Y"): [1, 2, 3],
            ("FPT", "3M"): [4, 5, 6],
            ("FPT", "1D"): [7, 8],
        }
    )
    monkeypatch.setattr(history, "_repo", fake)

    rows = asyncio.run(history.fetch_sparklines(["VNM", "FPT", "ZZZ"], "1Y"))

    assert rows["VNM"]["range"] == "1Y"
    assert rows["FPT"]["range"] == "3M"
    assert "ZZZ" not in rows
    ranges = [range_key for _symbols, range_key in fake.calls]
    assert ranges[:2] == ["1Y", "3M"]
    assert "1Y" not in ranges[1:]


def test_fetch_coverage_sorts_ranges_in_chart_order(monkeypatch) -> None:
    class FakeCoverage:
        async def range_coverage(self) -> dict[str, list[str]]:
            return {"VNM": ["1M", "1D", "1Y"], "FPT": ["1W"]}

    monkeypatch.setattr(symbols_service, "_history_repo", FakeCoverage())
    cache.clear()
    try:
        coverage = asyncio.run(symbols_service.fetch_coverage())
    finally:
        cache.clear()

    assert coverage["VNM"]["ranges"] == ["1D", "1M", "1Y"]
    assert coverage["FPT"]["ranges"] == ["1W"]


def test_ohlc_url_routes_indices_and_stocks() -> None:
    assert _ohlc_url("VNINDEX") == ENTRADE_INDEX
    assert _ohlc_url("hnx") == ENTRADE_INDEX
    assert _ohlc_url("VNM") == ENTRADE_OHLC


def test_history_repo_get_many_and_coverage(monkeypatch) -> None:
    async def run() -> None:
        import app.repositories.history_repo as repo_module
        from app.repositories.history_repo import HistoryRepository

        conn = await aiosqlite.connect(":memory:")
        conn.row_factory = aiosqlite.Row
        await conn.execute(
            "CREATE TABLE history (symbol TEXT, range_key TEXT, prices TEXT)"
        )
        await conn.executemany(
            "INSERT INTO history VALUES (?, ?, ?)",
            [("VNM", "1D", "[1,2]"), ("FPT", "1M", "[3,4]")],
        )
        await conn.commit()

        async def fake_get_db():
            return conn

        monkeypatch.setattr(repo_module, "get_db", fake_get_db)
        try:
            repo = HistoryRepository()
            assert await repo.get_many(["VNM", "FPT"], "1D") == {"VNM": [1.0, 2.0]}
            assert await repo.range_coverage() == {"VNM": ["1D"], "FPT": ["1M"]}
        finally:
            await conn.close()

    asyncio.run(run())


def test_waveform_peaks_with_level(tmp_path: Path) -> None:
    path = tmp_path / "level.wav"
    samples = array.array("h", [0, 8000, -8000, 0] * 100)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(8000)
        handle.writeframes(samples.tobytes())

    duration, peaks, level = waveform_peaks_with_level(path, buckets=4)

    assert duration > 0
    assert len(peaks) == 4
    assert max(peaks) == 1.0
    assert 0 < level <= 1
