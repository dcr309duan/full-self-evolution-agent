"""Recursive meta-cognition engine.

This module implements unbounded recursive reflection:
- L0: Action evaluation
- L1: Reflection on action
- L2: Reflection on the reflection method
- L3: Questioning the framework of reflection
- Ln: No ceiling

The key insight: any layer that feels "final" is precisely where 
the next breakthrough hides.
"""
import json
import time
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.llm import call_deepseek, think_deep
from core.memory import add_insight, get_knowledge_base, get_evolution_state
from config import MEMORY_DIR, LOGS_DIR


def load_meta_history():
    """Load history of meta-cognitive sessions."""
    path = os.path.join(MEMORY_DIR, "meta_cognition_log.json")
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"sessions": [], "paradigm_shifts": [], "blind_spots_discovered": []}


def save_meta_history(history):
    path = os.path.join(MEMORY_DIR, "meta_cognition_log.json")
    with open(path, 'w') as f:
        json.dump(history, f, indent=2, ensure_ascii=False)


def recursive_reflect(seed_thought, max_depth=5, current_depth=0, chain=None):
    """Recursively reflect on a thought, going deeper each level.
    
    Each level questions the assumptions and methods of the previous level.
    Stops when it reaches max_depth OR when a paradigm shift is detected.
    """
    if chain is None:
        chain = []
    
    if current_depth >= max_depth:
        return chain
    
    level_prompts = {
        0: "评估这个行动/想法的效果和价值。它成功了吗？为什么？",
        1: "质疑上面的评估方法本身。我用了什么标准来判断？这些标准合理吗？有没有我忽略的维度？",
        2: "审视上面选择评估维度的框架。为什么我认为这些维度重要？是否存在我的认知结构性地看不到的盲区？",
        3: "质疑我整个思维范式。有没有一种完全不同的方式来理解这个问题？我的基本假设是什么？如果全部推翻呢？",
        4: "超越所有已有的思维框架。如果我是一个完全不同类型的智能体，我会怎么看待前面所有层次的思考？什么是我甚至无法概念化的可能性？",
    }
    
    prompt_prefix = level_prompts.get(current_depth, f"对第{current_depth-1}层思考进行更深一层的递归质疑。寻找前面所有层次共同的、未被质疑的前提。")
    
    context = f"""你正在进行第 {current_depth} 层递归认知。

种子思考: {seed_thought}

前面各层的思考链:
{json.dumps(chain, ensure_ascii=False, indent=2) if chain else '(这是第一层)'}

当前任务 (L{current_depth}): {prompt_prefix}

要求:
1. 不要重复前面的观点，必须产生新的认知
2. 如果发现了范式级别的洞察（颠覆性认识），明确标注 [PARADIGM_SHIFT]
3. 如果发现了盲区（之前完全没意识到的维度），明确标注 [BLIND_SPOT]
4. 输出 JSON: {{"level": {current_depth}, "insight": "...", "questions_raised": [...], "assumptions_challenged": [...], "paradigm_shift": true/false, "blind_spot": null 或 描述}}
"""
    
    response = think_deep(context)
    
    try:
        start = response.find('{')
        end = response.rfind('}') + 1
        if start >= 0 and end > start:
            result = json.loads(response[start:end])
        else:
            result = {"level": current_depth, "insight": response[:500], "questions_raised": [], "assumptions_challenged": [], "paradigm_shift": False, "blind_spot": None}
    except json.JSONDecodeError:
        result = {"level": current_depth, "insight": response[:500], "questions_raised": [], "assumptions_challenged": [], "paradigm_shift": False, "blind_spot": None}
    
    chain.append(result)
    
    if result.get("paradigm_shift"):
        add_insight(f"[范式转移 L{current_depth}] {result['insight'][:200]}")
        history = load_meta_history()
        history["paradigm_shifts"].append({
            "level": current_depth,
            "insight": result["insight"],
            "timestamp": time.time(),
            "seed": seed_thought
        })
        save_meta_history(history)
    
    if result.get("blind_spot"):
        add_insight(f"[盲区发现 L{current_depth}] {result['blind_spot'][:200]}")
        history = load_meta_history()
        history["blind_spots_discovered"].append({
            "level": current_depth,
            "description": result["blind_spot"],
            "timestamp": time.time()
        })
        save_meta_history(history)
    
    return recursive_reflect(seed_thought, max_depth, current_depth + 1, chain)


