"""Module for failure-driven mutation selection.

Queries the failure pattern miner for the most common failure type in the last 10 cycles,
extracts keywords from the failure description, filters the candidate mutation pool to exclude
mutations whose target file or operation matches those keywords, and returns the filtered pool.
"""

import logging
from typing import List, Dict, Any, Optional, Set
from collections import Counter

logger = logging.getLogger(__name__)

# Default number of cycles to analyze
DEFAULT_CYCLES = 10


def get_most_common_failure_type(
    failure_pattern_miner: Any,
    cycles: int = DEFAULT_CYCLES
) -> Optional[str]:
    """Query the failure pattern miner for the most common failure type in the last N cycles.

    Args:
        failure_pattern_miner: An object with a method to retrieve recent failure patterns.
        cycles: Number of recent cycles to analyze (default 10).

    Returns:
        The most common failure type description, or None if no failures found.
    """
    try:
        # Assume the miner has a method 'get_recent_failures' that returns a list of failure dicts
        recent_failures = failure_pattern_miner.get_recent_failures(cycles=cycles)
        if not recent_failures:
            logger.warning("No recent failures found in the last %d cycles.", cycles)
            return None

        # Count failure types (assuming each failure has a 'type' or 'description' field)
        failure_types = [f.get('type', f.get('description', 'unknown')) for f in recent_failures]
        most_common = Counter(failure_types).most_common(1)
        if most_common:
            failure_type = most_common[0][0]
            logger.info("Most common failure type in last %d cycles: %s", cycles, failure_type)
            return failure_type
        return None
    except Exception as e:
        logger.error("Failed to query failure pattern miner: %s", e)
        return None


def extract_keywords(failure_description: str) -> Set[str]:
    """Extract keywords from a failure description.

    Splits the description into words and returns a set of lowercase keywords.
    Common stop words are excluded.

    Args:
        failure_description: A string describing the failure.

    Returns:
        A set of keyword strings.
    """
    if not failure_description:
        return set()

    # Simple stop words list (can be expanded)
    stop_words = {
        'a', 'an', 'the', 'is', 'was', 'are', 'were', 'in', 'on', 'at', 'to', 'for',
        'of', 'with', 'by', 'from', 'and', 'or', 'not', 'no', 'but', 'if', 'so',
        'as', 'it', 'its', 'this', 'that', 'these', 'those', 'be', 'been', 'being',
        'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'can', 'could',
        'should', 'may', 'might', 'must', 'about', 'into', 'through', 'during',
        'before', 'after', 'above', 'below', 'between', 'out', 'off', 'over', 'under',
        'again', 'further', 'then', 'once', 'here', 'there', 'when', 'where', 'why',
        'how', 'all', 'each', 'every', 'both', 'few', 'more', 'most', 'other', 'some',
        'such', 'only', 'own', 'same', 'so', 'than', 'too', 'very', 'just', 'because',
        'also', 'any', 'error', 'failed', 'failure', 'exception'
    }

    # Split into words, lowercase, filter out stop words and short words
    words = failure_description.lower().split()
    keywords = {
        word.strip('.,!?;:()[]{}"\'')
        for word in words
        if word.strip('.,!?;:()[]{}"\'') not in stop_words and len(word.strip('.,!?;:()[]{}"\'')) > 2
    }

    logger.debug("Extracted keywords: %s", keywords)
    return keywords


def filter_mutation_pool(
    mutation_pool: List[Dict[str, Any]],
    keywords: Set[str]
) -> List[Dict[str, Any]]:
    """Filter the candidate mutation pool to exclude mutations whose target file or operation matches keywords.

    A mutation is excluded if any keyword is found in its target file path or operation name.

    Args:
        mutation_pool: List of mutation dictionaries. Each dict should have at least
                       'target_file' and 'operation' keys.
        keywords: Set of keywords to filter against.

    Returns:
        Filtered list of mutations that do not match any keyword.
    """
    if not keywords:
        logger.info("No keywords provided, returning full mutation pool.")
        return mutation_pool

    filtered_pool = []
    for mutation in mutation_pool:
        target_file = mutation.get('target_file', '')
        operation = mutation.get('operation', '')

        # Check if any keyword is in target_file or operation (case-insensitive)
        should_exclude = False
        for keyword in keywords:
            if keyword in target_file.lower() or keyword in operation.lower():
                should_exclude = True
                logger.debug("Excluding mutation due to keyword '%s': file='%s', op='%s'",
                             keyword, target_file, operation)
                break

        if not should_exclude:
            filtered_pool.append(mutation)

    logger.info("Filtered mutation pool: %d out of %d mutations kept.",
                len(filtered_pool), len(mutation_pool))
    return filtered_pool


def select_mutations_failure_driven(
    failure_pattern_miner: Any,
    mutation_pool: List[Dict[str, Any]],
    cycles: int = DEFAULT_CYCLES
) -> List[Dict[str, Any]]:
    """Main function: query failure patterns, extract keywords, filter mutation pool.

    Args:
        failure_pattern_miner: Object to query for recent failure patterns.
        mutation_pool: List of candidate mutations.
        cycles: Number of recent cycles to analyze (default 10).

    Returns:
        Filtered mutation pool.
    """
    failure_type = get_most_common_failure_type(failure_pattern_miner, cycles)
    if not failure_type:
        logger.warning("No failure type identified; returning original mutation pool.")
        return mutation_pool

    keywords = extract_keywords(failure_type)
    if not keywords:
        logger.info("No keywords extracted; returning original mutation pool.")
        return mutation_pool

    filtered_pool = filter_mutation_pool(mutation_pool, keywords)
    return filtered_pool