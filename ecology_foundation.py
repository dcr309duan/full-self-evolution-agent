import os
import json
import glob
from pathlib import Path

class TestSuiteManifest:
    """Scans and catalogs all test files in the project."""
    
    def __init__(self, root_dir="."):
        self.root_dir = Path(root_dir).resolve()
        self.test_files = []
        self.manifest = {}
        
    def scan(self):
        """Scan for test files (test_*.py or *_test.py) recursively."""
        patterns = ["**/test_*.py", "**/*_test.py"]
        files = set()
        for pattern in patterns:
            for f in glob.glob(str(self.root_dir / pattern), recursive=True):
                files.add(Path(f).resolve())
        self.test_files = sorted(files)
        self._build_manifest()
        return self.test_files
    
    def _build_manifest(self):
        """Build a catalog of test files with metadata."""
        self.manifest = {}
        for tf in self.test_files:
            rel_path = tf.relative_to(self.root_dir)
            self.manifest[str(rel_path)] = {
                "path": str(tf),
                "size": tf.stat().st_size if tf.exists() else 0,
                "module_name": tf.stem,
                "parent_dir": str(tf.parent)
            }
        return self.manifest
    
    def get_manifest(self):
        """Return the built manifest dictionary."""
        return self.manifest
    
    def save_manifest(self, output_path="test_manifest.json"):
        """Save manifest to a JSON file."""
        with open(output_path, "w") as f:
            json.dump(self.manifest, f, indent=2)
        return output_path
    
    def get_test_count(self):
        """Return the number of test files found."""
        return len(self.test_files)


class CoverageAnalyzer:
    """Parses test files to extract what they test by reading function names and docstrings."""
    
    def __init__(self, manifest=None):
        self.manifest = manifest or {}
        self.coverage_data = {}
        
    def analyze_file(self, filepath):
        """Analyze a single test file and extract tested functions/classes."""
        path = Path(filepath)
        if not path.exists():
            return {}
        
        content = path.read_text(encoding="utf-8", errors="replace")
        lines = content.split("\n")
        
        results = {
            "file": str(path),
            "test_functions": [],
            "tested_items": [],
            "docstrings": []
        }
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            # Detect test function definitions
            if stripped.startswith("def test_") and stripped.endswith(":"):
                func_name = stripped[4:-1].strip()  # Remove 'def ' and trailing ':'
                results["test_functions"].append(func_name)
                # Look for docstring in next lines
                docstring = self._extract_docstring(lines, i)
                if docstring:
                    results["docstrings"].append(docstring)
                    # Extract what is being tested from docstring
                    tested = self._parse_docstring(docstring)
                    results["tested_items"].extend(tested)
            # Also detect class-based tests
            elif stripped.startswith("class Test") and stripped.endswith(":"):
                class_name = stripped[6:-1].strip()
                results["test_functions"].append(f"class:{class_name}")
        
        return results
    
    def _extract_docstring(self, lines, start_idx):
        """Extract docstring following a function definition."""
        docstring = ""
        in_docstring = False
        quote_char = None
        
        for i in range(start_idx + 1, min(start_idx + 20, len(lines))):
            line = lines[i].strip()
            if not line:
                continue
            if not in_docstring:
                if line.startswith('"""') or line.startswith("'''"):
                    quote_char = line[:3]
                    remaining = line[3:]
                    if remaining.endswith(quote_char):
                        docstring = remaining[:-3]
                        break
                    else:
                        in_docstring = True
                        docstring = remaining
                elif line.startswith('"') or line.startswith("'"):
                    # Single-line docstring with single quotes
                    if line.count('"') >= 2 or line.count("'") >= 2:
                        docstring = line.strip('"').strip("'")
                        break
                continue
            else:
                if quote_char and quote_char in line:
                    end_idx = line.index(quote_char)
                    docstring += " " + line[:end_idx]
                    break
                else:
                    docstring += " " + line
        
        return docstring.strip() if docstring else ""
    
    def _parse_docstring(self, docstring):
        """Parse docstring to extract what is being tested."""
        tested = []
        lower = docstring.lower()
        
        # Common patterns
        keywords = ["test", "verify", "check", "ensure", "validate", "confirm"]
        for kw in keywords:
            if kw in lower:
                # Extract the sentence containing the keyword
                sentences = docstring.replace(".", "\n").split("\n")
                for sent in sentences:
                    if kw in sent.lower():
                        tested.append(sent.strip())
        
        # Look for references to functions/classes (CamelCase or snake_case)
        import re
        refs = re.findall(r'[A-Z][a-z]+(?:\.[a-zA-Z_]+)*|[a-z_]+(?:\.[a-z_]+)*', docstring)
        for ref in refs:
            if ref not in ["test", "the", "and", "for", "with", "that", "this"]:
                tested.append(ref)
        
        return list(set(tested))
    
    def analyze_all(self, file_list=None):
        """Analyze all files in the manifest or provided list."""
        if file_list is None:
            file_list = list(self.manifest.keys())
        
        for filepath in file_list:
            self.coverage_data[filepath] = self.analyze_file(filepath)
        
        return self.coverage_data
    
    def get_coverage_report(self):
        """Generate a summary coverage report."""
        report = {
            "total_files": len(self.coverage_data),
            "total_test_functions": 0,
            "total_tested_items": 0,
            "files": {}
        }
        
        for filepath, data in self.coverage_data.items():
            report["total_test_functions"] += len(data.get("test_functions", []))
            report["total_tested_items"] += len(data.get("tested_items", []))
            report["files"][filepath] = {
                "test_count": len(data.get("test_functions", [])),
                "tested_count": len(data.get("tested_items", [])),
                "tested_items": data.get("tested_items", [])
            }
        
        return report
    
    def save_report(self, output_path="coverage_report.json"):
        """Save coverage report to JSON."""
        report = self.get_coverage_report()
        with open(output_path, "w") as f:
            json.dump(report, f, indent=2)
        return output_path


