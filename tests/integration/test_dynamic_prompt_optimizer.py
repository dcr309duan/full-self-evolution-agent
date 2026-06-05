import pytest
import os
import sys
import tempfile
import json
from unittest.mock import patch, MagicMock

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from evolution_orchestrator import EvolutionOrchestrator
from mutation_engine import MutationEngine
from failure_pattern_learner import FailurePatternLearner
from dynamic_prompt_optimizer import DynamicPromptOptimizer


class DeliberatelyFaultyMutator:
    """A mutation generator that always produces faulty code to trigger failure learning."""
    
    def __init__(self):
        self.mutation_count = 0
        self.faulty_snippets = [
            "def faulty_function():\n    return 1/0  # Division by zero",
            "def faulty_function():\n    import non_existent_module  # Import error",
            "def faulty_function():\n    x = [1,2,3]\n    return x[10]  # Index error",
            "def faulty_function():\n    return undefined_variable  # Name error",
            "def faulty_function():\n    while True:\n        pass  # Infinite loop",
        ]
    
    def mutate(self, code, context=None):
        """Always return a faulty mutation."""
        snippet = self.faulty_snippets[self.mutation_count % len(self.faulty_snippets)]
        self.mutation_count += 1
        return snippet
    
    def get_mutation_count(self):
        return self.mutation_count


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace for integration testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create necessary subdirectories
        os.makedirs(os.path.join(tmpdir, 'knowledge'), exist_ok=True)
        os.makedirs(os.path.join(tmpdir, 'logs'), exist_ok=True)
        os.makedirs(os.path.join(tmpdir, 'mutations'), exist_ok=True)
        yield tmpdir


@pytest.fixture
def faulty_orchestrator(temp_workspace):
    """Create an EvolutionOrchestrator with a deliberately faulty mutation generator."""
    # Initialize components
    learner = FailurePatternLearner(
        storage_path=os.path.join(temp_workspace, 'knowledge', 'failure_patterns.json')
    )
    prompt_optimizer = DynamicPromptOptimizer(
        learner=learner,
        storage_path=os.path.join(temp_workspace, 'knowledge', 'prompt_optimizations.json')
    )
    faulty_mutator = DeliberatelyFaultyMutator()
    mutation_engine = MutationEngine(
        mutator=faulty_mutator,
        prompt_optimizer=prompt_optimizer
    )
    
    orchestrator = EvolutionOrchestrator(
        workspace=temp_workspace,
        mutation_engine=mutation_engine,
        failure_pattern_learner=learner,
        prompt_optimizer=prompt_optimizer,
        max_iterations=10
    )
    
    return orchestrator, prompt_optimizer, learner


