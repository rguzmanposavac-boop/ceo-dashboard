"""Sprint 10: refresh schedule configuration endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.refresh_config import RefreshConfig
from app.security import require_api_key

router = APIRouter(prefix="/api/v1/config", tags=["config"])

VALID_INTERVALS = {"manual", "1min", "5min", "1hour", "daily"}


class RefreshScheduleIn(BaseModel):
    price_refresh_interval: str = "1hour"
    score_refresh_interval: str = "1hour"
    catalyst_auto_review: bool = True


def _validate(body: RefreshScheduleIn) -> None:
    if body.price_refresh_interval not in VALID_INTERVALS:
        raise HTTPException(
            400,
            f"Invalid price_refresh_interval '{body.price_refresh_interval}'. "
            f"Allowed: {sorted(VALID_INTERVALS)}",
        )
    if body.score_refresh_interval not in VALID_INTERVALS:
        raise HTTPException(
            400,
            f"Invalid score_refresh_interval '{body.score_refresh_interval}'. "
            f"Allowed: {sorted(VALID_INTERVALS)}",
        )


def _build_response(cfg: RefreshConfig) -> dict:
    from app.scheduler import cache_get
    return {
        "price_refresh_interval": cfg.price_refresh_interval,
        "score_refresh_interval": cfg.score_refresh_interval,
        "catalyst_auto_review":   cfg.catalyst_auto_review,
        "updated_at":             cfg.updated_at.isoformat() if cfg.updated_at else None,
        "last_price_update":      cache_get("prices:last_update"),
        "last_score_update":      cache_get("scores:last_update"),
    }


@router.get("/refresh-schedule")
def get_refresh_schedule(db: Session = Depends(get_db)):
    """Return current refresh schedule config and freshness timestamps."""
    from app.scheduler import cache_get
    cfg = db.query(RefreshConfig).first()
    if not cfg:
        return {
            "price_refresh_interval": "1hour",
            "score_refresh_interval": "1hour",
            "catalyst_auto_review":   True,
            "updated_at":             None,
            "last_price_update":      cache_get("prices:last_update"),
            "last_score_update":      cache_get("scores:last_update"),
        }
    return _build_response(cfg)


def _upsert_and_apply(body: RefreshScheduleIn, db: Session, app_state) -> dict:
    _validate(body)

    cfg = db.query(RefreshConfig).first()
    if not cfg:
        cfg = RefreshConfig()
        db.add(cfg)

    cfg.price_refresh_interval = body.price_refresh_interval
    cfg.score_refresh_interval = body.score_refresh_interval
    cfg.catalyst_auto_review   = body.catalyst_auto_review
    db.commit()
    db.refresh(cfg)

    scheduler = getattr(app_state, "scheduler", None)
    if scheduler:
        from app.scheduler import apply_refresh_config
        apply_refresh_config(scheduler, cfg)

    return _build_response(cfg)


@router.post("/refresh-schedule", dependencies=[Depends(require_api_key)])
def create_refresh_schedule(
    body: RefreshScheduleIn,
    request: Request,
    db: Session = Depends(get_db),
):
    """Create or replace the refresh schedule configuration."""
    return _upsert_and_apply(body, db, request.app.state)


@router.put("/refresh-schedule", dependencies=[Depends(require_api_key)])
def update_refresh_schedule(
    body: RefreshScheduleIn,
    request: Request,
    db: Session = Depends(get_db),
):
    """Update the refresh schedule configuration (idempotent)."""
    return _upsert_and_apply(body, db, request.app.state)
