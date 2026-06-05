"""Mutation engine - genetic programming inspired capability evolution.

Randomly selects existing functions/strategies, combines or modifies them,
tests against a problem suite, and promotes successful mutations.
"""
import json
import os
import sys
import random
import time
import ast
import shutil
import tempfile
import difflib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.llm import call_deepseek, evaluate_code
from core.memory import add_insight, record_success, record_failure, get_knowledge_base, save_knowledge_base
from core.self_modify import validate_python, safe_execute
from core.fs_abstraction import FileSystemAbstraction, get_fs
from config import PROJECT_ROOT, MEMORY_DIR


SEED_FUNCTIONS = [
    {"name": "fibonacci", "code": "def fibonacci(n):\n    a, b = 0, 1\n    for _ in range(n):\n        a, b = b, a + b\n    return a"},
    {"name": "is_prime", "code": "def is_prime(n):\n    if n < 2: return False\n    for i in range(2, int(n**0.5)+1):\n        if n % i == 0: return False\n    return True"},
    {"name": "quicksort", "code": "def quicksort(lst):\n    if len(lst) <= 1: return lst\n    pivot = lst[len(lst)//2]\n    left = [x for x in lst if x < pivot]\n    mid = [x for x in lst if x == pivot]\n    right = [x for x in lst if x > pivot]\n    return quicksort(left) + mid + quicksort(right)"},
    {"name": "flatten", "code": "def flatten(lst):\n    result = []\n    for item in lst:\n        if isinstance(item, list):\n            result.extend(flatten(item))\n        else:\n            result.append(item)\n    return result"},
    {"name": "memoize", "code": "def memoize(func):\n    cache = {}\n    def wrapper(*args):\n        if args not in cache:\n            cache[args] = func(*args)\n        return cache[args]\n    return wrapper"},
    {"name": "retry", "code": "def retry(func, max_attempts=3, delay=1):\n    import time\n    for attempt in range(max_attempts):\n        try:\n            return func()\n        except Exception as e:\n            if attempt == max_attempts - 1: raise\n            time.sleep(delay)"},
]

PROBLEM_SUITE = [
    {"name": "sort_numbers", "input": "[3,1,4,1,5,9,2,6]", "expected": "[1,1,2,3,4,5,6,9]", "test": "assert sorted_result == [1,1,2,3,4,5,6,9]"},
    {"name": "find_primes", "input": "20", "expected": "[2,3,5,7,11,13,17,19]", "test": "assert all(is_prime(p) for p in [2,3,5,7,11,13,17,19])"},
    {"name": "fibonacci_10", "input": "10", "expected": "55", "test": "assert result == 55"},
    {"name": "flatten_nested", "input": "[[1,[2,3]],[4,[5,[6]]]]", "expected": "[1,2,3,4,5,6]", "test": "assert result == [1,2,3,4,5,6]"},
]

# Configuration flag for simulation mode
simulation_mode = True

# Dry run mode flag - when True, simulate mutations without writing to disk
dry_run_mode = False

# Meta-bias parameter for mutation weighting
meta_bias = None

# Configuration flag for meta-mutation selector
META_MUTATION_ENABLED = False

# Sandbox mode flag - when True, clone affected files before mutation
sandbox_mode = False

# Mutation provenance tracking
mutation_provenance = []

# Test-driven mutation mode flag - when True, mutations must pass a generated test
TEST_DRIVEN_MUTATION_ENABLED = False

# Load configuration from system_config.json
config_path = os.path.join(PROJECT_ROOT, "system_config.json")
try:
    with open(config_path, 'r') as f:
        config = json.load(f)
        META_MUTATION_ENABLED = config.get("META_MUTATION_ENABLED", False)
        sandbox_mode = config.get("sandbox_mode", False)
        dry_run_mode = config.get("dry_run_mode", False)
        TEST_DRIVEN_MUTATION_ENABLED = config.get("TEST_DRIVEN_MUTATION_ENABLED", False)
except (FileNotFoundError, json.JSONDecodeError):
    pass


def get_function_pool():
    """Get all available functions for mutation."""
    pool = list(SEED_FUNCTIONS)
    mutations_path = os.path.join(MEMORY_DIR, "successful_mutations.json")
    fs = get_fs()
    try:
        content = fs.read_file(mutations_path)
        saved = json.loads(content)
        pool.extend(saved)
    except (FileNotFoundError, json.JSONDecodeError, PermissionError):
        pass
    return pool


