"""
core/ecology_foundation.py - Foundation module for ecology-based test suite management.

Provides base classes and a registry for managing ecological pressures on test suites.
Uses defensive imports and fallbacks for all dependencies.
"""

import os
import sys
import json
import copy
import random
import logging
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path

# ---------------------------------------------------------------------------
# Defensive imports with fallbacks
# ---------------------------------------------------------------------------

# Try to import numpy; fallback to a minimal stub
try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False
    # Minimal stub for basic array-like operations
    class _NumpyStub:
        @staticmethod
        def array(data, dtype=None):
            return data
        @staticmethod
        def mean(a):
            if isinstance(a, (list, tuple)):
                return sum(a) / len(a) if a else 0.0
            return a
        @staticmethod
        def std(a):
            if isinstance(a, (list, tuple)):
                m = _NumpyStub.mean(a)
                variance = sum((x - m) ** 2 for x in a) / len(a) if a else 0.0
                return variance ** 0.5
            return 0.0
        @staticmethod
        def random():
            return random.random()
    np = _NumpyStub()

# Try to import pandas; fallback to None
try:
    import pandas as pd
    _HAS_PANDAS = True
except ImportError:
    pd = None
    _HAS_PANDAS = False

# Try to import networkx; fallback to None
try:
    import networkx as nx
    _HAS_NETWORKX = True
except ImportError:
    nx = None
    _HAS_NETWORKX = False

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
# Ecology Engine
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
            landscape.fitness