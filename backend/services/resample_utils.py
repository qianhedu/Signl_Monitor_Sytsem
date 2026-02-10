
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def resample_data(df: pd.DataFrame, period: str) -> pd.DataFrame:
    """
    将数据重采样为自定义周期。
    支持周线/月线及自定义分钟周期（如90, 120, 180, 240分钟）。
    
    针对 180 分钟等长周期，采用了基于交易日 (Trading Day) 和累计交易时间 (Cumulative Trading Time) 
    的聚合算法，以确保与同花顺等主流软件的算法保持一致。
    
    主要逻辑：
    1. 识别交易日：将夜盘时间 (21:00起) 归入下一个自然日，确保夜盘与次日日盘合并为同一交易日。
    2. 计算累计时间：在同一交易日内，累计每一根基础K线的时长。
    3. 周期切分：当累计时长达到目标周期 (如180分钟) 时，切分生成一根新K线。
    4. 跨日处理：不同交易日之间强制断开，确保K线不会跨越交易日边界。
    """
    if df.empty:
        return df
        
    # 处理周线/月线
    if period in ['weekly', 'monthly']:
        rule = 'W' if period == 'weekly' else 'ME'
        
        # 创建临时时间戳列
        if not 'temp_ts' in df.columns:
            df = df.copy()
            df['temp_ts'] = df.index
            
        agg_dict = {
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum',
            'temp_ts': 'max'
        }
        if 'hold' in df.columns:
            agg_dict['hold'] = 'last'
            
        resampled = df.resample(rule, closed='right', label='right').agg(agg_dict)
        resampled.dropna(inplace=True)
        
        if not resampled.empty:
            resampled.set_index('temp_ts', inplace=True)
            resampled.index.name = 'date'
            # 确保按时间排序
            resampled.sort_index(inplace=True)
        return resampled

    # 处理自定义分钟周期 (Trading Hour Based Aggregation)
    # 90, 120, 180, 240
    if period.isdigit():
        target_min = int(period)
        
        # 准备数据
        df_reset = df.copy()
        if not 'temp_ts' in df_reset.columns:
            df_reset['temp_ts'] = df_reset.index
            
        # 1. 识别交易日 (Trading Date)
        # 逻辑：如果时间 >= 18:00 (涵盖21:00夜盘)，则归属为 "次日"。
        # 这样可以将 周五夜盘(归属周一) 和 周一早盘 视为同一天? 
        # 期货夜盘通常定义为 T+1。
        # 这里简单使用 Shift -18h 技巧：
        # 21:00 - 18h = 03:00 (当日) -> Date为当日。
        # 09:00 - 18h = 15:00 (前日) -> Date为前日。
        # 这样 21:00(T) 和 09:00(T+1) 会有不同的 Date。
        # 等等，我们需要它们是 "同一交易日"。
        # 通常：21:00(T) 是 T+1 的开始。09:00(T+1) 是 T+1 的延续。
        # 所以它们应该有 "相同" 的标签。
        # 如果 Shift +3h:
        # 21:00 + 3h = 24:00 (次日 00:00) -> Date = T+1.
        # 09:00 + 3h = 12:00 (T+1) -> Date = T+1.
        # 这样它们就是同一天了！
        # 验证：
        # 01:00 (T+1) + 3h = 04:00 (T+1).
        # 15:00 (T+1) + 3h = 18:00 (T+1).
        # 完美。所有属于同一交易时段的K线都会落在同一自然日内。
        
        # 注意：pandas timestamp 加减。
        df_reset['trading_date'] = (df_reset.index + timedelta(hours=3)).date
        
        # 2. 计算每根K线的时长 (Duration)
        # 计算当前K线与上一根K线的时间差
        time_diffs = df_reset['temp_ts'].diff().dt.total_seconds() / 60
        
        # 估算基础周期 (Base Period)
        # 取众数，若数据太少默认30或60
        if len(df_reset) > 1:
            mode_val = time_diffs.mode()
            base_min = int(mode_val[0]) if not mode_val.empty else 30
        else:
            base_min = 30 # 默认
            
        # 填充第一行的 NaN (第一根K线默认为 base_min)
        time_diffs = time_diffs.fillna(base_min)
        
        # 处理异常间隔 (如跨日、跨周末、午休)
        # 如果间隔大于 1.5 倍基础周期，说明发生了中断，
        # 此时该K线自身的时长应视为 base_min (因为它是刚开盘的那一根)
        # 例如：11:30 -> 13:30，间隔120分。13:30这根K线实际代表13:00-13:30(或13:30-14:00)，时长应为 base_min。
        durations = time_diffs.apply(lambda x: base_min if x > base_min * 1.5 else x)
        
        # 修正：有时候 diff 是代表 "距离上一根K线结束的时间"。
        # 如果数据是 Close Time。
        # 10:00, 10:30. Diff = 30. Duration = 30. Correct.
        # 11:30, 13:30. Diff = 120. Duration -> Base (30). Correct.
        df_reset['duration'] = durations
        
        # 3. 计算累计交易时间 (Cumulative Minutes)
        # 在每个交易日内累计
        df_reset['cum_mins'] = df_reset.groupby('trading_date')['duration'].cumsum()
        
        # 4. 生成分组 ID (Group ID)
        # 逻辑：(cum_mins - epsilon) // target_min
        # 例如 target=180:
        # cum=30 -> 0
        # cum=180 -> 0 (179.9 // 180 = 0)
        # cum=210 -> 1 (209.9 // 180 = 1)
        df_reset['group_id'] = ((df_reset['cum_mins'] - 0.1) // target_min).astype(int)
        
        # 5. 聚合重采样
        agg_dict = {
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum',
            'temp_ts': 'max', # 使用该组最后一根K线的时间戳
            'cum_mins': 'last' # 保留累计时间用于调试
        }
        if 'hold' in df_reset.columns:
            agg_dict['hold'] = 'last'
            
        resampled = df_reset.groupby(['trading_date', 'group_id']).agg(agg_dict)
        
        # 恢复索引
        if not resampled.empty:
            resampled.set_index('temp_ts', inplace=True)
            resampled.index.name = 'date'
            resampled.sort_index(inplace=True)
            
        return resampled
    
    return df
