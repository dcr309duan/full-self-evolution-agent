import unittest
from unittest.mock import patch, MagicMock
from core.nash_detector_and_forcer import NashEquilibriumDetector, NashForcer, CoordinatedChangeManager

class TestCoordinatedChange(unittest.TestCase):
    """Integration tests for coordinated multi-module changes using Nash equilibrium detection and forcing."""

    def setUp(self):
        self.detector = NashEquilibriumDetector()
        self.forcer = NashForcer()
        self.change_manager = CoordinatedChangeManager(self.detector, self.forcer)
        self.mock_modules = {
            'module_a': {'state': 'initial', 'deps': ['module_b']},
            'module_b': {'state': 'initial', 'deps': ['module_c']},
            'module_c': {'state': 'initial', 'deps': []}
        }

    def test_atomic_change_application(self):
        """Verify that coordinated changes are applied atomically across all modules."""
        changes = [
            {'module': 'module_a', 'new_state': 'changed_a'},
            {'module': 'module_b', 'new_state': 'changed_b'},
            {'module': 'module_c', 'new_state': 'changed_c'}
        ]
        with patch.object(self.change_manager, '_apply_change', side_effect=lambda m, s: self.mock_modules[m].update({'state': s})):
            success = self.change_manager.apply_coordinated_changes(changes)
            self.assertTrue(success)
            for mod in ['module_a', 'module_b', 'module_c']:
                self.assertEqual(self.mock_modules[mod]['state'], f'changed_{mod[-1]}')

    def test_partial_failure_rollback(self):
        """Verify that partial failures trigger proper rollback of all changes."""
        changes = [
            {'module': 'module_a', 'new_state': 'will_fail'},
            {'module': 'module_b', 'new_state': 'should_rollback'},
            {'module': 'module_c', 'new_state': 'also_rollback'}
        ]
        original_states = {mod: data['state'] for mod, data in self.mock_modules.items()}
        
        def failing_apply(module, state):
            if module == 'module_a':
                raise RuntimeError("Simulated failure in module_a")
            self.mock_modules[module]['state'] = state
        
        with patch.object(self.change_manager, '_apply_change', side_effect=failing_apply):
            success = self.change_manager.apply_coordinated_changes(changes)
            self.assertFalse(success)
            # Verify all modules rolled back to original states
            for mod, orig_state in original_states.items():
                self.assertEqual(self.mock_modules[mod]['state'], orig_state)

    def test_nash_equilibrium_preserved_after_change(self):
        """Verify that after a successful coordinated change, the system remains in Nash equilibrium."""
        # Setup initial equilibrium
        self.detector.detect_equilibrium = MagicMock(return_value=True)
        changes = [
            {'module': 'module_a', 'new_state': 'equilibrium_state'},
            {'module': 'module_b', 'new_state': 'equilibrium_state'}
        ]
        with patch.object(self.change_manager, '_apply_change', side_effect=lambda m, s: self.mock_modules[m].update({'state': s})):
            success = self.change_manager.apply_coordinated_changes(changes)
            self.assertTrue(success)
            self.detector.detect_equilibrium.assert_called_once()

    def test_rollback_restores_original_equilibrium(self):
        """Verify that rollback restores the original Nash equilibrium state."""
        original_equilibrium = {'module_a': 'eq_a', 'module_b': 'eq_b'}
        self.detector.get_current_equilibrium = MagicMock(return_value=original_equilibrium)
        
        changes = [
            {'module': 'module_a', 'new_state': 'fail_state'},
            {'module': 'module_b', 'new_state': 'fail_state'}
        ]
        
        def failing_apply(module, state):
            if module == 'module_a':
                raise RuntimeError("Simulated failure")
            self.mock_modules[module]['state'] = state
        
        with patch.object(self.change_manager, '_apply_change', side_effect=failing_apply):
            success = self.change_manager.apply_coordinated_changes(changes)
            self.assertFalse(success)
            # Verify original equilibrium is restored
            for mod, state in original_equilibrium.items():
                self.assertEqual(self.mock_modules[mod]['state'], state)

    def test_change_order_preserved(self):
        """Verify that changes are applied in the specified order and rolled back in reverse."""
        applied_order = []
        rolled_back_order = []
        
        def tracking_apply(module, state):
            applied_order.append(module)
            self.mock_modules[module]['state'] = state
            if module == 'module_b':
                raise RuntimeError("Simulated failure in module_b")
        
        def tracking_rollback(module):
            rolled_back_order.append(module)
            self.mock_modules[module]['state'] = 'initial'
        
        changes = [
            {'module': 'module_a', 'new_state': 'new_a'},
            {'module': 'module_b', 'new_state': 'new_b'},
            {'module': 'module_c', 'new_state': 'new_c'}
        ]
        
        with patch.object(self.change_manager, '_apply_change', side_effect=tracking_apply):
            with patch.object(self.change_manager, '_rollback_change', side_effect=tracking_rollback):
                success = self.change_manager.apply_coordinated_changes(changes)
                self.assertFalse(success)
                # Verify apply order: a, b (fails), c never applied
                self.assertEqual(applied_order, ['module_a', 'module_b'])
                # Verify rollback order: b (failed), a (reverse order)
                self.assertEqual(rolled_back_order, ['module_b', 'module_a'])

if __name__ == '__main__':
    unittest.main()