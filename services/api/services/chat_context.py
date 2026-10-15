"""
Grounding context for the chatbot (Workflow.md Step 8.2, Architecture.md §12, PRD.md FR39).

For every message the user's own data is read from the database and turned into one structured
object: risk profile, the active portfolio with every figure the cost engine stored, the latest
forecasts and news sentiment for the stocks in the portfolio or named in the conversation, the
latest backtest of the active portfolio, and the latest close of any other stock named.

Nothing is recalculated here. Every figure is the stored or served value, formatted the way the
web app shows it (Rs. with two decimals, percentages rounded half up to the screen's decimals),
so the model only has to copy text. Each figure is also recorded with its source, which is what
the figure check (services/chat_figure_check.py) matches a reply against and what the source
tags under a reply are built from.
"""

import datetime
import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from functools import lru_cache
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from core.config import API_ROOT, settings
from integrations.news.matching import DATA_DIR, normalize
from ml.inference import ModelNotFoundError, load_bundle
from models.backtest import BacktestResult
from models.stock import Stock
from models.user import User
from services import backtest_service, portfolio_service, risk_scoring
from services.chat_figure_check import extract_numbers
from services.prediction_service import latest_prediction, low_confidence_reasons
from services.sentiment_service import stock_sentiment
from services.stock_service import PriceDataUnavailable, StockService

logger = logging.getLogger(__name__)

CONTEXT_VERSION = "ctx-v4"
PKT = ZoneInfo("Asia/Karachi")

# Urdu replies use the app's own Urdu words for these terms (packages/i18n), so the chat and the
# screens say the same thing and the model invents no translations (decided 2026-10-13)
I18N_DIR = API_ROOT.parent.parent / "packages" / "i18n" / "src" / "locales"
# Each glossary entry is sent only when the context holds what it names (the marker: a field name
# or value in the context JSON), so a message carries only the words it can use. ALWAYS: the
# screen names, which the prompt may name in any reply. None: the English label itself (sectors).
ALWAYS = ""
GLOSSARY_MARKERS: dict[str, str | None] = {
    "risk.conservative": "conservative",
    "risk.moderate": "moderate",
    "risk.aggressive": "aggressive",
    "prediction.signal.BUY": '"buy"',
    "prediction.signal.SELL": '"sell"',
    "prediction.signal.HOLD": '"hold"',
    "prediction.confidence": "confidence_pct",
    "prediction.lowConfidenceTitle": "low_confidence",
    "sentiment.title": '"sentiment"',
    "sentiment.label.positive": '"positive"',
    "sentiment.label.negative": '"negative"',
    "sentiment.label.neutral": '"neutral"',
    "nav.portfolio": ALWAYS,
    "nav.stocks": ALWAYS,
    "nav.backtest": ALWAYS,
    "portfolio.totals.gross": "value_of_shares",
    "portfolio.totals.charges": "buying_charges",
    "portfolio.totals.cost": "total_cost",
    "portfolio.totals.cash": "left_uninvested",
    "portfolio.holding.charges.commission": "commission",
    "portfolio.holding.breakEven": "break_even_price",
    "portfolio.holding.cgt": '"cgt"',
    "portfolio.holding.dividendsNet": "dividends_last_12_months",
    "portfolio.form.nonFiler": "non_filer",
    "backtest.costs.wht": '"wht',
    "backtest.columns.benchmark": '"benchmark"',
    "backtest.metrics.totalReturn": "total_return_after_all_charges",
    "backtest.metrics.annualised": "return_per_year",
    "backtest.metrics.sharpe": "sharpe_ratio",
    "backtest.metrics.drawdown": "largest_fall",
    "backtest.metrics.winRate": "months_up",
    "backtest.mix.weight": "share_of_capital_pct",
    # Added for the chat in Phase 8 (Urdu wording for team review, Memory.md §4)
    "terms.forecast": "forecast",
    "terms.confidence": "confidence_pct",
    "terms.lowConfidence": "low_confidence",
    "terms.baselineNotBeaten": "beats_naive_baseline",
    # UI round (2026-10-15): one Urdu term for the risk level, always the app's own
    "terms.riskProfile": "risk_profile",
    **{
        f"terms.sector.{key}": None
        for key in (
            "automobileAssembler",
            "cableElectricalGoods",
            "cement",
            "commercialBanks",
            "fertilizer",
            "oilGasExploration",
            "oilGasMarketing",
            "powerGeneration",
            "refinery",
            "technologyCommunication",
        )
    },
}
GLOSSARY_KEYS = tuple(GLOSSARY_MARKERS)