def emit_event(event_type, context=None):
    """Emit an instrumentation event for the test harness."""
    event = {
        "type": event_type,
        "timestamp": time.time(),
        "context": context or {}
    }
    # Log to mutation log for test harness to read
    log_path = os.path.join(MEMORY_DIR, "instrumentation_events.json")
    fs = get_fs()
    try:
        content = fs.read_file(log_path)
        events = json.loads(content)
    except (FileNotFoundError, json.JSONDecodeError, PermissionError):
        events = []
    events.append(event)
    if len(events) > 1000:
        events = events[-1000:]
    try:
        fs.atomic_write(log_path, json.dumps(events, indent=2, ensure_ascii=False))
    except Exception:
        pass
    return event


def clone_file_for_sandbox(file_path):
    """Clone a file to a sandbox location before mutation."""
    if not sandbox_mode:
        return file_path
    
    if not os.path.exists(file_path):
        return file_path
    
    # Create sandbox directory
    sandbox_dir = os.path.join(tempfile.gettempdir(), "mutation_sandbox", str(int(time.time())))
    os.makedirs(sandbox_dir, exist_ok=True)
    
    # Clone the file
    clone_path = os.path.join(sandbox_dir, os.path.basename(file_path))
    shutil.copy2(file_path, clone_path)
    
    return clone_path


def track_provenance(goal_id, mutation_details):
    """Track which goal caused which mutation."""
    global mutation_provenance
    record = {
        "goal_id": goal_id,
        "timestamp": time.time(),
        "mutation_details": mutation_details
    }
    mutation_provenance.append(record)
    
    # Persist provenance to file
    provenance_path = os.path.join(MEMORY_DIR, "mutation_provenance.json")
    fs = get_fs()
    try:
        content = fs.read_file(provenance_path)
        provenance = json.loads(content)
    except (FileNotFoundError, json.JSONDecodeError, PermissionError):
        provenance = []
    provenance.append(record)
    if len(provenance) > 1000:
        provenance = provenance[-1000:]
    try:
        fs.atomic_write(provenance_path, json.dumps(provenance, indent=2, ensure_ascii=False))
    except Exception:
        pass


def mutate(func_a, func_b, operator="crossover", goal_context=None):
    """Use LLM to create a mutation from two parent functions."""
    # Emit mutation_start event
    emit_event("mutation_start", {
        "goal_context": goal_context,
        "parent_a": func_a["name"],
        "parent_b": func_b["name"],
        "operator": operator
    })
    
    prompt = f"""You are a genetic programming engine. Create a NEW useful function by applying 
the '{operator}' operator to these two parent functions:

Parent A:
```python
{func_a['code']}
```

Parent B:
```python
{func_b['code']}
```

Operators:
- crossover: combine logic/patterns from both into something new
- mutate: take one parent and significantly alter its behavior  
- hybrid: use structure of one with the domain of another

Create a NEW, useful function that is different from both parents.
Output ONLY the Python function definition, no explanation."""

    messages = [
        {"role": "system", "content": "You output only Python function code. No markdown, no explanation."},
        {"role": "user", "content": prompt}
    ]
    
    try:
        result = call_deepseek(messages, temperature=0.8, max_tokens=1024)
        
        if result.startswith("```"):
            lines = result.split('\n')
            result = '\n'.join(lines[1:-1]) if lines[-1].strip() == '```' else '\n'.join(lines[1:])
        
        # Emit mutation_success event
        emit_event("mutation_success", {
            "goal_context": goal_context,
            "parent_a": func_a["name"],
            "parent_b": func_b["name"],
            "operator": operator,
            "diff": result[:500]  # Truncate for event size
        })
        
        return result.strip()
    except Exception as e:
        # Emit mutation_failure event
        emit_event("mutation_failure", {
            "goal_context": goal_context,
            "parent_a": func_a["name"],
            "parent_b": func_b["name"],
            "operator": operator,
            "error": str(e)
        })
        raise


