"""Job: parse offering and capitalization data from SEC filing HTML.

For each issuer, selects the best available filing, downloads its HTML,
converts to plain text, runs the prospectus parsers, and writes results
to the ``offerings`` and ``capitalization`` tables.

This job does NOT parse lock-up data (later stage).

Usage
-----
::

    python -m app.jobs.parse_offering_data
"""

from __future__ import annotations

from ..collectors.sec import download_filing_html
from ..db import SessionLocal
from ..models import Capitalization, Filing, Issuer, Offering
from ..parsers.capitalization_parser import (
    extract_fully_diluted_shares,
    extract_shares_outstanding_post_ipo,
    extract_shares_outstanding_pre_ipo,
)
from ..parsers.filing_locator import select_best_filing
from ..parsers.prospectus_parser import (
    extract_bookrunners,
    extract_greenshoe_shares,
    extract_offer_price,
    extract_price_range,
    extract_shares_offered_total,
    extract_shares_primary_secondary,
)
from ..utils.dates import today_str
from ..utils.logging import get_logger
from ..utils.text import strip_html_to_text

logger = get_logger(__name__)


def parse_offering_data(force: bool = False) -> dict:
    """
    Parse offering and capitalization data for all issuers.

    Selects the best filing per issuer (via ``select_best_filing``),
    downloads its HTML, strips to plain text, runs parsers, and
    upserts into the ``offerings`` and ``capitalization`` tables.

    Skips issuers whose best filing has already been parsed
    (``is_parsed=1``) unless ``force=True``.

    Each issuer is processed in an independent try/except so a failure
    for one company does not abort others.

    Args:
        force: Re-parse filings already marked ``is_parsed=1``
               (default False).

    Returns:
        dict with keys: issuer_count, parsed, skipped, failed.
    """
    stats = {"issuer_count": 0, "parsed": 0, "skipped": 0, "failed": 0}

    db = SessionLocal()
    try:
        issuers: list[Issuer] = db.query(Issuer).order_by(Issuer.id).all()
        stats["issuer_count"] = len(issuers)
        logger.info("parse_offering_data: %d issuers", len(issuers))

        for issuer in issuers:
            try:
                result = _parse_one_issuer(db, issuer, force=force)
                if result == "parsed":
                    stats["parsed"] += 1
                else:
                    stats["skipped"] += 1
            except Exception as exc:
                db.rollback()
                logger.error("Failed to parse issuer %s: %s", issuer.company_name, exc)
                stats["failed"] += 1

    finally:
        db.close()

    logger.info(
        "parse_offering_data done — parsed=%d skipped=%d failed=%d",
        stats["parsed"], stats["skipped"], stats["failed"],
    )
    return stats


# ── Per-issuer logic ──────────────────────────────────────────────────────────

