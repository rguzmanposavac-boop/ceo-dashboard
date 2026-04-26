import logging

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import get_db
from app.models.score import ScoreSnapshot
from app.engines.regime_detector import run_regime_detection
from app.routers.regime import _save_detection, _row_to_dict
from app.security import require_api_key

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["scores", "admin"])


# ---------------------------------------------------------------------------
# GET /api/v1/scores/{ticker}  — score snapshot history
# ---------------------------------------------------------------------------

@router.get("/scores/{ticker}")
def get_score_history(ticker: str, limit: int = 10, db: Session = Depends(get_db)):
    rows = (
        db.query(ScoreSnapshot)
        .filter(ScoreSnapshot.ticker == ticker.upper())
        .order_by(desc(ScoreSnapshot.scored_at))
        .limit(limit)
        .all()
    )
    return [
        {
            "id":              r.id,
            "ticker":          r.ticker,
            "final_score":     r.final_score,
            "signal":          r.signal,
            "horizon":         r.horizon,
            "core_total":      r.core_total,
            "catalyst_total":  r.catalyst_total,
            "regime":          r.regime,
            "invalidators":    r.invalidators,
            "scored_at":       r.scored_at.isoformat(),
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# GET /api/v1/scores/{ticker}/core  — Core Engine breakdown (Sprint 3)
# ---------------------------------------------------------------------------

@router.get("/scores/{ticker}/core")
def get_core_score(ticker: str, regime: str | None = None, db: Session = Depends(get_db)):
    from app.engines.core_engine import score_core
    from app.models.stock import Stock
    stock = db.query(Stock).filter(Stock.ticker == ticker.upper()).first()
    if not stock:
        raise HTTPException(status_code=404, detail=f"Ticker {ticker} not found")
    result = score_core(ticker.upper(), stock.sector, db, regime_override=regime)
    return {"ticker": ticker.upper(), "sector": stock.sector, **result}


# ---------------------------------------------------------------------------
# POST /api/v1/scores/{ticker}/compute  — full Decision Engine for one ticker
# ---------------------------------------------------------------------------

@router.post("/scores/{ticker}/compute")
def compute_score(
    ticker: str,
    regime: str | None = None,
    db: Session = Depends(get_db),
):
    """
    Run the full pipeline (Core → Catalyst → Decision) for a single ticker,
    persist a new snapshot, and return the complete result.

    Optional ?regime=BAJISTA overrides the live DB regime (useful for testing).
    """
    from app.engines.decision_engine import run_decision
    try:
        result = run_decision(ticker.upper(), db, regime_override=regime)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        log.error("compute_score failed for %s: %s", ticker, exc)
        raise HTTPException(status_code=503, detail=str(exc))


# ---------------------------------------------------------------------------
# POST /api/v1/admin/refresh-scores  — full refresh for all active stocks
# ---------------------------------------------------------------------------

@router.post("/admin/refresh-scores")
def refresh_scores(db: Session = Depends(get_db), _: None = Depends(require_api_key)):
    """
    Run the Decision Engine for every active stock and persist snapshots.
    Returns a per-ticker summary of final_score and signal.
    Note: fetches live financials via yfinance — may take 60-120 s for 30 tickers.
    """
    from app.engines.decision_engine import run_decision
    from app.models.stock import Stock

    stocks = db.query(Stock).filter(Stock.is_active.is_(True)).all()
    results = []
    errors  = []

    for stock in stocks:
        try:
            r = run_decision(stock.ticker, db)
            results.append({
                "ticker":      r["ticker"],
                "final_score": r["final_score"],
                "signal":      r["signal"],
                "horizon":     r["horizon"],
                "core_total":  r["core"]["core_total"],
                "catalyst_total": r["catalyst"]["catalyst_total"],
            })
            log.info("  %s → %.1f %s", stock.ticker, r["final_score"], r["signal"])
        except Exception as exc:
            log.warning("refresh-scores failed for %s: %s", stock.ticker, exc)
            errors.append({"ticker": stock.ticker, "error": str(exc)})

    # Sort by final_score desc for easy reading
    results.sort(key=lambda x: x["final_score"], reverse=True)

    return {
        "status":   "ok",
        "computed": len(results),
        "errors":   len(errors),
        "results":  results,
        "error_detail": errors if errors else None,
    }


# ---------------------------------------------------------------------------
# POST /api/v1/admin/refresh-prices
# ---------------------------------------------------------------------------

@router.post("/admin/refresh-prices")
def admin_refresh_prices(_: None = Depends(require_api_key)):
    from app.populate_prices import populate_price_cache
    try:
        total = populate_price_cache(period="1y")
        return {"status": "ok", "rows_upserted": total}
    except Exception as exc:
        log.error("Admin refresh-prices failed: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc))


# ---------------------------------------------------------------------------
# POST /api/v1/admin/refresh-regime
# ---------------------------------------------------------------------------

@router.post("/admin/refresh-regime")
def admin_refresh_regime(db: Session = Depends(get_db), _: None = Depends(require_api_key)):
    try:
        data = run_regime_detection()
    except Exception as exc:
        log.error("Admin refresh-regime failed: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc))

    row    = _save_detection(data, db)
    result = _row_to_dict(row)
    result["vix_ma20"]     = data.get("vix_ma20")
    result["spy_vs_ma50"]  = data.get("spy_vs_ma50")
    return result


# ---------------------------------------------------------------------------
# GET /api/v1/admin/model-stats
# ---------------------------------------------------------------------------

@router.get("/admin/model-stats")
def model_stats(_: None = Depends(require_api_key)):
    from app.scheduler import cache_get
    cached = cache_get("backtest:latest")
    if cached:
        return {
            "r_squared":              cached.get("r_squared"),
            "spearman_rho":           cached.get("spearman_rho"),
            "spearman_p":             cached.get("spearman_p"),
            "avg_ic":                 cached.get("avg_ic"),
            "ic_ir":                  cached.get("ic_ir"),
            "hit_rate_cf":            cached.get("hit_rate_cf"),
            "hit_rate_buy":           cached.get("hit_rate_buy"),
            "total_cf_signals":       cached.get("total_cf_signals"),
            "total_observations":     cached.get("total_observations"),
            "avg_fwd_return_cf":      cached.get("avg_fwd_return_cf"),
            "avg_fwd_return_all":     cached.get("avg_fwd_return_all"),
            "period_start":           cached.get("period_start"),
            "period_end":             cached.get("period_end"),
            "computed_at":            cached.get("computed_at"),
            "tier_stats":             cached.get("tier_stats"),
            "portfolio_by_q":         cached.get("portfolio_by_q"),
            "avg_excess_return":      cached.get("avg_excess_return"),
            "win_rate_quarterly":     cached.get("win_rate_quarterly"),
            "regime_distribution":    cached.get("regime_distribution"),
            "per_ticker":             cached.get("per_ticker"),
            "methodology":            cached.get("methodology"),
            "source":                 "backtest",
        }
    # Static fallback before first backtest is run
    return {
        "r_squared":    0.61,
        "spearman_rho": 0.508,
        "spearman_p":   0.016,
        "hit_rate_cf":  None,
        "source":       "static",
        "note":         "Ejecuta POST /api/v1/admin/run-backtest para calcular estadísticas históricas reales.",
    }


# ---------------------------------------------------------------------------
# POST /api/v1/admin/run-backtest
# ---------------------------------------------------------------------------

@router.post("/admin/run-backtest", tags=["admin"])
def run_backtest_endpoint(db: Session = Depends(get_db), _: None = Depends(require_api_key)):
    """
    Run the full historical backtest (2020-2024).
    Downloads 5 years of price history from yfinance and simulates quarterly scores.
    Takes ~30-60 seconds depending on network. Result is cached in Redis (7 days).
    """
    from app.backtest import run_backtest
    log.info("Manual backtest triggered via API")
    try:
        result = run_backtest(db)
        if "error" in result:
            raise Exception(result["error"])
        return {"status": "ok", **result}
    except Exception as exc:
        log.error("Backtest failed: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc))
