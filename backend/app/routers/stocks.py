import logging
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import get_db
from app.models.stock import Stock, PriceCache
from app.models.price_history import PriceHistory
from app.models.ceo import CEO
from app.models.score import ScoreSnapshot
from app.data.sec_fetcher import fetch_insider_transactions
from app.data.price_fetcher import fetch_current_price
from app.routers.decision import get_price_trends, compute_final_signal

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/stocks", tags=["stocks"])


def _get_price_data(ticker: str, db: Session) -> dict:
    """Return latest price data: tries price_cache first, falls back to price_history."""
    try:
        price_row = (
            db.query(PriceCache)
            .filter(PriceCache.ticker == ticker)
            .order_by(desc(PriceCache.price_date))
            .first()
        )
        if price_row:
            # price_cache stores change_pct as decimal fraction (0.005 = 0.5%)
            # multiply by 100 so the frontend receives a true percentage
            chg = price_row.change_pct
            return {
                "current_price": price_row.close_price,
                "change_pct": round(chg * 100, 2) if chg is not None else None,
                "volume": price_row.volume,
            }

        # Fallback: price_history (fetch last 2 rows to compute change_pct)
        hist_rows = (
            db.query(PriceHistory)
            .filter(PriceHistory.ticker == ticker)
            .order_by(desc(PriceHistory.date))
            .limit(2)
            .all()
        )
        if not hist_rows:
            # Fallback final: try live fetch if both price_cache and price_history are empty.
            try:
                live = fetch_current_price(ticker)
                if live and live.get("price") is not None:
                    cache_row = PriceCache(
                        ticker=ticker,
                        price_date=live["price_date"],
                        close_price=live["price"],
                        volume=live["volume"],
                        change_pct=live["change_pct"],
                        fetched_at=datetime.utcnow(),
                    )
                    db.add(cache_row)
                    db.commit()
                    return {
                        "current_price": live["price"],
                        "change_pct": round(live["change_pct"] * 100, 2) if live["change_pct"] is not None else None,
                        "volume": live["volume"],
                    }
            except Exception as exc:
                log.warning("[price_data] live fetch fallback failed for %s: %s", ticker, exc)
            return {"current_price": None, "change_pct": None, "volume": None}

        latest = hist_rows[0]
        prev = hist_rows[1] if len(hist_rows) > 1 else None
        change_pct = None
        if prev and prev.close and latest.close:
            change_pct = round((latest.close - prev.close) / prev.close * 100, 4)

        return {
            "current_price": latest.close,
            "change_pct": change_pct,
            "volume": latest.volume,
        }
    except Exception as exc:
        log.error("[price_data] %s failed: %s", ticker, exc)
        return {"current_price": None, "change_pct": None, "volume": None}


@router.get("")
def list_stocks(
    signal: Optional[str] = Query(None),
    horizon: Optional[str] = Query(None),
    sector: Optional[str] = Query(None),
    min_score: Optional[float] = Query(None),
    db: Session = Depends(get_db),
):
    stocks = db.query(Stock).filter(Stock.is_active == True).all()

    results = []
    for stock in stocks:
        # Último score disponible
        snapshot = (
            db.query(ScoreSnapshot)
            .filter(ScoreSnapshot.ticker == stock.ticker)
            .order_by(desc(ScoreSnapshot.scored_at))
            .first()
        )

        ceo = db.query(CEO).filter(CEO.stock_id == stock.id).first()

        price_data = _get_price_data(stock.ticker, db)

        trends = get_price_trends(stock.id, price_data["current_price"] or 0.0)
        invalidators_active = bool(snapshot and snapshot.invalidators and len(snapshot.invalidators) > 0)
        final_score = (
            snapshot.final_score
            if snapshot and snapshot.final_score is not None
            else round(
                (snapshot.core_total or 0.0) * 0.65 + (snapshot.catalyst_total or 0.0) * 0.35,
                2,
            )
        )
        final_signal, _ = compute_final_signal(
            final_score,
            trends["trend_12m"],
            trends["momentum_3m"],
            invalidators_active,
        )

        if signal and final_signal != signal:
            continue
        if horizon and (not snapshot or snapshot.horizon != horizon):
            continue
        if min_score and (not snapshot or (snapshot.final_score or 0) < min_score):
            continue

        results.append({
            "ticker": stock.ticker,
            "company": stock.company,
            "sector": stock.sector,
            "sub_sector": stock.sub_sector,
            "market_cap_category": stock.market_cap_category,
            "exchange": stock.exchange,
            "universe_level": stock.universe_level,
            "current_price": price_data["current_price"],
            "change_pct": price_data["change_pct"],
            "volume": price_data["volume"],
            "trend_12m": trends["trend_12m"],
            "trend_label": trends["trend_label"],
            "momentum_3m": trends["momentum_3m"],
            "momentum_label": trends["momentum_label"],
            "ceo": {
                "name": ceo.name if ceo else None,
                "profile": ceo.profile if ceo else None,
                "tenure_years": ceo.tenure_years if ceo else None,
                "ownership_pct": ceo.ownership_pct if ceo else None,
                "succession_quality": ceo.succession_quality if ceo else None,
                "is_founder": ceo.is_founder if ceo else False,
            } if ceo else None,
            "score": {
                "final_score":         snapshot.final_score if snapshot else None,
                "signal":              final_signal,
                "horizon":             snapshot.horizon if snapshot else None,
                "core_total":          snapshot.core_total if snapshot else None,
                "catalyst_total":      snapshot.catalyst_total if snapshot else None,
                "sector_score":        snapshot.sector_score if snapshot else None,
                "base_score":          snapshot.base_score if snapshot else None,
                "ceo_score":           snapshot.ceo_score if snapshot else None,
                "roic_wacc_score":     snapshot.roic_wacc_score if snapshot else None,
                "catalyst_id":         snapshot.catalyst_id if snapshot else None,
                "expected_return_low": snapshot.expected_return_low if snapshot else None,
                "expected_return_high":snapshot.expected_return_high if snapshot else None,
                "probability":         snapshot.probability if snapshot else None,
                "invalidators":        snapshot.invalidators if snapshot else None,
                "regime":              snapshot.regime if snapshot else None,
                "scored_at":           snapshot.scored_at.isoformat() if snapshot else None,
            },
        })

    if sector:
        results = [r for r in results if r["sector"] == sector]

    results.sort(key=lambda r: (r["score"]["final_score"] or 0), reverse=True)
    return results