def generate_test_for_code(code):
    """Generate a test that the current code would fail.
    
    Uses LLM to create a test case that exposes a limitation or bug in the code.
    
    Args:
        code: The current code to generate a failing test for
        
    Returns:
        dict with 'test_code' (the test as Python code) and 'description' (human-readable)
    """
    prompt = f"""You are a test-driven development assistant. Given the following Python code, 
generate a test case that the code would FAIL on. The test should expose a limitation, edge case, 
or bug in the code. Output ONLY the test code as a Python assert statement or function.

Code:
```python
{code}
```

Requirements:
- The test must be a valid Python expression that evaluates to True if the code passes
- The test must FAIL on the current code
- The test should be specific and deterministic
- Output ONLY the test code, no explanation"""

    messages = [
        {"role": "system", "content": "You output only Python test code. No markdown, no explanation."},
        {"role": "user", "content": prompt}
    ]
    
    try:
        result = call_deepseek(messages, temperature=0.7, max_tokens=512)
        
        if result.startswith("```"):
            lines = result.split('\n')
            result = '\n'.join(lines[1:-1]) if lines[-1].strip() == '```' else '\n'.join(lines[1:])
        
        test_code = result.strip()
        
        # Validate the test code is syntactically valid
        try:
            ast.parse(test_code)
        except SyntaxError:
            # If not valid, wrap in a simple assert
            test_code = f"assert {test_code}"
            try:
                ast.parse(test_code)
            except SyntaxError:
                return None
        
        return {
            "test_code": test_code,
            "description": f"Generated test: {test_code[:100]}"
        }
    except Exception:
        return None


def test_mutation(code):
    """Test a mutated function for basic validity."""
    valid, error = validate_python(code)
    if not valid:
        return {"valid": False, "reason": f"Syntax error: {error}", "score": 0}
    
    test_code = f"""
{code}

# Basic tests
import inspect
funcs = [obj for name, obj in locals().items() if callable(obj) and not name.startswith('_')]
if not funcs:
    print("NO_FUNCTION")
else:
    func = funcs[-1]
    print(f"FUNCTION: {{func.__name__}}")
    # Try calling with various inputs
    test_inputs = [[], [1], [1,2,3], [5], [[1,[2,3]]]]
    successes = 0
    for inp in test_inputs:
        try:
            result = func(*inp) if inp else func()
            successes += 1
        except:
            pass
    print(f"SCORE: {{successes}}/{{len(test_inputs)}}")
"""
    result = safe_execute(test_code, timeout=10)
    
    if not result["success"]:
        return {"valid": False, "reason": result["stderr"][:200], "score": 0}
    
    stdout = result["stdout"]
    if "NO_FUNCTION" in stdout:
        return {"valid": False, "reason": "No callable function found", "score": 0}
    
    score = 0
    for line in stdout.split('\n'):
        if line.startswith("SCORE:"):
            try:
                parts = line.split(":")[1].strip().split("/")
                score = int(parts[0]) / int(parts[1])
            except:
                pass
    
    return {"valid": True, "reason": "OK", "score": score, "stdout": stdout[:200]}


def test_mutation_with_generated_test(code, test_spec):
    """Test a mutated function against a generated test.
    
    Args:
        code: The mutated code to test
        test_spec: Dict with 'test_code' key containing the test to run
        
    Returns:
        dict with 'passed' bool and 'reason' string
    """
    if not test_spec or "test_code" not in test_spec:
        return {"passed": False, "reason": "No test specification provided"}
    
    test_code = test_spec["test_code"]
    
    # Execute the code with the test
    full_code = f"""
{code}

# Run the generated test
try:
    {test_code}
    print("TEST_PASSED")
except AssertionError as e:
    print(f"TEST_FAILED: {{str(e)}}")
except Exception as e:
    print(f"TEST_ERROR: {{str(e)}}")
"""
    
    result = safe_execute(full_code, timeout=10)
    
    if not result["success"]:
        return {"passed": False, "reason": f"Execution error: {result['stderr'][:200]}"}
    
    stdout = result["stdout"]
    if "TEST_PASSED" in stdout:
        return {"passed": True, "reason": "Generated test passed"}
    elif "TEST_FAILED" in stdout:
        return {"passed": False, "reason": f"Test failed: {stdout}"}
    elif "TEST_ERROR" in stdout:
        return {"passed": False, "reason": f"Test error: {stdout}"}
    else:
        return {"passed": False, "reason": f"Unexpected output: {stdout[:200]}"}


