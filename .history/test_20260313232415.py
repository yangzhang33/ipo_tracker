from app.utils.text import strip_html_to_text

html = "<html><body><h1>Hello</h1><p>World</p></body></html>"
print(strip_html_to_text(html))