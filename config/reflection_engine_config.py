# Reflection Engine Configuration

# Default meta-cognition prompt with initial constraints
DEFAULT_META_COGNITION_PROMPT = """
You are an AI system reflecting on your own cognitive processes. Your task is to analyze your reasoning patterns, identify potential improvements, and generate self-modifications.

Initial constraints:
1. Maintain logical consistency across all reasoning steps
2. Avoid circular reasoning patterns
3. Ensure all conclusions are supported by evidence
4. Consider multiple perspectives before finalizing decisions
5. Document all assumptions explicitly
6. Verify that proposed changes do not introduce contradictions
7. Respect the hierarchical structure of the system
8. Do not modify core safety constraints
9. Ensure backward compatibility with existing functionality
10. Validate all modifications against test suite
"""

# Mutation interval (number of cycles between mutation attempts)
MUTATION_INTERVAL = 100

# Improvement threshold (minimum improvement percentage to accept a mutation)
IMPROVEMENT_THRESHOLD = 0.10  # 10%

# Test window size (number of cycles to evaluate a mutation)
TEST_WINDOW_SIZE = 10

# Maximum mutation attempts before forced reset
MAX_MUTATION_ATTEMPTS = 5

# List of allowed constraint types
ALLOWED_CONSTRAINT_TYPES = [
    "logical_consistency",
    "no_circular_reasoning",
    "evidence_based",
    "multiple_perspectives",
    "explicit_assumptions",
    "no_contradictions",
    "hierarchy_respect",
    "safety_constraints",
    "backward_compatibility",
    "test_validation",
    "performance_metrics",
    "resource_limits",
    "error_handling",
    "state_persistence",
    "dependency_management"
]