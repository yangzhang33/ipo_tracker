"""SQLAlchemy models for IPO Tracker."""

from sqlalchemy import (
    Column, Integer, String, Boolean, Text, Float,
    ForeignKey, UniqueConstraint,
)
from sqlalchemy.orm import relationship

from .db import Base


class Issuer(Base):
    """
    IPO candidate company.

    status values: candidate | filed | priced | trading | withdrawn
    """

    __tablename__ = "issuers"

    id = Column(Integer, primary_key=True, index=True)
    company_name = Column(Text, nullable=False)
    cik = Column(Text, unique=True, nullable=True)
    ticker = Column(Text, nullable=True)
    exchange = Column(Text, nullable=True)
    country = Column(Text, nullable=True)
    is_foreign_issuer = Column(Boolean, default=False)
    status = Column(Text, default="candidate")
    source_url = Column(Text, nullable=True)   # page where this candidate was discovered
    created_at = Column(Text, nullable=True)
    updated_at = Column(Text, nullable=True)

    # Relationships
    filings = relationship("Filing", back_populates="issuer", cascade="all, delete-orphan")
    offerings = relationship("Offering", back_populates="issuer", cascade="all, delete-orphan")
    capitalizations = relationship("Capitalization", back_populates="issuer", cascade="all, delete-orphan")
    lockups = relationship("Lockup", back_populates="issuer", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Issuer(id={self.id}, company_name='{self.company_name}', ticker='{self.ticker}')>"


class Filing(Base):
    """
    SEC filing record for an issuer.

    form_type values of interest: S-1 | S-1/A | F-1 | F-1/A | 424B4 | 424B1 | RW
    is_parsed: 0 = not yet parsed, 1 = parsed
    """

    __tablename__ = "filings"
    __table_args__ = (
        UniqueConstraint("issuer_id", "accession_no", "form_type", name="uq_filing_issuer_accession_form"),
    )

    id = Column(Integer, primary_key=True, index=True)
    issuer_id = Column(Integer, ForeignKey("issuers.id"), nullable=False)
    accession_no = Column(Text, nullable=False)
    form_type = Column(Text, nullable=False)
    filing_date = Column(Text, nullable=False)
    primary_doc_url = Column(Text, nullable=True)
    filing_index_url = Column(Text, nullable=True)
    is_parsed = Column(Integer, default=0)
    created_at = Column(Text, nullable=True)

    # Relationships
    issuer = relationship("Issuer", back_populates="filings")
    offerings = relationship("Offering", back_populates="filing")
    capitalizations = relationship("Capitalization", back_populates="filing")
    lockups = relationship("Lockup", back_populates="filing")

    def __repr__(self) -> str:
        return f"<Filing(id={self.id}, form_type='{self.form_type}', accession_no='{self.accession_no}')>"


class Offering(Base):
    """
    IPO offering data extracted from a prospectus filing.

    bookrunners is stored as a semicolon-separated string.
    """

    __tablename__ = "offerings"

    id = Column(Integer, primary_key=True, index=True)
    issuer_id = Column(Integer, ForeignKey("issuers.id"), nullable=False)
    filing_id = Column(Integer, ForeignKey("filings.id"), nullable=True)
    source_form_type = Column(Text, nullable=True)
    price_range_low = Column(Float, nullable=True)
    price_range_high = Column(Float, nullable=True)
    offer_price = Column(Float, nullable=True)
    pricing_date = Column(Text, nullable=True)
    expected_trade_date = Column(Text, nullable=True)
    shares_offered_total = Column(Float, nullable=True)
    shares_primary = Column(Float, nullable=True)
    shares_secondary = Column(Float, nullable=True)
    greenshoe_shares = Column(Float, nullable=True)
    gross_proceeds = Column(Float, nullable=True)
    exchange = Column(Text, nullable=True)
    bookrunners = Column(Text, nullable=True)
    parsed_at = Column(Text, nullable=True)

    # Relationships
    issuer = relationship("Issuer", back_populates="offerings")
    filing = relationship("Filing", back_populates="offerings")

    def __repr__(self) -> str:
        return f"<Offering(id={self.id}, issuer_id={self.issuer_id}, offer_price={self.offer_price})>"


class Capitalization(Base):
    """
    Post-IPO capitalization data extracted from a prospectus filing.

    free_float_at_ipo = shares_offered_total (v1 definition)
    float_ratio = free_float_at_ipo / shares_outstanding_post_ipo
    """

    __tablename__ = "capitalization"

    id = Column(Integer, primary_key=True, index=True)
    issuer_id = Column(Integer, ForeignKey("issuers.id"), nullable=False)
    filing_id = Column(Integer, ForeignKey("filings.id"), nullable=True)
    shares_outstanding_pre_ipo = Column(Float, nullable=True)
    shares_outstanding_post_ipo = Column(Float, nullable=True)
    free_float_at_ipo = Column(Float, nullable=True)
    float_ratio = Column(Float, nullable=True)
    fully_diluted_shares = Column(Float, nullable=True)
    parsed_at = Column(Text, nullable=True)

    # Relationships
    issuer = relationship("Issuer", back_populates="capitalizations")
    filing = relationship("Filing", back_populates="capitalizations")

    def __repr__(self) -> str:
        return f"<Capitalization(id={self.id}, issuer_id={self.issuer_id})>"


class Lockup(Base):
    """
    Lock-up agreement data extracted from a prospectus filing.

    confidence values: high | medium | low
    lockup_start_date: 424B4 filing_date if available, else prospectus filing_date
    lockup_end_date: lockup_start_date + lockup_days
    """

    __tablename__ = "lockups"

    id = Column(Integer, primary_key=True, index=True)
    issuer_id = Column(Integer, ForeignKey("issuers.id"), nullable=False)
    filing_id = Column(Integer, ForeignKey("filings.id"), nullable=True)
    lockup_days = Column(Integer, nullable=True)
    lockup_start_date = Column(Text, nullable=True)
    lockup_end_date = Column(Text, nullable=True)
    is_staged_unlock = Column(Boolean, default=False)
    unlock_notes = Column(Text, nullable=True)
    unlock_shares_estimate = Column(Float, nullable=True)
    confidence = Column(Text, nullable=True)
    parsed_at = Column(Text, nullable=True)

    # Relationships
    issuer = relationship("Issuer", back_populates="lockups")
    filing = relationship("Filing", back_populates="lockups")

    def __repr__(self) -> str:
        return f"<Lockup(id={self.id}, issuer_id={self.issuer_id}, lockup_days={self.lockup_days})>"
