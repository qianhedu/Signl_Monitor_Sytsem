import json
import os

# Path config
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_FILE = os.path.join(BASE_DIR, 'data', 'futures_contracts.json')
SUMMARY_FILE = os.path.join(BASE_DIR, 'data', 'hidden_contracts_summary.md')

def add_hidden_field():
    if not os.path.exists(DATA_FILE):
        print(f"Error: {DATA_FILE} not found.")
        return

    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    hidden_contracts = []
    updated_count = 0

    for symbol, contract in data.items():
        # Determine if it has night hours
        night_hours = contract.get('night_hours', [])
        
        # Logic:
        # If has night hours -> isHidden = false (Visible)
        # If no night hours -> isHidden = true (Hidden)
        has_night = bool(night_hours)
        is_hidden = not has_night
        
        contract['isHidden'] = is_hidden
        updated_count += 1
        
        if is_hidden:
            hidden_contracts.append(f"{symbol} ({contract.get('name', 'Unknown')})")

    # Save back
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        
    # Generate Summary
    summary_lines = [
        "# Hidden Contracts Summary (isHidden=true)",
        "",
        f"Total Hidden Contracts: {len(hidden_contracts)}",
        "",
        "| Symbol | Name |",
        "|---|---|"
    ]
    
    for item in hidden_contracts:
        symbol, name = item.split(' (')
        name = name.rstrip(')')
        summary_lines.append(f"| {symbol} | {name} |")
        
    with open(SUMMARY_FILE, 'w', encoding='utf-8') as f:
        f.write('\n'.join(summary_lines))

    print(f"Updated {updated_count} contracts. {len(hidden_contracts)} set to hidden. Summary saved to {SUMMARY_FILE}")

if __name__ == "__main__":
    add_hidden_field()
