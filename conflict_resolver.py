"""Automated rollback and conflict resolution module.

Maintains a registry of last stable snapshots per module (AST + hash).
Detects overlapping code regions via AST diff ranges.
Performs three-way merge using last stable snapshot as base.
On success, applies merged result and updates snapshot.
On failure, reverts both mutations to last stable snapshot and logs conflict details.
"""

import ast
import hashlib
import json
import copy
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Internal data structures
# ---------------------------------------------------------------------------

# Registry: module_path -> {"ast": AST_node, "hash": str}
_snapshot_registry: Dict[str, Dict[str, Any]] = {}

# Conflict log: list of conflict records
_conflict_log: List[Dict[str, Any]] = []

# Path to conflict log file
CONFLICT_LOG_PATH = Path("conflict_log.json")

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _compute_hash(ast_node: ast.AST) -> str:
    """Compute a deterministic hash of an AST node."""
    # Use AST's own dump to get a canonical representation
    try:
        dump = ast.dump(ast_node, indent=None)
    except TypeError:
        # Fallback for older Python versions
        dump = ast.dump(ast_node)
    return hashlib.sha256(dump.encode("utf-8")).hexdigest()


def _get_ast_ranges(ast_node: ast.AST) -> List[Tuple[int, int]]:
    """Extract line ranges from an AST node (start_line, end_line)."""
    ranges = []
    for node in ast.walk(ast_node):
        if hasattr(node, "lineno") and hasattr(node, "end_lineno"):
            ranges.append((node.lineno, node.end_lineno))
    return ranges


def _ranges_overlap(
    ranges1: List[Tuple[int, int]], ranges2: List[Tuple[int, int]]
) -> bool:
    """Check if any range in ranges1 overlaps with any range in ranges2."""
    for start1, end1 in ranges1:
        for start2, end2 in ranges2:
            if not (end1 < start2 or end2 < start1):
                return True
    return False


def _three_way_merge(
    base: ast.AST,
    mutation1: ast.AST,
    mutation2: ast.AST,
) -> Optional[ast.AST]:
    """
    Attempt a three-way merge of two mutations against a common base.
    Returns the merged AST if successful, None if conflict cannot be resolved.
    """
    # For simplicity, we use a line-by-line textual merge on the source code.
    # In a more advanced implementation, you could use AST-level merging.
    try:
        base_source = ast.unparse(base)
        source1 = ast.unparse(mutation1)
        source2 = ast.unparse(mutation2)
    except Exception:
        return None

    base_lines = base_source.splitlines(keepends=True)
    lines1 = source1.splitlines(keepends=True)
    lines2 = source2.splitlines(keepends=True)

    # Use Python's difflib to perform a three-way merge
    import difflib

    # Create unified diffs from base to each mutation
    diff1 = list(
        difflib.unified_diff(base_lines, lines1, n=0)
    )
    diff2 = list(
        difflib.unified_diff(base_lines, lines2, n=0)
    )

    # Simple heuristic: if both diffs modify the same lines, conflict
    # Extract changed line numbers from diffs
    changed_lines1 = set()
    changed_lines2 = set()
    for line in diff1:
        if line.startswith("@@") and len(line.split()) >= 3:
            # Format: @@ -start,count +start,count @@
            parts = line.split()
            old_info = parts[1]  # e.g., -10,5
            start_line = int(old_info.split(",")[0].lstrip("-"))
            count = int(old_info.split(",")[1]) if "," in old_info else 1
            for i in range(start_line, start_line + abs(count)):
                changed_lines1.add(i)
    for line in diff2:
        if line.startswith("@@") and len(line.split()) >= 3:
            parts = line.split()
            old_info = parts[1]
            start_line = int(old_info.split(",")[0].lstrip("-"))
            count = int(old_info.split(",")[1]) if "," in old_info else 1
            for i in range(start_line, start_line + abs(count)):
                changed_lines2.add(i)

    # If overlapping changed lines, conflict
    if changed_lines1 & changed_lines2:
        return None

    # Apply both diffs sequentially to base
    # This is a simplified approach; real three-way merge is more complex
    merged_lines = base_lines[:]
    # Apply diff1
    for line in diff1:
        if line.startswith("---") or line.startswith("+++") or line.startswith("@@"):
            continue
        if line.startswith("-"):
            # Remove line
            # Find the line in merged_lines (approximate)
            content = line[1:]
            if content in merged_lines:
                merged_lines.remove(content)
        elif line.startswith("+"):
            # Add line
            merged_lines.append(line[1:])
    # Apply diff2
    for line in diff2:
        if line.startswith("---") or line.startswith("+++") or line.startswith("@@"):
            continue
        if line.startswith("-"):
            content = line[1:]
            if content in merged_lines:
                merged_lines.remove(content)
        elif line.startswith("+"):
            merged_lines.append(line[1:])

    merged_source = "".join(merged_lines)
    try:
        merged_ast = ast.parse(merged_source)
        return merged_ast
    except SyntaxError:
        return None


