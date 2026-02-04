from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class DetectionRequest(BaseModel):
    symbols: List[str]
    market: str = "stock"  # "stock" or "futures"
    period: str = "daily"
    lookback: int = 5  # Check for signal in last N candles
    start_time: Optional[str] = None
    end_time: Optional[str] = None

class MaDetectionRequest(DetectionRequest):
    short_period: int = 5
    long_period: int = 10

class SignalResult(BaseModel):
    symbol: str
    symbol_name: str = ""
    date: str
    signal: str  # "BUY", "SELL", "NONE"
    close: float
    # Indicator specific values (optional)
    dkx: Optional[float] = None
    madkx: Optional[float] = None
    ma_short: Optional[float] = None
    ma_long: Optional[float] = None
    indicator: Optional[str] = None # DKX or MA
    offset: Optional[int] = None # How many candles ago the signal occurred (0 = latest)
    details: Dict[str, Any] = {}

class DetectionResponse(BaseModel):
    results: List[SignalResult]
