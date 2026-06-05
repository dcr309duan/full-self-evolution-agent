"""
system_health_audit.py

Provides meta-cognitive health metrics for an evolving system.
Tracks mutation rate, acceptance threshold, brittleness, parameter adjustment frequency,
and flags stuck-at-extreme parameters.
"""

import time
from collections import deque
from typing import Dict, List, Optional, Tuple

# Default configuration
DEFAULT_MUTATION_RATE = 0.1
DEFAULT_ACCEPTANCE_THRESHOLD = 0.7
BRITTLENESS_THRESHOLD = 0.8  # If mutation rate > this, system is brittle
EXTREME_LOW = 0.01
EXTREME_HIGH = 0.99
ADJUSTMENT_WINDOW = 30  # cycles

class SystemHealthAudit:
    """
    Tracks and reports meta-cognitive health metrics for an evolving system.
    """

    def __init__(self, mutation_rate: float = DEFAULT_MUTATION_RATE,
                 acceptance_threshold: float = DEFAULT_ACCEPTANCE_THRESHOLD):
        self.mutation_rate = mutation_rate
        self.acceptance_threshold = acceptance_threshold
        self.parameter_adjustments: deque = deque(maxlen=ADJUSTMENT_WINDOW)
        self.cycle_count = 0

    def record_adjustment(self, parameter_name: str, old_value: float, new_value: float) -> None:
        """Record a parameter adjustment with timestamp."""
        self.parameter_adjustments.append({
            'parameter': parameter_name,
            'old_value': old_value,
            'new_value': new_value,
            'cycle': self.cycle_count,
            'timestamp': time.time()
        })

    def increment_cycle(self) -> None:
        """Increment the cycle counter."""
        self.cycle_count += 1

    def get_brittleness_status(self) -> str:
        """
        Report brittleness status based on mutation rate.
        Returns one of: 'stable', 'moderate', 'brittle'
        """
        if self.mutation_rate < 0.3:
            return 'stable'
        elif self.mutation_rate < BRITTLENESS_THRESHOLD:
            return 'moderate'
        else:
            return 'brittle'

    def get_adjustment_count_last_30(self) -> int:
        """Return number of parameter adjustments in last 30 cycles."""
        cutoff_cycle = self.cycle_count - ADJUSTMENT_WINDOW
        return sum(1 for adj in self.parameter_adjustments if adj['cycle'] >= cutoff_cycle)

    def get_stuck_parameters(self) -> List[Dict]:
        """
        Flag parameters stuck at extreme values (near 0 or 1).
        Returns list of dicts with parameter name and current value.
        """
        stuck = []
        # Check mutation_rate
        if self.mutation_rate <= EXTREME_LOW or self.mutation_rate >= EXTREME_HIGH:
            stuck.append({
                'parameter': 'mutation_rate',
                'value': self.mutation_rate,
                'extreme': 'low' if self.mutation_rate <= EXTREME_LOW else 'high'
            })
        # Check acceptance_threshold
        if self.acceptance_threshold <= EXTREME_LOW or self.acceptance_threshold >= EXTREME_HIGH:
            stuck.append({
                'parameter': 'acceptance_threshold',
                'value': self.acceptance_threshold,
                'extreme': 'low' if self.acceptance_threshold <= EXTREME_LOW else 'high'
            })
        return stuck

    def generate_health_report(self) -> Dict:
        """
        Generate a comprehensive health report with all meta-cognitive metrics.
        """
        report = {
            'mutation_rate': self.mutation_rate,
            'acceptance_threshold': self.acceptance_threshold,
            'brittleness_status': self.get_brittleness_status(),
            'adjustments_last_30_cycles': self.get_adjustment_count_last_30(),
            'total_adjustments_recorded': len(self.parameter_adjustments),
            'stuck_parameters': self.get_stuck_parameters(),
            'cycle_count': self.cycle_count
        }
        return report

    def update_parameters(self, new_mutation_rate: Optional[float] = None,
                          new_acceptance_threshold: Optional[float] = None) -> None:
        """
        Update system parameters and record adjustments.
        """
        if new_mutation_rate is not None and new_mutation_rate != self.mutation_rate:
            self.record_adjustment('mutation_rate', self.mutation_rate, new_mutation_rate)
            self.mutation_rate = new_mutation_rate

        if new_acceptance_threshold is not None and new_acceptance_threshold != self.acceptance_threshold:
            self.record_adjustment('acceptance_threshold', self.acceptance_threshold, new_acceptance_threshold)
            self.acceptance_threshold = new_acceptance_threshold


# Example usage (if run as script)
if __name__ == "__main__":
    auditor = SystemHealthAudit()
    # Simulate some cycles and adjustments
    for i in range(35):
        auditor.increment_cycle()
        if i % 5 == 0:
            auditor.update_parameters(
                new_mutation_rate=0.1 + (i * 0.02),
                new_acceptance_threshold=0.7 - (i * 0.01)
            )
    # Generate and print report
    report = auditor.generate_health_report()
    for key, value in report.items():
        print(f"{key}: {value}")