class PressureRegistry:
    """Holds a list of environmental pressures as simple string descriptions."""
    
    def __init__(self):
        self.pressures = []
        self.categories = {}
        
    def register_pressure(self, description, category="general"):
        """Register a new environmental pressure."""
        pressure = {
            "id": len(self.pressures),
            "description": description,
            "category": category
        }
        self.pressures.append(pressure)
        if category not in self.categories:
            self.categories[category] = []
        self.categories[category].append(pressure)
        return pressure
    
    def register_pressures(self, pressure_list):
        """Register multiple pressures from a list of strings or dicts."""
        for item in pressure_list:
            if isinstance(item, str):
                self.register_pressure(item)
            elif isinstance(item, dict):
                self.register_pressure(
                    item.get("description", ""),
                    item.get("category", "general")
                )
    
    def get_pressures(self, category=None):
        """Get pressures, optionally filtered by category."""
        if category:
            return self.categories.get(category, [])
        return self.pressures
    
    def get_categories(self):
        """Return list of all categories."""
        return list(self.categories.keys())
    
    def remove_pressure(self, pressure_id):
        """Remove a pressure by its ID."""
        self.pressures = [p for p in self.pressures if p["id"] != pressure_id]
        # Rebuild categories
        self.categories = {}
        for p in self.pressures:
            cat = p["category"]
            if cat not in self.categories:
                self.categories[cat] = []
            self.categories[cat].append(p)
    
    def clear(self):
        """Remove all pressures."""
        self.pressures = []
        self.categories = {}
    
    def count(self, category=None):
        """Return the number of pressures, optionally filtered."""
        if category:
            return len(self.categories.get(category, []))
        return len(self.pressures)
    
    def save(self, output_path="pressures.json"):
        """Save pressures to a JSON file."""
        data = {
            "pressures": self.pressures,
            "categories": {k: [p["id"] for p in v] for k, v in self.categories.items()}
        }
        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)
        return output_path
    
    def load(self, input_path="pressures.json"):
        """Load pressures from a JSON file."""
        with open(input_path, "r") as f:
            data = json.load(f)
        self.pressures = data.get("pressures", [])
        self.categories = {}
        for p in self.pressures:
            cat = p.get("category", "general")
            if cat not in self.categories:
                self.categories[cat] = []
            self.categories[cat].append(p)
        return self


