
import pandas as pd
import numpy as np

def test_filter():
    # Create naive dataframe
    dates = pd.date_range(start='2023-01-01', end='2023-01-10', freq='D')
    df = pd.DataFrame({'val': np.arange(len(dates))}, index=dates)
    
    start_time = '2023-01-02T00:00:00.000Z'
    end_time = '2023-01-05T00:00:00.000Z'
    
    print(f"Index tz: {df.index.tz}")
    print(f"Start: {start_time}")
    
    # Simulate logic
    try:
        ts_start = pd.to_datetime(start_time)
        ts_end = pd.to_datetime(end_time)
        
        index_tz = df.index.tz
        
        if index_tz is None:
            if ts_start.tzinfo is not None:
                ts_start = ts_start.tz_localize(None)
                ts_end = ts_end.tz_localize(None)
        else:
            if ts_start.tzinfo is None:
                ts_start = ts_start.tz_localize(index_tz)
                ts_end = ts_end.tz_localize(index_tz)
            else:
                ts_start = ts_start.tz_convert(index_tz)
                ts_end = ts_end.tz_convert(index_tz)
                
        mask = (df.index >= ts_start) & (df.index <= ts_end)
        filtered = df.loc[mask]
        print(f"Filtered len: {len(filtered)}")
        print(filtered)
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_filter()
