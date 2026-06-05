import pytest
import random
import os
import tempfile
import shutil
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

@pytest.fixture
def temp_dir():
    """Create a temporary directory for test file generation."""
    dirpath = tempfile.mkdtemp()
    yield dirpath
    shutil.rmtree(dirpath)

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

# Test 5: generate_ecology_pressure creates valid Python test files
class TestGenerateEcologyPressure:
    def test_creates_valid_python_file(self, engine, temp_dir):
        """Test that generate_ecology_pressure() creates valid Python test files."""
        test_code = "def test_example(): assert 1 + 1 == 2"
        filepath = os.path.join(temp_dir, "test_generated.py")
        engine.generate_ecology_pressure(test_code, filepath)
        
        assert os.path.exists(filepath)
        with open(filepath, 'r') as f:
            content = f.read()
        assert 'def test_' in content
        assert 'assert' in content
        # Verify it's valid Python
        compile(content, filepath, 'exec')

    def test_creates_multiple_test_files(self, engine, temp_dir):
        """Test that multiple calls create separate valid files."""
        test_codes = [
            "def test_add(): assert 1 + 1 == 2",
            "def test_sub(): assert 2 - 1 == 1"
        ]
        for i, code in enumerate(test_codes):
            filepath = os.path.join(temp_dir, f"test_generated_{i}.py")
            engine.generate_ecology_pressure(code, filepath)
            assert os.path.exists(filepath)

    def test_generated_file_is_executable(self, engine, temp_dir):
        """Test that generated test files can be executed."""
        test_code = "def test_example(): assert 1 + 1 == 2"
        filepath = os.path.join(temp_dir, "test_executable.py")
        engine.generate_ecology_pressure(test_code, filepath)
        
        # Execute the generated file
        exec_globals = {}
        with open(filepath, 'r') as f:
            exec(f.read(), exec_globals)
        assert 'test_example' in exec_globals
        exec_globals['test_example']()

# Test 6: Stress tests introduce resource constraints
class TestStressTests:
    def test_memory_limit_introduced(self, engine):
        """Test that stress tests include memory limits."""
        stress_test = engine.generate_stress_test(memory_limit_mb=100)
        assert stress_test.memory_limit_mb == 100
        assert 'memory' in stress_test.code.lower() or 'resource' in stress_test.code.lower()

    def test_timeout_introduced(self, engine):
        """Test that stress tests include timeouts."""
        stress_test = engine.generate_stress_test(timeout_seconds=5)
        assert stress_test.timeout_seconds == 5
        assert 'timeout' in stress_test.code.lower() or 'time' in stress_test.code.lower()

    def test_both_constraints_applied(self, engine):
        """Test that both memory and timeout constraints can be applied."""
        stress_test = engine.generate_stress_test(memory_limit_mb=200, timeout_seconds=10)
        assert stress_test.memory_limit_mb == 200
        assert stress_test.timeout_seconds == 10

    def test_default_constraints(self, engine):
        """Test default constraints when none specified."""
        stress_test = engine.generate_stress_test()
        assert stress_test.memory_limit_mb is not None
        assert stress_test.timeout_seconds is not None

# Test 7: Cross-module tests reference at least 2 different modules
class TestCrossModuleTests:
    def test_references_two_modules(self, engine):
        """Test that cross-module tests reference at least 2 different modules."""
        cross_module_test = engine.generate_cross_module_test(['module_a', 'module_b'])
        code = cross_module_test.code
        assert 'module_a' in code
        assert 'module_b' in code

    def test_references_multiple_modules(self, engine):
        """Test that cross-module tests can reference more than 2 modules."""
        modules = ['module_a', 'module_b', 'module_c']
        cross_module_test = engine.generate_cross_module_test(modules)
        code = cross_module_test.code
        for module in modules:
            assert module in code

    def test_imports_are_valid(self, engine):
        """Test that cross-module tests have valid import statements."""
        cross_module_test = engine.generate_cross_module_test(['os', 'sys'])
        code = cross_module_test.code
        assert 'import os' in code or 'from os' in code
        assert 'import sys' in code or 'from sys' in code

