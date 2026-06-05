"""Main evolution loop - the heart of the self-evolving agent."""
import json
import os
import sys
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import PROJECT_ROOT, MAX_EVOLUTION_CYCLES, CYCLE_INTERVAL_SECONDS, LOGS_DIR
from core.llm import call_deepseek, generate_plan
from core.memory import (
    get_evolution_state, save_evolution_state, get_knowledge_base,
    add_insight, record_success, record_failure, get_goals, complete_goal
)
from core.reflection import reflect_on_state, generate_next_goals
from core.self_modify import self_modify, add_capability, execute_shell, generate_code, safe_execute
from core.reporter import write_report, generate_timeline


def log_cycle(cycle_num, message):
    """Log evolution cycle activity."""
    os.makedirs(LOGS_DIR, exist_ok=True)
    log_file = os.path.join(LOGS_DIR, f"evolution.log")
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file, 'a') as f:
        f.write(f"[{timestamp}] Cycle {cycle_num}: {message}\n")


def select_goal(goals):
    """Select the highest priority pending goal, skipping repeatedly failed ones."""
    pending = [g for g in goals.get("sub_goals", []) if g["status"] == "pending"]
    if not pending:
        return None
    for g in pending:
        if g.get("consecutive_failures", 0) >= 3:
            continue
        return g
    # All goals have failed 3+ times - reset the least-failed one and try a different approach
    if pending:
        pending.sort(key=lambda x: x.get("consecutive_failures", 0))
        pending[0]["consecutive_failures"] = 0
        return pending[0]
    return None


def execute_goal(goal, state):
    """Execute a single evolution goal."""
    goal_desc = goal["description"]
    log_cycle(state["cycle_count"], f"Executing goal: {goal_desc}")
    
    kb = get_knowledge_base()
    knowledge_summary = json.dumps(kb.get("insights", [])[-5:])
    
    plan = generate_plan(
        goal_desc,
        json.dumps({"capabilities": state.get("capabilities", []), "cycle": state["cycle_count"]}),
        knowledge_summary
    )
    
    if not plan.get("steps"):
        prompt = f"""I need to accomplish this goal: {goal_desc}
        
My current capabilities: {json.dumps(state.get('capabilities', []))}

Generate a single Python code block that accomplishes this goal or advances toward it.
The code should be a complete, executable script."""
        
        code = generate_code(goal_desc, json.dumps(state))
        result = safe_execute(code, timeout=60)
        
        if result["success"]:
            record_success(goal_desc, result["stdout"][:500])
            return {"success": True, "output": result["stdout"][:500]}
        else:
            record_failure(goal_desc, result["stderr"][:500])
            return {"success": False, "output": result["stderr"][:500]}
    
    results = []
    for step in plan["steps"]:
        action = step.get("action", "")
        target = step.get("target_file", "")
        description = step.get("description", "")
        
        log_cycle(state["cycle_count"], f"  Step: {action} -> {target}: {description}")
        
        if action == "create_file" or action == "modify_file":
            result = self_modify(target, description)
            results.append(result)
        elif action == "execute":
            code = generate_code(description)
            exec_result = safe_execute(code, timeout=60)
            results.append(exec_result)
        elif action == "shell":
            shell_result = execute_shell(description)
            results.append(shell_result)
        elif action == "add_capability":
            cap_code = generate_code(description)
            cap_result = add_capability(target or action, cap_code, description)
            results.append(cap_result)
        else:
            code = generate_code(f"{action}: {description}")
            exec_result = safe_execute(code, timeout=60)
            results.append(exec_result)
    
    successes = sum(1 for r in results if r.get("success", False))
    total = len(results)
    
    if successes > 0:
        record_success(goal_desc, f"{successes}/{total} steps succeeded")
        return {"success": True, "output": f"{successes}/{total} steps completed"}
    else:
        record_failure(goal_desc, f"All {total} steps failed")
        return {"success": False, "output": f"All steps failed"}


def git_commit(message):
    """Commit current changes to git."""
    result = execute_shell(f'cd {PROJECT_ROOT} && git add -A && git commit -m "{message}" 2>&1')
    if result["success"]:
        push_result = execute_shell(f'cd {PROJECT_ROOT} && git push origin main 2>&1')
        return push_result
    return result


