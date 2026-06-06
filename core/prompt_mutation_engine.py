import json
import re
from datetime import datetime
from typing import List, Optional, Dict, Any

class PromptMutationEngine:
    """
    Handles the mechanics of mutating the meta-cognition prompt.
    
    This engine parses prompts into constraints, applies mutation operators,
    validates syntactic correctness, and maintains a mutation history log.
    """
    
    def __init__(self, initial_prompt: str = "", failure_memory=None):
        self.mutation_history: List[Dict[str, Any]] = []
        self.current_prompt = initial_prompt
        self.constraints: List[str] = []
        self.failure_memory = failure_memory
        self.lessons_learned_path = "knowledge/lessons_learned.json"
        self._parse_constraints()
        
    def _parse_constraints(self) -> None:
        """Parse the current prompt into a list of constraints."""
        if not self.current_prompt.strip():
            self.constraints = []
            return
            
        # Split on common constraint delimiters: newlines, semicolons, or numbered lists
        raw_constraints = re.split(r'[;\n]|(?:\d+\.\s*)', self.current_prompt)
        
        self.constraints = []
        for constraint in raw_constraints:
            cleaned = constraint.strip()
            if cleaned and len(cleaned) > 3:  # Ignore very short fragments
                self.constraints.append(cleaned)
                
    def add_constraint(self, text: str) -> bool:
        """
        Add a new constraint to the prompt.
        
        Args:
            text: The constraint text to add
            
        Returns:
            True if the constraint was added successfully, False otherwise
        """
        if not text or not text.strip():
            return False
            
        # Validate the constraint text
        if not self._validate_constraint_text(text):
            return False
            
        self.constraints.append(text.strip())
        self._rebuild_prompt()
        self._log_mutation("add_constraint", {"text": text})
        return True
        
    def delete_constraint(self, index: int) -> bool:
        """
        Delete a constraint at the given index.
        
        Args:
            index: The index of the constraint to delete
            
        Returns:
            True if the constraint was deleted successfully, False otherwise
        """
        if index < 0 or index >= len(self.constraints):
            return False
            
        removed = self.constraints.pop(index)
        self._rebuild_prompt()
        self._log_mutation("delete_constraint", {"index": index, "removed": removed})
        return True
        
    def swap_constraints(self, i: int, j: int) -> bool:
        """
        Swap two constraints at the given indices.
        
        Args:
            i: First constraint index
            j: Second constraint index
            
        Returns:
            True if the swap was successful, False otherwise
        """
        if i < 0 or i >= len(self.constraints) or j < 0 or j >= len(self.constraints):
            return False
        if i == j:
            return False
            
        self.constraints[i], self.constraints[j] = self.constraints[j], self.constraints[i]
        self._rebuild_prompt()
        self._log_mutation("swap_constraints", {"index_i": i, "index_j": j})
        return True
        
    def _validate_constraint_text(self, text: str) -> bool:
        """
        Validate that a constraint text is syntactically valid.
        
        Args:
            text: The constraint text to validate
            
        Returns:
            True if the text is valid, False otherwise
        """
        # Check for basic syntactic validity
        if not text or not text.strip():
            return False
            
        # Check for unbalanced brackets, parentheses, or quotes
        stack = []
        quote_char = None
        
        for char in text:
            if quote_char:
                if char == quote_char:
                    quote_char = None
                continue
                
            if char in '"\'':
                quote_char = char
            elif char in '([{':
                stack.append(char)
            elif char in ')]}':
                if not stack:
                    return False
                expected = {'(': ')', '[': ']', '{': '}'}
                if expected.get(stack.pop()) != char:
                    return False
                    
        if quote_char or stack:
            return False
            
        # Check for minimum meaningful content
        if len(text.strip()) < 5:
            return False
            
        return True
        
    def validate_prompt(self, prompt: Optional[str] = None) -> bool:
        """
        Validate that the current prompt (or a given prompt) is syntactically valid.
        
        Args:
            prompt: Optional prompt to validate; if None, validates current prompt
            
        Returns:
            True if the prompt is valid, False otherwise
        """
        if prompt is None:
            prompt = self.current_prompt
            
        if not prompt or not prompt.strip():
            return False
            
        # Validate each constraint individually
        for constraint in self.constraints:
            if not self._validate_constraint_text(constraint):
                return False
                
        # Check for overall prompt structure
        # A valid prompt should not have consecutive empty lines
        lines = prompt.split('\n')
        empty_count = 0
        for line in lines:
            if not line.strip():
                empty_count += 1
                if empty_count > 2:  # More than 2 consecutive empty lines is invalid
                    return False
            else:
                empty_count = 0
                
        return True
        
    def _rebuild_prompt(self) -> None:
        """Rebuild the current prompt from the list of constraints."""
        if not self.constraints:
            self.current_prompt = ""
            return
            
        # Rebuild as a numbered list
        numbered_constraints = []
        for i, constraint in enumerate(self.constraints, 1):
            numbered_constraints.append(f"{i}. {constraint}")
            
        base_prompt = "\n".join(numbered_constraints)
        
        # Append lessons learned section if failure_memory is available
        if self.failure_memory is not None:
            lessons = self._get_failure_lessons()
            if lessons:
                base_prompt += "\n\n=== LESSONS FROM RECENT FAILURES ===\n" + "\n".join(lessons)
        
        self.current_prompt = base_prompt
        
    def _get_failure_lessons(self) -> List[str]:
        """
        Retrieve the last 5-10 failure lessons from FailureMemory.
        
        Returns:
            List of formatted failure lesson strings
        """
        if self.failure_memory is None:
            return []
        
        try:
            # Try to get failures from failure_memory
            if hasattr(self.failure_memory, 'get_recent_failures'):
                failures = self.failure_memory.get_recent_failures(10)
            elif hasattr(self.failure_memory, 'get_failures'):
                failures = self.failure_memory.get_failures()[-10:]
            else:
                # Fallback: try to access as list-like
                failures = list(self.failure_memory)[-10:]
            
            if not failures:
                return []
            
            # Take last 5-10 failures
            failures = failures[-10:]
            if len(failures) > 10:
                failures = failures[-10:]
            if len(failures) < 5:
                failures = failures
            
            lessons = []
            for failure in failures:
                if isinstance(failure, dict):
                    error_type = failure.get('error_type', 'UNKNOWN')
                    module = failure.get('module', 'unknown')
                    message = failure.get('message', 'No details')
                elif hasattr(failure, 'error_type') and hasattr(failure, 'module') and hasattr(failure, 'message'):
                    error_type = failure.error_type
                    module = failure.module
                    message = failure.message
                else:
                    error_type = 'UNKNOWN'
                    module = 'unknown'
                    message = str(failure)[:100]
                
                lesson = f"FAILURE: [{error_type}] in [{module}] - {message}"
                lessons.append(lesson)
            
            return lessons
            
        except Exception:
            return []
        
    def _log_mutation(self, operation: str, details: Dict[str, Any]) -> None:
        """
        Log a mutation operation to the history.
        
        Args:
            operation: The type of mutation performed
            details: Details about the mutation
        """
        self.mutation_history.append({
            "timestamp": datetime.now().isoformat(),
            "operation": operation,
            "details": details,
            "constraint_count": len(self.constraints),
            "prompt_preview": self.current_prompt[:100] + "..." if len(self.current_prompt) > 100 else self.current_prompt
        })
        
    def get_mutation_history(self) -> List[Dict[str, Any]]:
        """
        Get the full mutation history log.
        
        Returns:
            List of mutation history entries
        """
        return self.mutation_history.copy()
        
    def get_constraints(self) -> List[str]:
        """
        Get the current list of constraints.
        
        Returns:
            List of constraint strings
        """
        return self.constraints.copy()
        
    def get_prompt(self) -> str:
        """
        Get the current prompt.
        
        Returns:
            The current prompt string
        """
        return self.current_prompt
        
    def set_prompt(self, prompt: str) -> None:
        """
        Set a new prompt and re-parse constraints.
        
        Args:
            prompt: The new prompt string
        """
        self.current_prompt = prompt
        self._parse_constraints()
        self._log_mutation("set_prompt", {"length": len(prompt)})
        
    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize the engine state to a dictionary.
        
        Returns:
            Dictionary containing the engine state
        """
        return {
            "current_prompt": self.current_prompt,
            "constraints": self.constraints,
            "mutation_history": self.mutation_history
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PromptMutationEngine':
        """
        Create a PromptMutationEngine from a serialized dictionary.
        
        Args:
            data: Dictionary containing engine state
            
        Returns:
            A new PromptMutationEngine instance
        """
        engine = cls(data.get("current_prompt", ""))
        engine.constraints = data.get("constraints", [])
        engine.mutation_history = data.get("mutation_history", [])
        return engine
        
    def __repr__(self) -> str:
        return f"PromptMutationEngine(constraints={len(self.constraints)}, history={len(self.mutation_history)})"
        
    def _load_lessons_learned(self) -> Dict[str, Any]:
        """
        Load the lessons_learned.json knowledge base.
        
        Returns:
            Dictionary containing lessons learned data, or empty dict if file not found
        """
        try:
            with open(self.lessons_learned_path, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
    
    def _get_module_from_proposal(self, proposal: str) -> Optional[str]:
        """
        Extract the target module name from a mutation proposal.
        
        Args:
            proposal: The mutation proposal string
            
        Returns:
            The module name if found, None otherwise
        """
        # Look for common patterns like "module: X", "in module X", "file: X.py"
        patterns = [
            r'(?:module|file|target)\s*[:=]\s*([\w./]+)',
            r'(?:in|for|of)\s+(?:the\s+)?(?:module|file)\s+[\"\'`]?([\w./]+)[\"\'`]?',
            r'([\w./]+\.py)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, proposal, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        # Fallback: try to find any path-like string
        path_match = re.search(r'[\w./]+/\w+', proposal)
        if path_match:
            return path_match.group(0)
        
        return None
    
    def _query_lessons_for_module(self, module: str) -> List[Dict[str, Any]]:
        """
        Query lessons_learned.json for known failure patterns for a specific module.
        
        Args:
            module: The module name to query
            
        Returns:
            List of failure patterns found for the module
        """
        lessons = self._load_lessons_learned()
        if not lessons:
            return []
        
        # Normalize module name for comparison
        module_lower = module.lower()
        module_clean = module_lower.replace('.py', '').replace('/', '.').replace('\\', '.')
        
        matching_lessons = []
        
        # Check for module-specific entries
        if 'modules' in lessons and module_clean in lessons['modules']:
            module_lessons = lessons['modules'][module_clean]
            if isinstance(module_lessons, list):
                matching_lessons.extend(module_lessons)
            elif isinstance(module_lessons, dict):
                matching_lessons.append(module_lessons)
        
        # Check for general failure patterns that might apply
        if 'failures' in lessons:
            for failure in lessons['failures']:
                if isinstance(failure, dict):
                    failure_module = failure.get('module', '').lower().replace('.py', '').replace('/', '.').replace('\\', '.')
                    if module_clean in failure_module or failure_module in module_clean:
                        matching_lessons.append(failure)
        
        # Check for patterns that mention the module
        if 'patterns' in lessons:
            for pattern in lessons['patterns']:
                if isinstance(pattern, dict):
                    pattern_text = pattern.get('pattern', '').lower()
                    if module_clean in pattern_text:
                        matching_lessons.append(pattern)
        
        return matching_lessons
    
    def _format_lesson_warning(self, lesson: Dict[str, Any]) -> str:
        """
        Format a lesson into a warning string for the prompt context.
        
        Args:
            lesson: The lesson dictionary
            
        Returns:
            Formatted warning string
        """
        pattern = lesson.get('pattern', lesson.get('failure', 'Unknown failure pattern'))
        fix = lesson.get('fix', lesson.get('suggestion', 'No fix suggestion available'))
        module = lesson.get('module', 'unknown')
        
        return (
            f"KNOWN FAILURE PATTERN - AVOID THIS APPROACH\n"
            f"Module: {module}\n"
            f"Pattern: {pattern}\n"
            f"Suggested Fix: {fix}\n"
        )
    
    def apply_pre_generation_hook(self, proposal: str) -> str:
        """
        Apply the pre-generation hook to check lessons_learned KB before generating code.
        
        Args:
            proposal: The mutation proposal string
            
        Returns:
            The prompt context with any relevant warnings prepended
        """
        # Step 1: Identify the target module from the mutation proposal
        target_module = self._get_module_from_proposal(proposal)
        
        if not target_module:
            # No module identified, return current prompt as-is
            return self.current_prompt
        
        # Step 2: Check lessons_learned.json for known failure patterns for that module
        matching_lessons = self._query_lessons_for_module(target_module)
        
        if not matching_lessons:
            # No matching lessons found, return current prompt as-is
            return self.current_prompt
        
        # Step 3: If found, prepend a warning with the fix suggestion to the prompt context
        warnings = []
        for lesson in matching_lessons:
            warning = self._format_lesson_warning(lesson)
            warnings.append(warning)
        
        warning_section = "\n\n".join(warnings)
        
        # Prepend the warning to the current prompt
        if self.current_prompt:
            modified_prompt = f"{warning_section}\n\n{self.current_prompt}"
        else:
            modified_prompt = warning_section
        
        # Log the hook application
        self._log_mutation("pre_generation_hook", {
            "target_module": target_module,
            "lessons_found": len(matching_lessons),
            "warnings_applied": True
        })
        
        return modified_prompt
    
    def set_lessons_learned_path(self, path: str) -> None:
        """
        Set the path to the lessons_learned.json file.
        
        Args:
            path: The file path to the lessons learned knowledge base
        """
        self.lessons_learned_path = path

    def _query_pattern_in_lessons(self, pattern_name: str) -> Optional[Dict[str, Any]]:
        """
        Query lessons_learned.json for a specific pattern by name.
        
        Args:
            pattern_name: The name of the pattern to search for (e.g., 'repeated_goal_generation')
            
        Returns:
            The pattern entry if found, None otherwise
        """
        lessons = self._load_lessons_learned()
        if not lessons:
            return None
        
        # Normalize pattern name for comparison
        pattern_lower = pattern_name.lower().strip()
        
        # Check in patterns list
        if 'patterns' in lessons:
            for pattern in lessons['patterns']:
                if isinstance(pattern, dict):
                    pattern_entry_name = pattern.get('name', '').lower().strip()
                    if pattern_entry_name == pattern_lower:
                        return pattern
        
        # Check in failures list as fallback
        if 'failures' in lessons:
            for failure in lessons['failures']:
                if isinstance(failure, dict):
                    failure_pattern = failure.get('pattern', '').lower().strip()
                    if pattern_lower in failure_pattern:
                        return failure
        
        return None

    def _inject_pattern_fix_into_prompt(self, pattern_entry: Dict[str, Any]) -> str:
        """
        Inject a fix suggestion from a pattern entry into the prompt context.
        
        Args:
            pattern_entry: The pattern entry containing fix suggestion
            
        Returns:
            Modified prompt with fix suggestion injected
        """
        fix_suggestion = pattern_entry.get('fix', pattern_entry.get('suggestion', ''))
        pattern_name = pattern_entry.get('name', 'Unknown pattern')
        
        if not fix_suggestion:
            return self.current_prompt
        
        fix_injection = (
            f"\n\n=== FIX SUGGESTION FOR KNOWN PATTERN: {pattern_name} ===\n"
            f"The following fix is recommended to avoid a known failure pattern:\n"
            f"{fix_suggestion}\n"
            f"Please incorporate this fix into the generated code.\n"
        )
        
        if self.current_prompt:
            modified_prompt = self.current_prompt + fix_injection
        else:
            modified_prompt = fix_injection
        
        return modified_prompt

    def check_and_inject_repeated_goal_fix(self, target_module: str) -> str:
        """
        Check for 'repeated_goal_generation' pattern in lessons_learned KB and inject fix if found.
        This method specifically targets goal_generator and any module involved in goal creation.
        
        Args:
            target_module: The module name being targeted for code generation
            
        Returns:
            Modified prompt with fix suggestion injected if pattern exists, original prompt otherwise
        """
        # Define modules involved in goal creation
        goal_creation_modules = [
            'goal_generator',
            'goal_generator.py',
            'core/goal_generator',
            'core/goal_generator.py',
            'goal_creator',
            'goal_creator.py',
            'core/goal_creator',
            'core/goal_creator.py'
        ]
        
        # Check if the target module is involved in goal creation
        target_lower = target_module.lower().replace('.py', '').replace('/', '.').replace('\\', '.')
        is_goal_creation_module = any(
            goal_mod.lower().replace('.py', '').replace('/', '.').replace('\\', '.') in target_lower or
            target_lower in goal_mod.lower().replace('.py', '').replace('/', '.').replace('\\', '.')
            for goal_mod in goal_creation_modules
        )
        
        if not is_goal_creation_module:
            return self.current_prompt
        
        # Query for the 'repeated_goal_generation' pattern
        pattern_entry = self._query_pattern_in_lessons('repeated_goal_generation')
        
        if pattern_entry is None:
            return self.current_prompt
        
        # Inject the fix suggestion into the prompt context
        modified_prompt = self._inject_pattern_fix_into_prompt(pattern_entry)
        
        # Log the injection
        self._log_mutation("inject_repeated_goal_fix", {
            "target_module": target_module,
            "pattern_found": "repeated_goal_generation",
            "fix_injected": True
        })
        
        return modified_prompt

    def apply_pre_generation_hook_with_pattern_check(self, proposal: str) -> str:
        """
        Enhanced pre-generation hook that also checks for 'repeated_goal_generation' pattern
        before generating code for goal_generator or any module involved in goal creation.
        
        Args:
            proposal: The mutation proposal string
            
        Returns:
            The prompt context with any relevant warnings and fix suggestions injected
        """
        # First, apply the standard pre-generation hook
        prompt_context = self.apply_pre_generation_hook(proposal)
        
        # Temporarily set current_prompt to the modified context for pattern check
        original_prompt = self.current_prompt
        self.current_prompt = prompt_context
        
        try:
            # Identify the target module from the proposal
            target_module = self._get_module_from_proposal(proposal)
            
            if target_module:
                # Check and inject repeated_goal_generation fix if applicable
                prompt_context = self.check_and_inject_repeated_goal_fix(target_module)
        finally:
            # Restore original prompt
            self.current_prompt = original_prompt
        
        return prompt_context