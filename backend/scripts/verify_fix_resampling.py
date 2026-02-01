import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Add backend directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.backtest import resample_data

def generate_mock_data(symbol: str, days: int = 2):
    """
    Generate mock 1-minute data for a symbol based on its trading hours.
    """
    # AO: 21:00-01:00, 09:00-10:15, 10:30-11:30, 13:30-15:00
    # FG: 21:00-23:00, 09:00-10:15, 10:30-11:30, 13:30-15:00
    
    start_date = datetime(2025, 1, 1, 21, 0)
    timestamps = []
    
    current_time = start_date
    for _ in range(days):
        # Night Session
        night_end_hour = 1 if symbol == 'AO' else 23
        
        # 21:00 to Night End
        t = current_time
        while True:
            if symbol == 'AO':
                # Cross midnight
                if t.hour == 1 and t.minute == 0:
                    break
                if t.hour >= 21 or t.hour < 1:
                    timestamps.append(t)
                else:
                    break
            else:
                # FG: Ends 23:00
                if t.hour == 23 and t.minute == 0:
                    break
                timestamps.append(t)
            
            t += timedelta(minutes=1)
            
        # Move to next day 09:00
        if t.hour == 23:
            t = t.replace(hour=9, minute=0) + timedelta(days=1)
        elif t.hour == 1:
            t = t.replace(hour=9, minute=0)
            
        # Morning 1: 09:00-10:15
        end_m1 = t.replace(hour=10, minute=15)
        while t < end_m1:
            timestamps.append(t)
            t += timedelta(minutes=1)
            
        # Morning 2: 10:30-11:30
        t = t.replace(hour=10, minute=30)
        end_m2 = t.replace(hour=11, minute=30)
        while t < end_m2:
            timestamps.append(t)
            t += timedelta(minutes=1)
            
        # Afternoon: 13:30-15:00
        t = t.replace(hour=13, minute=30)
        end_aft = t.replace(hour=15, minute=0)
        while t < end_aft:
            timestamps.append(t)
            t += timedelta(minutes=1)
            
        # Prepare for next night (21:00)
        current_time = t.replace(hour=21, minute=0)
        
    # Create OHLCV data
    n = len(timestamps)
    data = {
        'open': np.random.randn(n) + 100,
        'high': np.random.randn(n) + 105,
        'low': np.random.randn(n) + 95,
        'close': np.random.randn(n) + 100,
        'volume': np.random.randint(100, 1000, n),
        'hold': np.random.randint(1000, 5000, n)
    }
    df = pd.DataFrame(data, index=timestamps)
    return df

def test_symbol(symbol: str):
    print(f"\nTesting Resampling Logic for {symbol}...")
    
    # 1. Generate 1m data
    df_1m = generate_mock_data(symbol, days=3)
    
    # 2. Resample to 30m base (mimicking API return)
    df_30m = df_1m.resample('30min', closed='left', label='right').last().dropna()
    print(f"Base 30m data count: {len(df_30m)}")
    
    # Show Night Session boundaries
    print("First 10 bars of 30m data:")
    print(df_30m.head(10).index.tolist())
    
    # 3. Apply NEW resample_data logic to 90m
    df_90m = resample_data(df_30m, '90')
    print(f"Resampled 90m data count: {len(df_90m)}")
    
    # 4. Analyze if grouping crossed sessions
    # We check if the time difference between consecutive 90m bars is unusually large
    # Wait, the best way to verify is to trace which 30m bars went into which 90m bar.
    # Since resample_data returns aggregated result, we can infer by timestamp.
    # The 'temp_ts' (index of df_90m) is the MAX timestamp of the group.
    
    # Let's verify manually for FG (Night 21:00-23:00 -> 4 bars: 21:30, 22:00, 22:30, 23:00)
    # Group 1: 21:30, 22:00, 22:30 -> Max 22:30.
    # Group 2: 23:00 -> Max 23:00.
    # Next Session starts 09:30.
    # Group 3: 09:30, 10:00, 10:15(if split) or 10:45?
    # 30m bars: 09:30, 10:00, 10:30 (spanning break 10:15-10:30?), 11:00, 11:30.
    
    print("Resulting 90m bars:")
    for ts in df_90m.index[:10]:
        print(ts)
        
    # Check specifically for the gap
    # If FG, we expect a bar at 23:00 (representing the orphan bar) or similar
    # And definitely NOT a bar that represents [23:00, 09:30, 10:00] -> Max 10:00
    
    # Detect huge gaps in the RESULTING index? No, result index is just timestamps.
    # We want to ensure no single bar "contains" a huge gap.
    # But we can't see "contained" bars in the result.
    # However, if the logic works, we should see a bar ending at 23:00 (or 01:00 for AO).
    
    has_night_end_bar = False
    for ts in df_90m.index:
        if symbol == 'FG' and ts.hour == 23 and ts.minute == 0:
            has_night_end_bar = True
        if symbol == 'AO' and ts.hour == 1 and ts.minute == 0:
            has_night_end_bar = True
            
    if has_night_end_bar:
        print(f"✅ SUCCESS: Found bar ending exactly at session close ({'23:00' if symbol=='FG' else '01:00'}). Logic preserved session boundary.")
    else:
        print(f"❌ FAILURE: Did not find bar ending at session close. It might have been merged with next morning.")

if __name__ == "__main__":
    test_symbol('FG')
    test_symbol('AO')
