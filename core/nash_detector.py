from collections import deque, defaultdict
from datetime import datetime
import json
import os
import sys
import typing

class NashEquilibriumDetector:
    """
    Self-contained Nash equilibrium detector.
    Tracks module performance over the last N cycles, detects when no single-module
    mutation improves the system for 3+ consecutive attempts.
    Uses only standard library (collections, json, datetime, os, sys, typing).
    Exposes is_at_nash() method and get_stable_modules() list.
    """

    def __init__(self, module_names=None, state_file="nash_state.json", window_size=20, consecutive_failures=3):
        """
        Initialize the detector with module names.
        
        Args:
            module_names: List of module names to track (optional, loaded from file if not provided)
            state_file: Path to JSON file for state persistence
            window_size: Number of recent cycles to track per module
            consecutive_failures: Number of consecutive attempts without improvement to detect Nash
        """
        self.state_file = state_file
        self.module_names = module_names or []
        self.window_size = window_size
        self.consecutive_failures = consecutive_failures
        self.mutation_success = defaultdict(lambda: deque(maxlen=self.window_size))
        self.module_success_rates = {}
        self.nash_detected = False
        self.stable_modules = []
        self.consecutive_no_improvement = 0
        self.system_failing_goals = False
        self.load_state()

    def record_mutation_outcome(self, module_name, improved):
        """
        Record the outcome of a mutation for a specific module.
        
        Args:
            module_name: Name of the module that mutated
            improved: Whether the mutation improved the system
        """
        self.mutation_success[module_name].append(improved)
        self._update_module_success_rate(module_name)
        self.save_state()

    def _update_module_success_rate(self, module_name):
        """Update the success rate for a module based on its sliding window."""
        history = self.mutation_success.get(module_name, deque())
        if len(history) > 0:
            success_count = sum(1 for outcome in history if outcome)
            self.module_success_rates[module_name] = success_count / len(history)
        else:
            self.module_success_rates[module_name] = 0.0

    def set_system_goal_status(self, goals_failing):
        """
        Set whether the system is currently failing its goals.
        
        Args:
            goals_failing: True if the system is failing goals, False otherwise
        """
        self.system_failing_goals = goals_failing

    def is_at_nash(self):
        """
        Detect if the system is at Nash equilibrium.
        
        Checks if no single module has had a successful mutation in the last N consecutive attempts
        while the system is still failing goals.
        
        Returns:
            True if Nash equilibrium is detected, False otherwise
        """
        if not self.module_names:
            return False

        # Check if any module has had a successful mutation in the last N attempts
        any_improvement = False
        for module_name in self.module_names:
            history = self.mutation_success.get(module_name, deque())
            recent_history = list(history)[-self.consecutive_failures:] if len(history) >= self.consecutive_failures else list(history)
            if any(outcome for outcome in recent_history):
                any_improvement = True
                break

        # Update consecutive no improvement counter
        if any_improvement:
            self.consecutive_no_improvement = 0
        else:
            self.consecutive_no_improvement += 1

        # Detect Nash: no improvements in last N consecutive attempts AND system still failing goals
        self.nash_detected = (
            self.consecutive_no_improvement >= self.consecutive_failures and
            self.system_failing_goals
        )

        if self.nash_detected:
            self.stable_modules = list(self.module_names)
        else:
            self.stable_modules = []

        self.save_state()
        return self.nash_detected

    def get_stable_modules(self):
        """
        Get the list of modules that are at equilibrium.
        
        Returns:
            List of module names that are at equilibrium
        """
        return list(self.stable_modules)

    def add_module(self, module_name):
        """
        Add a module to the detector.
        
        Args:
            module_name: Name of the module to add
        """
        if module_name not in self.module_names:
            self.module_names.append(module_name)
            self.module_success_rates[module_name] = 0.0
        self.save_state()

    def remove_module(self, module_name):
        """
        Remove a module from the detector.
        
        Args:
            module_name: Name of the module to remove
        """
        if module_name in self.module_names:
            self.module_names.remove(module_name)
        if module_name in self.mutation_success:
            del self.mutation_success[module_name]
        if module_name in self.module_success_rates:
            del self.module_success_rates[module_name]
        if module_name in self.stable_modules:
            self.stable_modules.remove(module_name)
        self.save_state()

    def get_module_success_rates(self):
        """
        Get the success rates for all modules.
        
        Returns:
            Dictionary mapping module names to their success rates
        """
        return dict(self.module_success_rates)

    def get_nash_state(self):
        """
        Get the current Nash equilibrium state information.
        
        Returns:
            Dictionary containing Nash equilibrium state information
        """
        return {
            'nash': self.nash_detected,
            'stable_modules': self.get_stable_modules(),
            'module_success_rates': self.get_module_success_rates(),
            'consecutive_no_improvement': self.consecutive_no_improvement,
            'system_failing_goals': self.system_failing_goals,
            'module_names': list(self.module_names),
            'consecutive_failures': self.consecutive_failures
        }

    def save_state(self):
        """Save the current state to a JSON file."""
        state = {
            'module_names': list(self.module_names),
            'module_success_rates': dict(self.module_success_rates),
            'nash_detected': self.nash_detected,
            'stable_modules': list(self.stable_modules),
            'consecutive_no_improvement': self.consecutive_no_improvement,
            'system_failing_goals': self.system_failing_goals,
            'mutation_success': {k: list(v) for k, v in self.mutation_success.items()},
            'window_size': self.window_size,
            'consecutive_failures': self.consecutive_failures
        }
        try:
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)
        except (IOError, OSError) as e:
            print(f"Warning: Could not save state to {self.state_file}: {e}")

    def load_state(self):
        """Load the state from a JSON file if it exists."""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                self.module_names = state.get('module_names', [])
                self.module_success_rates = state.get('module_success_rates', {})
                self.nash_detected = state.get('nash_detected', False)
                self.stable_modules = state.get('stable_modules', [])
                self.consecutive_no_improvement = state.get('consecutive_no_improvement', 0)
                self.system_failing_goals = state.get('system_failing_goals', False)
                self.window_size = state.get('window_size', 20)
                self.consecutive_failures = state.get('consecutive_failures', 3)
                mutation_data = state.get('mutation_success', {})
                for module, history in mutation_data.items():
                    self.mutation_success[module] = deque(history, maxlen=self.window_size)
            except (json.JSONDecodeError, IOError, OSError) as e:
                print(f"Warning: Could not load state from {self.state_file}: {e}")

    def reset(self):
        """Reset all tracking data and clear the state file."""
        self.module_names = []
        self.mutation_success.clear()
        self.module_success_rates = {}
        self.nash_detected = False
        self.stable_modules = []
        self.consecutive_no_improvement = 0
        self.system_failing_goals = False
        if os.path.exists(self.state_file):
            try:
                os.remove(self.state_file)
            except OSError as e:
                print(f"Warning: Could not remove state file {self.state_file}: {e}")


