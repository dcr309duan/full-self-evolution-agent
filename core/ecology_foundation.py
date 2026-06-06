"""
core/ecology_foundation.py - Foundation module for ecology-based test suite management.

Provides base classes and a registry for managing ecological pressures on test suites.
Uses only standard library imports (os, json, hashlib) with zero external dependencies.
"""

import os
import sys
import json
import copy
import random
import logging
import hashlib
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s'))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# Enums and Constants
# ---------------------------------------------------------------------------

class PressureType(Enum):
    """Types of ecological pressures that can be applied to test suites."""
    COMPLEXITY = "complexity"
    COVERAGE = "coverage"
    PERFORMANCE = "performance"
    STABILITY = "stability"
    MUTATION = "mutation"
    DEPENDENCY = "dependency"
    RESOURCE = "resource"
    CUSTOM = "custom"

class SeverityLevel(Enum):
    """Severity levels for ecological pressures."""
    LOW = 0.1
    MEDIUM = 0.5
    HIGH = 0.8
    CRITICAL = 1.0

# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------

@dataclass
class EcologyPressure:
    """
    Represents an ecological pressure to be applied to a test suite.
    
    Attributes:
        type: PressureType enum indicating the kind of pressure.
        severity: Float between 0.0 and 1.0 indicating intensity.
        target_metric: String name of the metric to target (e.g., 'coverage', 'execution_time').
        description: Optional human-readable description.
        parameters: Optional dict of additional parameters for custom pressures.
    """
    type: PressureType
    severity: float
    target_metric: str
    description: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        # Clamp severity to [0.0, 1.0]
        self.severity = max(0.0, min(1.0, self.severity))
        if isinstance(self.type, str):
            try:
                self.type = PressureType(self.type)
            except ValueError:
                self.type = PressureType.CUSTOM
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            'type': self.type.value,
            'severity': self.severity,
            'target_metric': self.target_metric,
            'description': self.description,
            'parameters': self.parameters
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EcologyPressure':
        """Deserialize from dictionary."""
        return cls(
            type=data.get('type', 'custom'),
            severity=data.get('severity', 0.5),
            target_metric=data.get('target_metric', ''),
            description=data.get('description', ''),
            parameters=data.get('parameters', {})
        )


@dataclass
class TestSuiteInfo:
    """
    Information about a registered test suite.
    
    Attributes:
        name: Unique name for the test suite.
        path: Filesystem path to the test suite directory or file.
        test_count: Number of individual tests.
        metadata: Arbitrary metadata dictionary.
        fitness_score: Current fitness score (0.0 to 1.0).
        last_pressure: Last applied pressure (if any).
    """
    name: str
    path: str
    test_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    fitness_score: float = 1.0
    last_pressure: Optional[EcologyPressure] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            'name': self.name,
            'path': self.path,
            'test_count': self.test_count,
            'metadata': self.metadata,
            'fitness_score': self.fitness_score,
            'last_pressure': self.last_pressure.to_dict() if self.last_pressure else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TestSuiteInfo':
        """Deserialize from dictionary."""
        last_pressure = None
        if data.get('last_pressure'):
            last_pressure = EcologyPressure.from_dict(data['last_pressure'])
        return cls(
            name=data.get('name', ''),
            path=data.get('path', ''),
            test_count=data.get('test_count', 0),
            metadata=data.get('metadata', {}),
            fitness_score=data.get('fitness_score', 1.0),
            last_pressure=last_pressure
        )


