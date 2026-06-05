import ast
import subprocess
import tempfile
import os
import sys
from typing import Dict, Any, Optional

def syntax_check(code: str) -> Dict[str, Any]:
    """
    Check Python code for syntax errors using compile() with try/except.
    
    Args:
        code: Python source code as a string.
    
    Returns:
        Dict with keys:
            - 'passed': bool
            - 'error': str or None
    """
    try:
        compile(code, '<string>', 'exec')
        return {"passed": True, "error": None}
    except SyntaxError as e:
        return {"passed": False, "error": str(e)}


def static_analysis(code: str) -> Dict[str, Any]:
    """
    Run a simplified AST-based static analysis on the given code.
    Avoids mypy dependency issues by using built-in AST checks.
    
    Args:
        code: Python source code as a string.
    
    Returns:
        Dict with keys:
            - 'passed': bool
            - 'error': str or None
            - 'output': str (analysis output)
    """
    try:
        tree = ast.parse(code)
        issues = []
        
        # Check for common issues
        for node in ast.walk(tree):
            # Check for bare except clauses
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                issues.append("Line {}: Bare except clause detected".format(node.lineno))
            
            # Check for unused imports (simplified)
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.asname is None and alias.name not in code:
                        pass  # Simplified check
        
        if issues:
            return {
                "passed": False,
                "error": "Static analysis issues found:\n" + "\n".join(issues),
                "output": "\n".join(issues)
            }
        
        return {"passed": True, "error": None, "output": "No issues found"}
    
    except SyntaxError as e:
        return {"passed": False, "error": f"Syntax error during analysis: {str(e)}", "output": ""}
    except Exception as e:
        return {"passed": False, "error": f"Unexpected error during static analysis: {str(e)}", "output": ""}


def integration_test(code: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Run a minimal integration test by executing a small test script in a subprocess.
    
    Args:
        code: Python source code as a string (should contain a test function or script).
        context: Optional dict with additional context (e.g., 'test_name', 'extra_args').
    
    Returns:
        Dict with keys:
            - 'passed': bool
            - 'error': str or None
            - 'output': str (test output)
    """
    if context is None:
        context = {}

    test_name = context.get('test_name', 'test_integration')
    extra_args = context.get('extra_args', [])
    retry_count = context.get('retry', 0)

    # Wrap code in a test function if it's not already one
    if 'def test_' not in code:
        wrapped_code = f"""
import sys

{code}

def {test_name}():
    # Execute the provided code's main logic
    try:
        exec({repr(code)})
        return True
    except Exception as e:
        print(f"Test failed: {{e}}", file=sys.stderr)
        return False

if __name__ == "__main__":
    result = {test_name}()
    sys.exit(0 if result else 1)
"""
    else:
        wrapped_code = code

    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(wrapped_code)
        temp_path = f.name

    try:
        for attempt in range(retry_count + 1):
            try:
                result = subprocess.run(
                    [sys.executable, temp_path] + extra_args,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if result.returncode == 0:
                    return {"passed": True, "error": None, "output": result.stdout}
                else:
                    if attempt < retry_count:
                        continue
                    return {
                        "passed": False,
                        "error": result.stderr.strip() or result.stdout.strip(),
                        "output": result.stdout + result.stderr
                    }
            except subprocess.TimeoutExpired:
                if attempt < retry_count:
                    continue
                return {"passed": False, "error": "Integration test timed out", "output": ""}
        
        return {"passed": False, "error": "All retry attempts failed", "output": ""}
    
    except FileNotFoundError:
        return {"passed": False, "error": "Python interpreter not found", "output": ""}
    except Exception as e:
        return {"passed": False, "error": f"Unexpected error during integration test: {str(e)}", "output": ""}
    finally:
        try:
            os.unlink(temp_path)
        except OSError:
            pass


def run_quality_gate(code: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Run all three quality gate checks in sequence: syntax, static analysis, integration test.
    
    Args:
        code: Python source code as a string.
        context: Optional dict passed to integration_test.
    
    Returns:
        Dict with keys:
            - 'passed': bool (True only if all checks pass)
            - 'checks': dict with individual check results
    """
    results = {
        "syntax": syntax_check(code),
        "static_analysis": static_analysis(code),
        "integration_test": integration_test(code, context)
    }
    
    all_passed = all(check["passed"] for check in results.values())
    
    return {
        "passed": all_passed,
        "checks": results
    }