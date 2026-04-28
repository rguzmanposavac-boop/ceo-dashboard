import logging
import logging.config
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException

# ---------------------------------------------------------------------------
# Logging — ensure INFO-level app/scheduler messages are visible in Docker
# ---------------------------------------------------------------------------
logging.config.dictConfig({
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(levelname)s:%(name)s: %(message)s",
        },
    },
    "handlers": {
        "stdout": {
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
            "formatter": "default",
        },
    },
    "loggers": {
        "app":          {"level": "INFO", "handlers": ["stdout"], "propagate": False},
        "apscheduler":  {"level": "INFO", "handlers": ["stdout"], "propagate": False},
    },
    "root": {"level": "WARNING"},
})
from fastapi.middleware.cors import CORSMiddleware

from app.routers import stocks, regime, catalysts, ceos, scores
from app.routers import config as config_router
from app.routers import refresh as refresh_router
from app.security import require_api_key

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan: start/stop APScheduler alongside the FastAPI process
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.scheduler import create_scheduler
    scheduler = create_scheduler()
    scheduler.start()

    jobs = scheduler.get_jobs()
    log.info("APScheduler started — %d jobs registered:", len(jobs))
    for job in jobs:
        log.info(
            "  [%-22s] next=%s",
            job.id,
            job.next_run_time.strftime("%Y-%m-%d %H:%M %Z") if job.next_run_time else "N/A",
        )

    # Expose scheduler on app.state so the status endpoint can inspect it
    app.state.scheduler = scheduler

    yield  # ← application runs here

    scheduler.shutdown(wait=False)
    log.info("APScheduler stopped")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="CEO Dashboard API",
    description="Sistema de detección de ganancias sobrenormales en acciones NYSE/Nasdaq",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://wonderful-tranquility-production-d363.up.railway.app",
        "https://*.railway.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Auto-initialize database
# ---------------------------------------------------------------------------

from app.database import Base, engine
from app.models import Stock, CEO, Catalyst, RegimeHistory, PriceCache, ScoreSnapshot, RefreshConfig, PriceHistory


def init_db():
    Base.metadata.create_all(bind=engine)

    from sqlalchemy import text
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        result = db.execute(text("SELECT COUNT(*) FROM stocks")).scalar()
        if result == 0:
            print("No data found. Running seed...")
            from app.seed import seed_data
            seed_data()
            print("✅ Database seeded")
        else:
            print(f"✅ Database ready: {result} stocks found")
    finally:
        db.close()


init_db()

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(stocks.router)
app.include_router(regime.router)
app.include_router(catalysts.router)
app.include_router(ceos.router)
app.include_router(scores.router)
app.include_router(config_router.router)
app.include_router(refresh_router.router)


# ---------------------------------------------------------------------------
# Insiders — canonical endpoint (CLAUDE.md spec)
# ---------------------------------------------------------------------------

@app.get("/api/v1/insiders/{ticker}", tags=["stocks"])
def get_insiders_canonical(ticker: str, days: int = 90):
    """Form 4 insider transactions via SEC EDGAR — live or Redis-cached."""
    from app.scheduler import cache_get
    from app.data.sec_fetcher import fetch_insider_transactions

    stock_upper = ticker.upper()
    log.info("Insider fetch: %s (%d days)", stock_upper, days)

    try:
        transactions = fetch_insider_transactions(stock_upper, days=days)
        return {"ticker": stock_upper, "days": days,
                "count": len(transactions), "transactions": transactions,
                "source": "live"}
    except Exception as exc:
        # Try Redis fallback (populated by daily job_refresh_insiders)
        cached = cache_get(f"insiders:{stock_upper}")
        if cached:
            log.info("Insider fallback from Redis for %s", stock_upper)
            return {"ticker": stock_upper, "days": days,
                    "count": len(cached), "transactions": cached,
                    "source": "redis_cache"}
        raise HTTPException(status_code=503, detail=str(exc))


# ---------------------------------------------------------------------------
# Scheduler status endpoint
# ---------------------------------------------------------------------------

@app.get("/api/v1/admin/scheduler/status", tags=["admin"])
def scheduler_status(_: None = Depends(require_api_key)):
    """List all scheduled jobs and their next fire times."""
    scheduler = getattr(app.state, "scheduler", None)
    if scheduler is None:
        return {"status": "not_started", "jobs": []}

    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id":           job.id,
            "name":         job.name,
            "next_run":     job.next_run_time.isoformat() if job.next_run_time else None,
            "trigger":      str(job.trigger),
            "max_instances":job.max_instances,
        })

    return {
        "status":   "running" if scheduler.running else "stopped",
        "timezone": str(scheduler.timezone),
        "job_count": len(jobs),
        "jobs":     jobs,
    }


# ---------------------------------------------------------------------------
# Health / root
# ---------------------------------------------------------------------------

@app.get("/")
def root():
    return {
        "service": "ceo-dashboard-api",
        "version": "0.1.0",
        "docs":    "/docs",
        "status":  "ok",
    }


@app.get("/health")
def health():
    return {"status": "ok"}