@dataclass
class FitnessLandscape:
    """
    Represents the fitness landscape of a test suite ecosystem.
    
    Attributes:
        dimension_names: Names of the dimensions in the landscape.
        dimension_values: Current values for each dimension.
        fitness_scores: Historical fitness scores.
        timestamp: When this landscape snapshot was taken.
    """
    dimension_names: List[str] = field(default_factory=list)
    dimension_values: Dict[str, float] = field(default_factory=dict)
    fitness_scores: List[float] = field(default_factory=list)
    timestamp: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            'dimension_names': self.dimension_names,
            'dimension_values': self.dimension_values,
            'fitness_scores': self.fitness_scores,
            'timestamp': self.timestamp
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FitnessLandscape':
        """Deserialize from dictionary."""
        return cls(
            dimension_names=data.get('dimension_names', []),
            dimension_values=data.get('dimension_values', {}),
            fitness_scores=data.get('fitness_scores', []),
            timestamp=data.get('timestamp', 0.0)
        )

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class TestSuiteRegistry:
    """
    Registry of existing test suites that can be modified by ecological pressures.
    
    Provides methods to register, unregister, query, and persist test suites.
    """
    
    def __init__(self, registry_path: Optional[str] = None):
        self._suites: Dict[str, TestSuiteInfo] = {}
        self._registry_path = registry_path
        if registry_path and os.path.exists(registry_path):
            self._load_from_disk()
    
    def register(self, suite: TestSuiteInfo) -> bool:
        """Register a test suite. Returns True if successful."""
        if suite.name in self._suites:
            logger.warning(f"Test suite '{suite.name}' already registered. Overwriting.")
        self._suites[suite.name] = suite
        self._save_to_disk()
        return True
    
    def unregister(self, name: str) -> bool:
        """Unregister a test suite by name. Returns True if existed."""
        if name in self._suites:
            del self._suites[name]
            self._save_to_disk()
            return True
        return False
    
    def get(self, name: str) -> Optional[TestSuiteInfo]:
        """Get a test suite by name."""
        return self._suites.get(name)
    
    def list_suites(self) -> List[str]:
        """List all registered test suite names."""
        return list(self._suites.keys())
    
    def get_all(self) -> List[TestSuiteInfo]:
        """Get all registered test suites."""
        return list(self._suites.values())
    
    def update_fitness(self, name: str, score: float) -> bool:
        """Update the fitness score of a test suite."""
        suite = self._suites.get(name)
        if suite:
            suite.fitness_score = max(0.0, min(1.0, score))
            self._save_to_disk()
            return True
        return False
    
    def clear(self) -> None:
        """Clear all registered test suites."""
        self._suites.clear()
        self._save_to_disk()
    
    def _save_to_disk(self) -> None:
        """Persist registry to disk if path is set."""
        if not self._registry_path:
            return
        try:
            data = {name: suite.to_dict() for name, suite in self._suites.items()}
            os.makedirs(os.path.dirname(self._registry_path) or '.', exist_ok=True)
            with open(self._registry_path, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save registry to {self._registry_path}: {e}")
    
    def _load_from_disk(self) -> None:
        """Load registry from disk."""
        if not self._registry_path or not os.path.exists(self._registry_path):
            return
        try:
            with open(self._registry_path, 'r') as f:
                data = json.load(f)
            for name, suite_data in data.items():
                self._suites[name] = TestSuiteInfo.from_dict(suite_data)
            logger.info(f"Loaded {len(self._suites)} test suites from registry.")
        except Exception as e:
            logger.error(f"Failed to load registry from {self._registry_path}: {e}")


# ---------------------------------------------------------------------------
# TestSuiteEvolver class
# ---------------------------------------------------------------------------

class TestSuiteEvolver:
    """
    Scans test files and evolves test suites based on ecological pressures.
    Uses only standard library imports.
    """
    
    def __init__(self, registry: Optional[TestSuiteRegistry] = None):
        self.registry = registry or TestSuiteRegistry()
        self._scan_cache: Dict[str, Dict[str, Any]] = {}
    
    def scan_test_file(self, file_path: str) -> Dict[str, Any]:
        """
        Scan a test file and extract metadata.
        
        Args:
            file_path: Path to the test file.
            
        Returns:
            Dictionary with file metadata (test_count, functions, classes, etc.)
        """
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return {'error': f"File not found: {file_path}"}
        
        # Use file hash as cache key
        file_hash = self._compute_file_hash(file_path)
        if file_path in self._scan_cache and self._scan_cache[file_path].get('hash') == file_hash:
            return self._scan_cache[file_path]
        
        try:
            with open(file_path, 'r') as f:
                content = f.read()
        except Exception as e:
            logger.error(f"Failed to read file {file_path}: {e}")
            return {'error': str(e)}
        
        # Simple parsing to count test functions and classes
        lines = content.split('\n')
        test_functions = []
        test_classes = []
        imports = []
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            # Detect test functions
            if stripped.startswith('def test_') or stripped.startswith('def _test_'):
                func_name = stripped.split('(')[0].replace('def ', '').strip()
                test_functions.append({'name': func_name, 'line': i + 1})
            # Detect test classes
            if stripped.startswith('class Test') or stripped.startswith('class _Test'):
                class_name = stripped.split(':')[0].replace('class ', '').strip().split('(')[0].strip()
                test_classes.append({'name': class_name, 'line': i + 1})
            # Detect imports
            if stripped.startswith('import ') or stripped.startswith('from '):
                imports.append(stripped)
        
        result = {
            'hash': file_hash,
            'file_path': file_path,
            'file_size': os.path.getsize(file_path),
            'test_count': len(test_functions),
            'test_functions': test_functions,
            'test_classes': test_classes,
            'imports': imports,
            'line_count': len(lines)
        }
        
        self._scan_cache[file_path] = result
        return result
    
    def scan_directory(self, directory_path: str, pattern: str = "test_*.py") -> List[Dict[str, Any]]:
        """
        Scan a directory for test files matching a pattern.
        
        Args:
            directory_path: Path to the directory.
            pattern: Glob pattern for test files.
            
        Returns:
            List of scan results for each matching file.
        """
        if not os.path.isdir(directory_path):
            logger.error(f"Directory not found: {directory_path}")
            return []
        
        results = []
        for root, dirs, files in os.walk(directory_path):
            for file in files:
                if file.startswith('test_') and file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    scan_result = self.scan_test_file(file_path)
                    if 'error' not in scan_result:
                        results.append(scan_result)
        
        return results
    
    def evolve_suite(self, suite_name: str, pressure: Optional[EcologyPressure] = None) -> Dict[str, Any]:
        """
        Evolve a test suite by applying ecological pressure.
        
        Args:
            suite_name: Name of the registered test suite.
            pressure: Optional pressure to apply.
            
        Returns:
            Dictionary with evolution results.
        """
        suite = self.registry.get(suite_name)
        if not suite:
            return {'success': False, 'error': f"Suite '{suite_name}' not found"}
        
        # Scan the suite's test files
        scan_results = self.scan_directory(suite.path) if os.path.isdir(suite.path) else []
        if not scan_results:
            scan_results = [self.scan_test_file(suite.path)] if os.path.isfile(suite.path) else []
        
        # Apply pressure effects
        if pressure:
            impact = pressure.severity * 0.3
            suite.fitness_score = max(0.0, min(1.0, suite.fitness_score - impact))
            suite.last_pressure = pressure
        
        return {
            'success': True,
            'suite_name': suite_name,
            'fitness_score': suite.fitness_score,
            'test_files_scanned': len(scan_results),
            'total_tests': sum(r.get('test_count', 0) for r in scan_results)
        }
    
    def _compute_file_hash(self, file_path: str) -> str:
        """Compute SHA256 hash of a file."""
        hasher = hashlib.sha256()
        try:
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b''):
                    hasher.update(chunk)
        except Exception:
            return ""
        return hasher.hexdigest()


