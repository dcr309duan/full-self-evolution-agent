from unittest.mock import MagicMock, patch
import pytest
from datetime import datetime, timedelta

from core.goal_queue import GoalQueue
from core.curiosity_generator import CuriosityGenerator
from core.task import Task
from core.goal import Goal


@pytest.fixture
def empty_task_list():
    return []


@pytest.fixture
def sample_tasks():
    return [
        Task(id="task_1", domain="math", description="Solve equation"),
        Task(id="task_2", domain="science", description="Run experiment"),
        Task(id="task_3", domain="literature", description="Write essay"),
        Task(id="task_4", domain="math", description="Prove theorem"),
        Task(id="task_5", domain="science", description="Analyze data"),
        Task(id="task_6", domain="history", description="Research event"),
    ]


@pytest.fixture
def goal_queue():
    return GoalQueue()


@pytest.fixture
def curiosity_generator(goal_queue, sample_tasks):
    gen = CuriosityGenerator(
        goal_queue=goal_queue,
        tasks=sample_tasks,
        injection_interval=3,
        enabled=True
    )
    return gen


class TestCuriosityGenerator:

    # ---------- Test 1: Injection fires only on correct cycle intervals ----------
    def test_injection_fires_on_correct_interval(self, curiosity_generator):
        # Should not fire before interval
        for cycle in range(1, curiosity_generator.injection_interval):
            result = curiosity_generator.tick()
            assert result is False, f"Should not inject at cycle {cycle}"
            assert len(curiosity_generator.goal_queue.queue) == 0

        # Should fire exactly at interval
        result = curiosity_generator.tick()
        assert result is True
        assert len(curiosity_generator.goal_queue.queue) == 1

    def test_injection_resets_after_fire(self, curiosity_generator):
        # Fire once
        for _ in range(curiosity_generator.injection_interval):
            curiosity_generator.tick()
        initial_queue_len = len(curiosity_generator.goal_queue.queue)
        assert initial_queue_len == 1

        # Next tick should not fire (counter reset)
        result = curiosity_generator.tick()
        assert result is False
        assert len(curiosity_generator.goal_queue.queue) == initial_queue_len

    def test_injection_multiple_intervals(self, curiosity_generator):
        # Simulate multiple intervals
        for interval_num in range(1, 4):
            for _ in range(curiosity_generator.injection_interval - 1):
                curiosity_generator.tick()
            result = curiosity_generator.tick()
            assert result is True, f"Should inject at interval {interval_num}"
        assert len(curiosity_generator.goal_queue.queue) == 3

    # ---------- Test 2: Round-robin domain selection ----------
    def test_round_robin_domain_selection(self, curiosity_generator):
        # Collect domains of first N injections (N = number of unique domains)
        domains_seen = []
        for _ in range(3):  # 3 unique domains: math, science, literature
            for _ in range(curiosity_generator.injection_interval):
                curiosity_generator.tick()
            # Get the last injected goal
            last_goal = curiosity_generator.goal_queue.queue[-1]
            domains_seen.append(last_goal.domain)

        # Should cycle through domains in order
        expected_domains = ["math", "science", "literature"]
        assert domains_seen == expected_domains

    def test_round_robin_wraps_around(self, curiosity_generator):
        # Inject more than number of unique domains
        domains_seen = []
        for _ in range(6):  # 2 full cycles through 3 domains
            for _ in range(curiosity_generator.injection_interval):
                curiosity_generator.tick()
            last_goal = curiosity_generator.goal_queue.queue[-1]
            domains_seen.append(last_goal.domain)

        expected = ["math", "science", "literature", "math", "science", "literature"]
        assert domains_seen == expected

    def test_round_robin_skips_exhausted_domains(self, curiosity_generator):
        # Manually exhaust math domain tasks
        math_tasks = [t for t in curiosity_generator.tasks if t.domain == "math"]
        for t in math_tasks:
            curiosity_generator.mark_task_completed(t.id)

        # Inject multiple times; math should be skipped
        domains_seen = []
        for _ in range(4):
            for _ in range(curiosity_generator.injection_interval):
                curiosity_generator.tick()
            last_goal = curiosity_generator.goal_queue.queue[-1]
            domains_seen.append(last_goal.domain)

        # Should only see science and literature (no math)
        assert "math" not in domains_seen
        assert domains_seen == ["science", "literature", "science", "literature"]

    # ---------- Test 3: Injected goal format and queue addition ----------
    def test_injected_goal_format(self, curiosity_generator):
        for _ in range(curiosity_generator.injection_interval):
            curiosity_generator.tick()

        goal = curiosity_generator.goal_queue.queue[0]
        assert isinstance(goal, Goal)
        assert hasattr(goal, 'id')
        assert hasattr(goal, 'domain')
        assert hasattr(goal, 'description')
        assert hasattr(goal, 'timestamp')
        assert goal.domain in ["math", "science", "literature"]
        assert isinstance(goal.timestamp, datetime)

    def test_goal_added_to_queue(self, curiosity_generator):
        assert len(curiosity_generator.goal_queue.queue) == 0
        for _ in range(curiosity_generator.injection_interval):
            curiosity_generator.tick()
        assert len(curiosity_generator.goal_queue.queue) == 1

    def test_goal_queue_order_preserved(self, curiosity_generator):
        # Inject multiple goals
        for _ in range(3):
            for _ in range(curiosity_generator.injection_interval):
                curiosity_generator.tick()

        queue = curiosity_generator.goal_queue.queue
        assert len(queue) == 3
        # Check timestamps are in order
        timestamps = [g.timestamp for g in queue]
        assert timestamps == sorted(timestamps)

    # ---------- Test 4: Structural change logging ----------
    def test_logging_on_injection(self, curiosity_generator):
        with patch.object(curiosity_generator, 'log_structural_change') as mock_log:
            for _ in range(curiosity_generator.injection_interval):
                curiosity_generator.tick()
            mock_log.assert_called_once()

    def test_logging_content(self, curiosity_generator):
        for _ in range(curiosity_generator.injection_interval):
            curiosity_generator.tick()
        goal = curiosity_generator.goal_queue.queue[0]
        log_entry = curiosity_generator.get_last_log()
        assert log_entry is not None
        assert "injected" in log_entry.lower()
        assert goal.id in log_entry
        assert goal.domain in log_entry

    def test_logging_not_on_no_injection(self, curiosity_generator):
        with patch.object(curiosity_generator, 'log_structural_change') as mock_log:
            curiosity_generator.tick()  # Not at interval
            mock_log.assert_not_called()

    # ---------- Test 5: Edge cases ----------
    def test_all_tasks_exhausted(self, curiosity_generator):
        # Mark all tasks as completed
        for task in curiosity_generator.tasks:
            curiosity_generator.mark_task_completed(task.id)

        # Should not inject any goal
        for _ in range(10):
            result = curiosity_generator.tick()
            assert result is False
        assert len(curiosity_generator.goal_queue.queue) == 0

    def test_empty_task_list(self, goal_queue, empty_task_list):
        gen = CuriosityGenerator(
            goal_queue=goal_queue,
            tasks=empty_task_list,
            injection_interval=3,
            enabled=True
        )
        for _ in range(10):
            result = gen.tick()
            assert result is False
        assert len(gen.goal_queue.queue) == 0

    def test_disabled_curiosity(self, goal_queue, sample_tasks):
        gen = CuriosityGenerator(
            goal_queue=goal_queue,
            tasks=sample_tasks,
            injection_interval=3,
            enabled=False
        )
        for _ in range(10):
            result = gen.tick()
            assert result is False
        assert len(gen.goal_queue.queue) == 0

    def test_disabled_curiosity_no_logging(self, goal_queue, sample_tasks):
        gen = CuriosityGenerator(
            goal_queue=goal_queue,
            tasks=sample_tasks,
            injection_interval=3,
            enabled=False
        )
        with patch.object(gen, 'log_structural_change') as mock_log:
            for _ in range(10):
                gen.tick()
            mock_log.assert_not_called()

    def test_single_task_single_domain(self, goal_queue):
        single_task = [Task(id="task_1", domain="math", description="Solve")]
        gen = CuriosityGenerator(
            goal_queue=goal_queue,
            tasks=single_task,
            injection_interval=2,
            enabled=True
        )
        for _ in range(gen.injection_interval):
            gen.tick()
        assert len(gen.goal_queue.queue) == 1
        assert gen.goal_queue.queue[0].domain == "math"

        # After task exhausted, no more injections
        gen.mark_task_completed("task_1")
        for _ in range(10):
            gen.tick()
        assert len(gen.goal_queue.queue) == 1

    def test_injection_interval_one(self, goal_queue, sample_tasks):
        gen = CuriosityGenerator(
            goal_queue=goal_queue,
            tasks=sample_tasks,
            injection_interval=1,
            enabled=True
        )
        result = gen.tick()
        assert result is True
        assert len(gen.goal_queue.queue) == 1