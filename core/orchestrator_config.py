"""Configuration parameters for the evolution orchestrator's coordinated mutation system."""

# Number of evolution cycles to wait before checking for equilibrium
# and potentially triggering a coordinated mutation phase.
COORDINATED_MUTATION_INTERVAL = 3

# Maximum number of files to modify in a single coordinated mutation phase.
# This prevents overly large, hard-to-validate changes.
MAX_COORDINATED_MUTATIONS = 5