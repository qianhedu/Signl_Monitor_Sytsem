import requests
import json

url = "http://localhost:8000/api/detect/dkx"
# Try a few popular stocks
data = {
    "symbols": ["000001", "600519", "601318"], # PingAn Bank, Moutai, PingAn Insurance
    "period": "daily",
    "lookback": 30 # Increase lookback to find *some* signal
}

try:
    response = requests.post(url, json=data, timeout=60)
    print("Status Code:", response.status_code)
    # Print only first result summary to avoid huge output
    res = response.json()
    print(f"Found {len(res['results'])} signals")
    if res['results']:
        print("First signal:", res['results'][0]['symbol'], res['results'][0]['signal'], res['results'][0]['date'])
except Exception as e:
    print("Error:", e)
