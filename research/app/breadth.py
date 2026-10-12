"""Độ rộng thị trường: bao nhiêu mã của rổ 200 trong năm đang đóng cửa trên MA50.

VN-Index trên MA200 chỉ đo một chuỗi, nên vài mã vốn hóa lớn đủ kéo nó qua đường trung bình
trong khi số đông đã yếu đi. Độ rộng đếm trên chính rổ theo năm của `pit_universe`, nên mã
đã hủy niêm yết vẫn được đếm trong năm nó còn giao dịch.

Một mã chỉ được đếm ở một phiên khi:

* nến cuối của nó cách phiên đang chấm không quá `BREADTH_MAX_STALE_SESSIONS` phiên của
  VN-Index, để mã bị tạm ngừng giao dịch không đứng mãi ở giá cũ;
* nó có đủ `BREADTH_MA_WINDOW` nến tính tới nến cuối;
* cửa sổ đó không chứa một bước giá quá biên độ sàn — cùng mốc với `unadjusted_split_gap`.
  Bước như vậy là hệ số chia tách của nguồn bị lệch, và nó làm MA50 sai suốt cả cửa sổ.

Trạng thái có độ trễ hai ngưỡng: mở khi tỷ lệ chạm `BREADTH_OPEN`, đóng khi chạm
`BREADTH_CLOSE`, ở giữa thì giữ trạng thái trước. Tỷ lệ của một phiên chỉ dùng giá đóng cửa
tới hết phiên đó.

Không đọc file, không gọi mạng: hàm nhận đúng những chuỗi mà các báo cáo đã có.
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass

from app.config import (
    BREADTH_CLOSE,
    BREADTH_MA_WINDOW,
    BREADTH_MAX_STALE_SESSIONS,
    BREADTH_MIN_NAMES,
    BREADTH_OPEN,
    BREADTH_START,
)
from app.pattern import jump_limit
from app.pit_universe import Basket


@dataclass(frozen=True)
class BreadthPoint:
    share: float | None
    above: int = 0
    names: int = 0
    # Mã của rổ không được đếm, tách theo lý do để báo cáo nói được rổ hụt vì đâu.
    stale: int = 0
    short: int = 0
    broken: int = 0


class _Tape:
    """Giá đóng cửa đã điều chỉnh của một mã, với tổng cộng dồn để tính MA trong O(1)."""

    __slots__ = ("days", "closes", "sums", "breaks")

    def __init__(self, bars: list[dict], exchange: str | None) -> None:
        limit, _board = jump_limit(exchange)
        self.days: list[str] = []
        self.closes: list[float] = []
        for bar in bars:
            close = float(bar["close"])
            if close > 0:
                self.days.append(str(bar["trade_date"]))
                self.closes.append(close)
        self.sums = [0.0]
        for close in self.closes:
            self.sums.append(self.sums[-1] + close)
        self.breaks = [
            index
            for index in range(1, len(self.closes))
            if abs(self.closes[index] / self.closes[index - 1] - 1) > limit
        ]

    def last_break(self, index: int) -> int | None:
        position = bisect_right(self.breaks, index) - 1
        return self.breaks[position] if position >= 0 else None


def adjustment_breaks(bars: list[dict], exchange: str | None = None) -> list[str]:
    """Ngày của mọi bước giá quá biên độ sàn trong chuỗi đã điều chỉnh."""
    tape = _Tape(bars, exchange)
    return [tape.days[index] for index in tape.breaks]


def basket_on(baskets: dict[int, Basket], day: str) -> Basket | None:
    """Rổ của năm chứa `day`; trước phiên chốt rổ của năm thì dùng rổ năm trước."""
    year = int(day[:4])
    basket = baskets.get(year)
    if basket is not None and basket.day is not None and day >= basket.day:
        return basket
    return baskets.get(year - 1)


def breadth_by_day(
    index_days: list[str],
    bars_by_symbol: dict[str, list[dict]],
    baskets: dict[int, Basket],
    exchanges: dict[str, str] | None = None,
    *,
    window: int = BREADTH_MA_WINDOW,
    max_stale: int = BREADTH_MAX_STALE_SESSIONS,
    min_names: int = BREADTH_MIN_NAMES,
) -> dict[str, BreadthPoint]:
    """Tỷ lệ mã của rổ 200 đóng cửa trên MA của chính nó, cho từng phiên của VN-Index."""
    exchanges = exchanges or {}
    members = {symbol for basket in baskets.values() for symbol in basket.universe}
    tapes = {
        symbol: _Tape(bars_by_symbol[symbol], exchanges.get(symbol))
        for symbol in members
        if bars_by_symbol.get(symbol)
    }
    out: dict[str, BreadthPoint] = {}
    for position, day in enumerate(index_days):
        basket = basket_on(baskets, day)
        if basket is None:
            out[day] = BreadthPoint(None)
            continue
        oldest = index_days[max(0, position - max_stale)]
        above = names = stale = short = broken = 0
        for symbol in basket.universe:
            tape = tapes.get(symbol)
            index = bisect_right(tape.days, day) - 1 if tape else -1
            if index < 0 or tape.days[index] < oldest:
                stale += 1
                continue
            if index + 1 < window:
                short += 1
                continue
            # Bước gãy ở nến j so nến j với nến j-1, nên nó chỉ nằm trong cửa sổ khi cả hai
            # nến đều trong cửa sổ.
            last = tape.last_break(index)
            if last is not None and last >= index - window + 2:
                broken += 1
                continue
            average = (tape.sums[index + 1] - tape.sums[index + 1 - window]) / window
            names += 1
            if tape.closes[index] > average:
                above += 1
        share = above / names if names >= min_names else None
        out[day] = BreadthPoint(share, above, names, stale, short, broken)
    return out


def breadth_states(
    shares: list[tuple[str, float | None]],
    *,
    open_at: float = BREADTH_OPEN,
    close_at: float = BREADTH_CLOSE,
    start_at: float = BREADTH_START,
) -> dict[str, bool | None]:
    """Trạng thái cổng theo từng phiên, từ chuỗi tỷ lệ đã xếp theo ngày.

    Phiên "Chưa chấm" ra None nhưng không xóa trạng thái trước: phiên chấm được tiếp theo
    vẫn so với mốc trên và mốc dưới như thường.
    """
    out: dict[str, bool | None] = {}
    state: bool | None = None
    for day, share in shares:
        if share is None:
            out[day] = None
            continue
        if state is None:
            state = share >= start_at
        elif share >= open_at:
            state = True
        elif share <= close_at:
            state = False
        out[day] = state
    return out


@dataclass(frozen=True)
class BreadthGate:
    open: bool | None
    reason: str
    share: float | None = None


def gate_on(day: str, points: dict[str, BreadthPoint], states: dict[str, bool | None]) -> BreadthGate:
    point = points.get(day) or BreadthPoint(None)
    state = states.get(day)
    return BreadthGate(state, breadth_reason(point.share, state, point.names), point.share)


def breadth_reason(share: float | None, state: bool | None, names: int = 0) -> str:
    if share is None or state is None:
        return f"Độ rộng chưa chấm: dưới {BREADTH_MIN_NAMES} mã của rổ đủ nến"
    where = f"{share:.0%} mã của rổ trên MA{BREADTH_MA_WINDOW}" + (f" ({names} mã)" if names else "")
    if state:
        return f"Độ rộng mở: {where}, đóng khi xuống {BREADTH_CLOSE:.0%}"
    return f"Độ rộng đóng: {where}, mở khi lên {BREADTH_OPEN:.0%}"
