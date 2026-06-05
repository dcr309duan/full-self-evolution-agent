#!/usr/bin/env python3
"""
Script: run_failure_analysis.py

Purpose:
    Run the failure pattern miner on all accumulated failure logs.
    Output a summary report to stdout.
    Optionally save the refactoring goals to a JSON file for the goal generator.

Usage:
    python scripts/run_failure_analysis.py [--output-goals goals.json]
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Any

# Import the failure pattern miner module.
# Adjust the import path based on your project structure.
try:
    from src.failure_pattern_miner import FailurePatternMiner, FailureLogEntry
except ImportError:
    # Fallback: assume the module is in the same package or adjust as needed.
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from src.failure_pattern_miner import FailurePatternMiner, FailureLogEntry


def collect_failure_logs(log_dir: str = "logs/failures") -> List[FailureLogEntry]:
    """
    Collect all failure log entries from the specified directory.

    Args:
        log_dir: Directory containing failure log files (JSON or plain text).

    Returns:
        List of FailureLogEntry objects.
    """
    log_path = Path(log_dir)
    if not log_path.exists():
        print(f"Warning: Failure log directory '{log_dir}' does not exist.", file=sys.stderr)
        return []

    entries: List[FailureLogEntry] = []
    for file_path in log_path.glob("*.json"):
        try:
            with open(file_path, "r") as f:
                data = json.load(f)
                # Support both single entry and list of entries
                if isinstance(data, list):
                    for item in data:
                        entries.append(FailureLogEntry(**item))
                else:
                    entries.append(FailureLogEntry(**data))
        except (json.JSONDecodeError, TypeError, KeyError) as e:
            print(f"Error parsing {file_path}: {e}", file=sys.stderr)
            continue

    # Also support plain text logs (one entry per line as JSON)
    for file_path in log_path.glob("*.log"):
        try:
            with open(file_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            data = json.loads(line)
                            entries.append(FailureLogEntry(**data))
                        except (json.JSONDecodeError, TypeError):
                            # Skip malformed lines
                            continue
        except IOError as e:
            print(f"Error reading {file_path}: {e}", file=sys.stderr)
            continue

    return entries


def generate_summary_report(miner: FailurePatternMiner) -> str:
    """
    Generate a human-readable summary report from the miner's analysis.

    Args:
        miner: An instance of FailurePatternMiner that has already analyzed logs.

    Returns:
        A string containing the summary report.
    """
    lines = []
    lines.append("=" * 60)
    lines.append("FAILURE PATTERN ANALYSIS SUMMARY REPORT")
    lines.append("=" * 60)
    lines.append("")

    patterns = miner.get_patterns()
    if not patterns:
        lines.append("No failure patterns detected.")
        lines.append("")
        return "\n".join(lines)

    lines.append(f"Total patterns found: {len(patterns)}")
    lines.append("")

    for idx, pattern in enumerate(patterns, start=1):
        lines.append(f"Pattern {idx}:")
        lines.append(f"  Description: {pattern.get('description', 'N/A')}")
        lines.append(f"  Frequency: {pattern.get('frequency', 0)}")
        lines.append(f"  Severity: {pattern.get('severity', 'unknown')}")
        lines.append(f"  Suggested fix: {pattern.get('suggested_fix', 'N/A')}")
        lines.append("")

    # Add refactoring goals if available
    goals = miner.get_refactoring_goals()
    if goals:
        lines.append("-" * 40)
        lines.append("REFACTORING GOALS")
        lines.append("-" * 40)
        lines.append("")
        for goal in goals:
            lines.append(f"  - {goal.get('goal', 'N/A')}")
            lines.append(f"    Priority: {goal.get('priority', 'medium')}")
            lines.append(f"    Rationale: {goal.get('rationale', 'N/A')}")
            lines.append("")

    lines.append("=" * 60)
    return "\n".join(lines)


def save_goals_to_json(miner: FailurePatternMiner, output_path: str) -> None:
    """
    Save the refactoring goals to a JSON file.

    Args:
        miner: An instance of FailurePatternMiner.
        output_path: Path to the output JSON file.
    """
    goals = miner.get_refactoring_goals()
    if not goals:
        print("No refactoring goals to save.", file=sys.stderr)
        return

    with open(output_path, "w") as f:
        json.dump(goals, f, indent=2)
    print(f"Refactoring goals saved to {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Run failure pattern miner on accumulated failure logs."
    )
    parser.add_argument(
        "--log-dir",
        type=str,
        default="logs/failures",
        help="Directory containing failure log files (default: logs/failures)",
    )
    parser.add_argument(
        "--output-goals",
        type=str,
        default=None,
        help="Optional path to save refactoring goals as JSON (e.g., goals.json)",
    )
    args = parser.parse_args()

    # Collect failure logs
    print(f"Collecting failure logs from '{args.log_dir}'...", file=sys.stderr)
    entries = collect_failure_logs(args.log_dir)
    print(f"Found {len(entries)} failure log entries.", file=sys.stderr)

    if not entries:
        print("No failure logs to analyze. Exiting.", file=sys.stderr)
        sys.exit(0)

    # Initialize and run the miner
    miner = FailurePatternMiner()
    miner.analyze(entries)

    # Generate and print summary report
    report = generate_summary_report(miner)
    print(report)

    # Optionally save refactoring goals
    if args.output_goals:
        save_goals_to_json(miner, args.output_goals)


if __name__ == "__main__":
    main()