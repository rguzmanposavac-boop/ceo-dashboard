"""
Sprint 5: Decision Engine — combines Core (65%) + Catalyst (35%) into the
final investment signal, horizon classification, expected return, probability,
and auto-generated invalidators.

Formula: final_score = core_total * 0.65 + catalyst_total * 0.35

Hard override: if core_result["excluded"] == True (ROIC < WACC),
signal is forced to "EVITAR" regardless of catalyst score.
"""
import logging

from sqlalchemy.orm import Session

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Invalidator templates (verbatim from CLAUDE.md section 5.4)
# ---------------------------------------------------------------------------

INVALIDATOR_TEMPLATES: dict[str, str] = {
    "REGIMEN_CHANGE":     "Cambio de régimen a CRISIS invalidaría la tesis de corto plazo",
    "CATALYST_PRICED_IN": "Precio sube >25% sin nuevo catalizador = catalizador ya descontado, salir",
    "EARNINGS_MISS":      "Miss de earnings >10% en próximo reporte trimestral",
    "FCF_DETERIORATION":  "FCF cae >15% YoY en próximo reporte",
    "ROIC_DROP":          "ROIC cae por debajo de WACC — destrucción de valor",
    "CEO_DEPARTURE":      "Salida del CEO actual sin sucesor identificado",
    "SECTOR_ROTATION":    "Salida de flujo institucional del sector en próximas 4 semanas",
    "MACRO_SHOCK":        "VIX supera 40 — entrada en régimen CRISIS",
    "CATALYST_REVERSAL":  "Reversión o cancelación del catalizador identificado",
    "DEBT_SURGE":         "Deuda/equity supera 2x sin justificación estratégica clara",
}


# ---------------------------------------------------------------------------
# Core decision functions (CLAUDE.md section 5.3)
# ---------------------------------------------------------------------------

def compute_final_score(core_score: float, catalyst_score: float) -> float:
    return round(core_score * 0.65 + catalyst_score * 0.35, 2)


def classify_signal(score: float) -> str:
    if score >= 80:
        return "COMPRA_FUERTE"
    if score >= 70:
        return "COMPRA"
    if score >= 58:
        return "VIGILAR"
    return "EVITAR"


def classify_horizon(
    catalyst_window: str,
    catalyst_total: float,
    core_roic: float,
    core_fundamentals: float,
) -> str:
    """
    CORTO_PLAZO  — imminent catalyst with high score
    LARGO_PLAZO  — strong fundamentals + solid ROIC, no urgent catalyst
    MEDIANO_PLAZO — everything else
    """
    if catalyst_window == "INMEDIATO" and catalyst_total > 75:
        return "CORTO_PLAZO"
    if core_fundamentals > 65 and core_roic > 70:
        return "LARGO_PLAZO"
    return "MEDIANO_PLAZO"


# ---------------------------------------------------------------------------
# Invalidator selection — context-aware subset from templates
# ---------------------------------------------------------------------------

def select_invalidators(
    signal: str,
    horizon: str,
    core_result: dict,
    catalyst_result: dict,
    financials: dict,
    ceo_succession: str | None,
) -> list[dict]:
    """
    Return a ranked list of relevant invalidators for this thesis.
    Every recommendation includes at least MACRO_SHOCK.
    """
    keys: set[str] = set()

    # Universal: macro crash invalidates everything
    keys.add("MACRO_SHOCK")

    # Strong-signal theses carry earnings/FCF risk
    if signal in ("COMPRA_FUERTE", "COMPRA"):
        keys.add("EARNINGS_MISS")
        keys.add("REGIMEN_CHANGE")

    # Short-horizon thesis: regime and sector rotation matter
    if horizon == "CORTO_PLAZO":
        keys.add("REGIMEN_CHANGE")
        keys.add("SECTOR_ROTATION")

    # Catalyst-based invalidators
    cat_total = catalyst_result.get("catalyst_total", 0.0)
    if cat_total > 40:
        keys.add("CATALYST_PRICED_IN")
    if cat_total > 50 and catalyst_result.get("catalyst_id") is not None:
        keys.add("CATALYST_REVERSAL")

    # FCF deterioration only when FCF is currently positive (means it can fall)
    fcf = financials.get("fcf") or 0.0
    if fcf > 0:
        keys.add("FCF_DETERIORATION")

    # ROIC near threshold → mention drop risk
    roic_ratio = core_result.get("roic_wacc_ratio")
    if roic_ratio is not None and roic_ratio < 1.5:
        keys.add("ROIC_DROP")

    # Succession risk
    if ceo_succession in ("poor", "unknown", None):
        keys.add("CEO_DEPARTURE")

    # Leverage risk
    dte = financials.get("debt_to_equity")
    if dte is not None and abs(float(dte)) > 1.0:
        keys.add("DEBT_SURGE")

    # Return ordered list — stable output for JSON diffs
    return [
        {"key": k, "description": INVALIDATOR_TEMPLATES[k]}
        for k in sorted(keys)
    ]


# ---------------------------------------------------------------------------
# Expected return + probability estimates
# ---------------------------------------------------------------------------

def estimate_expected_return(
    signal: str,
    catalyst_result: dict,
    core_result: dict,
) -> tuple[float, float]:
    """Return (low, high) fractional return bounds over the investment horizon."""
    base_ranges = {
        "COMPRA_FUERTE": (0.25, 0.60),
        "COMPRA":        (0.15, 0.35),
        "VIGILAR":       (0.05, 0.20),
        "EVITAR":        (-0.10, 0.05),
    }
    low, high = base_ranges.get(signal, (0.05, 0.15))

    # Boost the high end when catalyst still has material remaining upside
    if (catalyst_result.get("catalyst_total", 0) > 75
            and catalyst_result.get("discount_score", 0) > 60):
        high = min(round(high * 1.30, 2), 1.50)

    return low, high


