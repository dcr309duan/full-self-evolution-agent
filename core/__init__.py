"""Core package for the self-evolution agent.

All imports are lazy to prevent cascading failures from broken modules.
Use direct imports like 'from core.memory import get_evolution_state' instead.
"""

# Ensure av_research_engine is importable
from core import av_research_engine