from core.health_dashboard import HealthDashboard
from core.mutation_engine import MutationEngine
import time

class HealthDashboardIntegrationTest:
    """
    End-to-end integration test for HealthDashboard with controlled failure injection.
    Simulates 15 cycles, verifies rolling failure rate tracking, lockdown activation,
    mutation pausing, and recovery.
    """

    def __init__(self):
        self.dashboard = HealthDashboard()
        self.mutation_engine = MutationEngine(self.dashboard)
        self.cycle_results = []

    def run_test(self):
        """Execute the 15-cycle integration test."""
        print("Starting Health Dashboard Integration Test")
        print("=" * 50)

        # Cycle 1-9: Inject failures to set up scenario
        for cycle in range(1, 10):
            # Inject failures in cycles 1, 2, 3, 5, 6, 7 (6 failures total)
            if cycle in [1, 2, 3, 5, 6, 7]:
                self.dashboard.record_failure()
                print(f"Cycle {cycle}: Failure injected")
            else:
                print(f"Cycle {cycle}: No failure")
            
            self.dashboard.record_cycle()
            self.cycle_results.append({
                'cycle': cycle,
                'failure_rate': self.dashboard.get_rolling_failure_rate(),
                'lockdown_active': self.dashboard.is_lockdown_active(),
                'mutations_paused': self.mutation_engine.is_paused()
            })

        # Cycle 10: Inject failure to trigger lockdown (3 failures in last 10 = 30%)
        print(f"\nCycle 10: Injecting failure to trigger lockdown")
        self.dashboard.record_failure()
        self.dashboard.record_cycle()
        self.cycle_results.append({
            'cycle': 10,
            'failure_rate': self.dashboard.get_rolling_failure_rate(),
            'lockdown_active': self.dashboard.is_lockdown_active(),
            'mutations_paused': self.mutation_engine.is_paused()
        })

        # Verify lockdown activated at cycle 10
        assert self.dashboard.is_lockdown_active(), "Lockdown should be active after cycle 10"
        assert self.mutation_engine.is_paused(), "Mutations should be paused during lockdown"
        print("✓ Lockdown activated and mutations paused at cycle 10")

        # Cycle 11-14: No failures, should remain in lockdown
        for cycle in range(11, 15):
            print(f"Cycle {cycle}: No failure (in lockdown)")
            self.dashboard.record_cycle()
            self.cycle_results.append({
                'cycle': cycle,
                'failure_rate': self.dashboard.get_rolling_failure_rate(),
                'lockdown_active': self.dashboard.is_lockdown_active(),
                'mutations_paused': self.mutation_engine.is_paused()
            })

        # Verify still in lockdown
        assert self.dashboard.is_lockdown_active(), "Lockdown should still be active"
        assert self.mutation_engine.is_paused(), "Mutations should still be paused"
        print("✓ Lockdown maintained through cycles 11-14")

        # Cycle 15: No failure, should trigger recovery (5 cycles with no failures)
        print(f"\nCycle 15: No failure - should trigger recovery")
        self.dashboard.record_cycle()
        self.cycle_results.append({
            'cycle': 15,
            'failure_rate': self.dashboard.get_rolling_failure_rate(),
            'lockdown_active': self.dashboard.is_lockdown_active(),
            'mutations_paused': self.mutation_engine.is_paused()
        })

        # Verify recovery
        assert not self.dashboard.is_lockdown_active(), "Lockdown should be lifted after recovery"
        assert not self.mutation_engine.is_paused(), "Mutations should resume after recovery"
        print("✓ Recovery complete - lockdown lifted and mutations resumed")

        self._print_summary()

    def _print_summary(self):
        """Print a summary of the test results."""
        print("\n" + "=" * 50)
        print("Integration Test Summary")
        print("=" * 50)
        print(f"{'Cycle':<8} {'Failure Rate':<15} {'Lockdown':<12} {'Mutations':<12}")
        print("-" * 47)
        for result in self.cycle_results:
            print(f"{result['cycle']:<8} {result['failure_rate']:<15.2%} "
                  f"{'Active' if result['lockdown_active'] else 'Inactive':<12} "
                  f"{'Paused' if result['mutations_paused'] else 'Active':<12}")

        # Final assertions
        print("\nFinal Verifications:")
        print("-" * 20)
        
        # Check rolling failure rate at cycle 10
        cycle_10 = self.cycle_results[9]  # 0-indexed
        assert cycle_10['failure_rate'] > 0.20, \
            f"Failure rate at cycle 10 ({cycle_10['failure_rate']:.2%}) should exceed 20%"
        print(f"✓ Cycle 10 failure rate: {cycle_10['failure_rate']:.2%} (threshold: 20%)")

        # Check recovery at cycle 15
        cycle_15 = self.cycle_results[14]
        assert cycle_15['failure_rate'] == 0.0, \
            f"Failure rate at cycle 15 ({cycle_15['failure_rate']:.2%}) should be 0%"
        print(f"✓ Cycle 15 failure rate: {cycle_15['failure_rate']:.2%} (recovered)")

        print("\n✓ All integration tests passed!")


if __name__ == "__main__":
    test = HealthDashboardIntegrationTest()
    test.run_test()