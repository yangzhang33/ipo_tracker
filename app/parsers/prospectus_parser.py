"""Prospectus parser: extract offering-related fields from plain text.

All functions accept the plain-text string produced by
``strip_html_to_text()`` and return ``None`` when a confident match
cannot be found.  No guessing — if the pattern doesn't fire, return None.

Patterns were developed against 424B4 / S-1 filings from SEC EDGAR and
may need tuning for atypical prospectus layouts.
"""

from __future__ import annotations

import re
from typing import Optional


# ── Shared helpers ────────────────────────────────────────────────────────────

def _first(patterns: list[str], text: str, group: int = 1) -> Optional[str]:
    """Return the first group of the first matching pattern, or None."""
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE | re.DOTALL)
        if m:
            try:
                return m.group(group).strip()
            except IndexError:
                pass
    return None


def _parse_number(raw: str) -> Optional[float]:
    """
    Convert a raw number string to float.

    Handles: commas (``15,276,527``), decimals (``34.00``), and
    scale suffixes (``$20.2 million`` → 20_200_000.0).
    Returns None if conversion fails.
    """
    if not raw:
        return None
    raw = raw.strip()
    mult = 1.0
    lower = raw.lower()
    if "billion" in lower:
        mult = 1_000_000_000.0
        raw = re.sub(r"\s*billion", "", raw, flags=re.IGNORECASE)
    elif "million" in lower:
        mult = 1_000_000.0
        raw = re.sub(r"\s*million", "", raw, flags=re.IGNORECASE)
    raw = raw.replace(",", "").strip()
    try:
        return float(raw) * mult
    except (ValueError, TypeError):
        return None


# ── Offer price ───────────────────────────────────────────────────────────────

def extract_offer_price(text: str) -> Optional[float]:
    """
    Extract the final IPO offer price per share.

    Looks for "offering price per share ... $XX.XX" patterns typical of
    424B4 cover pages.  Also tries "price to the public" tables found
    in S-1 amendments.

    Returns:
        Offer price as a float (e.g. 34.0), or None.
    """
    raw = _first([
        # "offering price per share of our Class A common stock is $34.00"
        r"offering\s+price\s+per\s+share[^.]{0,150}\$\s*([\d,]+(?:\.\d+)?)",
        # "price to the public ... $XX.XX per share"
        r"price\s+to\s+(?:the\s+)?public[^.]{0,120}\$\s*([\d,]+(?:\.\d+)?)",
        # "at $XX.XX per share"
        r"at\s+\$\s*([\d,]+(?:\.\d+)?)\s+per\s+share",
        # "per share price of $XX.XX"
        r"per\s+share\s+(?:price\s+)?of\s+\$\s*([\d,]+(?:\.\d+)?)",
    ], text)
    return _parse_number(raw)


# ── Price range (S-1 / S-1/A) ─────────────────────────────────────────────────

def extract_price_range(text: str) -> tuple[Optional[float], Optional[float]]:
    """
    Extract the preliminary IPO price range (low, high).

    Matches patterns like "$25.00 to $31.50 per share" or
    "between $25.00 and $31.50".

    Returns:
        (price_low, price_high) tuple; each element is float or None.
        Returns (None, None) if no range is found.
    """
    for pat in [
        r"\$\s*([\d,]+(?:\.\d+)?)\s+to\s+\$\s*([\d,]+(?:\.\d+)?)\s+per\s+share",
        r"between\s+\$\s*([\d,]+(?:\.\d+)?)\s+and\s+\$\s*([\d,]+(?:\.\d+)?)",
        r"price\s+range[^.]{0,80}\$\s*([\d,]+(?:\.\d+)?)\s*[-–to]+\s*\$\s*([\d,]+(?:\.\d+)?)",
    ]:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return _parse_number(m.group(1)), _parse_number(m.group(2))
    return None, None


# ── Shares offered ────────────────────────────────────────────────────────────

def extract_shares_offered_total(text: str) -> Optional[float]:
    """
    Extract the total number of shares offered (primary + secondary).

    Tries to find an explicit aggregate first, then falls back to
    the primary-only count on the cover page.

    Returns:
        Total shares as a float, or None.
    """
    raw = _first([
        # "X shares of our Class A common stock offered by this prospectus"
        r"(\d[\d,]+)\s+shares[^.]{0,60}offered\s+by\s+this\s+prospectus",
        # "total of X shares" near this offering
        r"total\s+of\s+(\d[\d,]+)\s+shares[^.]{0,80}(?:this\s+offering|offered)",
        # "offering of X shares of ... common stock" — must not be preceded by "aggregate"
        r"(?<!aggregate\s)offering\s+of\s+(\d[\d,]+)\s+shares\s+of",
        # Cover page: "Company Inc. is offering X shares of its Class A..."
        r"[\w\s,\.]+(?:Inc\.|Corp\.|Ltd\.|LLC|L\.P\.)\s+is\s+offering\s+(\d[\d,]+)\s+shares\s+of\s+its",
        # "We are offering X shares" / "company is offering X shares"
        r"(?:we|the\s+company)\s+(?:are|is)\s+offering\s+(\d[\d,]+)\s+shares",
    ], text)
    return _parse_number(raw)


