"""Core package for the self-evolution agent.

All imports are lazy to prevent cascading failures from broken modules.
Use direct imports like 'from core.memory import get_evolution_state' instead.
"""

# Ensure av_research_engine is importable
from core import av_research_engine

# Ensure ecology_engine is importable
from core.ecology_engine import TestSuiteEvolver, EnvironmentalPressureGenerator, FitnessLandscapeModifier

# Export nash_detector_and_forcer for evolution_orchestrator
try:
    from core import nash_detector_and_forcer
except ImportError:
    nash_detector_and_forcer = None

# Export evolution_orchestrator as a core module
try:
    from core import evolution_orchestrator
except ImportError:
    evolution_orchestrator = None

# Export NashDetectorAndForcer and EvolutionOrchestrator for easy import by other modules
try:
    from core.nash_detector_and_forcer import NashDetectorAndForcer
except ImportError:
    NashDetectorAndForcer = None

try:
    from core.evolution_orchestrator import EvolutionOrchestrator
except ImportError:
    EvolutionOrchestrator = None

# Ensure proper initialization order: nash_detector_and_forcer before evolution_orchestrator
if nash_detector_and_forcer is not None and evolution_orchestrator is not None:
    # Force initialization of NashDetectorAndForcer before EvolutionOrchestrator
    try:
        from core.nash_detector_and_forcer import NashDetectorAndForcer
        if NashDetectorAndForcer is not None:
            # Trigger any necessary initialization
            pass
    except ImportError:
        pass

# Export new Nash equilibrium detection and forcing capabilities
try:
    from core.nash_detector_and_forcer import (
        NashDetectorAndForcer,
        detect_nash_equilibrium,
        force_nash_equilibrium,
        get_nash_equilibrium_state,
        reset_nash_equilibrium_state
    )
except ImportError:
    detect_nash_equilibrium = None
    force_nash_equilibrium = None
    get_nash_equilibrium_state = None
    reset_nash_equilibrium_state = None

# Export EvolutionOrchestrator with Nash integration
try:
    from core.evolution_orchestrator import EvolutionOrchestrator
except ImportError:
    EvolutionOrchestrator = None

# Export PreMutationValidator class and its key methods
try:
    from core.pre_mutation_validator import PreMutationValidator
except ImportError:
    PreMutationValidator = None

try:
    from core.pre_mutation_validator import (
        PreMutationValidator,
        validate_mutation,
        get_validation_rules,
        set_validation_rules,
        reset_validation_state
    )
except ImportError:
    validate_mutation = None
    get_validation_rules = None
    set_validation_rules = None
    reset_validation_state = None

# Ensure all core module exports are available
__all__ = [
    'av_research_engine',
    'TestSuiteEvolver',
    'EnvironmentalPressureGenerator',
    'FitnessLandscapeModifier',
    'nash_detector_and_forcer',
    'evolution_orchestrator',
    'NashDetectorAndForcer',
    'EvolutionOrchestrator',
    'detect_nash_equilibrium',
    'force_nash_equilibrium',
    'get_nash_equilibrium_state',
    'reset_nash_equilibrium_state',
    'PreMutationValidator',
    'validate_mutation',
    'get_validation_rules',
    'set_validation_rules',
    'reset_validation_state'
]