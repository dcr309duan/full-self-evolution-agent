"""Core package for the self-evolution agent.

All imports are lazy to prevent cascading failures from broken modules.
Use direct imports like 'from core.memory import get_evolution_state' instead.
"""

# Ensure av_research_engine is importable
from core import av_research_engine

# Export nash_detector_and_forcer for evolution_orchestrator
from core import nash_detector_and_forcer

# Export NashDetectorAndForcer and EvolutionOrchestrator for easy import by other modules
from core.nash_detector_and_forcer import NashDetectorAndForcer
from core.evolution_orchestrator import EvolutionOrchestrator