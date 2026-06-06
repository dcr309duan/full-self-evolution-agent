"""core/reflection_engine.py

Reflection engine that enforces concrete mutation specifications in all reflection outputs.
Every reflection must include a 'concrete_mutation_spec' field containing a valid Python mutation.
"""

import ast
import difflib
import re
from typing import Any, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field, asdict
from enum import Enum

from core.fallback_mutation_generator import generate_fallback_mutation


class MutationChangeType(Enum):
    """Types of code changes that can be specified in a mutation."""
    CREATE = "create"
    MODIFY = "modify"
    DELETE = "delete"
    RENAME = "rename"
    MOVE = "move"


class ValidationError(Exception):
    """Raised when a reflection fails validation."""
    pass


@dataclass
class ConcreteMutationSpec:
    """Specification for a concrete code mutation.
    
    Attributes:
        file_path: Path to the target file relative to project root.
        change_type: Type of change to perform (create, modify, delete, etc.).
        code_diff: Unified diff string representing the change. For CREATE, this
                   should be the full file content with '+' lines.
        description: Human-readable description of the mutation.
        target_symbol: Optional name of the symbol being modified (function, class, etc.).
    """
    file_path: str
    change_type: MutationChangeType
    code_diff: str
    description: str = ""
    target_symbol: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = asdict(self)
        result["change_type"] = self.change_type.value
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConcreteMutationSpec":
        """Create from dictionary."""
        if isinstance(data.get("change_type"), str):
            data["change_type"] = MutationChangeType(data["change_type"])
        return cls(**data)


@dataclass
class Reflection:
    """A reflection object that must include a concrete_mutation_spec.
    
    Attributes:
        content: The main reflection content/analysis text.
        concrete_mutation_spec: Required field specifying a concrete mutation.
        confidence: Optional confidence score (0.0 to 1.0).
        metadata: Optional additional metadata dictionary.
    """
    content: str
    concrete_mutation_spec: ConcreteMutationSpec
    confidence: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "content": self.content,
            "concrete_mutation_spec": self.concrete_mutation_spec.to_dict(),
            "confidence": self.confidence,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Reflection":
        """Create from dictionary, validating required fields."""
        if "concrete_mutation_spec" not in data:
            raise ValidationError(
                "Reflection missing required field 'concrete_mutation_spec'"
            )
        spec_data = data["concrete_mutation_spec"]
        if not isinstance(spec_data, ConcreteMutationSpec):
            spec_data = ConcreteMutationSpec.from_dict(spec_data)
        return cls(
            content=data["content"],
            concrete_mutation_spec=spec_data,
            confidence=data.get("confidence"),
            metadata=data.get("metadata", {}),
        )


def validate_mutation_spec(spec: ConcreteMutationSpec) -> List[str]:
    """Validate a ConcreteMutationSpec and return list of error messages.
    
    Returns empty list if valid.
    """
    errors: List[str] = []

    # Validate file_path
    if not spec.file_path:
        errors.append("file_path must be non-empty")
    elif not isinstance(spec.file_path, str):
        errors.append("file_path must be a string")
    else:
        # Check for path traversal attempts
        if ".." in spec.file_path.split("/"):
            errors.append("file_path must not contain path traversal sequences")
        # Check for absolute paths (should be relative)
        if spec.file_path.startswith("/"):
            errors.append("file_path should be relative, not absolute")

    # Validate change_type
    if not isinstance(spec.change_type, MutationChangeType):
        errors.append(f"change_type must be a MutationChangeType enum value")

    # Validate code_diff
    if not spec.code_diff:
        errors.append("code_diff must be non-empty")
    elif not isinstance(spec.code_diff, str):
        errors.append("code_diff must be a string")
    else:
        # Check that diff has proper unified diff format
        lines = spec.code_diff.split("\n")
        has_diff_header = any(
            line.startswith("--- ") or line.startswith("+++ ")
            for line in lines[:5]
        )
        has_hunk_header = any(
            line.startswith("@@ ") for line in lines
        )
        
        if spec.change_type in (MutationChangeType.MODIFY, MutationChangeType.DELETE):
            if not has_diff_header:
                errors.append("MODIFY/DELETE diffs should have '---'/'+++' headers")
            if not has_hunk_header:
                errors.append("MODIFY/DELETE diffs should have '@@' hunk headers")
        
        # For CREATE, diff should start with '+++ b/'
        if spec.change_type == MutationChangeType.CREATE:
            if not any(line.startswith("+++ b/") for line in lines[:5]):
                errors.append("CREATE diffs should have '+++ b/' header")

        # Validate Python syntax for the added/modified code
        if spec.change_type in (MutationChangeType.CREATE, MutationChangeType.MODIFY):
            python_errors = _validate_python_syntax_in_diff(spec.code_diff)
            errors.extend(python_errors)

    # Validate description (optional but recommended)
    if spec.description and not isinstance(spec.description, str):
        errors.append("description must be a string if provided")

    return errors