class ModuleInteractionTracker:
    """
    Tracks pairwise interaction scores between modules.
    Records performance metrics for each module pair and provides
    interaction score data for Nash equilibrium analysis.
    """

    def __init__(self, state_file="interaction_scores.json"):
        """
        Initialize the interaction tracker.
        
        Args:
            state_file: Path to JSON file for state persistence
        """
        self.state_file = state_file
        self.interaction_scores = defaultdict(lambda: defaultdict(float))
        self.interaction_counts = defaultdict(lambda: defaultdict(int))
        self.load_state()

    def record_interaction(self, module_a, module_b, score):
        """
        Record an interaction score between two modules.
        
        Args:
            module_a: Name of the first module
            module_b: Name of the second module
            score: Performance score for this interaction (0.0 to 1.0)
        """
        key_a, key_b = sorted([module_a, module_b])
        self.interaction_scores[key_a][key_b] = (
            (self.interaction_scores[key_a][key_b] * self.interaction_counts[key_a][key_b] + score) /
            (self.interaction_counts[key_a][key_b] + 1)
        )
        self.interaction_counts[key_a][key_b] += 1
        self.save_state()

    def get_interaction_score(self, module_a, module_b):
        """
        Get the interaction score between two modules.
        
        Args:
            module_a: Name of the first module
            module_b: Name of the second module
            
        Returns:
            Float score between 0.0 and 1.0, or 0.0 if no data
        """
        key_a, key_b = sorted([module_a, module_b])
        return self.interaction_scores.get(key_a, {}).get(key_b, 0.0)

    def get_all_interaction_scores(self):
        """
        Get all recorded interaction scores.
        
        Returns:
            Dictionary mapping module pairs to their scores
        """
        result = {}
        for module_a in self.interaction_scores:
            for module_b, score in self.interaction_scores[module_a].items():
                result[f"{module_a}-{module_b}"] = score
        return result

    def get_module_pairwise_scores(self, module_name):
        """
        Get all interaction scores involving a specific module.
        
        Args:
            module_name: Name of the module to query
            
        Returns:
            Dictionary mapping partner module names to scores
        """
        scores = {}
        for other_module in self.interaction_scores:
            if other_module == module_name:
                for partner, score in self.interaction_scores[other_module].items():
                    scores[partner] = score
            elif module_name in self.interaction_scores.get(other_module, {}):
                scores[other_module] = self.interaction_scores[other_module][module_name]
        return scores

    def save_state(self):
        """Save the current state to a JSON file."""
        state = {
            'interaction_scores': {k: dict(v) for k, v in self.interaction_scores.items()},
            'interaction_counts': {k: dict(v) for k, v in self.interaction_counts.items()}
        }
        try:
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)
        except (IOError, OSError) as e:
            print(f"Warning: Could not save interaction scores to {self.state_file}: {e}")

    def load_state(self):
        """Load the state from a JSON file if it exists."""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                scores_data = state.get('interaction_scores', {})
                for module_a, partners in scores_data.items():
                    for module_b, score in partners.items():
                        self.interaction_scores[module_a][module_b] = score
                counts_data = state.get('interaction_counts', {})
                for module_a, partners in counts_data.items():
                    for module_b, count in partners.items():
                        self.interaction_counts[module_a][module_b] = count
            except (json.JSONDecodeError, IOError, OSError) as e:
                print(f"Warning: Could not load interaction scores from {self.state_file}: {e}")

    def reset(self):
        """Reset all tracking data and clear the state file."""
        self.interaction_scores.clear()
        self.interaction_counts.clear()
        if os.path.exists(self.state_file):
            try:
                os.remove(self.state_file)
            except OSError as e:
                print(f"Warning: Could not remove state file {self.state_file}: {e}")


