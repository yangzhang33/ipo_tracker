from app.collectors.sec import download_filing_html

url = "https://www.sec.gov/Archives/edgar/data/1/000000000125000004/424b4.htm"
html = download_filing_html(url)

print(type(html))
print(len(html))
print(html[:200])