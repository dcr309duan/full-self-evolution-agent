from typing import Any, Dict, List, Optional, Tuple
from schema_alignment.registry import SchemaRegistry
from schema_alignment.schema import Schema, Field


class ValidationError(Exception):
    """Exception raised for schema validation failures."""
    pass


class FieldMismatch:
    """Represents a mismatch between a field and its expected schema definition."""
    
    def __init__(self, field_name: str, expected_type: str, actual_value: Any, 
                 module_name: str, direction: str, details: str = ""):
        self.field_name = field_name
        self.expected_type = expected_type
        self.actual_value = actual_value
        self.module_name = module_name
        self.direction = direction  # 'input' or 'output'
        self.details = details

    def __repr__(self) -> str:
        return (f"FieldMismatch(field='{self.field_name}', module='{self.module_name}', "
                f"expected={self.expected_type}, got={type(self.actual_value).__name__}, "
                f"direction='{self.direction}', details='{self.details}')")


class CrossModuleMismatch:
    """Represents a mismatch between connected fields across modules."""
    
    def __init__(self, source_module: str, source_field: str, 
                 target_module: str, target_field: str,
                 source_type: str, target_type: str, details: str = ""):
        self.source_module = source_module
        self.source_field = source_field
        self.target_module = target_module
        self.target_field = target_field
        self.source_type = source_type
        self.target_type = target_type
        self.details = details

    def __repr__(self) -> str:
        return (f"CrossModuleMismatch({self.source_module}.{self.source_field} -> "
                f"{self.target_module}.{self.target_field}: "
                f"{self.source_type} != {self.target_type})")


class ValidationReport:
    """Collects and reports all validation results."""
    
    def __init__(self):
        self.field_mismatches: List[FieldMismatch] = []
        self.cross_module_mismatches: List[CrossModuleMismatch] = []
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def has_errors(self) -> bool:
        return bool(self.field_mismatches or self.cross_module_mismatches or self.errors)

    def summary(self) -> str:
        lines = []
        if self.field_mismatches:
            lines.append(f"Field mismatches ({len(self.field_mismatches)}):")
            for mm in self.field_mismatches:
                lines.append(f"  - {mm}")
        if self.cross_module_mismatches:
            lines.append(f"Cross-module mismatches ({len(self.cross_module_mismatches)}):")
            for cm in self.cross_module_mismatches:
                lines.append(f"  - {cm}")
        if self.errors:
            lines.append(f"Errors ({len(self.errors)}):")
            for e in self.errors:
                lines.append(f"  - {e}")
        if self.warnings:
            lines.append(f"Warnings ({len(self.warnings)}):")
            for w in self.warnings:
                lines.append(f"  - {w}")
        if not lines:
            lines.append("Validation passed with no issues.")
        return "\n".join(lines)


