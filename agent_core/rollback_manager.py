from typing import Any, Dict, List, Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class RollbackManager:
    """
    Manages rollback operations for the agent system.
    Supports automatic rollback triggered by self-consistency failures.
    """

    def __init__(self, system_model: Optional[Dict[str, Any]] = None):
        """
        Initialize the rollback manager.

        Args:
            system_model: Optional reference to the system model dictionary
                          that tracks the current state of the system.
        """
        self.system_model = system_model if system_model is not None else {}
        self.mutation_history: List[Dict[str, Any]] = []
        self.rollback_log: List[Dict[str, Any]] = []

    def record_mutation(self, mutation: Dict[str, Any]) -> None:
        """
        Record a mutation that has been applied to the system.

        Args:
            mutation: A dictionary describing the mutation (e.g., {'type': 'update', 'target': '...', 'old_value': ..., 'new_value': ...})
        """
        mutation['timestamp'] = datetime.utcnow().isoformat()
        self.mutation_history.append(mutation)
        logger.debug(f"Mutation recorded: {mutation}")

    def trigger_rollback(self, reason: str, check_results: List[Dict[str, Any]]) -> bool:
        """
        Trigger an automatic rollback due to a self-consistency failure.

        Args:
            reason: A human-readable string explaining why the rollback was triggered.
            check_results: A list of dictionaries describing the self-consistency check failures
                           that caused this rollback.

        Returns:
            True if the rollback was successful, False otherwise.
        """
        logger.warning(f"Rollback triggered. Reason: {reason}")
        logger.warning(f"Check results: {check_results}")

        # Log the rollback event
        rollback_event = {
            'timestamp': datetime.utcnow().isoformat(),
            'reason': reason,
            'check_results': check_results,
            'success': False
        }

        if not self.mutation_history:
            logger.error("No mutations to roll back.")
            rollback_event['success'] = False
            self.rollback_log.append(rollback_event)
            return False

        # Revert the last mutation
        last_mutation = self.mutation_history.pop()
        try:
            self._revert_mutation(last_mutation)
            logger.info(f"Reverted mutation: {last_mutation}")
            rollback_event['success'] = True
        except Exception as e:
            logger.exception(f"Failed to revert mutation {last_mutation}: {e}")
            rollback_event['success'] = False
            # Re-add the mutation if revert failed to maintain consistency
            self.mutation_history.append(last_mutation)
            self.rollback_log.append(rollback_event)
            return False

        # Update the system model to reflect the rollback state
        self._update_system_model_after_rollback(last_mutation)

        self.rollback_log.append(rollback_event)
        logger.info(f"Rollback completed successfully. Reason: {reason}")
        return True

    def _revert_mutation(self, mutation: Dict[str, Any]) -> None:
        """
        Revert a single mutation on the system model.

        Args:
            mutation: The mutation dictionary to revert.

        Raises:
            KeyError: If the mutation target does not exist in the system model.
            ValueError: If the mutation type is unknown.
        """
        mutation_type = mutation.get('type')
        target = mutation.get('target')
        old_value = mutation.get('old_value')

        if mutation_type == 'update':
            if target is not None:
                self.system_model[target] = old_value
            else:
                raise ValueError("Mutation of type 'update' must have a 'target' field.")
        elif mutation_type == 'delete':
            # Revert deletion by restoring the old value
            if target is not None:
                self.system_model[target] = old_value
            else:
                raise ValueError("Mutation of type 'delete' must have a 'target' field.")
        elif mutation_type == 'create':
            # Revert creation by deleting the created key
            if target is not None:
                self.system_model.pop(target, None)
            else:
                raise ValueError("Mutation of type 'create' must have a 'target' field.")
        else:
            raise ValueError(f"Unknown mutation type: {mutation_type}")

    def _update_system_model_after_rollback(self, mutation: Dict[str, Any]) -> None:
        """
        Update the system model metadata to reflect that a rollback has occurred.

        Args:
            mutation: The mutation that was reverted.
        """
        # Add rollback metadata to the system model
        if '_rollback_info' not in self.system_model:
            self.system_model['_rollback_info'] = []
        self.system_model['_rollback_info'].append({
            'timestamp': datetime.utcnow().isoformat(),
            'reverted_mutation': mutation
        })
        logger.debug("System model updated with rollback info.")

    def get_rollback_history(self) -> List[Dict[str, Any]]:
        """
        Get the history of all rollback events.

        Returns:
            A list of rollback event dictionaries.
        """
        return list(self.rollback_log)

    def get_mutation_history(self) -> List[Dict[str, Any]]:
        """
        Get the history of all recorded mutations.

        Returns:
            A list of mutation dictionaries.
        """
        return list(self.mutation_history)

    def clear_history(self) -> None:
        """
        Clear all mutation and rollback history.
        """
        self.mutation_history.clear()
        self.rollback_log.clear()
        logger.info("Mutation and rollback history cleared.")