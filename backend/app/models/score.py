from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from app.database import Base


class ScoreSnapshot(Base):
    __tablename__ = "score_snapshots"

    id = Column(Integer, primary_key=True)
    ticker = Column(String(10), nullable=False)
    scored_at = Column(DateTime, server_default=func.now())
    regime = Column(String(20))
    # Core sub-scores
    regime_score = Column(Float)
    sector_score = Column(Float)
    base_score = Column(Float)
    ceo_score = Column(Float)
    roic_wacc_score = Column(Float)
    core_total = Column(Float)
    # Catalyst sub-scores
    catalyst_intensity = Column(Float)
    catalyst_discount = Column(Float)
    catalyst_sensitivity = Column(Float)
    catalyst_window_score = Column(Float)
    catalyst_coverage = Column(Float)
    catalyst_total = Column(Float)
    catalyst_id = Column(Integer, ForeignKey("catalysts.id"))
    # Decision
    final_score = Column(Float)
    signal = Column(String(20))   # COMPRA_FUERTE|COMPRA|VIGILAR|EVITAR
    horizon = Column(String(20))  # CORTO_PLAZO|MEDIANO_PLAZO|LARGO_PLAZO
    expected_return_low = Column(Float)
    expected_return_high = Column(Float)
    probability = Column(Float)
    invalidators = Column(JSONB)
