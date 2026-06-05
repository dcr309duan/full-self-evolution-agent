"""
Module: successful_pattern_extractor.py

Purpose: Enhances the pattern extractor to identify and output 'generalizable_strategies' — 
patterns that transcend the original problem context and can be applied to novel problems. 
This provides higher-quality input to the goal generator.
"""

import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class ExtractedPattern:
    """Represents a single extracted pattern with its generalizability score."""
    pattern_id: str
    description: str
    source_context: str
    generalizable_strategies: List[str] = field(default_factory=list)
    generalizability_score: float = 0.0


class GeneralizablePatternExtractor:
    """
    Extracts patterns from problem-solving contexts and identifies strategies 
    that are generalizable to new problems.
    """

    # Heuristic keywords indicating generalizable strategies
    GENERALIZABLE_KEYWORDS = [
        "decompose", "modularize", "abstract", "generalize",
        "reuse", "refactor", "encapsulate", "parameterize",
        "template", "pattern", "strategy", "algorithm",
        "heuristic", "framework", "methodology", "approach"
    ]

    def __init__(self, min_generalizability_score: float = 0.5):
        self.min_score = min_generalizability_score

    def extract_patterns(self, context: str) -> List[ExtractedPattern]:
        """
        Extract patterns from a given context string.
        Returns a list of ExtractedPattern objects with generalizable strategies.
        """
        patterns = self._parse_patterns(context)
        for pattern in patterns:
            strategies = self._identify_generalizable_strategies(pattern.description)
            pattern.generalizable_strategies = strategies
            pattern.generalizability_score = self._compute_generalizability_score(strategies)
        # Filter by minimum score
        patterns = [p for p in patterns if p.generalizability_score >= self.min_score]
        return patterns

    def _parse_patterns(self, context: str) -> List[ExtractedPattern]:
        """
        Parse the context to extract raw patterns.
        This is a simplified parser; in practice, this could use NLP or structured data.
        """
        patterns = []
        # Simple heuristic: split by pattern markers or numbered lists
        pattern_blocks = re.split(r'\n(?=\d+\.\s|\-\s|\* )', context.strip())
        for idx, block in enumerate(pattern_blocks):
            if not block.strip():
                continue
            pattern = ExtractedPattern(
                pattern_id=f"pattern_{idx+1}",
                description=block.strip(),
                source_context=context[:100]  # Truncated for brevity
            )
            patterns.append(pattern)
        return patterns

    def _identify_generalizable_strategies(self, description: str) -> List[str]:
        """
        Identify generalizable strategies from a pattern description.
        Uses keyword matching and simple heuristics.
        """
        strategies = []
        description_lower = description.lower()
        for keyword in self.GENERALIZABLE_KEYWORDS:
            if keyword in description_lower:
                # Extract the sentence or phrase containing the keyword
                sentences = re.split(r'[.!?]', description)
                for sentence in sentences:
                    if keyword in sentence.lower():
                        strategy = sentence.strip()
                        if strategy and strategy not in strategies:
                            strategies.append(strategy)
        return strategies

    def _compute_generalizability_score(self, strategies: List[str]) -> float:
        """
        Compute a generalizability score based on the number and quality of strategies.
        Score ranges from 0.0 to 1.0.
        """
        if not strategies:
            return 0.0
        # Simple scoring: ratio of strategies to a maximum expected count
        max_expected = 5  # Arbitrary max for normalization
        raw_score = len(strategies) / max_expected
        return min(raw_score, 1.0)

    def extract_generalizable_strategies(self, context: str) -> List[str]:
        """
        Convenience method to directly return only the generalizable strategies
        from a given context.
        """
        patterns = self.extract_patterns(context)
        all_strategies = []
        for pattern in patterns:
            all_strategies.extend(pattern.generalizable_strategies)
        # Remove duplicates while preserving order
        seen = set()
        unique_strategies = []
        for strategy in all_strategies:
            if strategy not in seen:
                seen.add(strategy)
                unique_strategies.append(strategy)
        return unique_strategies


# Example usage (for testing purposes)
if __name__ == "__main__":
    sample_context = """
    1. Decompose the problem into smaller subproblems. This modular approach allows reuse.
    2. Abstract common functionality into a base class. This is a template pattern.
    3. Parameterize the algorithm to handle different data types. This generalizes the solution.
    """
    extractor = GeneralizablePatternExtractor()
    strategies = extractor.extract_generalizable_strategies(sample_context)
    print("Generalizable Strategies:")
    for s in strategies:
        print(f"- {s}")