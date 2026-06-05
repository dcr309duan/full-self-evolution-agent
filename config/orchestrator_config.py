"""
Minimal configuration module for the orchestrator.
Uses only standard library (json) for serialization.
"""

import json

# Default configuration values
DEFAULT_CONFIG = {
    "equilibrium_window_size": 20,
    "improvement_threshold": 0.05,
    "max_multi_module_attempts": 3
}

def load_config(filepath="orchestrator_config.json"):
    """Load configuration from a JSON file, falling back to defaults."""
    try:
        with open(filepath, 'r') as f:
            config = json.load(f)
        # Merge with defaults to ensure all keys exist
        merged = DEFAULT_CONFIG.copy()
        merged.update(config)
        return merged
    except (FileNotFoundError, json.JSONDecodeError):
        return DEFAULT_CONFIG.copy()

def save_config(config, filepath="orchestrator_config.json"):
    """Save configuration to a JSON file."""
    with open(filepath, 'w') as f:
        json.dump(config, f, indent=2)

def get_config():
    """Return the default configuration dictionary."""
    return DEFAULT_CONFIG.copy()