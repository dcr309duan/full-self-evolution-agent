import json
import os
import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime

# Database file path
SUCCESS_DB_FILE = "goal_success_db.json"

# Default success rates for goal types
DEFAULT_SUCCESS_RATES = {
    "API server": 0.85,
    "mutation engine": 0.70,
    "data pipeline": 0.75,
    "web scraper": 0.80,
    "machine learning model": 0.60,
    "database schema": 0.90,
}

# Required capabilities per goal type
REQUIRED_CAPABILITIES = {
    "API server": ["http_handling", "routing", "authentication", "error_handling", "logging"],
    "mutation engine": ["data_transformation", "schema_validation", "state_management", "error_handling", "logging"],
    "data pipeline": ["data_ingestion", "data_transformation", "data_storage", "error_handling", "monitoring"],
    "web scraper": ["http_requests", "html_parsing", "rate_limiting", "error_handling", "data_extraction"],
    "machine learning model": ["data_processing", "model_training", "model_evaluation", "inference", "logging"],
    "database schema": ["schema_design", "migration_management", "query_optimization", "error_handling", "logging"],
}

# Keywords to goal type mapping
GOAL_TYPE_KEYWORDS = {
    "API server": ["api", "rest", "endpoint", "server", "service"],
    "mutation engine": ["mutation", "transform", "operator", "engine"],
    "data pipeline": ["pipeline", "etl", "data flow", "stream"],
    "web scraper": ["scrape", "crawl", "extract", "web"],
    "machine learning model": ["ml", "model", "train", "predict", "learn"],
    "database schema": ["schema", "database", "table", "migration"],
}


