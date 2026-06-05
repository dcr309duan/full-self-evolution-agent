from . import test_integration_pipeline
from . import test_pipeline_orchestrator
from . import integration_validator
from . import test_self_consistency
from . import test_end_to_end_pipeline

def run_pre_generation_tests():
    """
    Executes test_end_to_end_pipeline.py and returns success/failure status.
    
    Returns:
        bool: True if all tests pass, False otherwise.
    """
    try:
        test_end_to_end_pipeline.run_tests()
        return True
    except Exception:
        return False