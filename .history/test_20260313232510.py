from app.utils.http import get_json

url="https://data.sec.gov/submissions/CIK0000320193.json"
data=get_json(url)

print(data["name"])