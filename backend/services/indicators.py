import akshare as ak
import pandas as pd
import numpy as np
from typing import List, Optional

def get_market_data(symbol: str, market: str = "stock", period: str = "daily", adjust: str = "qfq") -> pd.DataFrame:
    """
    使用 akshare 获取市场数据。
    market: "stock" (股票) 或 "futures" (期货)
    period: "daily", "weekly", "monthly", "60", "30", "15", "5"
    """
    try:
        df = pd.DataFrame()
        
        # 标准化周期
        # Stock Minutes: period="60"
        # Futures Minutes: period="60"
        # Stock Daily: period="daily"
        
        is_minute = period in ["240", "180", "120", "90", "60", "30", "15", "5", "1"]

        if market == "stock":
            if is_minute:
                # Map long periods to base periods for resampling
                base_period = period
                need_resample = False
                
                if period in ["240", "180", "120", "90"]:
                    base_period = "60" # Use 60m as base for better performance than 1m
                    need_resample = True
                
                # 使用新浪接口获取分钟数据 (东方财富接口可能不稳定)
                # 代码需要前缀: 600519 -> sh600519, 000001 -> sz000001
                prefix = ""
                if symbol.startswith("6"):
                    prefix = "sh"
                elif symbol.startswith("0") or symbol.startswith("3"):
                    prefix = "sz"
                elif symbol.startswith("4") or symbol.startswith("8"):
                    prefix = "bj" 
                
                sina_symbol = f"{prefix}{symbol}"
                df = ak.stock_zh_a_minute(symbol=sina_symbol, period=base_period)
                if not df.empty:
                    df = df.rename(columns={
                        "day": "date",
                        "open": "open",
                        "high": "high",
                        "low": "low",
                        "close": "close",
                        "volume": "volume"
                    })
                    
                    if need_resample:
                        df['date'] = pd.to_datetime(df['date'])
                        df.set_index('date', inplace=True)
                        
                        # Custom resampling for stocks to match THS logic
                        # THS Logic for A-shares (09:30-11:30, 13:00-15:00):
                        # 120m: [09:30-11:30], [13:00-15:00] (2 bars/day)
                        # 240m: [09:30-15:00] (1 bar/day)
                        # 90m: Not standard, but usually splits available time.
                        # We use a mapping approach based on time.
                        
                        def get_period_end_time(ts, period_min):
                            # Convert time to minutes from 09:30
                            # Morning: 09:30 (0) to 11:30 (120)
                            # Afternoon: 13:00 (120 virtual) to 15:00 (240 virtual)
                            
                            hm = ts.hour * 60 + ts.minute
                            
                            # Normalize time to "trading minutes from 9:30"
                            # 9:30 = 570m
                            # 11:30 = 690m
                            # 13:00 = 780m
                            # 15:00 = 900m
                            
                            minutes_from_open = 0
                            if 570 < hm <= 690: # Morning
                                minutes_from_open = hm - 570
                            elif 780 < hm <= 900: # Afternoon
                                minutes_from_open = 120 + (hm - 780)
                            else:
                                # Out of bounds or exact open (shouldn't happen with closed='right')
                                return ts
                            
                            # Determine bin
                            # period_min e.g. 120
                            # bin_index = ceil(minutes_from_open / period_min)
                            import math
                            bin_idx = math.ceil(minutes_from_open / int(period_min))
                            
                            # Bin end in trading minutes
                            bin_end_trading_min = bin_idx * int(period_min)
                            
                            # Convert back to wall clock time
                            # If bin_end <= 120: Morning
                            # If bin_end > 120: Afternoon
                            
                            final_hm = 0
                            if bin_end_trading_min <= 120:
                                final_hm = 570 + bin_end_trading_min
                            else:
                                final_hm = 780 + (bin_end_trading_min - 120)
                                
                            # Construct new timestamp
                            new_h = final_hm // 60
                            new_m = final_hm % 60
                            
                            return ts.replace(hour=new_h, minute=new_m, second=0)

                        # Apply mapping
                        # Note: Vectorizing this would be faster, but apply is easier for logic
                        # Only apply to rows.
                        
                        # Optimization: Create a map for unique times
                        unique_times = pd.Series(df.index.time).unique()
                        time_map = {}
                        for t in unique_times:
                            # Create a dummy datetime to use the function
                            dummy_dt = pd.Timestamp(year=2000, month=1, day=1, hour=t.hour, minute=t.minute)
                            mapped_dt = get_period_end_time(dummy_dt, period)
                            time_map[t] = mapped_dt.time()
                            
                        # Assign new time
                        # We need to preserve the Date part
                        
                        new_dates = []
                        for idx in df.index:
                            t = idx.time()
                            mapped_time = time_map.get(t, t)
                            new_dates.append(idx.replace(hour=mapped_time.hour, minute=mapped_time.minute))
                            
                        df['resample_date'] = new_dates
                        
                        # Group by resample_date
                        ohlc_dict = {
                            'open': 'first',
                            'high': 'max',
                            'low': 'min',
                            'close': 'last',
                            'volume': 'sum'
                        }
                        
                        df_res = df.groupby('resample_date').agg(ohlc_dict).dropna()
                        df_res.index.name = 'date'
                        df = df_res.reset_index()
            else:
                # stock_zh_a_hist 支持日/周/月
                try:
                    df = ak.stock_zh_a_hist(symbol=symbol, period=period, adjust=adjust)
                except Exception as e:
                    print(f"Error fetching data for {symbol}: {e}")
                    # 降级方案：尝试获取分钟数据并重采样为日线
                    if period == 'daily':
                        print("Attempting fallback to Sina minute data resampled to daily...")
                        try:
                            prefix = "sh" if symbol.startswith("6") else "sz"
                            if symbol.startswith("4") or symbol.startswith("8"): prefix = "bj"
                            sina_symbol = f"{prefix}{symbol}"
                            df_min = ak.stock_zh_a_minute(symbol=sina_symbol, period="60")
                            if not df_min.empty:
                                df_min['day'] = pd.to_datetime(df_min['day'])
                                df_min.set_index('day', inplace=True)
                                df = df_min.resample('D').agg({
                                    'open': 'first',
                                    'high': 'max',
                                    'low': 'min',
                                    'close': 'last',
                                    'volume': 'sum'
                                }).dropna()
                                df = df.reset_index()
                                df = df.rename(columns={'day': '日期', 'open': '开盘', 'high': '最高', 'low': '最低', 'close': '收盘', 'volume': '成交量'})
                        except Exception as e2:
                            print(f"Fallback failed: {e2}")
                            
                if not df.empty:
                    df = df.rename(columns={
                        "日期": "date",
                        "开盘": "open",
                        "收盘": "close",
                        "最高": "high",
                        "最低": "low",
                        "成交量": "volume"
                    })
                
        elif market == "futures":
            if period in ["240", "180", "120", "90"]:
                # Custom resampling for futures long intraday
                base_period = "60"
                multiplier = 1
                if period == "120": multiplier = 2
                elif period == "180": multiplier = 3
                elif period == "240": multiplier = 4
                elif period == "90": 
                    base_period = "30"
                    multiplier = 3
                
                try:
                    df = ak.futures_zh_minute_sina(symbol=symbol, period=base_period)
                    if not df.empty:
                        df = df.rename(columns={
                            "datetime": "date",
                            "open": "open",
                            "high": "high",
                            "low": "low",
                            "close": "close",
                            "volume": "volume",
                            "hold": "hold"
                        })
                        
                        # Resample using row-based aggregation (simplest approximation for continuous contracts)
                        df['date'] = pd.to_datetime(df['date'])
                        df.sort_values('date', inplace=True)
                        df.reset_index(drop=True, inplace=True)
                        
                        agg_dict = {
                            'date': 'last',
                            'open': 'first',
                            'high': 'max',
                            'low': 'min',
                            'close': 'last',
                            'volume': 'sum'
                        }
                        if 'hold' in df.columns:
                            agg_dict['hold'] = 'last'
                            
                        # Group every N rows
                        group_key = df.index // multiplier
                        df = df.groupby(group_key).agg(agg_dict)
                        df.reset_index(drop=True, inplace=True)
                except Exception as e:
                    print(f"Error fetching/resampling futures data for {symbol} {period}: {e}")
                    df = pd.DataFrame()

            elif is_minute:
                # 期货分钟数据
                try:
                    df = ak.futures_zh_minute_sina(symbol=symbol, period=period)
                    if not df.empty:
                        df = df.rename(columns={
                            "datetime": "date",
                            "open": "open",
                            "high": "high",
                            "low": "low",
                            "close": "close",
                            "volume": "volume",
                            "hold": "hold"
                        })
                except Exception as e:
                    print(f"Error fetching futures minute data: {e}")
                    df = pd.DataFrame()
            else:
                # 期货日线数据 (futures_zh_daily_sina)
                try:
                    df = ak.futures_zh_daily_sina(symbol=symbol)
                    if not df.empty:
                        df = df.rename(columns={
                            "date": "date",
                            "日期": "date",
                            "open": "open", "开盘价": "open",
                            "high": "high", "最高价": "high",
                            "low": "low", "最低价": "low",
                            "close": "close", "收盘价": "close",
                            "volume": "volume", "成交量": "volume",
                            "hold": "hold", "持仓量": "hold"
                        })
                        
                        df['date'] = pd.to_datetime(df['date'])
                        
                        if period == "weekly":
                            df.set_index('date', inplace=True)
                            agg_dict = {
                                'open': 'first',
                                'high': 'max',
                                'low': 'min',
                                'close': 'last',
                                'volume': 'sum'
                            }
                            if 'hold' in df.columns: agg_dict['hold'] = 'last'
                            df = df.resample('W').agg(agg_dict).dropna().reset_index()
                        elif period == "monthly":
                            df.set_index('date', inplace=True)
                            agg_dict = {
                                'open': 'first',
                                'high': 'max',
                                'low': 'min',
                                'close': 'last',
                                'volume': 'sum'
                            }
                            if 'hold' in df.columns: agg_dict['hold'] = 'last'
                            df = df.resample('ME').agg(agg_dict).dropna().reset_index()
                except Exception as e:
                    print(f"Error fetching futures daily data: {e}")
                    df = pd.DataFrame()
        
        if df.empty:
            return pd.DataFrame()
            
        # 确保 date 列为 datetime 类型
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        # Ensure index is sorted for reliable slicing
        df.sort_index(inplace=True)
        
        # 确保数值列类型正确
        cols = ['open', 'close', 'high', 'low']
        for col in cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
                
        return df
    except Exception as e:
        print(f"Error fetching data for {symbol}: {e}")
        return pd.DataFrame()

