"""Tests for app.parsers.filing_locator.select_best_filing."""

from app.parsers.filing_locator import select_best_filing


# ── Helpers ───────────────────────────────────────────────────────────────────

def f(form_type: str, filing_date: str) -> dict:
    """Minimal filing dict for testing."""
    return {"form_type": form_type, "filing_date": filing_date}


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_empty_returns_none():
    assert select_best_filing([]) is None


def test_only_s1_selects_s1():
    filings = [f("S-1", "2024-02-01")]
    result = select_best_filing(filings)
    assert result["form_type"] == "S-1"


def test_s1a_beats_s1():
    filings = [
        f("S-1",   "2024-02-01"),
        f("S-1/A", "2024-02-15"),
    ]
    result = select_best_filing(filings)
    assert result["form_type"] == "S-1/A"


def test_424b4_beats_s1a():
    filings = [
        f("S-1",   "2024-02-01"),
        f("S-1/A", "2024-02-15"),
        f("424B4", "2024-03-01"),
    ]
    result = select_best_filing(filings)
    assert result["form_type"] == "424B4"


def test_424b4_beats_424b1():
    filings = [
        f("424B1", "2024-03-10"),
        f("424B4", "2024-03-01"),
    ]
    result = select_best_filing(filings)
    assert result["form_type"] == "424B4"


def test_latest_date_wins_within_tier():
    filings = [
        f("S-1/A", "2024-02-01"),
        f("S-1/A", "2024-03-15"),  # ← newer, should win
        f("S-1/A", "2024-01-10"),
    ]
    result = select_best_filing(filings)
    assert result["form_type"] == "S-1/A"
    assert result["filing_date"] == "2024-03-15"


def test_f1_selected_when_no_s1():
    filings = [f("F-1", "2024-05-01")]
    result = select_best_filing(filings)
    assert result["form_type"] == "F-1"


def test_f1a_beats_f1():
    filings = [
        f("F-1",   "2024-05-01"),
        f("F-1/A", "2024-06-01"),
    ]
    result = select_best_filing(filings)
    assert result["form_type"] == "F-1/A"


def test_unrecognised_forms_return_none():
    filings = [f("10-K", "2024-01-01"), f("8-K", "2024-02-01")]
    assert select_best_filing(filings) is None


def test_orm_like_object():
    """select_best_filing must also work with attribute-based objects."""
    class FakeFiling:
        def __init__(self, form_type, filing_date):
            self.form_type  = form_type
            self.filing_date = filing_date

    filings = [
        FakeFiling("S-1",   "2024-02-01"),
        FakeFiling("424B4", "2024-03-21"),
    ]
    result = select_best_filing(filings)
    assert result.form_type == "424B4"
