import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from app.database import get_db
from app.models.score import ScoreSnapshot
from app.models.invalidator_log import InvalidatorLog
from app.models.stock import Stock
from app.security import require_api_key

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/invalidators", tags=["invalidators"])
stock_invalidators_router = APIRouter()

RECOMMENDATION_BY_KEY = {
    "REGIMEN_CHANGE": "Revisar el régimen macro y ajustar exposición",
    "CATALYST_PRICED_IN": "Verificar si el catalizador ya está descontado en precio",
    "EARNINGS_MISS": "Monitorear próximo reporte trimestral",
    "FCF_DETERIORATION": "Analizar flujo de caja antes de mantener posición",
    "ROIC_DROP": "Revisar la calidad de retorno sobre capital",
    "CEO_DEPARTURE": "Confirmar sucesión y estabilidad del management",
    "SECTOR_ROTATION": "Revisar rotación sectorial y liquidez",
    "MACRO_SHOCK": "Reducir riesgo de corto plazo y proteger capital",
    "CATALYST_REVERSAL": "Ajustar la tesis si el catalizador se revierte",
    "DEBT_SURGE": "Monitorear niveles de deuda y cobertura de intereses",
}


@router.post("/check")
def check_invalidators(db: Session = Depends(get_db)):
    latest_ids = (
        db.query(func.max(ScoreSnapshot.id).label("max_id"))
        .group_by(ScoreSnapshot.ticker)
        .subquery()
    )
    rows = (
        db.query(ScoreSnapshot)
        .join(latest_ids, ScoreSnapshot.id == latest_ids.c.max_id)
        .all()
    )

    active = []
    for row in rows:
        invalidators = row.invalidators or []
        for invalidator in invalidators:
            key = invalidator.get("key") if isinstance(invalidator, dict) else invalidator
            description = invalidator.get("description") if isinstance(invalidator, dict) else str(invalidator)
            action = RECOMMENDATION_BY_KEY.get(key, "Revisar la tesis y actualizar alertas")

            log_entry = InvalidatorLog(
                ticker=row.ticker,
                invalidator_key=key,
                description=description,
                action_recommendation=action,
                triggered_at=row.scored_at,
                active=True,
            )
            db.add(log_entry)
            active.append({
                "ticker": row.ticker,
                "key": key,
                "description": description,
                "action_recommendation": action,
            })

    if active:
        db.commit()
    return {"count": len(active), "invalidators": active}


@stock_invalidators_router.get("/api/v1/stocks/{ticker}/invalidators")
def get_stock_invalidators(ticker: str, db: Session = Depends(get_db)):
    ticker = ticker.upper()
    rows = (
        db.query(InvalidatorLog)
        .filter(InvalidatorLog.ticker == ticker)
        .order_by(desc(InvalidatorLog.triggered_at))
        .all()
    )

    if not rows:
        return {"ticker": ticker, "invalidators": []}

    latest_by_key = {}
    for entry in rows:
        if entry.invalidator_key not in latest_by_key:
            latest_by_key[entry.invalidator_key] = entry

    invalidators = [
        {
            "name": row.invalidator_key,
            "active": row.active,
            "description": row.description,
            "activated_at": row.triggered_at.isoformat(),
        }
        for row in latest_by_key.values()
    ]

    return {"ticker": ticker, "invalidators": invalidators}
