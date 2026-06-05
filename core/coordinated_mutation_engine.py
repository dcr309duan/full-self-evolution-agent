"""Coordinated Mutation Engine for multi-module atomic changes."""

import ast
import copy
import hashlib
import logging
import os
import tempfile
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class CoordinatedMutation:
    """A single mutation within a coordinated set."""
    module_path: str
    change_description: str
    original_content: str = ""
    mutated_content: str = ""
    success: bool = False
    error: Optional[str] = None
    backup_path: Optional[str] = None


@dataclass
class MutationPlan:
    """Plan for a coordinated mutation across modules."""
    modules: List[str]
    interaction_description: str
    mutations: List[CoordinatedMutation] = field(default_factory=list)
    sandbox_dir: Optional[str] = None
    rollback_point_id: str = ""
    applied: bool = False


class CoordinatedMutationEngine:
    """Engine for generating and applying coordinated multi-module mutations."""

    def __init__(self, workspace_root: str = ".", sandbox_enabled: bool = True):
        self.workspace_root = Path(workspace_root).resolve()
        self.sandbox_enabled = sandbox_enabled
        self._plans: Dict[str, MutationPlan] = {}
        self._mutation_generators: Dict[str, Callable] = {}
        self._dependency_graph: Dict[str, List[str]] = {}

    def register_mutation_generator(self, module_pattern: str, generator: Callable) -> None:
        """Register a generator function for a module pattern."""
        self._mutation_generators[module_pattern] = generator

    def build_dependency_graph(self, modules: List[str]) -> Dict[str, List[str]]:
        """Build a simple dependency graph from module imports."""
        graph: Dict[str, List[str]] = {}
        for module_path in modules:
            full_path = self.workspace_root / module_path
            if full_path.exists():
                try:
                    with open(full_path, "r") as f:
                        content = f.read()
                    tree = ast.parse(content)
                    imports = []
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Import):
                            for alias in node.names:
                                imports.append(alias.name)
                        elif isinstance(node, ast.ImportFrom):
                            if node.module:
                                imports.append(node.module)
                    graph[module_path] = imports
                except Exception:
                    graph[module_path] = []
        self._dependency_graph = graph
        return graph

    def create_plan(self, modules: List[str], interaction_description: str) -> MutationPlan:
        """Create a mutation plan for coordinated changes across modules."""
        plan_id = hashlib.sha256(
            "|".join(sorted(modules) + [interaction_description]).encode()
        ).hexdigest()[:16]

        plan = MutationPlan(
            modules=modules,
            interaction_description=interaction_description,
            rollback_point_id=plan_id,
        )

        # Build dependency graph
        self.build_dependency_graph(modules)

        # Generate mutations for each module
        for module_path in modules:
            mutation = self._generate_mutation(module_path, interaction_description)
            plan.mutations.append(mutation)

        self._plans[plan_id] = plan
        return plan

    def _generate_mutation(self, module_path: str, interaction_description: str) -> CoordinatedMutation:
        """Generate a single mutation for a module based on the interaction description."""
        full_path = self.workspace_root / module_path
        mutation = CoordinatedMutation(module_path=module_path, change_description=interaction_description)

        try:
            if not full_path.exists():
                mutation.error = f"Module not found: {module_path}"
                return mutation

            # Read original content
            with open(full_path, "r") as f:
                original = f.read()
            mutation.original_content = original

            # Check for registered generator
            for pattern, generator in self._mutation_generators.items():
                if pattern in module_path or module_path.endswith(pattern):
                    mutated = generator(original, interaction_description, module_path)
                    mutation.mutated_content = mutated
                    mutation.success = True
                    return mutation

            # Default: use AST-based mutation
            mutated = self._default_mutate(original, interaction_description, module_path)
            mutation.mutated_content = mutated
            mutation.success = True

        except Exception as e:
            mutation.error = f"Mutation generation failed: {str(e)}\n{traceback.format_exc()}"
            logger.error(f"Failed to generate mutation for {module_path}: {e}")

        return mutation

    def _default_mutate(self, content: str, description: str, module_path: str) -> str:
        """Default mutation strategy using AST manipulation."""
        try:
            tree = ast.parse(content)
            transformer = _CoordinatedASTTransformer(description, module_path)
            modified_tree = transformer.visit(tree)
            ast.fix_missing_locations(modified_tree)
            return ast.unparse(modified_tree)
        except SyntaxError:
            # Fallback to simple text replacement if AST fails
            return self._text_based_mutate(content, description, module_path)

    def _text_based_mutate(self, content: str, description: str, module_path: str) -> str:
        """Fallback text-based mutation when AST parsing fails."""
        lines = content.split("\n")
        modified_lines = list(lines)

        # Add a coordinated mutation marker comment
        marker = f"# Coordinated mutation: {description[:50]}..."
        if modified_lines and not modified_lines[-1].strip().startswith("# Coordinated"):
            modified_lines.append("")
            modified_lines.append(marker)
            modified_lines.append(f"# Module: {module_path}")

        return "\n".join(modified_lines)

    def validate_mutations(self, plan: MutationPlan) -> bool:
        """Validate that all mutations in a plan are compatible."""
        if not plan.mutations:
            logger.warning("No mutations to validate")
            return False

        # Check all mutations generated successfully
        for mutation in plan.mutations:
            if not mutation.success:
                logger.error(f"Mutation failed for {mutation.module_path}: {mutation.error}")
                return False

        # Check for cross-module consistency (e.g., function signatures match)
        return self._check_cross_module_consistency(plan)

    def _check_cross_module_consistency(self, plan: MutationPlan) -> bool:
        """Check that mutations across modules are consistent with each other."""
        try:
            # Extract function/class definitions from each mutation
            definitions: Dict[str, set] = {}
            for mutation in plan.mutations:
                if mutation.mutated_content:
                    try:
                        tree = ast.parse(mutation.mutated_content)
                        names = set()
                        for node in ast.walk(tree):
                            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                                names.add(node.name)
                        definitions[mutation.module_path] = names
                    except SyntaxError:
                        continue

            # Check for naming conflicts
            all_names = set()
            for module_name, names in definitions.items():
                conflicts = names & all_names
                if conflicts:
                    logger.warning(f"Name conflicts detected in {module_name}: {conflicts}")
                all_names.update(names)

            # Check dependency compatibility
            if self._dependency_graph:
                for module_path, deps in self._dependency_graph.items():
                    for dep in deps:
                        dep_module = dep.replace(".", "/") + ".py"
                        if dep_module in plan.modules:
                            dep_mutation = next((m for m in plan.mutations if m.module_path == dep_module), None)
                            if dep_mutation and dep_mutation.success:
                                # Check if the dependent module uses any changed names
                                try:
                                    dep_tree = ast.parse(dep_mutation.mutated_content)
                                    dep_names = set()
                                    for node in ast.walk(dep_tree):
                                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                                            dep_names.add(node.name)
                                    # Verify the dependent module still has expected interfaces
                                    if module_path in definitions:
                                        expected_names = definitions[module_path]
                                        missing = expected_names - dep_names
                                        if missing:
                                            logger.warning(f"Dependency {dep_module} missing expected names: {missing}")
                                except SyntaxError:
                                    continue

            return True

        except Exception as e:
            logger.error(f"Consistency check failed: {e}")
            return False

    def apply_mutations(self, plan: MutationPlan) -> bool:
        """Apply all mutations in a plan atomically with sandbox support."""
        if plan.applied:
            logger.warning(f"Plan {plan.rollback_point_id} already applied")
            return False

        if not self.validate_mutations(plan):
            logger.error("Mutation validation failed, aborting")
            return False

        # Create sandbox if enabled
        sandbox_path = None
        if self.sandbox_enabled:
            sandbox_path = self._create_sandbox(plan)
            plan.sandbox_dir = str(sandbox_path)

        # Create backups and apply mutations
        applied_mutations = []
        try:
            for mutation in plan.mutations:
                full_path = self.workspace_root / mutation.module_path

                # Create backup
                backup_path = self._create_backup(full_path)
                mutation.backup_path = str(backup_path)

                # Apply mutation
                with open(full_path, "w") as f:
                    f.write(mutation.mutated_content)

                applied_mutations.append(mutation)
                logger.info(f"Applied mutation to {mutation.module_path}")

            plan.applied = True
            logger.info(f"Successfully applied coordinated mutation plan {plan.rollback_point_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to apply mutations: {e}")
            self._rollback(applied_mutations)
            return False

    def _create_sandbox(self, plan: MutationPlan) -> Path:
        """Create a sandbox directory for testing mutations."""
        sandbox_dir = Path(tempfile.mkdtemp(prefix=f"coord_mutation_{plan.rollback_point_id}_"))
        for mutation in plan.mutations:
            src_path = self.workspace_root / mutation.module_path
            if src_path.exists():
                sandbox_file = sandbox_dir / mutation.module_path
                sandbox_file.parent.mkdir(parents=True, exist_ok=True)
                with open(sandbox_file, "w") as f:
                    f.write(mutation.mutated_content)
        return sandbox_dir

    def _create_backup(self, file_path: Path) -> Path:
        """Create a backup of a file before mutation."""
        backup_dir = self.workspace_root / ".coordinated_mutation_backups"
        backup_dir.mkdir(exist_ok=True)

        backup_name = f"{file_path.name}.{hashlib.md5(str(file_path).encode()).hexdigest()[:8]}.bak"
        backup_path = backup_dir / backup_name

        if file_path.exists():
            import shutil
            shutil.copy2(file_path, backup_path)

        return backup_path

    def _rollback(self, applied_mutations: List[CoordinatedMutation]) -> None:
        """Rollback applied mutations."""
        for mutation in applied_mutations:
            if mutation.backup_path:
                backup_path = Path(mutation.backup_path)
                if backup_path.exists():
                    import shutil
                    shutil.copy2(backup_path, self.workspace_root / mutation.module_path)
                    logger.info(f"Rolled back {mutation.module_path}")

    def rollback_plan(self, plan_id: str) -> bool:
        """Rollback an entire mutation plan."""
        plan = self._plans.get(plan_id)
        if not plan:
            logger.error(f"Plan {plan_id} not found")
            return False

        self._rollback(plan.mutations)
        plan.applied = False
        logger.info(f"Rolled back plan {plan_id}")
        return True

    def test_in_sandbox(self, plan: MutationPlan, test_command: str) -> Tuple[bool, str]:
        """Test mutations in sandbox before applying."""
        if not plan.sandbox_dir:
            plan.sandbox_dir = str(self._create_sandbox(plan))

        import subprocess
        try:
            result = subprocess.run(
                test_command,
                shell=True,
                cwd=plan.sandbox_dir,
                capture_output=True,
                text=True,
                timeout=30
            )
            success = result.returncode == 0
            output = result.stdout + result.stderr
            return success, output
        except subprocess.TimeoutExpired:
            return False, "Sandbox test timed out"
        except Exception as e:
            return False, f"Sandbox test failed: {e}"


