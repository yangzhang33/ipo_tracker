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

filings = [
    {"form_type": "F-1", "filing_date": "2026-03-02"},
    {"form_type": "F-1/A", "filing_date": "2026-03-06"},
]

print(select_best_filing(filings))

filings = [
    {"form_type": "S-1/A", "filing_date": "2026-03-06"},
    {"form_type": "424B1", "filing_date": "2026-03-07"},
]

print(select_best_filing(filings))

filings = [
    {"form_type": "424B1", "filing_date": "2026-03-07"},
    {"form_type": "424B4", "filing_date": "2026-03-08"},
]

print(select_best_filing(filings))