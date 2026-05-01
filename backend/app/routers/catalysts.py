import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional

from app.database import get_db
from app.models.catalyst import Catalyst
from app.models.stock import Stock, PriceCache
from app.models.price_history import PriceHistory

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/catalysts", tags=["catalysts"])


class CatalystCreate(BaseModel):
    name: str
    catalyst_type: str
    description: Optional[str] = None
    affected_sectors: Optional[List[str]] = None
    affected_tickers: Optional[List[str]] = None
    intensity_score: Optional[float] = None
    expected_window: Optional[str] = None


def _catalyst_to_dict(c: Catalyst) -> dict:
    return {
        "id":               c.id,
        "name":             c.name,
        "catalyst_type":    c.catalyst_type,
        "description":      c.description,
        "affected_sectors": c.affected_sectors,
        "affected_tickers": c.affected_tickers,
        "intensity_score":  c.intensity_score,
        "expected_window":  c.expected_window,
        "discount_pct":     c.discount_pct,
        "is_active":        c.is_active,
        "detected_at":      c.detected_at.isoformat() if c.detected_at else None,
        "last_reviewed":    c.last_reviewed.isoformat() if c.last_reviewed else None,
    }


def _next_monday(from_dt: datetime) -> str:
    """Return the ISO date of the next Monday (never today even if today is Monday)."""
    days_ahead = (7 - from_dt.weekday()) % 7 or 7
    return (from_dt + timedelta(days=days_ahead)).date().isoformat()


# ---------------------------------------------------------------------------
# GET /api/v1/catalysts  — list all active catalysts
# ---------------------------------------------------------------------------

@router.get("")
def list_catalysts(db: Session = Depends(get_db)):
    catalysts = db.query(Catalyst).filter(Catalyst.is_active.is_(True)).all()
    return [_catalyst_to_dict(c) for c in catalysts]


# ---------------------------------------------------------------------------
# GET /api/v1/catalysts/score/{ticker}
# Must be registered BEFORE /{catalyst_id} to avoid route shadowing.
# ---------------------------------------------------------------------------

@router.get("/score/{ticker}")
def get_catalyst_score(ticker: str, all: bool = False, db: Session = Depends(get_db)):
    """
    Run the Catalyst Engine for a ticker.

    ?all=true  → returns all active catalysts scored (sorted by total desc)
    default    → returns only the best-matching catalyst
    """
    from app.engines.catalyst_engine import score_catalyst, score_all_catalysts

    stock = db.query(Stock).filter(Stock.ticker == ticker.upper()).first()
    if not stock:
        raise HTTPException(status_code=404, detail=f"Ticker {ticker} not found")

    if all:
        results = score_all_catalysts(
            ticker.upper(), stock.sector, stock.universe_level or 1, db
        )
        return {"ticker": ticker.upper(), "sector": stock.sector, "catalysts": results}

    result = score_catalyst(
        ticker.upper(), stock.sector, stock.universe_level or 1, db
    )
    return {"ticker": ticker.upper(), "sector": stock.sector, **result}


# ---------------------------------------------------------------------------
# POST /api/v1/catalysts/review-pending
# Must be before /{catalyst_id} — FastAPI matches paths top-down.
# ---------------------------------------------------------------------------

@router.post("/review-pending")
def review_pending(db: Session = Depends(get_db)):
    """Return active catalysts not reviewed in the past 7 days and mark them reviewed.

    Response:
      pending_catalysts  — list of catalysts awaiting review
      last_review        — ISO date of the most-recent review across all active catalysts
      next_review        — next Monday date (ISO)
      status             — "Es hora de revisar" | "Revisado recientemente"
    """
    now     = datetime.utcnow()
    cutoff  = now - timedelta(days=7)

    pending: list[Catalyst] = (
        db.query(Catalyst)
        .filter(
            Catalyst.is_active.is_(True),
            or_(Catalyst.last_reviewed.is_(None), Catalyst.last_reviewed < cutoff),
        )
        .order_by(Catalyst.detected_at.desc())
        .all()
    )

    # Most recent last_reviewed across ALL active catalysts
    last_review_ts = (
        db.query(func.max(Catalyst.last_reviewed))
        .filter(Catalyst.is_active.is_(True))
        .scalar()
    )

    # Stamp all pending catalysts as reviewed now
    for c in pending:
        c.last_reviewed = now
    db.commit()

    return {
        "pending_catalysts": [_catalyst_to_dict(c) for c in pending],
        "last_review":       last_review_ts.date().isoformat() if last_review_ts else None,
        "next_review":       _next_monday(now),
        "status":            "Es hora de revisar" if pending else "Revisado recientemente",
    }


# ---------------------------------------------------------------------------
# GET /api/v1/catalysts/review-status
# ---------------------------------------------------------------------------

