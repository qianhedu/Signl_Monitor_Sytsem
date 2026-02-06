import akshare as ak
import pandas as pd
import numpy as np
from typing import List, Optional

def get_market_data(symbol: str, market: str = "stock", period: str = "daily", adjust: str = "qfq") -> pd.DataFrame:
    """
    使用 akshare 获取市场数据。
    
    参数:
        symbol: 标的代码
        market: "stock" (股票) 或 "futures" (期货)
        period: 周期, 支持 "daily" (日线), "weekly" (周线), "monthly" (月线), 
                以及分钟周期 "60", "30", "15", "5"。
                注意: 对于 "120", "180" 等特殊周期，本函数会获取基础分钟数据（如60分钟）供后续重采样使用。
        adjust: 复权方式, 默认 "qfq" (前复权)
        
    返回:
        pd.DataFrame: 包含 date, open, high, low, close, volume 等列的数据框。
    """
    try:
        df = pd.DataFrame()
        
        # 标准化周期判断
        # 股票分钟: period="60" 等
        # 期货分钟: period="60" 等
        # 股票日线: period="daily"
        
        is_minute = period in ["240", "180", "120", "90", "60", "30", "15", "5", "1"]

        if market == "stock":
            # 特殊处理 240分钟 (即日线，但可能需要分钟级的时间戳格式)
            # 为了数据准确性（包括复权），直接使用日线数据，并将时间统一设置为 15:00
            if period == "240":
                df = pd.DataFrame()
                # 优先使用新浪接口
                try:
                    df = ak.stock_zh_a_hist(symbol=symbol, period="daily", adjust=adjust)
                except Exception as e:
                    print(f"新浪日线接口失败 (用于240m): {e}，尝试腾讯接口...")
                    try:
                         # 腾讯接口不支持 period 参数
                         prefix = "sh" if symbol.startswith("6") else "sz"
                         if symbol.startswith("4") or symbol.startswith("8"): prefix = "bj"
                         tx_symbol = f"{prefix}{symbol}"
                         df = ak.stock_zh_a_hist_tx(symbol=tx_symbol, start_date="20200101", adjust=adjust)
                    except Exception as e2:
                         print(f"腾讯日线接口也失败: {e2}")

                if not df.empty:
                    df = df.rename(columns={
                        "日期": "date",
                        "开盘": "open",
                        "收盘": "close",
                        "最高": "high",
                        "最低": "low",
                        "成交量": "volume"
                    })
                    df['date'] = pd.to_datetime(df['date'])
                    # 设置时间为 15:00:00
                    df['date'] = df['date'] + pd.Timedelta(hours=15)

            elif is_minute:
                # 映射长周期到基础周期以便后续重采样
                base_period = period
                need_resample = False
                
                # 如果请求的是 90/120/180 分钟，先获取 60 分钟数据，后续再进行重采样
                # 使用 60 分钟作为基础周期
                if period in ["180", "120", "90"]:
                    base_period = "60" 
                    need_resample = True
                
                # 使用东方财富接口获取分钟数据 (支持复权)
                # stock_zh_a_hist_min_em 不需要 sh/sz 前缀
                # 增加重试机制
                import time
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        df = ak.stock_zh_a_hist_min_em(symbol=symbol, period=base_period, adjust=adjust)
                        if not df.empty:
                            break
                    except Exception as e:
                        if attempt == max_retries - 1:
                             print(f"获取分钟数据失败 (尝试 {attempt+1}/{max_retries}): {e}")
                        time.sleep(1)

                if not df.empty:
                    df = df.rename(columns={
                        "日期": "date",
                        "开盘": "open",
                        "最高": "high",
                        "最低": "low",
                        "收盘": "close",
                        "成交量": "volume"
                    })
                        
                    if need_resample:
                            df['date'] = pd.to_datetime(df['date'])
                            df.set_index('date', inplace=True)
                            
                            # A股自定义重采样逻辑，旨在匹配同花顺(THS)等软件的处理方式
                            # 同花顺 A股逻辑 (交易时间 09:30-11:30, 13:00-15:00):
                            # 120分钟: [09:30-11:30] 为第一根, [13:00-15:00] 为第二根 (每天2根)
                            # 240分钟: [09:30-15:00] 包含全天 (每天1根) -> 已通过日线接口处理
                            # 90分钟: 非标准周期，通常按时间切分。
                            # 我们使用基于时间的映射方法来处理。
                            
                            def get_period_end_time(ts, period_min):
                                """
                                计算给定时间戳归属的K线结束时间。
                                逻辑：将交易时间标准化为从 09:30 开始的分钟数，计算其所在的周期区间。
                                """
                                # 将时间转换为从 09:30 开始的分钟数
                                # 上午: 09:30 (0) 到 11:30 (120)
                                # 下午: 13:00 (120 虚拟点) 到 15:00 (240 虚拟点)
                                
                                hm = ts.hour * 60 + ts.minute
                                
                                # 标准化时间为 "自09:30起的交易分钟数"
                                # 9:30 = 570m
                                # 11:30 = 690m
                                # 13:00 = 780m
                                # 15:00 = 900m
                                
                                minutes_from_open = 0
                                if 570 < hm <= 690: # 上午盘
                                    minutes_from_open = hm - 570
                                elif 780 < hm <= 900: # 下午盘
                                    minutes_from_open = 120 + (hm - 780)
                                else:
                                    # 超出范围或正好是开盘点 (通常closed='right'不会出现)
                                    return ts
                                
                                # 确定所属的区间 (Bin)
                                # period_min 例如 120
                                # bin_index = ceil(minutes_from_open / period_min)
                                import math
                                bin_idx = math.ceil(minutes_from_open / int(period_min))
                                
                                # 计算该区间结束时的交易分钟数
                                bin_end_trading_min = bin_idx * int(period_min)
                                
                                # 将交易分钟数转换回自然时间
                                # 如果结束时间 <= 120: 在上午
                                # 如果结束时间 > 120: 在下午
                                
                                final_hm = 0
                                if bin_end_trading_min <= 120:
                                    final_hm = 570 + bin_end_trading_min
                                else:
                                    final_hm = 780 + (bin_end_trading_min - 120)
                                    
                                # 构造新的时间戳
                                new_h = final_hm // 60
                                new_m = final_hm % 60
                                
                                return ts.replace(hour=new_h, minute=new_m, second=0)

                            # 应用映射逻辑
                            # 注意: 向量化处理会更快，但 apply 方法逻辑更直观
                            # 优化: 创建唯一时间映射表，减少重复计算
                            unique_times = pd.Series(df.index.time).unique()
                            time_map = {}
                            for t in unique_times:
                                # 创建一个哑元日期用于函数调用
                                dummy_dt = pd.Timestamp(year=2000, month=1, day=1, hour=t.hour, minute=t.minute)
                                mapped_dt = get_period_end_time(dummy_dt, period)
                                time_map[t] = mapped_dt.time()
                                
                            # 赋值新的时间
                            # 需要保留原有的日期部分
                            new_dates = []
                            for idx in df.index:
                                t = idx.time()
                                mapped_time = time_map.get(t, t)
                                new_dates.append(idx.replace(hour=mapped_time.hour, minute=mapped_time.minute))
                                
                            df['resample_date'] = new_dates
                            
                            # 按重采样后的时间分组聚合
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
                # stock_zh_a_hist 接口支持 日/周/月
                df = pd.DataFrame()
                try:
                    df = ak.stock_zh_a_hist(symbol=symbol, period=period, adjust=adjust)
                except Exception as e:
                    print(f"获取 {symbol} 数据出错: {e}")
                    # 故障转移：仅针对日线，尝试腾讯接口
                    if period == 'daily':
                        print("尝试使用腾讯接口作为备选方案...")
                        try:
                            prefix = "sh" if symbol.startswith("6") else "sz"
                            if symbol.startswith("4") or symbol.startswith("8"): prefix = "bj"
                            tx_symbol = f"{prefix}{symbol}"
                            # 腾讯接口返回所有历史数据，数据量较大，需注意
                            df = ak.stock_zh_a_hist_tx(symbol=tx_symbol, start_date="20200101", adjust=adjust)
                        except Exception as e_tx:
                             print(f"腾讯接口备选方案失败: {e_tx}")

                    # 二级降级方案：尝试获取分钟数据并重采样为日线
                    if df.empty and period == 'daily':
                        print("尝试使用新浪分钟数据重采样为日线作为二级备选方案...")
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
                            print(f"备选方案失败: {e2}")
                            
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
                # 期货长周期分钟数据的自定义重采样
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
                        
                        # 简单的行数聚合重采样 (适用于连续合约的近似处理)
                        # 注意：更严谨的处理应考虑交易时间段
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
                            
                        # 每 N 行分为一组
                        group_key = df.index // multiplier
                        df = df.groupby(group_key).agg(agg_dict)
                        df.reset_index(drop=True, inplace=True)
                except Exception as e:
                    print(f"获取/重采样期货数据 {symbol} {period} 出错: {e}")
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
                    print(f"获取期货分钟数据出错: {e}")
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
                        
                        # 周线/月线重采样
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
                    print(f"获取期货日线数据出错: {e}")
                    df = pd.DataFrame()
        
        if df.empty:
            return pd.DataFrame()
            
        # 确保 date 列为 datetime 类型
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        # 确保索引排序，以便进行可靠的切片操作
        df.sort_index(inplace=True)
        
        # 确保数值列类型正确
        cols = ['open', 'close', 'high', 'low']
        for col in cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
                
        return df
    except Exception as e:
        print(f"获取 {symbol} 数据时发生未知错误: {e}")
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
    """
    if df.empty or len(df) < 20:
        return df

    # 1. 计算 MID (中间价)
    # 权重分布: 收盘价(3), 最低价(1), 开盘价(1), 最高价(1)
    mid = (3 * df['close'] + df['low'] + df['open'] + df['high']) / 6
    
    # 2. 计算 DKX (20周期加权移动平均)
    # 构造权重数组: [1, 2, ..., 20]
    weights_asc = np.arange(1, 21) # [1, 2, ..., 20]
    sum_weights = np.sum(weights_asc) # 210
    
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
    检查 DKX 金叉 (向上突破) 或 死叉 (向下突破) 信号。
    
    参数:
        df: 包含 dkx, madkx 列的 DataFrame
        lookback: 回溯期，检查最近 N 根K线内的信号
        start_time: 开始时间 (可选)
        end_time: 结束时间 (可选)
        
    返回:
        List[dict]: 信号列表
    """
    if 'dkx' not in df.columns or df['dkx'].isnull().all():
        return []

    subset = pd.DataFrame()

    if start_time and end_time:
        # 按时间范围过滤，但需确保包含前一行以便检查交叉
        try:
            # 确保索引为 datetime 类型
            if not isinstance(df.index, pd.DatetimeIndex):
                df.index = pd.to_datetime(df.index)
            
            # 排序索引
            df.sort_index(inplace=True)
            
            # 1. 对齐时区
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
            
            # 2. 使用布尔掩码查找子集 (比 loc 切片更健壮)
            mask = (df.index >= ts_start) & (df.index <= ts_end)
            
            temp_subset = df.loc[mask]
            
            if temp_subset.empty:
                return []
                
            first_date = temp_subset.index[0]
            last_date = temp_subset.index[-1]
            
            # 查找整数位置索引
            loc_start = df.index.get_loc(first_date)
            if isinstance(loc_start, slice): loc_start = loc_start.start
            
            loc_end = df.index.get_loc(last_date)
            # 如果是 slice，stop 是排他的，需要 -1 才能指向最后一个元素
            # 但这里我们要的是整数索引
            if isinstance(loc_end, slice): 
                # 这里有点复杂，如果重复索引，slice stop 指向最后一个元素的下一个
                # 比如 [0, 1, 2], slice(0, 3). stop=3. 最后一个元素 idx=2.
                # 我们想定位到 idx=2.
                loc_end = loc_end.stop - 1 
            
            # 向前扩展一行
            start_slice = max(0, loc_start - 1)
            
            # 向后切片是排他的，所以要 +1
            if isinstance(loc_end, slice):
                 end_slice = loc_end.stop
            else:
                 end_slice = loc_end + 1
                
            subset = df.iloc[start_slice:end_slice]
            
        except Exception as e:
            print(f"check_dkx_signal 时间过滤出错: {e}")
            return []
        
    else:
        # 使用回溯期 (lookback)
        lb = abs(lookback)
        if lb == 0:
            # 如果 lookback 为 0，检查所有可用历史
            subset = df
        else:
            subset = df.iloc[-lb-1:]
    
    if len(subset) < 2:
        return []

    signals = []

    # 遍历检查交叉
    # 我们检查从前一天到当天的关系变化
    for i in range(1, len(subset)):
        prev = subset.iloc[i-1]
        curr = subset.iloc[i]
        
        # 计算偏移量 (用于前端定位)
        try:
            # 在原始 df 中查找绝对位置
            curr_idx = df.index.get_loc(curr.name)
            if isinstance(curr_idx, slice): 
                # 如果是 slice (重复索引)，取最后一个
                curr_idx = curr_idx.stop - 1
            offset = len(df) - 1 - curr_idx
        except:
            offset = None
        
        # 金叉: 前一日 DKX < MADKX 且 当日 DKX > MADKX
        if prev['dkx'] < prev['madkx'] and curr['dkx'] > curr['madkx']:
            signals.append({
                "signal": "BUY",
                "date": curr.name.strftime("%Y-%m-%d %H:%M:%S"),
                "price": curr['close'],
                "dkx": curr['dkx'],
                "madkx": curr['madkx'],
                "offset": offset
            })
        
        # 死叉: 前一日 DKX > MADKX 且 当日 DKX < MADKX
        elif prev['dkx'] > prev['madkx'] and curr['dkx'] < curr['madkx']:
             signals.append({
                "signal": "SELL",
                "date": curr.name.strftime("%Y-%m-%d %H:%M:%S"),
                "price": curr['close'],
                "dkx": curr['dkx'],
                "madkx": curr['madkx'],
                "offset": offset
            })
            
    return signals

