"""failure_miner package initialization.

Exports the FailurePatternMiner class and registers it with the orchestrator.
"""

from .miner import FailurePatternMiner

# Register with the orchestrator
try:
    from core.orchestrator import Orchestrator
    Orchestrator.register_plugin("failure_miner", FailurePatternMiner)
except ImportError:
    # Orchestrator not available; registration skipped
    pass

__all__ = ["FailurePatternMiner"]