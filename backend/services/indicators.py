import akshare as ak
import pandas as pd
import numpy as np

def get_market_data(symbol: str, market: str = "stock", period: str = "daily", adjust: str = "qfq") -> pd.DataFrame:
    """
    Fetch market data using akshare.
    market: "stock" or "futures"
    period: "daily", "weekly", "monthly", "60", "30", "15", "5"
    """
    try:
        df = pd.DataFrame()
        
        # Normalize period for internal logic if needed, but akshare mostly uses specific strings
        # Stock Minutes: period="60"
        # Futures Minutes: period="60"
        # Stock Daily: period="daily"
        
        is_minute = period in ["60", "30", "15", "5", "1"]

        if market == "stock":
            if is_minute:
                # Use Sina interface for minutes (Eastmoney is unstable)
                # Symbol needs prefix: 600519 -> sh600519, 000001 -> sz000001
                prefix = ""
                if symbol.startswith("6"):
                    prefix = "sh"
                elif symbol.startswith("0") or symbol.startswith("3"):
                    prefix = "sz"
                elif symbol.startswith("4") or symbol.startswith("8"):
                    prefix = "bj" # Sina might not support bj, but let's try or fallback
                
                sina_symbol = f"{prefix}{symbol}"
                df = ak.stock_zh_a_minute(symbol=sina_symbol, period=period)
                if not df.empty:
                    df = df.rename(columns={
                        "day": "date",
                        "open": "open",
                        "high": "high",
                        "low": "low",
                        "close": "close",
                        "volume": "volume"
                    })
            else:
                # stock_zh_a_hist supports daily, weekly, monthly
                df = ak.stock_zh_a_hist(symbol=symbol, period=period, adjust=adjust)
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
            if is_minute:
                # Futures Minute
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
            else:
                # futures_zh_daily_sina (Daily only)
                # If user requests weekly/monthly, we might need to resample or find another API
                # For now, let's just support daily for futures unless we resample
                if period != "daily":
                    # TODO: Resample daily to weekly if needed
                    pass
                
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
        
        if df.empty:
            return pd.DataFrame()
            
        # Ensure date is datetime (handle string formats)
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        
        # Ensure numeric columns
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
    Calculate DKX indicator.
    Formula:
    MID = (3*CLOSE + LOW + OPEN + HIGH)/6
    DKX = (20*MID + 19*REF(MID,1) + ... + 1*REF(MID,19)) / 210
    MADKX = MA(DKX, 10)
    """
    if df.empty or len(df) < 20:
        return df

    # Calculate MID
    mid = (3 * df['close'] + df['low'] + df['open'] + df['high']) / 6
    
    # Calculate DKX (Weighted Moving Average)
    weights = np.arange(20, 0, -1) # 20, 19, ..., 1
    sum_weights = np.sum(weights) # 210
    
    # Use rolling window with apply (can be slow, but simple for now)
    # Alternatively use pandas functionality
    def weighted_avg(x):
        if len(x) < 20: return np.nan
        return np.dot(x, weights) / sum_weights

    # We need to apply this to the 'mid' series
    # rolling(20) takes the last 20 elements. 
    # The weights should be applied such that the most recent (last in window) has weight 20.
    # np.dot(x, weights) where x is [t-19, ..., t] and weights is [20, ..., 1] ??
    # Wait, formula says 20*MID + 19*Ref(MID,1)... Ref(MID,1) is yesterday.
    # So Today (t) has weight 20. Yesterday (t-1) has weight 19.
    # If window is [x_0, x_1, ..., x_19] (where x_19 is current), we want x_19*20 + x_18*19 ...
    # So weights should be [1, 2, ..., 20] if multiplied by [oldest, ..., newest]
    
    w_asc = np.arange(1, 21) # 1, 2, ..., 20
    
    df['dkx'] = mid.rolling(window=20).apply(lambda x: np.dot(x, w_asc) / sum_weights, raw=True)
    
    # Calculate MADKX (Simple MA of DKX, period 10)
    df['madkx'] = df['dkx'].rolling(window=10).mean()
    
    return df

def check_dkx_signal(df: pd.DataFrame, lookback: int = 5) -> dict:
    """
    Check for Golden Cross (DKX crosses above MADKX) or Dead Cross.
    Returns the latest signal within lookback period.
    """
    if 'dkx' not in df.columns or df['dkx'].isnull().all():
        return None

    # Get last N rows
    subset = df.iloc[-lookback-1:] 
    
    if len(subset) < 2:
        return None

    last_signal = "NONE"
    signal_date = None
    price = 0.0
    dkx_val = 0.0
    madkx_val = 0.0

    # Iterate to find crossover
    # We check if relationship changed from previous day to current day
    for i in range(1, len(subset)):
        prev = subset.iloc[i-1]
        curr = subset.iloc[i]
        
        # Golden Cross: Prev DKX < Prev MADKX AND Curr DKX > Curr MADKX
        if prev['dkx'] < prev['madkx'] and curr['dkx'] > curr['madkx']:
            last_signal = "BUY"
            signal_date = curr.name.strftime("%Y-%m-%d")
            price = curr['close']
            dkx_val = curr['dkx']
            madkx_val = curr['madkx']
        
        # Dead Cross: Prev DKX > Prev MADKX AND Curr DKX < Curr MADKX
        elif prev['dkx'] > prev['madkx'] and curr['dkx'] < curr['madkx']:
            last_signal = "SELL"
            signal_date = curr.name.strftime("%Y-%m-%d")
            price = curr['close']
            dkx_val = curr['dkx']
            madkx_val = curr['madkx']
            
    if last_signal != "NONE":
        return {
            "signal": last_signal,
            "date": signal_date,
            "price": price,
            "dkx": dkx_val,
            "madkx": madkx_val
        }
    
    return None

def calculate_ma(df: pd.DataFrame, short_period: int = 5, long_period: int = 10) -> pd.DataFrame:
    """
    Calculate Dual Moving Average.
    """
    if df.empty:
        return df
        
    df['ma_short'] = df['close'].rolling(window=short_period).mean()
    df['ma_long'] = df['close'].rolling(window=long_period).mean()
    
    return df

def check_ma_signal(df: pd.DataFrame, lookback: int = 5) -> dict:
    """
    Check for MA Golden Cross / Dead Cross.
    """
    if 'ma_short' not in df.columns or df['ma_short'].isnull().all():
        return None

    subset = df.iloc[-lookback-1:] 
    if len(subset) < 2:
        return None

    last_signal = "NONE"
    signal_date = None
    price = 0.0
    ma_short_val = 0.0
    ma_long_val = 0.0

    for i in range(1, len(subset)):
        prev = subset.iloc[i-1]
        curr = subset.iloc[i]
        
        # Golden Cross: Prev Short < Prev Long AND Curr Short > Curr Long
        if prev['ma_short'] < prev['ma_long'] and curr['ma_short'] > curr['ma_long']:
            last_signal = "BUY"
            signal_date = curr.name.strftime("%Y-%m-%d")
            price = curr['close']
            ma_short_val = curr['ma_short']
            ma_long_val = curr['ma_long']
        
        # Dead Cross
        elif prev['ma_short'] > prev['ma_long'] and curr['ma_short'] < curr['ma_long']:
            last_signal = "SELL"
            signal_date = curr.name.strftime("%Y-%m-%d")
            price = curr['close']
            ma_short_val = curr['ma_short']
            ma_long_val = curr['ma_long']
            
    if last_signal != "NONE":
        return {
            "signal": last_signal,
            "date": signal_date,
            "price": price,
            "ma_short": ma_short_val,
            "ma_long": ma_long_val
        }
    
    return None
