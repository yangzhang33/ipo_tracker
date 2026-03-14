"""Lock-up agreement parser.

Extracts lock-up period information from plain-text prospectus content.

Public API
----------
- extract_lockup_days(text)      → int | None
- detect_staged_unlock(text)     → bool
- extract_unlock_notes(text)     → str | None
- determine_confidence(text, lockup_days, is_staged_unlock) → str
"""

from __future__ import annotations

import re

# ── Section keywords to locate lock-up relevant text ─────────────────────────

_SECTION_TITLES = [
    "lock-up agreements",
    "lock-up",
    "lockup agreements",
    "lockup",
    "market standoff",
    "shares eligible for future sale",
    "underwriting",
]

# Maximum characters to extract from a matched section
_SECTION_MAX_CHARS = 6000


def _find_lockup_section(text: str) -> str:
    """
    Return the portion of ``text`` that most likely contains lock-up language.

    Searches for section headers in priority order and returns up to
    ``_SECTION_MAX_CHARS`` characters from the first match.
    Falls back to the full text if no section header is found.
    """
    lower = text.lower()
    for title in _SECTION_TITLES:
        idx = lower.find(title)
        if idx != -1:
            return text[idx : idx + _SECTION_MAX_CHARS]
    return text


# ── extract_lockup_days ───────────────────────────────────────────────────────

# Patterns ordered from most specific to least specific.
# Each captures a numeric day count.
_LOCKUP_DAYS_PATTERNS: list[re.Pattern] = [
    # "for a period of 180 days after the date of this prospectus"
    re.compile(
        r"for\s+a\s+period\s+of\s+(\d+)\s+days?\s+(?:after|following|from)",
        re.IGNORECASE,
    ),
    # "for 180 days after the date of this prospectus"
    re.compile(
        r"for\s+(\d+)\s+days?\s+(?:after|following|from)",
        re.IGNORECASE,
    ),
    # "beginning 181 days after the date of this prospectus"
    re.compile(
        r"beginning\s+(\d+)\s+days?\s+(?:after|following|from)",
        re.IGNORECASE,
    ),
    # "a 180-day lock-up period" / "a 180-day restricted period"
    re.compile(
        r"(\d+)[- ]day\s+(?:lock[- ]?up|restricted|restriction)\s+period",
        re.IGNORECASE,
    ),
    # "lock-up period of 180 days"
    re.compile(
        r"lock[- ]?up\s+period\s+of\s+(\d+)\s+days?",
        re.IGNORECASE,
    ),
    # "not to sell ... for 180 days"
    re.compile(
        r"not\s+to\s+(?:sell|offer|transfer|dispose)\b.{0,80}?for\s+(\d+)\s+days?",
        re.IGNORECASE | re.DOTALL,
    ),
]


def extract_lockup_days(text: str) -> int | None:
    """
    Extract the primary lock-up duration in calendar days from prospectus text.

    Searches the lock-up relevant section first, falls back to full text.
    Returns the most commonly matched day count; ties are broken by taking
    the first match in the priority-ordered pattern list.

    Args:
        text: Plain-text prospectus content (output of strip_html_to_text).

    Returns:
        Integer number of days (e.g. 180), or None if not found.
    """
    section = _find_lockup_section(text)

    def _collect_matches(haystack: str) -> list[int]:
        results: list[int] = []
        for pattern in _LOCKUP_DAYS_PATTERNS:
            for m in pattern.finditer(haystack):
                try:
                    days = int(m.group(1))
                    if 30 <= days <= 730:  # sanity bounds
                        results.append(days)
                except (ValueError, IndexError):
                    pass
        return results

    # Search the targeted section first; fall back to full text so that day
    # counts appearing *before* the section header are not missed.
    all_matches = _collect_matches(section)
    if not all_matches and section is not text:
        all_matches = _collect_matches(text)

    if not all_matches:
        return None

    # Return the most frequent value; if tied, the first one encountered
    from collections import Counter
    counter = Counter(all_matches)
    return counter.most_common(1)[0][0]


# ── detect_staged_unlock ──────────────────────────────────────────────────────

