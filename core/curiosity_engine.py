"""Core curiosity engine for autonomous task generation and self-improvement."""

import random
import json
import hashlib
import time
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from pathlib import Path

# ---------------------------------------------------------------------------
# Template Library
# ---------------------------------------------------------------------------

TASK_TEMPLATES: List[Dict[str, Any]] = [
    {
        "name": "Caesar Cipher",
        "description": "Implement a Caesar cipher with configurable shift and both encode/decode.",
        "difficulty": 2,
        "tags": ["crypto", "string"],
        "test_cases": [
            {"input": {"text": "hello", "shift": 3}, "expected": "khoor"},
            {"input": {"text": "khoor", "shift": -3}, "expected": "hello"},
            {"input": {"text": "abc", "shift": 26}, "expected": "abc"},
        ],
    },
    {
        "name": "Regex Validator",
        "description": "Write a function that validates email addresses using regex.",
        "difficulty": 3,
        "tags": ["regex", "validation"],
        "test_cases": [
            {"input": "user@example.com", "expected": True},
            {"input": "invalid-email", "expected": False},
            {"input": "a@b.co", "expected": True},
        ],
    },
    {
        "name": "Simple Calculator",
        "description": "Build a calculator that parses and evaluates basic arithmetic expressions (+, -, *, /).",
        "difficulty": 4,
        "tags": ["parsing", "math"],
        "test_cases": [
            {"input": "2+3", "expected": 5},
            {"input": "10-4*2", "expected": 2},
            {"input": "(1+2)*3", "expected": 9},
        ],
    },
    {
        "name": "JSON Parser",
        "description": "Create a simple JSON parser that converts a JSON string to a Python dict.",
        "difficulty": 5,
        "tags": ["parsing", "serialization"],
        "test_cases": [
            {"input": '{"a":1,"b":2}', "expected": {"a": 1, "b": 2}},
            {"input": '{"x":[1,2,3]}', "expected": {"x": [1, 2, 3]}},
            {"input": "null", "expected": None},
        ],
    },
    {
        "name": "Binary Search",
        "description": "Implement binary search on a sorted list.",
        "difficulty": 3,
        "tags": ["algorithm", "search"],
        "test_cases": [
            {"input": {"arr": [1, 3, 5, 7, 9], "target": 5}, "expected": 2},
            {"input": {"arr": [1, 3, 5, 7, 9], "target": 2}, "expected": -1},
            {"input": {"arr": [], "target": 1}, "expected": -1},
        ],
    },
    {
        "name": "URL Shortener",
        "description": "Implement a simple URL shortener that maps long URLs to short codes.",
        "difficulty": 3,
        "tags": ["web", "hash"],
        "test_cases": [
            {"input": "https://example.com/very/long/url", "expected": "abc123"},
            {"input": "https://example.com/another/url", "expected": "def456"},
        ],
    },
    {
        "name": "Rate Limiter",
        "description": "Build a token bucket rate limiter that allows N requests per second.",
        "difficulty": 4,
        "tags": ["concurrency", "system design"],
        "test_cases": [
            {"input": {"requests": 5, "limit": 10, "window": 1}, "expected": True},
            {"input": {"requests": 15, "limit": 10, "window": 1}, "expected": False},
        ],
    },
    {
        "name": "Bloom Filter",
        "description": "Implement a Bloom filter with configurable false positive rate.",
        "difficulty": 5,
        "tags": ["data structure", "probabilistic"],
        "test_cases": [
            {"input": {"items": ["apple", "banana"], "test": "apple"}, "expected": True},
            {"input": {"items": ["apple", "banana"], "test": "grape"}, "expected": False},
        ],
    },
    {
        "name": "Markdown Parser",
        "description": "Create a simple markdown parser that converts markdown to HTML.",
        "difficulty": 5,
        "tags": ["parsing", "markup"],
        "test_cases": [
            {"input": "# Hello", "expected": "<h1>Hello</h1>"},
            {"input": "**bold**", "expected": "<strong>bold</strong>"},
            {"input": "- item", "expected": "<ul><li>item</li></ul>"},
        ],
    },
    {
        "name": "Caching Decorator",
        "description": "Write a decorator that caches function results with TTL support.",
        "difficulty": 4,
        "tags": ["decorator", "caching"],
        "test_cases": [
            {"input": {"func": lambda x: x * 2, "args": [5], "ttl": 10}, "expected": 10},
            {"input": {"func": lambda x: x * 2, "args": [5], "ttl": 0}, "expected": 10},
        ],
    },
    {
        "name": "Fibonacci Generator",
        "description": "Implement a generator that yields Fibonacci numbers up to N.",
        "difficulty": 2,
        "tags": ["generator", "math"],
        "test_cases": [
            {"input": 5, "expected": [0, 1, 1, 2, 3]},
            {"input": 0, "expected": []},
            {"input": 1, "expected": [0]},
        ],
    },
    {
        "name": "Anagram Checker",
        "description": "Write a function that checks if two strings are anagrams.",
        "difficulty": 2,
        "tags": ["string", "sorting"],
        "test_cases": [
            {"input": ("listen", "silent"), "expected": True},
            {"input": ("hello", "world"), "expected": False},
            {"input": ("", ""), "expected": True},
        ],
    },
]

# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------

