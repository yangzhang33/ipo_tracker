"""Filing locator: select the best filing to parse for a given issuer.

Given a list of filings (SQLAlchemy model objects or plain dicts),
returns the single filing most suitable for data extraction according
to a fixed priority ladder.

Priority order
--------------
1. 424B4          — final prospectus, richest data
2. 424B1          — preliminary prospectus
3. S-1/A or F-1/A — latest amendment (most current pre-pricing data)
4. S-1  or F-1    — original registration statement

Within the same priority tier, the filing with the latest ``filing_date``
wins.  Ties in date are broken by insertion order (whichever appears
first in the input list).
"""

from __future__ import annotations

from typing import Any


# Priority tiers — lower index = higher priority.
# Each tier is a frozenset of form_type strings that belong to it.
_TIERS: list[frozenset[str]] = [
    frozenset({"424B4"}),
    frozenset({"424B1"}),
    frozenset({"S-1/A", "F-1/A"}),
    frozenset({"S-1",   "F-1"}),
]


def _get(filing: Any, field: str):
    """Read ``field`` from a filing whether it is a dict or an ORM object."""
    if isinstance(filing, dict):
        return filing.get(field)
    return getattr(filing, field, None)


def select_best_filing(filings: list) -> Any | None:
    """
    Select the best filing to parse from a list of filings.

    Args:
        filings: List of Filing ORM objects or plain dicts, each having
                 at least ``form_type`` (str) and ``filing_date`` (str,
                 ISO format YYYY-MM-DD).  May be empty or contain
                 irrelevant form types — both are handled gracefully.

    Returns:
        The single best filing (same type as the input elements), or
        ``None`` if the list is empty or contains no recognised forms.
    """
    if not filings:
        return None

    for tier in _TIERS:
        candidates = [f for f in filings if _get(f, "form_type") in tier]
        if candidates:
            # Latest filing_date wins; fall back to "" so None-safe sort works
            return max(candidates, key=lambda f: _get(f, "filing_date") or "")

    return None
