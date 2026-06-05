"""schema_alignment_layer.py

Core schema alignment module for the self-evolving agent system.
Provides canonical JSON schema definitions, validation, transformation,
adaptive learning from mismatches, and runtime orchestration of alignment
before every inter-module data transfer.
"""

import json
import jsonschema
from jsonschema import validate, ValidationError
from typing import Any, Dict, List, Optional, Tuple, Callable
from collections import defaultdict
import copy
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 1. Canonical JSON Schema Definitions
# ---------------------------------------------------------------------------

# Schema for the output of reflection_parser
REFLECTION_PARSER_OUTPUT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
        "reflection_id": {"type": "string"},
        "timestamp": {"type": "string", "format": "date-time"},
        "content": {"type": "string"},
        "metadata": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "tags": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["source", "confidence"]
        },
        "embedding": {
            "type": "array",
            "items": {"type": "number"},
            "minItems": 1
        }
    },
    "required": ["reflection_id", "timestamp", "content", "metadata"]
}

# Schema for input to goal_generator
GOAL_GENERATOR_INPUT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
        "context": {
            "type": "object",
            "properties": {
                "current_state": {"type": "string"},
                "recent_reflections": {
                    "type": "array",
                    "items": {"$ref": "#/definitions/reflection_summary"}
                },
                "environment": {"type": "object"}
            },
            "required": ["current_state"]
        },
        "constraints": {
            "type": "array",
            "items": {"type": "string"}
        },
        "preferences": {
            "type": "object",
            "properties": {
                "priority": {"type": "string", "enum": ["low", "medium", "high"]},
                "deadline": {"type": "string", "format": "date-time"}
            }
        }
    },
    "required": ["context"],
    "definitions": {
        "reflection_summary": {
            "type": "object",
            "properties": {
                "reflection_id": {"type": "string"},
                "summary": {"type": "string"},
                "confidence": {"type": "number"}
            },
            "required": ["reflection_id", "summary"]
        }
    }
}

# Schema for output of goal_generator
GOAL_GENERATOR_OUTPUT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
        "goal_id": {"type": "string"},
        "description": {"type": "string"},
        "priority": {"type": "string", "enum": ["low", "medium", "high"]},
        "deadline": {"type": "string", "format": "date-time"},
        "subgoals": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "subgoal_id": {"type": "string"},
                    "description": {"type": "string"},
                    "status": {"type": "string", "enum": ["pending", "in_progress", "completed"]}
                },
                "required": ["subgoal_id", "description", "status"]
            }
        },
        "dependencies": {
            "type": "array",
            "items": {"type": "string"}
        },
        "metadata": {
            "type": "object",
            "properties": {
                "created_at": {"type": "string", "format": "date-time"},
                "source_reflection": {"type": "string"}
            }
        }
    },
    "required": ["goal_id", "description", "priority"]
}

# Schema for input to mutation_engine
MUTATION_ENGINE_INPUT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
        "target": {
            "type": "object",
            "properties": {
                "component": {"type": "string"},
                "version": {"type": "string"},
                "current_state": {"type": "object"}
            },
            "required": ["component", "current_state"]
        },
        "mutation_type": {
            "type": "string",
            "enum": ["add", "modify", "remove", "restructure"]
        },
        "parameters": {
            "type": "object",
            "properties": {
                "field": {"type": "string"},
                "value": {},
                "constraints": {
                    "type": "array",
                    "items": {"type": "string"}
                }
            }
        },
        "context": {
            "type": "object",
            "properties": {
                "goal_id": {"type": "string"},
                "reasoning": {"type": "string"}
            }
        }
    },
    "required": ["target", "mutation_type"]
}

# Registry of all canonical schemas
CANONICAL_SCHEMAS = {
    "reflection_parser_output": REFLECTION_PARSER_OUTPUT_SCHEMA,
    "goal_generator_input": GOAL_GENERATOR_INPUT_SCHEMA,
    "goal_generator_output": GOAL_GENERATOR_OUTPUT_SCHEMA,
    "mutation_engine_input": MUTATION_ENGINE_INPUT_SCHEMA
}


# ---------------------------------------------------------------------------
# 2. SchemaValidator Class
# ---------------------------------------------------------------------------

