import requests
import json

create_api = 'http://127.0.0.1:6000/dummy'

import time
time.sleep(3)

test_data = {'testdatum': 'a'}

for i in range(10):
    r = requests.post(create_api, data={'data': json.dumps({'testdatum': 'a'})})
    print(r.status_code)
    print(r.content)

if r.ok:
    print("Now we play the waiting game")

time.sleep(3)

list_api = 'http://127.0.0.1:7000/records'

r = requests.get(list_api)

print(r.status_code)
print(r.content)

assert r.ok

results = r.json()
assert results['count'] == 10
for r in results['results']:
    assert json.loads(r['data']) == test_data

print("Everything looks good!")
