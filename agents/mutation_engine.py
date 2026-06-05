from . import clone_and_promote
import logging

logger = logging.getLogger(__name__)

class MutationEngine:
    def __init__(self, strategy_tracker=None):
        self.strategy_tracker = strategy_tracker or {}

    def apply_mutation(self, module_path, mutation_function, mutation_strategy_name):
        """
        Apply a mutation using the clone-and-promote mechanism for safety.
        
        Args:
            module_path: Path to the module to mutate
            mutation_function: The mutation function to apply
            mutation_strategy_name: Name of the mutation strategy being used
            
        Returns:
            Result of the mutation operation
        """
        logger.info(f"Applying mutation strategy '{mutation_strategy_name}' to {module_path}")
        
        # Track strategy usage
        if mutation_strategy_name not in self.strategy_tracker:
            self.strategy_tracker[mutation_strategy_name] = 0
        self.strategy_tracker[mutation_strategy_name] += 1
        
        # Use clone-and-promote safe wrapper instead of direct mutation
        result = clone_and_promote.safe_mutate(
            module_path=module_path,
            mutation_function=mutation_function,
            mutation_strategy_name=mutation_strategy_name
        )
        
        logger.info(f"Mutation '{mutation_strategy_name}' completed with result: {result}")
        return result