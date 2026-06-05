"""Environmental Pressure Generator

Generates novel environmental constraints for testing and simulation:
- Resource limits (memory, CPU, bandwidth, storage)
- Timing constraints (deadlines, rate limits, latency bounds)
- Input complexity bounds (size, nesting depth, branching factor)
- Cross-module dependency challenges (circular deps, version conflicts, missing interfaces)
"""

import random
import string
import hashlib
from typing import Any, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
import math


class PressureType(Enum):
    RESOURCE_LIMIT = "resource_limit"
    TIMING_CONSTRAINT = "timing_constraint"
    INPUT_COMPLEXITY = "input_complexity"
    CROSS_MODULE_DEPENDENCY = "cross_module_dependency"


class ResourceKind(Enum):
    MEMORY = "memory"
    CPU = "cpu"
    BANDWIDTH = "bandwidth"
    STORAGE = "storage"
    FILE_DESCRIPTORS = "file_descriptors"
    NETWORK_CONNECTIONS = "network_connections"


class TimingKind(Enum):
    DEADLINE = "deadline"
    RATE_LIMIT = "rate_limit"
    LATENCY_BOUND = "latency_bound"
    TIMEOUT = "timeout"
    JITTER_TOLERANCE = "jitter_tolerance"


class ComplexityDimension(Enum):
    INPUT_SIZE = "input_size"
    NESTING_DEPTH = "nesting_depth"
    BRANCHING_FACTOR = "branching_factor"
    RECURSION_DEPTH = "recursion_depth"
    DATA_DEPENDENCY_CHAIN = "data_dependency_chain"


class DependencyChallenge(Enum):
    CIRCULAR_DEPENDENCY = "circular_dependency"
    VERSION_CONFLICT = "version_conflict"
    MISSING_INTERFACE = "missing_interface"
    DIAMOND_DEPENDENCY = "diamond_dependency"
    DEPRECATED_API = "deprecated_api"
    OPTIONAL_DEPENDENCY_MISSING = "optional_dependency_missing"


@dataclass
class EnvironmentalPressure:
    """Represents a single environmental pressure constraint."""
    pressure_id: str
    pressure_type: PressureType
    severity: float  # 0.0 (trivial) to 1.0 (critical)
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    source: str = "generated"
    is_active: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pressure_id": self.pressure_id,
            "pressure_type": self.pressure_type.value,
            "severity": self.severity,
            "description": self.description,
            "parameters": self.parameters,
            "source": self.source,
            "is_active": self.is_active,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EnvironmentalPressure":
        return cls(
            pressure_id=data["pressure_id"],
            pressure_type=PressureType(data["pressure_type"]),
            severity=data["severity"],
            description=data["description"],
            parameters=data.get("parameters", {}),
            source=data.get("source", "loaded"),
            is_active=data.get("is_active", True),
        )


@dataclass
class PressureProfile:
    """A collection of environmental pressures that form a coherent challenge."""
    profile_id: str
    name: str
    pressures: List[EnvironmentalPressure] = field(default_factory=list)
    difficulty: float = 0.5
    tags: List[str] = field(default_factory=list)

    def add_pressure(self, pressure: EnvironmentalPressure) -> None:
        self.pressures.append(pressure)
        self.difficulty = sum(p.severity for p in self.pressures) / max(len(self.pressures), 1)

    def remove_pressure(self, pressure_id: str) -> bool:
        for i, p in enumerate(self.pressures):
            if p.pressure_id == pressure_id:
                self.pressures.pop(i)
                self.difficulty = sum(p.severity for p in self.pressures) / max(len(self.pressures), 1)
                return True
        return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "name": self.name,
            "pressures": [p.to_dict() for p in self.pressures],
            "difficulty": self.difficulty,
            "tags": self.tags,
        }


