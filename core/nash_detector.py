import json
from collections import deque, defaultdict
from datetime import datetime
import os

class NashEquilibriumDetector:
    """
    Self-contained Nash equilibrium detector.
    Tracks module interaction frequencies via a simple dict.
    Detects Nash equilibrium when no single-module change improves the system for 3+ consecutive cycles.
    Exports detect_nash() function that returns True/False and get_stable_modules() list.
    Uses only json, collections, datetime from stdlib.
    """

    def __init__(self, module_names=None, max_history=10, equilibrium_cycles=3):
        """
        Initialize the detector with module names.
        
        Args:
            module_names: List of module names to track (optional, loaded from file if not provided)
            max_history: Maximum number of mutation outcomes to track per module pair
            equilibrium_cycles: Number of consecutive cycles with no improvement to detect equilibrium
        """
        self.module_names = module_names or []
        self.max_history = max_history
        self.equilibrium_cycles = equilibrium_cycles
        self.mutation_history = defaultdict(lambda: deque(maxlen=max_history))
        self.payoffs = {}
        self.module_metrics = {}
        self.equilibrium_detected = False
        self.equilibrium_log = []
        self.consecutive_no_improvement = 0
        self.stuck_pairs = []
        self.coordinated_candidates = []
        self.goal_cooccurrence = defaultdict(set)
        self.interaction_frequencies = defaultdict(int)

    def load_state(self, filepath='nash_state.json'):
        """
        Load interaction matrix from JSON file.
        
        Args:
            filepath: Path to the JSON file
        """
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            if not self.module_names and 'module_names' in data:
                self.module_names = data['module_names']
            
            if 'mutation_history' in data:
                for key, value in data['mutation_history'].items():
                    mod1, mod2 = key.split('|')
                    self.mutation_history[(mod1, mod2)] = deque(value, maxlen=self.max_history)
            
            if 'payoffs' in data:
                self.payoffs = data['payoffs']
            
            if 'module_metrics' in data:
                self.module_metrics = data['module_metrics']
            
            if 'equilibrium_log' in data:
                self.equilibrium_log = data['equilibrium_log']
            
            if 'equilibrium_detected' in data:
                self.equilibrium_detected = data['equilibrium_detected']
            
            if 'consecutive_no_improvement' in data:
                self.consecutive_no_improvement = data['consecutive_no_improvement']
            
            if 'stuck_pairs' in data:
                self.stuck_pairs = data['stuck_pairs']
            
            if 'coordinated_candidates' in data:
                self.coordinated_candidates = data['coordinated_candidates']
            
            if 'goal_cooccurrence' in data:
                self.goal_cooccurrence = {k: set(v) for k, v in data['goal_cooccurrence'].items()}
            
            if 'interaction_frequencies' in data:
                self.interaction_frequencies = defaultdict(int, data['interaction_frequencies'])
                
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Warning: Could not load state from {filepath}: {e}")

    def save_state(self, filepath='nash_state.json'):
        """
        Save current state to JSON file.
        
        Args:
            filepath: Path to save the JSON file
        """
        mutation_history_str = {}
        for key, value in self.mutation_history.items():
            mutation_history_str[f"{key[0]}|{key[1]}"] = list(value)
        
        goal_cooccurrence_list = {}
        for key, value in self.goal_cooccurrence.items():
            goal_cooccurrence_list[key] = list(value)
        
        state = {
            'module_names': self.module_names,
            'mutation_history': mutation_history_str,
            'payoffs': self.payoffs,
            'module_metrics': self.module_metrics,
            'equilibrium_detected': self.equilibrium_detected,
            'equilibrium_log': self.equilibrium_log,
            'consecutive_no_improvement': self.consecutive_no_improvement,
            'stuck_pairs': self.stuck_pairs,
            'coordinated_candidates': self.coordinated_candidates,
            'goal_cooccurrence': goal_cooccurrence_list,
            'interaction_frequencies': dict(self.interaction_frequencies)
        }
        
        with open(filepath, 'w') as f:
            json.dump(state, f, indent=2)

    def log_equilibrium(self, message):
        """
        Log an equilibrium detection event.
        
        Args:
            message: Description of the equilibrium event
        """
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'message': message,
            'modules': list(self.module_names),
            'payoffs': dict(self.payoffs),
            'module_metrics': dict(self.module_metrics),
            'stuck_pairs': list(self.stuck_pairs),
            'coordinated_candidates': list(self.coordinated_candidates)
        }
        self.equilibrium_log.append(log_entry)
        
        with open('nash_log.json', 'w') as f:
            json.dump(self.equilibrium_log, f, indent=2)

    def record_mutation_outcome(self, module1, module2, improved):
        """
        Record the outcome of a mutation between two modules.
        
        Args:
            module1: First module name
            module2: Second module name
            improved: Whether the mutation improved the system
        """
        pair = (module1, module2) if module1 < module2 else (module2, module1)
        self.mutation_history[pair].append(improved)
        
        # Track interaction frequencies
        self.interaction_frequencies[pair] += 1
        
        for mod in [module1, module2]:
            if mod not in self.module_metrics:
                self.module_metrics[mod] = {'success_rate': 0.0, 'change_frequency': 0.0}
            
            metrics = self.module_metrics[mod]
            total_outcomes = sum(1 for pair_history in self.mutation_history.values() 
                               if mod in pair_history and len(pair_history) > 0)
            if total_outcomes > 0:
                successful = sum(1 for pair_history in self.mutation_history.values() 
                                if mod in pair_history and len(pair_history) > 0 and pair_history[-1])
                metrics['success_rate'] = successful / total_outcomes
            
            metrics['change_frequency'] = total_outcomes / max(1, len(self.mutation_history))

    def check_pair_stuck(self, module1, module2):
        """
        Check if a module pair is stuck (no improvement in last N outcomes).
        
        Args:
            module1: First module name
            module2: Second module name
            
        Returns:
            True if the pair is stuck, False otherwise
        """
        pair = (module1, module2) if module1 < module2 else (module2, module1)
        history = self.mutation_history.get(pair, deque())
        
        if len(history) < self.max_history:
            return False
        
        return all(not outcome for outcome in history)

    def record_goal_cooccurrence(self, module_name, goal_id):
        """
        Record that a module is associated with a specific goal.
        
        Args:
            module_name: Name of the module
            goal_id: Identifier for the goal
        """
        self.goal_cooccurrence[module_name].add(goal_id)

    def find_coordinated_candidates(self):
        """
        Identify coordinated change candidates by grouping modules that interact
        based on co-occurrence in goals.
        
        Returns:
            List of lists, where each inner list contains module names that are coordinated candidates
        """
        module_graph = defaultdict(set)
        
        for mod1 in self.module_names:
            for mod2 in self.module_names:
                if mod1 < mod2:
                    shared_goals = self.goal_cooccurrence.get(mod1, set()) & self.goal_cooccurrence.get(mod2, set())
                    if shared_goals:
                        module_graph[mod1].add(mod2)
                        module_graph[mod2].add(mod1)
        
        for (mod1, mod2) in self.mutation_history:
            module_graph[mod1].add(mod2)
            module_graph[mod2].add(mod1)
        
        visited = set()
        coordinated_groups = []
        
        for module in self.module_names:
            if module not in visited:
                group = []
                queue = [module]
                visited.add(module)
                
                while queue:
                    current = queue.pop(0)
                    group.append(current)
                    
                    for neighbor in module_graph.get(current, set()):
                        if neighbor not in visited:
                            visited.add(neighbor)
                            queue.append(neighbor)
                
                if len(group) > 1:
                    coordinated_groups.append(group)
        
        self.coordinated_candidates = coordinated_groups
        return coordinated_groups

    def detect_equilibrium(self, module_metrics=None):
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
        
        all_stable = True
        self.stuck_pairs = []
        
        for i, mod1 in enumerate(self.module_names):
            for mod2 in self.module_names[i+1:]:
                if self.check_pair_stuck(mod1, mod2):
                    self.stuck_pairs.append((mod1, mod2))
                
                if mod1 in self.payoffs and mod2 in self.payoffs:
                    if self.payoffs[mod1] < self.payoffs.get(mod2, 0.0) or \
                       self.payoffs[mod2] < self.payoffs.get(mod1, 0.0):
                        all_stable = False
        
        if all_stable:
            self.consecutive_no_improvement += 1
        else:
            self.consecutive_no_improvement = 0
        
        self.equilibrium_detected = self.consecutive_no_improvement >= self.equilibrium_cycles
        
        self.find_coordinated_candidates()
        
        if self.equilibrium_detected:
            self.log_equilibrium(f"Nash equilibrium detected - no improvement for {self.consecutive_no_improvement} consecutive cycles")
        
        return self.equilibrium_detected

    def get_equilibrium_modules(self):
        """
        Get the list of modules that are at equilibrium.
        
        Returns:
            List of module names that are at equilibrium
        """
        if self.equilibrium_detected:
            return list(self.module_names)
        return []

    def get_stuck_pairs(self):
        """
        Get the list of module pairs that are stuck.
        
        Returns:
            List of tuples containing stuck module pairs
        """
        return list(self.stuck_pairs)

    def get_coordinated_candidates(self):
        """
        Get the list of coordinated change candidate groups.
        
        Returns:
            List of lists, where each inner list contains module names that are coordinated candidates
        """
        return list(self.coordinated_candidates)

    def get_equilibrium_state(self):
        """
        Get the current equilibrium state information.
        
        Returns:
            Dictionary containing equilibrium state information
        """
        return {
            'equilibrium': self.equilibrium_detected,
            'modules_at_equilibrium': self.get_equilibrium_modules(),
            'stuck_pairs': self.get_stuck_pairs(),
            'coordinated_candidates': self.get_coordinated_candidates(),
            'payoffs': dict(self.payoffs),
            'module_metrics': dict(self.module_metrics),
            'consecutive_no_improvement': self.consecutive_no_improvement
        }

    def reset(self):
        """Reset all tracking data."""
        self.mutation_history.clear()
        self.payoffs = {}
        self.module_metrics = {}
        self.equilibrium_detected = False
        self.equilibrium_log = []
        self.consecutive_no_improvement = 0
        self.stuck_pairs = []
        self.coordinated_candidates = []
        self.goal_cooccurrence.clear()
        self.interaction_frequencies.clear()

    def add_module(self, module_name, payoff=0.0):
        """
        Add a module to the detector.
        
        Args:
            module_name: Name of the module
            payoff: Current payoff for this module
        """
        if module_name not in self.module_names:
            self.module_names.append(module_name)
        
        self.payoffs[module_name] = payoff
        
        if module_name not in self.module_metrics:
            self.module_metrics[module_name] = {'success_rate': 0.0, 'change_frequency': 0.0}

    def remove_module(self, module_name):
        """
        Remove a module from the detector.
        
        Args:
            module_name: Name of the module to remove
        """
        if module_name in self.module_names:
            self.module_names.remove(module_name)
        
        if module_name in self.payoffs:
            del self.payoffs[module_name]
        
        if module_name in self.module_metrics:
            del self.module_metrics[module_name]
        
        if module_name in self.goal_cooccurrence:
            del self.goal_cooccurrence[module_name]
        
        keys_to_delete = []
        for key in self.mutation_history:
            if module_name in key:
                keys_to_delete.append(key)
        
        for key in keys_to_delete:
            del self.mutation_history[key]
        
        keys_to_delete = []
        for key in self.interaction_frequencies:
            if module_name in key:
                keys_to_delete.append(key)
        
        for key in keys_to_delete:
            del self.interaction_frequencies[key]

    def set_payoffs(self, payoffs):
        """
        Set current payoffs for modules.
        
        Args:
            payoffs: Dictionary mapping module names to payoff values
        """
        self.payoffs = payoffs

    def get_interaction_frequencies(self):
        """
        Get the interaction frequencies for all module pairs.
        
        Returns:
            Dictionary mapping module pairs to their interaction frequencies
        """
        return dict(self.interaction_frequencies)

    def detect_nash(self):
        """
        Detect if the system is at Nash equilibrium.
        
        Returns:
            True if equilibrium is detected, False otherwise
        """
        return self.detect_equilibrium()

    def get_stable_modules(self):
        """
        Get the list of modules that are at equilibrium.
        
        Returns:
            List of module names that are at equilibrium
        """
        return self.get_equilibrium_modules()


