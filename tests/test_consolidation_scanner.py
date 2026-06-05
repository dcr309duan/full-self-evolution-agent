import pytest
import tempfile
import os
import sys
import shutil
from pathlib import Path
from typing import List, Dict, Tuple

# Add the project root to the path so we can import the scanner
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the consolidation scanner (adjust import path as needed)
from consolidation_scanner import (
    ConsolidationScanner,
    DuplicateModule,
    MergePlan,
    DependencyConstraint,
    scan_for_duplicates,
    generate_merge_plan,
    validate_plan_constraints
)


@pytest.fixture
def temp_project_dir():
    """Create a temporary directory structure for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a project structure with multiple modules
        project_dir = Path(tmpdir) / "test_project"
        project_dir.mkdir()
        
        # Create subdirectories for different modules
        (project_dir / "module_a").mkdir()
        (project_dir / "module_b").mkdir()
        (project_dir / "module_c").mkdir()
        
        yield project_dir


def create_synthetic_duplicate_module(
    project_dir: Path,
    module_name: str,
    functions: List[str],
    classes: List[str],
    dependencies: List[str] = None
) -> Path:
    """Create a synthetic Python module with specified content."""
    module_path = project_dir / module_name / f"{module_name}.py"
    
    content = []
    
    # Add imports for dependencies
    if dependencies:
        for dep in dependencies:
            content.append(f"import {dep}")
    
    content.append("")
    
    # Add functions
    for func in functions:
        content.append(f"""
def {func}(x: int) -> int:
    \"\"\"{func} function.\"\"\"
    return x * 2
""")
    
    # Add classes
    for cls in classes:
        content.append(f"""
class {cls}:
    \"\"\"{cls} class.\"\"\"
    def __init__(self, value: int = 0):
        self.value = value
    
    def get_value(self) -> int:
        return self.value
