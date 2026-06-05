import pytest
from unittest.mock import Mock, patch, MagicMock
from src.meta_cognitive_evaluator import MetaCognitiveEvaluator
from src.orchestrator import Orchestrator

@pytest.fixture
def evaluator():
    """Fixture to create a MetaCognitiveEvaluator instance with mocked dependencies."""
    mock_orchestrator = Mock(spec=Orchestrator)
    mock_orchestrator.cycle_counter = 0
    return MetaCognitiveEvaluator(orchestrator=mock_orchestrator)

@pytest.fixture
def evaluator_with_cycles():
    """Fixture with a specific cycle counter for integration testing."""
    mock_orchestrator = Mock(spec=Orchestrator)
    mock_orchestrator.cycle_counter = 100
    return MetaCognitiveEvaluator(orchestrator=mock_orchestrator)

class TestMetaCognitiveEvaluator:
    """Unit tests for MetaCognitiveEvaluator."""

    def test_compute_fitness_capability_ratio(self, evaluator):
        """Test that fitness/capability ratio is computed correctly."""
        # Arrange
        evaluator.capability = 50.0
        evaluator.fitness = 25.0
        
        # Act
        ratio = evaluator.compute_fitness_capability_ratio()
        
        # Assert
        expected_ratio = 25.0 / 50.0  # 0.5
        assert ratio == pytest.approx(0.5), f"Expected {expected_ratio}, got {ratio}"

    def test_compute_fitness_capability_ratio_zero_capability(self, evaluator):
        """Test ratio computation when capability is zero."""
        # Arrange
        evaluator.capability = 0.0
        evaluator.fitness = 10.0
        
        # Act
        ratio = evaluator.compute_fitness_capability_ratio()
        
        # Assert
        assert ratio == float('inf'), "Ratio should be infinite when capability is zero"

    def test_trigger_pruning_when_ratio_below_threshold(self, evaluator):
        """Test that pruning is triggered when ratio < 0.1."""
        # Arrange
        evaluator.capability = 100.0
        evaluator.fitness = 5.0  # ratio = 0.05 < 0.1
        evaluator.prune_modules = MagicMock(return_value=True)
        
        # Act
        result = evaluator.evaluate_and_prune()
        
        # Assert
        assert result is True, "Pruning should be triggered when ratio < 0.1"
        evaluator.prune_modules.assert_called_once()

    def test_no_pruning_when_ratio_above_threshold(self, evaluator):
        """Test that pruning is not triggered when ratio >= 0.1."""
        # Arrange
        evaluator.capability = 100.0
        evaluator.fitness = 20.0  # ratio = 0.2 >= 0.1
        evaluator.prune_modules = MagicMock(return_value=False)
        
        # Act
        result = evaluator.evaluate_and_prune()
        
        # Assert
        assert result is False, "Pruning should not be triggered when ratio >= 0.1"
        evaluator.prune_modules.assert_not_called()

    def test_trigger_pruning_at_exact_threshold(self, evaluator):
        """Test boundary condition: ratio exactly 0.1 should not trigger pruning."""
        # Arrange
        evaluator.capability = 100.0
        evaluator.fitness = 10.0  # ratio = 0.1 exactly
        evaluator.prune_modules = MagicMock(return_value=False)
        
        # Act
        result = evaluator.evaluate_and_prune()
        
        # Assert
        assert result is False, "Pruning should not be triggered when ratio == 0.1"
        evaluator.prune_modules.assert_not_called()

    def test_identify_low_impact_modules(self, evaluator):
        """Test that low-impact modules are correctly identified based on usage frequency."""
        # Arrange
        module_usage = {
            'module_a': 50,   # high usage
            'module_b': 3,    # low usage
            'module_c': 100,  # high usage
            'module_d': 1,    # low usage
            'module_e': 0     # never used
        }
        evaluator.module_usage_frequency = module_usage
        evaluator.low_impact_threshold = 5  # modules with usage < 5 are low-impact
        
        # Act
        low_impact_modules = evaluator.identify_low_impact_modules()
        
        # Assert
        expected_low_impact = ['module_b', 'module_d', 'module_e']
        assert sorted(low_impact_modules) == sorted(expected_low_impact), \
            f"Expected {expected_low_impact}, got {low_impact_modules}"

    def test_identify_low_impact_modules_empty_usage(self, evaluator):
        """Test identification when no modules have been used."""
        # Arrange
        evaluator.module_usage_frequency = {}
        evaluator.low_impact_threshold = 5
        
        # Act
        low_impact_modules = evaluator.identify_low_impact_modules()
        
        # Assert
        assert low_impact_modules == [], "Should return empty list when no usage data"

    def test_identify_low_impact_modules_all_high_usage(self, evaluator):
        """Test identification when all modules have high usage."""
        # Arrange
        module_usage = {
            'module_a': 10,
            'module_b': 20,
            'module_c': 15
        }
        evaluator.module_usage_frequency = module_usage
        evaluator.low_impact_threshold = 5
        
        # Act
        low_impact_modules = evaluator.identify_low_impact_modules()
        
        # Assert
        assert low_impact_modules == [], "Should return empty list when all modules have high usage"

    def test_integration_with_orchestrator_cycle_counter(self, evaluator_with_cycles):
        """Test integration with orchestrator's cycle counter."""
        # Arrange
        evaluator = evaluator_with_cycles
        initial_cycle = evaluator.orchestrator.cycle_counter
        
        # Act
        evaluator.orchestrator.cycle_counter += 1  # simulate cycle increment
        evaluator.update_cycle_based_metrics()
        
        # Assert
        assert evaluator.orchestrator.cycle_counter == initial_cycle + 1, \
            "Cycle counter should be incremented"
        assert evaluator.current_cycle == initial_cycle + 1, \
            "Evaluator should track the current cycle"

    def test_cycle_counter_affects_pruning_decision(self, evaluator_with_cycles):
        """Test that cycle counter influences pruning decisions."""
        # Arrange
        evaluator = evaluator_with_cycles
        evaluator.capability = 100.0
        evaluator.fitness = 5.0  # ratio = 0.05 < 0.1
        evaluator.prune_modules = MagicMock(return_value=True)
        
        # Simulate that pruning is only allowed after certain cycles
        evaluator.min_cycles_before_pruning = 50
        
        # Act
        result = evaluator.evaluate_and_prune()
        
        # Assert
        assert result is True, "Pruning should be allowed after sufficient cycles"
        evaluator.prune_modules.assert_called_once()

    def test_cycle_counter_prevents_early_pruning(self, evaluator):
        """Test that pruning is prevented before minimum cycles."""
        # Arrange
        evaluator.capability = 100.0
        evaluator.fitness = 5.0  # ratio = 0.05 < 0.1
        evaluator.prune_modules = MagicMock(return_value=False)
        evaluator.min_cycles_before_pruning = 50
        evaluator.orchestrator.cycle_counter = 10  # below minimum
        
        # Act
        result = evaluator.evaluate_and_prune()
        
        # Assert
        assert result is False, "Pruning should be prevented before minimum cycles"
        evaluator.prune_modules.assert_not_called()

    def test_full_evaluation_cycle(self, evaluator):
        """Test a complete evaluation cycle including ratio computation and pruning decision."""
        # Arrange
        evaluator.capability = 200.0
        evaluator.fitness = 15.0  # ratio = 0.075 < 0.1
        evaluator.module_usage_frequency = {
            'module_x': 2,
            'module_y': 50,
            'module_z': 1
        }
        evaluator.low_impact_threshold = 5
        evaluator.prune_modules = MagicMock(return_value=True)
        
        # Act
        ratio = evaluator.compute_fitness_capability_ratio()
        low_impact = evaluator.identify_low_impact_modules()
        pruned = evaluator.evaluate_and_prune()
        
        # Assert
        assert ratio == pytest.approx(0.075), "Ratio should be 0.075"
        assert sorted(low_impact) == sorted(['module_x', 'module_z']), \
            "Should identify low-impact modules"
        assert pruned is True, "Pruning should be triggered"

    def test_evaluate_and_prune_no_low_impact_modules(self, evaluator):
        """Test evaluation when no low-impact modules exist but ratio is low."""
        # Arrange
        evaluator.capability = 100.0
        evaluator.fitness = 5.0  # ratio = 0.05 < 0.1
        evaluator.module_usage_frequency = {
            'module_a': 10,
            'module_b': 20
        }
        evaluator.low_impact_threshold = 5
        evaluator.prune_modules = MagicMock(return_value=True)
        
        # Act
        result = evaluator.evaluate_and_prune()
        
        # Assert
        assert result is True, "Pruning should still be triggered even without low-impact modules"
        evaluator.prune_modules.assert_called_once()