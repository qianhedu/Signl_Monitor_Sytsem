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
    from services.metadata import search_symbols
    from routers import backtest, symbols
except ImportError:
    # Try absolute import if running from root
    from backend.models import DetectionRequest, MaDetectionRequest, DetectionResponse, SignalResult
    from backend.services.indicators import get_market_data, calculate_dkx, check_dkx_signal, calculate_ma, check_ma_signal
    from backend.services.db import init_db, save_signal, get_history
    from backend.services.metadata import search_symbols
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
            signal_info = check_dkx_signal(df, request.lookback)
            
            if signal_info:
                # Prepare result
                # We might want to send the chart data too, but for now just the signal
                # To draw chart, frontend needs OHLC + DKX + MADKX history.
                # Let's include the last 100 candles in 'details' for charting
                
                chart_data = df.tail(100).reset_index().to_dict(orient='records')
                # Convert timestamp to string
                for item in chart_data:
                    item['date'] = item['date'].strftime("%Y-%m-%d")
                
                result = SignalResult(
                    symbol=symbol,
                    date=signal_info['date'],
                    signal=signal_info['signal'],
                    close=signal_info['price'],
                    dkx=signal_info['dkx'],
                    madkx=signal_info['madkx'],
                    details={"chart_data": chart_data}
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
            signal_info = check_ma_signal(df, request.lookback)
            
            if signal_info:
                chart_data = df.tail(100).reset_index().to_dict(orient='records')
                for item in chart_data:
                    item['date'] = item['date'].strftime("%Y-%m-%d")
                
                result = SignalResult(
                    symbol=symbol,
                    date=signal_info['date'],
                    signal=signal_info['signal'],
                    close=signal_info['price'],
                    ma_short=signal_info['ma_short'],
                    ma_long=signal_info['ma_long'],
                    details={"chart_data": chart_data}
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
