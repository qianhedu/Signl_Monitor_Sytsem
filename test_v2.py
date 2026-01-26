import requests
import json
from backend.services.indicators import get_market_data

def test_metadata_search():
    print("\n--- 测试元数据搜索 ---")
    try:
        # 测试沪深300
        url = "http://localhost:8802/api/symbols/search"
        res = requests.get(url, params={"q": "hs300", "market": "stock"})
        data = res.json()
        print(f"沪深300数量: {len(data)}")
        if data:
            print("沪深300首项:", data[0])
            
        # 测试全部期货
        res = requests.get(url, params={"q": "all", "market": "futures"})
        data = res.json()
        print(f"期货数量: {len(data)}")
        if data:
            print("期货首项:", data[0])
    except Exception as e:
        print(f"搜索错误: {e}")

def test_minute_data():
    print("\n--- 测试分钟数据获取（后端逻辑） ---")
    try:
        # 股票分钟
        # 600519 -> 函数内部转换为 sh600519
        print("获取 600519 60分钟数据...")
        df = get_market_data("600519", market="stock", period="60")
        print(f"Rows: {len(df)}")
        if not df.empty:
            print(df.tail(2))
            
        # 期货分钟
        print("获取 RB0 60分钟数据...")
        df = get_market_data("RB0", market="futures", period="60")
        print(f"Rows: {len(df)}")
        if not df.empty:
            print(df.tail(2))
            
    except Exception as e:
        print(f"数据错误: {e}")

if __name__ == "__main__":
    # 若需进行搜索测试，请确保后端已运行；
    # 此处直接测试 get_market_data
    test_minute_data()
    # test_metadata_search() # 若后端已运行，可取消注释
