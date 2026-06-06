"""Core package for the self-evolution agent.

All imports are lazy to prevent cascading failures from broken modules.
Use direct imports like 'from core.memory import get_evolution_state' instead.
"""

# Ensure av_research_engine is importable
from core import av_research_engine

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