def _validate_python_syntax_in_diff(diff_text: str) -> List[str]:
    """Extract added lines from a diff and validate they are valid Python syntax.
    
    Returns list of syntax error messages (empty if valid).
    """
    errors: List[str] = []
    
    # Extract lines that are additions (start with '+')
    added_lines = []
    for line in diff_text.split("\n"):
        # Skip diff headers and hunk markers
        if line.startswith("---") or line.startswith("+++") or line.startswith("@@"):
            continue
        # Skip context lines (starting with space)
        if line.startswith(" "):
            continue
        # Collect added lines (strip the leading '+')
        if line.startswith("+"):
            added_lines.append(line[1:])  # Remove the leading '+'
    
    if not added_lines:
        return errors  # No code to validate
    
    # Try to parse as a complete module
    code_to_check = "\n".join(added_lines)
    try:
        ast.parse(code_to_check)
    except SyntaxError as e:
        errors.append(f"Added code has Python syntax error: {e}")
    
    return errors


def validate_reflection(reflection: Union[Reflection, Dict[str, Any]]) -> Tuple[bool, List[str]]:
    """Validate a reflection object.
    
    Args:
        reflection: Either a Reflection dataclass instance or a dictionary.
    
    Returns:
        Tuple of (is_valid, list_of_error_messages).
    """
    if isinstance(reflection, dict):
        try:
            reflection = Reflection.from_dict(reflection)
        except ValidationError as e:
            return False, [str(e)]
        except (KeyError, TypeError, ValueError) as e:
            return False, [f"Invalid reflection structure: {e}"]
    
    errors: List[str] = []
    
    # Validate content
    if not reflection.content:
        errors.append("Reflection content must be non-empty")
    
    # Validate concrete_mutation_spec exists
    if not reflection.concrete_mutation_spec:
        errors.append("Reflection missing required field 'concrete_mutation_spec'")
        return False, errors
    
    # Validate the mutation spec
    spec_errors = validate_mutation_spec(reflection.concrete_mutation_spec)
    errors.extend(f"concrete_mutation_spec.{e}" for e in spec_errors)
    
    # Validate confidence if provided
    if reflection.confidence is not None:
        if not isinstance(reflection.confidence, (int, float)):
            errors.append("confidence must be a number")
        elif not 0.0 <= reflection.confidence <= 1.0:
            errors.append("confidence must be between 0.0 and 1.0")
    
    return len(errors) == 0, errors


