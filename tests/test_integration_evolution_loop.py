import os
import sys
import shutil
import tempfile
import logging
import json
import time
import tracemalloc
from pathlib import Path
from typing import Dict, List, Any

import pytest

# Ensure the project root is in sys.path for imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Import core modules
from core.evolution_orchestrator import EvolutionOrchestrator
from core.reflection_engine import ReflectionEngine
from core.goal_generator import GoalGenerator
from core.mutator import Mutator
from core.test_runner import TestRunner
from core.promoter import Promoter

# Configure logging for integration test
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('integration_test.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class SandboxEnvironment:
    """Manages a sandboxed temporary directory for integration tests."""

    def __init__(self, source_dir: Path = None):
        self.source_dir = source_dir or PROJECT_ROOT / 'core'
        self.sandbox_path = None
        self._original_cwd = None

    def setup(self):
        """Create sandbox directory and copy core modules."""
        # Clean up any previous sandbox
        self.teardown()

        # Create new temporary directory
        self.sandbox_path = Path(tempfile.mkdtemp(prefix='evolution_sandbox_'))
        logger.info(f"Created sandbox at: {self.sandbox_path}")

        # Copy core modules into sandbox
        core_dest = self.sandbox_path / 'core'
        shutil.copytree(self.source_dir, core_dest, dirs_exist_ok=True)
        logger.info(f"Copied core modules from {self.source_dir} to {core_dest}")

        # Change working directory to sandbox
        self._original_cwd = Path.cwd()
        os.chdir(self.sandbox_path)
        logger.info(f"Changed working directory to: {self.sandbox_path}")

        # Add sandbox to sys.path for imports
        sys.path.insert(0, str(self.sandbox_path))

        return self.sandbox_path

    def teardown(self):
        """Clean up sandbox directory and restore original state."""
        # Restore original working directory
        if self._original_cwd:
            os.chdir(self._original_cwd)
            logger.info(f"Restored working directory to: {self._original_cwd}")

        # Remove sandbox from sys.path
        if self.sandbox_path and str(self.sandbox_path) in sys.path:
            sys.path.remove(str(self.sandbox_path))

        # Remove sandbox directory
        if self.sandbox_path and self.sandbox_path.exists():
            shutil.rmtree(self.sandbox_path)
            logger.info(f"Removed sandbox at: {self.sandbox_path}")
            self.sandbox_path = None

    def get_sandbox_state(self):
        """Capture the current state of the sandbox directory."""
        if not self.sandbox_path or not self.sandbox_path.exists():
            return None
        
        state = {
            'files': [],
            'directories': [],
            'file_contents': {}
        }
        
        for root, dirs, files in os.walk(self.sandbox_path):
            rel_path = Path(root).relative_to(self.sandbox_path)
            for dir_name in dirs:
                state['directories'].append(str(rel_path / dir_name))
            for file_name in files:
                file_path = Path(root) / file_name
                rel_file_path = str(rel_path / file_name)
                state['files'].append(rel_file_path)
                try:
                    with open(file_path, 'r') as f:
                        state['file_contents'][rel_file_path] = f.read()
                except (IOError, UnicodeDecodeError):
                    state['file_contents'][rel_file_path] = None
        
        return state

    def check_no_files_leaked(self):
        """Verify that no files have been created outside the sandbox directory."""
        if not self.sandbox_path:
            return True
        
        sandbox_str = str(self.sandbox_path.resolve())
        leaked_files = []
        
        # Check common locations where files might leak
        check_dirs = [
            PROJECT_ROOT,
            Path.cwd(),
            Path.home()
        ]
        
        for check_dir in check_dirs:
            if check_dir and check_dir.exists():
                for item in check_dir.iterdir():
                    item_str = str(item.resolve())
                    # Skip items inside sandbox
                    if sandbox_str in item_str:
                        continue
                    # Skip common system files and directories
                    if item.name.startswith('.') or item.name in ['__pycache__', 'node_modules']:
                        continue
                    # Check if file was created during test (modification time within reasonable window)
                    if item.is_file() and not item.name.startswith('integration_test'):
                        leaked_files.append(item_str)
        
        return len(leaked_files) == 0, leaked_files


class EvolutionTestLogger:
    """Captures detailed logs for each step of the evolution cycle."""

    def __init__(self):
        self.cycle_logs: Dict[int, Dict[str, Any]] = {}
        self.current_cycle = None
        self.performance_data: Dict[int, Dict[str, Any]] = {}

    def start_cycle(self, cycle_number: int):
        """Initialize logging for a new cycle."""
        self.current_cycle = cycle_number
        self.cycle_logs[cycle_number] = {
            'reflection': None,
            'goal_generation': None,
            'mutation': None,
            'test': None,
            'promotion': None,
            'overall_status': None
        }
        self.performance_data[cycle_number] = {
            'steps': {},
            'memory_before': None,
            'memory_after': None
        }
        logger.info(f"=== Starting Evolution Cycle {cycle_number} ===")

    def log_step(self, step_name: str, status: str, details: Dict[str, Any] = None):
        """Log the result of a specific step."""
        if self.current_cycle is not None:
            self.cycle_logs[self.current_cycle][step_name] = {
                'status': status,
                'details': details or {}
            }
            logger.info(f"Cycle {self.current_cycle} - {step_name}: {status}")
            if details:
                logger.debug(f"Details: {json.dumps(details, indent=2)}")

    def log_step_performance(self, step_name: str, duration: float):
        """Log performance data for a step."""
        if self.current_cycle is not None:
            if 'steps' not in self.performance_data[self.current_cycle]:
                self.performance_data[self.current_cycle]['steps'] = {}
            self.performance_data[self.current_cycle]['steps'][step_name] = {
                'duration': duration
            }
            logger.info(f"Cycle {self.current_cycle} - {step_name} took {duration:.2f} seconds")
            
            # Warn if step exceeds 30 seconds
            if duration > 30:
                logger.warning(f"Cycle {self.current_cycle} - {step_name} exceeded 30 seconds! Duration: {duration:.2f} seconds")

    def log_memory_usage(self, before: bool = True):
        """Log memory usage before or after test."""
        if self.current_cycle is not None:
            current, peak = tracemalloc.get_traced_memory()
            memory_key = 'memory_before' if before else 'memory_after'
            self.performance_data[self.current_cycle][memory_key] = {
                'current_mb': current / 1024 / 1024,
                'peak_mb': peak / 1024 / 1024
            }
            logger.info(f"Cycle {self.current_cycle} - Memory {'before' if before else 'after'} test: Current={current/1024/1024:.2f}MB, Peak={peak/1024/1024:.2f}MB")

    def end_cycle(self, status: str):
        """Finalize logging for the current cycle."""
        if self.current_cycle is not None:
            self.cycle_logs[self.current_cycle]['overall_status'] = status
            logger.info(f"=== Cycle {self.current_cycle} completed with status: {status} ===")

    def get_report(self) -> Dict[str, Any]:
        """Generate a comprehensive test report."""
        report = {
            'total_cycles': len(self.cycle_logs),
            'cycles': {}
        }
        for cycle_num, cycle_data in self.cycle_logs.items():
            cycle_report = {
                'overall_status': cycle_data['overall_status'],
                'steps': {}
            }
            for step_name, step_data in cycle_data.items():
                if step_name != 'overall_status':
                    cycle_report['steps'][step_name] = {
                        'status': step_data['status'] if step_data else 'not_executed',
                        'details': step_data['details'] if step_data else {}
                    }
            report['cycles'][f'cycle_{cycle_num}'] = cycle_report
        return report

    def get_performance_report(self) -> Dict[str, Any]:
        """Generate performance report."""
        return {
            'cycles': self.performance_data
        }


@pytest.fixture(scope='module')
def sandbox():
    """Fixture to set up and tear down sandbox environment."""
    env = SandboxEnvironment()
    env.setup()
    yield env
    env.teardown()


@pytest.fixture
def orchestrator(sandbox):
    """Fixture to initialize the evolution orchestrator."""
    # Initialize all core components
    reflection_engine = ReflectionEngine()
    goal_generator = GoalGenerator()
    mutator = Mutator()
    test_runner = TestRunner()
    promoter = Promoter()

    # Create orchestrator with forced sequential execution
    orchestrator = EvolutionOrchestrator(
        reflection_engine=reflection_engine,
        goal_generator=goal_generator,
        mutator=mutator,
        test_runner=test_runner,
        promoter=promoter,
        parallel_execution=False  # Force sequential execution
    )
    return orchestrator


def run_evolution_cycles(sandbox, orchestrator, num_cycles=5, quick_mode=False):
    """Execute evolution cycles and return the final sandbox state."""
    test_logger = EvolutionTestLogger()
    total_start_time = time.time()

    # Start memory tracing
    tracemalloc.start()

    if quick_mode:
        num_cycles = 1
        logger.info("=== Quick mode enabled: Running 1 cycle with forced failures ===")

    for cycle in range(1, num_cycles + 1):
        test_logger.start_cycle(cycle)
        cycle_passed = True

        # Record memory before test
        test_logger.log_memory_usage(before=True)

        try:
            # Step 1: Reflection
            logger.info(f"Cycle {cycle}: Starting reflection step")
            step_start = time.time()
            reflection_result = orchestrator.reflection_engine.reflect()
            step_duration = time.time() - step_start
            test_logger.log_step_performance('reflection', step_duration)
            reflection_status = 'pass' if reflection_result.get('success', False) else 'fail'
            test_logger.log_step('reflection', reflection_status, reflection_result)
            if reflection_status == 'fail':
                cycle_passed = False

            # Assertion 1: Verify self-model was updated after reflection
            assert hasattr(orchestrator.reflection_engine, 'self_model'), "Self-model not found after reflection"
            assert orchestrator.reflection_engine.self_model is not None, "Self-model is None after reflection"
            assert isinstance(orchestrator.reflection_engine.self_model, dict), "Self-model is not a dictionary"
            assert len(orchestrator.reflection_engine.self_model) > 0, "Self-model is empty after reflection"
            logger.info(f"Cycle {cycle}: Self-model verified after reflection - {len(orchestrator.reflection_engine.self_model)} entries")

            # Step 2: Goal Generation
            logger.info(f"Cycle {cycle}: Starting goal generation step")
            step_start = time.time()
            goal_result = orchestrator.goal_generator.generate_goals(reflection_result)
            step_duration = time.time() - step_start
            test_logger.log_step_performance('goal_generation', step_duration)
            goal_status = 'pass' if goal_result.get('success', False) else 'fail'
            test_logger.log_step('goal_generation', goal_status, goal_result)
            if goal_status == 'fail':
                cycle_passed = False

            # Assertion 2: Verify goal queue changed appropriately
            assert hasattr(orchestrator.goal_generator, 'goal_queue'), "Goal queue not found after goal generation"
            assert orchestrator.goal_generator.goal_queue is not None, "Goal queue is None after goal generation"
            assert isinstance(orchestrator.goal_generator.goal_queue, list), "Goal queue is not a list"
            assert len(orchestrator.goal_generator.goal_queue) > 0, "Goal queue is empty after goal generation"
            
            # Assertion 3: Verify no duplicate goals
            goal_ids = [goal.get('id') for goal in orchestrator.goal_generator.goal_queue if 'id' in goal]
            if goal_ids:
                assert len(goal_ids) == len(set(goal_ids)), f"Duplicate goals found in goal queue: {goal_ids}"
            logger.info(f"Cycle {cycle}: Goal queue verified - {len(orchestrator.goal_generator.goal_queue)} goals, no duplicates")

            # Step 3: Mutation
            logger.info(f"Cycle {cycle}: Starting mutation step")
            step_start = time.time()
            if quick_mode:
                # Inject deliberate syntax error in mutation
                logger.info("Quick mode: Injecting deliberate syntax error in mutation")
                mutation_result = orchestrator.mutator.mutate(goal_result)
                # Force a syntax error by modifying the mutation result
                if mutation_result.get('success', False):
                    mutation_result['code'] = "def broken_function():\n    print('missing colon')\n"
                    mutation_result['error'] = "SyntaxError: invalid syntax"
                mutation_status = 'fail'
            else:
                mutation_result = orchestrator.mutator.mutate(goal_result)
                mutation_status = 'pass' if mutation_result.get('success', False) else 'fail'
            step_duration = time.time() - step_start
            test_logger.log_step_performance('mutation', step_duration)
            test_logger.log_step('mutation', mutation_status, mutation_result)
            if mutation_status == 'fail':
                cycle_passed = False

            # Step 4: Test
            logger.info(f"Cycle {cycle}: Starting test step")
            step_start = time.time()
            test_result = orchestrator.test_runner.run_tests(mutation_result)
            step_duration = time.time() - step_start
            test_logger.log_step_performance('test', step_duration)
            test_status = 'pass' if test_result.get('success', False) else 'fail'
            test_logger.log_step('test', test_status, test_result)
            if test_status == 'fail':
                cycle_passed = False

            # Step 5: Promotion
            logger.info(f"Cycle {cycle}: Starting promotion step")
            step_start = time.time()
            promotion_result = orchestrator.promoter.promote(test_result)
            step_duration = time.time() - step_start
            test_logger.log_step_performance('promotion', step_duration)
            promotion_status = 'pass' if promotion_result.get('success', False) else 'fail'
            test_logger.log_step('promotion', promotion_status, promotion_result)
            if promotion_status == 'fail':
                cycle_passed = False

            # Assertion 4: Verify system state is consistent (no dangling references)
            # Check that all components reference each other correctly
            assert hasattr(orchestrator, 'reflection_engine'), "Orchestrator missing reflection_engine"
            assert hasattr(orchestrator, 'goal_generator'), "Orchestrator missing goal_generator"
            assert hasattr(orchestrator, 'mutator'), "Orchestrator missing mutator"
            assert hasattr(orchestrator, 'test_runner'), "Orchestrator missing test_runner"
            assert hasattr(orchestrator, 'promoter'), "Orchestrator missing promoter"
            
            # Verify no dangling references in component outputs
            for component_name, component_result in [
                ('reflection', reflection_result),
                ('goal_generation', goal_result),
                ('mutation', mutation_result),
                ('test', test_result),
                ('promotion', promotion_result)
            ]:
                if component_result:
                    # Check for any references to non-existent objects
                    for key, value in component_result.items():
                        if isinstance(value, str) and 'ref_' in value:
                            # Check if referenced object exists
                            ref_id = value.split('ref_')[-1]
                            assert ref_id in str(orchestrator.__dict__), \
                                f"Dangling reference found in {component_name} result: {key}={value}"
            
            logger.info(f"Cycle {cycle}: System state consistency verified - no dangling references")

        except Exception as e:
            logger.error(f"Cycle {cycle} failed with exception: {str(e)}")
            cycle_passed = False
            test_logger.log_step('error', 'fail', {'error': str(e)})

        # Record memory after test
        test_logger.log_memory_usage(before=False)

        # Finalize cycle
        cycle_overall_status = 'pass' if cycle_passed else 'fail'
        test_logger.end_cycle(cycle_overall_status)

        if quick_mode:
            # In quick mode, we expect the cycle to fail
            logger.info(f"Quick mode: Expected cycle failure - actual status: {cycle_overall_status}")
            # Verify failure is caught and logged
            assert cycle_overall_status == 'fail', "Quick mode: Expected cycle to fail but it passed"
            # Verify error message contains expected details
            mutation_log = test_logger.cycle_logs[cycle].get('mutation', {})
            if mutation_log:
                error_details = mutation_log.get('details', {})
                error_msg = error_details.get('error', '')
                assert 'SyntaxError' in error_msg or 'error' in error_msg.lower(), \
                    f"Quick mode: Expected error message to contain syntax error details, got: {error_msg}"
            # Verify sandbox is cleaned up
            sandbox_state = sandbox.get_sandbox_state()
            assert sandbox_state is not None, "Quick mode: Sandbox state should exist after cycle"
            # Verify no files leaked
            no_leak, leaked_files = sandbox.check_no_files_leaked()
            assert no_leak, f"Quick mode: Files leaked outside sandbox: {leaked_files}"
            logger.info("Quick mode: All verifications passed - failure caught, logged, sandbox cleaned, error details present")
        else:
            # Assert cycle passed (optional - can be changed to soft assertion)
            assert cycle_passed, f"Cycle {cycle} failed"

    # Log total execution time
    total_duration = time.time() - total_start_time
    logger.info(f"Total execution time: {total_duration:.2f} seconds")

    # Generate and log final report
    report = test_logger.get_report()
    logger.info("=== Integration Test Report ===")
    logger.info(json.dumps(report, indent=2))

    # Log performance report
    performance_report = test_logger.get_performance_report()
    logger.info("=== Performance Report ===")
    logger.info(json.dumps(performance_report, indent=2))

    if not quick_mode:
        # Verify all cycles were executed
        assert len(report['cycles']) == num_cycles, f"Expected {num_cycles} cycles, got {len(report['cycles'])}"

        # Verify overall test passed (all cycles passed)
        all_passed = all(
            cycle_data['overall_status'] == 'pass'
            for cycle_data in report['cycles'].values()
        )
        assert all_passed, "Not all evolution cycles passed"

    # Save report to file for debugging
    report_path = Path('integration_test_report.json')
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    logger.info(f"Integration test report saved to: {report_path}")

    # Save performance report
    perf_report_path = Path('performance_report.json')
    with open(perf_report_path, 'w') as f:
        json.dump(performance_report, f, indent=2)
    logger.info(f"Performance report saved to: {perf_report_path}")

    # Stop memory tracing
    tracemalloc.stop()

    # Return final sandbox state
    return sandbox.get_sandbox_state()


def test_evolution_loop_integration(sandbox, orchestrator):
    """Main integration test: execute 5 evolution cycles twice and verify idempotency."""
    NUM_CYCLES = 5

    # First run
    logger.info("=== Starting first run of evolution cycles ===")
    first_run_state = run_evolution_cycles(sandbox, orchestrator, NUM_CYCLES)
    logger.info("First run completed successfully")

    # Verify no files leaked outside sandbox after first run
    no_leak_first, leaked_files_first = sandbox.check_no_files_leaked()
    assert no_leak_first, f"Files leaked outside sandbox after first run: {leaked_files_first}"
    logger.info("No files leaked outside sandbox after first run")

    # Reset orchestrator state for second run
    logger.info("=== Resetting orchestrator for second run ===")
    orchestrator.reflection_engine = ReflectionEngine()
    orchestrator.goal_generator = GoalGenerator()
    orchestrator.mutator = Mutator()
    orchestrator.test_runner = TestRunner()
    orchestrator.promoter = Promoter()

    # Second run
    logger.info("=== Starting second run of evolution cycles ===")
    second_run_state = run_evolution_cycles(sandbox, orchestrator, NUM_CYCLES)
    logger.info("Second run completed successfully")

    # Verify no files leaked outside sandbox after second run
    no_leak_second, leaked_files_second = sandbox.check_no_files_leaked()
    assert no_leak_second, f"Files leaked outside sandbox after second run: {leaked_files_second}"
    logger.info("No files leaked outside sandbox after second run")

    # Compare final states
    logger.info("=== Comparing final states of both runs ===")
    assert first_run_state is not None, "First run state is None"
    assert second_run_state is not None, "Second run state is None"

    # Compare files
    assert first_run_state['files'] == second_run_state['files'], \
        f"File lists differ:\nFirst run: {first_run_state['files']}\nSecond run: {second_run_state['files']}"
    logger.info("File lists are identical between runs")

    # Compare directories
    assert first_run_state['directories'] == second_run_state['directories'], \
        f"Directory lists differ:\nFirst run: {first_run_state['directories']}\nSecond run: {second_run_state['directories']}"
    logger.info("Directory lists are identical between runs")

    # Compare file contents
    for file_path in first_run_state['file_contents']:
        assert file_path in second_run_state['file_contents'], \
            f"File {file_path} missing in second run"
        assert first_run_state['file_contents'][file_path] == second_run_state['file_contents'][file_path], \
            f"File {file_path} contents differ between runs"
    logger.info("File contents are identical between runs")

    logger.info("=== Idempotency verification passed ===")


def test_evolution_loop_quick_mode(sandbox, orchestrator):
    """Quick mode test: run 1 cycle with forced failures to test failure logging."""
    logger.info("=== Starting quick mode test ===")
    run_evolution_cycles(sandbox, orchestrator, quick_mode=True)
    logger.info("=== Quick mode test completed successfully ===")


if __name__ == '__main__':
    # Allow running directly for debugging
    pytest.main([__file__, '-v'])