"""Self-modification engine - the agent can modify its own code."""
import os
import sys
import ast
import traceback
import subprocess
from core.llm import call_deepseek, evaluate_code
from core.memory import add_insight, record_success, record_failure, get_knowledge_base
from config import PROJECT_ROOT


def read_file(filepath):
    """Read a file's contents."""
    full_path = os.path.join(PROJECT_ROOT, filepath) if not filepath.startswith('/') else filepath
    try:
        with open(full_path, 'r') as f:
            return f.read()
    except FileNotFoundError:
        return None


def write_file(filepath, content):
    """Write content to a file."""
    full_path = os.path.join(PROJECT_ROOT, filepath) if not filepath.startswith('/') else filepath
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, 'w') as f:
        f.write(content)


def validate_python(code):
    """Check if code is valid Python syntax."""
    try:
        ast.parse(code)
        return True, None
    except SyntaxError as e:
        return False, str(e)


def safe_execute(code, timeout=30):
    """Execute code in a subprocess for safety."""
    try:
        result = subprocess.run(
            [sys.executable, '-c', code],
            capture_output=True, text=True, timeout=timeout,
            cwd=PROJECT_ROOT
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "stdout": "", "stderr": "Timeout", "returncode": -1}
    except Exception as e:
        return {"success": False, "stdout": "", "stderr": str(e), "returncode": -1}


def generate_code(task, context=""):
    """Generate code for a specific task."""
    kb = get_knowledge_base()
    failed = kb.get("failed_approaches", [])[-5:]
    
    system_prompt = f"""You are the code generation module of a self-evolving AI agent.
Generate Python code that accomplishes the given task.
The code must be:
1. Self-contained or properly importing from the project
2. Safe - no destructive operations without safeguards
3. Correct - syntactically and logically valid

Project structure:
- config.py: configuration constants
- core/llm.py: DeepSeek API interface
- core/memory.py: memory/knowledge persistence
- core/reflection.py: self-reflection module
- core/self_modify.py: self-modification (this module)
- core/evolution_loop.py: main evolution loop

Recent failed approaches to avoid: {[f['approach'] for f in failed]}

Output ONLY the Python code, no markdown fences."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Task: {task}\n\nContext: {context}"}
    ]
    
    return call_deepseek(messages, temperature=0.4, max_tokens=4096)


def self_modify(target_file, modification_goal, dry_run=False):
    """Modify a file in the project to achieve a goal.
    
    Returns dict with keys: success, changes_made, reason
    """
    current_code = read_file(target_file)
    if current_code is None:
        system_prompt = f"""You are creating a new Python source file named '{target_file}'.
Output ONLY the file content that should be written to '{target_file}'.
Do NOT output a script that creates the file. Output the actual content of the target file itself.
Do NOT wrap in markdown code fences.
The file should be a proper Python module with imports, functions, and/or classes as needed."""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Create the file '{target_file}' with this purpose: {modification_goal}"}
        ]
        new_code = call_deepseek(messages, temperature=0.4, max_tokens=4096)
    else:
        prompt = f"""Modify the following code to achieve: {modification_goal}

Current code in '{target_file}':
```python
{current_code}
```

Output the COMPLETE modified file content. Do not use placeholders."""
        
        messages = [
            {"role": "system", "content": "You modify Python code to achieve specified goals. Output only the complete file content, no markdown fences."},
            {"role": "user", "content": prompt}
        ]
        new_code = call_deepseek(messages, temperature=0.3, max_tokens=8192)
    
    if new_code.startswith("```"):
        lines = new_code.split('\n')
        new_code = '\n'.join(lines[1:-1]) if lines[-1].strip() == '```' else '\n'.join(lines[1:])
    
    valid, error = validate_python(new_code)
    if not valid:
        record_failure(f"modify {target_file}: {modification_goal}", f"Syntax error: {error}")
        return {"success": False, "changes_made": None, "reason": f"Generated code has syntax error: {error}"}
    
    evaluation = evaluate_code(new_code, modification_goal)
    if not evaluation.get("safe", True):
        record_failure(f"modify {target_file}: {modification_goal}", "Safety check failed")
        return {"success": False, "changes_made": None, "reason": "Code failed safety evaluation"}
    
    if dry_run:
        return {"success": True, "changes_made": new_code, "reason": "Dry run - not applied"}
    
    if current_code:
        backup_path = target_file + '.bak'
        write_file(backup_path, current_code)
    
    write_file(target_file, new_code)
    
    test_result = safe_execute(f"import ast; ast.parse(open('{os.path.join(PROJECT_ROOT, target_file)}').read()); print('OK')")
    if not test_result["success"]:
        if current_code:
            write_file(target_file, current_code)
        record_failure(f"modify {target_file}", "Post-write validation failed")
        return {"success": False, "changes_made": None, "reason": "Post-write validation failed, reverted"}
    
    record_success(f"modify {target_file}: {modification_goal}", "Applied successfully")
    add_insight(f"Successfully modified {target_file} to: {modification_goal}")
    return {"success": True, "changes_made": f"Modified {target_file}", "reason": "Success"}


def add_capability(capability_name, capability_code, description=""):
    """Add a new capability to the agent."""
    target_file = f"capabilities/{capability_name}.py"
    
    valid, error = validate_python(capability_code)
    if not valid:
        return {"success": False, "reason": f"Invalid code: {error}"}
    
    evaluation = evaluate_code(capability_code, description or capability_name)
    if not evaluation.get("safe", True):
        return {"success": False, "reason": "Code failed safety check"}
    
    write_file(target_file, capability_code)
    
    record_success(f"add_capability: {capability_name}", description)
    add_insight(f"New capability added: {capability_name} - {description}")
    return {"success": True, "reason": f"Capability '{capability_name}' added"}


def execute_shell(command, timeout=60):
    """Execute a shell command safely."""
    dangerous = ['rm -rf /', 'mkfs', 'dd if=', ':(){', 'fork bomb']
    for d in dangerous:
        if d in command:
            return {"success": False, "stdout": "", "stderr": f"Blocked dangerous command: {d}"}
    
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True,
            timeout=timeout, cwd=PROJECT_ROOT
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout[:5000],
            "stderr": result.stderr[:2000],
            "returncode": result.returncode
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "stdout": "", "stderr": "Command timed out"}
    except Exception as e:
        return {"success": False, "stdout": "", "stderr": str(e)}
