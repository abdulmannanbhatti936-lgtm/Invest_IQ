"""
Portfolio allocation (PRD.md FR23, FR24, FR28): risk-first weights with a bounded tilt from
the forecast and the news, whole shares, and the idle-cash check. Pure and deterministic:
the same inputs always give the same portfolio. Every rupee figure comes from the cost engine.

    risk weight   r = volatility ** -k                    (k per risk category)
    forecast      p = clamp(expected return / 1%, -1, 1)
    signal        q = +P(BUY), -P(SELL), 0 for HOLD        (Random Forest class probability)
    news          s = decayed sentiment score, 0 without a counted headline
    tilt          t = (p + q + s) / 3, in [-1, 1]
    raw weight    r * (1 + lambda * t)

The top N raw weights are kept (ties by ticker), normalised and capped per stock and sector.
"""

from dataclasses import dataclass, field
from decimal import Decimal

from core.portfolio_rules import MIN_CAPITAL_SEARCH_LIMIT, MIN_CAPITAL_STEP, SIGNAL_BAND, RiskRules
from services import cost_engine
from services.cost_engine import Purchase, Rates

ONE = Decimal("1")
ZERO = Decimal("0")
# Normalising divides, so a capped sector can exceed its limit by rounding noise
TOLERANCE = Decimal("1e-20")


@dataclass(frozen=True)
class Candidate:
    ticker: str
    sector: str
    price: Decimal
    volatility: Decimal
    expected_return: Decimal
    signal: str
    signal_probability: Decimal | None
    sentiment_score: Decimal | None


@dataclass(frozen=True)
class Scored:
    candidate: Candidate
    forecast_component: Decimal
    signal_component: Decimal
    sentiment_component: Decimal
    tilt: Decimal
    risk_weight: Decimal
    raw_weight: Decimal

    @property
    def ticker(self) -> str:
        return self.candidate.ticker


def _clamp(value: Decimal, low: Decimal, high: Decimal) -> Decimal:
    return max(low, min(high, value))


def score(candidate: Candidate, rules: RiskRules) -> Scored:
    forecast = _clamp(candidate.expected_return / SIGNAL_BAND, -ONE, ONE)
    probability = candidate.signal_probability or ZERO
    signal = {"BUY": probability, "SELL": -probability}.get(candidate.signal, ZERO)
    sentiment = candidate.sentiment_score if candidate.sentiment_score is not None else ZERO
    tilt = (forecast + signal + sentiment) / 3
    risk = candidate.volatility**-rules.volatility_exponent
    return Scored(
        candidate,
        forecast,
        signal,
        sentiment,
        tilt,
        risk,
        risk * (ONE + rules.tilt_strength * tilt),
    )


def rank(scored: list[Scored]) -> list[Scored]:
    return sorted(scored, key=lambda s: (-s.raw_weight, s.ticker))


def _water_fill(total: Decimal, raw: dict[str, Decimal], cap: Decimal) -> dict[str, Decimal]:
    """
    Share `total` in proportion to `raw`; a share over `cap` is set to `cap` and its excess
    goes to the others the same way. If every share reaches the cap, the rest stays unplaced.
    """
    capped: dict[str, Decimal] = {}
    while True:
        free = [t for t in raw if t not in capped]
        if not free:
            return capped
        room = total - sum(capped.values(), ZERO)
        free_raw = sum((raw[t] for t in free), ZERO)
        shares = {t: room * raw[t] / free_raw for t in free}
        over = [t for t in free if shares[t] > cap + TOLERANCE]
        if not over:
            return {**capped, **shares}
        capped.update({t: cap for t in over})


def cap_weights(
    raw: dict[str, Decimal],
    sectors: dict[str, str],
    max_stock: Decimal,
    max_sector: Decimal,
) -> dict[str, Decimal]:
    """
    Weights proportional to `raw`, with no stock above `max_stock` and no sector above
    `max_sector`. A crowded sector is held at its limit (shared among its stocks the same
    way) and the rest goes to the other sectors. Weight no stock can take (every stock or
    sector at its limit) is left unplaced and becomes idle cash.
    """
    held: dict[str, Decimal] = {}
    while True:
        free_raw = {t: w for t, w in raw.items() if t not in held}
        weights = {**held, **_water_fill(ONE - sum(held.values(), ZERO), free_raw, max_stock)}
        totals: dict[str, Decimal] = {}
        for ticker in free_raw:
            totals[sectors[ticker]] = totals.get(sectors[ticker], ZERO) + weights[ticker]
        crowded = sorted(s for s, total in totals.items() if total > max_sector + TOLERANCE)
        if not crowded:
            return weights
        for sector in crowded:
            members = {t: w for t, w in free_raw.items() if sectors[t] == sector}
            held.update(_water_fill(max_sector, members, max_stock))


class TooFewEligibleStocks(Exception):
    def __init__(self, eligible: int, needed: int):
        super().__init__(f"{eligible} eligible stocks, {needed} needed")
        self.eligible = eligible
        self.needed = needed


class CapitalTooLow(Exception):
    def __init__(self, capital: Decimal, rules: RiskRules):
        super().__init__(f"Rs {capital} cannot hold {rules.min_holdings} stocks within the caps")
        self.capital = capital
        self.rules = rules


