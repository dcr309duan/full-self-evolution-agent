import json
import os
from collections import defaultdict
from typing import Dict, List, Tuple, Set

# Default paths for log files
DEFAULT_EVOLUTION_LOG = "evolution_log.json"
DEFAULT_FAILURE_LOG = "failure_logs.json"

# Threshold for hotspot identification
HOTSPOT_THRESHOLD = 3


def load_json_log(filepath: str) -> List[dict]:
    """
    Load a JSON log file. Returns an empty list if file not found or invalid.
    """
    if not os.path.exists(filepath):
        print(f"Warning: {filepath} not found. Returning empty list.")
        return []
    try:
        with open(filepath, "r") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        else:
            print(f"Warning: {filepath} does not contain a JSON array. Returning empty list.")
            return []
    except (json.JSONDecodeError, IOError) as e:
        print(f"Error reading {filepath}: {e}. Returning empty list.")
        return []


def extract_module_pairs_from_event(event: dict) -> List[Tuple[str, str]]:
    """
    Extract module pairs (caller, callee) from a single rollback event.
    Looks for 'caller_module', 'callee_module', or 'import_chain' fields.
    Returns a list of (caller, callee) tuples.
    """
    pairs = []
    # Direct caller-callee fields
    caller = event.get("caller_module") or event.get("caller")
    callee = event.get("callee_module") or event.get("callee")
    if caller and callee:
        pairs.append((caller, callee))

    # Import chain (list of module names in order)
    import_chain = event.get("import_chain") or event.get("chain")
    if import_chain and isinstance(import_chain, list) and len(import_chain) >= 2:
        for i in range(len(import_chain) - 1):
            pairs.append((import_chain[i], import_chain[i + 1]))

    # Nested 'details' or 'context' field
    details = event.get("details") or event.get("context") or {}
    if isinstance(details, dict):
        caller2 = details.get("caller_module") or details.get("caller")
        callee2 = details.get("callee_module") or details.get("callee")
        if caller2 and callee2:
            pairs.append((caller2, callee2))
        chain2 = details.get("import_chain") or details.get("chain")
        if chain2 and isinstance(chain2, list) and len(chain2) >= 2:
            for i in range(len(chain2) - 1):
                pairs.append((chain2[i], chain2[i + 1]))

    return pairs


def extract_module_pairs_from_failure(failure: dict) -> List[Tuple[str, str]]:
    """
    Extract module pairs from a failure log entry.
    Similar structure to rollback events but may have 'failure_type' or 'error'.
    """
    pairs = []
    # Direct fields
    caller = failure.get("caller_module") or failure.get("caller")
    callee = failure.get("callee_module") or failure.get("callee")
    if caller and callee:
        pairs.append((caller, callee))

    # Import chain
    import_chain = failure.get("import_chain") or failure.get("chain")
    if import_chain and isinstance(import_chain, list) and len(import_chain) >= 2:
        for i in range(len(import_chain) - 1):
            pairs.append((import_chain[i], import_chain[i + 1]))

    # Error context
    error = failure.get("error") or failure.get("context") or {}
    if isinstance(error, dict):
        caller2 = error.get("caller_module") or error.get("caller")
        callee2 = error.get("callee_module") or error.get("callee")
        if caller2 and callee2:
            pairs.append((caller2, callee2))
        chain2 = error.get("import_chain") or error.get("chain")
        if chain2 and isinstance(chain2, list) and len(chain2) >= 2:
            for i in range(len(chain2) - 1):
                pairs.append((chain2[i], chain2[i + 1]))

    return pairs


def count_module_pair_frequencies(
    events: List[dict], failures: List[dict]
) -> Dict[Tuple[str, str], int]:
    """
    Count frequency of each module pair across all events and failures.
    Returns a dict mapping (caller, callee) -> count.
    """
    pair_counter: Dict[Tuple[str, str], int] = defaultdict(int)

    for event in events:
        pairs = extract_module_pairs_from_event(event)
        for pair in pairs:
            pair_counter[pair] += 1

    for failure in failures:
        pairs = extract_module_pairs_from_failure(failure)
        for pair in pairs:
            pair_counter[pair] += 1

    return dict(pair_counter)