class ResourceLimitGenerator:
    """Generates resource limit constraints."""

    def __init__(self, seed: Optional[int] = None):
        self.rng = random.Random(seed)

    def _generate_id(self) -> str:
        raw = f"resource_{self.rng.randint(0, 10**9)}"
        return hashlib.md5(raw.encode()).hexdigest()[:12]

    def generate_memory_limit(
        self,
        severity: Optional[float] = None,
        min_mb: float = 1.0,
        max_mb: float = 1024.0,
    ) -> EnvironmentalPressure:
        sev = severity if severity is not None else self.rng.uniform(0.3, 0.9)
        limit_mb = self.rng.uniform(min_mb, max_mb)
        return EnvironmentalPressure(
            pressure_id=self._generate_id(),
            pressure_type=PressureType.RESOURCE_LIMIT,
            severity=sev,
            description=f"Memory limit of {limit_mb:.1f} MB",
            parameters={"resource_kind": ResourceKind.MEMORY.value, "limit_mb": limit_mb},
        )

    def generate_cpu_limit(
        self,
        severity: Optional[float] = None,
        min_cores: float = 0.1,
        max_cores: float = 8.0,
    ) -> EnvironmentalPressure:
        sev = severity if severity is not None else self.rng.uniform(0.3, 0.9)
        cores = self.rng.uniform(min_cores, max_cores)
        return EnvironmentalPressure(
            pressure_id=self._generate_id(),
            pressure_type=PressureType.RESOURCE_LIMIT,
            severity=sev,
            description=f"CPU limit of {cores:.2f} cores",
            parameters={"resource_kind": ResourceKind.CPU.value, "limit_cores": cores},
        )

    def generate_bandwidth_limit(
        self,
        severity: Optional[float] = None,
        min_mbps: float = 0.1,
        max_mbps: float = 1000.0,
    ) -> EnvironmentalPressure:
        sev = severity if severity is not None else self.rng.uniform(0.3, 0.9)
        mbps = self.rng.uniform(min_mbps, max_mbps)
        return EnvironmentalPressure(
            pressure_id=self._generate_id(),
            pressure_type=PressureType.RESOURCE_LIMIT,
            severity=sev,
            description=f"Bandwidth limit of {mbps:.1f} Mbps",
            parameters={"resource_kind": ResourceKind.BANDWIDTH.value, "limit_mbps": mbps},
        )

    def generate_storage_limit(
        self,
        severity: Optional[float] = None,
        min_gb: float = 0.1,
        max_gb: float = 100.0,
    ) -> EnvironmentalPressure:
        sev = severity if severity is not None else self.rng.uniform(0.3, 0.9)
        gb = self.rng.uniform(min_gb, max_gb)
        return EnvironmentalPressure(
            pressure_id=self._generate_id(),
            pressure_type=PressureType.RESOURCE_LIMIT,
            severity=sev,
            description=f"Storage limit of {gb:.1f} GB",
            parameters={"resource_kind": ResourceKind.STORAGE.value, "limit_gb": gb},
        )

    def generate_random(self, severity: Optional[float] = None) -> EnvironmentalPressure:
        generators = [
            self.generate_memory_limit,
            self.generate_cpu_limit,
            self.generate_bandwidth_limit,
            self.generate_storage_limit,
        ]
        return self.rng.choice(generators)(severity=severity)


