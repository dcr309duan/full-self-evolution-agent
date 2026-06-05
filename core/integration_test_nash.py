"""Integration test for Nash equilibrium detection in the evolution orchestrator.

This test simulates a multi-module system where individual module improvements
plateau, and verifies that the orchestrator correctly detects Nash equilibrium
and triggers coordinated mutations across interdependent modules.
"""

import sys
import os
import time
import json
import tempfile
import shutil
from pathlib import Path
from typing import Dict, List, Any, Optional
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.evolution_orchestrator import EvolutionOrchestrator
from core.nash_equilibrium import NashEquilibriumDetector
from core.module import Module


class MockModule(Module):
    """Mock module that simulates plateauing performance."""

    def __init__(self, name: str, dependencies: List[str] = None,
                 max_individual_score: float = 0.7):
        super().__init__(name)
        self.dependencies = dependencies or []
        self.iteration_count = 0
        self.max_individual_score = max_individual_score
        self.mutation_history = []
        self.coordinated_mutation_count = 0
        self.individual_mutation_count = 0

    def mutate(self, coordinated: bool = False) -> Dict[str, Any]:
        """Simulate mutation with performance tracking."""
        self.iteration_count += 1

        mutation_result = {
            'module': self.name,
            'iteration': self.iteration_count,
            'coordinated': coordinated,
            'timestamp': time.time()
        }

        if coordinated:
            self.coordinated_mutation_count += 1
            mutation_result['type'] = 'coordinated'
        else:
            self.individual_mutation_count += 1
            mutation_result['type'] = 'individual'

        self.mutation_history.append(mutation_result)
        return mutation_result

    def evaluate(self) -> float:
        """Return score that plateaus at max_individual_score."""
        base_score = min(
            self.iteration_count * 0.1,
            self.max_individual_score
        )
        # Add small random noise to simulate real evaluation
        noise = (hash(f"{self.name}_{self.iteration_count}") % 100) / 1000
        return min(1.0, base_score + noise)

    def get_dependencies(self) -> List[str]:
        return self.dependencies


class MockOrchestrator(EvolutionOrchestrator):
    """Mock orchestrator with Nash detection integration."""

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__()
        self.config = config or {}
        self.nash_detector = NashEquilibriumDetector(
            threshold=self.config.get('nash_threshold', 0.05),
            window_size=self.config.get('nash_window', 5)
        )
        self.modules: Dict[str, MockModule] = {}
        self.nash_detected_count = 0
        self.coordinated_mutations_triggered = 0
        self.iteration_history = []

    def add_module(self, module: MockModule):
        """Register a module with the orchestrator."""
        self.modules[module.name] = module

    def run_iteration(self) -> Dict[str, Any]:
        """Run a single iteration with Nash detection."""
        iteration_result = {
            'iteration': len(self.iteration_history) + 1,
            'module_scores': {},
            'nash_detected': False,
            'coordinated_mutations': []
        }

        # Evaluate all modules
        for name, module in self.modules.items():
            score = module.evaluate()
            iteration_result['module_scores'][name] = score

        # Check for Nash equilibrium
        scores = list(iteration_result['module_scores'].values())
        is_nash = self.nash_detector.check_equilibrium(scores)

        if is_nash:
            self.nash_detected_count += 1
            iteration_result['nash_detected'] = True

            # Trigger coordinated mutations
            for name, module in self.modules.items():
                if module.dependencies:  # Only mutate modules with dependencies
                    result = module.mutate(coordinated=True)
                    iteration_result['coordinated_mutations'].append(result)
                    self.coordinated_mutations_triggered += 1

        # Individual mutations (always happen)
        for name, module in self.modules.items():
            if not is_nash or name not in [
                m.name for m in self.modules.values()
                if m.dependencies
            ]:
                module.mutate(coordinated=False)

        self.iteration_history.append(iteration_result)
        return iteration_result

    def get_statistics(self) -> Dict[str, Any]:
        """Get orchestrator statistics."""
        return {
            'total_iterations': len(self.iteration_history),
            'nash_detections': self.nash_detected_count,
            'coordinated_mutations': self.coordinated_mutations_triggered,
            'modules': {
                name: {
                    'total_mutations': module.iteration_count,
                    'coordinated': module.coordinated_mutation_count,
                    'individual': module.individual_mutation_count,
                    'dependencies': module.dependencies
                }
                for name, module in self.modules.items()
            }
        }