class NashEquilibriumLogger:
    """
    Logs Nash equilibrium states for later multi-module forcing.
    Stores equilibrium snapshots with timestamps and module interaction data.
    """

    def __init__(self, log_file="nash_equilibrium_log.json"):
        """
        Initialize the logger.
        
        Args:
            log_file: Path to JSON file for log persistence
        """
        self.log_file = log_file
        self.equilibrium_states = []
        self.load_log()

    def log_equilibrium_state(self, detector_state, interaction_scores=None):
        """
        Log a detected Nash equilibrium state.
        
        Args:
            detector_state: Dictionary from NashEquilibriumDetector.get_nash_state()
            interaction_scores: Optional dictionary of interaction scores
        """
        entry = {
            'timestamp': datetime.now().isoformat(),
            'detector_state': detector_state,
            'interaction_scores': interaction_scores or {}
        }
        self.equilibrium_states.append(entry)
        self.save_log()

    def get_equilibrium_states(self, limit=None):
        """
        Get logged equilibrium states.
        
        Args:
            limit: Optional maximum number of states to return (most recent first)
            
        Returns:
            List of equilibrium state dictionaries
        """
        states = list(self.equilibrium_states)
        if limit:
            states = states[-limit:]
        return states

    def get_latest_equilibrium(self):
        """
        Get the most recent equilibrium state.
        
        Returns:
            Dictionary of the latest equilibrium state, or None if no states logged
        """
        if self.equilibrium_states:
            return self.equilibrium_states[-1]
        return None

    def clear_log(self):
        """Clear all logged equilibrium states."""
        self.equilibrium_states = []
        self.save_log()

    def save_log(self):
        """Save the log to a JSON file."""
        state = {
            'equilibrium_states': self.equilibrium_states
        }
        try:
            with open(self.log_file, 'w') as f:
                json.dump(state, f, indent=2)
        except (IOError, OSError) as e:
            print(f"Warning: Could not save equilibrium log to {self.log_file}: {e}")

    def load_log(self):
        """Load the log from a JSON file if it exists."""
        if os.path.exists(self.log_file):
            try:
                with open(self.log_file, 'r') as f:
                    state = json.load(f)
                self.equilibrium_states = state.get('equilibrium_states', [])
            except (json.JSONDecodeError, IOError, OSError) as e:
                print(f"Warning: Could not load equilibrium log from {self.log_file}: {e}")