def generate_reflection(
    content: str,
    file_path: str,
    change_type: Union[str, MutationChangeType],
    code_diff: str,
    description: str = "",
    target_symbol: Optional[str] = None,
    confidence: Optional[float] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Reflection:
    """Generate a reflection with a concrete mutation spec.
    
    This is the main function for creating reflections. It enforces that
    a concrete_mutation_spec is always provided. If the spec is missing or
    invalid, a fallback mutation is generated automatically.
    
    Args:
        content: The reflection content/analysis.
        file_path: Path to the target file.
        change_type: Type of change (create, modify, delete, etc.).
        code_diff: Unified diff string representing the change.
        description: Human-readable description of the mutation.
        target_symbol: Optional symbol being modified.
        confidence: Optional confidence score (0.0 to 1.0).
        metadata: Optional additional metadata.
    
    Returns:
        A validated Reflection object.
    
    Raises:
        ValidationError: If the generated reflection fails validation even after fallback.
    """
    if isinstance(change_type, str):
        change_type = MutationChangeType(change_type.lower())
    
    spec = ConcreteMutationSpec(
        file_path=file_path,
        change_type=change_type,
        code_diff=code_diff,
        description=description,
        target_symbol=target_symbol,
    )
    
    # Check if the spec is valid; if not, use fallback
    spec_errors = validate_mutation_spec(spec)
    if spec_errors:
        # Generate fallback mutation
        fallback_spec = generate_fallback_mutation(file_path)
        if fallback_spec:
            spec = fallback_spec
    
    reflection = Reflection(
        content=content,
        concrete_mutation_spec=spec,
        confidence=confidence,
        metadata=metadata or {},
    )
    
    is_valid, errors = validate_reflection(reflection)
    if not is_valid:
        raise ValidationError(
            f"Generated reflection failed validation:\n" + "\n".join(errors)
        )
    
    return reflection


def generate_diff(
    original_content: str,
    new_content: str,
    file_path: str,
) -> str:
    """Generate a unified diff string between original and new content.
    
    Args:
        original_content: The original file content.
        new_content: The new file content.
        file_path: The file path (used for diff headers).
    
    Returns:
        A unified diff string.
    """
    original_lines = original_content.splitlines(keepends=True)
    new_lines = new_content.splitlines(keepends=True)
    
    diff = difflib.unified_diff(
        original_lines,
        new_lines,
        fromfile=f"a/{file_path}",
        tofile=f"b/{file_path}",
    )
    
    return "".join(diff)


def create_mutation_spec_from_diff(
    file_path: str,
    change_type: Union[str, MutationChangeType],
    original_content: str,
    new_content: str,
    description: str = "",
    target_symbol: Optional[str] = None,
) -> ConcreteMutationSpec:
    """Create a ConcreteMutationSpec by computing the diff automatically.
    
    Args:
        file_path: Path to the target file.
        change_type: Type of change.
        original_content: Original file content.
        new_content: New file content.
        description: Human-readable description.
        target_symbol: Optional symbol being modified.
    
    Returns:
        A ConcreteMutationSpec with the computed diff.
    """
    if isinstance(change_type, str):
        change_type = MutationChangeType(change_type.lower())
    
    code_diff = generate_diff(original_content, new_content, file_path)
    
    return ConcreteMutationSpec(
        file_path=file_path,
        change_type=change_type,
        code_diff=code_diff,
        description=description,
        target_symbol=target_symbol,
    )


def validate_reflection_dict(reflection_dict: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate a reflection represented as a dictionary.
    
    This is useful for validating reflections received from external sources
    (e.g., LLM outputs) before converting to Reflection objects.
    
    Args:
        reflection_dict: Dictionary representation of a reflection.
    
    Returns:
        Tuple of (is_valid, list_of_error_messages).
    """
    errors: List[str] = []
    
    # Check required top-level fields
    if "content" not in reflection_dict:
        errors.append("Missing required field 'content'")
    elif not isinstance(reflection_dict["content"], str):
        errors.append("'content' must be a string")
    
    if "concrete_mutation_spec" not in reflection_dict:
        errors.append("Missing required field 'concrete_mutation_spec'")
        return False, errors
    
    spec = reflection_dict["concrete_mutation_spec"]
    if not isinstance(spec, dict):
        errors.append("'concrete_mutation_spec' must be a dictionary")
        return False, errors
    
    # Validate spec fields
    if "file_path" not in spec:
        errors.append("concrete_mutation_spec missing 'file_path'")
    if "change_type" not in spec:
        errors.append("concrete_mutation_spec missing 'change_type'")
    if "code_diff" not in spec:
        errors.append("concrete_mutation_spec missing 'code_diff'")
    
    # If we have all required spec fields, do full validation
    if all(k in spec for k in ("file_path", "change_type", "code_diff")):
        try:
            spec_obj = ConcreteMutationSpec.from_dict(spec)
            spec_errors = validate_mutation_spec(spec_obj)
            errors.extend(f"concrete_mutation_spec.{e}" for e in spec_errors)
        except (ValueError, TypeError) as e:
            errors.append(f"Invalid concrete_mutation_spec: {e}")
    
    return len(errors) == 0, errors


def batch_validate_reflections(
    reflections: List[Union[Reflection, Dict[str, Any]]]
) -> List[Tuple[bool, List[str]]]:
    """Validate multiple reflections at once.
    
    Args:
        reflections: List of Reflection objects or dictionaries.
    
    Returns:
        List of (is_valid, errors) tuples, one per reflection.
    """
    return [validate_reflection(r) for r in reflections]


def filter_valid_reflections(
    reflections: List[Union[Reflection, Dict[str, Any]]]
) -> List[Reflection]:
    """Filter a list of reflections, returning only valid ones.
    
    Invalid reflections are silently discarded.
    
    Args:
        reflections: List of Reflection objects or dictionaries.
    
    Returns:
        List of valid Reflection objects.
    """
    valid: List[Reflection] = []
    for r in reflections:
        is_valid, _ = validate_reflection(r)
        if is_valid:
            if isinstance(r, dict):
                try:
                    r = Reflection.from_dict(r)
                except (ValidationError, KeyError, TypeError, ValueError):
                    continue
            valid.append(r)
    return valid