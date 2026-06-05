import pytest
import tempfile
import os
import shutil
import subprocess
import json
import time
from pathlib import Path
from typing import Dict, List, Any

# Assuming the project has these modules; adjust imports as needed
from self_model import SelfModel
from harness import Harness
from repair_goal import RepairGoal
from failure_point import FailurePoint
from logger import get_logger

logger = get_logger(__name__)


@pytest.fixture
def temp_git_repo():
    """Create a temporary git repository for sandboxed execution."""
    tmpdir = tempfile.mkdtemp()
    repo_path = Path(tmpdir) / "test_repo"
    repo_path.mkdir(parents=True, exist_ok=True)
    
    # Initialize git repo
    subprocess.run(["git", "init"], cwd=repo_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_path, capture_output=True)
    
    # Create initial commit
    (repo_path / "README.md").write_text("# Test Repo")
    subprocess.run(["git", "add", "."], cwd=repo_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_path, capture_output=True)
    
    # Create a test branch
    subprocess.run(["git", "checkout", "-b", "test-branch"], cwd=repo_path, capture_output=True)
    
    yield repo_path
    
    # Cleanup
    shutil.rmtree(tmpdir)


@pytest.fixture
def self_model_with_known_state(temp_git_repo):
    """Initialize the self-model with a known state."""
    model = SelfModel()
    
    # Define known state: system components, dependencies, and current status
    known_state = {
        "components": [
            {"id": "comp_a", "type": "service", "status": "healthy", "dependencies": []},
            {"id": "comp_b", "type": "service", "status": "healthy", "dependencies": ["comp_a"]},
            {"id": "comp_c", "type": "database", "status": "healthy", "dependencies": ["comp_b"]},
        ],
        "configurations": {
            "comp_a": {"version": "1.0", "port": 8080},
            "comp_b": {"version": "2.0", "port": 8081},
            "comp_c": {"version": "3.0", "port": 5432},
        },
        "git_branch": "test-branch",
        "repo_path": str(temp_git_repo),
    }
    
    model.initialize(known_state)
    return model


@pytest.fixture
def harness(temp_git_repo, self_model_with_known_state):
    """Create a harness instance for running multi-step scenarios."""
    return Harness(
        repo_path=temp_git_repo,
        self_model=self_model_with_known_state,
        config={"max_retries": 3, "timeout": 30}
    )


