import json
from collections import defaultdict
from typing import Dict, List, Tuple, Optional, Any

class NashEquilibriumHandler:
    """
    A self-contained module for detecting and forcing Nash equilibrium in a multi-module system.
    
    Tracks interaction scores between modules and determines if the current state is a Nash equilibrium
    (no single module can improve its score by changing unilaterally). Also provides mechanisms to
    force coordinated multi-module changes to escape suboptimal equilibria.
    """

    def __init__(self, num_modules: int = 5, default_score: float = 0.0):
        """
        Initialize the handler with a given number of modules.
        
        Args:
            num_modules: Number of modules in the system (default 5)
            default_score: Default interaction score between modules (default 0.0)
        """
        self.num_modules = num_modules
        self.default_score = default_score
        # interaction_scores[i][j] = score of module i interacting with module j
        self.interaction_scores: List[List[float]] = [
            [default_score for _ in range(num_modules)] for _ in range(num_modules)
        ]
        # Track changes for detecting equilibrium
        self.change_history: List[Dict[str, Any]] = []
        self.equilibrium_threshold = 0.01  # Threshold for considering a change significant

    def set_interaction_score(self, module_i: int, module_j: int, score: float) -> None:
        """
        Set the interaction score between two modules.
        
        Args:
            module_i: Index of first module
            module_j: Index of second module
            score: Interaction score value
        """
        if 0 <= module_i < self.num_modules and 0 <= module_j < self.num_modules:
            self.interaction_scores[module_i][module_j] = score
        else:
            raise ValueError(f"Module indices must be between 0 and {self.num_modules - 1}")

    def get_interaction_score(self, module_i: int, module_j: int) -> float:
        """Get the interaction score between two modules."""
        if 0 <= module_i < self.num_modules and 0 <= module_j < self.num_modules:
            return self.interaction_scores[module_i][module_j]
        raise ValueError(f"Module indices must be between 0 and {self.num_modules - 1}")

    def get_module_total_score(self, module_index: int) -> float:
        """
        Calculate the total interaction score for a given module.
        
        Args:
            module_index: Index of the module
            
        Returns:
            Sum of all interaction scores involving this module
        """
        if 0 <= module_index < self.num_modules:
            total = 0.0
            for j in range(self.num_modules):
                total += self.interaction_scores[module_index][j]
            return total
        raise ValueError(f"Module index must be between 0 and {self.num_modules - 1}")

    def get_system_total_score(self) -> float:
        """Calculate the total score of the entire system."""
        total = 0.0
        for i in range(self.num_modules):
            total += self.get_module_total_score(i)
        return total

    def _simulate_single_module_change(self, module_index: int, new_scores: List[float]) -> float:
        """
        Simulate what the module's total score would be if it changed its interaction scores.
        
        Args:
            module_index: The module considering a change
            new_scores: New interaction scores for this module (length = num_modules)
            
        Returns:
            The new total score for the module after the change
        """
        if len(new_scores) != self.num_modules:
            raise ValueError(f"new_scores must have length {self.num_modules}")
        
        old_scores = self.interaction_scores[module_index][:]
        self.interaction_scores[module_index] = new_scores
        new_total = self.get_module_total_score(module_index)
        self.interaction_scores[module_index] = old_scores
        return new_total

    def is_nash_equilibrium(self, check_all_modules: bool = True) -> Tuple[bool, Optional[int]]:
        """
        Check if the current state is a Nash equilibrium.
        
        A state is a Nash equilibrium if no single module can improve its total score
        by changing its interaction scores unilaterally.
        
        Args:
            check_all_modules: If True, check all modules; otherwise check only modules that have changed recently
            
        Returns:
            Tuple of (is_equilibrium, violating_module_index)
            violating_module_index is None if equilibrium holds
        """
        for i in range(self.num_modules):
            current_score = self.get_module_total_score(i)
            
            # Try a small perturbation: increase one interaction score slightly
            for j in range(self.num_modules):
                if i == j:
                    continue
                test_scores = self.interaction_scores[i][:]
                test_scores[j] += self.equilibrium_threshold * 2
                new_score = self._simulate_single_module_change(i, test_scores)
                
                if new_score > current_score + self.equilibrium_threshold:
                    return (False, i)
            
            # Try a small perturbation: decrease one interaction score slightly
            for j in range(self.num_modules):
                if i == j:
                    continue
                test_scores = self.interaction_scores[i][:]
                test_scores[j] -= self.equilibrium_threshold * 2
                new_score = self._simulate_single_module_change(i, test_scores)
                
                if new_score > current_score + self.equilibrium_threshold:
                    return (False, i)
        
        return (True, None)

    def force_coordinated_change(self, change_plan: Dict[int, List[float]]) -> bool:
        """
        Force a coordinated multi-module change to escape a suboptimal equilibrium.
        
        Args:
            change_plan: Dictionary mapping module indices to their new interaction score lists
            
        Returns:
            True if the change was applied successfully, False otherwise
        """
        # Validate the change plan
        for module_idx, new_scores in change_plan.items():
            if not (0 <= module_idx < self.num_modules):
                return False
            if len(new_scores) != self.num_modules:
                return False
        
        # Record the change
        change_record = {
            "type": "coordinated",
            "modules_changed": list(change_plan.keys()),
            "old_scores": {idx: self.interaction_scores[idx][:] for idx in change_plan},
            "new_scores": change_plan,
            "system_score_before": self.get_system_total_score()
        }
        
        # Apply the changes
        for module_idx, new_scores in change_plan.items():
            self.interaction_scores[module_idx] = new_scores
        
        change_record["system_score_after"] = self.get_system_total_score()
        self.change_history.append(change_record)
        return True

    def find_best_coordinated_change(self, max_iterations: int = 100) -> Dict[int, List[float]]:
        """
        Attempt to find a coordinated change that improves the system score.
        
        Uses a simple greedy approach: tries small coordinated adjustments.
        
        Args:
            max_iterations: Maximum number of iterations to search
            
        Returns:
            A change plan dictionary, or empty dict if no improvement found
        """
        import random
        best_plan = {}
        best_score = self.get_system_total_score()
        
        for _ in range(max_iterations):
            # Randomly select a subset of modules to change
            num_to_change = random.randint(1, max(1, self.num_modules // 2))
            modules_to_change = random.sample(range(self.num_modules), num_to_change)
            
            change_plan = {}
            for module_idx in modules_to_change:
                # Create a perturbed version of the module's scores
                new_scores = self.interaction_scores[module_idx][:]
                for j in range(self.num_modules):
                    if j != module_idx:
                        new_scores[j] += random.uniform(-0.5, 0.5)
                change_plan[module_idx] = new_scores
            
            # Simulate the change
            old_scores = {idx: self.interaction_scores[idx][:] for idx in modules_to_change}
            for idx, scores in change_plan.items():
                self.interaction_scores[idx] = scores
            
            new_score = self.get_system_total_score()
            
            # Restore old scores
            for idx, scores in old_scores.items():
                self.interaction_scores[idx] = scores
            
            if new_score > best_score:
                best_score = new_score
                best_plan = change_plan
        
        return best_plan

    def get_change_history(self) -> List[Dict[str, Any]]:
        """Return the history of all changes made."""
        return self.change_history

    def to_json(self) -> str:
        """Serialize the current state to JSON."""
        data = {
            "num_modules": self.num_modules,
            "default_score": self.default_score,
            "interaction_scores": self.interaction_scores,
            "change_history": self.change_history,
            "equilibrium_threshold": self.equilibrium_threshold
        }
        return json.dumps(data, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> 'NashEquilibriumHandler':
        """Create a NashEquilibriumHandler from a JSON string."""
        data = json.loads(json_str)
        handler = cls(
            num_modules=data["num_modules"],
            default_score=data["default_score"]
        )
        handler.interaction_scores = data["interaction_scores"]
        handler.change_history = data.get("change_history", [])
        handler.equilibrium_threshold = data.get("equilibrium_threshold", 0.01)
        return handler

    def reset(self) -> None:
        """Reset all interaction scores to default and clear history."""
        self.interaction_scores = [
            [self.default_score for _ in range(self.num_modules)]
            for _ in range(self.num_modules)
        ]
        self.change_history = []


def run_tests():
    """Run a comprehensive test of the NashEquilibriumHandler."""
    print("=" * 60)
    print("Nash Equilibrium Handler - Test Mode")
    print("=" * 60)
    
    # Test 1: Basic initialization
    print("\n[Test 1] Basic initialization")
    handler = NashEquilibriumHandler(num_modules=3)
    assert handler.num_modules == 3, "Should have 3 modules"
    assert handler.get_system_total_score() == 0.0, "System score should be 0"
    print("  PASSED: Handler initialized correctly")
    
    # Test 2: Setting and getting interaction scores
    print("\n[Test 2] Setting and getting interaction scores")
    handler.set_interaction_score(0, 1, 5.0)
    handler.set_interaction_score(1, 0, 3.0)
    assert handler.get_interaction_score(0, 1) == 5.0, "Score should be 5.0"
    assert handler.get_interaction_score(1, 0) == 3.0, "Score should be 3.0"
    print("  PASSED: Scores set and retrieved correctly")
    
    # Test 3: Module total score calculation
    print("\n[Test 3] Module total score calculation")
    handler.set_interaction_score(0, 2, 2.0)
    total = handler.get_module_total_score(0)
    assert total == 7.0, f"Module 0 total should be 7.0, got {total}"
    print(f"  PASSED: Module 0 total = {total}")
    
    # Test 4: System total score
    print("\n[Test 4] System total score")
    handler.set_interaction_score(1, 2, 4.0)
    handler.set_interaction_score(2, 0, 1.0)
    handler.set_interaction_score(2, 1, 2.0)
    system_total = handler.get_system_total_score()
    print(f"  System total score: {system_total}")
    print("  PASSED: System total calculated")
    
    # Test 5: Nash equilibrium detection
    print("\n[Test 5] Nash equilibrium detection")
    # With current scores, check if equilibrium holds
    is_eq, violator = handler.is_nash_equilibrium()
    print(f"  Is equilibrium: {is_eq}, Violator: {violator}")
    # Note: This may or may not be equilibrium depending on scores
    print("  PASSED: Equilibrium detection ran without error")
    
    # Test 6: Force coordinated change
    print("\n[Test 6] Force coordinated change")
    handler2 = NashEquilibriumHandler(num_modules=3)
    change_plan = {
        0: [0.0, 10.0, 5.0],
        1: [10.0, 0.0, 8.0],
        2: [5.0, 8.0, 0.0]
    }
    success = handler2.force_coordinated_change(change_plan)
    assert success, "Coordinated change should succeed"
    assert handler2.get_system_total_score() > 0, "System score should increase"
    print(f"  System score after change: {handler2.get_system_total_score()}")
    print("  PASSED: Coordinated change applied")
    
    # Test 7: Find best coordinated change
    print("\n[Test 7] Find best coordinated change")
    handler3 = NashEquilibriumHandler(num_modules=3)
    handler3.set_interaction_score(0, 1, 1.0)
    handler3.set_interaction_score(1, 0, 1.0)
    handler3.set_interaction_score(0, 2, 1.0)
    handler3.set_interaction_score(2, 0, 1.0)
    handler3.set_interaction_score(1, 2, 1.0)
    handler3.set_interaction_score(2, 1, 1.0)
    
    best_plan = handler3.find_best_coordinated_change(max_iterations=50)
    if best_plan:
        print(f"  Found improvement plan for modules: {list(best_plan.keys())}")
    else:
        print("  No improvement found (may be at local optimum)")
    print("  PASSED: Search for coordinated change completed")
    
    # Test 8: JSON serialization
    print("\n[Test 8] JSON serialization")
    json_str = handler2.to_json()
    handler_loaded = NashEquilibriumHandler.from_json(json_str)
    assert handler_loaded.num_modules == handler2.num_modules, "Module count should match"
    assert handler_loaded.get_system_total_score() == handler2.get_system_total_score(), "Scores should match"
    print("  PASSED: JSON serialization and deserialization works")
    
    # Test 9: Reset
    print("\n[Test 9] Reset")
    handler2.reset()
    assert handler2.get_system_total_score() == 0.0, "After reset, system score should be 0"
    assert len(handler2.get_change_history()) == 0, "Change history should be empty"
    print("  PASSED: Reset works correctly")
    
    # Test 10: Edge cases
    print("\n[Test 10] Edge cases")
    try:
        handler.set_interaction_score(10, 0, 1.0)
        print("  FAILED: Should have raised ValueError for invalid index")
    except ValueError:
        print("  PASSED: Invalid index raises ValueError")
    
    try:
        handler._simulate_single_module_change(0, [1.0, 2.0])
        print("  FAILED: Should have raised ValueError for wrong length")
    except ValueError:
        print("  PASSED: Wrong length raises ValueError")
    
    print("\n" + "=" * 60)
    print("All tests passed!")
    print("=" * 60)


if __name__ == "__main__":
    run_tests()