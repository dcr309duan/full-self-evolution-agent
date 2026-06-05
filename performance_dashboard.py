"""performance_dashboard.py

A lightweight dashboard module that aggregates data from performance_monitor,
self_diagnosis_module, and fragility_hotspot_miner, and generates summary
reports every 10 cycles with top bottlenecks, trend direction, and actions.
"""

import time
import logging
from collections import defaultdict
from typing import Dict, List, Tuple, Optional

# Attempt to import the monitoring modules (graceful fallback if not available)
try:
    from performance_monitor import PerformanceMonitor
except ImportError:
    PerformanceMonitor = None

try:
    from self_diagnosis_module import SelfDiagnosisModule
except ImportError:
    SelfDiagnosisModule = None

try:
    from fragility_hotspot_miner import FragilityHotspotMiner
except ImportError:
    FragilityHotspotMiner = None

logger = logging.getLogger(__name__)


class PerformanceDashboard:
    """Aggregates data and generates text-based summary reports every N cycles."""

    def __init__(self, report_interval: int = 10):
        """
        Initialize the dashboard.

        Args:
            report_interval: Number of cycles between summary reports.
        """
        self.report_interval = report_interval
        self.cycle_count = 0

        # Data stores
        self.performance_data: List[Dict] = []
        self.diagnosis_data: List[Dict] = []
        self.fragility_data: List[Dict] = []

        # Trend tracking
        self.previous_metrics: Optional[Dict[str, float]] = None
        self.trend_direction: str = "stable"

        # Sub-module instances (lazy init)
        self._perf_monitor = None
        self._diagnosis = None
        self._hotspot_miner = None

    def _init_modules(self):
        """Initialize sub-modules if available."""
        if PerformanceMonitor is not None and self._perf_monitor is None:
            self._perf_monitor = PerformanceMonitor()
        if SelfDiagnosisModule is not None and self._diagnosis is None:
            self._diagnosis = SelfDiagnosisModule()
        if FragilityHotspotMiner is not None and self._hotspot_miner is None:
            self._hotspot_miner = FragilityHotspotMiner()

    def collect_data(self):
        """Collect current data from all available modules."""
        self._init_modules()
        current_time = time.time()

        # Collect performance data
        if self._perf_monitor:
            try:
                perf = self._perf_monitor.get_metrics()
                self.performance_data.append({"time": current_time, "data": perf})
            except Exception as e:
                logger.warning(f"Failed to collect performance data: {e}")

        # Collect self-diagnosis data
        if self._diagnosis:
            try:
                diag = self._diagnosis.run_diagnostics()
                self.diagnosis_data.append({"time": current_time, "data": diag})
            except Exception as e:
                logger.warning(f"Failed to collect diagnosis data: {e}")

        # Collect fragility hotspot data
        if self._hotspot_miner:
            try:
                frag = self._hotspot_miner.mine_hotspots()
                self.fragility_data.append({"time": current_time, "data": frag})
            except Exception as e:
                logger.warning(f"Failed to collect fragility data: {e}")

    def _compute_trend(self) -> str:
        """
        Determine overall trend direction based on recent performance metrics.

        Returns:
            'improving', 'declining', or 'stable'
        """
        if len(self.performance_data) < 2:
            return "stable"

        # Use last two entries for trend
        current = self.performance_data[-1]["data"]
        previous = self.performance_data[-2]["data"]

        # Compare key metrics (e.g., execution_time, error_rate, resource_usage)
        improving_count = 0
        declining_count = 0

        for key in ["execution_time", "error_rate", "cpu_usage", "memory_usage"]:
            if key in current and key in previous:
                if current[key] < previous[key]:
                    improving_count += 1
                elif current[key] > previous[key]:
                    declining_count += 1

        if improving_count > declining_count:
            return "improving"
        elif declining_count > improving_count:
            return "declining"
        else:
            return "stable"

    def _get_top_bottlenecks(self, n: int = 3) -> List[Tuple[str, float]]:
        """
        Identify top N performance bottlenecks from collected data.

        Returns:
            List of (bottleneck_name, severity_score) tuples, sorted descending.
        """
        bottlenecks = defaultdict(float)

        # From performance data
        if self.performance_data:
            latest = self.performance_data[-1]["data"]
            # Example: high execution_time, error_rate, resource usage
            if "execution_time" in latest:
                bottlenecks["execution_time"] += latest["execution_time"]
            if "error_rate" in latest:
                bottlenecks["error_rate"] += latest["error_rate"]
            if "cpu_usage" in latest:
                bottlenecks["cpu_usage"] += latest["cpu_usage"]
            if "memory_usage" in latest:
                bottlenecks["memory_usage"] += latest["memory_usage"]

        # From diagnosis data
        if self.diagnosis_data:
            latest_diag = self.diagnosis_data[-1]["data"]
            if "issues" in latest_diag:
                for issue in latest_diag["issues"]:
                    name = issue.get("name", "unknown_issue")
                    severity = issue.get("severity", 0)
                    bottlenecks[name] += severity

        # From fragility data
        if self.fragility_data:
            latest_frag = self.fragility_data[-1]["data"]
            if "hotspots" in latest_frag:
                for hotspot in latest_frag["hotspots"]:
                    name = hotspot.get("component", "unknown_component")
                    risk = hotspot.get("risk_score", 0)
                    bottlenecks[name] += risk

        # Sort and return top N
        sorted_bottlenecks = sorted(bottlenecks.items(), key=lambda x: x[1], reverse=True)
        return sorted_bottlenecks[:n]

    def _generate_recommendations(self, bottlenecks: List[Tuple[str, float]], trend: str) -> List[str]:
        """
        Generate recommended actions based on bottlenecks and trend.

        Args:
            bottlenecks: List of (name, severity) tuples.
            trend: 'improving', 'declining', or 'stable'.

        Returns:
            List of recommendation strings.
        """
        recommendations = []

        if not bottlenecks:
            recommendations.append("No significant bottlenecks detected. Continue monitoring.")
            return recommendations

        # Map bottleneck names to actions
        action_map = {
            "execution_time": "Optimize critical code paths or consider caching.",
            "error_rate": "Investigate recent errors; review exception handling.",
            "cpu_usage": "Scale resources or optimize CPU-intensive operations.",
            "memory_usage": "Check for memory leaks; consider memory profiling.",
        }

        for name, severity in bottlenecks:
            if name in action_map:
                recommendations.append(f"{name} (severity: {severity:.2f}): {action_map[name]}")
            else:
                recommendations.append(f"{name} (severity: {severity:.2f}): Review and address.")

        if trend == "declining":
            recommendations.append("Overall trend is declining. Consider a system review.")
        elif trend == "improving":
            recommendations.append("Overall trend is improving. Continue current optimizations.")

        return recommendations

    def generate_report(self) -> str:
        """
        Generate a text-based summary report.

        Returns:
            Formatted report string.
        """
        self.cycle_count += 1
        self.collect_data()

        if self.cycle_count % self.report_interval != 0:
            return ""  # No report this cycle

        # Compute trend
        self.trend_direction = self._compute_trend()

        # Get top bottlenecks
        top_bottlenecks = self._get_top_bottlenecks(3)

        # Generate recommendations
        recommendations = self._generate_recommendations(top_bottlenecks, self.trend_direction)

        # Build report
        report_lines = []
        report_lines.append("=" * 60)
        report_lines.append(f"PERFORMANCE DASHBOARD REPORT - Cycle {self.cycle_count}")
        report_lines.append("=" * 60)
        report_lines.append(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append("")

        # Trend
        report_lines.append(f"Trend Direction: {self.trend_direction.upper()}")
        report_lines.append("")

        # Top bottlenecks
        report_lines.append("Top 3 Performance Bottlenecks:")
        if top_bottlenecks:
            for i, (name, severity) in enumerate(top_bottlenecks, 1):
                report_lines.append(f"  {i}. {name} (severity: {severity:.2f})")
        else:
            report_lines.append("  (No bottlenecks identified)")
        report_lines.append("")

        # Recommendations
        report_lines.append("Recommended Actions:")
        if recommendations:
            for rec in recommendations:
                report_lines.append(f"  - {rec}")
        else:
            report_lines.append("  (No recommendations)")
        report_lines.append("")

        # Data summary
        report_lines.append(f"Data points collected: perf={len(self.performance_data)}, "
                            f"diag={len(self.diagnosis_data)}, "
                            f"frag={len(self.fragility_data)}")
        report_lines.append("=" * 60)

        return "\n".join(report_lines)

    def run_cycle(self) -> Optional[str]:
        """
        Run one cycle of data collection and report generation.

        Returns:
            Report string if generated, else None.
        """
        report = self.generate_report()
        if report:
            logger.info("Dashboard report generated.")
            print(report)  # For immediate console feedback
            return report
        return None


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    dashboard = PerformanceDashboard(report_interval=10)

    # Simulate 25 cycles
    for _ in range(25):
        dashboard.run_cycle()
        time.sleep(0.1)  # Simulate work