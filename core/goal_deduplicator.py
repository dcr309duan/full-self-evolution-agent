import re
from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime

# Default set of English stopwords for keyword extraction
DEFAULT_STOPWORDS = frozenset({
    "a", "an", "the", "and", "or", "but", "if", "because", "as", "what",
    "which", "this", "that", "these", "those", "then", "just", "so", "than",
    "such", "both", "through", "about", "for", "is", "of", "while", "during",
    "to", "from", "in", "on", "by", "with", "at", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "can", "could",
    "shall", "should", "may", "might", "must", "need", "dare", "ought", "used",
    "it", "its", "my", "your", "his", "her", "their", "our", "we", "you", "they",
    "he", "she", "me", "him", "us", "them", "i", "not", "no", "nor", "very",
    "too", "much", "many", "more", "most", "some", "any", "each", "every",
    "all", "both", "few", "several", "own", "same", "other", "another",
    "such", "only", "own", "same", "than", "then", "also", "however",
    "therefore", "thus", "hence", "meanwhile", "nevertheless", "nonetheless",
    "furthermore", "moreover", "besides", "indeed", "instead", "otherwise",
    "never", "always", "often", "usually", "sometimes", "rarely", "seldom"
})

# Configuration dictionary for easy tuning
CONFIG = {
    'similarity_threshold': 0.7,
    'stopwords': list(DEFAULT_STOPWORDS) + ['implement', 'create', 'add'],
    'merge_description_separator': ' | ',
    'batch_interval_cycles': 10
}


def extract_keywords(description: str, stopwords: Optional[set] = None) -> set:
    """
    Tokenizes a goal description into a set of lowercase words, excluding stopwords.
    
    Args:
        description: The goal description string to tokenize.
        stopwords: Optional set of stopwords to exclude. Defaults to CONFIG['stopwords'].
    
    Returns:
        A set of lowercase keyword strings.
    """
    if stopwords is None:
        stopwords = set(CONFIG['stopwords'])
    
    # Tokenize: split on non-alphanumeric characters (preserve underscores and hyphens)
    tokens = re.findall(r'[a-zA-Z0-9_\-]+', description.lower())
    
    # Filter out stopwords and single-character tokens
    keywords = {token for token in tokens if token not in stopwords and len(token) > 1}
    
    return keywords


def jaccard_similarity(set_a: set, set_b: set) -> float:
    """
    Computes the Jaccard similarity between two sets.
    
    Jaccard similarity = |A ∩ B| / |A ∪ B|
    
    Args:
        set_a: First set of elements.
        set_b: Second set of elements.
    
    Returns:
        A float between 0.0 and 1.0 representing the similarity.
        Returns 0.0 if both sets are empty.
    """
    intersection = set_a & set_b
    union = set_a | set_b
    
    if not union:
        return 0.0
    
    return len(intersection) / len(union)


