import requests
import json
from backend.services.indicators import get_market_data

def test_metadata_search():
    print("\n--- Testing Metadata Search ---")
    try:
        # Test HS300
        url = "http://localhost:8000/api/symbols/search"
        res = requests.get(url, params={"q": "hs300", "market": "stock"})
        data = res.json()
        print(f"HS300 Count: {len(data)}")
        if data:
            print("First HS300:", data[0])
            
        # Test All Futures
        res = requests.get(url, params={"q": "all", "market": "futures"})
        data = res.json()
        print(f"All Futures Count: {len(data)}")
        if data:
            print("First Future:", data[0])
    except Exception as e:
        print(f"Error search: {e}")

def test_minute_data():
    print("\n--- Testing Minute Data Fetching (Backend Logic) ---")
    try:
        # Stock Minute
        # 600519 -> sh600519 inside function
        print("Fetching 600519 60m...")
        df = get_market_data("600519", market="stock", period="60")
        print(f"Rows: {len(df)}")
        if not df.empty:
            print(df.tail(2))
            
        # Futures Minute
        print("Fetching RB0 60m...")
        df = get_market_data("RB0", market="futures", period="60")
        print(f"Rows: {len(df)}")
        if not df.empty:
            print(df.tail(2))
            
    except Exception as e:
        print(f"Error data: {e}")

if __name__ == "__main__":
    # Ensure backend server is running for search test, 
    # but we can test get_market_data directly
    test_minute_data()
    # test_metadata_search() # Uncomment if server is running
