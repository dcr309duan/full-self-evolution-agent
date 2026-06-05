import pytest
from datetime import datetime, timedelta
from capability_fitness import CapabilityFitness, Capability, CapabilityStatus

@pytest.fixture
def fitness_system():
    """Create a CapabilityFitness instance with default config for testing."""
    return CapabilityFitness(
        deprecation_threshold=0.3,
        cycles_before_deprecation=5
    )

@pytest.fixture
def sample_capability():
    """Create a sample capability for testing."""
    return Capability(
        name="test_capability",
        description="A test capability",
        version="1.0.0"
    )

class TestCapabilityInitialization:
    """Test that new capabilities start with fitness=0."""
    
    def test_new_capability_has_zero_fitness(self, fitness_system, sample_capability):
        fitness_system.register_capability(sample_capability)
        assert fitness_system.get_fitness("test_capability") == 0.0
    
    def test_multiple_new_capabilities_have_zero_fitness(self, fitness_system):
        capabilities = [
            Capability("cap1", "First capability", "1.0"),
            Capability("cap2", "Second capability", "2.0"),
            Capability("cap3", "Third capability", "3.0")
        ]
        for cap in capabilities:
            fitness_system.register_capability(cap)
        
        for cap in capabilities:
            assert fitness_system.get_fitness(cap.name) == 0.0
    
    def test_capability_fitness_initialized_in_active_set(self, fitness_system, sample_capability):
        fitness_system.register_capability(sample_capability)
        assert sample_capability.name in fitness_system.get_active_capabilities()

class TestDownstreamRegistration:
    """Test that registering downstream uses increments fitness."""
    
    def test_single_downstream_increases_fitness(self, fitness_system, sample_capability):
        fitness_system.register_capability(sample_capability)
        initial_fitness = fitness_system.get_fitness("test_capability")
        
        fitness_system.register_downstream_usage("test_capability")
        assert fitness_system.get_fitness("test_capability") > initial_fitness
    
    def test_multiple_downstream_increases_fitness_proportionally(self, fitness_system, sample_capability):
        fitness_system.register_capability(sample_capability)
        initial_fitness = fitness_system.get_fitness("test_capability")
        
        for _ in range(5):
            fitness_system.register_downstream_usage("test_capability")
        
        expected_fitness = initial_fitness + (5 * fitness_system.downstream_increment)
        assert abs(fitness_system.get_fitness("test_capability") - expected_fitness) < 0.001
    
    def test_downstream_registration_on_nonexistent_capability(self, fitness_system):
        with pytest.raises(ValueError):
            fitness_system.register_downstream_usage("nonexistent_capability")

class TestDeprecationThreshold:
    """Test that capabilities below threshold are flagged after correct number of cycles."""
    
    def test_capability_below_threshold_flagged_after_cycles(self, fitness_system, sample_capability):
        fitness_system.register_capability(sample_capability)
        
        # Run cycles without downstream usage to decrease fitness
        for _ in range(fitness_system.cycles_before_deprecation):
            fitness_system.run_cycle()
        
        assert fitness_system.get_status("test_capability") == CapabilityStatus.DEPRECATED
    
    def test_capability_not_deprecated_before_required_cycles(self, fitness_system, sample_capability):
        fitness_system.register_capability(sample_capability)
        
        # Run fewer cycles than required
        for _ in range(fitness_system.cycles_before_deprecation - 1):
            fitness_system.run_cycle()
        
        assert fitness_system.get_status("test_capability") != CapabilityStatus.DEPRECATED
    
    def test_capability_above_threshold_not_deprecated(self, fitness_system, sample_capability):
        fitness_system.register_capability(sample_capability)
        
        # Keep fitness above threshold by registering downstream usage
        for _ in range(fitness_system.cycles_before_deprecation + 5):
            fitness_system.register_downstream_usage("test_capability")
            fitness_system.run_cycle()
        
        assert fitness_system.get_status("test_capability") != CapabilityStatus.DEPRECATED

class TestDeprecationRemoval:
    """Test that deprecation removes capability from active set."""
    
    def test_deprecated_capability_removed_from_active(self, fitness_system, sample_capability):
        fitness_system.register_capability(sample_capability)
        
        # Force deprecation
        for _ in range(fitness_system.cycles_before_deprecation):
            fitness_system.run_cycle()
        
        assert sample_capability.name not in fitness_system.get_active_capabilities()
    
    def test_deprecated_capability_in_deprecated_set(self, fitness_system, sample_capability):
        fitness_system.register_capability(sample_capability)
        
        for _ in range(fitness_system.cycles_before_deprecation):
            fitness_system.run_cycle()
        
        assert sample_capability.name in fitness_system.get_deprecated_capabilities()
    
    def test_multiple_deprecations_removed_from_active(self, fitness_system):
        capabilities = [
            Capability("cap1", "First", "1.0"),
            Capability("cap2", "Second", "2.0"),
            Capability("cap3", "Third", "3.0")
        ]
        for cap in capabilities:
            fitness_system.register_capability(cap)
        
        # Deprecate all
        for _ in range(fitness_system.cycles_before_deprecation):
            fitness_system.run_cycle()
        
        active = fitness_system.get_active_capabilities()
        for cap in capabilities:
            assert cap.name not in active

