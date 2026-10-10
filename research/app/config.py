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
# Brokers fund margin lending with debt, so the corporate debt gate cannot apply.
# Insurers carry float, which gets a wider ceiling than a plain corporate.
DEBT_TO_EQUITY_INSURER_MAX = 3.0
NPL_MAX = 0.03
PROVISION_COVERAGE_MIN = 0.80
DILUTION_SHARE_GROWTH = 0.05
# Valuation anchor. The live session reads P/E from the market database; the backtest
# never does, because that column is a snapshot and would look into the future.
PE_CEILING = 30.0
# Piotroski-style checklist. Fewer than this many computable items means no F-Score.
F_SCORE_MIN_ITEMS = 6
# An F-Score below this mark is weak enough to reject a corporate.
F_SCORE_MIN_PASS = 4
# A close-to-close move past the board band means the series is not split-adjusted.
# Limits sit above HOSE ±7%, HNX ±10%, and UPCOM ±15%. An unknown board uses the widest.
PRICE_JUMP_LIMITS = {"HOSE": 0.09, "HNX": 0.12, "UPCOM": 0.17}
PRICE_JUMP_LIMIT_UNKNOWN = 0.17
# Equity growth / share growth. Below the low mark the jump is a bonus or split.
# Above the high mark new equity arrived with the shares.
EQUITY_MATCH_BONUS = 0.35
EQUITY_MATCH_CASH = 0.60
BAR_LOOKBACK_DAYS = 1200
# Default matches news_filing_days in backend/config/providers.yaml.
# Docker passes ARTICLE_RETENTION_DAYS from NEWS_FILING_DAYS so the two stay together.
ARTICLE_RETENTION_DAYS = 1460

DEFAULT_UNIVERSE = (
    "FPT",
    "VNM",
    "HPG",
    "MWG",
    "GAS",
    "MSN",
    "PLX",
    "SAB",
    "PNJ",
    "REE",
    "DGC",
    "GMD",
    "VJC",
    "PVS",
    "VCB",
    "TCB",
    "MBB",
    "ACB",
    "VPB",
    "BID",
    "CTG",
    "HDB",
    "STB",
    "SSI",  # securities firm: scored with the securities template
    "VND",
    "BVH",  # insurer: scored with the insurer template
    "VIC",
    "VHM",
    "VRE",
    "SBT",
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

# Brokerages carry margin-lending debt and insurers carry float. Neither fits the
# corporate debt gate, so each gets its own template instead of falling through.
SECURITIES = frozenset(
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
    }
)

