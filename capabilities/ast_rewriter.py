"""
AST rewriter module with multi-file transactional refactoring support.

This module extends the basic AST rewriting capabilities to handle changes
across multiple files atomically, with automatic rollback on failure.
It integrates with the dependency analyzer to manage import statements
during refactoring operations.
"""

import ast
import copy
import os
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path

from .dependency_analyzer import DependencyAnalyzer


class ASTModification:
    """Represents a single AST modification to be applied to a file."""

    def __init__(self, node: ast.AST, transformer: ast.NodeTransformer):
        """
        Initialize an AST modification.

        Args:
            node: The AST node to modify
            transformer: The transformer to apply to the node
        """
        self.node = node
        self.transformer = transformer


class ASTRewriterError(Exception):
    """Base exception for AST rewriter errors."""
    pass


class TransactionError(ASTRewriterError):
    """Exception raised when a transaction fails."""
    pass


class FileBackup:
    """Manages file backups for rollback operations."""

    def __init__(self, file_path: str):
        """
        Initialize file backup.

        Args:
            file_path: Path to the file to backup
        """
        self.file_path = file_path
        self.backup_content: Optional[str] = None
        self.backup_path: Optional[str] = None

    def create_backup(self) -> None:
        """Create a backup of the current file content."""
        if not os.path.exists(self.file_path):
            return

        with open(self.file_path, 'r', encoding='utf-8') as f:
            self.backup_content = f.read()

        # Create backup file with .bak extension
        self.backup_path = self.file_path + '.bak'
        with open(self.backup_path, 'w', encoding='utf-8') as f:
            f.write(self.backup_content)

    def restore(self) -> None:
        """Restore the file from backup."""
        if self.backup_content is None:
            return

        with open(self.file_path, 'w', encoding='utf-8') as f:
            f.write(self.backup_content)

    def cleanup(self) -> None:
        """Remove the backup file."""
        if self.backup_path and os.path.exists(self.backup_path):
            os.remove(self.backup_path)


