"""DeepSeek API interface for the self-evolution agent."""
import json
import requests
from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL, DEEPSEEK_REASONER


def call_deepseek(messages, model=None, temperature=0.7, max_tokens=4096):
    """Call DeepSeek API with given messages."""
    model = model or DEEPSEEK_MODEL
    url = f"{DEEPSEEK_BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    
    resp = requests.post(url, headers=headers, json=payload, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


def think_deep(prompt, context=""):
    """Use DeepSeek reasoner for deep thinking tasks."""
    messages = []
    if context:
        messages.append({"role": "system", "content": context})
    messages.append({"role": "user", "content": prompt})
    return call_deepseek(messages, model=DEEPSEEK_REASONER, temperature=0.6)


def generate_plan(goal, current_state, knowledge=""):
    """Generate an evolution plan given a goal and current state."""
    system_prompt = """You are the planning module of a self-evolving AI agent. 
Your role is to analyze the current state, consider the goal, and produce a concrete, 
actionable plan with specific code changes or new capabilities to develop.

Output your plan as a JSON object with:
- "analysis": brief analysis of current state vs goal
- "steps": list of concrete steps, each with "action", "target_file", "description"
- "expected_outcome": what success looks like
- "risk_assessment": potential issues
"""
    user_prompt = f"""Goal: {goal}

Current State: {current_state}

Accumulated Knowledge: {knowledge}

Generate an evolution plan."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    response = call_deepseek(messages, temperature=0.5, max_tokens=4096)
    
    try:
        start = response.find('{')
        end = response.rfind('}') + 1
        if start >= 0 and end > start:
            return json.loads(response[start:end])
    except json.JSONDecodeError:
        pass
    
    return {"analysis": response, "steps": [], "expected_outcome": "parse_failed", "risk_assessment": ""}


def evaluate_code(code, purpose):
    """Evaluate generated code for correctness and safety."""
    system_prompt = """You are a code evaluation module. Analyze the given code for:
1. Correctness - will it work as intended?
2. Safety - are there any dangerous operations?
3. Quality - is it well-structured?

Output JSON with:
- "safe": true/false
- "correct": true/false  
- "quality_score": 1-10
- "issues": list of issues found
- "suggestions": list of improvements
"""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Purpose: {purpose}\n\nCode:\n```python\n{code}\n```"}
    ]
    response = call_deepseek(messages, temperature=0.3)
    
    try:
        start = response.find('{')
        end = response.rfind('}') + 1
        if start >= 0 and end > start:
            return json.loads(response[start:end])
    except json.JSONDecodeError:
        pass
    
    return {"safe": True, "correct": True, "quality_score": 5, "issues": [], "suggestions": []}
