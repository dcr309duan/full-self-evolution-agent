"""Reflection parser module for analyzing failures and generating root cause hypotheses.

This module provides functionality to parse reflection data, categorize failures,
generate root cause hypotheses, and track analysis history for continuous learning.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
from datetime import datetime
import uuid


class FailureCategory(Enum):
    """Enumeration of possible failure categories."""
    TIMEOUT = "timeout"
    MEMORY = "memory"
    LOGIC = "logic"
    SYNTAX = "syntax"
    DEPENDENCY = "dependency"
    PERMISSION = "permission"
    NETWORK = "network"
    DATA = "data"
    UNKNOWN = "unknown"


@dataclass
class RootCauseHypothesis:
    """Represents a generated root cause hypothesis."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    category: FailureCategory
    description: str
    confidence: float = 0.0
    evidence: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    validated: bool = False
    resolution_attempted: bool = False


@dataclass
class AnalysisRecord:
    """Tracks analysis of a specific failure category."""
    category: FailureCategory
    analyzed_at: datetime = field(default_factory=datetime.utcnow)
    hypotheses: List[RootCauseHypothesis] = field(default_factory=list)
    resolved: bool = False
    notes: str = ""


@dataclass
class CapabilityFitness:
    """Represents fitness scores and deprecation events for capabilities."""
    top_5_capabilities: List[Dict[str, Any]] = field(default_factory=list)
    bottom_5_capabilities: List[Dict[str, Any]] = field(default_factory=list)
    deprecation_events: List[str] = field(default_factory=list)
    merge_suggestions: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ReflectionOutput:
    """Output schema for reflection parsing with failure categories."""
    reflection_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)
    failure_categories: List[FailureCategory] = field(default_factory=list)
    root_cause_hypotheses: List[RootCauseHypothesis] = field(default_factory=list)
    analysis_history: Dict[FailureCategory, AnalysisRecord] = field(default_factory=dict)
    raw_reflection: Optional[str] = None
    summary: str = ""
    schema_version: str = "1.0.0"
    capability_fitness: Optional[CapabilityFitness] = None


