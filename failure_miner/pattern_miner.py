"""Core failure pattern miner module.

Aggregates failure logs from the knowledge base and task scheduler history,
extracts error patterns using NLP heuristics, computes statistics, maps patterns
to architectural components, and generates structured refactoring goals.
"""

import re
import json
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Pattern definitions and heuristics
# ---------------------------------------------------------------------------

# Known error pattern categories and their keyword signatures
ERROR_PATTERNS = {
    "schema_alignment": [
        r"schema.*mismatch",
        r"column.*not found",
        r"type.*conflict",
        r"incompatible.*type",
        r"field.*missing",
        r"schema.*validation.*fail",
        r"data.*type.*error",
    ],
    "import_error": [
        r"import.*error",
        r"module.*not found",
        r"cannot.*import",
        r"no module named",
        r"import.*fail",
        r"unresolved.*import",
    ],
    "type_mismatch": [
        r"type.*mismatch",
        r"expected.*got",
        r"cannot.*convert",
        r"incompatible.*type",
        r"type.*error",
        r"attribute.*type",
    ],
    "dependency_failure": [
        r"dependency.*not.*satisfied",
        r"missing.*dependency",
        r"version.*conflict",
        r"circular.*dependency",
        r"dependency.*error",
    ],
    "timeout": [
        r"timeout",
        r"timed out",
        r"deadline.*exceeded",
        r"time.*limit.*exceeded",
    ],
    "resource_exhaustion": [
        r"out of memory",
        r"memory.*error",
        r"disk.*full",
        r"resource.*exhausted",
        r"too many.*open",
    ],
    "network_error": [
        r"connection.*refused",
        r"network.*unreachable",
        r"dns.*resolution",
        r"connection.*timeout",
        r"broken.*pipe",
    ],
    "permission_denied": [
        r"permission.*denied",
        r"access.*denied",
        r"unauthorized",
        r"forbidden",
        r"not.*allowed",
    ],
}

# Mapping from error pattern to likely architectural component
PATTERN_TO_COMPONENT = {
    "schema_alignment": "data_layer",
    "import_error": "module_loader",
    "type_mismatch": "type_checker",
    "dependency_failure": "dependency_manager",
    "timeout": "scheduler",
    "resource_exhaustion": "resource_manager",
    "network_error": "network_layer",
    "permission_denied": "security_layer",
}


def _classify_failure(error_message: str) -> Optional[str]:
    """Classify a single error message into a pattern category using regex heuristics."""
    if not error_message:
        return None
    msg_lower = error_message.lower()
    for pattern_name, regex_list in ERROR_PATTERNS.items():
        for regex in regex_list:
            if re.search(regex, msg_lower):
                return pattern_name
    return None


