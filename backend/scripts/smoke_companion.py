#!/usr/bin/env python3
"""Local smoke for Companion routes (no full app lifespan)."""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.companion import router
from app.services.gemini_companion import scrub_advice


def main() -> None:
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    health = client.get("/v1/companion/health")
    assert health.status_code == 200, health.text
    print("OK health", health.json())

    now = int(time.time() * 1000)
    events = [
        {"type": "view_detail", "symbol": "HAG", "ts": now - i * 1000} for i in range(3)
    ]
    nudge = client.post(
        "/v1/companion/nudge",
        json={"events": events, "context": {"screen": "Detail", "symbol": "HAG"}},
    )
    assert nudge.status_code == 200, nudge.text
    body = nudge.json()
    assert body.get("show") is True and body.get("message"), body
    print("OK nudge", body["message"])

    scrubbed = scrub_advice("Bạn nên mua VNM ngay hôm nay")
    assert "không đưa khuyến nghị" in scrubbed.lower() or "khuyến nghị" in scrubbed
    print("OK scrub")

    chat = client.post(
        "/v1/companion/chat",
        json={
            "messages": [{"role": "user", "content": "xin chào"}],
            "stream": False,
        },
    )
    # 503 without API key is expected locally until GEMINI_API_KEY is set.
    assert chat.status_code in (200, 503), chat.text
    print("OK chat status", chat.status_code)
    print("Companion smoke passed.")


if __name__ == "__main__":
    main()
