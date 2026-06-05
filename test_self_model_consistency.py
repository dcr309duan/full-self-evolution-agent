import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
import tempfile
import shutil
import json

# Import the modules to test - adjust imports based on actual project structure
from self_model_validator import SelfModelValidator
from dependency_graph import DependencyGraph
from orchestrator import Orchestrator

class TestSelfModelConsistency:
    """Comprehensive tests for self-model consistency checking."""
    
    @pytest.fixture
    def temp_project_dir(self):
        """Create a temporary project directory with sample files."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def sample_function_file(self, temp_project_dir):
        """Create a sample Python file with a function."""
        file_path = temp_project_dir / "sample_module.py"
        file_path.write_text("""
def original_function(param1: int, param2: str) -> bool:
    return True

def another_function():
    pass
""")
        return file_path
    
    @pytest.fixture
    def sample_schema_file(self, temp_project_dir):
        """Create a sample schema file."""
        file_path = temp_project_dir / "schema.py"
        file_path.write_text("""
from pydantic import BaseModel

class UserSchema(BaseModel):
    id: int
    name: str
    email: str
    age: int
""")
        return file_path
    
    @pytest.fixture
    def dependency_graph(self, temp_project_dir):
        """Create a dependency graph for testing."""
        graph = DependencyGraph()
        # Add some initial dependencies
        graph.add_dependency("module_a", "module_b")
        graph.add_dependency("module_b", "module_c")
        graph.add_dependency("module_a", "module_c")
        return graph
    
    @pytest.fixture
    def validator(self, temp_project_dir):
        """Create a validator instance."""
        return SelfModelValidator(project_root=temp_project_dir)
    
    @pytest.fixture
    def orchestrator(self, temp_project_dir):
        """Create an orchestrator instance."""
        return Orchestrator(project_root=temp_project_dir)
    
    def test_function_signature_change_detection(self, validator, sample_function_file):
        """Test that validator catches function signature changes."""
        # Simulate original function signature
        original_signature = {
            "name": "original_function",
            "parameters": ["param1: int", "param2: str"],
            "return_type": "bool"
        }
        
        # Simulate modified function signature (parameter removed)
        modified_signature = {
            "name": "original_function",
            "parameters": ["param1: int"],  # param2 removed
            "return_type": "bool"
        }
        
        # Register the original signature
        validator.register_function_signature("sample_module", original_signature)
        
        # Simulate the change
        with patch.object(validator, 'get_current_function_signatures') as mock_get:
            mock_get.return_value = {"sample_module": [modified_signature]}
            
            # Run validation
            violations = validator.check_function_signature_consistency()
            
            # Assert that a violation is detected
            assert len(violations) > 0
            assert any("original_function" in str(v) for v in violations)
            assert any("signature" in str(v).lower() for v in violations)
    
    def test_schema_field_removal_detection(self, validator, sample_schema_file):
        """Test that schema field removal is flagged as critical mismatch."""
        # Simulate original schema
        original_schema = {
            "name": "UserSchema",
            "fields": ["id: int", "name: str", "email: str", "age: int"]
        }
        
        # Simulate modified schema (email field removed)
        modified_schema = {
            "name": "UserSchema",
            "fields": ["id: int", "name: str", "age: int"]  # email removed
        }
        
        # Register the original schema
        validator.register_schema("schema", original_schema)
        
        # Simulate the change
        with patch.object(validator, 'get_current_schemas') as mock_get:
            mock_get.return_value = {"schema": [modified_schema]}
            
            # Run validation
            violations = validator.check_schema_consistency()
            
            # Assert that a critical violation is detected
            assert len(violations) > 0
            assert any("UserSchema" in str(v) for v in violations)
            assert any("field" in str(v).lower() for v in violations)
            assert any("email" in str(v) for v in violations)
            # Check that it's flagged as critical
            assert any(getattr(v, 'severity', '') == 'critical' or 
                      'critical' in str(v).lower() for v in violations)
    
    def test_dependency_graph_update_after_modifications(self, dependency_graph, temp_project_dir):
        """Test that dependency graph updates correctly after file modifications."""
        # Create initial files
        module_a = temp_project_dir / "module_a.py"
        module_b = temp_project_dir / "module_b.py"
        module_c = temp_project_dir / "module_c.py"
        
        module_a.write_text("from module_b import func_b")
        module_b.write_text("from module_c import func_c")
        module_c.write_text("def func_c(): pass")
        
        # Update dependency graph based on initial state
        dependency_graph.update_from_filesystem(temp_project_dir)
        
        # Verify initial dependencies
        assert dependency_graph.has_dependency("module_a", "module_b")
        assert dependency_graph.has_dependency("module_b", "module_c")
        
        # Simulate file modification: module_a now depends on module_c directly
        module_a.write_text("from module_c import func_c")
        
        # Update dependency graph
        dependency_graph.update_from_filesystem(temp_project_dir)
        
        # Verify updated dependencies
        assert dependency_graph.has_dependency("module_a", "module_c")
        # module_a should no longer depend on module_b
        assert not dependency_graph.has_dependency("module_a", "module_b")
        
        # Simulate file deletion
        module_b.unlink()
        dependency_graph.update_from_filesystem(temp_project_dir)
        
        # Verify that module_b is removed from graph
        assert "module_b" not in dependency_graph.get_all_nodes()
    
    def test_orchestrator_rollback_integration(self, orchestrator, temp_project_dir):
        """Test integration with orchestrator rollback mechanism."""
        # Create a file to track changes
        test_file = temp_project_dir / "test_file.py"
        test_file.write_text("""
