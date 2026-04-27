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

Sprint 10: Dynamic rescheduling via apply_refresh_config().
  Supported intervals: manual | 1min | 5min | 1hour | daily
  'manual' pauses the job until POST /api/v1/refresh/{prices,scores} fires it.
"""
import json
import logging
import os
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import redis as redis_lib
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

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
    now_utc = datetime.now(timezone.utc)

    for ticker in tickers:
        try:
            data = fetch_current_price(ticker)
            # Persist to price_cache (with freshness timestamp)
            with _db_session() as db:
                stmt = (
                    pg_insert(PriceCache)
                    .values(
                        ticker     = ticker,
                        price_date = data["price_date"],
                        close_price= data["price"],
                        volume     = data["volume"],
                        change_pct = data["change_pct"],
                        fetched_at = now_utc,
                    )
                    .on_conflict_do_update(
                        constraint="uq_price_cache_ticker_date",
                        set_=dict(
                            close_price= data["price"],
                            volume     = data["volume"],
                            change_pct = data["change_pct"],
                            fetched_at = now_utc,
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

    # Record global freshness timestamp in Redis
    cache_set("prices:last_update", now_utc.isoformat(), ttl=86400)

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

    cache_set("scores:last_update", datetime.now(timezone.utc).isoformat(), ttl=86400)
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
# Job 6: review_catalysts_reminder  (weekly Monday 9:30 AM ET)
# ---------------------------------------------------------------------------

def job_review_catalysts_reminder() -> None:
    """Weekly Monday reminder: log alert + mark active catalysts as reviewed."""
    log.info("📋 Recordatorio: Es hora de revisar catalysts")
    from app.models.catalyst import Catalyst

    with _db_session() as db:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        cutoff = now - timedelta(days=7)
        pending = (
            db.query(Catalyst)
            .filter(
                Catalyst.is_active.is_(True),
                (Catalyst.last_reviewed.is_(None)) | (Catalyst.last_reviewed < cutoff),
            )
            .all()
        )
        for c in pending:
            c.last_reviewed = now
        db.commit()
        log.info("📋 Catalysts revisados: %d actualizados", len(pending))


# ---------------------------------------------------------------------------
# Dynamic rescheduling (Sprint 10)
# ---------------------------------------------------------------------------

_ET = "America/New_York"

_DEFAULT_TRIGGERS: dict[str, object] = {}  # populated in create_scheduler


def _interval_to_trigger(interval_str: str, job_id: str):
    """Return an APScheduler trigger for the given interval string.

    Returns None when interval_str is 'manual' (caller should pause the job).
    Falls back to the original market-hours CronTrigger for '1hour'.
    """
    if interval_str == "manual":
        return None
    if interval_str == "1min":
        return IntervalTrigger(minutes=1, timezone=_ET)
    if interval_str == "5min":
        return IntervalTrigger(minutes=5, timezone=_ET)
    if interval_str == "1hour":
        # Restore the default market-hours trigger for this job, if known
        return _DEFAULT_TRIGGERS.get(job_id) or IntervalTrigger(hours=1, timezone=_ET)
    if interval_str == "daily":
        # Fire once per day at 9:30 AM ET (market open) Mon-Fri
        minute = "30" if job_id == "refresh_prices" else "40"
        return CronTrigger(day_of_week="mon-fri", hour="9", minute=minute, timezone=_ET)
    # Unknown value — fall back to hourly interval
    log.warning("Unknown interval '%s' for job %s, defaulting to 1hour", interval_str, job_id)
    return _DEFAULT_TRIGGERS.get(job_id) or IntervalTrigger(hours=1, timezone=_ET)


def apply_refresh_config(scheduler: BackgroundScheduler, config) -> None:
    """Reschedule or pause refresh_prices and refresh_scores based on RefreshConfig."""
    pairs = [
        ("refresh_prices", config.price_refresh_interval),
        ("refresh_scores", config.score_refresh_interval),
    ]
    for job_id, interval in pairs:
        job = scheduler.get_job(job_id)
        if job is None:
            log.warning("apply_refresh_config: job '%s' not found in scheduler", job_id)
            continue

        trigger = _interval_to_trigger(interval, job_id)
        if trigger is None:
            job.pause()
            log.info("apply_refresh_config: '%s' PAUSED (interval=manual)", job_id)
        else:
            # Resume first if the job was paused, then reschedule
            if job.next_run_time is None:
                job.resume()
            scheduler.reschedule_job(job_id, trigger=trigger)
            log.info(
                "apply_refresh_config: '%s' rescheduled to interval='%s'",
                job_id, interval,
            )


# ---------------------------------------------------------------------------
# Scheduler factory
# ---------------------------------------------------------------------------

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

# Weekly catalyst review reminder: every Monday 9:30 AM ET
_WEEKLY_CATALYSTS_TRIGGER = CronTrigger(
    day_of_week="mon", hour="9", minute="30", timezone=_ET
)


def create_scheduler() -> BackgroundScheduler:
    """Create and configure the APScheduler BackgroundScheduler with all 5 jobs."""
    # Register default triggers so apply_refresh_config can restore them
    _DEFAULT_TRIGGERS["refresh_prices"] = _MARKET_PRICES_TRIGGER
    _DEFAULT_TRIGGERS["refresh_scores"] = _MARKET_SCORES_TRIGGER

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
        misfire_grace_time=600,
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
    scheduler.add_job(
        job_review_catalysts_reminder,
        trigger   = _WEEKLY_CATALYSTS_TRIGGER,
        id        = "review_catalysts",
        name      = "Review Catalysts Reminder (Monday 09:30 ET)",
        max_instances=1,
        coalesce  = True,
        misfire_grace_time=3600,
    )

    # Apply persisted config on startup (if DB is reachable)
    try:
        with _db_session() as db:
            from app.models.refresh_config import RefreshConfig
            cfg = db.query(RefreshConfig).first()
            if cfg:
                apply_refresh_config(scheduler, cfg)
                log.info(
                    "Loaded RefreshConfig from DB: prices=%s scores=%s",
                    cfg.price_refresh_interval,
                    cfg.score_refresh_interval,
                )
    except Exception as exc:
        log.warning("Could not load RefreshConfig at startup (DB not ready?): %s", exc)

    return scheduler
