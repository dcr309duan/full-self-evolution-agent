"""Goal constraints derived from meta-cognition paradigm shifts.

This module closes the gap between insight and action. When meta-cognition
produces a paradigm shift, it writes a binding constraint here. The goal
selector MUST satisfy active constraints or reject the goal.

Constraints expire after 20 cycles to prevent permanent rigidity.
"""
import json
import os
import time

from config import MEMORY_DIR

CONSTRAINTS_FILE = os.path.join(MEMORY_DIR, "goal_constraints.json")
CONSTRAINT_EXPIRY_CYCLES = 20


def load_constraints():
    try:
        with open(CONSTRAINTS_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"constraints": []}


def save_constraints(data):
    with open(CONSTRAINTS_FILE, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def add_constraint(rule: str, source_insight: str, cycle: int):
    """Add a binding constraint derived from a paradigm shift.
    
    Args:
        rule: A keyword or pattern that must/must-not appear in goals.
              Format: "REQUIRE:<keyword>" or "BLOCK:<keyword>"
              Examples:
                "REQUIRE:验证" - goal must involve verification
                "REQUIRE:import" - goal must mention import/testing
                "BLOCK:创建新模块" - goal must NOT just create new modules
                "REQUIRE:运行" - goal must involve actual execution
        source_insight: The paradigm shift text that generated this constraint
        cycle: The cycle number when constraint was created
    """
    data = load_constraints()
    data["constraints"].append({
        "rule": rule,
        "source": source_insight[:200],
        "created_cycle": cycle,
        "expires_cycle": cycle + CONSTRAINT_EXPIRY_CYCLES,
    })
    save_constraints(data)


def get_active_constraints(current_cycle: int):
    """Return all non-expired constraints."""
    data = load_constraints()
    active = [c for c in data["constraints"] if c["expires_cycle"] > current_cycle]
    if len(active) != len(data["constraints"]):
        data["constraints"] = active
        save_constraints(data)
    return active


def check_goal_against_constraints(goal_desc: str, current_cycle: int) -> tuple:
    """Check if a goal satisfies all active constraints.
    
    Returns:
        (passes: bool, reason: str)
    """
    active = get_active_constraints(current_cycle)
    if not active:
        return True, ""
    
    goal_lower = goal_desc.lower()
    
    for c in active:
        rule = c["rule"]
        if rule.startswith("REQUIRE:"):
            keywords = rule[8:].lower().split(",")
            if not any(kw.strip() in goal_lower for kw in keywords):
                return False, f"Constraint violated: goal must involve one of [{rule[8:]}] (from: {c['source'][:80]})"
        elif rule.startswith("BLOCK:"):
            keywords = rule[6:].lower().split(",")
            if any(kw.strip() in goal_lower for kw in keywords):
                matched = [kw.strip() for kw in keywords if kw.strip() in goal_lower]
                return False, f"Constraint violated: goal must NOT involve '{matched[0]}' (from: {c['source'][:80]})"
    
    return True, ""


def derive_constraints_from_shift(insight: str, cycle: int):
    """Automatically derive constraints from paradigm shift text.
    
    This is the key function: it reads a paradigm shift and generates
    concrete, binding rules that change what goals are allowed.
    """
    insight_lower = insight.lower()
    
    if any(k in insight_lower for k in ["成功率", "虚假", "虚幻", "太简单", "局部最优"]):
        add_constraint("REQUIRE:验证,verify,test,validate,run,执行,import", insight[:100], cycle)
    
    if any(k in insight_lower for k in ["重复", "又是", "同一模式", "局部最优陷阱"]):
        add_constraint("BLOCK:create a new,创建新,build a new", insight[:100], cycle)
    
    if any(k in insight_lower for k in ["外包", "llm驱动", "智能外包", "工具代理"]):
        add_constraint("REQUIRE:执行,run,execute,验证,test,import,实际运行", insight[:100], cycle)
    
    if any(k in insight_lower for k in ["从未验证", "从未运行", "未经验证"]):
        add_constraint("REQUIRE:test,verify,run,import,验证,运行", insight[:100], cycle)
    
    if any(k in insight_lower for k in ["基础设施膨胀", "复杂度", "能力膨胀"]):
        add_constraint("BLOCK:dashboard,monitor,health,仪表板,监控", insight[:100], cycle)
