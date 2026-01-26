from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from typing import List
import pandas as pd

# 导入本地模块
# 通常在 backend 目录运行。如果从项目根运行，需要使用 'backend.models' 等绝对路径。
# 标准做法是在 backend 下运行或正确设置 PYTHONPATH。
# 这里优先使用相对导入，或假设在 backend 目录下执行 'python main.py'。
try:
    from models import DetectionRequest, MaDetectionRequest, DetectionResponse, SignalResult
    from services.indicators import get_market_data, calculate_dkx, check_dkx_signal, calculate_ma, check_ma_signal
    from services.db import init_db, save_signal, get_history
    from services.metadata import search_symbols, get_symbol_name
except ImportError:
    # 若从项目根目录运行，尝试使用绝对导入
    from backend.models import DetectionRequest, MaDetectionRequest, DetectionResponse, SignalResult
    from backend.services.indicators import get_market_data, calculate_dkx, check_dkx_signal, calculate_ma, check_ma_signal
    from backend.services.db import init_db, save_signal, get_history
    from backend.services.metadata import search_symbols, get_symbol_name

app = FastAPI(title="Signal Monitor System API")

@app.on_event("startup")
def on_startup():
    init_db()

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Signal Monitor System API is running"}

@app.post("/api/detect/dkx", response_model=DetectionResponse)
async def detect_dkx(request: DetectionRequest):
    results = []
    
    for symbol in request.symbols:
        # 获取数据
        # 注：akshare 的股票代码常需检查（如 '000001' 的交易所前缀），
        # 这里假设用户提供了正确代码，或内部进行处理。
        # stock_zh_a_hist 接受 6 位股票代码。
        
        try:
            df = get_market_data(symbol, request.market, request.period)
            if df.empty:
                continue
                
            df = calculate_dkx(df)
            signal_info = check_dkx_signal(df, request.lookback)
            
            if signal_info:
                # 组装结果
                # 可同时返回图表数据；前端绘图需要 OHLC + DKX + MADKX 历史。
                # 在 details 中附带最近若干根 K 线用于绘图。
                
                chart_data = df.tail(500).reset_index().to_dict(orient='records')
                for item in chart_data:
                    if request.period in ["240", "120", "60", "30", "15", "5", "1"]:
                        item['date'] = item['date'].strftime("%Y-%m-%d %H:%M")
                    else:
                        item['date'] = item['date'].strftime("%Y-%m-%d")
                
                result = SignalResult(
                    symbol=symbol,
                    name=get_symbol_name(symbol, request.market),
                    date=signal_info['date'],
                    signal=signal_info['signal'],
                    close=signal_info['price'],
                    dkx=signal_info['dkx'],
                    madkx=signal_info['madkx'],
                    details={"chart_data": chart_data, "signal_point": {"date": signal_info['date'], "signal": signal_info['signal']}}
                )
                
                # 保存到数据库
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
                chart_data = df.tail(500).reset_index().to_dict(orient='records')
                for item in chart_data:
                    if request.period in ["240", "120", "60", "30", "15", "5", "1"]:
                        item['date'] = item['date'].strftime("%Y-%m-%d %H:%M")
                    else:
                        item['date'] = item['date'].strftime("%Y-%m-%d")
                
                result = SignalResult(
                    symbol=symbol,
                    name=get_symbol_name(symbol, request.market),
                    date=signal_info['date'],
                    signal=signal_info['signal'],
                    close=signal_info['price'],
                    ma_short=signal_info['ma_short'],
                    ma_long=signal_info['ma_long'],
                    details={"chart_data": chart_data, "signal_point": {"date": signal_info['date'], "signal": signal_info['signal']}}
                )
                
                # 保存到数据库
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

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8802, reload=True)
