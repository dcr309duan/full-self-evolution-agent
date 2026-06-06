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