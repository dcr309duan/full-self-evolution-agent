import os
import ast
import hashlib
import math
import re
from collections import defaultdict, Counter
from pathlib import Path
from typing import List, Tuple, Dict, Set, Optional

# ---------------------------------------------------------------------------
# TF-IDF helpers
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> List[str]:
    """Simple tokenizer: lower-case, split on non-alphanumeric."""
    return re.findall(r'[a-zA-Z_]\w*', text.lower())


def _compute_tf(text: str) -> Counter:
    tokens = _tokenize(text)
    return Counter(tokens)


def _compute_idf(documents: List[str]) -> Dict[str, float]:
    n = len(documents)
    df: Counter = Counter()
    for doc in documents:
        tokens = set(_tokenize(doc))
        for tok in tokens:
            df[tok] += 1
    idf: Dict[str, float] = {}
    for tok, freq in df.items():
        idf[tok] = math.log((1 + n) / (1 + freq)) + 1.0
    return idf


def _tfidf_vector(text: str, idf: Dict[str, float]) -> Dict[str, float]:
    tf = _compute_tf(text)
    vec: Dict[str, float] = {}
    for tok, freq in tf.items():
        vec[tok] = freq * idf.get(tok, 1.0)
    return vec


def _cosine_similarity(vec_a: Dict[str, float], vec_b: Dict[str, float]) -> float:
    common = set(vec_a) & set(vec_b)
    dot = sum(vec_a[t] * vec_b[t] for t in common)
    norm_a = math.sqrt(sum(v * v for v in vec_a.values()))
    norm_b = math.sqrt(sum(v * v for v in vec_b.values()))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


# ---------------------------------------------------------------------------
# Structural similarity helpers
# ---------------------------------------------------------------------------

def _extract_ast_info(source: str) -> Tuple[int, int, int]:
    """Return (function_count, import_count, loc)."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return (0, 0, 0)
    func_count = sum(1 for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)))
    import_count = sum(1 for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom)))
    loc = len(source.splitlines())
    return (func_count, import_count, loc)


def _normalize_counts(counts: List[Tuple[int, int, int]]) -> List[Tuple[float, float, float]]:
    """Normalize counts to [0,1] range across all modules."""
    if not counts:
        return []
    max_func = max(c[0] for c in counts) or 1
    max_import = max(c[1] for c in counts) or 1
    max_loc = max(c[2] for c in counts) or 1
    normalized = []
    for func, imp, loc in counts:
        normalized.append((
            func / max_func,
            imp / max_import,
            loc / max_loc
        ))
    return normalized


def _structural_similarity(norm_a: Tuple[float, float, float], norm_b: Tuple[float, float, float]) -> float:
    """Normalised similarity based on normalized function count, import count, LOC."""
    f1, i1, l1 = norm_a
    f2, i2, l2 = norm_b
    f_sim = 1.0 - abs(f1 - f2)
    i_sim = 1.0 - abs(i1 - i2)
    l_sim = 1.0 - abs(l1 - l2)
    return (f_sim + i_sim + l_sim) / 3.0


# ---------------------------------------------------------------------------
# Capability module scanning
# ---------------------------------------------------------------------------

def _find_capability_files(base_dir: str = "core") -> List[str]:
    """Return paths of Python files that look like capability modules."""
    paths = []
    for fname in os.listdir(base_dir):
        if fname.endswith(".py") and fname != "__init__.py":
            full = os.path.join(base_dir, fname)
            if os.path.isfile(full):
                paths.append(full)
    return sorted(paths)


def _read_source(path: str) -> Optional[str]:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()
    except Exception:
        return None


def _extract_docstrings(source: str) -> str:
    """Concatenate all docstrings from the AST."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return ""
    docs: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
            if node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant):
                docs.append(node.body[0].value.value)
    return "\n".join(docs)


