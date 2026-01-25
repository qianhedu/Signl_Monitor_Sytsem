import requests
import json

# Trigger detection again to save to DB
print("Triggering detection...")
try:
    requests.post("http://localhost:8000/api/detect/ma", json={
        "symbols": ["600519"],
        "market": "stock",
        "period": "daily",
        "lookback": 30,
        "short_period": 5,
        "long_period": 10
    })
except:
    pass

# Check history
print("Checking history...")
url = "http://localhost:8000/api/history"
try:
    response = requests.get(url)
    print("Status Code:", response.status_code)
    history = response.json()
    print(f"History items: {len(history)}")
    if history:
        print("Latest:", history[0])
except Exception as e:
    print("Error:", e)
