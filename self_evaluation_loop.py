from typing import Dict, List, Any, Optional
from collections import deque, Counter
import time
import json
from datetime import datetime

class ReflectionParser:
    """
    Parser for processing accumulated reflections and extracting structured information.
    """
    
    def __init__(self):
        self.parsing_rules = {
            'goal_relevance': ['goal', 'objective', 'target', 'purpose'],
            'performance_indicators': ['accuracy', 'efficiency', 'speed', 'quality'],
            'improvement_suggestions': ['improve', 'enhance', 'optimize', 'refactor']
        }
    
    def parse_reflection(self, reflection_text: str) -> Dict[str, Any]:
        """
        Parse a single reflection text and extract structured information.
        
        Args:
            reflection_text: Raw reflection text to parse
            
        Returns:
            Dict containing parsed reflection data
        """
        parsed_data = {
            'goal_relevance_score': 0.0,
            'performance_indicators': [],
            'improvement_suggestions': [],
            'key_phrases': [],
            'sentiment': 'neutral'
        }
        
        # Convert to lowercase for matching
        text_lower = reflection_text.lower()
        
        # Calculate goal relevance score
        relevance_count = sum(1 for keyword in self.parsing_rules['goal_relevance'] 
                            if keyword in text_lower)
        parsed_data['goal_relevance_score'] = min(relevance_count / len(self.parsing_rules['goal_relevance']), 1.0)
        
        # Extract performance indicators
        for indicator in self.parsing_rules['performance_indicators']:
            if indicator in text_lower:
                parsed_data['performance_indicators'].append(indicator)
        
        # Extract improvement suggestions
        for suggestion in self.parsing_rules['improvement_suggestions']:
            if suggestion in text_lower:
                parsed_data['improvement_suggestions'].append(suggestion)
        
        # Extract key phrases (words with more than 5 characters)
        words = reflection_text.split()
        parsed_data['key_phrases'] = [word for word in words if len(word) > 5]
        
        # Simple sentiment analysis based on positive/negative words
        positive_words = ['good', 'great', 'excellent', 'improved', 'successful']
        negative_words = ['bad', 'poor', 'failed', 'worse', 'problem']
        
        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in text_lower)
        
        if positive_count > negative_count:
            parsed_data['sentiment'] = 'positive'
        elif negative_count > positive_count:
            parsed_data['sentiment'] = 'negative'
        else:
            parsed_data['sentiment'] = 'neutral'
        
        return parsed_data