def scan_core_modules():
    """
    Scan all module files in the core/ directory for recent modification times and sizes.
    
    Returns:
        dict: Mapping of module names to their (modification_time, size) tuples
    """
    core_dir = "core"
    module_info = {}
    if not os.path.isdir(core_dir):
        return module_info
    
    for filename in os.listdir(core_dir):
        if filename.endswith(".py"):
            filepath = os.path.join(core_dir, filename)
            try:
                mod_time = os.path.getmtime(filepath)
                size = os.path.getsize(filepath)
                module_name = filename[:-3]  # Remove .py extension
                module_info[module_name] = (mod_time, size)
            except OSError:
                continue
    return module_info


def detect_nash():
    """
    Detect if the system is at Nash equilibrium.
    Scans core/ directory for module changes and detects equilibrium when no module
    has changed in the last 3 cycles.
    
    Returns:
        Tuple of (bool, list) where bool is True if Nash equilibrium is detected,
        and list contains the names of modules at equilibrium
    """
    detector = NashEquilibriumDetector()
    
    # Scan core modules
    module_info = scan_core_modules()
    if not module_info:
        return False, []
    
    # Update detector with current modules
    for module_name in module_info:
        detector.add_module(module_name)
    
    # Check if any module has changed recently (within last 3 cycles)
    # For simplicity, we use the current time as reference
    current_time = datetime.now().timestamp()
    three_cycles_ago = current_time - 3 * 60  # Assume 1 cycle = 1 minute
    
    changed_modules = []
    for module_name, (mod_time, size) in module_info.items():
        if mod_time > three_cycles_ago:
            changed_modules.append(module_name)
    
    # If no modules changed recently, we're at equilibrium
    if not changed_modules:
        detector.set_system_goal_status(True)
        for module_name in module_info:
            detector.record_mutation_outcome(module_name, False)
        is_nash = detector.is_at_nash()
        stable_modules = detector.get_stable_modules()
        return is_nash, stable_modules
    else:
        # Record successful mutations for changed modules
        for module_name in changed_modules:
            detector.record_mutation_outcome(module_name, True)
        is_nash = detector.is_at_nash()
        stable_modules = detector.get_stable_modules()
        return is_nash, stable_modules


def get_stable_modules():
    """
    Get the list of modules that are at equilibrium.
    
    Returns:
        List of module names that are at equilibrium
    """
    detector = NashEquilibriumDetector()
    return detector.get_stable_modules()