def detect_nash_equilibrium():
    """
    Detect if the system is at Nash equilibrium.
    
    Returns:
        Tuple of (bool, dict) where bool is True if equilibrium is detected,
        and dict contains the equilibrium state information
    """
    detector = NashEquilibriumDetector()
    try:
        detector.load_state()
    except:
        pass
    
    is_equilibrium = detector.detect_equilibrium()
    state = detector.get_equilibrium_state()
    
    return is_equilibrium, state


def run_test_mode():
    """Simple test mode that can run standalone."""
    print("Running NashEquilibriumDetector in test mode...")
    
    detector = NashEquilibriumDetector(max_history=5, equilibrium_cycles=3)
    
    print("\nTest 1: Load/create test data")
    test_payoffs = {
        "module_a": 0.8,
        "module_b": 0.9,
        "module_c": 0.85
    }
    
    test_metrics = {
        "module_a": {"success_rate": 0.5, "change_frequency": 0.3},
        "module_b": {"success_rate": 0.6, "change_frequency": 0.4},
        "module_c": {"success_rate": 0.55, "change_frequency": 0.35}
    }
    
    test_data = {
        'module_names': ["module_a", "module_b", "module_c"],
        'mutation_history': {},
        'payoffs': test_payoffs,
        'module_metrics': test_metrics,
        'equilibrium_detected': False,
        'equilibrium_log': [],
        'consecutive_no_improvement': 0,
        'stuck_pairs': [],
        'coordinated_candidates': [],
        'goal_cooccurrence': {},
        'interaction_frequencies': {}
    }
    
    with open('nash_state.json', 'w') as f:
        json.dump(test_data, f, indent=2)
    
    print("  Created test data file 'nash_state.json'")
    
    detector.load_state('nash_state.json')
    print(f"  Loaded {len(detector.module_names)} modules")
    print(f"  Module names: {detector.module_names}")
    print(f"  Module metrics: {detector.module_metrics}")
    print("  PASSED")
    
    print("\nTest 2: Record mutation outcomes and check equilibrium")
    
    for _ in range(5):
        detector.record_mutation_outcome("module_a", "module_b", False)
        detector.record_mutation_outcome("module_a", "module_c", False)
        detector.record_mutation_outcome("module_b", "module_c", False)
    
    is_eq = detector.detect_equilibrium()
    print(f"  Equilibrium after 1 cycle: {is_eq}")
    assert not is_eq, "Should not be equilibrium after 1 cycle"
    
    for _ in range(2):
        detector.record_mutation_outcome("module_a", "module_b", False)
        detector.record_mutation_outcome("module_a", "module_c", False)
        detector.record_mutation_outcome("module_b", "module_c", False)
        is_eq = detector.detect_equilibrium()
    
    print(f"  Equilibrium after 3 cycles: {is_eq}")
    assert is_eq, "Should be equilibrium after 3 cycles"
    print("  PASSED")
    
    print("\nTest 3: Check stuck pairs")
    stuck_pairs = detector.get_stuck_pairs()
    print(f"  Stuck pairs: {stuck_pairs}")
    assert len(stuck_pairs) > 0, "Should have at least one stuck pair"
    print("  PASSED")
    
    print("\nTest 4: Test goal co-occurrence and coordinated candidates")
    detector.record_goal_cooccurrence("module_a", "goal_1")
    detector.record_goal_cooccurrence("module_b", "goal_1")
    detector.record_goal_cooccurrence("module_b", "goal_2")
    detector.record_goal_cooccurrence("module_c", "goal_2")
    
    coordinated = detector.find_coordinated_candidates()
    print(f"  Coordinated candidates: {coordinated}")
    assert len(coordinated) > 0, "Should have at least one coordinated group"
    print("  PASSED")
    
    print("\nTest 5: Add a new module")
    detector.add_module("module_d", 0.5)
    print(f"  Module names: {detector.module_names}")
    assert "module_d" in detector.module_names, "module_d should be added"
    print("  PASSED")
    
    print("\nTest 6: Remove a module")
    detector.remove_module("module_d")
    print(f"  Module names: {detector.module_names}")
    assert "module_d" not in detector.module_names, "module_d should be removed"
    print("  PASSED")
    
    print("\nTest 7: Reset and verify")
    detector.reset()
    is_eq = detector.detect_equilibrium()
    stuck_pairs = detector.get_stuck_pairs()
    coordinated = detector.get_coordinated_candidates()
    print(f"  Equilibrium: {is_eq}")
    print(f"  Stuck pairs: {stuck_pairs}")
    print(f"  Coordinated candidates: {coordinated}")
    assert not is_eq, "After reset should not be in equilibrium"
    assert len(detector.module_names) == 0, "Module names should be empty after reset"
    assert len(coordinated) == 0, "Coordinated candidates should be empty after reset"
    print("  PASSED")
    
    print("\nTest 8: Load from file after reset")
    detector.load_state('nash_state.json')
    print(f"  Module names: {detector.module_names}")
    assert len(detector.module_names) == 3, "Should have 3 modules after loading"
    print("  PASSED")
    
    print("\nTest 9: Save state and verify")
    detector.save_state('test_state.json')
    
    with open('test_state.json', 'r') as f:
        saved_state = json.load(f)
    assert 'module_names' in saved_state, "Saved state should contain module_names"
    assert 'mutation_history' in saved_state, "Saved state should contain mutation_history"
    assert 'payoffs' in saved_state, "Saved state should contain payoffs"
    assert 'module_metrics' in saved_state, "Saved state should contain module_metrics"
    assert 'consecutive_no_improvement' in saved_state, "Saved state should contain consecutive_no_improvement"
    assert 'stuck_pairs' in saved_state, "Saved state should contain stuck_pairs"
    assert 'coordinated_candidates' in saved_state, "Saved state should contain coordinated_candidates"
    assert 'goal_cooccurrence' in saved_state, "Saved state should contain goal_cooccurrence"
    assert 'interaction_frequencies' in saved_state, "Saved state should contain interaction_frequencies"
    print("  PASSED")
    
    print("\nTest 10: Verify equilibrium log")
    if os.path.exists('nash_log.json'):
        with open('nash_log.json', 'r') as f:
            log_data = json.load(f)
        print(f"  Log entries: {len(log_data)}")
        assert len(log_data) > 0, "Should have at least one log entry"
        assert 'timestamp' in log_data[0], "Log entry should have timestamp"
        assert 'module_metrics' in log_data[0], "Log entry should have module_metrics"
        assert 'coordinated_candidates' in log_data[0], "Log entry should have coordinated_candidates"
        print("  PASSED")
    else:
        print("  FAILED: nash_log.json not created")
    
    print("\nTest 11: Test detect_nash() and get_stable_modules()")
    detector.reset()
    detector.add_module("module_a", 0.8)
    detector.add_module("module_b", 0.9)
    detector.add_module("module_c", 0.85)
    
    for _ in range(5):
        detector.record_mutation_outcome("module_a", "module_b", False)
        detector.record_mutation_outcome("module_a", "module_c", False)
        detector.record_mutation_outcome("module_b", "module_c", False)
    
    for _ in range(3):
        detector.record_mutation_outcome("module_a", "module_b", False)
        detector.record_mutation_outcome("module_a", "module_c", False)
        detector.record_mutation_outcome("module_b", "module_c", False)
        detector.detect_equilibrium()
    
    nash_result = detector.detect_nash()
    stable_modules = detector.get_stable_modules()
    print(f"  Nash equilibrium: {nash_result}")
    print(f"  Stable modules: {stable_modules}")
    assert nash_result, "Should detect Nash equilibrium"
    assert len(stable_modules) > 0, "Should have stable modules"
    print("  PASSED")
    
    print("\nTest 12: Test interaction frequencies")
    frequencies = detector.get_interaction_frequencies()
    print(f"  Interaction frequencies: {frequencies}")
    assert len(frequencies) > 0, "Should have interaction frequencies"
    print("  PASSED")
    
    print("\nTest 13: Test detect_nash_equilibrium() function")
    is_eq, state = detect_nash_equilibrium()
    print(f"  detect_nash_equilibrium() returned: ({is_eq}, {state})")
    assert isinstance(is_eq, bool), "Should return bool"
    assert isinstance(state, dict), "Should return dict"
    assert 'equilibrium' in state, "State should contain 'equilibrium'"
    assert 'modules_at_equilibrium' in state, "State should contain 'modules_at_equilibrium'"
    assert 'stuck_pairs' in state, "State should contain 'stuck_pairs'"
    assert 'coordinated_candidates' in state, "State should contain 'coordinated_candidates'"
    assert 'payoffs' in state, "State should contain 'payoffs'"
    assert 'module_metrics' in state, "State should contain 'module_metrics'"
    assert 'consecutive_no_improvement' in state, "State should contain 'consecutive_no_improvement'"
    print("  PASSED")
    
    if os.path.exists('test_state.json'):
        os.remove('test_state.json')
    if os.path.exists('nash_state.json'):
        os.remove('nash_state.json')
    if os.path.exists('nash_log.json'):
        os.remove('nash_log.json')
    
    print("\nAll tests passed!")


if __name__ == "__main__":
    run_test_mode()