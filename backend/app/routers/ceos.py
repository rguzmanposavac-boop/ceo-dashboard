from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.ceo import CEO
from app.models.stock import Stock

router = APIRouter(prefix="/api/v1/ceos", tags=["ceos"])


@router.get("")
def list_ceos(db: Session = Depends(get_db)):
    ceos = db.query(CEO).all()
    return [
        {
            "id": c.id,
            "stock_id": c.stock_id,
            "ticker": c.stock.ticker if c.stock else None,
            "company": c.stock.company if c.stock else None,
            "name": c.name,
            "profile": c.profile,
            "tenure_years": c.tenure_years,
            "ownership_pct": c.ownership_pct,
            "succession_quality": c.succession_quality,
            "is_founder": c.is_founder,
        }
        for c in ceos
    ]


@router.get("/{ticker}")
def get_ceo_by_ticker(ticker: str, db: Session = Depends(get_db)):
    stock = db.query(Stock).filter(Stock.ticker == ticker.upper()).first()
    if not stock:
        raise HTTPException(status_code=404, detail=f"Ticker {ticker} no encontrado")
    ceo = db.query(CEO).filter(CEO.stock_id == stock.id).first()
    if not ceo:
        raise HTTPException(status_code=404, detail=f"CEO de {ticker} no encontrado")
    return {
        "ticker": stock.ticker,
        "company": stock.company,
        "name": ceo.name,
        "profile": ceo.profile,
        "tenure_years": ceo.tenure_years,
        "ownership_pct": ceo.ownership_pct,
        "succession_quality": ceo.succession_quality,
        "is_founder": ceo.is_founder,
        "notes": ceo.notes,
    }
