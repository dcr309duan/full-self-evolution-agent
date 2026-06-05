import sys
import json
from typing import List, Dict, Any

def decompose_goal(goal: str) -> Dict[str, Any]:
    """
    Decompose a goal description into a structured plan.
    
    Args:
        goal: A natural language goal description
        
    Returns:
        A dictionary containing the decomposition plan with:
        - 'goal': original goal
        - 'subgoals': list of subgoal descriptions
        - 'steps': list of actionable steps
        - 'dependencies': list of dependency relationships
    """
    # Simple decomposition logic - can be extended with NLP or rule-based approaches
    words = goal.lower().split()
    
    # Basic heuristic decomposition
    subgoals = []
    steps = []
    dependencies = []
    
    # Identify potential subgoals based on conjunctions or action verbs
    action_verbs = ['create', 'build', 'develop', 'implement', 'design', 'setup', 'configure', 'install', 'run', 'test', 'deploy']
    conjunctions = ['and', 'then', 'after', 'before', 'while']
    
    current_subgoal = []
    current_steps = []
    
    for word in words:
        if word in conjunctions and current_subgoal:
            # Complete current subgoal
            subgoal_text = ' '.join(current_subgoal)
            if subgoal_text:
                subgoals.append(subgoal_text)
                if current_steps:
                    steps.extend(current_steps)
                    current_steps = []
            current_subgoal = []
        elif word in action_verbs:
            current_subgoal.append(word)
            current_steps.append(word)
        else:
            current_subgoal.append(word)
    
    # Add remaining subgoal
    if current_subgoal:
        subgoal_text = ' '.join(current_subgoal)
        if subgoal_text:
            subgoals.append(subgoal_text)
            if current_steps:
                steps.extend(current_steps)
    
    # If no subgoals were identified, create a single subgoal
    if not subgoals:
        subgoals.append(goal)
        steps = words[:5]  # Take first 5 words as steps
    
    # Create dependency relationships (simple sequential)
    for i in range(len(subgoals) - 1):
        dependencies.append({
            'from': subgoals[i],
            'to': subgoals[i + 1],
            'type': 'sequential'
        })
    
    return {
        'goal': goal,
        'subgoals': subgoals,
        'steps': steps,
        'dependencies': dependencies,
        'metadata': {
            'decomposition_method': 'heuristic',
            'word_count': len(words)
        }
    }

def main():
    if len(sys.argv) < 2:
        print("Usage: python decompose_goal.py <goal_description>", file=sys.stderr)
        sys.exit(1)
    
    goal = ' '.join(sys.argv[1:])
    
    try:
        plan = decompose_goal(goal)
        print(json.dumps(plan, indent=2))
    except Exception as e:
        print(f"Error decomposing goal: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()