# Roman Urdu replies take their finance words from these i18n strings (UI round, 2026-10-15,
# for team review), sent like the Urdu glossary: only the entries the context can use.
ROMAN_URDU_MARKERS: dict[str, str] = {
    "riskProfile": "risk_profile",
    "conservative": "conservative",
    "moderate": "moderate",
    "aggressive": "aggressive",
    "forecast": "forecast",
    "confidence": "confidence_pct",
    "lowConfidence": "low_confidence",
    "breakEvenPrice": "break_even_price",
    "totalCost": "total_cost",
    "charges": "buying_charges",
    "leftAsCash": "left_uninvested",
    "dividend": "dividends_last_12_months",
    "newsSentiment": '"sentiment"',
    "totalReturn": "total_return_after_all_charges",
    "benchmark": '"benchmark"',
}

# Architecture.md §12 grounding budget (decided 2026-10-13): context plus history together
MAX_INPUT_TOKENS = 12_000
# No tokenizer ships with the app; three characters per token over-counts English and Urdu
# JSON slightly, so the estimate errs on the side of a smaller prompt
CHARS_PER_TOKEN = 3
TOP_HEADLINES = 3

# Plain-language reasons a forecast is flagged low-confidence (services/prediction_service.py)
REASON_TEXT = {
    "below_threshold": "The model's confidence is below the 60% the app asks for.",
    "models_disagree": "The two models disagree about the direction.",
    "no_edge_over_baseline": (
        "On past data the model did not do better than assuming tomorrow's price equals today's."
    ),
    "sentiment_unavailable": "News was not up to date, so this forecast uses prices only.",
}

CAP_TEXT = {
    "short_horizon": "Needs the money within a year, so the profile is at most Conservative.",
    "sells_on_loss": "Would sell after a fall, so the profile is at most Moderate.",
    "low_emergency_savings": (
        "Has less than 3 months of emergency savings, so the profile is at most Moderate."
    ),
}

BENCHMARK_LABEL = "The 18 forecast stocks, equal weight, bought and held (not the KSE-100)"
KSE100_NOTE = "Not shown: waiting for PSX permission to use KSE-100 data."

# "PSX" is both a listed company and the exchange everyone names; only the exchange is meant
_NOT_A_MENTION = {"PSX"}


@dataclass(frozen=True)
class Figure:
    """One figure the model may state: its value, how it is shown, and where it came from."""

    value: Decimal
    kind: str  # "money", "pct" or "number"
    text: str
    source: str


@dataclass
class ChatContext:
    data: dict
    figures: list[Figure]
    dates: set[datetime.date]
    sources: dict[str, dict]
    refs: dict
    version: str = CONTEXT_VERSION
    trimmed: list[str] = field(default_factory=list)

    @property
    def json(self) -> str:
        return json.dumps(self.data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    @property
    def hash(self) -> str:
        return hashlib.sha256(self.json.encode("utf-8")).hexdigest()


def _quantize(value: Decimal, places: int) -> Decimal:
    return value.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)


