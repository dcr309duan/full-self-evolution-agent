"""Failure feature extraction utility for mutation proposals.

Extracts quantitative features from mutation proposals to build feature vectors
for the classifier. Features include complexity metrics, import counts, and
file impact analysis.
"""

import ast
import re
from typing import Dict, Any, List, Optional


def extract_features(mutation_proposal: Dict[str, Any]) -> Dict[str, Any]:
    """Extract feature vector from a mutation proposal.
    
    Args:
        mutation_proposal: Dictionary containing mutation details with keys:
            - 'code': The mutated code (string)
            - 'original_code': The original code (string)
            - 'file_path': Path to the file being mutated
            - 'file_paths': List of all affected file paths (optional)
            - 'imports': List of new imports added (optional)
            - 'diff': Unified diff string (optional)
    
    Returns:
        Dictionary with extracted features:
            - complexity: Lines of code changed + control flow statements
            - import_count: Number of new imports added
            - file_count: Number of files affected
            - feature_vector: List of [complexity, import_count, file_count]
    """
    code = mutation_proposal.get('code', '')
    original_code = mutation_proposal.get('original_code', '')
    file_paths = mutation_proposal.get('file_paths', [])
    imports = mutation_proposal.get('imports', [])
    diff = mutation_proposal.get('diff', '')
    
    # Calculate complexity
    complexity = _calculate_complexity(code, original_code, diff)
    
    # Count new imports
    import_count = _count_new_imports(code, original_code, imports)
    
    # Count affected files
    file_count = _count_affected_files(file_paths, mutation_proposal.get('file_path', ''))
    
    return {
        'complexity': complexity,
        'import_count': import_count,
        'file_count': file_count,
        'feature_vector': [complexity, import_count, file_count]
    }


def _calculate_complexity(code: str, original_code: str, diff: str = '') -> int:
    """Calculate complexity score based on code changes and control flow.
    
    Complexity = lines_changed + control_flow_statements
    
    Args:
        code: The mutated code
        original_code: The original code
        diff: Optional unified diff string
    
    Returns:
        Integer complexity score
    """
    lines_changed = 0
    control_flow_count = 0
    
    # Count lines changed from diff if available
    if diff:
        lines_changed = _count_lines_changed_from_diff(diff)
    else:
        # Fallback: compare line counts
        code_lines = code.split('\n')
        original_lines = original_code.split('\n')
        lines_changed = abs(len(code_lines) - len(original_lines))
        
        # Also count differing lines
        min_len = min(len(code_lines), len(original_lines))
        for i in range(min_len):
            if code_lines[i] != original_lines[i]:
                lines_changed += 1
    
    # Count control flow statements in the mutated code
    try:
        tree = ast.parse(code)
        control_flow_count = _count_control_flow_nodes(tree)
    except SyntaxError:
        # Fallback: use regex-based counting
        control_flow_count = _count_control_flow_regex(code)
    
    return lines_changed + control_flow_count


def _count_lines_changed_from_diff(diff: str) -> int:
    """Count lines added/modified from a unified diff string.
    
    Args:
        diff: Unified diff string
    
    Returns:
        Number of lines changed
    """
    count = 0
    for line in diff.split('\n'):
        # Count lines that start with + or - (excluding diff headers)
        if line.startswith('+') or line.startswith('-'):
            if not line.startswith('+++') and not line.startswith('---'):
                count += 1
    return count


def _count_control_flow_nodes(tree: ast.AST) -> int:
    """Count control flow AST nodes.
    
    Args:
        tree: AST tree to analyze
    
    Returns:
        Count of control flow statements
    """
    count = 0
    for node in ast.walk(tree):
        if isinstance(node, (ast.If, ast.For, ast.While, ast.Try,
                             ast.With, ast.AsyncFor, ast.AsyncWith)):
            count += 1
        elif isinstance(node, ast.FunctionDef):
            # Count function definitions as complexity
            count += 1
    return count


def _count_control_flow_regex(code: str) -> int:
    """Fallback regex-based control flow counting.
    
    Args:
        code: Source code string
    
    Returns:
        Approximate count of control flow statements
    """
    patterns = [
        r'\bif\b', r'\belif\b', r'\belse\b', r'\bfor\b', r'\bwhile\b',
        r'\btry\b', r'\bexcept\b', r'\bfinally\b', r'\bwith\b',
        r'\bdef\b', r'\bclass\b', r'\basync\b', r'\bawait\b'
    ]
    count = 0
    for pattern in patterns:
        count += len(re.findall(pattern, code))
    return count


def _count_new_imports(code: str, original_code: str, 
                       imports: Optional[List[str]] = None) -> int:
    """Count new imports added by the mutation.
    
    Args:
        code: Mutated code
        original_code: Original code
        imports: Optional pre-extracted list of new imports
    
    Returns:
        Number of new imports
    """
    if imports is not None:
        return len(imports)
    
    # Extract imports from both versions
    code_imports = _extract_imports(code)
    original_imports = _extract_imports(original_code)
    
    # Count imports in mutated code not in original
    new_imports = code_imports - original_imports
    return len(new_imports)


def _extract_imports(code: str) -> set:
    """Extract set of import statements from code.
    
    Args:
        code: Source code string
    
    Returns:
        Set of import strings (e.g., {'os', 'sys.path'})
    """
    imports = set()
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ''
                for alias in node.names:
                    imports.add(f"{module}.{alias.name}")
    except SyntaxError:
        # Fallback regex extraction
        import_pattern = r'^import\s+(\S+)'
        from_pattern = r'^from\s+(\S+)\s+import\s+(\S+)'
        for line in code.split('\n'):
            match = re.match(import_pattern, line.strip())
            if match:
                imports.add(match.group(1))
            match = re.match(from_pattern, line.strip())
            if match:
                imports.add(f"{match.group(1)}.{match.group(2)}")
    return imports


def _count_affected_files(file_paths: List[str], 
                          primary_file: str = '') -> int:
    """Count number of files affected by the mutation.
    
    Args:
        file_paths: List of all affected file paths
        primary_file: Primary file being mutated (optional)
    
    Returns:
        Number of unique files affected
    """
    files = set(file_paths) if file_paths else set()
    if primary_file:
        files.add(primary_file)
    return max(len(files), 1)  # At least 1 file is always affected