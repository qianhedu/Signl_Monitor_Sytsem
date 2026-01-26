from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class DetectionRequest(BaseModel):
    symbols: List[str]
    market: str = "stock"  # 股票或期货（"stock" 或 "futures"）
    period: str = "daily"
    lookback: int = 5  # 在最近 N 根 K 线内检查信号

class MaDetectionRequest(DetectionRequest):
    short_period: int = 5
    long_period: int = 10

class SignalResult(BaseModel):
    symbol: str
    name: Optional[str] = None
    date: str
    signal: str  # 信号类型：BUY、SELL 或 NONE
    close: float
    # 指标相关的可选字段
    dkx: Optional[float] = None
    madkx: Optional[float] = None
    ma_short: Optional[float] = None
    ma_long: Optional[float] = None
    details: Dict[str, Any] = {}

class DetectionResponse(BaseModel):
    results: List[SignalResult]
