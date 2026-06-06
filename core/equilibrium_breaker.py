"""
core/equilibrium_breaker.py

A lightweight module that scans capabilities for duplicates, identifies stuck capabilities,
generates a coordinated multi-module mutation plan, and returns the plan to the orchestrator.
"""

from typing import Dict, List, Tuple, Any, Optional
from collections import Counter
import random
import hashlib
import json

# Internal state for tracking capability occurrences
_capability_registry: Dict[str, List[Dict[str, Any]]] = {}
_mutation_counter = 0


def register_capability(capability_name: str, metadata: Optional[Dict[str, Any]] = None) -> None:
    """
    Register a capability occurrence in the internal registry.
    
    Args:
        capability_name: The name/identifier of the capability
        metadata: Optional dictionary with additional context (module, timestamp, etc.)
    """
    if metadata is None:
        metadata = {}
    if capability_name not in _capability_registry:
        _capability_registry[capability_name] = []
    _capability_registry[capability_name].append(metadata)


def scan_for_duplicates() -> Dict[str, List[Dict[str, Any]]]:
    """
    Scan all registered capabilities and return those that appear more than once.
    
    Returns:
        Dictionary mapping duplicate capability names to their metadata lists
    """
    return {
        name: occurrences
        for name, occurrences in _capability_registry.items()
        if len(occurrences) > 1
    }


def identify_stuck_capabilities(min_occurrences: int = 3) -> List[Tuple[str, int, List[Dict[str, Any]]]]:
    """
    Identify capabilities that appear at least min_occurrences times (stuck).
    
    Args:
        min_occurrences: Minimum number of occurrences to be considered stuck (default 3)
        
    Returns:
        List of tuples (capability_name, occurrence_count, metadata_list) for stuck capabilities,
        sorted by occurrence count descending, limited to top 5
    """
    stuck = [
        (name, len(occurrences), occurrences)
        for name, occurrences in _capability_registry.items()
        if len(occurrences) >= min_occurrences
    ]
    stuck.sort(key=lambda x: x[1], reverse=True)
    return stuck[:5]


