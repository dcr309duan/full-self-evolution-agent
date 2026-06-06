import re
from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime
import hashlib

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
    'batch_interval_cycles': 10,
    'hash_algorithm': 'sha256',
    'fuzzy_match_threshold': 0.6
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


def compute_goal_hash(goal_text: str, algorithm: str = None) -> str:
    """
    Computes a hash of the goal text for exact duplicate detection.
    
    Args:
        goal_text: The goal description text to hash.
        algorithm: Hash algorithm to use. Defaults to CONFIG['hash_algorithm'].
    
    Returns:
        A hex string representing the hash of the goal text.
    """
    if algorithm is None:
        algorithm = CONFIG['hash_algorithm']
    
    # Normalize the text before hashing
    normalized_text = goal_text.lower().strip()
    normalized_text = re.sub(r'\s+', ' ', normalized_text)
    
    hash_obj = hashlib.new(algorithm)
    hash_obj.update(normalized_text.encode('utf-8'))
    return hash_obj.hexdigest()


def fuzzy_match_against_capabilities(
    goal_text: str,
    capabilities: List[Dict[str, Any]],
    threshold: float = None
) -> Tuple[bool, Optional[Dict[str, Any]], float]:
    """
    Fuzzy matches a goal text against a list of existing capabilities.
    
    Args:
        goal_text: The proposed goal description text.
        capabilities: List of capability dictionaries, each with at least 'description'.
        threshold: Similarity threshold for fuzzy matching. Defaults to CONFIG['fuzzy_match_threshold'].
    
    Returns:
        Tuple of (is_duplicate, matched_capability, similarity_score).
        - is_duplicate: True if a match above threshold is found.
        - matched_capability: The matched capability dictionary, or None if no match.
        - similarity_score: The highest similarity score found.
    """
    if threshold is None:
        threshold = CONFIG['fuzzy_match_threshold']
    
    if not capabilities or not goal_text:
        return False, None, 0.0
    
    goal_keywords = extract_keywords(goal_text)
    if not goal_keywords:
        return False, None, 0.0
    
    best_match = None
    best_similarity = 0.0
    
    for capability in capabilities:
        if not isinstance(capability, dict) or 'description' not in capability:
            continue
        
        cap_keywords = extract_keywords(capability.get('description', ''))
        if not cap_keywords:
            continue
        
        similarity = jaccard_similarity(goal_keywords, cap_keywords)
        
        if similarity > best_similarity:
            best_similarity = similarity
            best_match = capability
            
            if similarity >= threshold:
                break
    
    is_duplicate = best_similarity >= threshold
    return is_duplicate, best_match, best_similarity


