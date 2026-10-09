import urllib.request
import json

req = urllib.request.Request(
    'http://127.0.0.1:5000/api/register',
    data=json.dumps({"email":"test30@test.com", "password":"test", "role":"Employee"}).encode('utf-8'),
    headers={'Content-Type': 'application/json'},
    method='POST'
)

try:
    resp = urllib.request.urlopen(req)
    print("SUCCESS", resp.status)
    print(resp.read().decode())
except Exception as e:
    print("FAILED", e.code)
    print(e.read().decode())
