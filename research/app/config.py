from __future__ import annotations

# One slot of capital, round-trip cost used by the measurement page.
ROUND_TRIP_COST = 0.003
CASH_YIELD = 0.055
HOLD_SESSIONS = 60
MA_WINDOW = 200
# Statement rows become eligible in the backtest this many days after period end.
STATEMENT_LAG_DAYS = 45
QUARTER_DUE_DAYS = 30
INSIDER_SELL_DAYS = 30
INSIDER_BUY_DAYS = 60
BLOCK_LOOKBACK_DAYS = 200
DEBT_TO_EQUITY_MAX = 2.0
NPL_MAX = 0.03
PROVISION_COVERAGE_MIN = 0.80
DILUTION_SHARE_GROWTH = 0.05
BAR_LOOKBACK_DAYS = 1200

DEFAULT_UNIVERSE = (
    "FPT",
    "VNM",
    "HPG",
    "MWG",
    "GAS",
    "MSN",
    "PLX",
    "SAB",
    "VCB",
    "TCB",
    "MBB",
    "ACB",
    "VPB",
    "SSI",
    "VIC",
)

# Scored with the bank template. Missing bank fields stay "Chưa chấm".
BANKS = frozenset(
    {
        "VCB",
        "CTG",
        "BID",
        "TCB",
        "MBB",
        "ACB",
        "VPB",
        "HDB",
        "STB",
        "TPB",
        "MSB",
        "LPB",
        "SHB",
        "EIB",
        "OCB",
        "NAB",
        "VIB",
        "SSB",
    }
)

# No template yet. They must not fall through to the corporate debt gate.
OTHER_FINANCIALS = frozenset(
    {
        "SSI",
        "VND",
        "HCM",
        "VCI",
        "MBS",
        "SHS",
        "BSI",
        "AGR",
        "FTS",
        "VDS",
        "BVH",
        "BMI",
        "BIC",
        "MIG",
        "PVI",
    }
)

CORPORATE_CODES = (
    "NET_SALES_QR",
    "NET_SALES_QR_GRYOY",
    "NET_PROFIT_QR",
    "NET_PROFIT_QR_GRYOY",
    "OPERATING_PROFIT_QR_GRYOY",
    "CFO_TO_SALES_QR",
    "DEBT_TO_EQUITY_AQ",
    "OUTSTANDING_SHARES",
)

BANK_CODES = (
    "NET_PROFIT_QR",
    "NET_PROFIT_QR_GRYOY",
    "BAD_LOANS_RATIO_AQ",
    "PROVISION_BAD_LOANS_AQ",
    "OWNERS_EQUITY_AQ",
    "CUSTOMER_LOANS_AQ_GRYOY",
)

RATIO_CODES = tuple(dict.fromkeys([*CORPORATE_CODES, *BANK_CODES]))

STATUS_RANK = {
    "Được vào": 0,
    "Theo dõi": 1,
    "Chờ": 2,
    "Chưa chấm": 3,
    "Loại": 4,
    "Khóa": 5,
}