def calculate_dkx(df: pd.DataFrame) -> pd.DataFrame:
    """
    计算 DKX (多空线) 指标。
    
    该指标算法参考了同花顺 (THS) 等主流行情软件的计算逻辑，用于判断中长期趋势。
    
    公式详解:
    1. MID (中间价): 
       MID = (3 * Close + Low + Open + High) / 6
       该公式加大了收盘价的权重 (3倍)，同时考虑了开盘、最高、最低价。
       
    2. DKX (多空线 - 加权移动平均):
       DKX 是 MID 的 20 周期加权移动平均 (WMA)。
       计算公式:
       DKX = (20 * MID(t) + 19 * MID(t-1) + ... + 1 * MID(t-19)) / 210
       其中分母 210 为权重之和 (1+2+...+20)。
       此算法赋予近期价格更大的权重，使其对价格变化更敏感。
       
    3. MADKX (信号线):
       MADKX 是 DKX 的 10 周期简单移动平均 (SMA)。
       MADKX = MA(DKX, 10)
       
    交易时段与数据源说明:
    - 对于 180 分钟等特殊周期，传入本函数的 DataFrame 必须已经过正确的重采样 (Resampling) 处理。
    - 重采样逻辑应确保：
      a) 纯日盘品种 (如 LC): 09:00-11:30 (150m) + 13:30-14:00 (30m) 组成第一根 180m K线。
      b) 夜盘品种 (如 SS): 夜盘数据 (21:00起) 必须正确归入次日交易日，避免跨日错误。
      c) 均线计算基于重采样后的 Close/High/Low/Open。
    """
    if df.empty or len(df) < 20:
        return df

    # 1. 计算 MID (中间价)
    # 权重分布: 收盘价(3), 最低价(1), 开盘价(1), 最高价(1)
    mid = (3 * df['close'] + df['low'] + df['open'] + df['high']) / 6
    
    # 2. 计算 DKX (20周期加权移动平均)
    # 构造权重数组: [1, 2, ..., 20]
    # 注意: rolling apply 时，传入的数组 x 是 [t-19, ..., t]，即 x[-1] 是当前时刻 t
    # 因此我们需要权重数组 w_asc = [1, 2, ..., 20]，使得 x[-1]*20 + x[-2]*19 ...
    weights_asc = np.arange(1, 21) # [1, 2, ..., 20]
    sum_weights = np.sum(weights_asc) # 210 (常数)
    
    # 使用 rolling().apply() 进行加权求和
    # raw=True 提升性能，直接操作 numpy 数组
    df['dkx'] = mid.rolling(window=20).apply(
        lambda x: np.dot(x, weights_asc) / sum_weights, 
        raw=True
    )
    
    # 3. 计算 MADKX (DKX 的 10 周期简单移动平均)
    df['madkx'] = df['dkx'].rolling(window=10).mean()
    
    return df

