import sys
import os
import pandas as pd
import numpy as np
import datetime

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.indicators import get_market_data, calculate_dkx
from services.backtest import filter_trading_hours
from services.metadata import get_trading_hours_type

def get_trading_day(ts):
    """
    Map timestamp to Trading Day.
    Logic: Shift forward by 4 hours.
    - 21:00 -> 01:00 (Next Day)
    - 02:00 -> 06:00 (Same Day)
    - 09:00 -> 13:00 (Same Day)
    - 15:00 -> 19:00 (Same Day)
    Then handle weekend: If Sat/Sun, map to Mon.
    """
    shifted = ts + pd.Timedelta(hours=4)
    # Check weekday: 0=Mon, 6=Sun
    # If Sat(5) or Sun(6), move to Mon
    if shifted.weekday() >= 5: 
        days_to_add = 7 - shifted.weekday()
        shifted += pd.Timedelta(days=days_to_add)
        
    return shifted.date()

def run_regression_test():
    symbols = ["SS0", "CJ0", "JD0"]
    results = []
    
    print("Starting Regression Test (2023-01-01 to Present)...")
    
    for symbol in symbols:
        print(f"Processing {symbol}...")
        
        # 1. Benchmark: Official Daily Data
        try:
            df_daily = get_market_data(symbol, market='futures', period='daily')
            if df_daily.empty:
                print(f"  No daily data for {symbol}")
                continue
                
            # Calculate DKX on Benchmark
            df_daily = calculate_dkx(df_daily)
        except Exception as e:
            print(f"  Error fetching daily data: {e}")
            continue
        
        # 2. New Logic: Minute Data -> Filter -> Agg -> DKX
        try:
            df_min = get_market_data(symbol, market='futures', period='60')
            if df_min.empty:
                print(f"  No minute data for {symbol}")
                continue
                
            # Filter (Includes JD Volume Adjust)
            df_min_filtered = filter_trading_hours(df_min, symbol)
            
            # Aggregate to Daily (Constructed)
            # Apply Trading Day mapping
            df_min_filtered['trading_date'] = df_min_filtered.index.map(get_trading_day)
            
            # Group by trading_date
            # Note: We must ensure we sort by time before grouping to get correct Open/Close
            df_min_filtered = df_min_filtered.sort_index()
            
            df_constructed = df_min_filtered.groupby('trading_date').agg({
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum'
            })
            
            # Restore index
            df_constructed.index.name = 'date'
            df_constructed.index = pd.to_datetime(df_constructed.index)
            
            # Calculate DKX on Constructed Daily
            df_constructed = calculate_dkx(df_constructed)
        except Exception as e:
            print(f"  Error processing new logic: {e}")
            continue
        
        # 3. Old Logic: Minute Data -> No Filter -> Simple Agg -> DKX
        try:
            df_min_old = get_market_data(symbol, market='futures', period='60')
            # Simple Date mapping (Calendar Day)
            df_min_old['trading_date'] = df_min_old.index.date 
            df_old_constructed = df_min_old.groupby('trading_date').agg({
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum'
            })
            df_old_constructed.index = pd.to_datetime(df_old_constructed.index)
            df_old_constructed = calculate_dkx(df_old_constructed)
        except Exception as e:
            print(f"  Error processing old logic: {e}")
            df_old_constructed = pd.DataFrame()
        
        # 4. Compare
        # Align dates
        common_dates = df_daily.index.intersection(df_constructed.index)
        # Filter for 2023-01-01 onwards
        start_date = pd.Timestamp("2023-01-01")
        common_dates = common_dates[common_dates >= start_date]
        
        print(f"  Comparing {len(common_dates)} days...")
        
        for date in common_dates:
            bench_dkx = df_daily.loc[date, 'dkx']
            new_dkx = df_constructed.loc[date, 'dkx']
            
            # Old might not exist
            old_dkx = np.nan
            if not df_old_constructed.empty and date in df_old_constructed.index:
                old_dkx = df_old_constructed.loc[date, 'dkx']
                
            # Error Calculation
            # abs(New - Bench) / Bench
            if pd.isna(bench_dkx) or bench_dkx == 0:
                error = 0.0
            else:
                error = abs(new_dkx - bench_dkx) / abs(bench_dkx)
            
            # Determine reason if error is high
            reason = ""
            if error >= 0.0005:
                reason = "偏差过大"
                # Check if it's due to Night Session
                # Compare Close prices
                bench_close = df_daily.loc[date, 'close']
                new_close = df_constructed.loc[date, 'close']
                if abs(new_close - bench_close) / bench_close > 0.001:
                    reason += " (收盘价不一致)"
            
            results.append({
                'symbol': symbol,
                'date': date,
                'benchmark_dkx': bench_dkx,
                'new_dkx': new_dkx,
                'old_dkx': old_dkx,
                'error': error,
                'compliant': error < 0.0005,
                'reason': reason
            })
            
    # Output
    if not results:
        print("No results generated.")
        return

    df_res = pd.DataFrame(results)
    output_path = os.path.join(os.path.dirname(__file__), 'dkx_regression_test.csv')
    df_res.to_csv(output_path, index=False)
    print(f"\nReport saved to {output_path}")
    
    # Stats
    print("\nCompliance Report:")
    for symbol in symbols:
        sub = df_res[df_res['symbol'] == symbol]
        if sub.empty:
            print(f"{symbol}: No Data")
            continue
        pass_rate = sub['compliant'].mean()
        max_error = sub['error'].max()
        avg_error = sub['error'].mean()
        print(f"{symbol}: Pass Rate {pass_rate:.1%}, Avg Error {avg_error:.6f}, Max Error {max_error:.6f}")

if __name__ == "__main__":
    run_regression_test()
