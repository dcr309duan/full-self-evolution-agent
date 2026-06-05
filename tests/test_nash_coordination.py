"""
Integration test for Nash equilibrium detection and coordinated multi-module mutation.

Simulates a scenario where multiple single-module mutations fail, triggering
Nash equilibrium detection and generation of a coordinated multi-module plan.
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
import json
import os
import sys
from typing import Dict, List, Any

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.nash_detector import NashDetector
from core.multi_module_forcer import MultiModuleForcer
from core.mutation_planner import MutationPlanner


@pytest.fixture
def mock_orchestrator():
    """Create a mock orchestrator with 3 modules."""
    orchestrator = MagicMock()
    orchestrator.modules = {
        "module_a": MagicMock(),
        "module_b": MagicMock(),
        "module_c": MagicMock(),
    }
    orchestrator.module_names = ["module_a", "module_b", "module_c"]
    return orchestrator


@pytest.fixture
def mock_dependency_graph():
    """Create a mock dependency graph with interdependencies."""
    graph = MagicMock()
    graph.get_dependencies.return_value = ["module_b", "module_c"]
    graph.get_dependents.return_value = []
    return graph


@pytest.fixture
def nash_detector(mock_orchestrator, mock_dependency_graph):
    """Create a NashDetector with mocked dependencies."""
    detector = NashDetector(
        orchestrator=mock_orchestrator,
        dependency_graph=mock_dependency_graph,
        threshold=0.3,
    )
    return detector


@pytest.fixture
def multi_module_forcer(mock_orchestrator, mock_dependency_graph):
    """Create a MultiModuleForcer with mocked dependencies."""
    forcer = MultiModuleForcer(
        orchestrator=mock_orchestrator,
        dependency_graph=mock_dependency_graph,
    )
    return forcer


@pytest.fixture
def mutation_planner(mock_orchestrator, mock_dependency_graph):
    """Create a MutationPlanner with mocked dependencies."""
    planner = MutationPlanner(
        orchestrator=mock_orchestrator,
        dependency_graph=mock_dependency_graph,
    )
    return planner


def test_nash_coordination_flow(nash_detector, multi_module_forcer, mutation_planner):
    """
    End-to-end test for Nash coordination:
    1. Simulate 10 single-module mutations that all fail
    2. Verify Nash detector triggers
    3. Verify coordinated multi-module plan is generated
    4. Verify plan involves 2-3 different modules
    """
    # Step 1: Simulate 10 failed single-module mutations
    failed_mutations = []
    for i in range(10):
        mutation = {
            "id": f"mutation_{i}",
            "module": f"module_{chr(97 + (i % 3))}",  # Cycles through a, b, c
            "type": "single",
            "changes": {"line": i, "content": f"change_{i}"},
            "result": "failure",
            "error": f"Test failure {i}",
        }
        failed_mutations.append(mutation)

    # Step 2: Feed failures to Nash detector
    for mutation in failed_mutations:
        nash_detector.record_mutation_result(
            module=mutation["module"],
            mutation_id=mutation["id"],
            success=False,
            error=mutation["error"],
        )

    # Verify Nash detector triggers
    assert nash_detector.is_nash_state(), (
        f"Nash detector should trigger after {len(failed_mutations)} failures"
    )

    # Get Nash equilibrium analysis
    analysis = nash_detector.analyze_equilibrium()
    assert analysis is not None, "Nash analysis should not be None"
    assert analysis.get("is_nash", False), "Analysis should confirm Nash state"
    assert analysis.get("confidence", 0) > 0.3, (
        f"Confidence should exceed threshold, got {analysis.get('confidence', 0)}"
    )

    # Step 3: Generate coordinated multi-module plan
    # First, get the modules involved in the Nash state
    nash_modules = nash_detector.get_nash_modules()
    assert len(nash_modules) >= 2, (
        f"Should have at least 2 modules in Nash state, got {len(nash_modules)}"
    )

    # Generate coordinated plan
    coordinated_plan = multi_module_forcer.generate_coordinated_plan(
        modules=nash_modules,
        mutation_history=failed_mutations,
    )
    assert coordinated_plan is not None, "Coordinated plan should not be None"
    assert "plan_id" in coordinated_plan, "Plan should have an ID"
    assert "mutations" in coordinated_plan, "Plan should contain mutations"

    # Step 4: Verify plan involves 2-3 different modules
    plan_mutations = coordinated_plan["mutations"]
    modules_in_plan = set()
    for mutation in plan_mutations:
        module = mutation.get("module", mutation.get("target_module"))
        if module:
            modules_in_plan.add(module)

    assert 2 <= len(modules_in_plan) <= 3, (
        f"Plan should involve 2-3 modules, got {len(modules_in_plan)}: {modules_in_plan}"
    )

    # Verify mutations are coordinated (not just independent single mutations)
    assert len(plan_mutations) >= 2, (
        f"Should have at least 2 coordinated mutations, got {len(plan_mutations)}"
    )

    # Verify the plan uses the mutation planner
    refined_plan = mutation_planner.refine_coordinated_plan(coordinated_plan)
    assert refined_plan is not None, "Refined plan should not be None"
    assert "execution_order" in refined_plan, "Refined plan should have execution order"


def test_nash_detection_with_partial_failures(nash_detector):
    """
    Test that Nash detector correctly handles partial failures.
    Should not trigger if failures are isolated to one module.
    """
    # Simulate failures in only module_a
    for i in range(10):
        nash_detector.record_mutation_result(
            module="module_a",
            mutation_id=f"mutation_{i}",
            success=False,
            error=f"Failure {i}",
        )

    # Should NOT be in Nash state (only one module affected)
    assert not nash_detector.is_nash_state(), (
        "Should not be Nash state with failures in only one module"
    )


def test_coordinated_plan_generation(multi_module_forcer, mutation_planner):
    """
    Test that coordinated plans are properly generated and involve multiple modules.
    """
    # Generate a plan for 3 modules
    modules = ["module_a", "module_b", "module_c"]
    mutation_history = [
        {"module": m, "type": "single", "result": "failure"}
        for m in modules
        for _ in range(3)
    ]

    plan = multi_module_forcer.generate_coordinated_plan(
        modules=modules,
        mutation_history=mutation_history,
    )

    assert plan is not None
    assert len(plan["mutations"]) >= 2

    # Verify all modules are represented
    modules_in_plan = set()
    for mutation in plan["mutations"]:
        module = mutation.get("module", mutation.get("target_module"))
        if module:
            modules_in_plan.add(module)

    # Should involve at least 2 of the 3 modules
    assert len(modules_in_plan) >= 2


def test_plan_execution_ordering(multi_module_forcer, mutation_planner):
    """
    Test that the coordinated plan has proper execution ordering.
    """
    modules = ["module_a", "module_b"]
    mutation_history = [
        {"module": m, "type": "single", "result": "failure"}
        for m in modules
        for _ in range(5)
    ]

    plan = multi_module_forcer.generate_coordinated_plan(
        modules=modules,
        mutation_history=mutation_history,
    )

    refined_plan = mutation_planner.refine_coordinated_plan(plan)

    # Verify execution order exists and is valid
    assert "execution_order" in refined_plan
    execution_order = refined_plan["execution_order"]
    assert len(execution_order) > 0

    # Verify all mutations in plan are ordered
    plan_mutation_ids = {m.get("id", m.get("mutation_id")) for m in plan["mutations"]}
    ordered_ids = set(execution_order)
    assert ordered_ids.issubset(plan_mutation_ids) or ordered_ids == plan_mutation_ids, (
        "Execution order should reference mutations in the plan"
    )