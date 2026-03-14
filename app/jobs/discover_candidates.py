"""Job: discover IPO candidate companies.

Fetches IPO candidates from Nasdaq and NYSE, deduplicates, and upserts
into the ``issuers`` table with status = "candidate".

This job does NOT fetch SEC filings or parse CIKs — that is a later stage.

Usage
-----
Run directly::

    python -m app.jobs.discover_candidates

Or import and call from a scheduler::

    from app.jobs.discover_candidates import discover_candidates
    stats = discover_candidates()
"""

from __future__ import annotations

import sys
from pathlib import Path

from ..collectors.nasdaq import fetch_nasdaq_candidates
from ..collectors.nyse import fetch_nyse_candidates
from ..db import SessionLocal
from ..models import Issuer
from ..utils.dates import today_str
from ..utils.logging import get_logger

logger = get_logger(__name__)


def discover_candidates() -> dict:
    """
    Discover IPO candidates from Nasdaq and NYSE and persist to the DB.

    Each source is fetched independently; a failure in one source does
    not abort the other or the DB write.

    Deduplication key before DB write: ``(ticker.upper(), company_name.lower())``.
    A None ticker is treated as empty string for the key only.

    DB upsert logic:
    - Look up existing row by ticker (if not None), then by company_name.
    - If found and some fields are blank, fill them in and mark as updated.
    - If not found, insert a new row with status = "candidate".

    Returns:
        dict with keys: total_fetched, inserted, updated, skipped.
    """
    stats = {"total_fetched": 0, "inserted": 0, "updated": 0, "skipped": 0}

    # ── 1. Fetch from each source independently ───────────────────────────────
    all_candidates: list[dict] = []

    try:
        nasdaq = fetch_nasdaq_candidates()
        all_candidates.extend(nasdaq)
        logger.info("Nasdaq fetched: %d", len(nasdaq))
    except Exception as exc:
        logger.error("Nasdaq collector failed (skipping): %s", exc)

    try:
        nyse = fetch_nyse_candidates()
        all_candidates.extend(nyse)
        logger.info("NYSE fetched: %d", len(nyse))
    except Exception as exc:
        logger.error("NYSE collector failed (skipping): %s", exc)

    # ── 2. In-memory deduplication ────────────────────────────────────────────
    seen: set[tuple[str, str]] = set()
    unique: list[dict] = []
    for c in all_candidates:
        ticker_key = (c.get("ticker") or "").strip().upper()
        name_key   = (c.get("company_name") or "").strip().lower()
        key = (ticker_key, name_key)
        if key in seen or not name_key:
            continue
        seen.add(key)
        unique.append(c)

    stats["total_fetched"] = len(unique)
    logger.info("Unique candidates after dedup: %d", len(unique))

    if not unique:
        return stats

    # ── 3. DB upsert ──────────────────────────────────────────────────────────
    db = SessionLocal()
    try:
        now = today_str()
        for c in unique:
            company_name = (c.get("company_name") or "").strip()
            ticker       = (c.get("ticker") or "").strip() or None
            exchange     = c.get("exchange") or None
            source_url   = c.get("source_url") or None

            # Lookup: ticker first, then company_name (case-insensitive)
            existing: Issuer | None = None
            if ticker:
                existing = (
                    db.query(Issuer)
                    .filter(Issuer.ticker == ticker)
                    .first()
                )
            if existing is None:
                existing = (
                    db.query(Issuer)
                    .filter(Issuer.company_name.ilike(company_name))
                    .first()
                )

            if existing:
                changed = False
                if not existing.exchange and exchange:
                    existing.exchange = exchange
                    changed = True
                if not existing.ticker and ticker:
                    existing.ticker = ticker
                    changed = True
                if not existing.source_url and source_url:
                    existing.source_url = source_url
                    changed = True
                if changed:
                    existing.updated_at = now
                    stats["updated"] += 1
                else:
                    stats["skipped"] += 1
            else:
                issuer = Issuer(
                    company_name=company_name,
                    ticker=ticker,
                    exchange=exchange,
                    source_url=source_url,
                    status="candidate",
                    created_at=now,
                    updated_at=now,
                )
                db.add(issuer)
                stats["inserted"] += 1

        db.commit()
        logger.info(
            "DB write complete — inserted=%d updated=%d skipped=%d",
            stats["inserted"], stats["updated"], stats["skipped"],
        )
    except Exception as exc:
        db.rollback()
        logger.error("DB write failed: %s", exc)
        raise
    finally:
        db.close()

    return stats


# ── CLI entry point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Allow running as:  python -m app.jobs.discover_candidates
    result = discover_candidates()
    print(
        f"\nDone — fetched={result['total_fetched']}  "
        f"inserted={result['inserted']}  "
        f"updated={result['updated']}  "
        f"skipped={result['skipped']}"
    )