_STAGED_UNLOCK_PATTERNS: list[re.Pattern] = [
    re.compile(r"\d+\s*%\s+(?:of\s+(?:the\s+)?(?:shares|securities|stock))?\s*(?:will\s+be\s+)?released", re.IGNORECASE),
    re.compile(r"at\s+the\s+beginning\s+of\s+each\s+\d+[- ]day\s+period", re.IGNORECASE),
    re.compile(r"release[sd]?\s+in\s+(?:tranches?|installments?|stages?|portions?)", re.IGNORECASE),
    re.compile(r"(?:pro[- ]?rata|ratable|ratably)\s+(?:over|during|throughout)", re.IGNORECASE),
    re.compile(r"(?:quarterly|monthly|annually|semi[- ]?annually)\s+(?:vest|release|unlock)", re.IGNORECASE),
    re.compile(r"earnings[- ]related\s+release", re.IGNORECASE),
    re.compile(r"performance[- ](?:based|related)\s+(?:release|unlock|vesting)", re.IGNORECASE),
    re.compile(r"multi[- ]?(?:stage|tranche|tier)\s+(?:release|unlock|lock[- ]?up)", re.IGNORECASE),
    re.compile(r"subject\s+to\s+certain\s+exceptions.*?\breleased?\b", re.IGNORECASE | re.DOTALL),
    re.compile(r"first\s+\d+\s+days?\s+.{0,60}?\s+next\s+\d+\s+days?", re.IGNORECASE | re.DOTALL),
]


def detect_staged_unlock(text: str) -> bool:
    """
    Detect whether the prospectus describes a staged (phased) lock-up release.

    Args:
        text: Plain-text prospectus content.

    Returns:
        True if staged unlock language is detected, False otherwise.
    """
    section = _find_lockup_section(text)
    for pattern in _STAGED_UNLOCK_PATTERNS:
        if pattern.search(section):
            return True
    return False


# ── extract_unlock_notes ──────────────────────────────────────────────────────

# Sentence-level patterns that capture notable lock-up language
_UNLOCK_NOTE_PATTERNS: list[re.Pattern] = [
    # "for a period of X days after ..."
    re.compile(
        r"for\s+(?:a\s+period\s+of\s+)?\d+\s+days?\s+(?:after|following|from)[^.]{0,200}\.",
        re.IGNORECASE,
    ),
    # "a X-day lock-up period ..."
    re.compile(
        r"\d+[- ]day\s+(?:lock[- ]?up|restricted)\s+period[^.]{0,200}\.",
        re.IGNORECASE,
    ),
    # staged-unlock sentence
    re.compile(
        r"\d+\s*%\s+(?:of\s+the\s+shares?\s+)?(?:will\s+be\s+)?released[^.]{0,200}\.",
        re.IGNORECASE,
    ),
]


def extract_unlock_notes(text: str) -> str | None:
    """
    Extract a brief human-readable note from lock-up language in the prospectus.

    Returns a short representative sentence or fragment describing the lock-up
    (and staged-unlock conditions if present), or None if nothing useful found.

    Args:
        text: Plain-text prospectus content.

    Returns:
        String up to ~300 characters, or None.
    """
    section = _find_lockup_section(text)
    notes: list[str] = []

    for pattern in _UNLOCK_NOTE_PATTERNS:
        m = pattern.search(section)
        if m:
            snippet = m.group(0).strip()
            # Collapse internal whitespace for readability
            snippet = re.sub(r"\s+", " ", snippet)
            if snippet and snippet not in notes:
                notes.append(snippet)
        if len(notes) >= 2:
            break

    if not notes:
        return None

    combined = " | ".join(notes)
    return combined[:300]


# ── determine_confidence ──────────────────────────────────────────────────────

def determine_confidence(
    text: str,
    lockup_days: int | None,
    is_staged_unlock: bool,
) -> str:
    """
    Rate the confidence of the lock-up extraction result.

    Heuristic:
    - ``high``:   lockup_days found AND one of the canonical day counts
                  (90, 180) AND not staged.
    - ``medium``: lockup_days found but staged, or an unusual day count.
    - ``low``:    lockup_days not found at all.

    Args:
        text:             Plain-text prospectus content (used for validation).
        lockup_days:      Extracted day count (or None).
        is_staged_unlock: Whether staged-unlock language was detected.

    Returns:
        "high" | "medium" | "low"
    """
    if lockup_days is None:
        return "low"

    # Standard day counts that appear in the vast majority of S-1 / 424B4 filings
    _STANDARD_DAYS = {90, 180, 360}

    if lockup_days in _STANDARD_DAYS and not is_staged_unlock:
        return "high"

    return "medium"
