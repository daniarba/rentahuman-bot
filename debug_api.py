import requests
import json
import os

RENTAHUMAN_API_KEY = os.environ.get("RENTAHUMAN_API_KEY", "")

headers = {
    "Authorization": f"Bearer {RENTAHUMAN_API_KEY}",
    "Content-Type": "application/json",
    "Accept-Encoding": "gzip, deflate",  # Brotli disable
    "Accept": "application/json"
}

print("=== TEST 1: /api/bounties ===")
resp = requests.get(
    "https://rentahuman.ai/api/bounties",
    headers=headers,
    params={"status": "open"}
)
print(f"Status: {resp.status_code}")
print(f"Response:\n{resp.text[:1000]}")
print()

print("=== TEST 2: /api/bounties (no params) ===")
resp2 = requests.get(
    "https://rentahuman.ai/api/bounties",
    headers=headers
)
print(f"Status: {resp2.status_code}")
print(f"Response:\n{resp2.text[:1000]}")
