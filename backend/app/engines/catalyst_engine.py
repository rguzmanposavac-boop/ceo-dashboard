"""
Sprint 4: Catalyst Engine — 5 subfactors per CLAUDE.md section 5.2.

catalyst_total = intensity(30%) + discount(30%) + sensitivity(20%)
                 + window(10%) + coverage(10%)

For each ticker, the engine selects the single best-matching active catalyst
and returns all 5 subfactor scores plus the weighted total.
"""
import logging

from sqlalchemy.orm import Session

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Taxonomy (kept for reference / future routing logic)
# ---------------------------------------------------------------------------

CATALYST_TYPES: dict[str, list[str]] = {
    "AI_INFRASTRUCTURE":     ["Semiconductores", "Data Centers", "Energía", "Ciberseguridad", "IA Infra"],
    "GEOPOLITICAL_CONFLICT": ["Defensa", "Aerospace", "Energía", "Materiales críticos"],
    "TRADE_WAR_TARIFFS":     ["Manufactura doméstica", "Reshoring", "Logística local"],
    "BIOTECH_BREAKTHROUGH":  ["Farmacéutica", "Biotech", "Dispositivos Médicos", "Healthcare"],
    "ENERGY_TRANSITION":     ["Solar", "Eólica", "Baterías", "EVs", "Grid", "Nuclear"],
    "RATE_CYCLE_TURN":       ["Financials", "REITs", "Utilities", "Growth tech"],
    "COMMODITY_SUPPLY_SHOCK":["Minería", "Energía", "Agri", "Materiales"],
    "GOVERNMENT_CAPEX":      ["Infraestructura", "Defensa", "Salud pública", "Nuclear SMR"],
    "PANDEMIC_HEALTH_CRISIS":["Farmacéutica", "Biotech", "Telemedicina", "Logística"],
    "EARNINGS_REVISION_UP":  ["acción específica"],
    "INSIDER_CLUSTER_BUY":   ["acción específica"],
    "ACTIVIST_INVESTOR":     ["acción específica"],
    "REGULATORY_CHANGE":     ["sector específico"],
}

# Window → score mapping (CLAUDE.md section 5.2, subfactor 4)
_WINDOW_SCORES: dict[str, float] = {
    "INMEDIATO": 95.0,   # 0-4 weeks
    "PROXIMO":   75.0,   # 1-6 months
    "FUTURO":    55.0,   # 6-24 months
    "INCIERTO":  30.0,   # >24 months
}

# Tickers with very wide analyst coverage (>15 analysts → low coverage score)
_MEGA_CAP_TICKERS = frozenset({
    "NVDA", "MSFT", "AAPL", "AMZN", "GOOGL", "META", "TSLA",
    "JPM", "V", "LLY", "AVGO", "BRK-B",
})

# Large-cap tickers with moderate coverage (5-15 analysts)
_LARGE_CAP_TICKERS = frozenset({
    "AMD", "NFLX", "CRWD", "WMT", "SYK", "RTX", "LMT", "NEE",
    "PGR", "PLTR", "AXON",
})


# ---------------------------------------------------------------------------
# Subfactor 1 — Catalyst Intensity (30%)
# CLAUDE.md: stored 0-100 in the catalyst record itself.
# ---------------------------------------------------------------------------

def _intensity_score(raw: float | None) -> float:
    return float(raw) if raw is not None else 50.0


# ---------------------------------------------------------------------------
# Subfactor 2 — Price Discount Level (30%) — most critical
# CLAUDE.md: measures how much is NOT yet priced in.
# Uses 6M price return as proxy; boosted for longer-horizon catalysts.
# ---------------------------------------------------------------------------

