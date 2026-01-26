import akshare as ak
import pandas as pd
import numpy as np

def get_market_data(symbol: str, market: str = "stock", period: str = "daily", adjust: str = "qfq") -> pd.DataFrame:
    """
    使用 akshare 获取行情数据。
    market: "stock" 或 "futures"
    period: "daily", "weekly", "monthly", "240", "120", "60", "30", "15", "5", "1"
    """
    try:
        df = pd.DataFrame()
        print(f"Fetching {market} data for {symbol} with period {period}")
        
        # 如有需要可在内部规范周期，但 akshare 多使用固定字符串
        # 股票分钟：period="60"
        # 期货分钟：period="60"
        # 股票日线：period="daily"
        
        is_minute = period in ["240", "120", "60", "30", "15", "5", "1"]

        if market == "stock":
            if is_minute:
                # 分钟数据使用新浪接口（东方财富较不稳定）
                # 股票分钟需加前缀：600519 -> sh600519，000001 -> sz000001
                prefix = ""
                if symbol.startswith("6"):
                    prefix = "sh"
                elif symbol.startswith("0") or symbol.startswith("3"):
                    prefix = "sz"
                elif symbol.startswith("4") or symbol.startswith("8"):
                    prefix = "bj" # 新浪可能不支持北交所前缀，尽量尝试或回退
                
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
                # stock_zh_a_hist 支持日/周/月周期
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
                # futures_zh_daily_sina（仅日线）
                # 如需周/月线，可能需要重采样或使用其它接口
                # 暂时仅支持期货日线，除非做重采样
                if period != "daily":
                    # TODO：如需可将日线重采样为周线
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
            
        # 确保日期为 datetime 类型（处理字符串格式）
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        
        # 确保数值列为数值类型
        cols = ['open', 'close', 'high', 'low']
        for col in cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        print(df.tail())       
        return df
    except Exception as e:
        print(f"Error fetching data for {symbol}: {e}")
        return pd.DataFrame()

def calculate_dkx(df: pd.DataFrame) -> pd.DataFrame:
    """
    计算 DKX 指标。
    公式：
    MID = (3*CLOSE + LOW + OPEN + HIGH)/6
    DKX = (20*MID + 19*REF(MID,1) + ... + 1*REF(MID,19)) / 210
    MADKX = MA(DKX, 10)
    """
    if df.empty or len(df) < 20:
        return df

    # 计算 MID
    mid = (3 * df['close'] + df['low'] + df['open'] + df['high']) / 6
    
    # 计算 DKX（加权移动平均）
    weights = np.arange(20, 0, -1) # 20, 19, ..., 1
    sum_weights = np.sum(weights) # 210
    
    # 使用 rolling 窗口配合 apply（简洁但可能较慢）
    # 或可用 pandas 内置函数实现
    def weighted_avg(x):
        if len(x) < 20: return np.nan
        return np.dot(x, weights) / sum_weights

    # 需要应用在 'mid' 序列上
    # rolling(20) 取最近 20 个元素
    # 权重应当让最近值（窗口末端）权重为 20
    # 若 x 为 [t-19, ..., t]，对应权重应为 [1, 2, ..., 20]
    # 公式含义：当日权重 20，昨日权重 19，依次递减
    
    w_asc = np.arange(1, 21) # 1, 2, ..., 20
    
    df['dkx'] = mid.rolling(window=20).apply(lambda x: np.dot(x, w_asc) / sum_weights, raw=True)
    
    # Calculate MADKX (Simple MA of DKX, period 10)
    df['madkx'] = df['dkx'].rolling(window=10).mean()
    
    return df

def check_dkx_signal(df: pd.DataFrame, lookback: int = 5) -> dict:
    """
    检测金叉（DKX 上穿 MADKX）或死叉（下穿）。
    在回溯窗口内返回最新的一个信号。
    """
    if 'dkx' not in df.columns or df['dkx'].isnull().all():
        return None

    # 取最近 N 行数据
    subset = df.iloc[-lookback-1:] 
    
    if len(subset) < 2:
        return None

    last_signal = "NONE"
    signal_date = None
    price = 0.0
    dkx_val = 0.0
    madkx_val = 0.0

    # 迭代查找交叉
    # 检查前一日与当日关系是否发生变化
    for i in range(1, len(subset)):
        prev = subset.iloc[i-1]
        curr = subset.iloc[i]
        
        # 金叉：前一日 DKX < 前一日 MADKX 且 当日 DKX > 当日 MADKX
        if prev['dkx'] < prev['madkx'] and curr['dkx'] > curr['madkx']:
            last_signal = "BUY"
            signal_date = _format_ts(curr.name)
            price = curr['close']
            dkx_val = curr['dkx']
            madkx_val = curr['madkx']
        
        # 死叉：前一日 DKX > 前一日 MADKX 且 当日 DKX < 当日 MADKX
        elif prev['dkx'] > prev['madkx'] and curr['dkx'] < curr['madkx']:
            last_signal = "SELL"
            signal_date = _format_ts(curr.name)
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
    计算双均线（MA）。
    """
    if df.empty:
        return df
        
    df['ma_short'] = df['close'].rolling(window=short_period).mean()
    df['ma_long'] = df['close'].rolling(window=long_period).mean()
    
    return df

def check_ma_signal(df: pd.DataFrame, lookback: int = 5) -> dict:
    """
    检测 MA 金叉/死叉。
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
        
        # 金叉：前一日短均线 < 前一日长均线 且 当日短均线 > 当日长均线
        if prev['ma_short'] < prev['ma_long'] and curr['ma_short'] > curr['ma_long']:
            last_signal = "BUY"
            signal_date = _format_ts(curr.name)
            price = curr['close']
            ma_short_val = curr['ma_short']
            ma_long_val = curr['ma_long']
        
        # 死叉
        elif prev['ma_short'] > prev['ma_long'] and curr['ma_short'] < curr['ma_long']:
            last_signal = "SELL"
            signal_date = _format_ts(curr.name)
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

def _format_ts(ts: pd.Timestamp) -> str:
    try:
        if getattr(ts, 'hour', 0) != 0 or getattr(ts, 'minute', 0) != 0 or getattr(ts, 'second', 0) != 0:
            return ts.strftime("%Y-%m-%d %H:%M")
        return ts.strftime("%Y-%m-%d")
    except Exception:
        return str(ts)
