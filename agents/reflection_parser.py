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