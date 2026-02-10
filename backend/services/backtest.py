import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Any
from .indicators import get_market_data, calculate_dkx, calculate_ma
from .resample_utils import resample_data
from .metadata import get_stock_list, get_futures_list
from .futures_master import (
    get_multiplier as get_futures_multiplier, 
    get_trading_hours_type, 
    get_margin_rate,
    get_min_tick
)

def get_symbol_name(symbol: str, market: str) -> str:
    """
    从元数据中获取标的名称。
    
    参数:
        symbol: 标的代码
        market: 市场类型 ("stock" 或 "futures")
        
    返回:
        str: 标的名称（不含代码），如果找不到则返回原代码。
    """
    try:
        if market == 'stock':
            data = get_stock_list()
        else:
            data = get_futures_list()
            
        for item in data:
            if item['value'] == symbol:
                parts = item['label'].split(' ')
                if len(parts) > 1:
                    return parts[1]
                return item['label']
    except:
        pass
    return symbol

def filter_trading_hours(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """
    根据交易时间类型过滤数据。
    
    主要用于剔除夜盘数据或非主要交易时段的数据，以匹配特定的回测需求。
    
    逻辑说明:
    1. 获取品种的交易时间类型 (get_trading_hours_type)。
    2. 根据类型进行时间过滤:
       - 'no_night': 仅保留 09:00 至 15:15 的日盘数据 (包含收盘集合竞价)。
       - 'late_night_2:30', 'late_night': 保留所有数据 (通常包含夜盘)。
    3. 特殊处理 (Volume/Hold 调整):
       - 针对 JD (鸡蛋) 等特殊品种，根据用户需求调整成交量和持仓量单位。
         例如: 将默认的 5吨/手 转换为 500千克/手，系数为 10。
    """
    # 1. 交易时间过滤
    hours_type = get_trading_hours_type(symbol)
    
    filtered_df = df
    if hours_type == 'no_night':
        # 仅保留 09:00 到 15:15 (包含收盘集合竞价)
        filtered_df = df.between_time('09:00', '15:15').copy()
    elif hours_type == 'late_night_2:30':
        # 保留所有数据 (假设数据源已正确处理 02:30 收盘或我们接受所有提供的数据)
        filtered_df = df.copy()
    elif hours_type == 'late_night':
        # 上期所等: 保留所有数据 (包括 21:00-01:00)
        filtered_df = df.copy()
    else:
        filtered_df = df.copy()

    # 2. 成交量/持仓量调整 (Volume/Hold Adjustment)
    # JD: 将默认的 5吨/手 转换为 500千克/手 (用户需求)。
    # 系数 Factor = 5000kg / 500kg = 10。
    # 将 Volume 和 Hold 乘以 10。
    import re
    match = re.match(r"([A-Z]+)", symbol.upper())
    code = match.group(1) if match else symbol.upper()
    
    if code == "JD":
        if 'volume' in filtered_df.columns:
            filtered_df['volume'] = filtered_df['volume'] * 10
        if 'hold' in filtered_df.columns:
            filtered_df['hold'] = filtered_df['hold'] * 10
            
    return filtered_df


    if df.empty:
        return df
        
    # 处理周线/月线
    if period in ['weekly', 'monthly']:
        rule = 'W' if period == 'weekly' else 'M'
        
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

def safe_round(value, ndigits=2):
    """Safely round a value, handling NaN/Inf by returning 0."""
    if value is None:
        return 0
    if isinstance(value, (float, np.floating)):
        if np.isnan(value) or np.isinf(value):
            return 0
    try:
        return round(value, ndigits)
    except:
        return 0

def run_backtest_ma(
    symbols: List[str],
    market: str,
    period: str,
    start_time: str,
    end_time: str,
    initial_capital: float = 100000.0,
    lot_size: int = 20,
    short_period: int = 5,
    long_period: int = 20
) -> Dict[str, Any]:
    """
    运行双均线策略回测。
    """
    results = []
    commission_rate = 0.0003 
    
    for symbol in symbols:
        multiplier = 100 if market == 'stock' else get_futures_multiplier(symbol)
        
        # 1. 获取数据
        custom_periods = ['90', '120', '180', '240']
        fetch_period = period
        need_resample = False
        
        if period in custom_periods:
            need_resample = True
            if period == '90':
                fetch_period = '30'
            elif period == '180':
                fetch_period = '30'
            else:
                fetch_period = '60'
        
        df = get_market_data(symbol, market=market, period=fetch_period)
        
        if df.empty:
            print(f"警告: 未获取到 {symbol} 的数据")
            continue

        if market == 'futures':
            df = filter_trading_hours(df, symbol)
        
        if need_resample:
             df = resample_data(df, period)
        
        if market == 'futures' and period in ['weekly', 'monthly']:
            if df.empty:
                df = get_market_data(symbol, market=market, period='daily')
                df = resample_data(df, period)
        
        if df.empty:
            continue
            
        try:
            if not isinstance(df.index, pd.DatetimeIndex):
                df.index = pd.to_datetime(df.index)
            df.sort_index(inplace=True)
            
            if start_time and end_time:
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
                    df = df.loc[mask].copy()
                except Exception as filter_err:
                    print(f"{symbol} 时间过滤错误: {filter_err}")
                    df = pd.DataFrame()
        except Exception as e:
            print(f"{symbol} 时间过滤错误: {e}")
            continue
            
        if df.empty:
            continue

        # 2. 计算指标 (Calculate MA)
        df = calculate_ma(df, short_period=short_period, long_period=long_period)
        
        # 3. 模拟交易
        trades = []
        equity_curve = []
        position = 0 
        entry_price = 0.0
        entry_time = None
        current_balance = initial_capital
        trade_count = 0
        trade_quantity_value = lot_size * multiplier
        margin_rate = get_margin_rate(symbol)
        max_margin_used = 0.0
        min_tick = get_min_tick(symbol)
        slippage_ticks = 1
        slippage_val = min_tick * slippage_ticks

        for i in range(1, len(df)):
            curr_idx = df.index[i]
            # MA 信号逻辑
            if 'ma_short' not in df.columns or 'ma_long' not in df.columns:
                break
                
            prev_short = df['ma_short'].iloc[i-1]
            prev_long = df['ma_long'].iloc[i-1]
            curr_short = df['ma_short'].iloc[i]
            curr_long = df['ma_long'].iloc[i]
            curr_price = df['close'].iloc[i]
            
            if position != 0:
                current_margin = entry_price * trade_quantity_value * margin_rate
                max_margin_used = max(max_margin_used, current_margin)
            
            if pd.isna(curr_short) or pd.isna(curr_long) or pd.isna(prev_short):
                equity_curve.append({'date': curr_idx.strftime('%Y-%m-%d %H:%M'), 'equity': current_balance})
                continue

            # 金叉: 短线上穿长线
            golden_cross = (prev_short < prev_long) and (curr_short > curr_long)
            # 死叉: 短线下穿长线
            dead_cross = (prev_short > prev_long) and (curr_short < curr_long)
            
            if golden_cross:
                if position == -1:
                    # 平空
                    real_close_price = curr_price + slippage_val
                    pnl = (entry_price - real_close_price) * trade_quantity_value
                    comm = real_close_price * trade_quantity_value * commission_rate
                    net_pnl = pnl - comm
                    current_balance += net_pnl
                    
                    trades.append({
                        'id': trade_count + 1,
                        'time': curr_idx.strftime('%Y-%m-%d %H:%M'),
                        'symbol': symbol,
                        'direction': '平空',
                        'price': curr_price,
                        'real_price': real_close_price,
                        'slippage': slippage_val,
                        'quantity': lot_size,
                        'commission': comm,
                        'profit': net_pnl,
                        'cumulative_profit': current_balance - initial_capital,
                        'position_dir': 0,
                        'funds_occupied': 0,
                        'risk_degree': 0,
                        'daily_balance': current_balance,
                        'order_type': '限价',
                        'counterparty': '模拟撮合'
                    })
                    trade_count += 1
                    
                    # 开多
                    real_open_price = curr_price + slippage_val
                    comm_open = real_open_price * trade_quantity_value * commission_rate
                    current_balance -= comm_open
                    position = 1
                    entry_price = real_open_price
                    entry_time = curr_idx
                    
                    curr_margin = real_open_price * multiplier * margin_rate * lot_size
                    risk_deg = curr_margin / current_balance if current_balance > 0 else 0
                    
                    trades.append({
                        'id': trade_count + 1,
                        'time': curr_idx.strftime('%Y-%m-%d %H:%M'),
                        'symbol': symbol,
                        'direction': '开多',
                        'price': curr_price,
                        'real_price': real_open_price,
                        'slippage': slippage_val,
                        'quantity': lot_size,
                        'commission': comm_open,
                        'profit': -comm_open,
                        'cumulative_profit': current_balance - initial_capital,
                        'position_dir': 1,
                        'funds_occupied': curr_margin,
                        'risk_degree': risk_deg,
                        'daily_balance': current_balance,
                        'order_type': '限价',
                        'counterparty': '模拟撮合'
                    })
                    trade_count += 1
                    
                elif position == 0:
                    # 开多
                    real_open_price = curr_price + slippage_val
                    comm_open = real_open_price * trade_quantity_value * commission_rate
                    current_balance -= comm_open
                    position = 1
                    entry_price = real_open_price
                    entry_time = curr_idx
                    
                    curr_margin = entry_price * trade_quantity_value * margin_rate
                    risk_deg = curr_margin / current_balance if current_balance > 0 else 0
                    
                    trades.append({
                        'id': trade_count + 1,
                        'time': curr_idx.strftime('%Y-%m-%d %H:%M'),
                        'symbol': symbol,
                        'direction': '开多',
                        'price': curr_price,
                        'real_price': real_open_price,
                        'slippage': slippage_val,
                        'quantity': lot_size,
                        'commission': comm_open,
                        'profit': -comm_open,
                        'cumulative_profit': current_balance - initial_capital,
                        'position_dir': 1,
                        'funds_occupied': curr_margin,
                        'risk_degree': risk_deg,
                        'daily_balance': current_balance,
                        'order_type': '限价',
                        'counterparty': '模拟撮合'
                    })
                    trade_count += 1
                    
            elif dead_cross:
                if position == 1:
                    # 平多
                    real_close_price = curr_price - slippage_val
                    pnl = (real_close_price - entry_price) * trade_quantity_value
                    comm = real_close_price * trade_quantity_value * commission_rate
                    net_pnl = pnl - comm
                    current_balance += net_pnl
                    
                    trades.append({
                        'id': trade_count + 1,
                        'time': curr_idx.strftime('%Y-%m-%d %H:%M'),
                        'symbol': symbol,
                        'direction': '平多',
                        'price': curr_price,
                        'real_price': real_close_price,
                        'slippage': slippage_val,
                        'quantity': lot_size,
                        'commission': comm,
                        'profit': net_pnl,
                        'cumulative_profit': current_balance - initial_capital,
                        'position_dir': 0,
                        'funds_occupied': 0,
                        'risk_degree': 0,
                        'daily_balance': current_balance,
                        'order_type': '限价',
                        'counterparty': '模拟撮合'
                    })
                    trade_count += 1
                    
                    # 开空
                    real_open_price = curr_price - slippage_val
                    comm_open = real_open_price * trade_quantity_value * commission_rate
                    current_balance -= comm_open
                    position = -1
                    entry_price = real_open_price
                    entry_time = curr_idx
                    
                    curr_margin = entry_price * trade_quantity_value * margin_rate
                    risk_deg = curr_margin / current_balance if current_balance > 0 else 0
                    
                    trades.append({
                        'id': trade_count + 1,
                        'time': curr_idx.strftime('%Y-%m-%d %H:%M'),
                        'symbol': symbol,
                        'direction': '开空',
                        'price': curr_price,
                        'real_price': real_open_price,
                        'slippage': slippage_val,
                        'quantity': lot_size,
                        'commission': comm_open,
                        'profit': -comm_open,
                        'cumulative_profit': current_balance - initial_capital,
                        'position_dir': -1,
                        'funds_occupied': curr_margin,
                        'risk_degree': risk_deg,
                        'daily_balance': current_balance,
                        'order_type': '限价',
                        'counterparty': '模拟撮合'
                    })
                    trade_count += 1
                    
                elif position == 0:
                    # 开空
                    real_open_price = curr_price - slippage_val
                    comm_open = real_open_price * trade_quantity_value * commission_rate
                    current_balance -= comm_open
                    position = -1
                    entry_price = real_open_price
                    entry_time = curr_idx
                    
                    curr_margin = entry_price * trade_quantity_value * margin_rate
                    risk_deg = curr_margin / current_balance if current_balance > 0 else 0
                    
                    trades.append({
                        'id': trade_count + 1,
                        'time': curr_idx.strftime('%Y-%m-%d %H:%M'),
                        'symbol': symbol,
                        'direction': '开空',
                        'price': curr_price,
                        'real_price': real_open_price,
                        'slippage': slippage_val,
                        'quantity': lot_size,
                        'commission': comm_open,
                        'profit': -comm_open,
                        'cumulative_profit': current_balance - initial_capital,
                        'position_dir': -1,
                        'funds_occupied': curr_margin,
                        'risk_degree': risk_deg,
                        'daily_balance': current_balance,
                        'order_type': '限价',
                        'counterparty': '模拟撮合'
                    })
                    trade_count += 1
            
            equity_curve.append({'date': curr_idx.strftime('%Y-%m-%d %H:%M'), 'equity': current_balance})
            
        # 4. 统计指标
        final_equity = current_balance
        total_profit = final_equity - initial_capital
        total_return = (total_profit / initial_capital) * 100
        
        days = (df.index[-1] - df.index[0]).days
        if days > 0 and final_equity > 0 and initial_capital > 0:
            try:
                annualized_return = (pow(final_equity / initial_capital, 365 / days) - 1) * 100
            except:
                annualized_return = 0
        else:
            annualized_return = 0
            
        winning_trades = [t for t in trades if t['profit'] > 0 and t['direction'] in ['平多', '平空']]
        losing_trades = [t for t in trades if t['profit'] <= 0 and t['direction'] in ['平多', '平空']]
        closed_trades = [t for t in trades if t['direction'] in ['平多', '平空']]
        total_closed_trades = len(closed_trades)
        
        win_rate = (len(winning_trades) / total_closed_trades * 100) if total_closed_trades > 0 else 0
        
        equities = [e['equity'] for e in equity_curve]
        max_drawdown = 0
        if equities:
            peak = equities[0]
            for e in equities:
                if e > peak:
                    peak = e
                dd = (peak - e) / peak * 100
                if dd > max_drawdown:
                    max_drawdown = dd
                    
        df_equity = pd.DataFrame(equity_curve)
        sharpe_ratio = 0
        if not df_equity.empty:
            df_equity['date'] = pd.to_datetime(df_equity['date'])
            df_equity.set_index('date', inplace=True)
            daily_returns = df_equity['equity'].resample('D').last().ffill().pct_change().dropna()
            if not daily_returns.empty and daily_returns.std() != 0:
                sharpe_ratio = (daily_returns.mean() / daily_returns.std()) * (252 ** 0.5)
                
        realized_profit = sum(t['profit'] for t in trades if t['direction'] in ['平多', '平空'])
        floating_profit = 0
        if position != 0:
            last_price = df['close'].iloc[-1]
            if position == 1:
                floating_profit = (last_price - entry_price) * trade_quantity_value
            else:
                floating_profit = (entry_price - last_price) * trade_quantity_value
                
        avg_profit = realized_profit / total_closed_trades if total_closed_trades > 0 else 0
        avg_win = sum(t['profit'] for t in winning_trades) / len(winning_trades) if winning_trades else 0
        avg_loss = sum(t['profit'] for t in losing_trades) / len(losing_trades) if losing_trades else 0
        profit_factor = abs(sum(t['profit'] for t in winning_trades) / sum(t['profit'] for t in losing_trades)) if losing_trades and sum(t['profit'] for t in losing_trades) != 0 else float('inf')
        
        max_consecutive_wins = 0
        max_consecutive_losses = 0
        current_wins = 0
        current_losses = 0
        for t in closed_trades:
            if t['profit'] > 0:
                current_wins += 1
                current_losses = 0
                max_consecutive_wins = max(max_consecutive_wins, current_wins)
            else:
                current_losses += 1
                current_wins = 0
                max_consecutive_losses = max(max_consecutive_losses, current_losses)

        return_on_margin = (total_profit / max_margin_used * 100) if max_margin_used > 0 else 0
        
        avg_volume = df['volume'].mean()
        avg_price_val = df['close'].mean()
        strategy_capacity = avg_volume * avg_price_val * multiplier * 0.01 
        
        max_daily_loss = 0
        if not df_equity.empty:
            daily_pnl = df_equity['equity'].resample('D').last().diff()
            if not daily_pnl.empty:
                max_daily_loss = daily_pnl.min()

        statistics = {
            'total_trades': total_closed_trades,
            'win_rate': safe_round(win_rate, 2),
            'max_drawdown': safe_round(max_drawdown, 2),
            'sharpe_ratio': safe_round(sharpe_ratio, 2),
            'total_return': safe_round(total_return, 2),
            'annualized_return': safe_round(annualized_return, 2),
            'total_profit': safe_round(total_profit, 2),
            'final_equity': safe_round(final_equity, 2),
            'realized_profit': safe_round(realized_profit, 2),
            'floating_profit': safe_round(floating_profit, 2),
            'avg_profit': safe_round(avg_profit, 2),
            'avg_win': safe_round(avg_win, 2),
            'avg_loss': safe_round(avg_loss, 2),
            'profit_factor': safe_round(profit_factor, 2) if profit_factor != float('inf') else 999,
            'max_consecutive_wins': max_consecutive_wins,
            'max_consecutive_losses': max_consecutive_losses,
            'return_on_margin': safe_round(return_on_margin, 2),
            'max_margin_used': safe_round(max_margin_used, 2),
            'avg_slippage': safe_round(slippage_val, 2),
            'max_slippage': safe_round(slippage_val, 2),
            'strategy_capacity': safe_round(strategy_capacity, 0),
            'max_daily_loss': safe_round(max_daily_loss, 2)
        }
        
        chart_data = []
        
        for idx, row in df.iterrows():
            def get_val(val):
                if pd.isna(val) or np.isinf(val):
                    return None
                return val

            chart_data.append({
                'date': idx.strftime('%Y-%m-%d %H:%M'),
                'open': get_val(row['open']),
                'close': get_val(row['close']),
                'low': get_val(row['low']),
                'high': get_val(row['high']),
                'ma_short': get_val(row['ma_short']),
                'ma_long': get_val(row['ma_long']),
                'volume': get_val(row['volume'])
            })
            
        results.append({
            'symbol': symbol,
            'symbol_name': get_symbol_name(symbol, market),
            'trades': trades,
            'statistics': statistics,
            'chart_data': chart_data
        })
        
    # Sort Results
    # Default Rule: Return Rate (Desc) -> Profit Factor (Desc) -> Symbol (Asc)
    results.sort(key=lambda x: (
        -x['statistics']['return_on_margin'], 
        -x['statistics']['profit_factor'], 
        x['symbol']
    ))

    return results

def run_backtest_dkx(
    symbols: List[str],
    market: str,
    period: str,
    start_time: str,
    end_time: str,
    initial_capital: float = 100000.0,
    lot_size: int = 20
) -> Dict[str, Any]:
    """
    运行 DKX 策略回测。
    
    参数:
        symbols: 标的代码列表
        market: 市场类型 ("stock" 或 "futures")
        period: K线周期
        start_time: 回测开始时间
        end_time: 回测结束时间
        initial_capital: 初始资金 (默认 100,000)
        lot_size: 交易手数 (默认 20)
        
    返回:
        Dict: 包含回测结果的字典
    """
    
    results = []
    
    # 交易费用设置
    # commission_rate: 手续费率，双边万三 (0.0003)
    commission_rate = 0.0003 
    
    for symbol in symbols:
        # 确定合约乘数 (Multiplier)
        # 股票默认为 100 (1手=100股)
        # 期货则根据品种获取对应乘数
        multiplier = 100 if market == 'stock' else get_futures_multiplier(symbol)
        
        # 1. 获取数据 (Fetch Data)
        # 处理自定义分钟周期
        custom_periods = ['90', '120', '180', '240']
        fetch_period = period
        need_resample = False
        
        if period in custom_periods:
            need_resample = True
            if period == '90':
                fetch_period = '30'
            elif period == '180':
                # 为确保 180 分钟周期在午休 (11:30-13:30) 和夜盘等场景下的切分精度，
                # 必须使用 30 分钟数据作为基础源，而非 60 分钟。
                # 原因：纯日盘品种 09:00-11:30 为 150 分钟，需补 30 分钟 (13:30-14:00) 才能凑齐 180 分钟。
                fetch_period = '30'
            else:
                fetch_period = '60'
        
        df = get_market_data(symbol, market=market, period=fetch_period)
        
        if df.empty:
            print(f"警告: 未获取到 {symbol} 的数据")
            continue

        # 应用交易时间过滤 (新需求)
        # 期货市场可能需要过滤夜盘等
        if market == 'futures':
            df = filter_trading_hours(df, symbol)
        
        # 如果需要重采样 (Resample)
        if need_resample:
             df = resample_data(df, period)
        
        # 处理期货的周线/月线 (如果 API 不直接支持)
        if market == 'futures' and period in ['weekly', 'monthly']:
            if df.empty:
                df = get_market_data(symbol, market=market, period='daily')
                df = resample_data(df, period)
        
        if df.empty:
            continue
            
        # 根据时间范围过滤数据
        try:
            # 确保 index 为 datetime 类型并排序
            if not isinstance(df.index, pd.DatetimeIndex):
                df.index = pd.to_datetime(df.index)
            df.sort_index(inplace=True)
            
            # 使用 loc 进行切片，避免 dtype 比较错误
            if start_time and end_time:
                try:
                    # 1. 统一转换为 Timestamp
                    ts_start = pd.to_datetime(start_time)
                    ts_end = pd.to_datetime(end_time)
                    
                    # 2. 检查 DataFrame 索引的时区属性
                    index_tz = df.index.tz
                    
                    # 3. 对齐查询时间的时区
                    if index_tz is None:
                        # 如果索引是 naive (无时区)，则将查询时间也转换为 naive
                        if ts_start.tzinfo is not None:
                            # 移除时区信息，使之变为 naive datetime，以便与索引比较
                            ts_start = ts_start.tz_localize(None)
                            ts_end = ts_end.tz_localize(None)
                    else:
                        # 如果索引是 aware (有时区)，则将查询时间转换为对应时区
                        if ts_start.tzinfo is None:
                            ts_start = ts_start.tz_localize(index_tz)
                            ts_end = ts_end.tz_localize(index_tz)
                        else:
                            ts_start = ts_start.tz_convert(index_tz)
                            ts_end = ts_end.tz_convert(index_tz)
                            
                    # 4. 使用布尔索引过滤 (比 loc 切片更健壮)
                    mask = (df.index >= ts_start) & (df.index <= ts_end)
                    df = df.loc[mask].copy()
                    
                except Exception as filter_err:
                    print(f"{symbol} 时间过滤错误: {filter_err}")
                    df = pd.DataFrame()
        except Exception as e:
            print(f"{symbol} 时间过滤错误: {e}")
            continue
            
        if df.empty:
            continue

        # 2. 计算指标 (Calculate Indicators)
        df = calculate_dkx(df)
        
        # 3. 模拟交易 (Simulate Trading)
        trades = []
        equity_curve = []
        
        # 状态变量
        # position: 0=空仓, 1=多头, -1=空头
        position = 0 
        entry_price = 0.0
        entry_time = None
        current_balance = initial_capital
        trade_count = 0
        
        # 计算实际交易数量 (Value Quantity)
        # lot_size 是用户输入的手数 (如 20 手)
        # multiplier 是合约乘数 (如 10 吨/手)
        # 我们记录 lot_size 为 'quantity' 用于显示
        # 我们使用 lot_size * multiplier 进行盈亏计算 (trade_quantity_value)
        
        trade_quantity_value = lot_size * multiplier
        
        # 最大保证金占用跟踪 (Max Margin Usage Tracking)
        # 最大占用 = Max(开仓价格 * 交易单位 * 保证金比例 * 手数)
        margin_rate = get_margin_rate(symbol)
        max_margin_used = 0.0
        
        # 滑点设置 (Slippage Settings)
        min_tick = get_min_tick(symbol)
        slippage_ticks = 1
        slippage_val = min_tick * slippage_ticks

        # 调试特定品种的保证金计算
        if symbol.upper().startswith('FG'):
            print(f"DEBUG FG Margin: Price={df['close'].iloc[0]}, Multiplier={multiplier}, MarginRate={margin_rate}, Lots={lot_size}")
            # 预期: Price * 20 * 0.05 * Lots

        # 遍历数据
        for i in range(1, len(df)):
            curr_idx = df.index[i]
            prev_dkx = df['dkx'].iloc[i-1]
            prev_madkx = df['madkx'].iloc[i-1]
            curr_dkx = df['dkx'].iloc[i]
            curr_madkx = df['madkx'].iloc[i]
            curr_price = df['close'].iloc[i]
            
            # 如果持有仓位，更新最大保证金占用
            if position != 0:
                # 保证金通常基于开仓价计算 (初始保证金)
                # 也可以基于市价计算 (维持保证金)
                # 这里为了简单起见，跟踪 "最大初始保证金占用"
                current_margin = entry_price * trade_quantity_value * margin_rate
                max_margin_used = max(max_margin_used, current_margin)
            
            if pd.isna(curr_dkx) or pd.isna(curr_madkx) or pd.isna(prev_dkx):
                equity_curve.append({'date': curr_idx.strftime('%Y-%m-%d %H:%M'), 'equity': current_balance})
                continue

            # 信号判断
            # 金叉: DKX 上穿 MADKX
            golden_cross = (prev_dkx < prev_madkx) and (curr_dkx > curr_madkx)
            # 死叉: DKX 下穿 MADKX
            dead_cross = (prev_dkx > prev_madkx) and (curr_dkx < curr_madkx)
            
            action = None # 'buy', 'sell', 'close_buy', 'close_sell'
            
            # 交易逻辑
            if golden_cross:
                if position == -1:
                    # 平空开多 (Close Short, Open Long)
                    # 1. 平空 (Buy to Cover) -> 价格 + 滑点
                    real_close_price = curr_price + slippage_val
                    pnl = (entry_price - real_close_price) * trade_quantity_value
                    comm = real_close_price * trade_quantity_value * commission_rate
                    net_pnl = pnl - comm
                    current_balance += net_pnl
                    
                    trades.append({
                        'id': trade_count + 1,
                        'time': curr_idx.strftime('%Y-%m-%d %H:%M'),
                        'symbol': symbol,
                        'direction': '平空',
                        'price': curr_price,
                        'real_price': real_close_price,
                        'slippage': slippage_val,
                        'quantity': lot_size, # 显示手数
                        'commission': comm,
                        'profit': net_pnl,
                        'cumulative_profit': current_balance - initial_capital,
                        'position_dir': 0,
                        'funds_occupied': 0,
                        'risk_degree': 0,
                        'daily_balance': current_balance,
                        'order_type': '限价',
                        'counterparty': '模拟撮合'
                    })
                    trade_count += 1
                    
                    # 2. 开多 (Buy) -> 价格 + 滑点
                    real_open_price = curr_price + slippage_val
                    comm_open = real_open_price * trade_quantity_value * commission_rate
                    current_balance -= comm_open # 开仓扣手续费
                    position = 1
                    entry_price = real_open_price
                    entry_time = curr_idx
                    
                    # 资金占用 = 合约最新价 × 交易单位 × 保证金比例 × 手数
                    curr_margin = real_open_price * multiplier * margin_rate * lot_size
                    risk_deg = curr_margin / current_balance if current_balance > 0 else 0
                    
                    trades.append({
                        'id': trade_count + 1,
                        'time': curr_idx.strftime('%Y-%m-%d %H:%M'),
                        'symbol': symbol,
                        'direction': '开多',
                        'price': curr_price,
                        'real_price': real_open_price,
                        'slippage': slippage_val,
                        'quantity': lot_size,
                        'commission': comm_open,
                        'profit': -comm_open, # 开仓即亏手续费
                        'cumulative_profit': current_balance - initial_capital,
                        'position_dir': 1,
                        'funds_occupied': curr_margin,
                        'risk_degree': risk_deg,
                        'daily_balance': current_balance,
                        'order_type': '限价',
                        'counterparty': '模拟撮合'
                    })
                    trade_count += 1
                    
                elif position == 0:
                    # 开多 (Buy) -> 价格 + 滑点
                    real_open_price = curr_price + slippage_val
                    comm_open = real_open_price * trade_quantity_value * commission_rate
                    current_balance -= comm_open
                    position = 1
                    entry_price = real_open_price
                    entry_time = curr_idx
                    
                    curr_margin = entry_price * trade_quantity_value * margin_rate
                    risk_deg = curr_margin / current_balance if current_balance > 0 else 0
                    
                    trades.append({
                        'id': trade_count + 1,
                        'time': curr_idx.strftime('%Y-%m-%d %H:%M'),
                        'symbol': symbol,
                        'direction': '开多',
                        'price': curr_price,
                        'real_price': real_open_price,
                        'slippage': slippage_val,
                        'quantity': lot_size,
                        'commission': comm_open,
                        'profit': -comm_open,
                        'cumulative_profit': current_balance - initial_capital,
                        'position_dir': 1,
                        'funds_occupied': curr_margin,
                        'risk_degree': risk_deg,
                        'daily_balance': current_balance,
                        'order_type': '限价',
                        'counterparty': '模拟撮合'
                    })
                    trade_count += 1
                    
            elif dead_cross:
                if position == 1:
                    # 平多开空 (Close Long, Open Short)
                    # 1. 平多 (Sell to Cover) -> 价格 - 滑点
                    real_close_price = curr_price - slippage_val
                    pnl = (real_close_price - entry_price) * trade_quantity_value
                    comm = real_close_price * trade_quantity_value * commission_rate
                    net_pnl = pnl - comm
                    current_balance += net_pnl
                    
                    trades.append({
                        'id': trade_count + 1,
                        'time': curr_idx.strftime('%Y-%m-%d %H:%M'),
                        'symbol': symbol,
                        'direction': '平多',
                        'price': curr_price,
                        'real_price': real_close_price,
                        'slippage': slippage_val,
                        'quantity': lot_size,
                        'commission': comm,
                        'profit': net_pnl,
                        'cumulative_profit': current_balance - initial_capital,
                        'position_dir': 0,
                        'funds_occupied': 0,
                        'risk_degree': 0,
                        'daily_balance': current_balance,
                        'order_type': '限价',
                        'counterparty': '模拟撮合'
                    })
                    trade_count += 1
                    
                    # 2. 开空 (Sell Short) -> Price - Slippage
                    real_open_price = curr_price - slippage_val
                    comm_open = real_open_price * trade_quantity_value * commission_rate
                    current_balance -= comm_open
                    position = -1
                    entry_price = real_open_price
                    entry_time = curr_idx
                    
                    curr_margin = entry_price * trade_quantity_value * margin_rate
                    risk_deg = curr_margin / current_balance if current_balance > 0 else 0
                    
                    trades.append({
                        'id': trade_count + 1,
                        'time': curr_idx.strftime('%Y-%m-%d %H:%M'),
                        'symbol': symbol,
                        'direction': '开空',
                        'price': curr_price,
                        'real_price': real_open_price,
                        'slippage': slippage_val,
                        'quantity': lot_size,
                        'commission': comm_open,
                        'profit': -comm_open,
                        'cumulative_profit': current_balance - initial_capital,
                        'position_dir': -1,
                        'funds_occupied': curr_margin,
                        'risk_degree': risk_deg,
                        'daily_balance': current_balance,
                        'order_type': '限价',
                        'counterparty': '模拟撮合'
                    })
                    trade_count += 1
                    
                elif position == 0:
                    # 开空 (Sell Short) -> Price - Slippage
                    real_open_price = curr_price - slippage_val
                    comm_open = real_open_price * trade_quantity_value * commission_rate
                    current_balance -= comm_open
                    position = -1
                    entry_price = real_open_price
                    entry_time = curr_idx
                    
                    curr_margin = entry_price * trade_quantity_value * margin_rate
                    risk_deg = curr_margin / current_balance if current_balance > 0 else 0
                    
                    trades.append({
                        'id': trade_count + 1,
                        'time': curr_idx.strftime('%Y-%m-%d %H:%M'),
                        'symbol': symbol,
                        'direction': '开空',
                        'price': curr_price,
                        'real_price': real_open_price,
                        'slippage': slippage_val,
                        'quantity': lot_size,
                        'commission': comm_open,
                        'profit': -comm_open,
                        'cumulative_profit': current_balance - initial_capital,
                        'position_dir': -1,
                        'funds_occupied': curr_margin,
                        'risk_degree': risk_deg,
                        'daily_balance': current_balance,
                        'order_type': '限价',
                        'counterparty': '模拟撮合'
                    })
                    trade_count += 1

            # 计算浮动权益 (用于最大回撤计算)
            floating_pnl = 0
            if position == 1:
                floating_pnl = (curr_price - entry_price) * trade_quantity_value
            elif position == -1:
                floating_pnl = (entry_price - curr_price) * trade_quantity_value
                
            equity_curve.append({
                'date': curr_idx.strftime('%Y-%m-%d %H:%M'),
                'equity': current_balance + floating_pnl
            })

        # 4. Calculate Statistics
        if not equity_curve:
            continue
            
        equities = [e['equity'] for e in equity_curve]
        max_equity = np.maximum.accumulate(equities)
        drawdowns = (max_equity - equities) / max_equity
        max_drawdown = np.max(drawdowns) if len(drawdowns) > 0 else 0
        
        total_return = (equities[-1] - initial_capital) / initial_capital
        
        # Sharpe Ratio (Daily) - Robust
        # Resample equity curve to daily to ensure correct annualization
        sharpe = 0
        if equity_curve:
            eq_df_s = pd.DataFrame(equity_curve)
            eq_df_s['date'] = pd.to_datetime(eq_df_s['date'])
            eq_df_s.set_index('date', inplace=True)
            # Resample to Daily Close
            daily_eq_s = eq_df_s['equity'].resample('D').last().dropna()
            
            if len(daily_eq_s) > 1:
                daily_returns = daily_eq_s.pct_change().dropna()
                if len(daily_returns) > 0 and daily_returns.std() != 0:
                    sharpe = (daily_returns.mean() / daily_returns.std()) * np.sqrt(252)

        # Legacy calculation (commented out)
        # returns = pd.Series(equities).pct_change().dropna()
        # if len(returns) > 0 and returns.std() != 0:
        #    sharpe = (returns.mean() / returns.std()) * np.sqrt(252) # Assuming daily
        # else:
        #    sharpe = 0
            
        # Win Rate (based on closed trades with profit > 0)
        closed_trades = [t for t in trades if t['direction'] in ['平多', '平空']]
        winning_trades = [t for t in closed_trades if t['profit'] > 0]
        losing_trades = [t for t in closed_trades if t['profit'] <= 0]
        
        win_rate = len(winning_trades) / len(closed_trades) if closed_trades else 0
        
        # Extended Stats
        avg_profit = np.mean([t['profit'] for t in closed_trades]) if closed_trades else 0
        avg_win = np.mean([t['profit'] for t in winning_trades]) if winning_trades else 0
        avg_loss = np.mean([t['profit'] for t in losing_trades]) if losing_trades else 0
        
        gross_profit = sum([t['profit'] for t in winning_trades])
        gross_loss = abs(sum([t['profit'] for t in losing_trades]))
        profit_factor = gross_profit / gross_loss if gross_loss != 0 else 0
        
        # Consecutive Wins/Losses
        max_consecutive_wins = 0
        max_consecutive_losses = 0
        current_wins = 0
        current_losses = 0
        
        for t in closed_trades:
            if t['profit'] > 0:
                current_wins += 1
                current_losses = 0
                max_consecutive_wins = max(max_consecutive_wins, current_wins)
            else:
                current_losses += 1
                current_wins = 0
                max_consecutive_losses = max(max_consecutive_losses, current_losses)

        realized_profit = sum(t['profit'] for t in trades)
        total_profit = equities[-1] - initial_capital
        floating_profit = total_profit - realized_profit
        
        # Return on Margin (ROI)
        # Net Profit / Max Margin Used
        # If Max Margin is 0 (no trades), ROI is 0
        return_on_margin = total_profit / max_margin_used if max_margin_used > 0 else 0
        
        # New Metrics
        avg_slippage = slippage_val # Simulated constant
        max_slippage = slippage_val # Simulated constant
        
        # Strategy Capacity Estimate (Simplified)
        # Min(Daily Volume * Price * 0.01) (1% of daily turnover)
        # We need daily volume. Since df might be minute, we approximate.
        # Use average daily volume from input df (if daily) or sum of volume.
        # Just use average turnover * 0.01 as a rough estimate.
        if not df.empty and 'volume' in df.columns and 'close' in df.columns:
            avg_turnover = (df['volume'] * df['close'] * multiplier).mean()
            strategy_capacity = avg_turnover * 0.01
        else:
            strategy_capacity = 0
            
        # Max Daily Loss
        # Need to resample equity to daily and calc diff
        if equity_curve:
            eq_df = pd.DataFrame(equity_curve)
            eq_df['date'] = pd.to_datetime(eq_df['date'])
            eq_df.set_index('date', inplace=True)
            daily_eq = eq_df.resample('D').last().dropna()
            if len(daily_eq) > 1:
                daily_pnl = daily_eq['equity'].diff()
                max_daily_loss = daily_pnl.min()
                if max_daily_loss > 0: max_daily_loss = 0 # No loss
            else:
                max_daily_loss = 0
        else:
            max_daily_loss = 0

        # Helper to clean float values for JSON compliance
        def clean_val(v):
            if isinstance(v, (float, np.float64, np.float32)):
                if np.isnan(v) or np.isinf(v):
                    return 0.0
                return float(v) # Ensure native float
            return v

        stats = {
            'total_trades': len(trades),
            'win_rate': clean_val(win_rate),
            'max_drawdown': clean_val(max_drawdown),
            'sharpe_ratio': clean_val(sharpe),
            'total_return': clean_val(total_return),
            'annualized_return': 0, 
            'total_profit': clean_val(total_profit),
            'final_equity': clean_val(equities[-1]),
            'realized_profit': clean_val(realized_profit),
            'floating_profit': clean_val(floating_profit),
            # New Stats
            'avg_profit': clean_val(avg_profit),
            'avg_win': clean_val(avg_win),
            'avg_loss': clean_val(avg_loss),
            'profit_factor': clean_val(profit_factor),
            'max_consecutive_wins': max_consecutive_wins,
            'max_consecutive_losses': max_consecutive_losses,
            'return_on_margin': clean_val(return_on_margin),
            'max_margin_used': clean_val(max_margin_used),
            # Advanced Stats
            'avg_slippage': clean_val(avg_slippage),
            'max_slippage': clean_val(max_slippage),
            'strategy_capacity': clean_val(strategy_capacity),
            'max_daily_loss': clean_val(max_daily_loss)
        }
        
        # Prepare Chart Data
        chart_data = []
        for i in range(len(df)):
            idx = df.index[i]
            row = df.iloc[i]
            
            # Helper to clean chart values (Inf/NaN -> None)
            def clean_chart_val(v):
                if pd.isna(v) or np.isinf(v):
                    return None
                return float(v)

            chart_data.append({
                'date': idx.strftime('%Y-%m-%d %H:%M'),
                'open': clean_chart_val(row['open']),
                'close': clean_chart_val(row['close']),
                'low': clean_chart_val(row['low']),
                'high': clean_chart_val(row['high']),
                'dkx': clean_chart_val(row['dkx']),
                'madkx': clean_chart_val(row['madkx']),
            })
            
        # Get Symbol Name
        symbol_name = get_symbol_name(symbol, market)

        results.append({
            'symbol': symbol,
            'symbol_name': symbol_name,
            'trades': trades,
            'statistics': stats,
            'chart_data': chart_data
        })
    
    # Sort Results
    # Default Rule: Return Rate (Desc) -> Profit Factor (Desc) -> Symbol (Asc)
    # return_on_margin, profit_factor
    results.sort(key=lambda x: (
        -x['statistics']['return_on_margin'], 
        -x['statistics']['profit_factor'], 
        x['symbol']
    ))

    # Sort Results
    # Default Rule: Return Rate (Desc) -> Profit Factor (Desc) -> Symbol (Asc)
    # return_on_margin, profit_factor
    results.sort(key=lambda x: (
        -x['statistics']['return_on_margin'], 
        -x['statistics']['profit_factor'], 
        x['symbol']
    ))

    return results

def calculate_statistics(trades: List[Dict], duration_days: int) -> Dict:
    if not trades:
        return {
            "total_trades": 0,
            "win_rate": 0.0,
            "avg_pl_ratio": 0.0,
            "max_drawdown": 0.0,
            "sharpe_ratio": 0.0,
            "total_return": 0.0,
            "annualized_return": 0.0
        }
        
    total_trades = len(trades)
    wins = [t for t in trades if t['profit'] > 0]
    losses = [t for t in trades if t['profit'] <= 0]
    
    win_rate = len(wins) / total_trades if total_trades > 0 else 0
    
    avg_win = np.mean([t['profit'] for t in wins]) if wins else 0
    avg_loss = np.mean([abs(t['profit']) for t in losses]) if losses else 0
    avg_pl_ratio = avg_win / avg_loss if avg_loss > 0 else (999.0 if avg_win > 0 else 0.0)
    
    total_return_pct = sum([t['profit_pct'] for t in trades])
    
    # Drawdown (Equity Curve based on pct)
    equity = np.cumsum([t['profit_pct'] for t in trades])
    peak = np.maximum.accumulate(equity)
    drawdown = peak - equity
    max_drawdown = np.max(drawdown) if len(drawdown) > 0 else 0
    
    # Sharpe
    returns = [t['profit_pct'] for t in trades]
    std_dev = np.std(returns)
    if std_dev > 0:
        sharpe = np.mean(returns) / std_dev * np.sqrt(len(trades))
    else:
        sharpe = 0
        
    # Annualized Return (Simple)
    # If duration is 0 (intraday), treat as 1 day
    years = duration_days / 365.0
    annualized = total_return_pct / years if years > 0 else 0
    
    return {
        "total_trades": int(total_trades),
        "win_rate": float(round(win_rate * 100, 2)),
        "avg_pl_ratio": float(round(avg_pl_ratio, 2)),
        "max_drawdown": float(round(max_drawdown * 100, 2)),
        "sharpe_ratio": float(round(sharpe, 2)),
        "total_return": float(round(total_return_pct * 100, 2)),
        "annualized_return": float(round(annualized * 100, 2))
    }