def stable_function():
    return "original"
""")
        
        # Create a backup of the original state
        original_content = test_file.read_text()
        orchestrator.create_backup(str(test_file))
        
        # Simulate a change that should trigger rollback
        test_file.write_text("""
def stable_function(new_param: str):  # Signature changed
    return "modified"
""")
        
        # Simulate validation failure
        with patch.object(orchestrator, 'validate_changes') as mock_validate:
            mock_validate.return_value = {
                "status": "failure",
                "violations": [
                    {"type": "signature_change", "severity": "critical"}
                ]
            }
            
            # Attempt to apply changes
            result = orchestrator.apply_changes_with_validation(str(test_file))
            
            # Assert that rollback was triggered
            assert result["rollback_performed"] == True
            assert result["status"] == "rolled_back"
            
            # Verify file content was restored
            restored_content = test_file.read_text()
            assert restored_content == original_content
    
    def test_complete_workflow_with_rollback(self, orchestrator, validator, temp_project_dir):
        """Test complete workflow: change, validation failure, and rollback."""
        # Setup initial state
        schema_file = temp_project_dir / "models.py"
        schema_file.write_text("""
from pydantic import BaseModel

class Product(BaseModel):
    id: int
    name: str
    price: float
""")
        
        # Register the schema with validator
        validator.register_schema("models", {
            "name": "Product",
            "fields": ["id: int", "name: str", "price: float"]
        })
        
        # Create backup
        orchestrator.create_backup(str(schema_file))
        original_content = schema_file.read_text()
        
        # Simulate a change that removes a field
        schema_file.write_text("""
from pydantic import BaseModel

class Product(BaseModel):
    id: int
    name: str
    # price field removed
""")
        
        # Run validation
        with patch.object(validator, 'get_current_schemas') as mock_get:
            mock_get.return_value = {"models": [{
                "name": "Product",
                "fields": ["id: int", "name: str"]  # price removed
            }]}
            
            violations = validator.check_schema_consistency()
            
            # Simulate orchestrator detecting violation and triggering rollback
            if any("critical" in str(v).lower() for v in violations):
                orchestrator.rollback(str(schema_file))
                
                # Verify rollback
                restored_content = schema_file.read_text()
                assert restored_content == original_content
                assert "price" in restored_content
    
    def test_multiple_changes_and_rollback(self, orchestrator, temp_project_dir):
        """Test rollback with multiple file changes."""
        files = {}
        original_contents = {}
        
        # Create multiple files
        for i in range(3):
            file_path = temp_project_dir / f"file_{i}.py"
            content = f"def func_{i}(): return {i}"
            file_path.write_text(content)
            files[f"file_{i}"] = file_path
            original_contents[f"file_{i}"] = content
            orchestrator.create_backup(str(file_path))
        
        # Modify all files
        for i, file_path in files.items():
            file_path.write_text(f"def func_{i}(new_param): return {i + 10}")
        
        # Simulate validation failure for all changes
        with patch.object(orchestrator, 'validate_changes') as mock_validate:
            mock_validate.return_value = {
                "status": "failure",
                "violations": [{"type": "multiple_changes", "severity": "critical"}]
            }
            
            # Attempt to apply all changes
            result = orchestrator.apply_batch_changes([str(p) for p in files.values()])
            
            # Assert rollback of all files
            assert result["rollback_performed"] == True
            for i, file_path in files.items():
                assert file_path.read_text() == original_contents[i]