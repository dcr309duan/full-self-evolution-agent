import pytest
from unittest.mock import patch, MagicMock
from src.external_knowledge_injector import ExternalKnowledgeInjector
from src.goal import Goal

@pytest.fixture
def mock_github_api():
    """Mock GitHub API responses with sample repos and patterns."""
    with patch('src.external_knowledge_injector.requests.get') as mock_get:
        # Mock response for repo search
        mock_repos_response = MagicMock()
        mock_repos_response.status_code = 200
        mock_repos_response.json.return_value = {
            'items': [
                {'full_name': 'user/repo1', 'html_url': 'https://github.com/user/repo1'},
                {'full_name': 'user/repo2', 'html_url': 'https://github.com/user/repo2'}
            ]
        }

        # Mock response for file content in repo1
        mock_file1_response = MagicMock()
        mock_file1_response.status_code = 200
        mock_file1_response.json.return_value = {
            'content': 'cGF0dGVybiBvbmU6IHNvbWUgZXhhbXBsZSBjb2RlIHdpdGggcGF0dGVybg==',
            'encoding': 'base64'
        }

        # Mock response for file content in repo2
        mock_file2_response = MagicMock()
        mock_file2_response.status_code = 200
        mock_file2_response.json.return_value = {
            'content': 'cGF0dGVybiB0d286IGFub3RoZXIgcGF0dGVybiBleGFtcGxl',
            'encoding': 'base64'
        }

        # Configure side effects for different URLs
        def side_effect(url, **kwargs):
            if 'search/repositories' in url:
                return mock_repos_response
            elif 'user/repo1' in url:
                return mock_file1_response
            elif 'user/repo2' in url:
                return mock_file2_response
            return MagicMock(status_code=404)

        mock_get.side_effect = side_effect
        yield mock_get

@pytest.fixture
def injector():
    """Create an ExternalKnowledgeInjector instance for testing."""
    return ExternalKnowledgeInjector(
        github_token='test_token',
        search_interval=20,
        max_repos=2
    )

