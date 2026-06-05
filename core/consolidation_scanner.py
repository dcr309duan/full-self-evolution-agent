from pathlib import Path
import ast
import re
import math
from collections import Counter
from typing import List, Tuple, Dict, Optional

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    import warnings
    warnings.warn("scikit-learn not installed; TF-IDF docstring similarity will use fallback method.")


# ----------------------------------------------------------------------
# 1. Function signature comparison using AST parsing
# ----------------------------------------------------------------------

def _get_function_signature(node: ast.FunctionDef) -> Tuple[str, List[str], Optional[str]]:
    """
    Extract normalized signature from an AST function definition node.
    Returns (name, parameter_names, return_annotation_str).
    """
    params = []
    for arg in node.args.args:
        params.append(arg.arg)
    # Handle *args and **kwargs
    if node.args.vararg:
        params.append(f"*{node.args.vararg.arg}")
    if node.args.kwarg:
        params.append(f"**{node.args.kwarg.arg}")
    # Return annotation as string if present
    return_ann = None
    if node.returns:
        try:
            return_ann = ast.dump(node.returns)
        except Exception:
            return_ann = None
    return (node.name, params, return_ann)


def signature_similarity(func1: ast.FunctionDef, func2: ast.FunctionDef) -> float:
    """
    Compare two function definitions by their parameter patterns.
    Returns a similarity score between 0.0 and 1.0.
    """
    name1, params1, ret1 = _get_function_signature(func1)
    name2, params2, ret2 = _get_function_signature(func2)

    # Parameter count similarity (exact match = 1, different = lower)
    len_sim = 1.0 - (abs(len(params1) - len(params2)) / max(len(params1), len(params2), 1))

    # Parameter name overlap (Jaccard similarity)
    set1 = set(params1)
    set2 = set(params2)
    if not set1 and not set2:
        name_sim = 1.0
    else:
        intersection = set1 & set2
        union = set1 | set2
        name_sim = len(intersection) / len(union) if union else 0.0

    # Return annotation match
    ret_sim = 1.0 if ret1 == ret2 else 0.0

    # Weighted combination
    return 0.3 * len_sim + 0.5 * name_sim + 0.2 * ret_sim


# ----------------------------------------------------------------------
# 2. Docstring similarity analysis using TF-IDF vectorization
# ----------------------------------------------------------------------

def _extract_docstring(node: ast.FunctionDef) -> str:
    """Extract and clean the docstring from a function definition."""
    docstring = ast.get_docstring(node) or ""
    # Normalize whitespace and lowercase
    docstring = re.sub(r'\s+', ' ', docstring).strip().lower()
    return docstring


def docstring_similarity(func1: ast.FunctionDef, func2: ast.FunctionDef) -> float:
    """
    Compute similarity between two function docstrings.
    Uses TF-IDF vectorization if sklearn is available, else a simple word overlap.
    Returns a score between 0.0 and 1.0.
    """
    doc1 = _extract_docstring(func1)
    doc2 = _extract_docstring(func2)

    if not doc1 or not doc2:
        return 0.0

    if SKLEARN_AVAILABLE:
        vectorizer = TfidfVectorizer(stop_words='english')
        try:
            tfidf_matrix = vectorizer.fit_transform([doc1, doc2])
            similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
            return float(similarity)
        except Exception:
            # Fallback if vectorization fails (e.g., empty vocabulary)
            pass

    # Fallback: simple word overlap (Jaccard)
    words1 = set(doc1.split())
    words2 = set(doc2.split())
    if not words1 or not words2:
        return 0.0
    intersection = words1 & words2
    union = words1 | words2
    return len(intersection) / len(union)


# ----------------------------------------------------------------------
# 3. Logic pattern matching by normalizing ASTs
# ----------------------------------------------------------------------

