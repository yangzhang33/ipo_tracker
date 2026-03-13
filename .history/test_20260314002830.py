data = get_submissions_json("0000320193")

print(data.keys())
print(data["filings"].keys())
print(data["filings"]["recent"].keys())