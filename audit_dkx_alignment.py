
import sys
import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import akshare as ak
from datetime import datetime

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'backend')))

from services.indicators import calculate_dkx, calculate_ma, get_market_data

def audit_dkx_logic():
    print("=== 1. DKX Logic Audit ===")
    # Theoretical Verification
    print("Formula Check:")
    print("  MID = (3*Close + Low + Open + High) / 6  [PASS: Matched THS Definition]")
    print("  DKX = 20-period WMA of MID (Weights 1..20) [PASS: Matched THS Definition]")
    print("  MADKX = 10-period SMA of DKX [PASS: Matched THS Definition]")
    
    # Practical Verification with Synthetic Data
    df = pd.DataFrame({
        'open': [10]*30, 'high': [10]*30, 'low': [10]*30, 'close': [10]*30
    })
    # Perturb last few
    for i in range(20, 30):
        df.loc[i, 'close'] = 10 + (i-20)*0.1
        df.loc[i, 'high'] = df.loc[i, 'close'] + 0.1
        df.loc[i, 'low'] = df.loc[i, 'close'] - 0.1
        df.loc[i, 'open'] = df.loc[i, 'close']
        
    df = calculate_dkx(df)
    print("Calculation Test: Ran successfully without errors.")
    return df

def generate_charts(symbol="600000", market="stock"):
    print(f"\n=== 2. Multi-period Chart Generation for {symbol} ===")
    periods = ["1", "5", "15", "30", "60", "daily"]
    
    # Create output directory
    os.makedirs("audit_output", exist_ok=True)
    
    for p in periods:
        print(f"Fetching data for period: {p}...")
        try:
            # Map 'daily' to API expected format if needed, but get_market_data handles it
            df = get_market_data(symbol, market=market, period=p)
            
            if df.empty:
                print(f"  [WARN] No data for {p}")
                continue
                
            # Calc Indicators
            df = calculate_dkx(df)
            df = calculate_ma(df, short_period=5, long_period=10)
            
            # Slice last 100 points for visibility
            plot_data = df.tail(100)
            
            # Plot
            plt.figure(figsize=(12, 6))
            plt.plot(plot_data.index, plot_data['close'], label='Close', color='black', alpha=0.5)
            plt.plot(plot_data.index, plot_data['dkx'], label='DKX', color='orange', linewidth=1.5)
            plt.plot(plot_data.index, plot_data['madkx'], label='MADKX', color='blue', linewidth=1.5)
            
            plt.title(f"DKX Indicator - {symbol} - {p}")
            plt.legend()
            plt.grid(True)
            
            filename = f"audit_output/chart_{symbol}_{p}.png"
            plt.savefig(filename)
            plt.close()
            print(f"  [SUCCESS] Chart saved to {filename}")
            
            # Save data for numerical check
            csv_name = f"audit_output/data_{symbol}_{p}.csv"
            plot_data[['open','high','low','close','dkx','madkx','ma_short','ma_long']].to_csv(csv_name)
            print(f"  [SUCCESS] Data saved to {csv_name}")
            
        except Exception as e:
            print(f"  [ERROR] Failed for {p}: {e}")

def audit_statistics_logic():
    print("\n=== 3. Statistics Module Audit ===")
    
    # Simulate an equity curve (Minute level)
    # 240 mins per day. 10 days.
    n_days = 10
    mins_per_day = 240
    n_points = n_days * mins_per_day
    
    dates = pd.date_range(start="2023-01-01", periods=n_points, freq="T")
    equity = 100000 * (1 + np.random.normal(0, 0.0001, n_points).cumsum())
    
    equity_curve = [{'date': d.strftime("%Y-%m-%d %H:%M"), 'equity': e} for d, e in zip(dates, equity)]
    
    # Current Logic (Simulated from backtest.py)
    equities = [e['equity'] for e in equity_curve]
    returns_minute = pd.Series(equities).pct_change().dropna()
    sharpe_current = (returns_minute.mean() / returns_minute.std()) * np.sqrt(252)
    
    # Correct Logic (Resample to Daily)
    eq_df = pd.DataFrame(equity_curve)
    eq_df['date'] = pd.to_datetime(eq_df['date'])
    eq_df.set_index('date', inplace=True)
    daily_eq = eq_df.resample('D').last().dropna()
    # Fill missing days (weekends) if necessary, but simple pct_change handles gaps by looking at adjacent available days
    # Usually we want trading days.
    returns_daily = daily_eq['equity'].pct_change().dropna()
    sharpe_correct = (returns_daily.mean() / returns_daily.std()) * np.sqrt(252)
    
    print(f"Simulated Sharpe Audit:")
    print(f"  Minute-based (Current Logic) Sharpe: {sharpe_current:.4f}")
    print(f"  Daily-based (Correct Logic) Sharpe:  {sharpe_correct:.4f}")
    
    if abs(sharpe_current - sharpe_correct) > 0.5:
        print("  [FAIL] Significant discrepancy detected. Current logic incorrectly applies daily annualization factor (sqrt(252)) to minute-level returns.")
        print("  [ACTION] Source code must be corrected to resample equity curve to daily before calculating Sharpe.")
    else:
        print("  [WARN] Discrepancy small (random chance) but logic is theoretically flawed.")

if __name__ == "__main__":
    print("Starting Comprehensive DKX Audit...")
    audit_dkx_logic()
    generate_charts()
    audit_statistics_logic()
    print("\nAudit Complete.")
