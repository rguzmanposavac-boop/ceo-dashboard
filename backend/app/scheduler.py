"""
Sprint 6: APScheduler — automated data refresh jobs.

Market-hours schedule (Mon-Fri 9:30-16:00 ET) — runs every ~60 min:
  :30  job_refresh_prices   → fetch latest prices, upsert price_cache
  :35  job_refresh_regime   → detect regime, persist to DB
  :40  job_refresh_scores   → full Decision Engine for all active stocks

Daily off-hours schedule (Mon-Fri 6:00 AM ET):
  06:00  job_refresh_financials  → ROIC/WACC/FCF per ticker → Redis 24h
  06:30  job_refresh_insiders    → Form 4 via SEC EDGAR → Redis 24h

Redis fallback strategy:
  - After every successful fetch, write to Redis with TTL
  - On yfinance/SEC failure, try Redis; log warning if missing
  - Prices TTL: 2h  |  Financials/Insiders TTL: 24h
"""
import json
import logging
import os
from contextlib import contextmanager

import redis as redis_lib
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Redis helpers
# ---------------------------------------------------------------------------

_redis_client: redis_lib.Redis | None = None


def _get_redis() -> redis_lib.Redis:
    global _redis_client
    if _redis_client is None:
        url = os.environ.get("REDIS_URL", "redis://localhost:6379")
        _redis_client = redis_lib.from_url(
            url,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
    return _redis_client


def cache_set(key: str, value: object, ttl: int = 7200) -> bool:
    """Serialize value to JSON and store in Redis with TTL (seconds). Returns True on success."""
    try:
        _get_redis().setex(key, ttl, json.dumps(value, default=str))
        return True
    except Exception as exc:
        log.debug("Redis SET failed [%s]: %s", key, exc)
        return False


def cache_get(key: str) -> object | None:
    """Retrieve and deserialize a JSON value from Redis. Returns None on miss/error."""
    try:
        raw = _get_redis().get(key)
        return json.loads(raw) if raw else None
    except Exception as exc:
        log.debug("Redis GET failed [%s]: %s", key, exc)
        return None


# ---------------------------------------------------------------------------
# DB session factory for scheduled jobs (independent of FastAPI DI)
# ---------------------------------------------------------------------------

@contextmanager
def _db_session():
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Job 1: refresh_prices  (market hours, :30 every hour)
# ---------------------------------------------------------------------------

def job_refresh_prices() -> None:
    """Fetch today's price for every active ticker → upsert price_cache + Redis 2h."""
    log.info("[sched] refresh_prices START")
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from app.models.stock import Stock, PriceCache
    from app.data.price_fetcher import fetch_current_price

    with _db_session() as db:
        tickers = [s.ticker for s in db.query(Stock).filter(Stock.is_active.is_(True)).all()]

    updated = 0
    failed  = 0

    for ticker in tickers:
        try:
            data = fetch_current_price(ticker)
            # Persist to price_cache
            with _db_session() as db:
                stmt = (
                    pg_insert(PriceCache)
                    .values(
                        ticker     = ticker,
                        price_date = data["price_date"],
                        close_price= data["price"],
                        volume     = data["volume"],
                        change_pct = data["change_pct"],
                    )
                    .on_conflict_do_update(
                        constraint="uq_price_cache_ticker_date",
                        set_=dict(
                            close_price= data["price"],
                            volume     = data["volume"],
                            change_pct = data["change_pct"],
                        ),
                    )
                )
                db.execute(stmt)
                db.commit()
            # Write to Redis (TTL 2h)
            cache_set(f"price:{ticker}", data, ttl=7200)
            updated += 1

        except Exception as exc:
            failed += 1
            log.warning("[sched] price fetch failed %s: %s", ticker, exc)
            # Fallback: Redis still holds the last known price
            cached = cache_get(f"price:{ticker}")
            if cached:
                log.info("[sched] price fallback active for %s (Redis hit)", ticker)
            else:
                log.error("[sched] no Redis fallback for %s price", ticker)

    log.info("[sched] refresh_prices DONE — updated=%d failed=%d / %d tickers",
             updated, failed, len(tickers))


# ---------------------------------------------------------------------------
# Job 2: refresh_regime  (market hours, :35 every hour)
# ---------------------------------------------------------------------------

def job_refresh_regime() -> None:
    """Detect current market regime → persist to regime_history + Redis 2h."""
    log.info("[sched] refresh_regime START")
    from app.engines.regime_detector import run_regime_detection
    from app.routers.regime import _save_detection

    try:
        data = run_regime_detection()
        with _db_session() as db:
            _save_detection(data, db)
        cache_set("regime:current", data, ttl=7200)
        log.info("[sched] refresh_regime DONE — regime=%s vix=%.2f",
                 data.get("regime"), data.get("vix", 0.0))

    except Exception as exc:
        log.error("[sched] refresh_regime failed: %s", exc)
        cached = cache_get("regime:current")
        if cached:
            log.info("[sched] regime fallback: %s (from Redis)", cached.get("regime"))
        else:
            log.error("[sched] no Redis fallback for regime")


# ---------------------------------------------------------------------------
# Job 3: refresh_scores  (market hours, :40 every hour)
# ---------------------------------------------------------------------------

def job_refresh_scores() -> None:
    """Run full Decision Engine for all active stocks → score_snapshots + Redis 2h."""
    log.info("[sched] refresh_scores START")
    from app.engines.decision_engine import run_decision
    from app.models.stock import Stock

    with _db_session() as db:
        tickers = [s.ticker for s in db.query(Stock).filter(Stock.is_active.is_(True)).all()]

    ok     = 0
    failed = 0

    for ticker in tickers:
        try:
            with _db_session() as db:
                result = run_decision(ticker, db)

            cache_set(f"score:{ticker}", {
                "final_score":    result["final_score"],
                "signal":         result["signal"],
                "horizon":        result["horizon"],
                "core_total":     result["core"]["core_total"],
                "catalyst_total": result["catalyst"]["catalyst_total"],
                "regime":         result["regime"],
            }, ttl=7200)
            ok += 1

        except Exception as exc:
            failed += 1
            log.warning("[sched] score failed %s: %s", ticker, exc)
            if cache_get(f"score:{ticker}"):
                log.info("[sched] score fallback active for %s (Redis hit)", ticker)
            else:
                log.error("[sched] no Redis fallback for %s score", ticker)

    log.info("[sched] refresh_scores DONE — ok=%d failed=%d / %d tickers",
             ok, failed, len(tickers))


# ---------------------------------------------------------------------------
# Job 4: refresh_financials  (daily 6:00 AM ET)
# ---------------------------------------------------------------------------

def job_refresh_financials() -> None:
    """Fetch ROIC/WACC/FCF for all active tickers → Redis 24h."""
    log.info("[sched] refresh_financials START")
    from app.models.stock import Stock
    from app.data.financials_fetcher import fetch_financials

    with _db_session() as db:
        tickers = [s.ticker for s in db.query(Stock).filter(Stock.is_active.is_(True)).all()]

    ok = 0
    for ticker in tickers:
        try:
            fin = fetch_financials(ticker)
            cache_set(f"financials:{ticker}", fin, ttl=86400)   # 24h
            ok += 1
        except Exception as exc:
            log.warning("[sched] financials failed %s: %s", ticker, exc)

    log.info("[sched] refresh_financials DONE — %d/%d tickers cached", ok, len(tickers))


# ---------------------------------------------------------------------------
# Job 5: refresh_insiders  (daily 6:30 AM ET)
# ---------------------------------------------------------------------------

def job_refresh_insiders() -> None:
    """Fetch Form 4 insider transactions for all active tickers → Redis 24h."""
    log.info("[sched] refresh_insiders START")
    from app.models.stock import Stock
    from app.data.sec_fetcher import fetch_insider_transactions

    with _db_session() as db:
        tickers = [s.ticker for s in db.query(Stock).filter(Stock.is_active.is_(True)).all()]

    ok = 0
    for ticker in tickers:
        try:
            txns = fetch_insider_transactions(ticker, days=90)
            cache_set(f"insiders:{ticker}", txns, ttl=86400)    # 24h
            ok += 1
            log.info("[sched]   %s: %d insider txns cached", ticker, len(txns))
        except Exception as exc:
            log.warning("[sched] insiders failed %s: %s", ticker, exc)

    log.info("[sched] refresh_insiders DONE — %d/%d tickers cached", ok, len(tickers))


# ---------------------------------------------------------------------------
# Scheduler factory
# ---------------------------------------------------------------------------

_ET = "America/New_York"

#  Market-hours cron: Mon-Fri, hours 9-15 (fires at 9:30, 10:30 … 15:30 ET)
#  The three jobs are staggered by 5 minutes so they run in sequence:
#  prices → regime → scores, all within the same hourly window.

_MARKET_PRICES_TRIGGER = CronTrigger(
    day_of_week="mon-fri", hour="9-15", minute="30", timezone=_ET
)
_MARKET_REGIME_TRIGGER = CronTrigger(
    day_of_week="mon-fri", hour="9-15", minute="35", timezone=_ET
)
_MARKET_SCORES_TRIGGER = CronTrigger(
    day_of_week="mon-fri", hour="9-15", minute="40", timezone=_ET
)

# Daily off-hours: 6:00 and 6:30 AM ET (Mon-Fri only, keeps weekends quiet)
_DAILY_FINANCIALS_TRIGGER = CronTrigger(
    day_of_week="mon-fri", hour="6", minute="0", timezone=_ET
)
_DAILY_INSIDERS_TRIGGER = CronTrigger(
    day_of_week="mon-fri", hour="6", minute="30", timezone=_ET
)


def create_scheduler() -> BackgroundScheduler:
    """Create and configure the APScheduler BackgroundScheduler with all 5 jobs."""
    scheduler = BackgroundScheduler(timezone=_ET)

    common = dict(max_instances=1, coalesce=True, misfire_grace_time=300)

    scheduler.add_job(
        job_refresh_prices,
        trigger   = _MARKET_PRICES_TRIGGER,
        id        = "refresh_prices",
        name      = "Refresh Prices (market hours, :30)",
        **common,
    )
    scheduler.add_job(
        job_refresh_regime,
        trigger   = _MARKET_REGIME_TRIGGER,
        id        = "refresh_regime",
        name      = "Refresh Regime (market hours, :35)",
        **common,
    )
    scheduler.add_job(
        job_refresh_scores,
        trigger   = _MARKET_SCORES_TRIGGER,
        id        = "refresh_scores",
        name      = "Refresh Scores (market hours, :40)",
        misfire_grace_time=600,   # scores can take up to 2 min — wider window
        max_instances=1,
        coalesce  = True,
    )
    scheduler.add_job(
        job_refresh_financials,
        trigger   = _DAILY_FINANCIALS_TRIGGER,
        id        = "refresh_financials",
        name      = "Refresh Financials (daily 06:00 ET)",
        max_instances=1,
        coalesce  = True,
        misfire_grace_time=1800,
    )
    scheduler.add_job(
        job_refresh_insiders,
        trigger   = _DAILY_INSIDERS_TRIGGER,
        id        = "refresh_insiders",
        name      = "Refresh Insiders (daily 06:30 ET)",
        max_instances=1,
        coalesce  = True,
        misfire_grace_time=1800,
    )

    return scheduler
