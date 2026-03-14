"""SEC EDGAR data collector.

Provides functions to fetch company submission metadata and filing documents
from SEC EDGAR. No database writes happen here — this module is pure I/O.

SEC EDGAR base URLs
-------------------
- Submissions JSON : https://data.sec.gov/submissions/CIK{cik10}.json
- Filing archive   : https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession}/
- Primary document : https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession}/{doc}

Usage example
-------------
    from app.collectors.sec import get_submissions_json, extract_recent_target_forms

    data   = get_submissions_json("320193")          # Apple Inc.
    forms  = extract_recent_target_forms(data)
    for f in forms:
        print(f["form_type"], f["filing_date"], f["primary_doc_url"])
"""

from __future__ import annotations

from typing import Optional

from ..config import settings
from ..utils.http import get_json, get_text
from ..utils.logging import get_logger

logger = get_logger(__name__)

# ── SEC EDGAR constants ───────────────────────────────────────────────────────

_SUBMISSIONS_BASE = "https://data.sec.gov/submissions"
_ARCHIVE_BASE = "https://www.sec.gov/Archives/edgar/data"

_TARGET_FORMS = {"S-1", "S-1/A", "F-1", "F-1/A", "424B4", "424B1", "RW"}


# ── Public helpers ────────────────────────────────────────────────────────────

def get_sec_headers() -> dict:
    """
    Return HTTP headers suitable for SEC EDGAR requests.

    SEC requires a descriptive User-Agent containing a contact address.
    The value is read from ``settings.SEC_USER_AGENT`` so callers can
    override it via the ``.env`` file without touching code.

    Returns:
        dict with User-Agent and Accept headers.
    """
    return {
        "User-Agent": settings.SEC_USER_AGENT,
        "Accept": "application/json, text/html, */*",
        "Accept-Encoding": "gzip, deflate",
    }


def normalize_cik(cik: str | int) -> str:
    """
    Normalise a CIK value to the 10-digit zero-padded string SEC uses.

    Args:
        cik: CIK as a string or integer (with or without leading zeros).

    Returns:
        10-digit zero-padded string, e.g. ``"0000320193"``.

    Raises:
        ValueError: If ``cik`` cannot be converted to an integer.
    """
    return str(int(cik)).zfill(10)


def get_submissions_json(cik: str | int, use_cache: bool = True) -> dict:
    """
    Fetch the company submissions JSON from SEC EDGAR.

    The JSON contains company metadata and a ``filings.recent`` block
    with arrays of filing attributes (form, date, accession number, …).

    Args:
        cik: Company CIK (any format accepted by ``normalize_cik``).
        use_cache: Pass through to the HTTP layer cache (default True).

    Returns:
        Parsed submissions dict as returned by data.sec.gov.

    Raises:
        httpx.HTTPStatusError: On non-2xx HTTP response.
    """
    cik10 = normalize_cik(cik)
    url = f"{_SUBMISSIONS_BASE}/CIK{cik10}.json"
    logger.info("Fetching submissions JSON for CIK %s", cik10)
    return get_json(url, headers=get_sec_headers(), use_cache=use_cache)


def build_filing_primary_doc_url(
    cik: str | int,
    accession_no: str,
    primary_doc: str,
) -> str:
    """
    Construct the HTTPS URL for a filing's primary document.

    SEC archive paths use the integer CIK (no leading zeros) and the
    accession number without dashes.

    Args:
        cik: Company CIK in any format.
        accession_no: Accession number, with or without dashes
                      (e.g. ``"0001234567-24-000001"`` or ``"000123456724000001"``).
        primary_doc: Filename of the primary document
                     (e.g. ``"s-1.htm"``).

    Returns:
        Full HTTPS URL to the primary document, e.g.
        ``"https://www.sec.gov/Archives/edgar/data/320193/000032019324000001/s-1.htm"``.
    """
    cik_int = int(cik)
    accession_path = accession_no.replace("-", "")
    return f"{_ARCHIVE_BASE}/{cik_int}/{accession_path}/{primary_doc}"


def build_filing_index_url(cik: str | int, accession_no: str) -> str:
    """
    Construct the HTTPS URL for a filing's index page on SEC EDGAR.

    Args:
        cik: Company CIK in any format.
        accession_no: Accession number with or without dashes.

    Returns:
        Full HTTPS URL to the filing index directory.
    """
    cik_int = int(cik)
    accession_path = accession_no.replace("-", "")
    return f"{_ARCHIVE_BASE}/{cik_int}/{accession_path}/"


def download_filing_html(url: str, use_cache: bool = True) -> str:
    """
    Download a filing HTML document from SEC EDGAR.

    Uses the shared HTTP cache so repeated calls for the same URL are free.

    Args:
        url: Full HTTPS URL to the filing document.
        use_cache: Whether to use the local file cache (default True).

    Returns:
        Raw HTML as a string.

    Raises:
        httpx.HTTPStatusError: On non-2xx HTTP response.
    """
    logger.info("Downloading filing HTML: %s", url)
    return get_text(url, headers=get_sec_headers(), use_cache=use_cache)


