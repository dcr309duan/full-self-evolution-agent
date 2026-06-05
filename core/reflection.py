"""Self-reflection and goal generation module."""
import json
import time
from core.llm import call_deepseek, think_deep
from core.memory import (
    get_evolution_state, get_knowledge_base, get_goals,
    add_insight, add_goal, save_goals
)


def reflect_on_state():
    """Deep self-reflection on current capabilities and progress."""
    state = get_evolution_state()
    kb = get_knowledge_base()
    goals = get_goals()
    
    context = f"""You are a self-evolving AI agent reflecting on your current state.

Current Evolution State:
- Cycle count: {state['cycle_count']}
- Generation: {state['current_generation']}
- Capabilities: {json.dumps(state.get('capabilities', []))}
- Status: {state['status']}

Knowledge Base Summary:
- Insights accumulated: {len(kb.get('insights', []))}
- Successful strategies: {len(kb.get('successful_strategies', []))}
- Failed approaches: {len(kb.get('failed_approaches', []))}
- Last 3 insights: {json.dumps(kb.get('insights', [])[-3:])}

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
    
    try:
        start = response.find('{')
        end = response.rfind('}') + 1
        if start >= 0 and end > start:
            reflection = json.loads(response[start:end])
            add_insight(f"Self-reflection: {reflection.get('meta_insight', 'no meta insight')}")
            return reflection
    except (json.JSONDecodeError, ValueError):
        pass
    
    return {
        "current_assessment": "Unable to parse reflection",
        "key_gaps": [],
        "next_priority": "improve_reflection_capability",
        "novel_ideas": [],
        "meta_insight": response[:500]
    }


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
