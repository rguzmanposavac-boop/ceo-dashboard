from sqlalchemy import Boolean, Column, Date, Float, Integer, String, BigInteger
from sqlalchemy.orm import relationship
from app.database import Base


class Stock(Base):
    __tablename__ = "stocks"

    id = Column(Integer, primary_key=True)
    ticker = Column(String(10), unique=True, nullable=False)
    company = Column(String(150), nullable=False)
    sector = Column(String(80), nullable=False)
    sub_sector = Column(String(80))
    market_cap_category = Column(String(20))  # large|mid|small
    exchange = Column(String(10))              # NYSE|NASDAQ
    universe_level = Column(Integer, default=1)  # 1=core, 2=opportunity
    is_active = Column(Boolean, default=True)

    ceo = relationship("CEO", back_populates="stock", uselist=False)


class PriceCache(Base):
    __tablename__ = "price_cache"

    id = Column(Integer, primary_key=True)
    ticker = Column(String(10), nullable=False)
    price_date = Column(Date, nullable=False)
    close_price = Column(Float)
    volume = Column(BigInteger)
    change_pct = Column(Float)
