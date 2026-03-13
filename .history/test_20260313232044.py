import time
from app.utils.http import get_text

start=time.time()
get_text("https://example.com")
print("first",time.time()-start)

start=time.time()
get_text("https://example.com")
print("second",time.time()-start)