def _parse_one_issuer(db, issuer: Issuer, force: bool) -> str:
    """
    Parse one issuer.  Returns "parsed" or "skipped".
    Commits to DB on success.
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

    if best.is_parsed and not force:
        logger.debug("Already parsed: %s (%s)", issuer.company_name, best.form_type)
        return "skipped"

    # ── Download and convert ──────────────────────────────────────────────────
    html = download_filing_html(best.primary_doc_url, use_cache=True)
    if not html:
        return "skipped"

    text = strip_html_to_text(html)

    # ── Extract fields ────────────────────────────────────────────────────────
    offer_price         = extract_offer_price(text)
    price_low, price_high = extract_price_range(text)
    shares_total        = extract_shares_offered_total(text)
    shares_primary, shares_secondary = extract_shares_primary_secondary(text)
    greenshoe           = extract_greenshoe_shares(text)
    bookrunners         = extract_bookrunners(text)

    shares_post   = extract_shares_outstanding_post_ipo(text)
    shares_pre    = extract_shares_outstanding_pre_ipo(text)
    fully_diluted = extract_fully_diluted_shares(text)

    # ── Derive computed values ────────────────────────────────────────────────
    # Prefer primary + secondary sum (most reliable), fall back to direct extract
    if shares_primary and shares_secondary:
        shares_total = shares_primary + shares_secondary
    elif shares_total is None:
        shares_total = shares_primary or shares_secondary  # best single-source fallback

    gross_proceeds: float | None = None
    if offer_price and shares_total:
        gross_proceeds = offer_price * shares_total

    float_ratio: float | None = None
    if shares_total and shares_post and shares_post > 0:
        float_ratio = shares_total / shares_post

    now = today_str()

    # ── Upsert offering ───────────────────────────────────────────────────────
    offering: Offering | None = (
        db.query(Offering)
        .filter(Offering.issuer_id == issuer.id, Offering.filing_id == best.id)
        .first()
    )
    if offering:
        # Always overwrite with fresh parse results; parsed data from the
        # best filing is always authoritative.  None values are left as-is.
        _set_if_not_none(offering, "source_form_type",   best.form_type)
        _set_if_not_none(offering, "offer_price",        offer_price)
        _set_if_not_none(offering, "price_range_low",    price_low)
        _set_if_not_none(offering, "price_range_high",   price_high)
        _set_if_not_none(offering, "shares_offered_total", shares_total)
        _set_if_not_none(offering, "shares_primary",     shares_primary)
        _set_if_not_none(offering, "shares_secondary",   shares_secondary)
        _set_if_not_none(offering, "greenshoe_shares",   greenshoe)
        _set_if_not_none(offering, "gross_proceeds",     gross_proceeds)
        _set_if_not_none(offering, "bookrunners",        bookrunners)
        _set_if_not_none(offering, "exchange",           issuer.exchange)
        offering.parsed_at = now
    else:
        offering = Offering(
            issuer_id          = issuer.id,
            filing_id          = best.id,
            source_form_type   = best.form_type,
            offer_price        = offer_price,
            price_range_low    = price_low,
            price_range_high   = price_high,
            shares_offered_total = shares_total,
            shares_primary     = shares_primary,
            shares_secondary   = shares_secondary,
            greenshoe_shares   = greenshoe,
            gross_proceeds     = gross_proceeds,
            bookrunners        = bookrunners,
            exchange           = issuer.exchange,
            parsed_at          = now,
        )
        db.add(offering)

    # ── Upsert capitalization ─────────────────────────────────────────────────
    cap: Capitalization | None = (
        db.query(Capitalization)
        .filter(
            Capitalization.issuer_id == issuer.id,
            Capitalization.filing_id == best.id,
        )
        .first()
    )
    if cap:
        _set_if_not_none(cap, "shares_outstanding_post_ipo", shares_post)
        _set_if_not_none(cap, "shares_outstanding_pre_ipo",  shares_pre)
        _set_if_not_none(cap, "fully_diluted_shares",        fully_diluted)
        _set_if_not_none(cap, "free_float_at_ipo",           shares_total)
        _set_if_not_none(cap, "float_ratio",                 float_ratio)
        cap.parsed_at = now
    else:
        cap = Capitalization(
            issuer_id                 = issuer.id,
            filing_id                 = best.id,
            shares_outstanding_post_ipo = shares_post,
            shares_outstanding_pre_ipo  = shares_pre,
            fully_diluted_shares        = fully_diluted,
            free_float_at_ipo           = shares_total,
            float_ratio                 = float_ratio,
            parsed_at                   = now,
        )
        db.add(cap)

    # Mark filing parsed
    best.is_parsed = 1

    db.commit()

    logger.info(
        "Parsed %s [%s]: offer_price=%s  shares_total=%s  post_ipo=%s  bookrunners=%s",
        issuer.company_name, best.form_type,
        offer_price, shares_total, shares_post,
        (bookrunners or "")[:60] or None,
    )
    return "parsed"


def _set_if_not_none(obj, attr: str, value) -> None:
    """Set ``attr`` on ``obj`` when ``value`` is not None (overwrites existing)."""
    if value is not None:
        setattr(obj, attr, value)


# ── CLI entry point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    force = "--force" in sys.argv
    result = parse_offering_data(force=force)
    print(
        f"\nDone — issuers={result['issuer_count']}  "
        f"parsed={result['parsed']}  "
        f"skipped={result['skipped']}  "
        f"failed={result['failed']}"
    )
