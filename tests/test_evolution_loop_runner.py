import argparse
import json
import sys
import os
from pathlib import Path

# Assuming the integration test harness is in a module named 'integration_test_harness'
# Adjust the import path as needed for your project structure.
try:
    from integration_test_harness import run_integration_test_cycle
except ImportError:
    # Fallback: if the harness is not importable, define a placeholder for testing.
    def run_integration_test_cycle(cycle_number, verbose=False):
        """Placeholder for the actual integration test harness function.
        
        In a real scenario, this function would execute a full cycle of 
        integration tests and return a list of step results.
        
        Returns:
            list of dict: Each dict represents a step result with keys:
                - 'step_name' (str)
                - 'status' (str): 'pass' or 'fail'
                - 'details' (str, optional): Additional info.
        """
        # Simulated results for demonstration.
        return [
            {"step_name": f"Step A of cycle {cycle_number}", "status": "pass", "details": ""},
            {"step_name": f"Step B of cycle {cycle_number}", "status": "fail", "details": "Timeout exceeded"},
            {"step_name": f"Step C of cycle {cycle_number}", "status": "pass", "details": ""},
        ]


def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Run evolution integration test loop and generate JSON report."
    )
    parser.add_argument(
        "--cycles",
        type=int,
        default=1,
        help="Number of cycles to run (default: 1)."
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output during test execution."
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="test_reports",
        help="Directory to write the JSON report (default: 'test_reports')."
    )
    return parser.parse_args()


def run_evolution_loop(cycles, verbose):
    """Run the integration test loop for the specified number of cycles.
    
    Args:
        cycles (int): Number of cycles to execute.
        verbose (bool): If True, print detailed progress.
    
    Returns:
        dict: A structured report containing per-cycle and per-step results.
    """
    report = {
        "cycles": [],
        "overall_pass": True
    }
    
    for cycle_num in range(1, cycles + 1):
        if verbose:
            print(f"Starting cycle {cycle_num}/{cycles}...")
        
        # Call the integration test harness for this cycle.
        step_results = run_integration_test_cycle(cycle_num, verbose=verbose)
        
        # Determine if this cycle passed (all steps pass).
        cycle_pass = all(step["status"] == "pass" for step in step_results)
        
        cycle_data = {
            "cycle_number": cycle_num,
            "pass": cycle_pass,
            "steps": step_results
        }
        report["cycles"].append(cycle_data)
        
        if verbose:
            print(f"Cycle {cycle_num} {'PASSED' if cycle_pass else 'FAILED'}")
            for step in step_results:
                status_icon = "✓" if step["status"] == "pass" else "✗"
                print(f"  {status_icon} {step['step_name']}: {step['status']}")
                if step.get("details"):
                    print(f"    Details: {step['details']}")
    
    # Overall pass only if all cycles passed.
    report["overall_pass"] = all(cycle["pass"] for cycle in report["cycles"])
    
    return report


def write_report(report, output_dir):
    """Write the JSON report to a file in the specified directory.
    
    Args:
        report (dict): The structured report to serialize.
        output_dir (str): Path to the output directory.
    
    Returns:
        str: The full path to the written report file.
    """
    # Ensure the output directory exists.
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    report_file = output_path / "evolution_test_report.json"
    with open(report_file, "w") as f:
        json.dump(report, f, indent=2)
    
    return str(report_file)


def main():
    """Entry point for the evolution loop runner."""
    args = parse_arguments()
    
    # Validate cycles argument.
    if args.cycles < 1:
        print("Error: --cycles must be at least 1.", file=sys.stderr)
        sys.exit(1)
    
    if args.verbose:
        print(f"Running {args.cycles} cycle(s) with verbose output.")
        print(f"Reports will be saved to: {args.output_dir}")
    
    # Execute the evolution loop.
    report = run_evolution_loop(args.cycles, args.verbose)
    
    # Write the JSON report.
    report_path = write_report(report, args.output_dir)
    print(f"Report written to: {report_path}")
    
    # Print summary.
    total_cycles = len(report["cycles"])
    passed_cycles = sum(1 for cycle in report["cycles"] if cycle["pass"])
    print(f"Summary: {passed_cycles}/{total_cycles} cycles passed.")
    
    # Return exit code based on overall pass/fail.
    if report["overall_pass"]:
        print("Overall: PASSED")
        sys.exit(0)
    else:
        print("Overall: FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()