import json
from collections import defaultdict, deque
from typing import List, Dict, Set, Tuple, Optional, Any

class NashEquilibriumDetector:
    """
    Minimal, self-contained Nash equilibrium detector.
    Tracks module interaction scores via a dict of dicts,
    detects equilibrium when no single module change improves score by >0.1,
    uses json for persistence, and includes a simple test harness.
    """

    def __init__(self, module_names: List[str]):
        """
        Initialize the detector with module names.
        
        Args:
            module_names: List of module names to track
        """
        if not module_names:
            raise ValueError("module_names list cannot be empty")
        
        self.module_names = list(module_names)
        
        # Module interaction scores: module_name -> {other_module: score}
        self.interaction_scores: Dict[str, Dict[str, float]] = {}
        
        # Current fitness scores for each module
        self.current_scores: Dict[str, float] = {}
        
        # Improvement threshold (0.1)
        self.improvement_threshold = 0.1
        
        # State machine for equilibrium tracking
        # States: 'normal', 'approaching', 'equilibrium'
        self.equilibrium_state = 'normal'
        
        # Counter for consecutive cycles without significant improvement
        self.cycles_without_improvement = 0
        
        # Number of consecutive non-improvement cycles required for equilibrium
        self.stagnation_threshold = 3
        
        # History of cycle outcomes: deque of booleans (True if any improvement > 0.1)
        self._cycle_improvement_history: deque = deque(maxlen=10)
        
        # Initialize interaction scores and current scores
        for module_name in self.module_names:
            self.current_scores[module_name] = 0.0
            self.interaction_scores[module_name] = {}
            for other_module in self.module_names:
                if other_module != module_name:
                    self.interaction_scores[module_name][other_module] = 0.0

    def update_interaction_score(self, module_a: str, module_b: str, score: float) -> None:
        """
        Update the interaction score between two modules.
        
        Args:
            module_a: First module name
            module_b: Second module name
            score: Interaction score value
        """
        if module_a in self.interaction_scores and module_b in self.interaction_scores[module_a]:
            self.interaction_scores[module_a][module_b] = score
        if module_b in self.interaction_scores and module_a in self.interaction_scores[module_b]:
            self.interaction_scores[module_b][module_a] = score

    def get_interaction_score(self, module_a: str, module_b: str) -> float:
        """
        Get the interaction score between two modules.
        
        Args:
            module_a: First module name
            module_b: Second module name
            
        Returns:
            Interaction score value
        """
        if module_a in self.interaction_scores and module_b in self.interaction_scores[module_a]:
            return self.interaction_scores[module_a][module_b]
        return 0.0

    def update_scores(self, module_scores: Dict[str, float]) -> None:
        """
        Update current scores for all modules.
        
        Args:
            module_scores: Dictionary mapping module names to their current scores
        """
        for module_name, score in module_scores.items():
            if module_name in self.current_scores:
                self.current_scores[module_name] = score

    def record_mutation_outcome(self, module_name: str, score_delta: float) -> None:
        """
        Record the outcome of a mutation affecting a module.
        
        Args:
            module_name: Name of the module
            score_delta: The change in score (positive = improvement)
        """
        if module_name in self.current_scores:
            self.current_scores[module_name] += score_delta

    def increment_cycle(self) -> None:
        """Advance to the next evaluation cycle and update state machine."""
        any_improvement = False
        
        for module_name in self.module_names:
            # Check if any single module change would improve score by > 0.1
            for other_module in self.module_names:
                if other_module != module_name:
                    interaction = self.get_interaction_score(module_name, other_module)
                    if interaction > self.improvement_threshold:
                        any_improvement = True
                        break
            if any_improvement:
                break
        
        self._cycle_improvement_history.append(any_improvement)
        
        if any_improvement:
            self.cycles_without_improvement = 0
            self.equilibrium_state = 'normal'
        else:
            self.cycles_without_improvement += 1
            if self.cycles_without_improvement >= self.stagnation_threshold:
                self.equilibrium_state = 'equilibrium'
            elif self.cycles_without_improvement >= 2:
                self.equilibrium_state = 'approaching'

    def detect_nash_equilibrium(self) -> bool:
        """
        Detect if the system is at Nash equilibrium.
        Returns True when no single module change improves score by > 0.1
        over the last 3 consecutive cycles.
        
        Returns:
            True if system is at Nash equilibrium, False otherwise
        """
        if len(self._cycle_improvement_history) < self.stagnation_threshold:
            return False
        
        recent_cycles = list(self._cycle_improvement_history)[-self.stagnation_threshold:]
        
        if any(recent_cycles):
            return False
        
        return self.equilibrium_state == 'equilibrium'

    def get_equilibrium_state(self) -> Dict[str, Any]:
        """
        Get the current equilibrium state information.
        
        Returns:
            Dictionary containing equilibrium state information
        """
        return {
            'equilibrium': self.detect_nash_equilibrium(),
            'state': self.equilibrium_state,
            'cycles_without_improvement': self.cycles_without_improvement,
            'module_scores': dict(self.current_scores),
            'interaction_scores': {k: dict(v) for k, v in self.interaction_scores.items()}
        }

    def save_state(self, filepath: str) -> None:
        """
        Save the current state to a JSON file.
        
        Args:
            filepath: Path to save the JSON file
        """
        state = {
            'module_names': self.module_names,
            'interaction_scores': {k: dict(v) for k, v in self.interaction_scores.items()},
            'current_scores': dict(self.current_scores),
            'equilibrium_state': self.equilibrium_state,
            'cycles_without_improvement': self.cycles_without_improvement,
            'stagnation_threshold': self.stagnation_threshold,
            'improvement_threshold': self.improvement_threshold,
            '_cycle_improvement_history': list(self._cycle_improvement_history)
        }
        
        with open(filepath, 'w') as f:
            json.dump(state, f, indent=2)

    def load_state(self, filepath: str) -> None:
        """
        Load state from a JSON file.
        
        Args:
            filepath: Path to load the JSON file from
        """
        with open(filepath, 'r') as f:
            state = json.load(f)
        
        self.module_names = state['module_names']
        self.interaction_scores = {k: dict(v) for k, v in state['interaction_scores'].items()}
        self.current_scores = dict(state['current_scores'])
        self.equilibrium_state = state['equilibrium_state']
        self.cycles_without_improvement = state['cycles_without_improvement']
        self.stagnation_threshold = state['stagnation_threshold']
        self.improvement_threshold = state['improvement_threshold']
        self._cycle_improvement_history = deque(state['_cycle_improvement_history'], maxlen=10)

    def reset(self) -> None:
        """Reset all tracking data."""
        self.interaction_scores.clear()
        self._cycle_improvement_history.clear()
        self.cycles_without_improvement = 0
        self.equilibrium_state = 'normal'
        
        for module_name in self.module_names:
            self.current_scores[module_name] = 0.0
            self.interaction_scores[module_name] = {}
            for other_module in self.module_names:
                if other_module != module_name:
                    self.interaction_scores[module_name][other_module] = 0.0

    def set_improvement_threshold(self, threshold: float) -> None:
        """
        Set the improvement threshold for detecting equilibrium.
        
        Args:
            threshold: Float representing the minimum improvement value (default 0.1)
        """
        if threshold < 0:
            raise ValueError("Improvement threshold must be non-negative")
        self.improvement_threshold = threshold

    def set_stagnation_threshold(self, threshold: int) -> None:
        """
        Set the number of consecutive non-improvement cycles required for equilibrium.
        
        Args:
            threshold: Number of cycles (must be positive)
        """
        if threshold < 1:
            raise ValueError("Stagnation threshold must be at least 1")
        self.stagnation_threshold = threshold