class GoalDeduplicator:
    """
    Manages goal deduplication with tracking and statistics.
    """
    
    def __init__(self):
        """Initialize the deduplicator with empty merge log and hash cache."""
        self.merge_log: List[Dict[str, Any]] = []
        self.goal_hash_cache: Dict[str, List[str]] = {}  # hash -> list of goal descriptions
        self.rejection_log: List[Dict[str, Any]] = []
    
    def check_against_capabilities(
        self,
        proposed_goal: Dict[str, Any],
        capabilities: List[Dict[str, Any]],
        use_hash: bool = True,
        use_fuzzy: bool = True
    ) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        """
        Checks a proposed goal against all existing capabilities.
        Uses both hash-based exact matching and fuzzy matching.
        
        Args:
            proposed_goal: The proposed goal dictionary with at least 'description'.
            capabilities: List of existing capability dictionaries.
            use_hash: Whether to use hash-based exact matching.
            use_fuzzy: Whether to use fuzzy keyword matching.
        
        Returns:
            Tuple of (is_duplicate, matched_capability, reason).
            - is_duplicate: True if the goal is a duplicate.
            - matched_capability: The matched capability, or None.
            - reason: String describing why it's considered a duplicate.
        """
        if not isinstance(proposed_goal, dict) or 'description' not in proposed_goal:
            return False, None, "Invalid goal format"
        
        goal_text = proposed_goal['description']
        
        # Hash-based exact matching
        if use_hash:
            goal_hash = compute_goal_hash(goal_text)
            
            # Check against cached hashes
            if goal_hash in self.goal_hash_cache:
                return True, None, f"Exact hash match: {goal_hash}"
            
            # Check against capability descriptions
            for capability in capabilities:
                if not isinstance(capability, dict) or 'description' not in capability:
                    continue
                cap_hash = compute_goal_hash(capability['description'])
                if cap_hash == goal_hash:
                    # Cache the hash for future reference
                    if goal_hash not in self.goal_hash_cache:
                        self.goal_hash_cache[goal_hash] = []
                    self.goal_hash_cache[goal_hash].append(goal_text)
                    return True, capability, f"Exact hash match with capability: {capability.get('name', 'unknown')}"
        
        # Fuzzy keyword matching
        if use_fuzzy:
            is_duplicate, matched_cap, similarity = fuzzy_match_against_capabilities(
                goal_text, capabilities
            )
            if is_duplicate:
                return True, matched_cap, f"Fuzzy match with similarity {similarity:.2f}"
        
        return False, None, "No duplicate found"
    
    def pre_goal_generation_filter(
        self,
        proposed_goal: Dict[str, Any],
        capabilities: List[Dict[str, Any]],
        pending_goals: List[Dict[str, Any]]
    ) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        """
        Runs before goal_generator adds new goals.
        Checks the proposed goal against both existing capabilities and pending goals.
        
        Args:
            proposed_goal: The proposed goal dictionary.
            capabilities: List of existing capability dictionaries.
            pending_goals: List of pending goal dictionaries.
        
        Returns:
            Tuple of (should_reject, matched_item, reason).
            - should_reject: True if the goal should be rejected as duplicate.
            - matched_item: The matched capability or pending goal, or None.
            - reason: String describing the rejection reason.
        """
        # First check against capabilities
        is_dup_cap, matched_cap, reason_cap = self.check_against_capabilities(
            proposed_goal, capabilities
        )
        if is_dup_cap:
            self.rejection_log.append({
                'timestamp': datetime.now().isoformat(),
                'proposed_goal': proposed_goal,
                'matched_item': matched_cap,
                'reason': reason_cap,
                'source': 'capability'
            })
            return True, matched_cap, f"Duplicate of capability: {reason_cap}"
        
        # Then check against pending goals
        is_dup_pending, matched_pending, reason_pending = self.check_against_capabilities(
            proposed_goal, pending_goals
        )
        if is_dup_pending:
            self.rejection_log.append({
                'timestamp': datetime.now().isoformat(),
                'proposed_goal': proposed_goal,
                'matched_item': matched_pending,
                'reason': reason_pending,
                'source': 'pending_goal'
            })
            return True, matched_pending, f"Duplicate of pending goal: {reason_pending}"
        
        return False, None, "Goal is unique"
    
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
            - total_rejections: Total number of goal rejections
            - rejection_sources: Breakdown of rejection sources
        """
        stats = {
            'total_merges': 0,
            'average_similarity_threshold': 0.0,
            'most_merged_goal_category': None,
            'total_rejections': len(self.rejection_log),
            'rejection_sources': {}
        }
        
        if self.merge_log:
            total_merges = len(self.merge_log)
            total_threshold = sum(entry['similarity_threshold'] for entry in self.merge_log)
            stats['total_merges'] = total_merges
            stats['average_similarity_threshold'] = total_threshold / total_merges
            
            # Count goal categories
            category_counts = {}
            for entry in self.merge_log:
                for goal in entry['original_goals']:
                    category = goal.get('category', goal.get('description', 'unknown'))
                    category_counts[category] = category_counts.get(category, 0) + 1
            
            stats['most_merged_goal_category'] = max(category_counts, key=category_counts.get) if category_counts else None
        
        # Count rejection sources
        for entry in self.rejection_log:
            source = entry.get('source', 'unknown')
            stats['rejection_sources'][source] = stats['rejection_sources'].get(source, 0) + 1
        
        return stats
    
    def clear_rejection_log(self):
        """Clears the rejection log."""
        self.rejection_log = []


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


def pre_goal_generation_filter(
    proposed_goal: Dict[str, Any],
    capabilities: List[Dict[str, Any]],
    pending_goals: List[Dict[str, Any]]
) -> Tuple[bool, Optional[Dict[str, Any]], str]:
    """Backward-compatible wrapper for GoalDeduplicator.pre_goal_generation_filter."""
    return _default_deduplicator.pre_goal_generation_filter(proposed_goal, capabilities, pending_goals)


def check_against_capabilities(
    proposed_goal: Dict[str, Any],
    capabilities: List[Dict[str, Any]],
    use_hash: bool = True,
    use_fuzzy: bool = True
) -> Tuple[bool, Optional[Dict[str, Any]], str]:
    """Backward-compatible wrapper for GoalDeduplicator.check_against_capabilities."""
    return _default_deduplicator.check_against_capabilities(proposed_goal, capabilities, use_hash, use_fuzzy)


def compute_goal_hash(goal_text: str, algorithm: str = None) -> str:
    """Backward-compatible wrapper for compute_goal_hash function."""
    if algorithm is None:
        algorithm = CONFIG['hash_algorithm']
    return compute_goal_hash(goal_text, algorithm)


def fuzzy_match_against_capabilities(
    goal_text: str,
    capabilities: List[Dict[str, Any]],
    threshold: float = None
) -> Tuple[bool, Optional[Dict[str, Any]], float]:
    """Backward-compatible wrapper for fuzzy_match_against_capabilities function."""
    if threshold is None:
        threshold = CONFIG['fuzzy_match_threshold']
    return fuzzy_match_against_capabilities(goal_text, capabilities, threshold)