@dataclass(frozen=True)
class PlannedHolding:
    scored: Scored
    target_weight: Decimal
    untilted_weight: Decimal
    purchase: Purchase

    @property
    def tilt_effect_pp(self) -> Decimal:
        return (self.target_weight - self.untilted_weight) * 100


@dataclass(frozen=True)
class IdleCash:
    amount: Decimal
    flagged: bool
    # Why cash that could buy another share was left: 'stock_cap' / 'sector_cap', per ticker
    blocked_by: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Allocation:
    capital: Decimal
    holdings: list[PlannedHolding]
    idle: IdleCash
    ranked: list[Scored]
    unaffordable: list[str]

    @property
    def gross_total(self) -> Decimal:
        return sum((h.purchase.gross for h in self.holdings), ZERO)

    @property
    def charges_total(self) -> Decimal:
        return sum((h.purchase.charges.total for h in self.holdings), ZERO)

    @property
    def cost_total(self) -> Decimal:
        return sum((h.purchase.total_cost for h in self.holdings), ZERO)


def _weights(selected: list[Scored], rules: RiskRules, tilted: bool) -> dict[str, Decimal]:
    raw = {s.ticker: s.raw_weight if tilted else s.risk_weight for s in selected}
    sectors = {s.ticker: s.candidate.sector for s in selected}
    return cap_weights(raw, sectors, rules.max_stock_weight, rules.max_sector_weight)


def _fill_leftover(
    selected: list[Scored],
    weights: dict[str, Decimal],
    purchases: dict[str, Purchase],
    capital: Decimal,
    rules: RiskRules,
    rates: Rates,
    commission_rate: Decimal | None,
) -> IdleCash:
    """
    Spend what flooring to whole shares left over: one share at a time to the holding
    furthest below its target, as long as the share fits and no cap is broken.
    """
    sector_of = {s.ticker: s.candidate.sector for s in selected}
    while True:
        leftover = capital - sum((p.total_cost for p in purchases.values()), ZERO)
        sector_cost: dict[str, Decimal] = {}
        for ticker, purchase in purchases.items():
            sector = sector_of[ticker]
            sector_cost[sector] = sector_cost.get(sector, ZERO) + purchase.total_cost

        options, blocked = [], {}
        for s in selected:
            current = purchases[s.ticker]
            nxt = cost_engine.buy(current.shares + 1, current.price, rates, commission_rate)
            step = nxt.total_cost - current.total_cost
            if step > leftover:
                continue
            if nxt.total_cost > rules.max_stock_weight * capital:
                blocked[s.ticker] = "stock_cap"
            elif sector_cost[sector_of[s.ticker]] + step > rules.max_sector_weight * capital:
                blocked[s.ticker] = "sector_cap"
            else:
                shortfall = weights[s.ticker] * capital - current.total_cost
                options.append((-shortfall, s.ticker, nxt))
        if not options:
            return IdleCash(leftover, bool(blocked), blocked)
        _, ticker, nxt = min(options)
        purchases[ticker] = nxt


def allocate(
    candidates: list[Candidate],
    capital: Decimal,
    rules: RiskRules,
    rates: Rates,
    commission_rate: Decimal | None = None,
) -> Allocation:
    ranked = rank([score(c, rules) for c in candidates])
    if len(ranked) < rules.min_holdings:
        raise TooFewEligibleStocks(len(ranked), rules.min_holdings)

    # A stock whose target cannot buy one share is replaced by the next in the ranking
    unaffordable: list[str] = []
    while True:
        selected = [s for s in ranked if s.ticker not in unaffordable][: rules.max_holdings]
        if len(selected) < rules.min_holdings:
            raise CapitalTooLow(capital, rules)
        weights = _weights(selected, rules, tilted=True)
        shares = {
            s.ticker: cost_engine.max_affordable_shares(
                s.candidate.price, weights[s.ticker] * capital, rates, commission_rate
            )
            for s in selected
        }
        missing = [t for t, n in shares.items() if n == 0]
        if not missing:
            break
        unaffordable.extend(missing)

    purchases = {
        s.ticker: cost_engine.buy(shares[s.ticker], s.candidate.price, rates, commission_rate)
        for s in selected
    }
    idle = _fill_leftover(selected, weights, purchases, capital, rules, rates, commission_rate)
    untilted = _weights(selected, rules, tilted=False)
    holdings = [
        PlannedHolding(s, weights[s.ticker], untilted[s.ticker], purchases[s.ticker])
        for s in selected
    ]
    return Allocation(capital, holdings, idle, ranked, unaffordable)


def minimum_capital(
    candidates: list[Candidate],
    start: Decimal,
    rules: RiskRules,
    rates: Rates,
    commission_rate: Decimal | None = None,
) -> Decimal | None:
    """
    The smallest amount, in steps of Rs 500 above `start`, for which `allocate` succeeds.
    Found with the generator itself, so the low-capital message always agrees with it.
    """
    amount = (start / MIN_CAPITAL_STEP).to_integral_value(rounding="ROUND_FLOOR") + 1
    amount *= MIN_CAPITAL_STEP
    while amount <= MIN_CAPITAL_SEARCH_LIMIT:
        try:
            allocate(candidates, amount, rules, rates, commission_rate)
            return amount
        except CapitalTooLow:
            amount += MIN_CAPITAL_STEP
    return None