class EnvironmentalPressureGenerator:
    """Analyzes current test suite coverage gaps and generates new environmental pressures."""
    
    def __init__(self, manifest=None, analyzer=None, registry=None):
        """Initialize with optional TestSuiteManifest, CoverageAnalyzer, and PressureRegistry instances."""
        self.manifest = manifest
        self.analyzer = analyzer
        self.registry = registry
        self.generated_pressures = []
        
    def generate_pressure(self):
        """Create a new test file with a basic passing test.
        
        Returns:
            Path to the generated test file.
        """
        test_content = '''"""Basic test for EnvironmentalPressureGenerator."""
import os
import sys
import tempfile
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ecology_foundation import EnvironmentalPressureGenerator


class TestEnvironmentalPressureGenerator:
    """Test class for EnvironmentalPressureGenerator."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.generator = EnvironmentalPressureGenerator()
    
    def test_generator_creation(self):
        """Test that the generator can be created."""
        assert self.generator is not None
        assert isinstance(self.generator, EnvironmentalPressureGenerator)
    
    def test_generate_pressure(self):
        """Test that generate_pressure creates a test file."""
        result = self.generator.generate_pressure()
        assert result is not None
        assert Path(result).exists()
        # Clean up
        Path(result).unlink()
    
    def test_scan_coverage_gaps(self):
        """Test that scan_coverage_gaps returns a list."""
        gaps = self.generator.scan_coverage_gaps()
        assert isinstance(gaps, list)
'''
        # Create the test file
        test_dir = Path("test_generated")
        test_dir.mkdir(exist_ok=True)
        test_file = test_dir / "test_environmental_pressure_generator.py"
        test_file.write_text(test_content, encoding="utf-8")
        return str(test_file)
    
    def scan_coverage_gaps(self):
        """Identify which modules lack tests.
        
        Returns:
            List of module names that lack test coverage.
        """
        gaps = []
        
        # Define expected modules that should have tests
        expected_modules = [
            "TestSuiteManifest",
            "CoverageAnalyzer", 
            "PressureRegistry",
            "EnvironmentalPressureGenerator",
            "TestSuiteMutator"
        ]
        
        # Check if test files exist for each module
        for module in expected_modules:
            test_file = Path(f"test_{module.lower()}.py")
            if not test_file.exists():
                gaps.append(module)
        
        return gaps
    
    def analyze_coverage_gaps(self):
        """Analyze the current test suite to identify coverage gaps.
        
        Returns:
            List of dicts describing coverage gaps found.
        """
        coverage_report = self.analyzer.get_coverage_report() if self.analyzer else {"files": {}}
        gaps = []
        
        # Check for files with no test functions
        for filepath, file_data in coverage_report.get("files", {}).items():
            if file_data.get("test_count", 0) == 0:
                gaps.append({
                    "file": filepath,
                    "type": "missing_tests",
                    "description": f"No test functions found in {filepath}",
                    "severity": "high"
                })
            
            # Check for files with low tested item count
            if file_data.get("tested_count", 0) < 3 and file_data.get("test_count", 0) > 0:
                gaps.append({
                    "file": filepath,
                    "type": "low_coverage",
                    "description": f"Low coverage in {filepath}: only {file_data.get('tested_count', 0)} tested items",
                    "severity": "medium"
                })
        
        # Check for missing categories in the registry
        if self.registry:
            existing_categories = self.registry.get_categories()
            expected_categories = ["general", "performance", "security", "integration", "unit"]
            for cat in expected_categories:
                if cat not in existing_categories:
                    gaps.append({
                        "file": "registry",
                        "type": "missing_category",
                        "description": f"Missing pressure category: {cat}",
                        "severity": "low"
                    })
        
        return gaps
    
    def generate_pressure(self, name, description, severity, category):
        """Generate a new pressure as a structured object and register it.
        
        Args:
            name: Short name for the pressure
            description: Detailed description of the pressure
            severity: Severity level (low, medium, high, critical)
            category: Category for the pressure
            
        Returns:
            The registered pressure object
        """
        pressure_obj = {
            "name": name,
            "description": description,
            "severity": severity,
            "category": category
        }
        
        # Register in the PressureRegistry if available
        if self.registry:
            registered = self.registry.register_pressure(
                description=description,
                category=category
            )
            # Add additional metadata to the registered pressure
            registered["name"] = name
            registered["severity"] = severity
            self.generated_pressures.append(registered)
            return registered
        
        self.generated_pressures.append(pressure_obj)
        return pressure_obj
    
    def generate_pressures_from_gaps(self):
        """Generate new pressures based on identified coverage gaps.
        
        Returns:
            List of generated pressure objects
        """
        gaps = self.analyze_coverage_gaps()
        new_pressures = []
        
        for gap in gaps:
            gap_type = gap.get("type", "unknown")
            severity = gap.get("severity", "medium")
            description = gap.get("description", "Unknown coverage gap")
            file_path = gap.get("file", "unknown")
            
            if gap_type == "missing_tests":
                name = f"CoverageGap_{file_path.replace('/', '_').replace('.', '_')}"
                pressure = self.generate_pressure(
                    name=name,
                    description=f"Missing test coverage for {file_path}: {description}",
                    severity=severity,
                    category="coverage_gap"
                )
                new_pressures.append(pressure)
                
            elif gap_type == "low_coverage":
                name = f"LowCoverage_{file_path.replace('/', '_').replace('.', '_')}"
                pressure = self.generate_pressure(
                    name=name,
                    description=f"Insufficient test coverage in {file_path}: {description}",
                    severity=severity,
                    category="coverage_improvement"
                )
                new_pressures.append(pressure)
                
            elif gap_type == "missing_category":
                name = f"MissingCategory_{description.split(':')[-1].strip()}"
                pressure = self.generate_pressure(
                    name=name,
                    description=f"Missing pressure category: {description}",
                    severity=severity,
                    category="registry_enhancement"
                )
                new_pressures.append(pressure)
        
        return new_pressures
    
    def generate_pressures_from_manifest(self):
        """Generate pressures based on manifest analysis.
        
        Returns:
            List of generated pressure objects
        """
        manifest = self.manifest.get_manifest() if self.manifest else {}
        new_pressures = []
        
        # Generate pressures for each test file found
        for filepath, file_info in manifest.items():
            module_name = file_info.get("module_name", "unknown")
            parent_dir = file_info.get("parent_dir", "unknown")
            
            # Create a pressure to ensure this test file is maintained
            name = f"MaintainTest_{module_name}"
            pressure = self.generate_pressure(
                name=name,
                description=f"Ensure test file {filepath} remains up-to-date and covers all relevant code paths",
                severity="medium",
                category="test_maintenance"
            )
            new_pressures.append(pressure)
            
            # Create a pressure to expand coverage in this area
            name = f"ExpandCoverage_{module_name}"
            pressure = self.generate_pressure(
                name=name,
                description=f"Expand test coverage in {parent_dir} by adding more test cases for {module_name}",
                severity="low",
                category="coverage_expansion"
            )
            new_pressures.append(pressure)
        
        return new_pressures
    
    def generate_all_pressures(self):
        """Generate all possible pressures from all analysis sources.
        
        Returns:
            List of all generated pressure objects
        """
        all_pressures = []
        
        # Generate from coverage gaps
        gap_pressures = self.generate_pressures_from_gaps()
        all_pressures.extend(gap_pressures)
        
        # Generate from manifest
        manifest_pressures = self.generate_pressures_from_manifest()
        all_pressures.extend(manifest_pressures)
        
        # Generate some default environmental pressures that don't yet exist
        default_pressures = [
            {
                "name": "TestQualityImprovement",
                "description": "Test quality should be maintained or improved over time",
                "severity": "high",
                "category": "quality"
            },
            {
                "name": "CoverageIncrease",
                "description": "Test coverage must increase over time to reduce risk",
                "severity": "high",
                "category": "coverage"
            },
            {
                "name": "PerformanceRegression",
                "description": "Test execution time should not regress significantly",
                "severity": "medium",
                "category": "performance"
            },
            {
                "name": "NewFeatureCoverage",
                "description": "New features should have corresponding test coverage",
                "severity": "high",
                "category": "coverage"
            },
            {
                "name": "SecurityTesting",
                "description": "Security-critical code paths should have dedicated tests",
                "severity": "critical",
                "category": "security"
            }
        ]
        
        # Only add default pressures if they don't already exist
        existing_descriptions = {p.get("description") for p in self.registry.get_pressures()} if self.registry else set()
        for dp in default_pressures:
            if dp["description"] not in existing_descriptions:
                pressure = self.generate_pressure(
                    name=dp["name"],
                    description=dp["description"],
                    severity=dp["severity"],
                    category=dp["category"]
                )
                all_pressures.append(pressure)
        
        return all_pressures
    
    def get_generated_pressures(self):
        """Return the list of pressures generated by this instance."""
        return self.generated_pressures
    
    def save_generated_pressures(self, output_path="generated_pressures.json"):
        """Save generated pressures to a JSON file."""
        data = {
            "generated_pressures": self.generated_pressures,
            "total_generated": len(self.generated_pressures)
        }
        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)
        return output_path


