"""
Integration Conflict Detector

Maintains a file-access log, detects temporal conflicts (same file modified within 5 cycles),
checks interface mismatches between modules, and assigns conflict severity scores.
"""

import re
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional

class IntegrationConflictDetector:
    """
    Detects integration conflicts between modules based on file access patterns
    and interface compatibility.
    """

    def __init__(self, conflict_window: int = 5):
        """
        Initialize the conflict detector.

        Args:
            conflict_window: Number of cycles to consider for temporal conflicts
        """
        self.conflict_window = conflict_window
        # file_access_log: {filename: [(cycle_number, module_name, operation)]}
        self.file_access_log = defaultdict(list)
        # interface_registry: {module_name: {function_name: signature_string}}
        self.interface_registry = defaultdict(dict)
        # interface_expectations: {module_name: {dependency_module: {function_name: expected_signature}}}
        self.interface_expectations = defaultdict(lambda: defaultdict(dict))
        # consistency_validator: optional validator for interface consistency checks
        self.consistency_validator = None

    def set_consistency_validator(self, validator):
        """
        Set a consistency validator to integrate with.

        Args:
            validator: A validator object with a validate method that returns a list of mismatches
        """
        self.consistency_validator = validator

    def log_file_access(self, module: str, filename: str, cycle: int, operation: str = "write"):
        """
        Log a file access event.

        Args:
            module: Name of the module accessing the file
            filename: Path or name of the file being accessed
            cycle: Cycle number when the access occurred
            operation: Type of operation ('read', 'write', 'modify')
        """
        self.file_access_log[filename].append((cycle, module, operation))

    def register_interface(self, module: str, function_name: str, signature: str):
        """
        Register a module's provided interface.

        Args:
            module: Name of the module
            function_name: Name of the function
            signature: Function signature string (e.g., "def foo(a: int, b: str) -> bool")
        """
        self.interface_registry[module][function_name] = signature

    def expect_interface(self, module: str, dependency: str, function_name: str, expected_signature: str):
        """
        Register an expected interface from a dependency.

        Args:
            module: Name of the module that has the expectation
            dependency: Name of the dependency module
            function_name: Name of the expected function
            expected_signature: Expected function signature
        """
        self.interface_expectations[module][dependency][function_name] = expected_signature

    def detect_temporal_conflicts(self) -> List[Dict]:
        """
        Detect conflicts where two modules modify the same file within the conflict window.

        Returns:
            List of conflict dictionaries with details
        """
        conflicts = []
        for filename, accesses in self.file_access_log.items():
            # Sort by cycle number
            sorted_accesses = sorted(accesses, key=lambda x: x[0])

            # Check for write/modify operations within the window
            for i in range(len(sorted_accesses)):
                for j in range(i + 1, len(sorted_accesses)):
                    cycle_i, module_i, op_i = sorted_accesses[i]
                    cycle_j, module_j, op_j = sorted_accesses[j]

                    # Only consider write/modify operations
                    if op_i not in ("write", "modify") and op_j not in ("write", "modify"):
                        continue

                    # Check if within conflict window
                    if abs(cycle_j - cycle_i) <= self.conflict_window:
                        conflicts.append({
                            "type": "temporal",
                            "filename": filename,
                            "modules": [module_i, module_j],
                            "cycles": [cycle_i, cycle_j],
                            "operations": [op_i, op_j],
                            "description": f"Modules '{module_i}' and '{module_j}' both modified '{filename}' "
                                         f"within {abs(cycle_j - cycle_i)} cycles"
                        })
        return conflicts

    def detect_interface_mismatches(self) -> List[Dict]:
        """
        Detect mismatches between expected and actual interfaces.

        Returns:
            List of mismatch dictionaries with details
        """
        mismatches = []
        for module, dependencies in self.interface_expectations.items():
            for dependency, expected_functions in dependencies.items():
                for func_name, expected_sig in expected_functions.items():
                    # Check if dependency provides this function
                    if dependency not in self.interface_registry:
                        mismatches.append({
                            "type": "interface_missing",
                            "module": module,
                            "dependency": dependency,
                            "function": func_name,
                            "expected": expected_sig,
                            "actual": None,
                            "description": f"Module '{dependency}' does not provide function '{func_name}' "
                                         f"expected by '{module}'"
                        })
                        continue

                    actual_sig = self.interface_registry[dependency].get(func_name)
                    if actual_sig is None:
                        mismatches.append({
                            "type": "interface_missing",
                            "module": module,
                            "dependency": dependency,
                            "function": func_name,
                            "expected": expected_sig,
                            "actual": None,
                            "description": f"Module '{dependency}' does not provide function '{func_name}' "
                                         f"expected by '{module}'"
                        })
                    elif not self._signatures_match(expected_sig, actual_sig):
                        mismatches.append({
                            "type": "interface_mismatch",
                            "module": module,
                            "dependency": dependency,
                            "function": func_name,
                            "expected": expected_sig,
                            "actual": actual_sig,
                            "description": f"Interface mismatch for '{func_name}': "
                                         f"'{module}' expects '{expected_sig}', "
                                         f"but '{dependency}' provides '{actual_sig}'"
                        })
        return mismatches

    def detect_consistency_conflicts(self) -> List[Dict]:
        """
        Detect conflicts using the consistency validator if available.

        Returns:
            List of conflict dictionaries from the consistency validator
        """
        conflicts = []
        if self.consistency_validator is not None:
            try:
                validator_results = self.consistency_validator.validate()
                for result in validator_results:
                    if result.get("type") == "interface_mismatch":
                        # Determine severity based on mismatch type
                        mismatch_type = result.get("mismatch_type", "unknown")
                        if mismatch_type == "parameter_count":
                            severity = "critical"
                        elif mismatch_type == "parameter_type":
                            severity = "medium"
                        elif mismatch_type == "return_type":
                            severity = "medium"
                        else:
                            severity = "low"
                        
                        conflicts.append({
                            "type": "consistency_interface_mismatch",
                            "module": result.get("module", "unknown"),
                            "dependency": result.get("dependency", "unknown"),
                            "function": result.get("function", "unknown"),
                            "expected": result.get("expected", ""),
                            "actual": result.get("actual", ""),
                            "description": f"Consistency validator detected interface mismatch: "
                                         f"{result.get('description', '')}",
                            "severity": severity,
                            "mismatch_type": mismatch_type
                        })
                    elif result.get("type") == "interface_missing":
                        conflicts.append({
                            "type": "consistency_interface_missing",
                            "module": result.get("module", "unknown"),
                            "dependency": result.get("dependency", "unknown"),
                            "function": result.get("function", "unknown"),
                            "expected": result.get("expected", ""),
                            "actual": None,
                            "description": f"Consistency validator detected missing interface: "
                                         f"{result.get('description', '')}",
                            "severity": "critical",
                            "mismatch_type": "missing"
                        })
            except Exception as e:
                # Log error but don't crash
                conflicts.append({
                    "type": "consistency_validator_error",
                    "description": f"Error running consistency validator: {str(e)}",
                    "severity": "low"
                })
        return conflicts

    def _signatures_match(self, sig1: str, sig2: str) -> bool:
        """
        Compare two function signatures for compatibility.

        Args:
            sig1: First signature string
            sig2: Second signature string

        Returns:
            True if signatures are compatible, False otherwise
        """
        # Extract parameter lists from signatures
        params1 = self._extract_parameters(sig1)
        params2 = self._extract_parameters(sig2)

        if params1 is None or params2 is None:
            return sig1.strip() == sig2.strip()

        # Compare parameter count
        if len(params1) != len(params2):
            return False

        # Compare parameter types (if available)
        for p1, p2 in zip(params1, params2):
            # Extract type annotations if present
            type1 = self._extract_type(p1)
            type2 = self._extract_type(p2)
            if type1 and type2 and type1 != type2:
                return False

        return True

    def _extract_parameters(self, signature: str) -> Optional[List[str]]:
        """
        Extract parameter list from a function signature.

        Args:
            signature: Function signature string

        Returns:
            List of parameter strings or None if extraction fails
        """
        # Match pattern: def func_name(params) -> return_type
        match = re.search(r'\(([^)]*)\)', signature)
        if match:
            params_str = match.group(1).strip()
            if params_str:
                return [p.strip() for p in params_str.split(',')]
            return []
        return None

    def _extract_type(self, param: str) -> Optional[str]:
        """
        Extract type annotation from a parameter.

        Args:
            param: Parameter string (e.g., "a: int" or "b: str = None")

        Returns:
            Type string or None if no annotation
        """
        # Match pattern: param_name: type
        match = re.search(r':\s*(\w+)', param)
        if match:
            return match.group(1)
        return None

    def assign_severity(self, conflict: Dict) -> str:
        """
        Assign a severity level to a conflict.

        Args:
            conflict: Conflict dictionary

        Returns:
            Severity level: 'low', 'medium', or 'critical'
        """
        if conflict["type"] == "temporal":
            # Temporal conflicts: severity based on proximity and operation types
            cycle_diff = abs(conflict["cycles"][1] - conflict["cycles"][0])
            ops = conflict["operations"]

            # Both are write/modify operations
            if all(op in ("write", "modify") for op in ops):
                if cycle_diff == 0:
                    return "critical"
                elif cycle_diff <= 2:
                    return "medium"
                else:
                    return "low"
            else:
                return "low"

        elif conflict["type"] == "interface_missing":
            # Missing interface is critical
            return "critical"

        elif conflict["type"] == "interface_mismatch":
            # Mismatch severity depends on parameter differences
            expected = conflict["expected"]
            actual = conflict["actual"]
            if self._signatures_match(expected, actual):
                return "low"
            else:
                return "medium"

        elif conflict["type"] in ("consistency_interface_mismatch", "consistency_interface_missing"):
            # Use severity already assigned by detect_consistency_conflicts
            return conflict.get("severity", "low")

        return "low"

    def analyze_all(self) -> List[Dict]:
        """
        Perform complete conflict analysis and assign severities.

        Returns:
            List of all conflicts with severity assigned
        """
        all_conflicts = []
        all_conflicts.extend(self.detect_temporal_conflicts())
        all_conflicts.extend(self.detect_interface_mismatches())
        all_conflicts.extend(self.detect_consistency_conflicts())

        for conflict in all_conflicts:
            if "severity" not in conflict:
                conflict["severity"] = self.assign_severity(conflict)

        return all_conflicts

    def get_summary(self) -> Dict:
        """
        Get a summary of the conflict analysis.

        Returns:
            Dictionary with summary statistics
        """
        conflicts = self.analyze_all()
        severity_counts = {"low": 0, "medium": 0, "critical": 0}
        type_counts = defaultdict(int)

        for conflict in conflicts:
            severity_counts[conflict["severity"]] += 1
            type_counts[conflict["type"]] += 1

        return {
            "total_conflicts": len(conflicts),
            "severity_distribution": dict(severity_counts),
            "type_distribution": dict(type_counts),
            "conflicts": conflicts
        }

    def clear(self):
        """Clear all logged data."""
        self.file_access_log.clear()
        self.interface_registry.clear()
        self.interface_expectations.clear()
        self.consistency_validator = None