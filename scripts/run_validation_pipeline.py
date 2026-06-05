#!/usr/bin/env python3
"""
Standalone script to validate a proposed mutation.
Runs all three validation phases and outputs a JSON report.
Also runs side-effect simulation and displays affected modules, risk score, and suggested compensations.
Usage:
    python scripts/run_validation_pipeline.py <mutation_file> [--old-code <code>] [--new-code <code>] [--auto-compensate]
"""

import argparse
import json
import sys
import os
from typing import Dict, Any, Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.validation.phase1_syntax import validate_syntax
from core.validation.phase2_semantics import validate_semantics
from core.validation.phase3_performance import validate_performance
from core.side_effects.simulator import simulate_side_effects
from core.compensation.applier import apply_compensations


def parse_mutation_file(filepath: str) -> Dict[str, Any]:
    """Parse a mutation description file (JSON format)."""
    with open(filepath, 'r') as f:
        return json.load(f)


def run_validation_pipeline(
    mutation: Dict[str, Any],
    old_code: Optional[str] = None,
    new_code: Optional[str] = None,
    auto_compensate: bool = False
) -> Dict[str, Any]:
    """
    Run all three validation phases on the given mutation, plus side-effect simulation.
    
    Args:
        mutation: Dictionary containing mutation description (must have 'old_code' and 'new_code' keys,
                  or provide them separately)
        old_code: Original code string (overrides mutation dict)
        new_code: Modified code string (overrides mutation dict)
        auto_compensate: If True, automatically apply suggested compensations
    
    Returns:
        Dictionary with validation results for each phase, side-effect analysis, and overall status
    """
    # Extract code from mutation or use provided strings
    old = old_code if old_code is not None else mutation.get('old_code', '')
    new = new_code if new_code is not None else mutation.get('new_code', '')
    
    if not old or not new:
        return {
            "status": "error",
            "error": "Both old_code and new_code must be provided",
            "phases": {},
            "side_effects": {}
        }
    
    results = {}
    overall_valid = True
    
    # Phase 1: Syntax Validation
    try:
        syntax_result = validate_syntax(old, new)
        results["phase1_syntax"] = {
            "valid": syntax_result.get("valid", False),
            "details": syntax_result.get("details", ""),
            "errors": syntax_result.get("errors", [])
        }
        if not syntax_result.get("valid", False):
            overall_valid = False
    except Exception as e:
        results["phase1_syntax"] = {
            "valid": False,
            "details": f"Exception during syntax validation: {str(e)}",
            "errors": [str(e)]
        }
        overall_valid = False
    
    # Phase 2: Semantics Validation (only if syntax passes)
    if results.get("phase1_syntax", {}).get("valid", False):
        try:
            semantics_result = validate_semantics(old, new)
            results["phase2_semantics"] = {
                "valid": semantics_result.get("valid", False),
                "details": semantics_result.get("details", ""),
                "warnings": semantics_result.get("warnings", [])
            }
            if not semantics_result.get("valid", False):
                overall_valid = False
        except Exception as e:
            results["phase2_semantics"] = {
                "valid": False,
                "details": f"Exception during semantics validation: {str(e)}",
                "warnings": []
            }
            overall_valid = False
    else:
        results["phase2_semantics"] = {
            "valid": False,
            "details": "Skipped due to syntax validation failure",
            "warnings": []
        }
    
    # Phase 3: Performance Validation (only if both previous phases pass)
    if (results.get("phase1_syntax", {}).get("valid", False) and 
        results.get("phase2_semantics", {}).get("valid", False)):
        try:
            performance_result = validate_performance(old, new)
            results["phase3_performance"] = {
                "valid": performance_result.get("valid", False),
                "details": performance_result.get("details", ""),
                "metrics": performance_result.get("metrics", {})
            }
            if not performance_result.get("valid", False):
                overall_valid = False
        except Exception as e:
            results["phase3_performance"] = {
                "valid": False,
                "details": f"Exception during performance validation: {str(e)}",
                "metrics": {}
            }
            overall_valid = False
    else:
        results["phase3_performance"] = {
            "valid": False,
            "details": "Skipped due to previous phase failure",
            "metrics": {}
        }
    
    # Side-effect simulation (runs regardless of validation results)
    side_effects_result = {}
    try:
        side_effects = simulate_side_effects(old, new)
        side_effects_result = {
            "affected_modules": side_effects.get("affected_modules", []),
            "risk_score": side_effects.get("risk_score", 0.0),
            "suggested_compensations": side_effects.get("suggested_compensations", [])
        }
    except Exception as e:
        side_effects_result = {
            "affected_modules": [],
            "risk_score": 0.0,
            "suggested_compensations": [],
            "error": f"Exception during side-effect simulation: {str(e)}"
        }
    
    # Apply compensations if auto_compensate flag is set
    if auto_compensate and side_effects_result.get("suggested_compensations"):
        try:
            compensation_result = apply_compensations(
                old, new, side_effects_result["suggested_compensations"]
            )
            side_effects_result["compensation_applied"] = True
            side_effects_result["compensation_details"] = compensation_result
        except Exception as e:
            side_effects_result["compensation_applied"] = False
            side_effects_result["compensation_error"] = str(e)
    else:
        side_effects_result["compensation_applied"] = False
    
    return {
        "status": "valid" if overall_valid else "invalid",
        "overall_valid": overall_valid,
        "phases": results,
        "side_effects": side_effects_result,
        "mutation": mutation
    }


def main():
    parser = argparse.ArgumentParser(
        description="Validate a proposed mutation through all three phases and analyze side effects"
    )
    parser.add_argument(
        "mutation_file",
        nargs="?",
        help="Path to JSON file containing mutation description (optional if --old-code and --new-code provided)"
    )
    parser.add_argument(
        "--old-code",
        help="Original code string (overrides mutation file)"
    )
    parser.add_argument(
        "--new-code",
        help="Modified code string (overrides mutation file)"
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print the JSON output"
    )
    parser.add_argument(
        "--auto-compensate",
        action="store_true",
        help="Automatically apply suggested compensations"
    )
    
    args = parser.parse_args()
    
    # Determine mutation source
    mutation = {}
    if args.mutation_file:
        if not os.path.exists(args.mutation_file):
            print(json.dumps({"status": "error", "error": f"File not found: {args.mutation_file}"}))
            sys.exit(1)
        mutation = parse_mutation_file(args.mutation_file)
    
    if not mutation and not args.old_code and not args.new_code:
        print(json.dumps({"status": "error", "error": "No mutation provided. Provide a file or --old-code and --new-code."}))
        sys.exit(1)
    
    # Run validation
    result = run_validation_pipeline(mutation, args.old_code, args.new_code, args.auto_compensate)
    
    # Output result
    indent = 2 if args.pretty else None
    print(json.dumps(result, indent=indent))
    
    # Exit with appropriate code
    if result.get("status") == "error":
        sys.exit(2)
    elif not result.get("overall_valid", False):
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()