def _generate_mutation_id() -> str:
    """Generate a unique mutation ID."""
    global _mutation_counter
    _mutation_counter += 1
    raw = f"mutation_{_mutation_counter}_{random.randint(0, 2**32)}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def _create_mutation_action(capability_name: str, occurrence_index: int, metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a single mutation action for a specific occurrence of a capability.
    
    Args:
        capability_name: The capability to mutate
        occurrence_index: Index of the occurrence in the registry
        metadata: Metadata of the occurrence
        
    Returns:
        Dictionary describing the mutation action
    """
    mutation_type = random.choice(["rename", "split", "merge", "refactor", "deprecate"])
    module = metadata.get("module", "unknown")
    
    action = {
        "mutation_id": _generate_mutation_id(),
        "capability": capability_name,
        "occurrence_index": occurrence_index,
        "module": module,
        "mutation_type": mutation_type,
        "description": f"{mutation_type.capitalize()} '{capability_name}' in module '{module}'"
    }
    
    if mutation_type == "rename":
        new_name = f"{capability_name}_variant_{occurrence_index}"
        action["new_name"] = new_name
        action["description"] = f"Rename '{capability_name}' to '{new_name}' in '{module}'"
    elif mutation_type == "split":
        action["parts"] = [f"{capability_name}_part_{i}" for i in range(2)]
        action["description"] = f"Split '{capability_name}' into {action['parts']} in '{module}'"
    elif mutation_type == "merge":
        action["merge_with"] = f"{capability_name}_sibling"
        action["description"] = f"Merge '{capability_name}' with '{action['merge_with']}' in '{module}'"
    elif mutation_type == "refactor":
        action["refactor_strategy"] = random.choice(["extract", "inline", "reorganize"])
        action["description"] = f"Refactor '{capability_name}' using {action['refactor_strategy']} in '{module}'"
    elif mutation_type == "deprecate":
        action["replacement"] = f"{capability_name}_new"
        action["description"] = f"Deprecate '{capability_name}' in favor of '{action['replacement']}' in '{module}'"
    
    return action


def generate_mutation_plan(stuck_capabilities: List[Tuple[str, int, List[Dict[str, Any]]]]) -> Dict[str, Any]:
    """
    Generate a coordinated multi-module mutation plan for the given stuck capabilities.
    
    Args:
        stuck_capabilities: List of tuples from identify_stuck_capabilities()
        
    Returns:
        Dictionary representing the mutation plan with metadata and actions
    """
    plan = {
        "plan_id": hashlib.sha256(str(random.getrandbits(256)).encode()).hexdigest()[:16],
        "timestamp": __import__("time").time(),
        "stuck_capabilities_count": len(stuck_capabilities),
        "total_occurrences": sum(count for _, count, _ in stuck_capabilities),
        "actions": [],
        "coordination": {}
    }
    
    for cap_name, count, occurrences in stuck_capabilities:
        # Create mutation actions for each occurrence
        for idx, metadata in enumerate(occurrences):
            action = _create_mutation_action(cap_name, idx, metadata)
            plan["actions"].append(action)
        
        # Add coordination info for this capability
        plan["coordination"][cap_name] = {
            "occurrence_count": count,
            "modules_affected": list(set(occ.get("module", "unknown") for occ in occurrences)),
            "action_count": len(occurrences)
        }
    
    # Add cross-capability coordination if multiple stuck capabilities
    if len(stuck_capabilities) > 1:
        plan["coordination"]["cross_capability"] = {
            "description": "Multiple stuck capabilities detected; consider batch processing",
            "capabilities_involved": [cap for cap, _, _ in stuck_capabilities],
            "suggested_order": "Process by descending occurrence count"
        }
    
    return plan


def break_equilibrium(min_occurrences: int = 3) -> Dict[str, Any]:
    """
    Main entry point: scan for duplicates, identify stuck capabilities, generate mutation plan.
    
    Args:
        min_occurrences: Minimum occurrences to consider a capability stuck (default 3)
        
    Returns:
        Dictionary with scan results and mutation plan, or error message if no stuck capabilities
    """
    duplicates = scan_for_duplicates()
    stuck = identify_stuck_capabilities(min_occurrences)
    
    if not stuck:
        return {
            "status": "no_stuck_capabilities",
            "message": "No capabilities found with sufficient repetitions to break equilibrium",
            "duplicates_found": len(duplicates),
            "plan": None
        }
    
    plan = generate_mutation_plan(stuck)
    
    return {
        "status": "plan_generated",
        "message": f"Generated mutation plan for {len(stuck)} stuck capabilities",
        "duplicates_found": len(duplicates),
        "stuck_capabilities": [
            {"name": name, "occurrences": count}
            for name, count, _ in stuck
        ],
        "plan": plan
    }


def reset_registry() -> None:
    """Reset the internal capability registry (useful for testing)."""
    global _capability_registry, _mutation_counter
    _capability_registry.clear()
    _mutation_counter = 0


# If run as script, demonstrate functionality
if __name__ == "__main__":
    # Example usage
    register_capability("data_validation", {"module": "core/validator.py"})
    register_capability("data_validation", {"module": "utils/checker.py"})
    register_capability("data_validation", {"module": "api/middleware.py"})
    register_capability("user_auth", {"module": "auth/login.py"})
    register_capability("user_auth", {"module": "auth/session.py"})
    register_capability("user_auth", {"module": "api/guard.py"})
    register_capability("user_auth", {"module": "admin/panel.py"})
    register_capability("log_formatter", {"module": "core/logger.py"})
    register_capability("log_formatter", {"module": "utils/logging.py"})
    
    result = break_equilibrium()
    print(json.dumps(result, indent=2, default=str))