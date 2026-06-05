from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
import re
from enum import Enum


class GoalType(Enum):
    """Enumeration of supported goal types."""
    FEATURE = "feature"
    OPTIMIZATION = "optimization"
    REFACTORING = "refactoring"
    BUG_FIX = "bug_fix"
    INTEGRATION = "integration"
    TESTING = "testing"
    DOCUMENTATION = "documentation"
    CUSTOM = "custom"


@dataclass
class GoalSpecification:
    """Standard format for representing a parsed goal."""
    goal_id: str = ""
    goal_type: GoalType = GoalType.CUSTOM
    target_modules: List[str] = field(default_factory=list)
    desired_outcomes: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    priority: int = 5  # 1 (lowest) to 10 (highest)
    dependencies: List[str] = field(default_factory=list)
    success_criteria: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    raw_text: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert specification to dictionary for serialization."""
        return {
            "goal_id": self.goal_id,
            "goal_type": self.goal_type.value,
            "target_modules": self.target_modules,
            "desired_outcomes": self.desired_outcomes,
            "constraints": self.constraints,
            "priority": self.priority,
            "dependencies": self.dependencies,
            "success_criteria": self.success_criteria,
            "metadata": self.metadata,
            "raw_text": self.raw_text
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GoalSpecification":
        """Create specification from dictionary."""
        return cls(
            goal_id=data.get("goal_id", ""),
            goal_type=GoalType(data.get("goal_type", "custom")),
            target_modules=data.get("target_modules", []),
            desired_outcomes=data.get("desired_outcomes", []),
            constraints=data.get("constraints", []),
            priority=data.get("priority", 5),
            dependencies=data.get("dependencies", []),
            success_criteria=data.get("success_criteria", []),
            metadata=data.get("metadata", {}),
            raw_text=data.get("raw_text", "")
        )


class GoalParser:
    """
    Parses natural language or structured goal descriptions into standardized GoalSpecification objects.
    Supports multiple input formats and extracts key components.
    """

    # Patterns for identifying goal components
    MODULE_PATTERN = re.compile(
        r'(?:in|for|of|module|component|class|function|file)\s+["\']?([a-zA-Z_][a-zA-Z0-9_\.]*)["\']?',
        re.IGNORECASE
    )
    
    CONSTRAINT_PATTERN = re.compile(
        r'(?:must|should|need|require|constraint|limit|restrict|without|except|but\s+not)\s+([^\.]+)',
        re.IGNORECASE
    )
    
    OUTCOME_PATTERN = re.compile(
        r'(?:to|so that|in order to|goal|objective|aim|purpose|achieve|accomplish)\s+([^\.]+)',
        re.IGNORECASE
    )

    PRIORITY_PATTERN = re.compile(
        r'(?:priority|p)\s*[:=]\s*(\d+)',
        re.IGNORECASE
    )

    # Keywords for goal type detection
    TYPE_KEYWORDS = {
        GoalType.FEATURE: ['feature', 'add', 'implement', 'create', 'new', 'support'],
        GoalType.OPTIMIZATION: ['optimize', 'performance', 'speed', 'fast', 'efficient', 'improve'],
        GoalType.REFACTORING: ['refactor', 'restructure', 'clean', 'reorganize', 'simplify'],
        GoalType.BUG_FIX: ['fix', 'bug', 'error', 'issue', 'problem', 'incorrect', 'wrong'],
        GoalType.INTEGRATION: ['integrate', 'connect', 'link', 'interface', 'api', 'service'],
        GoalType.TESTING: ['test', 'verify', 'validate', 'check', 'coverage'],
        GoalType.DOCUMENTATION: ['document', 'docstring', 'comment', 'readme', 'guide', 'explain']
    }

    def __init__(self, default_priority: int = 5):
        self.default_priority = default_priority
        self._goal_counter = 0

    def parse(self, text: str, goal_id: Optional[str] = None) -> GoalSpecification:
        """
        Parse a goal description from natural language or structured format.
        
        Args:
            text: The goal description text
            goal_id: Optional identifier for the goal
            
        Returns:
            GoalSpecification with extracted components
        """
        if not text or not text.strip():
            raise ValueError("Goal description cannot be empty")

        self._goal_counter += 1
        goal_id = goal_id or f"goal_{self._goal_counter}"

        # Detect structured format (e.g., JSON, YAML-like)
        if self._is_structured_format(text):
            return self._parse_structured(text, goal_id)
        
        # Parse natural language
        return self._parse_natural_language(text, goal_id)

    def parse_batch(self, texts: List[str]) -> List[GoalSpecification]:
        """Parse multiple goal descriptions."""
        return [self.parse(text) for text in texts]

    def _is_structured_format(self, text: str) -> bool:
        """Check if text appears to be in a structured format."""
        text = text.strip()
        # Check for JSON-like structure
        if text.startswith('{') and '}' in text:
            return True
        # Check for key-value pairs
        if any(text.startswith(f"{key}:") for key in ['goal', 'type', 'target', 'outcome']):
            return True
        return False

    def _parse_structured(self, text: str, goal_id: str) -> GoalSpecification:
        """Parse structured format (key-value pairs or JSON-like)."""
        spec = GoalSpecification(goal_id=goal_id, raw_text=text)
        
        # Try to parse as JSON
        if text.startswith('{'):
            try:
                import json
                data = json.loads(text)
                return GoalSpecification.from_dict({**data, "goal_id": goal_id, "raw_text": text})
            except (json.JSONDecodeError, ValueError):
                pass

        # Parse key-value pairs
        lines = text.strip().split('\n')
        current_key = None
        current_values = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Check for key-value separator
            if ':' in line:
                # Save previous key-value pair
                if current_key and current_values:
                    self._assign_to_spec(spec, current_key, current_values)
                    current_values = []
                
                parts = line.split(':', 1)
                current_key = parts[0].strip().lower()
                value = parts[1].strip()
                if value:
                    current_values = [value]
                else:
                    current_values = []
            elif current_key:
                current_values.append(line)
        
        # Save last key-value pair
        if current_key and current_values:
            self._assign_to_spec(spec, current_key, current_values)
        
        return spec

    def _assign_to_spec(self, spec: GoalSpecification, key: str, values: List[str]):
        """Assign parsed values to the appropriate specification field."""
        key = key.lower().replace(' ', '_')
        
        if key in ('target', 'targets', 'module', 'modules', 'target_module', 'target_modules'):
            spec.target_modules.extend([v.strip().strip('"\'') for v in values])
        elif key in ('outcome', 'outcomes', 'desired_outcome', 'desired_outcomes', 'goal'):
            spec.desired_outcomes.extend([v.strip().strip('"\'') for v in values])
        elif key in ('constraint', 'constraints', 'limit', 'limits'):
            spec.constraints.extend([v.strip().strip('"\'') for v in values])
        elif key in ('type', 'goal_type'):
            try:
                spec.goal_type = GoalType(values[0].strip().lower())
            except ValueError:
                spec.goal_type = GoalType.CUSTOM
        elif key in ('priority', 'p'):
            try:
                spec.priority = int(values[0].strip())
            except ValueError:
                pass
        elif key in ('dependency', 'dependencies'):
            spec.dependencies.extend([v.strip().strip('"\'') for v in values])
        elif key in ('success_criteria', 'criteria', 'success'):
            spec.success_criteria.extend([v.strip().strip('"\'') for v in values])
        else:
            spec.metadata[key] = values[0] if len(values) == 1 else values

    def _parse_natural_language(self, text: str, goal_id: str) -> GoalSpecification:
        """Parse natural language goal description."""
        spec = GoalSpecification(goal_id=goal_id, raw_text=text)
        
        # Detect goal type
        spec.goal_type = self._detect_goal_type(text)
        
        # Extract target modules
        spec.target_modules = self._extract_modules(text)
        
        # Extract desired outcomes
        spec.desired_outcomes = self._extract_outcomes(text)
        
        # Extract constraints
        spec.constraints = self._extract_constraints(text)
        
        # Extract priority
        spec.priority = self._extract_priority(text)
        
        # Extract success criteria (if any)
        spec.success_criteria = self._extract_success_criteria(text)
        
        return spec

    def _detect_goal_type(self, text: str) -> GoalType:
        """Detect the goal type based on keywords in the text."""
        text_lower = text.lower()
        scores = {goal_type: 0 for goal_type in GoalType}
        
        for goal_type, keywords in self.TYPE_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text_lower:
                    scores[goal_type] += 1
        
        # Return type with highest score, default to CUSTOM
        max_score = max(scores.values())
        if max_score > 0:
            return max(scores, key=scores.get)
        return GoalType.CUSTOM

    def _extract_modules(self, text: str) -> List[str]:
        """Extract target module/component names from text."""
        matches = self.MODULE_PATTERN.findall(text)
        # Remove duplicates while preserving order
        seen = set()
        modules = []
        for module in matches:
            if module not in seen:
                seen.add(module)
                modules.append(module)
        return modules

    def _extract_outcomes(self, text: str) -> List[str]:
        """Extract desired outcomes from text."""
        matches = self.OUTCOME_PATTERN.findall(text)
        return [match.strip() for match in matches if match.strip()]

    def _extract_constraints(self, text: str) -> List[str]:
        """Extract constraints from text."""
        matches = self.CONSTRAINT_PATTERN.findall(text)
        return [match.strip() for match in matches if match.strip()]

    def _extract_priority(self, text: str) -> int:
        """Extract priority level from text."""
        match = self.PRIORITY_PATTERN.search(text)
        if match:
            priority = int(match.group(1))
            return max(1, min(10, priority))  # Clamp to 1-10
        return self.default_priority

    def _extract_success_criteria(self, text: str) -> List[str]:
        """Extract success criteria from text."""
        # Look for criteria after keywords like "criteria:", "success:", "verify:", "check:"
        criteria_pattern = re.compile(
            r'(?:criteria|success|verify|check)\s*[:=]\s*([^\.]+(?:\.[^\.]+)*)',
            re.IGNORECASE
        )
        matches = criteria_pattern.findall(text)
        
        # Also look for bullet points or numbered lists
        bullet_pattern = re.compile(r'[-*]\s*(.+?)(?=[-*]|\Z)', re.DOTALL)
        bullet_matches = bullet_pattern.findall(text)
        
        criteria = [m.strip() for m in matches if m.strip()]
        criteria.extend([m.strip() for m in bullet_matches if m.strip()])
        
        return criteria

    def normalize_specification(self, spec: GoalSpecification) -> GoalSpecification:
        """Normalize a specification to ensure consistent format."""
        # Remove duplicates from lists
        spec.target_modules = list(dict.fromkeys(spec.target_modules))
        spec.desired_outcomes = list(dict.fromkeys(spec.desired_outcomes))
        spec.constraints = list(dict.fromkeys(spec.constraints))
        spec.dependencies = list(dict.fromkeys(spec.dependencies))
        spec.success_criteria = list(dict.fromkeys(spec.success_criteria))
        
        # Ensure priority is within valid range
        spec.priority = max(1, min(10, spec.priority))
        
        # Strip whitespace from all text fields
        spec.target_modules = [m.strip() for m in spec.target_modules]
        spec.desired_outcomes = [o.strip() for o in spec.desired_outcomes]
        spec.constraints = [c.strip() for c in spec.constraints]
        spec.dependencies = [d.strip() for d in spec.dependencies]
        spec.success_criteria = [s.strip() for s in spec.success_criteria]
        
        return spec

    def merge_specifications(self, specs: List[GoalSpecification]) -> GoalSpecification:
        """Merge multiple specifications into one."""
        if not specs:
            raise ValueError("Cannot merge empty list of specifications")
        
        merged = GoalSpecification(
            goal_id=f"merged_{self._goal_counter}",
            raw_text="\n---\n".join(s.raw_text for s in specs)
        )
        
        # Merge all fields
        for spec in specs:
            merged.target_modules.extend(spec.target_modules)
            merged.desired_outcomes.extend(spec.desired_outcomes)
            merged.constraints.extend(spec.constraints)
            merged.dependencies.extend(spec.dependencies)
            merged.success_criteria.extend(spec.success_criteria)
            merged.metadata.update(spec.metadata)
        
        # Use the highest priority
        merged.priority = max(s.priority for s in specs)
        
        # Normalize the merged specification
        return self.normalize_specification(merged)