def check_dkx_signal(df: pd.DataFrame, lookback: int = 5, start_time: Optional[str] = None, end_time: Optional[str] = None) -> List[dict]:
    """
    Check for Golden Cross (DKX crosses above MADKX) or Dead Cross.
    Returns list of signals within lookback period or specified time range.
    """
    if 'dkx' not in df.columns or df['dkx'].isnull().all():
        return []

    subset = pd.DataFrame()
    start_idx = 0

    if start_time and end_time:
        # Filter by time range, but ensure we have 1 extra row before for crossover check
        # Use label-based slicing which is more robust than direct comparison
        try:
            # Ensure index is datetime type
            if not isinstance(df.index, pd.DatetimeIndex):
                df.index = pd.to_datetime(df.index)
            
            # Sort index to ensure slicing works
            df.sort_index(inplace=True)
            
            # 1. Align Timezones for filtering
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
            
            # 2. Find subset using boolean mask (more robust than loc slicing for mixed types)
            mask = (df.index >= ts_start) & (df.index <= ts_end)
            # We need to find the range indices to extend backwards by 1
            # So we can't just return df[mask] because we need the previous row
            
            # Find the integer indices of the mask
            # valid_indices = np.where(mask)[0]
            # if len(valid_indices) == 0: return []
            # start_idx = max(0, valid_indices[0] - 1)
            # end_idx = valid_indices[-1] + 1
            # subset = df.iloc[start_idx:end_idx]
            
            # Let's stick to the previous logic but use robust finding
            temp_subset = df.loc[mask]
            
            if temp_subset.empty:
                return []
                
            first_date = temp_subset.index[0]
            last_date = temp_subset.index[-1]
            
            # Find integer locations
            loc_start = df.index.get_loc(first_date)
            if isinstance(loc_start, slice): loc_start = loc_start.start
            
            loc_end = df.index.get_loc(last_date)
            if isinstance(loc_end, slice): loc_end = loc_end.stop - 1 # get_loc slice stop is exclusive? No, get_loc returns slice of matches.
            # If unique index, get_loc returns int.
            
            start_slice = max(0, loc_start - 1)
            # For end_slice, we want to include the last matching element.
            # iloc slice end is exclusive. So we need loc_end + 1.
            if isinstance(loc_end, slice):
                 # If slice, stop is exclusive, so it points to next.
                 end_slice = loc_end.stop
            else:
                 end_slice = loc_end + 1
                
            subset = df.iloc[start_slice:end_slice]
            
        except Exception as e:
            print(f"Error in check_dkx_signal time filtering: {e}")
            return []
        
    else:
        # Use lookback
        # Handle negative lookback by taking absolute value
        lb = abs(lookback)
        if lb == 0:
            # If lookback is 0, check the entire available history
            subset = df
        else:
            subset = df.iloc[-lb-1:]
    
    if len(subset) < 2:
        return []

    signals = []

    # Iterate to find crossover
    # We check if relationship changed from previous day to current day
    for i in range(1, len(subset)):
        prev = subset.iloc[i-1]
        curr = subset.iloc[i]
        
        # Calculate offset
        try:
            # Use get_loc on the original df to find the absolute position
            curr_idx = df.index.get_loc(curr.name)
            if isinstance(curr_idx, slice): 
                # If slice (duplicate index), take the last one
                curr_idx = curr_idx.stop - 1
            offset = len(df) - 1 - curr_idx
        except:
            offset = None
        
        # Golden Cross: Prev DKX < Prev MADKX AND Curr DKX > Curr MADKX
        if prev['dkx'] < prev['madkx'] and curr['dkx'] > curr['madkx']:
            signals.append({
                "signal": "BUY",
                "date": curr.name.strftime("%Y-%m-%d %H:%M:%S"),
                "price": curr['close'],
                "dkx": curr['dkx'],
                "madkx": curr['madkx'],
                "offset": offset
            })
        
        # Dead Cross: Prev DKX > Prev MADKX AND Curr DKX < Curr MADKX
        elif prev['dkx'] > prev['madkx'] and curr['dkx'] < curr['madkx']:
             signals.append({
                "signal": "SELL",
                "date": curr.name.strftime("%Y-%m-%d %H:%M:%S"),
                "price": curr['close'],
                "dkx": curr['dkx'],
                "madkx": curr['madkx'],
                "offset": offset
            })
            
    # If lookback is 0 and no time range specified, we only return the latest signal
    # REVISED: We return ALL signals here. Filtering for "latest only" when lookback=0 
    # should be done in the caller (API handler) if desired, so that chart generation 
    # (which also uses lookback=0) can still get all signals.
    return signals

