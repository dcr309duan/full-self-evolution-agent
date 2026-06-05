"""Core prioritizer module for scoring, classifying, archiving, and prioritizing goals.

This module provides functions to evaluate goal impact based on test pass rate,
simplicity, and resource cost, then classify and manage goals accordingly.

Functions:
    score_goal: Compute a numeric score for a goal.
    classify_goals: Classify goals into high_priority, medium, or archive.
    get_actionable_goals: Filter pending goals to those with score > 0.7.
    archive_low_impact: Move goals with score < 0.3 to an archive list.
    archive_goals: Move goals with score < threshold to archive list.
    get_viable_goals: Return only goals with score > threshold.
"""

from typing import Any, Dict, List, Optional, Union


def score_goal(
    goal: Dict[str, Any],
    default_test_pass_rate: float = 0.5,
    default_simplicity_score: float = 0.5,
    default_lines_added: int = 0,
    default_new_deps: int = 0,
) -> float:
    """Compute a numeric score for a goal based on test pass rate, simplicity, and resource cost.

    The score is calculated as:
        (test_pass_rate * simplicity_score) / (lines_added + new_deps + 1)

    Missing or invalid fields in the goal dict are replaced with provided defaults.

    Args:
        goal: A dictionary representing a goal. Expected keys:
            - 'test_pass_rate' (float, 0-1): Rate of passing tests.
            - 'simplicity_score' (float, 0-1): Simplicity of implementation.
            - 'lines_added' (int): Number of lines of code added.
            - 'new_deps' (int): Number of new dependencies introduced.
        default_test_pass_rate: Fallback if 'test_pass_rate' is missing or invalid.
        default_simplicity_score: Fallback if 'simplicity_score' is missing or invalid.
        default_lines_added: Fallback if 'lines_added' is missing or invalid.
        default_new_deps: Fallback if 'new_deps' is missing or invalid.

    Returns:
        A float score. Returns 0.0 if the denominator is zero or negative (should not happen
        due to +1 safety), or if inputs are invalid beyond recovery.

    Raises:
        TypeError: If goal is not a dict.
    """
    if not isinstance(goal, dict):
        raise TypeError("goal must be a dictionary")

    try:
        test_pass_rate = goal.get("test_pass_rate", default_test_pass_rate)
        if not isinstance(test_pass_rate, (int, float)):
            test_pass_rate = default_test_pass_rate
        test_pass_rate = max(0.0, min(1.0, float(test_pass_rate)))

        simplicity_score = goal.get("simplicity_score", default_simplicity_score)
        if not isinstance(simplicity_score, (int, float)):
            simplicity_score = default_simplicity_score
        simplicity_score = max(0.0, min(1.0, float(simplicity_score)))

        lines_added = goal.get("lines_added", default_lines_added)
        if not isinstance(lines_added, (int, float)):
            lines_added = default_lines_added
        lines_added = max(0, int(lines_added))

        new_deps = goal.get("new_deps", default_new_deps)
        if not isinstance(new_deps, (int, float)):
            new_deps = default_new_deps
        new_deps = max(0, int(new_deps))

        numerator = test_pass_rate * simplicity_score
        denominator = lines_added + new_deps + 1

        if denominator <= 0:
            return 0.0

        return numerator / denominator

    except (TypeError, ValueError, ArithmeticError):
        return 0.0


def classify_goals(
    goals: Dict[str, Dict[str, Any]],
    high_threshold: float = 0.7,
    low_threshold: float = 0.3,
    **score_kwargs: Any,
) -> Dict[str, List[Dict[str, Any]]]:
    """Classify goals into high_priority, medium, or archive based on their scores.

    Classification rules:
        - score > high_threshold -> 'high_priority'
        - low_threshold <= score <= high_threshold -> 'medium'
        - score < low_threshold -> 'archive'

    Args:
        goals: Dictionary mapping goal IDs to goal dicts.
        high_threshold: Minimum score for 'high_priority' classification. Must be > low_threshold.
        low_threshold: Maximum score for 'archive' classification. Must be < high_threshold.
        **score_kwargs: Additional keyword arguments forwarded to score_goal().

    Returns:
        A dictionary with keys 'high_priority', 'medium', and 'archive', each containing
        a list of goal dicts (with 'id' and 'score' keys added).

    Raises:
        TypeError: If goals is not a dict.
        ValueError: If thresholds are invalid (high_threshold <= low_threshold).
    """
    if not isinstance(goals, dict):
        raise TypeError("goals must be a dictionary")

    if high_threshold <= low_threshold:
        raise ValueError(
            f"high_threshold ({high_threshold}) must be greater than "
            f"low_threshold ({low_threshold})"
        )

    result: Dict[str, List[Dict[str, Any]]] = {
        "high_priority": [],
        "medium": [],
        "archive": [],
    }

    for goal_id, goal in goals.items():
        try:
            score = score_goal(goal, **score_kwargs)
            scored_goal = dict(goal)
            scored_goal["id"] = goal_id
            scored_goal["score"] = score

            if score > high_threshold:
                result["high_priority"].append(scored_goal)
            elif score >= low_threshold:
                result["medium"].append(scored_goal)
            else:
                result["archive"].append(scored_goal)
        except (TypeError, ValueError):
            continue

    return result


