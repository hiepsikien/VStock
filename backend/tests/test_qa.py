"""QA sheet for the phase-1 daily symphony meter."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.stocks import router
from app.schemas import SonifyQaResponse
from app.sonify.model import Bar
from app.sonify.qa import ratio_total, score_daily_bars


def _line(payload: dict, block: str, label: str) -> str:
    section = next(item for item in payload["blocks"] if item["title"] == block)
    return next(line["value"] for line in section["lines"] if line["label"] == label)


def _hint(payload: dict, label: str) -> str:
    for block in payload["blocks"]:
        for line in block["lines"]:
            if line["label"] == label:
                return line["hint"]
    raise AssertionError(label)


def test_daily_symphony_sheet_reports_gates_and_skips_one_regime() -> None:
    closes = [100.0 + index * 0.4 for index in range(40)]
    bars = [Bar(close, 1_000.0 * (index + 1), close) for index, close in enumerate(closes)]
    payload = score_daily_bars("VNM", bars, "classic")

    SonifyQaResponse(symbol="VNM", date="2026-10-23", ensemble="classic", **payload)
    assert payload["gatesPass"] is True
    assert payload["chip"] == "QA · đạt"
    assert _line(payload, "Cổng", "Nến trên thân") == "Đạt"
    assert _line(payload, "Cổng", "Khung p → ppp") == "Đạt"
    assert _line(payload, "Trung thực", "F1 hướng") != "—"
    assert _line(payload, "Trung thực", "F6 lift") != "—"
    assert _line(payload, "Đối chứng", "Xáo regime F6") == "Bỏ qua"
    assert any("đối chứng xáo bỏ qua" in note for note in payload["notes"])
    hints = [line["hint"] for block in payload["blocks"] for line in block["lines"]]
    assert hints and all(hints)
    assert "lead và support" in _hint(payload, "F3 lead/support")
    assert "đáy" in _hint(payload, "F4 điểm ngoặt")
    assert "cùng đi một hướng" in _hint(payload, "M2 quãng 5 song song")
    total = _line(payload, "Tổng", "Điểm tổng")
    assert total.endswith("/4")
    assert "F5" in _hint(payload, "Điểm tổng")
    assert payload["chip"] == "QA · đạt"
    assert "dương rõ" in _hint(payload, "Xáo regime F6")


def test_ratio_total_maps_spearman_and_skips_missing_parts() -> None:
    assert ratio_total(1, 1, 1, 1) == (1, 4)
    assert ratio_total(0, -1, 0, 0) == (0, 4)
    mean, count = ratio_total(0.8, 0, None, 1)
    assert count == 3
    assert mean == (0.8 + 0.5 + 1) / 3
    assert ratio_total(None, None, None, None) == (None, 0)


def test_flat_session_omits_contour_from_the_total() -> None:
    bars = [Bar(50.0, 1_000.0, 50.0) for _ in range(30)]
    payload = score_daily_bars("VNM", bars, "classic")
    assert _line(payload, "Trung thực", "F1 hướng") == "—"
    assert _line(payload, "Tổng", "Điểm tổng").endswith("· 1/4")


def test_recap_score_route_is_symphony_only(monkeypatch) -> None:
    app = FastAPI()
    app.include_router(router)

    async def _bars(_symbol: str, _day) -> list[Bar]:
        raise AssertionError("jazz does not load candles")

    monkeypatch.setattr("app.routers.stocks.load_session_bars", _bars)
    with TestClient(app) as client:
        response = client.get("/v1/stocks/VNM/sessions/2026-10-23/recap/score?variant=jazz")
    assert response.status_code == 404


def test_recap_score_route_returns_the_sheet(monkeypatch) -> None:
    app = FastAPI()
    app.include_router(router)

    async def _bars(_symbol: str, _day) -> list[Bar]:
        return [Bar(100.0, 1_000.0, 100.0)]

    def _sheet(_symbol: str, _bars: list[Bar], _ensemble: str) -> dict[str, object]:
        return {
            "gatesPass": True,
            "chip": "QA · đạt",
            "blocks": [
                {
                    "title": "Cổng",
                    "lines": [{"label": "Nến trên thân", "value": "Đạt", "hint": "Nến nằm trên ô thân."}],
                }
            ],
            "notes": [],
        }

    monkeypatch.setattr("app.routers.stocks.load_session_bars", _bars)
    monkeypatch.setattr("app.routers.stocks.score_daily_bars", _sheet)
    with TestClient(app) as client:
        response = client.get("/v1/stocks/vnm/sessions/2026-10-23/recap/score")
    assert response.status_code == 200
    body = response.json()
    assert body["symbol"] == "VNM"
    assert body["date"] == "2026-10-23"
    assert body["chip"] == "QA · đạt"
    assert body["blocks"][0]["lines"][0]["value"] == "Đạt"
