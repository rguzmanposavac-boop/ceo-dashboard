"""
Sprint 3: Core Engine — 4 layers per CLAUDE.md spec.

Weights within core_total (sum = 65):
  Layer 0 — Sector/Regime score:  20 pts
  Layer 1 — Base stock score:     20 pts
  Layer 2 — ROIC/WACC score:      15 pts
  Layer 3 — CEO adjuster:         10 pts

core_total = (s0*20 + s1*20 + s2*15 + s3*10) / 65

Hard filter: ROIC < WACC → excluded (roic_wacc_score = 0, signal = EVITAR regardless).
"""
import logging
from datetime import date, timedelta

from sqlalchemy.orm import Session

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lookup tables
# ---------------------------------------------------------------------------

CEO_PROFILES = [
    "Racional Paciente",
    "Disciplinado Sistémico",
    "Paranoico Estratégico",
    "Visionario Analítico",
    "Carismático Cultural",
    "Visionario Sistémico",
    "Narcisista Visionario",
    "Operacional Excelente",
]

PROFILE_REGIME_SCORE: dict[str, dict[str, float]] = {
    "Racional Paciente":      {"CRISIS": 95, "BAJISTA": 90, "NORMAL": 70, "ALCISTA": 50, "REBOTE": 60},
    "Disciplinado Sistémico": {"CRISIS": 90, "BAJISTA": 88, "NORMAL": 75, "ALCISTA": 60, "REBOTE": 65},
    "Paranoico Estratégico":  {"CRISIS": 80, "BAJISTA": 78, "NORMAL": 75, "ALCISTA": 70, "REBOTE": 72},
    "Visionario Analítico":   {"CRISIS": 55, "BAJISTA": 65, "NORMAL": 80, "ALCISTA": 85, "REBOTE": 80},
    "Carismático Cultural":   {"CRISIS": 60, "BAJISTA": 65, "NORMAL": 72, "ALCISTA": 70, "REBOTE": 68},
    "Visionario Sistémico":   {"CRISIS": 45, "BAJISTA": 55, "NORMAL": 75, "ALCISTA": 90, "REBOTE": 88},
    "Narcisista Visionario":  {"CRISIS": 30, "BAJISTA": 40, "NORMAL": 65, "ALCISTA": 85, "REBOTE": 90},
    "Operacional Excelente":  {"CRISIS": 65, "BAJISTA": 68, "NORMAL": 72, "ALCISTA": 68, "REBOTE": 65},
}

# Sectors favored per regime (from CLAUDE.md section 5.1 Capa 0)
_FAVORED: dict[str, list[str]] = {
    "CRISIS":  ["Healthcare", "Consumer Staples", "Utilities", "Seguros", "Holdings", "Defensa"],
    "BAJISTA": ["Healthcare", "Seguros", "Holdings", "Consumer Staples", "Software recurrente"],
    "NORMAL":  ["Tecnología", "Healthcare", "Financials", "Industrials", "Cloud"],
    "ALCISTA": ["Semiconductores", "Software", "Consumer Discretionary", "Financials", "Cloud", "IA"],
    "REBOTE":  ["Semiconductores", "EVs", "Software", "Small caps quality", "Commodities"],
}

_AVOIDED: dict[str, list[str]] = {
    "CRISIS":  ["EVs", "Consumer Discretionary", "Streaming", "Social Media", "IA Software"],
    "BAJISTA": ["EVs", "Consumer Discretionary", "Streaming", "Social Media", "Biotecnología especulativa"],
    "NORMAL":  ["Commodities", "Utilities"],
    "ALCISTA": ["Utilities", "Consumer Staples", "Seguros"],
    "REBOTE":  ["Consumer Staples", "Utilities", "Seguros"],
}


# ---------------------------------------------------------------------------
# Layer 0 — Sector/Regime score  (0-100)
# ---------------------------------------------------------------------------

def _sector_score(sector: str, regime: str, confidence: float = 1.0) -> float:
    favored = _FAVORED.get(regime, [])
    avoided = _AVOIDED.get(regime, [])

    # Exact match first, then partial substring match
    def _matches(lst: list[str], s: str) -> bool:
        s_lower = s.lower()
        return any(item.lower() in s_lower or s_lower in item.lower() for item in lst)

    if _matches(favored, sector):
        base = 85.0
    elif _matches(avoided, sector):
        base = 20.0
    else:
        base = 55.0  # neutral

    # Regime confidence blends toward neutral (55)
    return base * confidence + 55.0 * (1.0 - confidence)