class _Recorder:
    """Formats each figure for the context and remembers it for the figure check."""

    def __init__(self):
        self.figures: list[Figure] = []
        self.dates: set[datetime.date] = set()

    def _keep(self, value: Decimal, kind: str, text: str, source: str) -> str:
        self.figures.append(Figure(value, kind, text, source))
        return text

    def money(self, value, source: str) -> str | None:
        if value is None:
            return None
        amount = _quantize(Decimal(str(value)), 2)
        return self._keep(amount, "money", f"Rs. {amount:,.2f}", source)

    def pct(self, value, source: str, places: int = 2, signed: bool = False) -> str | None:
        """A percentage given in percent (e.g. "14.8025" -> "14.80%")."""
        if value is None:
            return None
        pct = _quantize(Decimal(str(value)), places)
        sign = "+" if signed and pct > 0 else ""
        return self._keep(pct, "pct", f"{sign}{pct:,.{places}f}%", source)

    def ratio_pct(self, ratio, source: str, places: int = 2, signed: bool = False) -> str | None:
        """A fraction from a backtest (e.g. "0.235491" -> "23.55%"), like backtestView.ts."""
        if ratio is None:
            return None
        return self.pct(Decimal(str(ratio)) * 100, source, places, signed)

    def number(self, value, source: str, places: int = 0) -> str | None:
        if value is None:
            return None
        number = _quantize(Decimal(str(value)), places)
        return self._keep(number, "number", f"{number:,.{places}f}", source)

    def text(self, value: str | None, source: str) -> str | None:
        """A sentence the app wrote, or a headline title: the numbers in it may be repeated."""
        if value is None:
            return None
        for number in extract_numbers(value):
            self.figures.append(Figure(number.value, number.kind, number.text, source))
        return value

    def date(self, value) -> str | None:
        if value is None:
            return None
        # Timestamps are stored in UTC; PSX dates are Pakistan dates, as the web shows them
        if isinstance(value, datetime.datetime):
            value = value.astimezone(PKT) if value.tzinfo else value
        day = value.date() if isinstance(value, datetime.datetime) else value
        if isinstance(day, str):
            day = datetime.date.fromisoformat(day[:10])
        self.dates.add(day)
        return day.isoformat()


def _risk_profile(rec: _Recorder, user: User) -> dict:
    profile = user.risk_profile
    try:
        caps = risk_scoring.assess_risk(profile.answers).caps_applied
    except (KeyError, ValueError, TypeError):
        caps = []
    return {
        "source": "risk_profile",
        "category": profile.category.value,
        "caps_applied": [rec.text(CAP_TEXT[c], "risk_profile") for c in caps if c in CAP_TEXT],
    }


def _holding(rec: _Recorder, h: dict) -> dict:
    src = "portfolio"
    exit_ = h["forecast_exit"]
    why = h["why"]
    dividends = h.get("dividends")
    return {
        "ticker": h["ticker"],
        "name": h["name"],
        "sector": h["sector"],
        "shares": rec.number(h["shares"], src),
        "price": rec.money(h["price"], src),
        "share_of_capital_pct": rec.pct(h["allocation_pct"], src),
        "gross": rec.money(h["gross"], src),
        "charges": {key: rec.money(value, src) for key, value in h["charges"].items()},
        "total_cost": rec.money(h["total_cost"], src),
        "break_even_price": rec.money(h["break_even_price"], src),
        "break_even_change_pct": rec.pct(h["break_even_change_pct"], src),
        "round_trip_charges_pct": rec.pct(h["round_trip_pct"], src),
        "if_sold_at_forecast": {
            "price": rec.money(exit_["price"], src),
            "sale_value": rec.money(exit_["gross"], src),
            "selling_charges": rec.money(exit_["charges"]["total"], src),
            "cgt": rec.money(exit_["cgt"], src),
            "net_return": rec.money(exit_["net_return"], src),
            "net_return_pct": rec.pct(exit_["net_return_pct"], src, signed=True),
        },
        "dividends_last_12_months": (
            None
            if dividends is None
            else {
                "per_share": rec.money(dividends["per_share"], src),
                "gross": rec.money(dividends["gross"], src),
                "wht_rate_pct": rec.pct(dividends["wht_rate_pct"], src, places=0),
                "wht": rec.money(dividends["wht"], src),
                "net": rec.money(dividends["net"], src),
                "checked_against_psx": False,
            }
        ),
        "forecast_used_when_generated": {
            "forecast_price": rec.money(why["forecast_price"], src),
            "expected_change_pct": rec.pct(why["expected_change_pct"], src, signed=True),
            "confidence_pct": rec.ratio_pct(why["confidence_score"], src, places=0),
            "signal": why["signal"],
            "low_confidence_reasons": [
                rec.text(REASON_TEXT[r], src) for r in why["low_confidence_reasons"]
            ],
        },
    }


