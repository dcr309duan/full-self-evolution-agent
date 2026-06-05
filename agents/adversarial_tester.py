"""Adversarial Self-Testing Module.

Breaks the 'local optimum trap' by generating adversarial inputs, edge cases,
and chaos scenarios that stress-test the agent's own evolution pipeline.

Instead of only testing 'does this work?', this module asks
'what would BREAK this?' — driving antifragile evolution.
"""

import ast
import random
import string
import json
import logging
import time
from typing import Any, Callable, Dict, List, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class AdversarialCase:
    target_component: str
    attack_type: str
    payload: Any
    expected_behavior: str
    severity: int = 3  # 1-5
    timestamp: float = field(default_factory=time.time)


@dataclass
class StressResult:
    component: str
    attack_type: str
    survived: bool
    error: Optional[str] = None
    latency_ms: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)


class AdversarialTester:
    """Generates and executes adversarial tests against agent components."""

    ATTACK_TYPES = [
        "malformed_input",
        "resource_exhaustion",
        "circular_dependency",
        "schema_violation",
        "timing_attack",
        "state_corruption",
        "injection",
    ]

    def __init__(self):
        self.results: List[StressResult] = []
        self.vulnerabilities: List[Dict[str, Any]] = []

    def generate_adversarial_cases(self, component: str) -> List[AdversarialCase]:
        """Generate adversarial test cases for a specific component."""
        cases = []

        cases.append(AdversarialCase(
            target_component=component,
            attack_type="malformed_input",
            payload=self._generate_malformed_json(),
            expected_behavior="graceful_error_handling",
            severity=3,
        ))

        cases.append(AdversarialCase(
            target_component=component,
            attack_type="resource_exhaustion",
            payload=self._generate_deep_nesting(depth=100),
            expected_behavior="timeout_or_depth_limit",
            severity=4,
        ))

        cases.append(AdversarialCase(
            target_component=component,
            attack_type="circular_dependency",
            payload=self._generate_circular_graph(),
            expected_behavior="cycle_detection",
            severity=5,
        ))

        cases.append(AdversarialCase(
            target_component=component,
            attack_type="schema_violation",
            payload=self._generate_schema_violation(),
            expected_behavior="validation_rejection",
            severity=3,
        ))

        cases.append(AdversarialCase(
            target_component=component,
            attack_type="injection",
            payload=self._generate_code_injection(),
            expected_behavior="sanitization_or_rejection",
            severity=5,
        ))

        return cases

    def stress_test_function(
        self,
        func: Callable,
        cases: List[AdversarialCase],
        timeout_ms: float = 5000,
    ) -> List[StressResult]:
        """Execute adversarial cases against a callable and collect results."""
        results = []
        for case in cases:
            start = time.time()
            try:
                func(case.payload)
                survived = True
                error = None
            except (ValueError, TypeError, KeyError) as e:
                survived = True
                error = f"Handled: {type(e).__name__}: {str(e)[:100]}"
            except RecursionError:
                survived = case.attack_type == "resource_exhaustion"
                error = "RecursionError (expected for depth attacks)"
            except Exception as e:
                survived = False
                error = f"Unhandled: {type(e).__name__}: {str(e)[:200]}"

            latency = (time.time() - start) * 1000
            result = StressResult(
                component=case.target_component,
                attack_type=case.attack_type,
                survived=survived,
                error=error,
                latency_ms=latency,
                details={"severity": case.severity},
            )
            results.append(result)

            if not survived:
                self.vulnerabilities.append({
                    "component": case.target_component,
                    "attack_type": case.attack_type,
                    "error": error,
                    "severity": case.severity,
                    "timestamp": time.time(),
                })

        self.results.extend(results)
        return results

    def generate_chaos_scenario(self) -> Dict[str, Any]:
        """Generate a chaos engineering scenario for the evolution pipeline."""
        scenarios = [
            {
                "type": "api_timeout",
                "description": "Simulate DeepSeek API timeout during reflection",
                "inject_at": "reflection_phase",
                "duration_s": random.uniform(5, 30),
                "recovery_expected": True,
            },
            {
                "type": "disk_full",
                "description": "Simulate disk space exhaustion during file write",
                "inject_at": "mutation_phase",
                "affected_paths": ["agents/", "schema/", "tests/"],
                "recovery_expected": True,
            },
            {
                "type": "concurrent_modification",
                "description": "Simulate race condition in evolution state file",
                "inject_at": "state_update",
                "conflicting_writes": 3,
                "recovery_expected": True,
            },
            {
                "type": "memory_pressure",
                "description": "Simulate high memory usage during AST parsing",
                "inject_at": "ast_rewrite_phase",
                "target_mb": random.randint(100, 500),
                "recovery_expected": True,
            },
            {
                "type": "schema_drift",
                "description": "Simulate gradual schema incompatibility between components",
                "inject_at": "inter_component_communication",
                "drift_fields": random.sample(
                    ["timestamp", "component", "schema_version", "metrics"],
                    k=2,
                ),
                "recovery_expected": True,
            },
        ]
        return random.choice(scenarios)

    def get_vulnerability_report(self) -> Dict[str, Any]:
        """Generate a summary of discovered vulnerabilities."""
        total = len(self.results)
        survived = sum(1 for r in self.results if r.survived)
        return {
            "total_tests": total,
            "survived": survived,
            "failed": total - survived,
            "survival_rate": survived / total if total > 0 else 1.0,
            "critical_vulnerabilities": [
                v for v in self.vulnerabilities if v["severity"] >= 4
            ],
            "all_vulnerabilities": self.vulnerabilities,
            "avg_latency_ms": (
                sum(r.latency_ms for r in self.results) / total if total > 0 else 0
            ),
        }

    def _generate_malformed_json(self) -> str:
        noise = ''.join(random.choices(string.printable, k=random.randint(10, 200)))
        return "{" + noise + "}"

    def _generate_deep_nesting(self, depth: int = 100) -> dict:
        result: dict = {"value": "leaf"}
        for i in range(depth):
            result = {"nested": result, "level": i}
        return result

    def _generate_circular_graph(self) -> Dict[str, List[str]]:
        nodes = [f"module_{i}" for i in range(5)]
        graph = {n: [] for n in nodes}
        for i in range(len(nodes)):
            graph[nodes[i]].append(nodes[(i + 1) % len(nodes)])
        return graph

    def _generate_schema_violation(self) -> dict:
        return {
            "schema_version": -1,
            "timestamp": "not_a_number",
            "component": "",
            "cycle_id": None,
            "reflection_summary": 42,
        }

    def _generate_code_injection(self) -> str:
        payloads = [
            "__import__('os').system('echo pwned')",
            "'; DROP TABLE evolution; --",
            "{{7*7}}",
            "${IFS}cat${IFS}/etc/passwd",
            "a" * 10000,
        ]
        return random.choice(payloads)


def run_full_adversarial_suite(components: Optional[Dict[str, Callable]] = None) -> Dict[str, Any]:
    """Run complete adversarial test suite against all registered components."""
    tester = AdversarialTester()

    if not components:
        logger.info("No components registered for adversarial testing")
        return tester.get_vulnerability_report()

    for name, func in components.items():
        logger.info(f"Running adversarial tests against: {name}")
        cases = tester.generate_adversarial_cases(name)
        tester.stress_test_function(func, cases)

    report = tester.get_vulnerability_report()
    logger.info(
        f"Adversarial suite complete: {report['survived']}/{report['total_tests']} survived "
        f"({report['survival_rate']:.1%}), {len(report['critical_vulnerabilities'])} critical vulns"
    )
    return report