class SchemaValidator:
    """Validates module outputs against registered schemas and checks cross-module consistency."""

    def __init__(self, registry: Optional[SchemaRegistry] = None):
        self.registry = registry or SchemaRegistry()

    def validate_module_output(self, module_name: str, output_data: Dict[str, Any]) -> ValidationReport:
        """Validate a module's output data against its registered output schema."""
        report = ValidationReport()
        schema = self.registry.get_schema(module_name)
        if not schema:
            report.errors.append(f"No schema registered for module '{module_name}'")
            return report

        output_fields = schema.get_output_fields()
        self._validate_fields(module_name, output_data, output_fields, "output", report)
        return report

    def validate_module_input(self, module_name: str, input_data: Dict[str, Any]) -> ValidationReport:
        """Validate a module's input data against its registered input schema."""
        report = ValidationReport()
        schema = self.registry.get_schema(module_name)
        if not schema:
            report.errors.append(f"No schema registered for module '{module_name}'")
            return report

        input_fields = schema.get_input_fields()
        self._validate_fields(module_name, input_data, input_fields, "input", report)
        return report

    def validate_module(self, module_name: str, input_data: Dict[str, Any], 
                        output_data: Dict[str, Any]) -> ValidationReport:
        """Validate both input and output of a module."""
        report = ValidationReport()
        input_report = self.validate_module_input(module_name, input_data)
        output_report = self.validate_module_output(module_name, output_data)
        report.field_mismatches.extend(input_report.field_mismatches)
        report.field_mismatches.extend(output_report.field_mismatches)
        report.errors.extend(input_report.errors)
        report.errors.extend(output_report.errors)
        report.warnings.extend(input_report.warnings)
        report.warnings.extend(output_report.warnings)
        return report

    def _validate_fields(self, module_name: str, data: Dict[str, Any], 
                         expected_fields: List[Field], direction: str,
                         report: ValidationReport) -> None:
        """Validate actual data fields against expected schema fields."""
        expected_field_map = {f.name: f for f in expected_fields}
        
        # Check for missing fields
        for field_name, field_def in expected_field_map.items():
            if field_name not in data:
                report.field_mismatches.append(
                    FieldMismatch(field_name, field_def.field_type, None, 
                                  module_name, direction, "Missing field")
                )
                continue

            actual_value = data[field_name]
            if not self._type_matches(field_def.field_type, actual_value):
                report.field_mismatches.append(
                    FieldMismatch(field_name, field_def.field_type, actual_value,
                                  module_name, direction, "Type mismatch")
                )

        # Check for unexpected fields
        for field_name in data:
            if field_name not in expected_field_map:
                report.warnings.append(
                    f"Unexpected field '{field_name}' in {direction} of module '{module_name}'"
                )

    def _type_matches(self, expected_type: str, value: Any) -> bool:
        """Check if a value matches an expected type string."""
        type_map = {
            "string": str,
            "integer": int,
            "float": float,
            "boolean": bool,
            "list": list,
            "dict": dict,
            "any": None,  # any type is allowed
        }
        
        if expected_type == "any":
            return True
        
        expected_python_type = type_map.get(expected_type)
        if expected_python_type is None:
            # Unknown type, accept by default
            return True
        
        return isinstance(value, expected_python_type)

    def check_cross_module_consistency(self, connections: List[Tuple[str, str, str, str]]) -> ValidationReport:
        """
        Check consistency between connected fields across modules.
        
        Args:
            connections: List of tuples (source_module, source_field, target_module, target_field)
        """
        report = ValidationReport()
        
        for source_module, source_field, target_module, target_field in connections:
            source_schema = self.registry.get_schema(source_module)
            target_schema = self.registry.get_schema(target_module)
            
            if not source_schema:
                report.errors.append(f"No schema for source module '{source_module}'")
                continue
            if not target_schema:
                report.errors.append(f"No schema for target module '{target_module}'")
                continue

            # Find source field in output fields
            source_field_def = None
            for f in source_schema.get_output_fields():
                if f.name == source_field:
                    source_field_def = f
                    break
            
            if not source_field_def:
                report.errors.append(
                    f"Source field '{source_field}' not found in output of '{source_module}'"
                )
                continue

            # Find target field in input fields
            target_field_def = None
            for f in target_schema.get_input_fields():
                if f.name == target_field:
                    target_field_def = f
                    break

            if not target_field_def:
                report.errors.append(
                    f"Target field '{target_field}' not found in input of '{target_module}'"
                )
                continue

            # Check type compatibility
            if not self._types_compatible(source_field_def.field_type, target_field_def.field_type):
                report.cross_module_mismatches.append(
                    CrossModuleMismatch(
                        source_module, source_field,
                        target_module, target_field,
                        source_field_def.field_type,
                        target_field_def.field_type,
                        "Type incompatibility"
                    )
                )

        return report

    def _types_compatible(self, type_a: str, type_b: str) -> bool:
        """Check if two types are compatible for cross-module connection."""
        if type_a == "any" or type_b == "any":
            return True
        
        # Direct match
        if type_a == type_b:
            return True
        
        # Numeric compatibility
        numeric_types = {"integer", "float"}
        if type_a in numeric_types and type_b in numeric_types:
            return True
        
        return False

    def validate_pipeline(self, pipeline_config: Dict[str, Any]) -> ValidationReport:
        """
        Validate an entire pipeline configuration.
        
        Args:
            pipeline_config: Dict with 'modules' list and 'connections' list
        """
        report = ValidationReport()
        
        modules = pipeline_config.get("modules", [])
        connections = pipeline_config.get("connections", [])
        
        # Validate each module
        for module_config in modules:
            module_name = module_config.get("name")
            if not module_name:
                report.errors.append("Module config missing 'name'")
                continue
            
            input_data = module_config.get("input", {})
            output_data = module_config.get("output", {})
            
            module_report = self.validate_module(module_name, input_data, output_data)
            report.field_mismatches.extend(module_report.field_mismatches)
            report.errors.extend(module_report.errors)
            report.warnings.extend(module_report.warnings)

        # Check cross-module consistency
        if connections:
            conn_tuples = []
            for conn in connections:
                conn_tuples.append((
                    conn.get("source_module"),
                    conn.get("source_field"),
                    conn.get("target_module"),
                    conn.get("target_field")
                ))
            cross_report = self.check_cross_module_consistency(conn_tuples)
            report.cross_module_mismatches.extend(cross_report.cross_module_mismatches)
            report.errors.extend(cross_report.errors)
            report.warnings.extend(cross_report.warnings)

        return report