"""
Meta-Cognitive Evaluator for Ecological Fitness

This module provides metrics to evaluate the health and effectiveness of the
ecology engine's evolution of the fitness landscape. It measures:
1) Test suite diversity (Shannon entropy of test types)
2) Novelty pressure (number of unseen test types)
3) Adaptation rate (speed of improvement on new test types)
4) Test suite evolution rate (how many test files were modified or added per cycle)
5) Test diversity (Shannon entropy of test categories: unit, integration, stress, etc.)
"""

import math
from collections import Counter
from typing import Dict, List, Optional, Tuple

class EcologicalFitnessEvaluator:
    """
    Evaluates the ecological fitness of a test suite and agent population.
    Provides feedback on whether the ecology engine is effectively evolving
    the fitness landscape.
    """

    def __init__(self):
        self.history: Dict[str, List[float]] = {}  # test_type -> list of historical scores
        self.seen_test_types: set = set()
        self.test_file_history: List[int] = []  # track number of modified/added test files per cycle

    def compute_diversity_index(self, test_types: List[str]) -> float:
        """
        Compute Shannon entropy of test types as a measure of diversity.
        Higher entropy indicates more diverse test suite.

        Args:
            test_types: List of test type labels

        Returns:
            float: Shannon entropy (0 if no tests or single type)
        """
        if not test_types:
            return 0.0

        counter = Counter(test_types)
        total = len(test_types)
        entropy = 0.0

        for count in counter.values():
            p = count / total
            if p > 0:
                entropy -= p * math.log2(p)

        return entropy

    def compute_novelty_pressure(self, test_types: List[str]) -> Tuple[int, float]:
        """
        Compute how many test types the agent has never seen before.
        Also returns the ratio of novel types to total types.

        Args:
            test_types: List of test type labels from current evaluation

        Returns:
            Tuple[int, float]: (count of novel types, novelty ratio)
        """
        if not test_types:
            return 0, 0.0

        unique_current = set(test_types)
        novel_types = unique_current - self.seen_test_types
        novel_count = len(novel_types)
        novelty_ratio = novel_count / len(unique_current) if unique_current else 0.0

        # Update seen types for future evaluations
        self.seen_test_types.update(unique_current)

        return novel_count, novelty_ratio

    def compute_adaptation_rate(self, test_type: str, current_score: float) -> Optional[float]:
        """
        Compute how quickly the agent improves on a specific test type.
        Returns the rate of improvement (positive = improvement, negative = regression).

        Args:
            test_type: The test type to evaluate
            current_score: The agent's current score on this test type

        Returns:
            Optional[float]: Adaptation rate, or None if insufficient history
        """
        if test_type not in self.history:
            self.history[test_type] = [current_score]
            return None

        scores = self.history[test_type]
        scores.append(current_score)

        if len(scores) < 2:
            return None

        # Calculate rate of change (simple linear regression slope)
        n = len(scores)
        x_mean = (n - 1) / 2.0
        y_mean = sum(scores) / n

        numerator = 0.0
        denominator = 0.0
        for i, score in enumerate(scores):
            x_diff = i - x_mean
            y_diff = score - y_mean
            numerator += x_diff * y_diff
            denominator += x_diff * x_diff

        if denominator == 0:
            return 0.0

        slope = numerator / denominator
        return slope

    def compute_test_suite_evolution_rate(self, num_modified_or_added: int) -> float:
        """
        Track how many test files were modified or added per cycle.
        Returns the rate of change in test file modifications/additions.

        Args:
            num_modified_or_added: Number of test files modified or added in current cycle

        Returns:
            float: Evolution rate (positive = increasing modifications, negative = decreasing)
        """
        self.test_file_history.append(num_modified_or_added)
        
        if len(self.test_file_history) < 2:
            return 0.0
        
        # Calculate rate of change using simple linear regression
        n = len(self.test_file_history)
        x_mean = (n - 1) / 2.0
        y_mean = sum(self.test_file_history) / n
        
        numerator = 0.0
        denominator = 0.0
        for i, count in enumerate(self.test_file_history):
            x_diff = i - x_mean
            y_diff = count - y_mean
            numerator += x_diff * y_diff
            denominator += x_diff * x_diff
        
        if denominator == 0:
            return 0.0
        
        slope = numerator / denominator
        return slope

    def compute_test_diversity(self, test_categories: List[str]) -> float:
        """
        Compute Shannon entropy of test categories (unit, integration, stress, etc.).
        Higher entropy indicates more diverse test categories.

        Args:
            test_categories: List of test category labels

        Returns:
            float: Shannon entropy (0 if no categories or single category)
        """
        if not test_categories:
            return 0.0
        
        counter = Counter(test_categories)
        total = len(test_categories)
        entropy = 0.0
        
        for count in counter.values():
            p = count / total
            if p > 0:
                entropy -= p * math.log2(p)
        
        return entropy

    def compute_ecological_fitness(
        self,
        test_types: List[str],
        test_scores: Dict[str, float],
        test_categories: Optional[List[str]] = None,
        num_modified_or_added: int = 0,
        diversity_weight: float = 0.25,
        novelty_weight: float = 0.25,
        adaptation_weight: float = 0.25,
        evolution_rate_weight: float = 0.15,
        test_diversity_weight: float = 0.10
    ) -> Dict[str, float]:
        """
        Compute the overall ecological fitness metric.

        Args:
            test_types: List of test type labels
            test_scores: Dict mapping test_type -> current score
            test_categories: Optional list of test category labels (unit, integration, stress, etc.)
            num_modified_or_added: Number of test files modified or added in current cycle
            diversity_weight: Weight for diversity component (default 0.25)
            novelty_weight: Weight for novelty pressure component (default 0.25)
            adaptation_weight: Weight for adaptation rate component (default 0.25)
            evolution_rate_weight: Weight for test suite evolution rate (default 0.15)
            test_diversity_weight: Weight for test category diversity (default 0.10)

        Returns:
            Dict with keys:
                - 'ecological_fitness': weighted composite score
                - 'diversity_index': Shannon entropy of test types
                - 'novelty_count': number of novel test types
                - 'novelty_ratio': proportion of novel test types
                - 'mean_adaptation_rate': average adaptation rate across test types
                - 'test_suite_evolution_rate': rate of test file modifications/additions
                - 'test_diversity': Shannon entropy of test categories
                - 'components': dict of individual component scores
        """
        if not test_types:
            return {
                'ecological_fitness': 0.0,
                'diversity_index': 0.0,
                'novelty_count': 0,
                'novelty_ratio': 0.0,
                'mean_adaptation_rate': 0.0,
                'test_suite_evolution_rate': 0.0,
                'test_diversity': 0.0,
                'components': {}
            }

        # 1) Diversity index
        diversity_index = self.compute_diversity_index(test_types)

        # 2) Novelty pressure
        novelty_count, novelty_ratio = self.compute_novelty_pressure(test_types)

        # 3) Adaptation rate (mean across all test types with history)
        adaptation_rates = []
        for test_type in test_types:
            if test_type in test_scores:
                rate = self.compute_adaptation_rate(test_type, test_scores[test_type])
                if rate is not None:
                    adaptation_rates.append(rate)

        mean_adaptation_rate = sum(adaptation_rates) / len(adaptation_rates) if adaptation_rates else 0.0

        # 4) Test suite evolution rate
        test_suite_evolution_rate = self.compute_test_suite_evolution_rate(num_modified_or_added)

        # 5) Test diversity (categories)
        if test_categories is None:
            test_categories = test_types  # fallback to test types if no categories provided
        test_diversity = self.compute_test_diversity(test_categories)

        # Normalize components to [0, 1] range for combination
        # Diversity: entropy / log2(num_types+1) to normalize
        max_possible_entropy = math.log2(len(set(test_types)) + 1) if test_types else 1.0
        normalized_diversity = diversity_index / max_possible_entropy if max_possible_entropy > 0 else 0.0

        # Novelty: already a ratio [0, 1]
        normalized_novelty = novelty_ratio

        # Adaptation: sigmoid transform to map (-inf, inf) to (0, 1)
        # Positive rates are good, negative are bad
        normalized_adaptation = 1.0 / (1.0 + math.exp(-mean_adaptation_rate))

        # Test suite evolution rate: sigmoid transform to map (-inf, inf) to (0, 1)
        normalized_evolution_rate = 1.0 / (1.0 + math.exp(-test_suite_evolution_rate))

        # Test diversity: entropy / log2(num_categories+1) to normalize
        if test_categories:
            max_possible_category_entropy = math.log2(len(set(test_categories)) + 1)
            normalized_test_diversity = test_diversity / max_possible_category_entropy if max_possible_category_entropy > 0 else 0.0
        else:
            normalized_test_diversity = 0.0

        # Weighted combination
        ecological_fitness = (
            diversity_weight * normalized_diversity +
            novelty_weight * normalized_novelty +
            adaptation_weight * normalized_adaptation +
            evolution_rate_weight * normalized_evolution_rate +
            test_diversity_weight * normalized_test_diversity
        )

        return {
            'ecological_fitness': ecological_fitness,
            'diversity_index': diversity_index,
            'novelty_count': novelty_count,
            'novelty_ratio': novelty_ratio,
            'mean_adaptation_rate': mean_adaptation_rate,
            'test_suite_evolution_rate': test_suite_evolution_rate,
            'test_diversity': test_diversity,
            'components': {
                'normalized_diversity': normalized_diversity,
                'normalized_novelty': normalized_novelty,
                'normalized_adaptation': normalized_adaptation,
                'normalized_evolution_rate': normalized_evolution_rate,
                'normalized_test_diversity': normalized_test_diversity,
                'diversity_weight': diversity_weight,
                'novelty_weight': novelty_weight,
                'adaptation_weight': adaptation_weight,
                'evolution_rate_weight': evolution_rate_weight,
                'test_diversity_weight': test_diversity_weight
            }
        }

    def reset_history(self) -> None:
        """Reset all historical data (for fresh evaluation cycles)."""
        self.history.clear()
        self.seen_test_types.clear()
        self.test_file_history.clear()


# Convenience function for quick evaluation
def evaluate_ecological_fitness(
    test_types: List[str],
    test_scores: Dict[str, float],
    test_categories: Optional[List[str]] = None,
    num_modified_or_added: int = 0,
    evaluator: Optional[EcologicalFitnessEvaluator] = None
) -> Dict[str, float]:
    """
    Quick evaluation of ecological fitness.

    Args:
        test_types: List of test type labels
        test_scores: Dict mapping test_type -> current score
        test_categories: Optional list of test category labels
        num_modified_or_added: Number of test files modified or added in current cycle
        evaluator: Optional existing evaluator (creates new one if None)

    Returns:
        Dict with ecological fitness metrics
    """
    if evaluator is None:
        evaluator = EcologicalFitnessEvaluator()

    return evaluator.compute_ecological_fitness(
        test_types, 
        test_scores, 
        test_categories=test_categories,
        num_modified_or_added=num_modified_or_added
    )