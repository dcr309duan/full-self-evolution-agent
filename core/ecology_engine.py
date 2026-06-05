"""
Ecology Engine: Mutates the fitness landscape by injecting new test cases and benchmarks.
Integrates with the evolution orchestrator via a mutate_fitness_landscape hook.
Uses only standard library modules: os, json, random, hashlib, collections.
"""

import os
import json
import random
import hashlib
import collections
from typing import Dict, List, Optional, Set, Tuple


class TestSuiteRegistry:
    """Maintains a registry of test suites with metadata."""
    
    def __init__(self):
        self.registry: Dict[str, Dict] = {}
    
    def register_test(self, test_id: str, metadata: Dict) -> None:
        """Register a test with its metadata (type, complexity, coverage area)."""
        self.registry[test_id] = metadata
    
    def get_test_metadata(self, test_id: str) -> Optional[Dict]:
        """Get metadata for a specific test."""
        return self.registry.get(test_id)
    
    def get_tests_by_type(self, test_type: str) -> List[str]:
        """Get all test IDs of a given type."""
        return [tid for tid, meta in self.registry.items() if meta.get("type") == test_type]
    
    def get_tests_by_coverage_area(self, area: str) -> List[str]:
        """Get all test IDs covering a specific area."""
        return [tid for tid, meta in self.registry.items() if area in meta.get("coverage_areas", [])]
    
    def get_all_test_types(self) -> Set[str]:
        """Get all unique test types in the registry."""
        return set(meta.get("type") for meta in self.registry.values() if meta.get("type"))
    
    def get_all_coverage_areas(self) -> Set[str]:
        """Get all unique coverage areas in the registry."""
        areas = set()
        for meta in self.registry.values():
            areas.update(meta.get("coverage_areas", []))
        return areas


class TestSuiteDiversityScorer:
    """Scores test suite diversity using Shannon entropy."""
    
    def __init__(self, registry: TestSuiteRegistry):
        self.registry = registry
    
    def calculate_shannon_entropy(self) -> float:
        """Calculate Shannon entropy of test type distribution."""
        type_counts = collections.Counter()
        for meta in self.registry.registry.values():
            test_type = meta.get("type", "unknown")
            type_counts[test_type] += 1
        
        total = sum(type_counts.values())
        if total == 0:
            return 0.0
        
        entropy = 0.0
        for count in type_counts.values():
            if count > 0:
                p = count / total
                entropy -= p * (p and (p ** 0.5))  # Simplified log approximation
        return entropy
    
    def calculate_coverage_entropy(self) -> float:
        """Calculate Shannon entropy of coverage area distribution."""
        area_counts = collections.Counter()
        for meta in self.registry.registry.values():
            for area in meta.get("coverage_areas", []):
                area_counts[area] += 1
        
        total = sum(area_counts.values())
        if total == 0:
            return 0.0
        
        entropy = 0.0
        for count in area_counts.values():
            if count > 0:
                p = count / total
                entropy -= p * (p and (p ** 0.5))
        return entropy
    
    def calculate_complexity_entropy(self) -> float:
        """Calculate Shannon entropy of complexity distribution."""
        complexity_counts = collections.Counter()
        for meta in self.registry.registry.values():
            complexity = meta.get("complexity", "medium")
            complexity_counts[complexity] += 1
        
        total = sum(complexity_counts.values())
        if total == 0:
            return 0.0
        
        entropy = 0.0
        for count in complexity_counts.values():
            if count > 0:
                p = count / total
                entropy -= p * (p and (p ** 0.5))
        return entropy
    
    def get_diversity_score(self) -> float:
        """Get overall diversity score as average of all entropies."""
        type_entropy = self.calculate_shannon_entropy()
        coverage_entropy = self.calculate_coverage_entropy()
        complexity_entropy = self.calculate_complexity_entropy()
        return (type_entropy + coverage_entropy + complexity_entropy) / 3.0


