import pytest
from unittest.mock import MagicMock, patch
from goal_decomposition import GoalParser, DependencyResolver, ReadinessScorer, DecompositionPipeline, GoalNode

# ==================== Fixtures ====================

@pytest.fixture
def mock_knowledge_graph():
    """Create a mock knowledge graph for testing."""
    kg = MagicMock()
    kg.get_dependencies.return_value = []
    kg.get_components.return_value = []
    return kg

@pytest.fixture
def goal_parser():
    """Create a GoalParser instance."""
    return GoalParser()

@pytest.fixture
def dependency_resolver(mock_knowledge_graph):
    """Create a DependencyResolver with a mock knowledge graph."""
    return DependencyResolver(mock_knowledge_graph)

@pytest.fixture
def readiness_scorer():
    """Create a ReadinessScorer instance."""
    return ReadinessScorer()

@pytest.fixture
def decomposition_pipeline(mock_knowledge_graph):
    """Create a DecompositionPipeline with a mock knowledge graph."""
    return DecompositionPipeline(mock_knowledge_graph)

# ==================== Test Goal Parsing ====================

class TestGoalParsing:
    """Test parsing of various goal formats."""

    def test_parse_simple_goal(self, goal_parser):
        """Test parsing a simple, straightforward goal."""
        goal = "Build a web application"
        result = goal_parser.parse(goal)
        assert result is not None
        assert result.text == "Build a web application"
        assert result.complexity == "simple"

    def test_parse_complex_goal(self, goal_parser):
        """Test parsing a complex goal with multiple components."""
        goal = "Create an AI-powered recommendation system with user authentication and real-time analytics"
        result = goal_parser.parse(goal)
        assert result is not None
        assert len(result.sub_goals) >= 3

    def test_parse_goal_with_technical_terms(self, goal_parser):
        """Test parsing a goal containing technical terminology."""
        goal = "Implement REST API with OAuth2 authentication and PostgreSQL database"
        result = goal_parser.parse(goal)
        assert result is not None
        assert any("API" in sg for sg in result.sub_goals)

    def test_parse_goal_with_numbers(self, goal_parser):
        """Test parsing a goal that includes numerical specifications."""
        goal = "Deploy 5 microservices with 99.9% uptime"
        result = goal_parser.parse(goal)
        assert result is not None
        assert result.metrics is not None

    def test_parse_empty_goal(self, goal_parser):
        """Test parsing an empty goal string."""
        with pytest.raises(ValueError):
            goal_parser.parse("")

    def test_parse_goal_with_special_characters(self, goal_parser):
        """Test parsing a goal with special characters."""
        goal = "Develop a (secure) payment system - must handle $ transactions!"
        result = goal_parser.parse(goal)
        assert result is not None
        assert "payment" in result.text.lower()

# ==================== Test Dependency Resolution ====================

class TestDependencyResolution:
    """Test dependency resolution with mock knowledge graph."""

    def test_resolve_no_dependencies(self, dependency_resolver, mock_knowledge_graph):
        """Test resolving a goal with no dependencies."""
        mock_knowledge_graph.get_dependencies.return_value = []
        result = dependency_resolver.resolve("Simple goal")
        assert len(result) == 0

    def test_resolve_single_dependency(self, dependency_resolver, mock_knowledge_graph):
        """Test resolving a goal with a single dependency."""
        mock_knowledge_graph.get_dependencies.return_value = ["Database setup"]
        result = dependency_resolver.resolve("Build user login")
        assert len(result) == 1
        assert result[0] == "Database setup"

    def test_resolve_multiple_dependencies(self, dependency_resolver, mock_knowledge_graph):
        """Test resolving a goal with multiple dependencies."""
        mock_knowledge_graph.get_dependencies.return_value = ["Auth system", "Database", "API gateway"]
        result = dependency_resolver.resolve("Build full backend")
        assert len(result) == 3

    def test_resolve_nested_dependencies(self, dependency_resolver, mock_knowledge_graph):
        """Test resolving nested dependencies."""
        def get_deps_side_effect(goal):
            deps_map = {
                "Build full backend": ["Auth system", "Database"],
                "Auth system": ["User model", "JWT library"],
                "Database": ["Schema design"]
            }
            return deps_map.get(goal, [])
        mock_knowledge_graph.get_dependencies.side_effect = get_deps_side_effect
        result = dependency_resolver.resolve("Build full backend", recursive=True)
        assert len(result) >= 4

    def test_resolve_unknown_goal(self, dependency_resolver, mock_knowledge_graph):
        """Test resolving a goal not in the knowledge graph."""
        mock_knowledge_graph.get_dependencies.return_value = []
        result = dependency_resolver.resolve("Unknown goal")
        assert len(result) == 0

# ==================== Test Readiness Scoring ====================

class TestReadinessScoring:
    """Test readiness scoring functionality."""

    def test_score_ready_goal(self, readiness_scorer):
        """Test scoring a goal that is fully ready."""
        components = {"frontend": True, "backend": True, "database": True}
        score = readiness_scorer.score(components)
        assert score == 1.0

    def test_score_partially_ready_goal(self, readiness_scorer):
        """Test scoring a goal that is partially ready."""
        components = {"frontend": True, "backend": False, "database": True}
        score = readiness_scorer.score(components)
        assert 0.0 < score < 1.0

    def test_score_not_ready_goal(self, readiness_scorer):
        """Test scoring a goal with no ready components."""
        components = {"frontend": False, "backend": False, "database": False}
        score = readiness_scorer.score(components)
        assert score == 0.0

    def test_score_empty_components(self, readiness_scorer):
        """Test scoring with an empty components dictionary."""
        score = readiness_scorer.score({})
        assert score == 0.0

    def test_score_with_weights(self, readiness_scorer):
        """Test scoring with custom component weights."""
        components = {"critical": True, "optional": False}
        weights = {"critical": 0.8, "optional": 0.2}
        score = readiness_scorer.score(components, weights)
        assert score == 0.8

    def test_score_invalid_components(self, readiness_scorer):
        """Test scoring with invalid component data."""
        with pytest.raises(TypeError):
            readiness_scorer.score("invalid")