class SelfEvaluationLoop:
    """
    Self-evaluation loop that tracks per-capability scores and improvement rates,
    and reports them to the meta-evaluation loop.
    """

    def __init__(self, history_size: int = 10):
        """
        Initialize the self-evaluation loop.

        Args:
            history_size: Number of recent cycles to track for diversity metrics.
        """
        self.capability_scores: Dict[str, float] = {}
        self.improvement_rates: Dict[str, float] = {}
        self.change_history: deque = deque(maxlen=history_size)
        self.history_size = history_size
        self.cycle_count = 0
        self.reflection_parser = ReflectionParser()
        self.accumulated_reflections: List[Dict[str, Any]] = []
        self.parsed_reflections: List[Dict[str, Any]] = []
        self.reflection_parsing_accuracy: float = 0.0
        self.goal_relevance_score: float = 0.0

    def update_capability_score(self, capability: str, score: float) -> None:
        """
        Update the score for a specific capability.

        Args:
            capability: Name of the capability.
            score: Score value (0-100).
        """
        if not 0 <= score <= 100:
            raise ValueError(f"Score must be between 0 and 100, got {score}")
        old_score = self.capability_scores.get(capability, None)
        self.capability_scores[capability] = score

        # Update improvement rate
        if old_score is not None and old_score != 0:
            improvement = (score - old_score) / old_score
            self.improvement_rates[capability] = improvement
        else:
            self.improvement_rates[capability] = 0.0

    def get_capability_scores(self) -> Dict[str, float]:
        """
        Return a dictionary of capability names to their current scores.

        Returns:
            Dict mapping capability names to scores (0-100).
        """
        return dict(self.capability_scores)

    def get_improvement_rates(self) -> Dict[str, float]:
        """
        Return a dictionary of capability names to their improvement rates.

        Returns:
            Dict mapping capability names to improvement rates (as decimal fractions).
        """
        return dict(self.improvement_rates)

    def record_change(self, change_type: str, details: Optional[Dict[str, Any]] = None) -> None:
        """
        Record a change event for diversity tracking.

        Args:
            change_type: Type of change (e.g., 'parameter_update', 'architecture_change', 'data_augmentation').
            details: Optional additional details about the change.
        """
        self.change_history.append({
            'type': change_type,
            'timestamp': time.time(),
            'details': details or {}
        })
        self.cycle_count += 1

    def get_change_diversity(self) -> int:
        """
        Calculate the diversity of change types in the last N cycles.

        Returns:
            Count of unique change types in the recent history.
        """
        if not self.change_history:
            return 0
        change_types = [entry['type'] for entry in self.change_history]
        return len(set(change_types))

    def get_change_type_counts(self) -> Dict[str, int]:
        """
        Get the frequency of each change type in the recent history.

        Returns:
            Dict mapping change type names to their counts.
        """
        if not self.change_history:
            return {}
        change_types = [entry['type'] for entry in self.change_history]
        return dict(Counter(change_types))

    def add_reflection(self, reflection_text: str) -> None:
        """
        Add a raw reflection to the accumulated reflections list.
        
        Args:
            reflection_text: Raw reflection text to add
        """
        reflection_entry = {
            'raw_text': reflection_text,
            'timestamp': datetime.now().isoformat(),
            'cycle': self.cycle_count
        }
        self.accumulated_reflections.append(reflection_entry)

    def process_accumulated_reflections(self) -> None:
        """
        Process all accumulated reflections through the ReflectionParser
        and store parsed results alongside raw reflections.
        """
        if not self.accumulated_reflections:
            return
        
        successful_parses = 0
        total_reflections = len(self.accumulated_reflections)
        total_goal_relevance = 0.0
        
        for reflection in self.accumulated_reflections:
            try:
                # Parse the reflection
                parsed_data = self.reflection_parser.parse_reflection(reflection['raw_text'])
                
                # Create structured entry with both raw and parsed data
                structured_entry = {
                    'raw_reflection': reflection,
                    'parsed_data': parsed_data,
                    'parsing_timestamp': datetime.now().isoformat(),
                    'cycle': self.cycle_count
                }
                
                self.parsed_reflections.append(structured_entry)
                successful_parses += 1
                total_goal_relevance += parsed_data['goal_relevance_score']
                
            except Exception as e:
                # If parsing fails, store the error with the reflection
                error_entry = {
                    'raw_reflection': reflection,
                    'parsing_error': str(e),
                    'parsing_timestamp': datetime.now().isoformat(),
                    'cycle': self.cycle_count
                }
                self.parsed_reflections.append(error_entry)
        
        # Update evaluation metrics
        if total_reflections > 0:
            self.reflection_parsing_accuracy = successful_parses / total_reflections
            self.goal_relevance_score = total_goal_relevance / total_reflections if successful_parses > 0 else 0.0
        
        # Clear accumulated reflections after processing
        self.accumulated_reflections.clear()

    def get_parsed_reflections(self) -> List[Dict[str, Any]]:
        """
        Get all parsed reflections in structured format.
        
        Returns:
            List of structured reflection entries with raw and parsed data
        """
        return list(self.parsed_reflections)

    def get_reflection_metrics(self) -> Dict[str, float]:
        """
        Get current reflection parsing metrics.
        
        Returns:
            Dict containing reflection_parsing_accuracy and goal_relevance_score
        """
        return {
            'reflection_parsing_accuracy': self.reflection_parsing_accuracy,
            'goal_relevance_score': self.goal_relevance_score
        }

    def report_to_meta_evaluation(self) -> Dict[str, Any]:
        """
        Compile and return a report for the meta-evaluation loop.

        Returns:
            Dict containing capability scores, improvement rates, change diversity,
            and reflection parsing metrics.
        """
        # Process any remaining accumulated reflections before reporting
        self.process_accumulated_reflections()
        
        report = {
            'capability_scores': self.get_capability_scores(),
            'improvement_rates': self.get_improvement_rates(),
            'change_diversity': self.get_change_diversity(),
            'change_type_counts': self.get_change_type_counts(),
            'cycle_count': self.cycle_count,
            'timestamp': time.time(),
            'reflection_metrics': self.get_reflection_metrics(),
            'parsed_reflections_count': len(self.parsed_reflections)
        }
        return report

    def reset_history(self) -> None:
        """Reset the change history and cycle counter, and clear reflections."""
        self.change_history.clear()
        self.cycle_count = 0
        self.accumulated_reflections.clear()
        self.parsed_reflections.clear()
        self.reflection_parsing_accuracy = 0.0
        self.goal_relevance_score = 0.0

    def __repr__(self) -> str:
        return (f"SelfEvaluationLoop(capabilities={list(self.capability_scores.keys())}, "
                f"cycles={self.cycle_count}, diversity={self.get_change_diversity()}, "
                f"parsed_reflections={len(self.parsed_reflections)})")