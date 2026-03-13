from app.collectors.sec import get_submissions_json

data = get_submissions_json("0000320193")
recent = data.get("filings", {}).get("recent", {})

forms = recent.get("form", [])
accession_numbers = recent.get("accessionNumber", [])
filing_dates = recent.get("filingDate", [])
primary_docs = recent.get("primaryDocument", [])

for i in range(10):
    print(i, forms[i], filing_dates[i], accession_numbers[i], primary_docs[i])