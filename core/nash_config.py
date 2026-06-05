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