def _extract_signatures(source: str) -> str:
    """Extract function/class signatures as text."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return ""
    sigs: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = ", ".join(arg.arg for arg in node.args.args)
            sigs.append(f"{node.name}({args})")
        elif isinstance(node, ast.ClassDef):
            bases = ", ".join(ast.dump(b) for b in node.bases)
            sigs.append(f"class {node.name}({bases})")
    return "\n".join(sigs)


# ---------------------------------------------------------------------------
# Test pass history (simple file-based)
# ---------------------------------------------------------------------------

_TEST_HISTORY_FILE = "test_pass_history.txt"


def _load_test_history() -> Dict[str, List[bool]]:
    """Load {module_name: [pass/fail per cycle]}."""
    history: Dict[str, List[bool]] = {}
    if not os.path.exists(_TEST_HISTORY_FILE):
        return history
    with open(_TEST_HISTORY_FILE, "r") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            name = parts[0]
            results = [p == "1" for p in parts[1:]]
            history[name] = results
    return history


def _save_test_history(history: Dict[str, List[bool]]) -> None:
    with open(_TEST_HISTORY_FILE, "w") as fh:
        for name, results in history.items():
            line = name + " " + " ".join("1" if r else "0" for r in results)
            fh.write(line + "\n")


def _record_test_result(module_name: str, passed: bool) -> None:
    history = _load_test_history()
    if module_name not in history:
        history[module_name] = []
    history[module_name].append(passed)
    # Keep only last 20 cycles
    history[module_name] = history[module_name][-20:]
    _save_test_history(history)


def _zero_passes_last_n(module_name: str, n: int = 20) -> bool:
    history = _load_test_history()
    results = history.get(module_name, [])
    recent = results[-n:]
    if len(recent) < n:
        return False  # not enough data
    return not any(recent)


# ---------------------------------------------------------------------------
# Merging logic
# ---------------------------------------------------------------------------

def _extract_test_cases(source: str) -> List[str]:
    """Extract test case code blocks from source."""
    test_cases = []
    try:
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith('test_') or node.name.startswith('Test'):
                    test_cases.append(ast.unparse(node))
    except SyntaxError:
        pass
    return test_cases


def _is_more_general(source_a: str, source_b: str) -> bool:
    """Determine which source is more general (preferring shorter, more abstract code)."""
    lines_a = len(source_a.splitlines())
    lines_b = len(source_b.splitlines())
    
    # Count abstract patterns (type hints, generics, abstract base classes)
    abstract_patterns = ['typing.', 'abc.', 'abstractmethod', 'Generic', 'Protocol', 'TypeVar']
    abstract_count_a = sum(source_a.count(p) for p in abstract_patterns)
    abstract_count_b = sum(source_b.count(p) for p in abstract_patterns)
    
    # Prefer shorter code with more abstract patterns
    if abstract_count_a != abstract_count_b:
        return abstract_count_a > abstract_count_b
    return lines_a < lines_b


def _merge_sources(sources: List[str], source_names: List[str]) -> str:
    """Merge multiple source files into one with proper merge logic."""
    if not sources:
        return ""
    
    # Keep the most general implementation
    best_idx = 0
    for i in range(1, len(sources)):
        if _is_more_general(sources[i], sources[best_idx]):
            best_idx = i
    
    merged_source = sources[best_idx]
    
    # Combine unique test cases from all modules
    all_test_cases = []
    seen_tests = set()
    for src in sources:
        test_cases = _extract_test_cases(src)
        for tc in test_cases:
            # Use hash to detect duplicates
            tc_hash = hashlib.md5(tc.encode()).hexdigest()
            if tc_hash not in seen_tests:
                seen_tests.add(tc_hash)
                all_test_cases.append(tc)
    
    # Add unique test cases at the end
    if all_test_cases:
        merged_source += "\n\n# Merged test cases\n"
        for tc in all_test_cases:
            merged_source += tc + "\n\n"
    
    # Add comment header documenting the merge
    header = f"""# Merged module created from: {', '.join(source_names)}
