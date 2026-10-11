"""Rổ theo từng giai đoạn: hạng vốn hóa và thanh khoản của mọi mã còn niêm yết trong năm.

Danh sách cố định trong config chỉ có những mã sống tới hôm nay, nên rổ của quá khứ chứa
toàn mã mà người chạy biết là sẽ sống. Module này thay bằng cách xếp hạng của chính năm đó:

* một mã chỉ được xét khi nó đã niêm yết và chưa hủy niêm yết tính đến phiên chốt rổ;
* vốn hóa lấy giá thật của phiên chốt nhân số cổ phiếu đã công bố đủ 45 ngày;
* thanh khoản là trung vị giá trị khớp thật của 20 phiên ngay trước phiên chốt;
* mã thiếu vốn hóa hoặc dưới ngưỡng thanh khoản bị loại, rồi cắt ở 200 và 100.

Giá và giá trị khớp đều là giá thật của phiên, không phải giá đã điều chỉnh chia tách: số cổ
phiếu và khối lượng khớp là của chính phiên đó, nên nhân với giá đã điều chỉnh về mặt bằng hôm
nay thì mã chia tách nhiều bị đo thấp và rơi khỏi rổ. Nến chưa có cạnh thật thì quay về công
thức cũ, tức đo thấp đúng như trước khi vá.

Không đọc file, không gọi mạng: hàm nhận đúng những chuỗi mà các báo cáo đã có.
"""

from __future__ import annotations

import statistics
from bisect import bisect_right
from collections import namedtuple
from datetime import date
from typing import Callable

from app.config import (
    LIQUIDITY_LOOKBACK_SESSIONS,
    MIN_MEDIAN_TURNOVER,
    TRADE_LIMIT,
    UNIVERSE_LIMIT,
    VND_PER_PRICE_UNIT,
)
from app.valuation import market_cap

Basket = namedtuple("Basket", "day universe trade")
# Dưới mức này số mã có vốn hóa chưa đủ để chốt rổ, phiên đó bị bỏ qua và thử phiên sau.
MIN_RANKED_NAMES = 30
# Cần tối thiểu bao nhiêu phiên có giá trị giao dịch mới dám kết luận về thanh khoản.
MIN_TURNOVER_SESSIONS = 5


def listed_from(rows: dict[str, dict]) -> Callable[[str, str], bool]:
    """Hàm `listed_on(symbol, day)` từ bảng nhận diện đã lưu (`db.symbol_meta`).

    Mã có mặt khi đã niêm yết và chưa hủy tính đến hết `day`; thiếu ngày niêm yết thì coi như
    niêm yết từ trước, vì đó là dòng cũ của nguồn chứ không phải mã mới. Mã không có trong
    bảng bị coi là chưa niêm yết: rổ chỉ được dựng từ những mã nguồn đã xác nhận.
    """

    def listed_on(symbol: str, day: str) -> bool:
        meta = rows.get(symbol)
        if meta is None:
            return False
        listed = meta.get("listed_date")
        delisted = meta.get("delisted_date")
        if listed and day < listed:
            return False
        if delisted and day > delisted:
            return False
        return True

    return listed_on


class Tape:
    """Ngày, giá đóng cửa và giá trị giao dịch của một mã, tra bằng tìm nhị phân.

    Chuỗi được dựng một lần cho cả lần chấm: mỗi phiên chốt rổ hỏi hàng nghìn mã, quét lại
    nến từ đầu cho từng mã thì mất hàng phút.

    Hai chuỗi giá được giữ song song: `closes` là giá đã điều chỉnh chia tách, dùng cho chuỗi
    giá liên tục, còn `raw_closes` là giá thật của phiên, dùng để nhân với số cổ phiếu của
    chính năm đó. Nến cũ chưa có cạnh thật thì `raw_closes` bằng `closes`, tức hành vi cũ.
    """

    __slots__ = ("days", "closes", "raw_closes", "turnovers")

    def __init__(self, bars: list[dict]) -> None:
        self.days: list[str] = []
        closes: list[float] = []
        raw_closes: list[float] = []
        turnovers: list[float] = []
        for bar in bars:
            close = float(bar["close"])
            if close <= 0:
                continue
            raw = float(bar.get("raw_close") or 0)
            traded = float(bar.get("trade_value") or 0)
            self.days.append(str(bar["trade_date"]))
            closes.append(close)
            raw_closes.append(raw if raw > 0 else close)
            # Giá trị giao dịch lấy giá trị khớp thật của nguồn. Thiếu thì đo bằng giá đã điều
            # chỉnh (nghìn đồng) nhân khối lượng thật (cổ phiếu) — cách cũ, và là cách đo thấp.
            if traded > 0:
                turnovers.append(traded)
            else:
                turnovers.append(close * VND_PER_PRICE_UNIT * float(bar.get("volume") or 0))
        self.closes = closes
        self.raw_closes = raw_closes
        self.turnovers = turnovers

    def _last(self, day: str) -> int:
        """Vị trí phiên cuối cùng không muộn hơn `day`, hay -1 khi mã chưa có phiên nào."""
        return bisect_right(self.days, day) - 1

    def close_on(self, day: str) -> float | None:
        """Giá đã điều chỉnh chia tách của phiên, dùng cho chuỗi giá chứ không cho vốn hóa."""
        index = self._last(day)
        return self.closes[index] if index >= 0 else None

    def raw_close_on(self, day: str) -> float | None:
        """Giá thật của phiên, dùng cho vốn hóa vì nó nhân với số cổ phiếu của chính năm đó."""
        index = self._last(day)
        return self.raw_closes[index] if index >= 0 else None

    def median_turnover(self, day: str, sessions: int = LIQUIDITY_LOOKBACK_SESSIONS) -> float | None:
        """Trung vị giá trị giao dịch của `sessions` phiên có dữ liệu tính tới `day`.

        Trung vị chứ không phải trung bình: một phiên đột biến không đủ để đưa mã thanh khoản
        kém vào rổ. Thiếu `MIN_TURNOVER_SESSIONS` phiên thì trả None, và mã không vào rổ.
        """
        index = self._last(day)
        if index < 0:
            return None
        window = self.turnovers[max(0, index + 1 - sessions) : index + 1]
        if len(window) < MIN_TURNOVER_SESSIONS:
            return None
        return float(statistics.median(window))


