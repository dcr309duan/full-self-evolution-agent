import json
import os
from collections import defaultdict
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

class FailureClusterAnalyzer:
    """
    Analyzes failure logs to cluster failures by error type, module, and temporal proximity.
    Outputs structured cluster reports with actionable insights.
    """

    def __init__(self, log_path: str = "core/failure_log.json", cycle_window: int = 5):
        """
        Initialize the analyzer.

        Args:
            log_path: Path to the failure log JSON file.
            cycle_window: Number of cycles within which failures are considered part of the same cluster.
        """
        self.log_path = log_path
        self.cycle_window = cycle_window
        self.failures: List[Dict[str, Any]] = []
        self.clusters: List[Dict[str, Any]] = []

    def load_failures(self) -> None:
        """Load failure log from JSON file."""
        if not os.path.exists(self.log_path):
            raise FileNotFoundError(f"Failure log not found at {self.log_path}")
        with open(self.log_path, 'r') as f:
            self.failures = json.load(f)
        if not isinstance(self.failures, list):
            raise ValueError("Failure log must be a list of failure entries")

    def cluster_failures(self) -> List[Dict[str, Any]]:
        """
        Cluster failures by error type, module, and cycle proximity.

        Returns:
            List of cluster dictionaries with structured information.
        """
        if not self.failures:
            return []

        # Sort failures by cycle number for temporal clustering
        sorted_failures = sorted(self.failures, key=lambda x: x.get('cycle', 0))

        clusters = []
        current_cluster = None

        for failure in sorted_failures:
            error_type = failure.get('error_type', 'unknown')
            module = failure.get('module', 'unknown')
            cycle = failure.get('cycle', 0)

            # Start a new cluster if none exists or if criteria for new cluster met
            if current_cluster is None:
                current_cluster = {
                    'cluster_id': len(clusters) + 1,
                    'error_type': error_type,
                    'affected_modules': set(),
                    'cycle_range': [cycle, cycle],
                    'frequency': 0,
                    'failures': []
                }

            # Check if this failure belongs to the current cluster
            same_error = (error_type == current_cluster['error_type'])
            within_window = (cycle - current_cluster['cycle_range'][1]) <= self.cycle_window

            if same_error and within_window:
                # Add to current cluster
                current_cluster['affected_modules'].add(module)
                current_cluster['cycle_range'][1] = max(current_cluster['cycle_range'][1], cycle)
                current_cluster['frequency'] += 1
                current_cluster['failures'].append(failure)
            else:
                # Finalize current cluster and start a new one
                if current_cluster['failures']:
                    clusters.append(self._finalize_cluster(current_cluster))
                current_cluster = {
                    'cluster_id': len(clusters) + 1,
                    'error_type': error_type,
                    'affected_modules': {module},
                    'cycle_range': [cycle, cycle],
                    'frequency': 1,
                    'failures': [failure]
                }

        # Add the last cluster if it has failures
        if current_cluster and current_cluster['failures']:
            clusters.append(self._finalize_cluster(current_cluster))

        self.clusters = clusters
        return clusters

    def _finalize_cluster(self, cluster: Dict[str, Any]) -> Dict[str, Any]:
        """
        Finalize a cluster by converting sets to lists and adding suggested fix category.

        Args:
            cluster: Raw cluster dictionary with sets.

        Returns:
            Finalized cluster dictionary.
        """
        cluster['affected_modules'] = sorted(list(cluster['affected_modules']))
        cluster['suggested_fix_category'] = self._suggest_fix_category(cluster)
        # Remove raw failures list to keep report concise
        del cluster['failures']
        return cluster

    def _suggest_fix_category(self, cluster: Dict[str, Any]) -> str:
        """
        Suggest a fix category based on error type and affected modules.

        Args:
            cluster: Cluster dictionary.

        Returns:
            Suggested fix category string.
        """
        error_type = cluster['error_type'].lower()
        modules = cluster['affected_modules']

        # Heuristic mapping of error types to fix categories
        if 'timeout' in error_type or 'connection' in error_type:
            return 'Network/Connectivity'
        elif 'memory' in error_type or 'out of memory' in error_type:
            return 'Resource Allocation'
        elif 'permission' in error_type or 'access' in error_type:
            return 'Permissions/Security'
        elif 'syntax' in error_type or 'parse' in error_type:
            return 'Code/Configuration'
        elif 'dependency' in error_type or 'import' in error_type:
            return 'Dependency Management'
        elif 'disk' in error_type or 'io' in error_type:
            return 'Storage/IO'
        elif 'database' in error_type or 'db' in error_type:
            return 'Database'
        elif 'api' in error_type or 'endpoint' in error_type:
            return 'API Integration'
        elif 'crash' in error_type or 'segfault' in error_type:
            return 'Stability/Crash'
        elif 'validation' in error_type or 'invalid' in error_type:
            return 'Input Validation'
        else:
            return 'General/Uncategorized'

    def generate_report(self) -> List[Dict[str, Any]]:
        """
        Generate a structured cluster report.

        Returns:
            List of cluster report dictionaries.
        """
        if not self.clusters:
            self.cluster_failures()

        report = []
        for cluster in self.clusters:
            report.append({
                'cluster_id': cluster['cluster_id'],
                'error_type': cluster['error_type'],
                'affected_modules': cluster['affected_modules'],
                'cycle_range': cluster['cycle_range'],
                'frequency': cluster['frequency'],
                'suggested_fix_category': cluster['suggested_fix_category']
            })
        return report

    def save_report(self, output_path: str = "core/failure_cluster_report.json") -> None:
        """Save the cluster report to a JSON file."""
        report = self.generate_report()
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"Cluster report saved to {output_path}")


def main():
    """Example usage of the FailureClusterAnalyzer."""
    analyzer = FailureClusterAnalyzer()
    try:
        analyzer.load_failures()
        clusters = analyzer.cluster_failures()
        report = analyzer.generate_report()
        print(f"Found {len(clusters)} failure clusters:")
        for cluster in report:
            print(f"  Cluster {cluster['cluster_id']}: {cluster['error_type']} "
                  f"(x{cluster['frequency']}) - {cluster['suggested_fix_category']}")
        analyzer.save_report()
    except FileNotFoundError as e:
        print(f"Error: {e}")
    except json.JSONDecodeError as e:
        print(f"Error parsing failure log: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")


if __name__ == "__main__":
    main()