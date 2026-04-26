from sqlalchemy import Column, DateTime, Float, Integer, String, func
from sqlalchemy.dialects.postgresql import ARRAY
from app.database import Base


class RegimeHistory(Base):
    __tablename__ = "regime_history"

    id = Column(Integer, primary_key=True)
    detected_at = Column(DateTime, server_default=func.now())
    regime = Column(String(20), nullable=False)
    vix = Column(Float)
    spy_3m_return = Column(Float)
    yield_curve_spread = Column(Float)
    confidence = Column(Float)
    favored_sectors = Column(ARRAY(String))
    avoided_sectors = Column(ARRAY(String))
