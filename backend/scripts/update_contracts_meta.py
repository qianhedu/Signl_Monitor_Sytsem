import akshare as ak
import json
import os
import re
import datetime
import traceback
import math

# Path config
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_FILE = os.path.join(BASE_DIR, 'data', 'futures_contracts.json')
REPORT_FILE = os.path.join(BASE_DIR, 'data', 'update_report.md')

def load_json(path):
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def normalize_time_text(text):
    text = text.replace('～', '-').replace('－', '-').replace('至', '-').replace('~', '-').replace('—', '-')
    text = text.replace('：', ':')
    text = text.replace('次日', '').replace('Next Day', '') # Remove "Next Day" markers
    
    # Handle "Afternoon" 12h conversion
    def pm_repl(match):
        h = int(match.group(1))
        m = match.group(2)
        if h < 12:
            h += 12
        return f"{h}:{m}"
        
    text = re.sub(r'下午\s*(\d{1,2}):(\d{2})', pm_repl, text)
    return text

def parse_time_ranges(text):
    text = normalize_time_text(text)
    
    pattern = r'(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})'
    matches = re.findall(pattern, text)
    
    unique_ranges = set()
    for start, end in matches:
        sh, sm = map(int, start.split(':'))
        eh, em = map(int, end.split(':'))
        
        # Heuristic to fix End Time if it looks like 12h format mismatch
        if 8 <= sh <= 17:
            if eh < sh:
                 if eh < 12:
                     eh += 12
        
        # Split cross-day ranges (e.g. 21:00-02:30 -> 21:00-24:00, 00:00-02:30)
        # Check if it's a night range that crosses midnight
        is_cross_day = False
        if (sh >= 20 or sh < 6) and (eh < sh or (eh == sh and em < sm)): # Simple check for crossing midnight
             # Assuming standard night trading starts around 21:00 and ends next day early morning
             # But we need to be careful. 
             # If eh < sh, it definitely crosses midnight (e.g. 21:00 - 02:30)
             # unless it's an error. But for night hours this is expected.
             is_cross_day = True
        
        if is_cross_day:
            print(f"DEBUG: Splitting cross-day range {start}-{end}")
            unique_ranges.add(f"{sh:02d}:{sm:02d}-24:00")
            unique_ranges.add(f"00:00-{eh:02d}:{em:02d}")
        else:
            s_str = f"{sh:02d}:{sm:02d}"
            e_str = f"{eh:02d}:{em:02d}"
            unique_ranges.add(f"{s_str}-{e_str}")
        
    if "10:15-10:30" in unique_ranges:
        unique_ranges.remove("10:15-10:30")
        
    day_hours = []
    night_hours = []
    
    sorted_ranges = sorted(list(unique_ranges))
    
    for r in sorted_ranges:
        start_str = r.split('-')[0]
        h = int(start_str.split(':')[0])
        
        if 8 <= h < 18: 
            day_hours.append(r)
        elif 20 <= h <= 24 or 0 <= h < 6:
            night_hours.append(r)
            
    return day_hours, night_hours

def validate_hours(day_hours, night_hours):
    errors = []
    all_ranges = []
    
    def parse_minutes(t_str):
        h, m = map(int, t_str.split(':'))
        return h * 60 + m

    for h_list, label in [(day_hours, 'Day'), (night_hours, 'Night')]:
        for time_range in h_list:
            if not re.match(r'^\d{2}:\d{2}-\d{2}:\d{2}$', time_range):
                errors.append(f"{label} range format error: {time_range}")
                continue
            
            start_str, end_str = time_range.split('-')
            start_min = parse_minutes(start_str)
            end_min = parse_minutes(end_str)
            
            if end_min < start_min:
                end_min += 24 * 60
            
            all_ranges.append((start_min, end_min, time_range))

    all_ranges.sort()
    for i in range(len(all_ranges) - 1):
        r1 = all_ranges[i]
        r2 = all_ranges[i+1]
        
        if r1[1] > r2[0]:
            errors.append(f"Overlap detected: {r1[2]} and {r2[2]}")

    return errors

