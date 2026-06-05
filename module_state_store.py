import json
import os
import threading
import fcntl

class ModuleStateStore:
    def __init__(self, filepath="module_states.json"):
        self.filepath = filepath
        self.lock = threading.Lock()
        self._ensure_file_exists()
        self.schema_mismatches = {}

    def _ensure_file_exists(self):
        if not os.path.exists(self.filepath):
            with open(self.filepath, 'w') as f:
                json.dump({}, f)

    def _read_states(self):
        with open(self.filepath, 'r') as f:
            fcntl.flock(f, fcntl.LOCK_SH)
            try:
                return json.load(f)
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)

    def _write_states(self, states):
        with open(self.filepath, 'w') as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                json.dump(states, f, indent=2)
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)

    def get_state(self, module):
        with self.lock:
            states = self._read_states()
            return states.get(module, 'pending')

    def set_state(self, module, state):
        valid_states = {'pending', 'verified_consistent', 'needs_verification', 'mutation_in_progress', 'failed', 'consistency_check_failed', 'schema_validating', 'schema_transforming', 'schema_adapting'}
        if state not in valid_states:
            raise ValueError(f"Invalid state: {state}. Must be one of {valid_states}")
        with self.lock:
            states = self._read_states()
            states[module] = state
            self._write_states(states)

    def get_modules_in_state(self, state):
        with self.lock:
            states = self._read_states()
            return [module for module, s in states.items() if s == state]

    def get_consistency_failures(self):
        return self.get_modules_in_state('consistency_check_failed')

    def reset_all(self):
        with self.lock:
            self._write_states({})

    def record_schema_mismatch(self, module_name, mismatch_details):
        with self.lock:
            if module_name not in self.schema_mismatches:
                self.schema_mismatches[module_name] = []
            self.schema_mismatches[module_name].append(mismatch_details)

    def get_schema_alignment_stats(self):
        with self.lock:
            states = self._read_states()
            total = len(states)
            if total == 0:
                return {"total_modules": 0, "aligned": 0, "misaligned": 0, "alignment_rate": 0.0}
            
            aligned = 0
            misaligned = 0
            for module, state in states.items():
                if state in ('verified_consistent', 'schema_validating', 'schema_transforming', 'schema_adapting'):
                    aligned += 1
                elif state in ('failed', 'consistency_check_failed'):
                    misaligned += 1
            
            alignment_rate = aligned / total if total > 0 else 0.0
            return {
                "total_modules": total,
                "aligned": aligned,
                "misaligned": misaligned,
                "alignment_rate": alignment_rate
            }