# ---------------------------------------------------------------------------
# PressureGenerator class
# ---------------------------------------------------------------------------

class PressureGenerator:
    """
    Creates new test scenarios and generates ecological pressures.
    Uses only standard library imports.
    """
    
    def __init__(self, seed: Optional[int] = None):
        self._rng = random.Random(seed) if seed is not None else random.Random()
        self._generated_pressures: List[EcologyPressure] = []
    
    def generate_pressure(self, 
                          pressure_type: Optional[PressureType] = None,
                          severity: Optional[float] = None,
                          target_metric: Optional[str] = None) -> EcologyPressure:
        """
        Generate a new ecological pressure.
        
        Args:
            pressure_type: Optional specific type. If None, random.
            severity: Optional specific severity. If None, random.
            target_metric: Optional specific metric. If None, random.
            
        Returns:
            A new EcologyPressure instance.
        """
        if pressure_type is None:
            pressure_type = self._rng.choice(list(PressureType))
        
        if severity is None:
            severity = self._rng.uniform(0.1, 1.0)
        
        if target_metric is None:
            metrics = ['coverage', 'execution_time', 'memory_usage', 'complexity', 'stability']
            target_metric = self._rng.choice(metrics)
        
        pressure = EcologyPressure(
            type=pressure_type,
            severity=severity,
            target_metric=target_metric,
            description=f"Generated pressure: {pressure_type.value} on {target_metric}",
            parameters={'generated': True, 'seed': self._rng.random()}
        )
        
        self._generated_pressures.append(pressure)
        return pressure
    
    def generate_test_scenario(self, base_path: str, scenario_name: str) -> Dict[str, Any]:
        """
        Generate a new test scenario file.
        
        Args:
            base_path: Directory where the scenario file will be created.
            scenario_name: Name of the scenario.
            
        Returns:
            Dictionary with scenario generation results.
        """
        os.makedirs(base_path, exist_ok=True)
        file_path = os.path.join(base_path, f"scenario_{scenario_name}.py")
        
        # Generate a simple test scenario
        test_code = f'''"""
Auto-generated test scenario: {scenario_name}
"""
import unittest

class TestScenario{scenario_name.capitalize()}(unittest.TestCase):
    """Test scenario generated by PressureGenerator."""
    
    def test_scenario_basic(self):
        """Basic test for scenario {scenario_name}."""
        self.assertTrue(True)
    
    def test_scenario_edge_case(self):
        """Edge case test for scenario {scenario_name}."""
        self.assertIsNotNone(None)
    
    def test_scenario_performance(self):
        """Performance test for scenario {scenario_name}."""
        result = sum(range(1000))
        self.assertEqual(result, 499500)

if __name__ == '__main__':
    unittest.main()
'''
        
        try:
            with open(file_path, 'w') as f:
                f.write(test_code)
            logger.info(f"Generated test scenario: {file_path}")
            return {
                'success': True,
                'file_path': file_path,
                'scenario_name': scenario_name
            }
        except Exception as e:
            logger.error(f"Failed to generate scenario: {e}")
            return {'success': False, 'error': str(e)}
    
    def generate_pressure_batch(self, count: int = 5) -> List[EcologyPressure]:
        """
        Generate a batch of random pressures.
        
        Args:
            count: Number of pressures to generate.
            
        Returns:
            List of EcologyPressure instances.
        """
        return [self.generate_pressure() for _ in range(count)]
    
    def get_generated_pressures(self) -> List[EcologyPressure]:
        """Get list of all pressures generated by this instance."""
        return list(self._generated_pressures)
    
    def clear_generated(self) -> None:
        """Clear the list of generated pressures."""
        self._generated_pressures.clear()


