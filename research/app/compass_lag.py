"""Đường trễ của biên gộp sau cú sốc dầu. Không đọc giá cổ phiếu và không chọn một độ trễ.

Năm mốc 0 đến 4 quý được in cùng lúc. Quý kết quả sau 2024-12-31 không vào mẫu.
"""

from __future__ import annotations

import asyncio
from datetime import date
from pathlib import Path

from app.compass import (
    HEURISTIC_SIGN,
    LAG_HORIZONS,
    SCORED_NAMES,
    SELECT_END,
    gross_margins,
    oil_shock,
    projection_beta,
)
from app.compass_report import load

REPORT_PATH = Path(__file__).resolve().parents[1] / "reports" / "compass_lag.md"


def lag_table(loaded: dict) -> dict[str, list[tuple[float | None, int]]]:
    shock = oil_shock(loaded["oil"])
    table = {}
    for symbol in SCORED_NAMES:
        margins = gross_margins(loaded["books"][symbol]["revenue"], loaded["books"][symbol]["gross"])
        table[symbol] = [
            projection_beta(margins, shock, horizon, SELECT_END) for horizon in LAG_HORIZONS
        ]
    return table


def _cell(beta: float | None, count: int) -> str:
    if beta is None:
        return f"— (n={count})"
    return f"{beta * 0.25 * 100:+.2f} điểm (n={count})"


def render(table: dict[str, list[tuple[float | None, int]]]) -> str:
    lines = [
        "# Đường trễ biên gộp sau cú sốc dầu",
        "",
        f"Số liệu kéo ngày {date.today().isoformat()}. Quý kết quả kết thúc không muộn hơn {SELECT_END}.",
        "Mỗi ô là mức đổi biên gộp, tính bằng điểm phần trăm, khi dầu tăng 25% ở quý cú sốc.",
        "h = 0 là cuối quý xảy ra cú sốc. h = 4 là bốn quý sau quý đó. Mốc nào cũng được in. Không chọn mốc.",
        "Bảng này không đọc giá cổ phiếu, không đổi ngưỡng dầu, và không đổi `Được vào`.",
        "",
        "| Mã | h = 0 | h = 1 | h = 2 | h = 3 | h = 4 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for symbol in SCORED_NAMES:
        cells = " | ".join(_cell(beta, count) for beta, count in table[symbol])
        lines.append(f"| {symbol} | {cells} |")
    lines.append("")
    lines.append("Dấu viết tay đã khóa: PVD +, GAS +, DCM −, DPM −. Đọc mốc h = 4 theo dấu đó.")
    lines.append("")
    for symbol in SCORED_NAMES:
        beta_0, n_0 = table[symbol][0]
        beta_4, n_4 = table[symbol][4]
        lines.append(f"- {symbol}: {_reading(beta_0, n_0, beta_4, n_4, HEURISTIC_SIGN[symbol])}")
    lines.append("")
    return "\n".join(lines)


def _reading(
    beta_0: float | None,
    n_0: int,
    beta_4: float | None,
    n_4: int,
    hand_sign: int,
) -> str:
    if beta_4 is None or n_4 < 12:
        return f"mốc 4 quý chưa đủ mẫu (n={n_4})."
    same_direction = beta_4 * hand_sign > 0
    direction = "cùng dấu viết tay" if same_direction else "ngược dấu viết tay"
    if beta_0 is None or n_0 < 12:
        return f"sau 4 quý {direction}; mốc cùng quý chưa đủ mẫu để so biên độ."
    if abs(beta_4) > abs(beta_0):
        size = "biên độ lớn hơn mốc cùng quý"
    else:
        size = "biên độ không lớn hơn mốc cùng quý"
    return f"sau 4 quý {direction}, {size}."


def main() -> None:
    loaded = asyncio.run(load())
    if not loaded["oil"]:
        raise SystemExit("Không tải được CL=F")
    text = render(lag_table(loaded))
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(text)
    print(text)


if __name__ == "__main__":
    main()
