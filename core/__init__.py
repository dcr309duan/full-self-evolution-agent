from .capability_bankruptcy import (
    audit_and_prune,
    get_bankruptcy_stats,
    BankruptcyConfig,
    BankruptcyResult,
    CapabilityScore,
    PruningAction,
    __all__
)

from .nash_detector_and_forcer import (
    NashDetectorAndForcer,
    NashDetectorAndForcerConfig,
    DetectionResult,
    ForcingResult
)

def __getattr__(name):
    if name in ('NashEquilibriumDetector', 'detect_nash_equilibrium', 'NashDetectorConfig'):
        import importlib
        mod = importlib.import_module('.nash_detector', __package__)
        return getattr(mod, name)
    if name in ('MultiModuleForcer',):
        import importlib
        mod = importlib.import_module('.multi_module_forcer', __package__)
        return getattr(mod, name)
    if name in ('equilibrium_detector',):
        import importlib
        mod = importlib.import_module('.equilibrium_detector', __package__)
        return getattr(mod, name)
    if name in ('multi_module_forcer',):
        import importlib
        mod = importlib.import_module('.multi_module_forcer', __package__)
        return getattr(mod, name)
    if name in ('orchestrator_hook',):
        import importlib
        mod = importlib.import_module('.orchestrator_hook', __package__)
        return getattr(mod, name)
    if name in ('NashDetectorAndForcer', 'NashDetectorAndForcerConfig', 'DetectionResult', 'ForcingResult'):
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

from .coordinated_mutation_engine import CoordinatedMutationEngine, MutationConfig, MutationResult
from .coordinated_change_executor import CoordinatedChangeExecutor, ChangeExecutorConfig, ChangeResult
from .ecology_engine import EcologyEngine
from . import nash_detector
from . import multi_module_forcer

__all__ = [
    'audit_and_prune',
    'get_bankruptcy_stats',
    'BankruptcyConfig',
    'BankruptcyResult',
    'CapabilityScore',
    'PruningAction',
    'NashEquilibriumDetector',
    'detect_nash_equilibrium',
    'NashDetectorConfig',
    'MultiModuleForcer',
    'CoordinatedMutationEngine',
    'MutationConfig',
    'MutationResult',
    'CoordinatedChangeExecutor',
    'ChangeExecutorConfig',
    'ChangeResult',
    'EcologyEngine',
    'nash_detector',
    'multi_module_forcer',
    'equilibrium_detector',
    'orchestrator_hook',
    'NashDetectorAndForcer',
    'NashDetectorAndForcerConfig',
    'DetectionResult',
    'ForcingResult',
]