def extract_recent_target_forms(submissions_json: dict) -> list[dict]:
    """
    Extract IPO-relevant filings from a submissions JSON response.

    Filters for form types in ``_TARGET_FORMS`` (S-1, S-1/A, F-1, F-1/A,
    424B4, 424B1, RW) from the ``filings.recent`` block. Fields that are
    absent or empty in the source data are silently set to ``None``.

    Note: ``filings.recent`` only covers the most recent ~1000 filings.
    Older filings are referenced in ``filings.files`` but are not fetched
    here (out of scope for the current stage).

    Args:
        submissions_json: Parsed dict from ``get_submissions_json``.

    Returns:
        List of dicts, one per matched filing, each containing:

        - ``accession_no``    (str)  — dashed format, e.g. ``"0001234567-24-000001"``
        - ``form_type``       (str)
        - ``filing_date``     (str)  — ISO date, e.g. ``"2024-03-15"``
        - ``primary_doc``     (str | None)
        - ``primary_doc_url`` (str | None)
        - ``filing_index_url``(str)

        Sorted by filing_date descending (most recent first).
    """
    # CIK is embedded in the submissions JSON; fall back gracefully
    raw_cik: str = str(submissions_json.get("cik", "0"))

    try:
        recent: dict = submissions_json["filings"]["recent"]
    except (KeyError, TypeError):
        logger.warning("submissions_json has no filings.recent block")
        return []

    # Each key in `recent` is a parallel array of equal length
    accession_numbers: list = recent.get("accessionNumber", [])
    form_types: list       = recent.get("form", [])
    filing_dates: list     = recent.get("filingDate", [])
    primary_docs: list     = recent.get("primaryDocument", [])

    results: list[dict] = []

    for i, form_type in enumerate(form_types):
        if form_type not in _TARGET_FORMS:
            continue

        accession_no  = _safe_get(accession_numbers, i)
        filing_date   = _safe_get(filing_dates, i)
        primary_doc   = _safe_get(primary_docs, i) or None

        primary_doc_url: Optional[str] = None
        if accession_no and primary_doc:
            primary_doc_url = build_filing_primary_doc_url(
                raw_cik, accession_no, primary_doc
            )

        filing_index_url = build_filing_index_url(raw_cik, accession_no) if accession_no else ""

        results.append({
            "accession_no":     accession_no,
            "form_type":        form_type,
            "filing_date":      filing_date,
            "primary_doc":      primary_doc,
            "primary_doc_url":  primary_doc_url,
            "filing_index_url": filing_index_url,
        })

    # Most-recent first
    results.sort(key=lambda r: r["filing_date"] or "", reverse=True)
    logger.info(
        "Found %d target filing(s) for CIK %s", len(results), raw_cik
    )
    return results


# ── CIK lookup helper ─────────────────────────────────────────────────────────

_COMPANY_TICKERS_URL = (
    "https://www.sec.gov/files/company_tickers_exchange.json"
)


def search_edgar_company(query: str, max_results: int = 10) -> list[dict]:
    """
    Search the SEC EDGAR company list by ticker or company name.

    Downloads ``company_tickers_exchange.json`` from SEC (cached after the
    first call) and does a case-insensitive substring search across both
    the ticker symbol and the company name.

    Useful for manually looking up a CIK before running ``sync_sec_filings``.

    Example::

        from app.collectors.sec import search_edgar_company
        for hit in search_edgar_company("Reddit"):
            print(hit)
        # {"cik": "0001713445", "name": "Reddit, Inc.", "ticker": "RDDT", "exchange": "Nasdaq"}

    Args:
        query: Search string (matched against name and ticker).
        max_results: Maximum number of results to return (default 10).

    Returns:
        List of dicts with keys: ``cik``, ``name``, ``ticker``, ``exchange``.
    """
    data = get_json(
        _COMPANY_TICKERS_URL,
        headers=get_sec_headers(),
        use_cache=True,
    )
    fields: list[str] = data.get("fields", [])
    rows: list[list]  = data.get("data", [])

    query_lower = query.strip().lower()
    results: list[dict] = []

    for row in rows:
        entry = dict(zip(fields, row))
        name   = str(entry.get("name",   "") or "").lower()
        ticker = str(entry.get("ticker", "") or "").lower()
        if query_lower in name or query_lower == ticker:
            results.append({
                "cik":      normalize_cik(entry.get("cik", 0)),
                "name":     entry.get("name"),
                "ticker":   entry.get("ticker"),
                "exchange": entry.get("exchange"),
            })
            if len(results) >= max_results:
                break

    return results


# ── Internal ──────────────────────────────────────────────────────────────────

def _safe_get(lst: list, index: int):
    """Return ``lst[index]`` or ``None`` if the index is out of range."""
    try:
        return lst[index]
    except IndexError:
        return None
