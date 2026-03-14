from app.parsers.lockup_parser import extract_lockup_days

text = "Our directors, executive officers and substantially all of our stockholders have agreed, subject to certain exceptions, not to offer, sell or dispose of any shares for a period of 180 days after the date of this prospectus."
print(extract_lockup_days(text))