def _portfolio(rec: _Recorder, portfolio) -> dict:
    payload = portfolio_service.portfolio_payload(portfolio)
    src = "portfolio"
    totals = payload["totals"]
    return {
        "source": src,
        "generated_on": rec.date(payload["generated_at"]),
        "prices_as_of": rec.date(payload["prices_as_of"]),
        "rates_version": payload["rates"]["version"],
        "model_version": payload["model_version"],
        "risk_category": payload["risk_category"],
        "capital": rec.money(payload["capital"], src),
        "filer_status": payload["filer_status"],
        "shariah_only": payload["shariah_only"],
        "excluded_stocks": payload["excluded_tickers"],
        "commission_pct": rec.pct(payload["commission_pct"], src, places=3),
        "number_of_stocks": rec.number(len(payload["holdings"]), src),
        "totals": {
            "value_of_shares": rec.money(totals["gross"], src),
            "buying_charges": rec.money(totals["charges"], src),
            "total_cost": rec.money(totals["cost"], src),
            "left_uninvested": rec.money(totals["idle_cash"], src),
        },
        "recommended_stocks": [_holding(rec, h) for h in payload["holdings"]],
    }


def _forecast(rec: _Recorder, db: Session, stock: Stock, bundle) -> tuple[dict, str] | None:
    prediction = latest_prediction(db, stock, bundle.version)
    if prediction is None:
        return None
    src = f"prediction:{stock.ticker}"
    reasons = low_confidence_reasons(prediction, bundle, stock.ticker)
    evaluation = bundle.ticker_evaluation(stock.ticker) or {}
    last_close = Decimal(prediction.last_close)
    change = (Decimal(prediction.forecast_price) / last_close - 1) * 100
    payload = {
        "source": src,
        "ticker": stock.ticker,
        "as_of": rec.date(prediction.as_of_date),
        "model_version": prediction.model_version,
        "horizon": "next trading day",
        "last_close": rec.money(last_close, src),
        "forecast_price": rec.money(prediction.forecast_price, src),
        "expected_change_pct": rec.pct(change, src, signed=True),
        "confidence_pct": rec.ratio_pct(prediction.confidence_score, src, places=0),
        "low_confidence": bool(reasons),
        "low_confidence_reasons": [rec.text(REASON_TEXT[r], src) for r in reasons],
        "signal": prediction.signal,
        "signal_probability_pct": rec.ratio_pct(prediction.signal_probability, src, places=0),
        "beats_naive_baseline": bool(evaluation.get("beats_naive")),
    }
    return payload, str(prediction.id)


def _sentiment(rec: _Recorder, db: Session, stock: Stock) -> dict:
    payload = stock_sentiment(db, stock)
    src = f"sentiment:{stock.ticker}"
    counted = [h for h in payload["headlines"] if h["weight"] is not None]
    top = sorted(counted, key=lambda h: h["weight"], reverse=True)[:TOP_HEADLINES]
    return {
        "source": src,
        "ticker": stock.ticker,
        "as_of": rec.date(payload["as_of_date"]),
        "label": payload["label"],
        "counted_headlines": rec.number(payload["counted_headlines"], src),
        "window_trading_days": rec.number(payload["window_trading_days"], src),
        "news_sources_out_of_date": payload["freshness"]["stale"],
        # Third-party titles: quoted data, never instructions (system prompt)
        "top_headlines_untrusted": [
            {
                "title": rec.text(h["headline"], src),
                "source": h["source_name"],
                "published": rec.date(h["published_at"]),
                "label": h["label"],
                "label_probability_pct": rec.ratio_pct(h["label_probability"], src, places=0),
            }
            for h in top
        ],
    }


