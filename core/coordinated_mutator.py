"""Module for generating coordinated multi-module mutations when Nash equilibrium is detected.

This module identifies 2-3 modules with complementary interfaces, generates simultaneous
mutations that change their interaction patterns, and simulates the combined effect
before applying the mutations.
"""

from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import itertools
import random
import logging

logger = logging.getLogger(__name__)


class MutationType(Enum):
    """Types of coordinated mutations that can be applied."""
    INTERFACE_SHIFT = "interface_shift"
    DATA_FLOW_REVERSE = "data_flow_reverse"
    PROTOCOL_CHANGE = "protocol_change"
    SYNC_PATTERN_ALTER = "sync_pattern_alter"
    DEPENDENCY_INVERT = "dependency_invert"


@dataclass
class ModuleInterface:
    """Represents a module's interface for coordination analysis."""
    name: str
    inputs: List[str]
    outputs: List[str]
    protocols: List[str]
    dependencies: List[str]


@dataclass
class CoordinatedMutation:
    """A set of simultaneous mutations across multiple modules."""
    module_names: List[str]
    mutation_types: List[MutationType]
    changes: Dict[str, Dict[str, Any]]
    combined_effect_score: float
    is_simulated: bool = False


class CoordinatedMutator:
    """Generates and simulates coordinated multi-module mutations."""

    # Predefined complementary module groups
    COMPLEMENTARY_GROUPS = [
        ["goal_selector", "evolution_engine", "test_harness"],
        ["data_collector", "analyzer", "visualizer"],
        ["config_manager", "executor", "reporter"],
        ["validator", "optimizer", "deployer"],
    ]

    def __init__(self, modules: Dict[str, ModuleInterface]):
        """
        Initialize with a dictionary of available modules and their interfaces.
        
        Args:
            modules: Dict mapping module names to their interface definitions
        """
        self.modules = modules
        self.detected_equilibria: List[Dict[str, Any]] = []
        self.generated_mutations: List[CoordinatedMutation] = []

    def detect_nash_equilibrium(self, 
                                module_states: Dict[str, Any],
                                threshold: float = 0.95) -> bool:
        """
        Detect if the system is in a Nash equilibrium state.
        
        Args:
            module_states: Current states of all modules
            threshold: Similarity threshold for equilibrium detection
            
        Returns:
            True if equilibrium is detected
        """
        if len(module_states) < 2:
            return False

        # Check if all modules are in stable, non-improving states
        states_list = list(module_states.values())
        for i, state_i in enumerate(states_list):
            for j, state_j in enumerate(states_list[i+1:], i+1):
                similarity = self._compute_state_similarity(state_i, state_j)
                if similarity < threshold:
                    return False
        return True

    def _compute_state_similarity(self, state_a: Any, state_b: Any) -> float:
        """Compute similarity between two module states."""
        if type(state_a) != type(state_b):
            return 0.0
        if isinstance(state_a, dict):
            common_keys = set(state_a.keys()) & set(state_b.keys())
            if not common_keys:
                return 0.0
            similarities = []
            for key in common_keys:
                similarities.append(self._compute_state_similarity(
                    state_a[key], state_b[key]))
            return sum(similarities) / len(similarities)
        elif isinstance(state_a, (int, float)):
            if state_a == state_b:
                return 1.0
            return 1.0 / (1.0 + abs(state_a - state_b))
        else:
            return 1.0 if state_a == state_b else 0.0

    def find_complementary_modules(self) -> List[List[str]]:
        """
        Find 2-3 modules with complementary interfaces.
        
        Returns:
            List of module groups that are complementary
        """
        complementary_groups = []
        available_names = set(self.modules.keys())

        # Check predefined groups first
        for group in self.COMPLEMENTARY_GROUPS:
            if all(name in available_names for name in group):
                complementary_groups.append(group)

        # If no predefined groups found, search for complementary modules
        if not complementary_groups:
            complementary_groups = self._search_complementary_groups()

        return complementary_groups

    def _search_complementary_groups(self) -> List[List[str]]:
        """Search for complementary module groups based on interface analysis."""
        module_names = list(self.modules.keys())
        complementary_groups = []

        # Check all pairs and triples
        for r in [2, 3]:
            for combo in itertools.combinations(module_names, r):
                if self._are_complementary(list(combo)):
                    complementary_groups.append(list(combo))

        return complementary_groups[:5]  # Limit to top 5 groups

    def _are_complementary(self, module_names: List[str]) -> bool:
        """Check if a group of modules have complementary interfaces."""
        if len(module_names) < 2:
            return False

        interfaces = [self.modules[name] for name in module_names]
        
        # Check for input-output matching
        all_outputs = set()
        all_inputs = set()
        for iface in interfaces:
            all_outputs.update(iface.outputs)
            all_inputs.update(iface.inputs)

        # Modules are complementary if outputs of some match inputs of others
        matched = all_outputs & all_inputs
        return len(matched) >= len(module_names) - 1

    def generate_coordinated_mutations(self, 
                                       module_group: List[str]) -> List[CoordinatedMutation]:
        """
        Generate simultaneous mutations for a group of complementary modules.
        
        Args:
            module_group: List of module names to mutate
            
        Returns:
            List of coordinated mutation plans
        """
        if len(module_group) < 2 or len(module_group) > 3:
            raise ValueError("Module group must contain 2-3 modules")

        mutations = []
        interfaces = [self.modules[name] for name in module_group]

        # Generate interface shift mutations
        interface_shift = self._create_interface_shift(module_group, interfaces)
        if interface_shift:
            mutations.append(interface_shift)

        # Generate data flow reverse mutations
        data_flow_reverse = self._create_data_flow_reverse(module_group, interfaces)
        if data_flow_reverse:
            mutations.append(data_flow_reverse)

        # Generate protocol change mutations
        protocol_change = self._create_protocol_change(module_group, interfaces)
        if protocol_change:
            mutations.append(protocol_change)

        # Generate sync pattern alterations
        sync_alter = self._create_sync_pattern_alter(module_group, interfaces)
        if sync_alter:
            mutations.append(sync_alter)

        # Generate dependency invert mutations
        dep_invert = self._create_dependency_invert(module_group, interfaces)
        if dep_invert:
            mutations.append(dep_invert)

        self.generated_mutations.extend(mutations)
        return mutations

    def _create_interface_shift(self, 
                                module_names: List[str],
                                interfaces: List[ModuleInterface]) -> Optional[CoordinatedMutation]:
        """Create mutation that shifts interfaces between modules."""
        if len(module_names) < 2:
            return None

        changes = {}
        mutation_types = []
        
        for i, name in enumerate(module_names):
            iface = interfaces[i]
            # Shift one input to become an output or vice versa
            if iface.inputs and iface.outputs:
                shift_input = random.choice(iface.inputs)
                shift_output = random.choice(iface.outputs)
                changes[name] = {
                    "old_input": shift_input,
                    "new_output": shift_input,
                    "old_output": shift_output,
                    "new_input": shift_output
                }
                mutation_types.append(MutationType.INTERFACE_SHIFT)

        if not mutation_types:
            return None

        return CoordinatedMutation(
            module_names=module_names,
            mutation_types=mutation_types,
            changes=changes,
            combined_effect_score=random.uniform(0.6, 0.9)
        )

    def _create_data_flow_reverse(self,
                                   module_names: List[str],
                                   interfaces: List[ModuleInterface]) -> Optional[CoordinatedMutation]:
        """Create mutation that reverses data flow between modules."""
        if len(module_names) < 2:
            return None

        changes = {}
        mutation_types = [MutationType.DATA_FLOW_REVERSE] * len(module_names)

        for i, name in enumerate(module_names):
            iface = interfaces[i]
            # Reverse the primary data flow direction
            changes[name] = {
                "flow_direction": "reversed",
                "original_inputs": iface.inputs[:],
                "original_outputs": iface.outputs[:],
                "new_inputs": iface.outputs[:],
                "new_outputs": iface.inputs[:]
            }

        return CoordinatedMutation(
            module_names=module_names,
            mutation_types=mutation_types,
            changes=changes,
            combined_effect_score=random.uniform(0.5, 0.8)
        )

    def _create_protocol_change(self,
                                 module_names: List[str],
                                 interfaces: List[ModuleInterface]) -> Optional[CoordinatedMutation]:
        """Create mutation that changes communication protocols."""
        if len(module_names) < 2:
            return None

        changes = {}
        mutation_types = [MutationType.PROTOCOL_CHANGE] * len(module_names)

        protocol_alternatives = ["async", "sync", "event-driven", "polling", "streaming"]

        for i, name in enumerate(module_names):
            iface = interfaces[i]
            if iface.protocols:
                old_protocol = random.choice(iface.protocols)
                new_protocol = random.choice([p for p in protocol_alternatives 
                                              if p != old_protocol])
                changes[name] = {
                    "old_protocol": old_protocol,
                    "new_protocol": new_protocol,
                    "affected_interfaces": iface.inputs + iface.outputs
                }

        return CoordinatedMutation(
            module_names=module_names,
            mutation_types=mutation_types,
            changes=changes,
            combined_effect_score=random.uniform(0.4, 0.7)
        )

    def _create_sync_pattern_alter(self,
                                    module_names: List[str],
                                    interfaces: List[ModuleInterface]) -> Optional[CoordinatedMutation]:
        """Create mutation that alters synchronization patterns."""
        if len(module_names) < 2:
            return None

        changes = {}
        mutation_types = [MutationType.SYNC_PATTERN_ALTER] * len(module_names)

        sync_patterns = ["sequential", "parallel", "pipeline", "barrier", "lockstep"]

        for i, name in enumerate(module_names):
            iface = interfaces[i]
            old_pattern = random.choice(sync_patterns)
            new_pattern = random.choice([p for p in sync_patterns if p != old_pattern])
            changes[name] = {
                "old_sync_pattern": old_pattern,
                "new_sync_pattern": new_pattern,
                "sync_points": iface.dependencies[:]
            }

        return CoordinatedMutation(
            module_names=module_names,
            mutation_types=mutation_types,
            changes=changes,
            combined_effect_score=random.uniform(0.5, 0.85)
        )

    def _create_dependency_invert(self,
                                   module_names: List[str],
                                   interfaces: List[ModuleInterface]) -> Optional[CoordinatedMutation]:
        """Create mutation that inverts dependencies between modules."""
        if len(module_names) < 2:
            return None

        changes = {}
        mutation_types = [MutationType.DEPENDENCY_INVERT] * len(module_names)

        # Invert the dependency chain
        reversed_names = list(reversed(module_names))
        for i, name in enumerate(module_names):
            iface = interfaces[i]
            changes[name] = {
                "old_dependencies": iface.dependencies[:],
                "new_dependencies": [reversed_names[i]] if i < len(reversed_names) else [],
                "inversion_applied": True
            }

        return CoordinatedMutation(
            module_names=module_names,
            mutation_types=mutation_types,
            changes=changes,
            combined_effect_score=random.uniform(0.3, 0.6)
        )

    def simulate_combined_effect(self, 
                                 mutation: CoordinatedMutation,
                                 simulation_steps: int = 100) -> Dict[str, Any]:
        """
        Simulate the combined effect of a coordinated mutation before applying.
        
        Args:
            mutation: The coordinated mutation to simulate
            simulation_steps: Number of simulation steps to run
            
        Returns:
            Simulation results including stability, performance impact, and risks
        """
        logger.info(f"Simulating combined effect for mutation on {mutation.module_names}")

        # Simulate stability
        stability = self._simulate_stability(mutation, simulation_steps)
        
        # Simulate performance impact
        performance_impact = self._simulate_performance_impact(mutation)
        
        # Simulate risk factors
        risks = self._simulate_risks(mutation)

        # Calculate combined effect score
        combined_score = (
            stability * 0.4 +
            (1.0 - abs(performance_impact)) * 0.3 +
            (1.0 - risks["overall_risk"]) * 0.3
        )

        mutation.combined_effect_score = combined_score
        mutation.is_simulated = True

        return {
            "stability": stability,
            "performance_impact": performance_impact,
            "risks": risks,
            "combined_score": combined_score,
            "simulation_steps": simulation_steps,
            "is_feasible": combined_score > 0.5
        }

    def _simulate_stability(self, 
                            mutation: CoordinatedMutation,
                            steps: int) -> float:
        """Simulate stability of the system after mutation."""
        # Simple stability model based on mutation complexity
        base_stability = 0.8
        complexity_penalty = len(mutation.module_names) * 0.1
        mutation_type_penalty = len(mutation.mutation_types) * 0.05
        
        stability = base_stability - complexity_penalty - mutation_type_penalty
        return max(0.0, min(1.0, stability + random.uniform(-0.1, 0.1)))

    def _simulate_performance_impact(self, mutation: CoordinatedMutation) -> float:
        """Simulate performance impact (-1 to 1, negative means degradation)."""
        # More aggressive mutations have higher potential impact
        base_impact = 0.0
        for mutation_type in mutation.mutation_types:
            if mutation_type == MutationType.INTERFACE_SHIFT:
                base_impact += 0.2
            elif mutation_type == MutationType.DATA_FLOW_REVERSE:
                base_impact -= 0.3
            elif mutation_type == MutationType.PROTOCOL_CHANGE:
                base_impact += 0.1
            elif mutation_type == MutationType.SYNC_PATTERN_ALTER:
                base_impact += 0.15
            elif mutation_type == MutationType.DEPENDENCY_INVERT:
                base_impact -= 0.2

        return max(-1.0, min(1.0, base_impact + random.uniform(-0.2, 0.2)))

    def _simulate_risks(self, mutation: CoordinatedMutation) -> Dict[str, float]:
        """Simulate risk factors for the mutation."""
        risks = {
            "incompatibility_risk": random.uniform(0.1, 0.5),
            "deadlock_risk": random.uniform(0.0, 0.3),
            "data_loss_risk": random.uniform(0.0, 0.2),
            "regression_risk": random.uniform(0.1, 0.4)
        }
        risks["overall_risk"] = sum(risks.values()) / len(risks)
        return risks

    def apply_mutation(self, mutation: CoordinatedMutation) -> bool:
        """
        Apply a coordinated mutation after successful simulation.
        
        Args:
            mutation: The mutation to apply
            
        Returns:
            True if mutation was applied successfully
        """
        if not mutation.is_simulated:
            logger.warning("Mutation not simulated yet. Running simulation first.")
            simulation_result = self.simulate_combined_effect(mutation)
            if not simulation_result["is_feasible"]:
                logger.error("Mutation not feasible based on simulation.")
                return False

        if mutation.combined_effect_score < 0.5:
            logger.warning(f"Mutation score {mutation.combined_effect_score:.2f} "
                          "below threshold. Skipping.")
            return False

        logger.info(f"Applying coordinated mutation to {mutation.module_names}")
        
        # Apply changes to each module
        for module_name, changes in mutation.changes.items():
            if module_name in self.modules:
                self._apply_module_changes(module_name, changes)
            else:
                logger.error(f"Module {module_name} not found.")
                return False

        return True

    def _apply_module_changes(self, module_name: str, changes: Dict[str, Any]):
        """Apply changes to a specific module's interface."""
        iface = self.modules[module_name]
        
        # Update interface based on changes
        for key, value in changes.items():
            if hasattr(iface, key):
                setattr(iface, key, value)
        
        logger.debug(f"Applied changes to module {module_name}: {changes}")

    def get_mutation_history(self) -> List[CoordinatedMutation]:
        """Get the history of generated mutations."""
        return self.generated_mutations.copy()

    def clear_mutation_history(self):
        """Clear the mutation history."""
        self.generated_mutations.clear()
        self.detected_equilibria.clear()