def extract_number(text):
    if isinstance(text, (int, float)):
        if math.isnan(text): return 0.0
        return float(text)
    if not isinstance(text, str):
        return 0.0
    match = re.search(r'(\d+(\.\d+)?)', text)
    return float(match.group(1)) if match else 0.0

def update_contracts():
    data = load_json(DATA_FILE)
    report_lines = ["# Futures Contracts Update Report", "", f"Update Time: {datetime.datetime.now()}", "", "| Symbol | Field | Old Value | New Value | Note |", "|---|---|---|---|---|"]
    
    updated_count = 0
    
    print(f"Loaded {len(data)} contracts.")
    
    for symbol, contract_data in data.items():
        main_contract = contract_data.get('main_contract', f"{symbol}0")
        print(f"Updating {symbol} ({main_contract})...")
        
        try:
            detail_df = ak.futures_contract_detail(symbol=main_contract)
            if detail_df is None or detail_df.empty:
                print(f"  No data found for {main_contract}")
                continue
                
            info = {}
            for _, row in detail_df.iterrows():
                info[row['item']] = row['value']
                
            raw_trading_hours = info.get('交易时间', '')
            day_hours, night_hours = parse_time_ranges(raw_trading_hours)
            
            new_night_end = ""
            if night_hours:
                def get_end_min(r):
                    s, e = r.split('-')
                    sh = int(s.split(':')[0])
                    eh = int(e.split(':')[0])
                    
                    # sm = sh*60 + int(s.split(':')[1])
                    em = eh*60 + int(e.split(':')[1])
                    
                    # Logic to determine if this range represents "late night" (next day)
                    # Standard night session: 21:00 - ...
                    # If a range starts/ends in early morning (e.g. 00:00-02:30), it is the latest part.
                    if sh < 12: # Arbitrary cutoff, assuming night session won't start at 10am
                        em += 24 * 60
                    
                    return em
                
                last_range = max(night_hours, key=get_end_min)
                new_night_end = last_range.split('-')[1]
            
            margin_raw = info.get('最低交易保证金', '0.1')
            margin_val = extract_number(margin_raw)
            if margin_val > 1:
                margin_val = margin_val / 100
            
            fields_to_update = {
                'name': info.get('交易品种'),
                'multiplier': extract_number(info.get('交易单位')),
                'min_tick': extract_number(info.get('最小变动价位')),
                'quote_unit': info.get('交易单位'),
                'margin_rate': margin_val,
                'trading_hours': raw_trading_hours,
                'night_end': new_night_end,
                'day_hours': day_hours,
                'night_hours': night_hours,
                'last_updated': datetime.datetime.now().isoformat(),
                'source_url': 'https://www.akshare.xyz/'
            }
            
            changes_found = False
            for k, v in fields_to_update.items():
                old_v = contract_data.get(k)
                
                if isinstance(v, float):
                    if isinstance(old_v, (float, int)) and abs(v - old_v) < 1e-6:
                        continue
                elif v == old_v:
                    continue
                
                if isinstance(v, list) and isinstance(old_v, list):
                    if sorted(v) == sorted(old_v):
                        continue

                contract_data[k] = v
                report_lines.append(f"| {symbol} | {k} | {old_v} | {v} | Updated from official source |")
                changes_found = True
            
            if changes_found:
                updated_count += 1
                
            val_errors = validate_hours(day_hours, night_hours)
            if val_errors:
                print(f"  Validation Errors for {symbol}: {val_errors}")
                report_lines.append(f"| {symbol} | VALIDATION | - | - | {'; '.join(val_errors)} |")

        except Exception as e:
            print(f"  Error updating {symbol}: {e}")
            traceback.print_exc()

    save_json(DATA_FILE, data)
    
    with open(REPORT_FILE, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report_lines))
        
    print(f"Update complete. {updated_count} contracts updated. Report saved to {REPORT_FILE}")

if __name__ == "__main__":
    update_contracts()
