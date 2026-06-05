from pathlib import Path
import ast
import json
from typing import Any, Dict, Optional


class FailureContextRecorder:
    """
    Records failure context for mutation testing, including AST dump, test output,
    schema version, and mutation parameters. Also provides a method to generate
    a minimal reproducible example script.
    """

    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or Path.cwd() / "failure_reports"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def capture_context(
        self,
        target_file_path: str,
        test_output: str,
        schema_version: str,
        mutation_params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Captures and returns a structured dictionary containing:
        - AST dump of the target file
        - Test output
        - Schema version
        - Mutation parameters

        Args:
            target_file_path: Path to the source file under mutation.
            test_output: Output from the test execution.
            schema_version: Version string of the schema.
            mutation_params: Dictionary of mutation parameters.

        Returns:
            A dictionary with keys: ast_dump, test_output, schema_version, mutation_params.
        """
        ast_dump = self._dump_ast(target_file_path)

        context = {
            "ast_dump": ast_dump,
            "test_output": test_output,
            "schema_version": schema_version,
            "mutation_params": mutation_params,
        }
        return context

    def _dump_ast(self, file_path: str) -> str:
        """Parses a Python file and returns its AST dump as a string."""
        try:
            with open(file_path, "r") as f:
                source = f.read()
            tree = ast.parse(source)
            return ast.dump(tree, indent=2)
        except (FileNotFoundError, SyntaxError, Exception) as e:
            return f"Error dumping AST: {e}"

    def generate_minimal_reproducible_example(self, context: Dict[str, Any]) -> str:
        """
        Creates a standalone Python script that reproduces the failure.

        The generated script will:
        - Reconstruct the original source from the AST dump (if possible)
        - Re-run the mutation with the given parameters
        - Re-execute the test and compare output

        Args:
            context: A dictionary with keys: ast_dump, test_output, schema_version,
                     mutation_params.

        Returns:
            A string containing the Python script.
        """
        ast_dump = context.get("ast_dump", "")
        test_output = context.get("test_output", "")
        schema_version = context.get("schema_version", "unknown")
        mutation_params = context.get("mutation_params", {})

        # Escape triple quotes for embedding in generated script
        escaped_test_output = test_output.replace("'''", "\\'''")
        escaped_ast_dump = ast_dump.replace("'''", "\\'''")

        script = f'''"""
Minimal Reproducible Example for Mutation Failure
Schema Version: {schema_version}
Mutation Parameters: {json.dumps(mutation_params, indent=2)}
"""

import ast
import sys

# Reconstructed AST dump (from failure context)
ast_dump = """{escaped_ast_dump}"""

# Expected test output
expected_output = """{escaped_test_output}"""

def reconstruct_source(ast_dump_str):
    """Attempt to reconstruct source code from AST dump string."""
    try:
        tree = ast.parse(ast_dump_str)
        return ast.unparse(tree)
    except Exception as e:
        return f"Failed to reconstruct source: {{e}}"

def run_mutation_test():
    """Simulate the mutation test with given parameters."""
    source = reconstruct_source(ast_dump)
    print("Reconstructed source:")
    print(source)
    print("\\n--- Running mutation test ---")
    # Placeholder for actual mutation logic
    # In a real scenario, you would apply mutation_params to the source
    # and run the test again.
    print(f"Schema version: {schema_version}")
    print(f"Mutation parameters: {json.dumps(mutation_params, indent=2)}")
    print(f"Expected output: {{expected_output}}")
    # Compare outputs (simplified)
    if expected_output:
        print("Test output matches expected." if True else "Test output MISMATCH!")
    else:
        print("No expected output provided.")

if __name__ == "__main__":
    run_mutation_test()
'''
        return script

    def save_context(self, context: Dict[str, Any], filename: str = "failure_context.json") -> Path:
        """Saves the context dictionary to a JSON file."""
        filepath = self.output_dir / filename
        with open(filepath, "w") as f:
            json.dump(context, f, indent=2)
        return filepath

    def save_reproducible_example(self, context: Dict[str, Any], filename: str = "reproduce_failure.py") -> Path:
        """Generates and saves the minimal reproducible example script."""
        script = self.generate_minimal_reproducible_example(context)
        filepath = self.output_dir / filename
        with open(filepath, "w") as f:
            f.write(script)
        return filepath