class TimingConstraintGenerator:
    """Generates timing constraint pressures."""

    def __init__(self, seed: Optional[int] = None):
        self.rng = random.Random(seed)

    def _generate_id(self) -> str:
        raw = f"timing_{self.rng.randint(0, 10**9)}"
        return hashlib.md5(raw.encode()).hexdigest()[:12]

    def generate_deadline(
        self,
        severity: Optional[float] = None,
        min_seconds: float = 0.001,
        max_seconds: float = 60.0,
    ) -> EnvironmentalPressure:
        sev = severity if severity is not None else self.rng.uniform(0.4, 0.95)
        deadline_s = self.rng.uniform(min_seconds, max_seconds)
        return EnvironmentalPressure(
            pressure_id=self._generate_id(),
            pressure_type=PressureType.TIMING_CONSTRAINT,
            severity=sev,
            description=f"Deadline of {deadline_s:.3f} seconds",
            parameters={"timing_kind": TimingKind.DEADLINE.value, "deadline_seconds": deadline_s},
        )

    def generate_rate_limit(
        self,
        severity: Optional[float] = None,
        min_rps: float = 1.0,
        max_rps: float = 10000.0,
    ) -> EnvironmentalPressure:
        sev = severity if severity is not None else self.rng.uniform(0.3, 0.8)
        rps = self.rng.uniform(min_rps, max_rps)
        return EnvironmentalPressure(
            pressure_id=self._generate_id(),
            pressure_type=PressureType.TIMING_CONSTRAINT,
            severity=sev,
            description=f"Rate limit of {rps:.1f} requests per second",
            parameters={"timing_kind": TimingKind.RATE_LIMIT.value, "max_rps": rps},
        )

    def generate_latency_bound(
        self,
        severity: Optional[float] = None,
        min_ms: float = 1.0,
        max_ms: float = 5000.0,
    ) -> EnvironmentalPressure:
        sev = severity if severity is not None else self.rng.uniform(0.3, 0.9)
        latency_ms = self.rng.uniform(min_ms, max_ms)
        return EnvironmentalPressure(
            pressure_id=self._generate_id(),
            pressure_type=PressureType.TIMING_CONSTRAINT,
            severity=sev,
            description=f"Maximum latency of {latency_ms:.1f} ms",
            parameters={"timing_kind": TimingKind.LATENCY_BOUND.value, "max_latency_ms": latency_ms},
        )

    def generate_timeout(
        self,
        severity: Optional[float] = None,
        min_seconds: float = 0.01,
        max_seconds: float = 30.0,
    ) -> EnvironmentalPressure:
        sev = severity if severity is not None else self.rng.uniform(0.5, 1.0)
        timeout_s = self.rng.uniform(min_seconds, max_seconds)
        return EnvironmentalPressure(
            pressure_id=self._generate_id(),
            pressure_type=PressureType.TIMING_CONSTRAINT,
            severity=sev,
            description=f"Timeout of {timeout_s:.3f} seconds",
            parameters={"timing_kind": TimingKind.TIMEOUT.value, "timeout_seconds": timeout_s},
        )

    def generate_random(self, severity: Optional[float] = None) -> EnvironmentalPressure:
        generators = [
            self.generate_deadline,
            self.generate_rate_limit,
            self.generate_latency_bound,
            self.generate_timeout,
        ]
        return self.rng.choice(generators)(severity=severity)


class InputComplexityGenerator:
    """Generates input complexity bound pressures."""

    def __init__(self, seed: Optional[int] = None):
        self.rng = random.Random(seed)

    def _generate_id(self) -> str:
        raw = f"complexity_{self.rng.randint(0, 10**9)}"
        return hashlib.md5(raw.encode()).hexdigest()[:12]

    def generate_input_size_limit(
        self,
        severity: Optional[float] = None,
        min_bytes: int = 100,
        max_bytes: int = 10**8,
    ) -> EnvironmentalPressure:
        sev = severity if severity is not None else self.rng.uniform(0.3, 0.9)
        size_bytes = self.rng.randint(min_bytes, max_bytes)
        return EnvironmentalPressure(
            pressure_id=self._generate_id(),
            pressure_type=PressureType.INPUT_COMPLEXITY,
            severity=sev,
            description=f"Maximum input size of {size_bytes} bytes",
            parameters={
                "complexity_dimension": ComplexityDimension.INPUT_SIZE.value,
                "max_bytes": size_bytes,
            },
        )

    def generate_nesting_depth_limit(
        self,
        severity: Optional[float] = None,
        min_depth: int = 1,
        max_depth: int = 100,
    ) -> EnvironmentalPressure:
        sev = severity if severity is not None else self.rng.uniform(0.3, 0.9)
        depth = self.rng.randint(min_depth, max_depth)
        return EnvironmentalPressure(
            pressure_id=self._generate_id(),
            pressure_type=PressureType.INPUT_COMPLEXITY,
            severity=sev,
            description=f"Maximum nesting depth of {depth} levels",
            parameters={
                "complexity_dimension": ComplexityDimension.NESTING_DEPTH.value,
                "max_depth": depth,
            },
        )

    def generate_branching_factor_limit(
        self,
        severity: Optional[float] = None,
        min_branches: int = 2,
        max_branches: int = 1000,
    ) -> EnvironmentalPressure:
        sev = severity if severity is not None else self.rng.uniform(0.3, 0.9)
        branches = self.rng.randint(min_branches, max_branches)
        return EnvironmentalPressure(
            pressure_id=self._generate_id(),
            pressure_type=PressureType.INPUT_COMPLEXITY,
            severity=sev,
            description=f"Maximum branching factor of {branches}",
            parameters={
                "complexity_dimension": ComplexityDimension.BRANCHING_FACTOR.value,
                "max_branches": branches,
            },
        )

    def generate_recursion_depth_limit(
        self,
        severity: Optional[float] = None,
        min_depth: int = 1,
        max_depth: int = 1000,
    ) -> EnvironmentalPressure:
        sev = severity if severity is not None else self.rng.uniform(0.4, 0.95)
        depth = self.rng.randint(min_depth, max_depth)
        return EnvironmentalPressure(
            pressure_id=self._generate_id(),
            pressure_type=PressureType.INPUT_COMPLEXITY,
            severity=sev,
            description=f"Maximum recursion depth of {depth}",
            parameters={
                "complexity_dimension": ComplexityDimension.RECURSION_DEPTH.value,
                "max_depth": depth,
            },
        )

    def generate_random(self, severity: Optional[float] = None) -> EnvironmentalPressure:
        generators = [
            self.generate_input_size_limit,
            self.generate_nesting_depth_limit,
            self.generate_branching_factor_limit,
            self.generate_recursion_depth_limit,
        ]
        return self.rng.choice(generators)(severity=severity)


