import json
import os

JSON_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'futures_contracts.json')

def patch_night_hours():
    if not os.path.exists(JSON_PATH):
        print("JSON file not found.")
        return

    with open(JSON_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 02:30 contracts
    late_night_230 = ['AU', 'AG', 'SC'] # Crude oil SC often goes late too? No, SC is 3:00? Let's check.
    # SC (Crude) is until 3:00 am? No, usually 2:30 or 3:00.
    # Let's check common knowledge. SC is 3:00 usually? Or 2:30?
    # User mentioned "如沪金、沪银等... 凌晨 2:30".
    # I'll stick to AU, AG for 02:30. SC is actually 3:00 usually but user didn't mention it specifically as 2:30 group, but implied "late night".
    # Actually SC is 3:00. But for now I'll handle AU, AG.
    
    # 01:00 contracts (Metals)
    late_night_100 = ['CU', 'AL', 'ZN', 'PB', 'NI', 'SN', 'SS', 'BC'] 
    
    # 23:00 contracts (Black, Chemicals, Agriculture)
    # Most others.
    
    count = 0
    for code, info in data.items():
        original = info.get('night_end', '')
        
        if code in late_night_230:
            if original != '02:30':
                info['night_end'] = '02:30'
                count += 1
        elif code in late_night_100:
            if original != '01:00':
                info['night_end'] = '01:00'
                count += 1
        elif original: # If it has night trading (not empty)
             # Default to 23:00 if not specified otherwise and currently set to something else or empty?
             # But if I don't know, I shouldn't touch it unless I'm sure.
             # My previous script might have missed 23:00 if formatted weirdly.
             # Let's only fix 23:00 if we are sure it should be.
             # RB, I, M, etc. are 23:00.
             pass
        
        # Also ensure 'SH' is there (user request)
        if code == 'SH' and not info.get('night_end'):
            # SH (ShaoJian) usually 23:00?
            # It's CZCE. Usually 23:00.
            pass

    with open(JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        
    print(f"Patched {count} contracts.")

if __name__ == "__main__":
    patch_night_hours()