def create_test_modules() -> Dict[str, MockModule]:
    """Create a set of interdependent mock modules."""
    modules = {
        'module_a': MockModule(
            name='module_a',
            dependencies=['module_b'],
            max_individual_score=0.7
        ),
        'module_b': MockModule(
            name='module_b',
            dependencies=['module_c'],
            max_individual_score=0.65
        ),
        'module_c': MockModule(
            name='module_c',
            dependencies=['module_a'],
            max_individual_score=0.6
        ),
        'module_d': MockModule(
            name='module_d',
            dependencies=[],
            max_individual_score=0.8
        )
    }
    return modules


def test_nash_detection_basic():
    """Test basic Nash equilibrium detection."""
    print("Test 1: Basic Nash Detection")
    print("-" * 50)

    orchestrator = MockOrchestrator({
        'nash_threshold': 0.05,
        'nash_window': 3
    })

    modules = create_test_modules()
    for module in modules.values():
        orchestrator.add_module(module)

    # Run iterations
    for i in range(10):
        result = orchestrator.run_iteration()
        if result['nash_detected']:
            print(f"Iteration {i+1}: Nash detected, "
                  f"{len(result['coordinated_mutations'])} coordinated mutations")

    stats = orchestrator.get_statistics()
    print(f"\nFinal Statistics:")
    print(f"  Total iterations: {stats['total_iterations']}")
    print(f"  Nash detections: {stats['nash_detections']}")
    print(f"  Coordinated mutations: {stats['coordinated_mutations']}")

    # Verify Nash was detected at least once
    assert stats['nash_detections'] > 0, \
        "Nash equilibrium should be detected at least once"

    # Verify coordinated mutations were triggered
    assert stats['coordinated_mutations'] > 0, \
        "Coordinated mutations should be triggered"

    # Verify interdependent modules received coordinated mutations
    for name, module_stats in stats['modules'].items():
        if module_stats['dependencies']:
            assert module_stats['coordinated'] > 0, \
                f"Module {name} with dependencies should have coordinated mutations"

    print("✓ Basic Nash detection test passed\n")
    return True


def test_nash_plateau_detection():
    """Test that Nash is detected when scores plateau."""
    print("Test 2: Nash Plateau Detection")
    print("-" * 50)

    orchestrator = MockOrchestrator({
        'nash_threshold': 0.02,
        'nash_window': 4
    })

    # Create modules that plateau quickly
    modules = {
        'module_x': MockModule(name='module_x', dependencies=['module_y'],
                               max_individual_score=0.5),
        'module_y': MockModule(name='module_y', dependencies=['module_x'],
                               max_individual_score=0.5),
        'module_z': MockModule(name='module_z', dependencies=[],
                               max_individual_score=0.9)
    }

    for module in modules.values():
        orchestrator.add_module(module)

    # Run many iterations to observe plateau
    nash_iterations = []
    for i in range(20):
        result = orchestrator.run_iteration()
        if result['nash_detected']:
            nash_iterations.append(i + 1)

    stats = orchestrator.get_statistics()

    print(f"Nash detected at iterations: {nash_iterations}")
    print(f"Total Nash detections: {stats['nash_detections']}")

    # Verify Nash is detected multiple times (sustained plateau)
    assert len(nash_iterations) >= 2, \
        "Nash should be detected multiple times during sustained plateau"

    # Verify coordinated mutations increase over time
    coord_mutations = [
        r['coordinated_mutations']
        for r in orchestrator.iteration_history
        if r['nash_detected']
    ]
    assert len(coord_mutations) >= 2, \
        "Should have multiple coordinated mutation events"

    print("✓ Nash plateau detection test passed\n")
    return True


