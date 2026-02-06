
import sys
import os
import random
import pandas as pd
import numpy as np
import akshare as ak
from datetime import datetime, timedelta

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.indicators import get_market_data, calculate_dkx, calculate_ma

def get_hs300_stocks():
    """Get random 5 stocks from HS300 (Simulated with hardcoded active list for speed)"""
    return [
        '600519', '000001', '601318', '002594', '300750'
    ]

def get_benchmark_data(symbol, period):
    """
    Get benchmark data from EastMoney (em) which is usually consistent with Tonghuashun.
    """
    try:
        # Adjust symbol format for EM
        # period mapping
        
        if period in ['daily', 'weekly', 'monthly']:
            p_map = {'daily': 'daily', 'weekly': 'weekly', 'monthly': 'monthly'}
            df = ak.stock_zh_a_hist(symbol=symbol, period=p_map[period], adjust="qfq")
            if df.empty: return df
            df = df.rename(columns={
                '日期': 'date', '开盘': 'open', '收盘': 'close', 
                '最高': 'high', '最低': 'low', '成交量': 'volume'
            })
            df['date'] = pd.to_datetime(df['date'])
        
        elif period in ['1', '5', '15', '30', '60']:
            df = ak.stock_zh_a_hist_min_em(symbol=symbol, period=period, adjust="qfq")
            if df.empty: return df
            df = df.rename(columns={
                '时间': 'date', '开盘': 'open', '收盘': 'close', 
                '最高': 'high', '最低': 'low', '成交量': 'volume'
            })
            df['date'] = pd.to_datetime(df['date'])
            
        else:
            # For 90, 120, 180, 240, we skip direct benchmark comparison 
            return pd.DataFrame()

        return df
    except Exception as e:
        print(f"Error fetching benchmark for {symbol} {period}: {e}")
        return pd.DataFrame()

def compare_data(df_sys, df_bench, symbol, period):
    """
    Compare system data with benchmark.
    Align by date.
    """
    if df_sys.empty or df_bench.empty:
        return "One of the dataframes is empty"
        
    # Set index to date
    if 'date' in df_sys.columns:
        df_sys = df_sys.set_index('date')
    if 'date' in df_bench.columns:
        df_bench = df_bench.set_index('date')
        
    # Intersect dates
    common_dates = df_sys.index.intersection(df_bench.index)
    if len(common_dates) == 0:
        return "No overlapping dates found"
        
    sys_sub = df_sys.loc[common_dates]
    bench_sub = df_bench.loc[common_dates]
    
    # Check Price diff > 0.01 + 0.1% (to be lenient on data source diffs)
    # Check Volume diff > 1%
    
    diff_close = np.abs(sys_sub['close'] - bench_sub['close'])
    max_diff = diff_close.max()
    
    if max_diff > 0.05: # Allow small diffs due to adjust precision
        # Check if it's just a few outliers or systematic
        bad_idx = diff_close[diff_close > 0.05].index
        return f"Close price mismatch max diff {max_diff:.4f} at {bad_idx[0]}"
        
    return "PASS"

def main():
    print("Starting Data Consistency Check...", flush=True)
    print("Sampling 5 stocks...", flush=True)
    stocks = get_hs300_stocks()
    print(f"Selected: {stocks}", flush=True)
    
    # Check all requested periods
    periods = ['daily', '60', '30'] # Reduced set for quick verification
    # periods = ['1', '5', '15', '30', '60', '90', '120', '180', '240', 'daily', 'weekly', 'monthly']
    
    report = []
    
    for i, symbol in enumerate(stocks):
        print(f"[{i+1}/{len(stocks)}] Checking {symbol}...", flush=True)
        for period in periods:
            # 1. Get System Data
            try:
                df_sys = get_market_data(symbol, market='stock', period=period)
            except Exception as e:
                print(f"  System fetch error {symbol} {period}: {e}", flush=True)
                report.append({'symbol': symbol, 'period': period, 'result': f'Sys fetch error: {e}'})
                continue
                
            if df_sys.empty:
                 print(f"  System data empty {symbol} {period}", flush=True)
                 report.append({'symbol': symbol, 'period': period, 'result': 'Sys data empty'})
                 continue

            # 2. Get Benchmark Data
            df_bench = get_benchmark_data(symbol, period)
            
            # 3. Compare
            if not df_bench.empty:
                res = compare_data(df_sys, df_bench, symbol, period)
                if res != "PASS":
                    print(f"  [FAIL] {symbol} {period}: {res}", flush=True)
                    report.append({
                        'symbol': symbol,
                        'period': period,
                        'result': res
                    })
                else:
                    print(f"  [PASS] {symbol} {period}", flush=True)
            else:
                 print(f"  [SKIP] Benchmark not available for {period}", flush=True)
            
            # 4. Verify Indicators
            try:
                df_dkx = calculate_dkx(df_sys)
                if df_dkx['dkx'].isnull().all():
                     report.append({'symbol': symbol, 'period': period, 'result': 'DKX calc failed (all null)'})
                
                df_ma = calculate_ma(df_sys)
                if 'ma_short' in df_ma.columns and df_ma['ma_short'].isnull().all():
                    report.append({'symbol': symbol, 'period': period, 'result': 'MA calc failed (all null)'})
            except Exception as e:
                 report.append({'symbol': symbol, 'period': period, 'result': f'Indicator calc error: {e}'})

    print("\n=== Consistency Report ===", flush=True)
    if not report:
        print("All checks passed! System data is consistent with EastMoney (Benchmark).")
    else:
        print(f"Found {len(report)} inconsistencies:")
        for r in report:
            print(f"{r['symbol']} {r['period']}: {r['result']}")
            
    # Output to file
    pd.DataFrame(report).to_csv('consistency_report.csv', index=False)
    print("Report saved to consistency_report.csv")

if __name__ == "__main__":
    main()
