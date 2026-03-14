from app.parsers.filing_locator import select_best_filing

filings = [
    {"form_type": "S-1", "filing_date": "2026-03-01"}
]

print(select_best_filing(filings))

filings = [
    {"form_type": "S-1", "filing_date": "2026-03-01"},
    {"form_type": "S-1/A", "filing_date": "2026-03-05"},
]

print(select_best_filing(filings))