from app.database import SessionLocal
from app.data.price_fetcher import fetch_price_history
from app.models import Stock, PriceHistory


db = SessionLocal()
stocks = db.query(Stock).all()

for stock in stocks:
    print(f'Fetching {stock.ticker}...')
    data = fetch_price_history(stock.ticker)
    if data is not None:
        for row in data:
            exists = db.query(PriceHistory).filter(
                PriceHistory.stock_id == stock.id,
                PriceHistory.date == row['price_date'],
            ).first()
            if exists:
                continue

            ph = PriceHistory(
                stock_id=stock.id,
                ticker=stock.ticker,
                date=row['price_date'],
                open=row.get('open'),
                high=row.get('high'),
                low=row.get('low'),
                close=row.get('close_price'),
                volume=row.get('volume')
            )
            db.add(ph)
    db.commit()

print('✅ Prices populated')
db.close()