def _normalize_ast(node: ast.AST) -> str:
    """
    Normalize an AST by removing variable names and literal values,
    keeping only control flow structure and operator types.
    Returns a string representation suitable for comparison.
    """
    if isinstance(node, ast.Module):
        return "Module(" + ",".join(_normalize_ast(child) for child in node.body) + ")"
    elif isinstance(node, ast.FunctionDef):
        # Keep function name but not parameter names (replace with placeholder)
        body_normalized = ",".join(_normalize_ast(stmt) for stmt in node.body)
        return f"FuncDef({node.name}, params=[{','.join('_' for _ in node.args.args)}], body=[{body_normalized}])"
    elif isinstance(node, ast.ClassDef):
        body_normalized = ",".join(_normalize_ast(stmt) for stmt in node.body)
        return f"ClassDef({node.name}, body=[{body_normalized}])"
    elif isinstance(node, ast.If):
        test_normalized = _normalize_ast(node.test)
        body_normalized = ",".join(_normalize_ast(stmt) for stmt in node.body)
        orelse_normalized = ",".join(_normalize_ast(stmt) for stmt in node.orelse) if node.orelse else ""
        return f"If(test={test_normalized}, body=[{body_normalized}], orelse=[{orelse_normalized}])"
    elif isinstance(node, ast.While):
        test_normalized = _normalize_ast(node.test)
        body_normalized = ",".join(_normalize_ast(stmt) for stmt in node.body)
        return f"While(test={test_normalized}, body=[{body_normalized}])"
    elif isinstance(node, ast.For):
        target_normalized = _normalize_ast(node.target)
        iter_normalized = _normalize_ast(node.iter)
        body_normalized = ",".join(_normalize_ast(stmt) for stmt in node.body)
        return f"For(target={target_normalized}, iter={iter_normalized}, body=[{body_normalized}])"
    elif isinstance(node, ast.Try):
        body_normalized = ",".join(_normalize_ast(stmt) for stmt in node.body)
        handlers_normalized = ",".join(_normalize_ast(h) for h in node.handlers)
        finalbody_normalized = ",".join(_normalize_ast(stmt) for stmt in node.finalbody) if node.finalbody else ""
        return f"Try(body=[{body_normalized}], handlers=[{handlers_normalized}], finalbody=[{finalbody_normalized}])"
    elif isinstance(node, ast.ExceptHandler):
        body_normalized = ",".join(_normalize_ast(stmt) for stmt in node.body)
        return f"Except(type={node.type}, body=[{body_normalized}])"
    elif isinstance(node, ast.With):
        body_normalized = ",".join(_normalize_ast(stmt) for stmt in node.body)
        return f"With(body=[{body_normalized}])"
    elif isinstance(node, ast.Return):
        if node.value:
            return f"Return({_normalize_ast(node.value)})"
        return "Return()"
    elif isinstance(node, ast.Assign):
        targets_normalized = ",".join(_normalize_ast(t) for t in node.targets)
        value_normalized = _normalize_ast(node.value)
        return f"Assign(targets=[{targets_normalized}], value={value_normalized})"
    elif isinstance(node, ast.Expr):
        return f"Expr({_normalize_ast(node.value)})"
    elif isinstance(node, ast.Call):
        func_normalized = _normalize_ast(node.func)
        args_normalized = ",".join(_normalize_ast(a) for a in node.args)
        return f"Call(func={func_normalized}, args=[{args_normalized}])"
    elif isinstance(node, ast.Name):
        # Replace variable names with placeholder
        return "Name(id=_)"
    elif isinstance(node, ast.Attribute):
        # Keep attribute chain but replace base variable names
        return f"Attr(value={_normalize_ast(node.value)}, attr={node.attr})"
    elif isinstance(node, ast.Constant):
        # Replace constant values with placeholder
        return "Constant(value=_)"
    elif isinstance(node, ast.BinOp):
        op_name = type(node.op).__name__
        left = _normalize_ast(node.left)
        right = _normalize_ast(node.right)
        return f"BinOp({left}, {op_name}, {right})"
    elif isinstance(node, ast.UnaryOp):
        op_name = type(node.op).__name__
        operand = _normalize_ast(node.operand)
        return f"UnaryOp({op_name}, {operand})"
    elif isinstance(node, ast.Compare):
        left = _normalize_ast(node.left)
        ops = ",".join(type(op).__name__ for op in node.ops)
        comparators = ",".join(_normalize_ast(c) for c in node.comparators)
        return f"Compare({left}, ops=[{ops}], comparators=[{comparators}])"
    elif isinstance(node, ast.Subscript):
        value = _normalize_ast(node.value)
        slice_val = _normalize_ast(node.slice)
        return f"Subscript({value}, slice={slice_val})"
    elif isinstance(node, ast.Slice):
        lower = _normalize_ast(node.lower) if node.lower else "_"
        upper = _normalize_ast(node.upper) if node.upper else "_"
        step = _normalize_ast(node.step) if node.step else "_"
        return f"Slice({lower}, {upper}, {step})"
    elif isinstance(node, ast.List):
        elts = ",".join(_normalize_ast(e) for e in node.elts)
        return f"List([{elts}])"
    elif isinstance(node, ast.Dict):
        keys = ",".join(_normalize_ast(k) for k in node.keys)
        values = ",".join(_normalize_ast(v) for v in node.values)
        return f"Dict(keys=[{keys}], values=[{values}])"
    elif isinstance(node, ast.Tuple):
        elts = ",".join(_normalize_ast(e) for e in node.elts)
        return f"Tuple([{elts}])"
    elif isinstance(node, ast.Lambda):
        body = _normalize_ast(node.body)
        return f"Lambda(params=[{','.join('_' for _ in node.args.args)}], body={body})"
    elif isinstance(node, ast.comprehension):
        target = _normalize_ast(node.target)
        iter_val = _normalize_ast(node.iter)
        ifs = ",".join(_normalize_ast(i) for i in node.ifs)
        return f"Comprehension(target={target}, iter={iter_val}, ifs=[{ifs}])"
    elif isinstance(node, ast.ListComp):
        elt = _normalize_ast(node.elt)
        generators = ",".join(_normalize_ast(g) for g in node.generators)
        return f"ListComp(elt={elt}, generators=[{generators}])"
    elif isinstance(node, ast.DictComp):
        key = _normalize_ast(node.key)
        value = _normalize_ast(node.value)
        generators = ",".join(_normalize_ast(g) for g in node.generators)
        return f"DictComp(key={key}, value={value}, generators=[{generators}])"
    elif isinstance(node, ast.SetComp):
        elt = _normalize_ast(node.elt)
        generators = ",".join(_normalize_ast(g) for g in node.generators)
        return f"SetComp(elt={elt}, generators=[{generators}])"
    elif isinstance(node, ast.GeneratorExp):
        elt = _normalize_ast(node.elt)
        generators = ",".join(_normalize_ast(g) for g in node.generators)
        return f"GeneratorExp(elt={elt}, generators=[{generators}])"
    elif isinstance(node, ast.Await):
        value = _normalize_ast(node.value)
        return f"Await({value})"
    elif isinstance(node, ast.Yield):
        value = _normalize_ast(node.value) if node.value else "_"
        return f"Yield({value})"
    elif isinstance(node, ast.YieldFrom):
        value = _normalize_ast(node.value)
        return f"YieldFrom({value})"
    elif isinstance(node, ast.Raise):
        exc = _normalize_ast(node.exc) if node.exc else "_"
        cause = _normalize_ast(node.cause) if node.cause else "_"
        return f"Raise(exc={exc}, cause={cause})"
    elif isinstance(node, ast.Assert):
        test = _normalize_ast(node.test)
        msg = _normalize_ast(node.msg) if node.msg else "_"
        return f"Assert(test={test}, msg={msg})"
    elif isinstance(node, ast.Delete):
        targets = ",".join(_normalize_ast(t) for t in node.targets)
        return f"Delete(targets=[{targets}])"
    elif isinstance(node, ast.Pass):
        return "Pass"
    elif isinstance(node, ast.Break):
        return "Break"
    elif isinstance(node, ast.Continue):
        return "Continue"
    elif isinstance(node, ast.Import):
        names = ",".join(f"{alias.name}" for alias in node.names)
        return f"Import(names=[{names}])"
    elif isinstance(node, ast.ImportFrom):
        module = node.module or ""
        names = ",".join(f"{alias.name}" for alias in node.names)
        return f"ImportFrom(module={module}, names=[{names}])"
    elif isinstance(node, ast.Global):
        return f"Global(names={node.names})"
    elif isinstance(node, ast.Nonlocal):
        return f"Nonlocal(names={node.names})"
    elif isinstance(node, ast.AnnAssign):
        target = _normalize_ast(node.target)
        value = _normalize_ast(node.value) if node.value else "_"
        return f"AnnAssign(target={target}, value={value})"
    elif isinstance(node, ast.AugAssign):
        target = _normalize_ast(node.target)
        op_name = type(node.op).__name__
        value = _normalize_ast(node.value)
        return f"AugAssign(target={target}, op={op_name}, value={value})"
    elif isinstance(node, ast.IfExp):
        test = _normalize_ast(node.test)
        body = _normalize_ast(node.body)
        orelse = _normalize_ast(node.orelse)
        return f"IfExp(test={test}, body={body}, orelse={orelse})"
    elif isinstance(node, ast.Starred):
        value = _normalize_ast(node.value)
        return f"Starred({value})"
    elif isinstance(node, ast.FormattedValue):
        value = _normalize_ast(node.value)
        return f"FormattedValue({value})"
    elif isinstance(node, ast.JoinedStr):
        values = ",".join(_normalize_ast(v) for v in node.values)
        return f"JoinedStr([{values}])"
    elif isinstance(node, ast.Set):
        elts = ",".join(_normalize_ast(e) for e in node.elts)
        return f"Set([{elts}])"
    elif isinstance(node, ast.NamedExpr):
        target = _normalize_ast(node.target)
        value = _normalize_ast(node.value)
        return f"NamedExpr(target={target}, value={value})"
    else:
        # Fallback for unrecognized nodes: use class name
        return type(node).__name__


