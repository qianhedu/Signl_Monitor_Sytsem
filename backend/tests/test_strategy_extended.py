
import unittest
import pandas as pd
import numpy as np
import sys
import os

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.indicators import check_dkx_signal, check_ma_signal

class TestStrategyExtended(unittest.TestCase):
    def setUp(self):
        # Create 100 days of data
        dates = pd.date_range(start="2023-01-01", periods=100, freq="D")
        self.df = pd.DataFrame(index=dates)
        self.df['close'] = 100.0
        
        # DKX/MADKX
        self.df['dkx'] = 100.0
        self.df['madkx'] = 100.0
        
        # Signal 1: Day 50 (Index 50) - BUY
        # Index 49: DKX(99) < MADKX(100)
        # Index 50: DKX(101) > MADKX(100)
        dkx_idx = self.df.columns.get_loc('dkx')
        
        # 0-49: Bearish
        self.df.iloc[:50, dkx_idx] = 99.0
        
        # 50-79: Bullish
        self.df.iloc[50:80, dkx_idx] = 101.0
        
        # Signal 2: Day 80 (Index 80) - SELL
        # Index 79: Bullish
        # Index 80: Bearish
        self.df.iloc[80:, dkx_idx] = 99.0
        
        # MA Setup (Same pattern)
        self.df['ma_short'] = self.df['dkx']
        self.df['ma_long'] = self.df['madkx']

    def test_lookback_positive_hit(self):
        """Test Lookback > 0 detecting signals correctly"""
        # Day 80 is SELL. Last index is 99.
        # 99 - 80 = 19 days ago.
        # Lookback=20 should find it.
        signals = check_dkx_signal(self.df, lookback=20)
        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0]['signal'], 'SELL')
        self.assertEqual(signals[0]['date'], self.df.index[80].strftime("%Y-%m-%d %H:%M:%S"))

    def test_lookback_positive_miss(self):
        """Test Lookback > 0 correctly NOT finding old signals"""
        # Lookback=10 (scans index 89 to 99). Signal at 80 should be missed.
        signals = check_dkx_signal(self.df, lookback=10)
        self.assertEqual(len(signals), 0)

    def test_lookback_zero(self):
        """Test Lookback = 0 (Full History Scan)"""
        signals = check_dkx_signal(self.df, lookback=0)
        # Should find Day 50 (BUY) and Day 80 (SELL)
        self.assertEqual(len(signals), 2)
        self.assertEqual(signals[0]['signal'], 'BUY')
        self.assertEqual(signals[0]['date'], self.df.index[50].strftime("%Y-%m-%d %H:%M:%S"))
        self.assertEqual(signals[1]['signal'], 'SELL')
        self.assertEqual(signals[1]['date'], self.df.index[80].strftime("%Y-%m-%d %H:%M:%S"))

    def test_lookback_negative(self):
        """Test Lookback < 0 (Should be treated as Abs)"""
        # Lookback = -20 should behave like Lookback = 20
        signals = check_dkx_signal(self.df, lookback=-20)
        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0]['signal'], 'SELL')

    def test_ma_signals(self):
        """Verify MA signals work identically"""
        signals = check_ma_signal(self.df, lookback=20)
        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0]['signal'], 'SELL')
        
    def test_return_structure(self):
        """Verify return structure contains required fields"""
        signals = check_dkx_signal(self.df, lookback=20)
        sig = signals[0]
        self.assertIn('signal', sig)
        self.assertIn('date', sig)
        self.assertIn('price', sig)
        self.assertIn('dkx', sig)
        self.assertIn('madkx', sig)
        # Type is added in main.py, not here.

if __name__ == '__main__':
    unittest.main()
