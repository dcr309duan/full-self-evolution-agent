"""Core prioritizer module for scoring, classifying, archiving, and prioritizing goals.

This module provides functions to evaluate goal impact based on test pass rate,
simplicity, and resource cost, then classify and manage goals accordingly.

Functions:
    score_goal: Compute a numeric score for a goal.
    classify_goal: Classify a goal as 'mutable', 'pending', or 'archive'.
    archive_goal: Move a goal to archive and remove from pending.
    prioritize_goals: Sort pending goals by score descending.
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


def classify_goal(
    goal: Dict[str, Any],
    mutable_threshold: float = 0.7,
    archive_threshold: float = 0.3,
    **score_kwargs: Any,
) -> str:
    """Classify a goal as 'mutable', 'pending', or 'archive' based on its score.

    Classification rules:
        - score >= mutable_threshold -> 'mutable'
        - score >= archive_threshold -> 'pending'
        - score < archive_threshold  -> 'archive'

    Args:
        goal: A dictionary representing a goal (passed to score_goal).
        mutable_threshold: Minimum score for 'mutable' classification. Must be > archive_threshold.
        archive_threshold: Maximum score for 'archive' classification. Must be < mutable_threshold.
        **score_kwargs: Additional keyword arguments forwarded to score_goal().

    Returns:
        One of 'mutable', 'pending', or 'archive'.

    Raises:
        ValueError: If thresholds are invalid (mutable_threshold <= archive_threshold).
        TypeError: If goal is not a dict.
    """
    if not isinstance(goal, dict):
        raise TypeError("goal must be a dictionary")

    if mutable_threshold <= archive_threshold:
        raise ValueError(
            f"mutable_threshold ({mutable_threshold}) must be greater than "
            f"archive_threshold ({archive_threshold})"
        )

    score = score_goal(goal, **score_kwargs)

    if score >= mutable_threshold:
        return "mutable"
    elif score >= archive_threshold:
        return "pending"
    else:
        return "archive"


def archive_goal(
    goal_id: str,
    pending_goals: Dict[str, Dict[str, Any]],
    archive_list: List[Dict[str, Any]],
) -> None:
    """Move a goal from pending goals to the archive list.

    The goal is removed from pending_goals and appended to archive_list with an
    'archived' flag set to True.

    Args:
        goal_id: The key identifying the goal in pending_goals.
        pending_goals: Dictionary mapping goal IDs to goal dicts.
        archive_list: List of archived goal dicts (modified in place).

    Raises:
        KeyError: If goal_id is not found in pending_goals.
        TypeError: If pending_goals is not a dict or archive_list is not a list.
    """
    if not isinstance(pending_goals, dict):
        raise TypeError("pending_goals must be a dictionary")
    if not isinstance(archive_list, list):
        raise TypeError("archive_list must be a list")

    if goal_id not in pending_goals:
        raise KeyError(f"goal_id '{goal_id}' not found in pending_goals")

    goal = pending_goals.pop(goal_id)
    goal["archived"] = True
    archive_list.append(goal)


def prioritize_goals(
    pending_goals: Dict[str, Dict[str, Any]],
    **score_kwargs: Any,
) -> List[Dict[str, Any]]:
    """Sort pending goals by their score in descending order.

    Each goal is scored using score_goal(), and the results are returned as a list
    of dicts sorted from highest to lowest score. Each dict includes the original
    goal data plus a 'score' key.

    Args:
        pending_goals: Dictionary mapping goal IDs to goal dicts.
        **score_kwargs: Additional keyword arguments forwarded to score_goal().

    Returns:
        A list of goal dicts sorted by score descending, each with an added 'score' key.

    Raises:
        TypeError: If pending_goals is not a dict.
    """
    if not isinstance(pending_goals, dict):
        raise TypeError("pending_goals must be a dictionary")

    scored_goals: List[Dict[str, Any]] = []
    for goal_id, goal in pending_goals.items():
        try:
            score = score_goal(goal, **score_kwargs)
            scored_goal = dict(goal)  # shallow copy to avoid mutating original
            scored_goal["id"] = goal_id
            scored_goal["score"] = score
            scored_goals.append(scored_goal)
        except (TypeError, ValueError):
            # Skip goals that cause errors during scoring
            continue

    scored_goals.sort(key=lambda g: g["score"], reverse=True)
    return scored_goals