@dataclass
class GoalFeasibilityResult:
    """Result of goal feasibility estimation."""
    decision: str  # 'proceed', 'adjust_complexity', 'block'
    success_probability: float
    capability_overlap: float
    historical_success_rate: float
    missing_capabilities: List[str]
    explanation: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class GoalFeasibilityEstimator:
    """Estimates feasibility of achieving a goal based on capabilities and historical data."""

    def __init__(self, db_path: str = SUCCESS_DB_FILE):
        self.db_path = db_path
        self.success_rates = self._load_success_rates()

    def _load_success_rates(self) -> Dict[str, float]:
        """Load success rates from database file, falling back to defaults."""
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, 'r') as f:
                    data = json.load(f)
                    # Merge with defaults to ensure all goal types are present
                    merged = DEFAULT_SUCCESS_RATES.copy()
                    merged.update(data)
                    return merged
            except (json.JSONDecodeError, IOError):
                return DEFAULT_SUCCESS_RATES.copy()
        return DEFAULT_SUCCESS_RATES.copy()

    def _save_success_rates(self):
        """Save current success rates to database file."""
        try:
            with open(self.db_path, 'w') as f:
                json.dump(self.success_rates, f, indent=2)
        except IOError:
            # Silently fail if cannot write; data persists in memory
            pass

    def parse_goal_type(self, goal_description: str) -> Optional[str]:
        """Parse goal type from goal description using keyword matching."""
        goal_lower = goal_description.lower()
        
        # Check for exact matches first
        for goal_type, keywords in GOAL_TYPE_KEYWORDS.items():
            for keyword in keywords:
                if keyword in goal_lower:
                    return goal_type
        
        # Try pattern matching for common variations
        patterns = {
            "API server": r'\b(api|rest)\s*(server|service|endpoint)\b',
            "mutation engine": r'\bmutation\s*(engine|operator|tool)\b',
            "data pipeline": r'\b(data|etl)\s*(pipeline|flow|stream)\b',
            "web scraper": r'\b(web|data)\s*(scrape|crawl|extract)\b',
            "machine learning model": r'\b(machine learning|ml|predictive)\s*(model|system)\b',
            "database schema": r'\b(database|db|data)\s*(schema|migration|design)\b',
        }
        
        for goal_type, pattern in patterns.items():
            if re.search(pattern, goal_lower):
                return goal_type
        
        return None

    def compute_capability_overlap(self, goal_type: str, current_capabilities: List[str]) -> Tuple[float, List[str]]:
        """Compute capability overlap score and return missing capabilities."""
        required = self.get_required_capabilities(goal_type)
        if not required:
            return 0.0, []
        
        current_set = set(c.lower() for c in current_capabilities)
        required_set = set(c.lower() for c in required)
        overlap = current_set & required_set
        missing = list(required_set - current_set)
        overlap_score = len(overlap) / len(required_set) if required_set else 0.0
        
        return overlap_score, missing

    def update_success_rate(self, goal_type: str, success: bool):
        """Update the success rate for a goal type based on outcome."""
        current_rate = self.success_rates.get(goal_type, 0.5)
        # Simple moving average update with weight 0.1 for new observation
        new_rate = current_rate * 0.9 + (1.0 if success else 0.0) * 0.1
        self.success_rates[goal_type] = round(new_rate, 4)
        self._save_success_rates()

    def get_required_capabilities(self, goal_type: str) -> List[str]:
        """Get list of required capabilities for a goal type."""
        return REQUIRED_CAPABILITIES.get(goal_type, [])

    def adjust_complexity(self, goal: str, probability: float) -> str:
        """Return a modified goal with reduced scope based on probability."""
        goal_lower = goal.lower()
        
        # API server adjustments
        if any(kw in goal_lower for kw in GOAL_TYPE_KEYWORDS["API server"]):
            if probability < 0.5:
                return "Create a simple API server with 1-2 endpoints and basic authentication"
            elif probability < 0.7:
                return "Create an API server with 3-5 endpoints and authentication"
            else:
                return "Create a full API server with all endpoints and advanced features"
        
        # Mutation engine adjustments
        elif any(kw in goal_lower for kw in GOAL_TYPE_KEYWORDS["mutation engine"]):
            if probability < 0.5:
                return "Create a mutation engine with basic operators (insert, delete, update)"
            elif probability < 0.7:
                return "Create a mutation engine with standard operators and validation"
            else:
                return "Create a full mutation engine with all operators and state management"
        
        # Data pipeline adjustments
        elif any(kw in goal_lower for kw in GOAL_TYPE_KEYWORDS["data pipeline"]):
            if probability < 0.5:
                return "Create a simple data pipeline with single source and destination"
            elif probability < 0.7:
                return "Create a data pipeline with multiple sources and transformations"
            else:
                return "Create a full data pipeline with monitoring and error handling"
        
        # Web scraper adjustments
        elif any(kw in goal_lower for kw in GOAL_TYPE_KEYWORDS["web scraper"]):
            if probability < 0.5:
                return "Create a web scraper for a single page with basic extraction"
            elif probability < 0.7:
                return "Create a web scraper for multiple pages with rate limiting"
            else:
                return "Create a full web scraper with advanced features and error handling"
        
        # Machine learning model adjustments
        elif any(kw in goal_lower for kw in GOAL_TYPE_KEYWORDS["machine learning model"]):
            if probability < 0.5:
                return "Create a simple ML model with basic features and linear regression"
            elif probability < 0.7:
                return "Create an ML model with feature engineering and ensemble methods"
            else:
                return "Create a full ML model with advanced algorithms and optimization"
        
        # Database schema adjustments
        elif any(kw in goal_lower for kw in GOAL_TYPE_KEYWORDS["database schema"]):
            if probability < 0.5:
                return "Create a simple database schema with 2-3 tables"
            elif probability < 0.7:
                return "Create a database schema with 5-8 tables and relationships"
            else:
                return "Create a full database schema with migrations and optimization"
        
        # Default adjustment
        if probability < 0.5:
            return f"Simplified version of: {goal}"
        elif probability < 0.7:
            return f"Standard version of: {goal}"
        else:
            return goal

    def estimate_feasibility(
        self,
        goal_type: str,
        current_capabilities: List[str],
        complexity_level: str = "medium"
    ) -> GoalFeasibilityResult:
        """
        Estimate feasibility of achieving a goal given current capabilities.

        Args:
            goal_type: Type of goal (e.g., 'API server')
            current_capabilities: List of capabilities the system currently has
            complexity_level: 'low', 'medium', or 'high'

        Returns:
            GoalFeasibilityResult with decision and explanation
        """
        required = self.get_required_capabilities(goal_type)
        if not required:
            return GoalFeasibilityResult(
                decision="block",
                success_probability=0.0,
                capability_overlap=0.0,
                historical_success_rate=0.0,
                missing_capabilities=[],
                explanation=f"Unknown goal type: '{goal_type}'. Cannot estimate feasibility."
            )

        # Compute capability overlap
        current_set = set(c.lower() for c in current_capabilities)
        required_set = set(c.lower() for c in required)
        overlap = current_set & required_set
        missing = list(required_set - current_set)
        capability_overlap = len(overlap) / len(required_set) if required_set else 0.0

        # Get historical success rate
        historical_rate = self.success_rates.get(goal_type, 0.5)

        # Complexity adjustment
        complexity_penalty = {"low": 0.0, "medium": 0.1, "high": 0.25}.get(complexity_level, 0.1)

        # Estimate success probability
        # Weight: 60% capability overlap, 40% historical rate, minus complexity penalty
        success_probability = (0.6 * capability_overlap + 0.4 * historical_rate) * (1 - complexity_penalty)
        success_probability = max(0.0, min(1.0, success_probability))

        # Decision logic
        if success_probability >= 0.75:
            decision = "proceed"
            explanation = (
                f"High feasibility ({success_probability:.0%}): "
                f"Capability overlap {capability_overlap:.0%}, "
                f"historical success rate {historical_rate:.0%}."
            )
        elif success_probability >= 0.45:
            decision = "adjust_complexity"
            explanation = (
                f"Moderate feasibility ({success_probability:.0%}): "
                f"Consider reducing complexity or acquiring missing capabilities: {', '.join(missing)}. "
                f"Capability overlap {capability_overlap:.0%}, "
                f"historical success rate {historical_rate:.0%}."
            )
        else:
            decision = "block"
            explanation = (
                f"Low feasibility ({success_probability:.0%}): "
                f"Significant capability gaps: {', '.join(missing)}. "
                f"Capability overlap {capability_overlap:.0%}, "
                f"historical success rate {historical_rate:.0%}. "
                f"Consider alternative goal or acquire necessary capabilities first."
            )

        return GoalFeasibilityResult(
            decision=decision,
            success_probability=round(success_probability, 4),
            capability_overlap=round(capability_overlap, 4),
            historical_success_rate=round(historical_rate, 4),
            missing_capabilities=missing,
            explanation=explanation
        )

    def get_all_goal_types(self) -> List[str]:
        """Return list of all known goal types."""
        return list(REQUIRED_CAPABILITIES.keys())

    def get_success_rates(self) -> Dict[str, float]:
        """Return current success rates for all goal types."""
        return self.success_rates.copy()


