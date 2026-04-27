from sqlalchemy import (
    BigInteger, Column, DateTime, Float, ForeignKey,
    Integer, String, UniqueConstraint,
)
from sqlalchemy.sql import func
from app.database import Base


class PriceHistory(Base):
    __tablename__ = "price_history"
    __table_args__ = (
        UniqueConstraint("stock_id", "date", name="uq_price_history_stock_date"),
    )

    id         = Column(Integer, primary_key=True)
    stock_id   = Column(Integer, ForeignKey("stocks.id"), nullable=False, index=True)
    ticker     = Column(String(10), nullable=False, index=True)
    date       = Column(DateTime, nullable=False)
    open       = Column(Float)
    high       = Column(Float)
    low        = Column(Float)
    close      = Column(Float)
    volume     = Column(BigInteger)
    created_at = Column(DateTime, server_default=func.now())
