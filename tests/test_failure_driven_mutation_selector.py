from unittest.mock import MagicMock, patch
import pytest
from tests.test_failure_driven_mutation_selector import FailureDrivenMutationSelector
from tests.test_failure_pattern_miner import FailurePatternMiner


class TestFailureDrivenMutationSelector:
    """Comprehensive tests for FailureDrivenMutationSelector."""

    @pytest.fixture
    def selector(self):
        """Fixture to create a basic selector instance."""
        return FailureDrivenMutationSelector()

    @pytest.fixture
    def mock_miner(self):
        """Fixture to create a mock FailurePatternMiner."""
        miner = MagicMock(spec=FailurePatternMiner)
        return miner

    def test_mutations_targeting_failure_keywords_filtered(self, selector, mock_miner):
        """Test that mutations targeting files matching failure keywords are filtered out."""
        # Setup mock miner to return failure patterns
        mock_miner.mine_failure_patterns.return_value = {
            "failures": [
                {"file": "src/buggy_module.py", "keywords": ["buggy", "error"]},
                {"file": "src/legacy_code.py", "keywords": ["legacy", "deprecated"]}
            ]
        }
        selector.failure_miner = mock_miner

        # Create mutations pool
        mutations = [
            {"file": "src/buggy_module.py", "mutation": "change_operator"},
            {"file": "src/legacy_code.py", "mutation": "delete_line"},
            {"file": "src/stable_module.py", "mutation": "change_constant"}
        ]

        # Apply selector
        filtered = selector.select_mutations(mutations)

        # Assert only non-targeted mutations remain
        assert len(filtered) == 1
        assert filtered[0]["file"] == "src/stable_module.py"
        assert filtered[0]["mutation"] == "change_constant"

    def test_unrelated_mutations_pass_through(self, selector, mock_miner):
        """Test that mutations unrelated to failure keywords pass through."""
        # Setup mock miner with no relevant patterns
        mock_miner.mine_failure_patterns.return_value = {"failures": []}
        selector.failure_miner = mock_miner

        mutations = [
            {"file": "src/module_a.py", "mutation": "change_operator"},
            {"file": "src/module_b.py", "mutation": "delete_line"}
        ]

        filtered = selector.select_mutations(mutations)

        # All mutations should pass through
        assert len(filtered) == 2
        assert filtered == mutations

    def test_fallback_when_no_failures_exist(self, selector):
        """Test fallback behavior when no failure patterns exist."""
        # Selector without failure miner should return all mutations
        mutations = [
            {"file": "src/module_a.py", "mutation": "change_operator"},
            {"file": "src/module_b.py", "mutation": "delete_line"}
        ]

        filtered = selector.select_mutations(mutations)

        # Should return all mutations as fallback
        assert len(filtered) == 2
        assert filtered == mutations

    def test_empty_mutation_pool_graceful(self, selector, mock_miner):
        """Test that selector handles empty mutation pool gracefully."""
        mock_miner.mine_failure_patterns.return_value = {"failures": []}
        selector.failure_miner = mock_miner

        filtered = selector.select_mutations([])

        # Should return empty list without errors
        assert filtered == []

    def test_integration_with_failure_pattern_miner(self, selector, mock_miner):
        """Test integration with failure pattern miner."""
        # Setup mock miner with specific patterns
        mock_miner.mine_failure_patterns.return_value = {
            "failures": [
                {"file": "src/critical.py", "keywords": ["critical", "fatal"]}
            ]
        }
        selector.failure_miner = mock_miner

        mutations = [
            {"file": "src/critical.py", "mutation": "change_operator"},
            {"file": "src/other.py", "mutation": "delete_line"}
        ]

        filtered = selector.select_mutations(mutations)

        # Verify integration works correctly
        assert len(filtered) == 1
        assert filtered[0]["file"] == "src/other.py"
        mock_miner.mine_failure_patterns.assert_called_once()

    def test_partial_keyword_match(self, selector, mock_miner):
        """Test that partial keyword matches also filter mutations."""
        mock_miner.mine_failure_patterns.return_value = {
            "failures": [
                {"file": "src/buggy_module.py", "keywords": ["bug"]}
            ]
        }
        selector.failure_miner = mock_miner

        mutations = [
            {"file": "src/buggy_module.py", "mutation": "change_operator"},
            {"file": "src/stable.py", "mutation": "delete_line"}
        ]

        filtered = selector.select_mutations(mutations)

        # Should filter based on partial keyword match
        assert len(filtered) == 1
        assert filtered[0]["file"] == "src/stable.py"

    def test_multiple_failure_patterns(self, selector, mock_miner):
        """Test handling of multiple failure patterns."""
        mock_miner.mine_failure_patterns.return_value = {
            "failures": [
                {"file": "src/module1.py", "keywords": ["error1"]},
                {"file": "src/module2.py", "keywords": ["error2"]},
                {"file": "src/module3.py", "keywords": ["error3"]}
            ]
        }
        selector.failure_miner = mock_miner

        mutations = [
            {"file": "src/module1.py", "mutation": "m1"},
            {"file": "src/module2.py", "mutation": "m2"},
            {"file": "src/module3.py", "mutation": "m3"},
            {"file": "src/other.py", "mutation": "m4"}
        ]

        filtered = selector.select_mutations(mutations)

        # Only the non-targeted mutation should remain
        assert len(filtered) == 1
        assert filtered[0]["file"] == "src/other.py"

    def test_case_insensitive_matching(self, selector, mock_miner):
        """Test that keyword matching is case-insensitive."""
        mock_miner.mine_failure_patterns.return_value = {
            "failures": [
                {"file": "src/BuggyModule.py", "keywords": ["BUGGY"]}
            ]
        }
        selector.failure_miner = mock_miner

        mutations = [
            {"file": "src/buggyModule.py", "mutation": "change_operator"},
            {"file": "src/stable.py", "mutation": "delete_line"}
        ]

        filtered = selector.select_mutations(mutations)

        # Should match case-insensitively
        assert len(filtered) == 1
        assert filtered[0]["file"] == "src/stable.py"