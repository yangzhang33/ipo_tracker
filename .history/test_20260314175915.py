from app.parsers.lockup_parser import detect_staged_unlock

text = "25% of the shares will be released at the beginning of each 180-day period, subject to certain exceptions."
print(detect_staged_unlock(text))