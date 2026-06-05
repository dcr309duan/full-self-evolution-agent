import unittest
import tempfile
import os
import json
import time
from collections import defaultdict
from failure_pattern_miner import FailurePatternMiner, Rule

class TestFailurePatternMiner(unittest.TestCase):
    def setUp(self):
        self.miner = FailurePatternMiner()
        self.temp_dir = tempfile.mkdtemp()
        self.log_file = os.path.join(self.temp_dir, "failure_logs.json")
        self.rule_file = os.path.join(self.temp_dir, "rules.json")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir)

    def _seed_failure_logs(self, patterns):
        """Helper to seed fake failure logs with known patterns."""
        logs = []
        for pattern_name, entries in patterns.items():
            for entry in entries:
                logs.append({
                    "timestamp": entry.get("timestamp", time.time()),
                    "error": entry.get("error", "GenericError"),
                    "context": entry.get("context", {}),
                    "stack_trace": entry.get("stack_trace", ""),
                    "pattern": pattern_name
                })
        with open(self.log_file, 'w') as f:
            json.dump(logs, f)
        return logs

    def test_identifies_known_patterns(self):
        """Test that miner correctly identifies seeded patterns."""
        patterns = {
            "NullPointerException": [
                {"error": "NullPointerException", "context": {"method": "getUser"}, "stack_trace": "at com.app.UserService.getUser"},
                {"error": "NullPointerException", "context": {"method": "getUser"}, "stack_trace": "at com.app.UserService.getUser"},
                {"error": "NullPointerException", "context": {"method": "getUser"}, "stack_trace": "at com.app.UserService.getUser"}
            ],
            "TimeoutError": [
                {"error": "TimeoutError", "context": {"service": "database"}, "stack_trace": "at com.app.DBConnection.query"},
                {"error": "TimeoutError", "context": {"service": "database"}, "stack_trace": "at com.app.DBConnection.query"}
            ]
        }
        self._seed_failure_logs(patterns)
        
        mined_rules = self.miner.mine(self.log_file)
        
        # Check that both patterns are identified
        rule_errors = [rule.error_pattern for rule in mined_rules]
        self.assertIn("NullPointerException", rule_errors)
        self.assertIn("TimeoutError", rule_errors)
        
        # Check rule details
        for rule in mined_rules:
            if rule.error_pattern == "NullPointerException":
                self.assertIn("getUser", rule.context.get("method", ""))
                self.assertGreaterEqual(rule.hit_count, 3)
            elif rule.error_pattern == "TimeoutError":
                self.assertIn("database", rule.context.get("service", ""))
                self.assertGreaterEqual(rule.hit_count, 2)

    def test_blocks_matching_mutations(self):
        """Test that generated rules block mutations that match the pattern."""
        patterns = {
            "NullPointerException": [
                {"error": "NullPointerException", "context": {"method": "getUser"}, "stack_trace": "at com.app.UserService.getUser"}
            ]
        }
        self._seed_failure_logs(patterns)
        rules = self.miner.mine(self.log_file)
        
        # Create a mutation that matches the pattern
        matching_mutation = {
            "error": "NullPointerException",
            "context": {"method": "getUser"},
            "stack_trace": "at com.app.UserService.getUser"
        }
        
        for rule in rules:
            if rule.error_pattern == "NullPointerException":
                self.assertTrue(rule.matches(matching_mutation))
                self.assertTrue(self.miner.should_block(matching_mutation, rules))

    def test_does_not_block_non_matching_mutations(self):
        """Test that rules don't block mutations that don't match."""
        patterns = {
            "NullPointerException": [
                {"error": "NullPointerException", "context": {"method": "getUser"}, "stack_trace": "at com.app.UserService.getUser"}
            ]
        }
        self._seed_failure_logs(patterns)
        rules = self.miner.mine(self.log_file)
        
        # Create mutations that don't match
        non_matching_mutations = [
            {"error": "NullPointerException", "context": {"method": "saveUser"}, "stack_trace": "at com.app.UserService.saveUser"},
            {"error": "TimeoutError", "context": {"method": "getUser"}, "stack_trace": "at com.app.UserService.getUser"},
            {"error": "NullPointerException", "context": {"method": "getUser"}, "stack_trace": "at com.app.OtherService.getUser"}
        ]
        
        for mutation in non_matching_mutations:
            for rule in rules:
                if rule.error_pattern == "NullPointerException":
                    self.assertFalse(rule.matches(mutation))
            self.assertFalse(self.miner.should_block(mutation, rules))

    def test_rule_hit_counting_and_decay(self):
        """Test that rules accumulate hits and old rules without hits get deprioritized."""
        # Create initial logs with a pattern
        initial_patterns = {
            "FrequentError": [
                {"error": "FrequentError", "context": {"module": "auth"}, "timestamp": time.time() - 100}
            ] * 5  # 5 hits initially
        }
        self._seed_failure_logs(initial_patterns)
        
        # Mine initial rules
        rules = self.miner.mine(self.log_file)
        initial_rule = next(r for r in rules if r.error_pattern == "FrequentError")
        initial_hits = initial_rule.hit_count
        
        # Simulate more hits over time
        for i in range(3):
            new_log = {
                "timestamp": time.time() - (2 - i) * 10,  # Recent timestamps
                "error": "FrequentError",
                "context": {"module": "auth"},
                "stack_trace": "at com.app.AuthService.login"
            }
            self.miner.record_hit(new_log)
        
        # Re-mine and check hit count increased
        updated_rules = self.miner.mine(self.log_file)
        updated_rule = next(r for r in updated_rules if r.error_pattern == "FrequentError")
        self.assertGreater(updated_rule.hit_count, initial_hits)
        
        # Simulate decay: create a new rule that gets many hits, old rule should be deprioritized
        new_patterns = {
            "NewFrequentError": [
                {"error": "NewFrequentError", "context": {"module": "billing"}, "timestamp": time.time()}
            ] * 10  # 10 recent hits
        }
        self._seed_failure_logs(new_patterns)
        
        # Add old rule's logs with old timestamps to simulate decay
        with open(self.log_file, 'a') as f:
            for _ in range(5):
                json.dump({
                    "timestamp": time.time() - 10000,  # Very old
                    "error": "FrequentError",
                    "context": {"module": "auth"},
                    "stack_trace": "at com.app.AuthService.login"
                }, f)
                f.write('\n')
        
        final_rules = self.miner.mine(self.log_file)
        
        # The new rule should have higher priority (more recent hits)
        old_rule = next(r for r in final_rules if r.error_pattern == "FrequentError")
        new_rule = next(r for r in final_rules if r.error_pattern == "NewFrequentError")
        
        # Check that new rule has higher priority score
        self.assertGreater(new_rule.priority_score(), old_rule.priority_score())

    def test_rule_decay_over_time(self):
        """Test that rules without recent hits get deprioritized."""
        # Create a rule with old hits
        old_patterns = {
            "OldError": [
                {"error": "OldError", "context": {"module": "legacy"}, "timestamp": time.time() - 10000}
            ] * 3
        }
        self._seed_failure_logs(old_patterns)
        old_rules = self.miner.mine(self.log_file)
        old_rule = next(r for r in old_rules if r.error_pattern == "OldError")
        old_priority = old_rule.priority_score()
        
        # Wait a bit (simulate time passing)
        time.sleep(0.1)
        
        # Create a new rule with recent hits
        new_patterns = {
            "NewError": [
                {"error": "NewError", "context": {"module": "new"}, "timestamp": time.time()}
            ] * 3
        }
        self._seed_failure_logs(new_patterns)
        new_rules = self.miner.mine(self.log_file)
        new_rule = next(r for r in new_rules if r.error_pattern == "NewError")
        new_priority = new_rule.priority_score()
        
        # New rule should have higher priority due to recency
        self.assertGreater(new_priority, old_priority)

if __name__ == '__main__':
    unittest.main()