def simulate_mutation(module_path, old_ast, new_ast):
    """Simulate a mutation proposal and return validation results.
    
    Args:
        module_path: Path to the module being mutated
        old_ast: The original AST before mutation
        new_ast: The proposed new AST after mutation
        
    Returns:
        dict with keys:
            - valid: bool indicating if mutation is safe
            - reason: string explanation
            - score: float score from simulation
    """
    # Convert AST back to code for validation
    try:
        new_code = ast.unparse(new_ast)
    except Exception as e:
        return {"valid": False, "reason": f"Failed to unparse AST: {str(e)}", "score": 0}
    
    # Validate the new code
    valid, error = validate_python(new_code)
    if not valid:
        return {"valid": False, "reason": f"Syntax error in proposed mutation: {error}", "score": 0}
    
    # Run simulation tests
    test_result = test_mutation(new_code)
    
    if test_result["valid"]:
        return {
            "valid": True,
            "reason": "Mutation simulation passed",
            "score": test_result["score"],
            "stdout": test_result.get("stdout", "")
        }
    else:
        return {
            "valid": False,
            "reason": test_result.get("reason", "Unknown simulation failure"),
            "score": 0
        }


def dry_run_mutation(func_a, func_b, operator="crossover", goal_context=None):
    """Simulate a mutation in dry run mode without writing to disk.
    
    Args:
        func_a: First parent function dict
        func_b: Second parent function dict
        operator: Mutation operator to use
        goal_context: Optional goal context for tracking
        
    Returns:
        dict with keys:
            - valid: bool indicating if mutation is valid
            - diff: Unified diff string showing proposed changes
            - syntax_valid: bool indicating if generated code has valid syntax
            - code: The proposed new code
            - score: Float score from simulation tests
            - reason: String explanation
    """
    try:
        new_code = mutate(func_a, func_b, operator, goal_context=goal_context)
    except Exception as e:
        return {
            "valid": False,
            "diff": "",
            "syntax_valid": False,
            "code": "",
            "score": 0,
            "reason": f"Mutation generation failed: {str(e)}"
        }
    
    # Validate syntax of generated code
    syntax_valid = True
    syntax_error = None
    try:
        ast.parse(new_code)
    except SyntaxError as e:
        syntax_valid = False
        syntax_error = str(e)
    
    if not syntax_valid:
        return {
            "valid": False,
            "diff": "",
            "syntax_valid": False,
            "code": new_code,
            "score": 0,
            "reason": f"Syntax error in generated code: {syntax_error}"
        }
    
    # Generate diff against parent code (use func_a as baseline)
    parent_code = func_a["code"]
    diff_lines = difflib.unified_diff(
        parent_code.splitlines(keepends=True),
        new_code.splitlines(keepends=True),
        fromfile=f"parent_{func_a['name']}",
        tofile=f"mutation_{operator}_{func_a['name']}_{func_b['name']}",
        lineterm=''
    )
    diff = ''.join(diff_lines)
    
    # Run simulation tests
    test_result = test_mutation(new_code)
    
    return {
        "valid": test_result["valid"],
        "diff": diff,
        "syntax_valid": True,
        "code": new_code,
        "score": test_result.get("score", 0),
        "reason": test_result.get("reason", "OK")
    }


