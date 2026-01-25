import akshare as ak
import pandas as pd

try:
    print("Fetching futures data...")
    # Try a dominant contract, e.g., RB0 (Rebar dominant)
    df = ak.futures_zh_daily_sina(symbol="RB0")
    print("Columns:", df.columns)
    print(df.tail())
except Exception as e:
    print("Error:", e)
