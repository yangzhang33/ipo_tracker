"""Job: export database data to CSV reports.

Reads from the database and writes three CSV files to data/exports/:

1. upcoming_ipos.csv   — issuers with status candidate/filed/priced that
                         have had a filing in the last 60 days.
2. recent_ipos.csv     — issuers with a non-null offer_price and
                         pricing_date within the last 30 days.
3. upcoming_unlocks.csv — issuers whose lockup_end_date falls within
                          the next 30 days.

Usage
-----
::

    python -m app.jobs.export_reports
"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from ..config import settings
from ..db import SessionLocal
from ..models import Capitalization, Filing, Issuer, Lockup, Offering
from ..utils.dates import parse_date
from ..utils.logging import get_logger

logger = get_logger(__name__)

# ── Date window constants ──────────────────────────────────────────────────────

_UPCOMING_IPO_FILING_LOOKBACK_DAYS = 60
_RECENT_IPO_PRICING_LOOKBACK_DAYS  = 30
_UPCOMING_UNLOCK_LOOKAHEAD_DAYS    = 30


def export_reports() -> dict:
    """
    Export three CSV reports from the current database state.

    Writes files to ``data/exports/`` (creating the directory if needed).

    Returns:
        dict with keys:
        - ``exported_files``: list of absolute file paths written.
        - ``row_counts``:     dict mapping filename → number of data rows.
    """
    settings.EXPORT_DIR.mkdir(parents=True, exist_ok=True)

    exported_files: list[str] = []
    row_counts: dict[str, int] = {}

    db = SessionLocal()
    try:
        path, rows = _export_upcoming_ipos(db)
        exported_files.append(str(path))
        row_counts[path.name] = rows

        path, rows = _export_recent_ipos(db)
        exported_files.append(str(path))
        row_counts[path.name] = rows

        path, rows = _export_upcoming_unlocks(db)
        exported_files.append(str(path))
        row_counts[path.name] = rows

    finally:
        db.close()

    logger.info(
        "export_reports done — %s",
        "  ".join(f"{name}={cnt}" for name, cnt in row_counts.items()),
    )
    return {"exported_files": exported_files, "row_counts": row_counts}


# ── upcoming_ipos ─────────────────────────────────────────────────────────────

def _export_upcoming_ipos(db) -> tuple:
    """Build and write upcoming_ipos.csv."""
    cutoff = (date.today() - timedelta(days=_UPCOMING_IPO_FILING_LOOKBACK_DAYS)).isoformat()

    # Issuers with relevant status
    issuers: list[Issuer] = (
        db.query(Issuer)
        .filter(Issuer.status.in_(["candidate", "filed", "priced"]))
        .order_by(Issuer.company_name)
        .all()
    )

    rows = []
    for issuer in issuers:
        # Find the most recent filing within the lookback window
        recent_filing: Filing | None = (
            db.query(Filing)
            .filter(
                Filing.issuer_id == issuer.id,
                Filing.filing_date >= cutoff,
            )
            .order_by(Filing.filing_date.desc())
            .first()
        )
        if recent_filing is None:
            continue  # No filing in the last 60 days → skip

        # Best offering row (most recently parsed)
        offering: Offering | None = (
            db.query(Offering)
            .filter(Offering.issuer_id == issuer.id)
            .order_by(Offering.parsed_at.desc())
            .first()
        )

        rows.append({
            "company_name":         issuer.company_name,
            "cik":                  issuer.cik,
            "ticker":               issuer.ticker,
            "exchange":             issuer.exchange,
            "filing_status":        issuer.status,
            "price_range_low":      offering.price_range_low      if offering else None,
            "price_range_high":     offering.price_range_high     if offering else None,
            "offer_price":          offering.offer_price          if offering else None,
            "pricing_date":         offering.pricing_date         if offering else None,
            "expected_trade_date":  offering.expected_trade_date  if offering else None,
            "shares_offered_total": offering.shares_offered_total if offering else None,
            "shares_primary":       offering.shares_primary       if offering else None,
            "shares_secondary":     offering.shares_secondary     if offering else None,
            "greenshoe_shares":     offering.greenshoe_shares     if offering else None,
            "bookrunners":          offering.bookrunners          if offering else None,
            "latest_prospectus_url": recent_filing.primary_doc_url,
        })

    df = pd.DataFrame(rows, columns=[
        "company_name", "cik", "ticker", "exchange", "filing_status",
        "price_range_low", "price_range_high", "offer_price",
        "pricing_date", "expected_trade_date", "shares_offered_total",
        "shares_primary", "shares_secondary", "greenshoe_shares",
        "bookrunners", "latest_prospectus_url",
    ])

    out_path = settings.EXPORT_DIR / "upcoming_ipos.csv"
    df.to_csv(out_path, index=False)
    logger.info("upcoming_ipos.csv — %d rows → %s", len(df), out_path)
    return out_path, len(df)


# ── recent_ipos ───────────────────────────────────────────────────────────────

def _export_recent_ipos(db) -> tuple:
    """Build and write recent_ipos.csv."""
    cutoff = (date.today() - timedelta(days=_RECENT_IPO_PRICING_LOOKBACK_DAYS)).isoformat()

    # Offerings with non-null offer_price and recent pricing_date
    offerings: list[Offering] = (
        db.query(Offering)
        .filter(
            Offering.offer_price.isnot(None),
            Offering.pricing_date >= cutoff,
        )
        .order_by(Offering.pricing_date.desc())
        .all()
    )

    rows = []
    for offering in offerings:
        issuer: Issuer = offering.issuer

        cap: Capitalization | None = (
            db.query(Capitalization)
            .filter(Capitalization.issuer_id == issuer.id)
            .order_by(Capitalization.parsed_at.desc())
            .first()
        )

        lockup: Lockup | None = (
            db.query(Lockup)
            .filter(Lockup.issuer_id == issuer.id)
            .order_by(Lockup.parsed_at.desc())
            .first()
        )

        rows.append({
            "company_name":               issuer.company_name,
            "ticker":                     issuer.ticker,
            "exchange":                   issuer.exchange,
            "offer_price":                offering.offer_price,
            "pricing_date":               offering.pricing_date,
            "trade_date":                 offering.expected_trade_date,
            "shares_offered_total":       offering.shares_offered_total,
            "shares_outstanding_post_ipo": cap.shares_outstanding_post_ipo if cap else None,
            "free_float_at_ipo":          cap.free_float_at_ipo           if cap else None,
            "float_ratio":                cap.float_ratio                  if cap else None,
            "lockup_days":                lockup.lockup_days               if lockup else None,
            "lockup_end_date":            lockup.lockup_end_date           if lockup else None,
        })

    df = pd.DataFrame(rows, columns=[
        "company_name", "ticker", "exchange", "offer_price", "pricing_date",
        "trade_date", "shares_offered_total", "shares_outstanding_post_ipo",
        "free_float_at_ipo", "float_ratio", "lockup_days", "lockup_end_date",
    ])

    out_path = settings.EXPORT_DIR / "recent_ipos.csv"
    df.to_csv(out_path, index=False)
    logger.info("recent_ipos.csv — %d rows → %s", len(df), out_path)
    return out_path, len(df)


# ── upcoming_unlocks ──────────────────────────────────────────────────────────

def _export_upcoming_unlocks(db) -> tuple:
    """Build and write upcoming_unlocks.csv."""
    today = date.today()
    lookahead = (today + timedelta(days=_UPCOMING_UNLOCK_LOOKAHEAD_DAYS)).isoformat()
    today_str = today.isoformat()

    # Lockups whose end date is within the next 30 days
    lockups: list[Lockup] = (
        db.query(Lockup)
        .filter(
            Lockup.lockup_end_date.isnot(None),
            Lockup.lockup_end_date >= today_str,
            Lockup.lockup_end_date <= lookahead,
        )
        .order_by(Lockup.lockup_end_date)
        .all()
    )

    rows = []
    for lockup in lockups:
        issuer: Issuer = lockup.issuer

        offering: Offering | None = (
            db.query(Offering)
            .filter(Offering.issuer_id == issuer.id)
            .order_by(Offering.parsed_at.desc())
            .first()
        )

        # Source filing URL from the lockup's associated filing
        source_url: str | None = None
        if lockup.filing_id:
            filing: Filing | None = db.query(Filing).filter(Filing.id == lockup.filing_id).first()
            if filing:
                source_url = filing.primary_doc_url

        rows.append({
            "company_name":          issuer.company_name,
            "ticker":                issuer.ticker,
            "offer_price":           offering.offer_price          if offering else None,
            "trade_date":            offering.expected_trade_date  if offering else None,
            "lockup_days":           lockup.lockup_days,
            "lockup_end_date":       lockup.lockup_end_date,
            "is_staged_unlock":      lockup.is_staged_unlock,
            "unlock_notes":          lockup.unlock_notes,
            "unlock_shares_estimate": lockup.unlock_shares_estimate,
            "source_filing_url":     source_url,
        })

    df = pd.DataFrame(rows, columns=[
        "company_name", "ticker", "offer_price", "trade_date",
        "lockup_days", "lockup_end_date", "is_staged_unlock",
        "unlock_notes", "unlock_shares_estimate", "source_filing_url",
    ])

    out_path = settings.EXPORT_DIR / "upcoming_unlocks.csv"
    df.to_csv(out_path, index=False)
    logger.info("upcoming_unlocks.csv — %d rows → %s", len(df), out_path)
    return out_path, len(df)


# ── CLI entry point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    result = export_reports()
    print("\nDone — exported files:")
    for f in result["exported_files"]:
        name = f.split("/")[-1]
        print(f"  {f}  ({result['row_counts'][name]} rows)")
