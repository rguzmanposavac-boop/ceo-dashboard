from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.sql import func
from app.database import Base


class InvalidatorLog(Base):
    __tablename__ = "invalidator_logs"

    id = Column(Integer, primary_key=True)
    ticker = Column(String(10), nullable=False, index=True)
    invalidator_key = Column(String(50), nullable=False)
    description = Column(String(500), nullable=False)
    action_recommendation = Column(String(500), nullable=False)
    triggered_at = Column(DateTime, nullable=False)
    active = Column(Boolean, nullable=False, server_default="true")
    created_at = Column(DateTime, server_default=func.now())