def logic_similarity(func1: ast.FunctionDef, func2: ast.FunctionDef) -> float:
    """
    Compare the control flow structure of two functions by normalizing their ASTs.
    Returns a similarity score between 0.0 and 1.0 based on string edit distance.
    """
    norm1 = _normalize_ast(func1)
    norm2 = _normalize_ast(func2)

    # Use simple Levenshtein distance ratio
    len1, len2 = len(norm1), len(norm2)
    if len1 == 0 and len2 == 0:
        return 1.0
    if len1 == 0 or len2 == 0:
        return 0.0

    # Compute Levenshtein distance (simplified for strings)
    # Using dynamic programming with O(n*m) time
    dp = [[0] * (len2 + 1) for _ in range(len1 + 1)]
    for i in range(len1 + 1):
        dp[i][0] = i
    for j in range(len2 + 1):
        dp[0][j] = j
    for i in range(1, len1 + 1):
        for j in range(1, len2 + 1):
            cost = 0 if norm1[i-1] == norm2[j-1] else 1
            dp[i][j] = min(
                dp[i-1][j] + 1,      # deletion
                dp[i][j-1] + 1,      # insertion
                dp[i-1][j-1] + cost  # substitution
            )
    distance = dp[len1][len2]
    max_len = max(len1, len2)
    similarity = 1.0 - (distance / max_len)
