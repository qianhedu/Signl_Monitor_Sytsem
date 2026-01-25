import requests
import json

def test_search():
    print("Testing Symbol Search API...")
    
    # 1. Search Stock (empty query -> default list)
    url = "http://localhost:8000/api/symbols/search"
    print("\n--- Stock Search (Default) ---")
    try:
        res = requests.get(url, params={"market": "stock"})
        data = res.json()
        print(f"Count: {len(data)}")
        if data:
            print("First 3:", data[:3])
    except Exception as e:
        print(f"Error: {e}")

    # 2. Search Stock (Specific)
    print("\n--- Stock Search ('茅台') ---")
    try:
        res = requests.get(url, params={"q": "茅台", "market": "stock"})
        data = res.json()
        print(f"Count: {len(data)}")
        print("Results:", data)
    except Exception as e:
        print(f"Error: {e}")

    # 3. Search Futures
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
