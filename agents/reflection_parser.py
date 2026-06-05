from typing import Any, Dict, List, Optional
import re
import json


class ReflectionParser:
    """
    Parses reflection cycle output to extract structured feasibility assessment data.
    For each capability mentioned, the parser extracts:
        - dependency_coverage: list of dependencies that are covered
        - schema_alignment_status: whether the capability aligns with the schema
        - prerequisite_met: whether prerequisites for the capability are satisfied
    """

    def __init__(self):
        self._capability_pattern = re.compile(
            r'capability\s*[:\-]?\s*(?P<name>[A-Za-z0-9_]+)',
            re.IGNORECASE
        )
        self._dependency_pattern = re.compile(
            r'dependency\s*[:\-]?\s*(?P<dep>[A-Za-z0-9_]+)',
            re.IGNORECASE
        )
        self._schema_pattern = re.compile(
            r'schema\s*(aligned|misaligned|unknown)',
            re.IGNORECASE
        )
        self._prerequisite_pattern = re.compile(
            r'prerequisite\s*(met|unmet|unknown)',
            re.IGNORECASE
        )

    def parse(self, reflection_text: str) -> List[Dict[str, Any]]:
        """
        Parse reflection text and return a list of capability assessments.

        Args:
            reflection_text: The raw text output from a reflection cycle.

        Returns:
            List of dicts, each containing:
                - capability_name: str
                - dependency_coverage: List[str]
                - schema_alignment_status: str (aligned/misaligned/unknown)
                - prerequisite_met: str (met/unmet/unknown)
        """
        if not reflection_text:
            return []

        capabilities = self._extract_capabilities(reflection_text)
        assessments = []

        for cap_name, cap_block in capabilities:
            assessment = {
                "capability_name": cap_name,
                "dependency_coverage": self._extract_dependencies(cap_block),
                "schema_alignment_status": self._extract_schema_status(cap_block),
                "prerequisite_met": self._extract_prerequisite_status(cap_block),
            }
            assessments.append(assessment)

        return assessments

    def _extract_capabilities(self, text: str) -> List[tuple]:
        """
        Split reflection text into blocks per capability and return (name, block) pairs.
        """
        # Find all capability mentions and their surrounding context
        matches = list(self._capability_pattern.finditer(text))
        if not matches:
            return []

        capabilities = []
        for i, match in enumerate(matches):
            cap_name = match.group("name")
            start = match.start()
            # Determine end of this capability's block
            if i + 1 < len(matches):
                end = matches[i + 1].start()
            else:
                end = len(text)
            block = text[start:end].strip()
            capabilities.append((cap_name, block))

        return capabilities

    def _extract_dependencies(self, block: str) -> List[str]:
        """
        Extract dependency names from a capability block.
        """
        deps = self._dependency_pattern.findall(block)
        return list(set(deps))  # deduplicate

    def _extract_schema_status(self, block: str) -> str:
        """
        Extract schema alignment status from a capability block.
        Returns 'aligned', 'misaligned', or 'unknown'.
        """
        match = self._schema_pattern.search(block)
        if match:
            return match.group(1).lower()
        return "unknown"

    def _extract_prerequisite_status(self, block: str) -> str:
        """
        Extract prerequisite status from a capability block.
        Returns 'met', 'unmet', or 'unknown'.
        """
        match = self._prerequisite_pattern.search(block)
        if match:
            return match.group(1).lower()
        return "unknown"

    def parse_json(self, reflection_json: str) -> List[Dict[str, Any]]:
        """
        Parse reflection output that is in JSON format.

        Expected JSON structure (list or single object):
            {
                "capability_name": "...",
                "dependency_coverage": [...],
                "schema_alignment_status": "...",
                "prerequisite_met": "..."
            }
        """
        try:
            data = json.loads(reflection_json)
        except json.JSONDecodeError:
            # Fall back to text parsing
            return self.parse(reflection_json)

        if isinstance(data, dict):
            data = [data]

        assessments = []
        for item in data:
            assessment = {
                "capability_name": item.get("capability_name", "unknown"),
                "dependency_coverage": item.get("dependency_coverage", []),
                "schema_alignment_status": item.get("schema_alignment_status", "unknown"),
                "prerequisite_met": item.get("prerequisite_met", "unknown"),
            }
            assessments.append(assessment)

        return assessments

    def to_feasibility_input(self, assessments: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Convert parsed assessments into a format suitable for the feasibility estimator.
        """
        return {
            "capabilities": assessments,
            "total_capabilities": len(assessments),
            "aligned_count": sum(
                1 for a in assessments if a["schema_alignment_status"] == "aligned"
            ),
            "prerequisites_met_count": sum(
                1 for a in assessments if a["prerequisite_met"] == "met"
            ),
            "dependency_coverage_summary": {
                a["capability_name"]: a["dependency_coverage"]
                for a in assessments
            },
        }


def validate_reflection_output(output_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate the structure and types of a reflection output dictionary.

    Checks:
    (1) 'current_assessment' is a non-empty string
    (2) 'key_gaps' is a list of strings
    (3) 'next_priority' is a non-empty string
    (4) 'timestamp' is a valid float
    (5) 'cycle' is a positive integer

    Args:
        output_dict: The reflection output dictionary to validate.

    Returns:
        Dict with 'valid': bool and 'errors': list of mismatch descriptions.
    """
    errors = []

    # Check (1): 'current_assessment' is a non-empty string
    current_assessment = output_dict.get('current_assessment')
    if not isinstance(current_assessment, str) or current_assessment.strip() == '':
        errors.append("'current_assessment' must be a non-empty string")

    # Check (2): 'key_gaps' is a list of strings
    key_gaps = output_dict.get('key_gaps')
    if not isinstance(key_gaps, list):
        errors.append("'key_gaps' must be a list")
    else:
        if not all(isinstance(gap, str) for gap in key_gaps):
            errors.append("'key_gaps' must be a list of strings")

    # Check (3): 'next_priority' is a non-empty string
    next_priority = output_dict.get('next_priority')
    if not isinstance(next_priority, str) or next_priority.strip() == '':
        errors.append("'next_priority' must be a non-empty string")

    # Check (4): 'timestamp' is a valid float
    timestamp = output_dict.get('timestamp')
    if not isinstance(timestamp, (int, float)):
        errors.append("'timestamp' must be a valid float")
    else:
        try:
            float(timestamp)
        except (ValueError, TypeError):
            errors.append("'timestamp' must be a valid float")

    # Check (5): 'cycle' is a positive integer
    cycle = output_dict.get('cycle')
    if not isinstance(cycle, int) or cycle <= 0:
        errors.append("'cycle' must be a positive integer")

    return {
        'valid': len(errors) == 0,
        'errors': errors
    }


def normalize_reflection_output(output_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize a reflection output dictionary by ensuring all required fields exist
    with sensible defaults if missing, to prevent schema drift.

    Default values:
        - current_assessment: ""
        - key_gaps: []
        - next_priority: ""
        - timestamp: 0.0
        - cycle: 0

    Args:
        output_dict: The raw reflection output dictionary.

    Returns:
        A normalized dictionary with all required fields present.
    """
    normalized = output_dict.copy()

    # Ensure 'current_assessment' is a string
    if 'current_assessment' not in normalized or not isinstance(normalized['current_assessment'], str):
        normalized['current_assessment'] = ""

    # Ensure 'key_gaps' is a list of strings
    if 'key_gaps' not in normalized or not isinstance(normalized['key_gaps'], list):
        normalized['key_gaps'] = []
    else:
        normalized['key_gaps'] = [str(gap) for gap in normalized['key_gaps']]

    # Ensure 'next_priority' is a string
    if 'next_priority' not in normalized or not isinstance(normalized['next_priority'], str):
        normalized['next_priority'] = ""

    # Ensure 'timestamp' is a float
    if 'timestamp' not in normalized:
        normalized['timestamp'] = 0.0
    else:
        try:
            normalized['timestamp'] = float(normalized['timestamp'])
        except (ValueError, TypeError):
            normalized['timestamp'] = 0.0

    # Ensure 'cycle' is an integer
    if 'cycle' not in normalized:
        normalized['cycle'] = 0
    else:
        try:
            normalized['cycle'] = int(normalized['cycle'])
        except (ValueError, TypeError):
            normalized['cycle'] = 0

    return normalized