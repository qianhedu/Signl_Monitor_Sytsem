
import sys
import os
import pandas as pd
import numpy as np

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.indicators import get_market_data, calculate_dkx, check_dkx_signal, calculate_ma, check_ma_signal

def scan_real_stocks():
    # Popular stocks that likely have some activity
    symbols = ['600519', '000001', '300750', '601318', '002594'] 
    lookback = 20
    
    print(f"Scanning {len(symbols)} stocks with lookback={lookback}...")
    
    found_any = False
    
    for symbol in symbols:
        print(f"\nChecking {symbol}...")
        try:
            df = get_market_data(symbol, period='daily')
            if df.empty:
                print("  No data.")
                continue
                
            print(f"  Data fetched: {len(df)} rows. Last date: {df.index[-1]}")
            
            # 1. Check DKX
            df = calculate_dkx(df)
            dkx_signals = check_dkx_signal(df, lookback=lookback)
            print(f"  DKX Signals found: {len(dkx_signals)}")
            for s in dkx_signals:
                print(f"    -> DKX {s['signal']} at {s['date']}")
                found_any = True
                
            # 2. Check MA
            df = calculate_ma(df)
            ma_signals = check_ma_signal(df, lookback=lookback)
            print(f"  MA Signals found: {len(ma_signals)}")
            for s in ma_signals:
                print(f"    -> MA {s['signal']} at {s['date']}")
                found_any = True

        except Exception as e:
            print(f"  Error: {e}")
            
    if not found_any:
        print("\nWARNING: No signals found in any stock. This might indicate a logic issue (or just market conditions).")
    else:
        print("\nSuccess: Found signals.")

if __name__ == "__main__":
    scan_real_stocks()
