import json
import os
import random
from typing import Dict, List, Optional, Tuple

# Path to store the current meta-cognition prompt and mutation history
PROMPT_STORE_PATH = "meta_cognition_prompt.json"
HISTORY_PATH = "mutation_history.json"

# Default meta-cognition prompt with configurable constraints
DEFAULT_PROMPT = (
    "You are a self-modifying reflection engine. "
    "Constraints: always list blind spots; focus on improving capability diversity; "
    "avoid overfitting to recent successes; maintain a balance between exploration and exploitation."
)

# Mutable prompt string
current_prompt: str = DEFAULT_PROMPT

# Mutation history: list of dicts with keys: prompt, metrics_before, metrics_after, accepted
mutation_history: List[Dict] = []

# Cycle counter for triggering mutations
cycle_counter: int = 0

# Metrics storage for last 10 cycles and current 10 cycles
metrics_last_10: List[Dict] = []  # list of dicts with 'failure_rate' and 'novelty_score'
metrics_current_10: List[Dict] = []

# Flag to indicate if a mutation is being tested
mutation_testing: bool = False
candidate_prompt: Optional[str] = None
candidate_metrics: List[Dict] = []


def load_prompt() -> str:
    """Load the current meta-cognition prompt from disk, or return default."""
    global current_prompt
    if os.path.exists(PROMPT_STORE_PATH):
        try:
            with open(PROMPT_STORE_PATH, "r") as f:
                data = json.load(f)
                current_prompt = data.get("prompt", DEFAULT_PROMPT)
        except (json.JSONDecodeError, IOError):
            current_prompt = DEFAULT_PROMPT
    else:
        current_prompt = DEFAULT_PROMPT
    return current_prompt


def save_prompt(prompt: str) -> None:
    """Save the current meta-cognition prompt to disk."""
    with open(PROMPT_STORE_PATH, "w") as f:
        json.dump({"prompt": prompt}, f)


def load_history() -> List[Dict]:
    """Load mutation history from disk."""
    global mutation_history
    if os.path.exists(HISTORY_PATH):
        try:
            with open(HISTORY_PATH, "r") as f:
                mutation_history = json.load(f)
        except (json.JSONDecodeError, IOError):
            mutation_history = []
    else:
        mutation_history = []
    return mutation_history


def save_history() -> None:
    """Save mutation history to disk."""
    with open(HISTORY_PATH, "w") as f:
        json.dump(mutation_history, f)


def get_current_prompt() -> str:
    """Return the current meta-cognition prompt."""
    global current_prompt
    return current_prompt


def set_prompt(new_prompt: str) -> None:
    """Set a new meta-cognition prompt (for rollback or manual override)."""
    global current_prompt
    current_prompt = new_prompt
    save_prompt(new_prompt)


def generate_candidate_mutation() -> str:
    """
    Generate a candidate mutation of the current prompt.
    Either inserts a new constraint or deletes an existing one.
    Returns the mutated prompt string.
    """
    global current_prompt
    constraints = extract_constraints(current_prompt)
    if not constraints:
        # No constraints to delete, so insert a new one
        new_constraint = random.choice([
            "focus on removing one capability per cycle",
            "prioritize capabilities with high novelty",
            "avoid repeating the same capability type",
            "emphasize failure analysis over success replication",
            "limit the number of active capabilities to 10"
        ])
        return current_prompt + f" {new_constraint};"
    
    if random.random() < 0.5 and len(constraints) > 1:
        # Delete an existing constraint
        constraint_to_remove = random.choice(constraints)
        new_prompt = current_prompt.replace(f"{constraint_to_remove};", "").strip()
        # Clean up any double spaces or trailing punctuation
        new_prompt = new_prompt.replace("; ;", ";").rstrip(";") + ";"
        return new_prompt
    else:
        # Insert a new constraint
        new_constraint = random.choice([
            "focus on removing one capability per cycle",
            "prioritize capabilities with high novelty",
            "avoid repeating the same capability type",
            "emphasize failure analysis over success replication",
            "limit the number of active capabilities to 10"
        ])
        return current_prompt + f" {new_constraint};"


def extract_constraints(prompt: str) -> List[str]:
    """
    Extract individual constraints from the prompt.
    Constraints are assumed to be separated by semicolons.
    """
    parts = prompt.split(";")
    constraints = []
    for part in parts:
        part = part.strip()
        if part and ("constraint" in part.lower() or "focus" in part.lower() or "prioritize" in part.lower() or "avoid" in part.lower() or "emphasize" in part.lower() or "limit" in part.lower()):
            constraints.append(part)
    return constraints


def record_cycle_metrics(failure_rate: float, novelty_score: float) -> None:
    """
    Record metrics for the current cycle.
    This should be called at the end of each cycle.
    """
    global cycle_counter, metrics_last_10, metrics_current_10, mutation_testing, candidate_metrics
    
    cycle_counter += 1
    metrics_entry = {"failure_rate": failure_rate, "novelty_score": novelty_score}
    
    if mutation_testing:
        candidate_metrics.append(metrics_entry)
        if len(candidate_metrics) >= 10:
            evaluate_mutation()
    else:
        metrics_current_10.append(metrics_entry)
        if len(metrics_current_10) > 10:
            metrics_current_10.pop(0)
        
        # Check if it's time to trigger a mutation
        if cycle_counter % 100 == 0 and cycle_counter > 0:
            trigger_mutation()


