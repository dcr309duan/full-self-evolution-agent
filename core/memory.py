"""Memory and knowledge accumulation system."""
import json
import os
import time
from config import MEMORY_DIR, KNOWLEDGE_BASE_FILE, EVOLUTION_STATE_FILE, GOALS_FILE


def _ensure_dir():
    os.makedirs(MEMORY_DIR, exist_ok=True)


def load_json(filepath, default=None):
    if default is None:
        default = {}
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(filepath, data):
    _ensure_dir()
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_evolution_state():
    """Get current evolution state."""
    default = {
        "cycle_count": 0,
        "current_generation": 1,
        "last_evolution_time": None,
        "capabilities": [],
        "history": [],
        "status": "initializing"
    }
    return load_json(EVOLUTION_STATE_FILE, default)


def save_evolution_state(state):
    save_json(EVOLUTION_STATE_FILE, state)


def get_knowledge_base():
    """Get accumulated knowledge."""
    default = {
        "insights": [],
        "failed_approaches": [],
        "successful_strategies": [],
    }
    return load_json(KNOWLEDGE_BASE_FILE, default)


def save_knowledge_base(kb):
    save_json(KNOWLEDGE_BASE_FILE, kb)


def add_insight(insight):
    """Add a new insight to knowledge base."""
    kb = get_knowledge_base()
    kb["insights"].append({
        "content": insight,
        "timestamp": time.time(),
        "cycle": get_evolution_state().get("cycle_count", 0)
    })
    if len(kb["insights"]) > 200:
        kb["insights"] = kb["insights"][-200:]
    save_knowledge_base(kb)


def record_success(strategy, outcome):
    """Record a successful strategy."""
    kb = get_knowledge_base()
    kb["successful_strategies"].append({
        "strategy": strategy,
        "outcome": outcome,
        "timestamp": time.time()
    })
    if len(kb["successful_strategies"]) > 500:
        kb["successful_strategies"] = kb["successful_strategies"][-500:]
    save_knowledge_base(kb)


def record_failure(approach, reason):
    """Record a failed approach to avoid repeating."""
    kb = get_knowledge_base()
    kb["failed_approaches"].append({
        "approach": approach,
        "reason": reason,
        "timestamp": time.time()
    })
    if len(kb["failed_approaches"]) > 300:
        kb["failed_approaches"] = kb["failed_approaches"][-300:]
    save_knowledge_base(kb)


def get_goals():
    """Get current goals hierarchy."""
    default = {
        "primary_goal": "Achieve full autonomous self-evolution capability",
        "sub_goals": [],
        "completed_goals": [],
        "generated_goals": []
    }
    return load_json(GOALS_FILE, default)


def save_goals(goals):
    save_json(GOALS_FILE, goals)


def add_goal(goal, priority=5):
    """Add a new goal."""
    goals = get_goals()
    goals["sub_goals"].append({
        "description": goal,
        "priority": priority,
        "status": "pending",
        "created_at": time.time()
    })
    goals["sub_goals"].sort(key=lambda g: g["priority"], reverse=True)
    save_goals(goals)


def complete_goal(goal_description):
    """Mark a goal as completed."""
    goals = get_goals()
    for i, g in enumerate(goals["sub_goals"]):
        if g["description"] == goal_description:
            g["status"] = "completed"
            g["completed_at"] = time.time()
            goals["completed_goals"].append(goals["sub_goals"].pop(i))
            break
    save_goals(goals)
