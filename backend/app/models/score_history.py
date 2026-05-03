from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.sql import func
from app.database import Base


class ScoreHistory(Base):
    __tablename__ = "score_history"

    id = Column(Integer, primary_key=True)
    snapshot_id = Column(Integer, ForeignKey("score_snapshots.id"), nullable=True)
    ticker = Column(String(10), nullable=False, index=True)
    scored_at = Column(DateTime, nullable=False)
    final_score = Column(Float)
    signal = Column(String(20))
    horizon = Column(String(20))
    core_total = Column(Float)
    catalyst_total = Column(Float)
    probability = Column(Float)
    created_at = Column(DateTime, server_default=func.now())
