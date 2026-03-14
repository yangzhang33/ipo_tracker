"""Capitalization parser: extract share-count fields from prospectus text.

All functions accept the plain-text string produced by
``strip_html_to_text()`` and return ``None`` when no confident match
is found.

Note on share classes
---------------------
Many issuers have multiple share classes (Class A / B / C).  The
``_post_ipo`` and ``_pre_ipo`` functions try to find *total* (all-class)
counts first, then fall back to single-class counts.  The caller
(job layer) is responsible for deciding which value to persist.
"""

from __future__ import annotations

import re
from typing import Optional


# ── Shared helpers ────────────────────────────────────────────────────────────

def _first(patterns: list[str], text: str, group: int = 1) -> Optional[str]:
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE | re.DOTALL)
        if m:
            try:
                return m.group(group).strip()
            except IndexError:
                pass
    return None


def _parse_number(raw: str) -> Optional[float]:
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


def _all_matches(pattern: str, text: str) -> list[float]:
    """Return all numeric matches for a pattern as a list of floats."""
    results = []
    for m in re.finditer(pattern, text, re.IGNORECASE):
        v = _parse_number(m.group(1))
        if v is not None:
            results.append(v)
    return results


# ── Post-IPO shares outstanding ───────────────────────────────────────────────

def extract_shares_outstanding_post_ipo(text: str) -> Optional[float]:
    """
    Extract total shares outstanding immediately after the offering.

    Prefers patterns that refer to all share classes combined (Class A,
    Class B, and Class C).  Falls back to patterns that may capture a
    per-class count; in that case the largest value is returned as a
    best-effort proxy for the total.

    Returns:
        Total post-IPO shares outstanding as float, or None.
    """
    # Tier 1: explicit multi-class total
    # Pattern: "Class A, Class B, and Class C common stock to be outstanding
    #            immediately after this offering\n158,993,090 shares"
    raw = _first([
        r"Class\s+[A-C](?:(?:,|\s+and)\s+Class\s+[A-C])+\s+common\s+stock\s+"
        r"to\s+be\s+outstanding\s+(?:immediately\s+)?after\s+this\s+offering\s*\n\s*([\d,]+)",
        # "total ... shares ... outstanding after this offering"
        r"total\s+(?:of\s+)?(\d[\d,]+)\s+shares?[^.]{0,80}"
        r"outstanding\s+(?:immediately\s+)?after\s+(?:this\s+)?offering",
    ], text)
    if raw:
        return _parse_number(raw)

    # Tier 2: generic "X shares ... outstanding ... after this offering"
    # Collect all matches and return the largest (most likely the all-class total)
    candidates = _all_matches(
        r"(\d[\d,]+)\s+shares?[^.]{0,200}"
        r"outstanding\s+(?:immediately\s+)?after\s+(?:this\s+)?offering",
        text,
    )
    # Also try reversed: "outstanding after this offering ... X shares"
    candidates += _all_matches(
        r"outstanding\s+(?:immediately\s+)?after\s+this\s+offering\s*\n\s*([\d,]+)",
        text,
    )
    if candidates:
        return max(candidates)

    return None


# ── Pre-IPO shares outstanding ────────────────────────────────────────────────

def extract_shares_outstanding_pre_ipo(text: str) -> Optional[float]:
    """
    Extract total shares outstanding before the offering.

    These often appear as "X shares ... outstanding as of [date]" in
    the prospectus summary or the "Use of Proceeds" section.

    Returns:
        Pre-IPO shares outstanding as float, or None.
    """
    raw = _first([
        # "X shares of our common stock outstanding as of [date]"
        r"(\d[\d,]+)\s+shares?\s+of\s+(?:our\s+)?common\s+stock\s+outstanding\s+as\s+of",
        # "X shares outstanding as of [date], prior to this offering"
        r"(\d[\d,]+)\s+shares?\s+(?:of\s+\w+\s+)?outstanding\s+as\s+of[^.]{0,80}prior\s+to",
        # "X shares ... were outstanding" (past tense, pre-offering)
        r"(\d[\d,]+)\s+shares?[^.]{0,80}were\s+outstanding\s+(?:as\s+of|on)",
    ], text)
    return _parse_number(raw)


# ── Fully diluted shares ──────────────────────────────────────────────────────

def extract_fully_diluted_shares(text: str) -> Optional[float]:
    """
    Extract the fully diluted share count.

    Matches "X shares on a fully diluted basis" or the total in the
    dilution section.

    Returns:
        Fully diluted share count as float, or None.
    """
    raw = _first([
        # "X shares of our common stock outstanding on a fully diluted basis"
        r"(\d[\d,]+)\s+shares?[^.]{0,80}(?:fully\s+diluted|fully-diluted)\s+basis",
        r"on\s+a\s+(?:fully\s+diluted|fully-diluted)\s+basis[^.]{0,80}(\d[\d,]+)\s+shares?",
        # Dilution section: "total shares outstanding" line
        r"total\s+shares?\s+(?:of\s+common\s+stock\s+)?outstanding[^.]{0,60}(\d[\d,]+)",
    ], text)
    return _parse_number(raw)
