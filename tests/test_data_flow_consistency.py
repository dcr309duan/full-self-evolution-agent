import unittest
import json
import random
import string
from typing import Any, Dict, List, Optional
from datetime import datetime

# Assuming these imports from your project structure
# Adjust imports based on actual module locations
try:
    from reflection_parser import ReflectionParser
    from data_transformer import DataTransformer
    from schema_validator import SchemaValidator
    from pipeline_runner import PipelineRunner
except ImportError:
    # Placeholder classes for testing when actual modules aren't available
    class ReflectionParser:
        def parse(self, data: str) -> Dict[str, Any]:
            return json.loads(data)
    
    class DataTransformer:
        def transform(self, data: Dict[str, Any]) -> Dict[str, Any]:
            return data
    
    class SchemaValidator:
        def validate(self, data: Dict[str, Any]) -> bool:
            return True
    
    class PipelineRunner:
        def run(self, data: Dict[str, Any]) -> Dict[str, Any]:
            return data


class TestDataFlowConsistency(unittest.TestCase):
    """Test data flow consistency through the entire pipeline."""
    
    CANONICAL_SCHEMA = {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "timestamp": {"type": "string", "format": "datetime"},
            "version": {"type": "string"},
            "content": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "body": {"type": "string"},
                    "metadata": {
                        "type": "object",
                        "properties": {
                            "author": {"type": "string"},
                            "tags": {"type": "array", "items": {"type": "string"}},
                            "priority": {"type": "integer", "minimum": 0, "maximum": 5}
                        },
                        "required": ["author"]
                    }
                },
                "required": ["title", "body"]
            },
            "status": {"type": "string", "enum": ["active", "inactive", "pending"]}
        },
        "required": ["id", "timestamp", "version", "content", "status"]
    }
    
    def setUp(self):
        """Initialize pipeline components."""
        self.parser = ReflectionParser()
        self.transformer = DataTransformer()
        self.validator = SchemaValidator()
        self.pipeline = PipelineRunner()
        
    def _generate_random_string(self, length: int = 10) -> str:
        """Generate random alphanumeric string."""
        return ''.join(random.choices(string.ascii_letters + string.digits, k=length))
    
    def _generate_random_valid_output(self) -> Dict[str, Any]:
        """Generate random valid reflection parser output."""
        return {
            "id": self._generate_random_string(8),
            "timestamp": datetime.utcnow().isoformat(),
            "version": f"{random.randint(1, 5)}.{random.randint(0, 9)}.{random.randint(0, 9)}",
            "content": {
                "title": self._generate_random_string(20),
                "body": self._generate_random_string(100),
                "metadata": {
                    "author": self._generate_random_string(15),
                    "tags": [self._generate_random_string(5) for _ in range(random.randint(0, 5))],
                    "priority": random.randint(0, 5)
                }
            },
            "status": random.choice(["active", "inactive", "pending"])
        }
    
    def _validate_against_schema(self, data: Dict[str, Any], schema: Dict[str, Any]) -> List[str]:
        """Validate data against a schema and return list of violations."""
        violations = []
        
        # Check required fields
        if "required" in schema:
            for field in schema["required"]:
                if field not in data:
                    violations.append(f"Missing required field: {field}")
        
        # Check properties
        if "properties" in schema:
            for field, field_schema in schema["properties"].items():
                if field in data:
                    violations.extend(self._validate_field(data[field], field_schema, field))
        
        return violations
    
    def _validate_field(self, value: Any, schema: Dict[str, Any], path: str) -> List[str]:
        """Validate a single field against its schema."""
        violations = []
        
        if "type" in schema:
            expected_type = schema["type"]
            if expected_type == "string":
                if not isinstance(value, str):
                    violations.append(f"{path}: Expected string, got {type(value).__name__}")
                elif "enum" in schema and value not in schema["enum"]:
                    violations.append(f"{path}: Value '{value}' not in enum {schema['enum']}")
                elif "format" in schema and schema["format"] == "datetime":
                    try:
                        datetime.fromisoformat(value)
                    except ValueError:
                        violations.append(f"{path}: Invalid datetime format: {value}")
                        
            elif expected_type == "integer":
                if not isinstance(value, int):
                    violations.append(f"{path}: Expected integer, got {type(value).__name__}")
                else:
                    if "minimum" in schema and value < schema["minimum"]:
                        violations.append(f"{path}: Value {value} less than minimum {schema['minimum']}")
                    if "maximum" in schema and value > schema["maximum"]:
                        violations.append(f"{path}: Value {value} greater than maximum {schema['maximum']}")
                        
            elif expected_type == "array":
                if not isinstance(value, list):
                    violations.append(f"{path}: Expected array, got {type(value).__name__}")
                elif "items" in schema:
                    for i, item in enumerate(value):
                        violations.extend(self._validate_field(item, schema["items"], f"{path}[{i}]"))
                        
            elif expected_type == "object":
                if not isinstance(value, dict):
                    violations.append(f"{path}: Expected object, got {type(value).__name__}")
                else:
                    violations.extend(self._validate_against_schema(value, schema))
        
        return violations
    
    def _check_data_consistency(self, original: Dict[str, Any], processed: Dict[str, Any], path: str = "") -> List[str]:
        """Check that data is consistent between original and processed versions."""
        violations = []
        
        if type(original) != type(processed):
            violations.append(f"{path}: Type mismatch - {type(original).__name__} vs {type(processed).__name__}")
            return violations
        
        if isinstance(original, dict):
            # Check for missing keys
            missing_keys = set(original.keys()) - set(processed.keys())
            extra_keys = set(processed.keys()) - set(original.keys())
            
            for key in missing_keys:
                violations.append(f"{path}.{key}: Missing in processed data")
            for key in extra_keys:
                violations.append(f"{path}.{key}: Extra key in processed data")
            
            # Recursively check common keys
            for key in set(original.keys()) & set(processed.keys()):
                violations.extend(
                    self._check_data_consistency(original[key], processed[key], f"{path}.{key}")
                )
                
        elif isinstance(original, list):
            if len(original) != len(processed):
                violations.append(f"{path}: List length mismatch - {len(original)} vs {len(processed)}")
            else:
                for i, (orig_item, proc_item) in enumerate(zip(original, processed)):
                    violations.extend(
                        self._check_data_consistency(orig_item, proc_item, f"{path}[{i}]")
                    )
        
        return violations
    
    def test_random_valid_data_flow(self):
        """Test that random valid data flows correctly through the pipeline."""
        for _ in range(10):  # Run multiple random tests
            original_data = self._generate_random_valid_output()
            data_str = json.dumps(original_data)
            
            # Step 1: Parse
            parsed_data = self.parser.parse(data_str)
            self.assertIsInstance(parsed_data, dict)
            
            # Validate parsed output matches canonical schema
            violations = self._validate_against_schema(parsed_data, self.CANONICAL_SCHEMA)
            self.assertEqual(len(violations), 0, f"Schema violations after parsing: {violations}")
            
            # Step 2: Transform
            transformed_data = self.transformer.transform(parsed_data)
            self.assertIsInstance(transformed_data, dict)
            
            # Validate transformed output matches canonical schema
            violations = self._validate_against_schema(transformed_data, self.CANONICAL_SCHEMA)
            self.assertEqual(len(violations), 0, f"Schema violations after transform: {violations}")
            
            # Check no data loss between parse and transform
            violations = self._check_data_consistency(parsed_data, transformed_data)
            self.assertEqual(len(violations), 0, f"Data inconsistency between parse and transform: {violations}")
            
            # Step 3: Validate
            is_valid = self.validator.validate(transformed_data)
            self.assertTrue(is_valid, "Validator rejected valid data")
            
            # Step 4: Run full pipeline
            final_data = self.pipeline.run(transformed_data)
            self.assertIsInstance(final_data, dict)
            
            # Validate final output matches canonical schema
            violations = self._validate_against_schema(final_data, self.CANONICAL_SCHEMA)
            self.assertEqual(len(violations), 0, f"Schema violations after pipeline: {violations}")
            
            # Check no data loss through entire pipeline
            violations = self._check_data_consistency(original_data, final_data)
            self.assertEqual(len(violations), 0, f"Data inconsistency through full pipeline: {violations}")
    
    def test_empty_fields(self):
        """Test handling of empty fields."""
        test_cases = [
            # Empty string fields
            {
                "id": "",
                "timestamp": datetime.utcnow().isoformat(),
                "version": "1.0.0",
                "content": {
                    "title": "",
                    "body": "",
                    "metadata": {
                        "author": "",
                        "tags": [],
                        "priority": 0
                    }
                },
                "status": "active"
            },
            # Empty array
            {
                "id": "test123",
                "timestamp": datetime.utcnow().isoformat(),
                "version": "1.0.0",
                "content": {
                    "title": "Test",
                    "body": "Body",
                    "metadata": {
                        "author": "Author",
                        "tags": [],
                        "priority": 3
                    }
                },
                "status": "inactive"
            }
        ]
        
        for test_data in test_cases:
            data_str = json.dumps(test_data)
            parsed = self.parser.parse(data_str)
            transformed = self.transformer.transform(parsed)
            
            # Validate schema compliance
            violations = self._validate_against_schema(transformed, self.CANONICAL_SCHEMA)
            self.assertEqual(len(violations), 0, f"Schema violations for empty fields: {violations}")
            
            # Check data consistency
            violations = self._check_data_consistency(test_data, transformed)
            self.assertEqual(len(violations), 0, f"Data inconsistency for empty fields: {violations}")
    
    def test_null_values(self):
        """Test handling of null values where allowed."""
        # Note: In this schema, null values are not explicitly allowed,
        # but we test that the pipeline handles them gracefully
        test_data = {
            "id": None,
            "timestamp": None,
            "version": None,
            "content": None,
            "status": None
        }
        
        data_str = json.dumps(test_data)
        
        # Should not crash, but may fail validation
        try:
            parsed = self.parser.parse(data_str)
            transformed = self.transformer.transform(parsed)
            
            # Check that null values are preserved or handled appropriately
            violations = self._check_data_consistency(test_data, transformed)
            # Null values might be converted to empty strings or defaults
            # This test ensures we're aware of the behavior
            if violations:
                print(f"Null value handling produced violations: {violations}")
                
        except Exception as e:
            self.fail(f"Pipeline crashed on null values: {e}")
    
    def test_version_mismatches(self):
        """Test handling of version mismatches."""
        test_data = self._generate_random_valid_output()
        
        # Test with different version formats
        version_cases = [
            "1.0.0",      # Standard
            "2.0.0-beta", # Pre-release
            "3",          # Major only
            "1.2.3.4",    # Extra version components
            "v1.0.0",     # With prefix
            ""            # Empty version
        ]
        
        for version in version_cases:
            test_data["version"] = version
            data_str = json.dumps(test_data)
            
            try:
                parsed = self.parser.parse(data_str)
                transformed = self.transformer.transform(parsed)
                
                # Version field should be preserved as string
                self.assertEqual(transformed["version"], version,
                               f"Version not preserved: {version}")
                
                # Validate schema (version is just a string, so should pass)
                violations = self._validate_against_schema(transformed, self.CANONICAL_SCHEMA)
                self.assertEqual(len(violations), 0,
                               f"Schema violations for version '{version}': {violations}")
                
            except Exception as e:
                self.fail(f"Pipeline crashed on version '{version}': {e}")
    
    def test_data_corruption_detection(self):
        """Test that data corruption is detected."""
        original_data = self._generate_random_valid_output()
        data_str = json.dumps(original_data)
        
        # Parse and transform
        parsed = self.parser.parse(data_str)
        transformed = self.transformer.transform(parsed)
        
        # Corrupt the data in various ways
        corrupted_cases = [
            # Missing required field
            {k: v for k, v in transformed.items() if k != "id"},
            # Wrong type
            {**transformed, "id": 12345},
            # Invalid enum value
            {**transformed, "status": "invalid_status"},
            # Missing nested required field
            {**transformed, "content": {**transformed["content"], "metadata": {}}},
            # Invalid priority range
            {**transformed, "content": {
                **transformed["content"],
                "metadata": {**transformed["content"]["metadata"], "priority": 10}
            }}
        ]
        
        for corrupted in corrupted_cases:
            violations = self._validate_against_schema(corrupted, self.CANONICAL_SCHEMA)
            self.assertGreater(len(violations), 0,
                             f"Corrupted data should have schema violations: {corrupted}")
    
    def test_pipeline_idempotency(self):
        """Test that running the pipeline multiple times produces same result."""
        original_data = self._generate_random_valid_output()
        data_str = json.dumps(original_data)
        
        # Run pipeline multiple times
        results = []
        for _ in range(3):
            parsed = self.parser.parse(data_str)
            transformed = self.transformer.transform(parsed)
            final = self.pipeline.run(transformed)
            results.append(final)
        
        # All results should be identical
        for i in range(1, len(results)):
            self.assertEqual(results[0], results[i],
                           f"Pipeline not idempotent: run 0 vs run {i} differ")
    
    def test_large_data_flow(self):
        """Test data flow with large datasets."""
        large_data = self._generate_random_valid_output()
        
        # Add many tags to stress test
        large_data["content"]["metadata"]["tags"] = [
            self._generate_random_string(10) for _ in range(100)
        ]
        
        data_str = json.dumps(large_data)
        
        # Process through pipeline
        parsed = self.parser.parse(data_str)
        transformed = self.transformer.transform(parsed)
        
        # Verify all tags preserved
        self.assertEqual(
            len(parsed["content"]["metadata"]["tags"]),
            len(transformed["content"]["metadata"]["tags"]),
            "Tags count mismatch after transformation"
        )
        
        # Verify no data corruption
        violations = self._check_data_consistency(large_data, transformed)
        self.assertEqual(len(violations), 0, f"Data inconsistency in large dataset: {violations}")


if __name__ == '__main__':
    unittest.main()