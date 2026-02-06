from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from typing import List
import pandas as pd

# 导入本地模块
# 假设从 'backend' 或根目录运行。如果在根目录，需要 'backend.models'。
# 但标准是在 backend 内部运行或设置 PYTHONPATH。
# 我将使用相对导入或假设在 backend 文件夹内运行 'python main.py'。
from contextlib import asynccontextmanager

try:
    from models import DetectionRequest, MaDetectionRequest, DetectionResponse, SignalResult
    from services.indicators import get_market_data, calculate_dkx, check_dkx_signal, calculate_ma, check_ma_signal
    from services.db import init_db, save_signal, get_history
    from services.metadata import search_symbols, get_symbol_name
    from services.export_service import create_export_zip, create_dkx_plot, create_ma_plot
    from routers import backtest, symbols
except ImportError:
    # 如果从根目录运行，尝试绝对导入
    from backend.models import DetectionRequest, MaDetectionRequest, DetectionResponse, SignalResult
    from backend.services.indicators import get_market_data, calculate_dkx, check_dkx_signal, calculate_ma, check_ma_signal
    from backend.services.db import init_db, save_signal, get_history
    from backend.services.metadata import search_symbols, get_symbol_name
    from backend.services.export_service import create_export_zip, create_dkx_plot, create_ma_plot
    from backend.routers import backtest, symbols

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(title="Signal Monitor System API (信号监控系统 API)", lifespan=lifespan)

