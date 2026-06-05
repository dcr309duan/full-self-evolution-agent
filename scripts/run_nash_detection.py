#!/usr/bin/env python3
"""
run_nash_detection.py

Standalone runner script for Nash Equilibrium Detection.
Loads module interaction data from a JSON file, runs detection and multi-module forcing,
and outputs results to console and a log file.
"""

import json
import sys
import os
from datetime import datetime
from pathlib import Path

# Add parent directory to path so we can import core modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from core.nash_detector import NashEquilibriumDetector
except ImportError as e:
    print(f"ERROR: Could not import NashEquilibriumDetector: {e}")
    print("Make sure core/nash_detector.py exists and is properly implemented.")
    sys.exit(1)


def load_interaction_data(json_path):
    """
    Load module interaction data from a JSON file.
    
    Expected JSON format:
    {
        "modules": [
            {
                "name": "module_name",
                "dependencies": ["dep1", "dep2"],
                "interactions": [
                    {"target": "other_module", "type": "call|import|data", "weight": 0.5}
                ]
            }
        ],
        "metadata": {
            "description": "...",
            "timestamp": "..."
        }
    }
    """
    if not os.path.exists(json_path):
        print(f"ERROR: JSON file not found: {json_path}")
        sys.exit(1)
    
    try:
        with open(json_path, 'r') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in {json_path}: {e}")
        sys.exit(1)
    
    # Validate basic structure
    if 'modules' not in data:
        print("ERROR: JSON must contain a 'modules' key with a list of module objects.")
        sys.exit(1)
    
    if not isinstance(data['modules'], list):
        print("ERROR: 'modules' must be a list.")
        sys.exit(1)
    
    return data


def run_detection(detector, interaction_data, log_file=None):
    """
    Run Nash equilibrium detection on the provided interaction data.
    
    Args:
        detector: NashEquilibriumDetector instance
        interaction_data: dict with 'modules' list
        log_file: optional file path for logging
    
    Returns:
        dict with detection results
    """
    modules = interaction_data.get('modules', [])
    metadata = interaction_data.get('metadata', {})
    
    print(f"\n{'='*60}")
    print(f"NASH EQUILIBRIUM DETECTION RUN")
    print(f"{'='*60}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"Modules loaded: {len(modules)}")
    if metadata.get('description'):
        print(f"Description: {metadata['description']}")
    print(f"{'='*60}\n")
    
    # Log to file if specified
    if log_file:
        with open(log_file, 'a') as f:
            f.write(f"\n{'='*60}\n")
            f.write(f"RUN at {datetime.now().isoformat()}\n")
            f.write(f"{'='*60}\n")
            f.write(f"Modules: {len(modules)}\n")
    
    # Register modules with the detector
    for mod in modules:
        name = mod.get('name', 'unknown')
        dependencies = mod.get('dependencies', [])
        interactions = mod.get('interactions', [])
        
        print(f"  Registering module: {name}")
        print(f"    Dependencies: {dependencies}")
        
        # Add module to detector
        detector.add_module(name, dependencies)
        
        # Register interactions
        for interaction in interactions:
            target = interaction.get('target')
            i_type = interaction.get('type', 'call')
            weight = interaction.get('weight', 1.0)
            detector.register_interaction(name, target, i_type, weight)
            print(f"    Interaction: {name} -> {target} ({i_type}, weight={weight})")
        
        if log_file:
            with open(log_file, 'a') as f:
                f.write(f"Module: {name}, Dependencies: {dependencies}\n")
                for interaction in interactions:
                    f.write(f"  Interaction: {name} -> {interaction.get('target')} "
                            f"({interaction.get('type')}, weight={interaction.get('weight')})\n")
    
    print(f"\n{'='*60}")
    print("DETECTION RESULTS")
    print(f"{'='*60}\n")
    
    # Run detection
    try:
        equilibria = detector.detect_equilibria()
    except AttributeError as e:
        print(f"WARNING: detect_equilibria() not available: {e}")
        print("Attempting alternative detection method...")
        try:
            equilibria = detector.find_nash_equilibria()
        except AttributeError:
            print("ERROR: No equilibrium detection method found on detector.")
            equilibria = []
    
    print(f"Equilibria found: {len(equilibria)}")
    if log_file:
        with open(log_file, 'a') as f:
            f.write(f"Equilibria found: {len(equilibria)}\n")
    
    # Process each equilibrium
    results = {
        'timestamp': datetime.now().isoformat(),
        'modules_analyzed': len(modules),
        'equilibria': [],
        'forcing_attempts': []
    }
    
    for i, eq in enumerate(equilibria):
        print(f"\n  Equilibrium {i+1}:")
        print(f"    {eq}")
        
        eq_entry = {
            'index': i,
            'description': str(eq)
        }
        
        # Attempt multi-module forcing
        try:
            print(f"  Attempting multi-module forcing for equilibrium {i+1}...")
            forcing_result = detector.force_multi_module(eq)
            print(f"    Forcing result: {forcing_result}")
            
            forcing_entry = {
                'equilibrium_index': i,
                'result': str(forcing_result)
            }
            results['forcing_attempts'].append(forcing_entry)
            
            if log_file:
                with open(log_file, 'a') as f:
                    f.write(f"Equilibrium {i+1}: {eq}\n")
                    f.write(f"  Forcing result: {forcing_result}\n")
                    
        except AttributeError as e:
            print(f"    WARNING: force_multi_module() not available: {e}")
            print("    Skipping forcing step.")
        except Exception as e:
            print(f"    ERROR during forcing: {e}")
        
        results['equilibria'].append(eq_entry)
        
        if log_file:
            with open(log_file, 'a') as f:
                f.write(f"Equilibrium {i+1}: {eq}\n")
    
    # Print summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"  Total modules analyzed: {len(modules)}")
    print(f"  Total equilibria detected: {len(equilibria)}")
    print(f"  Forcing attempts: {len(results['forcing_attempts'])}")
    print(f"{'='*60}\n")
    
    if log_file:
        with open(log_file, 'a') as f:
            f.write(f"\nSUMMARY\n")
            f.write(f"  Total modules: {len(modules)}\n")
            f.write(f"  Equilibria: {len(equilibria)}\n")
            f.write(f"  Forcing attempts: {len(results['forcing_attempts'])}\n")
            f.write(f"{'='*60}\n\n")
    
    return results


def main():
    """Main entry point for the runner script."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Run Nash Equilibrium Detection on module interaction data.'
    )
    parser.add_argument(
        'input_file',
        help='Path to JSON file containing module interaction data'
    )
    parser.add_argument(
        '--log', '-l',
        default=None,
        help='Path to log file (default: no logging to file)'
    )
    parser.add_argument(
        '--output', '-o',
        default=None,
        help='Path to output JSON results file (default: print to console only)'
    )
    parser.add_argument(
        '--threshold', '-t',
        type=float,
        default=0.5,
        help='Detection threshold (default: 0.5)'
    )
    
    args = parser.parse_args()
    
    # Load interaction data
    print(f"Loading interaction data from: {args.input_file}")
    interaction_data = load_interaction_data(args.input_file)
    
    # Initialize detector
    print("Initializing NashEquilibriumDetector...")
    detector = NashEquilibriumDetector(threshold=args.threshold)
    
    # Run detection
    results = run_detection(detector, interaction_data, log_file=args.log)
    
    # Output results to JSON if requested
    if args.output:
        print(f"Writing results to: {args.output}")
        with open(args.output, 'w') as f:
            json.dump(results, f, indent=2)
        print("Results written successfully.")
    
    print("Detection run complete.")


if __name__ == '__main__':
    main()