import os
import re
import shutil
from collections import defaultdict
from typing import List, Dict, Tuple
from datetime import datetime
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Configuration constants
DEDUP_THRESHOLD_NEW = 0.85
PRUNE_THRESHOLD = 0.9
PRUNE_INTERVAL_CYCLES = 10

class CapabilityDeduplicator:
    """
    Module for deduplicating capabilities by TF-IDF similarity,
    archiving duplicates, and tracking consecutive failures.
    """

    def __init__(self, capabilities_dir: str = "capabilities",
                 archive_dir: str = "archived_capabilities",
                 log_file: str = "logs/evolution.log"):
        self.capabilities_dir = capabilities_dir
        self.archive_dir = archive_dir
        self.log_file = log_file
        self.dedup_log_file = "logs/dedup_log.txt"
        os.makedirs(self.archive_dir, exist_ok=True)
        os.makedirs("logs", exist_ok=True)
        self.vectorizer = TfidfVectorizer(max_features=100, stop_words='english')
        self.prune_cycle_counter = 0

    def _log_dedup_action(self, message: str) -> None:
        """Log a deduplication action to the dedup log file."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            with open(self.dedup_log_file, 'a', encoding='utf-8') as f:
                f.write(f"[{timestamp}] {message}\n")
        except Exception:
            pass

    def compute_embedding(self, text: str):
        """
        Compute TF-IDF embedding for a given text.
        """
        return self.vectorizer.fit_transform([text])

    def is_duplicate(self, new_text: str, existing_texts: List[str], threshold: float = DEDUP_THRESHOLD_NEW) -> bool:
        """
        Check if new_text is a duplicate of any existing_texts using cosine similarity.
        Returns True if any similarity > threshold.
        """
        if not existing_texts:
            return False
        all_texts = existing_texts + [new_text]
        tfidf_matrix = self.vectorizer.fit_transform(all_texts)
        similarity_matrix = cosine_similarity(tfidf_matrix)
        # Compare new_text (last row) with all existing texts (first n rows)
        new_similarities = similarity_matrix[-1, :-1]
        
        for i, sim in enumerate(new_similarities):
            if sim > threshold:
                # Log rejection with details
                rejected_snippet = new_text[:50].replace('\n', ' ')
                matched_snippet = existing_texts[i][:50].replace('\n', ' ')
                self._log_dedup_action(
                    f"REJECTION: rejected='{rejected_snippet}' matched='{matched_snippet}' similarity={sim:.4f}"
                )
                return True
        return False

    def prune_existing(self, threshold: float = PRUNE_THRESHOLD) -> List[str]:
        """
        Cluster capabilities by similarity and keep only the first from each cluster.
        Returns list of filenames that were archived.
        """
        capabilities = self._read_capabilities()
        if not capabilities:
            return []

        filenames = list(capabilities.keys())
        descriptions = list(capabilities.values())
        
        if len(filenames) < 2:
            return []

        tfidf_matrix = self.vectorizer.fit_transform(descriptions)
        similarity_matrix = cosine_similarity(tfidf_matrix)
        
        archived = []
        kept_indices = set()
        
        for i in range(len(filenames)):
            if i in kept_indices:
                continue
            kept_indices.add(i)
            cluster_size = 1
            for j in range(i + 1, len(filenames)):
                if j in kept_indices:
                    continue
                if similarity_matrix[i][j] > threshold:
                    kept_indices.add(j)
                    self._archive_capability(filenames[j], descriptions[j])
                    archived.append(f"Archived '{filenames[j]}' (similar to '{filenames[i]}')")
                    cluster_size += 1
            
            # Log pruning action with cluster size and kept capability
            if cluster_size > 1:
                self._log_dedup_action(
                    f"PRUNE: cluster_size={cluster_size} kept='{filenames[i]}'"
                )
        
        return archived

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
        Main method: identify duplicates using TF-IDF similarity, keep first occurrence, archive rest.
        Also archive capabilities with >3 consecutive failures.
        Returns a list of actions taken.
        """
        actions: List[str] = []
        capabilities = self._read_capabilities()
        if not capabilities:
            return actions

        # Group by hash (keep simple hash for initial grouping)
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
                    # Log rejection for hash-based duplicates
                    rejected_snippet = desc[:50].replace('\n', ' ')
                    matched_snippet = first_desc[:50].replace('\n', ' ')
                    self._log_dedup_action(
                        f"REJECTION: rejected='{rejected_snippet}' matched='{matched_snippet}' similarity=1.0000"
                    )

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

        # Increment cycle counter and run pruning if interval reached
        self.prune_cycle_counter += 1
        if self.prune_cycle_counter >= PRUNE_INTERVAL_CYCLES:
            self.prune_cycle_counter = 0
            pruned = self.prune_existing(threshold=PRUNE_THRESHOLD)
            actions.extend(pruned)

        return actions

    def run(self) -> List[str]:
        """
        Convenience method to execute deduplication and archiving.
        """
        return self.deduplicate_and_archive()

    def run_deduplication(self, capabilities_list: List[str], current_cycle: int) -> List[str]:
        """
        Main deduplication function that:
        1) If current_cycle % PRUNE_INTERVAL_CYCLES == 0, run prune_existing(PRUNE_THRESHOLD) on the list.
        2) Return filtered list with duplicates removed.
        3) Log all actions.
        Handles empty lists gracefully.
        """
        if not capabilities_list:
            self._log_dedup_action("run_deduplication: empty capabilities list received")
            return []

        # Log the start of deduplication
        self._log_dedup_action(f"run_deduplication: starting with {len(capabilities_list)} capabilities, cycle {current_cycle}")

        # Check if pruning should occur
        if current_cycle % PRUNE_INTERVAL_CYCLES == 0:
            self._log_dedup_action(f"run_deduplication: pruning interval reached at cycle {current_cycle}")
            pruned = self.prune_existing(threshold=PRUNE_THRESHOLD)
            if pruned:
                self._log_dedup_action(f"run_deduplication: pruned {len(pruned)} capabilities: {', '.join(pruned)}")
            else:
                self._log_dedup_action("run_deduplication: no capabilities pruned")

        # Remove duplicates from the list
        filtered_list = []
        seen_descriptions = set()
        duplicates_removed = 0

        for cap in capabilities_list:
            # Use the simple hash for quick duplicate detection
            cap_hash = self._simple_hash(cap)
            if cap_hash not in seen_descriptions:
                seen_descriptions.add(cap_hash)
                filtered_list.append(cap)
            else:
                duplicates_removed += 1
                self._log_dedup_action(f"run_deduplication: removed duplicate capability: {cap[:50]}...")

        # Log the results
        self._log_dedup_action(f"run_deduplication: completed - {len(filtered_list)} capabilities kept, {duplicates_removed} duplicates removed")

        return filtered_list