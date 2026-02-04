from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from typing import List
import pandas as pd

# Import local modules
# Assuming running from 'backend' or root. If from root, need 'backend.models'. 
# But standard is running inside backend or setting PYTHONPATH.
# I will use relative imports or assume running 'python main.py' inside backend folder.
from contextlib import asynccontextmanager

try:
    from models import DetectionRequest, MaDetectionRequest, DetectionResponse, SignalResult
    from services.indicators import get_market_data, calculate_dkx, check_dkx_signal, calculate_ma, check_ma_signal
    from services.db import init_db, save_signal, get_history
    from services.metadata import search_symbols, get_symbol_name
    from routers import backtest, symbols
except ImportError:
    # Try absolute import if running from root
    from backend.models import DetectionRequest, MaDetectionRequest, DetectionResponse, SignalResult
    from backend.services.indicators import get_market_data, calculate_dkx, check_dkx_signal, calculate_ma, check_ma_signal
    from backend.services.db import init_db, save_signal, get_history
    from backend.services.metadata import search_symbols, get_symbol_name
    from backend.routers import backtest, symbols

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(title="Signal Monitor System API", lifespan=lifespan)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(backtest.router, prefix="/api/backtest", tags=["backtest"])
app.include_router(symbols.router, prefix="/api/symbols", tags=["symbols"])

@app.get("/")
def read_root():
    return {"message": "Signal Monitor System API is running"}

def format_date(dt):
    if isinstance(dt, pd.Timestamp) and dt.tzinfo is not None:
        dt = dt.tz_convert('Asia/Shanghai')
    return dt.strftime("%Y-%m-%d %H:%M:%S")

@app.post("/api/detect/dkx", response_model=DetectionResponse)
async def detect_dkx(request: DetectionRequest):
    results = []
    
    for symbol in request.symbols:
        # Fetch data
        # Note: akshare symbols usually need checking (e.g., '000001' for sh/sz needs adjustment or correct code)
        # We assume user provides correct code or we handle it. 
        # stock_zh_a_hist takes 6 digit code.
        
        try:
            df = get_market_data(symbol, request.market, request.period)
            if df.empty:
                continue
                
            df = calculate_dkx(df)
            signals = check_dkx_signal(df, request.lookback, request.start_time, request.end_time)
            
            if request.lookback == 0:
                if signals:
                    signals = [signals[-1]]
                else:
                    last_row = df.iloc[-1]
                    current_signal = "BUY" if last_row['dkx'] > last_row['madkx'] else "SELL"
                    signals = [{
                        "signal": current_signal,
                        "date": format_date(last_row.name),
                        "price": last_row['close'],
                        "dkx": last_row['dkx'],
                        "madkx": last_row['madkx'],
                        "is_state": True,
                        "offset": 0
                    }]
            elif signals:
                # Ensure only the latest signal is returned per symbol
                latest_signal = signals[-1]
                
                # Strict Window Validation
                # Although check_dkx_signal uses lookback, we explicitly verify offset
                # User Requirement: 
                # - If signal offset > lookback, exclude it.
                # - Signal at boundary (offset < lookback) is included.
                # Note: offset is 0-based index from end. offset 19 means 20th candle.
                # If lookback=20, we accept offsets 0..19.
                if latest_signal.get('offset') is not None and latest_signal['offset'] >= request.lookback:
                     continue
                     
                signals = [latest_signal]
            
            symbol_name = get_symbol_name(symbol, request.market)

            for signal_info in signals:
                # Prepare result
                # We need to send the chart data centered around the signal or relevant range
                # and also include all signals within that range for chart markers.
                
                # Find index of signal in original df
                try:
                    sig_date = pd.to_datetime(signal_info['date'])
                    # If signal_info['date'] came from format_date, it is string. pd.to_datetime makes it naive (if string is naive).
                    # check_dkx_signal uses strftime so it is string.
                    # We need to find it in df.index.
                    # If df.index is naive, perfect.
                    # If df.index is aware, we might need to match.
                    
                    if df.index.tz is not None and sig_date.tzinfo is None:
                        sig_date = sig_date.tz_localize(df.index.tz)

                    loc = df.index.get_loc(sig_date)
                    if isinstance(loc, slice): loc = loc.start
                    
                    # Define chart window: Increased range (User request)
                    # 2000 bars before, 200 bars after to ensure plenty of history
                    start_pos = max(0, loc - 2000)
                    end_pos = min(len(df), loc + 200)
                    
                    # Ensure minimum length
                    if end_pos - start_pos < 1000:
                        start_pos = max(0, end_pos - 1000)
                    
                    chart_df = df.iloc[start_pos:end_pos]
                    chart_data = chart_df.reset_index().to_dict(orient='records')
                    # Convert timestamp to string
                    for item in chart_data:
                        item['date'] = format_date(item['date'])
                        
                    # Find all signals within this chart window for markers
                    c_start = format_date(chart_df.index[0])
                    c_end = format_date(chart_df.index[-1])
                    # Use lookback=0 to find all signals in range
                    chart_signals = check_dkx_signal(df, lookback=0, start_time=c_start, end_time=c_end)
                    
                    # If the main signal is a 'State' signal (no crossover), add it to chart signals so it's marked
                    if signal_info.get('is_state'):
                         chart_signals.append(signal_info)
                    
                except Exception as ex:
                    print(f"Error preparing chart data: {ex}")
                    # Fallback
                    chart_data = df.tail(300).reset_index().to_dict(orient='records')
                    for item in chart_data:
                        item['date'] = format_date(item['date'])
                    chart_signals = []
                
                result = SignalResult(
                    symbol=symbol,
                    symbol_name=symbol_name,
                    date=format_date(pd.to_datetime(signal_info['date'])), # Ensure format
                    signal=signal_info['signal'],
                    close=signal_info['price'],
                    dkx=signal_info['dkx'],
                    madkx=signal_info['madkx'],
                    indicator="DKX",
                    offset=signal_info.get('offset'),
                    details={
                        "chart_data": chart_data,
                        "chart_signals": chart_signals
                    }
                )
                
                # Save to DB
                save_data = result.dict()
                save_data['market'] = request.market
                save_data['indicator_type'] = 'DKX'
                save_signal(save_data)
                
                results.append(result)
                
        except Exception as e:
            print(f"Error processing {symbol}: {e}")
            continue
            
    return DetectionResponse(results=results)