@router.get("/review-status")
def review_status(db: Session = Depends(get_db)):
    """Flag active catalysts that may be priced-in or stale.

    Priced-in  — any affected ticker has risen >25 % since the catalyst was detected.
    Stale      — catalyst not reviewed in the last 6 months (180 days).

    For price comparison the endpoint uses price_history (if synced) and falls
    back to price_cache for the reference price at detection date.
    """
    now          = datetime.utcnow()
    stale_cutoff = now - timedelta(days=180)

    catalysts: list[Catalyst] = (
        db.query(Catalyst).filter(Catalyst.is_active.is_(True)).all()
    )

    flagged = []

    for c in catalysts:
        reasons:       list[str]  = []
        price_changes: list[dict] = []

        # ── Stale check ──────────────────────────────────────────────────────
        ref_ts = c.last_reviewed or c.detected_at
        if ref_ts and ref_ts < stale_cutoff:
            reasons.append("STALE")

        # ── Priced-in check (up to 3 affected tickers) ───────────────────────
        for ticker in (c.affected_tickers or [])[:3]:
            ticker = ticker.upper()

            # Reference price: first trading day within ±5 days of detected_at
            hist_row = (
                db.query(PriceHistory.close, PriceHistory.date)
                .filter(
                    PriceHistory.ticker == ticker,
                    PriceHistory.date   >= (c.detected_at - timedelta(days=5)),
                    PriceHistory.date   <= (c.detected_at + timedelta(days=5)),
                )
                .order_by(PriceHistory.date)
                .first()
            )
            # Fall back to price_cache if price_history not populated
            if hist_row is None:
                fallback = (
                    db.query(PriceCache.close_price, PriceCache.price_date)
                    .filter(PriceCache.ticker == ticker)
                    .order_by(PriceCache.price_date)
                    .first()
                )
                if fallback:
                    hist_row = (fallback[0], fallback[1])

            # Current price
            cur = (
                db.query(PriceCache.close_price)
                .filter(PriceCache.ticker == ticker)
                .order_by(PriceCache.price_date.desc())
                .first()
            )

            if hist_row and cur and hist_row[0] and cur[0] and hist_row[0] > 0:
                pct = (cur[0] - hist_row[0]) / hist_row[0]
                ref_date = (
                    hist_row[1].date().isoformat()
                    if hasattr(hist_row[1], "date") else str(hist_row[1])
                )
                price_changes.append({
                    "ticker":      ticker,
                    "ref_price":   round(float(hist_row[0]), 2),
                    "cur_price":   round(float(cur[0]),      2),
                    "pct_change":  round(pct, 4),
                    "since_date":  ref_date,
                })
                if pct > 0.25 and "PRICED_IN" not in reasons:
                    reasons.append("PRICED_IN")

        if not reasons:
            continue

        days_since = (
            (now - c.last_reviewed).days if c.last_reviewed
            else (now - c.detected_at).days if c.detected_at
            else None
        )

        flagged.append({
            **_catalyst_to_dict(c),
            "reasons":            sorted(set(reasons)),
            "days_since_reviewed": days_since,
            "price_changes":      price_changes,
        })

    # Sort: most reasons first, then oldest first
    flagged.sort(key=lambda x: (-len(x["reasons"]), x["days_since_reviewed"] or 0), reverse=False)

    return {
        "flagged_count":      len(flagged),
        "flagged_catalysts":  flagged,
        "checked_at":         now.isoformat(),
    }


# ---------------------------------------------------------------------------
# GET /api/v1/catalysts/{catalyst_id}  — single catalyst by ID (int)
# ---------------------------------------------------------------------------

@router.get("/{catalyst_id}")
def get_catalyst(catalyst_id: int, db: Session = Depends(get_db)):
    c = db.query(Catalyst).filter(Catalyst.id == catalyst_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Catalizador no encontrado")
    return _catalyst_to_dict(c)


# ---------------------------------------------------------------------------
# POST /api/v1/catalysts  — create a new catalyst
# ---------------------------------------------------------------------------

@router.post("")
def create_catalyst(body: CatalystCreate, db: Session = Depends(get_db)):
    catalyst = Catalyst(
        name=body.name,
        catalyst_type=body.catalyst_type,
        description=body.description,
        affected_sectors=body.affected_sectors,
        affected_tickers=body.affected_tickers,
        intensity_score=body.intensity_score,
        expected_window=body.expected_window,
        is_active=True,
    )
    db.add(catalyst)
    db.commit()
    db.refresh(catalyst)
    log.info("Created catalyst id=%d: %s", catalyst.id, catalyst.name)
    return {"id": catalyst.id, "message": "Catalizador creado"}


# ---------------------------------------------------------------------------
# PATCH /api/v1/catalysts/{catalyst_id}/deactivate
# ---------------------------------------------------------------------------

@router.patch("/{catalyst_id}/deactivate")
def deactivate_catalyst(catalyst_id: int, db: Session = Depends(get_db)):
    c = db.query(Catalyst).filter(Catalyst.id == catalyst_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Catalizador no encontrado")
    c.is_active = False
    db.commit()
    return {"id": catalyst_id, "is_active": False}