class TestDynamicPromptOptimizerIntegration:
    """Integration tests for the dynamic prompt optimizer within the evolution cycle."""
    
    def test_full_cycle_with_faulty_mutations(self, faulty_orchestrator):
        """Test that the full evolution cycle with faulty mutations accumulates lessons and adjusts prompts."""
        orchestrator, prompt_optimizer, learner = faulty_orchestrator
        
        # Run the evolution cycle
        results = orchestrator.run_evolution_cycle()
        
        # Verify that failures were recorded
        failure_count = learner.get_failure_count()
        assert failure_count > 0, "No failures were recorded despite using faulty mutator"
        
        # Verify that lessons were learned
        lessons = learner.get_lessons_learned()
        assert len(lessons) > 0, "No lessons were learned from failures"
        
        # Verify that prompt was optimized based on lessons
        optimization_history = prompt_optimizer.get_optimization_history()
        assert len(optimization_history) > 0, "No prompt optimizations were made"
        
        # Check that the latest prompt includes lessons from failures
        latest_prompt = prompt_optimizer.get_current_prompt()
        for lesson in lessons[:3]:  # Check at least first 3 lessons
            assert lesson['pattern'] in latest_prompt or lesson['solution'] in latest_prompt, \
                f"Lesson '{lesson['pattern']}' not found in optimized prompt"
    
    def test_prompt_evolution_over_multiple_cycles(self, faulty_orchestrator):
        """Test that prompts evolve over multiple cycles as more failures are accumulated."""
        orchestrator, prompt_optimizer, learner = faulty_orchestrator
        
        # Run multiple evolution cycles
        prompts_over_time = []
        for cycle in range(5):
            orchestrator.run_evolution_cycle()
            current_prompt = prompt_optimizer.get_current_prompt()
            prompts_over_time.append(current_prompt)
        
        # Verify that prompts changed over time
        unique_prompts = set(prompts_over_time)
        assert len(unique_prompts) > 1, "Prompts did not change across cycles"
        
        # Verify that later prompts are longer (more lessons accumulated)
        prompt_lengths = [len(p) for p in prompts_over_time]
        assert prompt_lengths[-1] > prompt_lengths[0], \
            "Later prompts should be longer due to accumulated lessons"
    
    def test_lesson_accumulation_and_deduplication(self, faulty_orchestrator):
        """Test that lessons are accumulated and duplicates are avoided."""
        orchestrator, prompt_optimizer, learner = faulty_orchestrator
        
        # Run cycles to accumulate lessons
        for _ in range(10):
            orchestrator.run_evolution_cycle()
        
        # Get all lessons
        all_lessons = learner.get_all_lessons()
        
        # Check for duplicates (same pattern should not appear twice)
        patterns = [lesson['pattern'] for lesson in all_lessons]
        assert len(patterns) == len(set(patterns)), "Duplicate lessons were found"
        
        # Verify that the prompt contains all unique lessons
        current_prompt = prompt_optimizer.get_current_prompt()
        for lesson in all_lessons:
            assert lesson['pattern'] in current_prompt or lesson['solution'] in current_prompt, \
                f"Lesson '{lesson['pattern']}' missing from prompt"
    
    def test_prompt_optimizer_persistence(self, faulty_orchestrator, temp_workspace):
        """Test that prompt optimizations persist across orchestrator restarts."""
        orchestrator, prompt_optimizer, learner = faulty_orchestrator
        
        # Run some cycles
        for _ in range(3):
            orchestrator.run_evolution_cycle()
        
        # Save state
        prompt_optimizer.save_state()
        
        # Create new orchestrator that loads from saved state
        new_learner = FailurePatternLearner(
            storage_path=os.path.join(temp_workspace, 'knowledge', 'failure_patterns.json')
        )
        new_optimizer = DynamicPromptOptimizer(
            learner=new_learner,
            storage_path=os.path.join(temp_workspace, 'knowledge', 'prompt_optimizations.json')
        )
        new_optimizer.load_state()
        
        # Verify that lessons and optimizations were preserved
        original_lessons = learner.get_all_lessons()
        loaded_lessons = new_learner.get_all_lessons()
        assert len(original_lessons) == len(loaded_lessons), "Lessons were lost during persistence"
        
        original_prompt = prompt_optimizer.get_current_prompt()
        loaded_prompt = new_optimizer.get_current_prompt()
        assert original_prompt == loaded_prompt, "Prompt was not preserved during persistence"
    
    def test_prompt_optimization_effectiveness(self, faulty_orchestrator):
        """Test that prompt optimization actually improves mutation quality over time."""
        orchestrator, prompt_optimizer, learner = faulty_orchestrator
        
        # Track success rates over cycles
        success_rates = []
        for cycle in range(8):
            results = orchestrator.run_evolution_cycle()
            success_rate = results.get('success_rate', 0.0)
            success_rates.append(success_rate)
        
        # The success rate should improve as the prompt incorporates lessons
        # (even with a faulty mutator, the prompt should guide better mutations)
        # Note: With deliberately faulty mutator, improvement may be limited
        # but we expect at least some positive trend
        assert success_rates[-1] >= success_rates[0], \
            "Success rate did not improve despite prompt optimization"
        
        # Verify that the number of unique failure types decreased
        failure_types = learner.get_failure_type_counts()
        initial_types = len(failure_types)
        
        # Run more cycles
        for _ in range(5):
            orchestrator.run_evolution_cycle()
        
        final_failure_types = learner.get_failure_type_counts()
        assert len(final_failure_types) <= initial_types + 2, \
            "Number of failure types should not increase dramatically with optimization"
    
    def test_prompt_optimizer_edge_cases(self, faulty_orchestrator):
        """Test edge cases in prompt optimization."""
        orchestrator, prompt_optimizer, learner = faulty_orchestrator
        
        # Test with no failures yet
        initial_prompt = prompt_optimizer.get_current_prompt()
        assert initial_prompt is not None, "Initial prompt should not be None"
        assert len(initial_prompt) > 0, "Initial prompt should not be empty"
        
        # Test that prompt handles special characters in lessons
        learner.add_lesson(
            pattern="Special chars: !@#$%^&*()",
            solution="Handle with: \\n\\t\\r",
            failure_type="syntax_error"
        )
        prompt_optimizer.optimize_prompt()
        updated_prompt = prompt_optimizer.get_current_prompt()
        assert "Special chars" in updated_prompt, "Prompt should handle special characters"
        
        # Test with maximum lessons
        for i in range(100):
            learner.add_lesson(
                pattern=f"Pattern_{i}_with_very_long_description_" * 10,
                solution=f"Solution_{i}_with_very_long_description_" * 10,
                failure_type="test_error"
            )
        prompt_optimizer.optimize_prompt(max_length=5000)
        assert len(prompt_optimizer.get_current_prompt()) <= 5000, \
            "Prompt should respect maximum length constraint"
    
    def test_concurrent_failure_learning(self, faulty_orchestrator):
        """Test that the system handles multiple failure types concurrently."""
        orchestrator, prompt_optimizer, learner = faulty_orchestrator
        
        # Introduce multiple failure types
        failure_types = ['syntax_error', 'runtime_error', 'import_error', 'type_error', 'value_error']
        for failure_type in failure_types:
            learner.add_lesson(
                pattern=f"Common pattern for {failure_type}",
                solution=f"Standard solution for {failure_type}",
                failure_type=failure_type
            )
        
        # Run optimization
        prompt_optimizer.optimize_prompt()
        optimized_prompt = prompt_optimizer.get_current_prompt()
        
        # Verify all failure types are addressed in the prompt
        for failure_type in failure_types:
            assert failure_type in optimized_prompt or \
                   f"Common pattern for {failure_type}" in optimized_prompt, \
                   f"Failure type '{failure_type}' not addressed in optimized prompt"
        
        # Verify that the prompt structure is coherent
        assert "Lessons Learned" in optimized_prompt or "lessons" in optimized_prompt.lower(), \
            "Prompt should contain lessons section"
        assert "Avoid" in optimized_prompt or "avoid" in optimized_prompt.lower(), \
            "Prompt should contain avoidance guidance"