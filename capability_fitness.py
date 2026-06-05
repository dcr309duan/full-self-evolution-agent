from typing import Dict, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict

class TestFirstComplianceTracker:
    """
    Tracks and calculates the 'test-first compliance score' for modules.
    
    The score measures the percentage of accepted mutations that had a 
    pre-written failing test. This is used to penalize modules that 
    bypass the test-first requirement.
    """
    
    def __init__(self, lookback_days: int = 30):
        """
        Initialize the tracker.
        
        Args:
            lookback_days: Number of days to look back for historical data
        """
        self.lookback_days = lookback_days
        # Structure: {module_id: [(timestamp, had_prewritten_test, accepted)]}
        self.mutation_records: Dict[str, List[tuple]] = defaultdict(list)
        self.compliance_history: Dict[str, List[tuple]] = defaultdict(list)
    
    def record_mutation(self, module_id: str, had_prewritten_test: bool, 
                       accepted: bool, timestamp: Optional[datetime] = None) -> None:
        """
        Record a mutation event for a module.
        
        Args:
            module_id: Identifier for the module
            had_prewritten_test: Whether a failing test was written before the mutation
            accepted: Whether the mutation was accepted
            timestamp: When the event occurred (defaults to now)
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        self.mutation_records[module_id].append((timestamp, had_prewritten_test, accepted))
    
    def calculate_compliance_score(self, module_id: str) -> float:
        """
        Calculate the test-first compliance score for a module.
        
        The score is the percentage of accepted mutations that had a 
        pre-written failing test, considering only records within the 
        lookback window.
        
        Args:
            module_id: Identifier for the module
            
        Returns:
            Float between 0.0 and 1.0 representing compliance score
        """
        cutoff = datetime.now() - timedelta(days=self.lookback_days)
        records = self.mutation_records.get(module_id, [])
        
        # Filter to accepted mutations within lookback window
        accepted_mutations = [
            (ts, had_test) for ts, had_test, accepted in records
            if accepted and ts >= cutoff
        ]
        
        if not accepted_mutations:
            return 1.0  # No accepted mutations means no violation
        
        compliant_count = sum(1 for _, had_test in accepted_mutations if had_test)
        return compliant_count / len(accepted_mutations)
    
    def get_penalty_factor(self, module_id: str, max_penalty: float = 0.5) -> float:
        """
        Calculate a penalty factor based on compliance score.
        
        Args:
            module_id: Identifier for the module
            max_penalty: Maximum penalty factor (0.0 to 1.0)
            
        Returns:
            Float between 0.0 and max_penalty representing the penalty
        """
        score = self.calculate_compliance_score(module_id)
        # Penalty increases as score decreases below 1.0
        return max_penalty * (1.0 - score)
    
    def get_compliance_trend(self, module_id: str, 
                            window_days: int = 7) -> List[tuple]:
        """
        Get compliance scores over time for trend analysis.
        
        Args:
            module_id: Identifier for the module
            window_days: Size of each time window for averaging
            
        Returns:
            List of (timestamp, score) tuples sorted chronologically
        """
        records = self.mutation_records.get(module_id, [])
        if not records:
            return []
        
        sorted_records = sorted(records, key=lambda x: x[0])
        
        # Group records into windows
        start_time = sorted_records[0][0]
        end_time = sorted_records[-1][0]
        
        trends = []
        current_window_start = start_time
        while current_window_start <= end_time:
            window_end = current_window_start + timedelta(days=window_days)
            
            window_records = [
                r for r in sorted_records
                if current_window_start <= r[0] < window_end
            ]
            
            accepted = [(ts, had_test) for ts, had_test, acc in window_records if acc]
            if accepted:
                score = sum(1 for _, had_test in accepted if had_test) / len(accepted)
                trends.append((current_window_start + timedelta(days=window_days/2), score))
            
            current_window_start = window_end
        
        return trends
    
    def get_module_summary(self, module_id: str) -> Dict:
        """
        Get a comprehensive summary for a module.
        
        Args:
            module_id: Identifier for the module
            
        Returns:
            Dictionary with compliance metrics
        """
        score = self.calculate_compliance_score(module_id)
        penalty = self.get_penalty_factor(module_id)
        trends = self.get_compliance_trend(module_id)
        
        records = self.mutation_records.get(module_id, [])
        total_accepted = sum(1 for _, _, acc in records if acc)
        total_compliant = sum(1 for _, test, acc in records if acc and test)
        
        return {
            "module_id": module_id,
            "compliance_score": score,
            "penalty_factor": penalty,
            "total_accepted_mutations": total_accepted,
            "compliant_mutations": total_compliant,
            "trend_data_points": len(trends),
            "current_trend": trends[-1][1] if trends else None
        }


class CapabilityFitness:
    """
    Main class for capability fitness evaluation including test-first compliance.
    """
    
    def __init__(self):
        self.compliance_tracker = TestFirstComplianceTracker()
        self.module_fitness_scores: Dict[str, float] = {}
    
    def evaluate_module(self, module_id: str, base_fitness: float = 1.0) -> float:
        """
        Evaluate a module's overall fitness, applying test-first compliance penalty.
        
        Args:
            module_id: Identifier for the module
            base_fitness: Base fitness score before penalty
            
        Returns:
            Adjusted fitness score after applying compliance penalty
        """
        penalty = self.compliance_tracker.get_penalty_factor(module_id)
        adjusted_fitness = base_fitness * (1.0 - penalty)
        self.module_fitness_scores[module_id] = adjusted_fitness
        return adjusted_fitness
    
    def get_all_module_scores(self) -> Dict[str, float]:
        """Get all current module fitness scores."""
        return dict(self.module_fitness_scores)
    
    def reset(self) -> None:
        """Reset all tracking data."""
        self.compliance_tracker = TestFirstComplianceTracker()
        self.module_fitness_scores.clear()


# Convenience functions for quick access
_default_tracker = TestFirstComplianceTracker()

def record_mutation(module_id: str, had_prewritten_test: bool, accepted: bool) -> None:
    """Quick function to record a mutation using the default tracker."""
    _default_tracker.record_mutation(module_id, had_prewritten_test, accepted)

def get_compliance_score(module_id: str) -> float:
    """Quick function to get compliance score from default tracker."""
    return _default_tracker.calculate_compliance_score(module_id)

def get_penalty(module_id: str) -> float:
    """Quick function to get penalty from default tracker."""
    return _default_tracker.get_penalty_factor(module_id)