def get_last_n_events(events: List[dict], n: int = 50) -> List[dict]:
    """
    Return the last n events (most recent first if timestamp available, else last in list).
    """
    # Try to sort by timestamp if available
    sorted_events = sorted(
        events,
        key=lambda e: e.get("timestamp", ""),
        reverse=True,
    )
    return sorted_events[:n]


def get_last_n_failures(failures: List[dict], n: int = 50) -> List[dict]:
    """
    Return the last n failures (most recent first if timestamp available, else last in list).
    """
    sorted_failures = sorted(
        failures,
        key=lambda f: f.get("timestamp", ""),
        reverse=True,
    )
    return sorted_failures[:n]


def identify_hotspots(
    pair_frequencies: Dict[Tuple[str, str], int], threshold: int = HOTSPOT_THRESHOLD
) -> List[Tuple[str, str, int]]:
    """
    Identify module pairs that appear more than 'threshold' times.
    Returns list of (caller, callee, count) sorted by count descending.
    """
    hotspots = [
        (caller, callee, count)
        for (caller, callee), count in pair_frequencies.items()
        if count > threshold
    ]
    hotspots.sort(key=lambda x: x[2], reverse=True)
    return hotspots


def generate_refactoring_goal(hotspots: List[Tuple[str, str, int]]) -> str:
    """
    Auto-generate a refactoring goal targeting the identified integration points.
    """
    if not hotspots:
        return "No fragile integration points detected. System is stable."

    lines = ["Refactoring Goal: Strengthen Integration Points", ""]
    lines.append(
        "The following module pairs have been identified as fragile integration points "
        "due to repeated failures or rollbacks. Refactor the interfaces between these "
        "modules to improve stability and reduce coupling."
    )
    lines.append("")
    lines.append("Target Integration Points (caller -> callee, failure count):")
    for caller, callee, count in hotspots:
        lines.append(f"  - {caller} -> {callee} ({count} failures)")
    lines.append("")
    lines.append("Suggested Actions:")
    lines.append(
        "1. Introduce a stable API or interface between each pair to decouple implementations."
    )
    lines.append(
        "2. Add defensive checks and error handling at the boundary between modules."
    )
    lines.append(
        "3. Consider merging or refactoring the modules if they are tightly coupled."
    )
    lines.append(
        "4. Add integration tests specifically for these module interactions."
    )
    return "\n".join(lines)


def mine_fragility_hotspots(
    evolution_log_path: str = DEFAULT_EVOLUTION_LOG,
    failure_log_path: str = DEFAULT_FAILURE_LOG,
    num_events: int = 50,
    threshold: int = HOTSPOT_THRESHOLD,
) -> Dict:
    """
    Main function: parse logs, extract pairs, count frequencies, identify hotspots,
    and generate a refactoring goal.
    Returns a dictionary with results.
    """
    # Load logs
    all_events = load_json_log(evolution_log_path)
    all_failures = load_json_log(failure_log_path)

    # Get last N events/failures
    recent_events = get_last_n_events(all_events, num_events)
    recent_failures = get_last_n_failures(all_failures, num_events)

    # Count pair frequencies
    pair_frequencies = count_module_pair_frequencies(recent_events, recent_failures)

    # Identify hotspots
    hotspots = identify_hotspots(pair_frequencies, threshold)

    # Generate refactoring goal
    refactoring_goal = generate_refactoring_goal(hotspots)

    return {
        "total_events_parsed": len(recent_events),
        "total_failures_parsed": len(recent_failures),
        "unique_module_pairs": len(pair_frequencies),
        "hotspot_pairs": hotspots,
        "refactoring_goal": refactoring_goal,
    }


# If run as script, execute mining and print results
if __name__ == "__main__":
    result = mine_fragility_hotspots()
    print("=== Fragility Hotspot Mining Results ===")
    print(f"Events parsed: {result['total_events_parsed']}")
    print(f"Failures parsed: {result['total_failures_parsed']}")
    print(f"Unique module pairs: {result['unique_module_pairs']}")
    print(f"Hotspot pairs (>{HOTSPOT_THRESHOLD} occurrences):")
    for caller, callee, count in result["hotspot_pairs"]:
        print(f"  {caller} -> {callee}: {count}")
    print("\n" + result["refactoring_goal"])