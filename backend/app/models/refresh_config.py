from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.sql import func
from app.database import Base


class RefreshConfig(Base):
    __tablename__ = "refresh_config"

    id = Column(Integer, primary_key=True)
    price_refresh_interval = Column(
        String(20), nullable=False, server_default="1hour"
    )  # manual|1min|5min|1hour|daily
    score_refresh_interval = Column(
        String(20), nullable=False, server_default="1hour"
    )
    catalyst_auto_review = Column(Boolean, nullable=False, server_default="true")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
