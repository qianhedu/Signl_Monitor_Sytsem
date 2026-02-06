import sys
import os
import pandas as pd
from unittest.mock import patch, MagicMock

sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

from backend.services.indicators import get_market_data

def verify_fix():
    print(f"Verifying fixes with MOCK data...", flush=True)
    
    # Mock Data for Daily (used for 240m)
    mock_daily_df = pd.DataFrame({
        "日期": ["2024-01-01", "2024-01-02"],
        "开盘": [10, 11],
        "收盘": [11, 12],
        "最高": [12, 13],
        "最低": [9, 10],
        "成交量": [1000, 2000]
    })
    
    # Mock Data for 60m (used for 120m/180m)
    # 2 days of 60m data (4 bars per day)
    # 09:30-10:30, 10:30-11:30, 13:00-14:00, 14:00-15:00
    dates = []
    base = pd.Timestamp("2024-01-01")
    times = ["10:30", "11:30", "14:00", "15:00"]
    for t in times:
        dates.append(pd.Timestamp(f"2024-01-01 {t}"))
    for t in times:
        dates.append(pd.Timestamp(f"2024-01-02 {t}"))
        
    mock_60m_df = pd.DataFrame({
        "日期": dates,
        "开盘": [10]*8,
        "收盘": [11]*8,
        "最高": [12]*8,
        "最低": [9]*8,
        "成交量": [100]*8
    })

    # 1. Verify 240m (Mocked)
    print("\n--- Verifying 240m (Mocked) ---", flush=True)
    with patch('akshare.stock_zh_a_hist', return_value=mock_daily_df) as mock_daily:
        try:
            df_240 = get_market_data("600519", period="240", adjust="qfq")
            print(f"240m Rows: {len(df_240)}", flush=True)
            if not df_240.empty:
                # Date is index now, reset to access as column
                df_reset = df_240.reset_index()
                print(df_reset.tail(2)[['date', 'open', 'close']], flush=True)
                # Check time is 15:00:00
                last_time = df_reset.iloc[-1]['date'].time()
                print(f"Last bar time: {last_time}", flush=True)
                if str(last_time) == "15:00:00":
                    print("PASS: Time aligned to 15:00:00", flush=True)
                else:
                    print(f"FAIL: Time alignment wrong: {last_time}", flush=True)
        except Exception as e:
            print(f"Error verifying 240m: {e}", flush=True)
    
    # 2. Verify 120m (Mocked)
    # This relies on stock_zh_a_hist_min_em
    print("\n--- Verifying 120m (Mocked) ---", flush=True)
    with patch('akshare.stock_zh_a_hist_min_em', return_value=mock_60m_df) as mock_min:
        try:
            # period="120" -> base="60"
            df_120 = get_market_data("600519", period="120", adjust="qfq")
            print(f"120m Rows: {len(df_120)}", flush=True)
            if not df_120.empty:
                df_reset = df_120.reset_index()
                print(df_reset[['date', 'open', 'close']], flush=True)
                # Expected:
                # 2024-01-01 11:30 (Morning)
                # 2024-01-01 15:00 (Afternoon)
                times = df_reset['date'].dt.time
                print(f"Times: {times.tolist()}", flush=True)
                if str(times.iloc[0]) == "11:30:00" and str(times.iloc[1]) == "15:00:00":
                    print("PASS: 120m Resampling Correct", flush=True)
                else:
                    print("FAIL: 120m Resampling Incorrect", flush=True)
        except Exception as e:
            print(f"Error verifying 120m: {e}", flush=True)

if __name__ == "__main__":
    verify_fix()
