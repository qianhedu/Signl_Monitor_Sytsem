import akshare as ak
import pandas as pd
import os

# 取消代理设置（以防万一）
os.environ.pop("HTTP_PROXY", None)
os.environ.pop("HTTPS_PROXY", None)

def test_stock_min():
    print("\n--- 测试股票分钟数据（600519） ---")
    try:
        # 若东方财富分钟接口失败，改用新浪来源
        # ak.stock_zh_a_minute 使用新浪数据源
        # 股票分钟代码需加前缀：sh600519
        df = ak.stock_zh_a_minute(symbol="sh600519", period="60")
        print(f"成功（新浪）! 行数: {len(df)}")
        print(df.head(2))
        print("Columns:", df.columns)
    except Exception as e:
        print(f"错误（新浪）: {e}")

    try:
        # 尝试东方财富分钟（不复权）看是否可用
        df = ak.stock_zh_a_hist_min_em(symbol="600519", period="60")
        print(f"成功（东方财富不复权）! 行数: {len(df)}")
    except Exception as e:
        print(f"错误（东方财富）: {e}")

def test_futures_min():
    print("\n--- 测试期货分钟数据（RB0） ---")
    try:
        # 支持的周期："1", "5", "15", "30", "60"
        # 注意：ak.futures_zh_minute_sina 可能使用不同的合约代码格式
        df = ak.futures_zh_minute_sina(symbol="RB0", period="60")
        print(f"成功! 行数: {len(df)}")
        print(df.head(2))
        print("Columns:", df.columns)
    except Exception as e:
        print(f"Error: {e}")

def test_hs300():
    print("\n--- 测试沪深300成分股 ---")
    try:
        # 指数成分：index_stock_cons
        df = ak.index_stock_cons(symbol="000300")
        print(f"Success! Rows: {len(df)}")
        print(df.head(2))
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_stock_min()
    test_futures_min()
    test_hs300()
