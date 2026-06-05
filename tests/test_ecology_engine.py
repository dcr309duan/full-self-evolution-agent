import pytest
import random
from unittest.mock import Mock, patch, PropertyMock
from ecology_engine import EcologyEngine, Test, DifficultyLevel, OverfittingDetector

# Fixtures
@pytest.fixture
def engine():
    return EcologyEngine(seed=42)

@pytest.fixture
def easy_test():
    return Test(
        code="def add(a, b): return a + b",
        difficulty=DifficultyLevel.EASY,
        test_cases=[((1, 2), 3), ((0, 0), 0)]
    )

@pytest.fixture
def medium_test():
    return Test(
        code="def multiply(a, b): return a * b",
        difficulty=DifficultyLevel.MEDIUM,
        test_cases=[((2, 3), 6), ((0, 5), 0), ((-1, 4), -4)]
    )

@pytest.fixture
def hard_test():
    return Test(
        code="def fibonacci(n): return n if n <= 1 else fibonacci(n-1) + fibonacci(n-2)",
        difficulty=DifficultyLevel.HARD,
        test_cases=[((0,), 0), ((1,), 1), ((5,), 5), ((10,), 55)]
    )

# Test 1: New tests are generated with appropriate difficulty
class TestNewTestGeneration:
    def test_generates_easy_test(self, engine):
        test = engine.generate_new_test(difficulty=DifficultyLevel.EASY)
        assert test.difficulty == DifficultyLevel.EASY
        assert len(test.test_cases) >= 2
        assert len(test.test_cases) <= 5

    def test_generates_medium_test(self, engine):
        test = engine.generate_new_test(difficulty=DifficultyLevel.MEDIUM)
        assert test.difficulty == DifficultyLevel.MEDIUM
        assert len(test.test_cases) >= 3
        assert len(test.test_cases) <= 7

    def test_generates_hard_test(self, engine):
        test = engine.generate_new_test(difficulty=DifficultyLevel.HARD)
        assert test.difficulty == DifficultyLevel.HARD
        assert len(test.test_cases) >= 4
        assert len(test.test_cases) <= 10

    def test_difficulty_increases_complexity(self, engine):
        easy = engine.generate_new_test(DifficultyLevel.EASY)
        hard = engine.generate_new_test(DifficultyLevel.HARD)
        # Hard tests should have more test cases on average
        assert len(hard.test_cases) >= len(easy.test_cases)

    def test_generated_test_is_executable(self, engine):
        test = engine.generate_new_test(DifficultyLevel.EASY)
        try:
            exec(test.code)
        except Exception as e:
            pytest.fail(f"Generated test code is not executable: {e}")

# Test 2: Existing tests can be mutated to be harder
class TestTestMutation:
    def test_mutate_increases_difficulty(self, engine, easy_test):
        mutated = engine.mutate_test(easy_test, target_difficulty=DifficultyLevel.MEDIUM)
        assert mutated.difficulty == DifficultyLevel.MEDIUM
        assert len(mutated.test_cases) >= len(easy_test.test_cases)

    def test_mutate_preserves_original_logic(self, engine, medium_test):
        mutated = engine.mutate_test(medium_test, target_difficulty=DifficultyLevel.HARD)
        # The core function should still work for original test cases
        for args, expected in medium_test.test_cases:
            try:
                result = eval(mutated.code)(*args)
                assert result == expected, f"Mutation broke original behavior for {args}"
            except Exception as e:
                pytest.fail(f"Mutation broke original behavior: {e}")

    def test_mutate_adds_edge_cases(self, engine, easy_test):
        mutated = engine.mutate_test(easy_test, target_difficulty=DifficultyLevel.HARD)
        # Harder tests should include edge cases
        edge_cases = [(0,), (1,), (-1,), (float('inf'),), (float('-inf'),)]
        for args in edge_cases:
            assert any(args == tc[0] for tc in mutated.test_cases), f"Missing edge case {args}"

    def test_mutate_does_not_reduce_test_cases(self, engine, medium_test):
        mutated = engine.mutate_test(medium_test, target_difficulty=DifficultyLevel.HARD)
        assert len(mutated.test_cases) >= len(medium_test.test_cases)

    def test_mutate_preserves_syntax(self, engine, hard_test):
        mutated = engine.mutate_test(hard_test, target_difficulty=DifficultyLevel.HARD)
        try:
            compile(mutated.code, '<test>', 'exec')
        except SyntaxError as e:
            pytest.fail(f"Mutated code has syntax error: {e}")

