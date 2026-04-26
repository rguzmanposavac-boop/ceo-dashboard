from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY
from app.database import Base


class Catalyst(Base):
    __tablename__ = "catalysts"

    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    catalyst_type = Column(String(50), nullable=False)
    description = Column(Text)
    affected_sectors = Column(ARRAY(String))
    affected_tickers = Column(ARRAY(String))
    intensity_score = Column(Float)
    expected_window = Column(String(20))  # INMEDIATO|PROXIMO|FUTURO|INCIERTO
    is_active = Column(Boolean, default=True)
    detected_at = Column(DateTime, server_default=func.now())
