import json
import os
import threading
import fcntl

class ModuleStateStore:
    def __init__(self, filepath="module_states.json"):
        self.filepath = filepath
        self.lock = threading.Lock()
        self._ensure_file_exists()

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
        valid_states = {'pending', 'verified_consistent', 'needs_verification', 'mutation_in_progress', 'failed', 'consistency_check_failed'}
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