# Test 3: Engine doesn't create impossible tests
class TestImpossibleTests:
    def test_no_contradictory_test_cases(self, engine):
        test = engine.generate_new_test(DifficultyLevel.EASY)
        # Check that no two test cases have same input but different expected output
        input_map = {}
        for args, expected in test.test_cases:
            if args in input_map:
                assert input_map[args] == expected, f"Contradictory test cases for input {args}"
            else:
                input_map[args] = expected

    def test_no_unsolvable_difficulty(self, engine):
        # Even hardest tests should be solvable by a perfect agent
        test = engine.generate_new_test(DifficultyLevel.HARD)
        # The test should have at least one valid solution
        try:
            exec(test.code)
            # Verify the function exists and is callable
            func_name = test.code.split('def ')[1].split('(')[0].strip()
            func = locals()[func_name]
            for args, expected in test.test_cases:
                result = func(*args)
                assert result == expected, f"Test case ({args} -> {expected}) failed for generated code"
        except Exception as e:
            pytest.fail(f"Generated test is impossible: {e}")

    def test_no_infinite_loops(self, engine):
        test = engine.generate_new_test(DifficultyLevel.EASY)
        # All test cases should complete quickly
        import signal
        class TimeoutError(Exception):
            pass

        def handler(signum, frame):
            raise TimeoutError("Test case timed out")

        signal.signal(signal.SIGALRM, handler)
        try:
            exec(test.code)
            func_name = test.code.split('def ')[1].split('(')[0].strip()
            func = locals()[func_name]
            for args, expected in test.test_cases:
                signal.alarm(1)  # 1 second timeout
                try:
                    func(*args)
                except TimeoutError:
                    pytest.fail(f"Test case {args} caused infinite loop")
                finally:
                    signal.alarm(0)
        finally:
            signal.alarm(0)

    def test_no_division_by_zero(self, engine):
        test = engine.generate_new_test(DifficultyLevel.EASY)
        # Generated tests should not cause division by zero
        try:
            exec(test.code)
            func_name = test.code.split('def ')[1].split('(')[0].strip()
            func = locals()[func_name]
            for args, expected in test.test_cases:
                try:
                    func(*args)
                except ZeroDivisionError:
                    pytest.fail(f"Test case {args} caused division by zero")
        except Exception:
            pass  # Other errors are acceptable

# Test 4: Engine detects overfitting
class TestOverfittingDetection:
    def test_detects_identical_performance(self, engine):
        # Simulate agent that always gets same score
        agent_scores = [0.95, 0.95, 0.95, 0.95, 0.95]
        assert engine.detect_overfitting(agent_scores) == True

    def test_detects_perfect_score_stagnation(self, engine):
        # Agent that gets perfect scores but doesn't improve
        agent_scores = [1.0, 1.0, 1.0, 1.0, 1.0]
        assert engine.detect_overfitting(agent_scores) == True

    def test_does_not_false_positive_improving(self, engine):
        # Agent that is genuinely improving
        agent_scores = [0.5, 0.6, 0.7, 0.8, 0.9]
        assert engine.detect_overfitting(agent_scores) == False

    def test_does_not_false_positive_varied(self, engine):
        # Agent with varied performance
        agent_scores = [0.8, 0.7, 0.9, 0.6, 0.85]
        assert engine.detect_overfitting(agent_scores) == False

    def test_detects_overfitting_with_noise(self, engine):
        # Agent that is overfitting but with small noise
        agent_scores = [0.98, 0.97, 0.99, 0.98, 0.97]
        assert engine.detect_overfitting(agent_scores) == True

    def test_insufficient_data_returns_false(self, engine):
        # Not enough data points to detect overfitting
        agent_scores = [0.9]
        assert engine.detect_overfitting(agent_scores) == False

    def test_empty_scores_returns_false(self, engine):
        assert engine.detect_overfitting([]) == False

    def test_overfitting_threshold_configurable(self, engine):
        # Test with custom threshold
        engine.overfitting_threshold = 0.02  # Very sensitive
        agent_scores = [0.9, 0.91, 0.9, 0.91, 0.9]
        assert engine.detect_overfitting(agent_scores) == True

        engine.overfitting_threshold = 0.2  # Very tolerant
        assert engine.detect_overfitting(agent_scores) == False

# Integration tests
class TestEcologyEngineIntegration:
    def test_full_workflow(self, engine):
        # Simulate a complete workflow: generate, mutate, detect overfitting
        initial_test = engine.generate_new_test(DifficultyLevel.EASY)
        mutated_test = engine.mutate_test(initial_test, DifficultyLevel.HARD)
        
        # Verify mutation chain
        assert mutated_test.difficulty == DifficultyLevel.HARD
        assert len(mutated_test.test_cases) >= len(initial_test.test_cases)
        
        # Simulate agent scores
        scores = [0.7, 0.75, 0.8, 0.85, 0.9]
        assert not engine.detect_overfitting(scores)
        
        # Simulate overfitting
        overfit_scores = [0.95, 0.95, 0.95, 0.95, 0.95]
        assert engine.detect_overfitting(overfit_scores)

    def test_difficulty_progression(self, engine):
        # Generate tests of increasing difficulty
        tests = []
        for difficulty in [DifficultyLevel.EASY, DifficultyLevel.MEDIUM, DifficultyLevel.HARD]:
            test = engine.generate_new_test(difficulty)
            tests.append(test)
        
        # Each subsequent test should be at least as hard
        for i in range(len(tests) - 1):
            assert tests[i].difficulty.value <= tests[i+1].difficulty.value