INSURERS = frozenset(
    {
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
    # Added for the balance-sheet checklist items.
    "TOTAL_ASSETS_AQ",
    "CURRENT_RATIO_AQ",
    "INVENTORY_AQ",
)

BANK_CODES = (
    "NET_PROFIT_QR",
    "NET_PROFIT_QR_GRYOY",
    "BAD_LOANS_RATIO_AQ",
    "PROVISION_BAD_LOANS_AQ",
    "OWNERS_EQUITY_AQ",
    "CUSTOMER_LOANS_AQ_GRYOY",
)

# Brokers and insurers report like corporates: sales, profit, equity.
SERVICES_CODES = (
    "NET_SALES_QR",
    "NET_SALES_QR_GRYOY",
    "NET_PROFIT_QR",
    "NET_PROFIT_QR_GRYOY",
    "OWNERS_EQUITY_AQ",
    "DEBT_TO_EQUITY_AQ",
    "OUTSTANDING_SHARES",
)

RATIO_CODES = tuple(dict.fromkeys([*CORPORATE_CODES, *BANK_CODES, *SERVICES_CODES]))

STATUS_RANK = {
    "Được vào": 0,
    "Theo dõi": 1,
    "Chờ": 2,
    "Chưa chấm": 3,
    "Loại": 4,
    "Khóa": 5,
}

# --- Lớp 3: dòng tiền khối ngoại -------------------------------------------------
# VNDirect Finfo keeps a daily foreign-trading history per symbol, so the flow layer
# reads the same host as the ratios and the news feed.
FLOW_LOOKBACK_SESSIONS = 60
FLOW_WINDOW = 10
# Bỏ qua cửa sổ khi thiếu hơn mức này số phiên có dữ liệu khối ngoại.
FLOW_MIN_SESSIONS = 5
# Room ngoại còn dưới mức này là gần cạn, chỉ ghi chú chứ không chặn.
FLOW_ROOM_LOW = 0.05
# Net foreign volume over the window, divided by matched volume, is "strong" past this.
FLOW_STRONG_RATIO = 0.10
# Price direction is flat inside this band when the flow gate compares price to flow.
FLOW_FLAT_BAND = 0.01

# --- Nhận diện mô hình (Lớp 4) ---------------------------------------------------
# ZigZag uses an ATR-scaled swing so the pivots adapt to each symbol's volatility.
STRUCTURE_LOOKBACK_SESSIONS = 120
DOUBLE_BOTTOM_TOLERANCE = 0.05
DOUBLE_BOTTOM_MIN_RISE = 0.05
DOUBLE_BOTTOM_MIN_BARS = 8
VCP_CONTRACTION_RATIO = 0.8
FLAG_POLE_ATR_MULTIPLE = 3.0
FLAG_MAX_CONSOLIDATION_BARS = 25
FLAG_MAX_RETRACE = 0.35
FIB_RETRACE_LOW = 0.382
FIB_RETRACE_HIGH = 0.886
FIB_EXTENSION_LOW = 0.618
FIB_EXTENSION_HIGH = 1.618

# --- Lớp 1: vĩ mô liên thị trường ------------------------------------------------
# Yahoo chart API. Research reads it directly, the same way it reads Entrade.
YAHOO_CHART = "https://query2.finance.yahoo.com/v8/finance/chart/{symbol}"
MACRO_SYMBOLS = (
    ("DXY", "DX-Y.NYB", "Chỉ số đô la"),
    ("USDVND", "USDVND=X", "Tỷ giá USD/VND"),
    ("SP500", "^GSPC", "S&P 500"),
    ("OIL", "CL=F", "Dầu WTI"),
)
MACRO_RANGE = "6mo"
MACRO_MA_WINDOW = 20
# A close inside this band of the average counts as neither above nor below.
MACRO_NEUTRAL_BAND = 0.005

# --- Tầng trading: ATR, thoát lệnh, cỡ vị thế -----------------------------------
ATR_WINDOW = 14
ATR_STOP_MULTIPLIER = 2.0
MA_FAST = 20
TRAIL_ATR_MULTIPLIER = 0.5
# Chốt một phần tại vùng +1R rồi kéo dừng lỗ về hòa vốn.
TP1_R_MULTIPLE = 1.0
TP1_FRACTION = 1 / 3
# Không đi tới +1R trong bao nhiêu phiên thì đóng vì tiền chết.
TIME_STOP_SESSIONS = 30
# Trần an toàn cho một vị thế.
MAX_HOLD_SESSIONS = 60
MAX_SLOTS = 5
RISK_PER_TRADE = 0.01
MAX_POSITION_WEIGHT = 0.35

# --- Điểm tổng hợp --------------------------------------------------------------
# Tài liệu yêu cầu điểm ≥ 75. Điểm ở đây dùng để xếp hạng và lọc danh sách ưu tiên;
# điều kiện vào vẫn là các cổng cứng.
SCORE_ENTRY_MIN = 75
SCORE_WEIGHTS = {
    "fa": 30,
    "flow": 25,
    "pattern": 25,
    "rs": 10,
    "news": 10,
}
# Flow đóng góp theo mức. Thiếu số thì lấy mức trung tính để không tự trừ điểm.
FLOW_SCORE = {
    "accumulation": 25,
    "support": 18,
    "neutral": 12,
    "missing": 12,
    "weak": 6,
    "block": 0,
}