# ==================== Test Full Decomposition Pipeline ====================

class TestDecompositionPipeline:
    """Test full decomposition pipeline with known abstract goals."""

    def test_decompose_simple_goal(self, decomposition_pipeline, mock_knowledge_graph):
        """Test decomposing a simple, well-known goal."""
        mock_knowledge_graph.get_components.return_value = ["component1", "component2"]
        result = decomposition_pipeline.decompose("Build a simple website")
        assert result is not None
        assert len(result.sub_goals) > 0

    def test_decompose_complex_goal(self, decomposition_pipeline, mock_knowledge_graph):
        """Test decomposing a complex, multi-step goal."""
        mock_knowledge_graph.get_components.return_value = ["comp1", "comp2", "comp3", "comp4"]
        result = decomposition_pipeline.decompose("Create enterprise SaaS platform")
        assert result is not None
        assert len(result.sub_goals) >= 4

    def test_decompose_with_known_patterns(self, decomposition_pipeline, mock_knowledge_graph):
        """Test decomposition using known decomposition patterns."""
        mock_knowledge_graph.get_decomposition_pattern.return_value = ["step1", "step2", "step3"]
        result = decomposition_pipeline.decompose("Implement CI/CD pipeline")
        assert result is not None
        assert "step1" in [sg.text for sg in result.sub_goals]

    def test_pipeline_returns_goal_node(self, decomposition_pipeline, mock_knowledge_graph):
        """Test that the pipeline returns a proper GoalNode."""
        mock_knowledge_graph.get_components.return_value = ["comp1"]
        result = decomposition_pipeline.decompose("Test goal")
        assert isinstance(result, GoalNode)

    def test_pipeline_with_readiness_scoring(self, decomposition_pipeline, mock_knowledge_graph):
        """Test that the pipeline includes readiness scoring."""
        mock_knowledge_graph.get_components.return_value = ["comp1", "comp2"]
        mock_knowledge_graph.get_readiness.return_value = 0.5
        result = decomposition_pipeline.decompose("Goal with readiness")
        assert hasattr(result, 'readiness_score')
        assert result.readiness_score is not None

# ==================== Test Edge Cases ====================

class TestEdgeCases:
    """Test edge cases such as circular dependencies and missing components."""

    def test_circular_dependency_detection(self, dependency_resolver, mock_knowledge_graph):
        """Test detection of circular dependencies."""
        def circular_deps(goal):
            deps = {
                "A": ["B"],
                "B": ["C"],
                "C": ["A"]  # Circular dependency
            }
            return deps.get(goal, [])
        mock_knowledge_graph.get_dependencies.side_effect = circular_deps
        with pytest.raises(CircularDependencyError):
            dependency_resolver.resolve("A", recursive=True)

    def test_missing_components_handling(self, decomposition_pipeline, mock_knowledge_graph):
        """Test handling of missing components in the knowledge graph."""
        mock_knowledge_graph.get_components.return_value = None
        result = decomposition_pipeline.decompose("Goal with missing components")
        assert result is not None
        assert len(result.sub_goals) == 0

    def test_self_referential_goal(self, dependency_resolver, mock_knowledge_graph):
        """Test a goal that depends on itself."""
        mock_knowledge_graph.get_dependencies.return_value = ["Self-referential goal"]
        with pytest.raises(CircularDependencyError):
            dependency_resolver.resolve("Self-referential goal", recursive=True)

    def test_very_long_goal_string(self, goal_parser):
        """Test parsing an extremely long goal string."""
        long_goal = "Build " + "and ".join(["component{}".format(i) for i in range(100)])
        result = goal_parser.parse(long_goal)
        assert result is not None
        assert len(result.sub_goals) > 50

    def test_goal_with_no_components(self, decomposition_pipeline, mock_knowledge_graph):
        """Test decomposition when no components are available."""
        mock_knowledge_graph.get_components.return_value = []
        result = decomposition_pipeline.decompose("Goal with no components")
        assert result is not None
        assert len(result.sub_goals) == 0

    def test_invalid_goal_type(self, goal_parser):
        """Test parsing a non-string goal."""
        with pytest.raises(TypeError):
            goal_parser.parse(12345)

    def test_dependency_resolution_with_empty_graph(self, dependency_resolver, mock_knowledge_graph):
        """Test dependency resolution with an empty knowledge graph."""
        mock_knowledge_graph.get_dependencies.return_value = []
        result = dependency_resolver.resolve("Any goal")
        assert len(result) == 0

    def test_readiness_scoring_with_missing_components(self, readiness_scorer):
        """Test readiness scoring when some components are missing from the dictionary."""
        components = {"existing": True}
        score = readiness_scorer.score(components, required_components=["existing", "missing"])
        assert score < 1.0

    def test_pipeline_with_no_knowledge_graph(self):
        """Test pipeline initialization without a knowledge graph."""
        with pytest.raises(ValueError):
            DecompositionPipeline(None)