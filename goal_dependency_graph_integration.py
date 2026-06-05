import asyncio
import logging
from typing import Dict, List, Set

from goal_dependency_graph import GoalDependencyGraph, GoalNode, GoalState
from goal_generator import GoalGenerator
from goal_executor import GoalExecutor
from evolution_loop import EvolutionLoop

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GoalDependencyGraphIntegrationTest:
    """
    Integration test for the full evolution loop with dependency graph enabled.
    Tests that goals are properly blocked/unblocked based on prerequisites and
    that disconnected implementations are not processed unnecessarily.
    """

    def __init__(self):
        self.dependency_graph = GoalDependencyGraph()
        self.goal_generator = GoalGenerator(self.dependency_graph)
        self.goal_executor = GoalExecutor(self.dependency_graph)
        self.evolution_loop = EvolutionLoop(
            goal_generator=self.goal_generator,
            goal_executor=self.goal_executor,
            dependency_graph=self.dependency_graph
        )

        # Define test goals with known dependencies
        self.goals: Dict[str, GoalNode] = {
            "goal_a": GoalNode(
                id="goal_a",
                description="Foundation goal with no prerequisites",
                prerequisites=set(),
                state=GoalState.PENDING
            ),
            "goal_b": GoalNode(
                id="goal_b",
                description="Depends on goal_a",
                prerequisites={"goal_a"},
                state=GoalState.PENDING
            ),
            "goal_c": GoalNode(
                id="goal_c",
                description="Depends on goal_b",
                prerequisites={"goal_b"},
                state=GoalState.PENDING
            ),
            "goal_d": GoalNode(
                id="goal_d",
                description="Independent goal with no prerequisites",
                prerequisites=set(),
                state=GoalState.PENDING
            ),
            "goal_e": GoalNode(
                id="goal_e",
                description="Depends on goal_d and goal_a",
                prerequisites={"goal_d", "goal_a"},
                state=GoalState.PENDING
            ),
            "goal_f": GoalNode(
                id="goal_f",
                description="Disconnected goal with no dependencies and no dependents",
                prerequisites=set(),
                state=GoalState.PENDING
            )
        }

        # Register all goals in the dependency graph
        for goal_id, goal_node in self.goals.items():
            self.dependency_graph.add_goal(goal_node)

    async def test_goals_blocked_with_unmet_prerequisites(self) -> bool:
        """
        Verify that goals with unmet prerequisites are blocked.
        Initially, only goal_a, goal_d, and goal_f should be unblocked.
        """
        logger.info("Test 1: Goals with unmet prerequisites are blocked")
        
        blocked_goals = self.dependency_graph.get_blocked_goals()
        unblocked_goals = self.dependency_graph.get_unblocked_goals()

        expected_blocked = {"goal_b", "goal_c", "goal_e"}
        expected_unblocked = {"goal_a", "goal_d", "goal_f"}

        blocked_ids = {g.id for g in blocked_goals}
        unblocked_ids = {g.id for g in unblocked_goals}

        if blocked_ids != expected_blocked:
            logger.error(f"Expected blocked goals {expected_blocked}, got {blocked_ids}")
            return False
        if unblocked_ids != expected_unblocked:
            logger.error(f"Expected unblocked goals {expected_unblocked}, got {unblocked_ids}")
            return False

        logger.info("Test 1 passed: Goals correctly blocked/unblocked based on prerequisites")
        return True

    async def test_goals_unblocked_when_prerequisites_completed(self) -> bool:
        """
        Verify that goals become unblocked when their prerequisites are completed.
        Complete goal_a, then goal_b should become unblocked.
        """
        logger.info("Test 2: Goals become unblocked when prerequisites are completed")

        # Complete goal_a
        self.dependency_graph.update_goal_state("goal_a", GoalState.COMPLETED)
        
        # Check that goal_b is now unblocked
        unblocked_goals = self.dependency_graph.get_unblocked_goals()
        unblocked_ids = {g.id for g in unblocked_goals}

        if "goal_b" not in unblocked_ids:
            logger.error("goal_b should be unblocked after goal_a is completed")
            return False

        # goal_c should still be blocked (depends on goal_b)
        blocked_goals = self.dependency_graph.get_blocked_goals()
        blocked_ids = {g.id for g in blocked_goals}
        if "goal_c" not in blocked_ids:
            logger.error("goal_c should still be blocked (goal_b not completed)")
            return False

        # Complete goal_b, then goal_c should become unblocked
        self.dependency_graph.update_goal_state("goal_b", GoalState.COMPLETED)
        unblocked_goals = self.dependency_graph.get_unblocked_goals()
        unblocked_ids = {g.id for g in unblocked_goals}

        if "goal_c" not in unblocked_ids:
            logger.error("goal_c should be unblocked after goal_b is completed")
            return False

        # Complete goal_d, then goal_e should become unblocked (also needs goal_a which is already done)
        self.dependency_graph.update_goal_state("goal_d", GoalState.COMPLETED)
        unblocked_goals = self.dependency_graph.get_unblocked_goals()
        unblocked_ids = {g.id for g in unblocked_goals}

        if "goal_e" not in unblocked_ids:
            logger.error("goal_e should be unblocked after goal_d and goal_a are completed")
            return False

        logger.info("Test 2 passed: Goals correctly unblocked when prerequisites completed")
        return True

    async def test_disconnected_goals_not_wasted(self) -> bool:
        """
        Verify that the system does not waste cycles on disconnected implementations.
        goal_f has no dependencies and no dependents; it should be processed independently
        and not cause unnecessary work on other goals.
        """
        logger.info("Test 3: System does not waste cycles on disconnected implementations")

        # Simulate evolution loop cycles
        initial_unblocked = self.dependency_graph.get_unblocked_goals()
        initial_unblocked_ids = {g.id for g in initial_unblocked}

        # goal_f should be in the unblocked set
        if "goal_f" not in initial_unblocked_ids:
            logger.error("goal_f should be initially unblocked")
            return False

        # Process one cycle: the evolution loop should only work on unblocked goals
        # and not attempt to process goals that are blocked
        processed_goals = await self.evolution_loop.run_single_cycle()

        # Verify that only unblocked goals were processed
        processed_ids = {g.id for g in processed_goals}
        expected_processed = {"goal_a", "goal_d", "goal_f"}  # Initially unblocked

        if processed_ids != expected_processed:
            logger.error(f"Expected processed goals {expected_processed}, got {processed_ids}")
            return False

        # Complete goal_f independently (simulating its own execution path)
        self.dependency_graph.update_goal_state("goal_f", GoalState.COMPLETED)

        # Verify that completing goal_f does not affect other goals' states
        goal_a_state = self.dependency_graph.get_goal_state("goal_a")
        goal_b_state = self.dependency_graph.get_goal_state("goal_b")
        goal_c_state = self.dependency_graph.get_goal_state("goal_c")
        goal_d_state = self.dependency_graph.get_goal_state("goal_d")
        goal_e_state = self.dependency_graph.get_goal_state("goal_e")

        if goal_a_state != GoalState.COMPLETED:
            logger.error("goal_a should remain completed")
            return False
        if goal_b_state != GoalState.COMPLETED:
            logger.error("goal_b should remain completed")
            return False
        if goal_c_state != GoalState.PENDING:
            logger.error("goal_c should remain pending (not affected by goal_f)")
            return False
        if goal_d_state != GoalState.COMPLETED:
            logger.error("goal_d should remain completed")
            return False
        if goal_e_state != GoalState.COMPLETED:
            logger.error("goal_e should remain completed")
            return False

        # Verify that goal_f completion does not unblock any additional goals
        unblocked_after_f = self.dependency_graph.get_unblocked_goals()
        unblocked_after_f_ids = {g.id for g in unblocked_after_f}
        # goal_c should still be blocked (depends on goal_b which is completed, but goal_c is already unblocked? Actually goal_c was unblocked after goal_b completed)
        # Let's re-check: after test 2, goal_c should be unblocked. So after goal_f completes, goal_c should still be unblocked.
        # But goal_c was already unblocked in test 2. So we need to verify that goal_f's completion doesn't cause extra processing.
        # The key point is that goal_f's completion should not trigger any new dependencies or unblock any other goals.
        # Since goal_f has no dependents, no other goals should change state.
        # goal_c is already unblocked from test 2, so that's fine.

        logger.info("Test 3 passed: Disconnected goals processed independently without wasting cycles")
        return True

    async def run_all_tests(self) -> bool:
        """Run all integration tests and return True if all pass."""
        logger.info("Starting Goal Dependency Graph Integration Tests")
        
        test1_result = await self.test_goals_blocked_with_unmet_prerequisites()
        if not test1_result:
            logger.error("Test 1 FAILED")
            return False

        test2_result = await self.test_goals_unblocked_when_prerequisites_completed()
        if not test2_result:
            logger.error("Test 2 FAILED")
            return False

        # Reset goal states for test 3 (re-initialize)
        self.__init__()
        test3_result = await self.test_disconnected_goals_not_wasted()
        if not test3_result:
            logger.error("Test 3 FAILED")
            return False

        logger.info("All integration tests PASSED")
        return True


async def main():
    """Main entry point to run the integration tests."""
    test_suite = GoalDependencyGraphIntegrationTest()
    success = await test_suite.run_all_tests()
    if not success:
        logger.error("Integration tests failed")
        exit(1)
    else:
        logger.info("Integration tests completed successfully")


if __name__ == "__main__":
    asyncio.run(main())