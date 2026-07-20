from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

VN = ZoneInfo("Asia/Ho_Chi_Minh")


def is_market_open(now: datetime | None = None) -> bool:
    """HOSE/HNX regular session, Mon–Fri."""
    now = now or datetime.now(VN)
    if now.weekday() >= 5:
        return False
    minutes = now.hour * 60 + now.minute
    morning = 9 * 60 <= minutes < 11 * 60 + 30
    afternoon = 13 * 60 <= minutes < 14 * 60 + 45
    return morning or afternoon


def session_label() -> str:
    return "open" if is_market_open() else "closed"
