"""Pydantic schemas for IPO Tracker."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class IssuerBase(BaseModel):
    """Base issuer schema."""
    company_name: str
    cik: Optional[str] = None
    ticker: Optional[str] = None
    exchange: Optional[str] = None
    country: str = "US"
    is_foreign_issuer: bool = False
    status: str = "candidate"


class IssuerCreate(IssuerBase):
    """Schema for creating an issuer."""
    pass


class IssuerUpdate(BaseModel):
    """Schema for updating an issuer."""
    company_name: Optional[str] = None
    cik: Optional[str] = None
    ticker: Optional[str] = None
    exchange: Optional[str] = None
    country: Optional[str] = None
    is_foreign_issuer: Optional[bool] = None
    status: Optional[str] = None


class Issuer(IssuerBase):
    """Schema for issuer response."""
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True