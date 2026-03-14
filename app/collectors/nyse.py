"""NYSE IPO calendar collector.

Fetches IPO candidate data from the NYSE IPO Center internal API.
No database access — returns plain dicts for the job layer to persist.

API endpoint
------------
https://www.nyse.com/api/ipo-center/calendar

Response key
------------
``calendarList``: list of deal objects.

Relevant fields per row
-----------------------
- issuer_nm                   — company name
- symbol                      — ticker
- custom_group_exchange_nm    — exchange (e.g. "New York Stock Exchange")
- deal_status_desc            — "Priced" | "Filed" | "Withdrawn" | …
- deal_status_flg             — "P" | "F" | "W" | …
- price_dt                    — offer pricing date (epoch ms, may be far-future if TBA)
- init_file_dt                — initial filing date (epoch ms)
- withdrawn_postponed_dt      — very negative epoch when not withdrawn

Withdrawn deals (deal_status_flg == "W") are excluded.
"""

from __future__ import annotations

from datetime import datetime, timezone

from ..utils.http import get_json
from ..utils.logging import get_logger

logger = get_logger(__name__)

_CALENDAR_URL = "https://www.nyse.com/api/ipo-center/calendar"
_SOURCE_URL   = "https://www.nyse.com/ipo-center"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Referer": "https://www.nyse.com/ipo-center",
}

# Epoch ms values this far in the future indicate a TBA / placeholder date
_MAX_VALID_EPOCH_MS = 4_102_444_800_000   # 2100-01-01


def fetch_nyse_candidates(use_cache: bool = False) -> list[dict]:
    """
    Fetch IPO candidates from the NYSE IPO Center calendar API.

    Excludes withdrawn deals (``deal_status_flg == "W"``). All other
    deal statuses (Priced, Filed, Expected, …) are included so the job
    layer gets a full picture of the current pipeline.

    Args:
        use_cache: Whether to use the HTTP cache (default False for
                   live data; set True in tests).

    Returns:
        List of candidate dicts, each containing:

        - ``company_name`` (str)
        - ``ticker``       (str | None)
        - ``exchange``     (str | None)
        - ``source_url``   (str)
        - ``raw_date_text``(str | None)  — ISO date string or None
    """
    try:
        data = get_json(_CALENDAR_URL, headers=_HEADERS, use_cache=use_cache)
    except Exception as exc:
        logger.warning("NYSE: failed to fetch calendar — %s", exc)
        return []

    rows = data.get("calendarList") or []
    candidates: list[dict] = []

    for row in rows:
        # Skip withdrawn deals
        if row.get("deal_status_flg") == "W":
            continue

        ticker = (row.get("symbol") or "").strip() or None
        company_name = (row.get("issuer_nm") or "").strip()
        exchange = (row.get("custom_group_exchange_nm") or "").strip() or None

        # Prefer pricing date; fall back to initial filing date
        raw_date = (
            _epoch_ms_to_iso(row.get("price_dt"))
            or _epoch_ms_to_iso(row.get("init_file_dt"))
        )

        candidates.append({
            "company_name": company_name,
            "ticker":       ticker,
            "exchange":     exchange,
            "source_url":   _SOURCE_URL,
            "raw_date_text": raw_date,
        })

    logger.info("NYSE: collected %d candidates", len(candidates))
    return candidates


# ── Internal helpers ──────────────────────────────────────────────────────────

def _epoch_ms_to_iso(epoch_ms) -> str | None:
    """
    Convert an epoch-millisecond timestamp to an ISO date string (YYYY-MM-DD).

    Returns None if the value is None, negative, or unreasonably far in
    the future (indicates a TBA placeholder in the NYSE data).
    """
    if epoch_ms is None:
        return None
    try:
        epoch_ms = int(epoch_ms)
    except (TypeError, ValueError):
        return None
    if epoch_ms <= 0 or epoch_ms > _MAX_VALID_EPOCH_MS:
        return None
    dt = datetime.fromtimestamp(epoch_ms / 1000, tz=timezone.utc)
    return dt.date().isoformat()
