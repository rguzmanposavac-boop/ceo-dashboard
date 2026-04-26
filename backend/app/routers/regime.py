import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import get_db
from app.models.regime import RegimeHistory
from app.engines.regime_detector import run_regime_detection

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/regime", tags=["regime"])


def _row_to_dict(r: RegimeHistory) -> dict:
    return {
        "regime": r.regime,
        "vix": r.vix,
        "spy_3m_return": r.spy_3m_return,
        "yield_curve_spread": r.yield_curve_spread,
        "confidence": r.confidence,
        "favored_sectors": r.favored_sectors,
        "avoided_sectors": r.avoided_sectors,
        "detected_at": r.detected_at.isoformat(),
    }


def _save_detection(data: dict, db: Session) -> RegimeHistory:
    row = RegimeHistory(
        regime=data["regime"],
        vix=data["vix"],
        spy_3m_return=data["spy_3m_return"],
        yield_curve_spread=data["yield_curve_spread"],
        confidence=data["confidence"],
        favored_sectors=data["favored_sectors"],
        avoided_sectors=data["avoided_sectors"],
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("/current")
def get_current_regime(db: Session = Depends(get_db)):
    """Return the most recent regime snapshot.

    On first call (empty table) auto-runs detection so the dashboard is
    immediately usable without a separate POST /refresh call.
    """
    latest = (
        db.query(RegimeHistory)
        .order_by(desc(RegimeHistory.detected_at))
        .first()
    )

    if not latest:
        log.info("No regime data in DB — running initial detection")
        try:
            data = run_regime_detection()
            latest = _save_detection(data, db)
        except Exception as exc:
            log.error("Auto-detection failed: %s", exc)
            raise HTTPException(
                status_code=503,
                detail=f"No regime data available and auto-detection failed: {exc}",
            )

    return _row_to_dict(latest)


@router.post("/refresh")
def refresh_regime(db: Session = Depends(get_db)):
    """Force-fetch live market data, detect regime, persist, and return result."""
    try:
        data = run_regime_detection()
    except Exception as exc:
        log.error("Regime detection failed: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc))

    row = _save_detection(data, db)
    result = _row_to_dict(row)
    result["vix_ma20"] = data.get("vix_ma20")
    result["spy_vs_ma50"] = data.get("spy_vs_ma50")
    return result


@router.get("/history")
def get_regime_history(limit: int = 30, db: Session = Depends(get_db)):
    rows = (
        db.query(RegimeHistory)
        .order_by(desc(RegimeHistory.detected_at))
        .limit(limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "regime": r.regime,
            "vix": r.vix,
            "spy_3m_return": r.spy_3m_return,
            "confidence": r.confidence,
            "detected_at": r.detected_at.isoformat(),
        }
        for r in rows
    ]