class TestDashboardOutput:
    """Test that dashboard output contains all required fields."""
    
    def test_dashboard_contains_required_fields(self, fitness_system, sample_capability):
        fitness_system.register_capability(sample_capability)
        dashboard = fitness_system.get_dashboard()
        
        required_fields = [
            "capability_name",
            "fitness_score",
            "status",
            "downstream_count",
            "last_updated",
            "cycles_since_update"
        ]
        
        for entry in dashboard:
            for field in required_fields:
                assert field in entry, f"Missing field: {field}"
    
    def test_dashboard_contains_all_capabilities(self, fitness_system):
        capabilities = [
            Capability("cap1", "First", "1.0"),
            Capability("cap2", "Second", "2.0"),
            Capability("cap3", "Third", "3.0")
        ]
        for cap in capabilities:
            fitness_system.register_capability(cap)
        
        dashboard = fitness_system.get_dashboard()
        dashboard_names = [entry["capability_name"] for entry in dashboard]
        
        for cap in capabilities:
            assert cap.name in dashboard_names
    
    def test_dashboard_includes_deprecated_capabilities(self, fitness_system, sample_capability):
        fitness_system.register_capability(sample_capability)
        
        for _ in range(fitness_system.cycles_before_deprecation):
            fitness_system.run_cycle()
        
        dashboard = fitness_system.get_dashboard()
        deprecated_entries = [e for e in dashboard if e["status"] == CapabilityStatus.DEPRECATED]
        
        assert len(deprecated_entries) > 0
        assert deprecated_entries[0]["capability_name"] == sample_capability.name

class TestConfigurableParameters:
    """Test configurable threshold and cycles_before_deprecation."""
    
    def test_custom_threshold(self):
        custom_threshold = 0.5
        system = CapabilityFitness(
            deprecation_threshold=custom_threshold,
            cycles_before_deprecation=3
        )
        assert system.deprecation_threshold == custom_threshold
    
    def test_custom_cycles_before_deprecation(self):
        custom_cycles = 10
        system = CapabilityFitness(
            deprecation_threshold=0.2,
            cycles_before_deprecation=custom_cycles
        )
        assert system.cycles_before_deprecation == custom_cycles
    
    def test_deprecation_uses_custom_threshold(self):
        system = CapabilityFitness(
            deprecation_threshold=0.8,  # High threshold
            cycles_before_deprecation=2
        )
        cap = Capability("test", "Test capability", "1.0")
        system.register_capability(cap)
        
        # Even with some downstream usage, fitness might be below high threshold
        system.register_downstream_usage("test")
        system.register_downstream_usage("test")
        
        for _ in range(2):
            system.run_cycle()
        
        # With high threshold, capability should be deprecated despite some usage
        assert system.get_status("test") == CapabilityStatus.DEPRECATED
    
    def test_deprecation_uses_custom_cycles(self):
        system = CapabilityFitness(
            deprecation_threshold=0.3,
            cycles_before_deprecation=10  # Many cycles required
        )
        cap = Capability("test", "Test capability", "1.0")
        system.register_capability(cap)
        
        # Run fewer cycles than required
        for _ in range(5):
            system.run_cycle()
        
        assert system.get_status("test") != CapabilityStatus.DEPRECATED
        
        # Run enough cycles to trigger deprecation
        for _ in range(5):
            system.run_cycle()
        
        assert system.get_status("test") == CapabilityStatus.DEPRECATED

class TestReRegistration:
    """Test that re-registering a deprecated capability re-activates it."""
    
    def test_reregister_deprecated_capability_reactivates(self, fitness_system, sample_capability):
        fitness_system.register_capability(sample_capability)
        
        # Deprecate the capability
        for _ in range(fitness_system.cycles_before_deprecation):
            fitness_system.run_cycle()
        
        assert sample_capability.name not in fitness_system.get_active_capabilities()
        
        # Re-register the capability
        fitness_system.register_capability(sample_capability)
        
        assert sample_capability.name in fitness_system.get_active_capabilities()
        assert fitness_system.get_fitness(sample_capability.name) == 0.0
    
    def test_reregister_removes_from_deprecated_set(self, fitness_system, sample_capability):
        fitness_system.register_capability(sample_capability)
        
        for _ in range(fitness_system.cycles_before_deprecation):
            fitness_system.run_cycle()
        
        assert sample_capability.name in fitness_system.get_deprecated_capabilities()
        
        fitness_system.register_capability(sample_capability)
        
        assert sample_capability.name not in fitness_system.get_deprecated_capabilities()
    
    def test_reregister_resets_fitness(self, fitness_system, sample_capability):
        fitness_system.register_capability(sample_capability)
        
        # Add some fitness
        for _ in range(3):
            fitness_system.register_downstream_usage(sample_capability.name)
        
        # Deprecate
        for _ in range(fitness_system.cycles_before_deprecation):
            fitness_system.run_cycle()
        
        # Re-register
        fitness_system.register_capability(sample_capability)
        
        assert fitness_system.get_fitness(sample_capability.name) == 0.0
    
    def test_reregister_preserves_metadata(self, fitness_system, sample_capability):
        fitness_system.register_capability(sample_capability)
        
        for _ in range(fitness_system.cycles_before_deprecation):
            fitness_system.run_cycle()
        
        # Re-register with updated version
        updated_capability = Capability(
            name=sample_capability.name,
            description=sample_capability.description,
            version="2.0.0"
        )
        fitness_system.register_capability(updated_capability)
        
        assert fitness_system.get_version(sample_capability.name) == "2.0.0"