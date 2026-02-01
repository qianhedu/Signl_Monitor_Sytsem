import akshare as ak
import pandas as pd
import json
import os

def fetch_futures_metadata():
    print("Fetching futures metadata...")
    
    # Try different potential functions to get contract details
    # 1. Commission info often contains contract size (multiplier) and margin
    try:
        # This function often returns exchange, code, name, unit (multiplier), min_tick, etc.
        # Note: Function names in akshare change frequently.
        # Trying 'futures_comm_info' or similar.
        # Based on docs, it might be separate per exchange or a general one.
        
        # Let's try to get a list of all futures first.
        # There isn't a simple "all futures" list function often.
        # But we can try 'futures_display_main_sina' to get main contracts
        print("Fetching main contracts list...")
        main_contracts = ak.futures_display_main_sina()
        print(f"Found {len(main_contracts)} main contracts.")
        
        # Now let's try to find rule info (multiplier, etc.)
        # There is 'futures_rule_cn' in some versions, let's check if it exists.
        if hasattr(ak, 'futures_rule_cn'):
            print("Using futures_rule_cn...")
            rules = ak.futures_rule_cn()
            print(rules.head())
            return rules.to_dict('records')
        else:
            print("futures_rule_cn not found. Trying alternatives...")
            
            # Alternative: Construct from hardcoded or per-exchange info if available.
            # But wait, the user wants "Real contract attributes from official interface".
            # akshare.futures_contract_detail(symbol='...') might work.
            
            # Let's just dump what we can get for a sample symbol to see structure
            sample_symbol = 'RB2310' # Example
            try:
                # Use a known recent contract or main contract
                # RB0 is not valid for detail usually, needs specific contract
                detail = ak.futures_contract_detail(symbol='RB2410')
                print("Sample Detail for RB2410:")
                print(detail)
            except Exception as e:
                print(f"Error fetching sample detail: {e}")

            # Try to fetch commission info which often has unit/tick
            # futures_fees_info_df = ak.futures_fees_info() # This might exist
            pass
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    fetch_futures_metadata()