@router.get("/{ticker}")
def get_stock(ticker: str, db: Session = Depends(get_db)):
    stock = db.query(Stock).filter(Stock.ticker == ticker.upper()).first()
    if not stock:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Ticker {ticker} no encontrado")

    snapshot = (
        db.query(ScoreSnapshot)
        .filter(ScoreSnapshot.ticker == stock.ticker)
        .order_by(desc(ScoreSnapshot.scored_at))
        .first()
    )
    ceo = db.query(CEO).filter(CEO.stock_id == stock.id).first()

    price_data = _get_price_data(stock.ticker, db)
    trends = get_price_trends(stock.id, price_data["current_price"] or 0.0)
    invalidators_active = bool(snapshot and snapshot.invalidators and len(snapshot.invalidators) > 0)
    final_score = (
        snapshot.final_score
        if snapshot and snapshot.final_score is not None
        else round(
            (snapshot.core_total or 0.0) * 0.65 + (snapshot.catalyst_total or 0.0) * 0.35,
            2,
        )
    )
    final_signal, _ = compute_final_signal(
        final_score,
        trends["trend_12m"],
        trends["momentum_3m"],
        invalidators_active,
    )

    return {
        "ticker": stock.ticker,
        "company": stock.company,
        "sector": stock.sector,
        "sub_sector": stock.sub_sector,
        "market_cap_category": stock.market_cap_category,
        "exchange": stock.exchange,
        "universe_level": stock.universe_level,
        "current_price": price_data["current_price"],
        "change_pct": price_data["change_pct"],
        "volume": price_data["volume"],
        "trend_12m": trends["trend_12m"],
        "trend_label": trends["trend_label"],
        "momentum_3m": trends["momentum_3m"],
        "momentum_label": trends["momentum_label"],
        "ceo": {
            "name": ceo.name,
            "profile": ceo.profile,
            "tenure_years": ceo.tenure_years,
            "ownership_pct": ceo.ownership_pct,
            "succession_quality": ceo.succession_quality,
            "is_founder": ceo.is_founder,
            "notes": ceo.notes,
        } if ceo else None,
        "score": {
            "final_score": snapshot.final_score if snapshot else None,
            "signal": final_signal,
            "horizon": snapshot.horizon if snapshot else None,
            "core_total": snapshot.core_total if snapshot else None,
            "catalyst_total": snapshot.catalyst_total if snapshot else None,
            "sector_score": snapshot.sector_score if snapshot else None,
            "base_score": snapshot.base_score if snapshot else None,
            "ceo_score": snapshot.ceo_score if snapshot else None,
            "roic_wacc_score": snapshot.roic_wacc_score if snapshot else None,
            "catalyst_id": snapshot.catalyst_id if snapshot else None,
            "regime": snapshot.regime if snapshot else None,
            "invalidators": snapshot.invalidators if snapshot else None,
            "expected_return_low": snapshot.expected_return_low if snapshot else None,
            "expected_return_high": snapshot.expected_return_high if snapshot else None,
            "probability": snapshot.probability if snapshot else None,
            "scored_at": snapshot.scored_at.isoformat() if snapshot else None,
        },
    }


