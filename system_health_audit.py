"""
system_health_audit.py

Provides meta-cognitive health metrics for an evolving system.
Tracks mutation rate, acceptance threshold, brittleness, parameter adjustment frequency,
flags stuck-at-extreme parameters, and includes conflict resolution metrics.
Also includes atomic write failure metrics and auto-generated fix success rate metrics.
Also tracks sandboxed mutation metrics: number of sandboxed mutations attempted,
number that passed tests, number that failed tests, number that required rollback.
Also tracks sleep cycle cleanup impact: number of modules deleted, number of functions consolidated,
total LOC freed, and timestamp of last sleep cycle.
Also includes capability audit to flag capabilities accepted without test-first verification.
Also tracks core stability score based on minimal core E2E test results.
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
FIX_EFFECTIVENESS_WINDOW = 30  # cycles for fix effectiveness tracking
CORE_STABILITY_WINDOW = 10  # cycles for core stability tracking
CORE_STABILITY_THRESHOLD = 0.9  # threshold for core stability alert

class SystemHealthAudit:
    """
    Tracks and reports meta-cognitive health metrics for an evolving system.
    Includes conflict resolution metrics, atomic write failure metrics,
    auto-generated fix effectiveness metrics, sandboxed mutation metrics,
    sleep cycle cleanup impact metrics, capability audit metrics,
    and core stability metrics.
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

        # Auto-generated fix effectiveness tracking
        self.fix_log: deque = deque(maxlen=1000)  # Store recent fixes
        self.fixes_last_30: deque = deque(maxlen=FIX_EFFECTIVENESS_WINDOW)
        self.total_fixes_applied: int = 0
        self.fixes_prevented_failures: int = 0

        # Sandboxed mutation tracking
        self.sandboxed_mutations_attempted: int = 0
        self.sandboxed_mutations_passed: int = 0
        self.sandboxed_mutations_failed: int = 0
        self.sandboxed_mutations_rollback: int = 0

        # Sleep cycle cleanup impact tracking
        self.sleep_cycle_cleanup_impact = {
            'modules_deleted': 0,
            'functions_consolidated': 0,
            'total_loc_freed': 0,
            'last_sleep_cycle_timestamp': None
        }

        # Capability audit tracking
        self.capability_log: deque = deque(maxlen=1000)  # Store all capabilities
        self.capabilities_without_tests: Dict[str, Dict] = {}  # Capabilities accepted without test-first verification

        # Core stability tracking
        self.core_e2e_results: deque = deque(maxlen=CORE_STABILITY_WINDOW)  # Store recent core E2E test results

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

    def record_fix(self, module: str, fix_type: str, prevented_failure: bool = False) -> None:
        """
        Record an auto-generated fix event.
        
        Args:
            module: The module where fix was applied
            fix_type: Type of fix applied (e.g., 'parameter_adjustment', 'conflict_resolution', 'rollback')
            prevented_failure: Whether the fix prevented a subsequent failure
        """
        fix_entry = {
            'module': module,
            'type': fix_type,
            'prevented_failure': prevented_failure,
            'cycle': self.cycle_count,
            'timestamp': time.time()
        }
        self.fix_log.append(fix_entry)
        
        # Track in last 30 cycles
        if self.cycle_count > 0:
            self.fixes_last_30.append(fix_entry)
        
        # Track fix statistics
        self.total_fixes_applied += 1
        if prevented_failure:
            self.fixes_prevented_failures += 1

    def record_sandboxed_mutation(self, outcome: str) -> None:
        """
        Record a sandboxed mutation attempt and its outcome.
        
        Args:
            outcome: The outcome of the sandboxed mutation.
                     Must be one of: 'passed', 'failed', 'rollback'
        """
        self.sandboxed_mutations_attempted += 1
        if outcome == 'passed':
            self.sandboxed_mutations_passed += 1
        elif outcome == 'failed':
            self.sandboxed_mutations_failed += 1
        elif outcome == 'rollback':
            self.sandboxed_mutations_rollback += 1
        else:
            raise ValueError(f"Invalid outcome: {outcome}. Must be 'passed', 'failed', or 'rollback'.")

    def record_sleep_cycle_cleanup(self, modules_deleted: int, functions_consolidated: int, loc_freed: int) -> None:
        """
        Record the impact of a sleep cycle cleanup.
        
        Args:
            modules_deleted: Number of modules deleted during cleanup
            functions_consolidated: Number of functions consolidated during cleanup
            loc_freed: Total lines of code freed during cleanup
        """
        self.sleep_cycle_cleanup_impact['modules_deleted'] += modules_deleted
        self.sleep_cycle_cleanup_impact['functions_consolidated'] += functions_consolidated
        self.sleep_cycle_cleanup_impact['total_loc_freed'] += loc_freed
        self.sleep_cycle_cleanup_impact['last_sleep_cycle_timestamp'] = time.time()

    def record_capability(self, capability_name: str, accepted: bool, test_first_verified: bool = False) -> None:
        """
        Record a capability and whether it was accepted with test-first verification.
        
        Args:
            capability_name: Name of the capability
            accepted: Whether the capability was accepted
            test_first_verified: Whether the capability was verified with test-first approach
        """
        capability_entry = {
            'capability': capability_name,
            'accepted': accepted,
            'test_first_verified': test_first_verified,
            'cycle': self.cycle_count,
            'timestamp': time.time()
        }
        self.capability_log.append(capability_entry)
        
        # Track capabilities accepted without test-first verification
        if accepted and not test_first_verified:
            self.capabilities_without_tests[capability_name] = capability_entry

    def record_core_e2e_result(self, successful: bool) -> None:
        """
        Record the result of a minimal core E2E test run.
        
        Args:
            successful: Whether the core E2E test run was successful
        """
        self.core_e2e_results.append({
            'successful': successful,
            'cycle': self.cycle_count,
            'timestamp': time.time()
        })

    def get_core_stability_score(self) -> float:
        """
        Calculate the core stability score as the ratio of successful minimal core E2E test runs
        to total cycles in the last CORE_STABILITY_WINDOW cycles.
        
        Returns:
            Float between 0 and 1 representing the stability score, or 1.0 if no data
        """
        if len(self.core_e2e_results) == 0:
            return 1.0
        
        successful = sum(1 for result in self.core_e2e_results if result['successful'])
        return successful / len(self.core_e2e_results)

    def audit_capabilities_without_tests(self) -> List[Dict]:
        """
        Audit all capabilities in the knowledge base and flag any that were accepted
        without a corresponding test-first verification.
        
        Returns:
            List of capability entries that were accepted without test-first verification
        """
        return list(self.capabilities_without_tests.values())

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

    def get_fix_count_last_30(self) -> int:
        """Return number of auto-generated fixes applied in last 30 cycles."""
        cutoff_cycle = self.cycle_count - FIX_EFFECTIVENESS_WINDOW
        return sum(1 for f in self.fix_log if f['cycle'] >= cutoff_cycle)

    def get_fix_success_rate(self) -> float:
        """
        Calculate success rate of auto-generated fixes (fixes that prevented subsequent failures vs total fixes applied).
        Returns a float between 0 and 1, or 0 if no fixes applied.
        """
        if self.total_fixes_applied == 0:
            return 0.0
        return self.fixes_prevented_failures / self.total_fixes_applied

    def get_fix_success_rate_last_30(self) -> float:
        """
        Calculate success rate of auto-generated fixes in last 30 cycles.
        Returns a float between 0 and 1, or 0 if no fixes applied in that window.
        """
        cutoff_cycle = self.cycle_count - FIX_EFFECTIVENESS_WINDOW
        recent_fixes = [f for f in self.fix_log if f['cycle'] >= cutoff_cycle]
        
        if not recent_fixes:
            return 0.0
        
        prevented = sum(1 for f in recent_fixes if f['prevented_failure'])
        return prevented / len(recent_fixes)

    def get_modules_with_high_fix_failures(self) -> List[str]:
        """
        Return list of modules with >2 fixes that did NOT prevent failures in last 30 cycles.
        """
        cutoff_cycle = self.cycle_count - FIX_EFFECTIVENESS_WINDOW
        recent_fixes = [f for f in self.fix_log if f['cycle'] >= cutoff_cycle and not f['prevented_failure']]
        
        module_failure_count = {}
        for fix in recent_fixes:
            module = fix['module']
            module_failure_count[module] = module_failure_count.get(module, 0) + 1
        
        return [module for module, count in module_failure_count.items() if count > 2]

    def get_fix_log_summary(self) -> List[Dict]:
        """Return a summary of recent fix log entries."""
        cutoff_cycle = self.cycle_count - FIX_EFFECTIVENESS_WINDOW
        recent_fixes = [f for f in self.fix_log if f['cycle'] >= cutoff_cycle]
        
        # Group by module and fix type
        summary = {}
        for fix in recent_fixes:
            module = fix['module']
            if module not in summary:
                summary[module] = {
                    'module': module,
                    'total_fixes': 0,
                    'parameter_adjustment': 0,
                    'conflict_resolution': 0,
                    'rollback': 0,
                    'other': 0,
                    'prevented_failure': 0,
                    'did_not_prevent': 0,
                    'last_fix': None
                }
            summary[module]['total_fixes'] += 1
            if fix['type'] == 'parameter_adjustment':
                summary[module]['parameter_adjustment'] += 1
            elif fix['type'] == 'conflict_resolution':
                summary[module]['conflict_resolution'] += 1
            elif fix['type'] == 'rollback':
                summary[module]['rollback'] += 1
            else:
                summary[module]['other'] += 1
            
            if fix['prevented_failure']:
                summary[module]['prevented_failure'] += 1
            else:
                summary[module]['did_not_prevent'] += 1
            
            if summary[module]['last_fix'] is None or fix['timestamp'] > summary[module]['last_fix']['timestamp']:
                summary[module]['last_fix'] = fix
        
        return list(summary.values())

    def get_sandboxed_mutation_metrics(self) -> Dict:
        """
        Return sandboxed mutation metrics.
        """
        return {
            'sandboxed_mutations_attempted': self.sandboxed_mutations_attempted,
            'sandboxed_mutations_passed': self.sandboxed_mutations_passed,
            'sandboxed_mutations_failed': self.sandboxed_mutations_failed,
            'sandboxed_mutations_rollback': self.sandboxed_mutations_rollback
        }

    def get_sleep_cycle_cleanup_impact(self) -> Dict:
        """
        Return sleep cycle cleanup impact metrics.
        """
        return {
            'modules_deleted': self.sleep_cycle_cleanup_impact['modules_deleted'],
            'functions_consolidated': self.sleep_cycle_cleanup_impact['functions_consolidated'],
            'total_loc_freed': self.sleep_cycle_cleanup_impact['total_loc_freed'],
            'last_sleep_cycle_timestamp': self.sleep_cycle_cleanup_impact['last_sleep_cycle_timestamp']
        }

    def generate_health_report(self) -> Dict:
        """
        Generate a comprehensive health report with all meta-cognitive metrics
        including conflict resolution metrics, atomic write failure metrics,
        auto-generated fix effectiveness metrics, sandboxed mutation metrics,
        sleep cycle cleanup impact metrics, capability audit metrics,
        and core stability metrics.
        """
        conflict_count = self.get_conflict_count_last_30()
        resolution_rate = self.get_conflict_resolution_success_rate()
        modules_with_high_unresolved = self.get_modules_with_unresolved_conflicts()
        
        write_failure_count = self.get_write_failure_count_last_30()
        rollback_success_rate = self.get_rollback_success_rate()
        modules_with_high_write_failures = self.get_modules_with_high_write_failures()
        
        fix_count = self.get_fix_count_last_30()
        fix_success_rate = self.get_fix_success_rate()
        fix_success_rate_last_30 = self.get_fix_success_rate_last_30()
        modules_with_high_fix_failures = self.get_modules_with_high_fix_failures()
        
        sandboxed_metrics = self.get_sandboxed_mutation_metrics()
        sleep_cycle_impact = self.get_sleep_cycle_cleanup_impact()
        
        # Capability audit
        capabilities_without_tests = self.audit_capabilities_without_tests()
        
        # Core stability
        core_stability_score = self.get_core_stability_score()
        core_stability_alert = core_stability_score < CORE_STABILITY_THRESHOLD
        core_stability_recommendation = None
        if core_stability_alert:
            core_stability_recommendation = "CRITICAL: Core stability score below 0.9. Recommend pausing all non-essential mutations."
        
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
            'write_failure_log_summary': self.get_write_failure_log_summary(),
            # Auto-generated fix effectiveness metrics
            'fixes_applied_last_30_cycles': fix_count,
            'fix_success_rate_overall': fix_success_rate,
            'fix_success_rate_last_30_cycles': fix_success_rate_last_30,
            'total_fixes_applied': self.total_fixes_applied,
            'fixes_prevented_failures': self.fixes_prevented_failures,
            'modules_with_high_fix_failures': modules_with_high_fix_failures,
            'fix_log_summary': self.get_fix_log_summary(),
            # Sandboxed mutation metrics
            'sandboxed_mutations_attempted': sandboxed_metrics['sandboxed_mutations_attempted'],
            'sandboxed_mutations_passed': sandboxed_metrics['sandboxed_mutations_passed'],
            'sandboxed_mutations_failed': sandboxed_metrics['sandboxed_mutations_failed'],
            'sandboxed_mutations_rollback': sandboxed_metrics['sandboxed_mutations_rollback'],
            # Sleep cycle cleanup impact metrics
            'sleep_cycle_cleanup_impact': sleep_cycle_impact,
            # Capability audit metrics
            'capabilities_accepted_without_tests': capabilities_without_tests,
            'capabilities_without_tests_count': len(capabilities_without_tests),
            # Core stability metrics
            'core_stability_score': core_stability_score,
            'core_stability_alert': core_stability_alert,
            'core_stability_recommendation': core_stability_recommendation
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
        # Simulate some auto-generated fixes
        if i % 2 == 0:
            auditor.record_fix('module_a', 'parameter_adjustment', prevented_failure=(i % 4 == 0))
        if i % 3 == 0:
            auditor.record_fix('module_b', 'conflict_resolution', prevented_failure=(i % 5 == 0))
        # Simulate some sandboxed mutations
        if i % 2 == 0:
            auditor.record_sandboxed_mutation('passed' if i % 3 != 0 else 'failed')
        if i % 5 == 0:
            auditor.record_sandboxed_mutation('rollback')
        # Simulate some sleep cycle cleanups
        if i % 10 == 0:
            auditor.record_sleep_cycle_cleanup(
                modules_deleted=i // 10,
                functions_consolidated=i // 5,
                loc_freed=i * 10
            )
        # Simulate some capability recordings
        if i % 4 == 0:
            auditor.record_capability(f'capability_{i}', accepted=True, test_first_verified=(i % 3 == 0))
        if i % 7 == 0:
            auditor.record_capability(f'legacy_capability_{i}', accepted=True, test_first_verified=False)
        # Simulate core E2E test results
        if i % 2 == 0:
            auditor.record_core_e2e_result(successful=(i % 5 != 0))
        else:
            auditor.record_core_e2e_result(successful=(i % 3 == 0))
    
    # Generate and print report
    report = auditor.generate_health_report()
    for key, value in report.items():
        print(f"{key}: {value}")