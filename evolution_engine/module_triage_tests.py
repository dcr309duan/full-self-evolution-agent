"""Tests for the module triage system."""

import os
import sys
import tempfile
import shutil
import pytest
from evolution_engine.module_triage import ModuleTriage, Classification, FailureTracker, TriageReport

@pytest.fixture
def temp_module_dir():
    """Create a temporary directory with test modules."""
    tmpdir = tempfile.mkdtemp()
    original_dir = os.getcwd()
    os.chdir(tmpdir)
    
    # Create functional module
    os.makedirs("functional_module")
    with open("functional_module/__init__.py", "w") as f:
        f.write("def add(a, b):\n    return a + b\n")
    with open("functional_module/module.py", "w") as f:
        f.write("from . import add\n\nclass Calculator:\n    def __init__(self):\n        self.result = 0\n    def compute(self, x, y):\n        self.result = add(x, y)\n        return self.result\n")
    
    # Create broken module (syntax error)
    os.makedirs("broken_module")
    with open("broken_module/__init__.py", "w") as f:
        f.write("def broken_func():\n    return 1 +\n")
    with open("broken_module/module.py", "w") as f:
        f.write("from . import broken_func\n\nclass Broken:\n    def __init__(self):\n        self.value = broken_func()\n")
    
    # Create redundant module (duplicates functional_module)
    os.makedirs("redundant_module")
    with open("redundant_module/__init__.py", "w") as f:
        f.write("def add(a, b):\n    return a + b\n")
    with open("redundant_module/module.py", "w") as f:
        f.write("from . import add\n\nclass Calculator:\n    def __init__(self):\n        self.result = 0\n    def compute(self, x, y):\n        self.result = add(x, y)\n        return self.result\n")
    
    yield tmpdir
    
    os.chdir(original_dir)
    shutil.rmtree(tmpdir)

def test_classification_functional(temp_module_dir):
    """Verify functional module is classified correctly."""
    triage = ModuleTriage()
    classification = triage.classify_module("functional_module")
    assert classification == Classification.FUNCTIONAL

def test_classification_broken(temp_module_dir):
    """Verify broken module is classified correctly."""
    triage = ModuleTriage()
    classification = triage.classify_module("broken_module")
    assert classification == Classification.BROKEN

def test_classification_redundant(temp_module_dir):
    """Verify redundant module is classified correctly."""
    triage = ModuleTriage()
    classification = triage.classify_module("redundant_module")
    assert classification == Classification.REDUNDANT

def test_failure_tracking_increments(temp_module_dir):
    """Verify failure tracking increments properly."""
    tracker = FailureTracker()
    assert tracker.get_failure_count("broken_module") == 0
    
    tracker.record_failure("broken_module")
    assert tracker.get_failure_count("broken_module") == 1
    
    tracker.record_failure("broken_module")
    assert tracker.get_failure_count("broken_module") == 2

def test_pruning_after_three_failures(temp_module_dir):
    """Verify pruning only happens after 3 failures."""
    triage = ModuleTriage()
    
    # First failure - should not prune
    triage.record_failure("broken_module")
    assert os.path.exists("broken_module")
    
    # Second failure - should not prune
    triage.record_failure("broken_module")
    assert os.path.exists("broken_module")
    
    # Third failure - should prune
    triage.record_failure("broken_module")
    assert not os.path.exists("broken_module")

def test_report_log_generated(temp_module_dir):
    """Verify the report log is generated."""
    triage = ModuleTriage()
    triage.classify_module("functional_module")
    triage.classify_module("broken_module")
    triage.classify_module("redundant_module")
    
    report = triage.generate_report()
    assert report is not None
    assert isinstance(report, TriageReport)
    assert report.functional_count >= 1
    assert report.broken_count >= 1
    assert report.redundant_count >= 1

def test_full_triage_workflow(temp_module_dir):
    """Test the complete triage workflow end-to-end."""
    triage = ModuleTriage()
    
    # Classify all modules
    classifications = triage.classify_all_modules()
    
    assert "functional_module" in classifications
    assert "broken_module" in classifications
    assert "redundant_module" in classifications
    
    assert classifications["functional_module"] == Classification.FUNCTIONAL
    assert classifications["broken_module"] == Classification.BROKEN
    assert classifications["redundant_module"] == Classification.REDUNDANT
    
    # Verify failure tracking with multiple failures
    for _ in range(2):
        triage.record_failure("broken_module")
    
    assert triage.failure_tracker.get_failure_count("broken_module") == 2
    assert os.path.exists("broken_module")  # Should still exist
    
    # Third failure triggers pruning
    triage.record_failure("broken_module")
    assert not os.path.exists("broken_module")
    
    # Generate and verify report
    report = triage.generate_report()
    assert report.functional_count == 1
    assert report.broken_count == 1
    assert report.redundant_count == 1
    assert report.pruned_modules == ["broken_module"]