from app.collectors.sec import build_filing_primary_doc_url

url = build_filing_primary_doc_url(
    "0000320193",
    "0001140361-26-006577",
    "ef20060722_8k.htm"
)

print(url)