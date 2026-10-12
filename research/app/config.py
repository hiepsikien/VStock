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
# Nến và chuỗi vĩ mô xin từ ngày này, để đo được sóng 2021 và sóng giảm 2022.
HISTORY_START = "2021-01-01"
# history_pull nạp lùi tới đây cho giai đoạn đo 2015–2020. Phiên live vẫn xin từ HISTORY_START,
# các phiên cũ đã lưu thì giữ nguyên. Năm 2014 chỉ để VN-Index đủ MA200 và cửa sổ ngành khởi động.
RESEARCH_HISTORY_START = "2014-01-01"
# Default matches news_filing_days in backend/config/providers.yaml.
# Docker passes ARTICLE_RETENTION_DAYS from NEWS_FILING_DAYS so the two stay together.
ARTICLE_RETENTION_DAYS = 1460

# --- Rổ theo từng giai đoạn -------------------------------------------------------
# Danh sách cố định bên dưới còn thiên lệch sống sót: mã đã hủy niêm yết không có mặt, nên
# rổ của năm 2015–2022 toàn mã biết là sẽ sống tới nay. Rổ theo thời điểm lấy lại từ danh
# sách niêm yết của VNDirect: mỗi năm chỉ thấy mã còn giao dịch trong năm đó, kể cả mã sau
# này hủy niêm yết. Hạng theo vốn hóa và thanh khoản đo bằng số đã công bố tính đến phiên
# chốt rổ, rồi cắt ở 200 cho phần ngành và 100 cho phần vào lệnh.
UNIVERSE_EXCHANGES = ("HOSE", "HNX")
# Rổ 200 mã dùng cho "Cả rổ" và cho sức mạnh ngành của cổng (chỉ số ngành và cổng ba mã đều
# dựng trên rổ này); rổ 100 chỉ dùng cho phần vào lệnh, nên cờ mở chỉ sinh cho mã thuộc rổ 100.
UNIVERSE_LIMIT = 200
TRADE_LIMIT = 100
# Số phiên dùng để đo thanh khoản ngay trước phiên chốt rổ.
LIQUIDITY_LOOKBACK_SESSIONS = 20
# Giá trong kho là nghìn đồng, khối lượng là cổ phiếu: nhân thêm mức này để ra đồng.
VND_PER_PRICE_UNIT = 1_000.0
# Trung bình khối lượng nhân giá đóng cửa mỗi phiên, đơn vị đồng. Dưới mức này mã không vào rổ.
MIN_MEDIAN_TURNOVER = 3_000_000_000.0


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
    # Added with the basket in 2026-10: financial codes the three template sets below already
    # scored but the basket never watched — banks, securities firms and insurers. Every one of them
    # lands in an existing gate set, so no threshold is invented here: banks on bad loans and
    # coverage, brokers without the corporate debt gate, insurers with the wider debt ceiling.
    "TPB",
    "MSB",
    "LPB",
    "SHB",
    "EIB",
    "OCB",
    "NAB",
    "VIB",
    "SSB",  # banks
    "HCM",
    "VCI",
    "MBS",
    "SHS",
    "BSI",
    "AGR",
    "FTS",
    "VDS",  # securities firms
    "BMI",
    "BIC",
    "MIG",
    "PVI",  # insurers
    # VN100 candidates beyond the original 51, so each 1 January can rank a real top 100.
    "KDH", "DXG", "NLG", "PDR", "DIG", "HDG", "KBC", "CEO", "IDC", "NVL", "TCH", "SCR", "VPI",
    "POW", "OIL", "PVT", "PVD", "GEG", "NT2",
    "HSG", "NKG", "DCM", "DPM", "GVR", "PHR", "VGC",
    "FRT", "DGW", "MCH", "QNS", "VHC", "ANV", "DBC", "KDC", "PET", "FMC",
    "CMG", "ELC",
    "ACV", "HVN", "SCS",
    "PC1",
    "CTD", "BMP", "VCG", "CII", "HHV", "BCM", "SZC",
    "HAG", "LSS", "PAN", "DHC",
    "CTS", "VIX",
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
        "CTS",
        "VIX",
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
    "CUSTOMER_LOANS_AQ",
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
# Mỗi trang của VNDirect. Lịch sử đầy đủ đi hết totalPages, không dừng ở 60 phiên.
FLOW_PAGE_SIZE = 300
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

