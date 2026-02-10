import json
import os
import re
import datetime

# Path config
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_FILE = os.path.join(BASE_DIR, 'data', 'futures_contracts.json')
REPORT_FILE = os.path.join(BASE_DIR, 'data', 'fix_report.md')

# Manual patches for contracts with missing/incorrect night hours
# Format: "Symbol": "Start-End" (Raw night session range)
NIGHT_HOURS_PATCH = {
    "SS": "21:00-01:00", # Stainless Steel
    "SN": "21:00-01:00", # Tin
    "BC": "21:00-01:00", # Bonded Copper
    "EB": "21:00-23:00", # Styrene
    "PG": "21:00-23:00", # LPG
    "SA": "21:00-23:00", # Soda Ash
    "PF": "21:00-23:00", # Polyester Staple Fiber
    "FU": "21:00-23:00", # Fuel Oil
    "LU": "21:00-23:00", # Low Sulfur Fuel Oil
    "BR": "21:00-23:00", # Butadiene Rubber
    "SM": "21:00-23:00", # Manganese Silicon
    "SF": "21:00-23:00", # Ferrosilicon
    "CY": "21:00-23:00", # Cotton Yarn
    "SC": "21:00-02:30", # Crude Oil (Verify)
    "AU": "21:00-02:30", # Gold (Verify)
    "AG": "21:00-02:30", # Silver (Verify)
    "NI": "21:00-01:00", # Nickel (Verify)
    "ZN": "21:00-01:00", # Zinc (Verify)
    "PB": "21:00-01:00", # Lead (Verify)
    "AL": "21:00-01:00", # Aluminum (Verify)
    "CU": "21:00-01:00", # Copper (Verify)
    "RB": "21:00-23:00", # Rebar (Verify)
    "HC": "21:00-23:00", # Hot Rolled Coil (Verify)
    "BU": "21:00-23:00", # Bitumen (Verify)
    "SP": "21:00-23:00", # Paper Pulp (Verify)
    "NR": "21:00-23:00", # NR (Verify)
}

def load_json(path):
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def split_night_hours(raw_range):
    """
    Splits a night range like '21:00-01:00' into ['21:00-24:00', '00:00-01:00']
    If no cross-day, returns [raw_range].
    """
    if not raw_range:
        return []
    
    start, end = raw_range.split('-')
    sh, sm = map(int, start.split(':'))
    eh, em = map(int, end.split(':'))
    
    # Check for cross-day: end hour < start hour
    # or specifically for night trading starting at 20:00+ and ending < 08:00
    if (sh >= 20) and (eh < sh):
        return [f"{start}-24:00", f"00:00-{end}"]
    
    return [raw_range]

def fix_contracts():
    data = load_json(DATA_FILE)
    report_lines = ["# Contract Hours Fix Report", "", f"Fix Time: {datetime.datetime.now()}", "", "| Symbol | Field | Old Value | New Value |", "|---|---|---|---|"]
    
    fixed_count = 0
    
    for symbol, contract in data.items():
        # 1. Apply Night Hours Patch
        if symbol in NIGHT_HOURS_PATCH:
            raw_night = NIGHT_HOURS_PATCH[symbol]
            expected_night_hours = split_night_hours(raw_night)
            expected_night_end = raw_night.split('-')[1]
            
            # Update night_hours
            if contract.get('night_hours') != expected_night_hours:
                report_lines.append(f"| {symbol} | night_hours | {contract.get('night_hours')} | {expected_night_hours} |")
                contract['night_hours'] = expected_night_hours
                fixed_count += 1
            
            # Update night_end
            if contract.get('night_end') != expected_night_end:
                report_lines.append(f"| {symbol} | night_end | {contract.get('night_end')} | {expected_night_end} |")
                contract['night_end'] = expected_night_end
                fixed_count += 1

        # 2. General Validation & Formatting
        # Ensure day_hours exists and is list
        if 'day_hours' not in contract or not isinstance(contract['day_hours'], list):
            # Try to recover or default
            # Most commodities have 09:00-10:15, 10:30-11:30, 13:30-15:00
            # But let's check existing trading_hours text to be safe
            pass # Assuming day_hours is mostly correct from previous script
        
        # Ensure time format HH:MM-HH:MM (pad with zeros)
        for field in ['day_hours', 'night_hours']:
            if field in contract:
                new_list = []
                changed = False
                for r in contract[field]:
                    s, e = r.split('-')
                    s_h, s_m = map(int, s.split(':'))
                    e_h, e_m = map(int, e.split(':'))
                    
                    # Fix 24:xx -> 24:00 if needed (though 24:00 is standard)
                    
                    formatted = f"{s_h:02d}:{s_m:02d}-{e_h:02d}:{e_m:02d}"
                    new_list.append(formatted)
                    if formatted != r:
                        changed = True
                
                if changed:
                    # report_lines.append(f"| {symbol} | {field} | {contract[field]} | {new_list} |")
                    contract[field] = new_list
        
        # 3. Fill empty fields if list is empty but should not be? 
        # (Already handled by patch for night_hours)
        
        contract['last_fixed'] = datetime.datetime.now().isoformat()

    save_json(DATA_FILE, data)
    
    with open(REPORT_FILE, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report_lines))
        
    print(f"Fix complete. {fixed_count} updates applied. Report saved to {REPORT_FILE}")

if __name__ == "__main__":
    fix_contracts()