def run_mutation_cycle(num_mutations=3, goal_context=None):
    """Run a complete mutation cycle."""
    global meta_bias
    
    pool = get_function_pool()
    if len(pool) < 2:
        return {"mutations": 0, "successes": 0, "reason": "Pool too small"}
    
    operators = ["crossover", "mutate", "hybrid"]
    
    # Apply meta-bias if meta-mutation selector is active
    if META_MUTATION_ENABLED:
        try:
            from core.meta_mutation_selector import MetaMutationSelector
            selector = MetaMutationSelector()
            highest_yield = selector.predict_highest_yield()
            if highest_yield is not None:
                meta_bias = highest_yield
                # Weight the probability distribution over mutation types
                weighted_operators = []
                for op in operators:
                    weight = highest_yield.get(op, 1.0)
                    weighted_operators.extend([op] * int(weight * 10))
                if weighted_operators:
                    operators = weighted_operators
        except ImportError:
            pass
    
    # Get current mutation rate from system state
    mutation_rate = 1.0  # Default to always mutate
    try:
        from core.system_state import get_system_state
        state = get_system_state()
        mutation_rate = state.get("mutation_rate", 1.0)
    except ImportError:
        pass
    except Exception:
        pass
    
    results = []
    
    for i in range(num_mutations):
        # Apply mutation rate: skip with probability (1 - mutation_rate)
        if random.random() > mutation_rate:
            results.append({
                "skipped": True,
                "reason": f"Mutation skipped due to mutation_rate={mutation_rate}",
                "timestamp": time.time()
            })
            continue
        
        func_a, func_b = random.sample(pool, 2)
        operator = random.choice(operators)
        
        # Handle dry run mode
        if dry_run_mode:
            dry_result = dry_run_mutation(func_a, func_b, operator, goal_context=goal_context)
            results.append({
                "parent_a": func_a["name"],
                "parent_b": func_b["name"],
                "operator": operator,
                "dry_run": True,
                "valid": dry_result["valid"],
                "diff": dry_result["diff"],
                "syntax_valid": dry_result["syntax_valid"],
                "code": dry_result["code"],
                "score": dry_result["score"],
                "reason": dry_result["reason"],
                "timestamp": time.time()
            })
            continue
        
        # Clone files if sandbox mode is enabled
        if sandbox_mode:
            # Clone the successful_mutations.json file for safety
            mutations_path = os.path.join(MEMORY_DIR, "successful_mutations.json")
            clone_path = clone_file_for_sandbox(mutations_path)
            if clone_path != mutations_path:
                print(f"Sandbox: Cloned {mutations_path} to {clone_path}")
        
        try:
            # Test-driven mutation mode: generate failing test first
            if TEST_DRIVEN_MUTATION_ENABLED:
                # Generate a test that the current code (parent) would fail
                test_spec = generate_test_for_code(func_a["code"])
                if test_spec is None:
                    # If we can't generate a test, skip this mutation
                    results.append({
                        "parent_a": func_a["name"],
                        "parent_b": func_b["name"],
                        "operator": operator,
                        "skipped": True,
                        "reason": "Could not generate failing test for parent code",
                        "timestamp": time.time()
                    })
                    continue
                
                # Generate the mutation
                new_code = mutate(func_a, func_b, operator, goal_context=goal_context)
                
                # Test the mutation against the generated test
                test_result = test_mutation_with_generated_test(new_code, test_spec)
                
                mutation_record = {
                    "parent_a": func_a["name"],
                    "parent_b": func_b["name"],
                    "operator": operator,
                    "code": new_code,
                    "test_result": test_result,
                    "generated_test": test_spec,
                    "timestamp": time.time(),
                    "test_driven": True
                }
                results.append(mutation_record)
                
                # Track provenance for this mutation
                if goal_context:
                    track_provenance(goal_context, mutation_record)
                
                # Only accept mutation if it passes the generated test
                if test_result["passed"]:
                    func_name = "unknown"
                    try:
                        tree = ast.parse(new_code)
                        for node in ast.walk(tree):
                            if isinstance(node, ast.FunctionDef):
                                func_name = node.name
                                break
                    except:
                        pass
                    
                    save_successful_mutation(func_name, new_code)
                    record_success(f"mutation:{operator}({func_a['name']},{func_b['name']})", f"Created {func_name}, passed generated test")
                else:
                    record_failure(f"mutation:{operator}({func_a['name']},{func_b['name']})", f"Failed generated test: {test_result.get('reason', 'unknown')}")
                
                continue
            
            # Original mutation flow (non-test-driven)
            new_code = mutate(func_a, func_b, operator, goal_context=goal_context)
            
            # Optional pre-validation step using simulation
            if simulation_mode:
                try:
                    new_ast = ast.parse(new_code)
                    # Create a mock module path for simulation
                    sim_path = f"simulated_mutation_{i}"
                    sim_result = simulate_mutation(sim_path, None, new_ast)
                    if not sim_result["valid"]:
                        mutation_record = {
                            "parent_a": func_a["name"],
                            "parent_b": func_b["name"],
                            "operator": operator,
                            "code": new_code,
                            "test_result": {"valid": False, "reason": f"Simulation rejected: {sim_result['reason']}", "score": 0},
                            "timestamp": time.time(),
                            "simulated": True
                        }
                        results.append(mutation_record)
                        continue
                except Exception as e:
                    # If simulation fails, fall through to normal testing
                    pass
            
            test_result = test_mutation(new_code)
            
            mutation_record = {
                "parent_a": func_a["name"],
                "parent_b": func_b["name"],
                "operator": operator,
                "code": new_code,
                "test_result": test_result,
                "timestamp": time.time()
            }
            results.append(mutation_record)
            
            # Track provenance for this mutation
            if goal_context:
                track_provenance(goal_context, mutation_record)
            
            if test_result["valid"] and test_result["score"] >= 0.4:
                func_name = "unknown"
                try:
                    tree = ast.parse(new_code)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.FunctionDef):
                            func_name = node.name
                            break
                except:
                    pass
                
                save_successful_mutation(func_name, new_code)
                record_success(f"mutation:{operator}({func_a['name']},{func_b['name']})", f"Created {func_name}, score={test_result['score']}")
            
        except Exception as e:
            results.append({"error": str(e), "operator": operator})
    
    log_mutations(results)
    
    successes = sum(1 for r in results if r.get("test_result", {}).get("passed") or (r.get("test_result", {}).get("valid") and r.get("test_result", {}).get("score", 0) >= 0.4))
    return {"mutations": len(results), "successes": successes, "details": results}


