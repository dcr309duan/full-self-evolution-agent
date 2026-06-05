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
class ReflectionOutput:
    """Output schema for reflection parsing with failure categories."""
    reflection_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)
    failure_categories: List[FailureCategory] = field(default_factory=list)
    root_cause_hypotheses: List[RootCauseHypothesis] = field(default_factory=list)
    analysis_history: Dict[FailureCategory, AnalysisRecord] = field(default_factory=dict)
    raw_reflection: Optional[str] = None
    summary: str = ""


class ReflectionParser:
    """Parser for reflection data that generates failure categories and hypotheses."""

    def __init__(self):
        self._analysis_history: Dict[FailureCategory, AnalysisRecord] = {}
        self._hypothesis_history: List[RootCauseHypothesis] = []

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

        output = ReflectionOutput(
            failure_categories=categories,
            root_cause_hypotheses=hypotheses,
            raw_reflection=reflection_text,
            summary=self._generate_summary(categories, hypotheses)
        )

        # Update tracking
        self._update_analysis_history(categories, hypotheses)
        self._hypothesis_history.extend(hypotheses)

        return output

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