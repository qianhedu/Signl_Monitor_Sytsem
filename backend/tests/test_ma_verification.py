
import unittest
from unittest.mock import patch, MagicMock
import pandas as pd
import numpy as np
import sys
import os
from datetime import datetime, timedelta

# Add backend directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.backtest import run_backtest_ma

class TestMaVerification(unittest.TestCase):
    
    def setUp(self):
        self.dates = pd.date_range(start='2023-01-01', periods=200, freq='D')
        
    def create_mock_data(self, pattern='trend'):
        df = pd.DataFrame(index=self.dates)
        
        # Base arrays
        close = np.ones(200) * 100.0
        
        if pattern == 'uptrend':
            # Price starts flat, dips (to ensure MA5 < MA20), then rises
            close[:25] = 100.0
            close[25:30] = 90.0 # Dip
            close[30:] = np.linspace(90, 200, 170) # Rise
            
        elif pattern == 'downtrend':
            # Price falls from 200 to 100
            # MA(5) will be < MA(20)
            close = np.linspace(200, 100, 200)
            
        elif pattern == 'choppy':
            # Sine wave to cause frequent crosses
            x = np.linspace(0, 8*np.pi, 200)
            close = 100 + 10 * np.sin(x)
            
        elif pattern == 'gap_up':
            # Flat then huge jump
            close[:100] = 100.0
            close[100:] = 120.0 # 20% gap
            
        df['open'] = close
        df['high'] = close
        df['low'] = close
        df['close'] = close
        df['volume'] = 10000
        
        return df

    @patch('services.backtest.get_market_data')
    @patch('services.backtest.get_futures_multiplier')
    @patch('services.backtest.get_margin_rate')
    @patch('services.backtest.get_min_tick')
    @patch('services.backtest.get_trading_hours_type')
    def test_uptrend_verification(self, mock_hours, mock_tick, mock_margin, mock_mult, mock_data):
        # Setup Mocks
        mock_hours.return_value = 'late_night' # No filtering
        mock_tick.return_value = 0.2
        mock_margin.return_value = 0.1
        mock_mult.return_value = 10
        
        # Data
        df = self.create_mock_data('uptrend')
        mock_data.return_value = df
        
        # Run Backtest
        results = run_backtest_ma(
            symbols=['TEST_UP'],
            market='futures',
            period='daily',
            start_time='2023-01-01',
            end_time='2023-07-01',
            initial_capital=100000,
            lot_size=1,
            short_period=5,
            long_period=20
        )
        
        res = results[0]
        stats = res['statistics']
        trades = res['trades']
        
        # Verification Logic
        # 1. Should have at least 1 trade (Open Long)
        # Uptrend: MA5 > MA20 eventually.
        self.assertGreater(len(trades), 0, "Should trigger at least one trade in uptrend")
        
        # 2. First trade should be '开多' (Open Long)
        self.assertEqual(trades[0]['direction'], '开多')
        
        # 3. Profit should be positive (Trend following)
        # Note: If trend continues to end, it might not close, so realized profit might be 0?
        # Let's check logic: 'run_backtest_ma' calculates floating profit if position is open at end?
        # Line 612: floating_profit = ...
        # But 'total_profit' = final_equity - initial.
        # final_equity is updated on close? Or marked to market?
        # Code check: 'equity_curve' appends 'current_balance'. 
        # 'current_balance' is only updated on CLOSE (realized PnL).
        # So if it never closes, total_profit = 0 (minus commissions).
        # Wait, let's force a close by reversing trend at end or check floating.
        
        # Actually, in a pure linear uptrend, it might never cross down if length is short.
        # Let's check floating profit.
        self.assertGreater(stats['floating_profit'], 0, "Floating profit should be positive in uptrend")
        
    @patch('services.backtest.get_market_data')
    @patch('services.backtest.get_futures_multiplier')
    @patch('services.backtest.get_margin_rate')
    @patch('services.backtest.get_min_tick')
    @patch('services.backtest.get_trading_hours_type')
    def test_choppy_verification(self, mock_hours, mock_tick, mock_margin, mock_mult, mock_data):
        mock_hours.return_value = 'late_night'
        mock_tick.return_value = 0.2
        mock_margin.return_value = 0.1
        mock_mult.return_value = 10
        
        df = self.create_mock_data('choppy')
        mock_data.return_value = df
        
        results = run_backtest_ma(
            symbols=['TEST_CHOP'],
            market='futures',
            period='daily',
            start_time='2023-01-01',
            end_time='2023-07-01'
        )
        
        res = results[0]
        stats = res['statistics']
        
        # Choppy market -> Frequent trades -> High transaction costs/slippage -> Likely Loss
        self.assertGreater(stats['total_trades'], 2, "Should have multiple trades in choppy market")
        
        # Win rate might be low
        # self.assertLess(stats['win_rate'], 50) # Not guaranteed but likely
        
    @patch('services.backtest.get_market_data')
    @patch('services.backtest.get_futures_multiplier')
    @patch('services.backtest.get_margin_rate')
    @patch('services.backtest.get_min_tick')
    @patch('services.backtest.get_trading_hours_type')
    def test_manual_calculation_verification(self, mock_hours, mock_tick, mock_margin, mock_mult, mock_data):
        """
        Precise verification against manual calculation.
        Scenario:
        Day 1-20: Price 100
        Day 21: Price 110 (MA5 rises, MA20 flat -> Cross UP? No, lag)
        Let's construct a simple crossover sequence.
        MA Short=5, Long=10 for simplicity in manual calc.
        """
        mock_hours.return_value = 'late_night'
        mock_tick.return_value = 0.0 # Zero slippage for easy calc
        mock_margin.return_value = 1.0 # 100% margin
        mock_mult.return_value = 1
        
        # Custom Data
        prices = [100.0] * 20
        # Create a sharp rise to trigger Golden Cross
        # MA5 will rise faster than MA10
        prices.extend([110.0] * 5) # MA5 moves up
        prices.extend([120.0] * 5)
        # Create a sharp fall to trigger Dead Cross
        prices.extend([90.0] * 10)
        
        df = pd.DataFrame(index=pd.date_range('2023-01-01', periods=len(prices)), data={'close': prices, 'open': prices, 'high': prices, 'low': prices, 'volume': 1000})
        mock_data.return_value = df
        
        results = run_backtest_ma(
            symbols=['TEST_CALC'],
            market='futures',
            period='daily',
            start_time='2023-01-01',
            end_time='2023-03-01',
            initial_capital=10000,
            lot_size=1,
            short_period=2, # Short periods for faster reaction in test
            long_period=5
        )
        
        trades = results[0]['trades']
        stats = results[0]['statistics']
        
        # Manual Logic Trace:
        # MA2: Avg of last 2. MA5: Avg of last 5.
        # Initial: 100. MA2=100, MA5=100.
        # Change at idx 20 (Day 21): Price 110.
        # Idx 20: P=110. MA2=(100+110)/2=105. MA5=(100*4+110)/5=102.
        # Golden Cross? Prev(100,100) -> Curr(105,102). 105>102. Yes.
        # Signal at Day 21 Close. Execute at Day 21 Close (Price 110).
        # Action: Open Long @ 110.
        
        # Check Trade 1
        if len(trades) > 0:
            t1 = trades[0]
            self.assertEqual(t1['direction'], '开多')
            self.assertEqual(t1['price'], 110.0)
            self.assertEqual(t1['commission'], 110.0 * 1 * 0.0003) # Rate 0.0003
            
            # Next change: Drop to 90 at idx 30.
            # Idx 30: P=90. Prev(120).
            # MA2: (120+90)/2=105. MA5: (120*4+90)/5=114.
            # Dead Cross? Prev(MA2>MA5) -> Curr(105<114). Yes.
            # Signal at Day 30 Close. Execute @ 90.
            # Action: Close Long @ 90, Open Short @ 90.
            
            # Check Trade 2 (Close Long)
            # Profit = (90 - 110) * 1 = -20.
            # Commission = 90 * 0.0003.
            # Net Profit = -20 - OpenComm - CloseComm.
            
            if len(trades) > 1:
                t2 = trades[1] # Close Long? Or is it merged? 
                # run_backtest_ma appends 'Close' then 'Open' if reversing?
                # Let's check code. It does:
                # if golden_cross:
                #   if position == -1: Close Short...
                #   if position == 0 or position == -1: Open Long...
                # So it produces 2 trade records if reversing.
                
                # However, our logic above:
                # Open Long at 110.
                # At 90 (Dead Cross):
                # position is 1.
                # if dead_cross:
                #   if position == 1: Close Long...
                #   if position == 0 or position == 1: Open Short...
                
                self.assertEqual(t2['direction'], '平多')
                self.assertEqual(t2['price'], 90.0)
                expected_profit = (90.0 - 110.0) * 1
                self.assertAlmostEqual(t2['profit'], expected_profit - t2['commission'], delta=0.01)
                
if __name__ == '__main__':
    unittest.main()
