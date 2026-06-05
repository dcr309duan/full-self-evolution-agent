from .capability_bankruptcy import (
    audit_and_prune,
    get_bankruptcy_stats,
    BankruptcyConfig,
    BankruptcyResult,
    CapabilityScore,
    PruningAction,
    __all__
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
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

from .coordinated_mutation_engine import CoordinatedMutationEngine, MutationConfig, MutationResult
from .coordinated_change_executor import CoordinatedChangeExecutor, ChangeExecutorConfig, ChangeResult
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
    'nash_detector',
    'multi_module_forcer',
    'equilibrium_detector',
    'orchestrator_hook',
]