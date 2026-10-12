"""Việc nặng của trang web, chỉ chạy khi bấm nút của chính nó.

Phép đo sau phí chạy vài phút, phép đếm mẫu bộ lọc vài giây. Mở trang hay bấm nút khác chỉ
đọc lần tính đã lưu. Lần tính được lưu ở bảng meta cùng khóa dữ liệu lúc bắt đầu, nên trang
biết nó đã cũ chưa, và server khởi động lại (kể cả `--reload`) không làm mất nó.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime

from app import db
from app.scheduled import VN

logger = logging.getLogger(__name__)


def stamp() -> str:
    return datetime.now(VN).strftime("%H:%M:%S %d/%m")


def _plain(key):
    """The key as it reads back from JSON, so a stored key and a fresh one compare equal."""
    return json.loads(json.dumps(key, default=str))


class Job:
    def __init__(self, meta_key: str) -> None:
        self.meta_key = meta_key
        self.task: asyncio.Task | None = None
        self.started = ""

    @property
    def running(self) -> bool:
        return self.task is not None and not self.task.done()

    def start(self, key, work: Callable[[], Awaitable[dict]]) -> bool:
        """Start one run; False when one is already going, so a double click runs it once."""
        if self.running:
            return False
        self.started = stamp()
        self.task = asyncio.create_task(self._finish(_plain(key), work))
        return True

    @property
    def _started_key(self) -> str:
        return f"{self.meta_key}_started"

    async def _finish(self, key, work: Callable[[], Awaitable[dict]]) -> None:
        # The mark outlives a restart that kills the run, so the next process can say so.
        await db.store_json(self._started_key, self.started)
        try:
            result = await work()
        except (Exception, SystemExit) as exc:
            logger.exception("%s failed", self.meta_key)
            result = {"error": str(exc) or type(exc).__name__}
        await db.store_json(self.meta_key, {"key": key, "at": stamp(), "result": result})
        await db.store_json(self._started_key, "")

    async def state(self, key) -> dict:
        stored = await db.stored_json(self.meta_key) or {}
        result = stored.get("result")
        return {
            "running": self.running,
            "started": self.started,
            "interrupted": "" if self.running else (await db.stored_json(self._started_key) or ""),
            "at": stored.get("at", ""),
            "result": result,
            "error": (result or {}).get("error") or "",
            "stale": bool(stored) and stored.get("key") != _plain(key),
        }


def status_line(
    state: dict, *, what: str, button: str, takes: str, refresh: int, session_busy: bool
) -> dict:
    """The one line above a job's output: never run, running, failed, stale or current."""
    at = state["at"]
    if state["running"]:
        text = (
            f"Đang tính {what}, bắt đầu lúc {state['started']}. {takes}; các trang khác vẫn dùng "
            f"được, trang này tự tải lại sau {refresh} giây."
        )
        if state["result"] and not state["error"]:
            text += f" Số dưới đây là lần tính lúc {at}."
        return {"text": text, "kind": "ok"}
    if state.get("interrupted"):
        text = (
            f"Lần tính bắt đầu lúc {state['interrupted']} bị dừng giữa chừng (server khởi động lại "
            f"hoặc bị tắt) nên không có kết quả. Bấm “{button}” để tính lại."
        )
        if state["result"] and not state["error"]:
            text += f" Số dưới đây là lần tính lúc {at}."
        kind = "bad"
    elif state["error"]:
        text, kind = f"Lần tính lúc {at} lỗi: {state['error']}", "bad"
    elif not state["result"]:
        text, kind = f"Chưa tính {what}. Bấm “{button}” để tính; {takes[0].lower()}{takes[1:]}.", ""
    elif state["stale"]:
        text = (
            f"Tính lúc {at}. Từ đó đã có lần chạy phiên mới hoặc danh sách mã đã đổi, nên số dưới "
            f"đây có thể đã cũ. Bấm “{button}” để tính lại."
        )
        kind = "bad"
    else:
        text, kind = f"Tính lúc {at}, khớp với lần chạy phiên và danh sách mã hiện tại.", ""
    if session_busy:
        text += " Đang chạy phiên; đợi phiên xong rồi mới bấm được."
    return {"text": text, "kind": kind}
