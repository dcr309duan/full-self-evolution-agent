import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Default path for the rules file; can be overridden
DEFAULT_RULES_PATH = "forbidden_mutation_rules.json"


def load_rules(rules_path: str = DEFAULT_RULES_PATH) -> Dict[str, List[Dict[str, Any]]]:
    """
    Load mutation validation rules from a JSON file.

    Expected structure:
    {
        "rules": [
            {
                "pattern": "some_pattern",
                "action": "block" | "warn" | "require_precheck",
                "message": "Optional explanation"
            },
            ...
        ]
    }
    """
    try:
        with open(rules_path, "r") as f:
            data = json.load(f)
        rules = data.get("rules", [])
        if not isinstance(rules, list):
            raise ValueError("'rules' must be a list")
        return {"rules": rules}
    except FileNotFoundError:
        logger.warning(f"Rules file not found at {rules_path}. No rules enforced.")
        return {"rules": []}
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in rules file: {e}")
        return {"rules": []}


def match_mutation(mutation: Dict[str, Any], pattern: str) -> bool:
    """
    Check if a mutation matches a given pattern.
    This is a simple placeholder implementation. Extend with regex or custom logic as needed.
    """
    # Example: match on mutation type or target field
    mutation_type = mutation.get("type", "")
    target = mutation.get("target", "")
    return pattern in mutation_type or pattern in target


def pre_mutation_validator(
    mutation: Dict[str, Any],
    rules_path: str = DEFAULT_RULES_PATH,
) -> Optional[str]:
    """
    Validate a proposed mutation against forbidden mutation rules.

    Args:
        mutation: Dictionary describing the mutation (e.g., {"type": "delete", "target": "field_x"})
        rules_path: Path to the JSON rules file.

    Returns:
        None if mutation is allowed (no block rule matched),
        or a string explanation if the mutation is blocked.
        Logs warnings and triggers precheck actions as needed.
    """
    rules_data = load_rules(rules_path)
    rules = rules_data["rules"]

    for rule in rules:
        pattern = rule.get("pattern", "")
        action = rule.get("action", "warn")
        message = rule.get("message", f"Matched rule with pattern '{pattern}'")

        if not match_mutation(mutation, pattern):
            continue

        if action == "block":
            logger.error(f"Mutation blocked: {message}")
            return message  # Reject immediately

        elif action == "warn":
            logger.warning(f"Mutation warning: {message}")

        elif action == "require_precheck":
            logger.info(f"Triggering precheck for mutation: {message}")
            # Placeholder: call a precheck function here
            # precheck_result = run_precheck(mutation)
            # if not precheck_result:
            #     return f"Precheck failed: {message}"
            # For now, just log and allow
            logger.info("Precheck passed (placeholder).")

    return None  # Mutation allowed