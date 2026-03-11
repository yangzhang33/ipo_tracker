"""SQLAlchemy models for IPO Tracker."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text

from .db import Base


class Issuer(Base):
    """Basic issuer model for initial setup."""

    __tablename__ = "issuers"

    id = Column(Integer, primary_key=True, index=True)
    company_name = Column(String(255), nullable=False)
    cik = Column(String(20), unique=True, nullable=True)
    ticker = Column(String(10), nullable=True)
    exchange = Column(String(10), nullable=True)
    country = Column(String(50), default="US")
    is_foreign_issuer = Column(Boolean, default=False)
    status = Column(String(20), default="candidate")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Issuer(id={self.id}, company_name='{self.company_name}', ticker='{self.ticker}')>"