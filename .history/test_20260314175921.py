from app.parsers.lockup_parser import extract_unlock_notes

text = "25% of the shares will be released at the beginning of each 180-day period, subject to certain exceptions."
print(extract_unlock_notes(text))