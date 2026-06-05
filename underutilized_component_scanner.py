from collections import defaultdict
from datetime import datetime, timedelta

class UnderutilizedComponentScanner:
    """
    Scans the last 20 cycles of capability usage to identify underutilized modules
    and orphan capabilities. Outputs a ranked list for the dashboard.
    """

    def __init__(self, usage_data, capability_registry):
        """
        Initialize scanner with usage data and capability registry.

        Args:
            usage_data: List of dicts with keys 'module', 'capability', 'timestamp', 'cycle'
            capability_registry: Dict mapping capability names to their creating module
        """
        self.usage_data = usage_data
        self.capability_registry = capability_registry
        self.underutilized_modules = []
        self.orphan_capabilities = []

    def scan(self):
        """Perform the full scan and return ranked results."""
        self._analyze_usage()
        self._detect_orphans()
        return self._rank_results()

    def _analyze_usage(self):
        """Analyze last 20 cycles of usage data."""
        # Get the last 20 unique cycles
        cycles = sorted(set(item['cycle'] for item in self.usage_data), reverse=True)[:20]
        if not cycles:
            return

        # Filter data to last 20 cycles
        recent_data = [item for item in self.usage_data if item['cycle'] in cycles]

        # Count executions per module
        module_execution_count = defaultdict(int)
        for item in recent_data:
            module_execution_count[item['module']] += 1

        # Flag modules executed less than 3 times
        self.underutilized_modules = [
            {
                'module': module,
                'execution_count': count,
                'category': 'underutilized',
                'cycles_analyzed': len(cycles)
            }
            for module, count in module_execution_count.items()
            if count < 3
        ]

    def _detect_orphans(self):
        """Detect capabilities that were created but never referenced by other modules."""
        # Get all capabilities that have been referenced (used) by any module
        referenced_capabilities = set()
        for item in self.usage_data:
            if 'capability' in item and item['capability']:
                referenced_capabilities.add(item['capability'])

        # Find capabilities that exist in registry but are never referenced
        for capability, creator_module in self.capability_registry.items():
            if capability not in referenced_capabilities:
                self.orphan_capabilities.append({
                    'capability': capability,
                    'creator_module': creator_module,
                    'category': 'orphan'
                })

    def _rank_results(self):
        """Rank underutilized modules and orphan capabilities for dashboard output."""
        # Sort underutilized modules by execution count (ascending - least used first)
        ranked_underutilized = sorted(
            self.underutilized_modules,
            key=lambda x: x['execution_count']
        )

        # Sort orphan capabilities by creator module name for grouping
        ranked_orphans = sorted(
            self.orphan_capabilities,
            key=lambda x: x['creator_module']
        )

        return {
            'underutilized_modules': ranked_underutilized,
            'orphan_capabilities': ranked_orphans,
            'summary': {
                'total_underutilized': len(ranked_underutilized),
                'total_orphans': len(ranked_orphans),
                'scan_timestamp': datetime.utcnow().isoformat()
            }
        }

    def generate_dashboard_output(self):
        """Generate a formatted output suitable for dashboard display."""
        results = self.scan()

        output_lines = []
        output_lines.append("=" * 60)
        output_lines.append("UNDERUTILIZED COMPONENT SCANNER REPORT")
        output_lines.append("=" * 60)
        output_lines.append(f"Scan Timestamp: {results['summary']['scan_timestamp']}")
        output_lines.append("")

        # Underutilized modules section
        output_lines.append("--- UNDERUTILIZED MODULES (executed < 3 times in last 20 cycles) ---")
        if results['underutilized_modules']:
            for idx, module in enumerate(results['underutilized_modules'], 1):
                output_lines.append(
                    f"{idx}. {module['module']} - "
                    f"Executed {module['execution_count']} time(s) in "
                    f"last {module['cycles_analyzed']} cycles"
                )
        else:
            output_lines.append("No underutilized modules detected.")
        output_lines.append("")

        # Orphan capabilities section
        output_lines.append("--- ORPHAN CAPABILITIES (created but never referenced) ---")
        if results['orphan_capabilities']:
            for idx, cap in enumerate(results['orphan_capabilities'], 1):
                output_lines.append(
                    f"{idx}. Capability '{cap['capability']}' "
                    f"(created by module: {cap['creator_module']})"
                )
        else:
            output_lines.append("No orphan capabilities detected.")
        output_lines.append("")

        # Summary
        output_lines.append("--- SUMMARY ---")
        output_lines.append(f"Total underutilized modules: {results['summary']['total_underutilized']}")
        output_lines.append(f"Total orphan capabilities: {results['summary']['total_orphans']}")
        output_lines.append("=" * 60)

        return "\n".join(output_lines)


# Example usage (for testing purposes)
if __name__ == "__main__":
    # Sample usage data (last 20 cycles)
    sample_usage = [
        {'module': 'auth_service', 'capability': 'user_auth', 'timestamp': '2023-01-01T00:00:00Z', 'cycle': 100},
        {'module': 'auth_service', 'capability': 'user_auth', 'timestamp': '2023-01-01T01:00:00Z', 'cycle': 100},
        {'module': 'data_processor', 'capability': 'data_transform', 'timestamp': '2023-01-01T02:00:00Z', 'cycle': 100},
        {'module': 'legacy_module', 'capability': 'old_api', 'timestamp': '2023-01-01T03:00:00Z', 'cycle': 99},
        {'module': 'new_feature', 'capability': 'new_api', 'timestamp': '2023-01-01T04:00:00Z', 'cycle': 98},
        # Add more sample data as needed
    ]

    # Sample capability registry
    sample_registry = {
        'user_auth': 'auth_service',
        'data_transform': 'data_processor',
        'old_api': 'legacy_module',
        'new_api': 'new_feature',
        'unused_capability': 'orphan_module'  # This capability is never referenced
    }

    scanner = UnderutilizedComponentScanner(sample_usage, sample_registry)
    print(scanner.generate_dashboard_output())