import akshare as ak
import pandas as pd
from typing import List, Dict
try:
    from services.futures_master import load_contracts
except ImportError:
    from backend.services.futures_master import load_contracts

# Simple in-memory cache
_STOCK_CACHE = None
_FUTURES_CACHE = None
_HS300_CACHE = None

def get_hs300_list() -> List[Dict[str, str]]:
    """Get HS300 constituent stocks"""
    global _HS300_CACHE
    if _HS300_CACHE is not None:
        return _HS300_CACHE
        
    try:
        df = ak.index_stock_cons(symbol="000300")
        results = []
        for _, row in df.iterrows():
            code = str(row['品种代码'])
            name = str(row['品种名称'])
            results.append({"value": code, "label": f"{code} {name}"})
        _HS300_CACHE = results
        return results
    except Exception as e:
        print(f"Error fetching HS300: {e}")
        return get_stock_list_fallback() # Fallback

def get_stock_list_fallback() -> List[Dict[str, str]]:
    """Fallback list of popular A-share stocks"""
    stocks = [
        ("600519", "贵州茅台"), ("000858", "五粮液"), ("601318", "中国平安"), ("600036", "招商银行"),
        ("002594", "比亚迪"), ("300750", "宁德时代"), ("000001", "平安银行"), ("600900", "长江电力"),
        ("601888", "中国中免"), ("000333", "美的集团"), ("603288", "海天味业"), ("002415", "海康威视"),
        ("601166", "兴业银行"), ("600276", "恒瑞医药"), ("600030", "中信证券"), ("300059", "东方财富"),
        ("002714", "牧原股份"), ("000651", "格力电器"), ("601012", "隆基绿能"), ("600887", "伊利股份"),
        ("601919", "中远海控"), ("601088", "中国神华"), ("601857", "中国石油"), ("600028", "中国石化")
    ]
    return [{"value": code, "label": f"{code} {name}"} for code, name in stocks]

def get_stock_list() -> List[Dict[str, str]]:
    """
    Get list of A-share stocks.
    """
    global _STOCK_CACHE
    if _STOCK_CACHE is not None:
        return _STOCK_CACHE

    try:
        # Try to fetch from akshare
        df = ak.stock_zh_a_spot_em()
        if df.empty:
            _STOCK_CACHE = get_stock_list_fallback()
            return _STOCK_CACHE
            
        results = []
        df = df[['代码', '名称']]
        for _, row in df.iterrows():
            code = str(row['代码'])
            name = str(row['名称'])
            results.append({
                "value": code,
                "label": f"{code} {name}"
            })
            
        _STOCK_CACHE = results
        return results
    except Exception as e:
        print(f"Error fetching stock list: {e}")
        _STOCK_CACHE = get_stock_list_fallback()
        return _STOCK_CACHE

def get_futures_list() -> List[Dict[str, str]]:
    """
    Get list of Futures (from futures_contracts.json).
    """
    global _FUTURES_CACHE
    if _FUTURES_CACHE is not None:
        return _FUTURES_CACHE

    contracts = load_contracts()
    results = []
    
    # Sort by code for better UX
    sorted_codes = sorted(contracts.keys())
    
    for code in sorted_codes:
        info = contracts[code]
        name = info.get('name', code)
        # Create "Main Contract" (0 suffix) entry
        # Usually users trade the main continuous contract
        symbol = f"{code}0"
        label = f"{symbol} {name}主力"
        results.append({"value": symbol, "label": label})

    # If cache is empty (json not found), fallback or just return empty
    if not results:
        # Fallback to a few common ones if json is missing
        return [
            {"value": "RB0", "label": "RB0 螺纹钢主力"},
            {"value": "I0", "label": "I0 铁矿石主力"},
            {"value": "CU0", "label": "CU0 沪铜主力"},
        ]
        
    _FUTURES_CACHE = results
    return results

def get_default_hot_symbols() -> List[str]:
    """
    Return default hot symbols configured in backend.
    """
    return ['RB0', 'I0', 'CU0', 'M0', 'TA0']

# Deprecated: These functions are now in futures_master.py
# Keeping them here as wrappers if needed, but better to use futures_master directly in other modules.


def search_symbols(query: str, market: str = "stock") -> List[Dict[str, str]]:
    """
    Search symbols by code or name.
    """
    query = query.lower()
    data = []
    
    if market == "stock":
        # Check for special query commands
        if query == "hs300":
            return get_hs300_list()
            
        data = get_stock_list()
    elif market == "futures":
        if query == "all":
            return get_futures_list()
            
        data = get_futures_list()
        
    if not query:
        return data[:50] 
        
    filtered = [
        item for item in data 
        if query in item['value'].lower() or query in item['label'].lower()
    ]
    
    return filtered[:50]
