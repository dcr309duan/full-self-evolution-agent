"""
meta_mutation_engine.py

Implements a meta-mutation engine that collects performance statistics from the
meta-evaluation loop, analyzes them periodically, generates targeted mutations
for underperforming meta-modules, and applies them with a rollback mechanism.
"""

import ast
import copy
import hashlib
import importlib
import inspect
import logging
import os
import sys
import time
import traceback
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Data structures for performance statistics
# -----------------------------------------------------------------------------

@dataclass
class MutationStats:
    """Statistics for a single mutation cycle."""
    cycle_id: int
    mutation_success_rate: float  # 0.0 to 1.0
    test_pass_rate: float         # 0.0 to 1.0
    integration_test_status: bool
    reflection_score: float       # 0.0 to 1.0
    timestamp: float = field(default_factory=time.time)

@dataclass
class ModulePerformance:
    """Aggregated performance data for a specific module."""
    module_name: str
    recent_stats: deque[MutationStats] = field(default_factory=lambda: deque(maxlen=50))
    avg_mutation_success_rate: float = 0.0
    avg_test_pass_rate: float = 0.0
    avg_reflection_score: float = 0.0
    integration_test_failures: int = 0
    last_mutation_time: float = 0.0
    mutation_count: int = 0

# -----------------------------------------------------------------------------
# AST-based code rewriter (safe mutation)
# -----------------------------------------------------------------------------

class SafeASTRewriter:
    """
    Applies AST transformations with rollback capability.
    Maintains a backup of original source code.
    """

    def __init__(self):
        self.backups: Dict[str, str] = {}
        self._lock = False

    def read_source(self, module_path: str) -> str:
        """Read the source code of a module."""
        with open(module_path, 'r') as f:
            return f.read()

    def parse_to_ast(self, source: str) -> ast.Module:
        """Parse source code into an AST."""
        return ast.parse(source)

    def ast_to_source(self, tree: ast.Module) -> str:
        """Convert AST back to source code."""
        return ast.unparse(tree)

    def backup(self, module_path: str) -> None:
        """Create a backup of the current source."""
        if module_path not in self.backups:
            self.backups[module_path] = self.read_source(module_path)
            logger.debug(f"Backup created for {module_path}")

    def restore(self, module_path: str) -> bool:
        """Restore from backup if available."""
        if module_path in self.backups:
            try:
                with open(module_path, 'w') as f:
                    f.write(self.backups[module_path])
                logger.info(f"Restored {module_path} from backup")
                return True
            except Exception as e:
                logger.error(f"Failed to restore {module_path}: {e}")
                return False
        return False

    def apply_mutation(self, module_path: str, mutation_func: Callable[[ast.Module], ast.Module]) -> bool:
        """
        Apply a mutation function to the module's AST.
        Returns True if successful, False otherwise.
        """
        if self._lock:
            logger.warning("Rewriter is locked, cannot apply mutation")
            return False

        self.backup(module_path)
        try:
            source = self.read_source(module_path)
            tree = self.parse_to_ast(source)
            mutated_tree = mutation_func(tree)
            new_source = self.ast_to_source(mutated_tree)

            # Write the mutated source back
            with open(module_path, 'w') as f:
                f.write(new_source)

            # Verify the new source is syntactically valid
            compile(new_source, module_path, 'exec')
            logger.info(f"Successfully applied mutation to {module_path}")
            return True
        except Exception as e:
            logger.error(f"Mutation failed for {module_path}: {e}")
            self.restore(module_path)
            return False

# -----------------------------------------------------------------------------
# Mutation strategies for specific modules
# -----------------------------------------------------------------------------

class MutationStrategy:
    """Base class for mutation strategies."""

    def __init__(self, module_name: str):
        self.module_name = module_name

    def generate_mutation(self, tree: ast.Module) -> ast.Module:
        """Override in subclasses to generate specific mutations."""
        raise NotImplementedError

class ReflectionParserMutation(MutationStrategy):
    """Mutations for reflection_parser.py."""

    def generate_mutation(self, tree: ast.Module) -> ast.Module:
        """Add a new field to track reflection depth."""
        # Find the main class and add a new attribute
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Add a new field to __init__ if it exists
                for item in node.body:
                    if isinstance(item, ast.FunctionDef) and item.name == '__init__':
                        # Add a new assignment for reflection_depth
                        new_assign = ast.Assign(
                            targets=[ast.Attribute(
                                value=ast.Name(id='self', ctx=ast.Load()),
                                attr='reflection_depth',
                                ctx=ast.Store()
                            )],
                            value=ast.Constant(value=0)
                        )
                        # Insert after the last assignment in __init__
                        for i, stmt in enumerate(item.body):
                            if isinstance(stmt, ast.Assign):
                                item.body.insert(i+1, new_assign)
                                break
                        break
                break
        return tree

