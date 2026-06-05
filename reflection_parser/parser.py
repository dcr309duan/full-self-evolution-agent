from typing import Any, Dict, Optional
import logging
from .schema_validator import SchemaValidator  # Assuming this module exists
from .canonical_converter import CanonicalConverter  # Assuming this module exists

logger = logging.getLogger(__name__)

class Parser:
    """Base parser class with output validation and auto-conversion capabilities."""

    def __init__(self, schema_validator: Optional[SchemaValidator] = None, 
                 canonical_converter: Optional[CanonicalConverter] = None):
        self.schema_validator = schema_validator or SchemaValidator()
        self.canonical_converter = canonical_converter or CanonicalConverter()

    def parse(self, input_data: Any) -> Dict[str, Any]:
        """Parse input data and return the result."""
        # Placeholder for actual parsing logic
        raise NotImplementedError("Subclasses must implement parse method")

    def validate_output(self, output: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate the parser's output against the schema.
        If validation fails, log the mismatch and attempt auto-conversion to canonical form.
        
        Args:
            output: The output dictionary to validate
            
        Returns:
            The validated (and possibly converted) output dictionary
        """
        if not self.schema_validator.validate(output):
            logger.warning(f"Output validation failed for: {output}")
            logger.info("Attempting auto-conversion to canonical form...")
            
            try:
                converted_output = self.canonical_converter.convert(output)
                if self.schema_validator.validate(converted_output):
                    logger.info("Auto-conversion successful")
                    return converted_output
                else:
                    logger.error("Auto-conversion failed: output still does not match schema")
                    return output  # Return original output if conversion fails
            except Exception as e:
                logger.error(f"Auto-conversion error: {e}")
                return output
        
        logger.debug("Output validation passed")
        return output

    def parse_and_validate(self, input_data: Any) -> Dict[str, Any]:
        """
        Parse input data and validate the output.
        
        Args:
            input_data: The input data to parse
            
        Returns:
            The validated output dictionary
        """
        output = self.parse(input_data)
        return self.validate_output(output)