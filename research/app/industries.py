"""Ngành, nhãn ICB và rổ của từng năm.

Một nhóm cần ba mã mới có lợi suất ngành riêng. Ít hơn thì nhãn vẫn còn, nhưng mã được xét
như một cổ phiếu đơn lẻ ngay khi chế độ trong nước mở.

Nhãn ngành của cả thị trường lấy từ bảng phân loại ICB của VNDirect, xếp vào đúng 12 nhóm
mà luật ở đây đã đo: cấp 3 trước, cấp 2 cho mã không thuộc nhóm cấp 3 nào, và danh sách
thủ công cho những mã quen mặt. Nhóm ICB không có cổng tương ứng — y tế, truyền thông, du
lịch — để trống nhãn chứ không gán bừa sang một nhóm đã đo: mã không nhãn chỉ cần chế độ
trong nước.
"""

from __future__ import annotations

from app.config import BANKS, INSURERS, SECURITIES

INDUSTRY_WINDOW = 60
MIN_INDUSTRY_NAMES = 3

# Nhóm ICB cấp 3, khoá là mã bốn chữ số, giá trị là nhãn của dự án.
ICB_LABELS = {
    "0530": "energy",  # Sản xuất dầu khí
    "0570": "energy",  # Dụng cụ, dịch vụ & phân phối dầu
    "0580": "power",  # Năng lượng tái tạo: cùng cổng với điện
    "1350": "materials",  # Hóa chất
    "1730": "materials",  # Sản xuất giấy & trồng rừng
    "1750": "materials",  # Kim loại công nghiệp
    "1770": "materials",  # Khai thác mỏ
    "2350": "industrial",  # Xây dựng & vật liệu
    "2710": "industrial",  # Vũ trụ & quốc phòng
    "2720": "industrial",  # Công nghiệp tổng hợp
    "2730": "industrial",  # Dụng cụ điện & điện tử
    "2750": "industrial",  # Công nghiệp cơ khí
    "2770": "transport",  # Giao thông công nghiệp: hàng không, cảng, logistics
    "2790": "industrial",  # Dịch vụ hỗ trợ
    "3350": "industrial",  # Ôtô & phụ tùng
    "3530": "consumer",  # Đồ uống
    "3570": "consumer",  # Sản xuất thực phẩm
    "3720": "consumer",  # Hàng gia dụng
    "3740": "consumer",  # Hàng hóa giải trí
    "3760": "consumer",  # Hàng hóa cá nhân
    "3780": "consumer",  # Thuốc lá
    "5330": "consumer",  # Bán lẻ thực phẩm & thuốc
    "5370": "consumer",  # Bán lẻ
    "6530": "tech",  # Viễn thông cố định
    "6570": "tech",  # Viễn thông di động
    "7530": "power",  # Điện lực
    "7570": "power",  # Ga, nước & dịch vụ công cộng
    "8350": "bank",  # Ngân hàng
    "8530": "insurer",  # Bảo hiểm phi nhân thọ
    "8570": "insurer",  # Bảo hiểm nhân thọ
    "8630": "real_estate",  # Dịch vụ đầu tư bất động sản
    "8670": "real_estate",  # Quỹ đầu tư bất động sản
    "8730": "real_estate",  # Bất động sản
    "8770": "securities",  # Dịch vụ tài chính: công ty chứng khoán
    "8980": "securities",  # Công cụ đầu tư cổ phần
    "8990": "securities",  # Công cụ đầu tư phi cổ phần
    "9530": "tech",  # Phần mềm & dịch vụ máy tính
    "9570": "tech",  # Dụng cụ & công nghệ phần cứng
}

# Nhóm ICB cấp 2 chỉ dùng khi mã không rơi vào nhóm cấp 3 nào ở trên. Cấp 2 trùng nhãn với
# cấp 3 ở mọi nhánh trừ 2700, nơi vận tải công nghiệp tách khỏi phần công nghiệp còn lại.
ICB_LEVEL2_LABELS = {
    "0500": "energy",
    "1300": "materials",
    "1700": "materials",
    "2300": "industrial",
    "2700": "industrial",
    "3300": "industrial",
    "3500": "consumer",
    "3700": "consumer",
    "5300": "consumer",
    "6500": "tech",
    "7500": "power",
    "8300": "bank",
    "8500": "insurer",
    "8600": "real_estate",
    "8700": "securities",
    "9500": "tech",
}

# Oil is the only pre-registered foreign lead. Materials use it as a commodity proxy
# until an ore series exists. Adding another country or lag is a new rule.
LEAD_SERIES = {
    "energy": "OIL",
    "materials": "OIL",
}
CREDIT_INDUSTRIES = frozenset({"bank", "securities"})
REGIME_INDUSTRIES = frozenset(
    {
        "real_estate",
        "consumer",
        "insurer",
        "transport",
        "agri",
        "industrial",
        "power",
        "tech",
    }
)

