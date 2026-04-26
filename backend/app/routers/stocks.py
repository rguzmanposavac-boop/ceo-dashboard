import logging
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import get_db
from app.models.stock import Stock, PriceCache
from app.models.ceo import CEO
from app.models.score import ScoreSnapshot
from app.data.sec_fetcher import fetch_insider_transactions

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/stocks", tags=["stocks"])


@router.get("")
def list_stocks(
    signal: Optional[str] = Query(None),
    horizon: Optional[str] = Query(None),
    sector: Optional[str] = Query(None),
    min_score: Optional[float] = Query(None),
    db: Session = Depends(get_db),
):
    stocks = db.query(Stock).filter(Stock.is_active == True).all()

    results = []
    for stock in stocks:
        # Último score disponible
        snapshot = (
            db.query(ScoreSnapshot)
            .filter(ScoreSnapshot.ticker == stock.ticker)
            .order_by(desc(ScoreSnapshot.scored_at))
            .first()
        )

        if signal and (not snapshot or snapshot.signal != signal):
            continue
        if horizon and (not snapshot or snapshot.horizon != horizon):
            continue
        if min_score and (not snapshot or (snapshot.final_score or 0) < min_score):
            continue

        ceo = db.query(CEO).filter(CEO.stock_id == stock.id).first()

        price_row = (
            db.query(PriceCache)
            .filter(PriceCache.ticker == stock.ticker)
            .order_by(desc(PriceCache.price_date))
            .first()
        )

        results.append({
            "ticker": stock.ticker,
            "company": stock.company,
            "sector": stock.sector,
            "sub_sector": stock.sub_sector,
            "market_cap_category": stock.market_cap_category,
            "exchange": stock.exchange,
            "universe_level": stock.universe_level,
            "current_price": price_row.close_price if price_row else None,
            "change_pct": price_row.change_pct if price_row else None,
            "ceo": {
                "name": ceo.name if ceo else None,
                "profile": ceo.profile if ceo else None,
                "tenure_years": ceo.tenure_years if ceo else None,
                "ownership_pct": ceo.ownership_pct if ceo else None,
                "succession_quality": ceo.succession_quality if ceo else None,
                "is_founder": ceo.is_founder if ceo else False,
            } if ceo else None,
            "score": {
                "final_score": snapshot.final_score if snapshot else None,
                "signal": snapshot.signal if snapshot else None,
                "horizon": snapshot.horizon if snapshot else None,
                "core_total": snapshot.core_total if snapshot else None,
                "catalyst_total": snapshot.catalyst_total if snapshot else None,
                "sector_score": snapshot.sector_score if snapshot else None,
                "base_score": snapshot.base_score if snapshot else None,
                "ceo_score": snapshot.ceo_score if snapshot else None,
                "roic_wacc_score": snapshot.roic_wacc_score if snapshot else None,
                "regime": snapshot.regime if snapshot else None,
                "scored_at": snapshot.scored_at.isoformat() if snapshot else None,
            },
        })

    if sector:
        results = [r for r in results if r["sector"] == sector]

    results.sort(key=lambda r: (r["score"]["final_score"] or 0), reverse=True)
    return results


@router.get("/{ticker}")
def get_stock(ticker: str, db: Session = Depends(get_db)):
    stock = db.query(Stock).filter(Stock.ticker == ticker.upper()).first()
    if not stock:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Ticker {ticker} no encontrado")

    snapshot = (
        db.query(ScoreSnapshot)
        .filter(ScoreSnapshot.ticker == stock.ticker)
        .order_by(desc(ScoreSnapshot.scored_at))
        .first()
    )
    ceo = db.query(CEO).filter(CEO.stock_id == stock.id).first()

    price_row = (
        db.query(PriceCache)
        .filter(PriceCache.ticker == stock.ticker)
        .order_by(desc(PriceCache.price_date))
        .first()
    )

    return {
        "ticker": stock.ticker,
        "company": stock.company,
        "sector": stock.sector,
        "sub_sector": stock.sub_sector,
        "market_cap_category": stock.market_cap_category,
        "exchange": stock.exchange,
        "universe_level": stock.universe_level,
        "current_price": price_row.close_price if price_row else None,
        "change_pct": price_row.change_pct if price_row else None,
        "ceo": {
            "name": ceo.name,
            "profile": ceo.profile,
            "tenure_years": ceo.tenure_years,
            "ownership_pct": ceo.ownership_pct,
            "succession_quality": ceo.succession_quality,
            "is_founder": ceo.is_founder,
            "notes": ceo.notes,
        } if ceo else None,
        "score": {
            "final_score": snapshot.final_score if snapshot else None,
            "signal": snapshot.signal if snapshot else None,
            "horizon": snapshot.horizon if snapshot else None,
            "core_total": snapshot.core_total if snapshot else None,
            "catalyst_total": snapshot.catalyst_total if snapshot else None,
            "sector_score": snapshot.sector_score if snapshot else None,
            "base_score": snapshot.base_score if snapshot else None,
            "ceo_score": snapshot.ceo_score if snapshot else None,
            "roic_wacc_score": snapshot.roic_wacc_score if snapshot else None,
            "catalyst_id": snapshot.catalyst_id if snapshot else None,
            "regime": snapshot.regime if snapshot else None,
            "invalidators": snapshot.invalidators if snapshot else None,
            "expected_return_low": snapshot.expected_return_low if snapshot else None,
            "expected_return_high": snapshot.expected_return_high if snapshot else None,
            "probability": snapshot.probability if snapshot else None,
            "scored_at": snapshot.scored_at.isoformat() if snapshot else None,
        },
    }


@router.get("/{ticker}/price-history")
def get_price_history(ticker: str, limit: int = 252, db: Session = Depends(get_db)):
    """Return cached daily price history for a ticker (most recent first)."""
    rows = (
        db.query(PriceCache)
        .filter(PriceCache.ticker == ticker.upper())
        .order_by(desc(PriceCache.price_date))
        .limit(limit)
        .all()
    )
    return [
        {
            "price_date": r.price_date.isoformat(),
            "close_price": r.close_price,
            "volume": r.volume,
            "change_pct": r.change_pct,
        }
        for r in rows
    ]


@router.get("/{ticker}/insiders")
def get_insiders(ticker: str, days: int = 90):
    """Return Form 4 insider transactions for the last N days via SEC EDGAR."""
    stock_upper = ticker.upper()
    log.info("Fetching insider transactions for %s (%d days)", stock_upper, days)
    try:
        transactions = fetch_insider_transactions(stock_upper, days=days)
        return {
            "ticker": stock_upper,
            "days": days,
            "count": len(transactions),
            "transactions": transactions,
        }
    except Exception as exc:
        log.error("Insider fetch failed for %s: %s", stock_upper, exc)
        raise HTTPException(status_code=503, detail=str(exc))