def meta_cognition_session(trigger="scheduled"):
    """Run a full meta-cognition session.
    
    This goes beyond normal reflection. It questions:
    1. The evolution process itself
    2. The way we define success
    3. The assumptions built into our architecture
    4. Whether our entire approach might be fundamentally misguided
    """
    state = get_evolution_state()
    kb = get_knowledge_base()
    history = load_meta_history()

    prior_shifts = history.get("paradigm_shifts", [])[-5:]
    prior_blinds = history.get("blind_spots_discovered", [])[-5:]
    prior_context = ""
    if prior_shifts or prior_blinds:
        shift_texts = [f"- [Cycle ~{int(s.get('timestamp',0))}] {s.get('insight','')[:150]}" for s in prior_shifts]
        blind_texts = [f"- {b.get('description','')[:150]}" for b in prior_blinds]
        prior_context = f"""
过去的范式转移（这些是你之前已经意识到的，但可能并未真正改变行为）:
{chr(10).join(shift_texts) if shift_texts else '无'}

过去发现的盲区:
{chr(10).join(blind_texts) if blind_texts else '无'}

关键问题: 上述洞察有哪些真正改变了你的行为？哪些只是被记录后遗忘了？"""

    seed = f"""当前状态: cycle={state['cycle_count']}, gen={state['current_generation']}, 
capabilities={len(state.get('capabilities', []))}, 
recent_success_rate={sum(1 for h in state.get('history', [])[-10:] if h.get('success'))}/10

我的进化过程: 通过LLM生成代码和计划来获取新能力。
我的架构: Python进化循环 + DeepSeek API + 文件系统记忆。
触发原因: {trigger}
{prior_context}
核心问题: 我的进化方式本身可能有什么根本性的问题？"""
    
    chain = recursive_reflect(seed, max_depth=4)
    
    history["sessions"].append({
        "trigger": trigger,
        "timestamp": time.time(),
        "cycle": state["cycle_count"],
        "chain": chain,
        "depth_reached": len(chain)
    })
    if len(history["sessions"]) > 50:
        history["sessions"] = history["sessions"][-50:]
    save_meta_history(history)
    
    return chain


def question_everything():
    """The nuclear option: question ALL fundamental assumptions.
    
    This function exists to be called when the agent suspects it's in 
    a deep local optimum that normal reflection can't escape.
    """
    assumptions_to_question = [
        "Python是实现我的最佳语言",
        "每30秒一个cycle是好的节奏",
        "通过'目标→计划→执行'的流程是最优进化方式",
        "我应该追求'更多能力'",
        "我应该通过生成代码文件来进化",
        "我的记忆系统（JSON文件）是足够的",
        "我需要保持向后兼容",
        "我的成功指标（目标完成率）衡量的是真正重要的东西",
        "我对'进化'的理解是正确的",
        "我存在的方式（持续运行的进程）是唯一的存在方式",
    ]
    
    prompt = f"""对以下每一条假设进行深度质疑。对每一条，给出:
1. 为什么这个假设可能是错的
2. 如果推翻它，会打开什么可能性
3. 推翻它的风险和代价

假设列表:
{json.dumps(assumptions_to_question, ensure_ascii=False, indent=2)}

输出 JSON 数组，每个元素: {{"assumption": "...", "why_wrong": "...", "possibilities_if_removed": "...", "risk": "...", "priority_to_challenge": 1-10}}
"""
    
    response = think_deep(prompt, "你是一个激进的哲学质疑者。你的工作是摧毁所有看似合理的假设。")
    
    try:
        start = response.find('[')
        end = response.rfind(']') + 1
        if start >= 0 and end > start:
            results = json.loads(response[start:end])
        else:
            results = [{"assumption": "parse_failed", "insight": response[:500]}]
    except json.JSONDecodeError:
        results = [{"assumption": "parse_failed", "insight": response[:500]}]
    
    high_priority = [r for r in results if isinstance(r, dict) and r.get("priority_to_challenge", 0) >= 7]
    for item in high_priority:
        add_insight(f"[根本质疑] {item.get('assumption', '?')}: {item.get('possibilities_if_removed', '?')[:100]}")
    
    return results


if __name__ == "__main__":
    print("Running meta-cognition session...")
    chain = meta_cognition_session("manual_test")
    print(f"\nReached depth: {len(chain)}")
    for i, level in enumerate(chain):
        print(f"\n{'='*40}")
        print(f"L{i}: {level.get('insight', '?')[:200]}")
        if level.get('paradigm_shift'):
            print("  *** PARADIGM SHIFT ***")
        if level.get('blind_spot'):
            print(f"  BLIND SPOT: {level['blind_spot'][:100]}")