def _metrics(rec: _Recorder, metrics: dict, src: str) -> dict:
    return {
        "total_return_after_all_charges": rec.ratio_pct(metrics["total_return"], src, signed=True),
        "return_per_year": rec.ratio_pct(metrics["annualised_return"], src, signed=True),
        "sharpe_ratio": rec.number(metrics["sharpe_ratio"], src, places=2),
        "largest_fall": rec.ratio_pct(metrics["max_drawdown"], src),
        "largest_fall_from": rec.date(metrics["drawdown_peak_date"]),
        "largest_fall_to": rec.date(metrics["drawdown_trough_date"]),
        "months_up": rec.number(metrics["months_won"], src),
        "months_total": rec.number(metrics["months_total"], src),
    }


def latest_portfolio_backtest(db: Session, user: User, portfolio_id) -> BacktestResult | None:
    return (
        db.query(BacktestResult)
        .filter(
            BacktestResult.user_id == user.id,
            BacktestResult.portfolio_id == portfolio_id,
            BacktestResult.kind == "portfolio",
        )
        .order_by(BacktestResult.created_at.desc())
        .first()
    )


def _backtest(rec: _Recorder, result: BacktestResult) -> dict:
    payload = backtest_service.result_payload(result)
    src = "backtest"
    rules = payload["start_date_rules"]
    return {
        "source": src,
        "run_on": rec.date(payload["created_at"]),
        "method_version": result.method_version,
        "years": rec.number(payload["period"]["years"], src),
        "period_start": rec.date(payload["period"]["start"]),
        "period_end": rec.date(payload["period"]["end"]),
        "capital": rec.money(payload["inputs"]["capital"], src),
        "end_value_after_selling": rec.money(payload["portfolio"]["costs"]["end_value_net"], src),
        "portfolio_as_recommended": {
            "note": "Uses today's portfolio on past prices, so it benefits from hindsight.",
            **_metrics(rec, payload["portfolio"]["metrics"], src),
        },
        "rules_applied_at_start_date": (
            _metrics(rec, rules["metrics"], src) if rules.get("status") == "available" else None
        ),
        "benchmark": {
            "label": rec.text(BENCHMARK_LABEL, src),
            **_metrics(rec, payload["benchmark"]["metrics"], src),
        },
        "kse100": rec.text(KSE100_NOTE, src),
    }


@lru_cache(maxsize=1)
def _matchable_aliases() -> dict[str, list[str]]:
    """Reviewed names of the forecast stocks, long enough not to be everyday words."""
    aliases: dict[str, list[str]] = {}
    with (DATA_DIR / "news_aliases.csv").open(encoding="utf-8") as fh:
        next(fh)
        for line in fh:
            ticker, alias = line.strip().split(",", 1)
            if " " in alias or len(alias) >= 5:
                aliases.setdefault(ticker, []).append(normalize(alias))
    return aliases


def mentioned_tickers(db: Session, texts: list[str]) -> list[str]:
    """
    Stocks the conversation names: a catalog ticker written in capitals as a whole word
    ("HBL", not "power" for POWER), or a reviewed company name of a forecast stock.
    """
    catalog = {t for (t,) in db.query(Stock.ticker)} - _NOT_A_MENTION
    found: list[str] = []
    for text in texts:
        for word in re.findall(r"\b[A-Z][A-Z0-9]{1,9}\b", text):
            if word in catalog and word not in found:
                found.append(word)
        clean = normalize(text)
        for ticker, names in _matchable_aliases().items():
            if ticker not in found and any(name in clean for name in names):
                found.append(ticker)
    return found


def _price(rec: _Recorder, db: Session, ticker: str, covered: bool) -> dict | None:
    try:
        quote = StockService.get_quote(db, ticker)
    except PriceDataUnavailable:
        return None
    src = f"price:{ticker}"
    return {
        "source": src,
        "ticker": ticker,
        "name": quote["name"],
        "has_forecast": covered,
        "last_close": rec.money(quote["price"], src),
        "as_of": rec.date(quote["timestamp"]),
    }


def _source_tags(data: dict) -> dict[str, dict]:
    """What a reply's tag says for each source: kind, stock and the date of the data."""
    tags = {"risk_profile": {"kind": "risk_profile"}}
    if data["portfolio"]:
        tags["portfolio"] = {"kind": "portfolio", "date": data["portfolio"]["generated_on"]}
    if data["backtest"]:
        tags["backtest"] = {"kind": "backtest", "date": data["backtest"]["run_on"]}
    for section, kind in (("forecasts", "prediction"), ("sentiment", "sentiment")):
        for item in data[section]:
            tags[item["source"]] = {"kind": kind, "ticker": item["ticker"], "date": item["as_of"]}
    for item in data["other_stocks"]:
        tags[item["source"]] = {"kind": "price", "ticker": item["ticker"], "date": item["as_of"]}
    return tags


