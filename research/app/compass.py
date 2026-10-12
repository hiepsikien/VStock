"""Điểm Z của Compass trên biên gộp và cửa spread giai đoạn chọn.

Đích hồi quy là thay đổi biên lợi nhuận gộp so với quý liền trước. Biên gộp là khoản
23100 chia khoản 21001, cả hai là số tiền. Khoản 23110 (lợi nhuận hoạt động) và biên
LNTT không nằm trong lần đo này.

Z của mã j tại phiên t là β nhân lợi suất dầu 60 phiên. β là OLS một biến, cửa sổ mở
rộng, chỉ trên các quý đã qua đúng số ngày trễ của sổ. Fact và LLM không nhân vào Z.

NT2 mang dấu viết tay bằng 0. Để ba spread cùng một rổ, NT2 đứng ngoài cả Z, dấu viết
tay và β giá. Ngưỡng cú sốc được chọn trên riêng chuỗi dầu, trước khi đọc lợi suất cổ
phiếu. Qua cửa ở giai đoạn chọn chưa phải lệnh được vào, và chưa mở giai đoạn xác nhận.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from app.config import STATEMENT_LAG_DAYS
from app.industry_screen import dated_returns, rolling_compound

# Bốn mã được chấm. Dấu viết tay khóa trước khi nhìn β và trước khi nhìn giá.
SCORED_NAMES = ("PVD", "GAS", "DCM", "DPM")
HEURISTIC_SIGN = {"PVD": 1, "GAS": 1, "DCM": -1, "DPM": -1}

GROSS_PROFIT_ITEM = "23100"
NET_REVENUE_ITEM = "21001"
# LNST cổ đông công ty mẹ. Giá cổ phiếu là phần của cổ đông mẹ, không phải LNST toàn công ty.
NET_INCOME_ITEM = "23000"
# Giá lấy ở phiên giao dịch đầu tiên không sớm hơn ngày được nhìn, và không muộn quá số ngày này.
PRICE_SLIP_DAYS = 10

WINDOW = 60
MIN_PAIRS = 12
MIN_SIDE = 2
MIN_EVENTS = 8
MIN_SCORED_EVENTS = 8
PRICE_BETA_SESSIONS = 756
# Quý liền trước cách khoảng 90 ngày. Lệch khỏi khoảng này là một quý bị thiếu.
QUARTER_GAP_MIN_DAYS = 80
QUARTER_GAP_MAX_DAYS = 100

SELECT_START = "2021-01-04"
SELECT_END = "2024-12-31"

# Đường trễ của biên gộp. h = 0 là quý xảy ra cú sốc. h = 4 là bốn quý sau đó.
# Cả năm mốc được in ra. Không có bước chọn mốc nào làm cửa giá.
LAG_HORIZONS = (0, 1, 2, 3, 4)

# Lưới khóa trước. Luật chọn là ngưỡng lớn nhất còn đủ số sự kiện dầu, không phải ngưỡng
# làm spread đẹp. Không nới lưới sau khi đã thấy lợi suất cổ phiếu.
THETA_GRID = (0.10, 0.12, 0.15, 0.18, 0.20, 0.25)


@dataclass(frozen=True)
class MarginPair:
    fiscal_end: str
    visible_from: str
    delta: float
    shock: float


def gross_margins(
    revenue: list[tuple[str, float]],
    gross_profit: list[tuple[str, float]],
) -> list[tuple[str, float]]:
    """Biên gộp theo ngày kết thúc quý. Doanh thu không dương thì quý đó bị bỏ."""
    sales = dict(revenue)
    profit = dict(gross_profit)
    margins = []
    for day in sorted(set(sales) & set(profit)):
        if sales[day] <= 0:
            continue
        margins.append((day, profit[day] / sales[day]))
    return margins


def oil_shock(oil_bars: list[dict], window: int = WINDOW) -> list[tuple[str, float]]:
    """Lợi suất dầu `window` phiên, biết tại phiên cuối của cửa sổ đó."""
    rolled = rolling_compound(dated_returns(oil_bars), window)
    return sorted(rolled.items())


def shock_on_or_before(shock: list[tuple[str, float]], day: str) -> float | None:
    latest = None
    for shock_day, value in shock:
        if shock_day > day:
            break
        latest = value
    return latest


def shock_by_session(sessions: list[str], shock: list[tuple[str, float]]) -> dict[str, float]:
    """Gắn mỗi phiên cổ phiếu với lợi suất dầu đã biết đến hết phiên đó."""
    out = {}
    cursor = 0
    latest = None
    for day in sessions:
        while cursor < len(shock) and shock[cursor][0] <= day:
            latest = shock[cursor][1]
            cursor += 1
        if latest is not None:
            out[day] = latest
    return out


def margin_pairs(
    margins: list[tuple[str, float]],
    shock: list[tuple[str, float]],
    *,
    lag_days: int = STATEMENT_LAG_DAYS,
) -> list[MarginPair]:
    """Một cặp quý liền trước. Quý chỉ được nhìn từ ngày kết thúc cộng số ngày trễ."""
    pairs = []
    for previous, current in zip(margins, margins[1:]):
        start = date.fromisoformat(previous[0])
        end = date.fromisoformat(current[0])
        gap = (end - start).days
        if gap < QUARTER_GAP_MIN_DAYS or gap > QUARTER_GAP_MAX_DAYS:
            continue
        oil = shock_on_or_before(shock, current[0])
        if oil is None:
            continue
        visible = (end + timedelta(days=lag_days)).isoformat()
        pairs.append(MarginPair(current[0], visible, current[1] - previous[1], oil))
    return pairs


def ols(x_values: list[float], y_values: list[float]) -> float | None:
    """Hệ số góc OLS một biến. Không có độ phân tán ở x thì không có hệ số."""
    count = len(x_values)
    if count < 2 or len(y_values) != count:
        return None
    mean_x = sum(x_values) / count
    mean_y = sum(y_values) / count
    variance = sum((item - mean_x) ** 2 for item in x_values)
    if variance <= 0:
        return None
    covariance = sum((x - mean_x) * (y - mean_y) for x, y in zip(x_values, y_values))
    return covariance / variance


def _adjacent_quarters(left: str, right: str) -> bool:
    gap = (date.fromisoformat(right) - date.fromisoformat(left)).days
    return QUARTER_GAP_MIN_DAYS <= gap <= QUARTER_GAP_MAX_DAYS


def projection_pairs(
    margins: list[tuple[str, float]],
    shock: list[tuple[str, float]],
    horizon: int,
    outcome_end: str,
) -> list[tuple[float, float]]:
    """Biên gộp tích lũy từ quý trước cú sốc đến h quý sau, trên dầu của quý cú sốc.

    Quý kết quả sau `outcome_end` không vào mẫu. Đứt một quý trên đường đi thì bỏ cặp đó.
    """
    if horizon < 0:
        return []
    pairs = []
    last = len(margins) - 1
    for index in range(1, last + 1):
        end_index = index + horizon
        if end_index > last:
            break
        if margins[end_index][0] > outcome_end:
            continue
        span = margins[index - 1 : end_index + 1]
        if any(not _adjacent_quarters(left[0], right[0]) for left, right in zip(span, span[1:])):
            continue
        oil = shock_on_or_before(shock, margins[index][0])
        if oil is None:
            continue
        pairs.append((oil, margins[end_index][1] - margins[index - 1][1]))
    return pairs


def visible_day(fiscal_end: str, lag_days: int = STATEMENT_LAG_DAYS) -> str:
    """Ngày báo cáo quý được phép nhìn: ngày kết thúc quý cộng số ngày trễ của sổ."""
    return (date.fromisoformat(fiscal_end) + timedelta(days=lag_days)).isoformat()


def session_on_or_after(sessions: list[str], day: str, max_slip_days: int = PRICE_SLIP_DAYS) -> str | None:
    """Phiên đầu tiên không sớm hơn `day`. Muộn hơn `max_slip_days` thì coi như không có giá."""
    limit = (date.fromisoformat(day) + timedelta(days=max_slip_days)).isoformat()
    for session in sessions:
        if session < day:
            continue
        if session > limit:
            return None
        return session
    return None


def _horizon_indexes(dates: list[str], horizon: int, outcome_end: str):
    """Bộ chỉ số (quý trước cú sốc, quý cú sốc, quý kết quả) trên một chuỗi quý liền nhau."""
    if horizon < 0:
        return
    last = len(dates) - 1
    for index in range(1, last + 1):
        end_index = index + horizon
        if end_index > last or dates[end_index] > outcome_end:
            continue
        span = dates[index - 1 : end_index + 1]
        if any(not _adjacent_quarters(left, right) for left, right in zip(span, span[1:])):
            continue
        yield index - 1, index, end_index


def npat_projection_pairs(
    npat: list[tuple[str, float]],
    revenue: list[tuple[str, float]],
    shock: list[tuple[str, float]],
    horizon: int,
    outcome_end: str,
) -> list[tuple[float, float]]:
    """LNST quý kết quả trừ LNST quý trước cú sốc, chia doanh thu quý trước cú sốc."""
    profit = dict(npat)
    sales = dict(revenue)
    dates = sorted(set(profit) & set(sales))
    pairs = []
    for base, shock_index, end in _horizon_indexes(dates, horizon, outcome_end):
        base_sales = sales[dates[base]]
        if base_sales <= 0:
            continue
        oil = shock_on_or_before(shock, dates[shock_index])
        if oil is None:
            continue
        delta = (profit[dates[end]] - profit[dates[base]]) / base_sales
        pairs.append((oil, delta))
    return pairs


def price_projection_pairs(
    closes: list[tuple[str, float]],
    fiscal_dates: list[str],
    shock: list[tuple[str, float]],
    horizon: int,
    outcome_end: str,
    *,
    lag_days: int = STATEMENT_LAG_DAYS,
    max_slip_days: int = PRICE_SLIP_DAYS,
) -> list[tuple[float, float]]:
    """Lợi suất từ phiên công bố quý trước cú sốc đến phiên công bố quý kết quả."""
    sessions = [day for day, close in closes if close > 0]
    close_on = {day: close for day, close in closes if close > 0}
    pairs = []
    for base, shock_index, end in _horizon_indexes(fiscal_dates, horizon, outcome_end):
        oil = shock_on_or_before(shock, fiscal_dates[shock_index])
        if oil is None:
            continue
        buy_day = session_on_or_after(sessions, visible_day(fiscal_dates[base], lag_days), max_slip_days)
        sell_day = session_on_or_after(sessions, visible_day(fiscal_dates[end], lag_days), max_slip_days)
        if buy_day is None or sell_day is None:
            continue
        buy = close_on[buy_day]
        if buy <= 0:
            continue
        pairs.append((oil, close_on[sell_day] / buy - 1.0))
    return pairs


def projection_beta(
    margins: list[tuple[str, float]],
    shock: list[tuple[str, float]],
    horizon: int,
    outcome_end: str,
) -> tuple[float | None, int]:
    pairs = projection_pairs(margins, shock, horizon, outcome_end)
    if len(pairs) < 2:
        return None, len(pairs)
    return ols([oil for oil, _delta in pairs], [delta for _oil, delta in pairs]), len(pairs)


def beta_on(pairs: list[MarginPair], as_of: str, *, min_pairs: int = MIN_PAIRS) -> float | None:
    """β tại ngày as_of. Quý có visible_from sau ngày đó không vào mẫu."""
    usable = [pair for pair in pairs if pair.visible_from <= as_of]
    if len(usable) < min_pairs:
        return None
    return ols([pair.shock for pair in usable], [pair.delta for pair in usable])


def common_sessions(bars: dict[str, list[tuple[str, float]]], names: tuple[str, ...]) -> list[str]:
    """Phiên cả rổ đều có giá dương, để bốn lợi suất tới cùng một lịch."""
    sets = []
    for name in names:
        sets.append({day for day, close in bars[name] if close > 0})
    if not sets:
        return []
    return sorted(set.intersection(*sets))


def event_starts(
    sessions: list[str],
    shock_on_day: dict[str, float],
    theta: float,
    start: str,
    end: str,
    *,
    window: int = WINDOW,
) -> list[str]:
    """Phiên cắt ngưỡng lần đầu, không chồng lên cửa sổ 60 phiên của sự kiện trước.

    Cửa sổ đo mua ở phiên sau tín hiệu và giữ `window` phiên. Tín hiệu mới chỉ được
    tính từ phiên liền sau phiên thoát. Đang đứng trên ngưỡng từ trước ngày bắt đầu
    thì chưa phải một lần cắt.
    """
    events = []
    previous = None
    next_allowed = 0
    for index, day in enumerate(sessions):
        value = shock_on_day.get(day)
        if index < next_allowed:
            previous = value
            continue
        crossed = (
            value is not None
            and abs(value) > theta
            and (previous is None or abs(previous) <= theta)
        )
        previous = value
        if not crossed or day < start or day > end:
            continue
        exit_index = index + 1 + window
        if exit_index >= len(sessions):
            continue
        events.append(day)
        next_allowed = exit_index + 1
    return events


def choose_theta(
    sessions: list[str],
    shock_on_day: dict[str, float],
    start: str,
    end: str,
) -> float | None:
    """Ngưỡng lớn nhất trên lưới còn đủ sự kiện dầu. Không đọc giá cổ phiếu."""
    for theta in sorted(THETA_GRID, reverse=True):
        if len(event_starts(sessions, shock_on_day, theta, start, end)) >= MIN_EVENTS:
            return theta
    return None


def daily_returns(closes: list[tuple[str, float]]) -> dict[str, float]:
    out = {}
    for (day_before, close_before), (day, close) in zip(closes, closes[1:]):
        del day_before
        if close_before > 0:
            out[day] = close / close_before - 1.0
    return out


def price_beta(
    stock_returns: dict[str, float],
    oil_returns: dict[str, float],
    as_of: str,
    *,
    sessions: int = PRICE_BETA_SESSIONS,
) -> float | None:
    """OLS lợi suất ngày của cổ phiếu trên lợi suất ngày của dầu, đủ `sessions` phiên trước as_of."""
    paired = [day for day in sorted(set(stock_returns) & set(oil_returns)) if day < as_of]
    window = paired[-sessions:]
    if len(window) < sessions:
        return None
    return ols([oil_returns[day] for day in window], [stock_returns[day] for day in window])


def forward_return(
    closes: dict[str, float],
    sessions: list[str],
    signal: str,
    *,
    window: int = WINDOW,
) -> float | None:
    """Mua giá đóng cửa phiên sau tín hiệu, bán sau đúng `window` phiên."""
    try:
        index = sessions.index(signal)
    except ValueError:
        return None
    entry = index + 1
    exit_index = entry + window
    if exit_index >= len(sessions):
        return None
    buy = closes.get(sessions[entry])
    sell = closes.get(sessions[exit_index])
    if buy is None or sell is None or buy <= 0:
        return None
    return sell / buy - 1.0


def classify(scores: dict[str, float], *, min_side: int = MIN_SIDE) -> dict[str, int] | None:
    """Dấu của điểm. Thiếu một phía đủ mã thì sự kiện không được chấm."""
    signs = {}
    for name, score in scores.items():
        if score > 0:
            signs[name] = 1
        elif score < 0:
            signs[name] = -1
    positive = sum(sign > 0 for sign in signs.values())
    negative = sum(sign < 0 for sign in signs.values())
    if positive < min_side or negative < min_side:
        return None
    return signs


def heuristic_scores(shock: float) -> dict[str, float]:
    return {name: sign * shock for name, sign in HEURISTIC_SIGN.items()}


def basket_spread(signs: dict[str, int], forwards: dict[str, float]) -> float | None:
    positive = []
    negative = []
    for name, sign in signs.items():
        if name not in forwards:
            return None
        (positive if sign > 0 else negative).append(forwards[name])
    if len(positive) < MIN_SIDE or len(negative) < MIN_SIDE:
        return None
    return sum(positive) / len(positive) - sum(negative) / len(negative)


def mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def verdict(spreads_z: list[float], spreads_heuristic: list[float], spreads_price: list[float]) -> str:
    """Ba bất đẳng thức trên trung bình spread của cùng một tập sự kiện. Thiếu mẫu thì chưa chấm."""
    count = len(spreads_z)
    if (
        count < MIN_SCORED_EVENTS
        or len(spreads_heuristic) != count
        or len(spreads_price) != count
    ):
        return "chua_du"
    score = mean(spreads_z)
    heuristic = mean(spreads_heuristic)
    price = mean(spreads_price)
    if score is None or heuristic is None or price is None:
        return "chua_du"
    if score > 0 and score > heuristic and score > price:
        return "qua"
    return "truot"
