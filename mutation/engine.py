"""Mutation engine integrating FailurePatternClassifier and strategy selector."""

import ast
import copy
import logging
import random
from typing import Any, Callable, Dict, List, Optional, Tuple

from mutation.classifier import FailurePatternClassifier
from mutation.strategies import StrategySelector, MutationStrategy

logger = logging.getLogger(__name__)


class WrapperMutationStrategy(MutationStrategy):
    """Mutation strategy that wraps function calls with modified behavior instead of AST rewriting."""

    def __init__(self, mutation_type: str = "wrapper"):
        super().__init__(mutation_type)
        self._wrappers: Dict[str, Callable] = {}

    def apply(self, code: str) -> str:
        """Apply wrapper-based mutation by injecting wrapper code around function calls."""
        # Parse the code to find function definitions and calls
        tree = ast.parse(code)
        wrapper_injector = _WrapperInjector(self._wrappers)
        modified_tree = wrapper_injector.visit(tree)
        return ast.unparse(modified_tree)

    def register_wrapper(self, func_name: str, wrapper_fn: Callable) -> None:
        """Register a wrapper function for a specific function name."""
        self._wrappers[func_name] = wrapper_fn

    def clear_wrappers(self) -> None:
        """Clear all registered wrappers."""
        self._wrappers.clear()


class _WrapperInjector(ast.NodeTransformer):
    """AST transformer that injects wrapper calls around function calls."""

    def __init__(self, wrappers: Dict[str, Callable]):
        self._wrappers = wrappers

    def visit_Call(self, node: ast.Call) -> ast.AST:
        """Wrap function calls that have registered wrappers."""
        self.generic_visit(node)

        # Determine the function name
        func_name = None
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            func_name = node.func.attr

        if func_name and func_name in self._wrappers:
            # Replace the call with a wrapper call
            wrapper_name = f"_mutation_wrapper_{func_name}"
            wrapper_call = ast.Call(
                func=ast.Name(id=wrapper_name, ctx=ast.Load()),
                args=[node],
                keywords=[],
            )
            return wrapper_call

        return node

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        """Inject wrapper function definitions for registered functions."""
        self.generic_visit(node)

        # Add wrapper function definitions after the original function
        wrappers_to_add = []
        for func_name, wrapper_fn in self._wrappers.items():
            if func_name == node.name:
                # Create a wrapper function that calls the original with modified behavior
                wrapper_def = self._create_wrapper_def(func_name, wrapper_fn)
                wrappers_to_add.append(wrapper_def)

        if wrappers_to_add:
            # Insert wrappers after the function definition
            new_body = [node] + wrappers_to_add
            return new_body

        return node

    def _create_wrapper_def(self, func_name: str, wrapper_fn: Callable) -> ast.FunctionDef:
        """Create an AST for a wrapper function."""
        # This creates a wrapper that calls the original function and applies the wrapper logic
        wrapper_code = f"""
def _mutation_wrapper_{func_name}(original_call):
    return wrapper_fn(original_call)
"""
        wrapper_tree = ast.parse(wrapper_code)
        return wrapper_tree.body[0]


class MutationEngine:
    """Engine that orchestrates mutation testing with failure pattern classification and strategy selection."""

    def __init__(
        self,
        classifier: Optional[FailurePatternClassifier] = None,
        strategy_selector: Optional[StrategySelector] = None,
        strategies: Optional[List[MutationStrategy]] = None,
    ):
        self._classifier = classifier or FailurePatternClassifier()
        self._strategy_selector = strategy_selector or StrategySelector()
        self._strategies = strategies or []
        self._current_strategy: Optional[MutationStrategy] = None
        self._target_strategy_map: Dict[str, MutationStrategy] = {}
        self._mutation_history: List[Dict[str, Any]] = []

        # Initialize default strategies if none provided
        if not self._strategies:
            self._strategies = [WrapperMutationStrategy()]

    def set_strategies(self, strategies: List[MutationStrategy]) -> None:
        """Set the available mutation strategies."""
        self._strategies = strategies

    def mutate(self, code: str, target_id: str, context: Optional[Dict[str, Any]] = None) -> Tuple[str, bool]:
        """Apply mutation to code and log results to classifier.

        Args:
            code: Source code to mutate
            target_id: Identifier for the mutation target
            context: Optional context information for classification

        Returns:
            Tuple of (mutated_code, success)
        """
        context = context or {}

        # Check if strategy switch is needed for this target
        self._check_strategy_switch(target_id)

        # Select strategy if not already set
        if self._current_strategy is None:
            self._current_strategy = self._select_strategy(target_id)

        # Apply mutation
        try:
            mutated_code = self._current_strategy.apply(code)
            success = mutated_code != code  # Mutation was applied if code changed
        except Exception as e:
            logger.error(f"Mutation failed for target {target_id}: {e}")
            mutated_code = code
            success = False

        # Log result to classifier
        mutation_record = {
            "target_id": target_id,
            "strategy": self._current_strategy.strategy_type,
            "success": success,
            "context": context,
        }
        self._mutation_history.append(mutation_record)
        self._classifier.log_mutation_result(mutation_record)

        # If failure, query classifier for recommended strategy change
        if not success:
            recommended_strategy = self._classifier.recommend_strategy(target_id, context)
            if recommended_strategy:
                self._handle_strategy_recommendation(target_id, recommended_strategy)

        return mutated_code, success

    def _select_strategy(self, target_id: str) -> MutationStrategy:
        """Select the best strategy for the given target."""
        # Check if we have a stored strategy for this target
        if target_id in self._target_strategy_map:
            return self._target_strategy_map[target_id]

        # Use strategy selector to pick one
        strategy_type = self._strategy_selector.select_strategy(target_id)
        for strategy in self._strategies:
            if strategy.strategy_type == strategy_type:
                self._target_strategy_map[target_id] = strategy
                return strategy

        # Fallback to first available strategy
        if self._strategies:
            return self._strategies[0]

        raise ValueError("No mutation strategies available")

    def _check_strategy_switch(self, target_id: str) -> None:
        """Check if a strategy switch is needed before mutating a target."""
        if target_id in self._target_strategy_map:
            current = self._target_strategy_map[target_id]
            # Query classifier if we should switch
            should_switch = self._classifier.should_switch_strategy(target_id, current.strategy_type)
            if should_switch:
                new_strategy = self._select_strategy(target_id)
                if new_strategy != current:
                    logger.info(f"Switching strategy for target {target_id}: {current.strategy_type} -> {new_strategy.strategy_type}")
                    self._target_strategy_map[target_id] = new_strategy
                    self._current_strategy = new_strategy

    def _handle_strategy_recommendation(self, target_id: str, recommended_strategy: str) -> None:
        """Handle a strategy recommendation from the classifier."""
        logger.info(f"Received strategy recommendation for {target_id}: {recommended_strategy}")
        # Find the recommended strategy
        for strategy in self._strategies:
            if strategy.strategy_type == recommended_strategy:
                self._target_strategy_map[target_id] = strategy
                self._current_strategy = strategy
                break

    def get_mutation_history(self) -> List[Dict[str, Any]]:
        """Get the history of all mutation attempts."""
        return self._mutation_history.copy()

    def get_classifier(self) -> FailurePatternClassifier:
        """Get the failure pattern classifier instance."""
        return self._classifier

    def get_strategy_selector(self) -> StrategySelector:
        """Get the strategy selector instance."""
        return self._strategy_selector

    def reset(self) -> None:
        """Reset the engine state."""
        self._current_strategy = None
        self._target_strategy_map.clear()
        self._mutation_history.clear()
        self._classifier.reset()
        self._strategy_selector.reset()