import akshare as ak
import pandas as pd
from typing import List, Dict

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
        print(f"获取沪深300失败: {e}")
        return get_stock_list_fallback() # 回退

def get_stock_list_fallback() -> List[Dict[str, str]]:
    """常用热门 A 股列表（回退）"""
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
    获取 A 股列表。
    """
    global _STOCK_CACHE
    if _STOCK_CACHE is not None:
        return _STOCK_CACHE

    try:
        # 尝试通过 akshare 获取
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
        print(f"获取股票列表失败: {e}")
        _STOCK_CACHE = get_stock_list_fallback()
        return _STOCK_CACHE

def get_futures_list() -> List[Dict[str, str]]:
    global _FUTURES_CACHE
    if _FUTURES_CACHE is not None:
        return _FUTURES_CACHE

    try:
        df = ak.futures_zh_spot()
        codes = set()
        if df is not None and not df.empty:
            cols = [c for c in ['symbol', '代码', '合约'] if c in df.columns]
            for _, row in df.iterrows():
                val = None
                for c in cols:
                    v = str(row[c])
                    if v:
                        val = v
                        break
                if not val:
                    continue
                prefix = ''
                for ch in val:
                    if ch.isalpha():
                        prefix += ch
                    else:
                        break
                if not prefix:
                    continue
                code = prefix.upper() + '0'
                codes.add(code)
        common_futures = [
            ("RB0", "螺纹钢主力"), ("HC0", "热卷主力"), ("FU0", "燃油主力"), ("BU0", "沥青主力"), ("RU0", "橡胶主力"),
            ("SP0", "纸浆主力"), ("CU0", "沪铜主力"), ("AL0", "沪铝主力"), ("ZN0", "沪锌主力"), ("PB0", "沪铅主力"),
            ("NI0", "沪镍主力"), ("SN0", "沪锡主力"), ("AU0", "黄金主力"), ("AG0", "白银主力"), ("SS0", "不锈钢主力"),
            ("M0", "豆粕主力"), ("Y0", "豆油主力"), ("A0", "豆一主力"), ("B0", "豆二主力"), ("P0", "棕榈油主力"),
            ("C0", "玉米主力"), ("CS0", "淀粉主力"), ("JD0", "鸡蛋主力"), ("I0", "铁矿石主力"), ("J0", "焦炭主力"),
            ("JM0", "焦煤主力"), ("L0", "塑料主力"), ("V0", "PVC主力"), ("PP0", "聚丙烯主力"), ("EG0", "乙二醇主力"),
            ("EB0", "苯乙烯主力"), ("PG0", "LPG主力"), ("LH0", "生猪主力"),
            ("SR0", "白糖主力"), ("CF0", "棉花主力"), ("TA0", "PTA主力"), ("MA0", "甲醇主力"), ("FG0", "玻璃主力"),
            ("SA0", "纯碱主力"), ("OI0", "菜油主力"), ("RM0", "菜粕主力"), ("RS0", "菜籽主力"), ("ZC0", "动力煤主力"),
            ("SF0", "硅铁主力"), ("SM0", "锰硅主力"), ("AP0", "苹果主力"), ("CJ0", "红枣主力"), ("PK0", "花生主力"),
            ("UR0", "尿素主力"),
            ("IF0", "沪深300主力"), ("IC0", "中证500主力"), ("IH0", "上证50主力"), ("IM0", "中证1000主力"),
            ("T0", "10年期国债主力"), ("TF0", "5年期国债主力"), ("TS0", "2年期国债主力")
        ]
        label_map = {code: name for code, name in common_futures}
        results = []
        for code in sorted(codes):
            name = label_map.get(code, code.replace('0', '') + '主力')
            results.append({"value": code, "label": f"{code} {name}"})
        if not results:
            results = [{"value": code, "label": f"{code} {name}"} for code, name in common_futures]
        _FUTURES_CACHE = results
        return results
    except Exception:
        common_futures = [
            ("RB0", "螺纹钢主力"), ("HC0", "热卷主力"), ("FU0", "燃油主力"), ("BU0", "沥青主力"), ("RU0", "橡胶主力"),
            ("SP0", "纸浆主力"), ("CU0", "沪铜主力"), ("AL0", "沪铝主力"), ("ZN0", "沪锌主力"), ("PB0", "沪铅主力"),
            ("NI0", "沪镍主力"), ("SN0", "沪锡主力"), ("AU0", "黄金主力"), ("AG0", "白银主力"), ("SS0", "不锈钢主力"),
            ("M0", "豆粕主力"), ("Y0", "豆油主力"), ("A0", "豆一主力"), ("B0", "豆二主力"), ("P0", "棕榈油主力"),
            ("C0", "玉米主力"), ("CS0", "淀粉主力"), ("JD0", "鸡蛋主力"), ("I0", "铁矿石主力"), ("J0", "焦炭主力"),
            ("JM0", "焦煤主力"), ("L0", "塑料主力"), ("V0", "PVC主力"), ("PP0", "聚丙烯主力"), ("EG0", "乙二醇主力"),
            ("EB0", "苯乙烯主力"), ("PG0", "LPG主力"),
            ("SR0", "白糖主力"), ("CF0", "棉花主力"), ("TA0", "PTA主力"), ("MA0", "甲醇主力"), ("FG0", "玻璃主力"),
            ("SA0", "纯碱主力"), ("OI0", "菜油主力"), ("RM0", "菜粕主力"), ("RS0", "菜籽主力"), ("ZC0", "动力煤主力"),
            ("SF0", "硅铁主力"), ("SM0", "锰硅主力"), ("AP0", "苹果主力"), ("CJ0", "红枣主力"), ("PK0", "花生主力"),
            ("UR0", "尿素主力"),
            ("IF0", "沪深300主力"), ("IC0", "中证500主力"), ("IH0", "上证50主力"), ("IM0", "中证1000主力"),
            ("T0", "10年期国债主力"), ("TF0", "5年期国债主力"), ("TS0", "2年期国债主力")
        ]
        results = [{"value": code, "label": f"{code} {name}"} for code, name in common_futures]
        _FUTURES_CACHE = results
        return results

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

def get_symbol_name(symbol: str, market: str = "stock") -> str:
    data: List[Dict[str, str]] = []
    if market == "stock":
        data = get_stock_list()
    elif market == "futures":
        data = get_futures_list()
    for item in data:
        if item.get("value") == symbol:
            label = item.get("label", symbol)
            parts = label.split(" ", 1)
            if len(parts) == 2:
                return parts[1]
            return label
    return symbol