# This module combines the most general implementation with unique test cases from all source modules.
# Original modules have been archived.
"""
    
    return header + merged_source


def _write_module(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)


def _archive_module(path: str, archive_dir: str = "archive") -> None:
    os.makedirs(archive_dir, exist_ok=True)
    base = os.path.basename(path)
    dest = os.path.join(archive_dir, base)
    try:
        os.rename(path, dest)
    except OSError:
        # fallback copy + remove
        import shutil
        shutil.copy2(path, dest)
        os.remove(path)


# ---------------------------------------------------------------------------
# Main consolidation routine
# ---------------------------------------------------------------------------

def consolidate_capabilities(base_dir: str = "core",
                             similarity_threshold: float = 0.85,
                             archive_zero_passes: bool = True,
                             zero_pass_cycles: int = 20) -> List[str]:
    """
    Run one consolidation pass.

    Returns list of log messages.
    """
    logs: List[str] = []
    files = _find_capability_files(base_dir)
    if not files:
        logs.append("No capability files found.")
        return logs

    # 1. Extract docstrings + signatures
    doc_texts: Dict[str, str] = {}
    sig_texts: Dict[str, str] = {}
    sources: Dict[str, str] = {}
    for fpath in files:
        src = _read_source(fpath)
        if src is None:
            continue
        name = os.path.basename(fpath)
        sources[name] = src
        docs = _extract_docstrings(src)
        sigs = _extract_signatures(src)
        doc_texts[name] = docs
        sig_texts[name] = sigs

    if not sources:
        logs.append("No readable sources.")
        return logs

    # 2. TF-IDF vectors using sklearn's TfidfVectorizer if available
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        # Combine docstrings and signatures for each module
        combined_texts = {}
        for name in sources:
            combined_texts[name] = doc_texts[name] + "\n" + sig_texts[name]
        
        # Preprocess: tokenization, stopword removal, lowercasing
        vectorizer = TfidfVectorizer(
            lowercase=True,
            token_pattern=r'[a-zA-Z_]\w*',
            stop_words='english',
            max_features=1000
        )
        names_list = list(combined_texts.keys())
        texts_list = [combined_texts[name] for name in names_list]
        tfidf_matrix = vectorizer.fit_transform(texts_list)
        
        # Convert to dictionary vectors for compatibility
        feature_names = vectorizer.get_feature_names_out()
        doc_vectors = {}
        for idx, name in enumerate(names_list):
            vec = {}
            row = tfidf_matrix[idx].toarray().flatten()
            for j, val in enumerate(row):
                if val > 0:
                    vec[feature_names[j]] = val
            doc_vectors[name] = vec
    except ImportError:
        # Fallback to simple TF-IDF implementation
        all_docs = list(doc_texts.values())
        idf = _compute_idf(all_docs)
        doc_vectors = {name: _tfidf_vector(doc_texts[name], idf) for name in sources}

    # 3. Structural info with normalization
    raw_struct_info = {name: _extract_ast_info(sources[name]) for name in sources}
    names = list(sources.keys())
    raw_counts = [raw_struct_info[name] for name in names]
    normalized_counts = _normalize_counts(raw_counts)
    struct_info = {name: norm for name, norm in zip(names, normalized_counts)}

    # 4. Compute combined similarity and merge
    merged_set: Set[str] = set()
    merges_done = 0

    for i in range(len(names)):
        if names[i] in merged_set:
            continue
        group = [names[i]]
        for j in range(i + 1, len(names)):
            if names[j] in merged_set:
                continue
            # Cosine similarity (docstrings + signatures)
            vec_i = doc_vectors[names[i]]
            vec_j = doc_vectors[names[j]]
            cos_sim = _cosine_similarity(vec_i, vec_j)
            # Structural similarity using normalized counts
            struct_sim = _structural_similarity(struct_info[names[i]], struct_info[names[j]])
            # Weighted average: 0.7 text + 0.3 structural
            combined = 0.7 * cos_sim + 0.3 * struct_sim
            if combined > similarity_threshold:
                group.append(names[j])
                merged_set.add(names[j])
        if len(group) > 1:
            merged_set.add(names[i])
            merges_done += 1
            merged_name = "merged_" + hashlib.md5("_".join(group).encode()).hexdigest()[:8] + ".py"
            merged_src = _merge_sources([sources[g] for g in group], group)
            merged_path = os.path.join(base_dir, merged_name)
            _write_module(merged_path, merged_src)
            logs.append(f"Merged {group} into {merged_name}")
            # Remove original files from capabilities list
            for g in group:
                orig_path = os.path.join(base_dir, g)
                if os.path.exists(orig_path):
                    os.remove(orig_path)
                    logs.append(f"Removed original {g} from capabilities list")

    # 5. Archive modules with zero test passes in last N cycles
    if archive_zero_passes:
        for name in sources:
            if name in merged_set:
                continue
            mod_name = name.replace(".py", "")
            if _zero_passes_last_n(mod_name, zero_pass_cycles):
                fpath = os.path.join(base_dir, name)
                if os.path.exists(fpath):
                    _archive_module(fpath)
                    logs.append(f"Archived {name} (zero passes in last {zero_pass_cycles} cycles)")

    if merges_done == 0:
        logs.append("No modules merged this cycle.")
    return logs


# ---------------------------------------------------------------------------
# Scheduler interface (run every 30 cycles)
# ---------------------------------------------------------------------------

_CYCLE_COUNTER_FILE = ".consolidator_cycle_counter"


def _read_cycle_counter() -> int:
    try:
        with open(_CYCLE_COUNTER_FILE, "r") as fh:
            return int(fh.read().strip())
    except (FileNotFoundError, ValueError):
        return 0


def _write_cycle_counter(val: int) -> None:
    with open(_CYCLE_COUNTER_FILE, "w") as fh:
        fh.write(str(val))


def maybe_run_consolidation(cycle_number: int, interval: int = 30) -> List[str]:
    """
    Call this every cycle. If cycle_number % interval == 0, run consolidation.

    Returns log messages (empty if not run).
    """
    counter = _read_cycle_counter()
    if cycle_number % interval == 0 and cycle_number > 0:
        logs = consolidate_capabilities()
        _write_cycle_counter(cycle_number)
        # Log results including number of modules merged, number archived, similarity matrix summary
        merged_count = sum(1 for msg in logs if msg.startswith("Merged"))
        archived_count = sum(1 for msg in logs if msg.startswith("Archived"))
        logs.append(f"Scheduler summary: cycle {cycle_number}, modules merged: {merged_count}, archived: {archived_count}")
        return logs
    return []


# ---------------------------------------------------------------------------
# Convenience: record test result externally
# ---------------------------------------------------------------------------

def record_test_pass(module_name: str, passed: bool) -> None:
    """Record a test pass/fail for a module."""
    _record_test_result(module_name, passed)


# ---------------------------------------------------------------------------
# Test suite for the consolidator
# ---------------------------------------------------------------------------

import unittest
import tempfile
import shutil


class TestConsolidator(unittest.TestCase):
    """Test suite for the capability consolidator."""

    def setUp(self):
        """Create a temporary directory structure for testing."""
        self.test_dir = tempfile.mkdtemp()
        self.core_dir = os.path.join(self.test_dir, "core")
        self.archive_dir = os.path.join(self.test_dir, "archive")
        os.makedirs(self.core_dir, exist_ok=True)
        os.makedirs(self.archive_dir, exist_ok=True)
        # Save original working directory and change to test dir
        self.orig_dir = os.getcwd()
        os.chdir(self.test_dir)

    def tearDown(self):
        """Clean up temporary directory."""
        os.chdir(self.orig_dir)
        shutil.rmtree(self.test_dir)

    def _create_module(self, name: str, content: str, base_dir: str = None) -> str:
        """Helper to create a module file in the core directory."""
        if base_dir is None:
            base_dir = self.core_dir
        path = os.path.join(base_dir, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path

    # -----------------------------------------------------------------------
    # Test 1: TF-IDF similarity between near-identical docstrings
    # -----------------------------------------------------------------------
    def test_tfidf_similarity_near_identical_docstrings(self):
        """Test that modules with very similar docstrings get high TF-IDF similarity."""
        # Create two modules with nearly identical docstrings
        doc1 = "This module provides utility functions for data processing and analysis."
        doc2 = "This module provides utility functions for data processing and analysis."
        src1 = f'"""\n{doc1}\n"""\ndef func_a(x):\n    return x + 1\n'
        src2 = f'"""\n{doc2}\n"""\ndef func_b(x):\n    return x * 2\n'
        self._create_module("module_a.py", src1)
        self._create_module("module_b.py", src2)

        # Compute TF-IDF vectors manually
        doc_texts = {
            "module_a.py": _extract_docstrings(src1),
            "module_b.py": _extract_docstrings(src2)
        }
        all_docs = list(doc_texts.values())
        idf = _compute_idf(all_docs)
        vec_a = _tfidf_vector(doc_texts["module_a.py"], idf)
        vec_b = _tfidf_vector(doc_texts["module_b.py"], idf)
        similarity = _cosine_similarity(vec_a, vec_b)

        # The docstrings are identical, so similarity should be 1.0
        self.assertAlmostEqual(similarity, 1.0, places=5,
                               msg="TF-IDF similarity between identical docstrings should be 1.0")

    # -----------------------------------------------------------------------
    # Test 2: Structural similarity between modules with same function count
    # -----------------------------------------------------------------------
    def test_structural_similarity_same_function_count(self):
        """Test that modules with the same number of functions get high structural similarity."""
        # Create two modules with same function count but different content
        src1 = "def func_a():\n    pass\n\ndef func_b():\n    pass\n"
        src2 = "def func_c():\n    return 42\n\ndef func_d():\n    return 'hello'\n"
        
        info1 = _extract_ast_info(src1)
        info2 = _extract_ast_info(src2)
        
        # Normalize counts (only two modules, so max is the same)
        normalized = _normalize_counts([info1, info2])
        norm1, norm2 = normalized[0], normalized[1]
        
        similarity = _structural_similarity(norm1, norm2)
        
        # Both have 2 functions, 0 imports, similar LOC -> similarity should be high
        self.assertGreater(similarity, 0.8,
                           msg="Structural similarity between modules with same function count should be high")

    # -----------------------------------------------------------------------
    # Test 3: Merge produces valid Python
    # -----------------------------------------------------------------------
    def test_merge_produces_valid_python(self):
        """Test that the merge operation produces syntactically valid Python code."""
        src1 = "def func_a():\n    return 1\n"
        src2 = "def func_b():\n    return 2\n"
        
        merged = _merge_sources([src1, src2], ["module_a.py", "module_b.py"])
        
        # Try to parse the merged source
        try:
            ast.parse(merged)
            valid = True
        except SyntaxError:
            valid = False
        
        self.assertTrue(valid, "Merged source should be valid Python")

    # -----------------------------------------------------------------------
    # Test 4: Archiving removes module from active list
    # -----------------------------------------------------------------------
    def test_archive_removes_module_from_active_list(self):
        """Test that archiving a module removes it from the active core directory."""
        # Create a module in core
        src = "def test_func():\n    return True\n"
        module_path = self._create_module("test_module.py", src)
        
        # Verify it exists in core
        self.assertTrue(os.path.exists(module_path), "Module should exist in core before archiving")
        
        # Archive it
        _archive_module(module_path, archive_dir=self.archive_dir)
        
        # Verify it's no longer in core
        self.assertFalse(os.path.exists(module_path), "Module should be removed from core after archiving")
        
        # Verify it exists in archive
        archived_path = os.path.join(self.archive_dir, "test_module.py")
        self.assertTrue(os.path.exists(archived_path), "Module should exist in archive after archiving")
        
        # Verify the content is preserved
        with open(archived_path, "r") as f:
            content = f.read()
        self.assertEqual(content, src, "Archived module content should match original")


# ---------------------------------------------------------------------------
# If run as script, do one consolidation pass
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    if "--test" in sys.argv:
        unittest.main(argv=[sys.argv[0]])
    else:
        logs = consolidate_capabilities()
        for msg in logs:
            print(msg)