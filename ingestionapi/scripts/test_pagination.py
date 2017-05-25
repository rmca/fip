"""
Run this against a live API to paginate through the complete set of
records.

Will write out the max, average, and minimum query times as we go so we have
some idea about how query time is changing as we page.
"""


import requests

import time

#r = requests.get("http://127.0.0.1:5000/records")
#res = r.json()
#next_tok = res['next']
#total_count = len(res['results'])

next_tok = None
count = 0

maxdur = 0
total = 0
mindur = None

while True:
    start = time.time()
    if next_tok is None:
        r = requests.get("http://127.0.0.1:7000/records")
    else:
        r = requests.get("http://127.0.0.1:7000/records?next=%s" % next_tok)
    diff = time.time() - start
    maxdur = max(diff, maxdur)
    if mindur is None:
        mindur = diff
    mindur = min(diff, mindur)
    total += diff
    res = r.json()
    next_tok = res['next']
    if next_tok is None:
        print("Nothing left to retrieve")
    count += 1
    if count % 100 == 0:
        print(maxdur, (total/count), mindur)

print("Total request count was: %d" % count)
