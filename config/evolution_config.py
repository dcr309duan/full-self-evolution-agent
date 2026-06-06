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

# Schema alignment configuration
ENABLE_SCHEMA_VALIDATION = True
SCHEMA_VERSION_STRICT_MODE = True
SCHEMA_AUTO_UPDATE = False
SCHEMA_VALIDATION_LOG_LEVEL = 'WARNING'

# Pre-generation test suite configuration
PRE_GENERATION_TEST_SUITE_ENABLED = True
PRE_GENERATION_TEST_TIMEOUT = 30
PRE_GENERATION_TEST_ABORT_ON_FAILURE = True

# Failure-aware selector configuration
FAILURE_AWARE_SELECTOR_ENABLED = False
FAILURE_AWARE_THRESHOLD = 0.3
FAILURE_AWARE_TRAINING_SIZE = 50
FAILURE_AWARE_CLASSIFIER_TYPE = 'logistic_regression'

# Ban configuration for consecutive failures
BAN_CONSECUTIVE_FAILURES = 3
BAN_DURATION_CYCLES = 5
REDUCED_PROBABILITY = 0.5
MAX_TRACKED_FAILURES = 20