# Convenience function for quick estimation
def estimate_goal_feasibility(
    goal_type: str,
    current_capabilities: List[str],
    complexity_level: str = "medium",
    db_path: str = SUCCESS_DB_FILE
) -> GoalFeasibilityResult:
    """Quick one-shot feasibility estimation."""
    estimator = GoalFeasibilityEstimator(db_path)
    return estimator.estimate_feasibility(goal_type, current_capabilities, complexity_level)


# Example usage (if run as script)
if __name__ == "__main__":
    # Example: estimate feasibility of building an API server
    capabilities = ["http_handling", "routing", "logging"]
    result = estimate_goal_feasibility("API server", capabilities, complexity_level="medium")
    print(f"Decision: {result.decision}")
    print(f"Success probability: {result.success_probability:.2%}")
    print(f"Explanation: {result.explanation}")

    # Update success rate after attempt
    estimator = GoalFeasibilityEstimator()
    estimator.update_success_rate("API server", success=True)
    print(f"Updated success rate for API server: {estimator.success_rates['API server']:.2%}")

    # Test new functionality
    print("\n--- Testing new functionality ---")
    
    # Test parse_goal_type
    test_descriptions = [
        "Build a REST API server with authentication",
        "Create a mutation engine for data transformation",
        "Develop a web scraper for e-commerce sites",
        "Train a machine learning model for predictions",
        "Design a database schema for user management",
        "Unknown goal type"
    ]
    
    for desc in test_descriptions:
        goal_type = estimator.parse_goal_type(desc)
        print(f"Description: '{desc}' -> Goal type: {goal_type}")
    
    # Test compute_capability_overlap
    current_caps = ["http_handling", "routing", "logging", "data_transformation"]
    overlap_score, missing = estimator.compute_capability_overlap("API server", current_caps)
    print(f"\nCapability overlap for API server: {overlap_score:.2%}")
    print(f"Missing capabilities: {missing}")
    
    # Test adjust_complexity
    test_goals = [
        ("Build a REST API server", 0.4),
        ("Build a REST API server", 0.6),
        ("Build a REST API server", 0.8),
        ("Create a mutation engine", 0.3),
        ("Create a mutation engine", 0.7),
    ]
    
    print("\nComplexity adjustments:")
    for goal, prob in test_goals:
        adjusted = estimator.adjust_complexity(goal, prob)
        print(f"Original: '{goal}' (prob={prob:.1%}) -> Adjusted: '{adjusted}'")