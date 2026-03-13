from app.collectors.sec import get_submissions_json

data = get_submissions_json("0000320193")
recent = data.get("filings", {}).get("recent", {})
forms = recent.get("form", [])

print(len(forms))
print(forms[:20])
print(sorted(set(forms))[:30])