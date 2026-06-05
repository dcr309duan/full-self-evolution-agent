"""
Configuration file for Nash detection thresholds.

This module defines default parameters for Nash equilibrium detection
and coordinated mutation within the evolutionary framework.
All values are importable without side effects.
"""

# Threshold for considering a strategy profile as an equilibrium.
# Lower values require stronger convergence (closer to 0.0).
EQUILIBRIUM_SCORE_THRESHOLD = 0.01

# Minimum number of agents that must be involved in a coordinated mutation.
COORDINATED_MUTATION_SIZE = 3

# Maximum number of iterations to run when detecting Nash equilibria.
NASH_DETECTION_MAX_ITERATIONS = 1000

# Learning rate for iterative best-response dynamics (if used).
NASH_LEARNING_RATE = 0.1

# Tolerance for convergence in iterative methods.
NASH_CONVERGENCE_TOLERANCE = 1e-6

# Whether to enable verbose logging during detection.
NASH_VERBOSE = False

# Default payoff matrix size (number of strategies per player).
DEFAULT_PAYOFF_SIZE = 2

# Number of top strategies to consider when forming coordinated mutations.
TOP_STRATEGIES_COUNT = 5

# Minimum improvement ratio to trigger a coordinated mutation.
COORDINATED_MUTATION_IMPROVEMENT_RATIO = 0.05

# Maximum number of coordinated mutation attempts per cycle.
MAX_COORDINATED_MUTATIONS_PER_CYCLE = 3