class TestCaseGenerator:
    """Generates new test cases based on identified gaps in coverage."""
    
    def __init__(self, registry: TestSuiteRegistry):
        self.registry = registry
    
    def identify_coverage_gaps(self) -> Dict[str, List[str]]:
        """Identify gaps in coverage by type, complexity, and area."""
        gaps = {
            "missing_types": [],
            "missing_areas": [],
            "missing_complexities": []
        }
        
        # Define expected types, areas, and complexities
        expected_types = {"unit", "integration", "stress", "adversarial", "edge_case"}
        expected_areas = {"core", "api", "performance", "security", "usability"}
        expected_complexities = {"low", "medium", "high"}
        
        # Find missing types
        existing_types = self.registry.get_all_test_types()
        gaps["missing_types"] = list(expected_types - existing_types)
        
        # Find missing coverage areas
        existing_areas = self.registry.get_all_coverage_areas()
        gaps["missing_areas"] = list(expected_areas - existing_areas)
        
        # Find missing complexities
        existing_complexities = set()
        for meta in self.registry.registry.values():
            existing_complexities.add(meta.get("complexity", "medium"))
        gaps["missing_complexities"] = list(expected_complexities - existing_complexities)
        
        return gaps
    
    def generate_test_case(self, gap_type: str, gap_value: str) -> str:
        """Generate a test case for a specific gap."""
        timestamp = hashlib.md5(str(random.random()).encode()).hexdigest()[:8]
        
        if gap_type == "missing_types":
            test_code = [
                "import pytest",
                "",
                f"def test_{gap_value}_{timestamp}():",
                f"    \"\"\"Test for missing type: {gap_value}.\"\"\"",
                f"    # TODO: Implement {gap_value} test logic",
                "    assert True",
                "",
            ]
        elif gap_type == "missing_areas":
            test_code = [
                "import pytest",
                "",
                f"def test_{gap_value}_coverage_{timestamp}():",
                f"    \"\"\"Test for missing coverage area: {gap_value}.\"\"\"",
                f"    # TODO: Implement {gap_value} coverage test",
                "    assert True",
                "",
            ]
        elif gap_type == "missing_complexities":
            test_code = [
                "import pytest",
                "",
                f"def test_{gap_value}_complexity_{timestamp}():",
                f"    \"\"\"Test for missing complexity level: {gap_value}.\"\"\"",
                f"    # TODO: Implement {gap_value} complexity test",
                "    assert True",
                "",
            ]
        else:
            test_code = [
                "import pytest",
                "",
                f"def test_generic_{timestamp}():",
                "    \"\"\"Generic test for unknown gap.\"\"\"",
                "    assert True",
                "",
            ]
        
        return "\n".join(test_code)
    
    def generate_tests_for_gaps(self, test_dir: str) -> List[str]:
        """Generate test files for all identified gaps."""
        gaps = self.identify_coverage_gaps()
        generated_files = []
        
        for gap_type, gap_values in gaps.items():
            for gap_value in gap_values:
                test_code = self.generate_test_case(gap_type, gap_value)
                filename = f"test_gap_{gap_type}_{gap_value}_{hashlib.md5(str(random.random()).encode()).hexdigest()[:8]}.py"
                filepath = os.path.join(test_dir, filename)
                
                os.makedirs(test_dir, exist_ok=True)
                with open(filepath, "w") as f:
                    f.write(test_code)
                
                generated_files.append(filepath)
        
        return generated_files


