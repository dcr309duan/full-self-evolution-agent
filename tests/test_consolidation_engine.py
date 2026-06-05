"""Tests for the consolidation engine."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from typing import Dict, List, Set
import importlib

from core.consolidation_engine import (
    ConsolidationEngine,
    ModuleScore,
    ArchiveManager,
    RefactoringEngine,
    ConsolidationConfig
)
from core.evolution_engine import EvolutionEngine
from core.goal_selector import GoalSelector


@pytest.fixture
def mock_usage_data():
    """Fixture providing mock module usage data."""
    return {
        "module_a": {"calls": 100, "last_used": datetime.now(), "avg_response_time": 0.5},
        "module_b": {"calls": 5, "last_used": datetime.now() - timedelta(days=30), "avg_response_time": 2.0},
        "module_c": {"calls": 200, "last_used": datetime.now(), "avg_response_time": 0.3},
        "module_d": {"calls": 2, "last_used": datetime.now() - timedelta(days=60), "avg_response_time": 5.0},
        "evolution_engine": {"calls": 50, "last_used": datetime.now(), "avg_response_time": 0.8},
        "goal_selector": {"calls": 30, "last_used": datetime.now(), "avg_response_time": 0.6},
    }


@pytest.fixture
def mock_dependency_graph():
    """Fixture providing mock dependency graph."""
    return {
        "module_a": {"module_c", "module_b"},
        "module_b": {"module_d"},
        "module_c": {"module_a"},
        "module_d": set(),
        "evolution_engine": {"module_a", "module_c"},
        "goal_selector": {"module_a", "module_c"},
    }


@pytest.fixture
def consolidation_config():
    """Fixture providing consolidation configuration."""
    return ConsolidationConfig(
        scoring_threshold=10,
        archive_check_interval=timedelta(days=7),
        critical_modules={"evolution_engine", "goal_selector"},
        max_dependency_count=3,
        refactoring_batch_size=2
    )


@pytest.fixture
def consolidation_engine(consolidation_config):
    """Fixture providing a consolidation engine instance."""
    engine = ConsolidationEngine(config=consolidation_config)
    engine.usage_data = {}
    engine.dependency_graph = {}
    engine.archived_modules = set()
    engine.active_modules = set()
    return engine


class TestScoring:
    """Test scoring correctly computes utility from mock usage data."""

    def test_high_usage_module_scores_high(self, consolidation_engine, mock_usage_data):
        """Test that frequently used modules get high scores."""
        consolidation_engine.usage_data = mock_usage_data
        scores = consolidation_engine.score_modules()
        
        # module_c has high calls and low response time
        assert scores["module_c"] > 50, "High usage module should score high"

    def test_low_usage_module_scores_low(self, consolidation_engine, mock_usage_data):
        """Test that infrequently used modules get low scores."""
        consolidation_engine.usage_data = mock_usage_data
        scores = consolidation_engine.score_modules()
        
        # module_d has very few calls and high response time
        assert scores["module_d"] < 10, "Low usage module should score low"

    def test_scoring_considers_recency(self, consolidation_engine, mock_usage_data):
        """Test that recency of usage affects scoring."""
        consolidation_engine.usage_data = mock_usage_data
        scores = consolidation_engine.score_modules()
        
        # module_b was used 30 days ago, should score lower than module_a used now
        assert scores["module_b"] < scores["module_a"], "Recent usage should increase score"

    def test_scoring_considers_response_time(self, consolidation_engine, mock_usage_data):
        """Test that response time affects scoring."""
        consolidation_engine.usage_data = mock_usage_data
        scores = consolidation_engine.score_modules()
        
        # module_a has lower response time than module_b
        assert scores["module_a"] > scores["module_b"], "Lower response time should increase score"


class TestArchivingThreshold:
    """Test that modules below threshold are archived."""

    def test_modules_below_threshold_archived(self, consolidation_engine, mock_usage_data):
        """Test that modules scoring below threshold get archived."""
        consolidation_engine.usage_data = mock_usage_data
        consolidation_engine.active_modules = set(mock_usage_data.keys())
        
        archived = consolidation_engine.archive_low_scoring_modules()
        
        # module_d should be archived (very low usage)
        assert "module_d" in archived, "Low scoring module should be archived"

    def test_modules_above_threshold_not_archived(self, consolidation_engine, mock_usage_data):
        """Test that modules scoring above threshold remain active."""
        consolidation_engine.usage_data = mock_usage_data
        consolidation_engine.active_modules = set(mock_usage_data.keys())
        
        archived = consolidation_engine.archive_low_scoring_modules()
        
        # module_c should NOT be archived (high usage)
        assert "module_c" not in archived, "High scoring module should not be archived"

    def test_threshold_respects_config(self, consolidation_engine, mock_usage_data):
        """Test that archiving respects the configured threshold."""
        consolidation_engine.usage_data = mock_usage_data
        consolidation_engine.active_modules = set(mock_usage_data.keys())
        
        # Set a very high threshold to archive more modules
        consolidation_engine.config.scoring_threshold = 100
        archived = consolidation_engine.archive_low_scoring_modules()
        
        # All non-critical modules should be archived with high threshold
        assert "module_a" in archived, "Module should be archived with high threshold"


class TestArchivingRemovesImports:
    """Test that archiving removes module from active imports."""

    def test_archived_module_removed_from_active(self, consolidation_engine, mock_usage_data):
        """Test that archived module is no longer in active imports."""
        consolidation_engine.usage_data = mock_usage_data
        consolidation_engine.active_modules = {"module_a", "module_b", "module_d"}
        
        consolidation_engine.archive_low_scoring_modules()
        
        assert "module_d" not in consolidation_engine.active_modules, "Archived module should be removed from active"

    def test_archived_module_moved_to_archive(self, consolidation_engine, mock_usage_data):
        """Test that archived module is moved to archive storage."""
        consolidation_engine.usage_data = mock_usage_data
        consolidation_engine.active_modules = {"module_a", "module_b", "module_d"}
        
        consolidation_engine.archive_low_scoring_modules()
        
        assert "module_d" in consolidation_engine.archived_modules, "Archived module should be in archive"

    def test_non_archived_modules_remain_active(self, consolidation_engine, mock_usage_data):
        """Test that non-archived modules remain in active imports."""
        consolidation_engine.usage_data = mock_usage_data
        consolidation_engine.active_modules = {"module_a", "module_b", "module_c", "module_d"}
        
        consolidation_engine.archive_low_scoring_modules()
        
        assert "module_a" in consolidation_engine.active_modules, "Non-archived module should remain active"
        assert "module_c" in consolidation_engine.active_modules, "Non-archived module should remain active"


class TestRefactoring:
    """Test that refactoring reduces dependency count in core pathways."""

    def test_refactoring_reduces_dependencies(self, consolidation_engine, mock_dependency_graph):
        """Test that refactoring reduces the number of dependencies."""
        consolidation_engine.dependency_graph = mock_dependency_graph
        initial_deps = sum(len(deps) for deps in mock_dependency_graph.values())
        
        consolidation_engine.refactor_core_pathways()
        final_deps = sum(len(deps) for deps in consolidation_engine.dependency_graph.values())
        
        assert final_deps < initial_deps, "Refactoring should reduce total dependencies"

    def test_refactoring_merges_duplicate_paths(self, consolidation_engine, mock_dependency_graph):
        """Test that refactoring merges duplicate dependency paths."""
        consolidation_engine.dependency_graph = mock_dependency_graph
        
        consolidation_engine.refactor_core_pathways()
        
        # Check that module_a and module_c dependencies are consolidated
        assert len(consolidation_engine.dependency_graph.get("module_a", set())) <= 2, "Should merge duplicate paths"

    def test_refactoring_preserves_critical_paths(self, consolidation_engine, mock_dependency_graph):
        """Test that refactoring preserves critical dependency paths."""
        consolidation_engine.dependency_graph = mock_dependency_graph
        
        consolidation_engine.refactor_core_pathways()
        
        # evolution_engine should still have access to its dependencies
        assert "module_a" in consolidation_engine.dependency_graph.get("evolution_engine", set()), "Critical path should be preserved"
        assert "module_c" in consolidation_engine.dependency_graph.get("evolution_engine", set()), "Critical path should be preserved"


class TestConsolidationCycles:
    """Test that consolidation runs on correct cycle intervals."""

    def test_consolidation_runs_on_schedule(self, consolidation_engine):
        """Test that consolidation runs at the configured interval."""
        with patch.object(consolidation_engine, 'should_run_consolidation') as mock_should_run:
            mock_should_run.return_value = True
            result = consolidation_engine.run_consolidation_cycle()
            assert result, "Consolidation should run when interval is met"

    def test_consolidation_skips_before_interval(self, consolidation_engine):
        """Test that consolidation is skipped before the interval has passed."""
        with patch.object(consolidation_engine, 'should_run_consolidation') as mock_should_run:
            mock_should_run.return_value = False
            result = consolidation_engine.run_consolidation_cycle()
            assert not result, "Consolidation should not run before interval"

    def test_consolidation_resets_timer_after_run(self, consolidation_engine):
        """Test that the consolidation timer resets after a run."""
        with patch.object(consolidation_engine, 'should_run_consolidation') as mock_should_run:
            mock_should_run.return_value = True
            initial_last_run = consolidation_engine.last_consolidation_run
            
            consolidation_engine.run_consolidation_cycle()
            
            assert consolidation_engine.last_consolidation_run > initial_last_run, "Timer should reset after run"


class TestRollbackRestore:
    """Test rollback/restore from archive works."""

    def test_restore_archived_module(self, consolidation_engine):
        """Test that an archived module can be restored."""
        consolidation_engine.archived_modules = {"module_d"}
        consolidation_engine.archive_data = {
            "module_d": {"code": "def module_d_func(): pass", "metadata": {}}
        }
        
        consolidation_engine.restore_module("module_d")
        
        assert "module_d" not in consolidation_engine.archived_modules, "Restored module should be removed from archive"
        assert "module_d" in consolidation_engine.active_modules, "Restored module should be in active modules"

    def test_rollback_restores_previous_state(self, consolidation_engine):
        """Test that rollback restores the system to its previous state."""
        # Simulate a consolidation that archived module_d
        consolidation_engine.active_modules = {"module_a", "module_b", "module_c"}
        consolidation_engine.archived_modules = {"module_d"}
        consolidation_engine.rollback_snapshots = [
            {"active_modules": {"module_a", "module_b", "module_c", "module_d"}, "archived_modules": set()}
        ]
        
        consolidation_engine.rollback()
        
        assert "module_d" in consolidation_engine.active_modules, "Rollback should restore module_d to active"
        assert "module_d" not in consolidation_engine.archived_modules, "Rollback should remove module_d from archive"

    def test_rollback_preserves_other_modules(self, consolidation_engine):
        """Test that rollback doesn't affect modules that weren't changed."""
        consolidation_engine.active_modules = {"module_a", "module_b", "module_c"}
        consolidation_engine.archived_modules = {"module_d"}
        consolidation_engine.rollback_snapshots = [
            {"active_modules": {"module_a", "module_b", "module_c", "module_d"}, "archived_modules": set()}
        ]
        
        consolidation_engine.rollback()
        
        assert "module_a" in consolidation_engine.active_modules, "Rollback should preserve module_a"
        assert "module_b" in consolidation_engine.active_modules, "Rollback should preserve module_b"
        assert "module_c" in consolidation_engine.active_modules, "Rollback should preserve module_c"


class TestCriticalModules:
    """Test that critical modules cannot be archived even if low-scoring."""

    def test_evolution_engine_not_archived(self, consolidation_engine, mock_usage_data):
        """Test that evolution_engine is never archived."""
        consolidation_engine.usage_data = mock_usage_data
        consolidation_engine.active_modules = set(mock_usage_data.keys())
        
        # Even if evolution_engine scores low, it should not be archived
        consolidation_engine.config.scoring_threshold = 100  # High threshold
        archived = consolidation_engine.archive_low_scoring_modules()
        
        assert "evolution_engine" not in archived, "Critical module evolution_engine should not be archived"

    def test_goal_selector_not_archived(self, consolidation_engine, mock_usage_data):
        """Test that goal_selector is never archived."""
        consolidation_engine.usage_data = mock_usage_data
        consolidation_engine.active_modules = set(mock_usage_data.keys())
        
        # Even if goal_selector scores low, it should not be archived
        consolidation_engine.config.scoring_threshold = 100  # High threshold
        archived = consolidation_engine.archive_low_scoring_modules()
        
        assert "goal_selector" not in archived, "Critical module goal_selector should not be archived"

    def test_critical_modules_remain_active(self, consolidation_engine, mock_usage_data):
        """Test that critical modules remain in active imports regardless of score."""
        consolidation_engine.usage_data = mock_usage_data
        consolidation_engine.active_modules = set(mock_usage_data.keys())
        
        consolidation_engine.archive_low_scoring_modules()
        
        assert "evolution_engine" in consolidation_engine.active_modules, "Critical module should remain active"
        assert "goal_selector" in consolidation_engine.active_modules, "Critical module should remain active"

    def test_critical_modules_in_archive_restored(self, consolidation_engine):
        """Test that if critical modules are somehow in archive, they get restored."""
        consolidation_engine.archived_modules = {"evolution_engine", "goal_selector", "module_d"}
        consolidation_engine.active_modules = {"module_a", "module_b", "module_c"}
        
        consolidation_engine.restore_critical_modules()
        
        assert "evolution_engine" not in consolidation_engine.archived_modules, "Critical module should be restored from archive"
        assert "goal_selector" not in consolidation_engine.archived_modules, "Critical module should be restored from archive"
        assert "evolution_engine" in consolidation_engine.active_modules, "Critical module should be active"
        assert "goal_selector" in consolidation_engine.active_modules, "Critical module should be active"