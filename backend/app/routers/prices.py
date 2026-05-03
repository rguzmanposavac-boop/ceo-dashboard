from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.refresh_config import RefreshConfig
from app.scheduler import cache_get, job_refresh_prices, apply_refresh_config
from app.security import require_api_key

router = APIRouter(prefix="/api/v1", tags=["prices"])

VALID_INTERVALS = {"manual", "1min", "5min", "10min", "1hour", "daily"}


class PriceRefreshConfigIn(BaseModel):
    price_refresh_interval: str = "daily"


def _validate_price_interval(value: str) -> None:
    if value not in VALID_INTERVALS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid price_refresh_interval '{value}'. "
                f"Allowed: {sorted(VALID_INTERVALS)}"
            ),
        )


def _build_response(cfg: RefreshConfig | None) -> dict:
    return {
        "price_refresh_interval": cfg.price_refresh_interval if cfg else "daily",
        "score_refresh_interval": cfg.score_refresh_interval if cfg else "daily",
        "catalyst_auto_review": cfg.catalyst_auto_review if cfg else True,
        "updated_at": cfg.updated_at.isoformat() if cfg and cfg.updated_at else None,
        "last_price_update": cache_get("prices:last_update"),
        "last_score_update": cache_get("scores:last_update"),
    }


@router.get("/config/price-refresh")
def get_price_refresh_config(db: Session = Depends(get_db)):
    cfg = db.query(RefreshConfig).first()
    return _build_response(cfg)


@router.put("/config/price-refresh", dependencies=[Depends(require_api_key)])
def update_price_refresh_config(
    body: PriceRefreshConfigIn,
    request: Request,
    db: Session = Depends(get_db),
):
    _validate_price_interval(body.price_refresh_interval)

    cfg = db.query(RefreshConfig).first()
    if not cfg:
        cfg = RefreshConfig()
        db.add(cfg)

    cfg.price_refresh_interval = body.price_refresh_interval
    db.commit()
    db.refresh(cfg)

    scheduler = getattr(request.app.state, "scheduler", None)
    if scheduler:
        apply_refresh_config(scheduler, cfg)

    return _build_response(cfg)


@router.post("/refresh/prices", dependencies=[Depends(require_api_key)])
def manual_refresh_prices(background_tasks: BackgroundTasks):
    background_tasks.add_task(job_refresh_prices)
    return {
        "status": "queued",
        "job": "refresh_prices",
        "message": "Price refresh started in background",
    }