class MetaEvaluationLoopMutation(MutationStrategy):
    """Mutations for meta_evaluation_loop.py."""

    def generate_mutation(self, tree: ast.Module) -> ast.Module:
        """Optimize loop logic by adding early exit conditions."""
        # Find the main loop function and add a break condition
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and 'loop' in node.name.lower():
                # Add an early exit condition based on performance
                for item in node.body:
                    if isinstance(item, ast.For) or isinstance(item, ast.While):
                        # Insert a break if performance threshold met
                        break_condition = ast.If(
                            test=ast.Compare(
                                left=ast.Name(id='performance_score', ctx=ast.Load()),
                                ops=[ast.GtE()],
                                comparators=[ast.Constant(value=0.95)]
                            ),
                            body=[ast.Break()],
                            orelse=[]
                        )
                        item.body.insert(0, break_condition)
                        break
                break
        return tree

class UnifiedEvolutionOrchestratorMutation(MutationStrategy):
    """Mutations for unified_evolution_loop_orchestrator.py."""

    def generate_mutation(self, tree: ast.Module) -> ast.Module:
        """Add bottleneck detection and optimization."""
        # Find the main orchestrator class and add a bottleneck detection method
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and 'orchestrator' in node.name.lower():
                # Add a new method for bottleneck detection
                new_method = ast.FunctionDef(
                    name='detect_bottlenecks',
                    args=ast.arguments(
                        posonlyargs=[],
                        args=[ast.arg(arg='self')],
                        kwonlyargs=[],
                        kw_defaults=[],
                        defaults=[]
                    ),
                    body=[
                        ast.Assign(
                            targets=[ast.Name(id='bottlenecks', ctx=ast.Store())],
                            value=ast.List(elts=[], ctx=ast.Load())
                        ),
                        ast.Return(value=ast.Name(id='bottlenecks', ctx=ast.Load()))
                    ],
                    decorator_list=[]
                )
                node.body.append(new_method)
                break
        return tree

# -----------------------------------------------------------------------------
# Meta-Mutation Engine
# -----------------------------------------------------------------------------