def estimate_probability(signal: str, final_score: float) -> float:
    """Rough probability that the thesis plays out (directional, not calibrated)."""
    base = {
        "COMPRA_FUERTE": 0.62,
        "COMPRA":        0.52,
        "VIGILAR":       0.38,
        "EVITAR":        0.20,
    }
    p = base.get(signal, 0.35)
    # Fine-tune by distance from threshold (±0.3 pp per score point)
    thresholds = {"COMPRA_FUERTE": 80, "COMPRA": 70, "VIGILAR": 58, "EVITAR": 0}
    thr = thresholds.get(signal, 58)
    p += (final_score - thr) * 0.003
    return round(min(0.85, max(0.10, p)), 2)


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def run_decision(
    ticker: str,
    db: Session,
    regime_override: str | None = None,
    financials: dict | None = None,
) -> dict:
    """
    Full pipeline for one ticker:
      1. Core Engine  (sector/regime + base + ROIC + CEO)
      2. Catalyst Engine  (best-matching active catalyst, 5 subfactors)
      3. Decision Engine  (final score, signal, horizon, invalidators)
      4. Persist snapshot to score_snapshots
      5. Return complete result dict

    Args:
        ticker: uppercase ticker symbol
        db: SQLAlchemy session
        regime_override: optional regime string ("BAJISTA" etc.) — bypasses DB lookup
        financials: pre-fetched financials dict; if None, fetches via yfinance
    """
    from app.models.stock import Stock
    from app.models.score import ScoreSnapshot
    from app.models.ceo import CEO
    from app.engines.core_engine import score_core
    from app.engines.catalyst_engine import score_catalyst
    from app.data.financials_fetcher import fetch_financials

    ticker = ticker.upper()

    # -- Stock metadata --
    stock = db.query(Stock).filter(Stock.ticker == ticker).first()
    if not stock:
        raise ValueError(f"Ticker {ticker} not found in DB")

    # -- Financials (shared between core and decision layers) --
    if financials is None:
        try:
            financials = fetch_financials(ticker)
        except Exception as exc:
            log.warning("Financials unavailable for %s: %s", ticker, exc)
            financials = {}

    # -- Core Engine --
    core_result = score_core(
        ticker, stock.sector, db,
        financials=financials,
        regime_override=regime_override,
    )

    # -- Catalyst Engine --
    catalyst_result = score_catalyst(
        ticker, stock.sector, stock.universe_level or 1, db
    )

    core_total     = core_result["core_total"]
    catalyst_total = catalyst_result["catalyst_total"]
    excluded       = core_result.get("excluded", False)

    # -- Final score --
    final_score = compute_final_score(core_total, catalyst_total)

    # -- Signal (hard EVITAR override for ROIC-excluded stocks) --
    signal = "EVITAR" if excluded else classify_signal(final_score)

    # -- Horizon --
    horizon = classify_horizon(
        catalyst_window  = catalyst_result.get("expected_window") or "INCIERTO",
        catalyst_total   = catalyst_total,
        core_roic        = core_result.get("roic_wacc_score", 0.0),
        core_fundamentals= core_result.get("base_score", 0.0),
    )

    # -- Invalidators --
    ceo_row = db.query(CEO).filter(CEO.stock_id == stock.id).first()
    invalidators = select_invalidators(
        signal        = signal,
        horizon       = horizon,
        core_result   = core_result,
        catalyst_result = catalyst_result,
        financials    = financials,
        ceo_succession= ceo_row.succession_quality if ceo_row else None,
    )

    # -- Expected return + probability --
    ret_low, ret_high = estimate_expected_return(signal, catalyst_result, core_result)
    probability       = estimate_probability(signal, final_score)

    # -- Persist to score_snapshots --
    snapshot = ScoreSnapshot(
        ticker              = ticker,
        regime              = core_result["regime"],
        sector_score        = core_result.get("sector_score"),
        base_score          = core_result.get("base_score"),
        ceo_score           = core_result.get("ceo_score"),
        roic_wacc_score     = core_result.get("roic_wacc_score"),
        core_total          = core_total,
        catalyst_intensity  = catalyst_result.get("intensity_score"),
        catalyst_discount   = catalyst_result.get("discount_score"),
        catalyst_sensitivity= catalyst_result.get("sensitivity_score"),
        catalyst_window_score= catalyst_result.get("window_score"),
        catalyst_coverage   = catalyst_result.get("coverage_score"),
        catalyst_total      = catalyst_total,
        catalyst_id         = catalyst_result.get("catalyst_id"),
        final_score         = round(final_score, 2),
        signal              = signal,
        horizon             = horizon,
        expected_return_low = ret_low,
        expected_return_high= ret_high,
        probability         = probability,
        invalidators        = invalidators,
    )
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)

    log.info(
        "%s → final=%.1f signal=%s horizon=%s (core=%.1f cat=%.1f)",
        ticker, final_score, signal, horizon, core_total, catalyst_total,
    )

    return {
        "ticker":              ticker,
        "company":             stock.company,
        "sector":              stock.sector,
        "regime":              core_result["regime"],
        "excluded":            excluded,
        # Sub-engine breakdowns
        "core":                core_result,
        "catalyst":            catalyst_result,
        # Decision output
        "final_score":         round(final_score, 2),
        "signal":              signal,
        "horizon":             horizon,
        "expected_return_low": ret_low,
        "expected_return_high":ret_high,
        "probability":         probability,
        "invalidators":        invalidators,
        # Persistence
        "snapshot_id":         snapshot.id,
        "scored_at":           snapshot.scored_at.isoformat(),
    }
