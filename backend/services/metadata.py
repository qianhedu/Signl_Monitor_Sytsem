import akshare as ak
import pandas as pd
from typing import List, Dict
try:
    from services.futures_master import load_contracts
except ImportError:
    from backend.services.futures_master import load_contracts

# 简单的内存缓存
_STOCK_CACHE = None
_FUTURES_CACHE = None
_HS300_CACHE = None

def get_hs300_list() -> List[Dict[str, str]]:
    """获取沪深300成分股列表"""
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
        return get_stock_list_fallback() # 降级处理

def get_stock_list_fallback() -> List[Dict[str, str]]:
    """获取热门A股列表作为备选方案 (Fallback)"""
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
    获取 A 股股票列表。
    """
    global _STOCK_CACHE
    if _STOCK_CACHE is not None:
        return _STOCK_CACHE

    try:
        # 尝试从 akshare 获取
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
    获取期货合约列表 (从 futures_contracts.json 加载)。
    """
    global _FUTURES_CACHE
    if _FUTURES_CACHE is not None:
        return _FUTURES_CACHE

    contracts = load_contracts()
    results = []
    
    # 按代码排序以提供更好的用户体验
    sorted_codes = sorted(contracts.keys())
    
    for code in sorted_codes:
        info = contracts[code]
        name = info.get('name', code)
        # 创建 "主力合约" (0 后缀) 条目
        # 通常用户交易连续主力合约
        symbol = f"{code}0"
        label = f"{symbol} {name}主连"
        results.append({"value": symbol, "label": label})

    # 如果缓存为空 (json 未找到)，使用降级方案或返回空
    _FUTURES_CACHE = results
    return results

def get_symbol_name(symbol: str, market: str) -> str:
    """
    从元数据中获取标的名称。
    """
    try:
        data = []
        if market == 'stock':
            # 先查 HS300，再查全列表
            if _HS300_CACHE:
                for item in _HS300_CACHE:
                    if item['value'] == symbol:
                        parts = item['label'].split(' ')
                        return parts[1] if len(parts) > 1 else item['label']
            
            # 如果 HS300 中未找到或缓存为空，尝试全列表
            data = get_stock_list()
        else:
            data = get_futures_list()
            
        for item in data:
            if item['value'] == symbol:
                parts = item['label'].split(' ')
                if len(parts) > 1:
                    return parts[1]
                return item['label']
                
        # 如果缓存中未找到且为股票，可能需要单独获取 (暂未实现)
        if market == 'stock' and not data:
             # 如果未找到，返回原代码
             pass
             
    except Exception as e:
        print(f"Error getting symbol name: {e}")
        
    return symbol

def get_symbols_info_batch(symbols: List[str], market: str) -> List[Dict[str, str]]:
    """
    批量获取标的信息 (value, label)。
    针对批量查询进行了优化。
    """
    if not symbols:
        return []
        
    # 获取该市场所有可用标的
    if market == 'stock':
        # 优先尝试 HS300 (数据量小)
        all_data = get_hs300_list()
        # 如果有标的未找到，则获取全量列表
        found_values = {item['value'] for item in all_data}
        if any(s not in found_values for s in symbols):
            all_data = get_stock_list()
    else:
        all_data = get_futures_list()
        
    # 创建映射表以实现 O(1) 查找
    data_map = {item['value']: item for item in all_data}
    
    results = []
    for s in symbols:
        if s in data_map:
            results.append(data_map[s])
        else:
            # 如果未找到，仅返回代码作为 label
            results.append({"value": s, "label": s})
            
    return results

def get_default_hot_symbols() -> List[str]:
    """
    返回后端配置的默认热门品种。
    """
    return ['RB0', 'I0', 'CU0', 'M0', 'TA0']

# 已废弃: 这些函数现在位于 futures_master.py 中
# 保留它们作为包装器以防需要，但建议在其他模块中直接使用 futures_master。


def search_symbols(query: str, market: str = "stock") -> List[Dict[str, str]]:
    """
    通过代码或名称搜索标的。
    """
    query = query.lower()
    data = []
    
    if market == "stock":
        # 检查特殊查询指令
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
