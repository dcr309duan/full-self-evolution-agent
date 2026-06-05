from . import clone_and_promote
from . import static_validator
import logging

logger = logging.getLogger(__name__)

class MutationEngine:
    def __init__(self, strategy_tracker=None):
        self.strategy_tracker = strategy_tracker or {}
        self.static_validation_failures = 0

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
        
        # Static validation before mutation
        validation_result = static_validator.validate_module_ast(module_path)
        if not validation_result:
            logger.error(f"Static validation failed for {module_path}: {validation_result.details}")
            self.static_validation_failures += 1
            logger.info(f"Mutation '{mutation_strategy_name}' skipped due to static validation failure")
            return None
        
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
        
        logger.info(f"Mutation '{mutation_strategy_name}' completed with result: {result} (static validation: passed)")
        return result