# 配置 CORS
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
        # 获取数据
        # 注意: akshare 的代码通常需要检查 (例如: 深沪股票代码需要调整或确保正确)
        # 我们假设用户提供了正确的代码或已在其他地方处理。
        # stock_zh_a_hist 接受 6 位代码。
        
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
                # 确保每个标的只返回最新的信号
                latest_signal = signals[-1]
                
                # 严格的时间窗口验证 (Strict Window Validation)
                # 虽然 check_dkx_signal 使用了 lookback，但我们在此显式验证 offset
                # 用户需求: 
                # - 如果信号 offset >= lookback，排除它。
                # - 边界处的信号 (offset < lookback) 被包含。
                # 注意: offset 是基于末尾的 0-based 索引。offset 19 表示倒数第 20 根 K 线。
                # 如果 lookback=20，我们接受 offset 0..19。
                if latest_signal.get('offset') is not None and latest_signal['offset'] >= request.lookback:
                     continue
                     
                signals = [latest_signal]
            
            symbol_name = get_symbol_name(symbol, request.market)

            for signal_info in signals:
                # 准备结果
                # 我们需要发送以信号为中心或相关范围的图表数据，
                # 并在该范围内包含所有信号作为图表标记。
                
                # 在原始 df 中查找信号索引
                try:
                    sig_date = pd.to_datetime(signal_info['date'])
                    # 如果 signal_info['date'] 来自 format_date，它是字符串。
                    # pd.to_datetime 会将其转换为 naive (如果字符串本身是 naive)。
                    # check_dkx_signal 使用 strftime，所以是字符串。
                    # 我们需要在 df.index 中找到它。
                    # 如果 df.index 是 naive，完美。
                    # 如果 df.index 是 aware，我们可能需要匹配时区。
                    
                    if df.index.tz is not None and sig_date.tzinfo is None:
                        sig_date = sig_date.tz_localize(df.index.tz)

                    loc = df.index.get_loc(sig_date)
                    if isinstance(loc, slice): loc = loc.start
                    
                    # 定义图表窗口: 增加范围 (用户需求)
                    # 向前 2000 根，向后 200 根，以确保有足够的历史数据
                    start_pos = max(0, loc - 2000)
                    end_pos = min(len(df), loc + 200)
                    
                    # 确保最小长度
                    if end_pos - start_pos < 1000:
                        start_pos = max(0, end_pos - 1000)
                    
                    chart_df = df.iloc[start_pos:end_pos]
                    chart_data = chart_df.reset_index().to_dict(orient='records')
                    # 转换时间戳为字符串
                    for item in chart_data:
                        item['date'] = format_date(item['date'])
                        
                    # 查找此图表窗口内的所有信号用于标记
                    c_start = format_date(chart_df.index[0])
                    c_end = format_date(chart_df.index[-1])
                    # 使用 lookback=0 查找范围内的所有信号
                    chart_signals = check_dkx_signal(df, lookback=0, start_time=c_start, end_time=c_end)
                    
                    # 如果主信号是 'State' 信号 (非交叉)，将其添加到 chart_signals 以便标记
                    if signal_info.get('is_state'):
                         chart_signals.append(signal_info)
                    
                except Exception as ex:
                    print(f"Error preparing chart data: {ex}")
                    # 降级处理 (Fallback)
                    chart_data = df.tail(300).reset_index().to_dict(orient='records')
                    for item in chart_data:
                        item['date'] = format_date(item['date'])
                    chart_signals = []
                
                result = SignalResult(
                    symbol=symbol,
                    symbol_name=symbol_name,
                    date=format_date(pd.to_datetime(signal_info['date'])), # 确保格式
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
                # 确保每个标的只返回最新的信号
                latest_signal = signals[-1]
                
                # 严格的时间窗口验证
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
                    
                    # 增加范围
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
async def search_symbols_api(q: str = "", market: str = "stock"):
    return search_symbols(q, market)

@app.post("/api/export/dkx")
async def export_dkx(request: DetectionRequest):
    results = []
    charts_map = {}
    
    for symbol in request.symbols:
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
                latest_signal = signals[-1]
                if latest_signal.get('offset') is not None and latest_signal['offset'] >= request.lookback:
                     continue
                signals = [latest_signal]
            
            symbol_name = get_symbol_name(symbol, request.market)

            for signal_info in signals:
                # Generate Plot
                plot_bytes = create_dkx_plot(df.tail(300), symbol, symbol_name, signal_info['date'])
                charts_map[f"{symbol}_{str(signal_info['date']).replace(':', '-').replace(' ', '_')}.png"] = plot_bytes
                
                results.append({
                    "标的代码": f"\t{symbol}",
                    "名称": symbol_name,
                    "信号日期": format_date(pd.to_datetime(signal_info['date'])),
                    "信号": "买入" if signal_info['signal'] == 'BUY' else "卖出",
                    "收盘价": signal_info['price'],
                    "DKX": signal_info['dkx'],
                    "MADKX": signal_info['madkx']
                })
                
        except Exception as e:
            print(f"Error exporting DKX for {symbol}: {e}")
            continue
            
    if not results:
        raise HTTPException(status_code=404, detail="No data found for export")

    csv_df = pd.DataFrame(results)
    csv_content = csv_df.to_csv(index=False)
    
    zip_bytes = create_export_zip(csv_content, charts_map, "dkx_signals.csv")
    
    return Response(
        content=zip_bytes.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=dkx_export.zip"}
    )

@app.post("/api/export/ma")
async def export_ma(request: MaDetectionRequest):
    results = []
    charts_map = {}
    
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
                latest_signal = signals[-1]
                if latest_signal.get('offset') is not None and latest_signal['offset'] >= request.lookback:
                     continue
                signals = [latest_signal]
            
            symbol_name = get_symbol_name(symbol, request.market)

            for signal_info in signals:
                # Generate Plot
                plot_bytes = create_ma_plot(df.tail(300), symbol, symbol_name, request.short_period, request.long_period, signal_info['date'])
                charts_map[f"{symbol}_{str(signal_info['date']).replace(':', '-').replace(' ', '_')}.png"] = plot_bytes
                
                results.append({
                    "标的代码": f"\t{symbol}",
                    "名称": symbol_name,
                    "信号日期": format_date(pd.to_datetime(signal_info['date'])),
                    "信号": "买入" if signal_info['signal'] == 'BUY' else "卖出",
                    "收盘价": signal_info['price'],
                    "短期均线": signal_info['ma_short'],
                    "长期均线": signal_info['ma_long']
                })
                
        except Exception as e:
            print(f"Error exporting MA for {symbol}: {e}")
            continue
            
    if not results:
        raise HTTPException(status_code=404, detail="No data found for export")

    csv_df = pd.DataFrame(results)
    csv_content = csv_df.to_csv(index=False)
    
    zip_bytes = create_export_zip(csv_content, charts_map, "ma_signals.csv")
    
    return Response(
        content=zip_bytes.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=ma_export.zip"}
    )

@app.get("/api/symbols/hot")
def get_hot_symbols_endpoint():
    return get_default_hot_symbols()

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