class SchemaValidator:
    """Validates data against canonical schemas and reports mismatches."""

    def __init__(self, schemas: Optional[Dict[str, Dict]] = None):
        self.schemas = schemas or CANONICAL_SCHEMAS
        self.validation_history: List[Dict] = []

    def validate(self, data: Any, schema_name: str) -> Tuple[bool, Optional[Dict]]:
        """
        Validate data against a named schema.
        Returns (is_valid, error_detail).
        """
        if schema_name not in self.schemas:
            raise ValueError(f"Unknown schema: {schema_name}")

        schema = self.schemas[schema_name]
        try:
            validate(instance=data, schema=schema)
            self.validation_history.append({
                "schema_name": schema_name,
                "valid": True,
                "error": None
            })
            return True, None
        except ValidationError as e:
            error_detail = {
                "schema_name": schema_name,
                "message": e.message,
                "path": list(e.absolute_path),
                "schema_path": list(e.schema_path),
                "validator": e.validator,
                "validator_value": e.validator_value,
                "instance": e.instance
            }
            self.validation_history.append({
                "schema_name": schema_name,
                "valid": False,
                "error": error_detail
            })
            return False, error_detail

    def validate_with_report(self, data: Any, schema_name: str) -> Dict:
        """Validate and return a detailed report."""
        valid, error = self.validate(data, schema_name)
        report = {
            "valid": valid,
            "schema_name": schema_name,
            "error": error,
            "data_summary": self._summarize_data(data)
        }
        return report

    def _summarize_data(self, data: Any) -> Dict:
        """Create a summary of the data structure for reporting."""
        if isinstance(data, dict):
            return {
                "type": "dict",
                "keys": list(data.keys()),
                "length": len(data)
            }
        elif isinstance(data, list):
            return {
                "type": "list",
                "length": len(data),
                "sample_types": [type(item).__name__ for item in data[:3]]
            }
        else:
            return {
                "type": type(data).__name__,
                "value": str(data)[:100]
            }

    def get_mismatch_patterns(self) -> List[Dict]:
        """Analyze validation history to find common mismatch patterns."""
        patterns = defaultdict(int)
        for entry in self.validation_history:
            if not entry["valid"] and entry["error"]:
                key = (
                    entry["schema_name"],
                    entry["error"]["validator"],
                    str(entry["error"]["path"])
                )
                patterns[key] += 1
        return [
            {"schema_name": k[0], "validator": k[1], "path": k[2], "count": v}
            for k, v in sorted(patterns.items(), key=lambda x: -x[1])
        ]


# ---------------------------------------------------------------------------
# 3. SchemaTransformer Class
# ---------------------------------------------------------------------------

class SchemaTransformer:
    """Normalizes data between different formats and schemas."""

    def __init__(self):
        self.transformations: Dict[str, Dict[str, Callable]] = defaultdict(dict)
        self._register_default_transforms()

    def _register_default_transforms(self):
        """Register default transformation functions."""
        # Example: flatten nested structures
        self.register_transform(
            "flatten_metadata",
            lambda data: {
                **data,
                "metadata_flattened": json.dumps(data.get("metadata", {}))
            } if isinstance(data, dict) else data
        )

        # Example: ensure timestamp format
        self.register_transform(
            "ensure_timestamp",
            lambda data: {
                **data,
                "timestamp": data.get("timestamp", "").replace("T", " ")[:19]
            } if isinstance(data, dict) and "timestamp" in data else data
        )

    def register_transform(self, name: str, func: Callable):
        """Register a new transformation function."""
        self.transformations["custom"][name] = func

    def transform(self, data: Any, source_schema: str, target_schema: str,
                  transforms: Optional[List[str]] = None) -> Any:
        """
        Transform data from source schema format to target schema format.
        Applies registered transforms in order.
        """
        transformed = copy.deepcopy(data)

        # Apply schema-specific transformations
        if transforms:
            for transform_name in transforms:
                for category in self.transformations.values():
                    if transform_name in category:
                        transformed = category[transform_name](transformed)
                        break

        # Apply default schema mapping if available
        mapping_func = self._get_schema_mapping(source_schema, target_schema)
        if mapping_func:
            transformed = mapping_func(transformed)

        return transformed

    def _get_schema_mapping(self, source: str, target: str) -> Optional[Callable]:
        """Get a mapping function between two schemas if one exists."""
        # Define known mappings
        mappings = {
            ("reflection_parser_output", "goal_generator_input"): self._reflection_to_goal_input,
            ("goal_generator_output", "mutation_engine_input"): self._goal_to_mutation_input,
        }
        return mappings.get((source, target))

    def _reflection_to_goal_input(self, data: Dict) -> Dict:
        """Transform reflection parser output to goal generator input."""
        return {
            "context": {
                "current_state": data.get("content", ""),
                "recent_reflections": [{
                    "reflection_id": data.get("reflection_id", ""),
                    "summary": data.get("content", "")[:200],
                    "confidence": data.get("metadata", {}).get("confidence", 0.5)
                }],
                "environment": {}
            },
            "constraints": [],
            "preferences": {
                "priority": "medium"
            }
        }

    def _goal_to_mutation_input(self, data: Dict) -> Dict:
        """Transform goal generator output to mutation engine input."""
        return {
            "target": {
                "component": "goal_system",
                "version": "1.0",
                "current_state": {
                    "goal_id": data.get("goal_id", ""),
                    "description": data.get("description", ""),
                    "priority": data.get("priority", "medium"),
                    "subgoals": data.get("subgoals", [])
                }
            },
            "mutation_type": "modify",
            "parameters": {
                "field": "priority",
                "value": data.get("priority", "medium"),
                "constraints": []
            },
            "context": {
                "goal_id": data.get("goal_id", ""),
                "reasoning": f"Updating goal based on new priority: {data.get('priority', 'medium')}"
            }
        }


