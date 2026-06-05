import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from failure_pattern_learner import record_failure, get_lessons_learned
from mutation_engine import generate_mutation_prompt


def test_prompt_contains_lessons_learned():
    # Arrange: seed 3 fake failures
    record_failure("module_a", "SyntaxError: invalid syntax")
    record_failure("module_b", "ImportError: No module named 'nonexistent'")
    record_failure("module_c", "AssertionError: expected 5 but got 3")

    # Act: generate a mutation prompt for a target module
    prompt = generate_mutation_prompt("module_a")

    # Assert: the prompt contains the LESSONS LEARNED section with relevant failure message
    assert "LESSONS LEARNED" in prompt
    assert "SyntaxError: invalid syntax" in prompt