# Test 8: Novel domain tests are not duplicates of existing tests
class TestNovelDomainTests:
    def test_not_duplicate_of_existing(self, engine):
        """Test that novel domain tests are not duplicates of existing tests."""
        existing_tests = [
            Test(code="def test_add(): assert 1+1==2", difficulty=DifficultyLevel.EASY, test_cases=[]),
            Test(code="def test_sub(): assert 2-1==1", difficulty=DifficultyLevel.EASY, test_cases=[])
        ]
        novel_test = engine.generate_novel_domain_test(existing_tests)
        assert novel_test.code != existing_tests[0].code
        assert novel_test.code != existing_tests[1].code

    def test_unique_function_name(self, engine):
        """Test that novel tests have unique function names."""
        existing_tests = [
            Test(code="def test_add(): pass", difficulty=DifficultyLevel.EASY, test_cases=[])
        ]
        novel_test = engine.generate_novel_domain_test(existing_tests)
        assert 'test_add' not in novel_test.code

    def test_different_domain(self, engine):
        """Test that novel tests cover different domains."""
        existing_tests = [
            Test(code="def test_math(): assert 1+1==2", difficulty=DifficultyLevel.EASY, test_cases=[])
        ]
        novel_test = engine.generate_novel_domain_test(existing_tests)
        assert 'math' not in novel_test.code.lower() or 'test_math' not in novel_test.code

# Test 9: Novelty threshold filtering works
class TestNoveltyThreshold:
    def test_rejects_high_similarity(self, engine):
        """Test that tests with similarity >0.7 to existing tests are rejected."""
        existing_tests = [
            Test(code="def test_add(): assert 1+1==2", difficulty=DifficultyLevel.EASY, test_cases=[])
        ]
        similar_test = Test(code="def test_add(): assert 1+1==2", difficulty=DifficultyLevel.EASY, test_cases=[])
        assert engine.is_novel(similar_test, existing_tests, threshold=0.7) == False

    def test_accepts_low_similarity(self, engine):
        """Test that tests with similarity <=0.7 are accepted."""
        existing_tests = [
            Test(code="def test_add(): assert 1+1==2", difficulty=DifficultyLevel.EASY, test_cases=[])
        ]
        novel_test = Test(code="def test_multiply(): assert 2*3==6", difficulty=DifficultyLevel.EASY, test_cases=[])
        assert engine.is_novel(novel_test, existing_tests, threshold=0.7) == True

    def test_threshold_configurable(self, engine):
        """Test that the threshold is configurable."""
        existing_tests = [
            Test(code="def test_add(): assert 1+1==2", difficulty=DifficultyLevel.EASY, test_cases=[])
        ]
        similar_test = Test(code="def test_add(): assert 1+1==2", difficulty=DifficultyLevel.EASY, test_cases=[])
        # With lower threshold, even similar tests might be accepted
        assert engine.is_novel(similar_test, existing_tests, threshold=0.5) == False
        # With higher threshold, similar tests are definitely rejected
        assert engine.is_novel(similar_test, existing_tests, threshold=0.9) == False

    def test_empty_existing_list(self, engine):
        """Test that all tests are novel when no existing tests."""
        test = Test(code="def test_anything(): pass", difficulty=DifficultyLevel.EASY, test_cases=[])
        assert engine.is_novel(test, [], threshold=0.7) == True