# ---------------------------------------------------------------------------
# FitnessLandscapeModifier class
# ---------------------------------------------------------------------------

class FitnessLandscapeModifier:
    """
    Adds or removes test requirements and modifies the fitness landscape.
    Uses only standard library imports.
    """
    
    def __init__(self, registry: Optional[TestSuiteRegistry] = None):
        self.registry = registry or TestSuiteRegistry()
        self._landscapes: Dict[str, FitnessLandscape] = {}
        self._requirements: Dict[str, List[str]] = {}
    
    def add_requirement(self, suite_name: str, requirement: str) -> bool:
        """
        Add a requirement to a test suite.
        
        Args:
            suite_name: Name of the registered test suite.
            requirement: Requirement string to add.
            
        Returns:
            True if requirement was added successfully.
        """
        suite = self.registry.get(suite_name)
        if not suite:
            logger.error(f"Suite '{suite_name}' not found")
            return False
        
        if suite_name not in self._requirements:
            self._requirements[suite_name] = []
        
        if requirement not in self._requirements[suite_name]:
            self._requirements[suite_name].append(requirement)
            logger.info(f"Added requirement '{requirement}' to suite '{suite_name}'")
            
            # Update fitness landscape
            landscape = self._landscapes.get(suite_name, FitnessLandscape())
            if 'requirements' not in landscape.dimension_names:
                landscape.dimension_names.append('requirements')
            landscape.dimension_values['requirements'] = len(self._requirements[suite_name])
            self._landscapes[suite_name] = landscape
        
        return True
    
    def remove_requirement(self, suite_name: str, requirement: str) -> bool:
        """
        Remove a requirement from a test suite.
        
        Args:
            suite_name: Name of the registered test suite.
            requirement: Requirement string to remove.
            
        Returns:
            True if requirement was removed successfully.
        """
        if suite_name not in self._requirements:
            logger.warning(f"No requirements found for suite '{suite_name}'")
            return False
        
        if requirement in self._requirements[suite_name]:
            self._requirements[suite_name].remove(requirement)
            logger.info(f"Removed requirement '{requirement}' from suite '{suite_name}'")
            
            # Update fitness landscape
            landscape = self._landscapes.get(suite_name, FitnessLandscape())
            landscape.dimension_values['requirements'] = len(self._requirements[suite_name])
            self._landscapes[suite_name] = landscape
            return True
        
        return False
    
    def get_requirements(self, suite_name: str) -> List[str]:
        """Get all requirements for a test suite."""
        return list(self._requirements.get(suite_name, []))
    
    def modify_fitness_landscape(self, suite_name: str, 
                                  dimension: str, 
                                  value: float) -> bool:
        """
        Modify a dimension of the fitness landscape for a test suite.
        
        Args:
            suite_name: Name of the registered test suite.
            dimension: Dimension name to modify.
            value: New value for the dimension.
            
        Returns:
            True if modification was successful.
        """
        suite = self.registry.get(suite_name)
        if not suite:
            logger.error(f"Suite '{suite_name}' not found")
            return False
        
        landscape = self._landscapes.get(suite_name, FitnessLandscape())
        
        if dimension not in landscape.dimension_names:
            landscape.dimension_names.append(dimension)
        
        landscape.dimension_values[dimension] = value
        landscape.timestamp = time.time() if 'time' in sys.modules else 0.0
        
        self._landscapes[suite_name] = landscape
        
        # Update suite fitness based on landscape changes
        avg_value = sum(landscape.dimension_values.values()) / max(len(landscape.dimension_values), 1)
        suite.fitness_score = max(0.0, min(1.0, avg_value))
        
        logger.info(f"Modified landscape dimension '{dimension}' for suite '{suite_name}' to {value}")
        return True
    
    def get_landscape(self, suite_name: str) -> Optional[FitnessLandscape]:
        """Get the fitness landscape for a test suite."""
        return self._landscapes.get(suite_name)
    
    def list_landscapes(self) -> List[str]:
        """List all suite names with landscapes."""
        return list(self._landscapes.keys())
    
    def clear_landscape(self, suite_name: str) -> bool:
        """Clear the fitness landscape for a test suite."""
        if suite_name in self._landscapes:
            del self._landscapes[suite_name]
            return True
        return False