def _discount_score(ret_6m: float | None, ret_3m: float | None,
                    expected_window: str | None) -> float:
    # Longer remaining window → higher score (more upside still ahead)
    window_boost = {"FUTURO": 15.0, "INCIERTO": 10.0, "PROXIMO": 8.0, "INMEDIATO": 0.0}
    boost = window_boost.get(expected_window or "INCIERTO", 8.0)

    # Prefer 6M momentum; fall back to 3M
    r = ret_6m if ret_6m is not None else ret_3m
    if r is None:
        return min(95.0, 65.0 + boost)

    # Map return → base discount score (inverse relationship)
    if r <= 0.0:      # flat or down → catalyst still largely unpriced
        base = 90.0
    elif r <= 0.10:   # <10% up → barely begun to price in
        base = 80.0
    elif r <= 0.25:   # 10-25% up → starting to price in
        base = 65.0
    elif r <= 0.50:   # 25-50% up → significantly priced in
        base = 45.0
    else:             # >50% up → largely priced in
        base = 25.0

    return min(95.0, base + boost)


# ---------------------------------------------------------------------------
# Subfactor 3 — Company Sensitivity (20%)
# CLAUDE.md: >60% of business directly affected → 90-100; 30-60% → 60-89; etc.
# Proxy: direct ticker match + sector match from catalyst's affected lists.
# ---------------------------------------------------------------------------

def _fuzzy_in(needle: str, haystack: list[str]) -> bool:
    n = needle.lower()
    return any(h.lower() in n or n in h.lower() for h in haystack)


def _sensitivity_score(ticker: str, sector: str, catalyst) -> float:
    affected_tickers = catalyst.affected_tickers or []
    affected_sectors = catalyst.affected_sectors or []

    ticker_match  = ticker.upper() in [t.upper() for t in affected_tickers]
    sector_match  = _fuzzy_in(sector, affected_sectors)

    if ticker_match and sector_match:
        # Company explicitly named AND sector aligns → >60% of business directly affected
        return 92.0
    elif ticker_match:
        # Explicitly named but sector label differs → still high direct exposure
        return 85.0
    elif sector_match:
        # Sector exposure only → ~30-60% of business
        return 62.0
    else:
        # No direct connection found
        return 12.0


# ---------------------------------------------------------------------------
# Subfactor 4 — Time Window (10%)
# ---------------------------------------------------------------------------

def _window_score(expected_window: str | None) -> float:
    return _WINDOW_SCORES.get(expected_window or "INCIERTO", 30.0)


# ---------------------------------------------------------------------------
# Subfactor 5 — Market Coverage (10%)
# CLAUDE.md: fewer analysts = more opportunity.
# Proxy: ticker universe level + mega-cap status.
# ---------------------------------------------------------------------------

def _coverage_score(ticker: str, universe_level: int, catalyst_type: str) -> float:
    t = ticker.upper()
    if t in _MEGA_CAP_TICKERS:
        # >15 analysts → 0-59 range per spec; use 28 (well-covered, no edge)
        return 28.0
    elif t in _LARGE_CAP_TICKERS:
        # 5-15 analysts → 60-89 range
        return 60.0
    elif universe_level == 2:
        # Mid-cap opportunity universe → fewer analysts → 60-89, higher end
        return 72.0
    else:
        # Unknown/small: treat as lightly covered
        return 80.0


# ---------------------------------------------------------------------------
# Price return helper (local; avoids circular import with core_engine)
# ---------------------------------------------------------------------------

def _compute_returns_local(price_rows: list) -> dict[str, float | None]:
    if not price_rows:
        return {"ret_3m": None, "ret_6m": None}
    rows = sorted(price_rows, key=lambda r: str(r.price_date), reverse=True)
    latest = rows[0].close_price
    if not latest:
        return {"ret_3m": None, "ret_6m": None}

    def _ret(n: int) -> float | None:
        if len(rows) < n:
            return None
        past = rows[min(n, len(rows) - 1)].close_price
        return (latest - past) / past if past else None

    return {"ret_3m": _ret(63), "ret_6m": _ret(126)}


# ---------------------------------------------------------------------------
# Score a single catalyst against a ticker
# ---------------------------------------------------------------------------

