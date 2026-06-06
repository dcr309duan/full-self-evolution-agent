# Meta-cognition timeout configuration
# Controls the mechanism that triggers radical mutations when the system
# fails to produce meaningful changes over a number of cycles.

# Number of consecutive cycles with no mutation before the timeout triggers
# a radical mutation attempt.
TIMEOUT_THRESHOLD = 3

# Pool of radical mutation strategies to choose from when timeout is triggered.
# Each entry is a string identifier or module path for the mutation idea.
RADICAL_MUTATION_POOL = [
    "random_parameter_perturbation",
    "structural_reorganization",
    "goal_reprioritization",
    "subsystem_replacement",
    "cross_domain_analogy",
    "random_code_injection",
    "dependency_graph_rewiring",
    "heuristic_flip",
]

# Master enable/disable flag for the meta-cognition timeout mechanism.
# Set to False to disable automatic radical mutations on timeout.
ENABLED = True

# File path for logging radical mutation events triggered by timeout.
# This log records when a timeout occurred, which mutation was applied,
# and the outcome.
LOG_PATH = "logs/radical_mutation.log"