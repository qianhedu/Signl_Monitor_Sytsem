
import unittest
from unittest.mock import patch, MagicMock
import pandas as pd
import numpy as np
import sys
import os
from fastapi.testclient import TestClient

# Add backend path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app

class TestUniqueSignalAPI(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        
        # Create a synthetic DataFrame with 100 candles
        dates = pd.date_range(start='2024-01-01', periods=100, freq='D')
        self.df = pd.DataFrame({
            'open': 100.0,
            'high': 105.0,
            'low': 95.0,
            'close': 100.0,
            'volume': 1000
        }, index=dates)
        self.df.index.name = 'date'
        
        # --- DKX Setup ---
        self.df['dkx'] = 100.0
        self.df['madkx'] = 100.0
        
        # Signal 1: Golden Cross at index 79 (Offset 20)
        # Prev: 78
        self.df.iloc[78, self.df.columns.get_loc('dkx')] = 100.0
        self.df.iloc[78, self.df.columns.get_loc('madkx')] = 101.0
        # Curr: 79
        self.df.iloc[79, self.df.columns.get_loc('dkx')] = 102.0
        self.df.iloc[79, self.df.columns.get_loc('madkx')] = 101.0
        
        # Signal 2: Dead Cross at index 80 (Offset 19)
        # Prev: 79 (was Golden Cross state)
        # Curr: 80
        self.df.iloc[80, self.df.columns.get_loc('dkx')] = 100.0
        self.df.iloc[80, self.df.columns.get_loc('madkx')] = 101.0
        
        # Signal 3: Golden Cross at index 99 (Offset 0 - Latest)
        self.df.iloc[98, self.df.columns.get_loc('dkx')] = 100.0
        self.df.iloc[98, self.df.columns.get_loc('madkx')] = 101.0
        self.df.iloc[99, self.df.columns.get_loc('dkx')] = 102.0
        self.df.iloc[99, self.df.columns.get_loc('madkx')] = 101.0

        # --- MA Setup ---
        self.df['ma_short'] = 100.0
        self.df['ma_long'] = 100.0
        
        # MA Signal at index 80 (Offset 19)
        self.df.iloc[79, self.df.columns.get_loc('ma_short')] = 100.0
        self.df.iloc[79, self.df.columns.get_loc('ma_long')] = 101.0
        self.df.iloc[80, self.df.columns.get_loc('ma_short')] = 102.0
        self.df.iloc[80, self.df.columns.get_loc('ma_long')] = 101.0

    @patch('main.get_market_data')
    @patch('main.calculate_dkx')
    def test_window_boundary_inclusion(self, mock_calc_dkx, mock_get_data):
        """
        Test: Lookback 20.
        Signal at index 80 has offset 19. Should be INCLUDED.
        Signal at index 79 has offset 20. Should be EXCLUDED (if strictly < 20) or INCLUDED (if <= 20)?
        User said: "Signal at window boundary (20th) -> should be included".
        20th candle corresponds to offset 19 (0..19 is 20 candles).
        So Lookback 20 should include offset 19.
        Offset 20 is the 21st candle. Should be EXCLUDED.
        
        To test this, we manipulate the DataFrame so the LATEST signal is at specific offsets.
        """
        mock_calc_dkx.side_effect = lambda x: x
        
        # Scenario 1: Latest signal at offset 19 (Index 80)
        # We simulate this by slicing the dataframe to end at index 80?
        # No, the code uses the full dataframe.
        # But my df has a signal at 99 (offset 0).
        # So I need to make sure the signal at 99 DOES NOT EXIST for this test case.
        
        df_scenario_1 = self.df.copy()
        # Remove signal at 99
        df_scenario_1.iloc[98, df_scenario_1.columns.get_loc('dkx')] = 100.0
        df_scenario_1.iloc[98, df_scenario_1.columns.get_loc('madkx')] = 100.0
        df_scenario_1.iloc[99, df_scenario_1.columns.get_loc('dkx')] = 100.0
        df_scenario_1.iloc[99, df_scenario_1.columns.get_loc('madkx')] = 100.0
        
        mock_get_data.return_value = df_scenario_1
        
        # Lookback 20.
        # Latest signal is at index 80. Offset = 100 - 1 - 80 = 19.
        # 19 < 20. Should be found.
        
        payload = {
            "symbols": ["000001"],
            "lookback": 20,
            "market": "stock",
            "period": "daily"
        }
        
        response = self.client.post("/api/detect/dkx", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data['results']), 1)
        self.assertEqual(data['results'][0]['offset'], 19)
        
    @patch('main.get_market_data')
    @patch('main.calculate_dkx')
    def test_window_boundary_exclusion(self, mock_calc_dkx, mock_get_data):
        """
        Test: Lookback 19.
        Latest signal is at index 80 (Offset 19).
        Lookback 19.
        User requirement: "Signal at boundary (20th) -> included".
        If lookback=19, we check 19 candles (Offsets 0..18).
        Offset 19 is the 20th candle. So it is OUTSIDE lookback 19.
        So it should be EXCLUDED.
        """
        mock_calc_dkx.side_effect = lambda x: x
        
        df_scenario_2 = self.df.copy()
        # Remove signal at 99
        df_scenario_2.iloc[98, df_scenario_2.columns.get_loc('dkx')] = 100.0
        df_scenario_2.iloc[98, df_scenario_2.columns.get_loc('madkx')] = 100.0
        df_scenario_2.iloc[99, df_scenario_2.columns.get_loc('dkx')] = 100.0
        df_scenario_2.iloc[99, df_scenario_2.columns.get_loc('madkx')] = 100.0
        
        mock_get_data.return_value = df_scenario_2
        
        payload = {
            "symbols": ["000001"],
            "lookback": 19,
            "market": "stock",
            "period": "daily"
        }
        
        response = self.client.post("/api/detect/dkx", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        # Should be empty because offset 19 >= lookback 19
        self.assertEqual(len(data['results']), 0)

    @patch('main.get_market_data')
    @patch('main.calculate_dkx')
    def test_offset_field_returned(self, mock_calc_dkx, mock_get_data):
        mock_get_data.return_value = self.df.copy()
        mock_calc_dkx.side_effect = lambda x: x
        
        # Lookback 100. Latest signal at 99 (Offset 0).
        payload = {
            "symbols": ["000001"],
            "lookback": 100,
            "market": "stock",
            "period": "daily"
        }
        
        response = self.client.post("/api/detect/dkx", json=payload)
        data = response.json()
        self.assertEqual(len(data['results']), 1)
        self.assertEqual(data['results'][0]['offset'], 0)

    @patch('main.get_market_data')
    @patch('main.calculate_ma')
    def test_ma_window_validation(self, mock_calc_ma, mock_get_data):
        mock_get_data.return_value = self.df.copy()
        mock_calc_ma.side_effect = lambda x, s, l: x
        
        # MA Signal at index 80 (Offset 19).
        # Lookback 20 -> OK.
        # Lookback 19 -> Empty.
        
        payload_ok = {
            "symbols": ["000001"],
            "lookback": 20,
            "market": "stock",
            "period": "daily",
            "short_period": 5,
            "long_period": 10
        }
        response = self.client.post("/api/detect/ma", json=payload_ok)
        self.assertEqual(len(response.json()['results']), 1)
        self.assertEqual(response.json()['results'][0]['offset'], 19)
        
        payload_fail = {
            "symbols": ["000001"],
            "lookback": 19,
            "market": "stock",
            "period": "daily",
            "short_period": 5,
            "long_period": 10
        }
        response = self.client.post("/api/detect/ma", json=payload_fail)
        self.assertEqual(len(response.json()['results']), 0)

if __name__ == '__main__':
    unittest.main()
