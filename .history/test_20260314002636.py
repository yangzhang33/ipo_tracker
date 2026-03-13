from app.collectors.sec import get_submissions_json, extract_recent_target_forms

data = get_submissions_json("0000320193")
forms = extract_recent_target_forms(data)

print(type(forms))
print(len(forms))
print(forms[:3])