def tapes(bars_by_symbol: dict[str, list[dict]]) -> dict[str, Tape]:
    return {symbol: Tape(bars) for symbol, bars in bars_by_symbol.items()}


def ranked_on(
    day: str,
    tapes_by_symbol: dict[str, Tape],
    ratios_by_symbol: dict,
    symbols,
    *,
    min_turnover: float = MIN_MEDIAN_TURNOVER,
    sessions: int = LIQUIDITY_LOOKBACK_SESSIONS,
) -> list[str]:
    """Danh sách mã của `day`, xếp từ vốn hóa lớn nhất xuống sau khi lọc thanh khoản.

    Vốn hóa nhân giá thật của phiên với số cổ phiếu đã công bố tính tới `day`. Dùng giá đã
    điều chỉnh chia tách ở đây là sai đơn vị: số cổ phiếu là của chính năm đó, còn giá đã
    điều chỉnh về mặt bằng hôm nay, nên mã chia tách nhiều bị đo thấp và rơi khỏi rổ.
    """
    as_of = date.fromisoformat(day)
    ranked = []
    for symbol in symbols:
        tape = tapes_by_symbol.get(symbol)
        if tape is None:
            continue
        close = tape.raw_close_on(day)
        if close is None:
            continue
        shares = (ratios_by_symbol.get(symbol) or {}).get("OUTSTANDING_SHARES") or []
        cap = market_cap(close, shares, as_of)
        if not cap:
            continue
        turnover = tape.median_turnover(day, sessions)
        if turnover is None or turnover < min_turnover:
            continue
        ranked.append((cap, symbol))
    ranked.sort(reverse=True)
    return [symbol for _cap, symbol in ranked]


def yearly_baskets(
    index_days: list[str],
    bars_by_symbol: dict[str, list[dict]],
    ratios_by_symbol: dict,
    listed_on,
    *,
    limit: int = UNIVERSE_LIMIT,
    trade_limit: int = TRADE_LIMIT,
    min_turnover: float = MIN_MEDIAN_TURNOVER,
    sessions: int = LIQUIDITY_LOOKBACK_SESSIONS,
    min_names: int = MIN_RANKED_NAMES,
) -> dict[int, Basket]:
    """Rổ 200 và rổ 100 của từng năm, chốt ở phiên đầu năm mà vốn hóa đã biết.

    `listed_on(symbol, day)` nói mã có đang niêm yết ở phiên đó không. Phiên chốt là phiên
    giao dịch đầu tiên của năm chứ không phải ngày 1 tháng 1, vì ngày 1 tháng 1 không phải
    phiên và số cổ phiếu quý 4 công bố muộn nhất là giữa tháng 2. Năm nào chưa đủ
    `min_names` mã có vốn hóa thì chưa chốt, và phiên sau được thử tiếp.
    """
    tube = tapes(bars_by_symbol)
    out: dict[int, Basket] = {}
    ranked_cache: dict[str, list[str]] = {}
    for day in index_days:
        year = int(day[:4])
        if year in out:
            continue
        ranked = ranked_cache.get(day)
        if ranked is None:
            ranked = ranked_on(
                day,
                tube,
                ratios_by_symbol,
                [symbol for symbol in bars_by_symbol if listed_on(symbol, day)],
                min_turnover=min_turnover,
                sessions=sessions,
            )
            ranked_cache[day] = ranked
        if len(ranked) < min_names:
            continue
        out[year] = Basket(day, ranked[:limit], ranked[:trade_limit])
    return out


def baskets_from_bars(
    index_days: list[str],
    bars_by_symbol: dict[str, list[dict]],
    ratios_by_symbol: dict,
    listings: dict[str, dict],
    **options,
) -> dict[int, Basket]:
    """Rổ của từng năm từ nến, BCTC và bảng niêm yết đã lưu.

    Gộp `listed_from` vào đây để ba chỗ dựng rổ (báo cáo, bảng dò, phép thử) không tự ghép
    lại và lệch nhau.
    """
    return yearly_baskets(
        index_days, bars_by_symbol, ratios_by_symbol, listed_from(listings), **options
    )


def basket_members(baskets: dict[int, Basket], year: int) -> list[str]:
    basket = baskets.get(year)
    return list(basket.universe) if basket else []


def trade_members(baskets: dict[int, Basket], year: int) -> list[str]:
    basket = baskets.get(year)
    return list(basket.trade) if basket else []


def member_of(baskets: dict[int, Basket], symbol: str, day: str) -> bool:
    """Mã có nằm trong rổ của năm chứa `day` không."""
    basket = baskets.get(int(day[:4]))
    return bool(basket and symbol in basket.universe)


def trade_member_of(baskets: dict[int, Basket], symbol: str, day: str) -> bool:
    basket = baskets.get(int(day[:4]))
    return bool(basket and symbol in basket.trade)
