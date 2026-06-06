import os
import json
from typing import Dict, List, Optional, Any
from datetime import datetime

class ActionClassifier:
    """
    Classifies each evolution cycle's actions into categories:
    - 'code_mutation': Any successful file modification (create, modify, delete)
    - 'reflective_only': Only goal generation, reflection, or failed mutations
    
    This classification feeds into the meta-cognition timeout counter
    to determine when to trigger meta-cognitive interventions.
    """
    
    # Action types that indicate code mutation
    CODE_MUTATION_KEYWORDS = [
        'create_file', 'modify_file', 'delete_file', 'write_file',
        'file_creation', 'file_modification', 'file_deletion',
        'code_change', 'implementation', 'refactor', 'rewrite',
        'add_feature', 'fix_bug', 'update_function', 'patch'
    ]
    
    # Action types that are purely reflective
    REFLECTIVE_KEYWORDS = [
        'reflect', 'analyze', 'evaluate', 'goal_generation',
        'goal_creation', 'planning', 'strategy', 'meta_cognition',
        'self_analysis', 'failure_analysis', 'insight_generation',
        'meta_insight', 'research', 'study', 'review'
    ]
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the action classifier.
        
        Args:
            config_path: Optional path to a JSON config file for custom keywords
        """
        self.code_mutation_keywords = list(self.CODE_MUTATION_KEYWORDS)
        self.reflective_keywords = list(self.REFLECTIVE_KEYWORDS)
        
        if config_path and os.path.exists(config_path):
            self._load_custom_keywords(config_path)
    
    def _load_custom_keywords(self, config_path: str) -> None:
        """Load custom classification keywords from a config file."""
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                if 'code_mutation_keywords' in config:
                    self.code_mutation_keywords.extend(config['code_mutation_keywords'])
                if 'reflective_keywords' in config:
                    self.reflective_keywords.extend(config['reflective_keywords'])
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not load config from {config_path}: {e}")
    
    def classify_action(self, action: Dict[str, Any]) -> str:
        """
        Classify a single action as 'code_mutation' or 'reflective_only'.
        
        Args:
            action: A dictionary representing an action, expected to have
                   at least a 'type' or 'description' field.
                   
        Returns:
            'code_mutation' if the action involves successful file modification,
            'reflective_only' otherwise.
        """
        # Extract action text from various possible field names
        action_text = self._extract_action_text(action)
        if not action_text:
            return 'reflective_only'
        
        action_text_lower = action_text.lower()
        
        # Check for code mutation indicators
        for keyword in self.code_mutation_keywords:
            if keyword.lower() in action_text_lower:
                # Verify it's a successful action
                if self._is_successful(action):
                    return 'code_mutation'
        
        # Check for reflective indicators
        for keyword in self.reflective_keywords:
            if keyword.lower() in action_text_lower:
                return 'reflective_only'
        
        # Default classification based on action type
        action_type = action.get('type', '').lower()
        if action_type in ['create', 'modify', 'delete', 'write', 'update']:
            if self._is_successful(action):
                return 'code_mutation'
        
        return 'reflective_only'
    
    def classify_cycle_actions(self, cycle_actions: List[Dict[str, Any]]) -> str:
        """
        Classify an entire cycle's worth of actions.
        Returns 'code_mutation' if ANY action in the cycle was a successful code mutation.
        
        Args:
            cycle_actions: List of action dictionaries from a single evolution cycle
            
        Returns:
            'code_mutation' if any successful file modification occurred,
            'reflective_only' otherwise
        """
        if not cycle_actions:
            return 'reflective_only'
        
        for action in cycle_actions:
            if self.classify_action(action) == 'code_mutation':
                return 'code_mutation'
        
        return 'reflective_only'
    
    def _extract_action_text(self, action: Dict[str, Any]) -> Optional[str]:
        """Extract the main text content from an action dictionary."""
        # Try common field names
        for field in ['description', 'action', 'type', 'name', 'summary', 'details']:
            if field in action and isinstance(action[field], str):
                return action[field]
        
        # Try nested structures
        if 'metadata' in action and isinstance(action['metadata'], dict):
            for field in ['description', 'action', 'type']:
                if field in action['metadata'] and isinstance(action['metadata'][field], str):
                    return action['metadata'][field]
        
        # Try to stringify the action if it's simple
        if isinstance(action, str):
            return action
        
        return None
    
    def _is_successful(self, action: Dict[str, Any]) -> bool:
        """Check if an action was successful."""
        # Check for explicit success indicators
        status = action.get('status', '').lower()
        if status in ['success', 'successful', 'completed', 'done', 'applied']:
            return True
        
        result = action.get('result', '')
        if isinstance(result, str) and result.lower() in ['success', 'successful']:
            return True
        
        # Check for error indicators
        error = action.get('error', '')
        if error and isinstance(error, str) and error.lower() not in ['', 'none', 'null']:
            return False
        
        # If no explicit status, assume success (optimistic default)
        return True
    
    def get_classification_stats(self, cycle_history: List[List[Dict[str, Any]]]) -> Dict[str, Any]:
        """
        Get statistics about action classifications across multiple cycles.
        
        Args:
            cycle_history: List of cycle action lists
            
        Returns:
            Dictionary with classification statistics
        """
        total_cycles = len(cycle_history)
        code_mutation_cycles = 0
        reflective_only_cycles = 0
        
        for cycle_actions in cycle_history:
            classification = self.classify_cycle_actions(cycle_actions)
            if classification == 'code_mutation':
                code_mutation_cycles += 1
            else:
                reflective_only_cycles += 1
        
        return {
            'total_cycles': total_cycles,
            'code_mutation_cycles': code_mutation_cycles,
            'reflective_only_cycles': reflective_only_cycles,
            'code_mutation_ratio': code_mutation_cycles / max(total_cycles, 1),
            'reflective_only_ratio': reflective_only_cycles / max(total_cycles, 1)
        }

# Singleton instance for easy import
_default_classifier = None

def get_classifier(config_path: Optional[str] = None) -> ActionClassifier:
    """Get or create the default action classifier instance."""
    global _default_classifier
    if _default_classifier is None:
        _default_classifier = ActionClassifier(config_path)
    return _default_classifier

def classify_cycle(cycle_actions: List[Dict[str, Any]], config_path: Optional[str] = None) -> str:
    """
    Convenience function to classify a cycle's actions.
    
    Args:
        cycle_actions: List of action dictionaries from a single evolution cycle
        config_path: Optional path to custom keywords config
        
    Returns:
        'code_mutation' or 'reflective_only'
    """
    classifier = get_classifier(config_path)
    return classifier.classify_cycle_actions(cycle_actions)