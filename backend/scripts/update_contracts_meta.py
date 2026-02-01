import akshare as ak
import pandas as pd
import json
import re
import os
import time

# Path to the JSON file
JSON_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'futures_contracts.json')

def parse_multiplier(text):
    # Extract number from "10吨/手" -> 10
    if not isinstance(text, str): return 1
    match = re.search(r'(\d+(\.\d+)?)', text)
    if match:
        return float(match.group(1))
    return 1

def parse_min_tick(text):
    # "1元/吨" -> 1
    if not isinstance(text, str): return 1
    match = re.search(r'(\d+(\.\d+)?)', text)
    if match:
        return float(match.group(1))
    return 1

def parse_margin(text):
    # "投机买卖0.070 ，套保买卖0.060" -> 0.07
    if not isinstance(text, str): return 0.1
    # Look for first percentage or decimal
    # Sometimes it's "5%" or "0.05"
    if '%' in text:
        match = re.search(r'(\d+(\.\d+)?)%', text)
        if match:
            return float(match.group(1)) / 100
    else:
        # Look for "0.07"
        match = re.search(r'(\d+\.\d+)', text)
        if match:
            return float(match.group(1))
    return 0.1

def map_exchange(text):
    if '上海' in text: return 'SHFE'
    if '大连' in text: return 'DCE'
    if '郑州' in text: return 'CZCE'
    if '金融' in text: return 'CFFEX'
    if '能源' in text: return 'INE'
    if '广州' in text: return 'GFEX'
    return 'UNKNOWN'

def update_contracts():
    print("Fetching main contracts list...")
    try:
        main_df = ak.futures_display_main_sina()
        # main_df columns: symbol (e.g. V2409), name, etc.
        # But actually akshare output might vary.
        # Let's assume 'symbol' column exists.
    except Exception as e:
        print(f"Error fetching main contracts: {e}")
        return

    print(f"Found {len(main_df)} contracts.")
    
    contracts_data = {}
    
    # Load existing to preserve manual edits if needed, or start fresh?
    # User said "Completely verify and complete", so refreshing is better, 
    # but maybe keep custom fields if any.
    if os.path.exists(JSON_PATH):
        with open(JSON_PATH, 'r', encoding='utf-8') as f:
            contracts_data = json.load(f)

    for index, row in main_df.iterrows():
        symbol = row['symbol'] # e.g. rb2410
        name = row['name'] # e.g. 螺纹钢
        
        # Extract generic code: rb2410 -> RB (or rb)
        # Usually first 1-2 letters.
        match = re.match(r'^([a-zA-Z]+)', symbol)
        if not match:
            continue
        
        code = match.group(1).upper()
        
        # Skip if we just updated this code (using main contract as proxy for all)
        # But maybe we want to verify using the *current* main contract.
        # We process it.
        
        print(f"Processing {code} ({name}) using {symbol}...")
        
        try:
            detail_df = ak.futures_contract_detail(symbol=symbol)
            # detail_df is key-value pair in 'item', 'value' columns
            
            info = {}
            for _, r in detail_df.iterrows():
                info[r['item']] = r['value']
            
            # Extract fields
            multiplier = parse_multiplier(info.get('交易单位', ''))
            min_tick = parse_min_tick(info.get('最小变动价位', ''))
            margin_rate = parse_margin(info.get('最低交易保证金', ''))
            exchange_name = info.get('上市交易所', '')
            exchange = map_exchange(exchange_name)
            quote_unit = info.get('报价单位', '')
            
            # Determine trading hours type (approximate for now, can be refined)
            # Night trading check
            trading_hours_str = info.get('交易时间', '')
            night_end = ""
            
            # Check for 2:30 (Gold, Silver, etc.)
            if '2:30' in trading_hours_str or '02:30' in trading_hours_str:
                night_end = '02:30'
            # Check for 1:00 (Copper, etc.)
            elif '1:00' in trading_hours_str or '01:00' in trading_hours_str:
                night_end = '01:00'
            # Check for 23:00 (Most others)
            elif '23:00' in trading_hours_str:
                night_end = '23:00'
            
            # Update data
            contracts_data[code] = {
                "name": name,
                "exchange": exchange,
                "multiplier": multiplier,
                "min_tick": min_tick,
                "quote_unit": quote_unit,
                "margin_rate": margin_rate,
                "trading_hours": trading_hours_str, # Store raw or simplified?
                "night_end": night_end,
                "main_contract": symbol
            }
            
            # Sleep to avoid rate limit
            time.sleep(0.5)
            
        except Exception as e:
            print(f"Failed to fetch details for {symbol}: {e}")
            # If failed, keep existing if present
            continue

    # Manual fix for SH (烧碱) if not found (it should be found if in main list)
    if 'SH' not in contracts_data:
        print("Manually adding SH (ShaoJian)...")
        # Try to fetch specific SH contract if we know one, e.g. SH2405?
        # Or just hardcode based on knowledge if akshare fails.
        contracts_data['SH'] = {
            "name": "烧碱",
            "exchange": "CZCE",
            "multiplier": 30,
            "min_tick": 1,
            "quote_unit": "元/吨",
            "margin_rate": 0.07,
            "night_end": "23:00" # Need verification
        }

    # Save
    with open(JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(contracts_data, f, ensure_ascii=False, indent=2)
    
    print(f"Updated {len(contracts_data)} contracts in {JSON_PATH}")

if __name__ == "__main__":
    update_contracts()
