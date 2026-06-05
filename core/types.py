from typing import Dict, List, Tuple, Union, Any

# Type aliases for Nash equilibrium analysis and coordinated mutation

# NashState: Maps module names to their success rates (0.0 to 1.0)
NashState = Dict[str, float]

# MultiModuleChange: A list of (module_name, change_description) tuples
# describing coordinated changes to apply across multiple modules
MultiModuleChange = List[Tuple[str, str]]

# InteractionRecord: Records the success rate of interactions between two modules
InteractionRecord = Tuple[str, str, float]

# For backward compatibility, also export as generic types if needed
# These aliases allow existing code that uses these names to continue working
# even if the internal representation changes in the future.

# Optional: Provide a function to create a NashState with validation
def create_nash_state(initial: Dict[str, float] = None) -> NashState:
    """Create a NashState dictionary with optional initial values.
    
    Args:
        initial: Optional dictionary mapping module names to success rates.
                 Values should be between 0.0 and 1.0.
    
    Returns:
        A NashState dictionary.
    """
    state: NashState = {}
    if initial:
        for module, rate in initial.items():
            if not isinstance(module, str):
                raise TypeError(f"Module name must be a string, got {type(module)}")
            if not isinstance(rate, (int, float)):
                raise TypeError(f"Success rate must be a number, got {type(rate)}")
            state[module] = float(rate)
    return state

# Optional: Provide a function to create a MultiModuleChange with validation
def create_multi_module_change(changes: List[Tuple[str, str]] = None) -> MultiModuleChange:
    """Create a MultiModuleChange list with optional initial changes.
    
    Args:
        changes: Optional list of (module_name, change_description) tuples.
    
    Returns:
        A MultiModuleChange list.
    """
    mmc: MultiModuleChange = []
    if changes:
        for module, desc in changes:
            if not isinstance(module, str):
                raise TypeError(f"Module name must be a string, got {type(module)}")
            if not isinstance(desc, str):
                raise TypeError(f"Change description must be a string, got {type(desc)}")
            mmc.append((module, desc))
    return mmc

# Optional: Provide a function to create an InteractionRecord with validation
def create_interaction_record(module_a: str, module_b: str, success_rate: float) -> InteractionRecord:
    """Create an InteractionRecord tuple with validation.
    
    Args:
        module_a: Name of the first module.
        module_b: Name of the second module.
        success_rate: Success rate of the interaction (0.0 to 1.0).
    
    Returns:
        An InteractionRecord tuple.
    """
    if not isinstance(module_a, str):
        raise TypeError(f"module_a must be a string, got {type(module_a)}")
    if not isinstance(module_b, str):
        raise TypeError(f"module_b must be a string, got {type(module_b)}")
    if not isinstance(success_rate, (int, float)):
        raise TypeError(f"success_rate must be a number, got {type(success_rate)}")
    return (module_a, module_b, float(success_rate))