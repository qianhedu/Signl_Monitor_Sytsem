from fastapi import APIRouter, Query, Body
from typing import List, Dict
try:
    from services.metadata import search_symbols, get_default_hot_symbols, get_symbols_info_batch
except ImportError:
    from backend.services.metadata import search_symbols, get_default_hot_symbols, get_symbols_info_batch

router = APIRouter()

@router.get("/search", response_model=List[Dict[str, str]])
async def search_symbols_endpoint(q: str = "", market: str = "stock"):
    """
    搜索标的端点。
    
    逻辑:
        根据查询关键词 `q` 和市场类型 `market` 模糊搜索匹配的标的。
        返回包含标的代码 (value) 和显示名称 (label) 的列表。
    """
    return search_symbols(q, market)

@router.get("/hot", response_model=List[str])
async def get_hot_symbols_endpoint():
    """
    获取热门标的端点。
    
    逻辑:
        返回系统预设的一组热门标的代码列表。
        通常用于前端初始化时的默认展示。
    """
    return get_default_hot_symbols()

@router.post("/info", response_model=List[Dict[str, str]])
async def get_symbols_info_endpoint(symbols: List[str] = Body(...), market: str = Body("stock")):
    """
    批量获取标的信息端点。
    
    逻辑:
        接收标的代码列表，批量查询对应的详细信息（如中文名称）。
        主要用于前端回显已保存的标的列表的中文名称。
    """
    return get_symbols_info_batch(symbols, market)
