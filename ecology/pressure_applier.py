"""
Ecological Pressure Applier for the evolution engine.
Maintains and applies a dynamic pressure schedule to drive agent adaptation.
"""

import random
import time
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict


class PressureType(Enum):
    NOVELTY = "novelty"
    COMPLEXITY = "complexity"
    RESOURCE_CONSTRAINT = "resource_constraint"
    CROSS_DOMAIN = "cross_domain"


@dataclass
class PressureEvent:
    """Represents a single application of pressure."""
    pressure_type: PressureType
    cycle_applied: int
    parameters: Dict[str, Any]
    effectiveness_score: float = 0.0
    was_ignored: bool = False


@dataclass
class PressureSchedule:
    """Defines when and how pressures are applied."""
    novelty_interval: int = 5
    complexity_interval: int = 10
    resource_constraint_interval: int = 15
    cross_domain_interval: int = 20
    rotation_interval: int = 20
    current_cycle: int = 0
    active_pressures: List[PressureType] = field(default_factory=lambda: list(PressureType))


class EcologicalPressureApplier:
    """
    Manages ecological pressures to drive agent adaptation.
    Implements self-modifying pressure schedules based on agent response.
    """

    def __init__(self, initial_schedule: Optional[PressureSchedule] = None):
        self.schedule = initial_schedule or PressureSchedule()
        self.pressure_history: List[PressureEvent] = []
        self.effectiveness_tracker: Dict[PressureType, List[float]] = defaultdict(list)
        self.adaptation_rate_window: List[float] = []
        self.cycle_count = 0
        self._last_rotation_cycle = 0

    def get_pressures_for_cycle(self, cycle: int) -> List[PressureEvent]:
        """
        Determine which pressures to apply in the given cycle.
        Returns a list of PressureEvent objects.
        """
        self.cycle_count = cycle
        self.schedule.current_cycle = cycle
        pressures_to_apply = []

        # Check for schedule rotation
        if (cycle - self._last_rotation_cycle) >= self.schedule.rotation_interval:
            self._rotate_pressures()
            self._last_rotation_cycle = cycle

        # Apply novelty pressure
        if cycle % self.schedule.novelty_interval == 0 and PressureType.NOVELTY in self.schedule.active_pressures:
            pressures_to_apply.append(PressureEvent(
                pressure_type=PressureType.NOVELTY,
                cycle_applied=cycle,
                parameters={
                    "new_categories": self._generate_novelty_categories(),
                    "difficulty_scale": self._calculate_difficulty_scale()
                }
            ))

        # Apply complexity pressure
        if cycle % self.schedule.complexity_interval == 0 and PressureType.COMPLEXITY in self.schedule.active_pressures:
            pressures_to_apply.append(PressureEvent(
                pressure_type=PressureType.COMPLEXITY,
                cycle_applied=cycle,
                parameters={
                    "min_steps": 3 + (cycle // 20),
                    "max_steps": 5 + (cycle // 10),
                    "interleaving_depth": min(3, cycle // 15)
                }
            ))

        # Apply resource constraint pressure
        if cycle % self.schedule.resource_constraint_interval == 0 and PressureType.RESOURCE_CONSTRAINT in self.schedule.active_pressures:
            pressures_to_apply.append(PressureEvent(
                pressure_type=PressureType.RESOURCE_CONSTRAINT,
                cycle_applied=cycle,
                parameters={
                    "time_limit_ms": max(100, 1000 - (cycle * 10)),
                    "memory_limit_mb": max(16, 256 - (cycle * 4)),
                    "iteration_limit": max(50, 500 - (cycle * 5))
                }
            ))

        # Apply cross-domain pressure
        if cycle % self.schedule.cross_domain_interval == 0 and PressureType.CROSS_DOMAIN in self.schedule.active_pressures:
            pressures_to_apply.append(PressureEvent(
                pressure_type=PressureType.CROSS_DOMAIN,
                cycle_applied=cycle,
                parameters={
                    "domains": self._select_cross_domains(),
                    "integration_required": True,
                    "transfer_distance": min(0.9, 0.3 + (cycle * 0.02))
                }
            ))

        # Record applied pressures
        self.pressure_history.extend(pressures_to_apply)
        return pressures_to_apply

    def record_pressure_outcome(self, event: PressureEvent, adaptation_rate: float, was_ignored: bool = False):
        """
        Record the outcome of a pressure application.
        Updates effectiveness tracking and triggers schedule self-modification.
        """
        event.was_ignored = was_ignored
        event.effectiveness_score = self._calculate_effectiveness(adaptation_rate, was_ignored)

        self.effectiveness_tracker[event.pressure_type].append(event.effectiveness_score)
        self.adaptation_rate_window.append(adaptation_rate)

        # Keep window size manageable
        if len(self.adaptation_rate_window) > 50:
            self.adaptation_rate_window.pop(0)

        # Self-modify schedule based on outcomes
        self._self_modify_schedule()

    def get_pressure_summary(self) -> Dict[str, Any]:
        """Return a summary of pressure effectiveness."""
        summary = {
            "total_pressures_applied": len(self.pressure_history),
            "pressures_by_type": {},
            "effectiveness_by_type": {},
            "current_schedule": {
                "novelty_interval": self.schedule.novelty_interval,
                "complexity_interval": self.schedule.complexity_interval,
                "resource_constraint_interval": self.schedule.resource_constraint_interval,
                "cross_domain_interval": self.schedule.cross_domain_interval,
                "rotation_interval": self.schedule.rotation_interval,
                "active_pressures": [p.value for p in self.schedule.active_pressures]
            },
            "adaptation_rate_trend": self._calculate_adaptation_trend()
        }

        for ptype in PressureType:
            events = [e for e in self.pressure_history if e.pressure_type == ptype]
            summary["pressures_by_type"][ptype.value] = len(events)
            if self.effectiveness_tracker[ptype]:
                summary["effectiveness_by_type"][ptype.value] = {
                    "mean": sum(self.effectiveness_tracker[ptype]) / len(self.effectiveness_tracker[ptype]),
                    "count": len(self.effectiveness_tracker[ptype])
                }

        return summary

    def _generate_novelty_categories(self) -> List[str]:
        """Generate new test categories based on cycle and past effectiveness."""
        base_categories = [
            "pattern_recognition", "logical_deduction", "spatial_reasoning",
            "temporal_sequencing", "causal_inference", "analogical_reasoning",
            "probabilistic_estimation", "constraint_satisfaction"
        ]

        # Introduce new categories over time
        if self.cycle_count > 30:
            base_categories.extend(["meta_reasoning", "self_reference", "recursive_problem_solving"])
        if self.cycle_count > 60:
            base_categories.extend(["emergent_property_detection", "multi_agent_coordination"])

        # Select categories that haven't been overused
        recent_categories = set()
        for event in self.pressure_history[-10:]:
            if event.pressure_type == PressureType.NOVELTY:
                recent_categories.update(event.parameters.get("new_categories", []))

        available = [c for c in base_categories if c not in recent_categories]
        if not available:
            available = base_categories

        return random.sample(available, min(3, len(available)))

    def _calculate_difficulty_scale(self) -> float:
        """Calculate difficulty scale based on recent adaptation rate."""
        if not self.adaptation_rate_window:
            return 0.5

        recent_adaptation = sum(self.adaptation_rate_window[-10:]) / min(10, len(self.adaptation_rate_window))
        # Scale difficulty: if adapting well, increase difficulty
        return min(1.0, 0.3 + (recent_adaptation * 0.7))

    def _select_cross_domains(self) -> List[str]:
        """Select domains for cross-domain pressure."""
        domains = [
            "mathematics", "linguistics", "visual_spatial", "music_rhythm",
            "social_reasoning", "scientific_method", "philosophical_logic"
        ]

        # Prefer domains that haven't been combined recently
        recent_combinations = set()
        for event in self.pressure_history[-5:]:
            if event.pressure_type == PressureType.CROSS_DOMAIN:
                recent_combinations.add(tuple(sorted(event.parameters.get("domains", []))))

        # Select 2-3 domains
        num_domains = random.randint(2, 3)
        selected = random.sample(domains, num_domains)

        # Avoid recent combinations
        attempts = 0
        while tuple(sorted(selected)) in recent_combinations and attempts < 5:
            selected = random.sample(domains, num_domains)
            attempts += 1

        return selected

    def _calculate_effectiveness(self, adaptation_rate: float, was_ignored: bool) -> float:
        """Calculate effectiveness score for a pressure event."""
        if was_ignored:
            return 0.0

        # Effectiveness is proportional to adaptation rate, but we want some challenge
        # Ideal adaptation rate is around 0.6-0.8 (challenging but not impossible)
        ideal_rate = 0.7
        effectiveness = 1.0 - abs(adaptation_rate - ideal_rate)
        return max(0.0, min(1.0, effectiveness))

    def _calculate_adaptation_trend(self) -> str:
        """Calculate the trend of adaptation rates."""
        if len(self.adaptation_rate_window) < 5:
            return "insufficient_data"

        recent = self.adaptation_rate_window[-5:]
        older = self.adaptation_rate_window[-10:-5] if len(self.adaptation_rate_window) >= 10 else [0.5] * 5

        recent_avg = sum(recent) / len(recent)
        older_avg = sum(older) / len(older)

        if recent_avg > older_avg * 1.1:
            return "improving"
        elif recent_avg < older_avg * 0.9:
            return "declining"
        else:
            return "stable"

    def _rotate_pressures(self):
        """Rotate out old pressures and potentially introduce new ones."""
        if not self.effectiveness_tracker:
            return

        # Find least effective pressure type
        effectiveness_means = {}
        for ptype in PressureType:
            if self.effectiveness_tracker[ptype]:
                effectiveness_means[ptype] = sum(self.effectiveness_tracker[ptype]) / len(self.effectiveness_tracker[ptype])

        if not effectiveness_means:
            return

        # Remove the least effective pressure if it's been applied enough
        least_effective = min(effectiveness_means, key=effectiveness_means.get)
        if len(self.effectiveness_tracker[least_effective]) >= 5 and least_effective in self.schedule.active_pressures:
            self.schedule.active_pressures.remove(least_effective)

        # If we removed one, potentially add a new one (or re-add an old one)
        if len(self.schedule.active_pressures) < len(PressureType):
            # Find the most effective pressure that's not active
            sorted_pressures = sorted(effectiveness_means.items(), key=lambda x: x[1], reverse=True)
            for ptype, _ in sorted_pressures:
                if ptype not in self.schedule.active_pressures:
                    self.schedule.active_pressures.append(ptype)
                    break

    def _self_modify_schedule(self):
        """
        Self-modify the pressure schedule based on agent adaptation rate.
        Increases pressure frequency if agent adapts well, decreases if struggling.
        """
        if len(self.adaptation_rate_window) < 10:
            return

        recent_adaptation = sum(self.adaptation_rate_window[-10:]) / 10

        # Adjust intervals based on adaptation rate
        if recent_adaptation > 0.8:
            # Agent adapting well - increase pressure frequency
            self.schedule.novelty_interval = max(3, self.schedule.novelty_interval - 1)
            self.schedule.complexity_interval = max(5, self.schedule.complexity_interval - 1)
            self.schedule.resource_constraint_interval = max(8, self.schedule.resource_constraint_interval - 1)
            self.schedule.cross_domain_interval = max(12, self.schedule.cross_domain_interval - 1)
        elif recent_adaptation < 0.3:
            # Agent struggling - decrease pressure frequency
            self.schedule.novelty_interval = min(10, self.schedule.novelty_interval + 1)
            self.schedule.complexity_interval = min(20, self.schedule.complexity_interval + 1)
            self.schedule.resource_constraint_interval = min(25, self.schedule.resource_constraint_interval + 1)
            self.schedule.cross_domain_interval = min(30, self.schedule.cross_domain_interval + 1)

        # Adjust rotation interval based on pressure effectiveness diversity
        effectiveness_variance = self._calculate_effectiveness_variance()
        if effectiveness_variance < 0.1:
            # All pressures similarly effective - rotate more frequently
            self.schedule.rotation_interval = max(10, self.schedule.rotation_interval - 2)
        elif effectiveness_variance > 0.5:
            # High variance - rotate less frequently to let effective pressures work
            self.schedule.rotation_interval = min(30, self.schedule.rotation_interval + 2)

    def _calculate_effectiveness_variance(self) -> float:
        """Calculate variance in effectiveness across pressure types."""
        means = []
        for ptype in PressureType:
            if self.effectiveness_tracker[ptype]:
                means.append(sum(self.effectiveness_tracker[ptype]) / len(self.effectiveness_tracker[ptype]))

        if len(means) < 2:
            return 0.0

        mean_of_means = sum(means) / len(means)
        variance = sum((m - mean_of_means) ** 2 for m in means) / len(means)
        return variance

    def reset(self):
        """Reset the pressure applier to initial state."""
        self.schedule = PressureSchedule()
        self.pressure_history.clear()
        self.effectiveness_tracker.clear()
        self.adaptation_rate_window.clear()
        self.cycle_count = 0
        self._last_rotation_cycle = 0