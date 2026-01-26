import requests
import json

url = "http://localhost:8802/api/detect/ma"
data = {
    "symbols": ["000001", "600519"],
    "market": "stock",
    "period": "daily",
    "lookback": 30,
    "short_period": 5,
    "long_period": 10
}

try:
    print(f"Testing {url}...")
    response = requests.post(url, json=data, timeout=60)
    print("Status Code:", response.status_code)
    
    if response.status_code == 200:
        res = response.json()
        print(f"Found {len(res['results'])} signals")
        for r in res['results']:
            print(f"Symbol: {r['symbol']}, Signal: {r['signal']}, Date: {r['date']}, Short: {r['ma_short']:.2f}, Long: {r['ma_long']:.2f}")
    else:
        print("Error response:", response.text)

except Exception as e:
    print("Error:", e)
