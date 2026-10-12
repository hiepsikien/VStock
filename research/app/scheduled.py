"""Chạy một phiên từ dòng lệnh, cho lịch chạy sau giờ đóng cửa.

Chạy từ thư mục research:

    PYTHONPATH=. .venv/bin/python -m app.scheduled               # chạy ngay
    PYTHONPATH=. .venv/bin/python -m app.scheduled --after-close  # bỏ qua nếu đang trong phiên

Không cần server web: lệnh tự mở kho, chạy `run_session`, rồi in kết quả kèm trạng thái độ rộng
đã lưu cho phiên VN-Index mới nhất. Phiên lỗi, phiên chạy xong mà không có trạng thái độ rộng, hoặc
nến VN-Index chưa tới phiên lẽ ra đã đóng cửa thì thoát với mã 1. Cảnh báo Telegram (nếu đã cấu
hình) đi ngay khi phiên lỗi hay thiếu trạng thái; thiếu nến chỉ báo ở lần thử cuối, sáng hôm sau,
và một chuỗi ngày nghỉ chỉ báo một lần. Phiên đo nào đã qua mà không có trạng thái độ rộng (không
ghi bù được) thì báo một lần, dù các lần chạy trước bị bỏ lỡ vì lý do gì. Nếu server web đang chạy
phiên, lệnh chờ nó xong.

Phiên nào không có trạng thái độ rộng thì mọi tín hiệu của phiên đó bị loại khỏi phép đo bộ lọc độ
rộng, và không được tính bù (docs/breadth-signal-filter.md).
"""

from __future__ import annotations

import argparse
import asyncio
import html
import logging
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app import db, notify
from app.config import BREADTH_FILTER_START, BREADTH_STATE_SERIES
from app.pipeline import BUSY_MESSAGE, run_session

VN = ZoneInfo("Asia/Ho_Chi_Minh")
SESSION_OPEN = time(9, 0)
SESSION_CLOSE = time(15, 0)
# A session started from the web takes under a minute; the scheduled run queues behind it.
SESSION_WAIT_SECONDS = 15 * 60
LOST_REPORTED_KEY = "scheduled_lost_sessions_reported"


def in_session(now: datetime) -> bool:
    """Trong giờ giao dịch thì nến phiên chưa đóng, và trạng thái độ rộng ghi lúc này chỉ là tạm."""
    local = now.astimezone(VN)
    return local.weekday() < 5 and SESSION_OPEN <= local.time() < SESSION_CLOSE


def expected_session(now: datetime) -> str:
    """Phiên mà nến ngày lẽ ra đã có: hôm nay nếu đã qua giờ đóng cửa, không thì ngày làm việc trước.

    Entrade chỉ thêm nến ngày sau giờ đóng cửa. Không biết ngày nghỉ lễ, nên ngày lễ sẽ báo thiếu.
    """
    local = now.astimezone(VN)
    if local.weekday() < 5 and local.time() >= SESSION_CLOSE:
        return local.date().isoformat()
    day = local.date() - timedelta(days=1)
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day.isoformat()


def _weekday_before(day: str) -> str:
    previous = date.fromisoformat(day) - timedelta(days=1)
    while previous.weekday() >= 5:
        previous -= timedelta(days=1)
    return previous.isoformat()


def breadth_line(index_day: str | None, states: list[tuple[str, float]], expected: str) -> tuple[str, str]:
    """The line to print and what it found: "ok", "no_index", "no_state" or "no_bar"."""
    if index_day is None:
        return "Độ rộng chưa chấm: chưa có nến VN-Index.", "no_index"
    stored = dict(states)
    if index_day not in stored:
        return f"Độ rộng phiên {index_day}: chưa ghi.", "no_state"
    line = f"Độ rộng phiên {index_day}: {'mở' if stored[index_day] >= 0.5 else 'đóng'}."
    if index_day < expected:
        return line + f" Chưa có nến phiên {expected}: nguồn chưa cập nhật, hoặc là ngày nghỉ.", "no_bar"
    return line, "ok"


def should_alert(message: str, found: str, index_day: str | None, expected: str, now: datetime) -> bool:
    """A failed run or a missing state always alerts; a missing bar only on its last try.

    Entrade adds the daily bar some time after the close, so on the day itself a missing bar is
    only late. The first run of the next day is the last try. A gap that began before the
    weekday ahead of `expected` was reported the day it began, so a holiday run (Tết) sends
    one message, not one per run.
    """
    if message.startswith("Phiên lỗi") or message == BUSY_MESSAGE:
        return True
    if found == "no_bar":
        last_try = expected != now.astimezone(VN).date().isoformat()
        return last_try and index_day == _weekday_before(expected)
    return found != "ok"


def lost_sessions(index_days: list[str], states: list[tuple[str, float]], reported: set[str]) -> list[str]:
    """Measured sessions behind the latest bar that never got a breadth state, not yet reported.

    Breadth is only written for the latest bar, so these can no longer be recorded. This catches
    a session lost whatever the clock said, e.g. a Mac asleep through all three runs that wakes
    during trading hours, when the next run already sees today's bar.
    """
    stored = {day for day, _value in states}
    return [
        day
        for day in index_days[:-1]
        if day >= BREADTH_FILTER_START and day not in stored and day not in reported
    ]


async def _once(now: datetime) -> tuple[str, bool]:
    expected = expected_session(now)
    await db.init_db()
    try:
        message = await run_session("lịch", wait=SESSION_WAIT_SECONDS)
        index = await db.bars("VNINDEX")
        states = (await db.market_points()).get(BREADTH_STATE_SERIES) or []
        reported = set(await db.stored_json(LOST_REPORTED_KEY) or [])
        lost = lost_sessions([str(bar["trade_date"]) for bar in index], states, reported)
        index_day = str(index[-1]["trade_date"]) if index else None
        line, found = breadth_line(index_day, states, expected)
        ok = found == "ok" and not message.startswith("Phiên lỗi") and message != BUSY_MESSAGE and not lost
        text = f"{message}\n{line}"
        if lost:
            text += (
                f"\nMất trạng thái độ rộng ở phiên {', '.join(lost)}: không ghi bù được, tín hiệu của "
                "các phiên này bị loại khỏi phép đo bộ lọc độ rộng."
            )
        sent = False
        if lost or should_alert(message, found, index_day, expected, now):
            sent = await notify.send("VStock research — lịch chạy cần xem lại\n" + html.escape(text, quote=False))
        # A send that failed leaves the sessions unreported, so the next run tries again.
        if lost and (sent or not notify.configured()):
            await db.store_json(LOST_REPORTED_KEY, sorted(reported | set(lost)))
    finally:
        await db.close_db()
    return text, ok


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--after-close",
        action="store_true",
        help="Bỏ qua nếu đang trong giờ giao dịch, ví dụ lần chạy bù khi máy vừa thức dậy.",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    now = datetime.now(VN)
    if args.after_close and in_session(now):
        print(f"{now:%Y-%m-%d %H:%M} đang trong giờ giao dịch: bỏ qua, chờ lần chạy sau giờ đóng cửa.")
        return
    text, ok = asyncio.run(_once(now))
    print(f"{now:%Y-%m-%d %H:%M} {text}")
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
