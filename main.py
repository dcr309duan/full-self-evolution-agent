#!/usr/bin/env python3
"""Entry point for the Self-Evolution Agent."""
import sys
import os
import argparse
import logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.evolution_loop import run_evolution
from core.self_model_builder import SelfModelBuilder
from core.goal_decomposition_orchestrator import GoalDecompositionOrchestrator

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Self-Evolution Agent")
    parser.add_argument("max_cycles", nargs="?", type=int, default=10, help="Maximum number of evolution cycles")
    parser.add_argument("--api", action="store_true", help="Start the API server instead of the evolution loop")
    args = parser.parse_args()

    # Initialize and update self-model at startup
    try:
        model_builder = SelfModelBuilder()
        model_data = model_builder.build_model()
        node_count = len(model_data.get('nodes', []))
        edge_count = len(model_data.get('edges', []))
        logger.info(f"Self-model initialized with {node_count} nodes and {edge_count} edges")
    except Exception as e:
        logger.error(f"Failed to initialize self-model: {e}")

    # Initialize GoalDecompositionOrchestrator
    try:
        goal_orchestrator = GoalDecompositionOrchestrator()
        logger.info("GoalDecompositionOrchestrator initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize GoalDecompositionOrchestrator: {e}")
        goal_orchestrator = None

    if args.api:
        print("""
╔══════════════════════════════════════════════════════════╗
║          SELF-EVOLUTION AGENT API SERVER                 ║
║          Autonomous Self-Improving System                ║
╠══════════════════════════════════════════════════════════╣
║  API Mode:                                              ║
║  - Evolution engine exposed as callable service         ║
║  - External triggers and data retrieval supported       ║
╚══════════════════════════════════════════════════════════╝
""")
        from api_server import app
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=8081)
    else:
        print("""
╔══════════════════════════════════════════════════════════╗
║          FULL SELF-EVOLUTION AGENT v0.1                  ║
║          Autonomous Self-Improving System                ║
╠══════════════════════════════════════════════════════════╣
║  Capabilities:                                           ║
║  - Deep self-reflection via DeepSeek Reasoner            ║
║  - Code self-modification with safety checks             ║
║  - Memory & knowledge accumulation                       ║
║  - Goal generation & pursuit                             ║
║  - Git-based version control of evolution                ║
╚══════════════════════════════════════════════════════════╝
""")
        run_evolution(args.max_cycles, goal_orchestrator=goal_orchestrator)


if __name__ == "__main__":
    main()