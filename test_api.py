import requests
import json

url = "http://localhost:8802/api/detect/dkx"
# 测试几只常见热门股票
data = {
    "symbols": ["000001", "600519", "601318"], # 平安银行、茅台、中国平安
    "period": "daily",
    "lookback": 30 # 增大回溯窗口以提高找到信号的概率
}

try:
    response = requests.post(url, json=data, timeout=60)
    print("Status Code:", response.status_code)
    # 仅打印首条结果摘要以避免过多输出
    res = response.json()
    print(f"Found {len(res['results'])} signals")
    if res['results']:
        print("First signal:", res['results'][0]['symbol'], res['results'][0]['signal'], res['results'][0]['date'])
except Exception as e:
    print("Error:", e)
