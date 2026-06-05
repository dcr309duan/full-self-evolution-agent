import os
import shutil
import json
import logging
from datetime import datetime
from typing import List, Optional

# Configure logging for pruning actions
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Paths
BACKUP_DIR = "logs/pruning_backups"
CAPABILITY_REGISTRY_PATH = "capability_registry.json"
ACTIVE_CODEBASE_DIR = "modules"

def ensure_backup_dir():
    """Ensure the backup directory exists."""
    os.makedirs(BACKUP_DIR, exist_ok=True)

def backup_module(module_name: str) -> Optional[str]:
    """
    Backup a module to the backup directory.
    Returns the backup path if successful, None otherwise.
    """
    module_path = os.path.join(ACTIVE_CODEBASE_DIR, module_name)
    if not os.path.exists(module_path):
        logger.warning(f"Module {module_name} does not exist at {module_path}. Skipping backup.")
        return None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BACKUP_DIR, f"{module_name}_{timestamp}")
    try:
        if os.path.isfile(module_path):
            shutil.copy2(module_path, backup_path)
        elif os.path.isdir(module_path):
            shutil.copytree(module_path, backup_path)
        logger.info(f"Backed up {module_name} to {backup_path}")
        return backup_path
    except Exception as e:
        logger.error(f"Failed to backup {module_name}: {e}")
        return None

def remove_module(module_name: str) -> bool:
    """
    Remove a module from the active codebase.
    Returns True if successful, False otherwise.
    """
    module_path = os.path.join(ACTIVE_CODEBASE_DIR, module_name)
    if not os.path.exists(module_path):
        logger.warning(f"Module {module_name} does not exist at {module_path}. Skipping removal.")
        return False

    try:
        if os.path.isfile(module_path):
            os.remove(module_path)
        elif os.path.isdir(module_path):
            shutil.rmtree(module_path)
        logger.info(f"Removed {module_name} from active codebase.")
        return True
    except Exception as e:
        logger.error(f"Failed to remove {module_name}: {e}")
        return False

def update_capability_registry(module_name: str, action: str = "pruned"):
    """
    Update the capability registry to mark a module as pruned.
    If the registry file does not exist, it creates a new one.
    """
    registry = {}
    if os.path.exists(CAPABILITY_REGISTRY_PATH):
        try:
            with open(CAPABILITY_REGISTRY_PATH, 'r') as f:
                registry = json.load(f)
        except json.JSONDecodeError:
            logger.error(f"Capability registry at {CAPABILITY_REGISTRY_PATH} is corrupted. Reinitializing.")
            registry = {}

    registry[module_name] = {
        "status": action,
        "pruned_at": datetime.now().isoformat(),
        "reason": "Low impact evaluation"
    }

    try:
        with open(CAPABILITY_REGISTRY_PATH, 'w') as f:
            json.dump(registry, f, indent=4)
        logger.info(f"Updated capability registry for {module_name} with status '{action}'.")
    except Exception as e:
        logger.error(f"Failed to update capability registry: {e}")

def log_pruning_action(module_name: str, backup_path: Optional[str], reason: str = "Low impact", impact_analysis: str = ""):
    """
    Log the pruning action with reason and impact analysis.
    """
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "module": module_name,
        "action": "pruned",
        "backup_path": backup_path,
        "reason": reason,
        "impact_analysis": impact_analysis
    }
    logger.info(f"Pruning action logged: {json.dumps(log_entry, indent=2)}")
    # Optionally append to a dedicated pruning log file
    log_file = os.path.join(BACKUP_DIR, "pruning_log.json")
    try:
        if os.path.exists(log_file):
            with open(log_file, 'r') as f:
                logs = json.load(f)
        else:
            logs = []
        logs.append(log_entry)
        with open(log_file, 'w') as f:
            json.dump(logs, f, indent=4)
    except Exception as e:
        logger.error(f"Failed to write pruning log: {e}")

def prune_modules(module_names: List[str], reason: str = "Low impact", impact_analysis: str = ""):
    """
    Main pruning routine: takes a list of low-impact module names,
    backs them up, removes them, updates registry, and logs the action.
    """
    ensure_backup_dir()
    for module_name in module_names:
        logger.info(f"Processing pruning for module: {module_name}")
        backup_path = backup_module(module_name)
        if backup_path is None:
            # Even if backup fails, we may still want to attempt removal and logging
            logger.warning(f"Backup failed for {module_name}. Proceeding with removal anyway.")
        removed = remove_module(module_name)
        if removed:
            update_capability_registry(module_name, action="pruned")
        else:
            # If removal failed, still log the attempt but mark as failed
            update_capability_registry(module_name, action="prune_failed")
        log_pruning_action(module_name, backup_path, reason, impact_analysis)

# Example usage (if run as standalone)
if __name__ == "__main__":
    # Example list of low-impact modules from evaluator
    low_impact_modules = ["module_a", "module_b", "module_c"]
    prune_modules(low_impact_modules, reason="Low usage and performance impact", impact_analysis="Removal reduces codebase size by 15% and improves load time.")