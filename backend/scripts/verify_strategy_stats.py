
import sys
import os
import pandas as pd
import numpy as np
import unittest
from datetime import datetime, timedelta

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

from backend.services.indicators import calculate_dkx, check_dkx_signal, calculate_ma
from backend.services.backtest import run_backtest_dkx
from unittest.mock import patch, MagicMock

class TestStrategyStats(unittest.TestCase):
    
    def setUp(self):
        # Create synthetic data: 100 days
        # Trend: Up then Down
        dates = pd.date_range(start='2024-01-01', periods=100, freq='D')
        self.df = pd.DataFrame(index=dates)
        
        # Price: 
        # Day 0-49: Uptrend (100 -> 150)
        # Day 50-99: Downtrend (150 -> 100)
        prices = np.concatenate([
            np.linspace(100, 150, 50),
            np.linspace(150, 100, 50)
        ])
        
        self.df['open'] = prices
        self.df['close'] = prices
        self.df['high'] = prices + 1
        self.df['low'] = prices - 1
        self.df['volume'] = 10000
        
        # We need to calculate DKX to have signals
        # DKX is WMA(20) of MID. MID ~= Close.
        # Uptrend: DKX should be below Close (lagging).
        # Downtrend: DKX should be above Close.
        
        # To strictly control signals, we will manually set DKX and MADKX
        self.df['dkx'] = prices # Default
        self.df['madkx'] = prices # Default
        
    def test_dkx_signal_logic(self):
        """
        Verify Signal Generation Logic:
        Golden Cross: Prev(DKX < MADKX) & Curr(DKX > MADKX)
        """
        df = self.df.copy()
        
        # Create a Golden Cross at Index 10
        # Index 9: DKX=100, MADKX=101 (Bearish)
        df.iloc[9, df.columns.get_loc('dkx')] = 100.0
        df.iloc[9, df.columns.get_loc('madkx')] = 101.0
        
        # Index 10: DKX=102, MADKX=101 (Bullish) -> Cross!
        df.iloc[10, df.columns.get_loc('dkx')] = 102.0
        df.iloc[10, df.columns.get_loc('madkx')] = 101.0
        
        # Run check_dkx_signal
        # lookback=20 to cover index 10
        signals = check_dkx_signal(df, lookback=100)
        
        # Should find BUY signal at Index 10
        found = False
        for s in signals:
            if s['date'] == df.index[10].strftime("%Y-%m-%d %H:%M:%S") and s['signal'] == 'BUY':
                found = True
                # Check price
                self.assertEqual(s['price'], df.iloc[10]['close'])
                break
        
        self.assertTrue(found, "Golden Cross at index 10 not found")
        print("PASS: DKX Signal Logic (Golden Cross)")

    @patch('backend.services.backtest.get_market_data')
    @patch('backend.services.backtest.calculate_dkx')
    def test_backtest_stats_accuracy(self, mock_calc, mock_get_data):
        """
        Verify Backtest Statistics:
        - P&L Calculation
        - Commission
        - Win Rate
        """
        print("\nVerifying Backtest Statistics...")
        
        # Setup Data for 1 Trade
        # Day 0: Setup
        # Day 1: Golden Cross (Buy Signal) -> Buy at Open of Day 2 (or Close of Day 1? Logic says: Signal at i, Action at i?)
        # Let's check logic in run_backtest_dkx:
        # Loop i:
        #   check signal at i (using i-1 and i)
        #   if signal:
        #      Action!
        #      Buy Price = curr_price (Close of i) + Slippage
        
        df = self.df.copy()[:10] # 10 days
        df['dkx'] = 100.0
        df['madkx'] = 100.0
        
        # Make a Golden Cross at Day 2 (Index 2)
        # Day 1: DKX=100, MADKX=101
        df.iloc[1, df.columns.get_loc('dkx')] = 100.0
        df.iloc[1, df.columns.get_loc('madkx')] = 101.0
        
        # Day 2: DKX=102, MADKX=101 -> BUY Signal
        df.iloc[2, df.columns.get_loc('dkx')] = 102.0
        df.iloc[2, df.columns.get_loc('madkx')] = 101.0
        df.iloc[2, df.columns.get_loc('close')] = 100.0 # Buy Price = 100
        
        # Make a Dead Cross at Day 5 (Index 5) -> SELL (Close Buy)
        # Day 4: DKX=105, MADKX=104
        df.iloc[4, df.columns.get_loc('dkx')] = 105.0
        df.iloc[4, df.columns.get_loc('madkx')] = 104.0
        
        # Day 5: DKX=103, MADKX=104 -> SELL Signal
        df.iloc[5, df.columns.get_loc('dkx')] = 103.0
        df.iloc[5, df.columns.get_loc('madkx')] = 104.0
        df.iloc[5, df.columns.get_loc('close')] = 110.0 # Sell Price = 110
        
        mock_get_data.return_value = df
        mock_calc.return_value = df # Already has dkx
        
        # Run Backtest
        # Commission: 0.0003
        # Slippage: 1 tick? Assume min_tick is handled or 0 for now.
        # In code: slippage_val = min_tick * 1. Default min_tick might be 0.01.
        
        # Mock get_min_tick to be 0 for exact calc
        with patch('backend.services.backtest.get_min_tick', return_value=0.0):
             results = run_backtest_dkx(['TEST'], 'stock', 'daily', '2024-01-01', '2024-01-10', 100000, 10)
        
        # Analyze Results
        # run_backtest_dkx returns {'results': [ {symbol:..., ...}, ... ]}
        res_list = results['results']
        self.assertEqual(len(res_list), 1)
        res = res_list[0]
        self.assertEqual(res['symbol'], 'TEST')
        
        trades = res['trades']
        
        # Expect 3 trades:
        # 1. Open Long (Day 2)
        # 2. Close Long (Day 5) - Triggered by Dead Cross
        # 3. Open Short (Day 5) - Triggered by Dead Cross (Reversal Strategy)
        self.assertEqual(len(trades), 3) 
        
        # Trade 1: Open Long
        t1 = trades[0]
        self.assertEqual(t1['direction'], '开多')
        self.assertEqual(t1['price'], 100.0)
        self.assertEqual(t1['quantity'], 10) # 10 lots = 1000 shares (stock multiplier 100)
        
        # Value = 100 * 1000 = 100,000
        # Comm = 100,000 * 0.0003 = 30.0
        self.assertAlmostEqual(t1['commission'], 30.0)
        self.assertAlmostEqual(t1['profit'], -30.0) # Only comm loss
        
        # Trade 2: Close Long
        t2 = trades[1]
        # Logic: Dead Cross -> Close Long -> Open Short
        self.assertEqual(t2['direction'], '平多')
        self.assertEqual(t2['price'], 110.0)
        
        # P&L Calculation
        # Buy: 100, Sell: 110. Diff: 10.
        # Quantity: 10 lots * 100 = 1000 shares.
        # Gross Profit: 10 * 1000 = 10,000.
        # Comm (Sell): 110 * 1000 * 0.0003 = 33.0.
        # Net Profit: 10,000 - 33.0 = 9967.0.
        
        self.assertAlmostEqual(t2['commission'], 33.0)
        self.assertAlmostEqual(t2['profit'], 9967.0)
        
        # Trade 3: Open Short
        t3 = trades[2]
        self.assertEqual(t3['direction'], '开空')
        self.assertEqual(t3['price'], 110.0)
        
        # Comm (Open Short): 110 * 1000 * 0.0003 = 33.0
        self.assertAlmostEqual(t3['commission'], 33.0)
        self.assertAlmostEqual(t3['profit'], -33.0)
        
        # Total P&L
        # T1: -30
        # T2: +9967
        # T3: -33
        # Realized Total: 9904
        total_pnl = t1['profit'] + t2['profit'] + t3['profit']
        self.assertAlmostEqual(res['statistics']['realized_profit'], 9904.0)
        
        # Floating P&L (Open Short from Day 5 to Day 9)
        # Entry: 110. Close Day 9: 109.18367...
        # Profit = (110 - 109.18367) * 1000 ~= 816.33
        self.assertAlmostEqual(res['statistics']['total_profit'], 10720.33, places=1)
        
        print(f"PASS: Backtest Stats (Realized: {res['statistics']['realized_profit']}, Total: {res['statistics']['total_profit']})")

    def test_dual_ma_consistency(self):
        """
        Verify Dual MA Logic
        """
        print("\nVerifying Dual MA Logic...")
        df = self.df.copy()
        # MA5, MA10
        # Create crossover
        # Day 10: MA5 crosses MA10 up
        
        # We use calculate_ma from indicators
        # Just ensure it calls rolling mean
        df['close'] = np.arange(100) # 0..99
        # MA5 at 10: mean(6..10) = 8
        # MA10 at 10: mean(1..10) = 5.5
        # MA5 > MA10
        
        df = calculate_ma(df, 5, 10)
        
        self.assertTrue('ma_short' in df.columns)
        self.assertTrue('ma_long' in df.columns)
        
        # Check values at index 10
        ma5 = df['ma_short'].iloc[10]
        ma10 = df['ma_long'].iloc[10]
        
        expected_ma5 = np.mean(np.arange(6, 11)) # 6,7,8,9,10 -> 8.0
        expected_ma10 = np.mean(np.arange(1, 11)) # 1..10 -> 5.5
        
        self.assertAlmostEqual(ma5, expected_ma5)
        self.assertAlmostEqual(ma10, expected_ma10)
        print("PASS: Dual MA Calculation")

if __name__ == "__main__":
    unittest.main()
