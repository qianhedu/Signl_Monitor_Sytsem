from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
try:
    from services.backtest import run_backtest_dkx, run_backtest_ma
except ImportError:
    from backend.services.backtest import run_backtest_dkx, run_backtest_ma

router = APIRouter()

class BacktestRequest(BaseModel):
    symbols: List[str]
    market: str
    period: str
    start_time: str
    end_time: str
    initial_capital: float = 100000.0
    lot_size: int = 20
    lookback: Optional[int] = 20 # DKX 参数，虽然目前计算中固定了

class MaBacktestRequest(BaseModel):
    symbols: List[str]
    market: str
    period: str
    start_time: str
    end_time: str
    initial_capital: float = 100000.0
    lot_size: int = 20
    short_period: int = 5
    long_period: int = 20

@router.post("/dkx")
async def backtest_dkx_endpoint(request: BacktestRequest):
    """
    DKX 策略回测端点
    """
    try:
        results = run_backtest_dkx(
            symbols=request.symbols,
            market=request.market,
            period=request.period,
            start_time=request.start_time,
            end_time=request.end_time,
            initial_capital=request.initial_capital,
            lot_size=request.lot_size
        )
        return {"results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/ma")
async def backtest_ma_endpoint(request: MaBacktestRequest):
    """
    双均线策略回测端点
    """
    try:
        results = run_backtest_ma(
            symbols=request.symbols,
            market=request.market,
            period=request.period,
            start_time=request.start_time,
            end_time=request.end_time,
            initial_capital=request.initial_capital,
            lot_size=request.lot_size,
            short_period=request.short_period,
            long_period=request.long_period
        )
        return {"results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
