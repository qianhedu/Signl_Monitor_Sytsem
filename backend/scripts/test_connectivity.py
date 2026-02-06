
import akshare as ak
import pandas as pd

def test_conn():
    print("Testing AkShare connectivity...")
    
    # 1. Test Tencent Daily (Backup for Daily)
    print("\n[1] Testing Stock Daily (Tencent)...")
    try:
        # Tencent interface usually doesn't take 'period' for daily history
        df = ak.stock_zh_a_hist_tx(symbol="sz000001", start_date="20240101", adjust="qfq")
        print(f"Successfully fetched TX daily data. Rows: {len(df)}")
        print(df.tail(2))
    except Exception as e:
        print(f"Failed to fetch TX daily data: {e}")

    # 2. Test EM Minute (Primary for Minute)
    print("\n[2] Testing Stock Minute (EM)...")
    try:
        # stock_zh_a_hist_min_em is the standard function for minute data
        df = ak.stock_zh_a_hist_min_em(symbol="000001", period="60", adjust="qfq")
        print(f"Successfully fetched EM 60m data. Rows: {len(df)}")
        print(df.tail(2))
    except AttributeError:
        print("akshare has no attribute 'stock_zh_a_hist_min_em'.")
    except Exception as e:
        print(f"Failed to fetch EM minute data: {e}")

if __name__ == "__main__":
    test_conn()
