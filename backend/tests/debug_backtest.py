
import sys
import os
import pandas as pd
from datetime import datetime

# Add backend directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.backtest import run_backtest_dkx

def test_backtest():
    print("Testing backtest with 600519...", flush=True)
    try:
        # Use a recent range with UTC format to reproduce the error
        results = run_backtest_dkx(
            symbols=['600519'],
            market='stock',
            period='daily',
            start_time='2023-01-01T00:00:00.000Z',
            end_time='2023-12-31T00:00:00.000Z',
            initial_capital=100000.0,
            lot_size=100
        )
        print(f"Results count: {len(results)}", flush=True)
        if len(results) > 0:
            print("Trades:", len(results[0].get('trades', [])), flush=True)
            # print(results[0])
        else:
            print("No results returned.", flush=True)
            
    except Exception as e:
        print(f"Error running backtest: {e}", flush=True)
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_backtest()
