from sqlalchemy import Boolean, Column, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from app.database import Base


class CEO(Base):
    __tablename__ = "ceos"

    id = Column(Integer, primary_key=True)
    stock_id = Column(Integer, ForeignKey("stocks.id"))
    name = Column(String(150), nullable=False)
    profile = Column(String(50))
    tenure_years = Column(Float)
    ownership_pct = Column(Float)
    succession_quality = Column(String(20))  # excellent|good|poor|unknown
    is_founder = Column(Boolean, default=False)
    notes = Column(Text)

    stock = relationship("Stock", back_populates="ceo")
