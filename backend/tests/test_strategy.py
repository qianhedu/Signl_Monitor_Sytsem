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
        # Create a sample DataFrame with 100 days of data
        dates = pd.date_range(start="2023-01-01", periods=100, freq="D")
        self.df = pd.DataFrame(index=dates)
        self.df['close'] = 100.0
        
        # Setup DKX/MADKX columns
        # Scenario: 
        # Day 50: Gold Cross (DKX crosses above MADKX)
        # Day 80: Dead Cross (DKX crosses below MADKX)
        # Day 99 (Last day): Gold Cross
        
        self.df['dkx'] = 100.0
        self.df['madkx'] = 100.0
        
        # Initialize with no cross state (DKX < MADKX)
        self.df['dkx'] = 99.0
        self.df['madkx'] = 100.0
        
        # Day 50: Cross (DKX > MADKX) - BUY Signal
        # Use iloc for position-based assignment
        dkx_col = self.df.columns.get_loc('dkx')
        madkx_col = self.df.columns.get_loc('madkx')
        
        # 0-49: DKX=99, MADKX=100 (Default)
        
        # Day 50 (index 50): Cross
        self.df.iloc[50, dkx_col] = 101.0
        
        # 51-78: UP state
        self.df.iloc[51:79, dkx_col] = 101.0
        
        # Day 79: Pre-cross (still UP)
        self.df.iloc[79, dkx_col] = 101.0
        
        # Day 80: Cross (DKX < MADKX) - SELL Signal
        self.df.iloc[80, dkx_col] = 99.0
        
        # 81-97: DOWN state (Default 99)
        
        # Day 98: Pre-cross (still DOWN)
        self.df.iloc[98, dkx_col] = 99.0

        # Day 99: Cross (DKX > MADKX) - BUY Signal
        self.df.iloc[99, dkx_col] = 101.0
        
        # Setup MA columns for check_ma_signal (Same logic)
        self.df['ma_short'] = self.df['dkx']
        self.df['ma_long'] = self.df['madkx']

    def test_dkx_lookback_1(self):
        """Test looking back 1 period (only the last candle transition)"""
        # Lookback 1 should check the transition from index 98 to 99
        signals = check_dkx_signal(self.df, lookback=1)
        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0]['signal'], 'BUY')
        self.assertEqual(signals[0]['date'], self.df.index[99].strftime("%Y-%m-%d %H:%M:%S"))

    def test_dkx_lookback_20(self):
        """Test looking back 20 periods (should include day 80 and 99)"""
        # Day 99 is index 99. Day 80 is index 80.
        # Lookback 20 from 99 goes back to index 79.
        # Subset will be index 79 to 99.
        # Index 80 is a Dead Cross. Index 99 is a Golden Cross.
        signals = check_dkx_signal(self.df, lookback=20)
        self.assertEqual(len(signals), 2)
        self.assertEqual(signals[0]['signal'], 'SELL') # Day 80
        self.assertEqual(signals[1]['signal'], 'BUY')  # Day 99

    def test_dkx_lookback_max(self):
        """Test looking back entire history (lookback=len(df))"""
        signals = check_dkx_signal(self.df, lookback=len(self.df))
        self.assertEqual(len(signals), 3) # Day 50, 80, 99
        self.assertEqual(signals[0]['signal'], 'BUY')
        self.assertEqual(signals[1]['signal'], 'SELL')
        self.assertEqual(signals[2]['signal'], 'BUY')

    def test_dkx_lookback_greater_than_max(self):
        """Test looking back more than available history"""
        signals = check_dkx_signal(self.df, lookback=len(self.df) + 100)
        self.assertEqual(len(signals), 3)

    def test_dkx_lookback_small_miss(self):
        """Test lookback that is too small to catch the last signal"""
        # If we remove the last signal by changing data or using lookback that misses it?
        # But lookback always anchors to the END of the dataframe.
        # So lookback=1 catches the last one.
        # To miss it, we need the signal to be older than lookback.
        
        # Let's verify a lookback that catches Day 99 but NOT Day 80.
        # Day 99 is last. Day 80 is 19 days ago.
        # Lookback 10 should catch Day 99 only.
        signals = check_dkx_signal(self.df, lookback=10)
        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0]['date'], self.df.index[99].strftime("%Y-%m-%d %H:%M:%S"))

    def test_ma_signal_parity(self):
        """Verify MA signal logic works identically"""
        signals = check_ma_signal(self.df, lookback=20)
        self.assertEqual(len(signals), 2)
        self.assertEqual(signals[0]['signal'], 'SELL')
        self.assertEqual(signals[1]['signal'], 'BUY')

if __name__ == '__main__':
    unittest.main()
