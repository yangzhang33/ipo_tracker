"""Job: sync SEC filings into the filings table.

For each issuer that already has a CIK, fetches the SEC submissions JSON,
extracts target-form filings, and writes them to the ``filings`` table.
Also updates ``issuer.status`` based on the forms found.

This job does NOT:
- Parse filing HTML content
- Write offerings / capitalization / lockups
- Auto-match CIKs (CIK must be pre-populated manually)

Prerequisite
------------
Issuers must have ``cik`` set before this job is useful.  To look up a
CIK by company name or ticker, call ``search_edgar_company()`` from
``app.collectors.sec`` and then update the issuer row manually::

    from app.collectors.sec import search_edgar_company
    results = search_edgar_company("Reddit")
    # → [{"cik": "0001713445", "name": "Reddit, Inc.", "ticker": "RDDT", ...}]

Usage
-----
::

    python -m app.jobs.sync_sec_filings
"""

from __future__ import annotations

from ..collectors.sec import extract_recent_target_forms, get_submissions_json
from ..db import SessionLocal
from ..models import Filing, Issuer
from ..utils.dates import today_str
from ..utils.logging import get_logger

logger = get_logger(__name__)

# ── Status derivation ─────────────────────────────────────────────────────────

# Status values whose rank is higher than "filed"; we never downgrade these
# automatically (they require price data, which comes in a later stage).
_NO_DOWNGRADE = {"priced", "trading"}

# Forms that indicate at least a filed/active state
_FILING_FORMS = {"S-1", "S-1/A", "F-1", "F-1/A", "424B4", "424B1"}


def _derive_status(current: str, form_types: set[str]) -> str:
    """
    Compute the new issuer status from the set of form types found.

    Rules (in priority order):
    1. Any RW (registration withdrawal) → "withdrawn", always.
    2. current is already "priced" or "trading" → keep as-is (no downgrade).
    3. Any S-1 / S-1/A / F-1 / F-1/A / 424B4 / 424B1 → upgrade to "filed"
       if currently "candidate".
    4. No relevant forms found → keep current status.

    Note: upgrading "filed" → "priced" requires offer_price, which is
    handled by a later parsing stage.
    """
    if "RW" in form_types:
        return "withdrawn"
    if current in _NO_DOWNGRADE:
        return current
    if form_types & _FILING_FORMS:
        # Only upgrade; never downgrade an already-withdrawn issuer this way
        if current not in ("withdrawn",):
            return "filed"
    return current


# ── Main job ──────────────────────────────────────────────────────────────────

def sync_sec_filings(use_cache: bool = True) -> dict:
    """
    Sync SEC filings for all issuers that have a CIK.

    For each such issuer:
    1. Fetches the SEC submissions JSON (CIK-based).
    2. Extracts target-form filings (S-1, S-1/A, F-1, F-1/A, 424B4, 424B1, RW).
    3. Inserts new filings into the ``filings`` table; skips duplicates.
    4. Updates ``issuer.status`` based on the forms found.

    Each issuer is processed in its own try/except so a failure for one
    company does not abort the rest.

    Args:
        use_cache: Whether to use the HTTP cache when fetching submissions
                   JSON (default True — avoids hammering SEC on re-runs).

    Returns:
        dict with keys:
        - ``issuer_count``      — number of issuers with a CIK
        - ``filings_inserted``  — new filing rows written
        - ``filings_skipped``   — filings already present in the DB
        - ``filings_failed``    — issuers whose processing raised an error
    """
    stats = {
        "issuer_count":     0,
        "filings_inserted": 0,
        "filings_skipped":  0,
        "filings_failed":   0,
    }

    db = SessionLocal()
    try:
        issuers: list[Issuer] = (
            db.query(Issuer)
            .filter(Issuer.cik.isnot(None))
            .order_by(Issuer.id)
            .all()
        )
        stats["issuer_count"] = len(issuers)
        logger.info("sync_sec_filings: %d issuers with CIK", len(issuers))

        now = today_str()

        for issuer in issuers:
            try:
                _sync_one_issuer(db, issuer, now, stats, use_cache=use_cache)
            except Exception as exc:
                db.rollback()
                logger.error(
                    "Failed to sync CIK %s (%s): %s",
                    issuer.cik, issuer.company_name, exc,
                )
                stats["filings_failed"] += 1

    finally:
        db.close()

    logger.info(
        "sync_sec_filings done — inserted=%d skipped=%d failed=%d",
        stats["filings_inserted"], stats["filings_skipped"], stats["filings_failed"],
    )
    return stats


# ── Per-issuer helper ─────────────────────────────────────────────────────────

def _sync_one_issuer(
    db,
    issuer: Issuer,
    now: str,
    stats: dict,
    use_cache: bool,
) -> None:
    """Fetch, filter and persist filings for a single issuer. Commits on success."""

    submissions = get_submissions_json(issuer.cik, use_cache=use_cache)
    forms = extract_recent_target_forms(submissions)

    if not forms:
        logger.debug("No target forms for CIK %s (%s)", issuer.cik, issuer.company_name)
        return

    found_form_types: set[str] = set()

    for form in forms:
        accession_no = form["accession_no"]
        form_type    = form["form_type"]

        if not accession_no or not form_type:
            continue

        found_form_types.add(form_type)

        # Skip if already in DB (unique constraint: issuer_id + accession_no + form_type)
        exists = (
            db.query(Filing.id)
            .filter(
                Filing.issuer_id   == issuer.id,
                Filing.accession_no == accession_no,
                Filing.form_type   == form_type,
            )
            .first()
        )
        if exists:
            stats["filings_skipped"] += 1
            continue

        filing = Filing(
            issuer_id        = issuer.id,
            accession_no     = accession_no,
            form_type        = form_type,
            filing_date      = form["filing_date"] or "",
            primary_doc_url  = form["primary_doc_url"],
            filing_index_url = form["filing_index_url"],
            is_parsed        = 0,
            created_at       = now,
        )
        db.add(filing)
        stats["filings_inserted"] += 1

    # Derive and (if changed) update issuer status
    new_status = _derive_status(issuer.status or "candidate", found_form_types)
    if new_status != issuer.status:
        logger.info(
            "Issuer %s status: %s → %s", issuer.company_name, issuer.status, new_status
        )
        issuer.status     = new_status
        issuer.updated_at = now

    db.commit()


# ── CLI entry point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    result = sync_sec_filings()
    print(
        f"\nDone — issuers={result['issuer_count']}  "
        f"inserted={result['filings_inserted']}  "
        f"skipped={result['filings_skipped']}  "
        f"failed={result['filings_failed']}"
    )
