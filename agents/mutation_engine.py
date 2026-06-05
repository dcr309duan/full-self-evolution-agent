from . import clone_and_promote
from . import static_validator
import logging

logger = logging.getLogger(__name__)

class MutationEngine:
    def __init__(self, strategy_tracker=None):
        self.strategy_tracker = strategy_tracker or {}
        self.static_validation_failures = 0

    def trigger_e2e_validation(self, mutated_module_path):
        """
        Trigger the end-to-end validation test suite on the mutated module.
        
        Args:
            mutated_module_path: Path to the mutated module to validate
        """
        logger.info(f"Triggering e2e validation for mutated module: {mutated_module_path}")
        # Invoke the test suite on the mutated module
        import subprocess
        import sys
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", mutated_module_path, "-v"],
                capture_output=True,
                text=True,
                timeout=300
            )
            if result.returncode == 0:
                logger.info(f"e2e validation passed for {mutated_module_path}")
            else:
                logger.error(f"e2e validation failed for {mutated_module_path}: {result.stderr}")
        except subprocess.TimeoutExpired:
            logger.error(f"e2e validation timed out for {mutated_module_path}")
        except Exception as e:
            logger.error(f"e2e validation error for {mutated_module_path}: {str(e)}")

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
        
        # Post-mutation hook: trigger e2e validation if mutation was successful
        if result is not None:
            mutated_module_path = result.get('mutated_path', module_path) if isinstance(result, dict) else module_path
            self.trigger_e2e_validation(mutated_module_path)
        
        logger.info(f"Mutation '{mutation_strategy_name}' completed with result: {result} (static validation: passed)")
        return result