@router.get("/{ticker}/current-price")
def get_current_price(ticker: str, db: Session = Depends(get_db)):
    """Return the latest price snapshot for a ticker. Never raises 500."""
    stock = db.query(Stock).filter(Stock.ticker == ticker.upper()).first()
    if not stock:
        raise HTTPException(status_code=404, detail=f"Ticker {ticker} no encontrado")

    data = _get_price_data(ticker.upper(), db)
    return {
        "ticker": ticker.upper(),
        "current_price": data["current_price"],
        "price_change_percent": data["change_pct"],
        "volume": data["volume"],
    }


@router.get("/{ticker}/price-history")
def get_price_history(ticker: str, limit: int = 252, db: Session = Depends(get_db)):
    """Return cached daily price history for a ticker (most recent first)."""
    rows = (
        db.query(PriceCache)
        .filter(PriceCache.ticker == ticker.upper())
        .order_by(desc(PriceCache.price_date))
        .limit(limit)
        .all()
    )
    return [
        {
            "price_date": r.price_date.isoformat(),
            "close_price": r.close_price,
            "volume": r.volume,
            "change_pct": r.change_pct,
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Internal helpers for /prices
# ---------------------------------------------------------------------------

_TIMEFRAME_YFINANCE: dict[str, tuple[str, str]] = {
    "1D":  ("1d",  "1m"),
    "5D":  ("5d",  "5m"),
    "15D": ("15d", "1d"),
    "1M":  ("1mo", "1d"),
    "6M":  ("6mo", "1d"),
    "1Y":  ("1y",  "1d"),
    "5Y":  ("5y",  "1d"),
}

_TIMEFRAME_DAYS: dict[str, int] = {
    "1D": 1, "5D": 5, "15D": 15, "1M": 30,
    "6M": 180, "1Y": 365, "5Y": 1825,
}

# Intraday timeframes: cannot be served from daily price_history
_INTRADAY = {"1D", "5D"}


def _fetch_from_yfinance(ticker: str, timeframe: str) -> list[dict]:
    import yfinance as yf
    import pandas as pd
    period, interval = _TIMEFRAME_YFINANCE[timeframe]
    try:
        hist = yf.Ticker(ticker.upper()).history(
            period=period, interval=interval, auto_adjust=True
        )
    except Exception as exc:
        log.error("[prices] yfinance error for %s (%s): %s", ticker, timeframe, exc)
        raise HTTPException(503, f"yfinance error: {exc}")

    if hist.empty:
        return []

    result: list[dict] = []
    for ts, row in hist.iterrows():
        close = row.get("Close")
        vol   = row.get("Volume")
        if close is None or pd.isna(close):
            continue
        result.append({
            "ts":     ts.isoformat(),
            "open":   round(float(row["Open"]),  4) if not pd.isna(row.get("Open",  float("nan"))) else None,
            "high":   round(float(row["High"]),  4) if not pd.isna(row.get("High",  float("nan"))) else None,
            "low":    round(float(row["Low"]),   4) if not pd.isna(row.get("Low",   float("nan"))) else None,
            "close":  round(float(close), 4),
            "volume": int(vol) if vol is not None and not pd.isna(vol) else None,
        })
    return result


def _resample_weekly(rows: list[PriceHistory]) -> list[dict]:
    """Aggregate daily rows to weekly OHLCV bars using pandas."""
    import pandas as pd

    if not rows:
        return []

    df = pd.DataFrame(
        [
            {
                "date":   r.date,
                "open":   r.open,
                "high":   r.high,
                "low":    r.low,
                "close":  r.close,
                "volume": r.volume or 0,
            }
            for r in rows
        ]
    ).set_index("date")

    weekly = (
        df.resample("W")
        .agg({"open": "first", "high": "max", "low": "min",
              "close": "last", "volume": "sum"})
        .dropna(subset=["close"])
    )

    return [
        {
            "ts":     idx.isoformat(),
            "open":   round(float(r["open"]),  4) if pd.notna(r["open"])  else None,
            "high":   round(float(r["high"]),  4) if pd.notna(r["high"])  else None,
            "low":    round(float(r["low"]),   4) if pd.notna(r["low"])   else None,
            "close":  round(float(r["close"]), 4),
            "volume": int(r["volume"]),
        }
        for idx, r in weekly.iterrows()
    ]


# ---------------------------------------------------------------------------
# GET /prices — with optional date-range DB lookup
# ---------------------------------------------------------------------------

@router.get("/{ticker}/prices")
def get_prices_timeframe(
    ticker: str,
    timeframe: str = Query("1M"),
    start_date: Optional[str] = Query(None, description="ISO date YYYY-MM-DD"),
    end_date:   Optional[str] = Query(None, description="ISO date YYYY-MM-DD"),
    db: Session = Depends(get_db),
):
    """Return OHLCV price data for a ticker.

    Resolution per timeframe:
      1D  → 1-min bars  (always live from yfinance)
      5D  → 5-min bars  (always live from yfinance)
      15D / 1M / 6M / 1Y → daily bars
      5Y  → weekly bars (aggregated from daily price_history)

    When start_date / end_date are supplied the data is read from the
    price_history DB table (populated via POST /{ticker}/sync-price-history).
    Intraday timeframes (1D, 5D) ignore date params and always fetch live.
    Falls back to yfinance when the DB has no rows for the requested range.
    """
    if timeframe not in _TIMEFRAME_YFINANCE:
        raise HTTPException(
            400,
            f"Invalid timeframe '{timeframe}'. Allowed: {sorted(_TIMEFRAME_YFINANCE)}",
        )

    # Intraday — always live, date params ignored
    if timeframe in _INTRADAY:
        return _fetch_from_yfinance(ticker, timeframe)

    # Parse / default date bounds
    try:
        end_dt   = datetime.fromisoformat(end_date)   if end_date   else datetime.utcnow()
        start_dt = datetime.fromisoformat(start_date) if start_date else (
            end_dt - timedelta(days=_TIMEFRAME_DAYS[timeframe])
        )
    except ValueError as exc:
        raise HTTPException(400, f"Invalid date format: {exc}")

    # Query price_history
    rows: list[PriceHistory] = (
        db.query(PriceHistory)
        .filter(
            PriceHistory.ticker == ticker.upper(),
            PriceHistory.date   >= start_dt,
            PriceHistory.date   <= end_dt,
        )
        .order_by(PriceHistory.date)
        .all()
    )

    if not rows:
        # DB has no history — fall back to yfinance live
        log.info("[prices] No DB history for %s (%s) — falling back to yfinance", ticker, timeframe)
        return _fetch_from_yfinance(ticker, timeframe)

    # 5Y → aggregate to weekly bars for manageable payload size
    if timeframe == "5Y":
        return _resample_weekly(rows)

    return [
        {
            "ts":     r.date.isoformat(),
            "open":   r.open,
            "high":   r.high,
            "low":    r.low,
            "close":  r.close,
            "volume": r.volume,
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# POST /sync-price-history — download 5 years and store
# ---------------------------------------------------------------------------

@router.post("/{ticker}/sync-price-history")
def sync_price_history(
    ticker: str,
    background_tasks: BackgroundTasks,
    days: int = Query(5 * 365, ge=30, le=5 * 365),
    db: Session = Depends(get_db),
):
    """Trigger a 5-year OHLCV download for a ticker and persist to price_history.

    Runs in the background; returns immediately with a job receipt.
    Duplicate dates are silently skipped (safe to call repeatedly).
    """
    stock = db.query(Stock).filter(Stock.ticker == ticker.upper()).first()
    if not stock:
        raise HTTPException(404, f"Ticker '{ticker.upper()}' not found in stocks table")

    def _run():
        from app.database import SessionLocal
        from app.data.price_fetcher import fetch_and_store_price_history
        with SessionLocal() as session:
            try:
                result = fetch_and_store_price_history(ticker.upper(), session, days=days)
                log.info("[sync-price-history] %s done: %s", ticker.upper(), result)
            except Exception as exc:
                log.error("[sync-price-history] %s failed: %s", ticker.upper(), exc)

    background_tasks.add_task(_run)
    return {
        "status":  "queued",
        "ticker":  ticker.upper(),
        "days":    days,
        "message": f"Downloading {days}d of daily OHLCV in background",
    }


@router.get("/{ticker}/insiders")
def get_insiders(ticker: str, days: int = 90):
    """Return Form 4 insider transactions for the last N days via SEC EDGAR."""
    stock_upper = ticker.upper()
    log.info("Fetching insider transactions for %s (%d days)", stock_upper, days)
    try:
        transactions = fetch_insider_transactions(stock_upper, days=days)
        return {
            "ticker": stock_upper,
            "days": days,
            "count": len(transactions),
            "transactions": transactions,
        }
    except Exception as exc:
        log.error("Insider fetch failed for %s: %s", stock_upper, exc)
        raise HTTPException(status_code=503, detail=str(exc))