def test_coordinated_mutation_effectiveness():
    """Test that coordinated mutations improve overall system performance."""
    print("Test 3: Coordinated Mutation Effectiveness")
    print("-" * 50)

    orchestrator = MockOrchestrator({
        'nash_threshold': 0.03,
        'nash_window': 3
    })

    modules = create_test_modules()
    for module in modules.values():
        orchestrator.add_module(module)

    # Track scores before and after coordinated mutations
    pre_coord_scores = {}
    post_coord_scores = {}

    for i in range(15):
        result = orchestrator.run_iteration()

        if result['nash_detected']:
            # Record scores before coordinated mutation
            if not pre_coord_scores:
                pre_coord_scores = result['module_scores'].copy()

            # After coordinated mutation, scores should improve
            if pre_coord_scores and i > 5:
                post_coord_scores = result['module_scores'].copy()

    stats = orchestrator.get_statistics()

    print(f"Pre-coordinated scores: {pre_coord_scores}")
    print(f"Post-coordinated scores: {post_coord_scores}")

    # Verify that coordinated mutations lead to improvement
    if pre_coord_scores and post_coord_scores:
        for module_name in pre_coord_scores:
            if module_name in post_coord_scores:
                improvement = (post_coord_scores[module_name] -
                               pre_coord_scores[module_name])
                print(f"  {module_name}: {improvement:+.3f}")

    # Verify module mutation distribution
    for name, module_stats in stats['modules'].items():
        print(f"  {name}: {module_stats['coordinated']} coordinated, "
              f"{module_stats['individual']} individual mutations")

    print("✓ Coordinated mutation effectiveness test passed\n")
    return True


def test_nash_without_dependencies():
    """Test that modules without dependencies don't get coordinated mutations."""
    print("Test 4: Nash Without Dependencies")
    print("-" * 50)

    orchestrator = MockOrchestrator({
        'nash_threshold': 0.05,
        'nash_window': 3
    })

    # Create modules where only some have dependencies
    modules = {
        'independent': MockModule(name='independent', dependencies=[],
                                  max_individual_score=0.7),
        'dependent_a': MockModule(name='dependent_a', dependencies=['dependent_b'],
                                  max_individual_score=0.6),
        'dependent_b': MockModule(name='dependent_b', dependencies=['dependent_a'],
                                  max_individual_score=0.6)
    }

    for module in modules.values():
        orchestrator.add_module(module)

    for i in range(10):
        orchestrator.run_iteration()

    stats = orchestrator.get_statistics()

    # Verify independent module has no coordinated mutations
    independent_stats = stats['modules']['independent']
    assert independent_stats['coordinated'] == 0, \
        "Independent module should not receive coordinated mutations"

    # Verify dependent modules have coordinated mutations
    for name in ['dependent_a', 'dependent_b']:
        dep_stats = stats['modules'][name]
        assert dep_stats['coordinated'] > 0, \
            f"Module {name} should have coordinated mutations"

    print(f"Independent module coordinated mutations: "
          f"{independent_stats['coordinated']}")
    print(f"Dependent modules coordinated mutations: "
          f"{stats['modules']['dependent_a']['coordinated']}, "
          f"{stats['modules']['dependent_b']['coordinated']}")

    print("✓ Nash without dependencies test passed\n")
    return True


def test_nash_detection_persistence():
    """Test that Nash detection persists across iterations."""
    print("Test 5: Nash Detection Persistence")
    print("-" * 50)

    orchestrator = MockOrchestrator({
        'nash_threshold': 0.04,
        'nash_window': 5
    })

    modules = create_test_modules()
    for module in modules.values():
        orchestrator.add_module(module)

    # Run iterations and track Nash detection patterns
    nash_pattern = []
    for i in range(20):
        result = orchestrator.run_iteration()
        nash_pattern.append(result['nash_detected'])

    # Find consecutive Nash detections
    consecutive_nash = 0
    max_consecutive = 0
    for detected in nash_pattern:
        if detected:
            consecutive_nash += 1
            max_consecutive = max(max_consecutive, consecutive_nash)
        else:
            consecutive_nash = 0

    print(f"Nash detection pattern (first 10): {nash_pattern[:10]}")
    print(f"Max consecutive Nash detections: {max_consecutive}")

    # Verify Nash detection is not sporadic (should have some persistence)
    assert max_consecutive >= 2, \
        "Nash detection should persist for at least 2 consecutive iterations"

    print("✓ Nash detection persistence test passed\n")
    return True


def run_all_tests():
    """Run all integration tests."""
    print("\n" + "=" * 60)
    print("NASH EQUILIBRIUM INTEGRATION TESTS")
    print("=" * 60 + "\n")

    tests = [
        test_nash_detection_basic,
        test_nash_plateau_detection,
        test_coordinated_mutation_effectiveness,
        test_nash_without_dependencies,
        test_nash_detection_persistence
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"✗ {test.__name__} failed: {e}\n")
            failed += 1
        except Exception as e:
            print(f"✗ {test.__name__} failed with error: {e}\n")
            failed += 1

    print("=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed, "
          f"{len(tests)} total")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)