class MetaMutationEngine:
    """
    Main engine that collects stats, analyzes performance, and applies mutations.
    """

    def __init__(self, cycle_interval: int = 10, modules_to_monitor: Optional[List[str]] = None):
        self.cycle_interval = cycle_interval
        self.modules_to_monitor = modules_to_monitor or [
            'reflection_parser',
            'meta_evaluation_loop',
            'unified_evolution_loop_orchestrator'
        ]
        self.performance_data: Dict[str, ModulePerformance] = {
            mod: ModulePerformance(module_name=mod) for mod in self.modules_to_monitor
        }
        self.rewriter = SafeASTRewriter()
        self.current_cycle = 0
        self.stats_history: List[MutationStats] = []
        self.mutation_strategies: Dict[str, MutationStrategy] = {
            'reflection_parser': ReflectionParserMutation('reflection_parser'),
            'meta_evaluation_loop': MetaEvaluationLoopMutation('meta_evaluation_loop'),
            'unified_evolution_loop_orchestrator': UnifiedEvolutionOrchestratorMutation('unified_evolution_loop_orchestrator')
        }
        self.module_paths: Dict[str, str] = self._discover_module_paths()

    def _discover_module_paths(self) -> Dict[str, str]:
        """Discover the file paths for the monitored modules."""
        paths = {}
        for mod_name in self.modules_to_monitor:
            try:
                module = importlib.import_module(mod_name)
                paths[mod_name] = inspect.getfile(module)
            except ImportError:
                # Try to find the file in the current directory
                potential_path = Path(f"{mod_name}.py")
                if potential_path.exists():
                    paths[mod_name] = str(potential_path)
                else:
                    logger.warning(f"Could not find module {mod_name}")
        return paths

    def record_stats(self, stats: MutationStats) -> None:
        """Record performance statistics from a cycle."""
        self.stats_history.append(stats)
        self.current_cycle = stats.cycle_id

        # Update performance data for each module
        for mod_name in self.modules_to_monitor:
            perf = self.performance_data[mod_name]
            perf.recent_stats.append(stats)
            # Update averages
            recent = list(perf.recent_stats)
            if recent:
                perf.avg_mutation_success_rate = sum(s.mutation_success_rate for s in recent) / len(recent)
                perf.avg_test_pass_rate = sum(s.test_pass_rate for s in recent) / len(recent)
                perf.avg_reflection_score = sum(s.reflection_score for s in recent) / len(recent)
                perf.integration_test_failures = sum(1 for s in recent if not s.integration_test_status)

        logger.debug(f"Recorded stats for cycle {stats.cycle_id}")

    def analyze_performance(self) -> List[str]:
        """
        Analyze performance data to identify underperforming modules.
        Returns a list of module names that need mutation.
        """
        underperforming = []
        threshold = 0.7  # Performance threshold

        for mod_name, perf in self.performance_data.items():
            # Check if module is underperforming
            if perf.avg_mutation_success_rate < threshold:
                logger.info(f"{mod_name} has low mutation success rate: {perf.avg_mutation_success_rate:.2f}")
                underperforming.append(mod_name)
            elif perf.avg_test_pass_rate < threshold:
                logger.info(f"{mod_name} has low test pass rate: {perf.avg_test_pass_rate:.2f}")
                underperforming.append(mod_name)
            elif perf.avg_reflection_score < threshold:
                logger.info(f"{mod_name} has low reflection score: {perf.avg_reflection_score:.2f}")
                underperforming.append(mod_name)
            elif perf.integration_test_failures > 5:
                logger.info(f"{mod_name} has too many integration test failures: {perf.integration_test_failures}")
                underperforming.append(mod_name)

        return underperforming

    def generate_mutation_for_module(self, module_name: str) -> Optional[Callable[[ast.Module], ast.Module]]:
        """
        Generate a mutation function for a specific module.
        Returns the mutation function or None if no strategy exists.
        """
        strategy = self.mutation_strategies.get(module_name)
        if strategy:
            return strategy.generate_mutation
        return None

    def apply_mutation(self, module_name: str) -> bool:
        """
        Apply a mutation to the specified module.
        Returns True if successful, False otherwise.
        """
        if module_name not in self.module_paths:
            logger.error(f"No path found for module {module_name}")
            return False

        module_path = self.module_paths[module_name]
        mutation_func = self.generate_mutation_for_module(module_name)

        if mutation_func is None:
            logger.warning(f"No mutation strategy for {module_name}")
            return False

        # Apply the mutation with rollback
        success = self.rewriter.apply_mutation(module_path, mutation_func)
        if success:
            self.performance_data[module_name].mutation_count += 1
            self.performance_data[module_name].last_mutation_time = time.time()
            logger.info(f"Mutation applied to {module_name}")
        else:
            logger.error(f"Mutation failed for {module_name}")

        return success

    def rollback_mutation(self, module_name: str) -> bool:
        """Rollback the last mutation for a module."""
        if module_name not in self.module_paths:
            return False
        module_path = self.module_paths[module_name]
        return self.rewriter.restore(module_path)

    def run_cycle(self, stats: MutationStats) -> Dict[str, Any]:
        """
        Run a single cycle of the meta-mutation engine.
        Records stats, analyzes performance, and applies mutations if needed.
        Returns a summary of actions taken.
        """
        self.record_stats(stats)
        actions = {'mutations_applied': [], 'mutations_rolled_back': [], 'analysis': []}

        # Check if we should analyze (every cycle_interval cycles)
        if self.current_cycle % self.cycle_interval == 0:
            logger.info(f"Running performance analysis at cycle {self.current_cycle}")
            underperforming = self.analyze_performance()
            actions['analysis'] = underperforming

            for mod_name in underperforming:
                # Try to apply a mutation
                if self.apply_mutation(mod_name):
                    actions['mutations_applied'].append(mod_name)
                else:
                    # If mutation fails, rollback
                    if self.rollback_mutation(mod_name):
                        actions['mutations_rolled_back'].append(mod_name)
                        logger.info(f"Rolled back mutation for {mod_name}")

        return actions

    def get_performance_summary(self) -> Dict[str, Dict[str, float]]:
        """Get a summary of performance data for all modules."""
        summary = {}
        for mod_name, perf in self.performance_data.items():
            summary[mod_name] = {
                'avg_mutation_success_rate': perf.avg_mutation_success_rate,
                'avg_test_pass_rate': perf.avg_test_pass_rate,
                'avg_reflection_score': perf.avg_reflection_score,
                'integration_test_failures': perf.integration_test_failures,
                'mutation_count': perf.mutation_count,
                'last_mutation_time': perf.last_mutation_time
            }
        return summary

# -----------------------------------------------------------------------------
# Utility functions for external integration
# -----------------------------------------------------------------------------

def create_engine(cycle_interval: int = 10) -> MetaMutationEngine:
    """Factory function to create a MetaMutationEngine instance."""
    return MetaMutationEngine(cycle_interval=cycle_interval)

def record_and_analyze(engine: MetaMutationEngine, stats: MutationStats) -> Dict[str, Any]:
    """Convenience function to record stats and run analysis."""
    return engine.run_cycle(stats)

# -----------------------------------------------------------------------------
# Example usage (if run as script)
# -----------------------------------------------------------------------------

if __name__ == '__main__':
    # Example of how to use the engine
    engine = create_engine(cycle_interval=5)

    # Simulate some cycles
    for cycle in range(20):
        stats = MutationStats(
            cycle_id=cycle,
            mutation_success_rate=0.6 + (cycle * 0.02) % 0.4,
            test_pass_rate=0.7 + (cycle * 0.01) % 0.3,
            integration_test_status=cycle % 3 != 0,
            reflection_score=0.5 + (cycle * 0.03) % 0.5
        )
        actions = engine.run_cycle(stats)
        if actions['mutations_applied']:
            print(f"Cycle {cycle}: Applied mutations to {actions['mutations_applied']}")
        if actions['mutations_rolled_back']:
            print(f"Cycle {cycle}: Rolled back mutations for {actions['mutations_rolled_back']}")

    # Print final performance summary
    summary = engine.get_performance_summary()
    for mod, data in summary.items():
        print(f"{mod}: {data}")