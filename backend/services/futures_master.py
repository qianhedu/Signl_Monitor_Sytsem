import json
import os
import re

DATA_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'futures_contracts.json')

_contracts_cache = None

def load_contracts():
    """
    加载期货合约元数据配置。
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
    """
    symbol = symbol.upper()
    match = re.match(r"([A-Z]+)", symbol)
    if match:
        return match.group(1)
    return symbol

def get_contract_info(symbol: str):
    """
    获取指定合约的详细信息。
    """
    contracts = load_contracts()
    code = get_contract_code(symbol)
    return contracts.get(code, {})

def get_multiplier(symbol: str) -> float:
    """
    获取合约乘数 (交易单位)。
    """
    info = get_contract_info(symbol)
    # 默认为 10，但应尽量确保配置存在
    return info.get('multiplier', 10)

def get_min_tick(symbol: str) -> float:
    """
    获取最小变动价位。
    """
    info = get_contract_info(symbol)
    return info.get('min_tick', 1.0)

def get_margin_rate(symbol: str) -> float:
    """
    获取保证金比例。
    """
    info = get_contract_info(symbol)
    return info.get('margin_rate', 0.10)

def get_night_end_time(symbol: str) -> str:
    """
    获取夜盘结束时间。
    返回: '23:00', '01:00', '02:30' 或 None (无夜盘)。
    """
    info = get_contract_info(symbol)
    return info.get('night_end', None)

def get_trading_hours_type(symbol: str) -> str:
    """
    获取交易时段类型。
    返回: 'no_night' (无夜盘), 'late_night' (至01:00), 'standard_night' (至23:00), 'late_night_2:30' (至02:30)
    """
    night_end = get_night_end_time(symbol)
    if not night_end:
        return 'no_night'
    if night_end == '01:00':
        return 'late_night'
    if night_end == '02:30':
        return 'late_night_2:30'
    return 'standard_night'
