import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def generate_mock_data(symbol: str, days: int = 5):
    """
    根据标的交易时间生成模拟 1 分钟数据。
    """
    # AO (氧化铝): 21:00-01:00, 09:00-10:15, 10:30-11:30, 13:30-15:00
    # FG (玻璃): 21:00-23:00, 09:00-10:15, 10:30-11:30, 13:30-15:00
    
    start_date = datetime(2025, 1, 1, 21, 0)
    timestamps = []
    
    current_time = start_date
    for _ in range(days):
        # 夜盘
        night_end_hour = 1 if symbol == 'AO' else 23
        
        # 21:00 到 夜盘结束
        t = current_time
        while True:
            if symbol == 'AO':
                # 跨零点
                if t.hour == 1 and t.minute == 0:
                    break
                if t.hour >= 21 or t.hour < 1:
                    timestamps.append(t)
                else:
                    break # 如果逻辑正确不应发生
            else:
                # FG: 23:00 结束
                if t.hour == 23 and t.minute == 0:
                    break
                timestamps.append(t)
            
            t += timedelta(minutes=1)
            
        # 移至次日 09:00
        # 如果是 AO, current_time 是前一日 21:00。t 是今日 01:00。
        # 如果是 FG, t 是前一日 23:00。
        
        # 计算次日 09:00
        # 对于 AO (t 是 01:00), 下一个 09:00 是同一天。
        # 对于 FG (t 是 23:00), 下一个 09:00 是次日。
        
        if t.hour == 23:
            t = t.replace(hour=9, minute=0) + timedelta(days=1)
        elif t.hour == 1:
            t = t.replace(hour=9, minute=0)
            
        # 上午 1: 09:00-10:15
        end_m1 = t.replace(hour=10, minute=15)
        while t < end_m1:
            timestamps.append(t)
            t += timedelta(minutes=1)
            
        # 上午 2: 10:30-11:30
        t = t.replace(hour=10, minute=30)
        end_m2 = t.replace(hour=11, minute=30)
        while t < end_m2:
            timestamps.append(t)
            t += timedelta(minutes=1)
            
        # 下午: 13:30-15:00
        t = t.replace(hour=13, minute=30)
        end_aft = t.replace(hour=15, minute=0)
        while t < end_aft:
            timestamps.append(t)
            t += timedelta(minutes=1)
            
        # 准备下一个夜盘 (21:00)
        current_time = t.replace(hour=21, minute=0)
        
    df = pd.DataFrame({'close': np.random.randn(len(timestamps)) + 100}, index=timestamps)
    return df

def mock_resample_logic(df_30m, target_min):
    """
    模拟 backend/services/backtest.py:resample_data 中的逻辑
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
    print(f"\n正在分析 {symbol}...")
    df_1m = generate_mock_data(symbol, days=3)
    
    # 重采样到 30m 基础周期 (模拟 API 返回)
    # 使用基于时间的标准重采样获取基础数据
    df_30m = df_1m.resample('30min', closed='left', label='right').last().dropna()
    
    print(f"3 天内的 30分钟 K线总数: {len(df_30m)}")
    print("前 5 个 30分钟 K线:")
    print(df_30m.head().index.tolist())
    
    # 使用计数逻辑重采样到 90m
    df_90m = mock_resample_logic(df_30m, 90)
    
    print(f"90分钟 K线总数: {len(df_90m)}")
    print("前 5 个 90分钟 K线 (基于计数):")
    for ts in df_90m.head().index:
        print(ts)
        
    # 检查与时段结束的对齐情况
    # AO 夜盘结束于 01:00。FG 结束于 23:00。
    # 检查是否有任何 90m K线跨越了时段边界 (例如包含 23:00 和 09:00)
    # 由于我们只有 'max' 时间戳，我们可以检查时间戳是否"奇怪"
    
    # 逻辑: 
    # AO: 21:00-01:00 (4小时, 8x30m)。90m=3x30m。
    # 分组: [0,1,2], [3,4,5], [6,7, 8(次日 09:30)]
    # Bar 1: 22:30. Bar 2: 00:00. Bar 3: 09:30 (包含 00:00-01:00 和 09:00-09:30?!)
    
    # 让我们直接检查分组
    base_min = 30
    group_size = 3
    df_reset = df_30m.reset_index()
    df_reset['group_id'] = df_reset.index // group_size
    
    print("\n详细分组分析 (前 4 组):")
    for gid in range(4):
        group = df_reset[df_reset['group_id'] == gid]
        # 列名是 'index' 因为原始索引没有名称
        col_name = 'index' if 'index' in group.columns else 'date'
        print(f"组 {gid}: {group[col_name].tolist()}")
        
        # 检查跨日缺口
        dates = group[col_name].tolist()
        if len(dates) > 1:
            diff = dates[-1] - dates[0]
            # 如果差值 > 90 分钟 (加上容差)，意味着跨越了缺口
            if diff.total_seconds() > 90 * 60 + 3600: # > 1.5h + 缓冲
                print(f"  [警告] 检测到跨时段缺口! 差值: {diff}")

if __name__ == "__main__":
    analyze_symbol('FG')
    analyze_symbol('AO')
