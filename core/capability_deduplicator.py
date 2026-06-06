import os
import re
import shutil
from collections import defaultdict
from typing import List, Dict, Tuple

class CapabilityDeduplicator:
    """
    Module for deduplicating capabilities by hashing descriptions,
    archiving duplicates, and tracking consecutive failures.
    """

    def __init__(self, capabilities_dir: str = "capabilities",
                 archive_dir: str = "archived_capabilities",
                 log_file: str = "logs/evolution.log"):
        self.capabilities_dir = capabilities_dir
        self.archive_dir = archive_dir
        self.log_file = log_file
        os.makedirs(self.archive_dir, exist_ok=True)

    def _simple_hash(self, description: str) -> str:
        """
        Create a simple hash from the first 80 characters and the length.
        """
        prefix = description[:80].strip()
        length = len(description)
        return f"{prefix}::{length}"

    def _read_capabilities(self) -> Dict[str, str]:
        """
        Read all capability files from the capabilities directory.
        Returns a dict mapping filename to description.
        """
        capabilities = {}
        if not os.path.isdir(self.capabilities_dir):
            return capabilities
        for fname in os.listdir(self.capabilities_dir):
            fpath = os.path.join(self.capabilities_dir, fname)
            if os.path.isfile(fpath):
                try:
                    with open(fpath, 'r', encoding='utf-8') as f:
                        description = f.read()
                    capabilities[fname] = description
                except Exception:
                    continue
        return capabilities

    def _read_failure_counts(self) -> Dict[str, int]:
        """
        Parse logs/evolution.log to count consecutive failures per capability.
        Returns a dict mapping capability filename to consecutive failure count.
        """
        failure_counts: Dict[str, int] = {}
        if not os.path.isfile(self.log_file):
            return failure_counts

        # Pattern to match lines like: "Capability X failed" or "Capability X succeeded"
        fail_pattern = re.compile(r'Capability\s+(\S+)\s+failed', re.IGNORECASE)
        success_pattern = re.compile(r'Capability\s+(\S+)\s+succeeded', re.IGNORECASE)

        try:
            with open(self.log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    fail_match = fail_pattern.search(line)
                    success_match = success_pattern.search(line)
                    if fail_match:
                        cap_name = fail_match.group(1)
                        # Increment consecutive failure count
                        failure_counts[cap_name] = failure_counts.get(cap_name, 0) + 1
                    elif success_match:
                        cap_name = success_match.group(1)
                        # Reset consecutive failure count on success
                        failure_counts[cap_name] = 0
        except Exception:
            pass

        return failure_counts

    def _archive_capability(self, filename: str, description: str) -> None:
        """
        Move a capability file to the archive directory.
        """
        src = os.path.join(self.capabilities_dir, filename)
        dst = os.path.join(self.archive_dir, filename)
        try:
            shutil.move(src, dst)
        except Exception:
            # If move fails, try copy and delete
            try:
                shutil.copy2(src, dst)
                os.remove(src)
            except Exception:
                pass

    def deduplicate_and_archive(self) -> List[str]:
        """
        Main method: identify duplicates, keep first occurrence, archive rest.
        Also archive capabilities with >3 consecutive failures.
        Returns a list of actions taken.
        """
        actions: List[str] = []
        capabilities = self._read_capabilities()
        if not capabilities:
            return actions

        # Group by hash
        hash_groups: Dict[str, List[Tuple[str, str]]] = defaultdict(list)
        for fname, desc in capabilities.items():
            h = self._simple_hash(desc)
            hash_groups[h].append((fname, desc))

        # Process duplicates: keep first, archive rest
        for h, group in hash_groups.items():
            if len(group) > 1:
                # Keep the first occurrence
                first_fname, first_desc = group[0]
                for fname, desc in group[1:]:
                    self._archive_capability(fname, desc)
                    actions.append(f"Archived duplicate '{fname}' (kept '{first_fname}')")

        # Read failure counts after potential archiving (to avoid archiving already archived)
        failure_counts = self._read_failure_counts()

        # Archive capabilities with >3 consecutive failures
        for fname, count in failure_counts.items():
            if count > 3:
                fpath = os.path.join(self.capabilities_dir, fname)
                if os.path.isfile(fpath):
                    # Read description to archive
                    try:
                        with open(fpath, 'r', encoding='utf-8') as f:
                            desc = f.read()
                        self._archive_capability(fname, desc)
                        actions.append(f"Archived '{fname}' due to {count} consecutive failures")
                    except Exception:
                        continue

        return actions

    def run(self) -> List[str]:
        """
        Convenience method to execute deduplication and archiving.
        """
        return self.deduplicate_and_archive()