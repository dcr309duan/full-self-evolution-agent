import ast
import os
import shutil
import json
import time
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from collections import defaultdict

logger = logging.getLogger(__name__)

class CapabilityConsolidationEngine:
    """
    Engine for analyzing, scoring, and consolidating Python modules in a codebase.
    
    Provides capabilities to scan modules, compute utility scores, archive low-value
    modules, and refactor high-complexity pathways.
    """
    
    def __init__(self, codebase_root: str, archive_dir: str = "archive", 
                 module_registry_path: str = "module_registry.json"):
        """
        Initialize the consolidation engine.
        
        Args:
            codebase_root: Root directory of the codebase to analyze
            archive_dir: Directory to move archived modules to
            module_registry_path: Path to the module registry JSON file
        """
        self.codebase_root = Path(codebase_root)
        self.archive_dir = self.codebase_root / archive_dir
        self.module_registry_path = Path(module_registry_path)
        self.modules: Dict[str, Dict[str, Any]] = {}
        self.import_graph: Dict[str, List[str]] = defaultdict(list)
        self.mutation_log: Dict[str, int] = {}
        self.last_modification_time: Dict[str, float] = {}
        
        # Ensure archive directory exists
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        
        # Load existing registry if available
        self._load_registry()
    
    def _load_registry(self) -> None:
        """Load the module registry from disk if it exists."""
        if self.module_registry_path.exists():
            try:
                with open(self.module_registry_path, 'r') as f:
                    data = json.load(f)
                    self.modules = data.get('modules', {})
                    self.import_graph = defaultdict(list, data.get('import_graph', {}))
                    self.mutation_log = data.get('mutation_log', {})
                    self.last_modification_time = data.get('last_modification_time', {})
                logger.info(f"Loaded registry with {len(self.modules)} modules")
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Failed to load registry: {e}. Starting fresh.")
    
    def _save_registry(self) -> None:
        """Save the current module registry to disk."""
        data = {
            'modules': self.modules,
            'import_graph': dict(self.import_graph),
            'mutation_log': self.mutation_log,
            'last_modification_time': self.last_modification_time
        }
        with open(self.module_registry_path, 'w') as f:
            json.dump(data, f, indent=2)
        logger.info(f"Saved registry with {len(self.modules)} modules")
    
    def scan_all_modules(self) -> Dict[str, Dict[str, Any]]:
        """
        Discover all Python modules in the codebase and analyze their properties.
        
        Returns:
            Dictionary mapping module paths to their metadata
        """
        self.modules = {}
        self.import_graph.clear()
        
        # Walk through all Python files in the codebase
        for py_file in self.codebase_root.rglob("*.py"):
            # Skip files in archive directory
            if self.archive_dir in py_file.parents:
                continue
                
            relative_path = py_file.relative_to(self.codebase_root)
            module_path = str(relative_path).replace(os.sep, '.')[:-3]  # Remove .py
            
            # Get module metadata
            self.modules[module_path] = {
                'path': str(relative_path),
                'absolute_path': str(py_file),
                'size': py_file.stat().st_size,
                'last_modified': py_file.stat().st_mtime,
                'usage_frequency': 0,
                'failure_rate': 0.0,
                'dependency_count': 0,
                'age': 0,
                'score': 0.0
            }
            
            # Track last modification time
            self.last_modification_time[module_path] = py_file.stat().st_mtime
            
            # Parse imports
            try:
                with open(py_file, 'r') as f:
                    tree = ast.parse(f.read(), filename=str(py_file))
                self._analyze_imports(tree, module_path)
            except (SyntaxError, UnicodeDecodeError) as e:
                logger.warning(f"Could not parse {py_file}: {e}")
        
        # Calculate dependency counts
        for module_path in self.modules:
            self.modules[module_path]['dependency_count'] = len(self.import_graph.get(module_path, []))
        
        # Update usage frequency based on import counts
        self._update_usage_frequency()
        
        # Calculate age (cycles since last modification)
        current_time = time.time()
        for module_path in self.modules:
            last_mod = self.last_modification_time.get(module_path, current_time)
            self.modules[module_path]['age'] = current_time - last_mod
        
        # Score all modules
        for module_path in self.modules:
            self.modules[module_path]['score'] = self.score_module(module_path)
        
        self._save_registry()
        logger.info(f"Scanned {len(self.modules)} modules")
        return self.modules
    
    def _analyze_imports(self, tree: ast.AST, module_path: str) -> None:
        """
        Analyze AST to extract import statements and build import graph.
        
        Args:
            tree: AST of the module
            module_path: Path of the current module
        """
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported_module = alias.name
                    self.import_graph[module_path].append(imported_module)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    self.import_graph[module_path].append(node.module)
    
    def _update_usage_frequency(self) -> None:
        """Update usage frequency for each module based on how many other modules import it."""
        # Count how many modules import each module
        import_counts = defaultdict(int)
        for module_path, imports in self.import_graph.items():
            for imported in imports:
                # Check if imported module exists in our modules
                if imported in self.modules:
                    import_counts[imported] += 1
                # Also check for submodule imports
                for mod in self.modules:
                    if mod.startswith(imported + '.') or mod == imported:
                        import_counts[mod] += 1
        
        for module_path in self.modules:
            self.modules[module_path]['usage_frequency'] = import_counts.get(module_path, 0)
    
    def score_module(self, module_path: str) -> float:
        """
        Compute a utility score for a module based on multiple factors.
        
        Score components:
        - usage_frequency: How often the module is imported (0-40 points)
        - failure_rate: Inverse of failure rate from mutation logs (0-30 points)
        - dependency_count: Number of dependencies (0-20 points, lower is better)
        - age: Time since last modification (0-10 points, newer is better)
        
        Args:
            module_path: Path of the module to score
            
        Returns:
            Utility score between 0 and 100
        """
        if module_path not in self.modules:
            logger.warning(f"Module {module_path} not found in registry")
            return 0.0
        
        module = self.modules[module_path]
        
        # Usage frequency score (0-40 points)
        max_usage = max(m['usage_frequency'] for m in self.modules.values()) if self.modules else 1
        usage_score = (module['usage_frequency'] / max_usage) * 40 if max_usage > 0 else 0
        
        # Failure rate score (0-30 points) - lower failure rate = higher score
        failure_rate = self.mutation_log.get(module_path, 0)
        # Normalize failure rate: assume max 10 failures for 0 score
        failure_score = max(0, 30 - (failure_rate * 3))
        
        # Dependency count score (0-20 points) - fewer dependencies = higher score
        max_deps = max(m['dependency_count'] for m in self.modules.values()) if self.modules else 1
        dep_score = (1 - (module['dependency_count'] / max_deps)) * 20 if max_deps > 0 else 20
        
        # Age score (0-10 points) - newer modules = higher score
        # Normalize age: assume max age of 30 days (2592000 seconds) for 0 score
        max_age = 2592000  # 30 days in seconds
        age_score = max(0, 10 - (module['age'] / max_age) * 10)
        
        total_score = usage_score + failure_score + dep_score + age_score
        return round(total_score, 2)
    
    def archive_module(self, module_path: str, threshold: float = 20.0) -> bool:
        """
        Move a low-scoring module to the archive directory and update the registry.
        
        Args:
            module_path: Path of the module to archive
            threshold: Score threshold below which modules can be archived
            
        Returns:
            True if module was archived, False otherwise
        """
        if module_path not in self.modules:
            logger.warning(f"Module {module_path} not found in registry")
            return False
        
        module = self.modules[module_path]
        
        # Check if module score is below threshold
        if module['score'] > threshold:
            logger.info(f"Module {module_path} score ({module['score']}) above threshold ({threshold}), skipping")
            return False
        
        source_path = Path(module['absolute_path'])
        if not source_path.exists():
            logger.warning(f"Source file {source_path} does not exist")
            return False
        
        # Create archive subdirectory structure
        archive_subdir = self.archive_dir / source_path.relative_to(self.codebase_root).parent
        archive_subdir.mkdir(parents=True, exist_ok=True)
        
        # Move file to archive
        destination_path = self.archive_dir / source_path.relative_to(self.codebase_root)
        try:
            shutil.move(str(source_path), str(destination_path))
            logger.info(f"Archived {module_path} to {destination_path}")
        except OSError as e:
            logger.error(f"Failed to archive {module_path}: {e}")
            return False
        
        # Update registry
        self.modules[module_path]['archived'] = True
        self.modules[module_path]['archive_path'] = str(destination_path)
        self.modules[module_path]['archived_at'] = time.time()
        
        # Remove from import graph
        if module_path in self.import_graph:
            del self.import_graph[module_path]
        
        # Update all modules that imported this module
        for mod in list(self.import_graph.keys()):
            if module_path in self.import_graph[mod]:
                self.import_graph[mod].remove(module_path)
        
        self._save_registry()
        return True
    
    def refactor_core_pathways(self) -> List[Dict[str, Any]]:
        """
        Identify high-complexity modules and generate simplified replacement suggestions.
        
        High-complexity modules are those with high dependency count and low score.
        Returns a list of refactoring suggestions.
        
        Returns:
            List of dictionaries containing refactoring suggestions
        """
        refactoring_suggestions = []
        
        # Identify high-complexity modules
        # High complexity: high dependency count (top 25%) AND low score (bottom 25%)
        if not self.modules:
            logger.warning("No modules to analyze for refactoring")
            return refactoring_suggestions
        
        # Calculate thresholds
        dep_counts = [m['dependency_count'] for m in self.modules.values()]
        scores = [m['score'] for m in self.modules.values()]
        
        if not dep_counts or not scores:
            return refactoring_suggestions
        
        dep_threshold = sorted(dep_counts)[len(dep_counts) * 3 // 4] if dep_counts else 0
        score_threshold = sorted(scores)[len(scores) // 4] if scores else 0
        
        high_complexity_modules = [
            path for path, module in self.modules.items()
            if module['dependency_count'] >= dep_threshold and module['score'] <= score_threshold
        ]
        
        logger.info(f"Found {len(high_complexity_modules)} high-complexity modules")
        
        for module_path in high_complexity_modules:
            module = self.modules[module_path]
            
            # Analyze dependencies
            dependencies = self.import_graph.get(module_path, [])
            
            # Generate simplified replacement suggestion
            suggestion = self._generate_refactoring_suggestion(module_path, module, dependencies)
            refactoring_suggestions.append(suggestion)
        
        return refactoring_suggestions
    
    def _generate_refactoring_suggestion(self, module_path: str, module: Dict[str, Any], 
                                          dependencies: List[str]) -> Dict[str, Any]:
        """
        Generate a refactoring suggestion for a high-complexity module.
        
        Args:
            module_path: Path of the module to refactor
            module: Module metadata
            dependencies: List of module dependencies
            
        Returns:
            Dictionary with refactoring suggestion details
        """
        # Analyze which dependencies are most critical
        critical_deps = []
        non_critical_deps = []
        
        for dep in dependencies:
            if dep in self.modules:
                dep_module = self.modules[dep]
                if dep_module['usage_frequency'] > 2:  # Used by multiple modules
                    critical_deps.append(dep)
                else:
                    non_critical_deps.append(dep)
            else:
                non_critical_deps.append(dep)
        
        # Generate replacement code structure
        replacement_structure = {
            'original_module': module_path,
            'complexity_score': module['score'],
            'dependency_count': module['dependency_count'],
            'critical_dependencies': critical_deps,
            'non_critical_dependencies': non_critical_deps,
            'suggested_actions': []
        }
        
        # Suggest splitting into smaller modules
        if len(critical_deps) > 3:
            replacement_structure['suggested_actions'].append({
                'action': 'split_module',
                'description': f"Split {module_path} into smaller modules based on critical dependencies",
                'new_modules': [f"{module_path}.{dep.split('.')[-1]}" for dep in critical_deps[:3]]
            })
        
        # Suggest removing unused dependencies
        if non_critical_deps:
            replacement_structure['suggested_actions'].append({
                'action': 'remove_unused_dependencies',
                'description': f"Remove {len(non_critical_deps)} non-critical dependencies",
                'dependencies_to_remove': non_critical_deps
            })
        
        # Suggest inlining small dependencies
        small_deps = [
            dep for dep in dependencies 
            if dep in self.modules and self.modules[dep]['size'] < 1024  # Less than 1KB
        ]
        if small_deps:
            replacement_structure['suggested_actions'].append({
                'action': 'inline_small_dependencies',
                'description': f"Inline {len(small_deps)} small dependencies",
                'dependencies_to_inline': small_deps
            })
        
        # Generate simplified replacement code template
        replacement_structure['replacement_template'] = self._create_replacement_template(
            module_path, critical_deps
        )
        
        return replacement_structure
    
    def _create_replacement_template(self, module_path: str, critical_deps: List[str]) -> str:
        """
        Create a template for the simplified replacement module.
        
        Args:
            module_path: Original module path
            critical_deps: Critical dependencies to keep
            
        Returns:
            String containing the replacement code template
        """
        template_lines = [
            f"# Simplified replacement for {module_path}",
            "# Generated by CapabilityConsolidationEngine",
            "",
            "# Critical dependencies (kept):",
        ]
        
        for dep in critical_deps:
            template_lines.append(f"from {dep} import *  # TODO: Replace with specific imports")
        
        template_lines.extend([
            "",
            "# TODO: Implement consolidated functionality",
            "# This module was refactored to reduce complexity",
            "",
            "def consolidated_function():",
            '    """Placeholder for consolidated functionality."""',
            "    pass",
            "",
            "# Remove non-critical dependencies and inline small utilities",
            "# to improve maintainability and reduce failure surface",
        ])
        
        return "\n".join(template_lines)
    
    def get_module_stats(self) -> Dict[str, Any]:
        """
        Get summary statistics about all scanned modules.
        
        Returns:
            Dictionary with module statistics
        """
        if not self.modules:
            return {'total_modules': 0, 'average_score': 0, 'archived_count': 0}
        
        scores = [m['score'] for m in self.modules.values()]
        archived_count = sum(1 for m in self.modules.values() if m.get('archived', False))
        
        return {
            'total_modules': len(self.modules),
            'average_score': round(sum(scores) / len(scores), 2) if scores else 0,
            'min_score': min(scores) if scores else 0,
            'max_score': max(scores) if scores else 0,
            'archived_count': archived_count,
            'high_complexity_count': len([
                m for m in self.modules.values()
                if m['dependency_count'] > 5 and m['score'] < 50
            ])
        }