# ---------------------------------------------------------------------------
# Ecology Engine (updated to use new classes)
# ---------------------------------------------------------------------------

class EcologyEngine:
    """
    Engine that manages ecological pressures on test suites.
    
    Provides methods to introduce pressures, apply them to test suites,
    and evolve the fitness landscape over time.
    """
    
    def __init__(self, registry: Optional[TestSuiteRegistry] = None):
        self.registry = registry or TestSuiteRegistry()
        self._active_pressures: List[EcologyPressure] = []
        self._fitness_landscapes: Dict[str, FitnessLandscape] = {}
        self._history: List[Dict[str, Any]] = []
        self._config = {
            'mutation_rate': 0.1,
            'crossover_rate': 0.5,
            'selection_pressure': 0.3,
            'max_history': 1000
        }
        self.evolver = TestSuiteEvolver(registry)
        self.pressure_generator = PressureGenerator()
        self.landscape_modifier = FitnessLandscapeModifier(registry)
    
    def configure(self, **kwargs) -> None:
        """Update engine configuration."""
        self._config.update(kwargs)
    
    # -----------------------------------------------------------------------
    # Pressure Management
    # -----------------------------------------------------------------------
    
    def introduce_pressure(self, pressure: EcologyPressure) -> bool:
        """
        Introduce a new ecological pressure to the system.
        
        Args:
            pressure: EcologyPressure instance to add.
            
        Returns:
            True if pressure was added successfully.
        """
        if not isinstance(pressure, EcologyPressure):
            logger.error("Invalid pressure type. Must be EcologyPressure.")
            return False
        
        self._active_pressures.append(pressure)
        logger.info(f"Introduced pressure: {pressure.type.value} (severity={pressure.severity:.2f}) "
                     f"targeting '{pressure.target_metric}'")
        return True
    
    def remove_pressure(self, pressure_type: PressureType) -> bool:
        """Remove all active pressures of a given type."""
        initial_count = len(self._active_pressures)
        self._active_pressures = [p for p in self._active_pressures if p.type != pressure_type]
        removed = initial_count - len(self._active_pressures)
        if removed > 0:
            logger.info(f"Removed {removed} pressure(s) of type '{pressure_type.value}'")
        return removed > 0
    
    def clear_pressures(self) -> None:
        """Remove all active pressures."""
        self._active_pressures.clear()
        logger.info("All pressures cleared.")
    
    def get_active_pressures(self) -> List[EcologyPressure]:
        """Get list of currently active pressures."""
        return list(self._active_pressures)
    
    # -----------------------------------------------------------------------
    # Applying Pressures to Test Suites
    # -----------------------------------------------------------------------
    
    def apply_pressure_to_test_suite(self, suite_name: str, 
                                      pressure: Optional[EcologyPressure] = None) -> Dict[str, Any]:
        """
        Apply a pressure (or all active pressures) to a specific test suite.
        
        Args:
            suite_name: Name of the registered test suite.
            pressure: Optional specific pressure to apply. If None, applies all active.
            
        Returns:
            Dictionary with results of the application.
        """
        suite = self.registry.get(suite_name)
        if not suite:
            logger.error(f"Test suite '{suite_name}' not found in registry.")
            return {'success': False, 'error': f"Suite '{suite_name}' not found"}
        
        pressures_to_apply = [pressure] if pressure else self._active_pressures
        if not pressures_to_apply:
            logger.warning(f"No pressures to apply to '{suite_name}'.")
            return {'success': True, 'applied': 0, 'message': 'No pressures active'}
        
        results = []
        total_impact = 0.0
        
        for p in pressures_to_apply:
            impact = self._calculate_pressure_impact(p, suite)
            total_impact += impact
            results.append({
                'pressure_type': p.type.value,
                'severity': p.severity,
                'target_metric': p.target_metric,
                'impact': impact
            })
            
            # Update suite metadata with pressure effects
            if p.target_metric not in suite.metadata:
                suite.metadata[p.target_metric] = 0.0
            suite.metadata[p.target_metric] += impact
            
            # Record last pressure
            suite.last_pressure = p
        
        # Update fitness score based on total impact
        new_fitness = max(0.0, min(1.0, suite.fitness_score - total_impact * 0.1))
        suite.fitness_score = new_fitness
        
        # Log the application
        logger.info(f"Applied {len(pressures_to_apply)} pressure(s) to '{suite_name}'. "
                     f"Total impact: {total_impact:.3f}, New fitness: {new_fitness:.3f}")
        
        # Record in history
        self._record_history(suite_name, pressures_to_apply, total_impact, new_fitness)
        
        return {
            'success': True,
            'suite_name': suite_name,
            'applied': len(pressures_to_apply),
            'total_impact': total_impact,
            'new_fitness': new_fitness,
            'details': results
        }
    
    def _calculate_pressure_impact(self, pressure: EcologyPressure, 
                                    suite: TestSuiteInfo) -> float:
        """
        Calculate the impact of a pressure on a test suite.
        
        Uses a combination of severity, test count, and random variation.
        """
        base_impact = pressure.severity * 0.5
        # Scale by test count (more tests = more resilient)
        test_factor = 1.0 / (1.0 + 0.01 * suite.test_count) if suite.test_count > 0 else 1.0
        # Add random variation
        variation = random.uniform(-0.1, 0.1)
        impact = base_impact * test_factor + variation
        return max(0.0, min(1.0, impact))
    
    # -----------------------------------------------------------------------
    # Fitness Landscape Evolution
    # -----------------------------------------------------------------------
    
    def evolve_fitness_landscape(self, suite_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Evolve the fitness landscape for one or all test suites.
        
        This simulates natural selection: suites with higher fitness scores
        are more likely to survive and reproduce (be duplicated with mutations).
        
        Args:
            suite_name: Optional specific suite to evolve. If None, evolves all.
            
        Returns:
            Dictionary with evolution results.
        """
        if suite_name:
            suites_to_evolve = [self.registry.get(suite_name)]
            if not suites_to_evolve[0]:
                return {'success': False, 'error': f"Suite '{suite_name}' not found"}
        else:
            suites_to_evolve = self.registry.get_all()
        
        if not suites_to_evolve:
            return {'success': False, 'error': 'No suites to evolve'}
        
        results = []
        
        for suite in suites_to_evolve:
            if suite is None:
                continue
            
            # Calculate selection probability based on fitness
            selection_prob = suite.fitness_score * (1.0 - self._config['selection_pressure'])
            
            # Apply mutation to fitness
            mutation = random.gauss(0, self._config['mutation_rate'])
            new_fitness = max(0.0, min(1.0, suite.fitness_score + mutation))
            
            # Update fitness landscape
            landscape = self._fitness_landscapes.get(suite.name, FitnessLandscape())
            landscape.fitness_scores.append(new_fitness)
            landscape.timestamp = time.time() if 'time' in sys.modules else 0.0
            self._fitness_landscapes[suite.name] = landscape
            
            # Update suite fitness
            suite.fitness_score = new_fitness
            
            results.append({
                'suite_name': suite.name,
                'old_fitness': suite.fitness_score,
                'new_fitness': new_fitness,
                'mutation': mutation,
                'selection_probability': selection_prob
            })
        
        return {
            'success': True,
            'evolved_suites': len(results),
            'details': results
        }
    
    def _record_history(self, suite_name: str, pressures: List[EcologyPressure],
                        total_impact: float, new_fitness: float) -> None:
        """Record an event in the engine history."""
        import time
        record = {
            'timestamp': time.time(),
            'suite_name': suite_name,
            'pressures': [p.to_dict() for p in pressures],
            'total_impact': total_impact,
            'new_fitness': new_fitness
        }
        self._history.append(record)
        if len(self._history) > self._config['max_history']:
            self._history.pop(0)
    
    def get_history(self) -> List[Dict[str, Any]]:
        """Get the engine's history of events."""
        return list(self._history)
    
    def clear_history(self) -> None:
        """Clear the engine's history."""
        self._history.clear()