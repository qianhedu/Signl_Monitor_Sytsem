import akshare as ak
import pandas as pd

try:
    print("Fetching futures rules...")
    # This function usually returns a table of all futures contracts specs
    df = ak.futures_rule_cn() 
    print(df.head())
    print(df.columns)
    
    # Check for specific symbols
    print("\nChecking for specific symbols (SH, RB, JD, AU):")
    for symbol in ['SH', 'RB', 'JD', 'AU']:
        row = df[df['品种代码'] == symbol] if '品种代码' in df.columns else pd.DataFrame()
        if not row.empty:
            print(f"\n{symbol}:")
            print(row.iloc[0])
        else:
            # Try searching in other columns
            print(f"\n{symbol} not found in '品种代码' directly.")
            
except Exception as e:
    print(f"Error: {e}")
