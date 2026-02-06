from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class DetectionRequest(BaseModel):
    symbols: List[str]
    market: str = "stock"  # "stock" (股票) 或 "futures" (期货)
    period: str = "daily"
    lookback: int = 5  # 检查最近 N 根 K 线内的信号
    start_time: Optional[str] = None
    end_time: Optional[str] = None

class MaDetectionRequest(DetectionRequest):
    short_period: int = 5
    long_period: int = 10

class SignalResult(BaseModel):
    symbol: str
    symbol_name: str = ""
    date: str
    signal: str  # "BUY" (买入), "SELL" (卖出), "NONE" (无)
    close: float
    # 特定指标值 (可选)
    dkx: Optional[float] = None
    madkx: Optional[float] = None
    ma_short: Optional[float] = None
    ma_long: Optional[float] = None
    indicator: Optional[str] = None # DKX 或 MA
    offset: Optional[int] = None # 信号发生在多少根 K 线之前 (0 = 最新)
    details: Dict[str, Any] = {}

class DetectionResponse(BaseModel):
    results: List[SignalResult]
