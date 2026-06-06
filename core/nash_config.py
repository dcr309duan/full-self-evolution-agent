"""Configuration module for Nash equilibrium detection and coordination.

This module provides default parameters for the Nash detection system,
making it configurable and avoiding hardcoded values throughout the codebase.
"""

# Number of recent evolution cycles to analyze for Nash equilibrium detection
# A larger window provides more statistical significance but may delay detection
nash_detection_window = 10

# Minimum relative improvement threshold (as a fraction) to consider a module's
# performance as having changed meaningfully. Values below this are treated as
# equilibrium (no significant improvement).
min_improvement_threshold = 0.05

# Maximum number of modules that can be coordinated simultaneously in a Nash
# equilibrium state. Limits complexity and prevents over-coordination.
max_coordinated_modules = 3

# Whether to automatically rollback changes when a Nash equilibrium is detected
# and the coordinated changes lead to regression or instability.
rollback_on_failure = True

# Threshold for considering a state as equilibrium (0.0 to 1.0)
# Higher values require stronger convergence before declaring equilibrium
equilibrium_threshold = 0.85

# Minimum number of cycles that must pass before declaring equilibrium
# Prevents premature equilibrium detection during transient states
min_cycles_for_equilibrium = 5

# Maximum number of attempts for multi-module coordination
# Limits retries to prevent infinite loops in coordination attempts
max_multi_module_attempts = 3

# Nash equilibrium parameters
# Number of consecutive attempts to check for equilibrium
EQUILIBRIUM_WINDOW = 5

# Minimum improvement threshold (1%) to consider a module's performance as changed
IMPROVEMENT_THRESHOLD = 0.01

# Coordinated improvement threshold (2%) for multi-module coordination
COORDINATED_IMPROVEMENT_THRESHOLD = 0.02

# Maximum number of modules in a coordinated bundle
MAX_BUNDLE_SIZE = 3

# Number of historical cycles to track for analysis
HISTORY_LENGTH = 20