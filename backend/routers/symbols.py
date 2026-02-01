from fastapi import APIRouter, Query
from typing import List, Dict
try:
    from services.metadata import search_symbols, get_default_hot_symbols
except ImportError:
    from backend.services.metadata import search_symbols, get_default_hot_symbols

router = APIRouter()

@router.get("/search", response_model=List[Dict[str, str]])
async def search_symbols_endpoint(q: str = "", market: str = "stock"):
    return search_symbols(q, market)

@router.get("/hot", response_model=List[str])
async def get_hot_symbols_endpoint():
    return get_default_hot_symbols()
