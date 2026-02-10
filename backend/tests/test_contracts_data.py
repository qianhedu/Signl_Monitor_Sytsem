import pytest
import json
import os
import re

# Path to the JSON file
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_FILE = os.path.join(BASE_DIR, 'data', 'futures_contracts.json')

@pytest.fixture(scope="module")
def contracts_data():
    if not os.path.exists(DATA_FILE):
        pytest.fail(f"Data file not found: {DATA_FILE}")
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def parse_minutes(t_str):
    """Convert HH:MM to minutes from midnight. Handles 24:00 as 1440."""
    if t_str == '24:00':
        return 24 * 60
    h, m = map(int, t_str.split(':'))
    return h * 60 + m

def test_contracts_schema(contracts_data):
    """Verify that all contracts have required fields."""
    required_fields = [
        'name', 'exchange', 'multiplier', 'min_tick', 
        'quote_unit', 'margin_rate', 'trading_hours', 
        'main_contract', 'day_hours', 'night_hours'
    ]
    
    for symbol, data in contracts_data.items():
        for field in required_fields:
            assert field in data, f"Contract {symbol} missing field {field}"
            
        assert isinstance(data['day_hours'], list), f"{symbol} day_hours must be a list"
        assert isinstance(data['night_hours'], list), f"{symbol} night_hours must be a list"

def test_trading_hours_format(contracts_data):
    """Verify time range format HH:MM-HH:MM."""
    pattern = re.compile(r'^\d{2}:\d{2}-\d{2}:\d{2}$')
    
    for symbol, data in contracts_data.items():
        all_hours = data['day_hours'] + data['night_hours']
        for time_range in all_hours:
            assert pattern.match(time_range), f"{symbol} Invalid time format: {time_range}"
            
            start, end = time_range.split('-')
            
            # Check hours and minutes validity
            sh, sm = map(int, start.split(':'))
            eh, em = map(int, end.split(':'))
            
            assert 0 <= sh <= 24, f"{symbol} Invalid start hour: {sh}"
            assert 0 <= sm < 60, f"{symbol} Invalid start minute: {sm}"
            assert 0 <= eh <= 24, f"{symbol} Invalid end hour: {eh}"
            assert 0 <= em < 60, f"{symbol} Invalid end minute: {em}"
            
            if sh == 24: assert sm == 0, f"{symbol} 24:xx is invalid, must be 24:00"
            if eh == 24: assert em == 0, f"{symbol} 24:xx is invalid, must be 24:00"

def test_trading_hours_logic(contracts_data):
    """Verify logical consistency: start <= end, no overlaps."""
    for symbol, data in contracts_data.items():
        day_ranges = []
        night_ranges = []
        
        # Parse ranges
        for r in data['day_hours']:
            s, e = r.split('-')
            day_ranges.append((parse_minutes(s), parse_minutes(e), r))
            
        for r in data['night_hours']:
            s, e = r.split('-')
            start_min = parse_minutes(s)
            end_min = parse_minutes(e)
            
            # With split logic, end should be >= start (e.g. 21:00-24:00 or 00:00-02:30)
            # If end < start, it means it wasn't split correctly
            assert end_min >= start_min, f"{symbol} Night range not split correctly: {r}"
            
            night_ranges.append((start_min, end_min, r))
            
        # Check overlaps within day/night lists independently first
        # Actually, check all together for simplicity, but day and night are distinct.
        # Usually we check day ranges for overlaps, and night ranges for overlaps.
        
        def check_overlaps(ranges, label):
            ranges.sort() # Sort by start time
            for i in range(len(ranges) - 1):
                r1_start, r1_end, r1_str = ranges[i]
                r2_start, r2_end, r2_str = ranges[i+1]
                
                # If r1 ends after r2 starts -> overlap
                assert r1_end <= r2_start, f"{symbol} {label} Overlap detected: {r1_str} and {r2_str}"

        check_overlaps(day_ranges, "Day")
        check_overlaps(night_ranges, "Night")
        
        # Verify that night hours don't overlap with day hours (though they are usually far apart)
        # But wait, 00:00-02:30 is "Night" but technically "Day" time on clock.
        # So we treat them as just time slots in a 24h cycle?
        # No, usually "Day Trading" is 9:00-15:00. "Night Trading" is 21:00-02:30.
        # They shouldn't overlap.
        
        all_ranges = day_ranges + night_ranges
        check_overlaps(all_ranges, "All")

def test_night_hours_split(contracts_data):
    """Specifically verify that known cross-day contracts are split."""
    # AU usually runs until 02:30
    if 'AU' in contracts_data:
        au_night = contracts_data['AU']['night_hours']
        # Should have at least 2 ranges if it covers 21:00 to 02:30
        # Or at least contain a range starting at 00:00
        has_post_midnight = any(r.startswith("00:00") for r in au_night)
        assert has_post_midnight, "AU night hours should contain a post-midnight segment (e.g. 00:00-02:30)"

def test_ss_night_hours(contracts_data):
    """Verify Stainless Steel (SS) has correct night hours."""
    assert 'SS' in contracts_data
    ss = contracts_data['SS']
    
    assert ss['night_end'] == "01:00", "SS night_end should be 01:00"
    assert len(ss['night_hours']) == 2, "SS should have 2 night segments (cross-day)"
    assert "21:00-24:00" in ss['night_hours']
    assert "00:00-01:00" in ss['night_hours']

def test_specific_missing_night_hours(contracts_data):
    """Verify other previously missing night hours."""
    # List of symbols that should have night hours
    should_have_night = ['EB', 'PG', 'SA', 'PF', 'FU', 'SN', 'LU', 'BC', 'BR', 'SM', 'SF', 'CY']
    
    for sym in should_have_night:
        if sym in contracts_data:
            assert contracts_data[sym]['night_hours'], f"{sym} should have night hours"
            assert contracts_data[sym]['night_end'], f"{sym} should have night_end"

def test_is_hidden_field(contracts_data):
    """Verify isHidden field logic."""
    for symbol, data in contracts_data.items():
        assert 'isHidden' in data, f"{symbol} missing isHidden field"
        assert isinstance(data['isHidden'], bool), f"{symbol} isHidden must be boolean"
        
        has_night = bool(data.get('night_hours'))
        
        # If has night hours -> isHidden = False
        # If no night hours -> isHidden = True
        if has_night:
            assert data['isHidden'] is False, f"{symbol} has night hours but isHidden is True"
        else:
            assert data['isHidden'] is True, f"{symbol} has no night hours but isHidden is False"

