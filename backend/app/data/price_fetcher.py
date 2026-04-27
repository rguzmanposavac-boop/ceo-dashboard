import logging
from datetime import date, datetime

import pandas as pd
import yfinance as yf

log = logging.getLogger(__name__)


def fetch_current_price(ticker: str) -> dict:
    """Return the most recent close price, volume, and daily change % for ticker."""
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="5d", interval="1d", auto_adjust=True)
    except Exception as exc:
        log.error("[price] yfinance error fetching current price for %s: %s", ticker, exc)
        raise ValueError(f"yfinance error for {ticker}: {exc}") from exc

    if hist.empty:
        log.warning("[price] No price data returned by yfinance for %s", ticker)
        raise ValueError(f"No price data returned for {ticker}")

    closes = hist["Close"].dropna()
    volumes = hist["Volume"]

    if len(closes) < 1:
        log.warning("[price] Empty close series for %s", ticker)
        raise ValueError(f"Empty close series for {ticker}")

    current_price = float(closes.iloc[-1])
    price_date: date = closes.index[-1].date()

    vol_val = volumes.iloc[-1] if len(volumes) > 0 else None
    current_volume = int(vol_val) if vol_val is not None and not pd.isna(vol_val) else 0

    change_pct = None
    if len(closes) >= 2:
        prev_price = float(closes.iloc[-2])
        if prev_price > 0:
            change_pct = (current_price - prev_price) / prev_price

    return {
        "ticker": ticker,
        "price": round(current_price, 4),
        "volume": current_volume,
        "change_pct": round(change_pct, 6) if change_pct is not None else None,
        "price_date": price_date,
    }


def fetch_price_history(ticker: str, period: str = "1y") -> list[dict]:
    """Return daily close/volume history as a list of dicts for price_cache insert."""
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period=period, interval="1d", auto_adjust=True)
    except Exception as exc:
        log.error("[price] yfinance error fetching history for %s (%s): %s", ticker, period, exc)
        raise ValueError(f"yfinance error for {ticker}: {exc}") from exc

    if hist.empty:
        log.warning("[price] No history returned for %s (period=%s)", ticker, period)
        raise ValueError(f"No history returned for {ticker}")

    result: list[dict] = []
    prev_close: float | None = None

    for ts, row in hist.iterrows():
        close = row["Close"]
        if pd.isna(close):
            continue

        close_f = float(close)
        vol_raw = row["Volume"]
        volume = int(vol_raw) if not pd.isna(vol_raw) else None

        change_pct = None
        if prev_close and prev_close > 0:
            change_pct = (close_f - prev_close) / prev_close

        result.append({
            "ticker": ticker,
            "price_date": ts.date(),
            "close_price": close_f,
            "volume": volume,
            "change_pct": round(change_pct, 6) if change_pct is not None else None,
        })
        prev_close = close_f

    return result


def fetch_and_store_price_history(ticker: str, db, days: int = 5 * 365) -> dict:
    """Download up to 5 years of daily OHLCV and bulk-upsert into price_history.

    Returns {ticker, inserted, skipped, total}.
    Duplicates (same stock_id + date) are silently ignored.
    """
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from app.models.price_history import PriceHistory
    from app.models.stock import Stock

    ticker = ticker.upper()

    stock = db.query(Stock).filter(Stock.ticker == ticker).first()
    if not stock:
        raise ValueError(f"Ticker '{ticker}' not in stocks table — seed first")

    period_str = "5y" if days >= 1825 else f"{days}d"
    t = yf.Ticker(ticker)
    hist = t.history(period=period_str, interval="1d", auto_adjust=True)

    if hist.empty:
        log.warning("[price_history] No data returned for %s (period=%s)", ticker, period_str)
        return {"ticker": ticker, "inserted": 0, "skipped": 0, "total": 0}

    rows: list[dict] = []
    for ts, row in hist.iterrows():
        close_val = row.get("Close")
        if close_val is None or pd.isna(close_val):
            continue
        # Normalize to naive datetime (UTC) — yfinance may return tz-aware timestamps
        ts_naive: datetime = ts.to_pydatetime().replace(tzinfo=None)
        rows.append({
            "stock_id": stock.id,
            "ticker":   ticker,
            "date":     ts_naive,
            "open":     float(row["Open"])   if not pd.isna(row.get("Open",   float("nan"))) else None,
            "high":     float(row["High"])   if not pd.isna(row.get("High",   float("nan"))) else None,
            "low":      float(row["Low"])    if not pd.isna(row.get("Low",    float("nan"))) else None,
            "close":    round(float(close_val), 4),
            "volume":   int(row["Volume"]) if not pd.isna(row.get("Volume", float("nan"))) else None,
        })

    if not rows:
        return {"ticker": ticker, "inserted": 0, "skipped": 0, "total": 0}

    stmt = (
        pg_insert(PriceHistory)
        .values(rows)
        .on_conflict_do_nothing(constraint="uq_price_history_stock_date")
    )
    result = db.execute(stmt)
    db.commit()

    inserted = result.rowcount if result.rowcount != -1 else len(rows)
    skipped  = len(rows) - inserted
    log.info(
        "[price_history] %s: %d rows total, %d inserted, %d skipped (dupes)",
        ticker, len(rows), inserted, skipped,
    )
    return {"ticker": ticker, "inserted": inserted, "skipped": skipped, "total": len(rows)}


def fetch_bulk_price_history(tickers: list[str], period: str = "1y") -> dict[str, list[dict]]:
    """Download price history for multiple tickers (one HTTP call per ticker).

    Returns dict: {ticker: [price_rows]}.
    Uses individual Ticker.history() calls for reliability across yfinance versions.
    """
    result: dict[str, list[dict]] = {}
    for ticker in tickers:
        try:
            rows = fetch_price_history(ticker, period)
            result[ticker] = rows
            log.info("  %s: %d trading days fetched", ticker, len(rows))
        except Exception as exc:
            log.error("  %s: failed — %s", ticker, exc)
            result[ticker] = []
    return result
