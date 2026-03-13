from app.collectors.sec import get_submissions_json
data = get_submissions_json("0000320193")
print(type(data))
print(data.get("name"))