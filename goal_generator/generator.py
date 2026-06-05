from goal_generator.converter import convert_to_canonical

CANONICAL_SCHEMA = {
    "type": "object",
    "properties": {
        "goal": {"type": "string"},
        "context": {"type": "string"},
        "constraints": {"type": "array", "items": {"type": "string"}},
        "priority": {"type": "string", "enum": ["low", "medium", "high"]},
        "deadline": {"type": "string", "format": "date-time"}
    },
    "required": ["goal", "context"]
}

def validate_input(data: dict) -> dict:
    """
    Validates that the incoming data matches the canonical schema.
    If validation fails, attempts to convert the data using the converter
    and returns the normalized result.

    Args:
        data (dict): The input data from reflection_parser.

    Returns:
        dict: The validated and normalized data conforming to the canonical schema.
    """
    if not isinstance(data, dict):
        raise ValueError("Input data must be a dictionary")

    # Check for required fields
    missing_fields = [field for field in CANONICAL_SCHEMA["required"] if field not in data]
    if missing_fields:
        # Attempt conversion if required fields are missing
        try:
            return convert_to_canonical(data)
        except Exception as e:
            raise ValueError(f"Input data missing required fields and conversion failed: {e}")

    # Validate field types and values
    for field, expected_type in CANONICAL_SCHEMA["properties"].items():
        if field in data:
            value = data[field]
            if expected_type.get("type") == "array":
                if not isinstance(value, list):
                    try:
                        return convert_to_canonical(data)
                    except Exception as e:
                        raise ValueError(f"Field '{field}' must be a list, got {type(value).__name__}: {e}")
                if expected_type.get("items", {}).get("type") == "string":
                    if not all(isinstance(item, str) for item in value):
                        try:
                            return convert_to_canonical(data)
                        except Exception as e:
                            raise ValueError(f"All items in '{field}' must be strings: {e}")
            elif expected_type.get("type") == "string":
                if not isinstance(value, str):
                    try:
                        return convert_to_canonical(data)
                    except Exception as e:
                        raise ValueError(f"Field '{field}' must be a string, got {type(value).__name__}: {e}")
                if "enum" in expected_type and value not in expected_type["enum"]:
                    try:
                        return convert_to_canonical(data)
                    except Exception as e:
                        raise ValueError(f"Field '{field}' must be one of {expected_type['enum']}, got '{value}': {e}")
            elif expected_type.get("type") == "object":
                if not isinstance(value, dict):
                    try:
                        return convert_to_canonical(data)
                    except Exception as e:
                        raise ValueError(f"Field '{field}' must be a dict, got {type(value).__name__}: {e}")

    # If all checks pass, return the original data
    return data