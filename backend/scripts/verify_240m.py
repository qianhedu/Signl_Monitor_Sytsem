
import akshare as ak
import pandas as pd
import numpy as np

def get_period_end_time(ts, period_min):
    hm = ts.hour * 60 + ts.minute
    minutes_from_open = 0
    if 570 < hm <= 690: # 9:30-11:30
        minutes_from_open = hm - 570
    elif 780 < hm <= 900: # 13:00-15:00
        minutes_from_open = 120 + (hm - 780)
    else:
        return ts
    
    import math
    bin_idx = math.ceil(minutes_from_open / int(period_min))
    bin_end_trading_min = bin_idx * int(period_min)
    
    final_hm = 0
    if bin_end_trading_min <= 120:
        final_hm = 570 + bin_end_trading_min
    else:
        final_hm = 780 + (bin_end_trading_min - 120)
        
    new_h = final_hm // 60
    new_m = final_hm % 60
    return ts.replace(hour=new_h, minute=new_m, second=0)

def verify_240m():
    symbol = "sh600519"
    print(f"Verifying 240m for {symbol}...", flush=True)
    
    # 1. Fetch Daily Data (The Truth for 240m)
    print("Fetching Daily data...", flush=True)
    df_daily = ak.stock_zh_a_hist(symbol="600519", period="daily", adjust="qfq")
    df_daily['日期'] = pd.to_datetime(df_daily['日期'])
    # Rename for comparison
    df_daily = df_daily.rename(columns={'日期': 'date', '最高': 'high', '最低': 'low', '收盘': 'close', '开盘': 'open'})
    df_daily = df_daily.set_index('date').sort_index()
    last_5_daily = df_daily.tail(5)
    print("Last 5 Daily:\n", last_5_daily[['open', 'high', 'low', 'close']], flush=True)

    # 2. Fetch 60m Data and Resample (Current Implementation)
    print("\nFetching 60m data (Sina)...", flush=True)
    try:
        # Check if adjust param is supported or defaulted
        # Sina interface usually returns unadjusted
        df_60m = ak.stock_zh_a_minute(symbol=symbol, period="60") # adjust=?
        df_60m = df_60m.rename(columns={"day": "date"})
        df_60m['date'] = pd.to_datetime(df_60m['date'])
        df_60m.set_index('date', inplace=True)
        
        # ... logic ...
        # Apply logic
        unique_times = pd.Series(df_60m.index.time).unique()
        time_map = {}
        for t in unique_times:
            dummy_dt = pd.Timestamp(year=2000, month=1, day=1, hour=t.hour, minute=t.minute)
            mapped_dt = get_period_end_time(dummy_dt, "240")
            time_map[t] = mapped_dt.time()
            
        new_dates = []
        for idx in df_60m.index:
            t = idx.time()
            mapped_time = time_map.get(t, t)
            new_dates.append(idx.replace(hour=mapped_time.hour, minute=mapped_time.minute))
        
        df_60m['resample_date'] = new_dates
        df_res = df_60m.groupby('resample_date').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        })
        
        df_res.index = df_res.index.normalize()
        
        print("\nLast 5 Resampled 240m (Sina 60m Unadjusted):\n", df_res.tail(5)[['open', 'high', 'low', 'close']], flush=True)
        
        common_dates = df_res.index.intersection(df_daily.index)
        diff = df_res.loc[common_dates] - df_daily.loc[common_dates]
        max_diff = diff[['open', 'high', 'low', 'close']].abs().max().max()
        print(f"\nMax Price Difference (Unadjusted 60m vs Adjusted Daily): {max_diff}", flush=True)

    except Exception as e:
        print(f"Error in 60m fetch: {e}", flush=True)
        
    # 3. Fetch Adjusted 60m from EM (Proposed Fix for 90/120/180)
    print("\nFetching 60m data (EM QFQ)...", flush=True)
    try:
        # EM symbol needs no prefix for code, but function might need it? 
        # ak.stock_zh_a_hist_min_em(symbol="600519", period="60", adjust="qfq")
        df_60m_adj = ak.stock_zh_a_hist_min_em(symbol="600519", period="60", adjust="qfq")
        df_60m_adj = df_60m_adj.rename(columns={"日期": "date", "开盘": "open", "最高": "high", "最低": "low", "收盘": "close", "成交量": "volume"})
        df_60m_adj['date'] = pd.to_datetime(df_60m_adj['date'])
        df_60m_adj.set_index('date', inplace=True)
        
        # Resample EM
        new_dates_em = []
        for idx in df_60m_adj.index:
            t = idx.time()
            # logic for EM times (usually end time)
            # EM 60m times: 10:30, 11:30, 14:00, 15:00
            mapped_dt = get_period_end_time(pd.Timestamp(year=2000, month=1, day=1, hour=t.hour, minute=t.minute), "240")
            new_dates_em.append(idx.replace(hour=mapped_dt.hour, minute=mapped_dt.minute))
            
        df_60m_adj['resample_date'] = new_dates_em
        df_res_adj = df_60m_adj.groupby('resample_date').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        })
        df_res_adj.index = df_res_adj.index.normalize()
        
        print("\nLast 5 Resampled 240m (EM 60m Adjusted):\n", df_res_adj.tail(5)[['open', 'high', 'low', 'close']], flush=True)
        
        common_dates_adj = df_res_adj.index.intersection(df_daily.index)
        diff_adj = df_res_adj.loc[common_dates_adj] - df_daily.loc[common_dates_adj]
        max_diff_adj = diff_adj[['open', 'high', 'low', 'close']].abs().max().max()
        print(f"\nMax Price Difference (Adjusted 60m vs Adjusted Daily): {max_diff_adj}", flush=True)
        
    except Exception as e:
        print(f"Error in EM 60m fetch: {e}", flush=True)

if __name__ == "__main__":
    verify_240m()
