
import pandas as pd
import numpy as np
import sys
import os

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.indicators import check_dkx_signal, check_ma_signal

def test_reproduce():
    # Create data
    dates = pd.date_range(start='2023-01-01', periods=20, freq='D')
    df = pd.DataFrame(index=dates)
    df['close'] = 100.0
    
    # DKX Setup
    # 0-9: DKX < MADKX (Bearish)
    # 10: Crossover (Golden Cross)
    # 11-19: DKX > MADKX (Bullish)
    
    df['dkx'] = 100.0
    df['madkx'] = 101.0 # Bearish default
    
    # Day 10 (index 10): DKX jumps to 102
    # Prev (idx 9): 100 < 101
    # Curr (idx 10): 102 > 101 -> GOLDEN CROSS
    
    df.iloc[10:, df.columns.get_loc('dkx')] = 102.0
    
    print("Data created. Crossover at index 10 (2023-01-11). Total len: 20.")
    
    # Test Lookback = 0 (Should return ALL signals or State?)
    # Based on my code, lookback=0 returns ALL signals in history (subset=df)
    # Wait, check_dkx_signal implementation:
    # if lookback == 0: subset = df
    # So it scans full history.
    signals_0 = check_dkx_signal(df, lookback=0)
    print(f"Lookback=0 signals: {len(signals_0)}")
    if signals_0:
        print(f"  Signal 0: {signals_0[0]}")
        
    # Test Lookback = 5 (Should NOT see index 10, because it's 10 days ago from index 19)
    # Index 19 is end. 
    # Subset = iloc[-6:] -> index 14 to 19.
    # Crossover is at 10. So should be empty.
    signals_5 = check_dkx_signal(df, lookback=5)
    print(f"Lookback=5 signals: {len(signals_5)} (Expected 0)")
    
    # Test Lookback = 15 (Should SEE index 10)
    # Subset = iloc[-16:] -> index 4 to 19.
    # Includes index 10.
    signals_15 = check_dkx_signal(df, lookback=15)
    print(f"Lookback=15 signals: {len(signals_15)} (Expected 1)")
    if signals_15:
        print(f"  Signal: {signals_15[0]}")

if __name__ == "__main__":
    test_reproduce()
