"""Configuration parameters for the evolution orchestrator's coordinated mutation system."""

# Number of evolution cycles to wait before checking for equilibrium
# and potentially triggering a coordinated mutation phase.
COORDINATED_MUTATION_INTERVAL = 3

# Maximum number of files to modify in a single coordinated mutation phase.
# This prevents overly large, hard-to-validate changes.
MAX_COORDINATED_MUTATIONS = 5

# Threshold for detecting Nash equilibrium (minimum improvement percentage).
# If the improvement in the last nash_check_interval cycles is below this threshold,
# the system considers it an equilibrium state.
EQUILIBRIUM_THRESHOLD = 0.01

# Number of cycles between Nash equilibrium checks.
NASH_CHECK_INTERVAL = 10

# Maximum number of coordinated changes allowed before forcing a reset.
# Prevents infinite loops of minor adjustments.
MAX_COORDINATED_CHANGES = 3

# Flag to enable or disable Nash equilibrium detection.
ENABLE_NASH_DETECTION = True