"""Chạy một phiên từ dòng lệnh, cho lịch chạy sau giờ đóng cửa.

Chạy từ thư mục research:

    PYTHONPATH=. .venv/bin/python -m app.scheduled               # chạy ngay
    PYTHONPATH=. .venv/bin/python -m app.scheduled --after-close  # bỏ qua nếu đang trong phiên

Không cần server web: lệnh tự mở kho, chạy `run_session`, rồi in kết quả kèm trạng thái độ rộng
đã lưu cho phiên VN-Index mới nhất. Phiên lỗi, phiên chạy xong mà không có trạng thái độ rộng, hoặc
nến VN-Index chưa tới phiên lẽ ra đã đóng cửa, gửi cảnh báo Telegram nếu đã cấu hình và thoát với
mã 1.

Phiên nào không có trạng thái độ rộng thì mọi tín hiệu của phiên đó bị loại khỏi phép đo bộ lọc độ
rộng, và không được tính bù (docs/breadth-signal-filter.md).
"""

from __future__ import annotations

import argparse
import asyncio
import html
import logging
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from app import db, notify
from app.config import BREADTH_STATE_SERIES
from app.pipeline import run_session

VN = ZoneInfo("Asia/Ho_Chi_Minh")
SESSION_OPEN = time(9, 0)
SESSION_CLOSE = time(15, 0)


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


def breadth_line(index_day: str | None, states: list[tuple[str, float]], expected: str) -> tuple[str, bool]:
    if index_day is None:
        return "Độ rộng chưa chấm: chưa có nến VN-Index.", False
    stored = dict(states)
    if index_day not in stored:
        return f"Độ rộng phiên {index_day}: chưa ghi.", False
    line = f"Độ rộng phiên {index_day}: {'mở' if stored[index_day] >= 0.5 else 'đóng'}."
    if index_day < expected:
        return line + f" Chưa có nến phiên {expected}: nguồn chưa cập nhật, hoặc là ngày nghỉ.", False
    return line, True


async def _once(expected: str) -> tuple[str, bool]:
    await db.init_db()
    try:
        message = await run_session()
        index = await db.bars("VNINDEX")
        points = await db.market_points()
    finally:
        await db.close_db()
    line, recorded = breadth_line(
        str(index[-1]["trade_date"]) if index else None, points.get(BREADTH_STATE_SERIES) or [], expected
    )
    ok = recorded and not message.startswith("Phiên lỗi")
    text = f"{message}\n{line}"
    if not ok:
        await notify.send("VStock research — lịch chạy cần xem lại\n" + html.escape(text, quote=False))
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
    text, ok = asyncio.run(_once(expected_session(now)))
    print(f"{now:%Y-%m-%d %H:%M} {text}")
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