def trigger_mutation() -> None:
    """
    Trigger a mutation attempt.
    Saves the current metrics as baseline and starts testing a candidate.
    """
    global mutation_testing, candidate_prompt, candidate_metrics, metrics_last_10, metrics_current_10
    
    # Save current metrics as baseline
    metrics_last_10 = metrics_current_10.copy()
    
    # Generate candidate mutation
    candidate_prompt = generate_candidate_mutation()
    candidate_metrics = []
    mutation_testing = True
    
    # Temporarily switch to candidate prompt (but keep current for rollback)
    # Note: The actual prompt used during testing should be the candidate
    # We'll handle this in the main loop by checking mutation_testing flag


def evaluate_mutation() -> None:
    """
    Evaluate the candidate mutation after 10 cycles.
    Compare against the previous 10 cycles' metrics.
    Accept if improvement >10% in either metric.
    """
    global mutation_testing, candidate_prompt, candidate_metrics, metrics_last_10, current_prompt
    
    if not candidate_metrics or not metrics_last_10:
        # Not enough data, reject
        mutation_testing = False
        candidate_prompt = None
        candidate_metrics = []
        return
    
    # Calculate average metrics for candidate
    avg_candidate_failure = sum(m["failure_rate"] for m in candidate_metrics) / len(candidate_metrics)
    avg_candidate_novelty = sum(m["novelty_score"] for m in candidate_metrics) / len(candidate_metrics)
    
    # Calculate average metrics for baseline
    avg_baseline_failure = sum(m["failure_rate"] for m in metrics_last_10) / len(metrics_last_10)
    avg_baseline_novelty = sum(m["novelty_score"] for m in metrics_last_10) / len(metrics_last_10)
    
    # Calculate improvements (note: failure rate should decrease, so improvement is negative)
    failure_improvement = (avg_baseline_failure - avg_candidate_failure) / avg_baseline_failure if avg_baseline_failure > 0 else 0
    novelty_improvement = (avg_candidate_novelty - avg_baseline_novelty) / avg_baseline_novelty if avg_baseline_novelty > 0 else (avg_candidate_novelty if avg_candidate_novelty > 0 else 0)
    
    # Accept if improvement >10% in either metric
    accepted = failure_improvement > 0.1 or novelty_improvement > 0.1
    
    # Record mutation in history
    mutation_record = {
        "old_prompt": current_prompt,
        "new_prompt": candidate_prompt,
        "baseline_metrics": {"avg_failure_rate": avg_baseline_failure, "avg_novelty_score": avg_baseline_novelty},
        "candidate_metrics": {"avg_failure_rate": avg_candidate_failure, "avg_novelty_score": avg_candidate_novelty},
        "failure_improvement": failure_improvement,
        "novelty_improvement": novelty_improvement,
        "accepted": accepted
    }
    mutation_history.append(mutation_record)
    save_history()
    
    if accepted:
        # Accept mutation
        current_prompt = candidate_prompt
        save_prompt(current_prompt)
        # Reset metrics for new prompt
        metrics_current_10 = candidate_metrics.copy()
    else:
        # Reject mutation, keep old prompt
        # metrics_current_10 remains as before (baseline)
        pass
    
    # Reset mutation testing state
    mutation_testing = False
    candidate_prompt = None
    candidate_metrics = []


def rollback_to_previous_prompt() -> Optional[str]:
    """
    Rollback to the previous accepted prompt.
    Returns the prompt that was rolled back to, or None if no history.
    """
    global current_prompt, mutation_history, metrics_current_10
    
    if not mutation_history:
        return None
    
    # Find the last accepted mutation
    for i in range(len(mutation_history) - 1, -1, -1):
        if mutation_history[i]["accepted"]:
            old_prompt = mutation_history[i]["old_prompt"]
            # Rollback
            current_prompt = old_prompt
            save_prompt(current_prompt)
            # Remove this and all subsequent mutations from history
            mutation_history = mutation_history[:i]
            save_history()
            # Reset metrics
            metrics_current_10 = []
            return old_prompt
    
    return None


def get_mutation_stats() -> Dict:
    """Return statistics about mutations."""
    total = len(mutation_history)
    accepted = sum(1 for m in mutation_history if m["accepted"])
    return {
        "total_mutations": total,
        "accepted_mutations": accepted,
        "rejected_mutations": total - accepted,
        "acceptance_rate": accepted / total if total > 0 else 0.0,
        "current_prompt": current_prompt
    }


def reset() -> None:
    """Reset the module to default state."""
    global current_prompt, mutation_history, cycle_counter, metrics_last_10, metrics_current_10
    global mutation_testing, candidate_prompt, candidate_metrics
    
    current_prompt = DEFAULT_PROMPT
    save_prompt(current_prompt)
    mutation_history = []
    save_history()
    cycle_counter = 0
    metrics_last_10 = []
    metrics_current_10 = []
    mutation_testing = False
    candidate_prompt = None
    candidate_metrics = []


# Initialize on import
load_prompt()
load_history()