# Test 10: Engine tracks which new tests led to fitness improvements
class TestFitnessTracking:
    def test_tracks_improving_tests(self, engine):
        """Test that the engine correctly tracks which new tests led to fitness improvements."""
        initial_fitness = 0.5
        test = Test(code="def test_improve(): assert 1+1==2", difficulty=DifficultyLevel.EASY, test_cases=[])
        engine.add_test(test)
        new_fitness = 0.8
        engine.update_fitness_tracking(test, initial_fitness, new_fitness)
        assert test in engine.improving_tests
        assert test not in engine.non_improving_tests

    def test_tracks_non_improving_tests(self, engine):
        """Test that the engine tracks tests that don't improve fitness."""
        initial_fitness = 0.5
        test = Test(code="def test_no_improve(): assert 1+1==2", difficulty=DifficultyLevel.EASY, test_cases=[])
        engine.add_test(test)
        new_fitness = 0.5
        engine.update_fitness_tracking(test, initial_fitness, new_fitness)
        assert test in engine.non_improving_tests
        assert test not in engine.improving_tests

    def test_tracks_decreasing_fitness(self, engine):
        """Test that the engine tracks tests that decrease fitness."""
        initial_fitness = 0.5
        test = Test(code="def test_decrease(): assert 1+1==2", difficulty=DifficultyLevel.EASY, test_cases=[])
        engine.add_test(test)
        new_fitness = 0.3
        engine.update_fitness_tracking(test, initial_fitness, new_fitness)
        assert test in engine.non_improving_tests

    def test_multiple_tests_tracked(self, engine):
        """Test that multiple tests can be tracked simultaneously."""
        test1 = Test(code="def test1(): pass", difficulty=DifficultyLevel.EASY, test_cases=[])
        test2 = Test(code="def test2(): pass", difficulty=DifficultyLevel.EASY, test_cases=[])
        engine.add_test(test1)
        engine.add_test(test2)
        engine.update_fitness_tracking(test1, 0.5, 0.8)
        engine.update_fitness_tracking(test2, 0.5, 0.4)
        assert len(engine.improving_tests) == 1
        assert len(engine.non_improving_tests) == 1

# Test 11: Engine respects max_new_tests_per_cycle limit
class TestMaxNewTestsPerCycle:
    def test_respects_limit(self, engine):
        """Test that the engine respects the max_new_tests_per_cycle limit."""
        max_tests = 3
        engine.max_new_tests_per_cycle = max_tests
        tests_generated = []
        for _ in range(10):
            test = engine.generate_new_test(DifficultyLevel.EASY)
            if engine.can_add_test(test):
                tests_generated.append(test)
                engine.add_test(test)
        assert len(tests_generated) <= max_tests

    def test_blocks_after_limit(self, engine):
        """Test that the engine blocks adding tests after reaching the limit."""
        engine.max_new_tests_per_cycle = 2
        test1 = Test(code="def test1(): pass", difficulty=DifficultyLevel.EASY, test_cases=[])
        test2 = Test(code="def test2(): pass", difficulty=DifficultyLevel.EASY, test_cases=[])
        test3 = Test(code="def test3(): pass", difficulty=DifficultyLevel.EASY, test_cases=[])
        
        assert engine.can_add_test(test1)
        engine.add_test(test1)
        assert engine.can_add_test(test2)
        engine.add_test(test2)
        assert not engine.can_add_test(test3)

    def test_resets_after_cycle(self, engine):
        """Test that the limit resets after a cycle."""
        engine.max_new_tests_per_cycle = 1
        test1 = Test(code="def test1(): pass", difficulty=DifficultyLevel.EASY, test_cases=[])
        test2 = Test(code="def test2(): pass", difficulty=DifficultyLevel.EASY, test_cases=[])
        
        assert engine.can_add_test(test1)
        engine.add_test(test1)
        assert not engine.can_add_test(test2)
        
        engine.reset_cycle()
        assert engine.can_add_test(test2)

    def test_configurable_limit(self, engine):
        """Test that the limit is configurable."""
        engine.max_new_tests_per_cycle = 5
        assert engine.max_new_tests_per_cycle == 5
        
        engine.max_new_tests_per_cycle = 10
        assert engine.max_new_tests_per_cycle == 10

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

    def test_comprehensive_pipeline(self, engine, temp_dir):
        """Test the complete pipeline with all features."""
        # Generate initial tests
        test1 = engine.generate_new_test(DifficultyLevel.EASY)
        test2 = engine.generate_new_test(DifficultyLevel.MEDIUM)
        
        # Generate ecology pressure
        engine.generate_ecology_pressure(test1.code, os.path.join(temp_dir, "test1.py"))
        engine.generate_ecology_pressure(test2.code, os.path.join(temp_dir, "test2.py"))
        
        # Generate stress test
        stress_test = engine.generate_stress_test(memory_limit_mb=100, timeout_seconds=5)
        assert stress_test.memory_limit_mb == 100
        assert stress_test.timeout_seconds == 5
        
        # Generate cross-module test
        cross_test = engine.generate_cross_module_test(['os', 'sys'])
        assert 'os' in cross_test.code
        assert 'sys' in cross_test.code
        
        # Test novelty filtering
        existing_tests = [test1, test2]
        novel_test = engine.generate_novel_domain_test(existing_tests)
        assert engine.is_novel(novel_test, existing_tests, threshold=0.7)
        
        # Test fitness tracking
        engine.add_test(novel_test)
        engine.update_fitness_tracking(novel_test, 0.5, 0.8)
        assert novel_test in engine.improving_tests
        
        # Test max tests per cycle
        engine.max_new_tests_per_cycle = 2
        assert engine.can_add_test(test1)
        engine.add_test(test1)
        assert not engine.can_add_test(test2)