class TestExternalKnowledgeInjector:
    """Integration tests for ExternalKnowledgeInjector."""

    def test_extract_patterns_correctly(self, mock_github_api, injector):
        """Test that injector extracts patterns correctly from GitHub repos."""
        # Execute pattern extraction
        patterns = injector.extract_patterns()

        # Verify patterns are extracted correctly
        assert len(patterns) == 2, "Should extract patterns from both repos"
        
        # Check first pattern
        assert 'pattern one' in patterns[0].lower()
        assert 'some example code with pattern' in patterns[0].lower()
        
        # Check second pattern
        assert 'pattern two' in patterns[1].lower()
        assert 'another pattern example' in patterns[1].lower()

    def test_only_runs_every_20_cycles(self, mock_github_api, injector):
        """Test that injector only runs pattern extraction every 20 cycles."""
        # First run should execute
        result1 = injector.run_cycle()
        assert result1 is True, "First cycle should execute"
        assert injector.cycle_count == 1
        assert mock_github_api.call_count > 0

        # Run 19 more cycles (total 20)
        for _ in range(19):
            result = injector.run_cycle()
            assert result is False, "Should not execute between cycles"
            assert mock_github_api.call_count == 3  # Should not increase

        # 21st cycle should execute again
        result21 = injector.run_cycle()
        assert result21 is True, "21st cycle should execute"
        assert injector.cycle_count == 21
        assert mock_github_api.call_count == 6  # Should have increased

    def test_generated_goals_are_well_formed(self, mock_github_api, injector):
        """Test that generated goals are well-formed and include integration instructions."""
        # Execute pattern extraction and goal generation
        injector.extract_patterns()
        goals = injector.generate_goals()

        # Verify goals are generated
        assert len(goals) > 0, "Should generate at least one goal"

        for goal in goals:
            # Check goal is a Goal instance
            assert isinstance(goal, Goal), "Each goal should be a Goal instance"
            
            # Check goal has required attributes
            assert hasattr(goal, 'description'), "Goal should have a description"
            assert hasattr(goal, 'priority'), "Goal should have a priority"
            assert hasattr(goal, 'source'), "Goal should have a source"
            
            # Check description is non-empty
            assert len(goal.description) > 0, "Goal description should not be empty"
            
            # Check priority is valid
            assert 0 <= goal.priority <= 10, "Priority should be between 0 and 10"
            
            # Check source is from GitHub
            assert 'github.com' in goal.source, "Goal source should reference GitHub"
            
            # Verify integration instructions are included
            assert 'integration' in goal.description.lower() or \
                   'implement' in goal.description.lower() or \
                   'apply' in goal.description.lower(), \
                   "Goal should include integration instructions"

    def test_goal_includes_pattern_details(self, mock_github_api, injector):
        """Test that generated goals include specific pattern details."""
        # Execute pattern extraction
        patterns = injector.extract_patterns()
        
        # Generate goals from patterns
        goals = injector.generate_goals()
        
        # Verify each pattern has a corresponding goal
        for pattern in patterns:
            pattern_found = False
            for goal in goals:
                if pattern.lower() in goal.description.lower():
                    pattern_found = True
                    break
            assert pattern_found, f"Pattern '{pattern}' should have a corresponding goal"

    def test_github_api_error_handling(self, mock_github_api, injector):
        """Test that injector handles GitHub API errors gracefully."""
        # Simulate API failure
        mock_github_api.side_effect = Exception("API Error")
        
        # Should not raise exception but return empty patterns
        patterns = injector.extract_patterns()
        assert len(patterns) == 0, "Should return empty patterns on API error"
        
        # Should not generate goals without patterns
        goals = injector.generate_goals()
        assert len(goals) == 0, "Should not generate goals without patterns"

    def test_injector_initialization(self, mock_github_api):
        """Test injector initialization with custom parameters."""
        custom_injector = ExternalKnowledgeInjector(
            github_token='custom_token',
            search_interval=10,
            max_repos=5
        )
        
        assert custom_injector.github_token == 'custom_token'
        assert custom_injector.search_interval == 10
        assert custom_injector.max_repos == 5
        assert custom_injector.cycle_count == 0
        assert len(custom_injector.patterns) == 0
        assert len(custom_injector.goals) == 0

    def test_multiple_cycles_with_goals(self, mock_github_api, injector):
        """Test that goals accumulate over multiple cycles."""
        # First cycle
        injector.run_cycle()
        first_cycle_goals = injector.get_goals()
        
        # Simulate 20 more cycles
        for _ in range(20):
            injector.run_cycle()
        
        # Second extraction should add more goals
        second_cycle_goals = injector.get_goals()
        assert len(second_cycle_goals) >= len(first_cycle_goals), \
               "Goals should accumulate over cycles"

    def test_goal_priority_based_on_pattern_frequency(self, mock_github_api, injector):
        """Test that goal priority reflects pattern frequency."""
        # Mock multiple occurrences of same pattern
        with patch.object(injector, 'extract_patterns') as mock_extract:
            mock_extract.return_value = ['pattern one'] * 5  # High frequency
            
            goals = injector.generate_goals()
            
            # High frequency patterns should have higher priority
            high_freq_goal = goals[0]
            assert high_freq_goal.priority > 5, \
                   "High frequency patterns should have higher priority"

    def test_cleanup_old_goals(self, mock_github_api, injector):
        """Test that old goals are cleaned up after a certain number of cycles."""
        # Generate some goals
        injector.extract_patterns()
        injector.generate_goals()
        initial_goal_count = len(injector.get_goals())
        
        # Run many cycles to trigger cleanup
        for _ in range(100):
            injector.run_cycle()
        
        # Old goals should be cleaned up
        final_goal_count = len(injector.get_goals())
        assert final_goal_count <= initial_goal_count, \
               "Old goals should be cleaned up over time"

    def test_concurrent_goal_generation(self, mock_github_api, injector):
        """Test that goal generation is thread-safe."""
        import threading
        
        goals_list = []
        errors = []
        
        def generate_goals_thread():
            try:
                injector.extract_patterns()
                goals = injector.generate_goals()
                goals_list.extend(goals)
            except Exception as e:
                errors.append(e)
        
        # Create multiple threads
        threads = []
        for _ in range(5):
            t = threading.Thread(target=generate_goals_thread)
            threads.append(t)
            t.start()
        
        # Wait for all threads to complete
        for t in threads:
            t.join()
        
        # Verify no errors occurred
        assert len(errors) == 0, f"Concurrent generation should not produce errors: {errors}"
        
        # Verify goals were generated
        assert len(goals_list) > 0, "Should generate goals in concurrent execution"