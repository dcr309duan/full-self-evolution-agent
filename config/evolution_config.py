"""Configuration parameters for the self-consistency test suite."""

# Enable or disable self-consistency checks
ENABLE_SELF_CONSISTENCY_CHECKS = True

# Maximum number of consistency failures before pausing the evolution
MAX_CONSISTENCY_FAILURES_BEFORE_PAUSE = 3

# Interval for running consistency checks (e.g., every cycle)
CONSISTENCY_CHECK_INTERVAL = "every cycle"

# Feasibility threshold for goal selection (0.0 to 1.0)
FEASIBILITY_THRESHOLD = 0.5

# Enable or disable dependency blocking for goals
ENABLE_DEPENDENCY_BLOCKING = True

# Maximum number of blocked goals before pausing the evolution
MAX_BLOCKED_GOALS_BEFORE_PAUSE = 5

# Priority weight for end-to-end pipeline completion (higher = more priority)
PRIORITY_WEIGHT_FOR_PIPELINE = 2.0