import json
import os
import sys
from collections import deque
from typing import Dict, List, Optional, Any

class NashEquilibriumDetector:
    """
    Self-contained Nash equilibrium detector.
    Reads module interaction data from 'nash_state.json'.
    Checks each module for unilateral improvement potential.
    If no module can improve alone, declares Nash equilibrium.
    Logs detected equilibria to 'nash_log.json'.
    """

    def __init__(self, module_names: Optional[List[str]] = None):
        """
        Initialize the detector with module names.
        
        Args:
            module_names: List of module names to track (optional, loaded from file if not provided)
        """
        self.module_names = module_names or []
        self.interaction_matrix = {}  # module_name -> {other_module: payoff}
        self.payoffs = {}  # module_name -> current payoff
        self.equilibrium_detected = False
        self.equilibrium_log = []
        
        # Load state if file exists
        if os.path.exists('nash_state.json'):
            self.load_state('nash_state.json')

    def load_state(self, filepath: str = 'nash_state.json') -> None:
        """
        Load interaction matrix from JSON file.
        
        Args:
            filepath: Path to the JSON file
        """
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            # Load module names if not provided
            if not self.module_names and 'module_names' in data:
                self.module_names = data['module_names']
            
            # Load interaction matrix
            if 'interaction_matrix' in data:
                self.interaction_matrix = data['interaction_matrix']
            
            # Load current payoffs
            if 'payoffs' in data:
                self.payoffs = data['payoffs']
            
            # Load equilibrium log
            if 'equilibrium_log' in data:
                self.equilibrium_log = data['equilibrium_log']
            
            # Load equilibrium state
            if 'equilibrium_detected' in data:
                self.equilibrium_detected = data['equilibrium_detected']
                
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Warning: Could not load state from {filepath}: {e}")

    def save_state(self, filepath: str = 'nash_state.json') -> None:
        """
        Save current state to JSON file.
        
        Args:
            filepath: Path to save the JSON file
        """
        state = {
            'module_names': self.module_names,
            'interaction_matrix': self.interaction_matrix,
            'payoffs': self.payoffs,
            'equilibrium_detected': self.equilibrium_detected,
            'equilibrium_log': self.equilibrium_log
        }
        
        with open(filepath, 'w') as f:
            json.dump(state, f, indent=2)

    def log_equilibrium(self, message: str) -> None:
        """
        Log an equilibrium detection event.
        
        Args:
            message: Description of the equilibrium event
        """
        log_entry = {
            'message': message,
            'modules': list(self.module_names),
            'payoffs': dict(self.payoffs)
        }
        self.equilibrium_log.append(log_entry)
        
        # Save log to file
        with open('nash_log.json', 'w') as f:
            json.dump(self.equilibrium_log, f, indent=2)

    def set_interaction_matrix(self, matrix: Dict[str, Dict[str, float]]) -> None:
        """
        Set the interaction matrix for modules.
        
        Args:
            matrix: Dictionary mapping module names to dictionaries of {other_module: payoff}
        """
        self.interaction_matrix = matrix
        self.module_names = list(matrix.keys())
        
        # Initialize payoffs if not set
        for module in self.module_names:
            if module not in self.payoffs:
                self.payoffs[module] = 0.0

    def set_payoffs(self, payoffs: Dict[str, float]) -> None:
        """
        Set current payoffs for modules.
        
        Args:
            payoffs: Dictionary mapping module names to payoff values
        """
        self.payoffs = payoffs

    def check_unilateral_improvement(self, module_name: str) -> bool:
        """
        Check if a module can improve its payoff by changing its strategy alone.
        
        Args:
            module_name: Name of the module to check
            
        Returns:
            True if the module can improve unilaterally, False otherwise
        """
        if module_name not in self.interaction_matrix:
            return False
        
        current_payoff = self.payoffs.get(module_name, 0.0)
        
        # Check all possible alternative strategies (other modules' current strategies)
        for other_module, payoff in self.interaction_matrix[module_name].items():
            if other_module != module_name and payoff > current_payoff:
                return True
        
        return False

    def detect_equilibrium(self, module_metrics: Optional[Dict[str, Dict[str, Any]]] = None) -> bool:
        """
        Detect if the system is at Nash equilibrium.
        
        Args:
            module_metrics: Optional dictionary of module metrics (not used in this implementation)
            
        Returns:
            True if equilibrium is detected, False otherwise
        """
        if not self.module_names:
            print("Warning: No modules to check for equilibrium")
            return False
        
        # Check each module for unilateral improvement potential
        all_stable = True
        for module_name in self.module_names:
            if self.check_unilateral_improvement(module_name):
                all_stable = False
                break
        
        self.equilibrium_detected = all_stable
        
        if self.equilibrium_detected:
            self.log_equilibrium("Nash equilibrium detected - no module can improve unilaterally")
        else:
            # Log that equilibrium was not detected
            pass
        
        return self.equilibrium_detected

    def get_equilibrium_modules(self) -> List[str]:
        """
        Get the list of modules that are at equilibrium.
        
        Returns:
            List of module names that are at equilibrium
        """
        if self.equilibrium_detected:
            return list(self.module_names)
        return []

    def get_equilibrium_state(self) -> Dict[str, Any]:
        """
        Get the current equilibrium state information.
        
        Returns:
            Dictionary containing equilibrium state information
        """
        return {
            'equilibrium': self.equilibrium_detected,
            'modules_at_equilibrium': self.get_equilibrium_modules(),
            'payoffs': dict(self.payoffs),
            'interaction_matrix': dict(self.interaction_matrix)
        }

    def reset(self) -> None:
        """Reset all tracking data."""
        self.interaction_matrix = {}
        self.payoffs = {}
        self.equilibrium_detected = False
        self.equilibrium_log = []

    def add_module(self, module_name: str, interactions: Dict[str, float], payoff: float = 0.0) -> None:
        """
        Add a module to the detector.
        
        Args:
            module_name: Name of the module
            interactions: Dictionary of {other_module: payoff} for interactions
            payoff: Current payoff for this module
        """
        if module_name not in self.module_names:
            self.module_names.append(module_name)
        
        self.interaction_matrix[module_name] = interactions
        self.payoffs[module_name] = payoff

    def remove_module(self, module_name: str) -> None:
        """
        Remove a module from the detector.
        
        Args:
            module_name: Name of the module to remove
        """
        if module_name in self.module_names:
            self.module_names.remove(module_name)
        
        if module_name in self.interaction_matrix:
            del self.interaction_matrix[module_name]
        
        if module_name in self.payoffs:
            del self.payoffs[module_name]
        
        # Remove from other modules' interaction matrices
        for other_module in self.interaction_matrix:
            if module_name in self.interaction_matrix[other_module]:
                del self.interaction_matrix[other_module][module_name]