def extract_shares_primary_secondary(
    text: str,
) -> tuple[Optional[float], Optional[float]]:
    """
    Extract primary (company) and secondary (selling stockholder) share counts.

    Returns:
        (shares_primary, shares_secondary); each is float or None.
    """
    # Primary: shares offered by the company itself
    primary_raw = _first([
        # "Reddit, Inc. is offering 15,276,527 shares"
        r"[\w\s,\.]+(?:Inc\.|Corp\.|Ltd\.|LLC|L\.P\.)\s+is\s+offering\s+(\d[\d,]+)\s+shares",
        r"(?:we|the\s+company)\s+(?:are|is)\s+offering\s+(\d[\d,]+)\s+shares",
        r"(\d[\d,]+)\s+shares\s+(?:of\s+(?:our|its)\s+(?:Class\s+[A-C]\s+)?common\s+stock\s+)?(?:are\s+being\s+)?offered\s+by\s+us",
    ], text)

    # Secondary: shares offered by selling stockholders
    secondary_raw = _first([
        r"selling\s+stockholders?[^.]{0,120}(?:are\s+)?offering\s+(?:an\s+aggregate\s+of\s+)?(\d[\d,]+)\s+shares",
        r"(\d[\d,]+)\s+shares[^.]{0,80}selling\s+stockholders?\s+(?:identified|named|listed)",
        r"selling\s+shareholders?[^.]{0,120}(?:are\s+)?offering\s+(?:an\s+aggregate\s+of\s+)?(\d[\d,]+)\s+shares",
    ], text)

    return _parse_number(primary_raw), _parse_number(secondary_raw)


# ── Greenshoe (over-allotment) ────────────────────────────────────────────────

def extract_greenshoe_shares(text: str) -> Optional[float]:
    """
    Extract the number of greenshoe (over-allotment) shares.

    Matches patterns like "3,300,000 shares ... to cover over-allotment"
    or "option to purchase up to X additional shares".

    Returns:
        Greenshoe share count as a float, or None.
    """
    raw = _first([
        # "3,300,000 shares [of our Class A common stock] from us to cover over-allotment"
        r"(\d[\d,]+)\s+(?:additional\s+)?shares?[^.]{0,120}to\s+cover\s+over.?allotment",
        # "over-allotment option ... to purchase ... X additional shares"
        r"over.?allotment\s+option[^.]{0,120}(?:to\s+purchase|of|for)\s+(?:up\s+to\s+)?(\d[\d,]+)\s+(?:additional\s+)?shares",
        # "purchase up to X additional shares ... over-allotment"
        r"purchase\s+(?:up\s+to\s+)?(\d[\d,]+)\s+additional\s+shares?[^.]{0,80}over.?allotment",
        # "grant the underwriters an option to purchase X shares"
        r"grant(?:ed)?\s+the\s+underwriters?\s+(?:an?\s+)?option\s+to\s+purchase[^.]{0,60}(\d[\d,]+)\s+(?:additional\s+)?shares",
    ], text)
    return _parse_number(raw)


# ── Bookrunners ───────────────────────────────────────────────────────────────

def extract_bookrunners(text: str) -> Optional[str]:
    """
    Extract the list of bookrunning managers from the cover page.

    On 424B4 cover pages, bookrunners are listed as one name per line
    between "underwriters expect to deliver" and "Prospectus dated".
    Returns a semicolon-delimited string, e.g.
    ``"MORGAN STANLEY; GOLDMAN SACHS & CO. LLC; J.P. MORGAN"``.

    Returns:
        Semicolon-delimited string of bookrunner names, or None.
    """
    # Locate the cover-page bookrunner block
    m = re.search(
        r"(?:deliver\s+the\s+shares\s+against\s+payment[^\n]*\n"
        r"|The\s+underwriters\s+expect\s+to\s+deliver[^\n]*\n)"
        r"((?:[^\n]+\n){1,40}?)"
        r"(?:Prospectus\s+dated|Table\s+of\s+Contents|_{4,})",
        text,
        re.IGNORECASE,
    )
    if m:
        block = m.group(1)
    else:
        # Fallback: look for "Joint Book-Running Managers" section
        m2 = re.search(
            r"(?:Joint\s+)?Book.?Running\s+Managers?\s*\n((?:[^\n]+\n){1,20}?)(?:\n\n|\Z)",
            text,
            re.IGNORECASE,
        )
        if not m2:
            return None
        block = m2.group(1)

    names: list[str] = []
    for line in block.splitlines():
        line = line.strip().rstrip("*").strip()
        # Skip blank, separator, pagination, or footnote lines
        if not line:
            continue
        if re.match(r"^[\d_\-\.\*]+$|^In\s+alphabetical|^Prospectus|^\*", line, re.IGNORECASE):
            continue
        if len(line) < 3 or re.match(r"^\d", line):
            continue
        names.append(line)

    return "; ".join(names) if names else None
