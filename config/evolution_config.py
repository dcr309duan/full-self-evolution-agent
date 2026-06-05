"""Configuration parameters for the self-consistency test suite."""

# Enable or disable self-consistency checks
ENABLE_SELF_CONSISTENCY_CHECKS = True

# Maximum number of consistency failures before pausing the evolution
MAX_CONSISTENCY_FAILURES_BEFORE_PAUSE = 3

# Interval for running consistency checks (e.g., every cycle)
CONSISTENCY_CHECK_INTERVAL = "every cycle"