# ---------------------------------------------------------------------------
# Layer 1 — Base stock score  (0-100)
# Subfactors: momentum 30%, balance 30%, liquidity 10%, valuation 30%
# ---------------------------------------------------------------------------

def _compute_returns(price_rows: list[dict]) -> dict[str, float | None]:
    """
    price_rows: list of {'price_date': date|str, 'close_price': float},
                sorted most-recent first (as returned by price-history endpoint).
    Returns 3M (~63 trading days), 6M (~126), 12M (~252) returns.
    """
    if not price_rows:
        return {"ret_3m": None, "ret_6m": None, "ret_12m": None}

    # Sort descending by date to be safe
    rows = sorted(price_rows, key=lambda r: str(r["price_date"]), reverse=True)
    latest = rows[0]["close_price"]

    def _ret(n: int) -> float | None:
        if len(rows) < n:
            return None
        past = rows[min(n, len(rows) - 1)]["close_price"]
        if not past:
            return None
        return (latest - past) / past

    return {
        "ret_3m":  _ret(63),
        "ret_6m":  _ret(126),
        "ret_12m": _ret(252),
    }


def _momentum_score(ret_3m: float | None, ret_6m: float | None, ret_12m: float | None) -> float:
    """Normalize returns to 0-100; returns that beat typical market are higher."""
    def _norm(r: float | None) -> float:
        if r is None:
            return 50.0  # neutral when data unavailable
        # Clamp to ±50% range, map to 0-100
        clamped = max(-0.5, min(0.5, r))
        return (clamped + 0.5) * 100.0

    return _norm(ret_3m) * 0.40 + _norm(ret_6m) * 0.30 + _norm(ret_12m) * 0.30


def _balance_score(fcf_yield: float | None, debt_to_equity: float | None,
                   interest_coverage: float | None) -> float:
    scores = []

    # FCF yield: >5% excellent, 2-5% good, <0 bad
    if fcf_yield is not None:
        if fcf_yield >= 0.05:
            scores.append(90.0)
        elif fcf_yield >= 0.02:
            scores.append(70.0)
        elif fcf_yield >= 0.0:
            scores.append(50.0)
        else:
            scores.append(20.0)
    else:
        scores.append(50.0)

    # D/E: <0.5 excellent, 0.5-1 good, 1-2 ok, >2 bad
    if debt_to_equity is not None:
        d = abs(debt_to_equity)
        if d < 0.5:
            scores.append(90.0)
        elif d < 1.0:
            scores.append(75.0)
        elif d < 2.0:
            scores.append(55.0)
        else:
            scores.append(25.0)
    else:
        scores.append(50.0)

    # Interest coverage: >5x excellent, 3-5 good, 1.5-3 ok, <1.5 bad
    if interest_coverage is not None:
        ic = interest_coverage
        if ic >= 5.0:
            scores.append(90.0)
        elif ic >= 3.0:
            scores.append(70.0)
        elif ic >= 1.5:
            scores.append(45.0)
        else:
            scores.append(15.0)
    else:
        scores.append(60.0)  # slight positive: benefit of doubt

    return sum(scores) / len(scores)


def _liquidity_score(avg_daily_volume: float | None) -> float:
    """Volume in USD. >$50M excellent, $10M-$50M good, $2M-$10M ok, <$2M bad."""
    if avg_daily_volume is None:
        return 50.0
    v = avg_daily_volume
    if v >= 50_000_000:
        return 95.0
    if v >= 10_000_000:
        return 75.0
    if v >= 2_000_000:
        return 50.0
    return 20.0


def _valuation_score(pe: float | None, ev_ebitda: float | None, p_fcf: float | None) -> float:
    """Lower multiples → higher score (cheaper valuation)."""
    scores = []

    def _pe_s(v: float) -> float:
        if v <= 0:
            return 30.0  # negative P/E: loss-making
        if v <= 15:
            return 90.0
        if v <= 25:
            return 70.0
        if v <= 40:
            return 50.0
        return 25.0

    def _ev_ebitda_s(v: float) -> float:
        if v <= 0:
            return 30.0
        if v <= 8:
            return 90.0
        if v <= 15:
            return 70.0
        if v <= 25:
            return 50.0
        return 25.0

    def _pfcf_s(v: float) -> float:
        if v <= 0:
            return 30.0
        if v <= 15:
            return 90.0
        if v <= 25:
            return 70.0
        if v <= 40:
            return 50.0
        return 25.0

    if pe is not None:
        scores.append(_pe_s(pe))
    if ev_ebitda is not None:
        scores.append(_ev_ebitda_s(ev_ebitda))
    if p_fcf is not None:
        scores.append(_pfcf_s(p_fcf))

    return sum(scores) / len(scores) if scores else 50.0


