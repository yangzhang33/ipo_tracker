"""Nasdaq IPO calendar collector.

Fetches IPO candidate data from the public Nasdaq IPO calendar API.
No database access — returns plain dicts for the job layer to persist.

API endpoint
------------
https://api.nasdaq.com/api/ipo/calendar?date=YYYY-MM

Response sections
-----------------
- priced        : recently priced IPOs (rows have pricedDate)
- upcoming      : upcoming IPOs nested under upcomingTable (rows have expectedPriceDate)
- filed         : S-1/F-1 filed but not yet priced (rows have filedDate, often no exchange)
- withdrawn     : withdrawn deals — excluded
"""

from __future__ import annotations

from datetime import date

from ..utils.http import get_json
from ..utils.logging import get_logger

logger = get_logger(__name__)

_CALENDAR_URL = "https://api.nasdaq.com/api/ipo/calendar"
_SOURCE_URL   = "https://www.nasdaq.com/market-activity/ipos"

# Nasdaq's API requires a browser-like User-Agent; the SEC user-agent is rejected.
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nasdaq.com/market-activity/ipos",
}


def fetch_nasdaq_candidates(
    lookback_months: int = 1,
    lookahead_months: int = 2,
    use_cache: bool = False,
) -> list[dict]:
    """
    Fetch IPO candidates from the Nasdaq IPO calendar API.

    Fetches ``lookback_months`` months back and ``lookahead_months``
    months ahead of today, then collects rows from the *priced*,
    *upcoming*, and *filed* sections. Withdrawn deals are excluded.

    Deduplication within this function is done by ``dealID`` so the
    same deal does not appear twice even if it spans a month boundary.

    Args:
        lookback_months: Months to look back from today (default 1).
        lookahead_months: Months to look ahead from today (default 2).
        use_cache: Whether to use the HTTP cache (default False for
                   live data; set True in tests).

    Returns:
        List of candidate dicts, each containing:

        - ``company_name`` (str)
        - ``ticker``       (str | None)
        - ``exchange``     (str | None)
        - ``source_url``   (str)
        - ``raw_date_text``(str | None)  — date string from the API
    """
    today = date.today()
    months: list[str] = []
    for delta in range(-lookback_months, lookahead_months + 1):
        total = today.year * 12 + (today.month - 1) + delta
        y, m = divmod(total, 12)
        months.append(f"{y:04d}-{m + 1:02d}")

    seen_deal_ids: set[str] = set()
    candidates: list[dict] = []

    for month_str in months:
        url = f"{_CALENDAR_URL}?date={month_str}"
        try:
            data = get_json(url, headers=_HEADERS, use_cache=use_cache)
        except Exception as exc:
            logger.warning("Nasdaq: failed to fetch %s — %s", month_str, exc)
            continue

        sections = data.get("data") or {}

        # ── priced ────────────────────────────────────────────────────
        for row in (sections.get("priced") or {}).get("rows") or []:
            deal_id = row.get("dealID", "")
            if deal_id in seen_deal_ids:
                continue
            seen_deal_ids.add(deal_id)
            candidates.append(_make_candidate(
                row, date_key="pricedDate",
            ))

        # ── upcoming (nested) ─────────────────────────────────────────
        upcoming_rows = (
            (sections.get("upcoming") or {})
            .get("upcomingTable", {})
            .get("rows") or []
        )
        for row in upcoming_rows:
            deal_id = row.get("dealID", "")
            if deal_id in seen_deal_ids:
                continue
            seen_deal_ids.add(deal_id)
            candidates.append(_make_candidate(
                row, date_key="expectedPriceDate",
            ))

        # ── filed ─────────────────────────────────────────────────────
        for row in (sections.get("filed") or {}).get("rows") or []:
            deal_id = row.get("dealID", "")
            if deal_id in seen_deal_ids:
                continue
            seen_deal_ids.add(deal_id)
            candidates.append(_make_candidate(
                row, date_key="filedDate",
            ))

    logger.info("Nasdaq: collected %d candidates", len(candidates))
    return candidates


# ── Internal helpers ──────────────────────────────────────────────────────────

def _make_candidate(row: dict, date_key: str) -> dict:
    return {
        "company_name": (row.get("companyName") or "").strip(),
        "ticker":       (row.get("proposedTickerSymbol") or "").strip() or None,
        "exchange":     (row.get("proposedExchange") or "").strip() or None,
        "source_url":   _SOURCE_URL,
        "raw_date_text": row.get(date_key) or None,
    }
