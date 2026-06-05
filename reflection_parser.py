"""reflection_parser.py

Implements a ReflectionParser class that extracts structured fields from raw reflection text
using regex patterns and lightweight NLP heuristics.
"""

import re
from typing import Dict, List, Optional, Tuple

# Default keyword patterns for each field
DEFAULT_PATTERNS = {
    "current_assessment": [
        r"(?:current|present|overall|general)\s+(?:state|status|situation|condition|assessment)",
        r"(?:system|model|approach)\s+(?:is|are|seems?|appears?)\s+\w+",
        r"(?:we\s+)?(?:are|have|see|observe)\s+(?:a|an|the)?\s*(?:state|condition|situation)",
    ],
    "key_gaps": [
        r"(?:missing|lacking|need|requires?|deficit|shortcoming|limitation|gap)",
        r"(?:not\s+(?:able|capable|sufficient|adequate|present))",
        r"(?:insufficient|inadequate|incomplete|unavailable)",
    ],
    "next_priority": [
        r"(?:should|must|need\s+to|ought\s+to|next\s+(?:step|priority|action))",
        r"(?:priority|critical|essential|important)\s+(?:is|to|action)",
        r"(?:focus|target|aim|goal)\s+(?:on|is|should)",
    ],
    "novel_ideas": [
        r"(?:suggest|consider|propose|recommend|alternative|idea)",
        r"(?:what\s+if|maybe\s+we|could\s+try|perhaps)",
        r"(?:novel|innovative|creative|new\s+approach)",
    ],
}


class ReflectionParser:
    """Parses raw reflection text to extract structured fields with confidence scores."""

    def __init__(self, patterns: Optional[Dict[str, List[str]]] = None):
        """
        Initialize the parser with optional custom regex patterns.

        Args:
            patterns: Dictionary mapping field names to lists of regex patterns.
                      If None, default patterns are used.
        """
        self.patterns = patterns if patterns is not None else DEFAULT_PATTERNS
        self._compiled_patterns = self._compile_patterns()

    def _compile_patterns(self) -> Dict[str, List[re.Pattern]]:
        """Compile all regex patterns for efficiency."""
        compiled = {}
        for field, pattern_list in self.patterns.items():
            compiled[field] = [re.compile(p, re.IGNORECASE) for p in pattern_list]
        return compiled

    def extract_field(self, text: str, field: str) -> List[Tuple[str, float]]:
        """
        Extract matches for a specific field from the text.

        Args:
            text: Raw reflection text.
            field: Field name to extract.

        Returns:
            List of (matched_text, confidence_score) tuples.
        """
        if field not in self._compiled_patterns:
            return []

        matches = []
        for pattern in self._compiled_patterns[field]:
            for match in pattern.finditer(text):
                matched_text = match.group(0).strip()
                # Confidence based on pattern specificity (length and word count)
                words = matched_text.split()
                specificity = len(matched_text) / 100.0 + len(words) / 20.0
                confidence = min(1.0, 0.5 + specificity * 0.1)
                matches.append((matched_text, round(confidence, 2)))

        # Remove duplicates while keeping highest confidence
        seen = {}
        for matched_text, confidence in matches:
            key = matched_text.lower()
            if key not in seen or confidence > seen[key][1]:
                seen[key] = (matched_text, confidence)

        return list(seen.values())

    def parse(self, text: str) -> Dict[str, List[Tuple[str, float]]]:
        """
        Parse the full reflection text and extract all fields.

        Args:
            text: Raw reflection text.

        Returns:
            Dictionary mapping field names to lists of (matched_text, confidence) tuples.
        """
        if not text or not isinstance(text, str):
            return {field: [] for field in self.patterns}

        results = {}
        for field in self.patterns:
            results[field] = self.extract_field(text, field)
        return results

    def get_high_confidence(self, text: str, threshold: float = 0.7) -> Dict[str, List[str]]:
        """
        Extract only high-confidence matches above a threshold.

        Args:
            text: Raw reflection text.
            threshold: Minimum confidence score (0.0 to 1.0).

        Returns:
            Dictionary mapping field names to lists of matched text strings.
        """
        parsed = self.parse(text)
        high_conf = {}
        for field, matches in parsed.items():
            high_conf[field] = [m[0] for m in matches if m[1] >= threshold]
        return high_conf

    def add_custom_pattern(self, field: str, pattern: str) -> None:
        """
        Add a custom regex pattern for a field.

        Args:
            field: Field name to add pattern to.
            pattern: Regex pattern string.
        """
        if field not in self.patterns:
            self.patterns[field] = []
            self._compiled_patterns[field] = []
        self.patterns[field].append(pattern)
        self._compiled_patterns[field].append(re.compile(pattern, re.IGNORECASE))

    def set_patterns(self, patterns: Dict[str, List[str]]) -> None:
        """
        Replace all patterns with a new set.

        Args:
            patterns: New dictionary of field->pattern list mappings.
        """
        self.patterns = patterns
        self._compiled_patterns = self._compile_patterns()


# Example usage (if run as script)
if __name__ == "__main__":
    sample_text = (
        "Current system state is stable but slow. We are missing key data integration. "
        "The next priority should be optimizing the database. Consider using a cache layer. "
        "Perhaps we could try a new approach for error handling."
    )

    parser = ReflectionParser()
    results = parser.parse(sample_text)

    print("=== Full Parsed Results ===")
    for field, matches in results.items():
        print(f"\n{field}:")
        for text, conf in matches:
            print(f"  - '{text}' (confidence: {conf})")

    print("\n=== High Confidence (>= 0.7) ===")
    high_conf = parser.get_high_confidence(sample_text, threshold=0.7)
    for field, matches in high_conf.items():
        print(f"{field}: {matches}")