class TestSuiteMutator:
    """Generates new test files based on pressures from the PressureRegistry."""
    
    def __init__(self, manifest):
        """Initialize with a TestSuiteManifest instance."""
        self.manifest = manifest
        self.registry = PressureRegistry()
        
    def set_registry(self, registry):
        """Set the PressureRegistry to use for generating tests."""
        self.registry = registry
        return self
    
    def generate_test_file(self, pressure_id, output_dir=None):
        """Generate a new test file for a given pressure from the registry.
        
        Args:
            pressure_id: The ID of the pressure to test
            output_dir: Optional directory to write the file (default: root_dir/test_generated)
            
        Returns:
            Path to the generated test file, or None if pressure not found
        """
        # Find the pressure
        pressure = None
        for p in self.registry.get_pressures():
            if p["id"] == pressure_id:
                pressure = p
                break
        
        if pressure is None:
            return None
        
        # Determine output directory
        if output_dir is None:
            output_dir = self.manifest.root_dir / "test_generated"
        else:
            output_dir = Path(output_dir)
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Create a safe filename from the pressure description
        safe_name = pressure["description"].lower().replace(" ", "_")
        safe_name = "".join(c for c in safe_name if c.isalnum() or c == "_")
        if not safe_name:
            safe_name = f"pressure_{pressure_id}"
        
        filename = f"test_{safe_name}.py"
        filepath = output_dir / filename
        
        # Generate the test file content
        content = self._generate_test_content(pressure)
        
        # Write the file
        filepath.write_text(content, encoding="utf-8")
        
        return filepath
    
    def _generate_test_content(self, pressure):
        """Generate the Python source code for a test file."""
        description = pressure["description"]
        category = pressure["category"]
        pressure_id = pressure["id"]
        
        # Create a safe function name
        func_name = "test_" + "".join(c if c.isalnum() else "_" for c in description.lower())
        func_name = func_name.strip("_")
        if not func_name:
            func_name = f"test_pressure_{pressure_id}"
        
        # Build the test content
        content = f'''"""Test for pressure: {description}"""
import os
import sys
import json
import tempfile
from pathlib import Path


# Import from ecology_foundation
from ecology_foundation import (
    TestSuiteManifest,
    CoverageAnalyzer,
    PressureRegistry,
    TestSuiteMutator,
    EnvironmentalPressureGenerator,
    create_default_foundation
)


class Test{description.replace(" ", "").replace("-", "_").replace(".", "_")}:
    """Test class for pressure: {description}"""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.foundation = create_default_foundation()
        self.manifest = self.foundation["manifest"]
        self.analyzer = self.foundation["analyzer"]
        self.registry = self.foundation["registry"]
        self.mutator = TestSuiteMutator(self.manifest)
        self.mutator.set_registry(self.registry)
    
    def {func_name}(self):
        """Test that the pressure '{description}' is properly handled."""
        # Verify the pressure exists in the registry
        pressures = self.registry.get_pressures(category="{category}")
        matching = [p for p in pressures if p["id"] == {pressure_id}]
        assert len(matching) > 0, f"Pressure with id {pressure_id} not found in category '{category}'"
        
        # Verify the mutator can generate a test for this pressure
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.mutator.generate_test_file({pressure_id}, output_dir=tmpdir)
            assert result is not None, "Failed to generate test file"
            assert result.exists(), f"Generated test file does not exist: {result}"
            
            # Verify the generated file has proper imports
            content = result.read_text(encoding="utf-8")
            assert "from ecology_foundation import" in content, "Missing import from ecology_foundation"
            assert "import os" in content, "Missing import os"
            assert "import sys" in content, "Missing import sys"
            assert "import json" in content, "Missing import json"
            assert "from pathlib import Path" in content, "Missing import Path"
            
            # Verify the generated file contains the pressure description
            assert description in content, f"Generated test does not mention pressure description: {description}"
            
            # Verify the generated file can be imported without errors
            sys.path.insert(0, tmpdir)
            try:
                module_name = result.stem
                import importlib
                module = importlib.import_module(module_name)
                assert hasattr(module, f"Test{description.replace(' ', '').replace('-', '_').replace('.', '_')}"), "Generated module missing test class"
            finally:
                sys.path.pop(0)
                # Clean up any imported modules
                if module_name in sys.modules:
                    del sys.modules[module_name]
    
    def test_pressure_registry_integration(self):
        """Test that the pressure registry integrates with the mutator."""
        # Register a new pressure
        new_pressure = self.registry.register_pressure(
            "Custom pressure for integration test",
            category="integration"
        )
        
        # Verify it was registered
        assert self.registry.count(category="integration") > 0
        
        # Generate a test for it
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.mutator.generate_test_file(new_pressure["id"], output_dir=tmpdir)
            assert result is not None, "Failed to generate test for new pressure"
            assert result.exists(), "Generated test file does not exist"
            
            # Verify the generated test references the new pressure
            content = result.read_text(encoding="utf-8")
            assert "Custom pressure for integration test" in content, "Generated test missing pressure description"
        
        # Clean up
        self.registry.remove_pressure(new_pressure["id"])
        assert self.registry.count(category="integration") == 0
'''
        return content
    
    def generate_all_tests(self, output_dir=None):
        """Generate test files for all registered pressures.
        
        Args:
            output_dir: Optional directory to write files
            
        Returns:
            List of generated file paths
        """
        generated = []
        for pressure in self.registry.get_pressures():
            filepath = self.generate_test_file(pressure["id"], output_dir)
            if filepath:
                generated.append(filepath)
        return generated