@dataclass
class CuriosityTask:
    """Represents a concrete task generated from a template."""
    template_name: str
    description: str
    difficulty: int
    tags: List[str]
    test_cases: List[Dict[str, Any]]
    created_at: float = field(default_factory=time.time)
    attempted: bool = False
    succeeded: bool = False
    failure_reason: Optional[str] = None
    task_id: str = field(default_factory=lambda: hashlib.md5(str(time.time()).encode()).hexdigest()[:8])


@dataclass
class CuriosityResult:
    """Stores the outcome of a curiosity-driven attempt."""
    task_id: str
    template_name: str
    attempted_at: float
    succeeded: bool
    failure_reason: Optional[str]
    solution_code: Optional[str] = None


# ---------------------------------------------------------------------------
# Knowledge Base Integration (stub)
# ---------------------------------------------------------------------------

class KnowledgeBaseStub:
    """Minimal stub for storing curiosity results. Replace with real KB integration."""
    def __init__(self):
        self.results: List[CuriosityResult] = []
        self.goals: List[Dict[str, Any]] = []

    def store_result(self, result: CuriosityResult) -> None:
        self.results.append(result)

    def promote_goal(self, description: str, priority: int = 5) -> None:
        self.goals.append({
            "description": description,
            "priority": priority,
            "created_at": time.time(),
        })

    def get_failed_tasks(self) -> List[CuriosityResult]:
        return [r for r in self.results if not r.succeeded]


# ---------------------------------------------------------------------------
# Core Engine
# ---------------------------------------------------------------------------

class CuriosityEngine:
    """Main curiosity engine that generates, attempts, and learns from tasks."""

    def __init__(self, knowledge_base: Optional[KnowledgeBaseStub] = None):
        self.templates = TASK_TEMPLATES.copy()
        self.kb = knowledge_base or KnowledgeBaseStub()
        self.current_task: Optional[CuriosityTask] = None
        self.generation_count = 0

    # ---------------------------------------------------------------
    # (2) Periodic generation
    # ---------------------------------------------------------------

    def generate_task(self) -> CuriosityTask:
        """Pick a random template and create a concrete task with test cases."""
        template = random.choice(self.templates)
        task = CuriosityTask(
            template_name=template["name"],
            description=template["description"],
            difficulty=template["difficulty"],
            tags=template["tags"].copy(),
            test_cases=template["test_cases"].copy(),
        )
        self.current_task = task
        self.generation_count += 1
        return task

    # ---------------------------------------------------------------
    # (3) Solution attempt
    # ---------------------------------------------------------------

    def attempt_solution(self, task: CuriosityTask) -> CuriosityResult:
        """Try to solve the task using existing capabilities (simulated)."""
        # In a real system, this would import from the agent's codebase
        # and attempt to run the solution against the test cases.
        # Here we simulate a random success/failure for demonstration.
        import random as rnd
        succeeded = rnd.random() > 0.4  # 60% success rate
        failure_reason = None
        solution_code = None

        if not succeeded:
            failure_reason = f"Failed to implement {task.template_name}: test case mismatch or runtime error."

        result = CuriosityResult(
            task_id=task.task_id,
            template_name=task.template_name,
            attempted_at=time.time(),
            succeeded=succeeded,
            failure_reason=failure_reason,
            solution_code=solution_code,
        )

        task.attempted = True
        task.succeeded = succeeded
        task.failure_reason = failure_reason

        # Store in knowledge base
        self.kb.store_result(result)
        return result

    # ---------------------------------------------------------------
    # (4) Gap detection
    # ---------------------------------------------------------------

    def detect_gaps(self) -> List[Dict[str, Any]]:
        """Record failures and promote them as high-priority goals."""
        failed = self.kb.get_failed_tasks()
        promoted_goals = []

        for result in failed:
            # Avoid duplicate promotions for the same template
            already_promoted = any(
                g["description"] == f"Implement {result.template_name}" for g in self.kb.goals
            )
            if not already_promoted:
                goal = {
                    "description": f"Implement {result.template_name}",
                    "priority": 5,  # high priority
                    "source": "curiosity_gap",
                    "task_id": result.task_id,
                }
                self.kb.promote_goal(goal["description"], priority=5)
                promoted_goals.append(goal)

        return promoted_goals

    # ---------------------------------------------------------------
    # (5) Integration helper
    # ---------------------------------------------------------------

    def run_curiosity_cycle(self) -> Dict[str, Any]:
        """Run one full curiosity cycle: generate -> attempt -> detect gaps."""
        task = self.generate_task()
        result = self.attempt_solution(task)
        gaps = self.detect_gaps()

        return {
            "task": asdict(task),
            "result": asdict(result),
            "gaps_detected": gaps,
            "total_failures": len(self.kb.get_failed_tasks()),
        }

    def get_statistics(self) -> Dict[str, Any]:
        """Return summary statistics about curiosity engine activity."""
        all_results = self.kb.results
        successes = sum(1 for r in all_results if r.succeeded)
        failures = len(all_results) - successes
        return {
            "total_tasks_generated": self.generation_count,
            "total_attempts": len(all_results),
            "successes": successes,
            "failures": failures,
            "success_rate": successes / len(all_results) if all_results else 0.0,
            "promoted_goals": len(self.kb.goals),
        }


# ---------------------------------------------------------------------------
# Convenience
# ---------------------------------------------------------------------------

def create_default_engine() -> CuriosityEngine:
    """Create a CuriosityEngine with a fresh knowledge base stub."""
    kb = KnowledgeBaseStub()
    return CuriosityEngine(knowledge_base=kb)