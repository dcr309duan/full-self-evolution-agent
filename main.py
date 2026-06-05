#!/usr/bin/env python3
"""Entry point for the Self-Evolution Agent."""
import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.evolution_orchestrator import EvolutionOrchestrator


def main():
    parser = argparse.ArgumentParser(description="Self-Evolution Agent")
    parser.add_argument("max_cycles", nargs="?", type=int, default=10, help="Maximum number of evolution cycles")
    parser.add_argument("--api", action="store_true", help="Start the API server instead of the evolution loop")
    args = parser.parse_args()

    orchestrator = EvolutionOrchestrator(max_cycles=args.max_cycles)

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
        orchestrator.start_api()
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
        orchestrator.start()


if __name__ == "__main__":
    main()