from app.collectors.sec import download_filing_html

url = "https://www.sec.gov/Archives/edgar/data/320193/000114036126006577/ef20060722_8k.htm"
html = download_filing_html(url)

print(type(html))
print(len(html))
print(html[:300])