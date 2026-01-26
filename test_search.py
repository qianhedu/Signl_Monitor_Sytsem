import requests
import json

def test_search():
    print("Testing Symbol Search API...")
    
    # 1. 股票搜索（空查询 -> 返回默认列表）
    url = "http://localhost:8802/api/symbols/search"
    print("\n--- Stock Search (Default) ---")
    try:
        res = requests.get(url, params={"market": "stock"})
        data = res.json()
        print(f"Count: {len(data)}")
        if data:
            print("First 3:", data[:3])
    except Exception as e:
        print(f"Error: {e}")

    # 2. 股票搜索（指定关键词）
    print("\n--- Stock Search ('茅台') ---")
    try:
        res = requests.get(url, params={"q": "茅台", "market": "stock"})
        data = res.json()
        print(f"Count: {len(data)}")
        print("Results:", data)
    except Exception as e:
        print(f"Error: {e}")

    # 3. 期货搜索
    print("\n--- Futures Search ---")
    try:
        res = requests.get(url, params={"market": "futures"})
        data = res.json()
        print(f"Count: {len(data)}")
        if data:
            print("First 3:", data[:3])
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_search()
