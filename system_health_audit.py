"""
system_health_audit.py

Provides meta-cognitive health metrics for an evolving system.
Tracks mutation rate, acceptance threshold, brittleness, parameter adjustment frequency,
flags stuck-at-extreme parameters, and includes conflict resolution metrics.
Also includes atomic write failure metrics.
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
CONFLICT_WINDOW = 30  # cycles for conflict tracking
WRITE_FAILURE_WINDOW = 30  # cycles for write failure tracking

class SystemHealthAudit:
    """
    Tracks and reports meta-cognitive health metrics for an evolving system.
    Includes conflict resolution metrics and atomic write failure metrics for health audit.
    """

    def __init__(self, mutation_rate: float = DEFAULT_MUTATION_RATE,
                 acceptance_threshold: float = DEFAULT_ACCEPTANCE_THRESHOLD):
        self.mutation_rate = mutation_rate
        self.acceptance_threshold = acceptance_threshold
        self.parameter_adjustments: deque = deque(maxlen=ADJUSTMENT_WINDOW)
        self.cycle_count = 0
        
        # Conflict tracking
        self.conflict_log: deque = deque(maxlen=1000)  # Store recent conflicts
        self.conflicts_last_30: deque = deque(maxlen=CONFLICT_WINDOW)
        self.snapshots_per_module: Dict[str, int] = {}
        self.unresolved_conflicts: Dict[str, int] = {}

        # Atomic write failure tracking
        self.write_failure_log: deque = deque(maxlen=1000)  # Store recent write failures
        self.write_failures_last_30: deque = deque(maxlen=WRITE_FAILURE_WINDOW)
        self.rollback_attempts: int = 0
        self.rollback_successes: int = 0

    def record_adjustment(self, parameter_name: str, old_value: float, new_value: float) -> None:
        """Record a parameter adjustment with timestamp."""
        self.parameter_adjustments.append({
            'parameter': parameter_name,
            'old_value': old_value,
            'new_value': new_value,
            'cycle': self.cycle_count,
            'timestamp': time.time()
        })

    def record_conflict(self, module: str, conflict_type: str, resolution: str = None) -> None:
        """
        Record a conflict event.
        
        Args:
            module: The module where conflict occurred
            conflict_type: Type of conflict (e.g., 'merge', 'dependency', 'version')
            resolution: Resolution method ('auto_merged', 'reverted', 'pending')
        """
        conflict_entry = {
            'module': module,
            'type': conflict_type,
            'resolution': resolution,
            'cycle': self.cycle_count,
            'timestamp': time.time()
        }
        self.conflict_log.append(conflict_entry)
        
        # Track in last 30 cycles
        if self.cycle_count > 0:
            self.conflicts_last_30.append(conflict_entry)
        
        # Update unresolved conflicts count
        if resolution == 'pending' or resolution is None:
            self.unresolved_conflicts[module] = self.unresolved_conflicts.get(module, 0) + 1
        elif resolution in ('auto_merged', 'reverted'):
            # Decrement unresolved count if it was previously unresolved
            if module in self.unresolved_conflicts and self.unresolved_conflicts[module] > 0:
                self.unresolved_conflicts[module] -= 1

    def record_snapshot(self, module: str) -> None:
        """Record a snapshot stored for a module."""
        self.snapshots_per_module[module] = self.snapshots_per_module.get(module, 0) + 1

    def record_write_failure(self, module: str, failure_type: str, rollback_successful: bool = False) -> None:
        """
        Record an atomic write failure event.
        
        Args:
            module: The module where write failure occurred
            failure_type: Type of write failure (e.g., 'disk_full', 'permission_denied', 'corruption')
            rollback_successful: Whether the rollback was successful
        """
        failure_entry = {
            'module': module,
            'type': failure_type,
            'rollback_successful': rollback_successful,
            'cycle': self.cycle_count,
            'timestamp': time.time()
        }
        self.write_failure_log.append(failure_entry)
        
        # Track in last 30 cycles
        if self.cycle_count > 0:
            self.write_failures_last_30.append(failure_entry)
        
        # Track rollback statistics
        self.rollback_attempts += 1
        if rollback_successful:
            self.rollback_successes += 1

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

    def get_conflict_count_last_30(self) -> int:
        """Return number of conflicts detected in last 30 cycles."""
        cutoff_cycle = self.cycle_count - CONFLICT_WINDOW
        return sum(1 for c in self.conflict_log if c['cycle'] >= cutoff_cycle)

    def get_conflict_resolution_success_rate(self) -> float:
        """
        Calculate conflict resolution success rate (auto-merged vs reverted).
        Returns a float between 0 and 1, or 0 if no conflicts resolved.
        """
        cutoff_cycle = self.cycle_count - CONFLICT_WINDOW
        resolved = [c for c in self.conflict_log if c['cycle'] >= cutoff_cycle and c['resolution'] in ('auto_merged', 'reverted')]
        
        if not resolved:
            return 0.0
        
        auto_merged = sum(1 for c in resolved if c['resolution'] == 'auto_merged')
        return auto_merged / len(resolved)

    def get_snapshots_per_module(self) -> Dict[str, int]:
        """Return number of snapshots stored per critical module."""
        return dict(self.snapshots_per_module)

    def get_modules_with_unresolved_conflicts(self) -> List[str]:
        """Return list of modules with >3 unresolved conflicts."""
        return [module for module, count in self.unresolved_conflicts.items() if count > 3]

    def get_conflict_log_summary(self) -> List[Dict]:
        """Return a summary of recent conflict log entries."""
        cutoff_cycle = self.cycle_count - CONFLICT_WINDOW
        recent_conflicts = [c for c in self.conflict_log if c['cycle'] >= cutoff_cycle]
        
        # Group by module and resolution type
        summary = {}
        for conflict in recent_conflicts:
            module = conflict['module']
            if module not in summary:
                summary[module] = {
                    'module': module,
                    'total_conflicts': 0,
                    'auto_merged': 0,
                    'reverted': 0,
                    'pending': 0,
                    'last_conflict': None
                }
            summary[module]['total_conflicts'] += 1
            if conflict['resolution'] == 'auto_merged':
                summary[module]['auto_merged'] += 1
            elif conflict['resolution'] == 'reverted':
                summary[module]['reverted'] += 1
            elif conflict['resolution'] == 'pending' or conflict['resolution'] is None:
                summary[module]['pending'] += 1
            
            if summary[module]['last_conflict'] is None or conflict['timestamp'] > summary[module]['last_conflict']['timestamp']:
                summary[module]['last_conflict'] = conflict
        
        return list(summary.values())

    def get_write_failure_count_last_30(self) -> int:
        """Return number of write failures in last 30 cycles."""
        cutoff_cycle = self.cycle_count - WRITE_FAILURE_WINDOW
        return sum(1 for f in self.write_failure_log if f['cycle'] >= cutoff_cycle)

    def get_rollback_success_rate(self) -> float:
        """
        Calculate rollback success rate.
        Returns a float between 0 and 1, or 0 if no rollback attempts.
        """
        if self.rollback_attempts == 0:
            return 0.0
        return self.rollback_successes / self.rollback_attempts

    def get_modules_with_high_write_failures(self) -> List[str]:
        """
        Return list of modules with >2 write failures in last 30 cycles.
        """
        cutoff_cycle = self.cycle_count - WRITE_FAILURE_WINDOW
        recent_failures = [f for f in self.write_failure_log if f['cycle'] >= cutoff_cycle]
        
        module_failure_count = {}
        for failure in recent_failures:
            module = failure['module']
            module_failure_count[module] = module_failure_count.get(module, 0) + 1
        
        return [module for module, count in module_failure_count.items() if count > 2]

    def get_write_failure_log_summary(self) -> List[Dict]:
        """Return a summary of recent write failure log entries."""
        cutoff_cycle = self.cycle_count - WRITE_FAILURE_WINDOW
        recent_failures = [f for f in self.write_failure_log if f['cycle'] >= cutoff_cycle]
        
        # Group by module and failure type
        summary = {}
        for failure in recent_failures:
            module = failure['module']
            if module not in summary:
                summary[module] = {
                    'module': module,
                    'total_failures': 0,
                    'disk_full': 0,
                    'permission_denied': 0,
                    'corruption': 0,
                    'other': 0,
                    'rollback_successful': 0,
                    'rollback_failed': 0,
                    'last_failure': None
                }
            summary[module]['total_failures'] += 1
            if failure['type'] == 'disk_full':
                summary[module]['disk_full'] += 1
            elif failure['type'] == 'permission_denied':
                summary[module]['permission_denied'] += 1
            elif failure['type'] == 'corruption':
                summary[module]['corruption'] += 1
            else:
                summary[module]['other'] += 1
            
            if failure['rollback_successful']:
                summary[module]['rollback_successful'] += 1
            else:
                summary[module]['rollback_failed'] += 1
            
            if summary[module]['last_failure'] is None or failure['timestamp'] > summary[module]['last_failure']['timestamp']:
                summary[module]['last_failure'] = failure
        
        return list(summary.values())

    def generate_health_report(self) -> Dict:
        """
        Generate a comprehensive health report with all meta-cognitive metrics
        including conflict resolution metrics and atomic write failure metrics.
        """
        conflict_count = self.get_conflict_count_last_30()
        resolution_rate = self.get_conflict_resolution_success_rate()
        modules_with_high_unresolved = self.get_modules_with_unresolved_conflicts()
        
        write_failure_count = self.get_write_failure_count_last_30()
        rollback_success_rate = self.get_rollback_success_rate()
        modules_with_high_write_failures = self.get_modules_with_high_write_failures()
        
        report = {
            'mutation_rate': self.mutation_rate,
            'acceptance_threshold': self.acceptance_threshold,
            'brittleness_status': self.get_brittleness_status(),
            'adjustments_last_30_cycles': self.get_adjustment_count_last_30(),
            'total_adjustments_recorded': len(self.parameter_adjustments),
            'stuck_parameters': self.get_stuck_parameters(),
            'cycle_count': self.cycle_count,
            # Conflict resolution metrics
            'conflicts_detected_last_30_cycles': conflict_count,
            'conflict_resolution_success_rate': resolution_rate,
            'snapshots_per_module': self.get_snapshots_per_module(),
            'modules_with_high_unresolved_conflicts': modules_with_high_unresolved,
            'conflict_log_summary': self.get_conflict_log_summary(),
            # Atomic write failure metrics
            'write_failures_last_30_cycles': write_failure_count,
            'rollback_success_rate': rollback_success_rate,
            'modules_with_high_write_failures': modules_with_high_write_failures,
            'write_failure_log_summary': self.get_write_failure_log_summary()
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
        # Simulate some conflicts
        if i % 3 == 0:
            auditor.record_conflict('module_a', 'merge', 'auto_merged' if i % 2 == 0 else 'reverted')
        if i % 7 == 0:
            auditor.record_conflict('module_b', 'dependency', 'pending')
        # Record some snapshots
        if i % 4 == 0:
            auditor.record_snapshot('module_a')
        if i % 6 == 0:
            auditor.record_snapshot('module_b')
        # Simulate some write failures
        if i % 5 == 0:
            auditor.record_write_failure('module_a', 'disk_full', rollback_successful=(i % 3 != 0))
        if i % 8 == 0:
            auditor.record_write_failure('module_b', 'corruption', rollback_successful=(i % 2 == 0))
    
    # Generate and print report
    report = auditor.generate_health_report()
    for key, value in report.items():
        print(f"{key}: {value}")