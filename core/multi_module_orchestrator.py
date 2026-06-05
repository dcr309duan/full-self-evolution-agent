"""
MultiModuleOrchestrator - Coordinates simultaneous changes across multiple modules
when NashDetector signals equilibrium, with rollback capability.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import random

logger = logging.getLogger(__name__)


class ChangeStatus(Enum):
    """Status of a coordinated change proposal."""
    PENDING = "pending"
    APPLIED = "applied"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"


@dataclass
class ModuleChange:
    """Represents a change to a single module."""
    module_name: str
    change_type: str  # e.g., 'modify', 'add', 'remove'
    change_data: Dict[str, Any]
    expected_impact: float  # Expected performance impact (-1.0 to 1.0)
    rollback_data: Optional[Dict[str, Any]] = None


@dataclass
class CoordinatedChangeProposal:
    """A proposal for coordinated changes across multiple modules."""
    proposal_id: str
    changes: List[ModuleChange]
    synergy_score: float  # Expected combined benefit (0.0 to 1.0)
    risk_score: float  # Risk of degradation (0.0 to 1.0)
    timestamp: datetime = field(default_factory=datetime.now)
    status: ChangeStatus = ChangeStatus.PENDING
    pre_change_metrics: Dict[str, float] = field(default_factory=dict)
    post_change_metrics: Dict[str, float] = field(default_factory=dict)


class MultiModuleOrchestrator:
    """
    Orchestrates coordinated changes across multiple modules when Nash equilibrium is detected.
    Generates change proposals, applies them, and provides rollback if performance degrades.
    """

    def __init__(self, mutation_engine: Any, nash_detector: Any,
                 performance_monitor: Optional[Any] = None,
                 max_concurrent_changes: int = 3,
                 rollback_threshold: float = -0.1):
        """
        Initialize the orchestrator.

        Args:
            mutation_engine: The mutation engine to apply changes
            nash_detector: NashDetector instance for equilibrium detection
            performance_monitor: Optional performance monitor for metrics
            max_concurrent_changes: Maximum number of simultaneous module changes
            rollback_threshold: Performance degradation threshold to trigger rollback
        """
        self.mutation_engine = mutation_engine
        self.nash_detector = nash_detector
        self.performance_monitor = performance_monitor
        self.max_concurrent_changes = max_concurrent_changes
        self.rollback_threshold = rollback_threshold

        # Track active proposals and their status
        self.active_proposals: Dict[str, CoordinatedChangeProposal] = {}
        self.change_history: List[CoordinatedChangeProposal] = []

        # Register with nash detector for equilibrium callbacks
        self._register_with_nash_detector()

    def _register_with_nash_detector(self) -> None:
        """Register equilibrium callback with the Nash detector."""
        if hasattr(self.nash_detector, 'on_equilibrium'):
            self.nash_detector.on_equilibrium(self._on_equilibrium_detected)
            logger.info("Registered equilibrium callback with NashDetector")

    async def _on_equilibrium_detected(self, equilibrium_data: Dict[str, Any]) -> None:
        """
        Callback when Nash equilibrium is detected.

        Args:
            equilibrium_data: Data about the detected equilibrium
        """
        logger.info(f"Nash equilibrium detected: {equilibrium_data}")

        # Generate coordinated change proposals
        proposals = await self.generate_change_proposals(equilibrium_data)

        if proposals:
            # Select the best proposal and apply it
            best_proposal = self._select_best_proposal(proposals)
            await self.apply_coordinated_change(best_proposal)

    async def generate_change_proposals(
        self,
        equilibrium_data: Dict[str, Any],
        num_proposals: int = 3
    ) -> List[CoordinatedChangeProposal]:
        """
        Generate coordinated change proposals based on equilibrium data.

        Args:
            equilibrium_data: Data about the detected equilibrium
            num_proposals: Number of proposals to generate

        Returns:
            List of CoordinatedChangeProposal objects
        """
        proposals = []
        modules_at_equilibrium = equilibrium_data.get('modules_at_equilibrium', [])
        module_performance = equilibrium_data.get('module_performance', {})

        if len(modules_at_equilibrium) < 2:
            logger.warning("Need at least 2 modules for coordinated change")
            return proposals

        for i in range(num_proposals):
            # Select 2-3 random modules from those at equilibrium
            num_modules = min(random.randint(2, 3), len(modules_at_equilibrium))
            selected_modules = random.sample(modules_at_equilibrium, num_modules)

            changes = []
            synergy_score = 0.0

            for module_name in selected_modules:
                # Generate change for each module
                change = await self._generate_module_change(
                    module_name,
                    module_performance.get(module_name, {})
                )
                if change:
                    changes.append(change)
                    # Calculate synergy based on change types
                    synergy_score += change.expected_impact

            if len(changes) >= 2:
                # Normalize synergy score
                synergy_score = min(1.0, max(0.0, synergy_score / len(changes)))

                # Calculate risk score (inverse of synergy)
                risk_score = 1.0 - synergy_score

                proposal = CoordinatedChangeProposal(
                    proposal_id=f"coordinated_{datetime.now().timestamp()}_{i}",
                    changes=changes,
                    synergy_score=synergy_score,
                    risk_score=risk_score
                )
                proposals.append(proposal)

        return proposals

    async def _generate_module_change(
        self,
        module_name: str,
        performance_data: Dict[str, Any]
    ) -> Optional[ModuleChange]:
        """
        Generate a change for a single module.

        Args:
            module_name: Name of the module
            performance_data: Performance data for the module

        Returns:
            ModuleChange object or None if no change is needed
        """
        # Get available mutation types from the mutation engine
        mutation_types = self._get_available_mutation_types(module_name)

        if not mutation_types:
            return None

        # Select a mutation type based on performance
        if performance_data.get('performance', 0.5) < 0.3:
            # Low performance - try a more aggressive change
            change_type = random.choice(mutation_types)
            expected_impact = random.uniform(0.1, 0.3)
        else:
            # Moderate performance - try a conservative change
            change_type = random.choice(mutation_types[:len(mutation_types)//2 + 1])
            expected_impact = random.uniform(0.05, 0.15)

        # Create change data
        change_data = {
            'mutation_type': change_type,
            'parameters': self._generate_mutation_parameters(module_name, change_type),
            'timestamp': datetime.now().isoformat()
        }

        # Capture current state for rollback
        rollback_data = await self._capture_module_state(module_name)

        return ModuleChange(
            module_name=module_name,
            change_type=change_type,
            change_data=change_data,
            expected_impact=expected_impact,
            rollback_data=rollback_data
        )

    def _get_available_mutation_types(self, module_name: str) -> List[str]:
        """Get available mutation types for a module."""
        if hasattr(self.mutation_engine, 'get_mutation_types'):
            return self.mutation_engine.get_mutation_types(module_name)
        return ['modify', 'tweak', 'adjust']

    def _generate_mutation_parameters(self, module_name: str, mutation_type: str) -> Dict[str, Any]:
        """Generate parameters for a mutation."""
        if hasattr(self.mutation_engine, 'generate_parameters'):
            return self.mutation_engine.generate_parameters(module_name, mutation_type)
        return {'intensity': random.uniform(0.1, 0.5)}

    async def _capture_module_state(self, module_name: str) -> Dict[str, Any]:
        """Capture current state of a module for rollback purposes."""
        state = {}
        if hasattr(self.mutation_engine, 'get_module_state'):
            state = await self.mutation_engine.get_module_state(module_name)
        return state

    def _select_best_proposal(self, proposals: List[CoordinatedChangeProposal]) -> CoordinatedChangeProposal:
        """
        Select the best proposal based on synergy and risk scores.

        Args:
            proposals: List of proposals to choose from

        Returns:
            The best proposal
        """
        # Score each proposal: higher synergy and lower risk is better
        def score_proposal(p: CoordinatedChangeProposal) -> float:
            return p.synergy_score * 0.7 + (1.0 - p.risk_score) * 0.3

        return max(proposals, key=score_proposal)

    async def apply_coordinated_change(self, proposal: CoordinatedChangeProposal) -> bool:
        """
        Apply a coordinated change proposal.

        Args:
            proposal: The proposal to apply

        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Applying coordinated change proposal: {proposal.proposal_id}")

        # Capture pre-change metrics
        proposal.pre_change_metrics = await self._get_current_metrics()

        try:
            # Apply changes sequentially (order matters for dependencies)
            for change in proposal.changes:
                success = await self._apply_single_change(change)
                if not success:
                    logger.error(f"Failed to apply change to {change.module_name}")
                    proposal.status = ChangeStatus.FAILED
                    await self._rollback_changes(proposal)
                    return False

            # Capture post-change metrics
            proposal.post_change_metrics = await self._get_current_metrics()

            # Check if performance degraded
            if self._should_rollback(proposal):
                logger.warning("Performance degraded, rolling back changes")
                await self._rollback_changes(proposal)
                proposal.status = ChangeStatus.ROLLED_BACK
                return False

            proposal.status = ChangeStatus.APPLIED
            self.active_proposals[proposal.proposal_id] = proposal
            self.change_history.append(proposal)
            logger.info(f"Successfully applied coordinated change: {proposal.proposal_id}")
            return True

        except Exception as e:
            logger.error(f"Error applying coordinated change: {e}")
            proposal.status = ChangeStatus.FAILED
            await self._rollback_changes(proposal)
            return False

    async def _apply_single_change(self, change: ModuleChange) -> bool:
        """
        Apply a single module change using the mutation engine.

        Args:
            change: The module change to apply

        Returns:
            True if successful
        """
        try:
            if hasattr(self.mutation_engine, 'apply_mutation'):
                await self.mutation_engine.apply_mutation(
                    module_name=change.module_name,
                    mutation_type=change.change_type,
                    parameters=change.change_data.get('parameters', {})
                )
                return True
            else:
                # Fallback: try direct module modification
                logger.warning(f"Mutation engine doesn't support apply_mutation, trying direct modification")
                return await self._direct_module_modification(change)
        except Exception as e:
            logger.error(f"Failed to apply change to {change.module_name}: {e}")
            return False

    async def _direct_module_modification(self, change: ModuleChange) -> bool:
        """
        Fallback method for direct module modification.

        Args:
            change: The module change to apply

        Returns:
            True if successful
        """
        # This is a placeholder - actual implementation depends on module structure
        logger.info(f"Direct modification of {change.module_name} with type {change.change_type}")
        return True

    async def _rollback_changes(self, proposal: CoordinatedChangeProposal) -> None:
        """
        Rollback all changes in a proposal.

        Args:
            proposal: The proposal to rollback
        """
        logger.info(f"Rolling back changes for proposal: {proposal.proposal_id}")

        # Rollback in reverse order
        for change in reversed(proposal.changes):
            try:
                if change.rollback_data and hasattr(self.mutation_engine, 'restore_module_state'):
                    await self.mutation_engine.restore_module_state(
                        module_name=change.module_name,
                        state=change.rollback_data
                    )
                elif hasattr(self.mutation_engine, 'rollback_mutation'):
                    await self.mutation_engine.rollback_mutation(
                        module_name=change.module_name,
                        mutation_data=change.change_data
                    )
                else:
                    logger.warning(f"No rollback mechanism for {change.module_name}")
            except Exception as e:
                logger.error(f"Error rolling back {change.module_name}: {e}")

        proposal.status = ChangeStatus.ROLLED_BACK
        logger.info(f"Rollback completed for proposal: {proposal.proposal_id}")

    def _should_rollback(self, proposal: CoordinatedChangeProposal) -> bool:
        """
        Determine if changes should be rolled back based on performance metrics.

        Args:
            proposal: The proposal to evaluate

        Returns:
            True if rollback is needed
        """
        if not proposal.pre_change_metrics or not proposal.post_change_metrics:
            return False

        # Calculate performance change
        perf_change = self._calculate_performance_change(
            proposal.pre_change_metrics,
            proposal.post_change_metrics
        )

        return perf_change < self.rollback_threshold

    def _calculate_performance_change(
        self,
        pre_metrics: Dict[str, float],
        post_metrics: Dict[str, float]
    ) -> float:
        """
        Calculate the performance change between pre and post metrics.

        Args:
            pre_metrics: Metrics before changes
            post_metrics: Metrics after changes

        Returns:
            Performance change value (negative means degradation)
        """
        if not pre_metrics or not post_metrics:
            return 0.0

        changes = []
        for key in pre_metrics:
            if key in post_metrics:
                if pre_metrics[key] != 0:
                    change = (post_metrics[key] - pre_metrics[key]) / abs(pre_metrics[key])
                    changes.append(change)

        return sum(changes) / len(changes) if changes else 0.0

    async def _get_current_metrics(self) -> Dict[str, float]:
        """
        Get current performance metrics.

        Returns:
            Dictionary of metric names to values
        """
        if self.performance_monitor and hasattr(self.performance_monitor, 'get_metrics'):
            return await self.performance_monitor.get_metrics()
        return {}

    def get_active_proposals(self) -> List[CoordinatedChangeProposal]:
        """Get list of currently active (applied) proposals."""
        return [
            p for p in self.active_proposals.values()
            if p.status == ChangeStatus.APPLIED
        ]

    def get_change_history(self, limit: int = 10) -> List[CoordinatedChangeProposal]:
        """Get recent change history."""
        return self.change_history[-limit:]

    async def force_coordinated_change(
        self,
        modules: List[str],
        change_types: Optional[List[str]] = None
    ) -> Optional[CoordinatedChangeProposal]:
        """
        Force a coordinated change on specified modules.

        Args:
            modules: List of module names to change
            change_types: Optional list of change types to apply

        Returns:
            The applied proposal or None if failed
        """
        if len(modules) < 2 or len(modules) > self.max_concurrent_changes:
            logger.error(f"Invalid number of modules: {len(modules)}")
            return None

        changes = []
        for i, module_name in enumerate(modules):
            change_type = change_types[i] if change_types and i < len(change_types) else 'modify'
            change = ModuleChange(
                module_name=module_name,
                change_type=change_type,
                change_data={
                    'mutation_type': change_type,
                    'parameters': self._generate_mutation_parameters(module_name, change_type),
                    'timestamp': datetime.now().isoformat()
                },
                expected_impact=0.1,
                rollback_data=await self._capture_module_state(module_name)
            )
            changes.append(change)

        proposal = CoordinatedChangeProposal(
            proposal_id=f"forced_{datetime.now().timestamp()}",
            changes=changes,
            synergy_score=0.5,
            risk_score=0.5
        )

        success = await self.apply_coordinated_change(proposal)
        return proposal if success else None

    async def orchestrate_multi_mutation(
        self,
        modules: List[str],
        goal: str
    ) -> Optional[CoordinatedChangeProposal]:
        """
        Orchestrate a coordinated mutation across multiple modules based on a goal.

        Args:
            modules: List of 2-3 module names to mutate simultaneously
            goal: Description of the goal (e.g., 'add shared interface', 'refactor common dependency')

        Returns:
            The applied proposal or None if failed
        """
        if len(modules) < 2 or len(modules) > 3:
            logger.error(f"Need 2-3 modules, got {len(modules)}")
            return None

        logger.info(f"Orchestrating multi-mutation for modules {modules} with goal: {goal}")

        # Generate coordinated mutations based on the goal
        changes = []
        synergy_score = 0.0

        for module_name in modules:
            # Determine change type based on goal
            if 'shared interface' in goal.lower():
                change_type = 'add_interface'
            elif 'refactor' in goal.lower() and 'dependency' in goal.lower():
                change_type = 'refactor_dependency'
            elif 'shared' in goal.lower() and 'dependency' in goal.lower():
                change_type = 'add_shared_dependency'
            else:
                change_type = 'modify'

            # Generate change data
            change_data = {
                'mutation_type': change_type,
                'parameters': self._generate_mutation_parameters(module_name, change_type),
                'goal': goal,
                'timestamp': datetime.now().isoformat()
            }

            # Capture current state for rollback
            rollback_data = await self._capture_module_state(module_name)

            # Expected impact based on goal complexity
            expected_impact = 0.15 if 'shared' in goal.lower() else 0.1

            change = ModuleChange(
                module_name=module_name,
                change_type=change_type,
                change_data=change_data,
                expected_impact=expected_impact,
                rollback_data=rollback_data
            )
            changes.append(change)
            synergy_score += expected_impact

        # Normalize synergy score
        synergy_score = min(1.0, max(0.0, synergy_score / len(changes)))
        risk_score = 1.0 - synergy_score

        proposal = CoordinatedChangeProposal(
            proposal_id=f"orchestrated_{datetime.now().timestamp()}",
            changes=changes,
            synergy_score=synergy_score,
            risk_score=risk_score
        )

        # Apply the coordinated mutation atomically
        success = await self.apply_coordinated_change(proposal)
        return proposal if success else None

    async def cleanup(self) -> None:
        """Clean up resources and rollback any active changes."""
        logger.info("Cleaning up MultiModuleOrchestrator")
        for proposal in list(self.active_proposals.values()):
            if proposal.status == ChangeStatus.APPLIED:
                await self._rollback_changes(proposal)
        self.active_proposals.clear()