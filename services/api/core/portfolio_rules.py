"""
Portfolio rules per risk category (Phase 5, approved by the team on 2026-10-11).

Risk comes first: weights follow volatility, and the forecast and news can only tilt them by
a bounded amount, because no model beats its baseline (Memory.md §10). Higher risk tolerance
accepts more model influence (larger tilt). There is no deliberate cash share: idle cash is
what FR24 flags.
"""

from dataclasses import dataclass
from decimal import Decimal

from ml.features import SIGNAL_THRESHOLD


@dataclass(frozen=True)
class RiskRules:
    # Base weight = volatility ** -volatility_exponent (2: strongly favour calm stocks;
    # 1: inverse volatility; 0: equal weights)
    volatility_exponent: int
    max_holdings: int
    min_holdings: int
    max_stock_weight: Decimal
    max_sector_weight: Decimal
    tilt_strength: Decimal

    @property
    def tilt_bound_pp(self) -> Decimal:
        """
        Largest change the tilt can make, in percentage points, to a stock at the stock cap:
        each weight is multiplied by 1 + lambda * t with t in [-1, 1] before normalising, so
        it moves by at most 2 * lambda / (1 - lambda) of its untilted size.
        """
        lam = self.tilt_strength
        return self.max_stock_weight * 100 * 2 * lam / (1 - lam)


RISK_RULES = {
    "conservative": RiskRules(2, 10, 7, Decimal("0.15"), Decimal("0.30"), Decimal("0.05")),
    "moderate": RiskRules(1, 8, 5, Decimal("0.20"), Decimal("0.35"), Decimal("0.10")),
    "aggressive": RiskRules(0, 6, 4, Decimal("0.25"), Decimal("0.40"), Decimal("0.15")),
}

# The forecast's expected return is scaled by the BUY/SELL label band (±1%, Memory.md §3), so
# a forecast at the band's edge counts as a full-strength signal
SIGNAL_BAND = Decimal(str(SIGNAL_THRESHOLD))

# Volatility: sample standard deviation of daily log returns over the last 250 served closes
VOLATILITY_WINDOW = 250

# Rolling (FR25): a holding is checked once 20 trading days have passed; it underperforms when
# it trails the benchmark by more than 1x its own 20-day volatility (daily sigma x sqrt(20))
ROLL_WINDOW_TRADING_DAYS = 20
ROLL_SIGMA_MULTIPLE = Decimal("1")

# The low-capital message rounds the smallest workable amount up to this step (presentation)
MIN_CAPITAL_STEP = Decimal("500")
MIN_CAPITAL_SEARCH_LIMIT = Decimal("10000000")

SHARIAH_FILE = "psx_shariah_review_2026-05-25.csv"
SHARIAH_LIST_VERSION = "PSX/N-610, effective 2026-05-25"
