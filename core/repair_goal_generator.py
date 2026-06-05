from typing import Dict, List, Optional, Any
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
import uuid

from core.goal_queue import GoalQueue, RepairGoal
from core.failure_recorder import FailureContext


class FailureType(Enum):
    """Enumeration of recognized failure patterns."""
    SCHEMA_MISMATCH = "schema_mismatch"
    MISSING_DEPENDENCY = "missing_dependency"
    SYNTAX_ERROR = "syntax_error"
    TEST_FAILURE = "test_failure"
    UNKNOWN = "unknown"


class Priority(Enum):
    """Priority levels for repair goals."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Complexity(Enum):
    """Estimated complexity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class RepairGoalTemplate:
    """Template for generating repair goals from failure patterns."""
    failure_type: FailureType
    goal_type: str
    priority: Priority
    estimated_complexity: Complexity
    description_template: str
    prerequisite_goal_types: List[str] = field(default_factory=list)
    success_criteria_template: str = ""


# Mapping of failure types to repair goal templates
REPAIR_GOAL_TEMPLATES: Dict[FailureType, RepairGoalTemplate] = {
    FailureType.SCHEMA_MISMATCH: RepairGoalTemplate(
        failure_type=FailureType.SCHEMA_MISMATCH,
        goal_type="fix_schema_alignment",
        priority=Priority.HIGH,
        estimated_complexity=Complexity.MEDIUM,
        description_template="Fix schema alignment failure: {failure_description}",
        prerequisite_goal_types=["update_interface_contract"],
        success_criteria_template="Schema alignment verified: {failure_details}"
    ),
    FailureType.MISSING_DEPENDENCY: RepairGoalTemplate(
        failure_type=FailureType.MISSING_DEPENDENCY,
        goal_type="add_missing_dependency",
        priority=Priority.HIGH,
        estimated_complexity=Complexity.LOW,
        description_template="Add missing dependency: {failure_description}",
        success_criteria_template="Dependency resolved: {failure_details}"
    ),
    FailureType.SYNTAX_ERROR: RepairGoalTemplate(
        failure_type=FailureType.SYNTAX_ERROR,
        goal_type="fix_syntax_error",
        priority=Priority.HIGH,
        estimated_complexity=Complexity.LOW,
        description_template="Fix syntax error: {failure_description}",
        success_criteria_template="Syntax error resolved: {failure_details}"
    ),
    FailureType.TEST_FAILURE: RepairGoalTemplate(
        failure_type=FailureType.TEST_FAILURE,
        goal_type="fix_test_failure",
        priority=Priority.MEDIUM,
        estimated_complexity=Complexity.MEDIUM,
        description_template="Fix test failure: {failure_description}",
        prerequisite_goal_types=["fix_schema_alignment", "add_missing_dependency", "fix_syntax_error"],
        success_criteria_template="All tests pass: {failure_details}"
    ),
}


class RepairGoalGenerator:
    """
    Generates structured repair goals from failure contexts.
    Maps failure patterns to specific repair goal templates and inserts
    them into the goal queue with appropriate dependencies.
    """

    def __init__(self, goal_queue: GoalQueue):
        self.goal_queue = goal_queue
        self._generated_goal_ids: List[str] = []

    def analyze_failure_pattern(self, failure_context: FailureContext) -> FailureType:
        """
        Analyze the failure context to determine the failure pattern.
        
        Args:
            failure_context: The failure context from the recorder.
            
        Returns:
            The identified FailureType.
        """
        failure_type = failure_context.failure_type.lower()
        
        if "schema" in failure_type or "alignment" in failure_type:
            return FailureType.SCHEMA_MISMATCH
        elif "dependency" in failure_type or "missing" in failure_type:
            return FailureType.MISSING_DEPENDENCY
        elif "syntax" in failure_type or "parse" in failure_type:
            return FailureType.SYNTAX_ERROR
        elif "test" in failure_type or "assertion" in failure_type:
            return FailureType.TEST_FAILURE
        else:
            return FailureType.UNKNOWN

    def generate_goal_from_template(
        self,
        template: RepairGoalTemplate,
        failure_context: FailureContext
    ) -> RepairGoal:
        """
        Generate a RepairGoal from a template and failure context.
        
        Args:
            template: The repair goal template to use.
            failure_context: The failure context providing details.
            
        Returns:
            A structured RepairGoal instance.
        """
        goal_id = str(uuid.uuid4())
        description = template.description_template.format(
            failure_description=failure_context.description
        )
        success_criteria = template.success_criteria_template.format(
            failure_details=str(failure_context.details)
        )
        
        # Resolve prerequisite goals by finding already generated goals of required types
        prerequisite_goals = self._find_prerequisite_goals(template.prerequisite_goal_types)
        
        return RepairGoal(
            goal_id=goal_id,
            goal_type=template.goal_type,
            priority=template.priority.value,
            description=description,
            failure_context=failure_context,
            prerequisite_goals=prerequisite_goals,
            estimated_complexity=template.estimated_complexity.value,
            success_criteria=success_criteria,
            created_at=datetime.utcnow(),
            status="pending"
        )

    def _find_prerequisite_goals(self, prerequisite_goal_types: List[str]) -> List[str]:
        """
        Find IDs of previously generated goals that match the prerequisite types.
        
        Args:
            prerequisite_goal_types: List of goal types that are prerequisites.
            
        Returns:
            List of goal IDs that satisfy the prerequisites.
        """
        prerequisite_ids = []
        for goal_id in self._generated_goal_ids:
            goal = self.goal_queue.get_goal(goal_id)
            if goal and goal.goal_type in prerequisite_goal_types:
                prerequisite_ids.append(goal_id)
        return prerequisite_ids

    def generate_repair_goal(self, failure_context: FailureContext) -> Optional[RepairGoal]:
        """
        Generate a repair goal from a failure context.
        
        Args:
            failure_context: The failure context from the recorder.
            
        Returns:
            A RepairGoal if a template is found, None otherwise.
        """
        failure_type = self.analyze_failure_pattern(failure_context)
        
        if failure_type == FailureType.UNKNOWN:
            return None
        
        template = REPAIR_GOAL_TEMPLATES.get(failure_type)
        if template is None:
            return None
        
        return self.generate_goal_from_template(template, failure_context)

    def insert_repair_goal(self, failure_context: FailureContext) -> Optional[str]:
        """
        Generate and insert a repair goal into the goal queue.
        
        Args:
            failure_context: The failure context to process.
            
        Returns:
            The goal ID if inserted, None otherwise.
        """
        repair_goal = self.generate_repair_goal(failure_context)
        
        if repair_goal is None:
            return None
        
        # Insert into goal queue
        success = self.goal_queue.add_goal(repair_goal)
        
        if success:
            self._generated_goal_ids.append(repair_goal.goal_id)
            return repair_goal.goal_id
        
        return None

    def process_failure_contexts(self, failure_contexts: List[FailureContext]) -> List[str]:
        """
        Process multiple failure contexts and generate repair goals for each.
        
        Args:
            failure_contexts: List of failure contexts to process.
            
        Returns:
            List of generated goal IDs.
        """
        generated_ids = []
        for context in failure_contexts:
            goal_id = self.insert_repair_goal(context)
            if goal_id:
                generated_ids.append(goal_id)
        return generated_ids

    def clear_generated_goals(self) -> None:
        """Clear the tracking of generated goal IDs."""
        self._generated_goal_ids.clear()