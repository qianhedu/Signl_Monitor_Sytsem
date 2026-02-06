import sys
import os
import pandas as pd
import numpy as np
import datetime

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.indicators import get_market_data, calculate_dkx
from services.backtest import filter_trading_hours
from services.metadata import get_trading_hours_type

def get_trading_day(ts):
    """
    将时间戳映射到交易日。
    逻辑: 将时间向后推移 4 小时。
    - 21:00 -> 01:00 (次日)
    - 02:00 -> 06:00 (当日)
    - 09:00 -> 13:00 (当日)
    - 15:00 -> 19:00 (当日)
    然后处理周末: 如果是周六/周日，则映射到周一。
    """
    shifted = ts + pd.Timedelta(hours=4)
    # 检查工作日: 0=周一, 6=周日
    # 如果是周六(5)或周日(6)，移至周一
    if shifted.weekday() >= 5: 
        days_to_add = 7 - shifted.weekday()
        shifted += pd.Timedelta(days=days_to_add)
        
    return shifted.date()

def run_regression_test():
    symbols = ["SS0", "CJ0", "JD0"]
    results = []
    
    print("开始回归测试 (2023-01-01 至今)...")
    
    for symbol in symbols:
        print(f"正在处理 {symbol}...")
        
        # 1. 基准: 官方日线数据
        try:
            df_daily = get_market_data(symbol, market='futures', period='daily')
            if df_daily.empty:
                print(f"  {symbol} 无日线数据")
                continue
                
            # 在基准数据上计算 DKX
            df_daily = calculate_dkx(df_daily)
        except Exception as e:
            print(f"  获取日线数据出错: {e}")
            continue
        
        # 2. 新逻辑: 分钟数据 -> 过滤 -> 聚合 -> DKX
        try:
            df_min = get_market_data(symbol, market='futures', period='60')
            if df_min.empty:
                print(f"  {symbol} 无分钟数据")
                continue
                
            # 过滤 (包含 JD 成交量调整)
            df_min_filtered = filter_trading_hours(df_min, symbol)
            
            # 聚合为日线 (构造)
            # 应用交易日映射
            df_min_filtered['trading_date'] = df_min_filtered.index.map(get_trading_day)
            
            # 按 trading_date 分组
            # 注意: 必须在分组前按时间排序以获得正确的 开盘/收盘价
            df_min_filtered = df_min_filtered.sort_index()
            
            df_constructed = df_min_filtered.groupby('trading_date').agg({
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum'
            })
            
            # 恢复索引
            df_constructed.index.name = 'date'
            df_constructed.index = pd.to_datetime(df_constructed.index)
            
            # 在构造的日线数据上计算 DKX
            df_constructed = calculate_dkx(df_constructed)
        except Exception as e:
            print(f"  新逻辑处理出错: {e}")
            continue
        
        # 3. 旧逻辑: 分钟数据 -> 无过滤 -> 简单聚合 -> DKX
        try:
            df_min_old = get_market_data(symbol, market='futures', period='60')
            # 简单日期映射 (日历日)
            df_min_old['trading_date'] = df_min_old.index.date 
            df_old_constructed = df_min_old.groupby('trading_date').agg({
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum'
            })
            df_old_constructed.index = pd.to_datetime(df_old_constructed.index)
            df_old_constructed = calculate_dkx(df_old_constructed)
        except Exception as e:
            print(f"  旧逻辑处理出错: {e}")
            df_old_constructed = pd.DataFrame()
        
        # 4. 比较
        # 对齐日期
        common_dates = df_daily.index.intersection(df_constructed.index)
        # 过滤 2023-01-01 之后的数据
        start_date = pd.Timestamp("2023-01-01")
        common_dates = common_dates[common_dates >= start_date]
        
        print(f"  正在比较 {len(common_dates)} 天的数据...")
        
        for date in common_dates:
            bench_dkx = df_daily.loc[date, 'dkx']
            new_dkx = df_constructed.loc[date, 'dkx']
            
            # 旧逻辑数据可能不存在
            old_dkx = np.nan
            if not df_old_constructed.empty and date in df_old_constructed.index:
                old_dkx = df_old_constructed.loc[date, 'dkx']
                
            # 误差计算
            # abs(新值 - 基准) / 基准
            if pd.isna(bench_dkx) or bench_dkx == 0:
                error = 0.0
            else:
                error = abs(new_dkx - bench_dkx) / abs(bench_dkx)
            
            # 如果误差过大，确定原因
            reason = ""
            if error >= 0.0005:
                reason = "偏差过大"
                # 检查是否由于夜盘导致
                # 比较收盘价
                bench_close = df_daily.loc[date, 'close']
                new_close = df_constructed.loc[date, 'close']
                if abs(new_close - bench_close) / bench_close > 0.001:
                    reason += " (收盘价不一致)"
            
            results.append({
                'symbol': symbol,
                'date': date,
                'benchmark_dkx': bench_dkx,
                'new_dkx': new_dkx,
                'old_dkx': old_dkx,
                'error': error,
                'compliant': error < 0.0005,
                'reason': reason
            })
            
    # 输出
    if not results:
        print("未生成结果。")
        return

    df_res = pd.DataFrame(results)
    output_path = os.path.join(os.path.dirname(__file__), 'dkx_regression_test.csv')
    df_res.to_csv(output_path, index=False)
    print(f"\n报告已保存至 {output_path}")
    
    # 统计信息
    print("\n合规性报告:")
    for symbol in symbols:
        sub = df_res[df_res['symbol'] == symbol]
        if sub.empty:
            print(f"{symbol}: 无数据")
            continue
        pass_rate = sub['compliant'].mean()
        max_error = sub['error'].max()
        avg_error = sub['error'].mean()
        print(f"{symbol}: 通过率 {pass_rate:.1%}, 平均误差 {avg_error:.6f}, 最大误差 {max_error:.6f}")

if __name__ == "__main__":
    run_regression_test()