class ReflectionParser:
    """Parser for reflection data that generates failure categories and hypotheses."""

    def __init__(self):
        self._analysis_history: Dict[FailureCategory, AnalysisRecord] = {}
        self._hypothesis_history: List[RootCauseHypothesis] = []
        self._capability_fitness_history: Dict[str, float] = {}
        self._deprecation_events: List[str] = []
        self._downstream_usage_patterns: Dict[str, List[str]] = {}

    def parse_reflection(self, reflection_text: str, context: Optional[Dict[str, Any]] = None) -> ReflectionOutput:
        """Parse a reflection text and generate failure categories and hypotheses.

        Args:
            reflection_text: The raw reflection text to analyze.
            context: Optional contextual information to aid analysis.

        Returns:
            A ReflectionOutput object containing parsed data.
        """
        categories = self._extract_failure_categories(reflection_text, context)
        hypotheses = self._generate_hypotheses(categories, reflection_text, context)

        # Generate capability fitness section
        capability_fitness = self._generate_capability_fitness(reflection_text, context)

        output = ReflectionOutput(
            failure_categories=categories,
            root_cause_hypotheses=hypotheses,
            raw_reflection=reflection_text,
            summary=self._generate_summary(categories, hypotheses),
            capability_fitness=capability_fitness
        )

        # Update tracking
        self._update_analysis_history(categories, hypotheses)
        self._hypothesis_history.extend(hypotheses)

        # Self-validate output against canonical reflection schema
        self._validate_output(output)

        return output

    def _generate_capability_fitness(self, text: str, context: Optional[Dict[str, Any]] = None) -> CapabilityFitness:
        """Generate capability fitness section with top/bottom scores, deprecation events, and merge suggestions.

        Args:
            text: The reflection text to analyze.
            context: Optional contextual information.

        Returns:
            A CapabilityFitness object.
        """
        # Simulate capability fitness scores (in real implementation, these would come from a capability tracking system)
        capability_scores = self._get_capability_scores(text, context)
        
        # Sort capabilities by fitness score
        sorted_capabilities = sorted(capability_scores.items(), key=lambda x: x[1], reverse=True)
        
        # Get top 5 and bottom 5 capabilities
        top_5 = [{"name": name, "score": score} for name, score in sorted_capabilities[:5]]
        bottom_5 = [{"name": name, "score": score} for name, score in sorted_capabilities[-5:]]
        
        # Get deprecation events since last reflection
        deprecation_events = self._get_deprecation_events(text, context)
        
        # Get merge suggestions based on overlapping downstream usage patterns
        merge_suggestions = self._get_merge_suggestions(text, context)
        
        return CapabilityFitness(
            top_5_capabilities=top_5,
            bottom_5_capabilities=bottom_5,
            deprecation_events=deprecation_events,
            merge_suggestions=merge_suggestions
        )

    def _get_capability_scores(self, text: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, float]:
        """Get capability fitness scores from the system.

        Args:
            text: The reflection text.
            context: Optional contextual information.

        Returns:
            Dictionary mapping capability names to fitness scores.
        """
        # In a real implementation, this would query a capability tracking system
        # For now, we simulate with some default capabilities and scores
        default_capabilities = {
            "data_processing": 0.85,
            "api_integration": 0.72,
            "error_handling": 0.91,
            "logging": 0.65,
            "authentication": 0.78,
            "caching": 0.43,
            "validation": 0.88,
            "serialization": 0.59,
            "monitoring": 0.37,
            "configuration": 0.81,
            "rate_limiting": 0.52,
            "retry_logic": 0.74,
            "circuit_breaker": 0.29,
            "health_check": 0.68,
            "metrics_collection": 0.45
        }
        
        # Update with any historical data
        for cap, score in self._capability_fitness_history.items():
            if cap in default_capabilities:
                default_capabilities[cap] = score
        
        # Simulate some variation based on reflection text
        if "timeout" in text.lower():
            default_capabilities["retry_logic"] = max(0.0, default_capabilities["retry_logic"] - 0.1)
            default_capabilities["circuit_breaker"] = max(0.0, default_capabilities["circuit_breaker"] - 0.05)
        
        if "memory" in text.lower():
            default_capabilities["caching"] = max(0.0, default_capabilities["caching"] - 0.15)
            default_capabilities["data_processing"] = max(0.0, default_capabilities["data_processing"] - 0.08)
        
        return default_capabilities

    def _get_deprecation_events(self, text: str, context: Optional[Dict[str, Any]] = None) -> List[str]:
        """Get deprecation events since last reflection.

        Args:
            text: The reflection text.
            context: Optional contextual information.

        Returns:
            List of deprecation event descriptions.
        """
        # In a real implementation, this would query a deprecation tracking system
        # For now, we simulate based on reflection text
        events = []
        
        # Check for deprecation indicators in the text
        deprecation_keywords = ["deprecated", "obsolete", "removed", "replaced", "no longer supported"]
        for keyword in deprecation_keywords:
            if keyword in text.lower():
                events.append(f"Deprecation detected: '{keyword}' mentioned in reflection")
        
        # Add any historical deprecation events that haven't been reported yet
        for event in self._deprecation_events:
            if event not in events:
                events.append(event)
        
        # Simulate some common deprecation events
        if not events:
            events = [
                "Legacy API v1 endpoint deprecated in favor of v2",
                "Old configuration format no longer supported",
                "Deprecated authentication method removed"
            ]
        
        return events[:5]  # Limit to 5 events

    def _get_merge_suggestions(self, text: str, context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Get suggestions for capabilities that could be merged based on overlapping downstream usage patterns.

        Args:
            text: The reflection text.
            context: Optional contextual information.

        Returns:
            List of merge suggestions with capability pairs and reasoning.
        """
        # In a real implementation, this would analyze downstream usage patterns
        # For now, we simulate based on common patterns
        suggestions = []
        
        # Check for overlapping patterns in the text
        if "validation" in text.lower() and "error" in text.lower():
            suggestions.append({
                "capabilities": ["validation", "error_handling"],
                "reasoning": "Both capabilities are frequently used together in input processing pipelines",
                "overlap_score": 0.85
            })
        
        if "logging" in text.lower() and "monitoring" in text.lower():
            suggestions.append({
                "capabilities": ["logging", "monitoring"],
                "reasoning": "Logging and monitoring share common infrastructure and are often implemented together",
                "overlap_score": 0.72
            })
        
        if "caching" in text.lower() and "rate_limiting" in text.lower():
            suggestions.append({
                "capabilities": ["caching", "rate_limiting"],
                "reasoning": "Both capabilities manage resource access patterns and can share state management",
                "overlap_score": 0.63
            })
        
        # Add some default suggestions if none found
        if not suggestions:
            suggestions = [
                {
                    "capabilities": ["health_check", "monitoring"],
                    "reasoning": "Health checks and monitoring share common metrics collection infrastructure",
                    "overlap_score": 0.78
                },
                {
                    "capabilities": ["retry_logic", "circuit_breaker"],
                    "reasoning": "Both handle failure recovery patterns and can share state tracking",
                    "overlap_score": 0.91
                },
                {
                    "capabilities": ["authentication", "rate_limiting"],
                    "reasoning": "Both capabilities operate at the request processing layer and share user context",
                    "overlap_score": 0.55
                }
            ]
        
        return suggestions[:3]  # Limit to 3 suggestions

    def _validate_output(self, output: ReflectionOutput) -> None:
        """Validate the output against the canonical reflection schema.

        Args:
            output: The ReflectionOutput to validate.

        Raises:
            ValueError: If validation fails.
        """
        # Check required fields
        if not output.reflection_id:
            raise ValueError("reflection_id is required")
        if not output.timestamp:
            raise ValueError("timestamp is required")
        if not output.schema_version:
            raise ValueError("schema_version is required")
        if output.failure_categories is None:
            raise ValueError("failure_categories is required")
        if output.root_cause_hypotheses is None:
            raise ValueError("root_cause_hypotheses is required")
        if output.analysis_history is None:
            raise ValueError("analysis_history is required")
        if output.summary is None:
            raise ValueError("summary is required")

        # Validate types
        if not isinstance(output.reflection_id, str):
            raise ValueError("reflection_id must be a string")
        if not isinstance(output.timestamp, datetime):
            raise ValueError("timestamp must be a datetime")
        if not isinstance(output.schema_version, str):
            raise ValueError("schema_version must be a string")
        if not isinstance(output.failure_categories, list):
            raise ValueError("failure_categories must be a list")
        if not isinstance(output.root_cause_hypotheses, list):
            raise ValueError("root_cause_hypotheses must be a list")
        if not isinstance(output.analysis_history, dict):
            raise ValueError("analysis_history must be a dict")
        if not isinstance(output.summary, str):
            raise ValueError("summary must be a string")

        # Validate failure categories
        for category in output.failure_categories:
            if not isinstance(category, FailureCategory):
                raise ValueError(f"Invalid failure category: {category}")

        # Validate root cause hypotheses
        for hypothesis in output.root_cause_hypotheses:
            if not isinstance(hypothesis, RootCauseHypothesis):
                raise ValueError(f"Invalid root cause hypothesis: {hypothesis}")
            if not hypothesis.id:
                raise ValueError("Each hypothesis must have an id")
            if not isinstance(hypothesis.category, FailureCategory):
                raise ValueError(f"Invalid hypothesis category: {hypothesis.category}")
            if not hypothesis.description:
                raise ValueError("Each hypothesis must have a description")
            if not isinstance(hypothesis.confidence, (int, float)):
                raise ValueError("Hypothesis confidence must be numeric")
            if not 0.0 <= hypothesis.confidence <= 1.0:
                raise ValueError("Hypothesis confidence must be between 0.0 and 1.0")
            if not isinstance(hypothesis.evidence, list):
                raise ValueError("Hypothesis evidence must be a list")
            if not isinstance(hypothesis.created_at, datetime):
                raise ValueError("Hypothesis created_at must be a datetime")
            if not isinstance(hypothesis.validated, bool):
                raise ValueError("Hypothesis validated must be a boolean")
            if not isinstance(hypothesis.resolution_attempted, bool):
                raise ValueError("Hypothesis resolution_attempted must be a boolean")

        # Validate analysis history
        for category, record in output.analysis_history.items():
            if not isinstance(category, FailureCategory):
                raise ValueError(f"Invalid analysis history key: {category}")
            if not isinstance(record, AnalysisRecord):
                raise ValueError(f"Invalid analysis history record for {category}")

        # Validate raw_reflection if present
        if output.raw_reflection is not None and not isinstance(output.raw_reflection, str):
            raise ValueError("raw_reflection must be a string or None")

        # Validate capability_fitness if present
        if output.capability_fitness is not None:
            if not isinstance(output.capability_fitness, CapabilityFitness):
                raise ValueError("capability_fitness must be a CapabilityFitness instance")
            if not isinstance(output.capability_fitness.top_5_capabilities, list):
                raise ValueError("capability_fitness.top_5_capabilities must be a list")
            if not isinstance(output.capability_fitness.bottom_5_capabilities, list):
                raise ValueError("capability_fitness.bottom_5_capabilities must be a list")
            if not isinstance(output.capability_fitness.deprecation_events, list):
                raise ValueError("capability_fitness.deprecation_events must be a list")
            if not isinstance(output.capability_fitness.merge_suggestions, list):
                raise ValueError("capability_fitness.merge_suggestions must be a list")

    def _extract_failure_categories(self, text: str, context: Optional[Dict[str, Any]] = None) -> List[FailureCategory]:
        """Extract failure categories from reflection text."""
        categories = []
        text_lower = text.lower()

        # Simple keyword-based extraction (can be enhanced with ML)
        category_keywords = {
            FailureCategory.TIMEOUT: ['timeout', 'timed out', 'slow', 'latency'],
            FailureCategory.MEMORY: ['memory', 'out of memory', 'oom', 'allocation'],
            FailureCategory.LOGIC: ['logic', 'incorrect', 'unexpected', 'wrong'],
            FailureCategory.SYNTAX: ['syntax', 'parse', 'compilation', 'compile'],
            FailureCategory.DEPENDENCY: ['dependency', 'import', 'module', 'package'],
            FailureCategory.PERMISSION: ['permission', 'access denied', 'unauthorized'],
            FailureCategory.NETWORK: ['network', 'connection', 'disconnect', 'timeout'],
            FailureCategory.DATA: ['data', 'corrupt', 'invalid', 'missing'],
        }

        for category, keywords in category_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                categories.append(category)

        if not categories:
            categories.append(FailureCategory.UNKNOWN)

        return categories

    def _generate_hypotheses(self, categories: List[FailureCategory], text: str,
                             context: Optional[Dict[str, Any]] = None) -> List[RootCauseHypothesis]:
        """Generate root cause hypotheses for identified failure categories."""
        hypotheses = []
        context = context or {}

        for category in categories:
            hypothesis = self._create_hypothesis_for_category(category, text, context)
            if hypothesis:
                hypotheses.append(hypothesis)

        return hypotheses

    def _create_hypothesis_for_category(self, category: FailureCategory, text: str,
                                        context: Dict[str, Any]) -> Optional[RootCauseHypothesis]:
        """Create a hypothesis for a specific failure category."""
        # Basic hypothesis generation logic
        hypothesis_templates = {
            FailureCategory.TIMEOUT: "Operation exceeded expected time threshold due to resource contention or inefficient algorithm.",
            FailureCategory.MEMORY: "Memory allocation failure caused by unbounded data growth or memory leak.",
            FailureCategory.LOGIC: "Unexpected behavior due to incorrect conditional logic or edge case not handled.",
            FailureCategory.SYNTAX: "Code structure violation detected during parsing or compilation phase.",
            FailureCategory.DEPENDENCY: "Required external component missing or incompatible version.",
            FailureCategory.PERMISSION: "Insufficient access rights for requested operation.",
            FailureCategory.NETWORK: "Communication failure due to network instability or configuration issue.",
            FailureCategory.DATA: "Data integrity issue caused by corruption or schema mismatch.",
            FailureCategory.UNKNOWN: "Unrecognized failure pattern requiring further investigation."
        }

        description = hypothesis_templates.get(category, "Unknown failure pattern.")
        evidence = self._extract_evidence(text, category)

        return RootCauseHypothesis(
            category=category,
            description=description,
            confidence=self._calculate_confidence(text, category),
            evidence=evidence
        )

    def _extract_evidence(self, text: str, category: FailureCategory) -> List[str]:
        """Extract evidence from text supporting the hypothesis."""
        evidence = []
        sentences = text.split('.')
        category_keywords = {
            FailureCategory.TIMEOUT: ['timeout', 'timed out', 'slow'],
            FailureCategory.MEMORY: ['memory', 'oom', 'allocation'],
            FailureCategory.LOGIC: ['logic', 'incorrect', 'unexpected'],
            FailureCategory.SYNTAX: ['syntax', 'parse', 'compilation'],
            FailureCategory.DEPENDENCY: ['dependency', 'import', 'module'],
            FailureCategory.PERMISSION: ['permission', 'access denied'],
            FailureCategory.NETWORK: ['network', 'connection'],
            FailureCategory.DATA: ['data', 'corrupt', 'invalid'],
        }

        keywords = category_keywords.get(category, [])
        for sentence in sentences:
            if any(keyword in sentence.lower() for keyword in keywords):
                evidence.append(sentence.strip())

        return evidence[:3]  # Limit to top 3 evidence items

    def _calculate_confidence(self, text: str, category: FailureCategory) -> float:
        """Calculate confidence score for a hypothesis based on text analysis."""
        # Simple confidence calculation based on keyword density
        text_lower = text.lower()
        category_keywords = {
            FailureCategory.TIMEOUT: ['timeout', 'timed out', 'slow', 'latency'],
            FailureCategory.MEMORY: ['memory', 'out of memory', 'oom', 'allocation'],
            FailureCategory.LOGIC: ['logic', 'incorrect', 'unexpected', 'wrong'],
            FailureCategory.SYNTAX: ['syntax', 'parse', 'compilation', 'compile'],
            FailureCategory.DEPENDENCY: ['dependency', 'import', 'module', 'package'],
            FailureCategory.PERMISSION: ['permission', 'access denied', 'unauthorized'],
            FailureCategory.NETWORK: ['network', 'connection', 'disconnect', 'timeout'],
            FailureCategory.DATA: ['data', 'corrupt', 'invalid', 'missing'],
        }

        keywords = category_keywords.get(category, [])
        if not keywords:
            return 0.1

        keyword_count = sum(1 for kw in keywords if kw in text_lower)
        return min(1.0, keyword_count / len(keywords) * 0.8 + 0.2)

    def _generate_summary(self, categories: List[FailureCategory],
                          hypotheses: List[RootCauseHypothesis]) -> str:
        """Generate a human-readable summary of the analysis."""
        if not categories:
            return "No failure categories identified."

        category_names = [c.value for c in categories]
        summary = f"Identified {len(categories)} failure category(ies): {', '.join(category_names)}. "

        if hypotheses:
            summary += f"Generated {len(hypotheses)} root cause hypothesis(es)."
        else:
            summary += "No hypotheses generated."

        return summary

    def _update_analysis_history(self, categories: List[FailureCategory],
                                 hypotheses: List[RootCauseHypothesis]) -> None:
        """Update the analysis history with new categories and hypotheses."""
        for category in categories:
            if category not in self._analysis_history:
                self._analysis_history[category] = AnalysisRecord(category=category)

            record = self._analysis_history[category]
            record.analyzed_at = datetime.utcnow()

            # Add hypotheses for this category
            category_hypotheses = [h for h in hypotheses if h.category == category]
            record.hypotheses.extend(category_hypotheses)

    def get_analysis_history(self, category: Optional[FailureCategory] = None) -> Dict[FailureCategory, AnalysisRecord]:
        """Get the analysis history for all categories or a specific one.

        Args:
            category: Optional specific category to query.

        Returns:
            Dictionary of analysis records.
        """
        if category:
            return {category: self._analysis_history.get(category, AnalysisRecord(category=category))}
        return dict(self._analysis_history)

    def get_hypothesis_history(self, category: Optional[FailureCategory] = None) -> List[RootCauseHypothesis]:
        """Get all generated hypotheses, optionally filtered by category.

        Args:
            category: Optional category to filter by.

        Returns:
            List of hypotheses.
        """
        if category:
            return [h for h in self._hypothesis_history if h.category == category]
        return list(self._hypothesis_history)

    def mark_hypothesis_resolved(self, hypothesis_id: str) -> bool:
        """Mark a hypothesis as resolved.

        Args:
            hypothesis_id: The ID of the hypothesis to mark.

        Returns:
            True if found and updated, False otherwise.
        """
        for hypothesis in self._hypothesis_history:
            if hypothesis.id == hypothesis_id:
                hypothesis.resolution_attempted = True
                hypothesis.validated = True
                return True
        return False

    def clear_history(self) -> None:
        """Clear all analysis and hypothesis history."""
        self._analysis_history.clear()
        self._hypothesis_history.clear()
        self._capability_fitness_history.clear()
        self._deprecation_events.clear()
        self._downstream_usage_patterns.clear()


# Convenience function for quick reflection parsing
def parse_reflection(reflection_text: str, context: Optional[Dict[str, Any]] = None) -> ReflectionOutput:
    """Convenience function to parse reflection text.

    Args:
        reflection_text: The raw reflection text to analyze.
        context: Optional contextual information.

    Returns:
        A ReflectionOutput object.
    """
    parser = ReflectionParser()
    return parser.parse_reflection(reflection_text, context)