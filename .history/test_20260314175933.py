from app.parsers.lockup_parser import determine_confidence

text = "for a period of 180 days after the date of this prospectus"
print(determine_confidence(text, 180, False))

text2 = "25% of the shares will be released at the beginning of each 180-day period, subject to certain exceptions."
print(determine_confidence(text2, 180, True))