""")
    
    module_path.write_text("\n".join(content))
    return module_path


def create_overlapping_modules(
    project_dir: Path,
    overlap_percentage: float = 0.9
) -> Tuple[Path, Path]:
    """Create two modules with a specified percentage of overlapping content."""
    # Create shared functions and classes
    shared_functions = [f"shared_func_{i}" for i in range(10)]
    shared_classes = [f"SharedClass_{i}" for i in range(5)]
    
    # Create unique functions for each module
    unique_functions_a = [f"unique_a_func_{i}" for i in range(2)]
    unique_functions_b = [f"unique_b_func_{i}" for i in range(2)]
    
    # Calculate overlap based on percentage
    overlap_count = int(len(shared_functions) * overlap_percentage)
    overlapping_funcs = shared_functions[:overlap_count]
    
    # Create module A
    module_a_path = create_synthetic_duplicate_module(
        project_dir, "module_a",
        functions=overlapping_funcs + unique_functions_a,
        classes=shared_classes[:3],
        dependencies=["os", "sys"]
    )
    
    # Create module B with overlapping content
    module_b_path = create_synthetic_duplicate_module(
        project_dir, "module_b",
        functions=overlapping_funcs + unique_functions_b,
        classes=shared_classes[:3],
        dependencies=["os", "json"]
    )
    
    return module_a_path, module_b_path


def create_dependent_modules(project_dir: Path) -> Dict[str, Path]:
    """Create modules with dependency relationships."""
    # Create base module
    base_path = create_synthetic_duplicate_module(
        project_dir, "module_base",
        functions=["base_function"],
        classes=["BaseClass"]
    )
    
    # Create dependent module
    dependent_path = create_synthetic_duplicate_module(
        project_dir, "module_dependent",
        functions=["dependent_function"],
        classes=["DependentClass"],
        dependencies=["module_base"]
    )
    
    # Create another module that depends on both
    combined_path = create_synthetic_duplicate_module(
        project_dir, "module_combined",
        functions=["combined_function"],
        classes=["CombinedClass"],
        dependencies=["module_base", "module_dependent"]
    )
    
    return {
        "base": base_path,
        "dependent": dependent_path,
        "combined": combined_path
    }


class TestConsolidationScanner:
    """Test suite for the ConsolidationScanner."""
    
    def test_scanner_initialization(self, temp_project_dir):
        """Test that the scanner initializes correctly."""
        scanner = ConsolidationScanner(temp_project_dir)
        assert scanner.project_dir == temp_project_dir
        assert scanner.duplicates == []
        assert scanner.merge_plans == []
    
    def test_scan_detects_duplicates(self, temp_project_dir):
        """Test that the scanner detects duplicate modules."""
        # Create overlapping modules
        create_overlapping_modules(temp_project_dir, overlap_percentage=0.9)
        
        scanner = ConsolidationScanner(temp_project_dir)
        duplicates = scanner.scan()
        
        # Should detect at least one duplicate pair
        assert len(duplicates) > 0
        
        # Verify the duplicate detection accuracy
        total_modules = len(list(temp_project_dir.glob("**/*.py")))
        detected_duplicates = len(duplicates)
        
        # With 90% overlap, we should detect most duplicates
        assert detected_duplicates >= 1  # At least one pair detected
    
    def test_scan_accuracy_high_overlap(self, temp_project_dir):
        """Test that scanner achieves >90% accuracy with high overlap."""
        # Create modules with 95% overlap
        create_overlapping_modules(temp_project_dir, overlap_percentage=0.95)
        
        scanner = ConsolidationScanner(temp_project_dir)
        duplicates = scanner.scan()
        
        # Calculate accuracy
        if len(duplicates) > 0:
            # Verify that detected duplicates have high similarity scores
            for dup in duplicates:
                assert dup.similarity_score >= 0.9, f"Similarity score {dup.similarity_score} < 0.9"
    
    def test_merge_plan_generation(self, temp_project_dir):
        """Test that merge plans are generated correctly."""
        # Create overlapping modules
        create_overlapping_modules(temp_project_dir, overlap_percentage=0.9)
        
        scanner = ConsolidationScanner(temp_project_dir)
        duplicates = scanner.scan()
        
        if len(duplicates) > 0:
            plans = scanner.generate_merge_plans(duplicates)
            
            # Verify plans have required fields
            for plan in plans:
                assert hasattr(plan, 'source_modules')
                assert hasattr(plan, 'target_module')
                assert hasattr(plan, 'merge_actions')
                assert hasattr(plan, 'dependency_constraints')
                
                # Verify source and target are different
                assert plan.source_modules != plan.target_module
    
    def test_merge_plan_respects_dependencies(self, temp_project_dir):
        """Test that merge plans respect dependency constraints."""
        # Create dependent modules
        modules = create_dependent_modules(temp_project_dir)
        
        scanner = ConsolidationScanner(temp_project_dir)
        duplicates = scanner.scan()
        
        if len(duplicates) > 0:
            plans = scanner.generate_merge_plans(duplicates)
            
            for plan in plans:
                # Validate that the plan respects dependencies
                is_valid = scanner.validate_plan_constraints(plan)
                assert is_valid, f"Plan {plan} violates dependency constraints"
    
    def test_delete_plan_generation(self, temp_project_dir):
        """Test that delete plans are generated for duplicate modules."""
        # Create overlapping modules
        create_overlapping_modules(temp_project_dir, overlap_percentage=0.9)
        
        scanner = ConsolidationScanner(temp_project_dir)
        duplicates = scanner.scan()
        
        if len(duplicates) > 0:
            delete_plans = scanner.generate_delete_plans(duplicates)
            
            # Verify delete plans
            for plan in delete_plans:
                assert hasattr(plan, 'modules_to_delete')
                assert hasattr(plan, 'backup_location')
                assert hasattr(plan, 'dependency_updates')
                
                # Verify we're not deleting modules that are depended upon
                for module in plan.modules_to_delete:
                    assert not scanner.is_module_dependency(module)
    
    def test_plan_validation(self, temp_project_dir):
        """Test that plan validation works correctly."""
        # Create dependent modules
        modules = create_dependent_modules(temp_project_dir)
        
        scanner = ConsolidationScanner(temp_project_dir)
        
        # Create a valid merge plan
        valid_plan = MergePlan(
            source_modules=["module_a", "module_b"],
            target_module="module_merged",
            merge_actions=[
                {"action": "merge", "source": "module_a", "target": "module_merged"},
                {"action": "merge", "source": "module_b", "target": "module_merged"}
            ],
            dependency_constraints=[
                DependencyConstraint(
                    module="module_dependent",
                    dependencies=["module_base"]
                )
            ]
        )
        
        # Validate the plan
        is_valid = scanner.validate_plan_constraints(valid_plan)
        assert is_valid
        
        # Create an invalid plan that violates dependencies
        invalid_plan = MergePlan(
            source_modules=["module_base"],
            target_module="module_merged",
            merge_actions=[
                {"action": "merge", "source": "module_base", "target": "module_merged"}
            ],
            dependency_constraints=[
                DependencyConstraint(
                    module="module_dependent",
                    dependencies=["module_base"]  # This would be broken
                )
            ]
        )
        
        # This should fail validation because module_dependent depends on module_base
        is_valid = scanner.validate_plan_constraints(invalid_plan)
        assert not is_valid
    
    def test_scan_with_no_duplicates(self, temp_project_dir):
        """Test that scanner handles projects with no duplicates."""
        # Create unique modules
        create_synthetic_duplicate_module(
            temp_project_dir, "module_unique_a",
            functions=["func_a1", "func_a2"],
            classes=["ClassA"]
        )
        create_synthetic_duplicate_module(
            temp_project_dir, "module_unique_b",
            functions=["func_b1", "func_b2"],
            classes=["ClassB"]
        )
        
        scanner = ConsolidationScanner(temp_project_dir)
        duplicates = scanner.scan()
        
        # Should detect no duplicates
        assert len(duplicates) == 0
    
    def test_merge_plan_execution(self, temp_project_dir):
        """Test that merge plans can be executed (simulated)."""
        # Create overlapping modules
        create_overlapping_modules(temp_project_dir, overlap_percentage=0.9)
        
        scanner = ConsolidationScanner(temp_project_dir)
        duplicates = scanner.scan()
        
        if len(duplicates) > 0:
            plans = scanner.generate_merge_plans(duplicates)
            
            for plan in plans:
                # Simulate plan execution
                result = scanner.execute_merge_plan(plan, dry_run=True)
                
                # Verify the result
                assert result.success
                assert result.dry_run
                assert len(result.actions_executed) > 0
    
    def test_delete_plan_execution(self, temp_project_dir):
        """Test that delete plans can be executed (simulated)."""
        # Create overlapping modules
        create_overlapping_modules(temp_project_dir, overlap_percentage=0.9)
        
        scanner = ConsolidationScanner(temp_project_dir)
        duplicates = scanner.scan()
        
        if len(duplicates) > 0:
            delete_plans = scanner.generate_delete_plans(duplicates)
            
            for plan in delete_plans:
                # Simulate plan execution
                result = scanner.execute_delete_plan(plan, dry_run=True)
                
                # Verify the result
                assert result.success
                assert result.dry_run
                assert len(result.modules_deleted) > 0
    
    def test_dependency_graph_construction(self, temp_project_dir):
        """Test that the dependency graph is constructed correctly."""
        # Create dependent modules
        create_dependent_modules(temp_project_dir)
        
        scanner = ConsolidationScanner(temp_project_dir)
        dependency_graph = scanner.build_dependency_graph()
        
        # Verify the graph structure
        assert "module_base" in dependency_graph
        assert "module_dependent" in dependency_graph
        assert "module_combined" in dependency_graph
        
        # Verify dependencies
        assert "module_base" in dependency_graph["module_dependent"]
        assert "module_base" in dependency_graph["module_combined"]
        assert "module_dependent" in dependency_graph["module_combined"]
    
    def test_accuracy_metric(self, temp_project_dir):
        """Test the accuracy metric calculation."""
        # Create modules with known overlap
        create_overlapping_modules(temp_project_dir, overlap_percentage=0.9)
        
        scanner = ConsolidationScanner(temp_project_dir)
        duplicates = scanner.scan()
        
        # Calculate accuracy
        accuracy = scanner.calculate_accuracy(duplicates)
        
        # With 90% overlap, accuracy should be > 90%
        assert accuracy > 0.9, f"Accuracy {accuracy} <= 0.9"
    
    def test_edge_case_empty_module(self, temp_project_dir):
        """Test scanner handles empty modules correctly."""
        # Create an empty module
        empty_module_path = temp_project_dir / "module_empty" / "module_empty.py"
        empty_module_path.parent.mkdir()
        empty_module_path.write_text("# Empty module\n")
        
        # Create a non-empty module
        create_synthetic_duplicate_module(
            temp_project_dir, "module_normal",
            functions=["func1"],
            classes=["Class1"]
        )
        
        scanner = ConsolidationScanner(temp_project_dir)
        duplicates = scanner.scan()
        
        # Empty modules should not cause errors
        assert isinstance(duplicates, list)
    
    def test_edge_case_single_file(self, temp_project_dir):
        """Test scanner handles single file projects."""
        # Create a single module
        create_synthetic_duplicate_module(
            temp_project_dir, "module_single",
            functions=["func1", "func2"],
            classes=["Class1"]
        )
        
        scanner = ConsolidationScanner(temp_project_dir)
        duplicates = scanner.scan()
        
        # Single module should not have duplicates
        assert len(duplicates) == 0
    
    def test_plan_rollback(self, temp_project_dir):
        """Test that plans can be rolled back."""
        # Create overlapping modules
        create_overlapping_modules(temp_project_dir, overlap_percentage=0.9)
        
        scanner = ConsolidationScanner(temp_project_dir)
        duplicates = scanner.scan()
        
        if len(duplicates) > 0:
            plans = scanner.generate_merge_plans(duplicates)
            
            for plan in plans:
                # Execute the plan
                result = scanner.execute_merge_plan(plan, dry_run=False)
                
                if result.success:
                    # Rollback the plan
                    rollback_result = scanner.rollback_plan(plan)
                    
                    # Verify rollback
                    assert rollback_result.success
                    assert rollback_result.modules_restored == len(plan.source_modules)


def test_integration_full_pipeline(temp_project_dir):
    """Integration test for the full consolidation pipeline."""
    # Setup: Create a realistic project structure
    modules = {}
    
    # Create module_a with overlapping content
    modules["module_a"] = create_synthetic_duplicate_module(
        temp_project_dir, "module_a",
        functions=["process_data", "validate_input", "format_output"],
        classes=["DataProcessor", "InputValidator"],
        dependencies=["os", "json"]
    )
    
    # Create module_b with significant overlap
    modules["module_b"] = create_synthetic_duplicate_module(
        temp_project_dir, "module_b",
        functions=["process_data", "validate_input", "transform_data"],
        classes=["DataProcessor", "OutputFormatter"],
        dependencies=["os", "csv"]
    )
    
    # Create module_c that depends on both
    modules["module_c"] = create_synthetic_duplicate_module(
        temp_project_dir, "module_c",
        functions=["run_pipeline"],
        classes=["PipelineRunner"],
        dependencies=["module_a", "module_b"]
    )
    
    # Initialize scanner
    scanner = ConsolidationScanner(temp_project_dir)
    
    # Step 1: Scan for duplicates
    duplicates = scanner.scan()
    assert len(duplicates) > 0, "Should detect duplicates"
    
    # Step 2: Generate merge plans
    merge_plans = scanner.generate_merge_plans(duplicates)
    assert len(merge_plans) > 0, "Should generate merge plans"
    
    # Step 3: Validate plans respect dependencies
    for plan in merge_plans:
        is_valid = scanner.validate_plan_constraints(plan)
        assert is_valid, f"Plan {plan} should be valid"
    
    # Step 4: Generate delete plans
    delete_plans = scanner.generate_delete_plans(duplicates)
    assert len(delete_plans) > 0, "Should generate delete plans"
    
    # Step 5: Calculate accuracy
    accuracy = scanner.calculate_accuracy(duplicates)
    assert accuracy > 0.9, f"Accuracy {accuracy} should be > 90%"
    
    # Step 6: Execute plans (dry run)
    for plan in merge_plans:
        result = scanner.execute_merge_plan(plan, dry_run=True)
        assert result.success, "Dry run should succeed"
    
    for plan in delete_plans:
        result = scanner.execute_delete_plan(plan, dry_run=True)
        assert result.success, "Dry run should succeed"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])