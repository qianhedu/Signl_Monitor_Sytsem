import akshare as ak
import pandas as pd

try:
    print("Fetching futures data...")
    # 测试主力合约，例如 RB0（螺纹钢主力）
    df = ak.futures_zh_daily_sina(symbol="RB0")
    print("Columns:", df.columns)
    print(df.tail())
except Exception as e:
    print("Error:", e)
