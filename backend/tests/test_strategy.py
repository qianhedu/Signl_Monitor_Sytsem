import unittest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

# Add backend directory to path to allow imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.indicators import check_dkx_signal, check_ma_signal

class TestStrategySignals(unittest.TestCase):
    def setUp(self):
        # 创建一个包含 100 天数据的示例 DataFrame
        dates = pd.date_range(start="2023-01-01", periods=100, freq="D")
        self.df = pd.DataFrame(index=dates)
        self.df['close'] = 100.0
        
        # 设置 DKX/MADKX 列
        # 场景: 
        # 第 50 天: 金叉 (DKX 向上穿过 MADKX)
        # 第 80 天: 死叉 (DKX 向下穿过 MADKX)
        # 第 99 天 (最后一天): 金叉
        
        self.df['dkx'] = 100.0
        self.df['madkx'] = 100.0
        
        # 初始化为无交叉状态 (DKX < MADKX)
        self.df['dkx'] = 99.0
        self.df['madkx'] = 100.0
        
        # 第 50 天: 交叉 (DKX > MADKX) - 买入信号
        # 使用 iloc 进行基于位置的赋值
        dkx_col = self.df.columns.get_loc('dkx')
        madkx_col = self.df.columns.get_loc('madkx')
        
        # 0-49: DKX=99, MADKX=100 (默认)
        
        # 第 50 天 (索引 50): 交叉
        self.df.iloc[50, dkx_col] = 101.0
        
        # 51-78: 上升状态
        self.df.iloc[51:79, dkx_col] = 101.0
        
        # 第 79 天: 交叉前夕 (仍为上升)
        self.df.iloc[79, dkx_col] = 101.0
        
        # 第 80 天: 交叉 (DKX < MADKX) - 卖出信号
        self.df.iloc[80, dkx_col] = 99.0
        
        # 81-97: 下降状态 (默认 99)
        
        # 第 98 天: 交叉前夕 (仍为下降)
        self.df.iloc[98, dkx_col] = 99.0

        # 第 99 天: 交叉 (DKX > MADKX) - 买入信号
        self.df.iloc[99, dkx_col] = 101.0
        
        # 为 check_ma_signal 设置 MA 列 (逻辑相同)
        self.df['ma_short'] = self.df['dkx']
        self.df['ma_long'] = self.df['madkx']

    def test_dkx_lookback_1(self):
        """测试回溯 1 个周期 (仅检查最后一个 K 线转换)"""
        # 回溯 1 应检查从索引 98 到 99 的转换
        signals = check_dkx_signal(self.df, lookback=1)
        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0]['signal'], 'BUY')
        self.assertEqual(signals[0]['date'], self.df.index[99].strftime("%Y-%m-%d %H:%M:%S"))

    def test_dkx_lookback_20(self):
        """测试回溯 20 个周期 (应包含第 80 天和第 99 天)"""
        # 第 99 天是索引 99。第 80 天是索引 80。
        # 从 99 回溯 20 到达索引 79。
        # 子集将是索引 79 到 99。
        # 索引 80 是死叉。索引 99 是金叉。
        signals = check_dkx_signal(self.df, lookback=20)
        self.assertEqual(len(signals), 2)
        self.assertEqual(signals[0]['signal'], 'SELL') # 第 80 天
        self.assertEqual(signals[1]['signal'], 'BUY')  # 第 99 天

    def test_dkx_lookback_max(self):
        """测试回溯整个历史 (lookback=len(df))"""
        signals = check_dkx_signal(self.df, lookback=len(self.df))
        self.assertEqual(len(signals), 3) # 第 50, 80, 99 天
        self.assertEqual(signals[0]['signal'], 'BUY')
        self.assertEqual(signals[1]['signal'], 'SELL')
        self.assertEqual(signals[2]['signal'], 'BUY')

    def test_dkx_lookback_greater_than_max(self):
        """测试回溯超过可用历史"""
        signals = check_dkx_signal(self.df, lookback=len(self.df) + 100)
        self.assertEqual(len(signals), 3)

    def test_dkx_lookback_small_miss(self):
        """测试回溯太小而错过最后一个信号的情况"""
        # 如果我们通过更改数据或使用错过的回溯来删除最后一个信号？
        # 但回溯总是锚定到 DataFrame 的末尾。
        # 所以 lookback=1 会捕获最后一个。
        # 要错过它，我们需要信号比回溯更早。
        
        # 让我们验证一个捕获第 99 天但不捕获第 80 天的回溯。
        # 第 99 天是最后一天。第 80 天是 19 天前。
        # 回溯 10 应仅捕获第 99 天。
        signals = check_dkx_signal(self.df, lookback=10)
        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0]['date'], self.df.index[99].strftime("%Y-%m-%d %H:%M:%S"))

    def test_ma_signal_parity(self):
        """验证 MA 信号逻辑工作完全相同"""
        signals = check_ma_signal(self.df, lookback=20)
        self.assertEqual(len(signals), 2)
        self.assertEqual(signals[0]['signal'], 'SELL')
        self.assertEqual(signals[1]['signal'], 'BUY')

if __name__ == '__main__':
    unittest.main()
