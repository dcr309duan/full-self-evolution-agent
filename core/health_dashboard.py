"""
HealthDashboard module for tracking system health metrics.
Monitors cross-module failures, sandbox errors, rollback frequencies,
and triggers stability lockdown when failure rate exceeds 20%.
"""

from collections import deque
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import threading


class HealthDashboard:
    """
    Tracks system health metrics across modules.
    Maintains a rolling 10-cycle window of failure events and
    triggers stability lockdown when failure rate exceeds 20%.
    """

    def __init__(self, window_size: int = 10):
        self._lock = threading.Lock()
        self._window_size = window_size
        self._failure_events: deque = deque(maxlen=window_size)
        self._lockdown_active = False
        self._lockdown_triggered_at: Optional[datetime] = None
        
        # Module-specific counters
        self._cross_module_failures: List[Dict] = []
        self._sandbox_errors: List[Dict] = []
        self._rollback_events: List[Dict] = []
        
        # Track total events per cycle
        self._total_events = 0
        self._failure_count = 0

    def record_cross_module_failure(self, source_module: str, target_module: str, 
                                   error_type: str, timestamp: Optional[datetime] = None) -> None:
        """Record a cross-module dependency failure from failure_pattern_miner."""
        event = {
            'type': 'cross_module_failure',
            'source': source_module,
            'target': target_module,
            'error_type': error_type,
            'timestamp': timestamp or datetime.now()
        }
        with self._lock:
            self._cross_module_failures.append(event)
            self._record_failure_event(event)

    def record_sandbox_error(self, sandbox_id: str, error_message: str, 
                            error_code: int, timestamp: Optional[datetime] = None) -> None:
        """Record a sandbox execution error from sandbox modules."""
        event = {
            'type': 'sandbox_error',
            'sandbox_id': sandbox_id,
            'error_message': error_message,
            'error_code': error_code,
            'timestamp': timestamp or datetime.now()
        }
        with self._lock:
            self._sandbox_errors.append(event)
            self._record_failure_event(event)

    def record_rollback(self, module_name: str, rollback_reason: str, 
                       rollback_depth: int, timestamp: Optional[datetime] = None) -> None:
        """Record a rollback event from rollback_manager."""
        event = {
            'type': 'rollback',
            'module': module_name,
            'reason': rollback_reason,
            'depth': rollback_depth,
            'timestamp': timestamp or datetime.now()
        }
        with self._lock:
            self._rollback_events.append(event)
            self._record_failure_event(event)

    def _record_failure_event(self, event: Dict) -> None:
        """Internal method to record a failure event in the rolling window."""
        self._failure_events.append(event)
        self._total_events += 1
        self._failure_count += 1
        self._check_lockdown_status()

    def _check_lockdown_status(self) -> None:
        """Check if failure rate exceeds threshold and trigger lockdown if needed."""
        failure_rate = self.get_failure_rate()
        if failure_rate > 20.0 and not self._lockdown_active:
            self._lockdown_active = True
            self._lockdown_triggered_at = datetime.now()

    def get_failure_rate(self) -> float:
        """Calculate real-time failure rate based on rolling window."""
        if len(self._failure_events) == 0:
            return 0.0
        
        # Count failures in current window
        window_failures = len(self._failure_events)
        return (window_failures / self._window_size) * 100.0

    def is_lockdown_active(self) -> bool:
        """Check if stability lockdown is currently active."""
        return self._lockdown_active

    def get_lockdown_trigger_time(self) -> Optional[datetime]:
        """Get the timestamp when lockdown was triggered."""
        return self._lockdown_triggered_at

    def release_lockdown(self) -> bool:
        """Manually release the lockdown status."""
        with self._lock:
            if self._lockdown_active:
                self._lockdown_active = False
                self._lockdown_triggered_at = None
                return True
            return False

    def get_window_failures(self) -> List[Dict]:
        """Get the list of failure events in the current rolling window."""
        return list(self._failure_events)

    def get_module_failure_counts(self) -> Dict[str, int]:
        """Get failure counts per module type."""
        counts = {
            'cross_module_failures': len(self._cross_module_failures),
            'sandbox_errors': len(self._sandbox_errors),
            'rollback_events': len(self._rollback_events)
        }
        return counts

    def get_summary(self) -> Dict:
        """Get a comprehensive summary of the current health status."""
        with self._lock:
            return {
                'lockdown_active': self._lockdown_active,
                'lockdown_triggered_at': self._lockdown_triggered_at,
                'failure_rate': self.get_failure_rate(),
                'window_size': self._window_size,
                'window_failures': len(self._failure_events),
                'total_events': self._total_events,
                'module_counts': self.get_module_failure_counts(),
                'recent_failures': list(self._failure_events)[-5:] if self._failure_events else []
            }

    def reset(self) -> None:
        """Reset all tracking data (useful for testing or manual reset)."""
        with self._lock:
            self._failure_events.clear()
            self._cross_module_failures.clear()
            self._sandbox_errors.clear()
            self._rollback_events.clear()
            self._total_events = 0
            self._failure_count = 0
            self._lockdown_active = False
            self._lockdown_triggered_at = None


# Global dashboard instance for easy import
dashboard = HealthDashboard()