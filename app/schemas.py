"""Pydantic schemas for IPO Tracker."""

from typing import Optional
from pydantic import BaseModel


# ─── Issuer ──────────────────────────────────────────────────────────────────

class IssuerCreate(BaseModel):
    """Schema for creating an issuer."""
    company_name: str
    cik: Optional[str] = None
    ticker: Optional[str] = None
    exchange: Optional[str] = None
    country: Optional[str] = None
    is_foreign_issuer: bool = False
    status: str = "candidate"
    source_url: Optional[str] = None


class IssuerRead(IssuerCreate):
    """Schema for reading an issuer."""
    id: int
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True


# ─── Filing ──────────────────────────────────────────────────────────────────

class FilingCreate(BaseModel):
    """Schema for creating a filing."""
    issuer_id: int
    accession_no: str
    form_type: str
    filing_date: str
    primary_doc_url: Optional[str] = None
    filing_index_url: Optional[str] = None
    is_parsed: int = 0


class FilingRead(FilingCreate):
    """Schema for reading a filing."""
    id: int
    created_at: Optional[str] = None

    class Config:
        from_attributes = True


# ─── Offering ────────────────────────────────────────────────────────────────

class OfferingCreate(BaseModel):
    """Schema for creating an offering record."""
    issuer_id: int
    filing_id: Optional[int] = None
    source_form_type: Optional[str] = None
    price_range_low: Optional[float] = None
    price_range_high: Optional[float] = None
    offer_price: Optional[float] = None
    pricing_date: Optional[str] = None
    expected_trade_date: Optional[str] = None
    shares_offered_total: Optional[float] = None
    shares_primary: Optional[float] = None
    shares_secondary: Optional[float] = None
    greenshoe_shares: Optional[float] = None
    gross_proceeds: Optional[float] = None
    exchange: Optional[str] = None
    bookrunners: Optional[str] = None


class OfferingRead(OfferingCreate):
    """Schema for reading an offering record."""
    id: int
    parsed_at: Optional[str] = None

    class Config:
        from_attributes = True


# ─── Capitalization ──────────────────────────────────────────────────────────

class CapitalizationCreate(BaseModel):
    """Schema for creating a capitalization record."""
    issuer_id: int
    filing_id: Optional[int] = None
    shares_outstanding_pre_ipo: Optional[float] = None
    shares_outstanding_post_ipo: Optional[float] = None
    free_float_at_ipo: Optional[float] = None
    float_ratio: Optional[float] = None
    fully_diluted_shares: Optional[float] = None


class CapitalizationRead(CapitalizationCreate):
    """Schema for reading a capitalization record."""
    id: int
    parsed_at: Optional[str] = None

    class Config:
        from_attributes = True


# ─── Lockup ──────────────────────────────────────────────────────────────────

class LockupCreate(BaseModel):
    """Schema for creating a lockup record."""
    issuer_id: int
    filing_id: Optional[int] = None
    lockup_days: Optional[int] = None
    lockup_start_date: Optional[str] = None
    lockup_end_date: Optional[str] = None
    is_staged_unlock: bool = False
    unlock_notes: Optional[str] = None
    unlock_shares_estimate: Optional[float] = None
    confidence: Optional[str] = None  # high | medium | low


class LockupRead(LockupCreate):
    """Schema for reading a lockup record."""
    id: int
    parsed_at: Optional[str] = None

    class Config:
        from_attributes = True