def calculate_ma(df: pd.DataFrame, short_period: int = 5, long_period: int = 10) -> pd.DataFrame:
    """
    Calculate Dual Moving Average.
    """
    if df.empty:
        return df
        
    df['ma_short'] = df['close'].rolling(window=short_period).mean()
    df['ma_long'] = df['close'].rolling(window=long_period).mean()
    
    return df

def check_ma_signal(df: pd.DataFrame, lookback: int = 5, start_time: Optional[str] = None, end_time: Optional[str] = None) -> List[dict]:
    """
    Check for MA Golden Cross / Dead Cross.
    """
    if 'ma_short' not in df.columns or df['ma_short'].isnull().all():
        return []

    subset = pd.DataFrame()
    
    if start_time and end_time:
         # Filter by time range, but ensure we have 1 extra row before for crossover check
        try:
            # Ensure index is datetime type
            if not isinstance(df.index, pd.DatetimeIndex):
                df.index = pd.to_datetime(df.index)
            
            # Sort index to ensure slicing works
            df.sort_index(inplace=True)

            # 1. Align Timezones for filtering
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
            
            # 2. Find subset using boolean mask (more robust than loc slicing for mixed types)
            mask = (df.index >= ts_start) & (df.index <= ts_end)
            
            # Let's stick to the previous logic but use robust finding
            temp_subset = df.loc[mask]

            if temp_subset.empty:
                return []
            
            first_date = temp_subset.index[0]
            last_date = temp_subset.index[-1]
            
            # Find integer locations
            loc_start = df.index.get_loc(first_date)
            if isinstance(loc_start, slice): loc_start = loc_start.start
            
            loc_end = df.index.get_loc(last_date)
            if isinstance(loc_end, slice): loc_end = loc_end.stop - 1 
            
            start_slice = max(0, loc_start - 1)
            
            if isinstance(loc_end, slice):
                 end_slice = loc_end.stop
            else:
                 end_slice = loc_end + 1
                
            subset = df.iloc[start_slice:end_slice]
        except Exception as e:
            print(f"Error in check_ma_signal time filtering: {e}")
            return []
    else:
        # Handle negative lookback
        lb = abs(lookback)
        if lb == 0:
            subset = df
        else:
            # Ensure at least 1 row + 1 prev row
            lb = max(1, lb)
            subset = df.iloc[-lb-1:]  
        
    if len(subset) < 2:
        return []

    signals = []

    for i in range(1, len(subset)):
        prev = subset.iloc[i-1]
        curr = subset.iloc[i]
        
        # Calculate offset
        try:
            curr_idx = df.index.get_loc(curr.name)
            if isinstance(curr_idx, slice): 
                curr_idx = curr_idx.stop - 1
            offset = len(df) - 1 - curr_idx
        except:
            offset = None
        
        # Golden Cross: Prev Short < Prev Long AND Curr Short > Curr Long
        if prev['ma_short'] < prev['ma_long'] and curr['ma_short'] > curr['ma_long']:
             signals.append({
                "signal": "BUY",
                "date": curr.name.strftime("%Y-%m-%d %H:%M:%S"),
                "price": curr['close'],
                "ma_short": curr['ma_short'],
                "ma_long": curr['ma_long'],
                "offset": offset
            })
        
        # Dead Cross
        elif prev['ma_short'] > prev['ma_long'] and curr['ma_short'] < curr['ma_long']:
            signals.append({
                "signal": "SELL",
                "date": curr.name.strftime("%Y-%m-%d %H:%M:%S"),
                "price": curr['close'],
                "ma_short": curr['ma_short'],
                "ma_long": curr['ma_long'],
                "offset": offset
            })
            
    # REVISED: Return all signals. Filtering is done in caller.
    return signals