# Convenience function to create a full foundation with defaults
def create_default_foundation(root_dir="."):
    """Create a default ecology foundation with all components initialized."""
    manifest = TestSuiteManifest(root_dir)
    manifest.scan()
    
    analyzer = CoverageAnalyzer(manifest.get_manifest())
    analyzer.analyze_all()
    
    registry = PressureRegistry()
    # Register some default pressures
    registry.register_pressures([
        "Test coverage must increase over time",
        "New tests should cover untested code paths",
        "Test quality should be maintained or improved",
        "Test execution time should not regress"
    ])
    
    return {
        "manifest": manifest,
        "analyzer": analyzer,
        "registry": registry
    }


if __name__ == "__main__":
    # Quick self-test when run directly
    foundation = create_default_foundation()
    print(f"Found {foundation['manifest'].get_test_count()} test files")
    report = foundation['analyzer'].get_coverage_report()
    print(f"Analyzed {report['total_files']} files with {report['total_test_functions']} test functions")
    print(f"Registered {foundation['registry'].count()} environmental pressures")
    
    # Test the mutator
    mutator = TestSuiteMutator(foundation["manifest"])
    mutator.set_registry(foundation["registry"])
    
    # Generate a test for the first pressure
    if foundation["registry"].count() > 0:
        first_pressure = foundation["registry"].get_pressures()[0]
        result = mutator.generate_test_file(first_pressure["id"])
        if result:
            print(f"Generated test file: {result}")
        else:
            print("Failed to generate test file")
    
    # Test the EnvironmentalPressureGenerator
    print("\nTesting EnvironmentalPressureGenerator...")
    generator = EnvironmentalPressureGenerator(
        foundation["manifest"],
        foundation["analyzer"],
        foundation["registry"]
    )
    
    # Analyze coverage gaps
    gaps = generator.analyze_coverage_gaps()
    print(f"Found {len(gaps)} coverage gaps")
    
    # Generate pressures from gaps
    gap_pressures = generator.generate_pressures_from_gaps()
    print(f"Generated {len(gap_pressures)} pressures from gaps")
    
    # Generate all pressures
    all_pressures = generator.generate_all_pressures()
    print(f"Generated {len(all_pressures)} total pressures")
    
    # Save generated pressures
    generator.save_generated_pressures()
    print("Saved generated pressures to generated_pressures.json")