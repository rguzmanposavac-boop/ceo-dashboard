"""
Sprint 2: Populate price_cache with 1 year of daily price history for all active stocks.

Usage (Docker):
    docker-compose exec backend python app/populate_prices.py

Usage (local dev):
    cd backend && python app/populate_prices.py
"""
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.database import SessionLocal
from app.models.stock import Stock, PriceCache
from app.data.price_fetcher import fetch_bulk_price_history

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

BATCH_SIZE = 500   # rows per DB commit


def populate_price_cache(period: str = "1y") -> int:
    """Download price history and upsert into price_cache.

    Returns the total number of rows inserted/updated.
    """
    db = SessionLocal()
    try:
        tickers = [
            s.ticker
            for s in db.query(Stock).filter(Stock.is_active.is_(True)).all()
        ]
        if not tickers:
            log.warning("No active stocks found in DB. Run seed.py first.")
            return 0

        log.info("Fetching %s of prices for %d tickers…", period, len(tickers))
        history = fetch_bulk_price_history(tickers, period=period)

        total = 0
        batch: list[dict] = []

        def _flush(b: list[dict]):
            nonlocal total
            if not b:
                return
            stmt = (
                pg_insert(PriceCache)
                .values(b)
                .on_conflict_do_update(
                    constraint="uq_price_cache_ticker_date",
                    set_={
                        "close_price": pg_insert(PriceCache).excluded.close_price,
                        "volume":      pg_insert(PriceCache).excluded.volume,
                        "change_pct":  pg_insert(PriceCache).excluded.change_pct,
                    },
                )
            )
            db.execute(stmt)
            db.commit()
            total += len(b)

        for ticker, rows in history.items():
            if not rows:
                log.warning("  %s: no rows to insert — skipping", ticker)
                continue

            for row in rows:
                batch.append({
                    "ticker":      row["ticker"],
                    "price_date":  row["price_date"],
                    "close_price": row["close_price"],
                    "volume":      row["volume"],
                    "change_pct":  row["change_pct"],
                })
                if len(batch) >= BATCH_SIZE:
                    _flush(batch)
                    batch = []

        _flush(batch)   # final partial batch

        log.info("Done — %d price rows upserted across %d tickers.", total, len(tickers))
        return total

    except Exception as exc:
        db.rollback()
        log.error("populate_price_cache failed: %s", exc)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    populate_price_cache()
