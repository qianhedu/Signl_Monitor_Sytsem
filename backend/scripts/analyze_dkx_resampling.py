import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def generate_mock_data(symbol: str, days: int = 5):
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
                    break # Should not happen if logic correct
            else:
                # FG: Ends 23:00
                if t.hour == 23 and t.minute == 0:
                    break
                timestamps.append(t)
            
            t += timedelta(minutes=1)
            
        # Move to next day 09:00
        # If AO, current_time was 21:00 prev day. t is 01:00 today.
        # If FG, t is 23:00 prev day.
        
        # Calculate next day 09:00
        # For AO (t is 01:00), next 09:00 is same day.
        # For FG (t is 23:00), next 09:00 is next day.
        
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
        
    df = pd.DataFrame({'close': np.random.randn(len(timestamps)) + 100}, index=timestamps)
    return df

def mock_resample_logic(df_30m, target_min):
    """
    Mimic logic in backend/services/backtest.py:resample_data
    """
    base_min = 30
    group_size = target_min // base_min
    
    df_reset = df_30m.copy()
    df_reset['temp_ts'] = df_reset.index
    df_reset = df_reset.reset_index(drop=True)
    df_reset['group_id'] = df_reset.index // group_size
    
    agg_dict = {
        'close': 'last',
        'temp_ts': 'max'
    }
    
    resampled = df_reset.groupby('group_id').agg(agg_dict)
    resampled.set_index('temp_ts', inplace=True)
    resampled.index.name = 'date'
    return resampled

def analyze_symbol(symbol):
    print(f"\nAnalyzing {symbol}...")
    df_1m = generate_mock_data(symbol, days=3)
    
    # Resample to 30m base (simulating API return)
    # Using standard time-based resampling for base data
    df_30m = df_1m.resample('30min', closed='left', label='right').last().dropna()
    
    print(f"Total 30min bars over 3 days: {len(df_30m)}")
    print("First 5 30min bars:")
    print(df_30m.head().index.tolist())
    
    # Resample to 90m using count logic
    df_90m = mock_resample_logic(df_30m, 90)
    
    print(f"Total 90min bars: {len(df_90m)}")
    print("First 5 90min bars (Count-Based):")
    for ts in df_90m.head().index:
        print(ts)
        
    # Check alignment with session end
    # Night end for AO is 01:00. FG is 23:00.
    # Check if any 90m bar crosses session boundaries (e.g. contains 23:00 and 09:00)
    # Since we only have 'max' timestamp, we can check if the timestamp is "weird"
    
    # Logic: 
    # AO: 21:00-01:00 (4h, 8x30m). 90m=3x30m.
    # Groups: [0,1,2], [3,4,5], [6,7, 8(next day 09:30)]
    # Bar 1: 22:30. Bar 2: 00:00. Bar 3: 09:30 (contains 00:00-01:00 and 09:00-09:30?!)
    
    # Let's inspect the groups directly
    base_min = 30
    group_size = 3
    df_reset = df_30m.reset_index()
    df_reset['group_id'] = df_reset.index // group_size
    
    print("\nDetailed Grouping Analysis (First 4 Groups):")
    for gid in range(4):
        group = df_reset[df_reset['group_id'] == gid]
        # Column name is 'index' because original index had no name
        col_name = 'index' if 'index' in group.columns else 'date'
        print(f"Group {gid}: {group[col_name].tolist()}")
        
        # Check for cross-day gap
        dates = group[col_name].tolist()
        if len(dates) > 1:
            diff = dates[-1] - dates[0]
            # If diff > 90 min (plus tolerance), it implies a gap was bridged
            if diff.total_seconds() > 90 * 60 + 3600: # > 1.5h + buffer
                print(f"  [WARNING] Cross-Session Gap Detected! Diff: {diff}")

if __name__ == "__main__":
    analyze_symbol('FG')
    analyze_symbol('AO')
