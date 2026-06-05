import pytest
from core.multi_module_forcer import force_coordinated_changes

def test_force_coordinated_changes_with_equilibrium():
    """Test that coordinated changes are generated when equilibrium is detected."""
    equilibrium_data = {
        "equilibrium_detected": True,
        "modules": ["module_a", "module_b"],
        "strategy": "cooperative"
    }
    changes = force_coordinated_changes(equilibrium_data)
    assert changes is not None
    assert isinstance(changes, list)
    assert len(changes) > 0
    for change in changes:
        assert "module" in change
        assert "change_type" in change
        assert change["module"] in ["module_a", "module_b"]

def test_force_coordinated_changes_no_equilibrium():
    """Test that no changes are generated when equilibrium is not detected."""
    equilibrium_data = {
        "equilibrium_detected": False,
        "modules": ["module_a", "module_b"],
        "strategy": "cooperative"
    }
    changes = force_coordinated_changes(equilibrium_data)
    assert changes is None or changes == []

def test_force_coordinated_changes_empty_data():
    """Test that empty data returns no changes."""
    equilibrium_data = {}
    changes = force_coordinated_changes(equilibrium_data)
    assert changes is None or changes == []