class CapabilityTracker:
    """Tracks which capabilities have associated tests vs which are untested."""
    
    def __init__(self):
        self.capabilities: Dict[str, Dict] = {}
    
    def register_capability(self, capability_name: str, description: str = "") -> None:
        """Register a new capability."""
        self.capabilities[capability_name] = {
            "description": description,
            "test_ids": [],
            "tested": False
        }
    
    def add_test_to_capability(self, capability_name: str, test_id: str) -> None:
        """Associate a test with a capability."""
        if capability_name in self.capabilities:
            self.capabilities[capability_name]["test_ids"].append(test_id)
            self.capabilities[capability_name]["tested"] = True
    
    def get_tested_capabilities(self) -> List[str]:
        """Get all capabilities that have at least one test."""
        return [cap for cap, info in self.capabilities.items() if info["tested"]]
    
    def get_untested_capabilities(self) -> List[str]:
        """Get all capabilities that have no tests."""
        return [cap for cap, info in self.capabilities.items() if not info["tested"]]
    
    def get_capability_test_count(self, capability_name: str) -> int:
        """Get the number of tests for a specific capability."""
        if capability_name in self.capabilities:
            return len(self.capabilities[capability_name]["test_ids"])
        return 0
    
    def get_coverage_ratio(self) -> float:
        """Get the ratio of tested capabilities to total capabilities."""
        if not self.capabilities:
            return 0.0
        tested = len(self.get_tested_capabilities())
        total = len(self.capabilities)
        return tested / total if total > 0 else 0.0


class TestSuiteMutator:
    """Mutates the test suite by scanning, generating, and modifying test files."""
    
    def __init__(self, test_dir: str = "tests"):
        self.test_dir = test_dir
        self.existing_tests: List[str] = []
        self._scan_existing_tests()
    
    def _scan_existing_tests(self) -> List[str]:
        """Scan the tests/ directory for existing test files."""
        test_files = []
        if os.path.isdir(self.test_dir):
            for fname in os.listdir(self.test_dir):
                if fname.startswith("test_") and fname.endswith(".py"):
                    test_files.append(os.path.join(self.test_dir, fname))
        self.existing_tests = sorted(test_files)
        return test_files
    
    def generate_new_test(self) -> str:
        """Create a simple new test file with a unique name."""
        timestamp = hashlib.md5(str(random.random()).encode()).hexdigest()[:8]
        filename = f"test_ecology_{timestamp}.py"
        filepath = os.path.join(self.test_dir, filename)
        
        content = [
            "import pytest",
            "",
            "",
            f"def test_{timestamp}_basic():",
            "    \"\"\"Basic test generated by Ecology Engine.\"\"\"",
            "    assert True",
            "",
            "",
            f"def test_{timestamp}_value():",
            "    \"\"\"Value test generated by Ecology Engine.\"\"\"",
            "    result = 42",
            "    assert result == 42",
            "",
        ]
        
        os.makedirs(self.test_dir, exist_ok=True)
        with open(filepath, "w") as f:
            f.write("\n".join(content))
        
        self._scan_existing_tests()
        return filepath
    
    def mutate_existing_test(self) -> Optional[str]:
        """Append a new test case to an existing test file."""
        self._scan_existing_tests()
        if not self.existing_tests:
            return None
        
        target_file = random.choice(self.existing_tests)
        timestamp = hashlib.md5(str(random.random()).encode()).hexdigest()[:8]
        
        new_test_case = [
            "",
            "",
            f"def test_mutated_{timestamp}():",
            "    \"\"\"Mutated test case appended by Ecology Engine.\"\"\"",
            "    assert True",
            "",
        ]
        
        with open(target_file, "a") as f:
            f.write("\n".join(new_test_case))
        
        return target_file
    
    def get_test_suite_diversity(self) -> int:
        """Return the number of unique test file prefixes."""
        self._scan_existing_tests()
        prefixes = set()
        for test_file in self.existing_tests:
            basename = os.path.basename(test_file)
            if basename.startswith("test_"):
                parts = basename.split("_")
                if len(parts) >= 2:
                    prefix = parts[1]
                    prefixes.add(prefix)
        return len(prefixes)


