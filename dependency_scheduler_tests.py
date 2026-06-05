import pytest
from dependency_scheduler import DependencyScheduler
from module_state_store import ModuleStateStore
from unittest.mock import Mock, patch

@pytest.fixture
def sample_manifest():
    return {
        "modules": {
            "module_a": {
                "prerequisites": [],
                "dependencies": ["module_b"]
            },
            "module_b": {
                "prerequisites": ["module_c"],
                "dependencies": ["module_c"]
            },
            "module_c": {
                "prerequisites": [],
                "dependencies": []
            },
            "module_d": {
                "prerequisites": ["module_a", "module_b"],
                "dependencies": ["module_a"]
            }
        }
    }

@pytest.fixture
def scheduler(sample_manifest):
    return DependencyScheduler(sample_manifest)

@pytest.fixture
def state_store():
    return ModuleStateStore()

class TestDependencyManifestLoading:
    def test_manifest_loads_correctly(self, scheduler):
        """Test that dependency manifest loads correctly."""
        assert scheduler.manifest is not None
        assert "module_a" in scheduler.manifest["modules"]
        assert "module_b" in scheduler.manifest["modules"]
        assert "module_c" in scheduler.manifest["modules"]
        assert "module_d" in scheduler.manifest["modules"]

    def test_manifest_has_correct_structure(self, scheduler):
        """Test that manifest has correct structure for each module."""
        for module_name, module_info in scheduler.manifest["modules"].items():
            assert "prerequisites" in module_info
            assert "dependencies" in module_info
            assert isinstance(module_info["prerequisites"], list)
            assert isinstance(module_info["dependencies"], list)

    def test_manifest_with_empty_modules(self):
        """Test loading manifest with no modules."""
        empty_manifest = {"modules": {}}
        scheduler = DependencyScheduler(empty_manifest)
        assert scheduler.manifest["modules"] == {}

    def test_manifest_with_invalid_structure(self):
        """Test that invalid manifest raises appropriate error."""
        with pytest.raises(ValueError):
            DependencyScheduler({"invalid": "structure"})

class TestGetMutationQueue:
    def test_returns_correct_order(self, scheduler):
        """Test that get_mutation_queue returns modules in correct dependency order."""
        queue = scheduler.get_mutation_queue()
        # module_c has no dependencies, should come first
        assert queue[0] == "module_c"
        # module_b depends on module_c
        assert queue.index("module_b") > queue.index("module_c")
        # module_a depends on module_b
        assert queue.index("module_a") > queue.index("module_b")
        # module_d depends on module_a
        assert queue.index("module_d") > queue.index("module_a")

    def test_returns_all_modules(self, scheduler):
        """Test that all modules are included in the queue."""
        queue = scheduler.get_mutation_queue()
        assert set(queue) == {"module_a", "module_b", "module_c", "module_d"}

    def test_no_duplicate_modules(self, scheduler):
        """Test that no modules are duplicated in the queue."""
        queue = scheduler.get_mutation_queue()
        assert len(queue) == len(set(queue))

    def test_handles_cyclic_dependencies(self):
        """Test that cyclic dependencies raise appropriate error."""
        cyclic_manifest = {
            "modules": {
                "module_a": {"prerequisites": [], "dependencies": ["module_b"]},
                "module_b": {"prerequisites": [], "dependencies": ["module_a"]}
            }
        }
        with pytest.raises(ValueError):
            DependencyScheduler(cyclic_manifest).get_mutation_queue()

class TestGetBlockedModules:
    def test_identifies_blocked_modules(self, scheduler, state_store):
        """Test that get_blocked_modules correctly identifies modules with unverified prerequisites."""
        # Initially, no modules are verified
        blocked = scheduler.get_blocked_modules(state_store)
        # module_b requires module_c as prerequisite, which is not verified
        assert "module_b" in blocked
        # module_d requires module_a and module_b as prerequisites
        assert "module_d" in blocked
        # module_a and module_c have no prerequisites
        assert "module_a" not in blocked
        assert "module_c" not in blocked

    def test_no_blocked_modules_when_all_verified(self, scheduler, state_store):
        """Test that no modules are blocked when all prerequisites are verified."""
        state_store.mark_verified("module_c")
        state_store.mark_verified("module_b")
        state_store.mark_verified("module_a")
        blocked = scheduler.get_blocked_modules(state_store)
        assert len(blocked) == 0

    def test_partially_blocked_modules(self, scheduler, state_store):
        """Test that only modules with unverified prerequisites are blocked."""
        state_store.mark_verified("module_c")
        # module_b's prerequisite (module_c) is now verified
        blocked = scheduler.get_blocked_modules(state_store)
        assert "module_b" not in blocked
        # module_d still requires module_a which is not verified
        assert "module_d" in blocked

    def test_handles_modules_without_prerequisites(self, scheduler, state_store):
        """Test that modules without prerequisites are never blocked."""
        blocked = scheduler.get_blocked_modules(state_store)
        assert "module_c" not in blocked
        assert "module_a" not in blocked