def _log_conflict(
    module_path: str,
    mutation1: ast.AST,
    mutation2: ast.AST,
    base_snapshot: ast.AST,
    reason: str = "Merge conflict",
) -> None:
    """Log a conflict record to the internal log and to the JSON file."""
    record = {
        "module_path": module_path,
        "mutation1_hash": _compute_hash(mutation1),
        "mutation2_hash": _compute_hash(mutation2),
        "base_hash": _compute_hash(base_snapshot),
        "reason": reason,
    }
    _conflict_log.append(record)
    # Write to file
    try:
        with open(CONFLICT_LOG_PATH, "w") as f:
            json.dump(_conflict_log, f, indent=2)
    except IOError:
        pass


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def register_snapshot(module_path: str, ast_node: ast.AST) -> None:
    """Register a stable snapshot for a module (AST + hash)."""
    snapshot = {
        "ast": copy.deepcopy(ast_node),
        "hash": _compute_hash(ast_node),
    }
    _snapshot_registry[module_path] = snapshot


def detect_conflict(
    mutation1: ast.AST, mutation2: ast.AST
) -> bool:
    """
    Detect if two mutations modify overlapping code regions.
    Returns True if conflict detected.
    """
    ranges1 = _get_ast_ranges(mutation1)
    ranges2 = _get_ast_ranges(mutation2)
    return _ranges_overlap(ranges1, ranges2)


def resolve_conflict(
    mutation1: ast.AST,
    mutation2: ast.AST,
    base_snapshot: ast.AST,
    module_path: Optional[str] = None,
) -> Optional[ast.AST]:
    """
    Attempt to resolve conflict between two mutations using three-way merge.
    Returns merged AST on success, None on failure.
    If module_path is provided, updates snapshot on success or reverts on failure.
    """
    # Attempt three-way merge
    merged = _three_way_merge(base_snapshot, mutation1, mutation2)
    if merged is not None:
        # Merge succeeded
        if module_path is not None:
            register_snapshot(module_path, merged)
        return merged
    else:
        # Merge failed
        if module_path is not None:
            # Revert both mutations to base snapshot
            revert_to_snapshot(module_path)
            # Log conflict
            _log_conflict(
                module_path,
                mutation1,
                mutation2,
                base_snapshot,
                reason="Three-way merge failed",
            )
        return None


def revert_to_snapshot(module_path: str) -> Optional[ast.AST]:
    """
    Revert a module to its last stable snapshot.
    Returns the snapshot AST if found, None otherwise.
    """
    snapshot = _snapshot_registry.get(module_path)
    if snapshot is None:
        return None
    # Return a deep copy of the stored AST
    return copy.deepcopy(snapshot["ast"])


def get_conflict_log() -> List[Dict[str, Any]]:
    """Return the list of conflict records."""
    return list(_conflict_log)


def load_conflict_log() -> None:
    """Load conflict log from file if it exists."""
    global _conflict_log
    try:
        if CONFLICT_LOG_PATH.exists():
            with open(CONFLICT_LOG_PATH, "r") as f:
                _conflict_log = json.load(f)
    except (IOError, json.JSONDecodeError):
        _conflict_log = []