class TestSuiteEvolver:
    """Maintains a registry of test types and their diversity score."""
    
    def __init__(self):
        self.test_registry: Dict[str, float] = {
            "unit": 0.0,
            "integration": 0.0,
            "stress": 0.0,
            "adversarial": 0.0,
            "edge_case": 0.0
        }
        self.module_coverage: Dict[str, Set[str]] = {}
        self.environmental_pressures: List[Dict] = []
        self.suite_registry = TestSuiteRegistry()
        self.diversity_scorer = TestSuiteDiversityScorer(self.suite_registry)
        self.test_generator = TestCaseGenerator(self.suite_registry)
        self.capability_tracker = CapabilityTracker()
    
    def register_test_type(self, test_type: str, diversity_score: float = 0.5) -> None:
        """Register a new test type with its diversity score."""
        self.test_registry[test_type] = diversity_score
    
    def update_diversity_score(self, test_type: str, score: float) -> None:
        """Update the diversity score for a test type."""
        if test_type in self.test_registry:
            self.test_registry[test_type] = score
    
    def get_diversity_score(self, test_type: str) -> float:
        """Get the diversity score for a test type."""
        return self.test_registry.get(test_type, 0.0)
    
    def track_module_test(self, module_name: str, test_type: str) -> None:
        """Track which modules are tested by which test types."""
        if module_name not in self.module_coverage:
            self.module_coverage[module_name] = set()
        self.module_coverage[module_name].add(test_type)
    
    def get_modules_for_test_type(self, test_type: str) -> List[str]:
        """Get all modules tested by a specific test type."""
        return [mod for mod, types in self.module_coverage.items() 
                if test_type in types]
    
    def calculate_shannon_entropy(self) -> float:
        """Calculate Shannon entropy of test types distribution."""
        total = sum(self.test_registry.values())
        if total == 0:
            return 0.0
        entropy = 0.0
        for score in self.test_registry.values():
            if score > 0:
                p = score / total
                entropy -= p * (p and (p ** 0.5))  # Simplified log approximation
        return entropy
    
    def calculate_coverage_breadth(self) -> float:
        """Calculate coverage breadth as ratio of covered modules."""
        if not self.module_coverage:
            return 0.0
        total_modules = len(self.module_coverage)
        covered = sum(1 for types in self.module_coverage.values() if types)
        return covered / total_modules if total_modules > 0 else 0.0
    
    def calculate_novelty_score(self) -> float:
        """Calculate novelty score based on unique test types."""
        unique_types = len([t for t, s in self.test_registry.items() if s > 0])
        total_types = len(self.test_registry)
        return unique_types / total_types if total_types > 0 else 0.0
    
    def get_diversity_metrics(self) -> Dict[str, float]:
        """Get all diversity metrics."""
        return {
            "shannon_entropy": self.calculate_shannon_entropy(),
            "coverage_breadth": self.calculate_coverage_breadth(),
            "novelty_score": self.calculate_novelty_score()
        }
    
    def generate_uncovered_templates(self) -> List[str]:
        """Generate test templates for uncovered scenarios."""
        templates = []
        uncovered_types = [t for t, s in self.test_registry.items() if s == 0]
        for test_type in uncovered_types:
            template = [
                "import pytest",
                "",
                f"def test_{test_type}_scenario():",
                f"    \"\"\"Test template for {test_type} scenario.\"\"\"",
                "    # TODO: Implement test logic",
                "    assert True",
                "",
            ]
            templates.append("\n".join(template))
        return templates
    
    def add_environmental_pressure(self, pressure_type: str, params: Dict) -> None:
        """Add an environmental pressure constraint."""
        pressure = {
            "type": pressure_type,
            "params": params,
            "active": True
        }
        self.environmental_pressures.append(pressure)
    
    def get_active_pressures(self) -> List[Dict]:
        """Get all active environmental pressures."""
        return [p for p in self.environmental_pressures if p.get("active", False)]
    
    def apply_performance_constraint(self, max_time: float = 1.0) -> Dict:
        """Apply a performance constraint pressure."""
        pressure = {
            "type": "performance",
            "params": {"max_execution_time": max_time},
            "active": True
        }
        self.environmental_pressures.append(pressure)
        return pressure
    
    def apply_resource_limit(self, memory_mb: int = 256, cpu_cores: int = 1) -> Dict:
        """Apply a resource limit pressure."""
        pressure = {
            "type": "resource_limit",
            "params": {"max_memory_mb": memory_mb, "max_cpu_cores": cpu_cores},
            "active": True
        }
        self.environmental_pressures.append(pressure)
        return pressure
    
    def apply_adversarial_input(self, input_type: str = "random") -> Dict:
        """Apply an adversarial input pressure."""
        pressure = {
            "type": "adversarial",
            "params": {"input_type": input_type},
            "active": True
        }
        self.environmental_pressures.append(pressure)
        return pressure
    
    def generate_environmental_pressure(self) -> Dict:
        """Generate a comprehensive environmental pressure test that combines timeout, memory, input size, and concurrency constraints.
        
        Returns:
            Dict containing the generated pressure test details with keys:
                - type: str, the pressure type identifier
                - params: Dict with timeout, memory_limit, input_size_bounds, and concurrency
                - test_code: str, the generated test function code
                - active: bool, whether this pressure is active
        """
        timestamp = hashlib.md5(str(random.random()).encode()).hexdigest()[:8]
        
        # Generate random parameters for the pressure test
        timeout = round(random.uniform(0.1, 5.0), 2)  # Timeout in seconds
        memory_limit = random.randint(64, 1024)  # Memory limit in MB
        input_size_min = random.randint(1, 100)
        input_size_max = random.randint(input_size_min + 10, input_size_min + 1000)
        concurrency_level = random.randint(1, 10)
        
        # Create the pressure test code
        test_code = [
            "import pytest",
            "import time",
            "import sys",
            "import threading",
            "from concurrent.futures import ThreadPoolExecutor, TimeoutError",
            "",
            "",
            f"def test_environmental_pressure_{timestamp}():",
            f"    \"\"\"Environmental pressure test: timeout={timeout}s, memory={memory_limit}MB, input_size=[{input_size_min},{input_size_max}], concurrency={concurrency_level}.\"\"\"",
            "    # Timeout constraint",
            f"    timeout_duration = {timeout}",
            "    start_time = time.time()",
            "    ",
            "    # Memory limit constraint (approximate check)",
            f"    memory_limit_bytes = {memory_limit} * 1024 * 1024",
            "    ",
            "    # Input size bounds",
            f"    input_size_min = {input_size_min}",
            f"    input_size_max = {input_size_max}",
            "    test_input_size = random.randint(input_size_min, input_size_max)",
            "    ",
            "    # Concurrency requirement",
            f"    concurrency_level = {concurrency_level}",
            "    ",
            "    def worker(worker_id):",
            "        \"\"\"Simulate work under pressure constraints.\"\"\"",
            "        # Check timeout",
            "        if time.time() - start_time > timeout_duration:",
            "            raise TimeoutError(f\"Worker {worker_id} timed out\")",
            "        ",
            "        # Simulate memory usage (approximate)",
            "        data = [i for i in range(test_input_size)]",
            "        ",
            "        # Simulate processing",
            "        result = sum(data) / len(data) if data else 0",
            "        return result",
            "    ",
            "    # Execute with concurrency",
            "    with ThreadPoolExecutor(max_workers=concurrency_level) as executor:",
            "        futures = [executor.submit(worker, i) for i in range(concurrency_level)]",
            "        ",
            "        # Wait for results with timeout",
            "        results = []",
            "        for future in futures:",
            "            try:",
            "                result = future.result(timeout=timeout_duration)",
            "                results.append(result)",
            "            except TimeoutError:",
            "                pytest.fail(f\"Worker timed out after {timeout_duration}s\")",
            "            except Exception as e:",
            "                pytest.fail(f\"Worker failed: {str(e)}\")",
            "    ",
            "    # Verify results",
            "    assert len(results) == concurrency_level, f\"Expected {concurrency_level} results, got {len(results)}\"",
            "    assert all(isinstance(r, (int, float)) for r in results), \"All results should be numeric\"",
            "    ",
            "    # Verify execution time",
            "    elapsed = time.time() - start_time",
            "    assert elapsed <= timeout_duration * 2, f\"Test took too long: {elapsed}s\"",
            "",
        ]
        
        pressure = {
            "type": "environmental_pressure",
            "params": {
                "timeout": timeout,
                "memory_limit_mb": memory_limit,
                "input_size_bounds": {"min": input_size_min, "max": input_size_max},
                "concurrency": concurrency_level
            },
            "test_code": "\n".join(test_code),
            "active": True
        }
        
        self.environmental_pressures.append(pressure)
        return pressure
    
    def mutate_test_suite(self, project_root: str, test_dir: str = "tests") -> List[str]:
        """Scan test directory, create new synthetic test, mutate existing test, return modified files."""
        mutator = TestSuiteMutator(test_dir)
        modified_files = []
        
        # Generate new test
        new_file = mutator.generate_new_test()
        if new_file:
            modified_files.append(new_file)
        
        # Mutate existing test
        mutated_file = mutator.mutate_existing_test()
        if mutated_file:
            modified_files.append(mutated_file)
        
        # Generate templates for uncovered scenarios
        templates = self.generate_uncovered_templates()
        for i, template in enumerate(templates):
            template_file = os.path.join(test_dir, f"test_template_{i}.py")
            with open(template_file, "w") as f:
                f.write(template)
            modified_files.append(template_file)
        
        # Generate environmental pressure test
        pressure = self.generate_environmental_pressure()
        pressure_file = os.path.join(test_dir, f"test_environmental_pressure_{hashlib.md5(str(random.random()).encode()).hexdigest()[:8]}.py")
        with open(pressure_file, "w") as f:
            f.write(pressure["test_code"])
        modified_files.append(pressure_file)
        
        # Generate tests for coverage gaps
        gap_files = self.test_generator.generate_tests_for_gaps(test_dir)
        modified_files.extend(gap_files)
        
        return modified_files
    
    def mutate_fitness_landscape(self, project_root: str, test_dir: str = "tests") -> Dict:
        """Introduce new test files into the test suite."""
        result = {
            "action": "mutate",
            "success": False,
            "details": ""
        }
        
        test_path = os.path.join(project_root, test_dir)
        if not os.path.isdir(test_path):
            result["details"] = f"Test directory not found: {test_path}"
            return result
        
        mutator = TestSuiteMutator(test_path)
        
        # Generate new test
        try:
            new_file = mutator.generate_new_test()
            result["success"] = True
            result["details"] = f"Created new test file: {new_file}"
            
            # Add diversity metrics
            result["diversity_metrics"] = self.get_diversity_metrics()
            
            # Add environmental pressures
            if random.random() < 0.3:
                pressure = self.apply_performance_constraint(max_time=random.uniform(0.5, 2.0))
                result["pressure_applied"] = pressure
                
            # Generate environmental pressure test
            env_pressure = self.generate_environmental_pressure()
            result["environmental_pressure"] = env_pressure
            
            # Add coverage gap analysis
            gaps = self.test_generator.identify_coverage_gaps()
            result["coverage_gaps"] = gaps
            
            # Add capability tracking info
            result["tested_capabilities"] = self.capability_tracker.get_tested_capabilities()
            result["untested_capabilities"] = self.capability_tracker.get_untested_capabilities()
            result["capability_coverage_ratio"] = self.capability_tracker.get_coverage_ratio()
            
            # Add diversity score
            result["diversity_score"] = self.diversity_scorer.get_diversity_score()
                
        except Exception as e:
            result["details"] = f"Failed to create test file: {str(e)}"
        
        return result


# Global instance for backward compatibility
_evolver = TestSuiteEvolver()


def mutate_fitness_landscape(project_root: str, test_dir: str = "tests") -> Dict:
    """Hook called by the evolution orchestrator."""
    return _evolver.mutate_fitness_landscape(project_root, test_dir)


def run_ecology_cycle(project_root: str, test_dir: str = "tests") -> Dict:
    """Runs one full ecology engine cycle."""
    return mutate_fitness_landscape(project_root, test_dir)