class GoalDeduplicator:
    """
    Manages goal deduplication with tracking and statistics.
    """
    
    def __init__(self):
        """Initialize the deduplicator with empty merge log."""
        self.merge_log: List[Dict[str, Any]] = []
    
    def deduplicate_goals(
        self,
        new_goal: Dict[str, Any],
        existing_goals: List[Dict[str, Any]],
        similarity_threshold: Optional[float] = None
    ) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Checks a new goal against a list of existing pending goals.
        If a goal with Jaccard similarity > threshold is found, merges them:
          - Takes the maximum priority.
          - Combines descriptions with CONFIG['merge_description_separator'].
          - Returns the merged goal and the updated list (with the matched goal removed).
        If no match, returns the original new goal and the unchanged list.
        
        Args:
            new_goal: A dictionary with at least 'description' (str) and 'priority' (int/float).
            existing_goals: List of goal dictionaries, each with 'description' and 'priority'.
            similarity_threshold: Float between 0 and 1. Defaults to CONFIG['similarity_threshold'].
        
        Returns:
            Tuple of (merged_goal_or_original, updated_existing_goals_list).
            merged_goal_or_original is None only if new_goal is invalid.
        """
        if similarity_threshold is None:
            similarity_threshold = CONFIG['similarity_threshold']
        
        if not isinstance(new_goal, dict) or 'description' not in new_goal:
            return None, existing_goals
        
        new_keywords = extract_keywords(new_goal.get('description', ''))
        new_priority = new_goal.get('priority', 0)
        new_description = new_goal.get('description', '')
        
        updated_goals = list(existing_goals)
        merged_goal = dict(new_goal)  # Start with a copy of the new goal
        
        for i, existing_goal in enumerate(existing_goals):
            if not isinstance(existing_goal, dict) or 'description' not in existing_goal:
                continue
            
            existing_keywords = extract_keywords(existing_goal.get('description', ''))
            similarity = jaccard_similarity(new_keywords, existing_keywords)
            
            if similarity > similarity_threshold:
                # Merge: take max priority
                merged_priority = max(new_priority, existing_goal.get('priority', 0))
                
                # Combine descriptions with separator from config
                existing_description = existing_goal.get('description', '')
                combined_description = f"{new_description}{CONFIG['merge_description_separator']}{existing_description}"
                
                # Build merged goal (preserve other keys from new_goal, override description/priority)
                merged_goal = dict(new_goal)
                merged_goal['description'] = combined_description
                merged_goal['priority'] = merged_priority
                merged_goal['merged_from'] = [new_goal, existing_goal]
                
                # Log the merge event
                self.merge_log.append({
                    'timestamp': datetime.now().isoformat(),
                    'original_goals': [new_goal, existing_goal],
                    'merged_result': merged_goal,
                    'similarity_threshold': similarity_threshold
                })
                
                # Remove the matched existing goal from the list
                updated_goals.pop(i)
                break
        
        return merged_goal, updated_goals
    
    def pre_insertion_filter(
        self,
        new_goal: Dict[str, Any],
        pending_goals: List[Dict[str, Any]],
        similarity_threshold: Optional[float] = None
    ) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Wrapper function that integrates with goal_generator's add_goal flow.
        Runs deduplication before insertion: if a similar goal exists, merges them.
        
        This is designed to be called as a pre-processing step before adding a goal
        to the pending goals list.
        
        Args:
            new_goal: The goal dictionary to be added.
            pending_goals: The current list of pending goals.
            similarity_threshold: Jaccard similarity threshold for deduplication. Defaults to CONFIG['similarity_threshold'].
        
        Returns:
            Tuple of (goal_to_add, updated_pending_goals).
            - goal_to_add: The goal to insert (merged or original). None if invalid.
            - updated_pending_goals: The pending goals list with any duplicates removed.
        """
        if similarity_threshold is None:
            similarity_threshold = CONFIG['similarity_threshold']
        
        if not isinstance(new_goal, dict) or 'description' not in new_goal:
            return None, pending_goals
        
        # Run deduplication
        dedup_result, updated_list = self.deduplicate_goals(
            new_goal, pending_goals, similarity_threshold
        )
        
        if dedup_result is None:
            return None, pending_goals
        
        # If the result has 'merged_from' key, it means a merge occurred
        if 'merged_from' in dedup_result:
            # The updated_list already has the matched goal removed
            return dedup_result, updated_list
        
        # No merge occurred; return original goal and unchanged list
        return new_goal, pending_goals
    
    def batch_deduplicate(
        self,
        pending_goals: List[Dict[str, Any]],
        similarity_threshold: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Processes the entire pending_goals list in one pass to deduplicate.
        (1) Sorts goals by priority descending.
        (2) For each goal, compares against all lower-priority goals.
        (3) Merges any with similarity > threshold.
        (4) Returns deduplicated list.
        
        This can be called periodically (e.g., every CONFIG['batch_interval_cycles'] cycles) to clean up
        any duplicates that slipped through.
        
        Args:
            pending_goals: List of goal dictionaries, each with 'description' and 'priority'.
            similarity_threshold: Float between 0 and 1. Defaults to CONFIG['similarity_threshold'].
        
        Returns:
            A deduplicated list of goal dictionaries.
        """
        if similarity_threshold is None:
            similarity_threshold = CONFIG['similarity_threshold']
        
        if not pending_goals:
            return []
        
        # Sort goals by priority descending (higher priority first)
        sorted_goals = sorted(
            pending_goals,
            key=lambda g: g.get('priority', 0),
            reverse=True
        )
        
        # Process goals: for each goal, compare against all lower-priority goals
        deduplicated = []
        for i, goal in enumerate(sorted_goals):
            if not isinstance(goal, dict) or 'description' not in goal:
                deduplicated.append(goal)
                continue
            
            goal_keywords = extract_keywords(goal.get('description', ''))
            goal_priority = goal.get('priority', 0)
            goal_description = goal.get('description', '')
            
            merged_goal = dict(goal)
            merged_indices = []
            
            # Compare against all lower-priority goals
            for j in range(i + 1, len(sorted_goals)):
                other_goal = sorted_goals[j]
                if not isinstance(other_goal, dict) or 'description' not in other_goal:
                    continue
                
                other_keywords = extract_keywords(other_goal.get('description', ''))
                similarity = jaccard_similarity(goal_keywords, other_keywords)
                
                if similarity > similarity_threshold:
                    # Merge: take max priority
                    merged_priority = max(goal_priority, other_goal.get('priority', 0))
                    
                    # Combine descriptions with separator from config
                    other_description = other_goal.get('description', '')
                    combined_description = f"{merged_goal['description']}{CONFIG['merge_description_separator']}{other_description}"
                    
                    # Update merged goal
                    merged_goal['description'] = combined_description
                    merged_goal['priority'] = merged_priority
                    
                    # Track merged goals
                    if 'merged_from' not in merged_goal:
                        merged_goal['merged_from'] = [goal, other_goal]
                    else:
                        merged_goal['merged_from'].append(other_goal)
                    
                    # Log the merge event
                    self.merge_log.append({
                        'timestamp': datetime.now().isoformat(),
                        'original_goals': [goal, other_goal],
                        'merged_result': merged_goal,
                        'similarity_threshold': similarity_threshold
                    })
                    
                    merged_indices.append(j)
            
            # Remove merged lower-priority goals (process in reverse to maintain indices)
            for idx in sorted(merged_indices, reverse=True):
                sorted_goals.pop(idx)
            
            # Update keywords for subsequent comparisons if merge occurred
            if merged_indices:
                goal_keywords = extract_keywords(merged_goal.get('description', ''))
            
            deduplicated.append(merged_goal)
        
        return deduplicated
    
    def get_merge_stats(self) -> Dict[str, Any]:
        """
        Returns statistics about merge operations.
        
        Returns:
            Dictionary with:
            - total_merges: Total number of merges performed
            - average_similarity_threshold: Average similarity threshold used
            - most_merged_goal_category: Most frequently merged goal category
        """
        if not self.merge_log:
            return {
                'total_merges': 0,
                'average_similarity_threshold': 0.0,
                'most_merged_goal_category': None
            }
        
        total_merges = len(self.merge_log)
        total_threshold = sum(entry['similarity_threshold'] for entry in self.merge_log)
        average_similarity_threshold = total_threshold / total_merges
        
        # Count goal categories (using 'category' key if present, otherwise 'description')
        category_counts = {}
        for entry in self.merge_log:
            for goal in entry['original_goals']:
                category = goal.get('category', goal.get('description', 'unknown'))
                category_counts[category] = category_counts.get(category, 0) + 1
        
        most_merged_goal_category = max(category_counts, key=category_counts.get) if category_counts else None
        
        return {
            'total_merges': total_merges,
            'average_similarity_threshold': average_similarity_threshold,
            'most_merged_goal_category': most_merged_goal_category
        }


# Create a default instance for backward compatibility
_default_deduplicator = GoalDeduplicator()

# Backward-compatible function wrappers
def deduplicate_goals(
    new_goal: Dict[str, Any],
    existing_goals: List[Dict[str, Any]],
    similarity_threshold: Optional[float] = None
) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
    """Backward-compatible wrapper for GoalDeduplicator.deduplicate_goals."""
    if similarity_threshold is None:
        similarity_threshold = CONFIG['similarity_threshold']
    return _default_deduplicator.deduplicate_goals(new_goal, existing_goals, similarity_threshold)


def pre_insertion_filter(
    new_goal: Dict[str, Any],
    pending_goals: List[Dict[str, Any]],
    similarity_threshold: Optional[float] = None
) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
    """Backward-compatible wrapper for GoalDeduplicator.pre_insertion_filter."""
    if similarity_threshold is None:
        similarity_threshold = CONFIG['similarity_threshold']
    return _default_deduplicator.pre_insertion_filter(new_goal, pending_goals, similarity_threshold)


def batch_deduplicate(
    pending_goals: List[Dict[str, Any]],
    similarity_threshold: Optional[float] = None
) -> List[Dict[str, Any]]:
    """Backward-compatible wrapper for GoalDeduplicator.batch_deduplicate."""
    if similarity_threshold is None:
        similarity_threshold = CONFIG['similarity_threshold']
    return _default_deduplicator.batch_deduplicate(pending_goals, similarity_threshold)