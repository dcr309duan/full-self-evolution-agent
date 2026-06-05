"""MetaMutationSelector: Analyzes past mutation outcomes and selects the most promising mutation type."""

import random
import math
from collections import defaultdict, Counter
from typing import List, Dict, Tuple, Optional


class MetaMutationSelector:
    """Selects mutation types based on historical performance using a decision forest."""

    def __init__(self, strategies_log: Optional[List[Dict]] = None, health_dashboard: Optional[Dict] = None):
        self.strategies_log = strategies_log or []
        self.health_dashboard = health_dashboard or {}
        self.mutation_stats = defaultdict(lambda: {"count": 0, "successes": 0, "impact_sum": 0.0})
        self.trees = []
        self._build_forest()

    def analyze_last_50_outcomes(self) -> Dict[str, Dict]:
        """Analyze the last 50 mutation outcomes from the strategies log."""
        recent = self.strategies_log[-50:] if len(self.strategies_log) >= 50 else self.strategies_log
        stats = defaultdict(lambda: {"count": 0, "successes": 0, "impact_sum": 0.0})

        for entry in recent:
            mtype = entry.get("mutation_type", "unknown")
            success = entry.get("success", False)
            impact = entry.get("downstream_impact", 0.0)

            stats[mtype]["count"] += 1
            if success:
                stats[mtype]["successes"] += 1
            stats[mtype]["impact_sum"] += impact

        # Compute derived metrics
        result = {}
        for mtype, data in stats.items():
            count = data["count"]
            success_rate = data["successes"] / count if count > 0 else 0.0
            avg_impact = data["impact_sum"] / count if count > 0 else 0.0
            result[mtype] = {
                "count": count,
                "success_rate": success_rate,
                "avg_impact": avg_impact,
                "score": success_rate * avg_impact  # combined metric
            }
        self.mutation_stats = result
        return result

    def _build_forest(self, n_trees: int = 5, subset_size: int = 561):
        """Build a simple ensemble of decision trees on random subsets of strategies."""
        if len(self.strategies_log) < subset_size:
            subset_size = len(self.strategies_log)

        self.trees = []
        for _ in range(n_trees):
            # Random subset with replacement
            subset = random.choices(self.strategies_log, k=subset_size) if self.strategies_log else []
            tree = self._train_simple_tree(subset)
            self.trees.append(tree)

    def _train_simple_tree(self, data: List[Dict]) -> Dict:
        """Train a simple decision tree (dictionary-based) on the given data."""
        # For simplicity, we compute per-mutation-type statistics from the subset
        stats = defaultdict(lambda: {"count": 0, "successes": 0, "impact_sum": 0.0})
        for entry in data:
            mtype = entry.get("mutation_type", "unknown")
            success = entry.get("success", False)
            impact = entry.get("downstream_impact", 0.0)
            stats[mtype]["count"] += 1
            if success:
                stats[mtype]["successes"] += 1
            stats[mtype]["impact_sum"] += impact

        # Convert to scores
        scores = {}
        for mtype, s in stats.items():
            count = s["count"]
            success_rate = s["successes"] / count if count > 0 else 0.0
            avg_impact = s["impact_sum"] / count if count > 0 else 0.0
            scores[mtype] = success_rate * avg_impact
        return scores

    def predict_highest_yield(self) -> str:
        """Return the mutation type with highest expected yield based on forest ensemble."""
        if not self.trees:
            self._build_forest()

        # Check health dashboard lockdown status
        lockdown_active = self.health_dashboard.get("lockdown", False)
        if lockdown_active:
            import logging
            logging.getLogger(__name__).info("Meta-mutation selector paused due to stability lockdown")
            return "none"  # Suppress all mutation suggestions

        # Aggregate votes from all trees
        vote_scores = defaultdict(float)
        for tree in self.trees:
            for mtype, score in tree.items():
                vote_scores[mtype] += score

        if not vote_scores:
            return "schema_alignment"  # default fallback

        # Return type with highest aggregate score
        return max(vote_scores, key=vote_scores.get)

    def bias_mutation_generator(self) -> Dict[str, float]:
        """Inject a weighted preference into the mutation engine based on learned biases."""
        if not self.mutation_stats:
            self.analyze_last_50_outcomes()

        # Check health dashboard lockdown status
        lockdown_active = self.health_dashboard.get("lockdown", False)
        if lockdown_active:
            import logging
            logging.getLogger(__name__).info("Meta-mutation selector paused due to stability lockdown")
            return {"none": 1.0}  # Suppress all mutation suggestions

        # Compute weights proportional to score
        scores = {mtype: data["score"] for mtype, data in self.mutation_stats.items()}
        total = sum(scores.values())
        if total == 0:
            # Uniform distribution as fallback
            n = len(scores) if scores else 1
            return {mtype: 1.0 / n for mtype in scores} if scores else {"schema_alignment": 1.0}

        weights = {mtype: score / total for mtype, score in scores.items()}
        return weights