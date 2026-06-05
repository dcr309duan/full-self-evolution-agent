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

# Number of cycles to look back when determining if the system is in equilibrium.
# A larger window makes detection more stable but slower to respond.
EQUILIBRIUM_WINDOW_SIZE = 5

# Minimum number of modules that must be actively coordinating to trigger
# a coordinated mutation phase. Prevents premature coordination with too few modules.
MIN_MODULES_FOR_COORDINATION = 3

# Maximum number of modules that can participate in a coordinated mutation phase.
# Prevents coordination from becoming too broad and difficult to manage.
MAX_COORDINATED_MODULES = 5

# Flag to enable or disable Nash equilibrium detection specifically for the Nash detector module.
ENABLE_NASH_DETECTION = True

# Number of stable cycles required to confirm Nash equilibrium.
NASH_STABLE_CYCLES_THRESHOLD = 3

# Number of cycles between Nash equilibrium checks (overrides NASH_CHECK_INTERVAL for Nash detector).
NASH_CHECK_INTERVAL = 5