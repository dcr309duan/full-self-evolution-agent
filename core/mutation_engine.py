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


def mutate(func_a, func_b, operator="crossover"):
    """Use LLM to create a mutation from two parent functions."""
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
    
    result = call_deepseek(messages, temperature=0.8, max_tokens=1024)
    
    if result.startswith("```"):
        lines = result.split('\n')
        result = '\n'.join(lines[1:-1]) if lines[-1].strip() == '```' else '\n'.join(lines[1:])
    
    return result.strip()


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


def run_mutation_cycle(num_mutations=3):
    """Run a complete mutation cycle."""
    pool = get_function_pool()
    if len(pool) < 2:
        return {"mutations": 0, "successes": 0, "reason": "Pool too small"}
    
    operators = ["crossover", "mutate", "hybrid"]
    results = []
    
    for i in range(num_mutations):
        func_a, func_b = random.sample(pool, 2)
        operator = random.choice(operators)
        
        try:
            new_code = mutate(func_a, func_b, operator)
            
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
    
    successes = sum(1 for r in results if r.get("test_result", {}).get("valid") and r.get("test_result", {}).get("score", 0) >= 0.4)
    return {"mutations": len(results), "successes": successes, "details": results}


def save_successful_mutation(name, code):
    """Save a successful mutation to the pool using atomic writes."""
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


if __name__ == "__main__":
    print("Running mutation cycle...")
    result = run_mutation_cycle(3)
    print(f"Mutations: {result['mutations']}, Successes: {result['successes']}")
    for r in result.get("details", []):
        if "error" not in r:
            print(f"  {r.get('test_result', {}).get('reason', '?')} | score={r.get('test_result', {}).get('score', 0)}")