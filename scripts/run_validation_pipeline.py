#!/usr/bin/env python3
"""
Standalone script to validate a proposed mutation.
Runs all three validation phases and outputs a JSON report.
Usage:
    python scripts/run_validation_pipeline.py <mutation_file> [--old-code <code>] [--new-code <code>]
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


def parse_mutation_file(filepath: str) -> Dict[str, Any]:
    """Parse a mutation description file (JSON format)."""
    with open(filepath, 'r') as f:
        return json.load(f)


def run_validation_pipeline(
    mutation: Dict[str, Any],
    old_code: Optional[str] = None,
    new_code: Optional[str] = None
) -> Dict[str, Any]:
    """
    Run all three validation phases on the given mutation.
    
    Args:
        mutation: Dictionary containing mutation description (must have 'old_code' and 'new_code' keys,
                  or provide them separately)
        old_code: Original code string (overrides mutation dict)
        new_code: Modified code string (overrides mutation dict)
    
    Returns:
        Dictionary with validation results for each phase and overall status
    """
    # Extract code from mutation or use provided strings
    old = old_code if old_code is not None else mutation.get('old_code', '')
    new = new_code if new_code is not None else mutation.get('new_code', '')
    
    if not old or not new:
        return {
            "status": "error",
            "error": "Both old_code and new_code must be provided",
            "phases": {}
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
    
    return {
        "status": "valid" if overall_valid else "invalid",
        "overall_valid": overall_valid,
        "phases": results,
        "mutation": mutation
    }


def main():
    parser = argparse.ArgumentParser(
        description="Validate a proposed mutation through all three phases"
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
    result = run_validation_pipeline(mutation, args.old_code, args.new_code)
    
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