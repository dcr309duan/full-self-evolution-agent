"""Schema Alignment Checker - validates data against canonical schemas and generates migration patches."""

from typing import Any, Dict, List, Optional, Tuple
import copy


class SchemaAlignmentChecker:
    """Validates data against registered module schemas and handles schema migrations."""

    def __init__(self):
        self._schemas: Dict[str, Dict[str, type]] = {}
        self._migration_patches: Dict[str, Dict[str, Any]] = {}

    def register_module(self, module_name: str, schema: Dict[str, type]) -> None:
        """Register a new module schema dynamically.

        Args:
            module_name: Name of the module to register.
            schema: Dictionary mapping field names to expected types.
        """
        if not isinstance(schema, dict):
            raise TypeError("Schema must be a dictionary mapping field names to types.")
        if not all(isinstance(v, type) for v in schema.values()):
            raise TypeError("All schema values must be Python types (e.g., int, str, list).")

        self._schemas[module_name] = schema

    def _get_schema(self, module_name: str) -> Dict[str, type]:
        """Retrieve the schema for a module, raising error if not registered."""
        if module_name not in self._schemas:
            raise ValueError(f"Module '{module_name}' is not registered. Call register_module() first.")
        return self._schemas[module_name]

    def validate_data(self, module_name: str, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Validate data against the canonical schema for a module.

        Returns a list of mismatches, each a dict with keys:
            - 'field': field name
            - 'issue': one of 'missing_field', 'type_mismatch', 'extra_field'
            - 'expected_type': (only for type_mismatch)
            - 'actual_type': (only for type_mismatch)
            - 'actual_value': (only for type_mismatch)
        """
        schema = self._get_schema(module_name)
        mismatches: List[Dict[str, Any]] = []

        # Check for missing fields and type mismatches
        for field, expected_type in schema.items():
            if field not in data:
                mismatches.append({
                    'field': field,
                    'issue': 'missing_field',
                    'expected_type': expected_type
                })
            else:
                actual_value = data[field]
                actual_type = type(actual_value)
                if actual_type != expected_type:
                    mismatches.append({
                        'field': field,
                        'issue': 'type_mismatch',
                        'expected_type': expected_type,
                        'actual_type': actual_type,
                        'actual_value': actual_value
                    })

        # Check for extra fields not in schema
        for field in data:
            if field not in schema:
                mismatches.append({
                    'field': field,
                    'issue': 'extra_field',
                    'actual_value': data[field]
                })

        return mismatches

    def generate_migration_patch(self, module_name: str, mismatches: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate a migration patch that transforms old data format to new format.

        The patch is a dict with:
            - 'add_fields': dict of field names to default values for missing fields
            - 'convert_fields': dict of field names to conversion functions (as strings) for type mismatches
            - 'remove_fields': list of field names to remove for extra fields

        Args:
            module_name: Name of the module (used to get schema for defaults).
            mismatches: List of mismatches from validate_data().

        Returns:
            A migration patch dict.
        """
        schema = self._get_schema(module_name)
        patch: Dict[str, Any] = {
            'add_fields': {},
            'convert_fields': {},
            'remove_fields': []
        }

        for mismatch in mismatches:
            if mismatch['issue'] == 'missing_field':
                field = mismatch['field']
                expected_type = mismatch['expected_type']
                # Provide a sensible default based on type
                if expected_type == str:
                    default = ""
                elif expected_type == int:
                    default = 0
                elif expected_type == float:
                    default = 0.0
                elif expected_type == bool:
                    default = False
                elif expected_type == list:
                    default = []
                elif expected_type == dict:
                    default = {}
                else:
                    default = None
                patch['add_fields'][field] = default

            elif mismatch['issue'] == 'type_mismatch':
                field = mismatch['field']
                expected_type = mismatch['expected_type']
                actual_type = mismatch['actual_type']
                # Generate a conversion hint (as string for serializability)
                if expected_type == str:
                    patch['convert_fields'][field] = 'str'
                elif expected_type == int:
                    patch['convert_fields'][field] = 'int'
                elif expected_type == float:
                    patch['convert_fields'][field] = 'float'
                elif expected_type == bool:
                    patch['convert_fields'][field] = 'bool'
                elif expected_type == list:
                    patch['convert_fields'][field] = 'list'
                elif expected_type == dict:
                    patch['convert_fields'][field] = 'dict'
                else:
                    patch['convert_fields'][field] = f'to_{expected_type.__name__}'

            elif mismatch['issue'] == 'extra_field':
                patch['remove_fields'].append(mismatch['field'])

        # Cache the patch for potential auto-apply
        self._migration_patches[module_name] = patch
        return patch

    def auto_apply_patch(self, module_name: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply migration patch to data in-place and return the updated data.

        If no patch has been generated yet, it will generate one based on current
        validation mismatches.

        Args:
            module_name: Name of the module.
            data: Data dict to patch in-place.

        Returns:
            The patched data dict (same object, modified in-place).
        """
        # If no cached patch, generate one by validating first
        if module_name not in self._migration_patches:
            mismatches = self.validate_data(module_name, data)
            if mismatches:
                self.generate_migration_patch(module_name, mismatches)
            else:
                # No mismatches, nothing to patch
                return data

        patch = self._migration_patches.get(module_name)
        if not patch:
            return data

        # Add missing fields with defaults
        for field, default_value in patch.get('add_fields', {}).items():
            if field not in data:
                data[field] = copy.deepcopy(default_value)

        # Convert type mismatches
        for field, conversion in patch.get('convert_fields', {}).items():
            if field in data:
                try:
                    if conversion == 'str':
                        data[field] = str(data[field])
                    elif conversion == 'int':
                        data[field] = int(data[field])
                    elif conversion == 'float':
                        data[field] = float(data[field])
                    elif conversion == 'bool':
                        data[field] = bool(data[field])
                    elif conversion == 'list':
                        if not isinstance(data[field], list):
                            data[field] = [data[field]]
                    elif conversion == 'dict':
                        if not isinstance(data[field], dict):
                            # Attempt to convert; if fails, wrap in dict
                            try:
                                data[field] = dict(data[field])
                            except (TypeError, ValueError):
                                data[field] = {'value': data[field]}
                    else:
                        # Custom conversion (fallback: try eval-like approach but safe)
                        # For simplicity, we just skip unknown conversions
                        pass
                except (ValueError, TypeError) as e:
                    # If conversion fails, leave as is (or could raise)
                    pass

        # Remove extra fields
        for field in patch.get('remove_fields', []):
            if field in data:
                del data[field]

        return data

    def get_registered_modules(self) -> List[str]:
        """Return list of registered module names."""
        return list(self._schemas.keys())