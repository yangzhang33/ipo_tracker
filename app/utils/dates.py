"""Date parsing and arithmetic utilities."""

from datetime import date, timedelta
from typing import Optional

from dateutil import parser as dateutil_parser


def parse_date(value: str) -> Optional[date]:
    """
    Parse a date string into a date object.

    Accepts a wide variety of formats (ISO 8601, US long form, etc.)
    via python-dateutil. Returns None on any parse failure rather than
    raising an exception.

    Args:
        value: Date string, e.g. "2024-03-15", "March 15, 2024",
               "15-Mar-2024".

    Returns:
        A date object, or None if parsing fails.
    """
    if not value or not value.strip():
        return None
    try:
        return dateutil_parser.parse(value.strip(), fuzzy=False).date()
    except (ValueError, OverflowError, TypeError):
        return None


def add_days(value: str, days: int) -> Optional[str]:
    """
    Add a number of calendar days to a date string.

    Args:
        value: Date string parseable by parse_date.
        days: Number of days to add (may be negative).

    Returns:
        ISO-formatted date string (YYYY-MM-DD), or None if value cannot
        be parsed.
    """
    parsed = parse_date(value)
    if parsed is None:
        return None
    return (parsed + timedelta(days=days)).isoformat()


def today_str() -> str:
    """
    Return today's date as an ISO-formatted string (YYYY-MM-DD).

    Returns:
        e.g. "2026-03-11"
    """
    return date.today().isoformat()