def _score_single_catalyst(
    ticker: str,
    sector: str,
    universe_level: int,
    catalyst,
    rets: dict[str, float | None],
) -> dict:
    s1 = _intensity_score(catalyst.intensity_score)
    s2 = _discount_score(rets.get("ret_6m"), rets.get("ret_3m"), catalyst.expected_window)
    s3 = _sensitivity_score(ticker, sector, catalyst)
    s4 = _window_score(catalyst.expected_window)
    s5 = _coverage_score(ticker, universe_level, catalyst.catalyst_type)

    total = s1 * 0.30 + s2 * 0.30 + s3 * 0.20 + s4 * 0.10 + s5 * 0.10
    total = min(100.0, max(0.0, total))

    return {
        "catalyst_id":        catalyst.id,
        "catalyst_name":      catalyst.name,
        "catalyst_type":      catalyst.catalyst_type,
        "expected_window":    catalyst.expected_window,
        "intensity_score":    round(s1, 2),
        "discount_score":     round(s2, 2),
        "sensitivity_score":  round(s3, 2),
        "window_score":       round(s4, 2),
        "coverage_score":     round(s5, 2),
        "catalyst_total":     round(total, 2),
    }


# ---------------------------------------------------------------------------
# Null result when no catalyst matches
# ---------------------------------------------------------------------------

def _null_result() -> dict:
    return {
        "catalyst_id":       None,
        "catalyst_name":     None,
        "catalyst_type":     None,
        "expected_window":   None,
        "intensity_score":   0.0,
        "discount_score":    0.0,
        "sensitivity_score": 0.0,
        "window_score":      0.0,
        "coverage_score":    0.0,
        "catalyst_total":    0.0,
    }


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def score_catalyst(
    ticker: str,
    sector: str,
    universe_level: int,
    db: Session,
) -> dict:
    """
    Find the best-matching active catalyst for a ticker and compute the
    5-subfactor Catalyst Engine score.

    Returns a dict with keys:
      catalyst_id, catalyst_name, catalyst_type, expected_window,
      intensity_score, discount_score, sensitivity_score,
      window_score, coverage_score, catalyst_total
    """
    from app.models.catalyst import Catalyst
    from app.models.stock import PriceCache
    from sqlalchemy import desc

    # Fetch price rows for momentum calculation
    price_rows = (
        db.query(PriceCache)
        .filter(PriceCache.ticker == ticker.upper())
        .order_by(desc(PriceCache.price_date))
        .limit(140)
        .all()
    )
    rets = _compute_returns_local(price_rows)

    # All active catalysts
    catalysts = db.query(Catalyst).filter(Catalyst.is_active.is_(True)).all()
    if not catalysts:
        log.warning("No active catalysts in DB for ticker %s", ticker)
        return _null_result()

    # Score each catalyst and pick the highest-scoring one
    best: dict | None = None
    for cat in catalysts:
        result = _score_single_catalyst(ticker, sector, universe_level, cat, rets)
        if best is None or result["catalyst_total"] > best["catalyst_total"]:
            best = result

    log.info(
        "%s: best catalyst '%s' → total=%.1f",
        ticker,
        (best or {}).get("catalyst_name", "none"),
        (best or {}).get("catalyst_total", 0.0),
    )
    return best or _null_result()


def score_all_catalysts(
    ticker: str,
    sector: str,
    universe_level: int,
    db: Session,
) -> list[dict]:
    """Return scores for ALL active catalysts, sorted by catalyst_total desc."""
    from app.models.catalyst import Catalyst
    from app.models.stock import PriceCache
    from sqlalchemy import desc

    price_rows = (
        db.query(PriceCache)
        .filter(PriceCache.ticker == ticker.upper())
        .order_by(desc(PriceCache.price_date))
        .limit(140)
        .all()
    )
    rets = _compute_returns_local(price_rows)

    catalysts = db.query(Catalyst).filter(Catalyst.is_active.is_(True)).all()
    results = [
        _score_single_catalyst(ticker, sector, universe_level, cat, rets)
        for cat in catalysts
    ]
    results.sort(key=lambda r: r["catalyst_total"], reverse=True)
    return results
