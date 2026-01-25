import akshare as ak
import pandas as pd
import os

# Unset proxy
os.environ.pop("HTTP_PROXY", None)
os.environ.pop("HTTPS_PROXY", None)
os.environ.pop("http_proxy", None)
os.environ.pop("https_proxy", None)

print("Testing Akshare stock list (No Proxy)...")
try:
    df = ak.stock_zh_a_spot_em()
    print("Success!")
    print(df.head())
except Exception as e:
    print(f"Error: {e}")
