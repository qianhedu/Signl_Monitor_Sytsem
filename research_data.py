import akshare as ak
import pandas as pd
import os

# Unset proxy just in case
os.environ.pop("HTTP_PROXY", None)
os.environ.pop("HTTPS_PROXY", None)

def test_stock_min():
    print("\n--- Testing Stock Minute Data (600519) ---")
    try:
        # Try Sina source for minutes if Eastmoney fails
        # ak.stock_zh_a_minute is from Sina
        # symbol needs prefix: sh600519
        df = ak.stock_zh_a_minute(symbol="sh600519", period="60")
        print(f"Success (Sina)! Rows: {len(df)}")
        print(df.head(2))
        print("Columns:", df.columns)
    except Exception as e:
        print(f"Error (Sina): {e}")

    try:
        # Retry Eastmoney with no adjust to see if it works
        df = ak.stock_zh_a_hist_min_em(symbol="600519", period="60")
        print(f"Success (EM No Adjust)! Rows: {len(df)}")
    except Exception as e:
        print(f"Error (EM): {e}")

def test_futures_min():
    print("\n--- Testing Futures Minute Data (RB0) ---")
    try:
        # period: "1", "5", "15", "30", "60"
        # Note: ak.futures_zh_minute_sina might use different symbol format
        df = ak.futures_zh_minute_sina(symbol="RB0", period="60")
        print(f"Success! Rows: {len(df)}")
        print(df.head(2))
        print("Columns:", df.columns)
    except Exception as e:
        print(f"Error: {e}")

def test_hs300():
    print("\n--- Testing HS300 Constituents ---")
    try:
        # index_stock_cons_weight_csindex
        df = ak.index_stock_cons(symbol="000300")
        print(f"Success! Rows: {len(df)}")
        print(df.head(2))
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_stock_min()
    test_futures_min()
    test_hs300()
