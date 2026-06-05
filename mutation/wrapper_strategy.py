"""Wrapper-based mutation strategy for intercepting and transforming function calls."""

import inspect
import functools
from typing import Any, Callable, Dict, Optional, Tuple


def analyze_function(func: Callable) -> Dict[str, Any]:
    """Analyze a function's signature and return metadata."""
    sig = inspect.signature(func)
    params = list(sig.parameters.values())
    
    return {
        'name': func.__name__,
        'module': func.__module__,
        'signature': sig,
        'parameters': params,
        'return_annotation': sig.return_annotation,
        'num_params': len(params),
        'param_names': [p.name for p in params],
        'has_varargs': any(p.kind == inspect.Parameter.VAR_POSITIONAL for p in params),
        'has_kwargs': any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params),
    }


def create_wrapper(func: Callable, 
                   input_transform: Optional[Callable] = None,
                   output_transform: Optional[Callable] = None) -> Callable:
    """Create a wrapper function that intercepts calls and applies transformations.
    
    Args:
        func: The original function to wrap
        input_transform: Optional function to transform inputs (args, kwargs) -> (args, kwargs)
        output_transform: Optional function to transform the return value
        
    Returns:
        Wrapper function that preserves the original function's signature
    """
    analysis = analyze_function(func)
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Apply input transformation if provided
        if input_transform:
            args, kwargs = input_transform(args, kwargs)
        
        # Call the original function
        result = func(*args, **kwargs)
        
        # Apply output transformation if provided
        if output_transform:
            result = output_transform(result)
        
        return result
    
    return wrapper


def inject_wrapper(module: Any, func_name: str, wrapper: Callable) -> Callable:
    """Inject a wrapper function into a module, replacing the original.
    
    Args:
        module: The module containing the function to replace
        func_name: Name of the function to replace
        wrapper: The wrapper function to inject
        
    Returns:
        The original function (for rollback purposes)
    """
    original = getattr(module, func_name)
    setattr(module, func_name, wrapper)
    return original


def rollback(module: Any, func_name: str, original: Callable) -> None:
    """Restore the original function in the module.
    
    Args:
        module: The module containing the patched function
        func_name: Name of the function to restore
        original: The original function to restore
    """
    setattr(module, func_name, original)


class WrapperMutation:
    """Context manager for applying and rolling back wrapper mutations."""
    
    def __init__(self, module: Any, func_name: str,
                 input_transform: Optional[Callable] = None,
                 output_transform: Optional[Callable] = None):
        self.module = module
        self.func_name = func_name
        self.input_transform = input_transform
        self.output_transform = output_transform
        self.original_func = None
        self.wrapper = None
    
    def __enter__(self):
        func = getattr(self.module, self.func_name)
        self.wrapper = create_wrapper(func, self.input_transform, self.output_transform)
        self.original_func = inject_wrapper(self.module, self.func_name, self.wrapper)
        return self.wrapper
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.original_func:
            rollback(self.module, self.func_name, self.original_func)


# Test cases
def test_double_return_value():
    """Test wrapping a function to double its return value."""
    import math
    
    # Original function
    original_sqrt = math.sqrt
    
    # Create wrapper that doubles the result
    double_transform = lambda x: x * 2
    wrapper = create_wrapper(math.sqrt, output_transform=double_transform)
    
    # Inject wrapper
    original = inject_wrapper(math, 'sqrt', wrapper)
    
    try:
        # Test the wrapped function
        assert math.sqrt(4) == 4.0  # sqrt(4) = 2, doubled = 4
        assert math.sqrt(9) == 6.0  # sqrt(9) = 3, doubled = 6
        assert math.sqrt(16) == 8.0  # sqrt(16) = 4, doubled = 8
        print("test_double_return_value PASSED")
    finally:
        # Rollback
        rollback(math, 'sqrt', original)


def test_input_transformation():
    """Test wrapping a function to transform its inputs."""
    # Create a simple add function
    def add(a, b):
        return a + b
    
    # Create wrapper that doubles the first argument
    def double_first(args, kwargs):
        if args:
            args = (args[0] * 2,) + args[1:]
        return args, kwargs
    
    wrapper = create_wrapper(add, input_transform=double_first)
    
    # Test the wrapper
    assert wrapper(3, 4) == 10  # 3*2 + 4 = 10
    assert wrapper(5, 6) == 16  # 5*2 + 6 = 16
    print("test_input_transformation PASSED")


def test_context_manager():
    """Test the context manager for automatic rollback."""
    import math
    
    with WrapperMutation(math, 'sqrt', output_transform=lambda x: x * 2):
        assert math.sqrt(4) == 4.0
        assert math.sqrt(9) == 6.0
    
    # After context, original function should be restored
    assert math.sqrt(4) == 2.0
    assert math.sqrt(9) == 3.0
    print("test_context_manager PASSED")


def test_signature_preservation():
    """Test that wrapper preserves the original function's signature."""
    def example(a: int, b: str = "default", *args, **kwargs) -> bool:
        return True
    
    wrapper = create_wrapper(example)
    
    # Check that wrapper has same signature
    assert wrapper.__name__ == example.__name__
    assert wrapper.__doc__ == example.__doc__
    
    import inspect
    original_sig = inspect.signature(example)
    wrapper_sig = inspect.signature(wrapper)
    assert str(original_sig) == str(wrapper_sig)
    print("test_signature_preservation PASSED")


def test_rollback():
    """Test manual rollback functionality."""
    import math
    
    original_sqrt = math.sqrt
    
    # Create and inject wrapper
    wrapper = create_wrapper(math.sqrt, output_transform=lambda x: x * 2)
    original = inject_wrapper(math, 'sqrt', wrapper)
    
    # Verify wrapper is active
    assert math.sqrt(4) == 4.0
    
    # Rollback
    rollback(math, 'sqrt', original)
    
    # Verify original is restored
    assert math.sqrt(4) == 2.0
    assert math.sqrt is original_sqrt
    print("test_rollback PASSED")


if __name__ == "__main__":
    test_double_return_value()
    test_input_transformation()
    test_context_manager()
    test_signature_preservation()
    test_rollback()
    print("\nAll tests passed!")