def run_test_mode():
    """Simple test mode that can run standalone."""
    print("Running NashEquilibriumDetector in test mode...")
    
    # Create detector with test modules
    detector = NashEquilibriumDetector(
        module_names=["module_a", "module_b", "module_c"]
    )
    
    # Test 1: Initial state
    print("\nTest 1: Initial state")
    print(f"  Equilibrium: {detector.detect_nash_equilibrium()}")
    print(f"  State: {detector.get_equilibrium_state()}")
    assert not detector.detect_nash_equilibrium(), "Initial state should not be in equilibrium"
    print("  PASSED")
    
    # Test 2: Record improvements (should not trigger equilibrium)
    print("\nTest 2: Record improvements (should not trigger equilibrium)")
    detector.update_interaction_score("module_a", "module_b", 0.5)  # 0.5 improvement
    detector.update_interaction_score("module_b", "module_c", 0.3)  # 0.3 improvement
    detector.update_interaction_score("module_c", "module_a", 0.4)  # 0.4 improvement
    detector.increment_cycle()
    
    print(f"  Equilibrium: {detector.detect_nash_equilibrium()}")
    print(f"  State: {detector.get_equilibrium_state()}")
    assert not detector.detect_nash_equilibrium(), "Improvements should prevent equilibrium"
    print("  PASSED")
    
    # Test 3: Record stagnation (small changes)
    print("\nTest 3: Record stagnation (small changes < 0.1)")
    for cycle in range(3):
        detector.update_interaction_score("module_a", "module_b", 0.01)  # 0.01 improvement
        detector.update_interaction_score("module_b", "module_c", 0.02)  # 0.02 improvement
        detector.update_interaction_score("module_c", "module_a", 0.015) # 0.015 improvement
        detector.increment_cycle()
    
    print(f"  Equilibrium: {detector.detect_nash_equilibrium()}")
    print(f"  State: {detector.get_equilibrium_state()}")
    assert detector.detect_nash_equilibrium(), "Stagnation should trigger equilibrium"
    print("  PASSED")
    
    # Test 4: JSON persistence
    print("\nTest 4: JSON persistence")
    detector.save_state("test_state.json")
    detector.reset()
    print(f"  After reset - Equilibrium: {detector.detect_nash_equilibrium()}")
    assert not detector.detect_nash_equilibrium(), "After reset should not be in equilibrium"
    
    detector.load_state("test_state.json")
    print(f"  After load - Equilibrium: {detector.detect_nash_equilibrium()}")
    assert detector.detect_nash_equilibrium(), "After load should be in equilibrium"
    print("  PASSED")
    
    # Test 5: Reset and verify
    print("\nTest 5: Reset")
    detector.reset()
    print(f"  Equilibrium: {detector.detect_nash_equilibrium()}")
    print(f"  State: {detector.get_equilibrium_state()}")
    assert not detector.detect_nash_equilibrium(), "After reset should not be in equilibrium"
    print("  PASSED")
    
    # Clean up test file
    import os
    if os.path.exists("test_state.json"):
        os.remove("test_state.json")
    
    print("\nAll tests passed!")


if __name__ == "__main__":
    run_test_mode()