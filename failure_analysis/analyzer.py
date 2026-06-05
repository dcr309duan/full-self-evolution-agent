from typing import Any, Dict, List, Optional, Union
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class SchemaValidationError(Exception):
    """Custom exception for schema validation errors."""
    pass


class OutputAnalyzer:
    """
    A class to analyze and validate output against a registered schema.
    
    Supports auto-conversion of output fields to match the expected schema types.
    """
    
    def __init__(self, schema: Optional[Dict[str, Any]] = None):
        """
        Initialize the analyzer with an optional schema.
        
        Args:
            schema: Dictionary defining expected output structure with field names as keys
                    and expected types or type strings as values.
        """
        self._schema = schema or {}
        self._conversion_log: List[Dict[str, Any]] = []
        
    def register_schema(self, schema: Dict[str, Any]) -> None:
        """
        Register or update the output schema.
        
        Args:
            schema: Dictionary mapping field names to expected types.
                    Types can be Python types (e.g., int, str) or type strings
                    (e.g., 'int', 'str', 'float', 'bool', 'datetime').
        """
        self._schema = schema
        logger.info(f"Schema registered with {len(schema)} fields")
        
    def validate_output(self, output: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate the analyzer's output against its registered schema and auto-convert if needed.
        
        Args:
            output: Dictionary containing the output data to validate.
            
        Returns:
            Validated and potentially converted output dictionary.
            
        Raises:
            SchemaValidationError: If validation fails and conversion is not possible.
        """
        if not self._schema:
            logger.warning("No schema registered; returning output as-is")
            return output
        
        validated_output = {}
        self._conversion_log = []
        
        for field, expected_type in self._schema.items():
            if field not in output:
                logger.warning(f"Field '{field}' missing from output; skipping validation")
                continue
                
            value = output[field]
            expected_type_obj = self._resolve_type(expected_type)
            
            if value is None:
                validated_output[field] = value
                continue
                
            if isinstance(value, expected_type_obj):
                validated_output[field] = value
            else:
                try:
                    converted_value = self._convert_value(value, expected_type_obj, field)
                    validated_output[field] = converted_value
                    self._conversion_log.append({
                        'field': field,
                        'original_type': type(value).__name__,
                        'converted_type': expected_type_obj.__name__,
                        'timestamp': datetime.now().isoformat()
                    })
                    logger.info(f"Auto-converted field '{field}' from {type(value).__name__} to {expected_type_obj.__name__}")
                except (ValueError, TypeError) as e:
                    raise SchemaValidationError(
                        f"Cannot convert field '{field}' from {type(value).__name__} to {expected_type_obj.__name__}: {e}"
                    )
        
        # Add any extra fields not in schema
        for field in output:
            if field not in self._schema:
                validated_output[field] = output[field]
                
        return validated_output
    
    def get_conversion_log(self) -> List[Dict[str, Any]]:
        """
        Get the log of all conversions performed during the last validation.
        
        Returns:
            List of conversion log entries.
        """
        return self._conversion_log.copy()
    
    def _resolve_type(self, type_spec: Union[type, str]) -> type:
        """
        Resolve a type specification to an actual Python type.
        
        Args:
            type_spec: Either a Python type or a string representation.
            
        Returns:
            The resolved Python type.
        """
        if isinstance(type_spec, type):
            return type_spec
        
        type_mapping = {
            'int': int,
            'float': float,
            'str': str,
            'bool': bool,
            'list': list,
            'dict': dict,
            'tuple': tuple,
            'set': set,
            'datetime': datetime,
            'any': object,
        }
        
        resolved = type_mapping.get(type_spec.lower())
        if resolved is None:
            raise SchemaValidationError(f"Unknown type specification: {type_spec}")
        return resolved
    
    def _convert_value(self, value: Any, target_type: type, field_name: str) -> Any:
        """
        Attempt to convert a value to the target type.
        
        Args:
            value: The value to convert.
            target_type: The target Python type.
            field_name: Name of the field (for error messages).
            
        Returns:
            The converted value.
            
        Raises:
            ValueError: If conversion is not possible.
        """
        if target_type == bool:
            if isinstance(value, (int, float)):
                return bool(value)
            if isinstance(value, str):
                if value.lower() in ('true', '1', 'yes'):
                    return True
                elif value.lower() in ('false', '0', 'no'):
                    return False
                raise ValueError(f"Cannot convert string '{value}' to bool")
                
        elif target_type == int:
            if isinstance(value, float):
                return int(value)
            if isinstance(value, str):
                return int(value.strip())
                
        elif target_type == float:
            if isinstance(value, int):
                return float(value)
            if isinstance(value, str):
                return float(value.strip())
                
        elif target_type == str:
            return str(value)
            
        elif target_type == datetime:
            if isinstance(value, str):
                # Try common datetime formats
                formats = [
                    '%Y-%m-%d %H:%M:%S',
                    '%Y-%m-%dT%H:%M:%S',
                    '%Y-%m-%d',
                    '%m/%d/%Y %H:%M:%S',
                    '%m/%d/%Y',
                ]
                for fmt in formats:
                    try:
                        return datetime.strptime(value, fmt)
                    except ValueError:
                        continue
                raise ValueError(f"Cannot parse datetime string '{value}'")
                
        elif target_type == list:
            if isinstance(value, (tuple, set)):
                return list(value)
            if isinstance(value, str):
                # Try to evaluate as a list literal (safe evaluation)
                try:
                    import ast
                    parsed = ast.literal_eval(value)
                    if isinstance(parsed, list):
                        return parsed
                except (ValueError, SyntaxError):
                    pass
                # Fallback: split by comma
                return [item.strip() for item in value.split(',')]
                
        elif target_type == dict:
            if isinstance(value, str):
                try:
                    import ast
                    parsed = ast.literal_eval(value)
                    if isinstance(parsed, dict):
                        return parsed
                except (ValueError, SyntaxError):
                    pass
                raise ValueError(f"Cannot convert string to dict")
                
        # For other types, try direct constructor
        try:
            return target_type(value)
        except (TypeError, ValueError) as e:
            raise ValueError(f"Cannot convert to {target_type.__name__}: {e}")