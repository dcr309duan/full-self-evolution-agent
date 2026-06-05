"""reflection_parser.py

Implements a ReflectionParser class that extracts structured fields from raw reflection text
using regex patterns and lightweight NLP heuristics. Extended to analyze multi-file refactoring
outcomes with fields for files_affected, dependency_changes, and refactoring_success_rate.
Also tags each reflection entry with actionable insights and outputs structured summary.
Now includes integration_test_status field to capture pass/fail status and error traces from
the integration test suite.
"""


class ParseError(Exception):
    """Raised when reflection text cannot be parsed into the expected structure."""
    pass

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
    "failure_type": [
        r"(?:error|exception|failure|crash|bug|issue|problem)",
        r"(?:timeout|time.?out|hang|freeze|stall)",
        r"(?:memory|overflow|leak|out.?of.?memory)",
        r"(?:permission|access|denied|unauthorized|forbidden)",
        r"(?:connection|network|socket|disconnect)",
        r"(?:syntax|parse|compilation|type.?error)",
        r"(?:logic|semantic|runtime|unexpected)",
    ],
    "root_cause_hint": [
        r"(?:because|due to|caused by|result of|stemming from)",
        r"(?:root cause|underlying|fundamental|primary reason)",
        r"(?:triggered by|originates from|starts with)",
        r"(?:missing|incorrect|invalid|wrong|bad)\s+\w+",
        r"(?:not\s+(?:found|defined|initialized|configured|handled))",
    ],
    "suggested_approach_change": [
        r"(?:try|attempt|use|implement|apply|adopt)\s+(?:a|an|the|different|new|alternative)",
        r"(?:instead|rather than|alternative|different approach|change strategy)",
        r"(?:refactor|redesign|restructure|rework|rewrite)",
        r"(?:add|include|integrate|incorporate)\s+(?:check|validation|handling|fallback)",
        r"(?:optimize|improve|enhance|upgrade|migrate)",
    ],
    "goal_type": [
        r"(?:goal|objective|target|aim)\s+(?:is|to|of|type|category)\s*[:=]?\s*([\w\s]+)",
        r"(?:type|category|kind)\s+(?:of\s+)?(?:goal|objective|target)\s*[:=]?\s*([\w\s]+)",
        r"(?:API\s+server|mutation\s+engine|data\s+pipeline|model\s+training|deployment|testing|optimization)",
        r"(?:build|create|develop|implement|design)\s+(?:an?\s+)?(?:API\s+server|mutation\s+engine|data\s+pipeline|model|system|application)",
    ],
    "files_affected": [
        r"(?:files?\s+(?:affected|changed|modified|touched|impacted))\s*[:=]?\s*([\w./\\\-]+(?:\s*,\s*[\w./\\\-]+)*)",
        r"(?:affected\s+files?\s*[:=]?\s*([\w./\\\-]+(?:\s*,\s*[\w./\\\-]+)*))",
        r"(?:changed\s+files?\s*[:=]?\s*([\w./\\\-]+(?:\s*,\s*[\w./\\\-]+)*))",
        r"(?:modified\s+files?\s*[:=]?\s*([\w./\\\-]+(?:\s*,\s*[\w./\\\-]+)*))",
        r"(?:files?\s+involved\s*[:=]?\s*([\w./\\\-]+(?:\s*,\s*[\w./\\\-]+)*))",
        r"(?:multi.?file\s+(?:refactor|change|update)\s+involving\s+([\w./\\\-]+(?:\s*,\s*[\w./\\\-]+)*))",
    ],
    "dependency_changes": [
        r"(?:dependency\s+(?:change|update|modification|alteration))\s*[:=]?\s*(.+)",
        r"(?:changed?\s+(?:dependencies?|imports?|requires?))\s*[:=]?\s*(.+)",
        r"(?:new\s+(?:dependency|import|requirement))\s*[:=]?\s*(.+)",
        r"(?:removed\s+(?:dependency|import|requirement))\s*[:=]?\s*(.+)",
        r"(?:updated\s+(?:dependency|import|requirement))\s*[:=]?\s*(.+)",
        r"(?:dependency\s+(?:graph|tree|chain)\s+(?:change|update))\s*[:=]?\s*(.+)",
    ],
    "refactoring_success_rate": [
        r"(?:success\s+rate|success\s+ratio|success\s+percentage)\s*[:=]?\s*(\d+(?:\.\d+)?)\s*%?",
        r"(?:refactoring\s+(?:success|completion|effectiveness))\s*(?:rate|ratio|percentage)?\s*[:=]?\s*(\d+(?:\.\d+)?)\s*%?",
        r"(?:(\d+(?:\.\d+)?)\s*%\s+(?:success|completion|effectiveness))",
        r"(?:successfully\s+(?:refactored|completed|applied))\s+(\d+(?:\.\d+)?)\s*%",
        r"(?:(\d+(?:\.\d+)?)\s+out\s+of\s+\d+\s+(?:files|changes|refactorings))\s+(?:succeeded|passed|completed)",
        r"(?:success\s+rate\s+(?:is|was|at)\s+(\d+(?:\.\d+)?)\s*%?)",
    ],
    "actionable_insights": [
        r"(?:architecture\s+change\s+needed|architectural\s+change\s+required)",
        r"(?:new\s+capabilit(?:y|ies)\s+required|need\s+new\s+capabilit(?:y|ies))",
        r"(?:optimization\s+opportunit(?:y|ies)|performance\s+optimization\s+needed)",
        r"(?:refactor\s+needed|refactoring\s+required|code\s+restructuring\s+needed)",
        r"(?:bug\s+fix\s+required|fix\s+needed|issue\s+resolution\s+needed)",
        r"(?:documentation\s+update\s+needed|docs\s+required)",
        r"(?:testing\s+improvement\s+needed|test\s+coverage\s+required)",
        r"(?:security\s+enhancement\s+needed|security\s+fix\s+required)",
        r"(?:scalability\s+improvement\s+needed|scaling\s+required)",
        r"(?:monitoring\s+addition\s+needed|observability\s+required)",
    ],
    "knowledge_gaps": [
        r"(?:knowledge\s+gap|information\s+missing|unknown\s+(?:aspect|area|part))",
        r"(?:need\s+(?:more|better|additional)\s+(?:information|data|knowledge|understanding))",
        r"(?:unclear|ambiguous|uncertain|not\s+understood|not\s+known)",
        r"(?:require\s+(?:research|investigation|exploration|analysis))",
        r"(?:missing\s+(?:context|background|details|specification))",
    ],
    "integration_test_status": [
        r"(?:integration\s+test\s+(?:status|result|outcome))\s*[:=]?\s*(pass|fail|passed|failed|success|error|skipped|incomplete)",
        r"(?:integration\s+tests?\s+(?:passed|failed|succeeded|errored|skipped|completed))",
        r"(?:test\s+suite\s+(?:status|result|outcome))\s*[:=]?\s*(pass|fail|passed|failed|success|error|skipped|incomplete)",
        r"(?:all\s+(?:integration\s+)?tests?\s+(?:passed|failed|succeeded|errored))",
        r"(?:(\d+)\s+(?:passed|failed|skipped|errored)\s+out\s+of\s+(\d+)\s+(?:integration\s+)?tests?)",
        r"(?:error\s+trace|traceback|stack\s+trace)\s*[:=]?\s*(.+)",
        r"(?:failure\s+message|error\s+message)\s*[:=]?\s*(.+)",
        r"(?:integration\s+test\s+(?:error|failure|exception))\s*[:=]?\s*(.+)",
    ],
    "meta_mutation_directives": [
        r"(?:mutation\s+needed)\s*[:=]?\s*(.+)",
        r"(?:mutation\s+required)\s*[:=]?\s*(.+)",
        r"(?:mutation\s+directive)\s*[:=]?\s*(.+)",
    ],
    "exploration_task_acceptance": [
        r"(?:exploration\s+opportunity)\s*[:=]?\s*(.+)",
        r"(?:exploration\s+task)\s*[:=]?\s*(.+)",
        r"(?:exploration\s+accepted)\s*[:=]?\s*(.+)",
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

    def parse_failure_context(self, text: str) -> Dict[str, List[Tuple[str, float]]]:
        """
        Extract structured insights from failure logs and error messages.

        Args:
            text: Raw failure log or error message text.

        Returns:
            Dictionary with keys: failure_type, root_cause_hint, suggested_approach_change, confidence_score.
            Each value is a list of (extracted_text, confidence) tuples.
        """
        if not text or not isinstance(text, str):
            return {
                "failure_type": [],
                "root_cause_hint": [],
                "suggested_approach_change": [],
                "confidence_score": []
            }

        results = {}
        
        # Extract failure type
        failure_matches = self.extract_field(text, "failure_type")
        results["failure_type"] = failure_matches
        
        # Extract root cause hints
        root_cause_matches = self.extract_field(text, "root_cause_hint")
        results["root_cause_hint"] = root_cause_matches
        
        # Extract suggested approach changes
        approach_matches = self.extract_field(text, "suggested_approach_change")
        results["suggested_approach_change"] = approach_matches
        
        # Calculate overall confidence score based on all extracted fields
        all_matches = failure_matches + root_cause_matches + approach_matches
        if all_matches:
            avg_confidence = sum(conf for _, conf in all_matches) / len(all_matches)
        else:
            avg_confidence = 0.0
        
        results["confidence_score"] = [("overall_confidence", round(avg_confidence, 2))]
        
        return results

    def parse_refactoring_outcome(self, text: str) -> Dict[str, List[Tuple[str, float]]]:
        """
        Extract structured insights from multi-file refactoring outcomes.

        Args:
            text: Raw reflection text describing refactoring outcomes.

        Returns:
            Dictionary with keys: files_affected, dependency_changes, refactoring_success_rate.
            Each value is a list of (matched_text, confidence) tuples.
        """
        if not text or not isinstance(text, str):
            return {
                "files_affected": [],
                "dependency_changes": [],
                "refactoring_success_rate": []
            }

        results = {}
        
        # Extract files affected
        files_matches = self.extract_field(text, "files_affected")
        results["files_affected"] = files_matches
        
        # Extract dependency changes
        dependency_matches = self.extract_field(text, "dependency_changes")
        results["dependency_changes"] = dependency_matches
        
        # Extract refactoring success rate
        success_matches = self.extract_field(text, "refactoring_success_rate")
        results["refactoring_success_rate"] = success_matches
        
        return results

    def parse_integration_test_status(self, text: str) -> Dict[str, List[Tuple[str, float]]]:
        """
        Extract structured insights from integration test results.

        Args:
            text: Raw reflection text describing integration test outcomes.

        Returns:
            Dictionary with keys: integration_test_status, error_traces.
            Each value is a list of (matched_text, confidence) tuples.
        """
        if not text or not isinstance(text, str):
            return {
                "integration_test_status": [],
                "error_traces": []
            }

        results = {}
        
        # Extract integration test status
        status_matches = self.extract_field(text, "integration_test_status")
        results["integration_test_status"] = status_matches
        
        # Extract error traces separately (more specific patterns)
        error_trace_patterns = [
            r"(?:error\s+trace|traceback|stack\s+trace)\s*[:=]?\s*(.+)",
            r"(?:failure\s+message|error\s+message)\s*[:=]?\s*(.+)",
            r"(?:integration\s+test\s+(?:error|failure|exception))\s*[:=]?\s*(.+)",
        ]
        error_traces = []
        for pattern_str in error_trace_patterns:
            pattern = re.compile(pattern_str, re.IGNORECASE)
            for match in pattern.finditer(text):
                matched_text = match.group(0).strip()
                words = matched_text.split()
                specificity = len(matched_text) / 100.0 + len(words) / 20.0
                confidence = min(1.0, 0.5 + specificity * 0.1)
                error_traces.append((matched_text, round(confidence, 2)))
        
        # Remove duplicates
        seen = {}
        for trace_text, trace_conf in error_traces:
            key = trace_text.lower()
            if key not in seen or trace_conf > seen[key][1]:
                seen[key] = (trace_text, trace_conf)
        results["error_traces"] = list(seen.values())
        
        return results

    def extract_goal_type_from_reflection(self, reflection_text: str) -> Optional[str]:
        """
        Parse the reflection output to identify the goal type (e.g., 'API server', 'mutation engine').
        This helps automatically categorize goals for the feasibility estimator's database.

        Args:
            reflection_text: Raw reflection text to analyze.

        Returns:
            The identified goal type as a string, or None if no goal type could be determined.
        """
        if not reflection_text or not isinstance(reflection_text, str):
            return None

        # Extract goal_type field matches
        goal_matches = self.extract_field(reflection_text, "goal_type")
        
        if not goal_matches:
            return None

        # Process matches to find the most specific goal type
        goal_types = []
        for matched_text, confidence in goal_matches:
            # Try to extract the actual goal type from capture groups
            for pattern in self._compiled_patterns["goal_type"]:
                match = pattern.search(reflection_text)
                if match:
                    # Check if there's a capture group (group 1)
                    if match.lastindex and match.lastindex >= 1:
                        extracted = match.group(1).strip()
                        if extracted and len(extracted) > 2:
                            goal_types.append((extracted, confidence))
                    else:
                        # Use the full match if no capture group
                        full_match = match.group(0).strip()
                        # Extract the actual goal type from common patterns
                        for prefix in ["build ", "create ", "develop ", "implement ", "design "]:
                            if full_match.lower().startswith(prefix):
                                extracted = full_match[len(prefix):].strip()
                                if extracted:
                                    goal_types.append((extracted, confidence))
                                    break
                        else:
                            goal_types.append((full_match, confidence))

        if not goal_types:
            return None

        # Sort by confidence and return the highest confidence match
        goal_types.sort(key=lambda x: x[1], reverse=True)
        return goal_types[0][0]

    def tag_actionable_insights(self, text: str) -> List[Tuple[str, float, str]]:
        """
        Tag each reflection entry with actionable insights for the goal generator.

        Args:
            text: Raw reflection text.

        Returns:
            List of (insight_text, confidence, insight_type) tuples.
            Insight types include: 'architecture_change_needed', 'new_capability_required',
            'optimization_opportunity', 'refactoring_needed', 'bug_fix_required',
            'documentation_update_needed', 'testing_improvement_needed',
            'security_enhancement_needed', 'scalability_improvement_needed',
            'monitoring_addition_needed'.
        """
        if not text or not isinstance(text, str):
            return []

        insights = []
        # Extract actionable_insights field
        insight_matches = self.extract_field(text, "actionable_insights")
        
        # Map matched text to insight type
        insight_type_map = {
            "architecture change needed": "architecture_change_needed",
            "architectural change required": "architecture_change_needed",
            "new capability required": "new_capability_required",
            "need new capability": "new_capability_required",
            "need new capabilities": "new_capability_required",
            "optimization opportunity": "optimization_opportunity",
            "performance optimization needed": "optimization_opportunity",
            "refactor needed": "refactoring_needed",
            "refactoring required": "refactoring_needed",
            "code restructuring needed": "refactoring_needed",
            "bug fix required": "bug_fix_required",
            "fix needed": "bug_fix_required",
            "issue resolution needed": "bug_fix_required",
            "documentation update needed": "documentation_update_needed",
            "docs required": "documentation_update_needed",
            "testing improvement needed": "testing_improvement_needed",
            "test coverage required": "testing_improvement_needed",
            "security enhancement needed": "security_enhancement_needed",
            "security fix required": "security_enhancement_needed",
            "scalability improvement needed": "scalability_improvement_needed",
            "scaling required": "scalability_improvement_needed",
            "monitoring addition needed": "monitoring_addition_needed",
            "observability required": "monitoring_addition_needed",
        }

        for matched_text, confidence in insight_matches:
            # Determine insight type
            lower_text = matched_text.lower()
            insight_type = insight_type_map.get(lower_text, "general_action_needed")
            insights.append((matched_text, confidence, insight_type))

        # Also check other fields for implicit actionable insights
        parsed = self.parse(text)
        
        # Check for key_gaps that might indicate architecture changes
        for gap_text, gap_conf in parsed.get("key_gaps", []):
            lower_gap = gap_text.lower()
            if any(word in lower_gap for word in ["architecture", "design", "structure", "pattern"]):
                insights.append((gap_text, gap_conf * 0.8, "architecture_change_needed"))
            elif any(word in lower_gap for word in ["capability", "feature", "functionality", "ability"]):
                insights.append((gap_text, gap_conf * 0.8, "new_capability_required"))
            elif any(word in lower_gap for word in ["performance", "speed", "efficiency", "slow"]):
                insights.append((gap_text, gap_conf * 0.8, "optimization_opportunity"))

        # Check for suggested_approach_change that might indicate specific actions
        for approach_text, approach_conf in parsed.get("suggested_approach_change", []):
            lower_approach = approach_text.lower()
            if any(word in lower_approach for word in ["refactor", "restructure", "redesign", "rewrite"]):
                insights.append((approach_text, approach_conf * 0.9, "refactoring_needed"))
            elif any(word in lower_approach for word in ["optimize", "improve performance", "speed up"]):
                insights.append((approach_text, approach_conf * 0.9, "optimization_opportunity"))
            elif any(word in lower_approach for word in ["add", "implement", "create", "build"]):
                insights.append((approach_text, approach_conf * 0.8, "new_capability_required"))

        # Remove duplicates while keeping highest confidence
        seen = {}
        for insight_text, confidence, insight_type in insights:
            key = (insight_text.lower(), insight_type)
            if key not in seen or confidence > seen[key][1]:
                seen[key] = (insight_text, confidence, insight_type)

        return list(seen.values())

    def extract_knowledge_gaps(self, text: str) -> List[Tuple[str, float]]:
        """
        Extract knowledge gaps from reflection text.

        Args:
            text: Raw reflection text.

        Returns:
            List of (gap_text, confidence) tuples.
        """
        if not text or not isinstance(text, str):
            return []

        return self.extract_field(text, "knowledge_gaps")

    def generate_structured_summary(self, text: str) -> Dict[str, List]:
        """
        Generate a structured summary with 'knowledge_gaps' and 'next_actionable_insights'
        that the goal generator can consume directly.

        Args:
            text: Raw reflection text.

        Returns:
            Dictionary with keys:
                - 'knowledge_gaps': List of (gap_text, confidence) tuples.
                - 'next_actionable_insights': List of (insight_text, confidence, insight_type) tuples.
        """
        if not text or not isinstance(text, str):
            return {
                "knowledge_gaps": [],
                "next_actionable_insights": []
            }

        # Extract knowledge gaps
        knowledge_gaps = self.extract_knowledge_gaps(text)
        
        # Also check other fields for implicit knowledge gaps
        parsed = self.parse(text)
        for field in ["current_assessment", "key_gaps", "root_cause_hint"]:
            for match_text, match_conf in parsed.get(field, []):
                lower_text = match_text.lower()
                if any(word in lower_text for word in ["unknown", "unclear", "missing information", "need to understand", "not sure", "uncertain"]):
                    knowledge_gaps.append((match_text, match_conf * 0.7))

        # Remove duplicates
        seen_gaps = {}
        for gap_text, gap_conf in knowledge_gaps:
            key = gap_text.lower()
            if key not in seen_gaps or gap_conf > seen_gaps[key][1]:
                seen_gaps[key] = (gap_text, gap_conf)
        knowledge_gaps = list(seen_gaps.values())

        # Extract actionable insights
        actionable_insights = self.tag_actionable_insights(text)

        # Also check next_priority for implicit actionable insights
        for priority_text, priority_conf in parsed.get("next_priority", []):
            lower_priority = priority_text.lower()
            if any(word in lower_priority for word in ["implement", "build", "create", "develop", "add"]):
                actionable_insights.append((priority_text, priority_conf * 0.8, "new_capability_required"))
            elif any(word in lower_priority for word in ["optimize", "improve", "enhance", "speed up"]):
                actionable_insights.append((priority_text, priority_conf * 0.8, "optimization_opportunity"))
            elif any(word in lower_priority for word in ["refactor", "restructure", "redesign"]):
                actionable_insights.append((priority_text, priority_conf * 0.8, "refactoring_needed"))

        # Remove duplicates from actionable insights
        seen_insights = {}
        for insight_text, confidence, insight_type in actionable_insights:
            key = (insight_text.lower(), insight_type)
            if key not in seen_insights or confidence > seen_insights[key][1]:
                seen_insights[key] = (insight_text, confidence, insight_type)
        actionable_insights = list(seen_insights.values())

        # Sort by confidence (highest first)
        knowledge_gaps.sort(key=lambda x: x[1], reverse=True)
        actionable_insights.sort(key=lambda x: x[1], reverse=True)

        return {
            "knowledge_gaps": knowledge_gaps,
            "next_actionable_insights": actionable_insights
        }

    def parse_meta_mutation_directives(self, text: str) -> List[Dict[str, str]]:
        """
        Extract meta mutation directives from reflection text.

        Args:
            text: Raw reflection text.

        Returns:
            List of dicts with keys: module, type_of_change, priority.
        """
        if not text or not isinstance(text, str):
            return []

        directives = []
        matches = self.extract_field(text, "meta_mutation_directives")
        
        for matched_text, confidence in matches:
            # Parse the matched text to extract module, type_of_change, priority
            # Pattern: "mutation needed: module=X, type_of_change=Y, priority=Z"
            module_match = re.search(r"module\s*[:=]\s*(\w+)", matched_text, re.IGNORECASE)
            type_match = re.search(r"type_of_change\s*[:=]\s*(\w+)", matched_text, re.IGNORECASE)
            priority_match = re.search(r"priority\s*[:=]\s*(\w+)", matched_text, re.IGNORECASE)
            
            if module_match or type_match or priority_match:
                directive = {
                    "module": module_match.group(1) if module_match else "unknown",
                    "type_of_change": type_match.group(1) if type_match else "unknown",
                    "priority": priority_match.group(1) if priority_match else "medium"
                }
                directives.append(directive)
        
        # Also check for patterns like "mutation needed in module X for type Y with priority Z"
        additional_patterns = [
            r"mutation\s+needed\s+in\s+module\s+(\w+)\s+for\s+(\w+)\s+with\s+priority\s+(\w+)",
            r"mutation\s+required\s+in\s+(\w+)\s+type\s+(\w+)\s+priority\s+(\w+)",
        ]
        for pattern_str in additional_patterns:
            pattern = re.compile(pattern_str, re.IGNORECASE)
            for match in pattern.finditer(text):
                directive = {
                    "module": match.group(1),
                    "type_of_change": match.group(2),
                    "priority": match.group(3)
                }
                directives.append(directive)
        
        # Remove duplicates
        seen = set()
        unique_directives = []
        for d in directives:
            key = (d["module"], d["type_of_change"], d["priority"])
            if key not in seen:
                seen.add(key)
                unique_directives.append(d)
        
        return unique_directives

    def parse_exploration_task_acceptance(self, text: str) -> Dict[str, object]:
        """
        Extract exploration task acceptance from reflection text.

        Args:
            text: Raw reflection text.

        Returns:
            Dict with keys: accepted (bool), task_spec (optional dict with domain, description, priority).
        """
        if not text or not isinstance(text, str):
            return {"accepted": False, "task_spec": None}

        result = {"accepted": False, "task_spec": None}
        
        # Check for exploration opportunity patterns
        matches = self.extract_field(text, "exploration_task_acceptance")
        
        for matched_text, confidence in matches:
            lower_text = matched_text.lower()
            
            # Check if exploration is accepted
            if "accepted" in lower_text or "approved" in lower_text or "yes" in lower_text:
                result["accepted"] = True
            elif "rejected" in lower_text or "denied" in lower_text or "no" in lower_text:
                result["accepted"] = False
            
            # Extract task spec if available
            domain_match = re.search(r"domain\s*[:=]\s*(\w+)", matched_text, re.IGNORECASE)
            desc_match = re.search(r"description\s*[:=]\s*(.+?)(?:,|$)", matched_text, re.IGNORECASE)
            priority_match = re.search(r"priority\s*[:=]\s*(\w+)", matched_text, re.IGNORECASE)
            
            if domain_match or desc_match or priority_match:
                task_spec = {}
                if domain_match:
                    task_spec["domain"] = domain_match.group(1)
                if desc_match:
                    task_spec["description"] = desc_match.group(1).strip()
                if priority_match:
                    task_spec["priority"] = priority_match.group(1)
                result["task_spec"] = task_spec
        
        # Also check for patterns like "exploration opportunity: domain=X, description=Y, priority=Z"
        additional_patterns = [
            r"exploration\s+opportunity\s*[:=]\s*domain\s*[:=]\s*(\w+)\s*,\s*description\s*[:=]\s*(.+?)\s*,\s*priority\s*[:=]\s*(\w+)",
            r"exploration\s+task\s*[:=]\s*accepted\s*[:=]\s*(yes|no|true|false)\s*,\s*domain\s*[:=]\s*(\w+)\s*,\s*description\s*[:=]\s*(.+?)\s*,\s*priority\s*[:=]\s*(\w+)",
        ]
        for pattern_str in additional_patterns:
            pattern = re.compile(pattern_str, re.IGNORECASE)
            for match in pattern.finditer(text):
                if len(match.groups()) == 3:
                    result["accepted"] = True
                    result["task_spec"] = {
                        "domain": match.group(1),
                        "description": match.group(2).strip(),
                        "priority": match.group(3)
                    }
                elif len(match.groups()) == 4:
                    accepted_str = match.group(1).lower()
                    result["accepted"] = accepted_str in ["yes", "true"]
                    result