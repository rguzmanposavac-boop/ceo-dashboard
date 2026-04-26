import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional

from app.database import get_db
from app.models.catalyst import Catalyst
from app.models.stock import Stock

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
        "is_active":        c.is_active,
        "detected_at":      c.detected_at.isoformat() if c.detected_at else None,
    }


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
