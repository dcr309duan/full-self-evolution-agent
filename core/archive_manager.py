import os
import json
import shutil
import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

class ArchiveManager:
    """
    Manages archiving of module files with timestamped directory structure,
    import updates, manifest tracking, and rollback capability.
    """

    def __init__(self, base_dir: str = "archive", manifest_file: str = "archive_manifest.json"):
        self.base_dir = Path(base_dir)
        self.manifest_file = Path(manifest_file)
        self.manifest: Dict[str, dict] = {}
        self._load_manifest()

    def _load_manifest(self) -> None:
        """Load existing manifest from file if it exists."""
        if self.manifest_file.exists():
            try:
                with open(self.manifest_file, 'r') as f:
                    self.manifest = json.load(f)
            except (json.JSONDecodeError, IOError):
                self.manifest = {}

    def _save_manifest(self) -> None:
        """Save current manifest to file."""
        with open(self.manifest_file, 'w') as f:
            json.dump(self.manifest, f, indent=2)

    def _get_timestamped_dir(self) -> Path:
        """Create and return a timestamped archive directory."""
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_dir = self.base_dir / timestamp
        archive_dir.mkdir(parents=True, exist_ok=True)
        return archive_dir

    def _preserve_structure(self, source_path: Path, archive_dir: Path) -> Path:
        """
        Copy the source file to archive directory preserving its relative structure.
        Returns the destination path.
        """
        # Get the relative path from the project root (assuming source is relative to cwd)
        relative_path = source_path.relative_to(Path.cwd())
        dest_path = archive_dir / relative_path
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, dest_path)
        return dest_path

    def archive_module(self, module_path: str, score: float = 0.0, 
                       update_imports: bool = True) -> Tuple[bool, str]:
        """
        Archive a single module file.
        
        Args:
            module_path: Path to the module file to archive
            score: Numeric score/rating for the module
            update_imports: Whether to update imports in remaining modules
            
        Returns:
            Tuple of (success, message)
        """
        source = Path(module_path)
        if not source.exists():
            return False, f"Module {module_path} does not exist"

        try:
            # Create timestamped archive directory
            archive_dir = self._get_timestamped_dir()
            
            # Move file preserving structure
            dest_path = self._preserve_structure(source, archive_dir)
            
            # Remove original file
            source.unlink()
            
            # Update manifest
            archive_entry = {
                "original_path": str(source),
                "archive_path": str(dest_path),
                "score": score,
                "archive_date": datetime.datetime.now().isoformat(),
                "timestamp_dir": archive_dir.name
            }
            self.manifest[str(source)] = archive_entry
            self._save_manifest()
            
            # Update imports if requested
            if update_imports:
                self._update_imports_for_module(str(source))
            
            return True, f"Archived {module_path} to {dest_path}"
            
        except Exception as e:
            return False, f"Failed to archive {module_path}: {str(e)}"

    def archive_modules(self, module_paths: List[str], scores: Optional[List[float]] = None,
                        update_imports: bool = True) -> List[Tuple[str, bool, str]]:
        """
        Archive multiple module files.
        
        Args:
            module_paths: List of paths to module files to archive
            scores: Optional list of scores corresponding to each module
            update_imports: Whether to update imports in remaining modules
            
        Returns:
            List of (module_path, success, message) tuples
        """
        results = []
        for i, module_path in enumerate(module_paths):
            score = scores[i] if scores and i < len(scores) else 0.0
            success, message = self.archive_module(module_path, score, update_imports)
            results.append((module_path, success, message))
        return results

    def _update_imports_for_module(self, archived_module_path: str) -> None:
        """
        Update imports in all non-archived Python files that reference the archived module.
        Replaces imports with a stub comment or removes them.
        """
        archived_name = Path(archived_module_path).stem
        archived_imports = self._get_possible_import_names(archived_module_path)
        
        for py_file in Path.cwd().rglob("*.py"):
            if str(py_file) == archived_module_path:
                continue
            if self._is_archived(str(py_file)):
                continue
                
            self._update_file_imports(py_file, archived_imports)

    def _get_possible_import_names(self, module_path: str) -> List[str]:
        """Generate possible import names for a given module path."""
        path = Path(module_path)
        names = [path.stem]
        
        # Handle package imports (e.g., core.module_name)
        parts = path.relative_to(Path.cwd()).with_suffix('').parts
        if len(parts) > 1:
            names.append('.'.join(parts))
            names.append(parts[-1])
            
        return names

    def _is_archived(self, file_path: str) -> bool:
        """Check if a file path is inside an archive directory."""
        return any(str(Path(file_path)).startswith(str(self.base_dir)))

    def _update_file_imports(self, file_path: Path, archived_imports: List[str]) -> None:
        """Update imports in a single file that reference archived modules."""
        try:
            with open(file_path, 'r') as f:
                content = f.read()
            
            modified = False
            lines = content.split('\n')
            new_lines = []
            
            for line in lines:
                stripped = line.strip()
                # Check for import statements
                if stripped.startswith('import ') or stripped.startswith('from '):
                    should_archive = False
                    for import_name in archived_imports:
                        if import_name in stripped:
                            should_archive = True
                            break
                    
                    if should_archive:
                        # Replace with stub comment
                        new_lines.append(f"# {line}  # Archived module - functionality removed")
                        modified = True
                    else:
                        new_lines.append(line)
                else:
                    new_lines.append(line)
            
            if modified:
                with open(file_path, 'w') as f:
                    f.write('\n'.join(new_lines))
                    
        except (IOError, UnicodeDecodeError):
            pass  # Skip files we can't read/write

    def rollback(self, archive_timestamp: Optional[str] = None) -> List[Tuple[str, bool, str]]:
        """
        Rollback archived modules from a specific timestamp or all archives.
        
        Args:
            archive_timestamp: Specific timestamp directory to rollback (optional).
                              If None, rolls back the most recent archive.
        
        Returns:
            List of (module_path, success, message) tuples
        """
        results = []
        
        # Determine which entries to rollback
        if archive_timestamp:
            entries_to_rollback = {
                path: entry for path, entry in self.manifest.items()
                if entry.get("timestamp_dir") == archive_timestamp
            }
        else:
            # Find the most recent timestamp
            timestamps = set()
            for entry in self.manifest.values():
                if "timestamp_dir" in entry:
                    timestamps.add(entry["timestamp_dir"])
            
            if not timestamps:
                return [("", False, "No archives found to rollback")]
            
            latest_timestamp = sorted(timestamps)[-1]
            entries_to_rollback = {
                path: entry for path, entry in self.manifest.items()
                if entry.get("timestamp_dir") == latest_timestamp
            }
        
        # Rollback each entry
        for original_path, entry in entries_to_rollback.items():
            try:
                archive_path = Path(entry["archive_path"])
                original = Path(original_path)
                
                if not archive_path.exists():
                    results.append((original_path, False, f"Archived file not found: {archive_path}"))
                    continue
                
                # Restore the file
                original.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(archive_path, original)
                
                # Remove from manifest
                del self.manifest[original_path]
                
                results.append((original_path, True, f"Restored {original_path}"))
                
            except Exception as e:
                results.append((original_path, False, f"Failed to restore {original_path}: {str(e)}"))
        
        # Save updated manifest
        self._save_manifest()
        
        # Clean up empty timestamp directories
        if entries_to_rollback:
            timestamp_dir = list(entries_to_rollback.values())[0].get("timestamp_dir")
            if timestamp_dir:
                archive_dir = self.base_dir / timestamp_dir
                if archive_dir.exists() and not any(archive_dir.iterdir()):
                    archive_dir.rmdir()
        
        return results

    def get_manifest(self) -> Dict[str, dict]:
        """Return the current archive manifest."""
        return self.manifest.copy()

    def list_archived_modules(self) -> List[dict]:
        """Return a list of all archived modules with their metadata."""
        return list(self.manifest.values())

    def get_archive_timestamps(self) -> List[str]:
        """Return list of unique archive timestamps."""
        timestamps = set()
        for entry in self.manifest.values():
            if "timestamp_dir" in entry:
                timestamps.add(entry["timestamp_dir"])
        return sorted(timestamps)