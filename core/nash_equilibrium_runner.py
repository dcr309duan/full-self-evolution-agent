#!/usr/bin/env python3
"""
core/nash_equilibrium_runner.py

Standalone runner script that demonstrates Nash equilibrium detection and multi-module forcing.
Imports NashDetector and MultiModuleForcer from nash_detector_and_forcer.py, runs a simulation
with 10 mock modules and 100 simulated mutation attempts, prints detection results and proposed
multi-module changes, and exits with code 0 on success.
"""

import sys
import random
from typing import List, Dict, Any

# Import from sibling module
from nash_detector_and_forcer import NashDetector, MultiModuleForcer


def create_mock_modules(num_modules: int = 10) -> List[Dict[str, Any]]:
    """Create mock modules with random interaction patterns."""
    modules = []
    for i in range(num_modules):
        # Each module has a random payoff matrix (2x2 for simplicity)
        # Rows: module's action (0=cooperate, 1=defect)
        # Cols: opponent's action (0=cooperate, 1=defect)
        payoff_matrix = [
            [random.uniform(0, 10), random.uniform(0, 10)],
            [random.uniform(0, 10), random.uniform(0, 10)]
        ]
        modules.append({
            'id': i,
            'name': f'module_{i}',
            'payoff_matrix': payoff_matrix,
            'current_strategy': random.choice(['cooperate', 'defect']),
            'mutation_rate': random.uniform(0.01, 0.1)
        })
    return modules


def simulate_mutations(modules: List[Dict[str, Any]], num_attempts: int = 100) -> List[Dict[str, Any]]:
    """Simulate mutation attempts on the modules."""
    mutated_modules = []
    for _ in range(num_attempts):
        # Pick a random module
        module = random.choice(modules)
        # Create a mutated copy
        mutated = module.copy()
        # Randomly mutate the payoff matrix
        for i in range(2):
            for j in range(2):
                if random.random() < module['mutation_rate']:
                    mutated['payoff_matrix'][i][j] += random.uniform(-2, 2)
                    # Clamp to [0, 10]
                    mutated['payoff_matrix'][i][j] = max(0, min(10, mutated['payoff_matrix'][i][j]))
        # Randomly flip strategy with some probability
        if random.random() < module['mutation_rate']:
            mutated['current_strategy'] = 'defect' if module['current_strategy'] == 'cooperate' else 'cooperate'
        mutated['id'] = module['id']
        mutated['name'] = module['name']
        mutated_modules.append(mutated)
    return mutated_modules


def main() -> int:
    """Main runner function. Returns exit code."""
    print("=" * 60)
    print("Nash Equilibrium Detection and Multi-Module Forcing Demo")
    print("=" * 60)

    # Step 1: Create mock modules
    print("\n[1] Creating 10 mock modules with random interaction patterns...")
    modules = create_mock_modules(10)
    for m in modules:
        print(f"    Module {m['id']}: strategy={m['current_strategy']}, mutation_rate={m['mutation_rate']:.3f}")

    # Step 2: Initialize detectors and forcers
    print("\n[2] Initializing NashDetector and MultiModuleForcer...")
    detector = NashDetector()
    forcer = MultiModuleForcer()

    # Step 3: Simulate mutations
    print("\n[3] Simulating 100 mutation attempts...")
    mutated_modules = simulate_mutations(modules, 100)
    print(f"    Generated {len(mutated_modules)} mutated module configurations")

    # Step 4: Run detection on each mutated configuration
    print("\n[4] Running Nash equilibrium detection...")
    equilibrium_detected = False
    for idx, mutated in enumerate(mutated_modules):
        # Prepare the interaction data for detection
        # We need to create a payoff matrix from the module's data
        payoff_matrix = mutated['payoff_matrix']
        
        # Detect Nash equilibrium
        is_equilibrium = detector.detect(payoff_matrix)
        
        if is_equilibrium:
            equilibrium_detected = True
            print(f"\n    >>> EQUILIBRIUM DETECTED at mutation attempt {idx + 1}")
            print(f"        Module: {mutated['name']}")
            print(f"        Payoff matrix: {payoff_matrix}")
            print(f"        Current strategy: {mutated['current_strategy']}")
            
            # Propose multi-module changes
            print(f"    >>> Proposing multi-module changes...")
            changes = forcer.propose_changes(mutated, modules)
            if changes:
                print(f"        Proposed changes:")
                for change in changes:
                    print(f"            - {change}")
            else:
                print(f"        No changes proposed (already optimal)")

    if not equilibrium_detected:
        print("\n    No Nash equilibrium detected in this simulation run.")

    # Step 5: Summary
    print("\n" + "=" * 60)
    print("Simulation Complete")
    print("=" * 60)
    print(f"Total modules: {len(modules)}")
    print(f"Total mutation attempts: {len(mutated_modules)}")
    print(f"Equilibrium detected: {equilibrium_detected}")
    print("Exit code: 0 (Success)")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())