def calculate_ma(df: pd.DataFrame, short_period: int = 5, long_period: int = 10) -> pd.DataFrame:
    """
    计算双均线 (Dual Moving Average)。
    """
    if df.empty:
        return df
        
    df['ma_short'] = df['close'].rolling(window=short_period).mean()
    df['ma_long'] = df['close'].rolling(window=long_period).mean()
    
    return df

def check_ma_signal(df: pd.DataFrame, lookback: int = 5, start_time: Optional[str] = None, end_time: Optional[str] = None) -> List[dict]:
    """
    检查均线金叉 / 死叉信号。
    """
    if 'ma_short' not in df.columns or df['ma_short'].isnull().all():
        return []

    subset = pd.DataFrame()
    
    if start_time and end_time:
         # 按时间范围过滤
        try:
            if not isinstance(df.index, pd.DatetimeIndex):
                df.index = pd.to_datetime(df.index)
            
            df.sort_index(inplace=True)

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
            
            temp_subset = df.loc[mask]

            if temp_subset.empty:
                return []
            
            first_date = temp_subset.index[0]
            last_date = temp_subset.index[-1]
            
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
            print(f"check_ma_signal 时间过滤出错: {e}")
            return []
    else:
        lb = abs(lookback)
        if lb == 0:
            subset = df
        else:
            lb = max(1, lb)
            subset = df.iloc[-lb-1:]  
        
    if len(subset) < 2:
        return []

    signals = []

    for i in range(1, len(subset)):
        prev = subset.iloc[i-1]
        curr = subset.iloc[i]
        
        try:
            curr_idx = df.index.get_loc(curr.name)
            if isinstance(curr_idx, slice): 
                curr_idx = curr_idx.stop - 1
            offset = len(df) - 1 - curr_idx
        except:
            offset = None
        
        # 金叉: 短均线 上穿 长均线
        if prev['ma_short'] < prev['ma_long'] and curr['ma_short'] > curr['ma_long']:
             signals.append({
                "signal": "BUY",
                "date": curr.name.strftime("%Y-%m-%d %H:%M:%S"),
                "price": curr['close'],
                "ma_short": curr['ma_short'],
                "ma_long": curr['ma_long'],
                "offset": offset
            })
        
        # 死叉: 短均线 下穿 长均线
        elif prev['ma_short'] > prev['ma_long'] and curr['ma_short'] < curr['ma_long']:
            signals.append({
                "signal": "SELL",
                "date": curr.name.strftime("%Y-%m-%d %H:%M:%S"),
                "price": curr['close'],
                "ma_short": curr['ma_short'],
                "ma_long": curr['ma_long'],
                "offset": offset
            })
            
    return signals
