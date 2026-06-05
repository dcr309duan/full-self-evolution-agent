from typing import Any, Dict, Optional
import json
import logging

from agent_core.schema_alignment import validate_and_normalize

logger = logging.getLogger(__name__)


def parse_reflection(raw_reflection: Any) -> Optional[Dict[str, Any]]:
    """
    Parse a raw reflection input and return a normalized JSON dict conforming
    to the canonical reflection schema.

    Args:
        raw_reflection: The raw reflection data, which may be a dict, JSON string,
                        or other type.

    Returns:
        A normalized reflection dict if parsing and validation succeed, otherwise None.
    """
    if raw_reflection is None:
        logger.warning("Received None as raw reflection input.")
        return None

    # Attempt to parse if it's a JSON string
    if isinstance(raw_reflection, str):
        try:
            raw_reflection = json.loads(raw_reflection)
        except (json.JSONDecodeError, ValueError) as e:
            logger.error("Failed to parse reflection JSON string: %s", e)
            return None

    if not isinstance(raw_reflection, dict):
        logger.error(
            "Expected a dict or JSON string for reflection, got %s",
            type(raw_reflection).__name__,
        )
        return None

    # Use schema_alignment to validate and normalize
    try:
        normalized = validate_and_normalize(raw_reflection, schema_type="reflection")
    except Exception as e:
        logger.error("Schema validation/normalization failed: %s", e)
        return None

    if normalized is None:
        logger.warning("Schema alignment returned None for reflection data.")
        return None

    return normalized


def build_reflection_payload(
    reflection_text: str,
    confidence: float = 1.0,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Build a reflection payload dict and normalize it via schema_alignment.

    Args:
        reflection_text: The textual content of the reflection.
        confidence: A confidence score (0.0 to 1.0).
        metadata: Optional additional metadata.

    Returns:
        A normalized reflection dict.
    """
    raw = {
        "reflection_text": reflection_text,
        "confidence": confidence,
        "metadata": metadata or {},
    }
    normalized = parse_reflection(raw)
    if normalized is None:
        # Fallback: return a minimal valid reflection if normalization fails
        logger.error("Failed to normalize reflection payload; returning minimal fallback.")
        return {
            "reflection_text": reflection_text,
            "confidence": confidence,
            "metadata": metadata or {},
        }
    return normalized


def parse_reflection_batch(raw_reflections: list) -> list:
    """
    Parse a batch of raw reflection inputs and return a list of normalized dicts.

    Args:
        raw_reflections: A list of raw reflection inputs (dicts, JSON strings, etc.).

    Returns:
        A list of normalized reflection dicts; invalid entries are omitted.
    """
    normalized_list = []
    for i, raw in enumerate(raw_reflections):
        normalized = parse_reflection(raw)
        if normalized is not None:
            normalized_list.append(normalized)
        else:
            logger.warning("Skipping invalid reflection at index %d", i)
    return normalized_list