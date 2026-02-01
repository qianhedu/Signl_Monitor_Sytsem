
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def simulate_resampling(df, period_min):
    """
    Simulate the new proposed resampling logic.
    """
    df = df.copy()
    if 'temp_ts' not in df.columns:
        df['temp_ts'] = df.index

    # 1. Trading Date Grouping (Shift -18h)
    # 21:00 previous day -> 03:00 current day
    # 09:00 current day -> 15:00 current day
    # All fall within same "Date"
    df['trading_date'] = (df.index - timedelta(hours=18)).date
    
    # 2. Calculate Duration
    # Use diff, but cap at base period (e.g. 30min)
    # Assume base period is the mode of diffs
    time_diffs = df.index.to_series().diff().dt.total_seconds() / 60
    base_period = int(time_diffs.mode()[0]) if len(df) > 1 else 30
    
    print(f"Detected Base Period: {base_period} min")
    
    # Fill first NaN
    time_diffs = time_diffs.fillna(base_period)
    
    # Cap durations (handle overnight gaps)
    # If diff > base_period * 2, assume it's just one bar of duration
    durations = time_diffs.apply(lambda x: base_period if x > base_period * 1.5 else x)
    df['duration'] = durations
    
    # 3. Cumulative Sum within Trading Date
    df['cum_mins'] = df.groupby('trading_date')['duration'].cumsum()
    
    # 4. Group ID
    # We want groups of 'period_min'
    # 0-180 -> Group 0
    # 180-360 -> Group 1
    # Note: If cum_mins is [30, 60, ..., 180], 180 // 180 = 1.
    # We want 180 to be in Group 0?
    # Usually: Bar closes at 180.
    # So strictly: (cum_mins - epsilon) // period
    df['group_id'] = ((df['cum_mins'] - 0.1) // period_min).astype(int)
    
    # 5. Resample
    agg_dict = {
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum',
        'temp_ts': 'max',
        'cum_mins': 'last'
    }
    
    resampled = df.groupby(['trading_date', 'group_id']).agg(agg_dict)
    return resampled

def generate_mock_data(symbol, start_str, days=2, base_freq='30min'):
    """
    Generate mock data for testing.
    LC: 09:00-11:30, 13:30-15:00
    SS: 21:00-01:00, 09:00-10:15...
    """
    dates = pd.date_range(start=start_str, periods=days*24*2, freq=base_freq) # Excess range
    data = []
    
    for date in dates:
        t = date.time()
        # LC Logic
        if symbol == 'LC':
            # 09:00-11:30 (Ends 09:30, 10:00, 10:30, 11:00, 11:30)
            if (t > datetime.strptime('09:00', '%H:%M').time() and t <= datetime.strptime('11:30', '%H:%M').time()) or \
               (t > datetime.strptime('13:30', '%H:%M').time() and t <= datetime.strptime('15:00', '%H:%M').time()):
                data.append(date)
                
        # SS Logic
        elif symbol == 'SS':
            # Night: 21:30... 00:00, 00:30, 01:00
            # Day: 09:30... 15:00
            is_night = (t > datetime.strptime('21:00', '%H:%M').time()) or (t <= datetime.strptime('01:00', '%H:%M').time())
            is_day = (t > datetime.strptime('09:00', '%H:%M').time() and t <= datetime.strptime('11:30', '%H:%M').time()) or \
                     (t > datetime.strptime('13:30', '%H:%M').time() and t <= datetime.strptime('15:00', '%H:%M').time())
            
            if is_night or is_day:
                data.append(date)

    df = pd.DataFrame(index=data)
    df['open'] = 100
    df['high'] = 105
    df['low'] = 95
    df['close'] = 100
    df['volume'] = 1000
    df.index.name = 'date'
    df = df.sort_index()
    return df

# Test LC (Pure Day) with 180min
print("--- Testing LC (Pure Day) 180min ---")
df_lc = generate_mock_data('LC', '2024-01-01', base_freq='30min')
res_lc = simulate_resampling(df_lc, 180)
print(res_lc[['temp_ts', 'cum_mins']])

# Test SS (Night 01:00) with 180min
print("\n--- Testing SS (Night 01:00) 180min ---")
df_ss = generate_mock_data('SS', '2024-01-01', base_freq='30min')
res_ss = simulate_resampling(df_ss, 180)
print(res_ss[['temp_ts', 'cum_mins']])
