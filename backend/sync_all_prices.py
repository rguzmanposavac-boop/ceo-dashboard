"""Sync 5 years of daily OHLCV price history for all seeded stocks.

Usage:
    # Inside container
    docker compose exec backend python sync_all_prices.py

    # Outside container (with DB accessible)
    cd backend && python sync_all_prices.py
"""
import sys
import time

# Allow running from repo root or from backend/
sys.path.insert(0, "/app")
sys.path.insert(0, ".")

from app.database import SessionLocal
from app.data.price_fetcher import fetch_and_store_price_history

TICKERS = [
    # Core Universe
    "BRK-B", "PGR",  "MSFT", "NVDA", "AMZN", "GOOGL", "AAPL", "META",
    "TSLA",  "NFLX", "AVGO", "SYK",  "WMT",  "LUV",   "AMD",  "LMT",
    "RTX",   "NEE",  "LLY",  "JPM",  "V",    "CRWD",
    # Opportunity Universe
    "VRT",   "CEG",  "AXON", "VKTX", "PLTR", "SMCI",  "GEV",  "ASTS",
]

DAYS = 5 * 365  # ~5 years of trading data


def main() -> None:
    total_records  = 0
    succeeded      = 0
    failed_tickers: list[str] = []

    print(f"\n📦 Sincronizando {len(TICKERS)} stocks — {DAYS} días (~5 años) por ticker\n")

    with SessionLocal() as db:
        for i, ticker in enumerate(TICKERS, 1):
            prefix = f"[{i:02d}/{len(TICKERS)}]"
            try:
                result = fetch_and_store_price_history(ticker, db, days=DAYS)
                days_dl = result["total"]
                inserted = result["inserted"]
                skipped  = result["skipped"]

                detail = f"{inserted} nuevos" if skipped == 0 else f"{inserted} nuevos, {skipped} ya existían"
                print(f"  ✅ {prefix} {ticker}: {days_dl} días descargados ({detail})")

                total_records += inserted
                succeeded += 1

            except Exception as exc:
                print(f"  ❌ {prefix} {ticker}: {exc}", file=sys.stderr)
                failed_tickers.append(ticker)

            # Small pause to avoid hammering yfinance rate limits
            if i < len(TICKERS):
                time.sleep(0.5)

    print(f"\n{'─' * 55}")
    print(f"  ✅ Sincronización completa: {succeeded} stocks, {total_records:,} registros nuevos")

    if failed_tickers:
        print(f"  ⚠️  Fallaron {len(failed_tickers)}: {', '.join(failed_tickers)}")

    print(f"{'─' * 55}\n")

    if failed_tickers:
        sys.exit(1)


if __name__ == "__main__":
    main()
