#!/usr/bin/env python3
"""bootstrap_ecology.py - Minimal bootstrap script for ecology engine initialization.

This script initializes the ecology engine, generates an initial test suite mutation,
and runs it. It is designed to have minimal dependencies to avoid import issues.
"""

import sys
import os
import random
import subprocess
import tempfile
import json
from pathlib import Path

# ---------------------------------------------------------------------------
# Minimal ecology engine core (self-contained)
# ---------------------------------------------------------------------------

class EcologyEngine:
    """Minimal ecology engine that can generate and run test mutations."""

    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root).resolve()
        self.test_dir = self.project_root / "tests"
        self.mutations = []
        self.results = []

    def discover_tests(self) -> list:
        """Discover test files in the project's test directory."""
        if not self.test_dir.exists():
            print(f"[WARN] Test directory {self.test_dir} does not exist.")
            return []
        test_files = sorted(self.test_dir.glob("test_*.py"))
        print(f"[INFO] Discovered {len(test_files)} test files.")
        return test_files

    def generate_mutation(self, test_file: Path) -> dict:
        """Generate a simple mutation for a given test file.

        The mutation is a dict describing a change to the test file.
        """
        mutation = {
            "file": str(test_file),
            "type": random.choice(["comment_swap", "assert_flip", "import_remove"]),
            "description": "",
        }
        if mutation["type"] == "comment_swap":
            mutation["description"] = f"Swap a comment in {test_file.name}"
        elif mutation["type"] == "assert_flip":
            mutation["description"] = f"Flip an assertion in {test_file.name}"
        elif mutation["type"] == "import_remove":
            mutation["description"] = f"Remove an import in {test_file.name}"
        return mutation

    def apply_mutation(self, mutation: dict) -> str:
        """Apply a mutation to a test file and return the mutated content.

        For simplicity, this reads the file, applies a trivial change,
        and returns the new content. The original file is NOT modified.
        """
        filepath = Path(mutation["file"])
        if not filepath.exists():
            return ""
        original = filepath.read_text()
        lines = original.splitlines(keepends=True)
        if mutation["type"] == "comment_swap":
            # Find first comment line and replace it
            for i, line in enumerate(lines):
                stripped = line.strip()
                if stripped.startswith("#"):
                    lines[i] = f"# MUTATED: {stripped[1:].strip()}\n"
                    break
        elif mutation["type"] == "assert_flip":
            # Find first assert and negate it
            for i, line in enumerate(lines):
                if "assert " in line:
                    lines[i] = line.replace("assert ", "assert not ", 1)
                    break
        elif mutation["type"] == "import_remove":
            # Remove first import line
            for i, line in enumerate(lines):
                if line.strip().startswith("import ") or line.strip().startswith("from "):
                    lines[i] = f"# REMOVED: {line}"
                    break
        return "".join(lines)

    def run_mutation(self, mutation: dict) -> dict:
        """Run a mutation by writing a temporary file and executing it.

        Returns a dict with 'file', 'type', 'passed', and 'output'.
        """
        filepath = Path(mutation["file"])
        if not filepath.exists():
            return {"file": mutation["file"], "type": mutation["type"], "passed": False, "output": "File not found"}

        mutated_content = self.apply_mutation(mutation)
        if not mutated_content:
            return {"file": mutation["file"], "type": mutation["type"], "passed": False, "output": "Empty content"}

        # Write mutated content to a temporary file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, dir=str(self.project_root)) as tmp:
            tmp.write(mutated_content)
            tmp_path = tmp.name

        try:
            result = subprocess.run(
                [sys.executable, tmp_path],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(self.project_root),
            )
            passed = result.returncode == 0
            output = result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            passed = False
            output = "Timeout"
        except Exception as e:
            passed = False
            output = str(e)
        finally:
            os.unlink(tmp_path)

        return {
            "file": mutation["file"],
            "type": mutation["type"],
            "passed": passed,
            "output": output[:500],
        }

    def run(self):
        """Main bootstrap sequence: discover tests, generate mutations, run them."""
        print("=" * 60)
        print("Ecology Engine Bootstrap")
        print("=" * 60)

        test_files = self.discover_tests()
        if not test_files:
            print("[ERROR] No test files found. Exiting.")
            return

        # Generate one mutation per test file
        for tf in test_files:
            mutation = self.generate_mutation(tf)
            self.mutations.append(mutation)
            print(f"[MUTATION] {mutation['description']}")

        print(f"\n[INFO] Running {len(self.mutations)} mutations...\n")

        # Run each mutation
        for mutation in self.mutations:
            result = self.run_mutation(mutation)
            self.results.append(result)
            status = "PASSED" if result["passed"] else "FAILED"
            print(f"  [{status}] {mutation['description']}")

        # Summary
        passed = sum(1 for r in self.results if r["passed"])
        failed = len(self.results) - passed
        print(f"\n[SUMMARY] {passed} passed, {failed} failed out of {len(self.results)} mutations.")

        # Save results to a JSON file for further analysis
        results_file = self.project_root / "bootstrap_results.json"
        with open(results_file, "w") as f:
            json.dump(self.results, f, indent=2)
        print(f"[INFO] Results saved to {results_file}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    """Entry point for the bootstrap script."""
    project_root = os.environ.get("PROJECT_ROOT", ".")
    engine = EcologyEngine(project_root)
    engine.run()


if __name__ == "__main__":
    main()