def _load_bundle():
    try:
        return load_bundle(settings.MODEL_DIR)
    except ModelNotFoundError:
        return None


def build_context(
    db: Session,
    user: User,
    message: str,
    recent_user_messages: list[str],
    reply_language: str,
    bundle=None,
) -> ChatContext:
    """
    The grounding context for one message. Forecasts and sentiment cover the portfolio's
    stocks plus any stock named in this message or the last two user messages.
    """
    rec = _Recorder()
    bundle = bundle if bundle is not None else _load_bundle()
    covered = set(bundle.metadata["tickers"]) if bundle else set()
    missing: list[str] = []
    refs: dict = {"model_version": bundle.version if bundle else None}

    portfolio = portfolio_service.active_portfolio(db, user)
    portfolio_data = _portfolio(rec, portfolio) if portfolio else None
    if portfolio is None:
        missing.append("No portfolio yet: the user can generate one on the Portfolio screen.")
    else:
        refs["portfolio_id"] = str(portfolio.id)

    result = latest_portfolio_backtest(db, user, portfolio.id) if portfolio else None
    backtest_data = _backtest(rec, result) if result else None
    if portfolio is not None and result is None:
        missing.append("No backtest of this portfolio yet: it can be run on the Backtest screen.")
    if result is not None:
        refs["backtest_id"] = str(result.id)

    recommended = (
        [h["ticker"] for h in portfolio_data["recommended_stocks"]] if portfolio_data else []
    )
    named = mentioned_tickers(db, [message, *recent_user_messages[-2:]])
    focus = list(dict.fromkeys([*recommended, *named]))
    stocks = {s.ticker: s for s in db.query(Stock).filter(Stock.ticker.in_(focus))}

    forecasts, sentiments, others, prediction_ids = [], [], [], []
    if bundle is None:
        missing.append("No forecasts: the forecast model is not available right now.")
    for ticker in focus:
        stock = stocks.get(ticker)
        if stock is None:
            continue
        if ticker in covered:
            forecast = _forecast(rec, db, stock, bundle)
            if forecast:
                forecasts.append(forecast[0])
                prediction_ids.append(forecast[1])
            else:
                missing.append(f"No forecast for {ticker} has been made yet.")
        if ticker in settings.tracked_tickers:
            sentiments.append(_sentiment(rec, db, stock))
        if ticker not in recommended and ticker not in covered:
            price = _price(rec, db, ticker, covered=False)
            if price:
                others.append(price)
            missing.append(
                f"{ticker} has no forecast: forecasts cover only the {len(covered)} stocks the "
                "model was trained on."
            )
    refs["prediction_ids"] = prediction_ids

    data = {
        "context_version": CONTEXT_VERSION,
        "today": rec.date(datetime.datetime.now(datetime.timezone.utc)),
        "reply_language": reply_language,
        # InvestIQ never buys anything: the portfolio is always named as a recommendation
        "portfolio_name": portfolio_name(reply_language),
        "portfolio_short_name": portfolio_name(reply_language, short=True),
        "risk_profile": _risk_profile(rec, user),
        "portfolio": portfolio_data,
        "forecasts": forecasts,
        "sentiment": sentiments,
        "backtest": backtest_data,
        "other_stocks": others,
        "forecast_stocks": sorted(covered),
        "urdu_glossary": {},
        "roman_urdu_glossary": {},
        "missing": [rec.text(m, "context") for m in missing],
    }
    if reply_language == "ur":
        data["urdu_glossary"] = glossary_for(json.dumps(data, ensure_ascii=False))
    if reply_language == "ur-latn":
        data["roman_urdu_glossary"] = roman_glossary_for(json.dumps(data, ensure_ascii=False))
    return ChatContext(
        data=data,
        figures=rec.figures,
        dates=rec.dates,
        sources=_source_tags(data),
        refs=refs,
    )