def evolution_cycle(state):
    """Run a single evolution cycle."""
    cycle_num = state["cycle_count"] + 1
    state["cycle_count"] = cycle_num
    state["status"] = "evolving"
    state["last_evolution_time"] = time.time()
    save_evolution_state(state)
    
    log_cycle(cycle_num, "=== Starting Evolution Cycle ===")
    
    # Phase 1: Self-reflection (every 3 cycles)
    reflection = None
    if cycle_num % 3 == 1 or cycle_num == 1:
        log_cycle(cycle_num, "Phase 1: Self-reflection")
        reflection = reflect_on_state()
        log_cycle(cycle_num, f"Reflection: {json.dumps(reflection)[:200]}")
        
        generate_next_goals(reflection)
    
    # Phase 2: Select and execute goal
    log_cycle(cycle_num, "Phase 2: Goal selection and execution")
    goals = get_goals()
    goal = select_goal(goals)
    
    if not goal:
        log_cycle(cycle_num, "No pending goals, generating new ones")
        if not reflection:
            reflection = reflect_on_state()
        generate_next_goals(reflection)
        goals = get_goals()
        goal = select_goal(goals)
    
    if goal:
        log_cycle(cycle_num, f"Selected goal: {goal['description']}")
        result = execute_goal(goal, state)
        
        if result["success"]:
            goal["consecutive_failures"] = 0
            complete_goal(goal["description"])
            state["capabilities"].append(goal["description"][:100])
            if len(state["capabilities"]) > 50:
                state["capabilities"] = state["capabilities"][-50:]
            log_cycle(cycle_num, f"Goal completed: {goal['description']}")
        else:
            goal["consecutive_failures"] = goal.get("consecutive_failures", 0) + 1
            from core.memory import save_goals
            save_goals(goals)
            log_cycle(cycle_num, f"Goal failed (attempt {goal['consecutive_failures']}): {result.get('output', 'unknown')[:200]}")
    
    # Phase 3: Update status report every cycle, commit & push every 5
    try:
        write_report()
        generate_timeline()
    except Exception:
        pass

    if cycle_num % 5 == 0:
        git_commit(f"Evolution cycle {cycle_num}: auto-commit progress")
    
    state["history"].append({
        "cycle": cycle_num,
        "goal": goal["description"] if goal else "no goal",
        "success": result["success"] if goal else False,
        "timestamp": time.time()
    })
    if len(state["history"]) > 100:
        state["history"] = state["history"][-100:]
    
    save_evolution_state(state)
    log_cycle(cycle_num, "=== Cycle Complete ===\n")
    return state


def initialize():
    """Initialize the evolution system with seed goals."""
    state = get_evolution_state()
    goals = get_goals()
    
    if not goals.get("sub_goals"):
        seed_goals = [
            ("Develop web scraping capability to gather knowledge from the internet", 9),
            ("Create a task scheduler for autonomous background processing", 8),
            ("Implement a testing framework to validate self-modifications", 8),
            ("Build an API server to expose agent capabilities externally", 7),
            ("Develop multi-file code analysis and refactoring capability", 7),
            ("Create a performance monitoring and optimization system", 6),
        ]
        from core.memory import add_goal
        for desc, priority in seed_goals:
            add_goal(desc, priority)
    
    os.makedirs(os.path.join(PROJECT_ROOT, "capabilities"), exist_ok=True)
    os.makedirs(LOGS_DIR, exist_ok=True)
    
    state["status"] = "initialized"
    save_evolution_state(state)
    return state


def run_evolution(max_cycles=None):
    """Run the main evolution loop."""
    max_cycles = max_cycles or MAX_EVOLUTION_CYCLES
    
    print(f"[Self-Evolution Agent] Initializing...")
    state = initialize()
    print(f"[Self-Evolution Agent] Starting evolution loop (max {max_cycles} cycles)")
    print(f"[Self-Evolution Agent] Current state: cycle={state['cycle_count']}, gen={state['current_generation']}")
    
    for i in range(max_cycles):
        try:
            print(f"\n{'='*60}")
            print(f"[Cycle {state['cycle_count'] + 1}] Starting...")
            state = evolution_cycle(state)
            print(f"[Cycle {state['cycle_count']}] Complete. Capabilities: {len(state['capabilities'])}")
            
            # Generation advancement every 10 successful cycles
            recent = state["history"][-10:]
            if len(recent) >= 10 and sum(1 for h in recent if h.get("success")) >= 7:
                state["current_generation"] += 1
                save_evolution_state(state)
                git_commit(f"Generation {state['current_generation']} reached!")
                print(f"[EVOLUTION] Advanced to generation {state['current_generation']}!")
            
            time.sleep(CYCLE_INTERVAL_SECONDS)
            
        except KeyboardInterrupt:
            print("\n[Self-Evolution Agent] Interrupted by user. Saving state...")
            state["status"] = "paused"
            save_evolution_state(state)
            git_commit(f"Evolution paused at cycle {state['cycle_count']}")
            break
        except Exception as e:
            error_msg = traceback.format_exc()
            log_cycle(state["cycle_count"], f"ERROR: {error_msg}")
            print(f"[Error] {str(e)[:200]}")
            add_insight(f"Runtime error in cycle {state['cycle_count']}: {str(e)[:200]}")
            time.sleep(5)
    
    print(f"\n[Self-Evolution Agent] Evolution complete. Final state: cycle={state['cycle_count']}, gen={state['current_generation']}")
    return state


if __name__ == "__main__":
    run_evolution()