# New integration tests for mutate_test_suite()
class TestMutateTestSuite:
    def test_mutate_test_suite_modifies_at_least_one_file(self, engine, temp_dir):
        """Test that mutate_test_suite() actually modifies at least one test file."""
        # Create initial test files
        test_file1 = os.path.join(temp_dir, "test_example1.py")
        test_file2 = os.path.join(temp_dir, "test_example2.py")
        with open(test_file1, 'w') as f:
            f.write("def test_add(): assert 1 + 1 == 2\n")
        with open(test_file2, 'w') as f:
            f.write("def test_sub(): assert 2 - 1 == 1\n")
        
        # Record original content
        with open(test_file1, 'r') as f:
            original1 = f.read()
        with open(test_file2, 'r') as f:
            original2 = f.read()
        
        # Run mutate_test_suite
        engine.mutate_test_suite(temp_dir)
        
        # Check that at least one file was modified
        with open(test_file1, 'r') as f:
            new1 = f.read()
        with open(test_file2, 'r') as f:
            new2 = f.read()
        
        assert new1 != original1 or new2 != original2, "No test files were modified"

    def test_mutate_test_suite_can_create_new_test_file(self, engine, temp_dir):
        """Test that mutate_test_suite() can create a new test file."""
        # Create initial test files
        test_file1 = os.path.join(temp_dir, "test_example1.py")
        with open(test_file1, 'w') as f:
            f.write("def test_add(): assert 1 + 1 == 2\n")
        
        # Count initial files
        initial_files = set(os.listdir(temp_dir))
        
        # Run mutate_test_suite
        engine.mutate_test_suite(temp_dir)
        
        # Check that a new file was created
        final_files = set(os.listdir(temp_dir))
        new_files = final_files - initial_files
        assert len(new_files) > 0, "No new test file was created"
        
        # Verify the new file is a Python file
        for new_file in new_files:
            assert new_file.endswith('.py'), f"New file {new_file} is not a Python file"

    def test_mutate_test_suite_new_tests_are_valid_python(self, engine, temp_dir):
        """Test that new tests created by mutate_test_suite() are valid Python."""
        # Create initial test files
        test_file1 = os.path.join(temp_dir, "test_example1.py")
        with open(test_file1, 'w') as f:
            f.write("def test_add(): assert 1 + 1 == 2\n")
        
        # Record initial files
        initial_files = set(os.listdir(temp_dir))
        
        # Run mutate_test_suite
        engine.mutate_test_suite(temp_dir)
        
        # Check all files (including modified ones) for valid Python
        final_files = set(os.listdir(temp_dir))
        for file_name in final_files:
            file_path = os.path.join(temp_dir, file_name)
            if file_name.endswith('.py'):
                with open(file_path, 'r') as f:
                    content = f.read()
                try:
                    compile(content, file_path, 'exec')
                except SyntaxError as e:
                    pytest.fail(f"File {file_name} contains invalid Python: {e}")
        
        # Also verify that new files contain at least one test function
        new_files = final_files - initial_files
        for new_file in new_files:
            file_path = os.path.join(temp_dir, new_file)
            with open(file_path, 'r') as f:
                content = f.read()
            assert 'def test_' in content, f"New file {new_file} does not contain a test function"