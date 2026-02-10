import json
import os
import sys
import pytest
from unittest.mock import patch, mock_open

# Add backend directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services import futures_master

# Mock data
MOCK_CONTRACTS_DATA = {
    "VISIBLE_1": {
        "name": "Visible Contract 1",
        "isHidden": False
    },
    "VISIBLE_2": {
        "name": "Visible Contract 2",
        # Missing isHidden implies False (default behavior check, though we enforced adding it)
        # But let's assume if missing it might show up or not? 
        # User requirement 2 says "add isHidden... default False for night... default True for day"
        # But here we are testing the loading logic. 
        # If the file has it missing, let's see what happens.
        # But our previous step added it to all.
        "isHidden": False
    },
    "HIDDEN_1": {
        "name": "Hidden Contract 1",
        "isHidden": True
    },
    "HIDDEN_2": {
        "name": "Hidden Contract 2",
        "isHidden": True
    }
}

@pytest.fixture
def mock_data_file(tmp_path):
    d = tmp_path / "data"
    d.mkdir()
    p = d / "futures_contracts.json"
    p.write_text(json.dumps(MOCK_CONTRACTS_DATA, ensure_ascii=False), encoding='utf-8')
    return str(p)

def test_load_contracts_filtering():
    # We need to patch DATA_PATH in futures_master or mock open
    # Since DATA_PATH is a module level variable, we can patch it?
    # Or just mock json.load and os.path.exists
    
    with patch("services.futures_master.DATA_PATH", "dummy_path"), \
         patch("os.path.exists", return_value=True), \
         patch("builtins.open", mock_open(read_data=json.dumps(MOCK_CONTRACTS_DATA))):
        
        # Reset cache first
        futures_master._contracts_cache = None
        
        contracts = futures_master.load_contracts()
        
        # Check that hidden contracts are NOT in the result
        assert "VISIBLE_1" in contracts
        assert "VISIBLE_2" in contracts
        assert "HIDDEN_1" not in contracts
        assert "HIDDEN_2" not in contracts
        
        # Check size
        assert len(contracts) == 2

def test_load_contracts_isHidden_none():
    # Test case where isHidden might be None or missing (should default to show? or strict?)
    # User requirement: "isHidden为True的记录直接排除" -> implying if False or None/Missing it might show?
    # But let's stick to explicit True excludes.
    
    data_with_none = {
        "NONE_HIDDEN": {
            "name": "None Hidden",
            "isHidden": None
        },
        "MISSING_HIDDEN": {
            "name": "Missing Hidden"
        },
        "TRUE_HIDDEN": {
            "name": "True Hidden",
            "isHidden": True
        }
    }
    
    with patch("backend.services.futures_master.DATA_PATH", "dummy_path"), \
         patch("os.path.exists", return_value=True), \
         patch("builtins.open", mock_open(read_data=json.dumps(data_with_none))):
        
        futures_master._contracts_cache = None
        contracts = futures_master.load_contracts()
        
        assert "TRUE_HIDDEN" not in contracts
        assert "NONE_HIDDEN" in contracts # None != True
        assert "MISSING_HIDDEN" in contracts # Missing != True