class _CoordinatedASTTransformer(ast.NodeTransformer):
    """AST transformer for coordinated mutations."""

    def __init__(self, description: str, module_path: str):
        self.description = description
        self.module_path = module_path
        self._modified = False

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
        """Add coordination markers to function definitions."""
        if not self._modified:
            # Add a docstring or comment indicating coordinated change
            new_docstring = (
                f"Coordinated mutation for: {self.description[:100]}"
            )
            if not ast.get_docstring(node):
                node.body.insert(0, ast.Expr(value=ast.Constant(value=new_docstring)))
            self._modified = True
        return node

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.ClassDef:
        """Add coordination markers to class definitions."""
        if not self._modified:
            new_docstring = (
                f"Coordinated mutation for: {self.description[:100]}"
            )
            if not ast.get_docstring(node):
                node.body.insert(0, ast.Expr(value=ast.Constant(value=new_docstring)))
            self._modified = True
        return node


# Convenience function for quick coordinated mutations
def coordinated_mutate(
    modules: List[str],
    description: str,
    workspace_root: str = ".",
    apply: bool = False,
    test_command: Optional[str] = None,
) -> Optional[MutationPlan]:
    """Quick coordinated mutation across modules."""
    engine = CoordinatedMutationEngine(workspace_root=workspace_root)
    plan = engine.create_plan(modules, description)

    if test_command:
        success, output = engine.test_in_sandbox(plan, test_command)
        if not success:
            logger.error(f"Sandbox test failed: {output}")
            return None

    if apply:
        success = engine.apply_mutations(plan)
        if not success:
            logger.error("Failed to apply coordinated mutations")
            return None

    return plan