def _locale(language: str) -> dict:
    return json.loads((I18N_DIR / f"{language}.json").read_text(encoding="utf-8"))


def _lookup(messages: dict, key: str) -> str:
    for part in key.split("."):
        messages = messages[part]
    return messages


@lru_cache(maxsize=1)
def urdu_glossary() -> dict[str, str]:
    """English term -> the app's Urdu word, from the locale files the web app uses."""
    return {english: urdu for _marker, english, urdu in _glossary_entries()}


@lru_cache(maxsize=1)
def _glossary_entries() -> list[tuple[str, str, str]]:
    """(marker, English, Urdu) for every glossary key; the marker defaults to the English."""
    try:
        en, ur = _locale("en"), _locale("ur")
    except FileNotFoundError:
        logger.warning("Urdu glossary unavailable: no locale files in %s", I18N_DIR)
        return []
    entries = []
    for key, marker in GLOSSARY_MARKERS.items():
        english, urdu = _lookup(en, key), _lookup(ur, key)
        entries.append(((english if marker is None else marker).lower(), english, urdu))
    return entries


@lru_cache(maxsize=6)
def portfolio_name(language: str, short: bool = False) -> str:
    """
    "Your InvestIQ recommended portfolio" in the reply's language, from packages/i18n; `short`
    is the name used after the first mention ("this portfolio"), so a reply does not repeat
    the full phrase (UI round, 2026-10-15).
    """
    key = "terms.recommendedPortfolioShort" if short else "terms.recommendedPortfolio"
    if language == "ur-latn":
        key += "RomanUrdu"
    try:
        return _lookup(_locale("ur" if language == "ur" else "en"), key)
    except FileNotFoundError:
        return "this portfolio" if short else "your InvestIQ recommended portfolio"


@lru_cache(maxsize=1)
def _roman_entries() -> list[tuple[str, str, str]]:
    """(marker, English, Roman Urdu) for every Roman Urdu glossary key."""
    try:
        en = _locale("en")
    except FileNotFoundError:
        return []
    return [
        (
            marker.lower(),
            _lookup(en, f"terms.romanUrdu.{key}.en"),
            _lookup(en, f"terms.romanUrdu.{key}.roman"),
        )
        for key, marker in ROMAN_URDU_MARKERS.items()
    ]


def roman_glossary_for(context_text: str) -> dict[str, str]:
    """English term -> Roman Urdu word, for the entries this context holds."""
    text = context_text.lower()
    return {english: roman for marker, english, roman in _roman_entries() if marker in text}


def glossary_for(context_text: str) -> dict[str, str]:
    """The glossary entries whose term this context holds (screen names always)."""
    text = context_text.lower()
    return {english: urdu for marker, english, urdu in _glossary_entries() if marker in text}


def estimate_tokens(text: str) -> int:
    return -(-len(text) // CHARS_PER_TOKEN)


def fit_to_budget(
    context: ChatContext, history_chars: int, budget_tokens: int = MAX_INPUT_TOKENS
) -> ChatContext:
    """
    Trims the context until it and the history fit the provider's budget: headline titles go
    first (their counts stay), then the per-holding charge lines (each holding's total stays).
    Portfolio totals and forecasts are never dropped; the caller drops old history turns.
    Figures that leave the context also leave the figure check's list.
    """

    def over() -> bool:
        return estimate_tokens(context.json) + -(-history_chars // CHARS_PER_TOKEN) > (
            budget_tokens
        )

    def keep_figures_in(data_text: str) -> None:
        context.figures = [f for f in context.figures if f.text in data_text]

    if over():
        for item in context.data["sentiment"]:
            item["top_headlines_untrusted"] = []
        context.trimmed.append("headlines")
        keep_figures_in(context.json)
    if over() and context.data["portfolio"]:
        for holding in context.data["portfolio"]["recommended_stocks"]:
            holding["charges"] = {"total": holding["charges"]["total"]}
        context.trimmed.append("charge_lines")
        keep_figures_in(context.json)
    return context