def save_successful_mutation(name, code):
    """Save a successful mutation to the pool using atomic writes."""
    # Skip saving in dry run mode
    if dry_run_mode:
        return
    
    path = os.path.join(MEMORY_DIR, "successful_mutations.json")
    fs = get_fs()
    
    # Check write permission before attempting mutation
    if not fs.check_permission(path, 'write'):
        print(f"Warning: No write permission for {path}, skipping mutation save")
        return
    
    try:
        content = fs.read_file(path)
        mutations = json.loads(content)
    except (FileNotFoundError, json.JSONDecodeError, PermissionError):
        mutations = []
    
    mutations.append({"name": name, "code": code, "created": time.time()})
    if len(mutations) > 50:
        mutations = mutations[-50:]
    
    # Use atomic write to prevent partial file states
    fs.atomic_write(path, json.dumps(mutations, indent=2, ensure_ascii=False))


def log_mutations(results):
    """Log mutation results using atomic writes."""
    # Skip logging in dry run mode
    if dry_run_mode:
        return
    
    path = os.path.join(MEMORY_DIR, "mutation_log.json")
    fs = get_fs()
    
    # Check write permission before attempting mutation
    if not fs.check_permission(path, 'write'):
        print(f"Warning: No write permission for {path}, skipping mutation log")
        return
    
    try:
        content = fs.read_file(path)
        log = json.loads(content)
    except (FileNotFoundError, json.JSONDecodeError, PermissionError):
        log = []
    
    log.append({"timestamp": time.time(), "results": results})
    if len(log) > 100:
        log = log[-100:]
    
    # Use atomic write to prevent partial file states
    fs.atomic_write(path, json.dumps(log, indent=2, ensure_ascii=False))


def get_mutation_provenance():
    """Get the mutation provenance tracking data."""
    return mutation_provenance


def generate_mutations(code, context=None):
    """Generate mutations for the given code.
    
    Args:
        code: The source code to mutate
        context: Optional context dictionary
        
    Returns:
        list of mutation specifications
    """
    pool = get_function_pool()
    if len(pool) < 2:
        return []
    
    mutations = []
    operators = ["crossover", "mutate", "hybrid"]
    
    for _ in range(3):
        func_a, func_b = random.sample(pool, 2)
        operator = random.choice(operators)
        
        try:
            new_code = mutate(func_a, func_b, operator, goal_context=context)
            mutations.append({
                "code": new_code,
                "operator": operator,
                "parent_a": func_a["name"],
                "parent_b": func_b["name"]
            })
        except Exception:
            continue
    
    return mutations


def apply_mutation(code, mutation_spec):
    """Apply a mutation specification to the given code.
    
    Args:
        code: The source code to apply mutation to
        mutation_spec: Dictionary with mutation details
        
    Returns:
        The mutated code string
    """
    if not mutation_spec or "code" not in mutation_spec:
        return code
    
    return mutation_spec["code"]


def validate_mutation(mutation_spec):
    """Validate a mutation specification.
    
    Args:
        mutation_spec: Dictionary with mutation details
        
    Returns:
        dict with 'valid' bool and 'reason' string
    """
    if not mutation_spec or "code" not in mutation_spec:
        return {"valid": False, "reason": "Invalid mutation specification"}
    
    code = mutation_spec["code"]
    
    # Check syntax
    try:
        ast.parse(code)
    except SyntaxError as e:
        return {"valid": False, "reason": f"Syntax error: {str(e)}"}
    
    # Run basic tests
    test_result = test_mutation(code)
    
    return {
        "valid": test_result["valid"],
        "reason": test_result.get("reason", "OK"),
        "score": test_result.get("score", 0)
    }