class TestSystemicIntegration:
    """Integration tests for systemic failure detection and repair."""

    def test_multi_step_scenario_with_failures(self, harness, self_model_with_known_state):
        """
        Run a multi-step scenario through the harness and verify:
        - All failure points are logged with complete context
        - Repair goals are generated for each failure
        - Repair goals have valid dependency chains
        - Cycle time is measured and logged
        """
        # Define a multi-step scenario that will trigger failures
        scenario_steps = [
            {
                "action": "deploy",
                "component": "comp_a",
                "params": {"version": "1.1", "force": True}
            },
            {
                "action": "deploy",
                "component": "comp_b",
                "params": {"version": "2.1", "force": True}
            },
            {
                "action": "deploy",
                "component": "comp_c",
                "params": {"version": "3.1", "force": True}
            },
            {
                "action": "verify",
                "component": "comp_a",
                "params": {"health_check": True}
            },
            {
                "action": "verify",
                "component": "comp_b",
                "params": {"health_check": True}
            },
            {
                "action": "verify",
                "component": "comp_c",
                "params": {"health_check": True}
            },
        ]

        # Track metrics
        start_time = time.time()
        failure_points: List[FailurePoint] = []
        repair_goals: List[RepairGoal] = []
        step_results = []

        # Run the scenario
        for step in scenario_steps:
            try:
                result = harness.execute_step(step)
                step_results.append(result)
                
                # Collect failure points from the result
                if result.get("failures"):
                    for failure in result["failures"]:
                        failure_points.append(FailurePoint.from_dict(failure))
                
                # Collect repair goals
                if result.get("repair_goals"):
                    for goal in result["repair_goals"]:
                        repair_goals.append(RepairGoal.from_dict(goal))
                        
            except Exception as e:
                logger.error(f"Step failed: {step['action']} on {step['component']}: {str(e)}")
                # Create a failure point for the exception
                failure_point = FailurePoint(
                    component=step["component"],
                    action=step["action"],
                    error=str(e),
                    context={"step": step, "timestamp": time.time()}
                )
                failure_points.append(failure_point)

        end_time = time.time()
        cycle_time = end_time - start_time

        # Assertion 1: All failure points are logged with complete context
        assert len(failure_points) > 0, "No failure points were generated"
        for fp in failure_points:
            assert fp.component is not None, f"Failure point missing component: {fp}"
            assert fp.action is not None, f"Failure point missing action: {fp}"
            assert fp.error is not None, f"Failure point missing error: {fp}"
            assert fp.context is not None, f"Failure point missing context: {fp}"
            assert "timestamp" in fp.context, f"Failure point missing timestamp in context: {fp}"
            assert "step" in fp.context, f"Failure point missing step in context: {fp}"
            logger.info(f"Validated failure point: {fp.component}/{fp.action}")

        # Assertion 2: Repair goals are generated for each failure
        assert len(repair_goals) > 0, "No repair goals were generated"
        assert len(repair_goals) >= len(failure_points), (
            f"Expected at least {len(failure_points)} repair goals, got {len(repair_goals)}"
        )
        for rg in repair_goals:
            assert rg.failure_point_id is not None, f"Repair goal missing failure_point_id: {rg}"
            assert rg.action_plan is not None, f"Repair goal missing action_plan: {rg}"
            logger.info(f"Validated repair goal for failure: {rg.failure_point_id}")

        # Assertion 3: Repair goals have valid dependency chains
        for rg in repair_goals:
            assert rg.dependency_chain is not None, f"Repair goal missing dependency chain: {rg}"
            assert len(rg.dependency_chain) > 0, f"Repair goal has empty dependency chain: {rg}"
            
            # Verify dependency chain is valid (no cycles, all components exist)
            visited = set()
            for dep in rg.dependency_chain:
                assert dep not in visited, f"Cycle detected in dependency chain: {rg.dependency_chain}"
                visited.add(dep)
                # Verify the dependency exists in the self-model
                component = self_model_with_known_state.get_component(dep)
                assert component is not None, f"Dependency {dep} not found in self-model"
            
            logger.info(f"Validated dependency chain for repair goal: {rg.failure_point_id}")

        # Assertion 4: Cycle time is measured and logged
        assert cycle_time > 0, f"Cycle time should be positive, got {cycle_time}"
        logger.info(f"Cycle time for scenario: {cycle_time:.3f} seconds")
        
        # Log performance metrics
        performance_metrics = {
            "total_steps": len(scenario_steps),
            "successful_steps": len([r for r in step_results if r.get("status") == "success"]),
            "failed_steps": len(failure_points),
            "repair_goals_generated": len(repair_goals),
            "cycle_time_seconds": cycle_time,
            "average_step_time": cycle_time / len(scenario_steps) if scenario_steps else 0,
        }
        logger.info(f"Performance metrics: {json.dumps(performance_metrics, indent=2)}")

        # Additional verification: Ensure harness state is consistent
        final_state = harness.get_state()
        assert final_state is not None, "Harness state should not be None after scenario"
        assert "components" in final_state, "Harness state should contain components"
        assert "git_branch" in final_state, "Harness state should contain git branch"
        assert final_state["git_branch"] == "test-branch", "Git branch should remain unchanged"

        # Verify git branch is still the test branch
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=harness.repo_path,
            capture_output=True,
            text=True
        )
        assert result.stdout.strip() == "test-branch", (
            f"Expected git branch 'test-branch', got '{result.stdout.strip()}'"
        )

    def test_no_failure_scenario(self, harness):
        """Test that a scenario without failures produces no failure points or repair goals."""
        scenario_steps = [
            {
                "action": "verify",
                "component": "comp_a",
                "params": {"health_check": True}
            },
            {
                "action": "verify",
                "component": "comp_b",
                "params": {"health_check": True}
            },
        ]

        failure_points = []
        repair_goals = []

        for step in scenario_steps:
            result = harness.execute_step(step)
            if result.get("failures"):
                failure_points.extend(result["failures"])
            if result.get("repair_goals"):
                repair_goals.extend(result["repair_goals"])

        assert len(failure_points) == 0, f"Expected no failures, got {len(failure_points)}"
        assert len(repair_goals) == 0, f"Expected no repair goals, got {len(repair_goals)}"

    def test_dependency_chain_validation(self, harness, self_model_with_known_state):
        """Test that dependency chains are correctly validated."""
        # Create a scenario that triggers a failure in comp_c (depends on comp_b and comp_a)
        scenario_steps = [
            {
                "action": "deploy",
                "component": "comp_c",
                "params": {"version": "3.1", "force": True}
            },
        ]

        result = harness.execute_step(scenario_steps[0])
        
        if result.get("failures"):
            for failure in result["failures"]:
                failure_point = FailurePoint.from_dict(failure)
                # The dependency chain should include comp_b and comp_a
                assert "comp_b" in failure_point.dependency_chain, (
                    f"Expected comp_b in dependency chain, got {failure_point.dependency_chain}"
                )
                assert "comp_a" in failure_point.dependency_chain, (
                    f"Expected comp_a in dependency chain, got {failure_point.dependency_chain}"
                )
                logger.info(f"Validated dependency chain for failure in comp_c: {failure_point.dependency_chain}")

    def test_performance_metrics_logging(self, harness, caplog):
        """Test that performance metrics are properly logged."""
        import logging
        caplog.set_level(logging.INFO)
        
        scenario_steps = [
            {
                "action": "deploy",
                "component": "comp_a",
                "params": {"version": "1.1", "force": True}
            },
        ]

        start_time = time.time()
        harness.execute_step(scenario_steps[0])
        cycle_time = time.time() - start_time

        # Check that cycle time is logged
        assert any("cycle_time" in record.message for record in caplog.records), (
            "Cycle time not found in log records"
        )
        assert any("performance" in record.message.lower() for record in caplog.records), (
            "Performance metrics not found in log records"
        )
        
        logger.info(f"Verified performance metrics logging with cycle time: {cycle_time:.3f}s")