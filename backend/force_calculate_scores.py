"""Force-calculate scores for all active stocks and refresh price_cache.

Usage (inside container):
    docker compose exec backend python force_calculate_scores.py

Usage (local, with DB accessible):
    cd backend && python force_calculate_scores.py
"""
import sys
import time

sys.path.insert(0, "/app")
sys.path.insert(0, ".")

from app.database import SessionLocal
from app.models.stock import Stock


def refresh_prices(tickers: list[str]) -> int:
    """Update price_cache for every ticker. Returns number of rows upserted."""
    from app.data.price_fetcher import fetch_current_price
    from app.models.stock import PriceCache
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    total = 0
    with SessionLocal() as db:
        for ticker in tickers:
            try:
                p = fetch_current_price(ticker)
                stmt = (
                    pg_insert(PriceCache)
                    .values(
                        ticker=ticker,
                        price_date=p["price_date"],
                        close_price=p["price"],
                        volume=p["volume"],
                        change_pct=p["change_pct"],
                    )
                    .on_conflict_do_update(
                        index_elements=["ticker", "price_date"],
                        set_={
                            "close_price": p["price"],
                            "volume":      p["volume"],
                            "change_pct":  p["change_pct"],
                        },
                    )
                )
                db.execute(stmt)
                total += 1
            except Exception as exc:
                print(f"  ⚠️  price skip {ticker}: {exc}", file=sys.stderr)
        db.commit()
    return total


def calculate_scores(tickers: list[str]) -> tuple[list[dict], list[dict]]:
    """Run Decision Engine for each ticker. Returns (results, errors)."""
    from app.engines.decision_engine import run_decision

    results = []
    errors  = []

    for i, ticker in enumerate(tickers, 1):
        prefix = f"[{i:02d}/{len(tickers)}]"
        try:
            with SessionLocal() as db:
                r = run_decision(ticker, db)

            score  = r["final_score"]
            signal = r["signal"]
            horizon = r["horizon"]
            print(f"  ✅ {prefix} {ticker:6s} → {score:5.1f}  {signal:<15}  {horizon}")
            results.append(r)

        except Exception as exc:
            print(f"  ❌ {prefix} {ticker}: {exc}", file=sys.stderr)
            errors.append({"ticker": ticker, "error": str(exc)})

        # Small pause to avoid hammering yfinance
        if i < len(tickers):
            time.sleep(0.3)

    return results, errors


def main() -> None:
    with SessionLocal() as db:
        tickers = [
            s.ticker
            for s in db.query(Stock).filter(Stock.is_active.is_(True)).order_by(Stock.ticker).all()
        ]

    if not tickers:
        print("❌ No active stocks found — run seed first.", file=sys.stderr)
        sys.exit(1)

    print(f"\n💰 Actualizando precios para {len(tickers)} stocks…")
    n_prices = refresh_prices(tickers)
    print(f"   ✅ {n_prices} precios actualizados en price_cache\n")

    print(f"🎯 Calculando scores ({len(tickers)} stocks)…\n")
    t0 = time.time()
    results, errors = calculate_scores(tickers)
    elapsed = time.time() - t0

    print(f"\n{'─' * 55}")
    print(f"  ✅ Scores calculados: {len(results)}/{len(tickers)} en {elapsed:.0f}s")
    if errors:
        print(f"  ⚠️  Errores: {len(errors)} — {[e['ticker'] for e in errors]}")

    if results:
        results_sorted = sorted(results, key=lambda r: r["final_score"], reverse=True)
        print(f"\n  Top 5 por score:")
        for r in results_sorted[:5]:
            print(f"    {r['ticker']:6s}  {r['final_score']:5.1f}  {r['signal']}")
    print(f"{'─' * 55}\n")

    if errors and len(errors) == len(tickers):
        sys.exit(1)


if __name__ == "__main__":
    main()
