"""Fallback Mutation Generator

This module provides a fallback mechanism for generating safe, simple mutations
when the reflection engine fails to produce a concrete_mutation_spec.
It randomly selects from a set of predefined safe mutation operations.
"""

import ast
import random
from pathlib import Path
from typing import Optional, Tuple

# Common typos to fix in comments
COMMON_TYPOS = {
    "teh": "the",
    "recieve": "receive",
    "definately": "definitely",
    "seperate": "separate",
    "occured": "occurred",
    "accomodate": "accommodate",
    "wich": "which",
    "thier": "their",
    "recieved": "received",
    "alot": "a lot",
    "untill": "until",
    "writen": "written",
    "occuring": "occurring",
    "occurence": "occurrence",
    "fufill": "fulfill",
    "embarass": "embarrass",
    "neccessary": "necessary",
    "comittee": "committee",
    "guage": "gauge",
    "calender": "calendar",
}

# Common unused imports that can be safely removed
COMMON_UNUSED_IMPORTS = [
    "from __future__ import annotations",
    "import typing",
    "from typing import Optional",
    "from typing import List",
    "from typing import Dict",
    "from typing import Tuple",
    "from typing import Any",
    "import os",
    "import sys",
    "import json",
    "import re",
    "from pathlib import Path",
    "import logging",
    "from dataclasses import dataclass",
    "from abc import ABC, abstractmethod",
    "import random",
    "import math",
    "from collections import defaultdict",
    "from enum import Enum",
    "import itertools",
    "from functools import partial",
]


def _find_python_files(base_path: str = ".") -> list[Path]:
    """Find all Python files in the project directory."""
    base = Path(base_path)
    python_files = []
    for path in base.rglob("*.py"):
        # Skip __pycache__ and virtual environments
        if "__pycache__" in str(path) or ".venv" in str(path) or "venv" in str(path):
            continue
        python_files.append(path)
    return python_files


def _add_docstring_to_file(file_path: Path) -> Tuple[bool, str]:
    """Add a simple docstring to a module that doesn't have one."""
    try:
        content = file_path.read_text(encoding="utf-8")
        tree = ast.parse(content)

        # Check if module already has a docstring
        if (
            tree.body
            and isinstance(tree.body[0], ast.Expr)
            and isinstance(tree.body[0].value, ast.Constant)
            and isinstance(tree.body[0].value.value, str)
        ):
            return False, f"{file_path} already has a module docstring"

        # Generate a simple docstring based on the file name
        module_name = file_path.stem.replace("_", " ").replace("-", " ").title()
        docstring = f'"""{module_name} Module\n\nAuto-generated docstring for {file_path.name}.\n"""\n\n'

        # Insert docstring at the beginning of the file
        new_content = docstring + content
        file_path.write_text(new_content, encoding="utf-8")
        return True, f"Added docstring to {file_path}"

    except (SyntaxError, UnicodeDecodeError) as e:
        return False, f"Failed to add docstring to {file_path}: {e}"


def _fix_typos_in_comments(file_path: Path) -> Tuple[bool, str]:
    """Fix common typos in comments within a Python file."""
    try:
        content = file_path.read_text(encoding="utf-8")
        original_content = content
        lines = content.split("\n")
        fixed_count = 0

        for i, line in enumerate(lines):
            # Only process comment lines or inline comments
            if "#" in line:
                comment_start = line.index("#")
                comment = line[comment_start:]

                # Check for typos in the comment
                new_comment = comment
                for typo, correction in COMMON_TYPOS.items():
                    # Case-insensitive replacement within the comment
                    if typo.lower() in comment.lower():
                        # Use regex-like approach to preserve case
                        idx = comment.lower().find(typo.lower())
                        while idx != -1:
                            original_word = comment[idx : idx + len(typo)]
                            # Preserve case pattern
                            if original_word.islower():
                                replacement = correction
                            elif original_word.istitle():
                                replacement = correction.title()
                            elif original_word.isupper():
                                replacement = correction.upper()
                            else:
                                replacement = correction
                            new_comment = (
                                new_comment[:idx]
                                + replacement
                                + new_comment[idx + len(typo) :]
                            )
                            idx = new_comment.lower().find(
                                typo.lower(), idx + len(replacement)
                            )
                            fixed_count += 1

                if new_comment != comment:
                    lines[i] = line[:comment_start] + new_comment

        if fixed_count > 0:
            new_content = "\n".join(lines)
            file_path.write_text(new_content, encoding="utf-8")
            return (
                True,
                f"Fixed {fixed_count} typo(s) in comments in {file_path}",
            )
        return False, f"No typos found in {file_path}"

    except (UnicodeDecodeError, OSError) as e:
        return False, f"Failed to fix typos in {file_path}: {e}"