# Cửa sổ nền vẫn là 20 phiên cuối của chuỗi nền, nên đỉnh dùng để xét phá và đáy dùng để
# dừng lỗ không đổi. Hai điều kiện dưới đây chỉ siết thêm cổng vào: nền không sâu quá, và
# phải có nhịp tăng trước nền — điều kiện thứ hai chặn đoạn đi ngang trong xu hướng giảm.
FLAT_BASE_MAX_DEPTH = 0.15
FLAT_BASE_MIN_ADVANCE = 0.15
# Nhịp tăng đo từ đáy thấp nhất của bao nhiêu phiên ngay trước cửa sổ nền lên đỉnh nền.
FLAT_BASE_ADVANCE_LOOKBACK = 40
# Khối lượng nến phá so với trung bình khối lượng của 20 phiên nền (không gồm nến phá).
BREAKOUT_VOLUME_RATIO = 1.5
# Một lần đóng cửa trở lại dưới mốc đã phá trong bao nhiêu phiên thì coi là phá hỏng.
FAILED_BREAKOUT_SESSIONS = 3

# --- Lớp 1: vĩ mô liên thị trường ------------------------------------------------
# Yahoo chart API. Research reads it directly, the same way it reads Entrade.
YAHOO_CHART = "https://query2.finance.yahoo.com/v8/finance/chart/{symbol}"
MACRO_SYMBOLS = (
    ("DXY", "DX-Y.NYB", "Chỉ số đô la"),
    ("USDVND", "USDVND=X", "Tỷ giá USD/VND"),
    ("SP500", "^GSPC", "S&P 500"),
    ("OIL", "CL=F", "Dầu WTI"),
)
MACRO_MA_WINDOW = 20
# A close inside this band of the average counts as neither above nor below.
MACRO_NEUTRAL_BAND = 0.005

# --- Cổng tiền tệ: tiền đang thừa hay thiếu, và giá của đồng tiền ------------------
# Cổng này đứng cạnh cổng VN-Index trên MA200 và là cổng AND: cả hai cùng mở thì danh
# sách mới được xét tiếp. Chuỗi bắt buộc còn thiếu thì trạng thái là "Chưa chấm", cùng
# kiểu với một mã thiếu báo cáo. Ngưỡng viết thành số ở đây, trước khi chạy phiên.
TRADINGVIEW_SCANNER = "https://scanner.tradingview.com/symbol"
# Mã nguồn công khai, đọc được không cần đăng nhập. Giá trị lấy tại thời điểm chạy phiên
# rồi lưu theo ngày, nên các phiên cũ không bao giờ nhìn thấy số của hôm nay.
MARKET_SERIES = (
    ("INTERBANK_ON", "Lãi suất liên ngân hàng qua đêm", "%/năm", "ECONOMICS:VNINBR"),
    ("GOV10Y", "Lợi suất trái phiếu chính phủ 10 năm", "%/năm", "TVC:VN10Y"),
    ("USDVND", "Tỷ giá USD/VND liên ngân hàng", "VND", "FX_IDC:USDVND"),
    # Tín phiếu và thị trường mở chưa có nguồn công khai: chuỗi đứng trống và không nằm
    # trong danh sách bắt buộc, nên nó không thể khóa danh sách.
    ("NHNN_NET", "NHNN hút/bơm ròng qua tín phiếu và thị trường mở", "tỷ đồng", ""),
    ("POLICY_RATE", "Lãi suất tái cấp vốn", "%/năm", ""),
)
# Chỉ những chuỗi ở đây mới làm cổng đứng ở "Chưa chấm" khi thiếu số.
MARKET_GATE_REQUIRED = ("USDVND", "POLICY_RATE")
# Lãi qua đêm và TPCP 10Y chưa có chuỗi lịch sử từ 2021, nên tạm đóng: vẫn lưu mỗi phiên và
# hiện trên trang /market, nhưng không khóa cổng kể cả khi đã đủ số phiên.
MARKET_GATE_CLOSED = ("INTERBANK_ON", "GOV10Y")
# Lãi suất điều hành không có nguồn tự động. Mỗi quyết định của NHNN là một dòng, ghi
# ngày có hiệu lực; bài báo chỉ để biết ngày đó, không dùng để chấm điểm.
POLICY_RATE_HISTORY = (
    ("2014-03-18", 6.5),
    ("2017-07-10", 6.25),
    ("2019-09-16", 6.0),
    ("2020-03-17", 5.0),
    ("2020-05-13", 4.5),
    ("2020-10-01", 4.0),
    ("2022-09-23", 5.0),
    ("2022-10-25", 6.0),
    ("2023-04-03", 5.5),
    ("2023-05-25", 5.0),
    ("2023-06-19", 4.5),
)
# So với trung bình bao nhiêu phiên đã lưu, và cần tối thiểu bao nhiêu số mới chấm.
MARKET_MA_WINDOW = 20
MARKET_MIN_SESSIONS = 5
# Một ngưỡng đặt None nghĩa là chưa khai báo, và chuỗi đó không thể khóa danh sách.
MARKET_RATE_RISE_MAX = 1.0  # lãi qua đêm vượt trung bình quá 1 điểm % là thắt
MARKET_YIELD_RISE_MAX = 0.5  # lợi suất 10 năm vượt trung bình quá 0,5 điểm % là thắt
MARKET_FX_ABOVE_MA_MAX = 0.01  # tỷ giá vượt trung bình quá 1% là áp lực ngoại tệ
MARKET_FX_ABOVE_DAYS = 5  # ...và giữ đủ bao nhiêu phiên thì mới thành cờ
MARKET_POLICY_LOOKBACK_DAYS = 90  # lãi điều hành tăng trong bao nhiêu ngày gần đây
MARKET_DRAIN_DAYS = 5  # hút ròng liên tiếp bao nhiêu phiên
MARKET_DRAIN_MIN = 5000  # ...và tổng hút ròng từ mức này (tỷ đồng)

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
# Trần an toàn cho một vị thế. Trần 132 phiên chỉ bật khi cổng ngành đã được phép chặn.
MAX_HOLD_SESSIONS = 60
MAX_HOLD_EXTENDED = 132
# Cả hai cờ đứng tắt cho đến khi cổng ngành qua giai đoạn 2021–2024 và 2025–2026.
INDUSTRY_GATE_ENFORCED = False
INDUSTRY_HOLD_ENABLED = False
STOCK_SHORTLIST_ENFORCED = False