@app.post("/api/detect/ma", response_model=DetectionResponse)
async def detect_ma(request: MaDetectionRequest):
    results = []
    
    for symbol in request.symbols:
        try:
            df = get_market_data(symbol, request.market, request.period)
            if df.empty:
                continue
                
            df = calculate_ma(df, request.short_period, request.long_period)
            signals = check_ma_signal(df, request.lookback, request.start_time, request.end_time)
            
            if request.lookback == 0:
                if signals:
                    signals = [signals[-1]]
                else:
                    last_row = df.iloc[-1]
                    current_signal = "BUY" if last_row['ma_short'] > last_row['ma_long'] else "SELL"
                    signals = [{
                        "signal": current_signal,
                        "date": format_date(last_row.name),
                        "price": last_row['close'],
                        "ma_short": last_row['ma_short'],
                        "ma_long": last_row['ma_long'],
                        "is_state": True,
                        "offset": 0
                    }]
            elif signals:
                # Ensure only the latest signal is returned per symbol
                latest_signal = signals[-1]
                
                # Strict Window Validation
                if latest_signal.get('offset') is not None and latest_signal['offset'] >= request.lookback:
                     continue
                
                signals = [latest_signal]
            
            symbol_name = get_symbol_name(symbol, request.market)

            for signal_info in signals:
                try:
                    sig_date = pd.to_datetime(signal_info['date'])
                    
                    if df.index.tz is not None and sig_date.tzinfo is None:
                        sig_date = sig_date.tz_localize(df.index.tz)

                    loc = df.index.get_loc(sig_date)
                    if isinstance(loc, slice): loc = loc.start
                    
                    # Increased range
                    start_pos = max(0, loc - 800)
                    end_pos = min(len(df), loc + 100)
                    
                    if end_pos - start_pos < 300:
                        start_pos = max(0, end_pos - 400)
                    
                    chart_df = df.iloc[start_pos:end_pos]
                    chart_data = chart_df.reset_index().to_dict(orient='records')
                    for item in chart_data:
                        item['date'] = format_date(item['date'])
                        
                    c_start = format_date(chart_df.index[0])
                    c_end = format_date(chart_df.index[-1])
                    chart_signals = check_ma_signal(df, lookback=0, start_time=c_start, end_time=c_end)
                    
                    if signal_info.get('is_state'):
                         chart_signals.append(signal_info)
                    
                except Exception as ex:
                    print(f"Error preparing MA chart data: {ex}")
                    chart_data = df.tail(300).reset_index().to_dict(orient='records')
                    for item in chart_data:
                        item['date'] = format_date(item['date'])
                    chart_signals = []
                
                result = SignalResult(
                    symbol=symbol,
                    symbol_name=symbol_name,
                    date=format_date(pd.to_datetime(signal_info['date'])),
                    signal=signal_info['signal'],
                    close=signal_info['price'],
                    ma_short=signal_info['ma_short'],
                    ma_long=signal_info['ma_long'],
                    indicator="MA",
                    offset=signal_info.get('offset'),
                    details={
                        "chart_data": chart_data,
                        "chart_signals": chart_signals
                    }
                )
                
                # Save to DB
                save_data = result.dict()
                save_data['market'] = request.market
                save_data['indicator_type'] = 'MA'
                save_signal(save_data)
                
                results.append(result)
                
        except Exception as e:
            print(f"Error processing MA for {symbol}: {e}")
            continue
            
    return DetectionResponse(results=results)

@app.get("/api/history")
def get_signal_history(limit: int = 100):
    return get_history(limit)

@app.get("/api/symbols/search")
def search_market_symbols(q: str = "", market: str = "stock"):
    return search_symbols(q, market)

@app.get("/api/symbols/hot")
def get_hot_symbols_endpoint():
    return get_default_hot_symbols()

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