class TestVerifyPrerequisites:
    def test_returns_true_when_prerequisites_met(self, scheduler, state_store):
        """Test that verify_prerequisites returns True when all prerequisites are verified."""
        state_store.mark_verified("module_c")
        assert scheduler.verify_prerequisites("module_b", state_store) is True

    def test_returns_false_when_prerequisites_not_met(self, scheduler, state_store):
        """Test that verify_prerequisites returns False when prerequisites are not verified."""
        assert scheduler.verify_prerequisites("module_b", state_store) is False

    def test_returns_true_for_no_prerequisites(self, scheduler, state_store):
        """Test that verify_prerequisites returns True for modules with no prerequisites."""
        assert scheduler.verify_prerequisites("module_c", state_store) is True
        assert scheduler.verify_prerequisites("module_a", state_store) is True

    def test_handles_multiple_prerequisites(self, scheduler, state_store):
        """Test that verify_prerequisites checks all prerequisites."""
        state_store.mark_verified("module_a")
        state_store.mark_verified("module_b")
        assert scheduler.verify_prerequisites("module_d", state_store) is True
        
        state_store.reset()
        state_store.mark_verified("module_a")
        assert scheduler.verify_prerequisites("module_d", state_store) is False

class TestGetBottleneck:
    def test_returns_most_blocked_module(self, scheduler, state_store):
        """Test that get_bottleneck returns the most blocked module."""
        bottleneck = scheduler.get_bottleneck(state_store)
        # module_d is blocked by 2 prerequisites (module_a and module_b)
        assert bottleneck == "module_d"

    def test_returns_none_when_no_blocked_modules(self, scheduler, state_store):
        """Test that get_bottleneck returns None when no modules are blocked."""
        state_store.mark_verified("module_c")
        state_store.mark_verified("module_b")
        state_store.mark_verified("module_a")
        assert scheduler.get_bottleneck(state_store) is None

    def test_returns_single_blocked_module(self, scheduler, state_store):
        """Test that get_bottleneck returns the only blocked module."""
        state_store.mark_verified("module_c")
        # module_d is still blocked by module_a
        bottleneck = scheduler.get_bottleneck(state_store)
        assert bottleneck == "module_d"

    def test_handles_tie_in_blocked_count(self, scheduler, state_store):
        """Test that get_bottleneck handles ties in blocked count."""
        # Both module_b and module_d are blocked (module_b by 1, module_d by 2)
        bottleneck = scheduler.get_bottleneck(state_store)
        assert bottleneck == "module_d"  # module_d has more blocked prerequisites

class TestIntegrationWithModuleStateStore:
    def test_state_store_interaction(self, scheduler, state_store):
        """Test integration with module_state_store."""
        # Initially, no modules are verified
        assert state_store.is_verified("module_c") is False
        
        # Verify a module
        state_store.mark_verified("module_c")
        assert state_store.is_verified("module_c") is True
        
        # Check that scheduler recognizes the change
        assert scheduler.verify_prerequisites("module_b", state_store) is True

    def test_state_store_reset(self, scheduler, state_store):
        """Test that state store can be reset and affects scheduler."""
        state_store.mark_verified("module_c")
        assert scheduler.verify_prerequisites("module_b", state_store) is True
        
        state_store.reset()
        assert scheduler.verify_prerequisites("module_b", state_store) is False

    def test_multiple_verifications(self, scheduler, state_store):
        """Test that multiple verifications work correctly."""
        state_store.mark_verified("module_c")
        state_store.mark_verified("module_b")
        state_store.mark_verified("module_a")
        
        queue = scheduler.get_mutation_queue()
        # All modules should be eligible for mutation
        for module in queue:
            assert scheduler.verify_prerequisites(module, state_store) is True

class TestMutationBlocked:
    def test_mutation_blocked_when_prerequisites_not_met(self, scheduler, state_store):
        """Test that mutation is blocked when prerequisites are not met."""
        # module_b requires module_c, which is not verified
        assert scheduler.verify_prerequisites("module_b", state_store) is False
        assert scheduler.is_mutation_allowed("module_b", state_store) is False

    def test_mutation_allowed_when_prerequisites_met(self, scheduler, state_store):
        """Test that mutation is allowed when prerequisites are met."""
        state_store.mark_verified("module_c")
        assert scheduler.verify_prerequisites("module_b", state_store) is True
        assert scheduler.is_mutation_allowed("module_b", state_store) is True

    def test_mutation_allowed_for_no_prerequisites(self, scheduler, state_store):
        """Test that mutation is allowed for modules with no prerequisites."""
        assert scheduler.is_mutation_allowed("module_c", state_store) is True
        assert scheduler.is_mutation_allowed("module_a", state_store) is True

    def test_mutation_blocked_for_deep_dependencies(self, scheduler, state_store):
        """Test that mutation is blocked for modules with deep dependency chains."""
        # module_d requires module_a and module_b, both unverified
        assert scheduler.is_mutation_allowed("module_d", state_store) is False
        
        # Verify one prerequisite
        state_store.mark_verified("module_a")
        assert scheduler.is_mutation_allowed("module_d", state_store) is False
        
        # Verify all prerequisites
        state_store.mark_verified("module_b")
        assert scheduler.is_mutation_allowed("module_d", state_store) is True

    def test_mutation_blocked_after_state_change(self, scheduler, state_store):
        """Test that mutation status updates after state changes."""
        # Initially blocked
        assert scheduler.is_mutation_allowed("module_b", state_store) is False
        
        # After verifying prerequisite
        state_store.mark_verified("module_c")
        assert scheduler.is_mutation_allowed("module_b", state_store) is True
        
        # After resetting state
        state_store.reset()
        assert scheduler.is_mutation_allowed("module_b", state_store) is False

if __name__ == "__main__":
    pytest.main([__file__])