# --- Cổng độ rộng: bao nhiêu mã của rổ 200 đang trên MA50 -------------------------
# Chốt ngày 2026-10-12, trước lần đo đầu. Đứng cạnh VN-Index trên MA200 và là cổng AND.
# Số sát ngưỡng không phải lý do để nới ngưỡng; đổi một số ở đây là luật mới, đo lại từ đầu.
BREADTH_MA_WINDOW = 50
# Mở khi tỷ lệ chạm mốc trên, đóng khi chạm mốc dưới; ở giữa thì giữ trạng thái phiên trước.
BREADTH_OPEN = 0.55
BREADTH_CLOSE = 0.45
# Phiên đầu tiên chấm được chưa có trạng thái trước, nên lấy mốc này để quyết định.
BREADTH_START = 0.50
# Ít hơn số mã hợp lệ này thì phiên đó "Chưa chấm".
BREADTH_MIN_NAMES = 30
# Nến cuối của mã phải nằm trong bao nhiêu phiên gần nhất của VN-Index mới được đếm.
BREADTH_MAX_STALE_SESSIONS = 5
# Luật qua cửa, phải đạt ở cả giai đoạn chọn và xác nhận.
# Tầng thị trường: "MA200 và độ rộng" so với MA200 đơn thuần trên danh mục chia đều rổ 100.
BREADTH_MIN_DRAWDOWN_CUT = 0.20  # sụt sâu nhất nông hơn ít nhất 20% (tương đối)
BREADTH_MAX_YEARLY_GIVEUP = 0.01  # lợi nhuận mỗi năm không kém quá 1 điểm %
# Tầng tín hiệu: lợi nhuận 40 phiên của tín hiệu phá nền lúc mở trừ lúc đóng.
BREADTH_SIGNAL_HORIZON = 40
BREADTH_MIN_SIGNAL_EDGE = 0.02
BREADTH_MIN_SIGNALS = 30  # mỗi phía cần chừng này tín hiệu, thiếu là "chưa đủ mẫu"
# Đứng tắt cho đến khi báo cáo cổng độ rộng qua cả hai giai đoạn.
BREADTH_GATE_ENFORCED = False
# Phiên live lưu tỷ lệ và trạng thái của mình vào market_points dưới hai tên này.
BREADTH_SERIES = "BREADTH50"
BREADTH_STATE_SERIES = "BREADTH50_STATE"

# --- Độ rộng làm bộ lọc tín hiệu phá nền ------------------------------------------
# Chốt ngày 2026-10-12, trước khi có dữ liệu đo: luật ở docs/breadth-signal-filter.md, mốc là
# tag `prereg/breadth-filter` trên GitHub. Chỉ đo trên phiên chạy thật từ ngày bắt đầu, là phiên
# đóng cửa đầu tiên sau khi tag được push. Tách khỏi các hằng số của cổng độ rộng để đổi luật
# cổng không kéo theo luật này.
BREADTH_FILTER_START = "2026-10-13"
# Lợi nhuận đo từ giá đóng cửa phiên sau phiên tín hiệu, vì kết luận chỉ có sau giờ đóng cửa.
BREADTH_FILTER_HORIZON = 40
BREADTH_FILTER_MIN_SIGNALS = 30  # mỗi nhóm, chỉ đếm tín hiệu đã đủ 40 phiên
BREADTH_FILTER_MIN_EDGE = 0.02  # nhóm giữ hơn nhóm bỏ ít nhất 2 điểm %
BREADTH_FILTER_MIN_MONTHS = 12
BREADTH_FILTER_MAX_MONTHS = 60

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