def _base_score(
    ret_3m: float | None, ret_6m: float | None, ret_12m: float | None,
    fcf_yield: float | None, debt_to_equity: float | None, interest_coverage: float | None,
    avg_daily_volume: float | None,
    pe: float | None, ev_ebitda: float | None, p_fcf: float | None,
    accruals_ratio: float | None,
) -> float:
    mom   = _momentum_score(ret_3m, ret_6m, ret_12m)
    bal   = _balance_score(fcf_yield, debt_to_equity, interest_coverage)
    liq   = _liquidity_score(avg_daily_volume)
    val   = _valuation_score(pe, ev_ebitda, p_fcf)

    score = mom * 0.30 + bal * 0.30 + liq * 0.10 + val * 0.30

    # Hard accruals penalty per CLAUDE.md
    if accruals_ratio is not None and accruals_ratio > 0.10:
        score = max(0.0, score - 20.0)

    return score


# ---------------------------------------------------------------------------
# Layer 2 — ROIC/WACC  (0-100, with hard exclusion at ratio < 1.0)
# ---------------------------------------------------------------------------

def roic_wacc_score(ratio: float) -> float:
    if ratio >= 2.0:
        return 100.0
    if ratio >= 1.5:
        return 80.0
    if ratio >= 1.0:
        return 60.0
    return 0.0  # triggers hard exclusion


# ---------------------------------------------------------------------------
# Layer 3 — CEO Adjuster  (0-100 equivalent, then used as *weight*)
# ---------------------------------------------------------------------------

def tenure_multiplier(years: float) -> float:
    if years < 1:    return 0.85
    if years <= 2:   return 0.92
    if years <= 5:   return 1.10
    if years <= 8:   return 1.05
    if years <= 12:  return 1.00
    if years <= 15:  return 0.95
    return 0.88


def ownership_factor(pct: float) -> float:
    if pct >= 10:   return 1.15
    if pct >= 3:    return 1.10
    if pct >= 1:    return 1.05
    if pct >= 0.1:  return 1.00
    return 0.95


def succession_factor(quality: str) -> float:
    return {"excellent": 1.08, "good": 1.02, "poor": 0.92, "unknown": 0.97}.get(quality, 0.97)


