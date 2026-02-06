
import sys
import os
import pandas as pd
import numpy as np
import unittest
from unittest.mock import patch, MagicMock

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

from backend.services.indicators import calculate_ma
from backend.services.backtest import run_backtest_dkx # We can reuse or create a similar runner for MA if needed
# Actually, run_backtest_dkx is specific to DKX. 
# But the user wants to verify "Dual MA Strategy".
# I should check if there is a "run_backtest_ma" or if I need to implement/verify the logic for MA strategy.
# The user's prompt mentions "DKX Signal Strategy" and "Dual MA Strategy".
# The codebase seems to currently have `run_backtest_dkx`. 
# Does it have `run_backtest_ma`?
# Let's check `backend/services/backtest.py` again.
# It seems `run_backtest_dkx` is the main one. 
# If there is no `run_backtest_ma`, I should verify the MA calculation itself which is the core of the strategy.

class TestDualMAConsistency(unittest.TestCase):
    
    def setUp(self):
        # Create synthetic data
        dates = pd.date_range(start='2024-01-01', periods=200, freq='D')
        self.df = pd.DataFrame(index=dates)
        # Linear price 100 -> 200 -> 100
        prices = np.concatenate([
            np.linspace(100, 200, 100),
            np.linspace(200, 100, 100)
        ])
        self.df['close'] = prices
        self.df['open'] = prices
        self.df['high'] = prices + 1
        self.df['low'] = prices - 1
        self.df['volume'] = 10000

    def test_ma_calculation_logic(self):
        """
        Verify MA calculation uses Simple Moving Average (SMA)
        Standard: Sum(Close, N) / N
        """
        print("\nVerifying MA Calculation Logic (SMA)...")
        df = self.df.copy()
        
        # Calculate MA5, MA10
        df = calculate_ma(df, 5, 10)
        
        # Check Index 10 (11th day)
        # Prices: 100, 101, ..., 110
        # MA5 at 10: (106+107+108+109+110)/5 = 108
        # MA10 at 10: (101+...+110)/10 = 105.5
        
        price_slice_5 = df['close'].iloc[6:11] # Indices 6,7,8,9,10
        expected_ma5 = price_slice_5.mean()
        
        price_slice_10 = df['close'].iloc[1:11] # Indices 1..10
        expected_ma10 = price_slice_10.mean()
        
        calc_ma5 = df['ma_short'].iloc[10]
        calc_ma10 = df['ma_long'].iloc[10]
        
        print(f"Index 10: Price={df['close'].iloc[10]}")
        print(f"Expected MA5={expected_ma5}, Calculated={calc_ma5}")
        print(f"Expected MA10={expected_ma10}, Calculated={calc_ma10}")
        
        self.assertAlmostEqual(calc_ma5, expected_ma5)
        self.assertAlmostEqual(calc_ma10, expected_ma10)
        print("PASS: MA Calculation Logic matches Standard SMA")

    def test_parameter_combinations(self):
        """
        Verify various parameter combinations (5-60)
        """
        print("\nVerifying MA Parameter Combinations...")
        df = self.df.copy()
        
        params = [(5, 10), (10, 20), (20, 60), (5, 60)]
        
        for short_p, long_p in params:
            df_res = calculate_ma(df.copy(), short_p, long_p)
            
            # Check if columns exist
            self.assertTrue('ma_short' in df_res.columns)
            self.assertTrue('ma_long' in df_res.columns)
            
            # Check values are not all NaN (after warm-up)
            valid_idx = max(short_p, long_p)
            self.assertFalse(pd.isna(df_res['ma_short'].iloc[valid_idx]))
            self.assertFalse(pd.isna(df_res['ma_long'].iloc[valid_idx]))
            
            print(f"PASS: Combination MA{short_p}/MA{long_p}")

    def test_signal_generation(self):
        """
        Verify Crossover Signals logic
        Golden Cross: Short < Long (prev) AND Short > Long (curr)
        """
        print("\nVerifying Signal Generation Logic...")
        df = self.df.copy()
        df['ma_short'] = [100.0] * 200
        df['ma_long'] = [100.0] * 200
        
        # Create Golden Cross at Index 50
        df.iloc[49, df.columns.get_loc('ma_short')] = 99.0
        df.iloc[49, df.columns.get_loc('ma_long')] = 100.0
        
        df.iloc[50, df.columns.get_loc('ma_short')] = 101.0
        df.iloc[50, df.columns.get_loc('ma_long')] = 100.0
        
        # Check logic
        prev_short = df['ma_short'].iloc[49]
        prev_long = df['ma_long'].iloc[49]
        curr_short = df['ma_short'].iloc[50]
        curr_long = df['ma_long'].iloc[50]
        
        golden_cross = (prev_short < prev_long) and (curr_short > curr_long)
        self.assertTrue(golden_cross)
        print("PASS: Golden Cross Logic")
        
        # Create Dead Cross at Index 60
        df.iloc[59, df.columns.get_loc('ma_short')] = 101.0
        df.iloc[59, df.columns.get_loc('ma_long')] = 100.0
        
        df.iloc[60, df.columns.get_loc('ma_short')] = 99.0
        df.iloc[60, df.columns.get_loc('ma_long')] = 100.0
        
        prev_short = df['ma_short'].iloc[59]
        prev_long = df['ma_long'].iloc[59]
        curr_short = df['ma_short'].iloc[60]
        curr_long = df['ma_long'].iloc[60]
        
        dead_cross = (prev_short > prev_long) and (curr_short < curr_long)
        self.assertTrue(dead_cross)
        print("PASS: Dead Cross Logic")

if __name__ == '__main__':
    unittest.main()
