from typing import Any, Dict, Optional, Callable


class SchemaConverter:
    """
    Auto-converter that maps between module-specific JSON formats and a canonical representation.
    Uses a field-mapping dictionary and supports default values for missing fields.
    """

    def __init__(self, field_mapping: Dict[str, Dict[str, Any]]):
        """
        Initialize the converter with a field mapping.

        The field_mapping should be a dictionary where keys are canonical field names,
        and values are dictionaries with:
            - 'source_key': str (the key in the module-specific JSON)
            - 'default': optional default value if the source key is missing
            - 'transform': optional callable to transform the value (e.g., type conversion)
        """
        self.field_mapping = field_mapping

    def convert_to_canonical(self, module_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert module-specific JSON data to canonical representation.

        Args:
            module_data: Dictionary from the module-specific format.

        Returns:
            Dictionary in canonical format.
        """
        canonical = {}
        for canonical_key, mapping in self.field_mapping.items():
            source_key = mapping.get('source_key')
            default = mapping.get('default')
            transform = mapping.get('transform')

            # Get value from module data, falling back to default
            value = module_data.get(source_key, default)

            # Apply transform if provided and value is not None
            if transform is not None and value is not None:
                value = transform(value)

            canonical[canonical_key] = value
        return canonical

    def convert_from_canonical(self, canonical_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert canonical representation back to module-specific JSON format.

        Args:
            canonical_data: Dictionary in canonical format.

        Returns:
            Dictionary in module-specific format.
        """
        module_data = {}
        for canonical_key, mapping in self.field_mapping.items():
            source_key = mapping.get('source_key')
            default = mapping.get('default')
            transform = mapping.get('transform')

            # Get value from canonical data, falling back to default
            value = canonical_data.get(canonical_key, default)

            # Apply transform if provided and value is not None
            if transform is not None and value is not None:
                value = transform(value)

            module_data[source_key] = value
        return module_data

    def add_mapping(self, canonical_key: str, source_key: str, default: Any = None,
                    transform: Optional[Callable] = None) -> None:
        """
        Add a new field mapping dynamically.

        Args:
            canonical_key: The canonical field name.
            source_key: The key in the module-specific JSON.
            default: Default value if the source key is missing.
            transform: Optional callable to transform the value.
        """
        self.field_mapping[canonical_key] = {
            'source_key': source_key,
            'default': default,
            'transform': transform
        }

    def remove_mapping(self, canonical_key: str) -> None:
        """
        Remove a field mapping by canonical key.

        Args:
            canonical_key: The canonical field name to remove.
        """
        self.field_mapping.pop(canonical_key, None)