_EXTRA = {
    "VIC": "real_estate",
    "VHM": "real_estate",
    "VRE": "real_estate",
    "KDH": "real_estate",
    "DXG": "real_estate",
    "NLG": "real_estate",
    "PDR": "real_estate",
    "DIG": "real_estate",
    "HDG": "real_estate",
    "KBC": "real_estate",
    "CEO": "real_estate",
    "IDC": "real_estate",
    "NVL": "real_estate",
    "TCH": "real_estate",
    "SCR": "real_estate",
    "VPI": "real_estate",
    "GAS": "energy",
    "PLX": "energy",
    "PVS": "energy",
    "OIL": "energy",
    "PVD": "energy",
    "PVT": "energy",
    "POW": "power",
    "GEG": "power",
    "NT2": "power",
    "PC1": "power",
    "REE": "power",
    "HPG": "materials",
    "DGC": "materials",
    "HSG": "materials",
    "NKG": "materials",
    "DCM": "materials",
    "DPM": "materials",
    "GVR": "materials",
    "PHR": "materials",
    "VGC": "materials",
    "VNM": "consumer",
    "MWG": "consumer",
    "MSN": "consumer",
    "SAB": "consumer",
    "PNJ": "consumer",
    "FRT": "consumer",
    "DGW": "consumer",
    "MCH": "consumer",
    "QNS": "consumer",
    "VHC": "consumer",
    "ANV": "consumer",
    "DBC": "consumer",
    "KDC": "consumer",
    "PET": "consumer",
    "FMC": "consumer",
    "FPT": "tech",
    "CMG": "tech",
    "ELC": "tech",
    "VJC": "transport",
    "GMD": "transport",
    "ACV": "transport",
    "HVN": "transport",
    "SCS": "transport",
    "CTD": "industrial",
    "BMP": "industrial",
    "VCG": "industrial",
    "CII": "industrial",
    "HHV": "industrial",
    "BCM": "industrial",
    "SZC": "industrial",
    "SBT": "agri",
    "HAG": "agri",
    "LSS": "agri",
    "PAN": "agri",
    "DHC": "materials",
}


def _icb_key(code: str) -> str:
    """Mã ICB về dạng bốn chữ số: nguồn trả \"580\" cho nhóm được ghi là 0580."""
    text = str(code or "").strip()
    if not text:
        return ""
    try:
        return f"{int(text):04d}"
    except ValueError:
        return text


def icb_industry(code: str, level: int) -> str | None:
    """Nhãn của một nhóm ICB, None khi nhóm đó chưa có cổng riêng để dùng."""
    key = _icb_key(code)
    if not key:
        return None
    if int(level or 0) >= 3:
        label = ICB_LABELS.get(key)
        if label:
            return label
    return ICB_LEVEL2_LABELS.get(key)


def industry_rows(groups: list[dict]) -> list[tuple[str, int, str, str, str]]:
    """Đổi danh sách nhóm ICB thành dòng (mã, cấp, mã nhóm, tên nhóm, nhãn ngành).

    Cấp 2 đọc trước cấp 3, nên mã nằm trong một nhóm cấp 3 có nhãn thì nhãn cấp 3 thắng —
    đó là chỗ vận tải công nghiệp tách khỏi phần công nghiệp còn lại. Nhóm không có nhãn
    vẫn được ghi lại để bảng ngành thấy được mã nào cố tình đứng ngoài cổng.
    """
    rows: dict[str, tuple[str, int, str, str, str]] = {}
    for level in (2, 3):
        for group in sorted(groups, key=lambda item: str(item.get("industryLevel") or "")):
            if int(group.get("industryLevel") or 0) != level:
                continue
            code = str(group.get("industryCode") or "")
            name = str(group.get("englishName") or "")
            label = icb_industry(code, level) or ""
            for symbol in str(group.get("codeList") or "").split(","):
                ticker = symbol.strip().upper()
                if ticker:
                    rows[ticker] = (ticker, level, code, name, label)
    return [rows[ticker] for ticker in sorted(rows)]


_INJECTED: dict[str, str] = {}


def set_industry_map(mapping: dict[str, str]) -> None:
    """Gắn bảng ngành ICB đã lưu. Chưa gắn thì chỉ danh sách thủ công còn tác dụng."""
    global _INJECTED
    _INJECTED = {symbol: label for symbol, label in mapping.items() if label}


def industry_labels() -> dict[str, str]:
    """Bản sao bảng ngành đang gắn, để tiến trình con nhận lại đúng bảng đó và sửa được."""
    return dict(_INJECTED)


def industry_of(symbol: str) -> str | None:
    """Nhãn ngành của một mã: bảng mẫu trước, rồi tới danh sách thủ công, rồi bảng ICB.

    Ba bảng mẫu chứng khoán, ngân hàng, bảo hiểm quyết định cả cách chấm điểm nên chúng
    đứng trên nhãn ICB: một công ty chứng khoán nhỏ vẫn đọc theo mẫu chứng khoán.
    """
    if symbol in BANKS:
        return "bank"
    if symbol in SECURITIES:
        return "securities"
    if symbol in INSURERS:
        return "insurer"
    curated = _EXTRA.get(symbol)
    if curated:
        return curated
    return _INJECTED.get(symbol)



def members(industry: str, universe: list[str] | tuple[str, ...]) -> list[str]:
    return [symbol for symbol in universe if industry_of(symbol) == industry]


def gated_industries(universe: list[str] | tuple[str, ...]) -> list[str]:
    found = []
    for industry in sorted({industry_of(symbol) for symbol in universe} - {None}):
        if industry is not None and len(members(industry, universe)) >= MIN_INDUSTRY_NAMES:
            found.append(industry)
    return found
