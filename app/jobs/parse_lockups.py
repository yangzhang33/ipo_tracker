"""Job: parse lock-up data from SEC filing HTML.

For each issuer, selects the best available filing, downloads its HTML,
converts to plain text, runs the lock-up parsers, and writes results
to the ``lockups`` table.

Date calibration
----------------
- lockup_start_date = filing_date of the best filing
  (424B4 filing_date is the standard anchor; other form types use their
  own filing_date as a conservative fallback — matches the spec).
- lockup_end_date = lockup_start_date + lockup_days (calendar days).

Usage
-----
::

    python -m app.jobs.parse_lockups
    python -m app.jobs.parse_lockups --force
"""

from __future__ import annotations

from ..collectors.sec import download_filing_html
from ..db import SessionLocal
from ..models import Filing, Issuer, Lockup
from ..parsers.filing_locator import select_best_filing
from ..parsers.lockup_parser import (
    determine_confidence,
    detect_staged_unlock,
    extract_lockup_days,
    extract_unlock_notes,
)
from ..utils.dates import add_days, today_str
from ..utils.logging import get_logger
from ..utils.text import strip_html_to_text

logger = get_logger(__name__)


def parse_lockups(force: bool = False) -> dict:
    """
    Parse lock-up data for all issuers that have at least one filing.

    Selects the best filing per issuer (via ``select_best_filing``),
    downloads its HTML, strips to plain text, runs the lock-up parsers,
    and upserts into the ``lockups`` table.

    Skips issuers whose best filing has ``is_parsed=1`` and the lockup
    table already has a row for that filing, unless ``force=True``.

    Each issuer is processed in an independent try/except so a failure
    for one company does not abort others.

    Args:
        force: Re-parse filings even if a lockup record already exists
               (default False).

    Returns:
        dict with keys: issuer_count, parsed, skipped, failed.
    """
    stats = {"issuer_count": 0, "parsed": 0, "skipped": 0, "failed": 0}

    db = SessionLocal()
    try:
        issuers: list[Issuer] = db.query(Issuer).order_by(Issuer.id).all()
        stats["issuer_count"] = len(issuers)
        logger.info("parse_lockups: %d issuers", len(issuers))

        for issuer in issuers:
            try:
                result = _parse_one_issuer(db, issuer, force=force)
                if result == "parsed":
                    stats["parsed"] += 1
                else:
                    stats["skipped"] += 1
            except Exception as exc:
                db.rollback()
                logger.error(
                    "Failed to parse lockup for %s: %s",
                    issuer.company_name, exc,
                )
                stats["failed"] += 1

    finally:
        db.close()

    logger.info(
        "parse_lockups done — parsed=%d skipped=%d failed=%d",
        stats["parsed"], stats["skipped"], stats["failed"],
    )
    return stats


# ── Per-issuer logic ──────────────────────────────────────────────────────────

def _parse_one_issuer(db, issuer: Issuer, force: bool) -> str:
    """
    Parse lock-up data for one issuer.

    Returns "parsed" or "skipped".  Commits to DB on success.
    """
    filings: list[Filing] = (
        db.query(Filing)
        .filter(Filing.issuer_id == issuer.id)
        .all()
    )
    if not filings:
        return "skipped"

    best: Filing | None = select_best_filing(filings)
    if best is None or not best.primary_doc_url:
        return "skipped"

    # Skip if lockup record already exists for this filing (unless force)
    existing: Lockup | None = (
        db.query(Lockup)
        .filter(Lockup.issuer_id == issuer.id, Lockup.filing_id == best.id)
        .first()
    )
    if existing and not force:
        logger.debug(
            "Lockup already parsed: %s (%s)", issuer.company_name, best.form_type
        )
        return "skipped"

    # ── Download and convert ──────────────────────────────────────────────────
    html = download_filing_html(best.primary_doc_url, use_cache=True)
    if not html:
        return "skipped"

    text = strip_html_to_text(html)

    # ── Extract lock-up fields ────────────────────────────────────────────────
    lockup_days    = extract_lockup_days(text)
    is_staged      = detect_staged_unlock(text)
    unlock_notes   = extract_unlock_notes(text)
    confidence     = determine_confidence(text, lockup_days, is_staged)

    # ── Date calculations ─────────────────────────────────────────────────────
    # lockup_start_date = filing_date of best filing (424B4 → actual pricing date;
    # other form types → conservative proxy).
    lockup_start_date: str | None = best.filing_date  # already ISO YYYY-MM-DD
    lockup_end_date: str | None = None
    if lockup_start_date and lockup_days is not None:
        lockup_end_date = add_days(lockup_start_date, lockup_days)

    now = today_str()

    # ── Upsert lockup ─────────────────────────────────────────────────────────
    if existing:
        existing.lockup_days        = lockup_days
        existing.lockup_start_date  = lockup_start_date
        existing.lockup_end_date    = lockup_end_date
        existing.is_staged_unlock   = is_staged
        existing.unlock_notes       = unlock_notes
        existing.confidence         = confidence
        existing.parsed_at          = now
    else:
        lockup_row = Lockup(
            issuer_id          = issuer.id,
            filing_id          = best.id,
            lockup_days        = lockup_days,
            lockup_start_date  = lockup_start_date,
            lockup_end_date    = lockup_end_date,
            is_staged_unlock   = is_staged,
            unlock_notes       = unlock_notes,
            unlock_shares_estimate = None,   # v1: leave empty
            confidence         = confidence,
            parsed_at          = now,
        )
        db.add(lockup_row)

    db.commit()

    logger.info(
        "Lockup parsed — %s [%s]: days=%s  start=%s  end=%s  staged=%s  conf=%s",
        issuer.company_name, best.form_type,
        lockup_days, lockup_start_date, lockup_end_date,
        is_staged, confidence,
    )
    return "parsed"


# ── CLI entry point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    force = "--force" in sys.argv
    result = parse_lockups(force=force)
    print(
        f"\nDone — issuers={result['issuer_count']}  "
        f"parsed={result['parsed']}  "
        f"skipped={result['skipped']}  "
        f"failed={result['failed']}"
    )
