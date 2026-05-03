import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import get_db
from app.models.stock import Stock
from app.models.score import ScoreSnapshot
from app.engines.decision_engine import run_decision

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["evaluation"])


@router.post("/evaluate/candidates")
def evaluate_candidates(db: Session = Depends(get_db)):
    stocks = (
        db.query(Stock)
        .filter(Stock.is_active.is_(True), Stock.universe_level == 2)
        .all()
    )
    if not stocks:
        raise HTTPException(status_code=404, detail="No candidate stocks found")

    results = []
    for stock in stocks:
        try:
            snapshot = (
                db.query(ScoreSnapshot)
                .filter(ScoreSnapshot.ticker == stock.ticker)
                .order_by(desc(ScoreSnapshot.scored_at))
                .first()
            )
            if snapshot and snapshot.scored_at:
                final_score = snapshot.final_score
                signal = snapshot.signal
            else:
                result = run_decision(stock.ticker, db)
                final_score = result["final_score"]
                signal = result["signal"]

            results.append({
                "ticker": stock.ticker,
                "company": stock.company,
                "score": final_score,
                "signal": signal,
                "should_enter": final_score is not None and final_score > 70,
            })
        except Exception as exc:
            log.warning("Candidate evaluation failed for %s: %s", stock.ticker, exc)
            continue

    results.sort(key=lambda x: (x["score"] or 0), reverse=True)
    return {
        "count": len(results),
        "candidates": results,
    }