def _ceo_score(
    profile: str | None,
    regime: str,
    tenure_years: float | None,
    ownership_pct: float | None,
    succession_quality: str | None,
) -> float:
    base = PROFILE_REGIME_SCORE.get(profile or "", {}).get(regime, 60.0)
    t_mult = tenure_multiplier(tenure_years if tenure_years is not None else 5.0)
    o_fact = ownership_factor(ownership_pct if ownership_pct is not None else 0.1)
    s_fact = succession_factor(succession_quality or "unknown")
    raw = base * t_mult * o_fact * s_fact
    return min(100.0, max(0.0, raw))


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def score_core(
    ticker: str,
    sector: str,
    db: Session,
    financials: dict | None = None,
    regime_override: str | None = None,
) -> dict:
    """
    Compute the Core Engine score for a single ticker.

    Returns a dict with keys:
      regime, excluded, sector_score, base_score, roic_wacc_score,
      ceo_score, core_total, accruals_penalized, roic_wacc_ratio
    """
    from app.models.regime import RegimeHistory
    from app.models.stock import PriceCache
    from app.models.ceo import CEO
    from app.models.stock import Stock
    from app.data.financials_fetcher import fetch_financials
    from sqlalchemy import desc

    # ---- Regime ----
    if regime_override:
        regime = regime_override
        confidence = 1.0
    else:
        row = db.query(RegimeHistory).order_by(desc(RegimeHistory.detected_at)).first()
        if row:
            regime = row.regime
            confidence = row.confidence or 1.0
        else:
            regime = "NORMAL"
            confidence = 0.8

    # ---- Financials ----
    if financials is None:
        try:
            financials = fetch_financials(ticker)
        except Exception as exc:
            log.warning("Financials fetch failed for %s: %s", ticker, exc)
            financials = {}

    roic_wacc_ratio: float | None = financials.get("roic_wacc_ratio")

    # ---- Hard ROIC/WACC filter ----
    if roic_wacc_ratio is not None and roic_wacc_ratio < 1.0:
        log.info("%s excluded: ROIC < WACC (ratio=%.2f)", ticker, roic_wacc_ratio)
        return {
            "regime": regime,
            "excluded": True,
            "sector_score": 0.0,
            "base_score": 0.0,
            "roic_wacc_score": 0.0,
            "ceo_score": 0.0,
            "core_total": 0.0,
            "accruals_penalized": False,
            "roic_wacc_ratio": roic_wacc_ratio,
        }

    # ---- Layer 0: Sector/Regime ----
    s0 = _sector_score(sector, regime, confidence)

    # ---- Layer 1: Base score ----
    # Price rows from price_cache (most-recent first)
    price_rows = (
        db.query(PriceCache)
        .filter(PriceCache.ticker == ticker.upper())
        .order_by(desc(PriceCache.price_date))
        .limit(260)
        .all()
    )
    price_dicts = [{"price_date": str(r.price_date), "close_price": r.close_price} for r in price_rows]
    rets = _compute_returns(price_dicts)

    # Estimate avg daily volume in USD from most recent 30 rows
    recent_30 = price_rows[:30]
    if recent_30:
        avg_vol_usd = sum(
            (r.close_price or 0) * (r.volume or 0) for r in recent_30
        ) / len(recent_30)
    else:
        avg_vol_usd = None

    # Derived valuation multiples from financials
    market_cap = financials.get("market_cap") or 0
    fcf        = financials.get("fcf") or 0
    ebitda     = financials.get("ebitda")
    ebit       = financials.get("ebit") or 0
    total_debt = financials.get("total_debt") or 0
    cash       = financials.get("cash") or 0

    pe: float | None = None
    ev_ebitda: float | None = None
    p_fcf: float | None = None
    fcf_yield: float | None = None

    net_income = financials.get("net_income")
    if market_cap and net_income and net_income > 0:
        pe = market_cap / net_income

    if market_cap and ebitda and ebitda > 0:
        ev = market_cap + total_debt - cash
        ev_ebitda = ev / ebitda

    if market_cap and fcf and fcf > 0:
        p_fcf = market_cap / fcf
        fcf_yield = fcf / market_cap

    accruals_ratio = financials.get("accruals_ratio")
    accruals_penalized = bool(accruals_ratio is not None and accruals_ratio > 0.10)

    s1 = _base_score(
        ret_3m=rets["ret_3m"], ret_6m=rets["ret_6m"], ret_12m=rets["ret_12m"],
        fcf_yield=fcf_yield,
        debt_to_equity=financials.get("debt_to_equity"),
        interest_coverage=financials.get("interest_coverage"),
        avg_daily_volume=avg_vol_usd,
        pe=pe, ev_ebitda=ev_ebitda, p_fcf=p_fcf,
        accruals_ratio=accruals_ratio,
    )

    # ---- Layer 2: ROIC/WACC ----
    if roic_wacc_ratio is not None:
        s2 = roic_wacc_score(roic_wacc_ratio)
    else:
        s2 = 50.0  # neutral when data unavailable

    # ---- Layer 3: CEO ----
    stock = db.query(Stock).filter(Stock.ticker == ticker.upper()).first()
    ceo_row = db.query(CEO).filter(CEO.stock_id == stock.id).first() if stock else None

    if ceo_row:
        s3 = _ceo_score(
            profile=ceo_row.profile,
            regime=regime,
            tenure_years=ceo_row.tenure_years,
            ownership_pct=ceo_row.ownership_pct,
            succession_quality=ceo_row.succession_quality,
        )
    else:
        s3 = 55.0  # neutral fallback

    # ---- Weighted total (weights sum to 65, normalize to 0-100) ----
    core_total = (s0 * 20 + s1 * 20 + s2 * 15 + s3 * 10) / 65.0
    core_total = min(100.0, max(0.0, core_total))

    return {
        "regime":            regime,
        "excluded":          False,
        "sector_score":      round(s0, 2),
        "base_score":        round(s1, 2),
        "roic_wacc_score":   round(s2, 2),
        "ceo_score":         round(s3, 2),
        "core_total":        round(core_total, 2),
        "accruals_penalized": accruals_penalized,
        "roic_wacc_ratio":   roic_wacc_ratio,
    }
