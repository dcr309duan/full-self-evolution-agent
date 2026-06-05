import json
import random
from collections import defaultdict
from typing import List, Dict, Tuple, Optional, Set

class NashDetectorAndForcer:
    """
    A self-contained module for detecting Nash equilibria in a system of interacting modules
    and forcing coordinated multi-module changes to escape suboptimal equilibria.
    
    Uses only standard library: json, collections, random, typing.
    No external imports.
    """

    def __init__(self, num_modules: int = 5, random_seed: Optional[int] = None):
        """
        Initialize the detector/forcer with a given number of modules.
        
        Args:
            num_modules: Number of modules in the system (default 5)
            random_seed: Optional seed for reproducibility
        """
        if random_seed is not None:
            random.seed(random_seed)
        
        self.num_modules = num_modules
        # Dependency matrix: dependency[i][j] = strength of influence from module j to module i
        # Initialized with random values between 0.0 and 1.0
        self.dependency_matrix: List[List[float]] = [
            [random.random() for _ in range(num_modules)]
            for _ in range(num_modules)
        ]
        
        # Current scores for each module (simulating module interaction outcomes)
        self.module_scores: List[float] = [0.0 for _ in range(num_modules)]
        
        # History of scores for equilibrium detection
        self.score_history: List[List[float]] = []
        
        # Threshold for considering a change "improving"
        self.improvement_threshold: float = 0.01
        
        # Equilibrium detection parameters
        self.equilibrium_window: int = 5  # Number of recent iterations to check
        self.equilibrium_tolerance: float = 0.001  # Max score change to consider stable
        
        # Current equilibrium state
        self.in_equilibrium: bool = False
        self.equilibrium_iterations: int = 0

    def set_dependency_matrix(self, matrix: List[List[float]]) -> None:
        """
        Set a custom dependency matrix.
        
        Args:
            matrix: Square matrix where matrix[i][j] is influence from j to i
        """
        if len(matrix) != self.num_modules:
            raise ValueError(f"Matrix must have {self.num_modules} rows")
        for row in matrix:
            if len(row) != self.num_modules:
                raise ValueError(f"Each row must have {self.num_modules} elements")
        self.dependency_matrix = matrix

    def compute_module_score(self, module_idx: int) -> float:
        """
        Compute the score for a single module based on its dependencies.
        
        The score is a weighted sum of influences from all modules,
        with a small random perturbation to simulate stochastic interactions.
        
        Args:
            module_idx: Index of the module to score
            
        Returns:
            Computed score for the module
        """
        score = 0.0
        for j in range(self.num_modules):
            # Weighted contribution from module j to module i
            score += self.dependency_matrix[module_idx][j] * (self.module_scores[j] if j != module_idx else 1.0)
        
        # Add small random noise to simulate stochasticity
        score += random.uniform(-0.05, 0.05)
        
        return score

    def update_all_scores(self) -> List[float]:
        """
        Update scores for all modules based on current dependencies.
        
        Returns:
            Updated list of module scores
        """
        new_scores = []
        for i in range(self.num_modules):
            new_scores.append(self.compute_module_score(i))
        
        self.module_scores = new_scores
        self.score_history.append(new_scores.copy())
        
        # Keep history bounded
        if len(self.score_history) > 100:
            self.score_history.pop(0)
        
        return new_scores

    def check_equilibrium(self) -> bool:
        """
        Check if the system is in a Nash equilibrium.
        
        A Nash equilibrium exists when no single module can improve its score
        by changing its dependencies (within a small tolerance).
        
        Returns:
            True if system is in equilibrium, False otherwise
        """
        # First check if scores have stabilized
        if len(self.score_history) < self.equilibrium_window:
            return False
        
        recent_scores = self.score_history[-self.equilibrium_window:]
        
        # Check if scores are stable over the window
        for i in range(self.num_modules):
            scores_i = [s[i] for s in recent_scores]
            if max(scores_i) - min(scores_i) > self.equilibrium_tolerance:
                return False
        
        # Check if any single-module change improves the system
        for module_idx in range(self.num_modules):
            # Try a small perturbation to this module's dependencies
            original_deps = self.dependency_matrix[module_idx].copy()
            
            # Try increasing a random dependency
            dep_idx = random.randint(0, self.num_modules - 1)
            original_value = self.dependency_matrix[module_idx][dep_idx]
            self.dependency_matrix[module_idx][dep_idx] = min(1.0, original_value + 0.1)
            
            # Compute new score for this module
            new_score = self.compute_module_score(module_idx)
            
            # Restore original
            self.dependency_matrix[module_idx] = original_deps
            
            # If improvement found, not in equilibrium
            if new_score > self.module_scores[module_idx] + self.improvement_threshold:
                return False
        
        self.in_equilibrium = True
        self.equilibrium_iterations += 1
        return True

    def force_coordinated_change(self, num_modules_to_change: int = 3) -> Dict[str, any]:
        """
        Force a coordinated multi-module change to escape equilibrium.
        
        Generates simultaneous mutations across 2-4 modules.
        
        Args:
            num_modules_to_change: Number of modules to mutate (default 3, clamped to 2-4)
            
        Returns:
            Dictionary describing the forced change
        """
        # Clamp to valid range
        num_modules_to_change = max(2, min(4, num_modules_to_change))
        
        # Select random modules to change
        modules_to_change = random.sample(range(self.num_modules), num_modules_to_change)
        
        change_record = {
            "type": "coordinated_mutation",
            "modules_changed": modules_to_change,
            "mutations": []
        }
        
        for module_idx in modules_to_change:
            # Generate mutation for this module
            mutation_type = random.choice(["dependency_shift", "dependency_swap", "dependency_reset"])
            
            if mutation_type == "dependency_shift":
                # Shift all dependencies slightly
                shift_amount = random.uniform(-0.2, 0.2)
                original = self.dependency_matrix[module_idx].copy()
                for j in range(self.num_modules):
                    self.dependency_matrix[module_idx][j] = max(0.0, min(1.0, 
                        self.dependency_matrix[module_idx][j] + shift_amount))
                change_record["mutations"].append({
                    "module": module_idx,
                    "type": "shift",
                    "amount": shift_amount,
                    "original": original,
                    "new": self.dependency_matrix[module_idx].copy()
                })
                
            elif mutation_type == "dependency_swap":
                # Swap two dependencies
                j1, j2 = random.sample(range(self.num_modules), 2)
                original = self.dependency_matrix[module_idx].copy()
                self.dependency_matrix[module_idx][j1], self.dependency_matrix[module_idx][j2] = \
                    self.dependency_matrix[module_idx][j2], self.dependency_matrix[module_idx][j1]
                change_record["mutations"].append({
                    "module": module_idx,
                    "type": "swap",
                    "indices": (j1, j2),
                    "original": original,
                    "new": self.dependency_matrix[module_idx].copy()
                })
                
            else:  # dependency_reset
                # Reset a random subset of dependencies
                num_to_reset = random.randint(1, max(1, self.num_modules // 2))
                indices_to_reset = random.sample(range(self.num_modules), num_to_reset)
                original = self.dependency_matrix[module_idx].copy()
                for j in indices_to_reset:
                    self.dependency_matrix[module_idx][j] = random.random()
                change_record["mutations"].append({
                    "module": module_idx,
                    "type": "reset",
                    "indices_reset": indices_to_reset,
                    "original": original,
                    "new": self.dependency_matrix[module_idx].copy()
                })
        
        # Update scores after forced change
        self.update_all_scores()
        self.in_equilibrium = False
        
        return change_record

    def run_equilibrium_cycle(self, max_iterations: int = 100) -> Dict[str, any]:
        """
        Run a full equilibrium detection and forcing cycle.
        
        Continuously updates scores, checks for equilibrium, and forces
        coordinated changes when equilibrium is detected.
        
        Args:
            max_iterations: Maximum number of iterations to run
            
        Returns:
            Dictionary with cycle results
        """
        results = {
            "iterations": 0,
            "equilibria_detected": 0,
            "coordinated_changes_forced": 0,
            "final_scores": [],
            "history": []
        }
        
        for iteration in range(max_iterations):
            # Update scores
            scores = self.update_all_scores()
            
            # Check for equilibrium
            if self.check_equilibrium():
                results["equilibria_detected"] += 1
                
                # Force coordinated change
                num_to_change = random.randint(2, 4)
                change = self.force_coordinated_change(num_to_change)
                results["coordinated_changes_forced"] += 1
                results["history"].append({
                    "iteration": iteration,
                    "type": "coordinated_change",
                    "details": change
                })
            
            results["iterations"] = iteration + 1
        
        results["final_scores"] = self.module_scores.copy()
        return results

    def to_json(self) -> str:
        """
        Serialize the current state to JSON.
        
        Returns:
            JSON string representation
        """
        state = {
            "num_modules": self.num_modules,
            "dependency_matrix": self.dependency_matrix,
            "module_scores": self.module_scores,
            "in_equilibrium": self.in_equilibrium,
            "equilibrium_iterations": self.equilibrium_iterations
        }
        return json.dumps(state, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> 'NashDetectorAndForcer':
        """
        Deserialize from JSON string.
        
        Args:
            json_str: JSON string representation
            
        Returns:
            New NashDetectorAndForcer instance
        """
        state = json.loads(json_str)
        instance = cls(num_modules=state["num_modules"])
        instance.dependency_matrix = state["dependency_matrix"]
        instance.module_scores = state["module_scores"]
        instance.in_equilibrium = state["in_equilibrium"]
        instance.equilibrium_iterations = state["equilibrium_iterations"]
        return instance

    def get_system_summary(self) -> Dict[str, any]:
        """
        Get a summary of the current system state.
        
        Returns:
            Dictionary with system summary
        """
        return {
            "num_modules": self.num_modules,
            "average_score": sum(self.module_scores) / self.num_modules if self.num_modules > 0 else 0.0,
            "max_score": max(self.module_scores) if self.module_scores else 0.0,
            "min_score": min(self.module_scores) if self.module_scores else 0.0,
            "in_equilibrium": self.in_equilibrium,
            "equilibrium_iterations": self.equilibrium_iterations,
            "dependency_density": sum(
                sum(1 for val in row if val > 0.5) for row in self.dependency_matrix
            ) / (self.num_modules ** 2) if self.num_modules > 0 else 0.0
        }


# Example usage and test function
def run_example():
    """
    Run an example demonstrating the NashDetectorAndForcer.
    """
    print("Initializing NashDetectorAndForcer with 5 modules...")
    detector = NashDetectorAndForcer(num_modules=5, random_seed=42)
    
    print("\nInitial system summary:")
    print(json.dumps(detector.get_system_summary(), indent=2))
    
    print("\nRunning equilibrium cycle (20 iterations)...")
    results = detector.run_equilibrium_cycle(max_iterations=20)
    
    print(f"\nCycle results:")
    print(f"  Iterations: {results['iterations']}")
    print(f"  Equilibria detected: {results['equilibria_detected']}")
    print(f"  Coordinated changes forced: {results['coordinated_changes_forced']}")
    print(f"  Final scores: {results['final_scores']}")
    
    print("\nFinal system summary:")
    print(json.dumps(detector.get_system_summary(), indent=2))
    
    # Demonstrate serialization
    print("\nSerializing to JSON...")
    json_str = detector.to_json()
    print(f"JSON length: {len(json_str)} characters")
    
    # Demonstrate deserialization
    print("\nDeserializing from JSON...")
    restored = NashDetectorAndForcer.from_json(json_str)
    print(f"Restored system summary:")
    print(json.dumps(restored.get_system_summary(), indent=2))
    
    return detector


if __name__ == "__main__":
    run_example()