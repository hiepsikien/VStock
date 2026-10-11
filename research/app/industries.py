"""Industry labels and the yearly VN100 membership.

A group needs three names before it has an industry return of its own. Fewer than that
and the label stays, but the name is judged as a single stock once the domestic regime is open.
"""

from __future__ import annotations

from app.config import BANKS, INSURERS, SECURITIES

INDUSTRY_WINDOW = 60
MIN_INDUSTRY_NAMES = 3
VN100_SIZE = 100

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


def industry_of(symbol: str) -> str | None:
    if symbol in BANKS:
        return "bank"
    if symbol in SECURITIES:
        return "securities"
    if symbol in INSURERS:
        return "insurer"
    return _EXTRA.get(symbol)


def members(industry: str, universe: list[str] | tuple[str, ...]) -> list[str]:
    return [symbol for symbol in universe if industry_of(symbol) == industry]


def gated_industries(universe: list[str] | tuple[str, ...]) -> list[str]:
    found = []
    for industry in sorted({industry_of(symbol) for symbol in universe} - {None}):
        if industry is not None and len(members(industry, universe)) >= MIN_INDUSTRY_NAMES:
            found.append(industry)
    return found


def yearly_universe(market_caps: dict[str, float], *, limit: int = VN100_SIZE) -> list[str]:
    """Largest names by market cap on the day the year list is fixed. Missing caps stay out."""
    ranked = sorted(
        ((cap, symbol) for symbol, cap in market_caps.items() if cap is not None and cap > 0),
        reverse=True,
    )
    return [symbol for _cap, symbol in ranked[:limit]]