def run_test_mode() -> None:
    """Simple test mode that can run standalone."""
    print("Running NashEquilibriumDetector in test mode...")
    
    # Create detector with test modules
    detector = NashEquilibriumDetector()
    
    # Test 1: Load from file (if exists) or create test data
    print("\nTest 1: Load/create test data")
    if not os.path.exists('nash_state.json'):
        # Create test interaction matrix
        test_matrix = {
            "module_a": {"module_a": 0.8, "module_b": 0.6, "module_c": 0.7},
            "module_b": {"module_a": 0.5, "module_b": 0.9, "module_c": 0.4},
            "module_c": {"module_a": 0.3, "module_b": 0.2, "module_c": 0.85}
        }
        test_payoffs = {
            "module_a": 0.8,
            "module_b": 0.9,
            "module_c": 0.85
        }
        
        # Save test data
        test_data = {
            'module_names': ["module_a", "module_b", "module_c"],
            'interaction_matrix': test_matrix,
            'payoffs': test_payoffs,
            'equilibrium_detected': False,
            'equilibrium_log': []
        }
        
        with open('nash_state.json', 'w') as f:
            json.dump(test_data, f, indent=2)
        
        print("  Created test data file 'nash_state.json'")
    
    # Load the state
    detector.load_state('nash_state.json')
    print(f"  Loaded {len(detector.module_names)} modules")
    print(f"  Module names: {detector.module_names}")
    print("  PASSED")
    
    # Test 2: Check equilibrium with current payoffs
    print("\nTest 2: Check equilibrium with current payoffs")
    is_eq = detector.detect_equilibrium()
    modules_eq = detector.get_equilibrium_modules()
    print(f"  Equilibrium: {is_eq}")
    print(f"  Modules at equilibrium: {modules_eq}")
    
    # With current payoffs (0.8, 0.9, 0.85), check if any module can improve
    # module_a: current=0.8, can get 0.6 from module_b or 0.7 from module_c -> no improvement
    # module_b: current=0.9, can get 0.5 from module_a or 0.4 from module_c -> no improvement
    # module_c: current=0.85, can get 0.3 from module_a or 0.2 from module_b -> no improvement
    # So this should be an equilibrium
    assert is_eq, "With current payoffs, this should be an equilibrium"
    print("  PASSED")
    
    # Test 3: Modify payoffs to break equilibrium
    print("\nTest 3: Modify payoffs to break equilibrium")
    detector.set_payoffs({
        "module_a": 0.5,  # Can improve to 0.8 by staying with itself
        "module_b": 0.9,
        "module_c": 0.85
    })
    is_eq = detector.detect_equilibrium()
    modules_eq = detector.get_equilibrium_modules()
    print(f"  Equilibrium: {is_eq}")
    print(f"  Modules at equilibrium: {modules_eq}")
    assert not is_eq, "With modified payoffs, this should NOT be an equilibrium"
    print("  PASSED")
    
    # Test 4: Restore equilibrium and verify logging
    print("\nTest 4: Restore equilibrium and verify logging")
    detector.set_payoffs({
        "module_a": 0.8,
        "module_b": 0.9,
        "module_c": 0.85
    })
    is_eq = detector.detect_equilibrium()
    print(f"  Equilibrium: {is_eq}")
    assert is_eq, "Should be back to equilibrium"
    
    # Check that log file was created
    if os.path.exists('nash_log.json'):
        with open('nash_log.json', 'r') as f:
            log_data = json.load(f)
        print(f"  Log entries: {len(log_data)}")
        assert len(log_data) > 0, "Should have at least one log entry"
        print("  PASSED")
    else:
        print("  FAILED: nash_log.json not created")
    
    # Test 5: Add a new module
    print("\nTest 5: Add a new module")
    detector.add_module(
        "module_d",
        {"module_a": 0.9, "module_b": 0.7, "module_c": 0.6, "module_d": 0.5},
        0.5
    )
    print(f"  Module names: {detector.module_names}")
    assert "module_d" in detector.module_names, "module_d should be added"
    print("  PASSED")
    
    # Test 6: Remove a module
    print("\nTest 6: Remove a module")
    detector.remove_module("module_d")
    print(f"  Module names: {detector.module_names}")
    assert "module_d" not in detector.module_names, "module_d should be removed"
    print("  PASSED")
    
    # Test 7: Reset and verify
    print("\nTest 7: Reset")
    detector.reset()
    is_eq = detector.detect_equilibrium()
    modules_eq = detector.get_equilibrium_modules()
    print(f"  Equilibrium: {is_eq}")
    print(f"  Modules at equilibrium: {modules_eq}")
    assert not is_eq, "After reset should not be in equilibrium"
    assert len(detector.module_names) == 0, "Module names should be empty after reset"
    print("  PASSED")
    
    # Test 8: Load from file after reset
    print("\nTest 8: Load from file after reset")
    detector.load_state('nash_state.json')
    print(f"  Module names: {detector.module_names}")
    assert len(detector.module_names) == 3, "Should have 3 modules after loading"
    print("  PASSED")
    
    # Test 9: Save state and verify
    print("\nTest 9: Save state and verify")
    detector.save_state('test_state.json')
    assert os.path.exists('test_state.json'), "test_state.json should exist"
    
    # Load the saved state
    with open('test_state.json', 'r') as f:
        saved_state = json.load(f)
    assert 'module_names' in saved_state, "Saved state should contain module_names"
    assert 'interaction_matrix' in saved_state, "Saved state should contain interaction_matrix"
    assert 'payoffs' in saved_state, "Saved state should contain payoffs"
    print("  PASSED")
    
    # Clean up test files
    if os.path.exists('test_state.json'):
        os.remove('test_state.json')
    if os.path.exists('nash_state.json'):
        os.remove('nash_state.json')
    if os.path.exists('nash_log.json'):
        os.remove('nash_log.json')
    
    print("\nAll tests passed!")


if __name__ == "__main__":
    run_test_mode()