
import pandas as pd
import numpy as np
import sys
import os

# Add backend path to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

try:
    from backend.services.indicators import calculate_dkx, calculate_ma
except ImportError:
    # Try local import if running from root
    from services.indicators import calculate_dkx, calculate_ma

def generate_test_data(periods=100):
    """
    Generate synthetic OHLC data.
    """
    dates = pd.date_range(start='2024-01-01', periods=periods, freq='D')
    np.random.seed(42)
    close = 100 + np.cumsum(np.random.randn(periods))
    high = close + np.random.rand(periods) * 2
    low = close - np.random.rand(periods) * 2
    open_p = low + np.random.rand(periods) * (high - low)
    
    df = pd.DataFrame({
        'open': open_p,
        'high': high,
        'low': low,
        'close': close,
        'volume': 1000
    }, index=dates)
    return df

def verify_dkx_logic():
    print("=== Verifying DKX Logic ===")
    df = generate_test_data(50)
    
    # Run implementation
    df_calc = calculate_dkx(df.copy())
    
    # Manual Verification
    # MID = (3C + L + O + H) / 6
    mid = (3 * df['close'] + df['low'] + df['open'] + df['high']) / 6
    
    # DKX = WMA(MID, 20)
    # Weights: 1, 2, ..., 20. Sum = 210.
    # We verify the last value manually.
    # Take last 20 MID values
    if len(mid) >= 20:
        last_20_mid = mid.iloc[-20:].values
        weights = np.arange(1, 21)
        expected_dkx = np.dot(last_20_mid, weights) / 210
        
        actual_dkx = df_calc['dkx'].iloc[-1]
        
        print(f"Manual Calc DKX[-1]: {expected_dkx:.6f}")
        print(f"Code Calc DKX[-1]:   {actual_dkx:.6f}")
        
        diff = abs(expected_dkx - actual_dkx)
        if diff < 1e-9:
            print("DKX Calculation: PASS")
        else:
            print(f"DKX Calculation: FAIL (Diff: {diff})")
            
        # MADKX = SMA(DKX, 10)
        # Verify last MADKX
        # Take last 10 DKX values from df_calc
        last_10_dkx = df_calc['dkx'].iloc[-10:].values
        expected_madkx = np.mean(last_10_dkx)
        actual_madkx = df_calc['madkx'].iloc[-1]
        
        print(f"Manual Calc MADKX[-1]: {expected_madkx:.6f}")
        print(f"Code Calc MADKX[-1]:   {actual_madkx:.6f}")
        
        diff_ma = abs(expected_madkx - actual_madkx)
        if diff_ma < 1e-9:
            print("MADKX Calculation: PASS")
        else:
            print(f"MADKX Calculation: FAIL (Diff: {diff_ma})")
    else:
        print("Not enough data for DKX verification")

def verify_ma_logic():
    print("\n=== Verifying Dual MA Logic ===")
    df = generate_test_data(50)
    
    df_calc = calculate_ma(df.copy(), short_period=5, long_period=10)
    
    # Verify last value
    last_5_close = df['close'].iloc[-5:].values
    expected_ma5 = np.mean(last_5_close)
    actual_ma5 = df_calc['ma_short'].iloc[-1]
    
    print(f"Manual MA5: {expected_ma5:.6f}")
    print(f"Code MA5:   {actual_ma5:.6f}")
    
    if abs(expected_ma5 - actual_ma5) < 1e-9:
        print("MA Short Calculation: PASS")
    else:
        print("MA Short Calculation: FAIL")

if __name__ == "__main__":
    verify_dkx_logic()
    verify_ma_logic()
