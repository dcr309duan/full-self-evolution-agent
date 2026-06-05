from pathlib import Path
import ast
import shutil
import tempfile
import subprocess
import sys
import os
import importlib.util
from typing import Dict, List, Optional, Set, Tuple, Any

class DependencySubgraphCloner:
    """Clones a target module and its dependencies into a temporary directory using AST analysis."""

    def __init__(self, target_module_path: Path):
        self.target_module_path = target_module_path.resolve()
        self.dependency_map: Dict[Path, Set[Path]] = {}  # module -> set of dependency paths
        self.all_dependencies: Set[Path] = set()
        self._analyze()

    def _resolve_import(self, module_name: str, base_path: Path) -> Optional[Path]:
        """Resolve an import statement to an actual file path."""
        # Try relative import first
        parts = module_name.split('.')
        for i in range(len(parts), 0, -1):
            relative_path = base_path / '/'.join(parts[:i]) / '__init__.py'
            if relative_path.exists():
                return relative_path
            relative_path = base_path / '/'.join(parts[:i]) + '.py'
            if relative_path.exists():
                return relative_path

        # Try absolute import from sys.path
        for path in sys.path:
            abs_path = Path(path)
            for i in range(len(parts), 0, -1):
                full_path = abs_path / '/'.join(parts[:i]) / '__init__.py'
                if full_path.exists():
                    return full_path
                full_path = abs_path / '/'.join(parts[:i]) + '.py'
                if full_path.exists():
                    return full_path
        return None

    def _extract_imports(self, file_path: Path) -> Set[str]:
        """Extract all import names from a Python file using AST."""
        imports = set()
        try:
            with open(file_path, 'r') as f:
                tree = ast.parse(f.read(), filename=str(file_path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.add(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.add(node.module)
        except (SyntaxError, IOError):
            pass
        return imports

    def _analyze(self, current_path: Optional[Path] = None, visited: Optional[Set[Path]] = None):
        """Recursively analyze dependencies starting from target module."""
        if current_path is None:
            current_path = self.target_module_path
        if visited is None:
            visited = set()

        if current_path in visited:
            return
        visited.add(current_path)

        imports = self._extract_imports(current_path)
        resolved_deps = set()
        for import_name in imports:
            resolved = self._resolve_import(import_name, current_path.parent)
            if resolved and resolved != current_path:
                resolved_deps.add(resolved)
                self._analyze(resolved, visited)

        self.dependency_map[current_path] = resolved_deps
        self.all_dependencies.update(resolved_deps)
        self.all_dependencies.add(current_path)

    def get_clone_sources(self) -> Dict[Path, str]:
        """Return mapping of relative paths to source code for all dependencies."""
        clone_sources = {}
        base_dir = self.target_module_path.parent
        for dep_path in self.all_dependencies:
            try:
                relative = dep_path.relative_to(base_dir)
            except ValueError:
                # If not under base dir, use absolute path as key
                relative = dep_path
            with open(dep_path, 'r') as f:
                clone_sources[relative] = f.read()
        return clone_sources

    def get_dependency_graph(self) -> Dict[str, List[str]]:
        """Return a human-readable dependency graph."""
        graph = {}
        for module, deps in self.dependency_map.items():
            module_name = module.name
            graph[module_name] = [d.name for d in deps]
        return graph


class SandboxEnvironment:
    """Creates a temporary directory with cloned dependency files for safe mutation testing."""

    def __init__(self, clone_sources: Dict[Path, str], base_dir: Optional[Path] = None):
        self.clone_sources = clone_sources
        self.base_dir = base_dir
        self.temp_dir: Optional[Path] = None
        self._setup()

    def _setup(self):
        """Create temp directory and write all cloned files."""
        self.temp_dir = Path(tempfile.mkdtemp(prefix="sandbox_"))
        for relative_path, source_code in self.clone_sources.items():
            target_path = self.temp_dir / relative_path
            target_path.parent.mkdir(parents=True, exist_ok=True)
            with open(target_path, 'w') as f:
                f.write(source_code)

    def apply_mutation(self, file_path: Path, mutated_source: str):
        """Apply a mutated source code to a file in the sandbox."""
        full_path = self.temp_dir / file_path
        if not full_path.exists():
            raise FileNotFoundError(f"File {file_path} not found in sandbox")
        with open(full_path, 'w') as f:
            f.write(mutated_source)

    def run_test(self, test_command: List[str]) -> subprocess.CompletedProcess:
        """Run a test command within the sandbox environment."""
        env = os.environ.copy()
        env['PYTHONPATH'] = f"{self.temp_dir}:{env.get('PYTHONPATH', '')}"
        result = subprocess.run(
            test_command,
            cwd=self.temp_dir,
            capture_output=True,
            text=True,
            env=env,
            timeout=30
        )
        return result

    def cleanup(self):
        """Remove the temporary sandbox directory."""
        if self.temp_dir and self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
            self.temp_dir = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()


class MutationSimulator:
    """Applies mutations to cloned dependency subgraphs and runs tests to evaluate impact."""

    def __init__(self, target_module_path: Path):
        self.target_module_path = target_module_path.resolve()
        self.cloner = DependencySubgraphCloner(self.target_module_path)

    def simulate(self, mutation: Dict[str, Any], test_command: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Apply a proposed mutation to the cloned subgraph, run tests, and return structured results.

        Args:
            mutation: Dictionary with 'file' (relative Path), 'source' (str), and optional 'description' (str)
            test_command: List of command arguments to run tests (default: ['python', '-m', 'pytest'])

        Returns:
            Dictionary with keys:
                - 'passed': bool
                - 'stdout': str
                - 'stderr': str
                - 'returncode': int
                - 'side_effects': dict with impact analysis
                - 'error': str (if any)
        """
        if test_command is None:
            test_command = [sys.executable, '-m', 'pytest', '--tb=short', '-q']

        clone_sources = self.cloner.get_clone_sources()
        result = {
            'passed': False,
            'stdout': '',
            'stderr': '',
            'returncode': -1,
            'side_effects': {},
            'error': ''
        }

        try:
            with SandboxEnvironment(clone_sources) as sandbox:
                # Apply mutation
                mutation_file = mutation.get('file')
                mutation_source = mutation.get('source')
                if not mutation_file or not mutation_source:
                    raise ValueError("Mutation must contain 'file' (Path) and 'source' (str)")

                sandbox.apply_mutation(mutation_file, mutation_source)

                # Run tests
                test_result = sandbox.run_test(test_command)

                # Analyze side effects
                side_effects = self._analyze_side_effects(
                    sandbox.temp_dir,
                    mutation_file,
                    mutation_source,
                    clone_sources
                )

                result.update({
                    'passed': test_result.returncode == 0,
                    'stdout': test_result.stdout,
                    'stderr': test_result.stderr,
                    'returncode': test_result.returncode,
                    'side_effects': side_effects
                })

        except subprocess.TimeoutExpired:
            result['error'] = 'Test execution timed out'
        except FileNotFoundError as e:
            result['error'] = f"File not found: {e}"
        except ValueError as e:
            result['error'] = str(e)
        except Exception as e:
            result['error'] = f"Unexpected error: {str(e)}"

        return result

    def _analyze_side_effects(self, sandbox_path: Path, mutated_file: Path,
                              mutated_source: str, original_sources: Dict[Path, str]) -> Dict[str, Any]:
        """Analyze the impact of the mutation on the dependency subgraph."""
        side_effects = {
            'mutated_file': str(mutated_file),
            'affected_dependencies': [],
            'import_changes': [],
            'structural_changes': []
        }

        # Compare AST of original vs mutated
        original_source = original_sources.get(mutated_file, '')
        try:
            original_tree = ast.parse(original_source)
            mutated_tree = ast.parse(mutated_source)

            # Detect import changes
            original_imports = {node.names[0].name for node in ast.walk(original_tree)
                               if isinstance(node, (ast.Import, ast.ImportFrom)) and node.names}
            mutated_imports = {node.names[0].name for node in ast.walk(mutated_tree)
                               if isinstance(node, (ast.Import, ast.ImportFrom)) and node.names}

            added_imports = mutated_imports - original_imports
            removed_imports = original_imports - mutated_imports
            if added_imports:
                side_effects['import_changes'].append({'type': 'added', 'imports': list(added_imports)})
            if removed_imports:
                side_effects['import_changes'].append({'type': 'removed', 'imports': list(removed_imports)})

            # Detect structural changes (function/class definitions)
            original_defs = {node.name for node in ast.walk(original_tree)
                             if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef))}
            mutated_defs = {node.name for node in ast.walk(mutated_tree)
                            if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef))}

            added_defs = mutated_defs - original_defs
            removed_defs = original_defs - mutated_defs
            if added_defs:
                side_effects['structural_changes'].append({'type': 'added', 'definitions': list(added_defs)})
            if removed_defs:
                side_effects['structural_changes'].append({'type': 'removed', 'definitions': list(removed_defs)})

            # Identify affected dependencies (files that import from mutated file)
            mutated_module_name = mutated_file.stem
            for dep_path, dep_source in original_sources.items():
                if dep_path != mutated_file:
                    try:
                        dep_tree = ast.parse(dep_source)
                        for node in ast.walk(dep_tree):
                            if isinstance(node, ast.ImportFrom) and node.module == mutated_module_name:
                                side_effects['affected_dependencies'].append(str(dep_path))
                                break
                            elif isinstance(node, ast.Import):
                                for alias in node.names:
                                    if alias.name == mutated_module_name or alias.name.startswith(f"{mutated_module_name}."):
                                        side_effects['affected_dependencies'].append(str(dep_path))
                                        break
                    except SyntaxError:
                        pass

        except SyntaxError:
            side_effects['structural_changes'].append({'type': 'syntax_error', 'detail': 'Mutated source has syntax errors'})

        return side_effects

    def batch_simulate(self, mutations: List[Dict[str, Any]],
                       test_command: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Run multiple mutation simulations sequentially."""
        results = []
        for mutation in mutations:
            result = self.simulate(mutation, test_command)
            results.append(result)
        return results