def get_actionable_goals(
    pending_goals: Dict[str, Dict[str, Any]],
    threshold: float = 0.7,
    **score_kwargs: Any,
) -> List[Dict[str, Any]]:
    """Filter pending goals to only those with score > threshold.

    Args:
        pending_goals: Dictionary mapping goal IDs to goal dicts.
        threshold: Minimum score for a goal to be considered actionable.
        **score_kwargs: Additional keyword arguments forwarded to score_goal().

    Returns:
        A list of goal dicts (with 'id' and 'score' keys added) that have scores > threshold.

    Raises:
        TypeError: If pending_goals is not a dict.
    """
    if not isinstance(pending_goals, dict):
        raise TypeError("pending_goals must be a dictionary")

    actionable: List[Dict[str, Any]] = []

    for goal_id, goal in pending_goals.items():
        try:
            score = score_goal(goal, **score_kwargs)
            if score > threshold:
                scored_goal = dict(goal)
                scored_goal["id"] = goal_id
                scored_goal["score"] = score
                actionable.append(scored_goal)
        except (TypeError, ValueError):
            continue

    return actionable


def archive_low_impact(
    pending_goals: Dict[str, Dict[str, Any]],
    archive_list: List[Dict[str, Any]],
    threshold: float = 0.3,
    **score_kwargs: Any,
) -> None:
    """Move goals with score < threshold from pending_goals to archive_list.

    Each archived goal is removed from pending_goals and appended to archive_list
    with an 'archived' flag set to True.

    Args:
        pending_goals: Dictionary mapping goal IDs to goal dicts (modified in place).
        archive_list: List of archived goal dicts (modified in place).
        threshold: Maximum score for a goal to be archived.
        **score_kwargs: Additional keyword arguments forwarded to score_goal().

    Raises:
        TypeError: If pending_goals is not a dict or archive_list is not a list.
    """
    if not isinstance(pending_goals, dict):
        raise TypeError("pending_goals must be a dictionary")
    if not isinstance(archive_list, list):
        raise TypeError("archive_list must be a list")

    goals_to_archive: List[str] = []

    for goal_id, goal in pending_goals.items():
        try:
            score = score_goal(goal, **score_kwargs)
            if score < threshold:
                goals_to_archive.append(goal_id)
        except (TypeError, ValueError):
            continue

    for goal_id in goals_to_archive:
        goal = pending_goals.pop(goal_id)
        goal["archived"] = True
        archive_list.append(goal)


def archive_goals(
    pending_goals: Dict[str, Dict[str, Any]],
    archive_list: List[Dict[str, Any]],
    threshold: float = 0.3,
    **score_kwargs: Any,
) -> None:
    """Move goals with score < threshold from pending_goals to archive_list.

    This function is an alias for archive_low_impact with the same behavior.
    Each archived goal is removed from pending_goals and appended to archive_list
    with an 'archived' flag set to True.

    Args:
        pending_goals: Dictionary mapping goal IDs to goal dicts (modified in place).
        archive_list: List of archived goal dicts (modified in place).
        threshold: Maximum score for a goal to be archived.
        **score_kwargs: Additional keyword arguments forwarded to score_goal().

    Raises:
        TypeError: If pending_goals is not a dict or archive_list is not a list.
    """
    if not isinstance(pending_goals, dict):
        raise TypeError("pending_goals must be a dictionary")
    if not isinstance(archive_list, list):
        raise TypeError("archive_list must be a list")

    goals_to_archive: List[str] = []

    for goal_id, goal in pending_goals.items():
        try:
            score = score_goal(goal, **score_kwargs)
            if score < threshold:
                goals_to_archive.append(goal_id)
        except (TypeError, ValueError):
            continue

    for goal_id in goals_to_archive:
        goal = pending_goals.pop(goal_id)
        goal["archived"] = True
        archive_list.append(goal)


def get_viable_goals(
    pending_goals: Dict[str, Dict[str, Any]],
    threshold: float = 0.7,
    **score_kwargs: Any,
) -> List[Dict[str, Any]]:
    """Return only goals with score > threshold from pending_goals.

    This function is an alias for get_actionable_goals with the same behavior.
    Returns a list of goal dicts (with 'id' and 'score' keys added) that have scores > threshold.

    Args:
        pending_goals: Dictionary mapping goal IDs to goal dicts.
        threshold: Minimum score for a goal to be considered viable.
        **score_kwargs: Additional keyword arguments forwarded to score_goal().

    Returns:
        A list of goal dicts (with 'id' and 'score' keys added) that have scores > threshold.

    Raises:
        TypeError: If pending_goals is not a dict.
    """
    if not isinstance(pending_goals, dict):
        raise TypeError("pending_goals must be a dictionary")

    viable: List[Dict[str, Any]] = []

    for goal_id, goal in pending_goals.items():
        try:
            score = score_goal(goal, **score_kwargs)
            if score > threshold:
                scored_goal = dict(goal)
                scored_goal["id"] = goal_id
                scored_goal["score"] = score
                viable.append(scored_goal)
        except (TypeError, ValueError):
            continue

    return viable