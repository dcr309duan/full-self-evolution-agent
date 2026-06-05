from typing import Any, Dict, Optional
from agent_core.schema_registry import SchemaRegistry, SchemaValidationError

# Initialize schema registry
schema_registry = SchemaRegistry()

def validate_schema(schema_name: str, schema_version: str):
    """Decorator to validate function output against a registered schema."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            try:
                schema_registry.validate(result, schema_name, schema_version)
            except SchemaValidationError as e:
                raise SchemaValidationError(
                    f"Output validation failed for {schema_name} v{schema_version}: {e}"
                )
            return result
        return wrapper
    return decorator

class MutationEngine:
    """Engine for generating mutations with schema validation."""

    def __init__(self, registry: Optional[SchemaRegistry] = None):
        self.registry = registry or schema_registry
        self._input_schemas = {
            'data_source': ('data_source_input', '1.0'),
            'transformer': ('transformer_input', '1.0'),
            'generator': ('generator_input', '1.0')
        }

    def _validate_input(self, data: Dict[str, Any], source: str) -> None:
        """Validate input data from a specific module using the registry."""
        if source not in self._input_schemas:
            raise ValueError(f"Unknown input source: {source}")
        
        schema_name, schema_version = self._input_schemas[source]
        try:
            self.registry.validate(data, schema_name, schema_version)
        except SchemaValidationError as e:
            raise SchemaValidationError(
                f"Input validation failed for {source} ({schema_name} v{schema_version}): {e}"
            )

    @validate_schema('mutation_engine', version=1)
    def generate_mutation(self, input_data: Dict[str, Any], 
                          source: str = 'data_source') -> Dict[str, Any]:
        """Main mutation generation method with input validation and output schema validation."""
        # Pre-processing: validate input data
        self._validate_input(input_data, source)
        
        # Mutation generation logic (simplified example)
        mutation_result = {
            'mutated_data': self._apply_mutations(input_data),
            'metadata': {
                'source': source,
                'timestamp': self._get_timestamp()
            }
        }
        
        # Update result format to include schema_version
        mutation_result['schema_version'] = '1.0'
        
        return mutation_result

    @validate_schema('mutation_result', version=1)
    def return_result(self, result_data: Dict[str, Any]) -> Dict[str, Any]:
        """Return mutation result with schema validation."""
        # Version check before processing incoming test results
        if 'schema_version' in result_data:
            version = result_data['schema_version']
            if version != '1.0':
                raise SchemaValidationError(
                    f"Unsupported schema version: {version}. Expected: 1.0"
                )
        else:
            raise SchemaValidationError("Missing schema_version in result data")
        
        # Process and return the result
        return result_data

    def _apply_mutations(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply mutations to the input data (placeholder implementation)."""
        # Actual mutation logic would go here
        return {k: f"mutated_{v}" if isinstance(v, str) else v 
                for k, v in data.items()}

    def _get_timestamp(self) -> str:
        """Get current timestamp (placeholder)."""
        from datetime import datetime
        return datetime.utcnow().isoformat()

    def register_input_schema(self, source: str, schema_name: str, 
                              schema_version: str) -> None:
        """Register a new input schema for a specific module source."""
        self._input_schemas[source] = (schema_name, schema_version)