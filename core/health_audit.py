import json
import os
from typing import List, Tuple, Dict, Any
from datetime import datetime, timedelta

# Assuming a schema checker module exists for interface alignment scoring
# from core.schema_checker import calculate_interface_alignment


class SystemHealthAudit:
    """
    Audits system capabilities and computes health scores across multiple dimensions:
    novelty, necessity, and integration.
    """

    def __init__(self, capabilities: List[Dict[str, Any]], scores_file: str = "health_scores.json"):
        """
        Initialize the audit with a list of capabilities.

        Args:
            capabilities: List of capability dictionaries, each containing:
                - 'name': str
                - 'last_modified': datetime or ISO string
                - 'dependents': int
                - 'interface_alignment_score': float (0-1)
            scores_file: Path to JSON file for persisting scores.
        """
        self.capabilities = capabilities
        self.scores_file = scores_file
        self.scores = self._load_scores()

    def _load_scores(self) -> Dict[str, Dict[str, float]]:
        """Load persisted scores from JSON file, or return empty dict."""
        if os.path.exists(self.scores_file):
            try:
                with open(self.scores_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}

    def _save_scores(self):
        """Persist current scores to JSON file."""
        with open(self.scores_file, 'w') as f:
            json.dump(self.scores, f, indent=2)

    def score_capability(self, cap_name: str) -> float:
        """
        Score a single capability across three dimensions (0-1 each).

        Returns:
            A composite score (average of three dimensions), or 0.0 if capability not found.
        """
        cap = next((c for c in self.capabilities if c.get('name') == cap_name), None)
        if not cap:
            return 0.0

        # Novelty: 1.0 if modified within last 30 days, decreasing linearly
        last_mod = cap.get('last_modified')
        if isinstance(last_mod, str):
            last_mod = datetime.fromisoformat(last_mod)
        if last_mod:
            days_since = (datetime.now() - last_mod).days
            novelty = min(1.0, days_since / 30.0)
        else:
            novelty = 0.0

        # Necessity: 1.0 if 5 or more dependents
        dependents = cap.get('dependents', 0)
        necessity = min(1.0, dependents / 5.0)

        # Integration: use interface alignment score (assumed 0-1)
        integration = cap.get('interface_alignment_score', 0.0)

        # Store individual dimension scores
        self.scores[cap_name] = {
            'novelty': novelty,
            'necessity': necessity,
            'integration': integration
        }
        self._save_scores()

        # Return composite (average)
        return (novelty + necessity + integration) / 3.0

    def compute_average_score(self) -> float:
        """
        Compute the average composite score across all capabilities.

        Returns:
            Average score (0-1), or 0.0 if no capabilities.
        """
        if not self.capabilities:
            return 0.0

        total = 0.0
        count = 0
        for cap in self.capabilities:
            name = cap.get('name')
            if name:
                total += self.score_capability(name)
                count += 1

        return total / count if count > 0 else 0.0

    def identify_bottom_10_percent(self) -> List[str]:
        """
        Identify capabilities in the bottom 10% by composite score.

        Returns:
            List of capability names in the bottom 10%.
        """
        if not self.capabilities:
            return []

        # Score all capabilities
        scored = []
        for cap in self.capabilities:
            name = cap.get('name')
            if name:
                score = self.score_capability(name)
                scored.append((name, score))

        if not scored:
            return []

        # Sort by score ascending
        scored.sort(key=lambda x: x[1])

        # Bottom 10% (at least 1)
        threshold = max(1, len(scored) // 10)
        return [name for name, _ in scored[:threshold]]

    def merge_duplicates(self) -> List[Tuple[str, str]]:
        """
        Merge duplicate capabilities based on name similarity (case-insensitive exact match).

        Returns:
            List of tuples (kept_name, removed_name) for each merge performed.
        """
        merged_pairs = []
        seen = {}
        to_remove = []

        for cap in self.capabilities:
            name = cap.get('name', '')
            normalized = name.lower().strip()
            if normalized in seen:
                # Merge: keep the one with higher composite score
                existing = seen[normalized]
                existing_score = self.score_capability(existing['name'])
                current_score = self.score_capability(name)

                if current_score > existing_score:
                    # Swap: current becomes the kept one
                    merged_pairs.append((name, existing['name']))
                    to_remove.append(existing)
                    seen[normalized] = cap
                else:
                    merged_pairs.append((existing['name'], name))
                    to_remove.append(cap)
            else:
                seen[normalized] = cap

        # Remove duplicates from capabilities list
        for cap in to_remove:
            if cap in self.capabilities:
                self.capabilities.remove(cap)

        # Clean up scores for removed capabilities
        for _, removed_name in merged_pairs:
            if removed_name in self.scores:
                del self.scores[removed_name]
        self._save_scores()

        return merged_pairs