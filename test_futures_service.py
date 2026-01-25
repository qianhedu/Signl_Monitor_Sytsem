from backend.services.indicators import get_market_data, calculate_ma, check_ma_signal

try:
    print("Testing get_market_data for futures...")
    df = get_market_data("RB0", market="futures")
    print("Data fetched. Rows:", len(df))
    print(df.tail())
    
    print("Calculating MA...")
    df = calculate_ma(df)
    print("MA Calculated.")
    
    print("Checking Signal...")
    signal = check_ma_signal(df, lookback=10)
    print("Signal:", signal)
    
except Exception as e:
    print("Error:", e)
