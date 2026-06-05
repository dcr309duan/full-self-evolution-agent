#!/usr/bin/env python3
"""Entry point for the Self-Evolution Agent."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.evolution_loop import run_evolution


def main():
    max_cycles = int(sys.argv[1]) if len(sys.argv) > 1 else 10
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
    run_evolution(max_cycles)


if __name__ == "__main__":
    main()
