import akshare as ak
import pandas as pd
import numpy as np

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
        
        is_minute = period in ["60", "30", "15", "5", "1"]

        if market == "stock":
            if is_minute:
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
            if is_minute:
                # 期货分钟数据
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
                # 期货日线数据 (futures_zh_daily_sina)
                if period != "daily":
                    # TODO: 若需要周线/月线，需在此处处理重采样
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
            
        # 确保 date 列为 datetime 类型
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        
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
