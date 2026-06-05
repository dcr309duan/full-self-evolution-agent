"""Module for analyzing knowledge gaps in the knowledge base."""

from typing import List, Dict, Set, Any, Optional
from dataclasses import dataclass, field
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class KnowledgeGap:
    """Represents a knowledge gap identified in the knowledge base."""
    topic: str
    description: str
    severity: str  # 'low', 'medium', 'high', 'critical'
    related_areas: List[str] = field(default_factory=list)
    evidence: List[str] = field(default_factory=list)
    suggested_resolution: Optional[str] = None


class KnowledgeGapAnalyzer:
    """Analyzes knowledge base to identify gaps that can inform goal generation."""

    def __init__(self, knowledge_base: Dict[str, Any]):
        """
        Initialize the analyzer with a knowledge base.
        
        Args:
            knowledge_base: Dictionary representing the knowledge base structure.
                Expected format: {'topics': {...}, 'entities': {...}, 'relations': {...}}
        """
        self.knowledge_base = knowledge_base
        self.gaps: List[KnowledgeGap] = []
        self._analyzed = False

    def knowledge_gap_analysis(self) -> List[KnowledgeGap]:
        """
        Perform comprehensive knowledge gap analysis.
        
        Identifies areas where the knowledge base lacks information by examining:
        - Missing topics or subtopics
        - Incomplete entity descriptions
        - Sparse relationship networks
        - Low coverage areas
        - Outdated or contradictory information
        
        Returns:
            List of KnowledgeGap objects sorted by severity.
        """
        self.gaps.clear()
        
        # Run all gap detection methods
        self._check_missing_topics()
        self._check_incomplete_entities()
        self._check_sparse_relations()
        self._check_coverage_gaps()
        self._check_contradictions()
        
        # Sort by severity (critical first)
        severity_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
        self.gaps.sort(key=lambda g: severity_order.get(g.severity, 4))
        
        self._analyzed = True
        logger.info(f"Knowledge gap analysis complete: {len(self.gaps)} gaps identified")
        return self.gaps

    def _check_missing_topics(self) -> None:
        """Identify missing topics or subtopics based on expected domain coverage."""
        topics = self.knowledge_base.get('topics', {})
        expected_categories = {
            'fundamentals', 'advanced_concepts', 'applications',
            'methodologies', 'case_studies', 'best_practices'
        }
        
        existing_categories = set(topics.keys())
        missing_categories = expected_categories - existing_categories
        
        for category in missing_categories:
            self.gaps.append(KnowledgeGap(
                topic=f"Missing category: {category}",
                description=f"The knowledge base lacks the entire '{category}' topic category",
                severity='high',
                related_areas=list(existing_categories),
                evidence=[f"Expected category '{category}' not found in topics"],
                suggested_resolution=f"Add foundational content for '{category}' category"
            ))

    def _check_incomplete_entities(self) -> None:
        """Identify entities with incomplete or missing descriptions."""
        entities = self.knowledge_base.get('entities', {})
        
        for entity_id, entity_data in entities.items():
            missing_fields = []
            
            # Check for essential fields
            if not entity_data.get('description'):
                missing_fields.append('description')
            if not entity_data.get('type'):
                missing_fields.append('type')
            if not entity_data.get('properties'):
                missing_fields.append('properties')
            
            if missing_fields:
                severity = 'critical' if 'description' in missing_fields else 'medium'
                self.gaps.append(KnowledgeGap(
                    topic=f"Incomplete entity: {entity_id}",
                    description=f"Entity '{entity_id}' is missing fields: {', '.join(missing_fields)}",
                    severity=severity,
                    related_areas=[entity_data.get('type', 'unknown')],
                    evidence=[f"Missing fields: {missing_fields}"],
                    suggested_resolution=f"Complete the missing fields for entity '{entity_id}'"
                ))

    def _check_sparse_relations(self) -> None:
        """Identify entities with too few relationships (potential knowledge gaps)."""
        relations = self.knowledge_base.get('relations', [])
        entities = self.knowledge_base.get('entities', {})
        
        # Count relations per entity
        relation_counts = defaultdict(int)
        for relation in relations:
            source = relation.get('source')
            target = relation.get('target')
            if source:
                relation_counts[source] += 1
            if target:
                relation_counts[target] += 1
        
        # Identify entities with sparse relations
        for entity_id in entities:
            count = relation_counts.get(entity_id, 0)
            if count == 0:
                self.gaps.append(KnowledgeGap(
                    topic=f"Isolated entity: {entity_id}",
                    description=f"Entity '{entity_id}' has no relations to other entities",
                    severity='high',
                    related_areas=[entities[entity_id].get('type', 'unknown')],
                    evidence=["Zero relations found"],
                    suggested_resolution=f"Establish connections between '{entity_id}' and related entities"
                ))
            elif count < 3:
                self.gaps.append(KnowledgeGap(
                    topic=f"Sparse relations: {entity_id}",
                    description=f"Entity '{entity_id}' has only {count} relations (minimum 3 recommended)",
                    severity='low',
                    related_areas=[entities[entity_id].get('type', 'unknown')],
                    evidence=[f"Only {count} relations found"],
                    suggested_resolution=f"Add more relations for '{entity_id}' to improve connectivity"
                ))

    def _check_coverage_gaps(self) -> None:
        """Identify areas with low coverage or missing depth."""
        topics = self.knowledge_base.get('topics', {})
        
        for topic_name, topic_data in topics.items():
            subtopics = topic_data.get('subtopics', [])
            articles = topic_data.get('articles', [])
            
            # Check if topic has sufficient depth
            if not subtopics and not articles:
                self.gaps.append(KnowledgeGap(
                    topic=f"Shallow topic: {topic_name}",
                    description=f"Topic '{topic_name}' exists but has no subtopics or articles",
                    severity='medium',
                    related_areas=[topic_name],
                    evidence=["No subtopics or articles found"],
                    suggested_resolution=f"Add subtopics and articles for '{topic_name}'"
                ))
            elif len(articles) < 3:
                self.gaps.append(KnowledgeGap(
                    topic=f"Low coverage: {topic_name}",
                    description=f"Topic '{topic_name}' has only {len(articles)} articles (minimum 3 recommended)",
                    severity='low',
                    related_areas=[topic_name],
                    evidence=[f"Only {len(articles)} articles"],
                    suggested_resolution=f"Add more articles to cover '{topic_name}' comprehensively"
                ))

    def _check_contradictions(self) -> None:
        """Identify potential contradictions or inconsistencies in the knowledge base."""
        entities = self.knowledge_base.get('entities', {})
        
        # Check for entities with contradictory properties
        for entity_id, entity_data in entities.items():
            properties = entity_data.get('properties', {})
            if isinstance(properties, dict):
                # Example: check for conflicting type assignments
                types = properties.get('types', [])
                if isinstance(types, list) and len(types) > 1:
                    # Check if types are compatible (simplified check)
                    incompatible_pairs = [('concrete', 'abstract'), ('static', 'dynamic')]
                    for t1, t2 in incompatible_pairs:
                        if t1 in types and t2 in types:
                            self.gaps.append(KnowledgeGap(
                                topic=f"Contradiction: {entity_id}",
                                description=f"Entity '{entity_id}' has contradictory types: {t1} and {t2}",
                                severity='high',
                                related_areas=[entity_data.get('type', 'unknown')],
                                evidence=[f"Properties contain both '{t1}' and '{t2}'"],
                                suggested_resolution=f"Resolve type contradiction for '{entity_id}'"
                            ))

    def get_goal_suggestions(self) -> List[Dict[str, Any]]:
        """
        Generate goal suggestions based on identified knowledge gaps.
        
        Returns:
            List of goal suggestions with priority and description.
        """
        if not self._analyzed:
            self.knowledge_gap_analysis()
        
        suggestions = []
        for gap in self.gaps:
            suggestion = {
                'title': f"Fill knowledge gap: {gap.topic}",
                'description': gap.description,
                'priority': gap.severity,
                'related_areas': gap.related_areas,
                'suggested_action': gap.suggested_resolution or f"Investigate and address '{gap.topic}'",
                'gap_type': 'knowledge_gap'
            }
            suggestions.append(suggestion)
        
        return suggestions

    def get_summary_statistics(self) -> Dict[str, Any]:
        """
        Get summary statistics of the knowledge gap analysis.
        
        Returns:
            Dictionary with gap statistics.
        """
        if not self._analyzed:
            self.knowledge_gap_analysis()
        
        severity_counts = defaultdict(int)
        for gap in self.gaps:
            severity_counts[gap.severity] += 1
        
        return {
            'total_gaps': len(self.gaps),
            'by_severity': dict(severity_counts),
            'critical_gaps': severity_counts.get('critical', 0),
            'high_gaps': severity_counts.get('high', 0),
            'medium_gaps': severity_counts.get('medium', 0),
            'low_gaps': severity_counts.get('low', 0),
            'topics_affected': len(set(g.topic for g in self.gaps))
        }

    def get_repeated_failure_patterns(self, failure_log: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Scan the failure log and return components that have failed 3+ consecutive times
        with the same failure type. This is used by the goal generator to trigger redesign.
        
        Args:
            failure_log: List of failure records. Each record is a dictionary with keys:
                - 'component': str (e.g., 'mutation_strategy', 'dependency_graph')
                - 'failure_type': str (e.g., 'timeout', 'invalid_output', 'crash')
                - 'timestamp': str (optional, for ordering)
        
        Returns:
            List of dictionaries with keys:
                - 'component': str
                - 'failure_type': str
                - 'consecutive_failures': int (number of consecutive failures, >= 3)
                - 'suggested_action': str (e.g., 'redesign')
        """
        if not failure_log:
            return []
        
        # Sort by timestamp if available, otherwise maintain order
        sorted_log = sorted(failure_log, key=lambda x: x.get('timestamp', ''))
        
        # Track consecutive failures per component
        component_failures: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for entry in sorted_log:
            component = entry.get('component', 'unknown')
            component_failures[component].append(entry)
        
        patterns = []
        for component, entries in component_failures.items():
            # Count consecutive same failure types
            consecutive_count = 0
            current_failure_type = None
            for entry in entries:
                failure_type = entry.get('failure_type', 'unknown')
                if failure_type == current_failure_type:
                    consecutive_count += 1
                else:
                    # Check if previous streak was >= 3
                    if consecutive_count >= 3 and current_failure_type is not None:
                        patterns.append({
                            'component': component,
                            'failure_type': current_failure_type,
                            'consecutive_failures': consecutive_count,
                            'suggested_action': 'redesign'
                        })
                    # Start new streak
                    current_failure_type = failure_type
                    consecutive_count = 1
            
            # Check last streak
            if consecutive_count >= 3 and current_failure_type is not None:
                patterns.append({
                    'component': component,
                    'failure_type': current_failure_type,
                    'consecutive_failures': consecutive_count,
                    'suggested_action': 'redesign'
                })
        
        return patterns


def knowledge_gap_analysis(knowledge_base: Dict[str, Any]) -> List[KnowledgeGap]:
    """
    Convenience function to perform knowledge gap analysis.
    
    Args:
        knowledge_base: Dictionary representing the knowledge base.
        
    Returns:
        List of identified knowledge gaps.
    """
    analyzer = KnowledgeGapAnalyzer(knowledge_base)
    return analyzer.knowledge_gap_analysis()