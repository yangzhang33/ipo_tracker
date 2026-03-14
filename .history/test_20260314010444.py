from app.collectors.nasdaq import fetch_nasdaq_candidates
from app.collectors.nyse import fetch_nyse_candidates
from app.jobs.discover_candidates import discover_candidates

a = fetch_nasdaq_candidates()
print("nasdaq:", type(a), len(a), a[:2] if a else a)

b = fetch_nyse_candidates()
print("nyse:", type(b), len(b), b[:2] if b else b)

r = discover_candidates()
print("job:", r)