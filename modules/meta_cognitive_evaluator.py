"""
Meta-Cognitive Evaluator for Ecological Fitness

This module provides metrics to evaluate the health and effectiveness of the
ecology engine's evolution of the fitness landscape. It measures:
1) Test suite diversity (Shannon entropy of test types)
2) Novelty pressure (number of unseen test types)
3) Adaptation rate (speed of improvement on new test types)
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

    def compute_ecological_fitness(
        self,
        test_types: List[str],
        test_scores: Dict[str, float],
        diversity_weight: float = 0.3,
        novelty_weight: float = 0.3,
        adaptation_weight: float = 0.4
    ) -> Dict[str, float]:
        """
        Compute the overall ecological fitness metric.

        Args:
            test_types: List of test type labels
            test_scores: Dict mapping test_type -> current score
            diversity_weight: Weight for diversity component (default 0.3)
            novelty_weight: Weight for novelty pressure component (default 0.3)
            adaptation_weight: Weight for adaptation rate component (default 0.4)

        Returns:
            Dict with keys:
                - 'ecological_fitness': weighted composite score
                - 'diversity_index': Shannon entropy of test types
                - 'novelty_count': number of novel test types
                - 'novelty_ratio': proportion of novel test types
                - 'mean_adaptation_rate': average adaptation rate across test types
                - 'components': dict of individual component scores
        """
        if not test_types:
            return {
                'ecological_fitness': 0.0,
                'diversity_index': 0.0,
                'novelty_count': 0,
                'novelty_ratio': 0.0,
                'mean_adaptation_rate': 0.0,
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

        # Normalize components to [0, 1] range for combination
        # Diversity: entropy / log2(num_types+1) to normalize
        max_possible_entropy = math.log2(len(set(test_types)) + 1) if test_types else 1.0
        normalized_diversity = diversity_index / max_possible_entropy if max_possible_entropy > 0 else 0.0

        # Novelty: already a ratio [0, 1]
        normalized_novelty = novelty_ratio

        # Adaptation: sigmoid transform to map (-inf, inf) to (0, 1)
        # Positive rates are good, negative are bad
        normalized_adaptation = 1.0 / (1.0 + math.exp(-mean_adaptation_rate))

        # Weighted combination
        ecological_fitness = (
            diversity_weight * normalized_diversity +
            novelty_weight * normalized_novelty +
            adaptation_weight * normalized_adaptation
        )

        return {
            'ecological_fitness': ecological_fitness,
            'diversity_index': diversity_index,
            'novelty_count': novelty_count,
            'novelty_ratio': novelty_ratio,
            'mean_adaptation_rate': mean_adaptation_rate,
            'components': {
                'normalized_diversity': normalized_diversity,
                'normalized_novelty': normalized_novelty,
                'normalized_adaptation': normalized_adaptation,
                'diversity_weight': diversity_weight,
                'novelty_weight': novelty_weight,
                'adaptation_weight': adaptation_weight
            }
        }

    def reset_history(self) -> None:
        """Reset all historical data (for fresh evaluation cycles)."""
        self.history.clear()
        self.seen_test_types.clear()


# Convenience function for quick evaluation
def evaluate_ecological_fitness(
    test_types: List[str],
    test_scores: Dict[str, float],
    evaluator: Optional[EcologicalFitnessEvaluator] = None
) -> Dict[str, float]:
    """
    Quick evaluation of ecological fitness.

    Args:
        test_types: List of test type labels
        test_scores: Dict mapping test_type -> current score
        evaluator: Optional existing evaluator (creates new one if None)

    Returns:
        Dict with ecological fitness metrics
    """
    if evaluator is None:
        evaluator = EcologicalFitnessEvaluator()

    return evaluator.compute_ecological_fitness(test_types, test_scores)