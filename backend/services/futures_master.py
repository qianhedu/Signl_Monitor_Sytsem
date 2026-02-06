import json
import os
import re

DATA_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'futures_contracts.json')

_contracts_cache = None

def load_contracts():
    """
    加载期货合约元数据配置。
    
    逻辑:
        1. 检查内存缓存 `_contracts_cache` 是否已加载。
        2. 如果未加载，检查本地 JSON 配置文件是否存在。
        3. 读取并解析 JSON 文件到内存缓存。
        4. 如果文件不存在，初始化为空字典。
    """
    global _contracts_cache
    if _contracts_cache is None:
        if os.path.exists(DATA_PATH):
            with open(DATA_PATH, 'r', encoding='utf-8') as f:
                _contracts_cache = json.load(f)
        else:
            _contracts_cache = {}
    return _contracts_cache

def get_contract_code(symbol: str) -> str:
    """
    从完整合约代码获取品种代码 (例如 FG205 -> FG)。
    
    逻辑:
        1. 将输入代码转为大写。
        2. 使用正则表达式提取开头的字母部分作为品种代码。
        3. 如果匹配失败，返回原代码。
    """
    symbol = symbol.upper()
    match = re.match(r"([A-Z]+)", symbol)
    if match:
        return match.group(1)
    return symbol

def get_contract_info(symbol: str):
    """
    获取指定合约的详细信息。
    
    逻辑:
        1. 加载所有合约配置。
        2. 解析输入代码获取品种代码。
        3. 从配置中查找对应品种的信息，找不到则返回空字典。
    """
    contracts = load_contracts()
    code = get_contract_code(symbol)
    return contracts.get(code, {})

def get_multiplier(symbol: str) -> float:
    """
    获取合约乘数 (交易单位)。
    
    逻辑:
        1. 获取合约详细信息。
        2. 返回 `multiplier` 字段值，默认为 10。
    """
    info = get_contract_info(symbol)
    # 默认为 10，但应尽量确保配置存在
    return info.get('multiplier', 10)

def get_min_tick(symbol: str) -> float:
    """
    获取最小变动价位。
    
    逻辑:
        1. 获取合约详细信息。
        2. 返回 `min_tick` 字段值，默认为 1.0。
    """
    info = get_contract_info(symbol)
    return info.get('min_tick', 1.0)

def get_margin_rate(symbol: str) -> float:
    """
    获取保证金比例。
    
    逻辑:
        1. 获取合约详细信息。
        2. 返回 `margin_rate` 字段值，默认为 0.10 (10%)。
    """
    info = get_contract_info(symbol)
    return info.get('margin_rate', 0.10)

def get_night_end_time(symbol: str) -> str:
    """
    获取夜盘结束时间。
    返回: '23:00', '01:00', '02:30' 或 None (无夜盘)。
    
    逻辑:
        1. 获取合约详细信息。
        2. 返回 `night_end` 字段值。
    """
    info = get_contract_info(symbol)
    return info.get('night_end', None)

def get_trading_hours_type(symbol: str) -> str:
    """
    获取交易时段类型。
    返回: 'no_night' (无夜盘), 'late_night' (至01:00), 'standard_night' (至23:00), 'late_night_2:30' (至02:30)
    
    逻辑:
        1. 获取夜盘结束时间。
        2. 如果无夜盘结束时间，返回 'no_night'。
        3. 根据具体时间返回对应的类型标识。
    """
    night_end = get_night_end_time(symbol)
    if not night_end:
        return 'no_night'
    if night_end == '01:00':
        return 'late_night'
    if night_end == '02:30':
        return 'late_night_2:30'
    return 'standard_night'