class ASTRewriter:
    """
    AST rewriter with multi-file transactional support.

    This class extends basic AST rewriting to handle changes across multiple
    files atomically, with automatic rollback on failure. It integrates with
    the dependency analyzer for import management.
    """

    def __init__(self, dependency_analyzer: Optional[DependencyAnalyzer] = None):
        """
        Initialize the AST rewriter.

        Args:
            dependency_analyzer: Optional dependency analyzer for import management
        """
        self.dependency_analyzer = dependency_analyzer or DependencyAnalyzer()
        self._backups: Dict[str, FileBackup] = {}
        self._transaction_active = False

    def refactor_across_files(
        self, changes: List[Tuple[str, List[ASTModification]]]
    ) -> None:
        """
        Apply changes transactionally across multiple files.

        Args:
            changes: List of (file_path, modifications) tuples

        Raises:
            TransactionError: If any modification fails and rollback is performed
        """
        if not changes:
            return

        self._begin_transaction()

        try:
            for file_path, modifications in changes:
                self._apply_modifications(file_path, modifications)

            self._commit_transaction()
        except Exception as e:
            self._rollback_transaction()
            raise TransactionError(
                f"Transaction failed, changes rolled back: {str(e)}"
            ) from e

    def _begin_transaction(self) -> None:
        """Start a new transaction."""
        if self._transaction_active:
            raise TransactionError("Transaction already in progress")

        self._transaction_active = True
        self._backups.clear()

    def _commit_transaction(self) -> None:
        """Commit the current transaction."""
        if not self._transaction_active:
            raise TransactionError("No active transaction to commit")

        # Clean up backup files
        for backup in self._backups.values():
            backup.cleanup()

        self._backups.clear()
        self._transaction_active = False

    def _rollback_transaction(self) -> None:
        """Rollback the current transaction."""
        if not self._transaction_active:
            return

        # Restore all backed up files
        for backup in self._backups.values():
            try:
                backup.restore()
                backup.cleanup()
            except Exception as e:
                print(f"Warning: Failed to restore {backup.file_path}: {e}")

        self._backups.clear()
        self._transaction_active = False

    def _apply_modifications(
        self, file_path: str, modifications: List[ASTModification]
    ) -> None:
        """
        Apply AST modifications to a single file.

        Args:
            file_path: Path to the file to modify
            modifications: List of modifications to apply

        Raises:
            FileNotFoundError: If the file doesn't exist
            ASTRewriterError: If modification fails
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        # Create backup if not already backed up
        if file_path not in self._backups:
            backup = FileBackup(file_path)
            backup.create_backup()
            self._backups[file_path] = backup

        # Read and parse the file
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()

        try:
            tree = ast.parse(source, filename=file_path)
        except SyntaxError as e:
            raise ASTRewriterError(f"Failed to parse {file_path}: {e}") from e

        # Apply modifications
        modified_tree = self._apply_transformations(tree, modifications)

        # Update imports if needed
        if self.dependency_analyzer:
            modified_tree = self._update_imports(file_path, modified_tree)

        # Write modified content back
        try:
            modified_source = ast.unparse(modified_tree)
        except Exception as e:
            raise ASTRewriterError(
                f"Failed to unparse modified AST for {file_path}: {e}"
            ) from e

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(modified_source)

    def _apply_transformations(
        self, tree: ast.AST, modifications: List[ASTModification]
    ) -> ast.AST:
        """
        Apply a list of transformations to an AST tree.

        Args:
            tree: The AST tree to transform
            modifications: List of modifications to apply

        Returns:
            The transformed AST tree
        """
        # Deep copy to avoid modifying the original
        tree = copy.deepcopy(tree)

        for modification in modifications:
            try:
                tree = self._apply_single_transformation(tree, modification)
            except Exception as e:
                raise ASTRewriterError(
                    f"Failed to apply transformation: {e}"
                ) from e

        return tree

    def _apply_single_transformation(
        self, tree: ast.AST, modification: ASTModification
    ) -> ast.AST:
        """
        Apply a single transformation to the AST tree.

        Args:
            tree: The AST tree to transform
            modification: The modification to apply

        Returns:
            The transformed AST tree
        """
        transformer = modification.transformer

        # Visit and transform the tree
        transformed_tree = transformer.visit(tree)

        # Fix missing locations if needed
        ast.fix_missing_locations(transformed_tree)

        return transformed_tree

    def _update_imports(self, file_path: str, tree: ast.AST) -> ast.AST:
        """
        Update imports in the AST tree based on dependency analysis.

        Args:
            file_path: Path to the file being modified
            tree: The AST tree to update

        Returns:
            The AST tree with updated imports
        """
        # Get dependencies for the file
        dependencies = self.dependency_analyzer.get_dependencies(file_path)

        # Add missing imports
        for dependency in dependencies:
            if not self._import_exists(tree, dependency):
                tree = self._add_import(tree, dependency)

        # Remove unused imports
        tree = self._remove_unused_imports(tree, dependencies)

        return tree

    def _import_exists(self, tree: ast.AST, import_name: str) -> bool:
        """
        Check if an import already exists in the AST tree.

        Args:
            tree: The AST tree to check
            import_name: The import name to look for

        Returns:
            True if the import exists, False otherwise
        """
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == import_name:
                        return True
            elif isinstance(node, ast.ImportFrom):
                if node.module == import_name:
                    return True
        return False

    def _add_import(self, tree: ast.AST, import_name: str) -> ast.AST:
        """
        Add an import statement to the AST tree.

        Args:
            tree: The AST tree to modify
            import_name: The import to add

        Returns:
            The modified AST tree
        """
        import_node = ast.Import(names=[ast.alias(name=import_name, asname=None)])

        # Add import at the beginning of the module
        if isinstance(tree, ast.Module):
            tree.body.insert(0, import_node)

        return tree

    def _remove_unused_imports(
        self, tree: ast.AST, used_imports: List[str]
    ) -> ast.AST:
        """
        Remove unused imports from the AST tree.

        Args:
            tree: The AST tree to modify
            used_imports: List of imports that are actually used

        Returns:
            The modified AST tree
        """
        if not isinstance(tree, ast.Module):
            return tree

        # Collect all import nodes
        import_nodes = []
        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                import_nodes.append(node)

        # Remove unused imports
        for node in import_nodes:
            if isinstance(node, ast.Import):
                # Filter out unused imports
                node.names = [
                    alias for alias in node.names
                    if alias.name in used_imports
                ]
                if not node.names:
                    tree.body.remove(node)
            elif isinstance(node, ast.ImportFrom):
                if node.module not in used_imports:
                    tree.body.remove(node)

        return tree

    def apply_single_file(
        self, file_path: str, modifications: List[ASTModification]
    ) -> None:
        """
        Apply modifications to a single file (non-transactional).

        Args:
            file_path: Path to the file to modify
            modifications: List of modifications to apply

        Raises:
            FileNotFoundError: If the file doesn't exist
            ASTRewriterError: If modification fails
        """
        self._apply_modifications(file_path, modifications)

    def create_modification(
        self, node: ast.AST, transformer: ast.NodeTransformer
    ) -> ASTModification:
        """
        Create an ASTModification object.

        Args:
            node: The AST node to modify
            transformer: The transformer to apply

        Returns:
            An ASTModification object
        """
        return ASTModification(node=node, transformer=transformer)