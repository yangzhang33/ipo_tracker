from app.parsers.lockup_parser import extract_lockup_days

text = "The holders may not sell their shares for 90 days after the date of this prospectus."
print(extract_lockup_days(text))