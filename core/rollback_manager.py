"""Rollback Manager for atomic file operations and safe mutation recovery.

Maintains an atomic transaction log for all file writes, implements try/except/finally
wrappers for mutations, and provides rollback capabilities to restore files to their
pre-mutation state on failure. Integrates with the failure pattern miner for diagnostics.
Reports rollback events to health dashboard with cause tracking.
"""

import os
import shutil
import json
import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field, asdict
from contextlib import contextmanager

logger = logging.getLogger(__name__)


@dataclass
class FileSnapshot:
    """Represents a snapshot of a file before mutation."""
    path: str
    original_hash: str
    backup_path: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class TransactionEntry:
    """Single entry in the atomic transaction log."""
    transaction_id: str
    module_name: str
    operation: str
    snapshots: List[FileSnapshot] = field(default_factory=list)
    status: str = "pending"  # pending, committed, rolled_back
    reason: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class RollbackManager:
    """Manages atomic transactions and rollback for file mutations."""

    def __init__(self, backup_dir: str = ".rollback_backups", log_file: str = "transaction_log.json"):
        self.backup_dir = Path(backup_dir)
        self.log_file = Path(log_file)
        self.transaction_log: Dict[str, TransactionEntry] = {}
        self._current_transaction_id: Optional[str] = None
        self._snapshots: List[FileSnapshot] = []
        self._rollback_frequency: Dict[str, int] = {}  # module -> rollback count
        self._ensure_directories()
        self._load_transaction_log()
        self._load_rollback_frequency()

    def _ensure_directories(self) -> None:
        """Ensure backup and log directories exist."""
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

    def _load_transaction_log(self) -> None:
        """Load existing transaction log from disk."""
        if self.log_file.exists():
            try:
                with open(self.log_file, 'r') as f:
                    data = json.load(f)
                    for entry_data in data:
                        entry = TransactionEntry(**entry_data)
                        entry.snapshots = [FileSnapshot(**s) for s in entry_data.get('snapshots', [])]
                        self.transaction_log[entry.transaction_id] = entry
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Failed to load transaction log: {e}")

    def _save_transaction_log(self) -> None:
        """Persist transaction log to disk."""
        data = []
        for entry in self.transaction_log.values():
            entry_dict = asdict(entry)
            entry_dict['snapshots'] = [asdict(s) for s in entry.snapshots]
            data.append(entry_dict)
        with open(self.log_file, 'w') as f:
            json.dump(data, f, indent=2)

    def _load_rollback_frequency(self) -> None:
        """Load rollback frequency data from disk."""
        freq_file = self.backup_dir / "rollback_frequency.json"
        if freq_file.exists():
            try:
                with open(freq_file, 'r') as f:
                    self._rollback_frequency = json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load rollback frequency: {e}")

    def _save_rollback_frequency(self) -> None:
        """Persist rollback frequency data to disk."""
        freq_file = self.backup_dir / "rollback_frequency.json"
        try:
            with open(freq_file, 'w') as f:
                json.dump(self._rollback_frequency, f, indent=2)
        except IOError as e:
            logger.error(f"Failed to save rollback frequency: {e}")

    def _compute_file_hash(self, file_path: str) -> str:
        """Compute SHA-256 hash of a file."""
        hasher = hashlib.sha256()
        try:
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b''):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except FileNotFoundError:
            return ""

    def _create_backup(self, file_path: str) -> Optional[str]:
        """Create a backup copy of a file."""
        if not os.path.exists(file_path):
            return None
        
        backup_name = f"{Path(file_path).name}.{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}.bak"
        backup_path = self.backup_dir / backup_name
        
        try:
            shutil.copy2(file_path, backup_path)
            return str(backup_path)
        except (IOError, OSError) as e:
            logger.error(f"Failed to create backup of {file_path}: {e}")
            return None

    def _restore_from_backup(self, snapshot: FileSnapshot) -> bool:
        """Restore a file from its backup."""
        if not snapshot.backup_path or not os.path.exists(snapshot.backup_path):
            logger.warning(f"No backup available for {snapshot.path}")
            return False
        
        try:
            shutil.copy2(snapshot.backup_path, snapshot.path)
            return True
        except (IOError, OSError) as e:
            logger.error(f"Failed to restore {snapshot.path}: {e}")
            return False

    def begin_transaction(self, module_name: str, operation: str) -> str:
        """Start a new atomic transaction."""
        transaction_id = f"{module_name}_{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"
        entry = TransactionEntry(
            transaction_id=transaction_id,
            module_name=module_name,
            operation=operation
        )
        self.transaction_log[transaction_id] = entry
        self._current_transaction_id = transaction_id
        self._snapshots = []
        logger.info(f"Transaction {transaction_id} started for {module_name}: {operation}")
        return transaction_id

    def snapshot_file(self, file_path: str) -> FileSnapshot:
        """Take a snapshot of a file before mutation."""
        original_hash = self._compute_file_hash(file_path)
        backup_path = self._create_backup(file_path)
        
        snapshot = FileSnapshot(
            path=file_path,
            original_hash=original_hash,
            backup_path=backup_path
        )
        self._snapshots.append(snapshot)
        return snapshot

    def commit_transaction(self, transaction_id: Optional[str] = None) -> bool:
        """Commit the current transaction, marking it as successful."""
        tid = transaction_id or self._current_transaction_id
        if not tid or tid not in self.transaction_log:
            logger.error(f"No active transaction to commit: {tid}")
            return False
        
        entry = self.transaction_log[tid]
        entry.snapshots = self._snapshots
        entry.status = "committed"
        
        # Clean up backups for successful transactions
        for snapshot in self._snapshots:
            if snapshot.backup_path and os.path.exists(snapshot.backup_path):
                try:
                    os.remove(snapshot.backup_path)
                except OSError as e:
                    logger.warning(f"Failed to remove backup {snapshot.backup_path}: {e}")
        
        self._save_transaction_log()
        self._current_transaction_id = None
        self._snapshots = []
        logger.info(f"Transaction {tid} committed successfully")
        return True

    def rollback_transaction(self, transaction_id: Optional[str] = None, reason: Optional[str] = None) -> bool:
        """Rollback a transaction, restoring all files to pre-mutation state."""
        tid = transaction_id or self._current_transaction_id
        if not tid or tid not in self.transaction_log:
            logger.error(f"No transaction to rollback: {tid}")
            return False
        
        entry = self.transaction_log[tid]
        entry.reason = reason
        entry.status = "rolled_back"
        
        # Use the snapshots from the entry or current session
        snapshots = entry.snapshots if entry.snapshots else self._snapshots
        
        success = True
        for snapshot in snapshots:
            if not self._restore_from_backup(snapshot):
                success = False
                logger.error(f"Failed to restore {snapshot.path}")
        
        # Log rollback details
        self._log_rollback(tid, reason, snapshots)
        
        # Integrate with failure pattern miner
        self._notify_failure_pattern_miner(tid, entry.module_name, reason)
        
        # Report to health dashboard
        self._report_to_health_dashboard(tid, entry.module_name, reason, snapshots)
        
        # Track rollback frequency per module
        self._track_rollback_frequency(entry.module_name)
        
        self._save_transaction_log()
        self._save_rollback_frequency()
        self._current_transaction_id = None
        self._snapshots = []
        
        if success:
            logger.info(f"Transaction {tid} rolled back successfully: {reason}")
        else:
            logger.error(f"Transaction {tid} rollback completed with errors: {reason}")
        
        return success

    def _log_rollback(self, transaction_id: str, reason: Optional[str], snapshots: List[FileSnapshot]) -> None:
        """Log rollback reason and affected modules."""
        rollback_log = {
            "timestamp": datetime.utcnow().isoformat(),
            "transaction_id": transaction_id,
            "reason": reason or "No reason provided",
            "affected_files": [s.path for s in snapshots],
            "module": self.transaction_log.get(transaction_id, TransactionEntry("", "", "")).module_name
        }
        
        log_path = self.backup_dir / "rollback_log.json"
        try:
            existing = []
            if log_path.exists():
                with open(log_path, 'r') as f:
                    existing = json.load(f)
            existing.append(rollback_log)
            with open(log_path, 'w') as f:
                json.dump(existing, f, indent=2)
        except (IOError, json.JSONDecodeError) as e:
            logger.error(f"Failed to write rollback log: {e}")

    def _notify_failure_pattern_miner(self, transaction_id: str, module: str, reason: Optional[str]) -> None:
        """Notify the failure pattern miner about a rollback."""
        try:
            from core.failure_pattern_miner import FailurePatternMiner
            miner = FailurePatternMiner()
            miner.record_failure(
                transaction_id=transaction_id,
                module=module,
                error_type="rollback",
                error_message=reason or "Unknown rollback reason",
                timestamp=datetime.utcnow().isoformat()
            )
        except ImportError:
            logger.debug("FailurePatternMiner not available, skipping integration")
        except Exception as e:
            logger.warning(f"Failed to notify failure pattern miner: {e}")

    def _report_to_health_dashboard(self, transaction_id: str, module: str, reason: Optional[str], snapshots: List[FileSnapshot]) -> None:
        """Report rollback event to health dashboard with cause information."""
        try:
            from core.health_dashboard import HealthDashboard
            dashboard = HealthDashboard()
            
            # Determine the cause of rollback
            cause = "unknown"
            if reason:
                if "conflict" in reason.lower():
                    cause = "conflict"
                elif "partial" in reason.lower() or "incomplete" in reason.lower():
                    cause = "partial_failure"
                elif "timeout" in reason.lower():
                    cause = "timeout"
                elif "permission" in reason.lower() or "access" in reason.lower():
                    cause = "permission_error"
                elif "disk" in reason.lower() or "space" in reason.lower():
                    cause = "disk_error"
                elif "corrupt" in reason.lower() or "invalid" in reason.lower():
                    cause = "corruption"
                else:
                    cause = "other_error"
            
            dashboard.record_event(
                event_type="rollback",
                module=module,
                transaction_id=transaction_id,
                cause=cause,
                reason=reason,
                affected_files=[s.path for s in snapshots],
                timestamp=datetime.utcnow().isoformat()
            )
        except ImportError:
            logger.debug("HealthDashboard not available, skipping report")
        except Exception as e:
            logger.warning(f"Failed to report to health dashboard: {e}")

    def _track_rollback_frequency(self, module_name: str) -> None:
        """Track rollback frequency per module."""
        if module_name in self._rollback_frequency:
            self._rollback_frequency[module_name] += 1
        else:
            self._rollback_frequency[module_name] = 1

    def get_rollback_frequency(self, module_name: Optional[str] = None) -> Dict[str, int]:
        """Get rollback frequency data, optionally filtered by module."""
        if module_name:
            return {module_name: self._rollback_frequency.get(module_name, 0)}
        return dict(self._rollback_frequency)

    def get_aggregate_rollback_stats(self) -> Dict[str, Any]:
        """Provide aggregate rollback statistics for dashboard."""
        total_rollbacks = sum(self._rollback_frequency.values())
        modules_with_rollbacks = len(self._rollback_frequency)
        
        # Get rollback history for additional stats
        history = self.get_rollback_history()
        causes = {}
        for entry in history:
            cause = "unknown"
            reason = entry.get("reason", "")
            if reason:
                if "conflict" in reason.lower():
                    cause = "conflict"
                elif "partial" in reason.lower() or "incomplete" in reason.lower():
                    cause = "partial_failure"
                elif "timeout" in reason.lower():
                    cause = "timeout"
                elif "permission" in reason.lower() or "access" in reason.lower():
                    cause = "permission_error"
                elif "disk" in reason.lower() or "space" in reason.lower():
                    cause = "disk_error"
                elif "corrupt" in reason.lower() or "invalid" in reason.lower():
                    cause = "corruption"
                else:
                    cause = "other_error"
            causes[cause] = causes.get(cause, 0) + 1
        
        # Get most affected modules
        sorted_modules = sorted(self._rollback_frequency.items(), key=lambda x: x[1], reverse=True)
        top_modules = [{"module": mod, "count": count} for mod, count in sorted_modules[:10]]
        
        return {
            "total_rollbacks": total_rollbacks,
            "modules_with_rollbacks": modules_with_rollbacks,
            "rollback_frequency_per_module": dict(self._rollback_frequency),
            "causes_breakdown": causes,
            "top_affected_modules": top_modules,
            "last_updated": datetime.utcnow().isoformat()
        }

    @contextmanager
    def mutation_context(self, module_name: str, operation: str, files: List[str]):
        """Context manager for safe file mutations with automatic rollback on failure."""
        tid = self.begin_transaction(module_name, operation)
        try:
            # Take snapshots of all files that will be mutated
            for file_path in files:
                self.snapshot_file(file_path)
            
            # Yield control to the mutation code
            yield
            
            # If successful, commit the transaction
            self.commit_transaction(tid)
        except Exception as e:
            # On any exception, rollback all changes
            reason = f"{type(e).__name__}: {str(e)}"
            logger.error(f"Mutation failed, initiating rollback: {reason}")
            self.rollback_transaction(tid, reason)
            raise

    def get_transaction_status(self, transaction_id: str) -> Optional[str]:
        """Get the status of a specific transaction."""
        entry = self.transaction_log.get(transaction_id)
        return entry.status if entry else None

    def get_rollback_history(self, module_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get rollback history, optionally filtered by module."""
        log_path = self.backup_dir / "rollback_log.json"
        if not log_path.exists():
            return []
        
        try:
            with open(log_path, 'r') as f:
                history = json.load(f)
            if module_name:
                history = [h for h in history if h.get('module') == module_name]
            return history
        except (IOError, json.JSONDecodeError) as e:
            logger.error(f"Failed to read rollback history: {e}")
            return []

    def cleanup_old_backups(self, max_age_days: int = 7) -> int:
        """Clean up backup files older than specified days."""
        cutoff = datetime.utcnow().timestamp() - (max_age_days * 86400)
        cleaned = 0
        
        for backup_file in self.backup_dir.glob("*.bak"):
            if backup_file.stat().st_mtime < cutoff:
                try:
                    backup_file.unlink()
                    cleaned += 1
                except OSError as e:
                    logger.warning(f"Failed to remove old backup {backup_file}: {e}")
        
        return cleaned


# Convenience functions for easy integration
_global_rollback_manager: Optional[RollbackManager] = None


def get_rollback_manager() -> RollbackManager:
    """Get or create the global rollback manager instance."""
    global _global_rollback_manager
    if _global_rollback_manager is None:
        _global_rollback_manager = RollbackManager()
    return _global_rollback_manager


def safe_mutation(module_name: str, operation: str, files: List[str]):
    """Decorator/context manager for safe file mutations."""
    return get_rollback_manager().mutation_context(module_name, operation, files)