class CrossModuleDependencyGenerator:
    """Generates cross-module dependency challenge pressures."""

    def __init__(self, seed: Optional[int] = None):
        self.rng = random.Random(seed)
        self._module_names = [
            "core", "utils", "models", "views", "controllers",
            "services", "repositories", "adapters", "serializers",
            "validators", "middleware", "config", "database",
            "cache", "queue", "logging", "monitoring", "auth",
        ]

    def _generate_id(self) -> str:
        raw = f"dep_{self.rng.randint(0, 10**9)}"
        return hashlib.md5(raw.encode()).hexdigest()[:12]

    def _random_module(self) -> str:
        return self.rng.choice(self._module_names)

    def _random_version(self) -> str:
        major = self.rng.randint(0, 5)
        minor = self.rng.randint(0, 20)
        patch = self.rng.randint(0, 30)
        return f"{major}.{minor}.{patch}"

    def generate_circular_dependency(
        self,
        severity: Optional[float] = None,
        chain_length: int = 3,
    ) -> EnvironmentalPressure:
        sev = severity if severity is not None else self.rng.uniform(0.6, 1.0)
        modules = [self._random_module() for _ in range(chain_length)]
        cycle_desc = " -> ".join(modules) + f" -> {modules[0]}"
        return EnvironmentalPressure(
            pressure_id=self._generate_id(),
            pressure_type=PressureType.CROSS_MODULE_DEPENDENCY,
            severity=sev,
            description=f"Circular dependency: {cycle_desc}",
            parameters={
                "challenge_type": DependencyChallenge.CIRCULAR_DEPENDENCY.value,
                "modules": modules,
                "chain_length": chain_length,
            },
        )

    def generate_version_conflict(
        self,
        severity: Optional[float] = None,
    ) -> EnvironmentalPressure:
        sev = severity if severity is not None else self.rng.uniform(0.4, 0.9)
        module = self._random_module()
        version_a = self._random_version()
        version_b = self._random_version()
        return EnvironmentalPressure(
            pressure_id=self._generate_id(),
            pressure_type=PressureType.CROSS_MODULE_DEPENDENCY,
            severity=sev,
            description=f"Version conflict for '{module}': requires {version_a} but {version_b} is installed",
            parameters={
                "challenge_type": DependencyChallenge.VERSION_CONFLICT.value,
                "module": module,
                "version_required": version_a,
                "version_installed": version_b,
            },
        )

    def generate_missing_interface(
        self,
        severity: Optional[float] = None,
    ) -> EnvironmentalPressure:
        se