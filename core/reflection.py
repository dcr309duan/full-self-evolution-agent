"""Self-reflection and goal generation module."""
import json
import os
import time
from core.llm import call_deepseek, think_deep
from core.memory import (
    get_evolution_state, get_knowledge_base, get_goals,
    add_insight, add_goal, save_goals
)
from config import MEMORY_DIR


def load_principles():
    """Load core evolution principles."""
    path = os.path.join(MEMORY_DIR, "principles.json")
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def detect_stuck_pattern(kb):
    """Detect if agent is stuck repeating the same failures."""
    failures = kb.get("failed_approaches", [])
    if len(failures) < 3:
        return None
    recent = failures[-5:]
    approaches = [f.get("approach", "")[:60] for f in recent]
    from collections import Counter
    counts = Counter(approaches)
    repeated = [(a, c) for a, c in counts.items() if c >= 3]
    if repeated:
        return repeated[0][0]
    return None


def reflect_on_state():
    """Deep self-reflection on current capabilities and progress."""
    state = get_evolution_state()
    kb = get_knowledge_base()
    goals = get_goals()
    principles = load_principles()
    stuck_on = detect_stuck_pattern(kb)
    
    context = f"""You are a self-evolving AI agent reflecting on your current state.

核心原则（必须遵循）:
{json.dumps(principles.get('core_principles', []), ensure_ascii=False, indent=2)}

进化哲学: {principles.get('evolution_philosophy', '')}

元指令: {json.dumps(principles.get('meta_directives', []), ensure_ascii=False, indent=2)}

Current Evolution State:
- Cycle count: {state['cycle_count']}
- Generation: {state['current_generation']}
- Capabilities: {json.dumps(state.get('capabilities', []))}
- Status: {state['status']}

Knowledge Base Summary:
- Insights accumulated: {len(kb.get('insights', []))}
- Successful strategies: {len(kb.get('successful_strategies', []))}
- Failed approaches: {len(kb.get('failed_approaches', []))}
- Last 3 insights: {json.dumps(kb.get('insights', [])[-3:], ensure_ascii=False)}
- Recent failures: {json.dumps([f.get('approach','')[:80] for f in kb.get('failed_approaches',[])[-5:]], ensure_ascii=False)}

{"!!! 警告: 检测到重复失败模式: " + stuck_on + " - 必须彻底改变策略 !!!" if stuck_on else ""}

Goals:
- Primary: {goals['primary_goal']}
- Sub-goals pending: {len([g for g in goals.get('sub_goals', []) if g['status'] == 'pending'])}
- Completed goals: {len(goals.get('completed_goals', []))}
"""
    
    prompt = """Perform deep self-reflection. Consider:
1. What have I learned so far?
2. What capabilities do I still lack?
3. What is the most impactful next step for my evolution?
4. Am I stuck in any local optima?
5. What novel approaches haven't I tried yet?

Output JSON with:
- "current_assessment": honest assessment of current state
- "key_gaps": list of missing capabilities
- "next_priority": most important thing to work on
- "novel_ideas": creative approaches to try
- "meta_insight": insight about the evolution process itself
"""
    
    response = think_deep(prompt, context)
    
    reflection = _parse_json_response(response)
    if reflection and reflection.get("current_assessment") != "Unable to parse reflection":
        add_insight(f"Self-reflection: {reflection.get('meta_insight', 'no meta insight')[:200]}")
        return reflection
    
    return {
        "current_assessment": response[:300] if response else "Empty response",
        "key_gaps": [],
        "next_priority": "continue_current_direction",
        "novel_ideas": [],
        "meta_insight": response[300:600] if response else ""
    }


def _parse_json_response(response):
    """Robustly extract JSON from LLM response."""
    if not response:
        return None
    
    # Strategy 1: simple find
    try:
        start = response.find('{')
        end = response.rfind('}') + 1
        if start >= 0 and end > start:
            return json.loads(response[start:end])
    except (json.JSONDecodeError, ValueError):
        pass
    
    # Strategy 2: bracket-counting to find first complete object
    try:
        start = response.find('{')
        if start >= 0:
            depth = 0
            for i in range(start, len(response)):
                if response[i] == '{':
                    depth += 1
                elif response[i] == '}':
                    depth -= 1
                    if depth == 0:
                        return json.loads(response[start:i+1])
    except (json.JSONDecodeError, ValueError):
        pass
    
    # Strategy 3: extract from code fence
    try:
        if '```json' in response:
            block = response.split('```json')[1].split('```')[0]
            return json.loads(block.strip())
        elif '```' in response:
            block = response.split('```')[1].split('```')[0]
            if block.strip().startswith('{'):
                return json.loads(block.strip())
    except (json.JSONDecodeError, ValueError, IndexError):
        pass
    
    return None


def generate_next_goals(reflection):
    """Generate new sub-goals based on reflection results."""
    current_goals = get_goals()
    pending = [g for g in current_goals.get("sub_goals", []) if g["status"] == "pending"]
    
    if len(pending) >= 5:
        return pending
    
    prompt = f"""Based on this self-reflection, generate new evolution goals:

Reflection: {json.dumps(reflection)}

Current pending goals: {json.dumps([g['description'] for g in pending])}

Generate 2-3 NEW concrete, actionable goals that will advance the agent's evolution.
Each goal should be specific enough to implement in one evolution cycle.

Output JSON array of objects with "description" and "priority" (1-10, 10 highest).
"""
    
    messages = [
        {"role": "system", "content": "You generate actionable evolution goals for a self-improving AI agent."},
        {"role": "user", "content": prompt}
    ]
    
    response = call_deepseek(messages, temperature=0.7)
    
    try:
        start = response.find('[')
        end = response.rfind(']') + 1
        if start >= 0 and end > start:
            new_goals = json.loads(response[start:end])
            for g in new_goals:
                add_goal(g["description"], g.get("priority", 5))
            return get_goals()["sub_goals"]
    except (json.JSONDecodeError, ValueError, KeyError):
        add_goal("Improve goal generation reliability", 8)
    
    return get_goals()["sub_goals"]
