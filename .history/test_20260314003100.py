from app.collectors.sec import extract_recent_target_forms

mock_data = {
    "cik": "0000000001",
    "filings": {
        "recent": {
            "form": ["10-K", "S-1", "8-K", "424B4", "F-1/A", "DEF 14A"],
            "filingDate": ["2025-01-01", "2025-01-02", "2025-01-03", "2025-01-04", "2025-01-05", "2025-01-06"],
            "accessionNumber": [
                "0000000001-25-000001",
                "0000000001-25-000002",
                "0000000001-25-000003",
                "0000000001-25-000004",
                "0000000001-25-000005",
                "0000000001-25-000006",
            ],
            "primaryDocument": [
                "a.htm",
                "s1.htm",
                "b.htm",
                "424b4.htm",
                "f1a.htm",
                "c.htm",
            ],
        }
    }
}

forms = extract_recent_target_forms(mock_data)
print(forms)