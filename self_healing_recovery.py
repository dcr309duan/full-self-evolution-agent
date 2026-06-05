import json
import os
import subprocess
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('self_healing_recovery')

# Constants
STATE_FILE = 'recovery_state.json'
MAX_CONSECUTIVE_FAILURES = 2
MAX_FAILURE_CHAIN = 3
KNOWN_GOOD_COMMIT_FILE = 'last_good_commit.txt'
SIMPLIFIED_MODULE_SUFFIX = '_simplified'

class SelfHealingRecovery:
    """
    Main self-healing recovery module that tracks failures, triggers git revert,
    logs patterns, generates simplified versions, and provides restore functionality.
    """

    def __init__(self, state_file: str = STATE_FILE):
        self.state_file = state_file
        self.failure_tracker: Dict[str, List[Dict[str, Any]]] = {}
        self.consecutive_failure_chain: Dict[str, int] = {}
        self._load_state()

    def _load_state(self) -> None:
        """Load failure tracking state from JSON file."""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    data = json.load(f)
                    self.failure_tracker = data.get('failures', {})
                    self.consecutive_failure_chain = data.get('failure_chain', {})
                    logger.info(f"Loaded state from {self.state_file}")
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Failed to load state file: {e}")
                self.failure_tracker = {}
                self.consecutive_failure_chain = {}
        else:
            logger.info("No state file found, starting fresh")
            self.failure_tracker = {}
            self.consecutive_failure_chain = {}

    def _save_state(self) -> None:
        """Save current failure tracking state to JSON file."""
        try:
            with open(self.state_file, 'w') as f:
                json.dump({
                    'failures': self.failure_tracker,
                    'failure_chain': self.consecutive_failure_chain
                }, f, indent=2)
            logger.info(f"State saved to {self.state_file}")
        except IOError as e:
            logger.error(f"Failed to save state file: {e}")

    def track_failure(self, module_name: str, error_type: str, error_message: str) -> None:
        """
        Track a failure for a given module with timestamp and error details.

        Args:
            module_name: Name of the core module that failed
            error_type: Type/category of the error
            error_message: Detailed error message
        """
        timestamp = datetime.now().isoformat()
        failure_entry = {
            'timestamp': timestamp,
            'error_type': error_type,
            'error_message': error_message
        }

        if module_name not in self.failure_tracker:
            self.failure_tracker[module_name] = []

        self.failure_tracker[module_name].append(failure_entry)
        self._save_state()

        consecutive_failures = self.get_consecutive_failures(module_name)
        logger.info(f"Tracked failure for {module_name}: {error_type} (consecutive: {consecutive_failures})")

        if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
            logger.warning(f"Module {module_name} has {consecutive_failures} consecutive failures. Triggering recovery.")
            self.trigger_recovery(module_name)

    def get_consecutive_failures(self, module_name: str) -> int:
        """
        Count consecutive failures for a module (failures without a successful restore).

        Args:
            module_name: Name of the module to check

        Returns:
            Number of consecutive failures
        """
        if module_name not in self.failure_tracker:
            return 0

        failures = self.failure_tracker[module_name]
        consecutive = 0
        for failure in reversed(failures):
            if failure.get('restored', False):
                break
            consecutive += 1
        return consecutive

    def trigger_recovery(self, module_name: str) -> bool:
        """
        Trigger git revert to last known-good commit for the specified module.

        Args:
            module_name: Name of the module to recover

        Returns:
            True if recovery was successful, False otherwise
        """
        logger.info(f"Triggering recovery for module: {module_name}")

        # Increment failure chain counter
        if module_name not in self.consecutive_failure_chain:
            self.consecutive_failure_chain[module_name] = 0
        self.consecutive_failure_chain[module_name] += 1
        self._save_state()

        # Check if failure chain has reached threshold
        if self.consecutive_failure_chain[module_name] >= MAX_FAILURE_CHAIN:
            logger.warning(f"Module {module_name} has reached {MAX_FAILURE_CHAIN} failures in chain. Calling deprecate_module.")
            try:
                import failure_driven_simplification
                failure_driven_simplification.deprecate_module(module_name)
                self._log_recovery(module_name, 'deprecation', f"Module deprecated after {MAX_FAILURE_CHAIN} failures")
                return True
            except ImportError:
                logger.error("failure_driven_simplification module not available")
                return False
            except Exception as e:
                logger.error(f"Failed to deprecate module {module_name}: {e}")
                return False

        # Get last known-good commit
        good_commit = self._get_last_good_commit(module_name)
        if not good_commit:
            logger.error(f"No known-good commit found for {module_name}")
            return False

        # Perform git revert
        try:
            result = subprocess.run(
                ['git', 'revert', '--no-commit', good_commit],
                capture_output=True,
                text=True,
                check=True
            )
            logger.info(f"Git revert successful for {module_name}: {result.stdout}")
            self._log_recovery(module_name, 'git_revert', f"Reverted to commit {good_commit}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Git revert failed for {module_name}: {e.stderr}")
            self._log_recovery(module_name, 'git_revert_failed', str(e.stderr))
            return False

    def _get_last_good_commit(self, module_name: str) -> Optional[str]:
        """
        Retrieve the last known-good commit for a module.

        Args:
            module_name: Name of the module

        Returns:
            Commit hash if found, None otherwise
        """
        # In a real scenario, this would read from a file or database
        # For demonstration, we check a simple file
        commit_file = f"{module_name}_{KNOWN_GOOD_COMMIT_FILE}"
        if os.path.exists(commit_file):
            try:
                with open(commit_file, 'r') as f:
                    return f.read().strip()
            except IOError:
                pass
        logger.warning(f"No known-good commit found for {module_name}")
        return None

    def _log_recovery(self, module_name: str, recovery_type: str, details: str) -> None:
        """
        Log recovery action with timestamp.

        Args:
            module_name: Name of the module
            recovery_type: Type of recovery action performed
            details: Additional details about the recovery
        """
        timestamp = datetime.now().isoformat()
        recovery_entry = {
            'timestamp': timestamp,
            'recovery_type': recovery_type,
            'details': details
        }

        if module_name not in self.failure_tracker:
            self.failure_tracker[module_name] = []

        self.failure_tracker[module_name].append(recovery_entry)
        self._save_state()
        logger.info(f"Recovery logged for {module_name}: {recovery_type}")

    def log_failure_pattern(self, module_name: str) -> Dict[str, Any]:
        """
        Log and analyze failure patterns for a module.

        Args:
            module_name: Name of the module

        Returns:
            Dictionary with failure pattern analysis
        """
        if module_name not in self.failure_tracker:
            return {'module': module_name, 'total_failures': 0, 'patterns': []}

        failures = [f for f in self.failure_tracker[module_name] if 'error_type' in f]
        total_failures = len(failures)
        error_types = {}
        time_distribution = {'morning': 0, 'afternoon': 0, 'evening': 0, 'night': 0}

        for failure in failures:
            error_type = failure['error_type']
            error_types[error_type] = error_types.get(error_type, 0) + 1

            # Analyze time distribution
            try:
                timestamp = datetime.fromisoformat(failure['timestamp'])
                hour = timestamp.hour
                if 6 <= hour < 12:
                    time_distribution['morning'] += 1
                elif 12 <= hour < 18:
                    time_distribution['afternoon'] += 1
                elif 18 <= hour < 24:
                    time_distribution['evening'] += 1
                else:
                    time_distribution['night'] += 1
            except (ValueError, KeyError):
                pass

        pattern = {
            'module': module_name,
            'total_failures': total_failures,
            'error_types': error_types,
            'time_distribution': time_distribution,
            'consecutive_failures': self.get_consecutive_failures(module_name)
        }

        logger.info(f"Failure pattern for {module_name}: {pattern}")
        return pattern

    def generate_simplified_version(self, module_name: str, original_code: str) -> str:
        """
        Generate a simplified version of a module with optional features disabled.

        Args:
            module_name: Name of the module to simplify
            original_code: Original source code of the module

        Returns:
            Simplified version of the code
        """
        logger.info(f"Generating simplified version for {module_name}")

        # Simple simplification: comment out lines with optional features
        simplified_lines = []
        optional_features = ['async', 'await', 'threading', 'multiprocessing', 'asyncio']

        for line in original_code.split('\n'):
            # Check if line contains optional features
            if any(feature in line.lower() for feature in optional_features):
                # Comment out the line
                simplified_lines.append(f"# DISABLED: {line}")
            else:
                simplified_lines.append(line)

        simplified_code = '\n'.join(simplified_lines)

        # Save simplified version to file
        simplified_filename = f"{module_name}{SIMPLIFIED_MODULE_SUFFIX}.py"
        try:
            with open(simplified_filename, 'w') as f:
                f.write(simplified_code)
            logger.info(f"Simplified version saved to {simplified_filename}")
        except IOError as e:
            logger.error(f"Failed to save simplified version: {e}")

        return simplified_code

    def restore_full_functionality(self, module_name: str) -> bool:
        """
        Attempt to restore full functionality for the next cycle.

        Args:
            module_name: Name of the module to restore

        Returns:
            True if restoration was successful, False otherwise
        """
        logger.info(f"Attempting to restore full functionality for {module_name}")

        # Reset failure chain counter on successful execution
        if module_name in self.consecutive_failure_chain:
            self.consecutive_failure_chain[module_name] = 0
            self._save_state()
            logger.info(f"Reset failure chain counter for {module_name}")

        # Check if there's a simplified version to restore from
        simplified_filename = f"{module_name}{SIMPLIFIED_MODULE_SUFFIX}.py"
        if not os.path.exists(simplified_filename):
            logger.warning(f"No simplified version found for {module_name}")
            return False

        # In a real scenario, this would perform a more sophisticated restoration
        # For now, we mark the last failure as restored
        if module_name in self.failure_tracker and self.failure_tracker[module_name]:
            # Find the last failure entry and mark it as restored
            for entry in reversed(self.failure_tracker[module_name]):
                if 'error_type' in entry:
                    entry['restored'] = True
                    self._save_state()
                    logger.info(f"Marked last failure as restored for {module_name}")
                    return True

        logger.warning(f"No failures to restore for {module_name}")
        return False

    def get_failure_history(self, module_name: str) -> List[Dict[str, Any]]:
        """
        Get the full failure history for a module.

        Args:
            module_name: Name of the module

        Returns:
            List of failure entries
        """
        return self.failure_tracker.get(module_name, [])

    def clear_failures(self, module_name: str) -> None:
        """
        Clear all failure tracking for a module.

        Args:
            module_name: Name of the module to clear
        """
        if module_name in self.failure_tracker:
            del self.failure_tracker[module_name]
            self._save_state()
            logger.info(f"Cleared failure tracking for {module_name}")

# Example usage and testing
if __name__ == "__main__":
    # Initialize recovery module
    recovery = SelfHealingRecovery()

    # Simulate failures
    recovery.track_failure('core_module', 'ValueError', 'Invalid input detected')
    recovery.track_failure('core_module', 'RuntimeError', 'Connection timeout')

    # Check consecutive failures
    print(f"Consecutive failures: {recovery.get_consecutive_failures('core_module')}")

    # Log failure pattern
    pattern = recovery.log_failure_pattern('core_module')
    print(f"Failure pattern: {pattern}")

    # Generate simplified version
    sample_code = """
def process_data(data):
    import asyncio
    result = asyncio.run(handle_data(data))
    return result
"""
    simplified = recovery.generate_simplified_version('core_module', sample_code)
    print(f"Simplified code:\n{simplified}")

    # Restore functionality
    recovery.restore_full_functionality('core_module')

    # Get history
    history = recovery.get_failure_history('core_module')
    print(f"Failure history: {history}")