def _remove_unused_import(file_path: Path) -> Tuple[bool, str]:
    """Try to remove a common unused import from a Python file."""
    try:
        content = file_path.read_text(encoding="utf-8")
        original_content = content
        lines = content.split("\n")
        removed_count = 0

        # Try to find and remove common unused imports
        for import_stmt in COMMON_UNUSED_IMPORTS:
            # Check if the import exists in the file
            if import_stmt in content:
                # Verify it's on its own line
                for i, line in enumerate(lines):
                    stripped = line.strip()
                    if stripped == import_stmt:
                        # Check if the imported name is actually used
                        import_name = import_stmt.split()[-1]
                        if import_name.startswith("from"):
                            # Handle 'from X import Y' style
                            import_name = import_stmt.split()[-1]
                        else:
                            # Handle 'import X' style
                            import_name = import_stmt.split()[-1]

                        # Simple check: see if the name appears elsewhere in the file
                        # (excluding the import line itself)
                        other_lines = lines[:i] + lines[i + 1 :]
                        other_content = "\n".join(other_lines)

                        # Check if the imported name is used (case-sensitive)
                        if import_name not in other_content:
                            lines.pop(i)
                            removed_count += 1
                            break

        if removed_count > 0:
            new_content = "\n".join(lines)
            file_path.write_text(new_content, encoding="utf-8")
            return (
                True,
                f"Removed {removed_count} unused import(s) from {file_path}",
            )
        return False, f"No unused imports found in {file_path}"

    except (UnicodeDecodeError, OSError) as e:
        return False, f"Failed to remove unused imports from {file_path}: {e}"


def generate_fallback_mutation(
    base_path: str = ".",
    seed: Optional[int] = None,
) -> Tuple[bool, str]:
    """Generate a random fallback mutation.

    Randomly selects one of the safe mutation operations and applies it
    to a random Python file in the project.

    Args:
        base_path: Root directory to search for Python files
        seed: Optional random seed for reproducibility

    Returns:
        Tuple of (success, message) describing the mutation result
    """
    if seed is not None:
        random.seed(seed)

    python_files = _find_python_files(base_path)
    if not python_files:
        return False, "No Python files found to mutate"

    # Select a random file
    target_file = random.choice(python_files)

    # Select a random mutation operation
    mutation_operations = [
        _add_docstring_to_file,
        _fix_typos_in_comments,
        _remove_unused_import,
    ]
    mutation_func = random.choice(mutation_operations)

    # Apply the mutation
    success, message = mutation_func(target_file)
    return success, message


def generate_safe_mutation(
    base_path: str = ".",
    preferred_type: Optional[str] = None,
    seed: Optional[int] = None,
) -> Tuple[bool, str]:
    """Generate a safe mutation, optionally preferring a specific type.

    Args:
        base_path: Root directory to search for Python files
        preferred_type: Optional preference ('docstring', 'typo', 'import')
        seed: Optional random seed for reproducibility

    Returns:
        Tuple of (success, message) describing the mutation result
    """
    if seed is not None:
        random.seed(seed)

    python_files = _find_python_files(base_path)
    if not python_files:
        return False, "No Python files found to mutate"

    # Filter by preferred type if specified
    mutation_map = {
        "docstring": _add_docstring_to_file,
        "typo": _fix_typos_in_comments,
        "import": _remove_unused_import,
    }

    if preferred_type and preferred_type in mutation_map:
        mutation_func = mutation_map[preferred_type]
    else:
        mutation_func = random.choice(list(mutation_map.values()))

    # Try up to 3 random files to find one that works
    for _ in range(min(3, len(python_files))):
        target_file = random.choice(python_files)
        success, message = mutation_func(target_file)
        if success:
            return success, message

    return False, "Failed to apply any mutation after 3 attempts"


if __name__ == "__main__":
    # Example usage
    success, message = generate_fallback_mutation()
    print(f"Mutation {'succeeded' if success else 'failed'}: {message}")