def run_test_mode():
    """Simple test mode that can run standalone."""
    print("Running NashEquilibriumDetector in test mode...")
    
    detector = NashEquilibriumDetector(state_file="test_nash_state.json")
    interaction_tracker = ModuleInteractionTracker(state_file="test_interaction_scores.json")
    logger = NashEquilibriumLogger(log_file="test_nash_log.json")
    
    print("\nTest 1: Create test data")
    detector.add_module("module_a")
    detector.add_module("module_b")
    detector.add_module("module_c")
    print(f"  Created detector with {len(detector.module_names)} modules")
    print(f"  Module names: {detector.module_names}")
    print("  PASSED")
    
    print("\nTest 2: Record mutation outcomes and check Nash equilibrium")
    
    # Record unsuccessful mutations (no improvement)
    for _ in range(3):
        detector.record_mutation_outcome("module_a", False)
        detector.record_mutation_outcome("module_b", False)
        detector.record_mutation_outcome("module_c", False)
    
    # System is failing goals
    detector.set_system_goal_status(True)
    
    is_nash = detector.is_at_nash()
    print(f"  Nash after 1 cycle: {is_nash}")
    assert not is_nash, "Should not be Nash after 1 cycle"
    
    for _ in range(2):
        detector.record_mutation_outcome("module_a", False)
        detector.record_mutation_outcome("module_b", False)
        detector.record_mutation_outcome("module_c", False)
        is_nash = detector.is_at_nash()
    
    print(f"  Nash after 3 cycles: {is_nash}")
    assert is_nash, "Should be Nash after 3 cycles with no success and failing goals"
    print("  PASSED")
    
    print("\nTest 3: Check stable modules")
    stable_modules = detector.get_stable_modules()
    print(f"  Stable modules: {stable_modules}")
    assert len(stable_modules) > 0, "Should have at least one stable module"
    print("  PASSED")
    
    print("\nTest 4: Test successful mutation breaks Nash")
    detector.record_mutation_outcome("module_a", True)
    is_nash = detector.is_at_nash()
    print(f"  Nash after success: {is_nash}")
    assert not is_nash, "Should not be Nash after a successful mutation"
    print("  PASSED")
    
    print("\nTest 5: Test system not failing goals")
    detector.reset()
    detector.add_module("module_a")
    detector.add_module("module_b")
    detector.set_system_goal_status(False)
    
    for _ in range(3):
        detector.record_mutation_outcome("module_a", False)
        detector.record_mutation_outcome("module_b", False)
        is_nash = detector.is_at_nash()
    
    print(f"  Nash with goals not failing: {is_nash}")
    assert not is_nash, "Should not be Nash if goals are not failing"
    print("  PASSED")
    
    print("\nTest 6: Test add and remove modules")
    detector.add_module("module_d")
    print(f"  Module names after add: {detector.module_names}")
    assert "module_d" in detector.module_names, "module_d should be added"
    
    detector.remove_module("module_d")
    print(f"  Module names after remove: {detector.module_names}")
    assert "module_d" not in detector.module_names, "module_d should be removed"
    print("  PASSED")
    
    print("\nTest 7: Test state persistence")
    detector.reset()
    detector.add_module("module_x")
    detector.add_module("module_y")
    detector.record_mutation_outcome("module_x", True)
    detector.record_mutation_outcome("module_y", False)
    detector.save_state()
    
    # Create a new detector and load state
    detector2 = NashEquilibriumDetector(state_file="test_nash_state.json")
    print(f"  Loaded module names: {detector2.module_names}")
    print(f"  Loaded success rates: {detector2.get_module_success_rates()}")
    assert "module_x" in detector2.module_names, "module_x should be loaded"
    assert "module_y" in detector2.module_names, "module_y should be loaded"
    print("  PASSED")
    
    print("\nTest 8: Test detect_nash() function")
    is_nash, stable = detect_nash()
    print(f"  detect_nash() returned: ({is_nash}, {stable})")
    assert isinstance(is_nash, bool), "Should return bool"
    assert isinstance(stable, list), "Should return list"
    print("  PASSED")
    
    print("\nTest 9: Test get_stable_modules() function")
    stable = get_stable_modules()
    print(f"  get_stable_modules() returned: {stable}")
    assert isinstance(stable, list), "Should return a list"
    print("  PASSED")
    
    print("\nTest 10: Test interaction tracker")
    interaction_tracker.record_interaction("module_a", "module_b", 0.8)
    interaction_tracker.record_interaction("module_a", "module_c", 0.6)
    interaction_tracker.record_interaction("module_b", "module_c", 0.9)
    print(f"  Interaction scores: {interaction_tracker.get_all_interaction_scores()}")
    assert interaction_tracker.get_interaction_score("module_a", "module_b") == 0.8
    print("  PASSED")
    
    print("\nTest 11: Test Nash equilibrium logger")
    detector_state = detector.get_nash_state()
    logger.log_equilibrium_state(detector_state, interaction_tracker.get_all_interaction_scores())
    latest = logger.get_latest_equilibrium()
    print(f"  Latest equilibrium logged: {latest['timestamp']}")
    assert latest is not None, "Should have logged an equilibrium state"
    print("  PASSED")
    
    print("\nTest 12: Test reset clears everything")
    detector.reset()
    is_nash = detector.is_at_nash()
    stable_modules = detector.get_stable_modules()
    print(f"  Nash after reset: {is_nash}")
    print(f"  Stable modules after reset: {stable_modules}")
    assert not is_nash, "After reset should not be in Nash"
    assert len(stable_modules) == 0, "Stable modules should be empty after reset"
    assert len(detector.module_names) == 0, "Module names should be empty after reset"
    assert not os.path.exists("test_nash_state.json"), "State file should be removed"
    print("  PASSED")
    
    print("\nAll tests passed!")
    
    # Clean up test files
    for f in ["test_nash_state.json", "test_interaction_scores.json", "test_nash_log.json"]:
        if os.path.exists(f):
            os.remove(f)


if __name__ == "__main__":
    run_test_mode()