def aggregate_failures(
    knowledge_base: Optional[List[Dict[str, Any]]] = None,
    task_history: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Collect all failure logs from the knowledge base and task scheduler history.

    Args:
        knowledge_base: List of failure records from the knowledge base.
                        Each record should have at least 'error_message' and optionally
                        'timestamp', 'component', 'task_id'.
        task_history: List of task records from the scheduler history.
                      Each record should have at least 'error_message' and optionally
                      'timestamp', 'task_type', 'status'.

    Returns:
        A unified list of failure log dictionaries with keys:
            'error_message', 'timestamp', 'source', 'task_id', 'component'.
    """
    failures: List[Dict[str, Any]] = []

    # Collect from knowledge base
    if knowledge_base:
        for record in knowledge_base:
            if "error_message" in record and record["error_message"]:
                failures.append(
                    {
                        "error_message": record["error_message"],
                        "timestamp": record.get("timestamp", None),
                        "source": "knowledge_base",
                        "task_id": record.get("task_id", None),
                        "component": record.get("component", None),
                    }
                )

    # Collect from task scheduler history
    if task_history:
        for record in task_history:
            if "error_message" in record and record["error_message"]:
                failures.append(
                    {
                        "error_message": record["error_message"],
                        "timestamp": record.get("timestamp", None),
                        "source": "task_scheduler",
                        "task_id": record.get("task_id", None),
                        "component": record.get("component", None),
                    }
                )

    return failures


def extract_patterns(
    failures: List[Dict[str, Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    """Cluster failures by error type using NLP heuristics.

    Args:
        failures: List of failure log dictionaries (as returned by aggregate_failures).

    Returns:
        Dictionary mapping pattern names to lists of failure records that match.
        Unclassified failures are stored under the key 'unclassified'.
    """
    clustered: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    for failure in failures:
        msg = failure.get("error_message", "")
        pattern = _classify_failure(msg)
        if pattern:
            clustered[pattern].append(failure)
        else:
            clustered["unclassified"].append(failure)

    return dict(clustered)


def compute_statistics(
    clustered: Dict[str, List[Dict[str, Any]]],
) -> Dict[str, Any]:
    """Calculate frequency percentages per pattern.

    Args:
        clustered: Dictionary mapping pattern names to lists of failure records.

    Returns:
        Dictionary with keys:
            'total_failures': int,
            'pattern_counts': dict mapping pattern name to count,
            'pattern_percentages': dict mapping pattern name to float percentage,
            'unclassified_count': int,
            'unclassified_percentage': float.
    """
    total = sum(len(fails) for fails in clustered.values())
    if total == 0:
        return {
            "total_failures": 0,
            "pattern_counts": {},
            "pattern_percentages": {},
            "unclassified_count": 0,
            "unclassified_percentage": 0.0,
        }

    pattern_counts: Dict[str, int] = {}
    unclassified_count = 0

    for pattern, fails in clustered.items():
        count = len(fails)
        if pattern == "unclassified":
            unclassified_count = count
        else:
            pattern_counts[pattern] = count

    pattern_percentages = {
        pattern: round((count / total) * 100, 2)
        for pattern, count in pattern_counts.items()
    }
    unclassified_percentage = round((unclassified_count / total) * 100, 2)

    return {
        "total_failures": total,
        "pattern_counts": pattern_counts,
        "pattern_percentages": pattern_percentages,
        "unclassified_count": unclassified_count,
        "unclassified_percentage": unclassified_percentage,
    }


def identify_bottlenecks(
    clustered: Dict[str, List[Dict[str, Any]]],
    self_model: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Map failure patterns to architectural components using the self-model.

    Args:
        clustered: Dictionary mapping pattern names to lists of failure records.
        self_model: Optional dictionary representing the system's architectural model.
                    If provided, it can contain component definitions and relationships.
                    If None, a default mapping based on PATTERN_TO_COMPONENT is used.

    Returns:
        Dictionary with keys:
            'component_patterns': dict mapping component names to list of pattern names,
            'component_failure_counts': dict mapping component names to total failure count,
            'bottleneck_scores': dict mapping component names to a score (0-1) representing
                                 the proportion of total failures attributed to that component.
    """
    # Build pattern-to-component mapping
    if self_model and "components" in self_model:
        # Use self-model to map patterns to components
        pattern_to_component = {}
        for comp_name, comp_def in self_model["components"].items():
            if "error_patterns" in comp_def:
                for pat in comp_def["error_patterns"]:
                    pattern_to_component[pat] = comp_name
    else:
        pattern_to_component = PATTERN_TO_COMPONENT.copy()

    # Count failures per component
    component_failures: Dict[str, int] = defaultdict(int)
    component_patterns: Dict[str, List[str]] = defaultdict(list)

    for pattern, fails in clustered.items():
        if pattern == "unclassified":
            continue
        component = pattern_to_component.get(pattern, "unknown")
        component_failures[component] += len(fails)
        if pattern not in component_patterns[component]:
            component_patterns[component].append(pattern)

    total_failures = sum(component_failures.values())
    if total_failures == 0:
        bottleneck_scores = {comp: 0.0 for comp in component_failures}
    else:
        bottleneck_scores = {
            comp: round(count / total_failures, 4)
            for comp, count in component_failures.items()
        }

    return {
        "component_patterns": dict(component_patterns),
        "component_failure_counts": dict(component_failures),
        "bottleneck_scores": bottleneck_scores,
    }


def generate_refactoring_goals(
    statistics: Dict[str, Any],
    bottlenecks: Dict[str, Any],
    clustered: Dict[str, List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    """Produce structured goals targeting root causes of failures.

    Args:
        statistics: Output from compute_statistics().
        bottlenecks: Output from identify_bottlenecks().
        clustered: Output from extract_patterns().

    Returns:
        List of goal dictionaries with keys:
            'pattern': str,
            'component': str,
            'frequency_percentage': float,
            'goal_description': str,
            'priority': str ('high', 'medium', 'low').
    """
    goals: List[Dict[str, Any]] = []
    pattern_percentages = statistics.get("pattern_percentages", {})
    component_patterns = bottlenecks.get("component_patterns", {})
    bottleneck_scores = bottlenecks.get("bottleneck_scores", {})

    # Define refactoring templates for each pattern
    refactoring_templates = {
        "schema_alignment": "Implement canonical schema validation layer to reduce schema_alignment failures",
        "import_error": "Standardize module import paths and add import validation to reduce import_error failures",
        "type_mismatch": "Introduce strict type checking and type coercion utilities to reduce type_mismatch failures",
        "dependency_failure": "Implement dependency resolution and version locking to reduce dependency_failure failures",
        "timeout": "Optimize task execution time and add timeout handling to reduce timeout failures",
        "resource_exhaustion": "Add resource monitoring and limits to reduce resource_exhaustion failures",
        "network_error": "Implement retry logic and circuit breakers to reduce network_error failures",
        "permission_denied": "Review and simplify permission model to reduce permission_denied failures",
    }

    for pattern, percentage in pattern_percentages.items():
        # Determine component
        component = None
        for comp, pats in component_patterns.items():
            if pattern in pats:
                component = comp
                break
        if not component:
            component = "unknown"

        # Determine priority based on percentage
        if percentage >= 20:
            priority = "high"
        elif percentage >= 10:
            priority = "medium"
        else:
            priority = "low"

        # Generate goal description
        template = refactoring_templates.get(pattern, f"Investigate and resolve {pattern} failures")
        goal_description = template

        goals.append(
            {
                "pattern": pattern,
                "component": component,
                "frequency_percentage": percentage,
                "goal_description": goal_description,
                "priority": priority,
            }
        )

    # Sort by frequency descending
    goals.sort(key=lambda g: g["frequency_percentage"], reverse=True)

    return goals


def analyze_failure_trends(
    clustered: Dict[str, List[Dict[str, Any]]],
    num_cycles: int = 10,
) -> Dict[str, Any]:
    """Track how pattern frequencies change over time (last N cycles) to identify emerging bottlenecks.

    Args:
        clustered: Dictionary mapping pattern names to lists of failure records.
                   Each failure record should have a 'timestamp' key for cycle identification.
        num_cycles: Number of recent cycles to analyze (default 10).

    Returns:
        Dictionary with keys:
            'top_patterns': list of dicts with 'pattern', 'frequency', 'trend_direction', 'refactoring_priority'
            'cycle_data': dict mapping cycle index to pattern frequencies
    """
    # Extract timestamps and sort failures by time
    all_failures = []
    for pattern, fails in clustered.items():
        for fail in fails:
            all_failures.append((fail.get("timestamp", 0), pattern, fail))
    
    # Sort by timestamp
    all_failures.sort(key=lambda x: x[0] if x[0] is not None else 0)
    
    if not all_failures:
        return {"top_patterns": [], "cycle_data": {}}
    
    # Determine cycle boundaries based on timestamps
    timestamps = [f[0] for f in all_failures if f[0] is not None]
    if not timestamps:
        return {"top_patterns": [], "cycle_data": {}}
    
    min_time = min(timestamps)
    max_time = max(timestamps)
    
    # If all timestamps are the same, treat as single cycle
    if min_time == max_time:
        cycle_duration = 1
    else:
        cycle_duration = (max_time - min_time) / num_cycles
    
    # Group failures into cycles
    cycle_pattern_counts = [defaultdict(int) for _ in range(num_cycles)]
    for timestamp, pattern, _ in all_failures:
        if timestamp is None:
            continue
        cycle_index = min(num_cycles - 1, int((timestamp - min_time) / cycle_duration)) if cycle_duration > 0 else 0
        if pattern != "unclassified":
            cycle_pattern_counts[cycle_index][pattern] += 1
    
    # Calculate frequencies per cycle
    cycle_data = {}
    for i, counts in enumerate(cycle_pattern_counts):
        total = sum(counts.values())
        if total > 0:
            cycle_data[i] = {pattern: round((count / total) * 100, 2) for pattern, count in counts.items()}
        else:
            cycle_data[i] = {}
    
    # Get overall frequencies from last cycle
    last_cycle = cycle_data.get(num_cycles - 1, {})
    if not last_cycle:
        # Fall back to all cycles
        all_counts = defaultdict(int)
        for counts in cycle_pattern_counts:
            for pattern, count in counts.items():
                all_counts[pattern] += count
        total_all = sum(all_counts.values())
        if total_all > 0:
            last_cycle = {p: round((c / total_all) * 100, 2) for p, c in all_counts.items()}
    
    # Sort patterns by frequency in last cycle
    sorted_patterns = sorted(last_cycle.items(), key=lambda x: x[1], reverse=True)
    top_patterns = sorted_patterns[:3]
    
    # Determine trend direction and refactoring priority
    result_top = []
    for pattern, freq in top_patterns:
        # Calculate trend: compare first half vs second half of cycles
        mid_point = num_cycles // 2
        first_half_freq = 0
        second_half_freq = 0
        first_half_count = 0
        second_half_count = 0
        
        for i in range(num_cycles):
            if i < mid_point:
                if pattern in cycle_data.get(i, {}):
                    first_half_freq += cycle_data[i][pattern]
                    first_half_count += 1
            else:
                if pattern in cycle_data.get(i, {}):
                    second_half_freq += cycle_data[i][pattern]
                    second_half_count += 1
        
        avg_first = first_half_freq / first_half_count if first_half_count > 0 else 0
        avg_second = second_half_freq / second_half_count if second_half_count > 0 else 0
        
        if avg_second > avg_first * 1.1:  # 10% increase threshold
            trend = "increasing"
        elif avg_second < avg_first * 0.9:  # 10% decrease threshold
            trend = "decreasing"
        else:
            trend = "stable"
        
        # Determine refactoring priority based on frequency and trend
        if freq >= 20 or (freq >= 10 and trend == "increasing"):
            priority = "high"
        elif freq >= 10 or (freq >= 5 and trend == "increasing"):
            priority = "medium"
        else:
            priority = "low"
        
        result_top.append({
            "pattern": pattern,
            "frequency": freq,
            "trend_direction": trend,
            "refactoring_priority": priority
        })
    
    return {
        "top_patterns": result_top,
        "cycle_data": cycle_data
    }


def run_full_analysis(
    knowledge_base: Optional[List[Dict[str, Any]]] = None,
    task_history: Optional[List[Dict[str, Any]]] = None,
    self_model: Optional[Dict[str, Any]] = None,
    num_trend_cycles: int = 10,
) -> Dict[str, Any]:
    """Convenience function to run the full failure pattern analysis pipeline.

    Args:
        knowledge_base: List of failure records from the knowledge base.
        task_history: List of task records from the scheduler history.
        self_model: Optional architectural self-model.
        num_trend_cycles: Number of cycles for trend analysis (default 10).

    Returns:
        Dictionary with keys:
            'failures': list of aggregated failures,
            'clustered_patterns': dict of pattern -> failures,
            'statistics': dict of computed statistics,
            'bottlenecks': dict of bottleneck analysis,
            'refactoring_goals': list of structured goals,
            'failure_trends': dict of trend analysis results.
    """
    failures = aggregate_failures(knowledge_base, task_history)
    clustered = extract_patterns(failures)
    statistics = compute_statistics(clustered)
    bottlenecks = identify_bottlenecks(clustered, self_model)
    goals = generate_refactoring_goals(statistics, bottlenecks, clustered)
    trends = analyze_failure_trends(clustered, num_cycles=num_trend_cycles)

    return {
        "failures": failures,
        "clustered_patterns": clustered,
        "statistics": statistics,
        "bottlenecks": bottlenecks,
        "refactoring_goals": goals,
        "failure_trends": trends,
    }