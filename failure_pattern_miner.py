import json
import re
from collections import defaultdict
from typing import List, Dict, Any, Optional, Tuple

class FailurePatternMiner:
    """
    Mines failure logs to identify recurring error patterns and generate
    'forbidden mutation space' rules.
    """

    def __init__(self, log_path: str = "failure_log.jsonl"):
        self.log_path = log_path
        self.failures: List[Dict[str, Any]] = []
        self.clusters: Dict[str, List[Dict[str, Any]]] = {}
        self.patterns: List[Dict[str, Any]] = []
        self.rules: List[Dict[str, Any]] = []

    def load_logs(self) -> None:
        """Load failure logs from JSONL file."""
        self.failures = []
        try:
            with open(self.log_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            entry = json.loads(line)
                            self.failures.append(entry)
                        except json.JSONDecodeError:
                            continue
        except FileNotFoundError:
            print(f"Warning: {self.log_path} not found. No failures loaded.")
        except Exception as e:
            print(f"Error loading logs: {e}")

    def cluster_failures(self) -> None:
        """
        Cluster failures by error type and affected modules.
        Uses a composite key of (error_type, module_name) for clustering.
        """
        self.clusters = defaultdict(list)
        for failure in self.failures:
            error_type = failure.get("error_type", "unknown")
            module_name = failure.get("module", "unknown")
            # Normalize module name to handle minor variations
            module_name = self._normalize_module(module_name)
            cluster_key = f"{error_type}::{module_name}"
            self.clusters[cluster_key].append(failure)

    def _normalize_module(self, module: str) -> str:
        """Normalize module name by stripping version suffixes and whitespace."""
        module = module.strip()
        # Remove common version patterns like @1.2.3 or -v1
        module = re.sub(r'[@\-]\d+\.\d+\.\d+', '', module)
        module = re.sub(r'[@\-]v\d+', '', module)
        return module

    def identify_patterns(self) -> None:
        """
        Identify recurring patterns from clusters.
        Patterns include:
        - Frequent import errors in a module (3+ occurrences)
        - Schema mismatches between two modules
        - Repeated timeout errors
        - Consistent permission errors
        """
        self.patterns = []
        for cluster_key, failures in self.clusters.items():
            if len(failures) < 3:
                continue  # Skip small clusters

            error_type, module = cluster_key.split("::", 1)
            pattern = {
                "cluster_key": cluster_key,
                "error_type": error_type,
                "module": module,
                "count": len(failures),
                "sample_failures": failures[:3],  # Keep first 3 as samples
                "pattern_type": self._classify_pattern(error_type, module, failures)
            }
            self.patterns.append(pattern)

    def _classify_pattern(self, error_type: str, module: str, failures: List[Dict]) -> str:
        """Classify the pattern type based on error characteristics."""
        if "import" in error_type.lower() or "module" in error_type.lower():
            return "import_error"
        elif "schema" in error_type.lower() or "mismatch" in error_type.lower():
            return "schema_mismatch"
        elif "timeout" in error_type.lower():
            return "timeout"
        elif "permission" in error_type.lower() or "auth" in error_type.lower():
            return "permission_error"
        elif "type" in error_type.lower() or "typeerror" in error_type.lower():
            return "type_error"
        else:
            return "generic_error"

    def generate_rules(self) -> None:
        """
        Generate 'forbidden mutation space' rules from identified patterns.
        Rules include conditions (module_pattern, error_type, affected_interface)
        and actions (block, warn, require_precheck).
        """
        self.rules = []
        for pattern in self.patterns:
            rule = self._create_rule_from_pattern(pattern)
            if rule:
                self.rules.append(rule)

    def _create_rule_from_pattern(self, pattern: Dict) -> Optional[Dict]:
        """Create a single rule from a pattern."""
        error_type = pattern["error_type"]
        module = pattern["module"]
        count = pattern["count"]
        pattern_type = pattern["pattern_type"]

        # Determine severity based on count and pattern type
        if count >= 10:
            action = "block"
        elif count >= 5:
            action = "warn"
        else:
            action = "require_precheck"

        # Build conditions
        conditions = {
            "module_pattern": f"*{module}*",
            "error_type": error_type,
            "affected_interface": self._infer_affected_interface(pattern)
        }

        rule = {
            "id": f"rule_{module}_{error_type}_{pattern_type}",
            "conditions": conditions,
            "action": action,
            "severity": "high" if action == "block" else ("medium" if action == "warn" else "low"),
            "description": f"Detected {count} occurrences of {error_type} in module {module}",
            "pattern_type": pattern_type,
            "sample_count": count
        }
        return rule

    def _infer_affected_interface(self, pattern: Dict) -> str:
        """Infer the affected interface from sample failures."""
        sample = pattern["sample_failures"][0] if pattern["sample_failures"] else {}
        # Try common fields that might indicate the interface
        for field in ["interface", "api", "endpoint", "function", "method"]:
            if field in sample:
                return sample[field]
        return "unknown"

    def export_rules(self, output_path: str = "forbidden_mutation_rules.json") -> None:
        """Export generated rules to a JSON file."""
        output = {
            "rules": self.rules,
            "metadata": {
                "total_failures": len(self.failures),
                "total_clusters": len(self.clusters),
                "total_patterns": len(self.patterns),
                "total_rules": len(self.rules)
            }
        }
        try:
            with open(output_path, 'w') as f:
                json.dump(output, f, indent=2)
            print(f"Rules exported to {output_path}")
        except Exception as e:
            print(f"Error exporting rules: {e}")

    def get_most_common_failure_type(self, last_n_cycles: int = 10) -> Optional[Dict[str, Any]]:
        """
        Analyze the last N cycles of failure logs and return the most frequent
        failure type with associated keywords.
        
        Args:
            last_n_cycles: Number of recent cycles to analyze (default 10)
            
        Returns:
            Dictionary with 'failure_type' and 'keywords' if failures exist,
            None if no failures in the window
        """
        if not self.failures:
            return None
        
        # Get the last N cycles worth of failures
        # Assuming failures have a 'cycle' field, otherwise use the last N failures
        recent_failures = []
        if 'cycle' in self.failures[0]:
            # Find unique cycles and get the last N
            cycles = sorted(set(f.get('cycle', 0) for f in self.failures))
            if len(cycles) > last_n_cycles:
                cutoff_cycle = cycles[-last_n_cycles]
                recent_failures = [f for f in self.failures if f.get('cycle', 0) >= cutoff_cycle]
            else:
                recent_failures = self.failures[:]
        else:
            # If no cycle field, just take the last N failures
            recent_failures = self.failures[-last_n_cycles:] if len(self.failures) >= last_n_cycles else self.failures[:]
        
        if not recent_failures:
            return None
        
        # Count failure types
        type_counts = defaultdict(int)
        type_keywords = defaultdict(set)
        
        for failure in recent_failures:
            error_type = failure.get("error_type", "unknown")
            type_counts[error_type] += 1
            
            # Extract keywords from error message
            error_msg = failure.get("error_message", "")
            if error_msg:
                # Extract meaningful keywords (words longer than 3 characters)
                words = re.findall(r'\b[a-zA-Z_]{4,}\b', error_msg.lower())
                type_keywords[error_type].update(words[:5])  # Limit to 5 keywords per failure
        
        # Find the most common failure type
        if not type_counts:
            return None
        
        most_common_type = max(type_counts, key=type_counts.get)
        
        return {
            "failure_type": most_common_type,
            "keywords": list(type_keywords.get(most_common_type, []))[:10]  # Return top 10 keywords
        }

    def run(self, output_path: str = "forbidden_mutation_rules.json") -> None:
        """Execute the full mining pipeline."""
        print("Loading failure logs...")
        self.load_logs()
        print(f"Loaded {len(self.failures)} failures.")

        print("Clustering failures...")
        self.cluster_failures()
        print(f"Created {len(self.clusters)} clusters.")

        print("Identifying patterns...")
        self.identify_patterns()
        print(f"Identified {len(self.patterns)} patterns.")

        print("Generating rules...")
        self.generate_rules()
        print(f"Generated {len(self.rules)} rules.")

        print("Exporting rules...")
        self.export_rules(output_path)

        return self.rules


def main():
    """CLI entry point for the failure pattern miner."""
    import argparse
    parser = argparse.ArgumentParser(description="Mine failure logs for recurring patterns and generate mutation rules.")
    parser.add_argument("--log", default="failure_log.jsonl", help="Path to failure log JSONL file")
    parser.add_argument("--output", default="forbidden_mutation_rules.json", help="Output path for generated rules")
    args = parser.parse_args()

    miner = FailurePatternMiner(log_path=args.log)
    miner.run(output_path=args.output)


if __name__ == "__main__":
    main()