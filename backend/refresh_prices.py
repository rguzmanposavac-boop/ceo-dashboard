from app.data.price_fetcher import fetch_current_price
from app.database import SessionLocal
from app.models import Stock, PriceCache
from datetime import datetime

db = SessionLocal()
stocks = db.query(Stock).all()

print(f"Actualizando {len(stocks)} stocks...")

for stock in stocks:
    try:
        price = fetch_current_price(stock.ticker)
        cache = db.query(PriceCache).filter_by(stock_id=stock.id).first()
        if cache:
            cache.price = price
            cache.last_updated = datetime.now()
        else:
            # Si no existe, crear
            cache = PriceCache(stock_id=stock.id, price=price, last_updated=datetime.now())
            db.add(cache)
        db.commit()
        print(f'✅ {stock.ticker}: ${price}')
    except Exception as e:
        print(f'❌ {stock.ticker}: Error - {e}')

print('✅ Price cache updated')
db.close()