# ---------------------------------------------------------------------------
# 4. AutoAdapter Class
# ---------------------------------------------------------------------------

class AutoAdapter:
    """Learns from mismatch patterns and updates transformation rules."""

    def __init__(self, validator: SchemaValidator, transformer: SchemaTransformer):
        self.validator = validator
        self.transformer = transformer
        self.mismatch_history: List[Dict] = []
        self.adaptation_rules: Dict[str, List[Dict]] = defaultdict(list)
        self.learning_rate = 0.1

    def analyze_mismatch(self, data: Any, schema_name: str, error_detail: Dict):
        """Analyze a mismatch and potentially create an adaptation rule."""
        self.mismatch_history.append({
            "data": data,
            "schema_name": schema_name,
            "error": error_detail,
            "timestamp": __import__('datetime').datetime.now().isoformat()
        })

        # Extract pattern
        pattern = self._extract_pattern(data, error_detail)
        if pattern:
            rule = self._create_adaptation_rule(pattern, schema_name)
            if rule:
                self.adaptation_rules[schema_name].append(rule)
                logger.info(f"Created adaptation rule for {schema_name}: {rule}")

    def _extract_pattern(self, data: Any, error: Dict) -> Optional[Dict]:
        """Extract a pattern from the mismatch data."""
        path = error.get("path", [])
        if not path:
            return None

        # Navigate to the problematic field
        current = data
        for key in path:
            if isinstance(current, dict):
                current = current.get(key)
            elif isinstance(current, list) and isinstance(key, int):
                current = current[key] if key < len(current) else None
            else:
                return None

        return {
            "path": path,
            "expected_type": error.get("validator_value"),
            "actual_value": current,
            "actual_type": type(current).__name__,
            "validator": error.get("validator")
        }

    def _create_adaptation_rule(self, pattern: Dict, schema_name: str) -> Optional[Dict]:
        """Create an adaptation rule based on the pattern."""
        rule = {
            "schema_name": schema_name,
            "path": pattern["path"],
            "condition": {
                "validator": pattern["validator"],
                "expected": pattern["expected_type"]
            },
            "action": self._determine_action(pattern),
            "confidence": self.learning_rate,
            "created_at": __import__('datetime').datetime.now().isoformat()
        }
        return rule

    def _determine_action(self, pattern: Dict) -> Dict:
        """Determine the appropriate action to fix the mismatch."""
        action = {"type": "transform", "function": None}

        if pattern["validator"] == "type":
            # Type mismatch - add type coercion
            action["function"] = f"coerce_to_{pattern['expected_type']}"
        elif pattern["validator"] == "required":
            # Missing required field - add default value
            action["type"] = "default"
            action["value"] = None  # Could be inferred
        elif pattern["validator"] == "enum":
            # Invalid enum value - map to closest valid value
            action["type"] = "map"
            action["mapping"] = {str(pattern["actual_value"]): pattern["expected_type"][0]
                                 if isinstance(pattern["expected_type"], list) else "unknown"}

        return action

    def apply_adaptations(self, data: Any, schema_name: str) -> Any:
        """Apply learned adaptation rules to data before validation."""
        adapted = copy.deepcopy(data)
        rules = self.adaptation_rules.get(schema_name, [])

        for rule in rules:
            if rule["confidence"] > 0.5:  # Only apply high-confidence rules
                adapted = self._apply_rule(adapted, rule)

        return adapted

    def _apply_rule(self, data: Any, rule: Dict) -> Any:
        """Apply a single adaptation rule to the data."""
        path = rule["path"]
        action = rule["action"]

        # Navigate to the parent of the target field
        current = data
        for key in path[:-1]:
            if isinstance(current, dict):
                current = current.get(key, {})
            else:
                return data

        target_key = path[-1] if path else None
        if target_key and isinstance(current, dict):
            if action["type"] == "default" and target_key not in current:
                current[target_key] = action.get("value")
            elif action["type"] == "map" and target_key in current:
                str_val = str(current[target_key])
                if str_val in action.get("mapping", {}):
                    current[target_key] = action["mapping"][str_val]

        return data

    def get_adaptation_stats(self) -> Dict:
        """Get statistics about adaptations."""
        return {
            "total_mismatches": len(self.mismatch_history),
            "total_rules": sum(len(rules) for rules in self.adaptation_rules.values()),
            "rules_by_schema": {
                schema: len(rules)
                for schema, rules in self.adaptation_rules.items()
            },
            "recent_mismatches": self.mismatch_history[-10:] if self.mismatch_history else []
        }


# ---------------------------------------------------------------------------
# 5. RuntimeAlignmentEngine Class
# ---------------------------------------------------------------------------

class RuntimeAlignmentEngine:
    """Orchestrates validation before each data transfer between modules."""

    def __init__(self):
        self.validator = SchemaValidator()
        self.transformer = SchemaTransformer()
        self.ad