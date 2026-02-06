
import sys
import os
import pandas as pd
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))
from backend.services.indicators import get_market_data

def test_fetch():
    print("Testing get_market_data for 60m...")
    df = get_market_data("000001", period="60")
    print(f"Result empty? {df.empty}")
    if not df.empty:
        print(df.tail())
    else:
        print("Failed to fetch 60m data")

    print("\nTesting get_market_data for daily...")
    df = get_market_data("000001", period="daily")
    print(f"Result empty? {df.empty}")
    if not df.empty:
        print(df.tail())

if __name__ == "__main__":
    test_fetch()
